#!/usr/bin/env python3
"""Tests for router_integration_patch.py"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "operator_router"))


class FakeAdjustment:
    def __init__(self, action="no_change", reason="", evidence=None,
                 recommendation="", suggested_model="", confidence=1.0):
        self.action = action
        self.reason = reason
        self.evidence = evidence or []
        self.recommendation = recommendation
        self.suggested_model = suggested_model
        self.confidence = confidence

    @property
    def is_blocking(self):
        return self.action == "hard_block"


def _no_change():
    return FakeAdjustment(action="no_change")

def _hard_block():
    return FakeAdjustment(
        action="hard_block",
        reason="5 consecutive failures on gate-3",
        evidence=[{"outcome": "fail", "detail": "timeout"}],
        recommendation="switch to claude-3-5-sonnet or investigate gate-3",
    )

def _adjust_model():
    return FakeAdjustment(
        action="adjust_model",
        suggested_model="claude-3-5-sonnet-20241022",
        reason="3 failures with grok-3",
        confidence=0.85,
    )


def _original_router(task_config: dict) -> dict:
    return {"routed": True, "model": task_config.get("model", "default"),
            "task_config": task_config}


class TestWrapRouterNoChange:
    def test_passes_through_when_no_change(self):
        with patch("router_integration_patch._BRAIN_QUERY", True), \
             patch("router_integration_patch.query_before_route", return_value=_no_change()), \
             patch("router_integration_patch.apply_routing_adjustment", side_effect=lambda tc, adj: tc):
            from router_integration_patch import wrap_router
            wrapped = wrap_router(_original_router)
            result = wrapped({"model": "grok-3", "run_id": "r1"})
        assert result["routed"] is True
        assert result["model"] == "grok-3"

    def test_original_task_config_not_mutated(self):
        original = {"model": "grok-3", "gate_id": "gate-1", "run_id": "r2"}
        with patch("router_integration_patch._BRAIN_QUERY", True), \
             patch("router_integration_patch.query_before_route", return_value=_no_change()), \
             patch("router_integration_patch.apply_routing_adjustment", side_effect=lambda tc, adj: tc):
            from router_integration_patch import wrap_router
            wrap_router(_original_router)(original)
        assert original["model"] == "grok-3"


class TestWrapRouterHardBlock:
    def test_blocked_dict_returned_without_calling_original(self):
        call_count = {"n": 0}
        def _counting(tc): call_count["n"] += 1; return {"routed": True}

        with patch("router_integration_patch._BRAIN_QUERY", True), \
             patch("router_integration_patch.query_before_route", return_value=_hard_block()), \
             patch("router_integration_patch.apply_routing_adjustment", side_effect=lambda tc, adj: tc):
            from router_integration_patch import wrap_router
            result = wrap_router(_counting)({"model": "grok-3", "run_id": "r3"})

        assert result["blocked"] is True
        assert "5 consecutive failures" in result["reason"]
        assert call_count["n"] == 0

    def test_blocked_result_has_recommendation(self):
        with patch("router_integration_patch._BRAIN_QUERY", True), \
             patch("router_integration_patch.query_before_route", return_value=_hard_block()), \
             patch("router_integration_patch.apply_routing_adjustment", side_effect=lambda tc, adj: tc):
            from router_integration_patch import wrap_router
            result = wrap_router(_original_router)({"model": "grok-3", "run_id": "r4"})
        assert result["recommendation"] != ""

    def test_task_config_included_in_blocked_result(self):
        tc = {"model": "grok-3", "gate_id": "gate-3"}
        with patch("router_integration_patch._BRAIN_QUERY", True), \
             patch("router_integration_patch.query_before_route", return_value=_hard_block()), \
             patch("router_integration_patch.apply_routing_adjustment", side_effect=lambda tc, adj: tc):
            from router_integration_patch import wrap_router
            result = wrap_router(_original_router)(tc)
        assert result["task_config"]["gate_id"] == "gate-3"


class TestWrapRouterModelAdjustment:
    def test_model_adjusted_before_original_called(self):
        def _adjust(tc, adj): return {**tc, "model": adj.suggested_model}

        with patch("router_integration_patch._BRAIN_QUERY", True), \
             patch("router_integration_patch.query_before_route", return_value=_adjust_model()), \
             patch("router_integration_patch.apply_routing_adjustment", side_effect=_adjust):
            from router_integration_patch import wrap_router
            result = wrap_router(_original_router)({"model": "grok-3", "run_id": "r5"})

        assert result["model"] == "claude-3-5-sonnet-20241022"

    def test_original_model_not_mutated(self):
        def _adjust(tc, adj): return {**tc, "model": adj.suggested_model}
        original = {"model": "grok-3", "run_id": "r6"}
        with patch("router_integration_patch._BRAIN_QUERY", True), \
             patch("router_integration_patch.query_before_route", return_value=_adjust_model()), \
             patch("router_integration_patch.apply_routing_adjustment", side_effect=_adjust):
            from router_integration_patch import wrap_router
            wrap_router(_original_router)(original)
        assert original["model"] == "grok-3"


class TestWrapRouterBrainUnavailable:
    def test_continues_when_brain_query_flag_false(self):
        with patch("router_integration_patch._BRAIN_QUERY", False):
            from router_integration_patch import wrap_router
            result = wrap_router(_original_router)({"model": "grok-3", "run_id": "r7"})
        assert result["routed"] is True

    def test_continues_when_brain_query_raises(self):
        def _boom(tc): raise ConnectionError("brain offline")
        with patch("router_integration_patch._BRAIN_QUERY", True), \
             patch("router_integration_patch.query_before_route", side_effect=_boom), \
             patch("router_integration_patch.apply_routing_adjustment", side_effect=lambda tc, adj: tc):
            from router_integration_patch import wrap_router
            result = wrap_router(_original_router)({"model": "grok-3", "run_id": "r8"})
        assert result["routed"] is True


class TestPatchedCallModel:
    def _fake_result(self, success=True):
        r = MagicMock()
        r.success = success
        r.content = "Hello" if success else ""
        r.error = "" if success else "API timeout"
        r.model_used = "grok-3"
        r.backend = "grok"
        r.latency_ms = 320.0
        r.input_tokens = 10
        r.output_tokens = 5
        return r

    def test_returns_dict_on_success(self):
        with patch("router_integration_patch._CONDUCTOR_ADAPTER", True), \
             patch("router_integration_patch.call_model", return_value=self._fake_result(True)):
            from router_integration_patch import patched_call_model
            result = patched_call_model("grok-3", "hello", run_id="r9")
        assert result["success"] is True
        assert result["content"] == "Hello"
        assert result["latency_ms"] == 320.0

    def test_returns_dict_on_failure(self):
        with patch("router_integration_patch._CONDUCTOR_ADAPTER", True), \
             patch("router_integration_patch.call_model", return_value=self._fake_result(False)):
            from router_integration_patch import patched_call_model
            result = patched_call_model("grok-3", "hello", run_id="r10")
        assert result["success"] is False
        assert result["error"] == "API timeout"

    def test_raises_when_adapter_unavailable(self):
        with patch("router_integration_patch._CONDUCTOR_ADAPTER", False):
            from router_integration_patch import patched_call_model
            with pytest.raises(ImportError):
                patched_call_model("grok-3", "hello")
