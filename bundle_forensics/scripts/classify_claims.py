#!/usr/bin/env python3
"""Classify claims extracted from a bundle text file."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from conductor_harness.claim_mapper import extract_claims

def main():
    if len(sys.argv) < 2:
        print("Usage: classify_claims.py <bundle_text.md>")
        sys.exit(1)
    text = Path(sys.argv[1]).read_text()
    claims = extract_claims(text)
    print(json.dumps({"artifact_name": Path(sys.argv[1]).name, "claims": claims}, indent=2))

if __name__ == "__main__":
    main()
