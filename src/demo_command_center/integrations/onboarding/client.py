from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.integrations.http_security import (
    fixed_provider_url,
    validate_provider_base_url,
)
from demo_command_center.modules.demo_core.domain.identifiers import IdempotencyKey
from demo_command_center.modules.demo_core.ports.gateways import OnboardingHandoffRequest


class OnboardingCompatibilityGateway:
    """Adapter for the deployed onboarding agent's shared-secret handoff contract."""

    _PATH = "/whatsapp/onboarding/webhook"

    def __init__(
        self,
        *,
        base_url: str,
        shared_secret: str,
        timeout_seconds: float,
        require_https: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not shared_secret:
            raise ValueError("onboarding shared secret is required")
        self._base_url = validate_provider_base_url(base_url, require_https=require_https)
        self._secret = shared_secret
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds), follow_redirects=False
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def handoff_paid_user(
        self,
        handoff: OnboardingHandoffRequest,
        idempotency_key: IdempotencyKey,
    ) -> Mapping[str, Any]:
        role = handoff.role.lower()
        if role not in {"student", "teacher"}:
            raise ServiceError(ErrorCode.POLICY_REJECTED, "Onboarding role is not permitted")
        payload = {
            "source": "lead_intake_agent",
            "message_text": role,
            "wa_phone": handoff.recipient_phone,
            "wa_message_id": str(idempotency_key),
            "demo_id": str(handoff.demo_id),
            "website_user_ref": handoff.user_ref,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        try:
            response = await self._client.post(
                fixed_provider_url(self._base_url, self._PATH),
                headers={
                    "Content-Type": "application/json",
                    "X-NXTUTORS-INTERNAL-SECRET": self._secret,
                    "X-Correlation-Id": handoff.correlation_id,
                    "Idempotency-Key": str(idempotency_key),
                },
                content=raw,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "The onboarding handoff is temporarily unavailable",
            ) from exc
        if not isinstance(result, dict) or result.get("status") not in {"accepted", "duplicate"}:
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "The onboarding acknowledgement is invalid",
            )
        return result
