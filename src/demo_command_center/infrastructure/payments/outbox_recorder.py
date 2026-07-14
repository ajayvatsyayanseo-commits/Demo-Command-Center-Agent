from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.infrastructure.database.models import (
    AgentOutboxEvent,
    DemoCase,
    DemoStateTransition,
    PaymentCheckoutSession,
    PaymentOrder,
    ProviderRequest,
)
from demo_command_center.infrastructure.payments.contracts import (
    AuthoritativePlanQuote,
    CashfreeOrderAcknowledgement,
    CashfreeOrderPayload,
    PlanQuoteRequestPayload,
)
from demo_command_center.security.encryption import PayloadCipher
from demo_command_center.state.machine.demo_state import DemoState
from demo_command_center.state.transitions.table import TransitionCommand


class DeliveryRecorder(Protocol):
    async def record(
        self,
        *,
        row: AgentOutboxEvent,
        payload: Mapping[str, Any],
        provider_reference: str,
        restricted_details: Mapping[str, Any],
        session: AsyncSession,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CompositeOutboxDeliveryRecorder:
    recorders: tuple[DeliveryRecorder, ...]

    async def record(
        self,
        *,
        row: AgentOutboxEvent,
        payload: Mapping[str, Any],
        provider_reference: str,
        restricted_details: Mapping[str, Any],
        session: AsyncSession,
    ) -> None:
        for recorder in self.recorders:
            await recorder.record(
                row=row,
                payload=payload,
                provider_reference=provider_reference,
                restricted_details=restricted_details,
                session=session,
            )


@dataclass(frozen=True, slots=True)
class PaymentOutboxDeliveryRecorder:
    cipher: PayloadCipher
    key_reference: str
    cashfree_environment: str
    payment_expiry: timedelta

    @staticmethod
    def _outbox_associated_data(tenant_id: str, target: str, event_id: UUID) -> bytes:
        return f"{tenant_id}:{target}:{event_id}".encode()

    @staticmethod
    def _checkout_associated_data(tenant_id: str, payment_order_id: UUID) -> bytes:
        return f"payment-checkout-session:{tenant_id}:{payment_order_id}".encode()

    async def record(
        self,
        *,
        row: AgentOutboxEvent,
        payload: Mapping[str, Any],
        provider_reference: str,
        restricted_details: Mapping[str, Any],
        session: AsyncSession,
    ) -> None:
        if row.event_type == "payment.plan-quote.requested.v1":
            await self._record_quote(row, payload, restricted_details, session)
        elif row.event_type == "payment.cashfree-order.requested.v1":
            await self._record_cashfree_order(
                row, payload, provider_reference, restricted_details, session
            )

    async def _record_quote(
        self,
        row: AgentOutboxEvent,
        raw_request: Mapping[str, Any],
        raw_quote: Mapping[str, Any],
        session: AsyncSession,
    ) -> None:
        request = PlanQuoteRequestPayload.model_validate(raw_request)
        quote = AuthoritativePlanQuote.model_validate(raw_quote)
        if (
            row.event_id != request.request_id
            or row.target_agent != "nxtutors-website-gateway"
            or str(request.request_id) != row.idempotency_key
            or request.correlation_id != row.correlation_id
            or quote.plan_id != request.plan_ref
            or quote.user_ref != request.website_user_ref
            or not quote.eligible
        ):
            raise ServiceError(
                ErrorCode.PAYMENT_MISMATCH,
                "The authoritative plan quote is not bound to this payment request",
            )
        now = datetime.now(UTC)
        if quote.expires_at <= now:
            raise ServiceError(ErrorCode.POLICY_REJECTED, "The authoritative plan quote expired")
        existing = await session.scalar(
            select(PaymentOrder)
            .where(
                PaymentOrder.tenant_id == row.tenant_id,
                PaymentOrder.creation_idempotency_key == row.idempotency_key,
            )
            .with_for_update()
        )
        if existing is not None:
            self._validate_existing_order(existing, request, quote)
            return
        demo = await session.scalar(
            select(DemoCase)
            .where(
                DemoCase.id == request.demo_ref,
                DemoCase.tenant_id == row.tenant_id,
            )
            .with_for_update()
        )
        if demo is None:
            raise ServiceError(ErrorCode.POLICY_REJECTED, "The demo does not exist")
        if demo.external_user_id != request.website_user_ref:
            raise ServiceError(
                ErrorCode.PAYMENT_MISMATCH,
                "The website user is not bound to this demo",
            )
        if demo.state != DemoState.CONVERSION_FOLLOW_UP.value:
            raise ServiceError(
                ErrorCode.INVALID_TRANSITION,
                "A standard-price payment can only start from conversion follow-up",
            )
        expires_at = min(quote.expires_at, now + self.payment_expiry)
        order_id = uuid5(request.request_id, "nxtutors:payment-order")
        domain_order_id = f"dcc-{demo.id.hex}-{request.request_id.hex[:16]}"
        order = PaymentOrder(
            id=order_id,
            tenant_id=row.tenant_id,
            demo_case_id=demo.id,
            domain_order_id=domain_order_id,
            provider="cashfree",
            user_ref=request.website_user_ref,
            customer_ref=request.website_user_ref,
            plan_ref=request.plan_ref,
            plan_version=quote.plan_version,
            amount_minor=quote.amount_minor,
            currency=quote.currency,
            purpose=request.purpose,
            provider_environment=self.cashfree_environment,
            status="creating",
            creation_idempotency_key=row.idempotency_key,
            correlation_id=row.correlation_id,
            expires_at=expires_at,
            version=1,
        )
        session.add(order)
        cashfree_event_id = uuid5(request.request_id, "nxtutors:cashfree-create-order")
        cashfree_payload = {
            "event_type": "payment.cashfree-order.requested.v1",
            "request_id": str(request.request_id),
            "payment_order_id": str(order.id),
            "order_reference": order.domain_order_id,
            "amount_minor": order.amount_minor,
            "currency": order.currency,
            "customer_ref": order.customer_ref,
            "customer_phone": request.customer_phone.get_secret_value(),
            "purpose": order.purpose,
            "correlation_id": row.correlation_id,
            "expires_at": order.expires_at.isoformat(),
        }
        encoded = json.dumps(cashfree_payload, sort_keys=True, separators=(",", ":")).encode()
        session.add(
            AgentOutboxEvent(
                event_id=cashfree_event_id,
                event_type="payment.cashfree-order.requested.v1",
                schema_version="1.0",
                tenant_id=row.tenant_id,
                target_agent="cashfree",
                idempotency_key=str(cashfree_event_id),
                correlation_id=row.correlation_id,
                payload_ciphertext=self.cipher.encrypt(
                    encoded,
                    associated_data=self._outbox_associated_data(
                        row.tenant_id, "cashfree", cashfree_event_id
                    ),
                ),
                available_at=now,
                attempts=0,
            )
        )
        demo.state = DemoState.PAYMENT_PENDING.value
        demo.version += 1
        session.add(
            DemoStateTransition(
                demo_case_id=demo.id,
                state_before=DemoState.CONVERSION_FOLLOW_UP.value,
                state_after=DemoState.PAYMENT_PENDING.value,
                command=TransitionCommand.REQUEST_PAYMENT.value,
                actor_type="user",
                actor_ref=request.website_user_ref,
                reason_code="AUTHORITATIVE_QUOTE_VERIFIED",
                occurred_at=now,
                correlation_id=row.correlation_id,
                idempotency_key=f"payment-request:{request.request_id}",
                flow_version=demo.flow_version,
                policy_version=quote.plan_version,
                side_effects_requested=["create_cashfree_order"],
                side_effects_completed=["fetch_authoritative_quote"],
            )
        )
        provider_request = await session.scalar(
            select(ProviderRequest).where(
                ProviderRequest.tenant_id == row.tenant_id,
                ProviderRequest.provider == "nxtutors-website-gateway",
                ProviderRequest.idempotency_key == row.idempotency_key,
            )
        )
        if provider_request is not None:
            provider_request.status = "quote_verified"
            provider_request.provider_reference = quote.plan_version

    @staticmethod
    def _validate_existing_order(
        order: PaymentOrder,
        request: PlanQuoteRequestPayload,
        quote: AuthoritativePlanQuote,
    ) -> None:
        if (
            order.demo_case_id != request.demo_ref
            or order.user_ref != request.website_user_ref
            or order.customer_ref != request.website_user_ref
            or order.plan_ref != request.plan_ref
            or order.plan_version != quote.plan_version
            or order.amount_minor != quote.amount_minor
            or order.currency != quote.currency
            or order.purpose != request.purpose
        ):
            raise ServiceError(
                ErrorCode.IDEMPOTENCY_CONFLICT,
                "The payment request replay does not match its persisted order",
            )

    async def _record_cashfree_order(
        self,
        row: AgentOutboxEvent,
        raw_request: Mapping[str, Any],
        provider_reference: str,
        raw_acknowledgement: Mapping[str, Any],
        session: AsyncSession,
    ) -> None:
        request = CashfreeOrderPayload.model_validate(raw_request)
        acknowledgement = CashfreeOrderAcknowledgement.model_validate(raw_acknowledgement)
        expected_order_id = uuid5(request.request_id, "nxtutors:payment-order")
        expected_event_id = uuid5(request.request_id, "nxtutors:cashfree-create-order")
        if (
            request.payment_order_id != expected_order_id
            or row.event_id != expected_event_id
            or row.idempotency_key != str(expected_event_id)
            or row.target_agent != "cashfree"
            or request.correlation_id != row.correlation_id
            or acknowledgement.provider_order_id != provider_reference
        ):
            raise ServiceError(
                ErrorCode.PAYMENT_MISMATCH,
                "Cashfree order acknowledgement is not bound to its durable request",
            )
        order = await session.scalar(
            select(PaymentOrder)
            .where(
                PaymentOrder.id == request.payment_order_id,
                PaymentOrder.tenant_id == row.tenant_id,
            )
            .with_for_update()
        )
        if order is None or (
            order.domain_order_id != request.order_reference
            or order.creation_idempotency_key != str(request.request_id)
            or order.amount_minor != request.amount_minor
            or order.currency != request.currency
            or order.customer_ref != request.customer_ref
            or order.purpose != request.purpose
            or order.expires_at != request.expires_at
        ):
            raise ServiceError(
                ErrorCode.PAYMENT_MISMATCH,
                "Cashfree order acknowledgement failed local binding checks",
            )
        if acknowledgement.status.upper() != "ACTIVE":
            order.status = "payment_review"
            raise ServiceError(
                ErrorCode.HUMAN_REVIEW_REQUIRED,
                "Cashfree created an order in an unexpected state",
            )
        if order.provider_order_id not in {None, acknowledgement.provider_order_id}:
            raise ServiceError(
                ErrorCode.IDEMPOTENCY_CONFLICT,
                "The local payment order already has another provider order",
            )
        order.provider_order_id = acknowledgement.provider_order_id
        order.status = "pending"
        order.reconcile_after = datetime.now(UTC)
        order.version += 1
        checkout = await session.scalar(
            select(PaymentCheckoutSession)
            .where(PaymentCheckoutSession.payment_order_id == order.id)
            .with_for_update()
        )
        session_ciphertext = self.cipher.encrypt(
            acknowledgement.payment_session_id.get_secret_value().encode(),
            associated_data=self._checkout_associated_data(row.tenant_id, order.id),
        )
        if checkout is None:
            session.add(
                PaymentCheckoutSession(
                    payment_order_id=order.id,
                    session_ciphertext=session_ciphertext,
                    key_reference=self.key_reference,
                    expires_at=order.expires_at,
                )
            )
        else:
            checkout.session_ciphertext = session_ciphertext
            checkout.key_reference = self.key_reference
            checkout.expires_at = order.expires_at
        provider_request = await session.scalar(
            select(ProviderRequest).where(
                ProviderRequest.tenant_id == row.tenant_id,
                ProviderRequest.provider == "nxtutors-website-gateway",
                ProviderRequest.idempotency_key == str(request.request_id),
            )
        )
        if provider_request is not None:
            provider_request.status = "ready"
            provider_request.provider_reference = acknowledgement.provider_order_id
