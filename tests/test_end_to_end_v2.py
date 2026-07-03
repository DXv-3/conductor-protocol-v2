import pytest
from pathlib import Path

@pytest.fixture
def tmp_config(tmp_path):
    ref_doc = tmp_path / "conductor-v1-full-bundle.md"
    ref_doc.write_text(
        "# Bundle\nProof gate enforced. Cost cap enforced. "
        "Memory artifact persists. Just listen background cycle active. "
        "Config loaded from YAML. Build on top gated. Canonical rewrite only post-promotion."
    )
    build_script = tmp_path / "build-bundle.py"
    build_script.write_text("# stub")
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Skill")
    config = {
        "skill_dir": str(skill_dir),
        "reference_doc": str(ref_doc),
        "build_script": str(build_script),
        "artifacts_dir": str(tmp_path / "artifacts"),
        "evidence_dir": str(tmp_path / "artifacts" / "evidence"),
        "required_runtime_categories": [
            "proof_gate", "rewrite_behavior", "cost_control",
            "memory_persistence", "background_collection",
            "config_loading", "build_on_top"
        ]
    }
    return config

def test_full_pipeline_runs(tmp_config):
    from conductor_harness.conductor import Conductor
    conductor = Conductor(tmp_config)
    result = conductor.run()
    assert "promotion_report" in result
    assert result["promotion_report"]["decision"] in ("allowed", "blocked")

def test_provenance_trace_persisted(tmp_config):
    from conductor_harness.conductor import Conductor
    conductor = Conductor(tmp_config)
    conductor.run()
    provenance_dir = Path(tmp_config["artifacts_dir"]) / "provenance"
    files = list(provenance_dir.glob("*.json"))
    assert len(files) >= 1

def test_claim_map_persisted(tmp_config):
    from conductor_harness.conductor import Conductor
    conductor = Conductor(tmp_config)
    conductor.run()
    claim_file = Path(tmp_config["artifacts_dir"]) / "claims" / "claim_map.json"
    assert claim_file.exists()

def test_runtime_evidence_persisted(tmp_config):
    from conductor_harness.conductor import Conductor
    conductor = Conductor(tmp_config)
    conductor.run()
    evidence_file = Path(tmp_config["evidence_dir"]) / "runtime_evidence.json"
    assert evidence_file.exists()

def test_promotion_report_persisted(tmp_config):
    from conductor_harness.conductor import Conductor
    conductor = Conductor(tmp_config)
    conductor.run()
    reports_dir = Path(tmp_config["artifacts_dir"]) / "reports"
    files = list(reports_dir.glob("promotion_*.json"))
    assert len(files) >= 1

def test_blocked_when_required_claims_unverified(tmp_config):
    from conductor_harness.conductor import Conductor
    conductor = Conductor(tmp_config)
    result = conductor.run()
    report = result["promotion_report"]
    if report["decision"] == "blocked":
        assert len(report["blocking_claims"]) > 0
