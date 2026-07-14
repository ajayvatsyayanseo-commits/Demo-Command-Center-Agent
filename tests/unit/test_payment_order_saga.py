from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4, uuid5

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.api.errors.taxonomy import ServiceError
from demo_command_center.infrastructure.database.models import (
    AgentOutboxEvent,
    DemoCase,
    DemoStateTransition,
    PaymentCheckoutSession,
    PaymentOrder,
    ProviderRequest,
)
from demo_command_center.infrastructure.payments import (
    PaymentOrderCommand,
    PaymentOrderJobService,
)
from demo_command_center.infrastructure.payments.contracts import (
    CashfreeOrderAcknowledgement,
)
from demo_command_center.infrastructure.payments.outbox_recorder import (
    PaymentOutboxDeliveryRecorder,
)
from demo_command_center.security.encryption import PayloadCipher
from demo_command_center.state.machine.demo_state import DemoState


class FakeSession:
    def __init__(self, scalar_results: list[object | None]) -> None:
        self.scalar_results = scalar_results
        self.added: list[object] = []

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalar_results.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        del args

    def begin(self) -> FakeSession:
        return self


class FakeSessions:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __call__(self) -> FakeSession:
        return self.session


def _cipher() -> PayloadCipher:
    return PayloadCipher.from_encoded_key("hex:" + "33" * 32)


def _recorder() -> PaymentOutboxDeliveryRecorder:
    return PaymentOutboxDeliveryRecorder(
        cipher=_cipher(),
        key_reference="kms:payment-test",
        cashfree_environment="sandbox",
        payment_expiry=timedelta(minutes=15),
    )


def _job_service(fake: FakeSession) -> PaymentOrderJobService:
    return PaymentOrderJobService(
        sessions=cast(async_sessionmaker[AsyncSession], FakeSessions(fake)),
        cipher=_cipher(),
        key_reference="kms:payment-test",
        request_hash_key="request-hash-key",
        tenant_id="tenant-1",
    )


def _quote_row(request_id: UUID) -> AgentOutboxEvent:
    return AgentOutboxEvent(
        id=1,
        event_id=request_id,
        event_type="payment.plan-quote.requested.v1",
        schema_version="1.0",
        tenant_id="tenant-1",
        target_agent="nxtutors-website-gateway",
        idempotency_key=str(request_id),
        correlation_id="correlation-1",
        payload_ciphertext=b"encrypted",
        available_at=datetime.now(UTC),
        attempts=0,
    )


def _quote_request(request_id: UUID, demo_id: UUID) -> dict[str, object]:
    return {
        "event_type": "payment.plan-quote.requested.v1",
        "request_id": str(request_id),
        "demo_ref": str(demo_id),
        "website_user_ref": "user-17",
        "plan_ref": "17",
        "customer_phone": "+919876543210",
        "purpose": "demo_conversion",
        "correlation_id": "correlation-1",
    }


def _quote() -> dict[str, object]:
    return {
        "plan_id": "17",
        "name": "Standard",
        "amount_minor": 50_000,
        "currency": "INR",
        "duration_days": 30,
        "eligible": True,
        "updated_at": datetime.now(UTC).isoformat(),
        "plan_version": "a" * 64,
        "user_ref": "user-17",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    }


