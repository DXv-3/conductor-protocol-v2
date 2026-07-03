#!/usr/bin/env python3
import sys
import json
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conductor_harness.verifier import Verifier

def main():
    with open("configs/conductor.config.yaml") as f:
        config = yaml.safe_load(f)
    claim_path = Path("artifacts/claims/claim_map.json")
    if not claim_path.exists():
        print("No claim map. Run map_claims.py first.")
        return
    with open(claim_path) as f:
        claim_map = json.load(f)
    verifier = Verifier(config["evidence_dir"])
    evidence = verifier.run_all(claim_map)
    print(f"Runtime evidence saved. Summary: {evidence['summary']}")

if __name__ == "__main__":
    main()
