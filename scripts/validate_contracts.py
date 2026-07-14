from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put", "trace"}


def _resolve_pointer(document: object, pointer: str) -> object:
    current = document
    for raw_part in pointer.removeprefix("#/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"unresolved local reference: {pointer}")
        current = current[part]
    return current


def _walk_local_references(document: object, root: object) -> None:
    if isinstance(document, dict):
        reference = document.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/"):
            _resolve_pointer(root, reference)
        for value in document.values():
            _walk_local_references(value, root)
    elif isinstance(document, list):
        for value in document:
            _walk_local_references(value, root)


def _validate_openapi(path: Path, document: dict[str, Any]) -> int:
    version = document.get("openapi")
    if not isinstance(version, str) or not version.startswith("3."):
        raise ValueError(f"OpenAPI 3.x declaration missing: {path}")
    info = document.get("info")
    paths = document.get("paths")
    if not isinstance(info, dict) or not {"title", "version"}.issubset(info):
        raise ValueError(f"OpenAPI info title/version missing: {path}")
    if not isinstance(paths, dict) or not paths:
        raise ValueError(f"OpenAPI paths must be a non-empty object: {path}")

    schemes = document.get("components", {}).get("securitySchemes", {})
    if not isinstance(schemes, dict):
        raise ValueError(f"OpenAPI securitySchemes must be an object: {path}")
    operation_ids: set[str] = set()
    operation_count = 0
    for route, path_item in paths.items():
        if not isinstance(route, str) or not route.startswith("/"):
            raise ValueError(f"OpenAPI route must start with '/': {path}: {route!r}")
        if not isinstance(path_item, dict):
            raise ValueError(f"OpenAPI path item must be an object: {path}: {route}")
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                raise ValueError(f"OpenAPI operation must be an object: {path}: {method} {route}")
            operation_id = operation.get("operationId")
            responses = operation.get("responses")
            if not isinstance(operation_id, str) or not operation_id:
                raise ValueError(f"OpenAPI operationId missing: {path}: {method} {route}")
            if operation_id in operation_ids:
                raise ValueError(f"duplicate OpenAPI operationId {operation_id!r}: {path}")
            if not isinstance(responses, dict) or not responses:
                raise ValueError(f"OpenAPI responses missing: {path}: {method} {route}")
            operation_ids.add(operation_id)
            operation_count += 1

            security = operation.get("security", document.get("security", []))
            if not isinstance(security, list):
                raise ValueError(f"OpenAPI security must be a list: {path}: {method} {route}")
            for requirement in security:
                if not isinstance(requirement, dict):
                    raise ValueError(f"invalid OpenAPI security requirement: {path}")
                unknown = set(requirement).difference(schemes)
                if unknown:
                    raise ValueError(
                        f"undefined OpenAPI security schemes {sorted(unknown)}: {path}"
                    )

    _walk_local_references(document, document)
    return operation_count


def main() -> None:
    contract_root = ROOT / "contracts"
    schemas: dict[Path, dict[str, object]] = {}
    json_count = 0
    yaml_count = 0
    operation_count = 0
    for path in sorted(contract_root.rglob("*.json")):
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
        json_count += 1
        if not isinstance(document, dict):
            raise ValueError(f"JSON contract must be an object: {path}")
        if path.name.endswith("schema.json") and "$schema" not in document:
            raise ValueError(f"JSON schema declaration missing: {path}")
        if path.name.endswith("schema.json"):
            Draft202012Validator.check_schema(document)
            schemas[path] = document
    for path in sorted(contract_root.rglob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        yaml_count += 1
        if not isinstance(document, dict):
            raise ValueError(f"YAML document must be an object: {path}")
        if "openapi" in document:
            operation_count += _validate_openapi(path, document)

    from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope

    example_path = contract_root / "events" / "example.whatsapp-handoff-demo.v1.json"
    with example_path.open(encoding="utf-8") as handle:
        example = json.load(handle)
    AgentEventEnvelope.model_validate(example)
    envelope_schema = schemas[contract_root / "events" / "agent-event-envelope.v1.schema.json"]
    format_checker = FormatChecker()
    Draft202012Validator(envelope_schema, format_checker=format_checker).validate(example)
    payload_schema = schemas[contract_root / "events" / "whatsapp-handoff-demo.v1.schema.json"]
    Draft202012Validator(payload_schema, format_checker=format_checker).validate(example["payload"])
    if example["event_type"] != "whatsapp.handoff.demo.v1":
        raise ValueError("WhatsApp handoff example has the wrong event_type")

    outbound_example_path = (
        contract_root / "lead_intake" / "example.outbound-delivery-requested.v1.json"
    )
    with outbound_example_path.open(encoding="utf-8") as handle:
        outbound_example = json.load(handle)
    outbound_schema = schemas[
        contract_root / "lead_intake" / "outbound-delivery-requested.v1.schema.json"
    ]
    Draft202012Validator(outbound_schema, format_checker=format_checker).validate(outbound_example)
    print(
        "contracts: valid "
        f"({len(schemas)} schemas, {json_count} JSON files, {yaml_count} YAML files, "
        f"{operation_count} OpenAPI operations)"
    )


if __name__ == "__main__":
    main()
