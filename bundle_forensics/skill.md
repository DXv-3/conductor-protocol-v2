# Bundle Forensics Skill

Install into Claude Code / Codex as an agent skill.

## Trigger
When asked to audit a bundle, forensically examine a build artifact, or detect claim drift.

## Steps
1. Read `compiler_trace.json` to understand generation lineage.
2. Read `bundle_text.md` and extract all nontrivial claims.
3. Compare claims against `runtime_evidence.json`.
4. Classify each claim: `runtime_proven`, `compiler_inferred`, `reference_only`, `contradicted`.
5. Emit `claim_map.json` and `drift_report.md`.

## Hard rules
- Never label a claim `runtime_proven` without a concrete test artifact.
- Always emit a drift report even if no drift is found.
