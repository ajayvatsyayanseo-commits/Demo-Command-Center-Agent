from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from demo_command_center.api.dependencies.container import get_container
from demo_command_center.api.schemas.ingress import IngressReceipt
from demo_command_center.bootstrap.dependency_container import DependencyContainer
from demo_command_center.glue.envelopes.agent_event import (
    ActorType,
    AgentEventEnvelope,
    EventActor,
    EventSubject,
    PiiClassification,
)
from demo_command_center.security.signatures.webhook import (
    verify_cashfree_signature,
    verify_meta_signature,
)

router = APIRouter(prefix="/v1/provider", tags=["provider-webhooks"])


def _object_payload(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed provider payload",
        ) from exc
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provider payload must be an object",
        )
    return value


def _nested_string(payload: dict[str, Any], *path: str) -> str | None:
    value: Any = payload
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value[:255] if isinstance(value, str) and value else None


def _nested_reference(payload: dict[str, Any], *path: str) -> str | None:
    value: Any = payload
    for part in path:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit():
            index = int(part)
            value = value[index] if index < len(value) else None
        else:
            return None
    if isinstance(value, bool) or not isinstance(value, str | int):
        return None
    reference = str(value).strip()
    return reference[:255] if reference else None


def _provider_envelope(
    *,
    request: Request,
    container: DependencyContainer,
    provider: str,
    provider_event_id: str,
    event_type: str,
    occurred_at: datetime,
    payload: dict[str, Any],
) -> AgentEventEnvelope:
    digest = hashlib.sha256(f"{provider}:{provider_event_id}".encode()).hexdigest()
    return AgentEventEnvelope(
        event_id=uuid5(NAMESPACE_URL, f"{provider}:{provider_event_id}"),
        event_type=event_type,
        occurred_at=occurred_at,
        source_agent=provider,
        target_agent=container.settings.app_name,
        tenant_id=container.settings.tenant_id or "local",
        correlation_id=getattr(request.state, "correlation_id", digest[:32]),
        conversation_id=f"provider:{digest[:32]}",
        actor=EventActor(type=ActorType.PROVIDER, id=provider),
        subject=EventSubject(),
        idempotency_key=f"provider:{digest}",
        pii_classification=PiiClassification.RESTRICTED,
        payload=payload,
    )


@router.get("/meta/whatsapp")
async def verify_meta_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
    container: DependencyContainer = Depends(get_container),
) -> PlainTextResponse:
    settings = container.settings
    expected = settings.meta_whatsapp_verify_token.get_secret_value()
    if not settings.meta_direct_webhook_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Direct webhook disabled")
    if expected and hub_mode == "subscribe" and hmac.compare_digest(expected, hub_verify_token):
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post(
    "/meta/whatsapp",
    response_model=IngressReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_meta_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    container: DependencyContainer = Depends(get_container),
) -> IngressReceipt:
    settings = container.settings
    if not settings.meta_direct_webhook_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Direct webhook disabled")
    raw = await request.body()
    if not verify_meta_signature(
        raw, x_hub_signature_256, settings.meta_whatsapp_app_secret.get_secret_value()
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")
    payload = _object_payload(raw)
    provider_event_id = hashlib.sha256(raw).hexdigest()
    envelope = _provider_envelope(
        request=request,
        container=container,
        provider="meta-whatsapp-direct",
        provider_event_id=provider_event_id,
        event_type="meta.whatsapp.webhook.received.v1",
        occurred_at=datetime.now(UTC),
        payload=payload,
    )
    return await container.event_ingress.accept(envelope)


@router.post(
    "/cashfree",
    response_model=IngressReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_cashfree_webhook(
    request: Request,
    x_webhook_timestamp: str | None = Header(default=None, alias="X-Webhook-Timestamp"),
    x_webhook_signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
    container: DependencyContainer = Depends(get_container),
) -> IngressReceipt:
    settings = container.settings
    if not settings.demo_payments_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payments disabled")
    raw = await request.body()
    if not verify_cashfree_signature(
        raw,
        x_webhook_timestamp,
        x_webhook_signature,
        settings.cashfree_secret_key.get_secret_value(),
        replay_window_seconds=settings.cashfree_webhook_replay_window_seconds,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")
    payload = _object_payload(raw)
    provider_reference = (
        _nested_reference(payload, "data", "payment", "cf_payment_id")
        or _nested_reference(payload, "data", "order", "order_id")
        or hashlib.sha256(raw).hexdigest()
    )
    provider_event_id = (
        f"{_nested_string(payload, 'type') or 'unknown'}:{provider_reference}:"
        f"{hashlib.sha256(raw).hexdigest()[:16]}"
    )
    try:
        timestamp = int(x_webhook_timestamp or "0")
        if timestamp > 10_000_000_000:
            timestamp //= 1_000
        occurred_at = datetime.fromtimestamp(timestamp, tz=UTC)
    except (ValueError, OSError, OverflowError):
        occurred_at = datetime.now(UTC)
    envelope = _provider_envelope(
        request=request,
        container=container,
        provider="cashfree",
        provider_event_id=provider_event_id,
        event_type="cashfree.payment.webhook.received.v1",
        occurred_at=occurred_at,
        payload=payload,
    )
    return await container.event_ingress.accept(envelope)
