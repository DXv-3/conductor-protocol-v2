"""operator_router/router.py

Routes claim maps through provenance gates and emits every decision
to the-brain via ConductorBridge (fire-and-forget, graceful fallback).
"""
import json
import yaml
from pathlib import Path
from .gates import DEFAULT_GATES, GateResult
from typing import List


def _get_bridge():
    """Lazy-load ConductorBridge. Returns None if the-brain is unreachable."""
    try:
        from brain_integration import get_bridge
        return get_bridge()
    except Exception:
        return None


class Router:
    def __init__(self, config_path: str = "operator_router/config.yaml"):
        self.config = {}
        try:
            with open(config_path) as f:
                self.config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            pass
        self.gates = DEFAULT_GATES
        self._bridge = _get_bridge()

    def inspect_and_route(self, claim_map_path: str, run_id: str = "") -> dict:
        import uuid
        _run_id = run_id or f"router_{uuid.uuid4().hex[:12]}"

        claim_map = json.loads(Path(claim_map_path).read_text())
        artifact = claim_map.get("artifact_name", Path(claim_map_path).stem)

        # Emit session start
        if self._bridge:
            try:
                self._bridge.session_start(_run_id, operator="inspect_and_route")
            except Exception:
                pass

        results: List[GateResult] = []
        for gate in self.gates:
            result = gate.evaluate(claim_map)
            results.append(result)

            # Emit each gate result to the-brain
            if self._bridge:
                try:
                    self._bridge.gate_event(
                        run_id=_run_id,
                        gate_name=result.gate_name,
                        artifact=artifact,
                        outcome="pass" if result.passed else "blocked",
                        detail=result.reason,
                    )
                except Exception:
                    pass

        all_passed = all(r.passed for r in results)
        route = (
            self.config.get("route_on_pass", "canonical")
            if all_passed
            else self.config.get("route_on_fail", "blocked_queue")
        )

        # Emit promotion decision to the-brain
        if self._bridge:
            try:
                self._bridge.promotion_event(
                    run_id=_run_id,
                    artifact=artifact,
                    status="allowed" if all_passed else "blocked",
                    trace_id=_run_id,
                    notes=f"Route: {route}",
                )
                self._bridge.session_end(
                    _run_id,
                    summary=f"Artifact '{artifact}' → {route} "
                            f"({'all gates passed' if all_passed else 'gates failed'})",
                    record_count=len(results) + 2,
                )
            except Exception:
                pass

        return {
            "run_id": _run_id,
            "artifact": artifact,
            "route": route,
            "all_gates_passed": all_passed,
            "gate_results": [
                {"gate": r.gate_name, "passed": r.passed, "reason": r.reason}
                for r in results
            ],
        }
