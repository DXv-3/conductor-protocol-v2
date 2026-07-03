import json
import jsonschema
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

def load_schema(name: str) -> dict:
    with open(SCHEMA_DIR / f"{name}.schema.json") as f:
        return json.load(f)

def validate(instance: dict, schema_name: str) -> None:
    schema = load_schema(schema_name)
    jsonschema.validate(instance, schema)
