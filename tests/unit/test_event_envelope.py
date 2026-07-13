from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope


def test_event_requires_schema_version_and_idempotency(
    canonical_event: AgentEventEnvelope,
) -> None:
    data: dict[str, Any] = canonical_event.model_dump()
    data.pop("idempotency_key")
    with pytest.raises(ValidationError):
        AgentEventEnvelope.model_validate(data)


def test_event_normalizes_aware_time_to_utc(canonical_event: AgentEventEnvelope) -> None:
    assert isinstance(canonical_event.occurred_at, datetime)
    offset = canonical_event.occurred_at.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0


def test_none_pii_classification_rejects_message(canonical_event: AgentEventEnvelope) -> None:
    data = canonical_event.model_dump()
    data["pii_classification"] = "none"
    with pytest.raises(ValidationError, match="contains PII"):
        AgentEventEnvelope.model_validate(data)
