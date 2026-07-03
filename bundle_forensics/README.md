# Bundle Forensics

Forensic toolkit for auditing Conductor bundles post-generation.

## Purpose
- Extract provenance from compiler traces
- Classify all claims by evidence class
- Diff claims against runtime behavior to detect drift

## Usage
```bash
python scripts/extract_provenance.py <compiler_trace.json>
python scripts/classify_claims.py <bundle_text.md>
python scripts/diff_claims_vs_runtime.py <claim_map.json> <runtime_evidence.json>
```
