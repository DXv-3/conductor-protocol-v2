# CONDUCTOR_PROTOCOL_v2_MASTER.md

**Version:** 2.0 — Provenance‑Gated
**Status:** Draft until compiler provenance and runtime proof both pass

## 1. Purpose

Conductor v2 exists to close the gap between polished artifact generation and actual runtime truth. The videos show a repeatable generation pipeline driven by source reads and a build script, while the audits show that runtime claims about proof gating, config, cost, persistence, and background behavior repeatedly failed or regressed across versions.

## 2. Immutable loop

Observe -> Compile -> Trace provenance -> Extract claims -> Verify runtime -> Reclassify claims -> Decide promotion -> Canonicalize only if all required claims are runtime-backed.

## 3. Mandatory output contract

Every Conductor v2 output must contain:
- master artifact
- provenance trace
- claim map
- runtime evidence
- promotion report

## 4. Promotion invariant

No "production," "proof‑gated," or "validated" label may appear unless promotion passes.

## 5. Background mode

Background collection may continue, but any claims produced in background mode default to `reference_only` until explicit runtime verification upgrades them.

Exact audit gates for v2:
1. **Generation gate** — was the artifact generation path captured?
2. **Source gate** — which files, scripts, and references shaped output?
3. **Claim gate** — what nontrivial claims does the output make?
4. **Evidence gate** — what runtime artifacts prove each required claim?
5. **Contradiction gate** — does any audit or test refute a claim?
6. **Promotion gate** — does every required claim have `runtime_proven` status?
7. **Drift gate** — do compiler sources and runtime behavior disagree?
8. **Memory gate** — were provenance, claims, evidence, and report all persisted?