@pytest.mark.asyncio
async def test_authoritative_quote_creates_bound_order_and_encrypted_cashfree_request() -> None:
    request_id = uuid4()
    demo = DemoCase(
        id=uuid4(),
        tenant_id="tenant-1",
        external_user_id="user-17",
        conversation_id="conversation-1",
        state=DemoState.CONVERSION_FOLLOW_UP.value,
        participant_timezone="Asia/Kolkata",
        flow_version="demo-flow-v1",
        version=3,
    )
    fake = FakeSession([None, demo, None, None])
    recorder = _recorder()
    await recorder.record(
        row=_quote_row(request_id),
        payload=_quote_request(request_id, demo.id),
        provider_reference="a" * 64,
        restricted_details=_quote(),
        session=cast(AsyncSession, fake),
    )

    order = next(value for value in fake.added if isinstance(value, PaymentOrder))
    cashfree = next(value for value in fake.added if isinstance(value, AgentOutboxEvent))
    transition = next(value for value in fake.added if isinstance(value, DemoStateTransition))
    assert order.amount_minor == 50_000
    assert order.user_ref == order.customer_ref == "user-17"
    assert order.plan_version == "a" * 64
    assert demo.state == DemoState.PAYMENT_PENDING.value
    assert transition.side_effects_completed == ["fetch_authoritative_quote"]
    assert cashfree.target_agent == "cashfree"
    plaintext = recorder.cipher.decrypt(
        cashfree.payload_ciphertext,
        associated_data=(f"tenant-1:cashfree:{cashfree.event_id}".encode()),
    )
    cashfree_request = json.loads(plaintext)
    assert cashfree_request["customer_phone"] == "+919876543210"
    assert "phone" not in order.__dict__


@pytest.mark.asyncio
async def test_request_job_persists_intent_before_any_provider_call() -> None:
    demo = DemoCase(
        id=uuid4(),
        tenant_id="tenant-1",
        external_user_id="user-17",
        conversation_id="conversation-1",
        state=DemoState.CONVERSION_FOLLOW_UP.value,
        participant_timezone="Asia/Kolkata",
        flow_version="demo-flow-v1",
        version=3,
    )
    fake = FakeSession([None, demo, None, None])
    service = _job_service(fake)
    command = PaymentOrderCommand(
        request_id=uuid4(),
        demo_ref=demo.id,
        website_user_ref="user-17",
        plan_ref="17",
        customer_phone="+919876543210",
    )
    result = await service.request(command, correlation_id="correlation-1")
    assert result.status == "quote_pending"
    provider_request = next(value for value in fake.added if isinstance(value, ProviderRequest))
    outbox = next(value for value in fake.added if isinstance(value, AgentOutboxEvent))
    assert provider_request.provider_reference == str(demo.id)
    assert provider_request.request_hash != "+919876543210"
    assert b"+919876543210" not in provider_request.request_hash.encode()
    assert outbox.target_agent == "nxtutors-website-gateway"
    plaintext = service.cipher.decrypt(
        outbox.payload_ciphertext,
        associated_data=f"tenant-1:nxtutors-website-gateway:{outbox.event_id}".encode(),
    )
    assert json.loads(plaintext)["customer_phone"] == "+919876543210"


@pytest.mark.asyncio
async def test_request_job_rejects_user_not_bound_to_demo_before_queueing() -> None:
    demo = DemoCase(
        id=uuid4(),
        tenant_id="tenant-1",
        external_user_id="another-user",
        conversation_id="conversation-1",
        state=DemoState.CONVERSION_FOLLOW_UP.value,
        participant_timezone="Asia/Kolkata",
        flow_version="demo-flow-v1",
        version=3,
    )
    fake = FakeSession([None, demo])
    with pytest.raises(ServiceError, match="not bound"):
        await _job_service(fake).request(
            PaymentOrderCommand(
                request_id=uuid4(),
                demo_ref=demo.id,
                website_user_ref="user-17",
                plan_ref="17",
                customer_phone="+919876543210",
            ),
            correlation_id="correlation-1",
        )
    assert fake.added == []


@pytest.mark.asyncio
async def test_request_job_rejects_a_second_active_order_for_demo() -> None:
    demo = DemoCase(
        id=uuid4(),
        tenant_id="tenant-1",
        external_user_id="user-17",
        conversation_id="conversation-1",
        state=DemoState.CONVERSION_FOLLOW_UP.value,
        participant_timezone="Asia/Kolkata",
        flow_version="demo-flow-v1",
        version=3,
    )
    fake = FakeSession([None, demo, uuid4()])
    with pytest.raises(ServiceError, match="active payment order"):
        await _job_service(fake).request(
            PaymentOrderCommand(
                request_id=uuid4(),
                demo_ref=demo.id,
                website_user_ref="user-17",
                plan_ref="17",
                customer_phone="+919876543210",
            ),
            correlation_id="correlation-1",
        )
    assert fake.added == []


