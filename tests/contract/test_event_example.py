from __future__ import annotations

import json
from pathlib import Path

from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope


def test_versioned_example_matches_pydantic_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "contracts" / "events" / "example.whatsapp-handoff-demo.v1.json"
    with path.open(encoding="utf-8") as handle:
        event = AgentEventEnvelope.model_validate(json.load(handle))
    assert event.event_type.endswith(".v1")
    assert event.idempotency_key
