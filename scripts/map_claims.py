#!/usr/bin/env python3
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conductor_harness.claim_mapper import extract_claims

def main():
    bundle_path = Path("artifacts/bundles/bundle.md")
    if not bundle_path.exists():
        print("No bundle found. Run compile_bundle.py first.")
        return
    text = bundle_path.read_text()
    claims = extract_claims(text)
    claim_map = {"artifact_name": "bundle.md", "claims": claims}
    out_path = Path("artifacts/claims/claim_map.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(claim_map, indent=2))
    print(f"Claim map written to {out_path}")

if __name__ == "__main__":
    main()
