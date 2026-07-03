import pytest
from conductor_harness.runtime_tests import (
    test_rewrite_safety,
    test_cost_cap_enforced,
    test_build_on_top,
)
from conductor_harness.schemas import validate

def test_rewrite_safety_passes():
    result = test_rewrite_safety()
    assert result.status == "pass"

def test_persistence_writes_passes(tmp_path):
    from conductor_harness.runtime_tests import test_persistence_writes
    result = test_persistence_writes(tmpdir=str(tmp_path))
    assert result.status == "pass"
    assert len(result.artifacts_written) > 0

def test_background_collection_passes(tmp_path):
    from conductor_harness.just_listen_bridge import JustListenBridge
    bridge = JustListenBridge(str(tmp_path))
    bridge.collect_observation("smoke test")
    obs = bridge.recent_observations(limit=1)
    assert obs and "smoke test" in obs[0]

def test_cost_cap_fails_with_stub():
    result = test_cost_cap_enforced()
    assert result.status == "fail"
    assert result.test_id == "TEST-COST-001"

def test_build_on_top_skipped():
    result = test_build_on_top()
    assert result.status == "skip"

def test_runtime_evidence_schema_valid():
    from conductor_harness.verifier import Verifier
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        verifier = Verifier(evidence_dir=tmpdir)
        evidence = verifier.run_all()
        validate(evidence, "runtime_evidence")
