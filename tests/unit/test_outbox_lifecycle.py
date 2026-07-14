from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.database.models import (
    AgentOutboxEvent,
    CommunicationMessage,
    DemoCase,
    DemoStateTransition,
    OnboardingHandoff,
    PaidTransition,
    PaymentOrder,
)
from demo_command_center.infrastructure.inbox.processor import DefaultInboxEventHandler
from demo_command_center.infrastructure.outbox.lifecycle import LifecycleOutboxDeliveryRecorder
from demo_command_center.security.encryption import PayloadCipher
from demo_command_center.state.machine.demo_state import DemoState


class ScalarRows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class FakeSession:
    def __init__(
        self,
        *,
        scalar_results: list[object | None],
        get_results: list[object | None],
        scalar_lists: list[list[object]] | None = None,
    ) -> None:
        self.scalar_results = scalar_results
        self.get_results = get_results
        self.scalar_lists = scalar_lists or []
        self.added: list[object] = []

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalar_results.pop(0)

    async def scalars(self, statement: object) -> ScalarRows:
        del statement
        return ScalarRows(self.scalar_lists.pop(0))

    async def get(self, entity: object, identifier: object, **kwargs: object) -> object | None:
        del entity, identifier, kwargs
        return self.get_results.pop(0)

    def add(self, instance: object) -> None:
        self.added.append(instance)


def _entities() -> tuple[PaymentOrder, PaidTransition, DemoCase]:
    now = datetime.now(UTC)
    demo_id = uuid4()
    order = PaymentOrder(
        id=uuid4(),
        tenant_id="tenant-1",
        demo_case_id=demo_id,
        domain_order_id="dcc-order-1",
        provider="cashfree",
        provider_order_id="900001",
        user_ref="user-1",
        customer_ref="customer-1",
        plan_ref="17",
        plan_version="a" * 64,
        amount_minor=50_000,
        currency="INR",
        purpose="demo_conversion",
        provider_environment="sandbox",
        status="paid",
        creation_idempotency_key="create-order-1",
        correlation_id="correlation-1",
        expires_at=now + timedelta(hours=1),
        paid_at=now,
        version=2,
    )
    paid = PaidTransition(
        id=uuid4(),
        payment_order_id=order.id,
        provider_payment_id="700001",
        website_activation_key="activation-key",
        verified_amount_minor=50_000,
        verified_currency="INR",
        verification_source="signed_webhook",
        transitioned_at=now,
    )
    demo = DemoCase(
        id=demo_id,
        tenant_id="tenant-1",
        conversation_id="conversation-1",
        state=DemoState.PAID.value,
        participant_timezone="Asia/Kolkata",
        flow_version="demo-flow-v1",
        version=4,
    )
    return order, paid, demo


def _cipher() -> PayloadCipher:
    return PayloadCipher.from_encoded_key("hex:" + "11" * 32)


@pytest.mark.asyncio
async def test_website_activation_ack_queues_minimized_onboarding_event() -> None:
    order, paid, demo = _entities()
    row = AgentOutboxEvent(
        id=1,
        event_id=uuid4(),
        event_type="demo.payment.verified.v1",
        schema_version="1.0",
        tenant_id="tenant-1",
        target_agent="nxtutors-website-gateway",
        idempotency_key="activation-key",
        correlation_id="correlation-1",
        payload_ciphertext=b"ciphertext",
        available_at=datetime.now(UTC),
        attempts=0,
    )
    fake = FakeSession(
        scalar_results=[order, paid, None],
        get_results=[demo],
        scalar_lists=[["consent-1"]],
    )
    recorder = LifecycleOutboxDeliveryRecorder(
        cipher=_cipher(),
        source_agent="demo-command-center-agent",
        onboarding_locale="en-IN",
        onboarding_policy_reference="onboarding-v1",
    )

    await recorder.record(
        row=row,
        payload={
            "demo_ref": str(demo.id),
            "provider_order_ref": order.provider_order_id,
            "payment_evidence_ref": paid.provider_payment_id,
        },
        provider_reference="activation-1",
        restricted_details={},
        session=cast(AsyncSession, fake),
    )

    handoff = next(item for item in fake.added if isinstance(item, OnboardingHandoff))
    assert handoff.status == "pending"
    outbox = next(item for item in fake.added if isinstance(item, AgentOutboxEvent))
    assert outbox.target_agent == "onboarding-agent"
    assert outbox.event_type == "onboarding.paid-user.requested.v1"


