from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid5

import httpx
import pytest
from pydantic import ValidationError

from demo_command_center.api.errors.taxonomy import ServiceError
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.outbox import OutboxDeliveryResult
from demo_command_center.integrations.cashfree import CashfreePaymentGateway
from demo_command_center.integrations.http_security import InternalRequestSigner
from demo_command_center.integrations.lead_intake import LeadIntakeOutboundGateway
from demo_command_center.integrations.nxtutors_website import NxtutorsWebsiteGateway
from demo_command_center.integrations.onboarding import OnboardingEventGateway
from demo_command_center.integrations.outbox_router import RoutingOutboxTransport


def _signer(*, audience: str) -> InternalRequestSigner:
    return InternalRequestSigner(
        key_id="test-key",
        secret="test-secret",
        source="demo-command-center",
        issuer="nxtutors-internal",
        audience=audience,
    )


def _lead_payload() -> dict[str, object]:
    return {
        "event_id": "f6e89b95-c1cc-5a52-b964-0a3cdd79c71f",
        "event_type": "outbound.delivery.requested.v1",
        "demo_id": "9e383b38-5475-4815-a966-5a09c5a626d9",
        "recipient_ref": "conversation-1",
        "template_or_message_ref": "demo.collect_requirements.v1",
        "variables": {"missing_fields": "subject"},
        "message_category": "service",
        "service_window_expires_at": "2026-07-14T06:00:00Z",
        "send_key": "demo-requirements:f6e89b95-c1cc-5a52-b964-0a3cdd79c71f",
    }


