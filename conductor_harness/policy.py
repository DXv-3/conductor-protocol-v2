from dataclasses import dataclass
from typing import Iterable, List
import yaml
from pathlib import Path

_policy_config = {}
try:
    _policy_path = Path(__file__).resolve().parent.parent / "configs/promotion.policy.yaml"
    with open(_policy_path) as f:
        _policy_config = yaml.safe_load(f)
except Exception:
    pass

BLOCKING = set(
    _policy_config.get("blocking_statuses", ["asserted_unverified", "contradicted", "reference_only", "unverified"])
)

@dataclass
class PromotionDecision:
    allowed: bool
    blocking_claims: List[str]
    notes: List[str]

def decide_promotion(claims: Iterable[dict]) -> PromotionDecision:
    blocking = []
    for c in claims:
        if c.get("required_for_production") and c.get("evidence_class") in BLOCKING:
            blocking.append(c["claim_id"])
    return PromotionDecision(
        allowed=len(blocking) == 0,
        blocking_claims=blocking,
        notes=["promotion denied until all required claims have runtime evidence"] if blocking else ["promotion allowed"]
    )
