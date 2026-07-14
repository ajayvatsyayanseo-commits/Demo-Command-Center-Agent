from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.database.models import (
    AgentOutboxEvent,
    DemoCase,
    PaidTransition,
    PaymentAttempt,
    PaymentOrder,
    ProviderWebhookEvent,
)
from demo_command_center.infrastructure.inbox.processor import DefaultInboxEventHandler
from demo_command_center.security.encryption import PayloadCipher
from demo_command_center.state.machine.demo_state import DemoState


class FakeSession:
    def __init__(self, scalar_results: list[object | None]) -> None:
        self.scalar_results = scalar_results
        self.added: list[object] = []

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        for instance in self.added:
            if isinstance(instance, ProviderWebhookEvent) and instance.id is None:
                instance.id = 41

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalar_results.pop(0)


def _order(now: datetime) -> PaymentOrder:
    return PaymentOrder(
        id=uuid4(),
        tenant_id="tenant-1",
        demo_case_id=uuid4(),
        domain_order_id="dcc-order-1",
        provider="cashfree",
        provider_order_id="900001",
        user_ref="website-user-1",
        customer_ref="customer-1",
        plan_ref="17",
        plan_version="a" * 64,
        amount_minor=50_000,
        currency="INR",
        purpose="demo_conversion",
        provider_environment="sandbox",
        status="pending",
        creation_idempotency_key="create-order-1",
        correlation_id="correlation-1",
        expires_at=now + timedelta(hours=1),
        version=1,
    )


def _demo(order: PaymentOrder) -> DemoCase:
    return DemoCase(
        id=order.demo_case_id,
        tenant_id=order.tenant_id,
        conversation_id="conversation-1",
        state=DemoState.PAYMENT_PENDING.value,
        participant_timezone="Asia/Kolkata",
        flow_version="demo-flow-v1",
        version=3,
    )


def _event(now: datetime, *, amount: str = "500.00") -> AgentEventEnvelope:
    return AgentEventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": "cashfree.payment.webhook.received.v1",
            "schema_version": "1.0",
            "occurred_at": now.isoformat(),
            "source_agent": "cashfree",
            "target_agent": "demo-command-center-agent",
            "tenant_id": "tenant-1",
            "correlation_id": "correlation-1",
            "conversation_id": "provider-cashfree",
            "actor": {"type": "provider", "id": "cashfree"},
            "subject": {},
            "idempotency_key": f"cashfree:{uuid4()}",
            "pii_classification": "restricted",
            "payload": {
                "type": "PAYMENT_SUCCESS_WEBHOOK",
                "data": {
                    "order": {
                        "order_id": "dcc-order-1",
                        "cf_order_id": 900001,
                        "order_tags": {
                            "purpose": "demo_conversion",
                            "environment": "sandbox",
                        },
                    },
                    "payment": {
                        "cf_payment_id": 700001,
                        "payment_status": "SUCCESS",
                        "payment_currency": "INR",
                        "payment_amount": amount,
                    },
                    "customer_details": {"customer_id": "customer-1"},
                },
            },
        }
    )


def _handler() -> DefaultInboxEventHandler:
    cipher = PayloadCipher.from_encoded_key("hex:" + "11" * 32)
    return DefaultInboxEventHandler(
        default_timezone="Asia/Kolkata",
        cipher=cipher,
        key_reference="test-key-reference",
        cashfree_environment="sandbox",
    )


@pytest.mark.asyncio
async def test_verified_cashfree_terminal_success_transitions_paid_once() -> None:
    now = datetime.now(UTC)
    order = _order(now)
    demo = _demo(order)
    fake = FakeSession([order, None, demo])

    await _handler().handle(_event(now), cast(AsyncSession, fake))

    assert order.status == "paid"
    assert demo.state == DemoState.PAID.value
    assert any(isinstance(item, PaymentAttempt) for item in fake.added)
    assert any(isinstance(item, PaidTransition) for item in fake.added)
    outbox = next(item for item in fake.added if isinstance(item, AgentOutboxEvent))
    assert outbox.target_agent == "nxtutors-website-gateway"
    assert outbox.event_type == "demo.payment.verified.v1"


@pytest.mark.asyncio
async def test_cashfree_amount_mismatch_is_held_for_review() -> None:
    now = datetime.now(UTC)
    order = _order(now)
    fake = FakeSession([order, None])

    await _handler().handle(_event(now, amount="499.99"), cast(AsyncSession, fake))

    assert order.status == "payment_review"
    assert not any(isinstance(item, PaidTransition) for item in fake.added)
    assert not any(isinstance(item, AgentOutboxEvent) for item in fake.added)
