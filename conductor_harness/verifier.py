import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from .runtime_tests import ALL_RUNTIME_TESTS

@dataclass
class RuntimeTest:
    test_id: str
    purpose: str
    status: str
    observed_output: str = ""
    artifacts_written: List[str] = field(default_factory=list)
    claims_covered: List[str] = field(default_factory=list)

class Verifier:
    def __init__(self, evidence_dir: str):
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.tests: List[RuntimeTest] = []

    def run_all(self, claim_map: Optional[dict] = None, conductor_config: Optional[dict] = None) -> dict:
        self.tests.clear()
        for test_fn in ALL_RUNTIME_TESTS:
            result = test_fn()
            self.tests.append(result)

        if claim_map:
            passed_ids = {t.test_id for t in self.tests if t.status == "pass"}
            for claim in claim_map.get("claims", []):
                for t in self.tests:
                    if claim["claim_id"] in t.claims_covered and t.test_id in passed_ids:
                        claim["evidence_class"] = "runtime_proven"
                        claim["runtime_tests"] = [t.test_id]
                        break

        summary = {
            "pass_count": sum(1 for t in self.tests if t.status == "pass"),
            "fail_count": sum(1 for t in self.tests if t.status == "fail"),
            "skip_count": sum(1 for t in self.tests if t.status == "skip"),
        }
        evidence = {
            "artifact_name": claim_map["artifact_name"] if claim_map else "unknown",
            "tests": [
                {
                    "test_id": t.test_id,
                    "purpose": t.purpose,
                    "status": t.status,
                    "observed_output": t.observed_output,
                    "claims_covered": t.claims_covered
                } for t in self.tests
            ],
            "summary": summary
        }
        with open(self.evidence_dir / "runtime_evidence.json", "w") as f:
            json.dump(evidence, f, indent=2)
        return evidence
