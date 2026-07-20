from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.database.models import (
    AgentOutboxEvent,
    ConversationState,
    DemoRequirement,
)
from demo_command_center.infrastructure.inbox.processor import DefaultInboxEventHandler
from demo_command_center.security.encryption import PayloadCipher


class FakeSession:
    def __init__(self, scalar_results: list[object | None]) -> None:
        self.scalar_results = scalar_results
        self.added: list[object] = []

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalar_results.pop(0)


def _cipher() -> PayloadCipher:
    return PayloadCipher.from_encoded_key("hex:" + "22" * 32)


def _handler(cipher: PayloadCipher) -> DefaultInboxEventHandler:
    return DefaultInboxEventHandler(
        default_timezone="Asia/Kolkata",
        cipher=cipher,
        key_reference="test-key-reference",
    )


def _event(text: str) -> AgentEventEnvelope:
    now = datetime.now(UTC)
    return AgentEventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": "whatsapp.handoff.demo.v1",
            "schema_version": "1.0",
            "occurred_at": now.isoformat(),
            "source_agent": "lead-intake-agent",
            "target_agent": "demo-command-center-agent",
            "tenant_id": "nxtutors",
            "region_id": None,
            "correlation_id": "corr-requirements",
            "causation_id": "provider-message-ref",
            "conversation_id": "conversation-ref",
            "actor": {"type": "user", "id": "opaque-user"},
            "subject": {"lead_id": "lead-ref", "user_id": None, "tutor_id": None, "demo_id": None},
            "idempotency_key": f"lead:message:{uuid4()}",
            "traceparent": None,
            "pii_classification": "restricted",
            "payload": {
                "provider_message_ref": str(uuid4()),
                "intent": "demo_request",
                "lead_ref": "lead-ref",
                "user_ref": None,
                "message": {"type": "text", "text": text},
                "service_window": {
                    "last_user_message_at": now.isoformat(),
                    "expires_at": (now + timedelta(hours=23)).isoformat(),
                },
                "consent_refs": [],
            },
        }
    )


def _outbox_payload(outbox: AgentOutboxEvent, cipher: PayloadCipher) -> dict[str, object]:
    plaintext = cipher.decrypt(
        outbox.payload_ciphertext,
        associated_data=f"nxtutors:lead-intake-agent:{outbox.event_id}".encode(),
    )
    value = json.loads(plaintext)
    assert isinstance(value, dict)
    return value


@pytest.mark.asyncio
async def test_subject_correction_clears_previous_subject_instead_of_reusing_it() -> None:
    cipher = _cipher()
    demo_id = uuid4()
    conversation = ConversationState(
        tenant_id="nxtutors",
        demo_case_id=demo_id,
        conversation_id="conversation-ref",
        current_step="collect_class_city",
        safe_summary="Class 7 | Mathematics | Gurugram",
        flow_version="demo-flow-v1",
        version=1,
    )
    requirement = DemoRequirement(
        demo_case_id=demo_id,
        class_level=None,
        subject="Mathematics",
        location_region=None,
        timezone="Asia/Kolkata",
        preferred_times=[],
        missing_fields=["class_level", "location_region", "mode", "preferred_times"],
        version=1,
    )
    fake = FakeSession([conversation, requirement])

    await _handler(cipher).handle(
        _event("no i dont want mathematics i want to do it feom sgarting"),
        cast(AsyncSession, fake),
    )

    assert requirement.subject is None
    assert requirement.learning_goal == "Start from the beginning"
    assert "subject" in requirement.missing_fields
    outbox = next(item for item in fake.added if isinstance(item, AgentOutboxEvent))
    payload = _outbox_payload(outbox, cipher)
    variables = payload["variables"]
    assert isinstance(variables, dict)
    assert "Mathematics" not in variables["body"]


@pytest.mark.asyncio
async def test_class_city_reply_after_subject_clear_prompts_for_subject_not_old_maths() -> None:
    cipher = _cipher()
    demo_id = uuid4()
    conversation = ConversationState(
        tenant_id="nxtutors",
        demo_case_id=demo_id,
        conversation_id="conversation-ref",
        current_step="collect_class_city",
        safe_summary="Demo requested; requirements pending.",
        flow_version="demo-flow-v1",
        version=1,
    )
    requirement = DemoRequirement(
        demo_case_id=demo_id,
        subject=None,
        timezone="Asia/Kolkata",
        preferred_times=[],
        missing_fields=["class_level", "subject", "location_region", "mode", "preferred_times"],
        version=1,
    )
    fake = FakeSession([conversation, requirement])

    await _handler(cipher).handle(_event("class 7 Gurgaon"), cast(AsyncSession, fake))

    assert requirement.class_level == "Class 7"
    assert requirement.location_region == "Gurugram"
    assert requirement.subject is None
    outbox = next(item for item in fake.added if isinstance(item, AgentOutboxEvent))
    payload = _outbox_payload(outbox, cipher)
    variables = payload["variables"]
    assert isinstance(variables, dict)
    assert variables["current_step"] == "collect_subject"
    assert "Which subject or skill" in variables["body"]
    assert "Mathematics" not in variables["body"]


@pytest.mark.asyncio
async def test_replacement_subject_and_timing_complete_requirements() -> None:
    cipher = _cipher()
    demo_id = uuid4()
    conversation = ConversationState(
        tenant_id="nxtutors",
        demo_case_id=demo_id,
        conversation_id="conversation-ref",
        current_step="collect_preferred_times",
        safe_summary="Class 7 | Skating | Gurugram | online",
        flow_version="demo-flow-v1",
        version=1,
    )
    requirement = DemoRequirement(
        demo_case_id=demo_id,
        class_level="Class 7",
        subject="Skating",
        mode="online",
        location_region="Gurugram",
        timezone="Asia/Kolkata",
        preferred_times=[],
        missing_fields=["preferred_times"],
        version=1,
    )
    fake = FakeSession([conversation, requirement])

    await _handler(cipher).handle(_event("1"), cast(AsyncSession, fake))

    assert requirement.preferred_times == [{"label": "morning"}]
    assert requirement.missing_fields == []
    outbox = next(item for item in fake.added if isinstance(item, AgentOutboxEvent))
    payload = _outbox_payload(outbox, cipher)
    variables = payload["variables"]
    assert isinstance(variables, dict)
    assert variables["current_step"] == "requirements_complete"
    assert "Class 7 | Skating | Gurugram | online | morning" in variables["body"]
