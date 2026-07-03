import streamlit as st
from pathlib import Path
import json
import yaml
from conductor_harness.conductor import Conductor

st.set_page_config(page_title="Conductor v2 Provenance Gate", layout="wide")
st.title("Conductor Protocol v2 — Provenance‑Gated Promotion")

config_path = Path("configs/conductor.config.yaml")
if not config_path.exists():
    st.error("Missing conductor config.")
else:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    if st.button("Run Full Promotion Pipeline"):
        conductor = Conductor(config)
        report = conductor.run()
        st.subheader("Promotion Report")
        st.json(report["promotion_report"])
        if report["promotion_report"]["decision"] == "allowed":
            st.success("🎉 Bundle is canonical‑ready!")
        else:
            st.error("🚫 Bundle blocked. Review blocking claims.")
            st.write(report["promotion_report"]["blocking_claims"])
