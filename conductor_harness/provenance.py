from dataclasses import dataclass, field
from typing import List

@dataclass
class ProvenanceTrace:
    trace_id: str
    session_id: str
    artifact_name: str
    source_videos: list = field(default_factory=list)
    files_read: List[str] = field(default_factory=list)
    commands_run: List[str] = field(default_factory=list)
    reference_docs_used: List[str] = field(default_factory=list)
    scripts_invoked: List[str] = field(default_factory=list)
    artifact_paths_checked: List[str] = field(default_factory=list)
    generated_outputs: List[str] = field(default_factory=list)
    timestamps: dict = field(default_factory=dict)
    operator_notes: str = ""

    def classify_generation(self) -> str:
        if self.reference_docs_used and self.scripts_invoked:
            return "compiled_from_reference_and_script"
        if self.files_read:
            return "assembled_from_local_sources"
        return "unknown"
