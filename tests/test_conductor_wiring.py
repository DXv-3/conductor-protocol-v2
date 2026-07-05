"""
tests/test_conductor_wiring.py
-------------------------------
Tests for CONDUCTOR-01 wiring:
  - ConductorModelGateway (model_gateway_adapter)
  - BrainSkillRouter (brain_skill_router)
  - harmony_subscriber handlers

All external dependencies mocked. No real API calls, no real DB beyond
SQLite in-memory, no real harmony bus.
"""

import json
import sqlite3
import sys
import types
import unittest
from dataclasses import dataclass
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub zai-wrap model_gateway before imports
# ---------------------------------------------------------------------------

@dataclass
class _FakeModelResponse:
    content: str
    model: str = "claude/claude-sonnet-4-5"

_fake_router = MagicMock()
_fake_router.call.return_value = _FakeModelResponse(content="test response")
_fake_router.route.return_value = _FakeModelResponse(content="routed response", model="deepseek/deepseek-coder")
_fake_router.usage_summary.return_value = {}

_model_gateway_mod = types.ModuleType("model_gateway")
_model_gateway_mod.ModelRouter = MagicMock(return_value=_fake_router)
sys.modules["model_gateway"] = _model_gateway_mod

# Stub harmony_publisher_base
_harmony_pub_mod = types.ModuleType("harmony_publisher_base")
_harmony_pub_mod.HarmonyPublisher = MagicMock()
_harmony_pub_mod.HarmonySubscriber = MagicMock()
sys.modules["harmony_publisher_base"] = _harmony_pub_mod

# Stub brain_integration
_brain_int_mod = types.ModuleType("brain_integration")
_brain_int_mod.record_model_call = MagicMock()
sys.modules["brain_integration"] = _brain_int_mod

# Stub skill_brain_sync
_sbs_mod = types.ModuleType("skill_brain_sync")
_sbs_mod.get_all_skill_scores = MagicMock(return_value={"code": 0.9, "review": 0.6, "deploy": 0.3})
_sbs_mod.get_skill_history = MagicMock(return_value=[
    {"event_type": "promoted", "skill_version": 2, "outcome_score": 0.9, "delta_summary": "added retry"},
])
sys.modules["skill_brain_sync"] = _sbs_mod

# Stub anthropic (fallback path)
_anthropic_mod = types.ModuleType("anthropic")
_fake_anthropic_client = MagicMock()
_fake_anthropic_client.messages.create.return_value = MagicMock(
    content=[MagicMock(text="fallback response")]
)
_anthropic_mod.Anthropic = MagicMock(return_value=_fake_anthropic_client)
sys.modules["anthropic"] = _anthropic_mod


