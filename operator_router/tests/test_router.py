import pytest
import json
from operator_router.router import Router

PASSING_CLAIM_MAP = {
    "artifact_name": "bundle.md",
    "claims": [
        {"claim_id": "C001", "required_for_production": True, "evidence_class": "runtime_proven"},
        {"claim_id": "C002", "required_for_production": True, "evidence_class": "runtime_proven"},
    ]
}

FAILING_CLAIM_MAP = {
    "artifact_name": "bundle.md",
    "claims": [
        {"claim_id": "C001", "required_for_production": True, "evidence_class": "runtime_proven"},
        {"claim_id": "C002", "required_for_production": True, "evidence_class": "asserted_unverified"},
    ]
}

def test_router_routes_to_canonical(tmp_path):
    p = tmp_path / "claim_map.json"
    p.write_text(json.dumps(PASSING_CLAIM_MAP))
    router = Router(config_path="operator_router/config.yaml")
    result = router.inspect_and_route(str(p))
    assert result["all_gates_passed"] is True
    assert result["route"] == "canonical"

def test_router_routes_to_blocked(tmp_path):
    p = tmp_path / "claim_map.json"
    p.write_text(json.dumps(FAILING_CLAIM_MAP))
    router = Router(config_path="operator_router/config.yaml")
    result = router.inspect_and_route(str(p))
    assert result["all_gates_passed"] is False
    assert result["route"] == "blocked_queue"
