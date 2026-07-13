from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope


@pytest.fixture
def canonical_event() -> AgentEventEnvelope:
    return AgentEventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": "whatsapp.handoff.demo.v1",
            "schema_version": "1.0",
            "occurred_at": datetime.now(UTC),
            "source_agent": "lead-intake-agent",
            "target_agent": "demo-command-center-agent",
            "tenant_id": "nxtutors",
            "region_id": None,
            "correlation_id": "test-correlation",
            "causation_id": None,
            "conversation_id": "conversation-ref",
            "actor": {"type": "user", "id": "user-ref"},
            "subject": {
                "lead_id": "lead-ref",
                "user_id": None,
                "tutor_id": None,
                "demo_id": None,
            },
            "idempotency_key": "test-idempotency-key",
            "traceparent": None,
            "pii_classification": "restricted",
            "payload": {"message_text": "demo please"},
        }
    )
