from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.infrastructure.database.models import (
    AgentOutboxEvent,
    DemoCase,
    PaymentCheckoutSession,
    PaymentOrder,
    ProviderRequest,
)
from demo_command_center.security.encryption import PayloadCipher
from demo_command_center.state.machine.demo_state import DemoState


@dataclass(frozen=True, slots=True)
class PaymentOrderCommand:
    request_id: UUID
    demo_ref: UUID
    website_user_ref: str
    plan_ref: str
    customer_phone: str


@dataclass(frozen=True, slots=True)
class PaymentOrderJob:
    request_id: UUID
    status: str
    provider_order_ref: str | None = None
    payment_session_id: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentOrderJobService:
    sessions: async_sessionmaker[AsyncSession]
    cipher: PayloadCipher
    key_reference: str
    request_hash_key: str
    tenant_id: str

    @staticmethod
    def _associated_data(tenant_id: str, target: str, event_id: UUID) -> bytes:
        return f"{tenant_id}:{target}:{event_id}".encode()

    @staticmethod
    def _checkout_associated_data(tenant_id: str, payment_order_id: UUID) -> bytes:
        return f"payment-checkout-session:{tenant_id}:{payment_order_id}".encode()

    def _request_hash(self, command: PaymentOrderCommand) -> str:
        material = json.dumps(
            {
                "request_id": str(command.request_id),
                "demo_ref": str(command.demo_ref),
                "website_user_ref": command.website_user_ref,
                "plan_ref": command.plan_ref,
                "customer_phone": command.customer_phone,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hmac.new(self.request_hash_key.encode(), material, hashlib.sha256).hexdigest()

    async def request(
        self,
        command: PaymentOrderCommand,
        *,
        correlation_id: str,
    ) -> PaymentOrderJob:
        if not self.request_hash_key:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Payment request hashing is not configured",
            )
        request_key = str(command.request_id)
        request_hash = self._request_hash(command)
        payload = {
            "event_type": "payment.plan-quote.requested.v1",
            "request_id": request_key,
            "demo_ref": str(command.demo_ref),
            "website_user_ref": command.website_user_ref,
            "plan_ref": command.plan_ref,
            "customer_phone": command.customer_phone,
            "purpose": "demo_conversion",
            "correlation_id": correlation_id,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        target = "nxtutors-website-gateway"
        try:
            async with self.sessions() as session, session.begin():
                existing = await session.scalar(
                    select(ProviderRequest)
                    .where(
                        ProviderRequest.tenant_id == self.tenant_id,
                        ProviderRequest.provider == target,
                        ProviderRequest.idempotency_key == request_key,
                    )
                    .with_for_update()
                )
                if existing is not None:
                    self._validate_replay(existing, request_hash)
                    return await self._job(session, command.request_id)
                demo = await session.scalar(
                    select(DemoCase)
                    .where(
                        DemoCase.id == command.demo_ref,
                        DemoCase.tenant_id == self.tenant_id,
                    )
                    .with_for_update()
                )
                if demo is None:
                    raise ServiceError(ErrorCode.POLICY_REJECTED, "The demo does not exist")
                if demo.external_user_id != command.website_user_ref:
                    raise ServiceError(
                        ErrorCode.PAYMENT_MISMATCH,
                        "The website user is not bound to this demo",
                    )
                active_order = await session.scalar(
                    select(PaymentOrder.id).where(
                        PaymentOrder.tenant_id == self.tenant_id,
                        PaymentOrder.demo_case_id == command.demo_ref,
                        PaymentOrder.status.in_(
                            {
                                "creating",
                                "pending",
                                "reconciling",
                                "reconciliation_required",
                                "payment_review",
                            }
                        ),
                    )
                )
                if active_order is not None:
                    raise ServiceError(
                        ErrorCode.CONCURRENCY_CONFLICT,
                        "The demo already has an active payment order",
                    )
                if demo.state != DemoState.CONVERSION_FOLLOW_UP.value:
                    raise ServiceError(
                        ErrorCode.INVALID_TRANSITION,
                        "A standard-price payment can only start from conversion follow-up",
                    )
                active_request = await session.scalar(
                    select(ProviderRequest).where(
                        ProviderRequest.tenant_id == self.tenant_id,
                        ProviderRequest.provider == target,
                        ProviderRequest.operation == "fetch_authoritative_plan_quote",
                        ProviderRequest.provider_reference == str(command.demo_ref),
                        ProviderRequest.status.in_({"queued", "quote_verified"}),
                    )
                )
                if active_request is not None:
                    raise ServiceError(
                        ErrorCode.CONCURRENCY_CONFLICT,
                        "The demo already has an active payment request",
                    )
                session.add(
                    ProviderRequest(
                        tenant_id=self.tenant_id,
                        provider=target,
                        operation="fetch_authoritative_plan_quote",
                        idempotency_key=request_key,
                        correlation_id=correlation_id,
                        request_hash=request_hash,
                        provider_reference=str(command.demo_ref),
                        status="queued",
                        attempt_count=0,
                    )
                )
                session.add(
                    AgentOutboxEvent(
                        event_id=command.request_id,
                        event_type="payment.plan-quote.requested.v1",
                        schema_version="1.0",
                        tenant_id=self.tenant_id,
                        target_agent=target,
                        idempotency_key=request_key,
                        correlation_id=correlation_id,
                        payload_ciphertext=self.cipher.encrypt(
                            raw,
                            associated_data=self._associated_data(
                                self.tenant_id, target, command.request_id
                            ),
                        ),
                        available_at=datetime.now(UTC),
                        attempts=0,
                    )
                )
        except IntegrityError as exc:
            async with self.sessions() as session:
                existing = await session.scalar(
                    select(ProviderRequest).where(
                        ProviderRequest.tenant_id == self.tenant_id,
                        ProviderRequest.provider == target,
                        ProviderRequest.idempotency_key == request_key,
                    )
                )
                if existing is None:
                    raise ServiceError(
                        ErrorCode.CONCURRENCY_CONFLICT,
                        "Payment request collided with another operation",
                    ) from exc
                self._validate_replay(existing, request_hash)
                return await self._job(session, command.request_id)
        return PaymentOrderJob(command.request_id, "quote_pending")

    @staticmethod
    def _validate_replay(existing: ProviderRequest, request_hash: str) -> None:
        if not hmac.compare_digest(existing.request_hash, request_hash):
            raise ServiceError(
                ErrorCode.IDEMPOTENCY_CONFLICT,
                "The payment request ID was already used for different input",
            )

    async def status(self, request_id: UUID) -> PaymentOrderJob | None:
        async with self.sessions() as session:
            request = await session.scalar(
                select(ProviderRequest).where(
                    ProviderRequest.tenant_id == self.tenant_id,
                    ProviderRequest.provider == "nxtutors-website-gateway",
                    ProviderRequest.idempotency_key == str(request_id),
                )
            )
            if request is None:
                return None
            return await self._job(session, request_id)

    async def _job(self, session: AsyncSession, request_id: UUID) -> PaymentOrderJob:
        order = await session.scalar(
            select(PaymentOrder).where(
                PaymentOrder.tenant_id == self.tenant_id,
                PaymentOrder.creation_idempotency_key == str(request_id),
            )
        )
        if order is None:
            return PaymentOrderJob(request_id, "quote_pending")
        checkout = await session.scalar(
            select(PaymentCheckoutSession).where(
                PaymentCheckoutSession.payment_order_id == order.id
            )
        )
        if checkout is None:
            state = (
                order.status
                if order.status in {"failed", "payment_review", "paid"}
                else "provider_pending"
            )
            return PaymentOrderJob(request_id, state, order.provider_order_id)
        if checkout.expires_at <= datetime.now(UTC) or order.status == "expired":
            return PaymentOrderJob(request_id, "expired", order.provider_order_id)
        if order.status != "pending":
            state = (
                order.status if order.status in {"failed", "payment_review", "paid"} else "failed"
            )
            return PaymentOrderJob(request_id, state, order.provider_order_id)
        plaintext = self.cipher.decrypt(
            checkout.session_ciphertext,
            associated_data=self._checkout_associated_data(self.tenant_id, order.id),
        )
        return PaymentOrderJob(
            request_id,
            "ready",
            order.provider_order_id,
            plaintext.decode(),
        )
