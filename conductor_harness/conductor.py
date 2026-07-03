import json
from pathlib import Path
from datetime import datetime, timezone
from .compiler import Compiler
from .verifier import Verifier
from .evidence_store import EvidenceStore
from .policy import decide_promotion
from .schemas import validate

class Conductor:
    def __init__(self, config: dict):
        self.config = config
        self.compiler = Compiler(
            skill_dir=config["skill_dir"],
            reference_doc=config["reference_doc"],
            script=config["build_script"]
        )
        self.verifier = Verifier(evidence_dir=config["evidence_dir"])
        self.store = EvidenceStore(base_dir=config["artifacts_dir"])

    def run(self) -> dict:
        print("=== Conductor v2 Pipeline ===")
        bundle_text = self.compiler.compile()
        trace = self.compiler.trace
        trace_dict = {
            "trace_id": trace.trace_id,
            "session_id": trace.session_id,
            "artifact_name": trace.artifact_name,
            "source_videos": trace.source_videos,
            "files_read": trace.files_read,
            "commands_run": trace.commands_run,
            "reference_docs_used": trace.reference_docs_used,
            "scripts_invoked": trace.scripts_invoked,
            "generated_outputs": trace.generated_outputs,
            "timestamps": trace.timestamps,
            "operator_notes": trace.operator_notes
        }
        validate(trace_dict, "provenance_trace")
        self.store.store_provenance(trace_dict)
        print("1. Provenance trace captured.")

        from .claim_mapper import extract_claims
        required_cats = self.config.get("required_runtime_categories")
        claims = extract_claims(bundle_text, required_cats)
        claim_map = {"artifact_name": "bundle.md", "claims": claims}
        validate(claim_map, "claim_map")
        print("2. Claim map extracted.")

        evidence = self.verifier.run_all(claim_map, self.config)
        validate(evidence, "runtime_evidence")
        self.store.store_runtime_evidence(evidence)
        print("3. Runtime evidence collected.")

        self.store.store_claims(claim_map)
        print("   Claim map updated with runtime evidence.")

        decision = decide_promotion(claims)
        promotion_report = {
            "artifact_name": "bundle.md",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": "allowed" if decision.allowed else "blocked",
            "blocking_claims": decision.blocking_claims,
            "notes": decision.notes,
            "claim_statuses": [{"claim_id": c["claim_id"], "class": c["evidence_class"]} for c in claims]
        }
        validate(promotion_report, "promotion_report")
        self.store.store_promotion_report(promotion_report)
        print("4. Promotion decision:", "ALLOWED" if decision.allowed else "BLOCKED")
        if decision.blocking_claims:
            print(f"   Blocking claims: {decision.blocking_claims}")

        routing_decision = None
        try:
            from operator_router.router import Router
            router = Router(config_path="operator_router/config.yaml")
            routing_decision = router.inspect_and_route("artifacts/claims/claim_map.json")
        except Exception:
            pass

        return {
            "promotion_report": promotion_report,
            "routing_decision": routing_decision
        }
