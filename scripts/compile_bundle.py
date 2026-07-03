#!/usr/bin/env python3
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conductor_harness.compiler import Compiler

def main():
    with open("configs/conductor.config.yaml") as f:
        config = yaml.safe_load(f)
    compiler = Compiler(config["skill_dir"], config["reference_doc"], config["build_script"])
    bundle = compiler.compile()
    output_path = Path("artifacts/bundles/bundle.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(bundle)
    print(f"Bundle compiled: {output_path}")

if __name__ == "__main__":
    main()
