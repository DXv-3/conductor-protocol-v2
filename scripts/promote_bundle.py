#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conductor_harness.conductor import Conductor
import yaml

def main():
    with open("configs/conductor.config.yaml") as f:
        config = yaml.safe_load(f)
    conductor = Conductor(config)
    result = conductor.run()
    if result["promotion_report"]["decision"] == "allowed":
        print("Bundle CAN be promoted to canonical.")
    else:
        print("Bundle BLOCKED. See artifacts/reports/ for details.")

if __name__ == "__main__":
    main()
