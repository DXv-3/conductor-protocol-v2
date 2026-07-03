import pytest
from conductor_harness.provenance import ProvenanceTrace
from conductor_harness.schemas import validate

def test_provenance_trace_valid():
    trace = ProvenanceTrace(
        trace_id="prov-test",
        session_id="test-session",
        artifact_name="bundle.md",
        files_read=["SKILL.md", "build-bundle.py"],
        commands_run=["python build-bundle.py"],
        reference_docs_used=["conductor-v1-full-bundle.md"],
        scripts_invoked=["build-bundle.py"],
        generated_outputs=["bundle.md"],
        timestamps={"observed_at": "2026-07-03T00:00:00+00:00"}
    )
    trace_dict = {
        "trace_id": trace.trace_id,
        "session_id": trace.session_id,
        "artifact_name": trace.artifact_name,
        "source_videos": trace.source_videos,
        "files_read": trace.files_read,
        "commands_run": trace.commands_run,
        "reference_docs_used": trace.reference_docs_used,
        "scripts_invoked": trace.scripts_invoked,
        "artifact_paths_checked": trace.artifact_paths_checked,
        "generated_outputs": trace.generated_outputs,
        "timestamps": trace.timestamps,
        "operator_notes": trace.operator_notes
    }
    validate(trace_dict, "provenance_trace")

def test_provenance_classify_reference_and_script():
    trace = ProvenanceTrace(
        trace_id="prov-002",
        session_id="s1",
        artifact_name="bundle.md",
        reference_docs_used=["ref.md"],
        scripts_invoked=["build.py"],
        timestamps={"observed_at": "2026-07-03T00:00:00+00:00"}
    )
    assert trace.classify_generation() == "compiled_from_reference_and_script"

def test_provenance_classify_local_sources():
    trace = ProvenanceTrace(
        trace_id="prov-003",
        session_id="s1",
        artifact_name="bundle.md",
        files_read=["local.md"],
        timestamps={"observed_at": "2026-07-03T00:00:00+00:00"}
    )
    assert trace.classify_generation() == "assembled_from_local_sources"

def test_provenance_classify_unknown():
    trace = ProvenanceTrace(
        trace_id="prov-004",
        session_id="s1",
        artifact_name="bundle.md",
        timestamps={"observed_at": "2026-07-03T00:00:00+00:00"}
    )
    assert trace.classify_generation() == "unknown"
