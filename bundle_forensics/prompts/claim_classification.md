# Prompt: Claim Classification

You are classifying claims in an AI-generated bundle by evidence class.

Evidence classes:
- `runtime_proven`: a test artifact confirms this claim executed correctly
- `compiler_inferred`: the claim comes directly from compiler input sources
- `reference_only`: the claim exists only in reference/markdown docs
- `asserted_unverified`: stated in the bundle but no compiler or runtime evidence supports it
- `contradicted`: a test, audit, or prior run falsifies this claim

For each claim extracted from the bundle:
1. State the claim text.
2. Assign an evidence class.
3. Cite the source (file, test ID, or audit reference).
4. Flag if the claim is required for production promotion.