@pytest.mark.asyncio
async def test_routes_verified_payment_to_scoped_website_activation() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/subscriptions/activations")
        assert request.headers["X-NXTutors-Scopes"] == "demo:subscription:write"
        assert request.headers["Idempotency-Key"] == "activation-key"
        body = json.loads(request.content)
        assert body["plan_id"] == 17
        return httpx.Response(
            201,
            json={"data": {"activation_ref": "activation-17", "status": "applied"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    router = RoutingOutboxTransport(
        website=NxtutorsWebsiteGateway(
            base_url="https://website.invalid",
            signer=_signer(audience="nxtutors-website-gateway"),
            timeout_seconds=2,
            client=client,
        )
    )
    occurred_at = datetime.now(UTC)
    acknowledgement = await router.publish(
        target="nxtutors-website-gateway",
        payload={
            "event_type": "demo.payment.verified.v1",
            "demo_ref": "demo-1",
            "website_user_ref": "user-1",
            "plan_id": 17,
            "plan_version": "a" * 64,
            "amount_minor": 50000,
            "currency": "INR",
            "provider_order_ref": "cf-order-1",
            "payment_evidence_ref": "cf-payment-1",
            "payment_verified_at": occurred_at.isoformat(),
            "correlation_id": "correlation-1",
            "activation_key": "activation-key",
        },
        idempotency_key="activation-key",
        correlation_id="correlation-1",
    )
    assert acknowledgement == "activation-17"
    await client.aclose()


@pytest.mark.asyncio
async def test_routes_only_approved_delivery_to_lead_intake() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/internal/outbound/whatsapp"
        assert request.headers["X-NXTutors-Scopes"] == "whatsapp:send"
        assert request.headers["Idempotency-Key"] == (
            "demo-requirements:f6e89b95-c1cc-5a52-b964-0a3cdd79c71f"
        )
        assert request.headers["X-Correlation-Id"] == "correlation-1"
        assert json.loads(request.content) == {
            **_lead_payload(),
            "correlation_id": "correlation-1",
        }
        return httpx.Response(202, json={"message_id": "message-1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    router = RoutingOutboxTransport(
        lead_intake=LeadIntakeOutboundGateway(
            base_url="https://lead.invalid",
            signer=_signer(audience="lead-intake-agent"),
            timeout_seconds=2,
            client=client,
        )
    )
    acknowledgement = await router.publish(
        target="lead-intake-agent",
        payload=_lead_payload(),
        idempotency_key="demo-requirements:f6e89b95-c1cc-5a52-b964-0a3cdd79c71f",
        correlation_id="correlation-1",
    )
    assert acknowledgement == "message-1"
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("event_id", "not-an-event-uuid"),
        ("demo_id", "not-a-demo-uuid"),
        ("service_window_expires_at", "2026-07-14T06:00:00"),
    ],
)
async def test_lead_delivery_rejects_invalid_policy_metadata_before_network(
    field: str,
    invalid_value: str,
) -> None:
    def must_not_send(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid Lead metadata reached the network")

    client = httpx.AsyncClient(transport=httpx.MockTransport(must_not_send))
    router = RoutingOutboxTransport(
        lead_intake=LeadIntakeOutboundGateway(
            base_url="https://lead.invalid",
            signer=_signer(audience="lead-intake-agent"),
            timeout_seconds=2,
            client=client,
        )
    )
    payload = _lead_payload()
    payload[field] = invalid_value
    with pytest.raises(ValidationError):
        await router.publish(
            target="lead-intake-agent",
            payload=payload,
            idempotency_key="demo-requirements:f6e89b95-c1cc-5a52-b964-0a3cdd79c71f",
            correlation_id="correlation-1",
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_lead_delivery_rejects_outbox_metadata_mismatch_before_network() -> None:
    def must_not_send(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("mismatched Lead metadata reached the network")

    client = httpx.AsyncClient(transport=httpx.MockTransport(must_not_send))
    router = RoutingOutboxTransport(
        lead_intake=LeadIntakeOutboundGateway(
            base_url="https://lead.invalid",
            signer=_signer(audience="lead-intake-agent"),
            timeout_seconds=2,
            client=client,
        )
    )
    with pytest.raises(ServiceError):
        await router.publish(
            target="lead-intake-agent",
            payload={**_lead_payload(), "correlation_id": "wrong-correlation"},
            idempotency_key="demo-requirements:f6e89b95-c1cc-5a52-b964-0a3cdd79c71f",
            correlation_id="correlation-1",
        )
    with pytest.raises(ServiceError):
        await router.publish(
            target="lead-intake-agent",
            payload=_lead_payload(),
            idempotency_key="different-send-key",
            correlation_id="correlation-1",
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_outbox_router_fails_closed_for_unknown_or_unconfigured_targets() -> None:
    router = RoutingOutboxTransport()
    with pytest.raises(ServiceError):
        await router.publish(
            target="unknown-agent",
            payload={},
            idempotency_key="key",
            correlation_id="correlation",
        )
    with pytest.raises(ServiceError):
        await router.publish(
            target="nxtutors-website-gateway",
            payload={},
            idempotency_key="key",
            correlation_id="correlation",
        )


@pytest.mark.asyncio
async def test_routes_canonical_onboarding_event_with_hmac() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/internal/events"
        assert request.headers["X-NXTutors-Scopes"] == "events:write"
        body = json.loads(request.content)
        assert body["event_type"] == "onboarding.paid-user.requested.v1"
        return httpx.Response(
            202,
            json={
                "event_id": body["event_id"],
                "status": "accepted",
                "correlation_id": body["correlation_id"],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    router = RoutingOutboxTransport(
        onboarding=OnboardingEventGateway(
            base_url="https://onboarding.invalid",
            signer=_signer(audience="onboarding-agent"),
            timeout_seconds=2,
            client=client,
        )
    )
    event_id = "bb17c955-eabe-4de9-96a6-508b300ca75a"
    acknowledgement = await router.publish(
        target="onboarding-agent",
        payload={
            "event_id": event_id,
            "event_type": "onboarding.paid-user.requested.v1",
            "schema_version": "1.0",
            "occurred_at": datetime.now(UTC).isoformat(),
            "source_agent": "demo-command-center-agent",
            "target_agent": "onboarding-agent",
            "tenant_id": "tenant-1",
            "region_id": None,
            "correlation_id": "correlation-1",
            "causation_id": None,
            "conversation_id": "conversation-1",
            "actor": {"type": "system", "id": "demo-command-center-agent"},
            "subject": {"user_id": "user-1", "demo_id": "demo-1"},
            "idempotency_key": "onboarding-paid:transition-1",
            "traceparent": None,
            "pii_classification": "low",
            "payload": {
                "demo_ref": "demo-1",
                "user_ref": "user-1",
                "activation_ref": "activation-1",
                "payment_ref": "payment-1",
                "plan_ref": "17",
                "locale": "en-IN",
                "consent_refs": [],
                "requested_flow": "existing_account",
            },
        },
        idempotency_key="onboarding-paid:transition-1",
        correlation_id="correlation-1",
    )
    assert acknowledgement == event_id
    await client.aclose()


@pytest.mark.asyncio
async def test_onboarding_gateway_rejects_acknowledgement_for_another_event() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            202,
            json={
                "event_id": "2d13cfdc-9d20-4773-9d2d-8204cd2587e9",
                "status": "accepted",
                "correlation_id": "correlation-1",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    gateway = OnboardingEventGateway(
        base_url="https://onboarding.invalid",
        signer=_signer(audience="onboarding-agent"),
        timeout_seconds=2,
        client=client,
    )
    event = AgentEventEnvelope.model_validate(
        {
            "event_id": "bb17c955-eabe-4de9-96a6-508b300ca75a",
            "event_type": "onboarding.paid-user.requested.v1",
            "occurred_at": datetime.now(UTC).isoformat(),
            "source_agent": "demo-command-center-agent",
            "target_agent": "onboarding-agent",
            "tenant_id": "tenant-1",
            "correlation_id": "correlation-1",
            "conversation_id": "conversation-1",
            "actor": {"type": "system", "id": "demo-command-center-agent"},
            "subject": {"user_id": "user-1", "demo_id": "demo-1"},
            "idempotency_key": "onboarding-paid:transition-1",
            "pii_classification": "low",
            "payload": {
                "demo_ref": "demo-1",
                "user_ref": "user-1",
                "activation_ref": "activation-1",
                "payment_ref": "payment-1",
                "plan_ref": "17",
                "locale": "en-IN",
                "consent_refs": [],
                "requested_flow": "existing_account",
            },
        }
    )

    with pytest.raises(ServiceError):
        await gateway.publish(event)
    await client.aclose()


@pytest.mark.asyncio
async def test_routes_quote_then_cashfree_without_persisting_session_as_reference() -> None:
    def website_handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/plans/17/quote")
        assert request.headers["X-NXTutors-Scopes"] == "demo:plans:read"
        return httpx.Response(
            200,
            json={
                "data": {
                    "plan_id": "17",
                    "name": "Standard",
                    "amount_minor": 50000,
                    "currency": "INR",
                    "duration_days": 30,
                    "eligible": True,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "plan_version": "a" * 64,
                    "user_ref": "user-17",
                    "expires_at": datetime.now(UTC).isoformat(),
                }
            },
        )

    website_client = httpx.AsyncClient(transport=httpx.MockTransport(website_handle))
    website = NxtutorsWebsiteGateway(
        base_url="https://website.invalid",
        signer=_signer(audience="nxtutors-website-gateway"),
        timeout_seconds=2,
        client=website_client,
    )
    router = RoutingOutboxTransport(website=website)
    request_id = "6a29d365-f7ef-48b8-a58f-e120eb65eedd"
    quote = await router.publish(
        target="nxtutors-website-gateway",
        payload={
            "event_type": "payment.plan-quote.requested.v1",
            "request_id": request_id,
            "demo_ref": "9c1973ec-d10e-4c47-a592-60d50f4870fe",
            "website_user_ref": "user-17",
            "plan_ref": "17",
            "customer_phone": "+919876543210",
            "purpose": "demo_conversion",
            "correlation_id": "correlation-17",
        },
        idempotency_key=request_id,
        correlation_id="correlation-17",
    )
    assert isinstance(quote, OutboxDeliveryResult)
    assert quote.provider_reference == "a" * 64
    cashfree_idempotency_key = str(uuid5(UUID(request_id), "nxtutors:cashfree-create-order"))
    payment_order_id = str(uuid5(UUID(request_id), "nxtutors:payment-order"))

    def cashfree_handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pg/orders"
        assert request.headers["x-idempotency-key"] == cashfree_idempotency_key
        assert json.loads(request.content)["order_amount"] == "500"
        assert "order_expiry_time" in json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "cf_order_id": 90017,
                "payment_session_id": "restricted-session-17",
                "order_status": "ACTIVE",
            },
        )

    cashfree_client = httpx.AsyncClient(transport=httpx.MockTransport(cashfree_handle))
    router.cashfree = CashfreePaymentGateway(
        environment="sandbox",
        app_id="app-id",
        secret_key="secret-key",
        api_version="2025-01-01",
        timeout_seconds=2,
        client=cashfree_client,
    )
    acknowledgement = await router.publish(
        target="cashfree",
        payload={
            "event_type": "payment.cashfree-order.requested.v1",
            "request_id": request_id,
            "payment_order_id": payment_order_id,
            "order_reference": "dcc-order-17",
            "amount_minor": 50000,
            "currency": "INR",
            "customer_ref": "user-17",
            "customer_phone": "+919876543210",
            "purpose": "demo_conversion",
            "correlation_id": "correlation-17",
            "expires_at": datetime.now(UTC).isoformat(),
        },
        idempotency_key=cashfree_idempotency_key,
        correlation_id="correlation-17",
    )
    assert isinstance(acknowledgement, OutboxDeliveryResult)
    assert acknowledgement.provider_reference == "90017"
    assert "restricted-session" not in acknowledgement.provider_reference
    assert acknowledgement.restricted_details["payment_session_id"] == "restricted-session-17"
    await router.close()