def test_cashfree_ack_rejects_empty_checkout_session() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        CashfreeOrderAcknowledgement.model_validate(
            {
                "provider_order_id": "cf-order-17",
                "payment_session_id": "",
                "status": "ACTIVE",
            }
        )


@pytest.mark.asyncio
async def test_quote_rejects_cross_user_demo_binding() -> None:
    request_id = uuid4()
    demo = DemoCase(
        id=uuid4(),
        tenant_id="tenant-1",
        external_user_id="other-user",
        conversation_id="conversation-1",
        state=DemoState.CONVERSION_FOLLOW_UP.value,
        participant_timezone="Asia/Kolkata",
        flow_version="demo-flow-v1",
        version=3,
    )
    fake = FakeSession([None, demo])
    with pytest.raises(ServiceError, match="not bound"):
        await _recorder().record(
            row=_quote_row(request_id),
            payload=_quote_request(request_id, demo.id),
            provider_reference="a" * 64,
            restricted_details=_quote(),
            session=cast(AsyncSession, fake),
        )


@pytest.mark.asyncio
async def test_cashfree_ack_encrypts_session_and_keeps_only_safe_reference() -> None:
    request_id = uuid4()
    order = PaymentOrder(
        id=uuid5(request_id, "nxtutors:payment-order"),
        tenant_id="tenant-1",
        demo_case_id=uuid4(),
        domain_order_id="dcc-order-17",
        provider="cashfree",
        user_ref="user-17",
        customer_ref="user-17",
        plan_ref="17",
        plan_version="a" * 64,
        amount_minor=50_000,
        currency="INR",
        purpose="demo_conversion",
        provider_environment="sandbox",
        status="creating",
        creation_idempotency_key=str(request_id),
        correlation_id="correlation-1",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        version=1,
    )
    cashfree_event_id = uuid5(request_id, "nxtutors:cashfree-create-order")
    row = AgentOutboxEvent(
        id=2,
        event_id=cashfree_event_id,
        event_type="payment.cashfree-order.requested.v1",
        schema_version="1.0",
        tenant_id="tenant-1",
        target_agent="cashfree",
        idempotency_key=str(cashfree_event_id),
        correlation_id="correlation-1",
        payload_ciphertext=b"encrypted",
        available_at=datetime.now(UTC),
        attempts=0,
    )
    payload = {
        "event_type": "payment.cashfree-order.requested.v1",
        "request_id": str(request_id),
        "payment_order_id": str(order.id),
        "order_reference": order.domain_order_id,
        "amount_minor": order.amount_minor,
        "currency": order.currency,
        "customer_ref": order.customer_ref,
        "customer_phone": "+919876543210",
        "purpose": order.purpose,
        "correlation_id": row.correlation_id,
        "expires_at": order.expires_at.isoformat(),
    }
    fake = FakeSession([order, None, None])
    recorder = _recorder()
    await recorder.record(
        row=row,
        payload=payload,
        provider_reference="cf-order-17",
        restricted_details={
            "provider_order_id": "cf-order-17",
            "payment_session_id": "session-secret-17",
            "status": "ACTIVE",
        },
        session=cast(AsyncSession, fake),
    )

    checkout = next(value for value in fake.added if isinstance(value, PaymentCheckoutSession))
    assert order.provider_order_id == "cf-order-17"
    assert order.status == "pending"
    assert b"session-secret-17" not in checkout.session_ciphertext
    assert (
        recorder.cipher.decrypt(
            checkout.session_ciphertext,
            associated_data=f"payment-checkout-session:tenant-1:{order.id}".encode(),
        )
        == b"session-secret-17"
    )
