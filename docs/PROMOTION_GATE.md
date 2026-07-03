# Promotion Gate

## State machine
`draft` → `compiled` → `claims_mapped` → `runtime_verified` → `promotion_pending` → `canonical` or `blocked`.

## Promotion algorithm
1. Compile bundle.
2. Extract provenance trace.
3. Extract claims from bundle.
4. Map claims to evidence.
5. Run runtime tests.
6. Reclassify claims.
7. Fail promotion if any required claim is `asserted_unverified`, `contradicted`, `reference_only`, or `unverified`.
8. Emit promotion report.
9. Only then mark canonical.

## Hard rule
A bundle may say:
- "compiled from reference sources" if provenance supports it.
- "runtime validated" only if runtime evidence supports it.
- "production" only if both compiler provenance and runtime evidence pass.
