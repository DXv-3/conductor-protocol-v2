import pytest
from operator_router.gates import (
    Gate, _no_contradicted_claims, _all_required_runtime_proven
)

def test_no_contradicted_passes():
    cm = {"claims": [{"claim_id": "C001", "evidence_class": "runtime_proven"}]}
    r = _no_contradicted_claims(cm)
    assert r.passed is True

def test_no_contradicted_fails():
    cm = {"claims": [{"claim_id": "C001", "evidence_class": "contradicted"}]}
    r = _no_contradicted_claims(cm)
    assert r.passed is False
    assert "C001" in r.reason

def test_all_required_runtime_proven_passes():
    cm = {"claims": [
        {"claim_id": "C001", "required_for_production": True, "evidence_class": "runtime_proven"}
    ]}
    r = _all_required_runtime_proven(cm)
    assert r.passed is True

def test_all_required_runtime_proven_fails():
    cm = {"claims": [
        {"claim_id": "C001", "required_for_production": True, "evidence_class": "reference_only"}
    ]}
    r = _all_required_runtime_proven(cm)
    assert r.passed is False

def test_non_required_claim_does_not_block():
    cm = {"claims": [
        {"claim_id": "C001", "required_for_production": False, "evidence_class": "reference_only"}
    ]}
    r = _all_required_runtime_proven(cm)
    assert r.passed is True
