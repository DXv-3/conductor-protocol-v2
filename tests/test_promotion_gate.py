import pytest
from conductor_harness.policy import decide_promotion

def _claim(cid, category, evidence_class, required=True):
    return {
        "claim_id": cid,
        "category": category,
        "required_for_production": required,
        "evidence_class": evidence_class,
    }

def test_promotion_allowed_when_all_runtime_proven():
    claims = [
        _claim("C001", "proof_gate", "runtime_proven"),
        _claim("C002", "cost_control", "runtime_proven"),
        _claim("C003", "memory_persistence", "runtime_proven"),
    ]
    decision = decide_promotion(claims)
    assert decision.allowed is True
    assert decision.blocking_claims == []

def test_promotion_blocked_on_asserted_unverified():
    claims = [
        _claim("C001", "proof_gate", "runtime_proven"),
        _claim("C002", "cost_control", "asserted_unverified"),
    ]
    decision = decide_promotion(claims)
    assert decision.allowed is False
    assert "C002" in decision.blocking_claims

def test_promotion_blocked_on_contradicted():
    claims = [_claim("C001", "cost_control", "contradicted")]
    decision = decide_promotion(claims)
    assert decision.allowed is False

def test_promotion_blocked_on_reference_only():
    claims = [_claim("C001", "build_on_top", "reference_only")]
    decision = decide_promotion(claims)
    assert decision.allowed is False

def test_non_required_claim_does_not_block():
    claims = [
        _claim("C001", "versioning", "reference_only", required=False),
        _claim("C002", "proof_gate", "runtime_proven", required=True),
    ]
    decision = decide_promotion(claims)
    assert decision.allowed is True

def test_empty_claims_allowed():
    decision = decide_promotion([])
    assert decision.allowed is True

def test_promotion_decision_notes_populated():
    claims = [_claim("C001", "cost_control", "asserted_unverified")]
    decision = decide_promotion(claims)
    assert len(decision.notes) > 0
