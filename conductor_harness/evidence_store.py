import json
from pathlib import Path
from datetime import datetime, timezone

class EvidenceStore:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def store_provenance(self, trace: dict) -> Path:
        p = self.base / "provenance" / f"{trace['trace_id']}.json"
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(trace, indent=2))
        return p

    def store_claims(self, claim_map: dict) -> Path:
        p = self.base / "claims" / "claim_map.json"
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(claim_map, indent=2))
        return p

    def store_runtime_evidence(self, evidence: dict) -> Path:
        p = self.base / "evidence" / "runtime_evidence.json"
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(evidence, indent=2))
        return p

    def store_promotion_report(self, report: dict) -> Path:
        p = self.base / "reports" / f"promotion_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(report, indent=2))
        return p
