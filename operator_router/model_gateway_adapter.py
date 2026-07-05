"""
operator_router/model_gateway_adapter.py
-----------------------------------------
The canonical LLM call interface for conductor-protocol-v2.

Replaces any direct model API calls scattered across the conductor with
a single entry point that routes through zai-wrap's ModelRouter, records
every inference as a provenance artifact on the harmony bus, and falls
back gracefully if zai-wrap is not on the path.

Usage:
    from operator_router.model_gateway_adapter import ConductorModelGateway

    gw = ConductorModelGateway()
    result = gw.call(prompt, task_type="reasoning", operator_id="op-123")
    print(result.content)   # the LLM response text
    print(result.model)     # which model actually answered
    print(result.latency_ms)

Or use the module-level singleton:
    from operator_router.model_gateway_adapter import call_for_conductor
    text = call_for_conductor(prompt, task_type="code", operator_id="op-456")
"""

import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------

@dataclass
class ConductorModelResponse:
    content: str
    model: str
    task_type: str
    operator_id: str
    latency_ms: float
    success: bool
    error: Optional[str] = None
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tokens_used: int = 0
    provider: str = ""


# ---------------------------------------------------------------------------
# Gateway class
# ---------------------------------------------------------------------------

class ConductorModelGateway:
    """
    Wraps zai-wrap ModelRouter with conductor-specific concerns:
      - operator_id tagging on every call
      - harmony bus publish of every inference event
      - per-call latency tracking
      - graceful fallback to direct Anthropic SDK if ModelRouter unavailable
    """

    # task_type → (primary_model, fallback_model)
    TASK_DEFAULTS = {
        "code":      ("deepseek/deepseek-coder",       "claude/claude-sonnet-4-5"),
        "reasoning": ("claude/claude-opus-4-5",         "deepseek/deepseek-r1"),
        "fast":      ("deepseek/deepseek-chat",          "claude/claude-haiku-4-5"),
        "creative":  ("claude/claude-sonnet-4-5",        "deepseek/deepseek-chat"),
        "vision":    ("claude/claude-opus-4-5",          "grok_api/grok-3"),
        "routing":   ("claude/claude-haiku-4-5",         "deepseek/deepseek-chat"),
        "audit":     ("claude/claude-sonnet-4-5",        "deepseek/deepseek-r1"),
        "forensics": ("claude/claude-opus-4-5",          "deepseek/deepseek-r1"),
    }

    def __init__(self):
        self._router = None
        self._router_available = False
        self._harmony_publisher = None
        self._init_router()
        self._init_harmony()
        self._usage: Dict[str, Dict] = {}

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def _init_router(self):
        zai_path = os.getenv("ZAI_WRAP_PATH", "../zai-wrap")
        sys.path.insert(0, zai_path)
        try:
            from model_gateway import ModelRouter  # noqa
            self._router = ModelRouter()
            self._router_available = True
            logger.info("ConductorModelGateway: ModelRouter loaded from %s", zai_path)
        except ImportError:
            logger.warning(
                "ConductorModelGateway: zai-wrap not found at %s — using direct fallback", zai_path
            )
        except Exception as exc:
            logger.warning("ConductorModelGateway: ModelRouter init failed: %s", exc)

    def _init_harmony(self):
        matrix_path = os.getenv("MATRIX_PATH", "../MATRIX")
        sys.path.insert(0, matrix_path)
        try:
            from harmony_publisher_base import HarmonyPublisher  # noqa
            self._harmony_publisher = HarmonyPublisher()
            logger.info("ConductorModelGateway: HarmonyPublisher connected")
        except Exception:
            pass  # harmony is optional

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(
        self,
        prompt: str,
        task_type: str = "reasoning",
        operator_id: str = "",
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> ConductorModelResponse:
        """Route an LLM call through ModelRouter with conductor provenance tagging."""
        start = time.perf_counter()
        call_id = str(uuid.uuid4())
        error = None
        content = ""
        model_used = model or self.TASK_DEFAULTS.get(task_type, ("claude/claude-sonnet-4-5",))[0]
        provider = model_used.split("/")[0] if "/" in model_used else "unknown"
        success = False

        # --- Attempt 1: ModelRouter (preferred) ---
        if self._router_available:
            try:
                if model:
                    resp = self._router.call(
                        prompt=prompt, model=model, system=system,
                        max_tokens=max_tokens, temperature=temperature,
                    )
                else:
                    resp = self._router.route(
                        prompt=prompt, task_type=task_type, system=system,
                        max_tokens=max_tokens, temperature=temperature,
                    )
                content = resp.content
                model_used = getattr(resp, "model", model_used)
                provider = model_used.split("/")[0] if "/" in model_used else "unknown"
                success = True
            except Exception as exc:
                error = str(exc)
                logger.warning("ConductorModelGateway: ModelRouter failed (%s): %s", task_type, exc)

        # --- Attempt 2: Direct Anthropic SDK fallback ---
        if not success:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
                msg = client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                    **(({"system": system}) if system else {}),
                )
                content = msg.content[0].text
                model_used = "claude/claude-sonnet-4-5"
                provider = "claude"
                error = None
                success = True
            except Exception as exc2:
                error = str(exc2)
                content = f"[ConductorModelGateway: all backends failed. Last error: {exc2}]"
                logger.error("ConductorModelGateway: all backends failed for task=%s: %s", task_type, exc2)

        latency_ms = (time.perf_counter() - start) * 1000

        result = ConductorModelResponse(
            content=content,
            model=model_used,
            task_type=task_type,
            operator_id=operator_id,
            latency_ms=latency_ms,
            success=success,
            error=error,
            call_id=call_id,
            provider=provider,
        )

        # --- Record provenance ---
        self._record_call(result)
        self._publish_to_harmony(result)
        self._update_usage(result)

        return result

    def usage_summary(self) -> Dict[str, Any]:
        """Return per-model usage stats for the conductor dashboard."""
        summary = {}
        for model, stats in self._usage.items():
            calls = stats.get("calls", 0)
            summary[model] = {
                "calls": calls,
                "failures": stats.get("failures", 0),
                "avg_latency_ms": round(stats.get("total_latency_ms", 0) / max(calls, 1), 1),
                "success_rate": round(
                    (calls - stats.get("failures", 0)) / max(calls, 1) * 100, 1
                ),
            }
        return summary

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _record_call(self, result: ConductorModelResponse):
        try:
            import brain_integration  # conductor's existing brain module
            if hasattr(brain_integration, "record_model_call"):
                brain_integration.record_model_call(
                    call_id=result.call_id,
                    model=result.model,
                    task_type=result.task_type,
                    operator_id=result.operator_id,
                    latency_ms=result.latency_ms,
                    success=result.success,
                )
        except Exception:
            pass

    def _publish_to_harmony(self, result: ConductorModelResponse):
        if not self._harmony_publisher:
            return
        try:
            self._harmony_publisher.publish("model_call", {
                "call_id": result.call_id,
                "model": result.model,
                "provider": result.provider,
                "task_type": result.task_type,
                "operator_id": result.operator_id,
                "latency_ms": result.latency_ms,
                "success": result.success,
                "timestamp": result.timestamp,
                "source_repo": "conductor-protocol-v2",
            })
        except Exception as exc:
            logger.debug("ConductorModelGateway: harmony publish failed: %s", exc)

    def _update_usage(self, result: ConductorModelResponse):
        stats = self._usage.setdefault(result.model, {
            "calls": 0, "failures": 0, "total_latency_ms": 0.0
        })
        stats["calls"] += 1
        stats["total_latency_ms"] += result.latency_ms
        if not result.success:
            stats["failures"] += 1


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_gateway: Optional[ConductorModelGateway] = None


def get_gateway() -> ConductorModelGateway:
    global _gateway
    if _gateway is None:
        _gateway = ConductorModelGateway()
    return _gateway


def call_for_conductor(
    prompt: str,
    task_type: str = "reasoning",
    operator_id: str = "",
    system: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    model: Optional[str] = None,
) -> str:
    """One-liner call for use throughout conductor modules."""
    return get_gateway().call(
        prompt=prompt,
        task_type=task_type,
        operator_id=operator_id,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
        model=model,
    ).content
