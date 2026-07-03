#!/usr/bin/env python3
"""Extract and summarize provenance from a compiler trace JSON."""
import sys
import json
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_provenance.py <compiler_trace.json>")
        sys.exit(1)
    trace_path = Path(sys.argv[1])
    trace = json.loads(trace_path.read_text())
    print("=== Provenance Summary ===")
    print(f"Trace ID   : {trace.get('trace_id', 'N/A')}")
    print(f"Files read : {trace.get('files_read', [])}")
    print(f"Scripts    : {trace.get('scripts_invoked', [])}")
    print(f"Ref docs   : {trace.get('reference_docs_used', [])}")
    print(f"Outputs    : {trace.get('generated_outputs', [])}")

if __name__ == "__main__":
    main()
