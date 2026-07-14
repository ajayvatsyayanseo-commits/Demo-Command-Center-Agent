from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.outbox import OutboxDeliveryResult
from demo_command_center.infrastructure.payments.contracts import (
    CashfreeOrderPayload,
    PlanQuoteRequestPayload,
)
from demo_command_center.integrations.cashfree import CashfreePaymentGateway
from demo_command_center.integrations.lead_intake import (
    LeadIntakeDeliveryRequest,
    LeadIntakeOutboundGateway,
)
from demo_command_center.integrations.nxtutors_website import NxtutorsWebsiteGateway
from demo_command_center.integrations.onboarding import OnboardingEventGateway
from demo_command_center.modules.demo_core.domain.identifiers import IdempotencyKey
from demo_command_center.modules.demo_core.ports.gateways import (
    PaymentOrderRequest,
    VerifiedSubscriptionActivation,
)


class WebsiteActivationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(pattern=r"^demo\.payment\.verified\.v1$")
    demo_ref: str
    website_user_ref: str
    plan_id: int = Field(gt=0)
    plan_version: str = Field(min_length=1, max_length=64)
    amount_minor: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    provider_order_ref: str
    payment_evidence_ref: str
    payment_verified_at: datetime
    correlation_id: str
    activation_key: str

    @model_validator(mode="after")
    def validate_aware_timestamp(self) -> WebsiteActivationPayload:
        if self.payment_verified_at.tzinfo is None:
            raise ValueError("payment_verified_at must be timezone-aware")
        return self


