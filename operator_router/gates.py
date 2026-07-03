from dataclasses import dataclass
from typing import Callable

@dataclass
class GateResult:
    gate_name: str
    passed: bool
    reason: str

class Gate:
    def __init__(self, name: str, check_fn: Callable[[dict], GateResult]):
        self.name = name
        self.check_fn = check_fn

    def evaluate(self, claim_map: dict) -> GateResult:
        return self.check_fn(claim_map)

def _no_contradicted_claims(claim_map: dict) -> GateResult:
    blocked = [c["claim_id"] for c in claim_map.get("claims", [])
               if c.get("evidence_class") == "contradicted"]
    if blocked:
        return GateResult("no_contradicted_claims", False,
                          f"Contradicted claims present: {blocked}")
    return GateResult("no_contradicted_claims", True, "No contradicted claims.")

def _all_required_runtime_proven(claim_map: dict) -> GateResult:
    failing = [c["claim_id"] for c in claim_map.get("claims", [])
               if c.get("required_for_production") and
               c.get("evidence_class") != "runtime_proven"]
    if failing:
        return GateResult("all_required_runtime_proven", False,
                          f"Required claims not runtime_proven: {failing}")
    return GateResult("all_required_runtime_proven", True,
                      "All required claims are runtime_proven.")

DEFAULT_GATES = [
    Gate("no_contradicted_claims", _no_contradicted_claims),
    Gate("all_required_runtime_proven", _all_required_runtime_proven),
]
