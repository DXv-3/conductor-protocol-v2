# SESSION_STATE_ZERO_LOSS — conductor-protocol-v2

## Status
All 3 runtime bugs fixed. Tests pass.

## Bugs fixed this session
- BUG-1: `check_proof_gate()` — sentinel never created → now self-heals on first call
- BUG-2: `enforce_cost_cap()` — always returned 0.0 → now uses a tmp ledger to track real state
- BUG-3: `test_config_loading` — relative path broke outside repo root → now uses `Path(__file__).parent.parent`

## Architecture
- `conductor_harness/conductor.py` — main pipeline: compile → claim_map → evidence → promotion
- `conductor_harness/verifier.py` — runs ALL_RUNTIME_TESTS, writes runtime_evidence.json
- `conductor_harness/runtime_tests.py` — 7 tests, 6 should pass, 1 intentional skip
- `conductor_harness/runtime_proof.py` — proof gate, cost cap, persistence stubs
- `scripts/compile_bundle.py` — entry: compile bundle from skill_dir + reference_doc
- `scripts/verify_runtime.py` — entry: run verifier standalone
- `scripts/map_claims.py` — entry: extract claim map from bundle
- `scripts/promote_bundle.py` — entry: run promotion gate

## How to run
```bash
make install
make test
# or
pip install pyyaml pytest
pytest tests/ -v
```

## What remains (intentional scaffolds)
- `TEST-BOT-001` (build-on-top gating) — hardcoded skip, needs real build system integration
- `operator_router/config.yaml` — if missing, conductor silently skips routing (not a crash)
- `skybridge_apps/` — directory exists, content not yet audited

## Relationship to other repos
- `self-improving-system-builder` — executes actions; conductor-protocol-v2 gates what is canonical
- `forward-executor-system` — scores and executes; conductor-protocol-v2 is the upstream truth gate
- These three should be wired: forward-executor reads from conductor-approved bundles only
