.PHONY: install compile map verify promote test demo clean

install:
	pip install -r requirements.txt

compile:
	python scripts/compile_bundle.py

map:
	python scripts/map_claims.py

verify:
	python scripts/verify_runtime.py

promote:
	python scripts/promote_bundle.py

pipeline: compile map verify promote

test:
	pytest tests/ operator_router/tests/ -v

demo:
	streamlit run skybridge_apps/conductor_demo/app.py

clean:
	rm -rf artifacts/bundles/* artifacts/provenance/* artifacts/evidence/* \
	       artifacts/claims/* artifacts/reports/* \
	       /tmp/conductor_persist_test /tmp/conductor_bg_test
