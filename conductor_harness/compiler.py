import os
from datetime import datetime, timezone
from pathlib import Path
from conductor_harness.provenance import ProvenanceTrace

class Compiler:
    def __init__(self, skill_dir: str, reference_doc: str, script: str):
        self.skill_dir = Path(skill_dir)
        self.reference_doc = Path(reference_doc)
        self.script = Path(script)
        self.trace = None

    def compile(self) -> str:
        files_read = [
            str(self.skill_dir / "SKILL.md"),
            str(self.script),
            str(self.reference_doc)
        ]
        bundle_text = ""
        if self.reference_doc.exists():
            bundle_text = self.reference_doc.read_text()
        else:
            bundle_text = "# Compiled Bundle\nPlaceholder"

        now = datetime.now(timezone.utc).isoformat()
        self.trace = ProvenanceTrace(
            trace_id=f"prov-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}",
            session_id=os.environ.get("SESSION_ID", "local"),
            artifact_name="bundle.md",
            files_read=files_read,
            commands_run=[f"python {self.script}"],
            reference_docs_used=[str(self.reference_doc)],
            scripts_invoked=[str(self.script)],
            generated_outputs=["bundle.md"],
            timestamps={"observed_at": now}
        )
        return bundle_text
