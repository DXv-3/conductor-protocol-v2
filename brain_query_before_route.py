#!/usr/bin/env python3
"""brain_query_before_route.py — Query the brain before routing any task.

This module implements the intelligence layer in conductor-protocol-v2.
It is called at the TOP of inspect_and_route() before any gate checks.

The problem it solves:
    The conductor previously wrote gate outcomes to the brain but never
    read from it before routing. This created a write-only log that
    accumulated intelligence that was never used. This module closes that loop.

What it does:
    1. Queries learning_memory for the last N events matching this task's
       signature (source + category + event_type combination)
    2. Detects repeated failure patterns (3+ failures in recent history)
    3. Returns a routing adjustment: skip, adjust_model, adjust_gate_order,
       hard_block, or no_change
    4. Logs the pre-route query itself as a learning event

Integration into conductor:
    # At the TOP of inspect_and_route(), before gate checks:
    from brain_query_before_route import query_before_route, apply_routing_adjustment

    adjustment = query_before_route(task_config, brain)
    if adjustment.action == "hard_block":
        return {"blocked": True, "reason": adjustment.reason, "learned_from": adjustment.evidence}
    task_config = apply_routing_adjustment(task_config, adjustment)
    # ... then proceed with gate checks as normal
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------ #
#  Result types                                                       #
# ------------------------------------------------------------------ #

@dataclass
class RoutingAdjustment:
    """What the brain recommends before this task is routed."""

    action: str
    """One of: no_change | adjust_model | adjust_gate_order | skip_gate | hard_block"""

    reason: str = ""
    """Human-readable explanation of why this adjustment was made."""

    evidence: list[dict] = field(default_factory=list)
    """The learning events that triggered this adjustment (for transparency)."""

    suggested_model: str = ""
    """If action=adjust_model, the model to use instead."""

    skip_gates: list[str] = field(default_factory=list)
    """If action=skip_gate, these gate IDs should be skipped."""

    adjusted_gate_order: list[str] = field(default_factory=list)
    """If action=adjust_gate_order, reordered gate list."""

    confidence: float = 1.0
    """0.0-1.0: how confident the brain is in this recommendation."""

    @property
    def is_blocking(self) -> bool:
        return self.action == "hard_block"

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence_count": len(self.evidence),
            "suggested_model": self.suggested_model,
            "skip_gates": self.skip_gates,
            "adjusted_gate_order": self.adjusted_gate_order,
        }


# ------------------------------------------------------------------ #
#  Core query logic                                                   #
# ------------------------------------------------------------------ #

# Thresholds — tune these based on your failure data
FAILURE_HARD_BLOCK_THRESHOLD = 5    # 5+ failures = hard block
FAILURE_ADJUST_THRESHOLD = 3        # 3+ failures = routing adjustment
LOOKBACK_LIMIT = 20                 # How many past events to analyze
RECENT_WINDOW_DAYS = 14             # Only look at last 2 weeks


def _build_task_signature(task_config: dict) -> tuple[str, str, str]:
    """Extract the (source, category, event_type) signature from a task config.

    These three fields together uniquely identify a 'type' of task.
    A repeated failure on the same signature is what triggers adjustment.
    """
    source = (
        task_config.get("source")
        or task_config.get("operator")
        or task_config.get("repo")
        or "unknown"
    )
    category = (
        task_config.get("category")
        or task_config.get("task_type")
        or task_config.get("type")
        or "general"
    )
    event_type = (
        task_config.get("event_type")
        or task_config.get("gate_id")
        or task_config.get("action")
        or "route"
    )
    return source, category, event_type


def _analyze_history(rows: list[dict]) -> dict:
    """Analyze a list of learning events and return failure statistics."""
    total = len(rows)
    if total == 0:
        return {"total": 0, "failures": 0, "passes": 0, "failure_rate": 0.0,
                "last_outcome": None, "last_model": None, "models_tried": []}

    failures = [r for r in rows if (r.get("outcome") or "").lower() in ("fail", "failed", "error", "blocked")]
    passes = [r for r in rows if (r.get("outcome") or "").lower() in ("pass", "passed", "success", "ok")]

    models_tried = []
    for r in rows:
        detail = r.get("detail") or ""
        try:
            d = json.loads(detail)
            if m := d.get("model"):
                if m not in models_tried:
                    models_tried.append(m)
        except (json.JSONDecodeError, AttributeError):
            pass

    last_model = None
    try:
        last_model = json.loads(rows[0].get("detail") or "{}").get("model")
    except (json.JSONDecodeError, AttributeError, IndexError):
        pass

    return {
        "total": total,
        "failures": len(failures),
        "passes": len(passes),
        "failure_rate": len(failures) / total,
        "last_outcome": rows[0].get("outcome") if rows else None,
        "last_model": last_model,
        "models_tried": models_tried,
    }


def _pick_alternative_model(models_tried: list[str], task_config: dict) -> str:
    """Suggest an alternative model that hasn't been tried yet."""
    # Ordered fallback chain
    MODEL_FALLBACK_CHAIN = [
        "claude-3-5-sonnet-20241022",
        "gpt-4o",
        "claude-3-opus-20240229",
        "deepseek-chat",
        "gemini-1.5-pro",
    ]

    # Check if task_config specifies a preference
    preferred = task_config.get("preferred_model") or task_config.get("model")
    if preferred and preferred not in models_tried:
        return preferred

    for m in MODEL_FALLBACK_CHAIN:
        if m not in models_tried:
            return m

    # All known models have been tried; reset to best default
    return MODEL_FALLBACK_CHAIN[0]


