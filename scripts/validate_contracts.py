from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    contract_root = ROOT / "contracts"
    schemas: dict[Path, dict[str, object]] = {}
    for path in sorted(contract_root.rglob("*.json")):
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
        if path.name.endswith("schema.json") and "$schema" not in document:
            raise ValueError(f"JSON schema declaration missing: {path}")
        if path.name.endswith("schema.json"):
            Draft202012Validator.check_schema(document)
            schemas[path] = document
    for path in sorted(contract_root.rglob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        if not isinstance(document, dict):
            raise ValueError(f"YAML document must be an object: {path}")
        if "openapi" in document and not {"info", "paths"}.issubset(document):
            raise ValueError(f"OpenAPI document missing info/paths: {path}")

    from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope

    example_path = contract_root / "events" / "example.whatsapp-handoff-demo.v1.json"
    with example_path.open(encoding="utf-8") as handle:
        example = json.load(handle)
    AgentEventEnvelope.model_validate(example)
    envelope_schema = schemas[contract_root / "events" / "agent-event-envelope.v1.schema.json"]
    Draft202012Validator(envelope_schema).validate(example)
    print("contracts: valid")


if __name__ == "__main__":
    main()
