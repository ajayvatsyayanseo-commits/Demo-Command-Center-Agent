from __future__ import annotations

import json

import httpx

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.integrations.http_security import (
    InternalRequestSigner,
    fixed_provider_url,
    validate_provider_base_url,
)


class OnboardingEventGateway:
    """Canonical durable-event client; it carries opaque references, never phone data."""

    _PATH = "/v1/internal/events"

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

    async def publish(self, event: AgentEventEnvelope) -> str:
        raw = json.dumps(
            event.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        headers = self._signer.headers(
            method="POST",
            path=self._PATH,
            body=raw,
            scopes=("events:write",),
            idempotency_key=event.idempotency_key,
        )
        try:
            response = await self._client.post(
                fixed_provider_url(self._base_url, self._PATH),
                headers=headers,
                content=raw,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "The onboarding event gateway is unavailable",
            ) from exc
        if (
            not isinstance(result, dict)
            or result.get("status") not in {"accepted", "duplicate"}
            or result.get("event_id") != str(event.event_id)
        ):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "The onboarding event acknowledgement is invalid",
            )
        return str(result["event_id"])
