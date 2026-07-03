"""Stubs for runtime proof checks."""
from pathlib import Path

def check_proof_gate() -> bool:
    return Path("/tmp/proof_gate_passed").exists()

def check_rewrite_safety() -> bool:
    return True

def enforce_cost_cap(session_id: str, cap: float = 5.0) -> float:
    return 0.0

def verify_persistence(artifact_dir: str) -> bool:
    return Path(artifact_dir).exists()
