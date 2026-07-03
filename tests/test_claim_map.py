import pytest
from conductor_harness.claim_mapper import extract_claims
from conductor_harness.schemas import validate

SAMPLE_TEXT = """
The proof gate enforces that no bundle is promoted without runtime evidence.
Cost cap enforced per session. Memory artifact persists across resets.
Just listen background cycle collects observations. Config values are loaded from YAML.
Build on top only permitted after valid gate pass. Canonical rewrite occurs only post-promotion.
"""

def test_extract_claims_nonempty():
    claims = extract_claims(SAMPLE_TEXT)
    assert len(claims) > 0

def test_claim_ids_unique():
    claims = extract_claims(SAMPLE_TEXT)
    ids = [c["claim_id"] for c in claims]
    assert len(ids) == len(set(ids))

def test_all_claims_default_asserted_unverified():
    claims = extract_claims(SAMPLE_TEXT)
    for c in claims:
        assert c["evidence_class"] == "asserted_unverified"

def test_claim_map_schema_valid():
    claims = extract_claims(SAMPLE_TEXT)
    claim_map = {"artifact_name": "bundle.md", "claims": claims}
    validate(claim_map, "claim_map")

def test_required_for_production_flags():
    required = ["cost_control", "proof_gate"]
    claims = extract_claims(SAMPLE_TEXT, required_categories=required)
    req_claims = [c for c in claims if c["required_for_production"]]
    assert all(c["category"] in required for c in req_claims)

def test_no_claims_on_empty_text():
    claims = extract_claims("")
    assert claims == []