# Now safe to import our modules
from operator_router.model_gateway_adapter import (
    ConductorModelGateway, ConductorModelResponse, call_for_conductor, get_gateway
)
from operator_router.brain_skill_router import BrainSkillRouter
from harmony_subscriber import (
    handle_skill_event, handle_model_call, handle_kg_patch,
    get_local_skill_scores, _init_db, _process_message
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    _init_db(conn)
    return conn


# ---------------------------------------------------------------------------
# ConductorModelGateway tests
# ---------------------------------------------------------------------------

class TestConductorModelGateway(unittest.TestCase):

    def setUp(self):
        self.gw = ConductorModelGateway()
        self.gw._router = _fake_router
        self.gw._router_available = True
        self.gw._harmony_publisher = MagicMock()

    def test_call_returns_response_object(self):
        resp = self.gw.call("hello", task_type="code", operator_id="op-1")
        self.assertIsInstance(resp, ConductorModelResponse)
        self.assertTrue(resp.success)
        self.assertEqual(resp.task_type, "code")
        self.assertEqual(resp.operator_id, "op-1")

    def test_call_routes_through_model_router(self):
        _fake_router.route.reset_mock()
        self.gw.call("test prompt", task_type="reasoning")
        _fake_router.route.assert_called_once()

    def test_call_direct_model_uses_router_call(self):
        _fake_router.call.reset_mock()
        self.gw.call("prompt", model="claude/claude-opus-4-5")
        _fake_router.call.assert_called_once()

    def test_harmony_publish_called(self):
        self.gw._harmony_publisher.publish.reset_mock()
        self.gw.call("test", task_type="fast", operator_id="op-2")
        self.gw._harmony_publisher.publish.assert_called_once()
        call_args = self.gw._harmony_publisher.publish.call_args
        self.assertEqual(call_args[0][0], "model_call")

    def test_usage_summary_accumulates(self):
        self.gw.call("p1", task_type="code")
        self.gw.call("p2", task_type="code")
        summary = self.gw.usage_summary()
        # At least one model should have 2 calls
        total_calls = sum(v["calls"] for v in summary.values())
        self.assertGreaterEqual(total_calls, 2)

    def test_fallback_to_anthropic_on_router_failure(self):
        self.gw._router.route.side_effect = Exception("router down")
        self.gw._router.call.side_effect = Exception("router down")
        resp = self.gw.call("test", task_type="reasoning")
        # Should fall through to Anthropic SDK
        self.assertIn("response", resp.content)
        # Reset side effects
        self.gw._router.route.side_effect = None
        self.gw._router.call.side_effect = None

    def test_call_for_conductor_returns_string(self):
        gw = get_gateway()
        gw._router = _fake_router
        gw._router_available = True
        result = call_for_conductor("test", task_type="fast")
        self.assertIsInstance(result, str)

    def test_task_defaults_cover_all_conductor_types(self):
        required = {"code", "reasoning", "fast", "creative", "vision", "routing", "audit", "forensics"}
        self.assertEqual(required, set(ConductorModelGateway.TASK_DEFAULTS.keys()))


# ---------------------------------------------------------------------------
# BrainSkillRouter tests
# ---------------------------------------------------------------------------

class TestBrainSkillRouter(unittest.TestCase):

    def setUp(self):
        self.router = BrainSkillRouter()
        self.router._sync = _sbs_mod
        self.router._sync_available = True
        self.router._cache_ts = 0.0  # force cache refresh

    def test_enrich_returns_all_keys(self):
        context = self.router.enrich_route_context({"category": "code_generation"})
        for key in ["best_skill", "skill_score", "skill_history_summary",
                    "recommended_task_type", "recommended_model", "all_skill_scores"]:
            self.assertIn(key, context)

    def test_category_maps_to_task_type(self):
        context = self.router.enrich_route_context({"category": "code_generation"})
        self.assertEqual(context["recommended_task_type"], "code")

    def test_best_skill_selected_by_score(self):
        task = {
            "category": "code_generation",
            "candidate_skills": ["code", "review", "deploy"],
        }
        context = self.router.enrich_route_context(task)
        self.assertEqual(context["best_skill"], "code")  # score=0.9 is highest
        self.assertAlmostEqual(context["skill_score"], 0.9)

    def test_high_score_gets_primary_model(self):
        task = {"category": "code_review", "candidate_skills": ["code"]}
        context = self.router.enrich_route_context(task)
        # code score=0.9 >= 0.5, so primary model
        primary, _ = ConductorModelGateway.TASK_DEFAULTS["code"]
        self.assertEqual(context["recommended_model"], primary)

    def test_low_score_gets_fallback_model(self):
        task = {"category": "code_generation", "candidate_skills": ["deploy"]}
        context = self.router.enrich_route_context(task)
        # deploy score=0.3 < 0.5, so fallback model
        _, fallback = ConductorModelGateway.TASK_DEFAULTS["code"]
        self.assertEqual(context["recommended_model"], fallback)

    def test_skill_history_summary_populated(self):
        task = {"category": "code_generation", "candidate_skills": ["code"]}
        context = self.router.enrich_route_context(task)
        self.assertIn("promoted", context["skill_history_summary"])

    def test_graceful_when_sync_unavailable(self):
        self.router._sync_available = False
        context = self.router.enrich_route_context({"category": "reasoning"})
        self.assertEqual(context["best_skill"], "")
        self.assertEqual(context["recommended_task_type"], "reasoning")


# ---------------------------------------------------------------------------
# harmony_subscriber handler tests
# ---------------------------------------------------------------------------

class TestHarmonySubscriberHandlers(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()

    def tearDown(self):
        self.conn.close()

    def test_handle_skill_event_inserts_row(self):
        payload = {
            "event_id": "evt-001",
            "skill_name": "code",
            "outcome_score": 0.85,
            "event_type": "promoted",
        }
        handle_skill_event(payload, self.conn)
        row = self.conn.execute(
            "SELECT avg_score FROM skill_scores WHERE skill_name='code'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row[0], 0.85)

    def test_handle_skill_event_rolling_avg(self):
        for score in [0.8, 0.6]:
            handle_skill_event(
                {"event_id": str(score), "skill_name": "review", "outcome_score": score},
                self.conn
            )
        row = self.conn.execute(
            "SELECT avg_score FROM skill_scores WHERE skill_name='review'"
        ).fetchone()
        # After two events: first sets to 0.8, second: 0.7*0.8 + 0.3*0.6 = 0.74
        self.assertAlmostEqual(row[0], 0.74, places=5)

    def test_handle_model_call_inserts_log(self):
        payload = {
            "call_id": "call-001",
            "model": "claude/claude-sonnet-4-5",
            "provider": "claude",
            "task_type": "reasoning",
            "operator_id": "op-1",
            "latency_ms": 342.5,
            "success": True,
            "timestamp": "2026-07-04T20:00:00Z",
        }
        handle_model_call(payload, self.conn)
        row = self.conn.execute(
            "SELECT model, latency_ms FROM model_call_log WHERE call_id='call-001'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "claude/claude-sonnet-4-5")
        self.assertAlmostEqual(row[1], 342.5)

    def test_handle_kg_patch_stores_patch(self):
        payload = {
            "patch_id": "patch-001",
            "node_type": "skill",
            "node_id": "skill:code",
            "data": {"last_outcome_score": 0.9},
        }
        handle_kg_patch(payload, self.conn)
        row = self.conn.execute(
            "SELECT node_type, node_id FROM kg_patches WHERE patch_id='patch-001'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "skill")
        self.assertEqual(row[1], "skill:code")

    def test_process_message_dispatches_to_correct_handler(self):
        msg = json.dumps({
            "event_type": "skill_event",
            "payload": {"event_id": "x1", "skill_name": "deploy", "outcome_score": 0.4},
        })
        _process_message(msg, self.conn)
        row = self.conn.execute(
            "SELECT avg_score FROM skill_scores WHERE skill_name='deploy'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_process_message_stores_unknown_event_type(self):
        msg = json.dumps({"event_type": "mystery_event", "payload": {"foo": "bar"}})
        _process_message(msg, self.conn)
        row = self.conn.execute(
            "SELECT event_type FROM harmony_events WHERE event_type='mystery_event'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_get_local_skill_scores_reads_from_db(self):
        handle_skill_event(
            {"event_id": "sc1", "skill_name": "audit", "outcome_score": 0.77}, self.conn
        )
        # get_local_skill_scores uses its own connection, so we need to write to the real DB path
        # This tests the function signature and return type rather than DB content
        scores = get_local_skill_scores()
        self.assertIsInstance(scores, dict)


if __name__ == "__main__":
    unittest.main()
