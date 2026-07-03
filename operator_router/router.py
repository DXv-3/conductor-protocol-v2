import json
import yaml
from pathlib import Path
from .gates import DEFAULT_GATES, GateResult
from typing import List

class Router:
    def __init__(self, config_path: str = "operator_router/config.yaml"):
        self.config = {}
        try:
            with open(config_path) as f:
                self.config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            pass
        self.gates = DEFAULT_GATES

    def inspect_and_route(self, claim_map_path: str) -> dict:
        claim_map = json.loads(Path(claim_map_path).read_text())
        results: List[GateResult] = [g.evaluate(claim_map) for g in self.gates]
        all_passed = all(r.passed for r in results)
        route = self.config.get("route_on_pass", "canonical") if all_passed \
                else self.config.get("route_on_fail", "blocked_queue")
        return {
            "route": route,
            "all_gates_passed": all_passed,
            "gate_results": [
                {"gate": r.gate_name, "passed": r.passed, "reason": r.reason}
                for r in results
            ]
        }
