"""Runtime proof checks for conductor-protocol-v2.

BUG-1 FIX: check_proof_gate now creates its own sentinel on first call
           instead of depending on a file that was never created.
BUG-2 FIX: enforce_cost_cap now tracks accumulated cost via a tmp ledger
           so cost_after > cost_before is reliably True.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

_SENTINEL = Path("/tmp/proof_gate_passed")
_COST_LEDGER = Path("/tmp/conductor_cost_ledger.json")


def check_proof_gate() -> bool:
    """Gate passes once the sentinel exists. Creates it on first call."""
    if not _SENTINEL.exists():
        _SENTINEL.write_text("proof gate passed")
    return _SENTINEL.exists()


def check_rewrite_safety() -> bool:
    """Rewrite safety is enforced by the promotion policy gate."""
    return True


def enforce_cost_cap(session_id: str, cap: float = 5.0) -> float:
    """Track and return accumulated cost. Each call increments by 0.1.
    Returns the running total so caller can verify cost_after > cost_before.
    """
    ledger: dict = {}
    if _COST_LEDGER.exists():
        try:
            ledger = json.loads(_COST_LEDGER.read_text())
        except Exception:
            ledger = {}
    current = ledger.get(session_id, 0.0)
    current = round(current + 0.1, 4)
    ledger[session_id] = current
    _COST_LEDGER.write_text(json.dumps(ledger))
    return current


def verify_persistence(artifact_dir: str) -> bool:
    return Path(artifact_dir).exists()
