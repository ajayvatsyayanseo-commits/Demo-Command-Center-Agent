from __future__ import annotations

import json
from collections.abc import Mapping

import httpx

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.integrations.http_security import (
    InternalRequestSigner,
    fixed_provider_url,
    validate_provider_base_url,
)
from demo_command_center.modules.demo_core.domain.identifiers import IdempotencyKey


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
        recipient_ref: str,
        template_or_message_ref: str,
        variables: Mapping[str, str],
        idempotency_key: IdempotencyKey,
    ) -> str:
        payload = {
            "recipient_ref": recipient_ref,
            "template_or_message_ref": template_or_message_ref,
            "variables": dict(variables),
            "idempotency_key": str(idempotency_key),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        headers = self._signer.headers(
            method="POST",
            path=self._PATH,
            body=raw,
            scopes=("whatsapp:send",),
            idempotency_key=str(idempotency_key),
        )
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
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), str):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "The outbound messaging acknowledgement is invalid",
            )
        return result["message_id"]
