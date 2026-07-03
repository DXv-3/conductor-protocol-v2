FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p artifacts/bundles artifacts/provenance artifacts/evidence \
            artifacts/claims artifacts/reports

CMD ["python", "scripts/promote_bundle.py"]
