from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.integrations.http_security import (
    InternalRequestSigner,
    fixed_provider_url,
    validate_provider_base_url,
)
from demo_command_center.modules.demo_core.domain.identifiers import IdempotencyKey


class LeadIntakeDeliveryRequest(BaseModel):
    """The complete, policy-relevant request sent to the sole WhatsApp owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    event_type: Literal["outbound.delivery.requested.v1"]
    demo_id: UUID
    recipient_ref: str = Field(min_length=1, max_length=255)
    template_or_message_ref: str = Field(min_length=1, max_length=255)
    variables: dict[str, str] = Field(max_length=50)
    message_category: Literal["service", "utility", "marketing"]
    service_window_expires_at: datetime
    send_key: str = Field(min_length=8, max_length=255)
    correlation_id: str = Field(min_length=1, max_length=128)

    @field_validator("service_window_expires_at")
    @classmethod
    def require_aware_service_window(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("service_window_expires_at must be timezone-aware")
        return value


class LeadIntakeOutboundGateway:
    """Canonical WhatsApp send request client; this service never calls Meta to send."""

    _PATH = "/v1/internal/outbound/whatsapp"

    def __init__(
        self,
        *,
        base_url: str,
        signer: InternalRequestSigner,
        timeout_seconds: float,
        require_https: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = validate_provider_base_url(base_url, require_https=require_https)
        self._signer = signer
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds), follow_redirects=False
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request_delivery(
        self,
        request: LeadIntakeDeliveryRequest,
        idempotency_key: IdempotencyKey,
    ) -> str:
        if request.send_key != str(idempotency_key):
            raise ServiceError(
                ErrorCode.POLICY_REJECTED,
                "Outbound send metadata does not match its idempotency header",
            )
        payload = request.model_dump(mode="json")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        headers = self._signer.headers(
            method="POST",
            path=self._PATH,
            body=raw,
            scopes=("whatsapp:send",),
            idempotency_key=str(idempotency_key),
        )
        headers["X-Correlation-Id"] = request.correlation_id
        try:
            response = await self._client.post(
                fixed_provider_url(self._base_url, self._PATH),
                content=raw,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "The canonical outbound messaging gateway is unavailable",
            ) from exc
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if not isinstance(message_id, str):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "The outbound messaging acknowledgement is invalid",
            )
        return message_id
