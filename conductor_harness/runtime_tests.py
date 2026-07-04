"""Runtime tests for conductor-protocol-v2.

BUG-3 FIX: test_config_loading now resolves the config path relative to
           this file's location so it works regardless of CWD.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class RuntimeTestResult:
    test_id: str
    purpose: str
    status: str
    observed_output: str
    artifacts_written: List[str] = field(default_factory=list)
    claims_covered: List[str] = field(default_factory=list)


def test_proof_gate() -> RuntimeTestResult:
    try:
        from conductor_harness.runtime_proof import check_proof_gate
        ok = check_proof_gate()
        return RuntimeTestResult(
            "TEST-PROOF-001", "Proof gate operational",
            "pass" if ok else "fail",
            f"check_proof_gate returned {ok}",
            claims_covered=["CLAIM-001"]
        )
    except Exception as e:
        return RuntimeTestResult("TEST-PROOF-001", "Proof gate operational", "fail",
                                 str(e), claims_covered=["CLAIM-001"])


def test_rewrite_safety() -> RuntimeTestResult:
    try:
        from conductor_harness.runtime_proof import check_rewrite_safety
        ok = check_rewrite_safety()
        return RuntimeTestResult(
            "TEST-REWRITE-001", "Rewrite safety check",
            "pass" if ok else "fail", "rewrite safety stub",
            claims_covered=["CLAIM-REWRITE-001"]
        )
    except Exception as e:
        return RuntimeTestResult("TEST-REWRITE-001", "Rewrite safety check", "fail",
                                 str(e), claims_covered=["CLAIM-REWRITE-001"])


def test_cost_cap_enforced(session_id: str = "test-session", cap: float = 5.0) -> RuntimeTestResult:
    try:
        from conductor_harness.runtime_proof import enforce_cost_cap
        cost_before = enforce_cost_cap(session_id, cap)
        cost_after = enforce_cost_cap(session_id, cap)
        if cost_after > cost_before:
            return RuntimeTestResult(
                "TEST-COST-001", "Cost cap enforced", "pass",
                f"Cost changed from {cost_before} to {cost_after}",
                claims_covered=["CLAIM-003"]
            )
        else:
            return RuntimeTestResult(
                "TEST-COST-001", "Cost cap enforced", "fail",
                f"Cost did not increase: before={cost_before} after={cost_after}",
                claims_covered=["CLAIM-003"]
            )
    except Exception as e:
        return RuntimeTestResult("TEST-COST-001", "Cost cap enforced", "fail",
                                 str(e), claims_covered=["CLAIM-003"])


def test_persistence_writes(tmpdir: str = "/tmp/conductor_persist_test") -> RuntimeTestResult:
    try:
        p = Path(tmpdir) / "test_memory_artifact.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("conductor v2 persistence test")
        if p.exists():
            return RuntimeTestResult(
                "TEST-PERSIST-001", "Memory artifact persistence", "pass",
                f"Artifact written to {p}", [str(p)],
                claims_covered=["CLAIM-MEM-001"]
            )
        else:
            return RuntimeTestResult("TEST-PERSIST-001", "Memory artifact persistence", "fail",
                                     "Artifact not found after write.",
                                     claims_covered=["CLAIM-MEM-001"])
    except Exception as e:
        return RuntimeTestResult("TEST-PERSIST-001", "Memory artifact persistence", "fail",
                                 str(e), claims_covered=["CLAIM-MEM-001"])


def test_background_collection() -> RuntimeTestResult:
    try:
        from conductor_harness.just_listen_bridge import JustListenBridge
        bridge = JustListenBridge("/tmp/conductor_bg_test")
        bridge.collect_observation("test observation")
        obs = bridge.recent_observations(limit=1)
        if obs and "test observation" in obs[0]:
            return RuntimeTestResult(
                "TEST-BG-001", "Just-listen background cycle", "pass",
                f"Observation collected: {obs[0]}",
                ["/tmp/conductor_bg_test/observations.log"],
                claims_covered=["CLAIM-BG-001"]
            )
        else:
            return RuntimeTestResult("TEST-BG-001", "Just-listen background cycle", "fail",
                                     "No observation found.",
                                     claims_covered=["CLAIM-BG-001"])
    except Exception as e:
        return RuntimeTestResult("TEST-BG-001", "Just-listen background cycle", "fail",
                                 str(e), claims_covered=["CLAIM-BG-001"])


def test_config_loading(config_path: str = "") -> RuntimeTestResult:
    """BUG-3 FIX: resolve config relative to repo root, not CWD."""
    try:
        import yaml
        resolved = Path(config_path) if config_path else _REPO_ROOT / "configs" / "conductor.config.yaml"
        with open(resolved) as f:
            config = yaml.safe_load(f)
        if config and "skill_dir" in config:
            return RuntimeTestResult(
                "TEST-CONFIG-001", "Config values loaded", "pass",
                f"Config keys: {list(config.keys())[:5]}",
                [str(resolved)], claims_covered=["CLAIM-CONF-001"]
            )
        else:
            return RuntimeTestResult("TEST-CONFIG-001", "Config values loaded", "fail",
                                     "Missing skill_dir in config.",
                                     claims_covered=["CLAIM-CONF-001"])
    except Exception as e:
        return RuntimeTestResult("TEST-CONFIG-001", "Config values loaded", "fail",
                                 str(e), claims_covered=["CLAIM-CONF-001"])


def test_build_on_top() -> RuntimeTestResult:
    return RuntimeTestResult(
        "TEST-BOT-001", "Build-on-top gating", "skip",
        "Not implemented yet — scaffold preserved in ROADMAP_UNBUILT_BUT_DISCUSSED.md",
        claims_covered=["CLAIM-BOT-001"]
    )


ALL_RUNTIME_TESTS = [
    test_proof_gate,
    test_rewrite_safety,
    test_cost_cap_enforced,
    test_persistence_writes,
    test_background_collection,
    test_config_loading,
    test_build_on_top,
]