def query_before_route(
    task_config: dict,
    brain=None,
    db_path: str | None = None,
) -> RoutingAdjustment:
    """Query the brain and return a routing adjustment for this task.

    Args:
        task_config: The task dict being routed (same object passed to inspect_and_route)
        brain: Optional BrainSync instance. If None, creates one.
        db_path: Optional explicit db path.

    Returns:
        RoutingAdjustment with action and evidence.
    """
    # Import here to avoid circular dep; conductor imports us, not vice versa
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from brain_integration import get_brain_sync
        b = brain or get_brain_sync(db_path)
    except ImportError:
        # Graceful degradation: if brain_integration not available, no adjustment
        return RoutingAdjustment(action="no_change", reason="brain_integration not available")

    if b is None or not getattr(b, '_available', False):
        return RoutingAdjustment(action="no_change", reason="brain.db not available")

    source, category, event_type = _build_task_signature(task_config)

    # Query recent history for this task signature
    rows = b.query_learning(
        source=source,
        outcome=None,  # All outcomes, we'll filter ourselves
        limit=LOOKBACK_LIMIT,
    )

    # Filter to matching category + event_type
    matching = [
        r for r in rows
        if r.get("category") == category and r.get("event_type") == event_type
    ]

    stats = _analyze_history(matching)

    # Log that we did a pre-route query
    import uuid
    pre_route_run_id = task_config.get("run_id") or str(uuid.uuid4())[:8]
    b.learn(
        run_id=pre_route_run_id,
        source="conductor:brain_query_before_route",
        category=category,
        event_type="PRE_ROUTE_QUERY",
        detail=json.dumps({
            "task_signature": f"{source}:{category}:{event_type}",
            "history_found": stats["total"],
            "failures_in_history": stats["failures"],
            "failure_rate": stats["failure_rate"],
        }),
        outcome="info",
    )

    # Decision logic
    num_failures = stats["failures"]

    if num_failures == 0 or stats["total"] < 2:
        return RoutingAdjustment(
            action="no_change",
            reason="No concerning failure pattern found.",
            evidence=matching[:3],
            confidence=1.0,
        )

    if num_failures >= FAILURE_HARD_BLOCK_THRESHOLD:
        reason = (
            f"Hard block: task signature '{source}:{category}:{event_type}' has failed "
            f"{num_failures} times in the last {stats['total']} runs "
            f"({stats['failure_rate']:.0%} failure rate). "
            f"Manual review required before re-routing."
        )
        return RoutingAdjustment(
            action="hard_block",
            reason=reason,
            evidence=matching[:5],
            confidence=0.95,
        )

    if num_failures >= FAILURE_ADJUST_THRESHOLD:
        alt_model = _pick_alternative_model(stats["models_tried"], task_config)

        if alt_model and alt_model != stats["last_model"]:
            reason = (
                f"Model adjustment: {num_failures} failures detected for "
                f"'{source}:{category}:{event_type}'. "
                f"Last model: {stats['last_model'] or 'unknown'}. "
                f"Trying: {alt_model}."
            )
            return RoutingAdjustment(
                action="adjust_model",
                reason=reason,
                evidence=matching[:5],
                suggested_model=alt_model,
                confidence=0.8,
            )
        else:
            reason = (
                f"Pattern detected: {num_failures} failures for "
                f"'{source}:{category}:{event_type}'. "
                f"No untried model available. Consider manual review."
            )
            return RoutingAdjustment(
                action="no_change",
                reason=reason,
                evidence=matching[:5],
                confidence=0.6,
            )

    # 1-2 failures: note it, no adjustment yet
    return RoutingAdjustment(
        action="no_change",
        reason=f"Early failure signal ({num_failures} failures). Monitoring.",
        evidence=matching[:3],
        confidence=0.9,
    )


def apply_routing_adjustment(task_config: dict, adjustment: RoutingAdjustment) -> dict:
    """Apply a routing adjustment to task_config and return the modified config.

    Does not mutate the original dict.
    """
    if adjustment.action == "no_change" or adjustment.action == "hard_block":
        return task_config

    config = dict(task_config)  # Shallow copy

    if adjustment.action == "adjust_model" and adjustment.suggested_model:
        config["model"] = adjustment.suggested_model
        config["_brain_adjusted"] = True
        config["_brain_adjustment_reason"] = adjustment.reason

    elif adjustment.action == "adjust_gate_order" and adjustment.adjusted_gate_order:
        config["gate_order"] = adjustment.adjusted_gate_order
        config["_brain_adjusted"] = True
        config["_brain_adjustment_reason"] = adjustment.reason

    elif adjustment.action == "skip_gate" and adjustment.skip_gates:
        existing_skip = config.get("skip_gates", [])
        config["skip_gates"] = list(set(existing_skip + adjustment.skip_gates))
        config["_brain_adjusted"] = True
        config["_brain_adjustment_reason"] = adjustment.reason

    return config


# ------------------------------------------------------------------ #
#  CLI for manual testing                                            #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test brain_query_before_route")
    parser.add_argument("--source", default="test_source")
    parser.add_argument("--category", default="test_category")
    parser.add_argument("--event-type", default="test_event")
    args = parser.parse_args()

    task = {"source": args.source, "category": args.category, "event_type": args.event_type}
    adj = query_before_route(task)
    print(f"Task: {task}")
    print(f"Adjustment: {adj.action}")
    print(f"Reason: {adj.reason}")
    print(f"Confidence: {adj.confidence}")
    print(f"Evidence count: {len(adj.evidence)}")
    if adj.suggested_model:
        print(f"Suggested model: {adj.suggested_model}")
    if adj.is_blocking:
        print("HARD BLOCK — this task would be blocked")
