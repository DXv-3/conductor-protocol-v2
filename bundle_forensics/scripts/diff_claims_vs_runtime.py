#!/usr/bin/env python3
"""Diff a claim map against runtime evidence and emit a drift report."""
import sys
import json
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("Usage: diff_claims_vs_runtime.py <claim_map.json> <runtime_evidence.json>")
        sys.exit(1)
    claim_map = json.loads(Path(sys.argv[1]).read_text())
    evidence = json.loads(Path(sys.argv[2]).read_text())

    covered_claims = set()
    for t in evidence.get("tests", []):
        if t["status"] == "pass":
            covered_claims.update(t.get("claims_covered", []))

    drift_lines = ["# Drift Report\n"]
    for claim in claim_map.get("claims", []):
        cid = claim["claim_id"]
        ec = claim.get("evidence_class", "asserted_unverified")
        if cid in covered_claims:
            drift_lines.append(f"- [{cid}] NO DRIFT — runtime_proven ✓")
        elif ec == "runtime_proven":
            drift_lines.append(f"- [{cid}] DRIFT — labeled runtime_proven but no passing test covers it ⚠️")
        else:
            drift_lines.append(f"- [{cid}] COMPILER-ONLY — {ec}")

    print("\n".join(drift_lines))

if __name__ == "__main__":
    main()
