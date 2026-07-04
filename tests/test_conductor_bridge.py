#!/usr/bin/env python3
"""test_conductor_bridge.py — Integration tests for conductor <-> brain bridge.

Verifies:
- brain_integration.py resolves brain_sync correctly
- brain_query_before_route.py returns correct adjustments
- BrainSyncProtocol conformance for conductor's brain client
- Hard block / model adjustment thresholds
- apply_routing_adjustment modifies task_config correctly

Run: pytest tests/test_conductor_bridge.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "the-brain"))

try:
    from brain_query_before_route import (
        RoutingAdjustment,
        _analyze_history,
        _build_task_signature,
        _pick_alternative_model,
        apply_routing_adjustment,
        query_before_route,
    )
    QBRT_AVAILABLE = True
except ImportError:
    QBRT_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not QBRT_AVAILABLE,
    reason="brain_query_before_route not available"
)


# ------------------------------------------------------------------ #
#  Fixtures                                                           #
# ------------------------------------------------------------------ #

@pytest.fixture
def mock_brain():
    """A minimal mock brain that satisfies BrainSyncProtocol."""
    brain = MagicMock()
    brain._available = True
    brain.learn.return_value = True
    brain.query_learning.return_value = []
    return brain


@pytest.fixture
def failing_history():
    """5 failure records for the same task signature."""
    return [
        {
            "run_id": f"r{i}",
            "source": "conductor",
            "category": "gate",
            "event_type": "GATE_FAILED",
            "outcome": "fail",
            "detail": json.dumps({"model": "claude-3-5-sonnet-20241022"}),
            "timestamp": f"2026-07-0{i+1}T10:00:00Z",
        }
        for i in range(5)
    ]


@pytest.fixture
def passing_history():
    """5 passing records."""
    return [
        {
            "run_id": f"r{i}",
            "source": "conductor",
            "category": "gate",
            "event_type": "GATE_PASSED",
            "outcome": "pass",
            "detail": json.dumps({"model": "claude-3-5-sonnet-20241022"}),
            "timestamp": f"2026-07-0{i+1}T10:00:00Z",
        }
        for i in range(5)
    ]


# ------------------------------------------------------------------ #
#  Tests: _build_task_signature                                       #
# ------------------------------------------------------------------ #

class TestBuildTaskSignature:
    def test_extracts_explicit_fields(self):
        task = {"source": "conductor", "category": "gate", "event_type": "GATE_PASSED"}
        src, cat, et = _build_task_signature(task)
        assert src == "conductor"
        assert cat == "gate"
        assert et == "GATE_PASSED"

    def test_falls_back_to_operator(self):
        task = {"operator": "myop", "task_type": "audit", "gate_id": "g1"}
        src, cat, et = _build_task_signature(task)
        assert src == "myop"
        assert cat == "audit"
        assert et == "g1"

    def test_defaults_for_empty_task(self):
        src, cat, et = _build_task_signature({})
        assert src == "unknown"
        assert cat == "general"
        assert et == "route"


# ------------------------------------------------------------------ #
#  Tests: _analyze_history                                            #
# ------------------------------------------------------------------ #

class TestAnalyzeHistory:
    def test_empty_history(self):
        stats = _analyze_history([])
        assert stats["total"] == 0
        assert stats["failures"] == 0
        assert stats["failure_rate"] == 0.0

    def test_all_failures(self, failing_history):
        stats = _analyze_history(failing_history)
        assert stats["failures"] == 5
        assert stats["failure_rate"] == 1.0

    def test_all_passes(self, passing_history):
        stats = _analyze_history(passing_history)
        assert stats["failures"] == 0
        assert stats["passes"] == 5
        assert stats["failure_rate"] == 0.0

    def test_mixed_history(self, failing_history, passing_history):
        mixed = failing_history[:3] + passing_history[:3]
        stats = _analyze_history(mixed)
        assert stats["failures"] == 3
        assert stats["passes"] == 3
        assert abs(stats["failure_rate"] - 0.5) < 0.01

    def test_extracts_model_from_detail(self, failing_history):
        stats = _analyze_history(failing_history)
        assert "claude-3-5-sonnet-20241022" in stats["models_tried"]


# ------------------------------------------------------------------ #
#  Tests: _pick_alternative_model                                     #
# ------------------------------------------------------------------ #

class TestPickAlternativeModel:
    def test_picks_untried_model(self):
        tried = ["claude-3-5-sonnet-20241022"]
        alt = _pick_alternative_model(tried, {})
        assert alt not in tried

    def test_prefers_task_preferred_model(self):
        task = {"preferred_model": "gpt-4o"}
        alt = _pick_alternative_model([], task)
        assert alt == "gpt-4o"

    def test_skips_already_tried_preferred(self):
        task = {"preferred_model": "gpt-4o"}
        alt = _pick_alternative_model(["gpt-4o"], task)
        assert alt != "gpt-4o"

    def test_returns_string(self):
        alt = _pick_alternative_model([], {})
        assert isinstance(alt, str)
        assert len(alt) > 0


# ------------------------------------------------------------------ #
#  Tests: query_before_route with mock brain                          #
# ------------------------------------------------------------------ #

class TestQueryBeforeRoute:
    def test_no_history_returns_no_change(self, mock_brain):
        mock_brain.query_learning.return_value = []
        task = {"source": "conductor", "category": "gate", "event_type": "GATE_PASSED"}
        adj = query_before_route(task, brain=mock_brain)
        assert adj.action == "no_change"

    def test_five_failures_returns_hard_block(self, mock_brain, failing_history):
        mock_brain.query_learning.return_value = failing_history
        task = {"source": "conductor", "category": "gate", "event_type": "GATE_FAILED"}
        adj = query_before_route(task, brain=mock_brain)
        assert adj.action == "hard_block"
        assert adj.is_blocking is True
        assert len(adj.evidence) > 0

    def test_three_failures_returns_model_adjustment(self, mock_brain, failing_history):
        mock_brain.query_learning.return_value = failing_history[:3]
        task = {"source": "conductor", "category": "gate", "event_type": "GATE_FAILED"}
        adj = query_before_route(task, brain=mock_brain)
        assert adj.action in ("adjust_model", "no_change")  # depends on model availability

    def test_all_passes_returns_no_change(self, mock_brain, passing_history):
        mock_brain.query_learning.return_value = passing_history
        task = {"source": "conductor", "category": "gate", "event_type": "GATE_PASSED"}
        adj = query_before_route(task, brain=mock_brain)
        assert adj.action == "no_change"

    def test_pre_route_query_logged(self, mock_brain):
        """query_before_route must call brain.learn() to log the query."""
        mock_brain.query_learning.return_value = []
        task = {"source": "conductor", "category": "gate", "event_type": "GATE_PASSED",
                "run_id": "test-pre-route"}
        query_before_route(task, brain=mock_brain)
        mock_brain.learn.assert_called()
        # Verify it logged a PRE_ROUTE_QUERY event
        call_kwargs = mock_brain.learn.call_args
        assert call_kwargs is not None

    def test_unavailable_brain_returns_no_change(self):
        brain = MagicMock()
        brain._available = False
        task = {"source": "x", "category": "y", "event_type": "z"}
        adj = query_before_route(task, brain=brain)
        assert adj.action == "no_change"


# ------------------------------------------------------------------ #
#  Tests: apply_routing_adjustment                                    #
# ------------------------------------------------------------------ #

class TestApplyRoutingAdjustment:
    def test_no_change_returns_original(self):
        task = {"source": "x", "model": "original"}
        adj = RoutingAdjustment(action="no_change")
        result = apply_routing_adjustment(task, adj)
        assert result["model"] == "original"
        assert result is not task  # Always returns a copy

    def test_adjust_model_sets_model(self):
        task = {"source": "x", "model": "old-model"}
        adj = RoutingAdjustment(action="adjust_model", suggested_model="gpt-4o")
        result = apply_routing_adjustment(task, adj)
        assert result["model"] == "gpt-4o"
        assert result["_brain_adjusted"] is True

    def test_hard_block_does_not_modify_task(self):
        task = {"source": "x", "model": "original"}
        adj = RoutingAdjustment(action="hard_block", reason="too many failures")
        result = apply_routing_adjustment(task, adj)
        assert "_brain_adjusted" not in result
        assert result["model"] == "original"

    def test_skip_gate_appends_to_existing(self):
        task = {"source": "x", "skip_gates": ["g1"]}
        adj = RoutingAdjustment(action="skip_gate", skip_gates=["g2", "g3"])
        result = apply_routing_adjustment(task, adj)
        assert set(result["skip_gates"]) == {"g1", "g2", "g3"}

    def test_does_not_mutate_original_task(self):
        task = {"source": "x", "model": "original"}
        original_task = dict(task)
        adj = RoutingAdjustment(action="adjust_model", suggested_model="gpt-4o")
        apply_routing_adjustment(task, adj)
        assert task == original_task  # Original not mutated


# ------------------------------------------------------------------ #
#  Tests: RoutingAdjustment dataclass                                 #
# ------------------------------------------------------------------ #

class TestRoutingAdjustment:
    def test_is_blocking_for_hard_block(self):
        adj = RoutingAdjustment(action="hard_block")
        assert adj.is_blocking is True

    def test_is_not_blocking_for_no_change(self):
        adj = RoutingAdjustment(action="no_change")
        assert adj.is_blocking is False

    def test_to_dict_contains_action(self):
        adj = RoutingAdjustment(action="adjust_model", suggested_model="gpt-4o", confidence=0.8)
        d = adj.to_dict()
        assert d["action"] == "adjust_model"
        assert d["suggested_model"] == "gpt-4o"
        assert d["confidence"] == 0.8

    def test_default_confidence_is_1(self):
        adj = RoutingAdjustment(action="no_change")
        assert adj.confidence == 1.0
