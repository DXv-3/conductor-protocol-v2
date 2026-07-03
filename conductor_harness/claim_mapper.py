import re
from typing import List, Optional

CLAIM_PATTERNS = {
    "cost_control": [r"cost cap enforced", r"cost cap reached"],
    "memory_persistence": [r"memory artifact", r"trace.*persist", r"first-class memory"],
    "background_collection": [r"just listen", r"background cycle"],
    "proof_gate": [r"proof_dashboard", r"proof gate", r"proof-gated"],
    "build_on_top": [r"buildontop", r"build on top", r"suitable_for_build_on_top"],
    "config_loading": [r"configurable", r"config", r"yaml"],
    "rewrite_behavior": [r"rewrite", r"canonical rewrite", r"tighten"]
}

def extract_claims(text: str, required_categories: Optional[List[str]] = None) -> List[dict]:
    if not text:
        return []
    if required_categories is None:
        from conductor_harness.policy import _policy_config
        required_categories = _policy_config.get("required_runtime_categories", [])
    claims = []
    idx = 1
    for category, patterns in CLAIM_PATTERNS.items():
        for pat in patterns:
            for m in re.finditer(pat, text, flags=re.I):
                claims.append({
                    "claim_id": f"CLAIM-{idx:03d}",
                    "text": text[max(0, m.start()-80):m.end()+80].strip(),
                    "category": category,
                    "required_for_production": category in required_categories,
                    "evidence_class": "asserted_unverified",
                    "sources": [],
                    "runtime_tests": [],
                    "notes": ""
                })
                idx += 1
    return claims
