# Bundle Forensics Master Spec

## Inputs
- `compiler_trace.json`: output of compiler step recording all files read and scripts invoked
- `bundle_text.md`: the compiled bundle artifact

## Outputs
- `claim_map.json`: every nontrivial claim with evidence class
- `drift_report.md`: discrepancies between compiler-observed claims and runtime-proven claims

## Drift classification
- **No drift**: claim is runtime_proven and compiler_observed
- **Compiler-only drift**: claim present in compiler sources but not runtime verified
- **Runtime-only**: claim emerges at runtime with no compiler lineage (rare; escalate)
- **Contradicted**: runtime explicitly falsifies a compiler claim
