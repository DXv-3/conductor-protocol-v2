"""operator_router/router.py

Routes claim maps through provenance gates and emits every decision
to the-brain via ConductorBridge (fire-and-forget, graceful fallback).

IGNITION-02 PATCH (applied 2026-07-04):
  Router.inspect_and_route is wrapped with wrap_router() at class
  definition time.  The wrapper runs a brain pre-route query before
  any gate evaluation:
    - hard_block  → returns immediately, original method never called
    - adjust_model → mutates claim_map before passing to original method
    - proceed      → passes through unchanged
  Graceful no-op if router_integration_patch or the-brain is unavailable.
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


# ---------------------------------------------------------------------------
# IGNITION-02: wrap_router patch — applied at class definition time
# ---------------------------------------------------------------------------
# wrap_router() injects a brain pre-route query BEFORE inspect_and_route
# runs any gate evaluation.  The wrapper is a no-op if
# router_integration_patch or the-brain is unreachable (graceful degradation).
#
# Behaviour matrix:
#   adjustment.is_blocking == True   → return hard_block dict immediately
#   adjustment.action == "adjust_model" → patch claim_map["model"], then proceed
#   adjustment is None / proceed     → pass through unchanged
# ---------------------------------------------------------------------------

def _apply_wrap_router_patch():
    try:
        import sys
        from pathlib import Path as _Path
        # router_integration_patch lives in the same package directory
        _pkg = _Path(__file__).parent
        if str(_pkg) not in sys.path:
            sys.path.insert(0, str(_pkg))
        from router_integration_patch import wrap_router as _wrap_router

        original = Router.inspect_and_route

        def _patched(self, claim_map_path: str, run_id: str = "") -> dict:
            import uuid, json as _json
            from pathlib import Path as _P
            _run_id = run_id or f"router_{uuid.uuid4().hex[:12]}"

            # Load claim_map early so the pre-route query can inspect it
            try:
                _raw = _P(claim_map_path).read_text()
                _claim_map = _json.loads(_raw)
            except Exception:
                # If the file can't be read, fall through to original which
                # will surface the same error naturally
                return original(self, claim_map_path, run_id)

            model = _claim_map.get("model", "")
            gate_id = _claim_map.get("gate_id", "")

            # ── Pre-route brain query ────────────────────────────────────────
            try:
                from brain_query_before_route import query_before_route, apply_routing_adjustment
                adjustment = query_before_route(
                    task_config=_claim_map,
                    model=model,
                    gate_id=gate_id,
                    run_id=_run_id,
                )

                if adjustment is not None:
                    if getattr(adjustment, "is_blocking", False):
                        # Hard block — do not call original method
                        return {
                            "run_id": _run_id,
                            "artifact": _claim_map.get("artifact_name", ""),
                            "route": "hard_blocked",
                            "all_gates_passed": False,
                            "blocked": True,
                            "reason": getattr(adjustment, "reason", "brain hard_block"),
                            "recommendation": getattr(adjustment, "recommendation", ""),
                            "evidence_count": len(getattr(adjustment, "evidence", [])),
                            "gate_results": [],
                        }

                    # Soft adjustment — mutate claim_map and write back
                    _claim_map = apply_routing_adjustment(_claim_map, adjustment)
                    # Persist mutated claim_map so original method reads patched version
                    import tempfile, os
                    _tmp = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json", delete=False,
                        dir=str(_P(claim_map_path).parent)
                    )
                    _json.dump(_claim_map, _tmp)
                    _tmp.close()
                    claim_map_path = _tmp.name
                    # Clean up temp file after call
                    try:
                        result = original(self, claim_map_path, _run_id)
                    finally:
                        os.unlink(_tmp.name)
                    return result

            except ImportError:
                pass  # brain_query_before_route not available — proceed normally
            except Exception:
                pass  # Any brain error must not break routing

            return original(self, claim_map_path, _run_id)

        Router.inspect_and_route = _patched

    except ImportError:
        pass  # router_integration_patch not importable — router runs unpatched


_apply_wrap_router_patch()
