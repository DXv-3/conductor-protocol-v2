# Claim Evidence Policy

## Required claim classes (promotion‑blocking)
- proof gate works
- rewrite is safe
- cost cap enforced
- trace memory persists
- just‑listen logic functions
- config values are actually loaded
- build‑on‑top only occurs after valid gate pass

## Claim statuses (evidence classes)
- `runtime_proven`: keep.
- `compiler_inferred`: may remain only if labeled "compiler provenance".
- `reference_only`: allowed in design docs, blocked in production claims.
- `asserted_unverified`: blocked.
- `contradicted`: blocked and escalated.

## Example
```json
{
  "artifact_name": "CONDUCTOR_PROTOCOL_v2_MASTER.md",
  "claims": [
    {
      "claim_id": "CLAIM-001",
      "text": "Cost cap enforced per session.",
      "category": "cost_control",
      "required_for_production": true,
      "evidence_class": "contradicted",
      "sources": [{"kind": "audit", "ref": "code_file:8"}],
      "runtime_tests": ["TEST-COST-001"],
      "notes": "current_cost remained 0.0 after cycle in audited v1."
    }
  ]
}
```