@dataclass(slots=True)
class RoutingOutboxTransport:
    """Strictly routes durable effects to their single approved external owner."""

    website: NxtutorsWebsiteGateway | None = None
    lead_intake: LeadIntakeOutboundGateway | None = None
    onboarding: OnboardingEventGateway | None = None
    cashfree: CashfreePaymentGateway | None = None

    async def publish(
        self,
        *,
        target: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        correlation_id: str,
    ) -> str | OutboxDeliveryResult:
        if target == "nxtutors-website-gateway":
            return await self._route_website(payload, idempotency_key, correlation_id)
        if target in {"lead-intake", "lead-intake-agent"}:
            return await self._request_whatsapp(payload, idempotency_key, correlation_id)
        if target == "onboarding-agent":
            return await self._publish_onboarding(payload, idempotency_key, correlation_id)
        if target == "cashfree":
            return await self._create_cashfree_order(payload, idempotency_key, correlation_id)
        raise ServiceError(
            ErrorCode.POLICY_REJECTED,
            "The outbox target is not allow-listed",
        )

    async def _route_website(
        self,
        payload: Mapping[str, Any],
        idempotency_key: str,
        correlation_id: str,
    ) -> str | OutboxDeliveryResult:
        if self.website is None:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "The website integration gateway is not configured",
            )
        if payload.get("event_type") == "payment.plan-quote.requested.v1":
            quote_request = PlanQuoteRequestPayload.model_validate(payload)
            if (
                str(quote_request.request_id) != idempotency_key
                or quote_request.correlation_id != correlation_id
            ):
                raise ServiceError(
                    ErrorCode.POLICY_REJECTED,
                    "Plan quote metadata does not match its durable outbox record",
                )
            quote = await self.website.get_plan_quote(
                quote_request.plan_ref, quote_request.website_user_ref
            )
            reference = quote.get("plan_version")
            return OutboxDeliveryResult(
                provider_reference=(
                    reference if isinstance(reference, str) and reference else "plan-quote"
                ),
                restricted_details=quote,
            )
        activation = WebsiteActivationPayload.model_validate(payload)
        if (
            activation.correlation_id != correlation_id
            or activation.activation_key != idempotency_key
        ):
            raise ServiceError(
                ErrorCode.POLICY_REJECTED,
                "Website activation metadata does not match its durable outbox record",
            )
        result = await self.website.activate_verified_subscription(
            VerifiedSubscriptionActivation(
                demo_ref=activation.demo_ref,
                website_user_ref=activation.website_user_ref,
                plan_id=activation.plan_id,
                plan_version=activation.plan_version,
                amount_minor=activation.amount_minor,
                currency=activation.currency,
                provider_order_ref=activation.provider_order_ref,
                payment_evidence_ref=activation.payment_evidence_ref,
                payment_verified_at=activation.payment_verified_at,
                correlation_id=activation.correlation_id,
            ),
            IdempotencyKey(idempotency_key),
        )
        return str(result["activation_ref"])

    async def _create_cashfree_order(
        self,
        payload: Mapping[str, Any],
        idempotency_key: str,
        correlation_id: str,
    ) -> OutboxDeliveryResult:
        if self.cashfree is None:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Cashfree order creation is not configured",
            )
        event = CashfreeOrderPayload.model_validate(payload)
        try:
            provider_idempotency_key = UUID(idempotency_key)
        except ValueError as exc:
            raise ServiceError(
                ErrorCode.POLICY_REJECTED,
                "Cashfree order idempotency key must be a UUID",
            ) from exc
        if (
            event.payment_order_id != uuid5(event.request_id, "nxtutors:payment-order")
            or provider_idempotency_key != uuid5(event.request_id, "nxtutors:cashfree-create-order")
            or event.correlation_id != correlation_id
        ):
            raise ServiceError(
                ErrorCode.POLICY_REJECTED,
                "Cashfree order metadata does not match its durable outbox record",
            )
        result = await self.cashfree.create_order(
            PaymentOrderRequest(
                order_reference=event.order_reference,
                amount_minor=event.amount_minor,
                currency=event.currency,
                customer_ref=event.customer_ref,
                customer_phone=event.customer_phone.get_secret_value(),
                purpose=event.purpose,
                correlation_id=event.correlation_id,
                expires_at=event.expires_at,
            ),
            IdempotencyKey(str(provider_idempotency_key)),
        )
        return OutboxDeliveryResult(
            provider_reference=result.provider_order_id,
            restricted_details={
                "provider_order_id": result.provider_order_id,
                "payment_session_id": result.payment_session_id,
                "status": result.status,
            },
        )

    async def _request_whatsapp(
        self,
        payload: Mapping[str, Any],
        idempotency_key: str,
        correlation_id: str,
    ) -> str:
        if self.lead_intake is None:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "The canonical outbound messaging gateway is not configured",
            )
        request_data = dict(payload)
        request_data.setdefault("correlation_id", correlation_id)
        event = LeadIntakeDeliveryRequest.model_validate(request_data)
        if event.send_key != idempotency_key or event.correlation_id != correlation_id:
            raise ServiceError(
                ErrorCode.POLICY_REJECTED,
                "Outbound send metadata does not match its durable outbox record",
            )
        return await self.lead_intake.request_delivery(
            event,
            IdempotencyKey(idempotency_key),
        )

    async def _publish_onboarding(
        self,
        payload: Mapping[str, Any],
        idempotency_key: str,
        correlation_id: str,
    ) -> str:
        if self.onboarding is None:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "The canonical onboarding event gateway is not configured",
            )
        event = AgentEventEnvelope.model_validate(payload)
        if (
            event.event_type != "onboarding.paid-user.requested.v1"
            or event.target_agent != "onboarding-agent"
            or event.idempotency_key != idempotency_key
            or event.correlation_id != correlation_id
        ):
            raise ServiceError(
                ErrorCode.POLICY_REJECTED,
                "Onboarding event metadata does not match its durable outbox record",
            )
        return await self.onboarding.publish(event)

    async def close(self) -> None:
        if self.website is not None:
            await self.website.close()
        if self.lead_intake is not None:
            await self.lead_intake.close()
        if self.onboarding is not None:
            await self.onboarding.close()
        if self.cashfree is not None:
            await self.cashfree.close()