@pytest.mark.asyncio
async def test_onboarding_completion_converts_and_queues_welcome() -> None:
    order, paid, demo = _entities()
    demo.state = DemoState.ONBOARDING_HANDOFF.value
    handoff = OnboardingHandoff(
        id=uuid4(),
        tenant_id="tenant-1",
        paid_transition_id=paid.id,
        idempotency_key=f"onboarding-paid:{paid.id}",
        onboarding_required=True,
        status="accepted",
        attempt_count=1,
    )
    fake = FakeSession(
        scalar_results=[paid, handoff],
        get_results=[demo],
        scalar_lists=[[order]],
    )
    event = AgentEventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": "onboarding.completed.v1",
            "occurred_at": datetime.now(UTC).isoformat(),
            "source_agent": "onboarding-agent",
            "target_agent": "demo-command-center-agent",
            "tenant_id": "tenant-1",
            "correlation_id": "correlation-1",
            "conversation_id": "conversation-1",
            "actor": {"type": "system", "id": "onboarding-agent"},
            "subject": {"user_id": "user-1", "demo_id": str(demo.id)},
            "idempotency_key": f"onboarding-completed:{handoff.id}",
            "pii_classification": "low",
            "payload": {
                "demo_ref": str(demo.id),
                "user_ref": "user-1",
                "onboarding_ref": "onboarding-1",
                "completion_status": "completed",
            },
        }
    )
    handler = DefaultInboxEventHandler(
        default_timezone="Asia/Kolkata",
        cipher=_cipher(),
        key_reference="key-reference",
        onboarding_policy_reference="onboarding-v1",
        message_policy_reference="messages-v1",
        welcome_template_reference="paid.welcome.v1",
        welcome_message_version="welcome-v1",
    )

    await handler.handle(event, cast(AsyncSession, fake))

    assert demo.state == DemoState.CONVERTED.value
    assert handoff.status == "completed"
    assert any(isinstance(item, CommunicationMessage) for item in fake.added)
    assert any(isinstance(item, DemoStateTransition) for item in fake.added)
    welcome = next(item for item in fake.added if isinstance(item, AgentOutboxEvent))
    assert welcome.target_agent == "lead-intake-agent"


@pytest.mark.asyncio
async def test_onboarding_acceptance_requires_paid_context_and_advances_handoff() -> None:
    order, paid, demo = _entities()
    handoff = OnboardingHandoff(
        id=uuid4(),
        tenant_id="tenant-1",
        paid_transition_id=paid.id,
        idempotency_key=f"onboarding-paid:{paid.id}",
        onboarding_required=True,
        status="pending",
        attempt_count=0,
    )
    fake = FakeSession(
        scalar_results=[paid, handoff],
        get_results=[demo],
        scalar_lists=[[order]],
    )
    event = AgentEventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": "onboarding.handoff.accepted.v1",
            "occurred_at": datetime.now(UTC).isoformat(),
            "source_agent": "onboarding-agent",
            "target_agent": "demo-command-center-agent",
            "tenant_id": "tenant-1",
            "correlation_id": "correlation-1",
            "conversation_id": "conversation-1",
            "actor": {"type": "system", "id": "onboarding-agent"},
            "subject": {"user_id": "user-1", "demo_id": str(demo.id)},
            "idempotency_key": f"onboarding-accepted:{handoff.id}",
            "pii_classification": "low",
            "payload": {
                "demo_ref": str(demo.id),
                "user_ref": "user-1",
                "onboarding_ref": "onboarding-1",
                "inbox_ref": "inbox-1",
                "capability_version": "onboarding-v1",
            },
        }
    )
    handler = DefaultInboxEventHandler(
        default_timezone="Asia/Kolkata",
        cipher=_cipher(),
        key_reference="key-reference",
        onboarding_policy_reference="onboarding-v1",
    )

    await handler.handle(event, cast(AsyncSession, fake))

    assert demo.state == DemoState.ONBOARDING_HANDOFF.value
    assert handoff.status == "accepted"
    assert handoff.acknowledgement_ref == "onboarding-1"
    assert any(isinstance(item, DemoStateTransition) for item in fake.added)


@pytest.mark.asyncio
async def test_onboarding_event_fails_closed_for_ambiguous_payment_order() -> None:
    order, _, demo = _entities()
    duplicate_order, _, _ = _entities()
    duplicate_order.demo_case_id = order.demo_case_id
    duplicate_order.user_ref = order.user_ref
    fake = FakeSession(
        scalar_results=[],
        get_results=[],
        scalar_lists=[[order, duplicate_order]],
    )
    event = AgentEventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": "onboarding.handoff.accepted.v1",
            "occurred_at": datetime.now(UTC).isoformat(),
            "source_agent": "onboarding-agent",
            "target_agent": "demo-command-center-agent",
            "tenant_id": "tenant-1",
            "correlation_id": "correlation-1",
            "conversation_id": "conversation-1",
            "actor": {"type": "system", "id": "onboarding-agent"},
            "subject": {"user_id": "user-1", "demo_id": str(demo.id)},
            "idempotency_key": "onboarding-accepted:ambiguous",
            "pii_classification": "low",
            "payload": {
                "demo_ref": str(demo.id),
                "user_ref": "user-1",
                "onboarding_ref": "onboarding-1",
                "inbox_ref": "inbox-1",
                "capability_version": "onboarding-v1",
            },
        }
    )
    handler = DefaultInboxEventHandler(
        default_timezone="Asia/Kolkata",
        cipher=_cipher(),
        key_reference="key-reference",
        onboarding_policy_reference="onboarding-v1",
    )

    with pytest.raises(ValueError, match="multiple payment orders"):
        await handler.handle(event, cast(AsyncSession, fake))
