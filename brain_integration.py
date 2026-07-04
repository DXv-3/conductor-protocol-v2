"""brain_integration.py — conductor-protocol-v2 side of the-brain bridge.

This module resolves and lazily initializes the ConductorBridge,
handling all path resolution and import fallback logic so that
conductor-protocol-v2 continues to work even when the-brain is
not installed locally.

Resolution order for the-brain location:
  1. BRAIN_REPO_PATH environment variable
  2. Sibling directory: ../the-brain/
  3. ~/the-brain/
  4. BRAIN_DB_PATH env var (path directly to brain.db)

Usage within conductor-protocol-v2:
    from brain_integration import get_bridge
    bridge = get_bridge()
    if bridge:
        bridge.gate_event(run_id, gate_name, artifact, outcome, detail)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

_bridge_singleton = None
_bridge_resolved = False


def _resolve_brain_path() -> Optional[Path]:
    """Find the-brain repo root."""
    candidates = [
        os.environ.get("BRAIN_REPO_PATH", ""),
        str(Path(__file__).resolve().parent.parent / "the-brain"),
        str(Path.home() / "the-brain"),
        str(Path.home() / "repos" / "the-brain"),
        str(Path.home() / "dev" / "the-brain"),
        str(Path.home() / "projects" / "the-brain"),
    ]
    for c in candidates:
        if c:
            p = Path(c)
            # Valid if brain_sync.py is present
            if (p / "brain_sync.py").exists():
                return p
    return None


def get_bridge():
    """Return a ConductorBridge instance or None if unavailable."""
    global _bridge_singleton, _bridge_resolved
    if _bridge_resolved:
        return _bridge_singleton

    _bridge_resolved = True
    brain_path = _resolve_brain_path()

    if brain_path is None:
        print(
            "[brain_integration] WARNING: the-brain repo not found. "
            "Set BRAIN_REPO_PATH=/path/to/the-brain to enable brain sync. "
            "conductor-protocol-v2 will continue to work without brain sync."
        )
        _bridge_singleton = None
        return None

    # Add the-brain to sys.path so we can import conductor_bridge
    brain_str = str(brain_path)
    if brain_str not in sys.path:
        sys.path.insert(0, brain_str)

    try:
        from conductor_bridge import ConductorBridge  # type: ignore

        db_path = os.environ.get("BRAIN_DB_PATH", "")
        _bridge_singleton = ConductorBridge(
            db_path=db_path if db_path else None
        )
        print(f"[brain_integration] Connected to the-brain at: {brain_path}")
    except Exception as exc:
        print(f"[brain_integration] Could not initialize ConductorBridge: {exc}")
        _bridge_singleton = None

    return _bridge_singleton


def reset_bridge() -> None:
    """Force re-resolution of bridge on next get_bridge() call."""
    global _bridge_singleton, _bridge_resolved
    _bridge_singleton = None
    _bridge_resolved = False
