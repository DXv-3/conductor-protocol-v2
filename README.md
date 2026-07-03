# Conductor Protocol v2.0 — Provenance‑Gated Production Bundle

**Status:** Compiler + Runtime split
**Purpose:** Prevent polished bundle output from outrunning actual system truth.

**Why v2 exists**
The earlier bundle‑generation flow visibly read `SKILL.md`, `build-bundle.py`, and `conductor-v1-full-bundle.md` before emitting the final bundle, which means the artifact was assembled from upstream source materials rather than demonstrated purely by live runtime behavior in that moment. The same recordings show shell inspection and file reads, but they do not show proof execution, config loading, persistence writes, or background-cycle validation, so v2 must separate artifact provenance from runtime truth.

**Core Rule**
No bundle may be marked canonical, production, validated, proof‑gated, or build‑on‑top‑ready unless:
1. A provenance trace exists.
2. A claim map exists.
3. Runtime evidence exists.
4. Promotion policy confirms that all required claims are backed by runtime evidence rather than reference‑only sources.

**Artifact Classes**
- `provenance_trace`: what inputs and steps generated the artifact.
- `claim_map`: every nontrivial claim extracted from the bundle, tagged by evidence class.
- `runtime_evidence`: concrete proof that code paths, persistence, configs, and gates actually executed.
- `promotion_report`: final pass/fail decision for canonical promotion.

## Quickstart

```bash
make install
make pipeline
make test
make demo
```
