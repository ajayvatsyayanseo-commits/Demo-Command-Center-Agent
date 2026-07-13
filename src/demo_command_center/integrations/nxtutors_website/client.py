from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.integrations.http_security import (
    InternalRequestSigner,
    fixed_provider_url,
    validate_provider_base_url,
)
from demo_command_center.modules.demo_core.domain.identifiers import IdempotencyKey
from demo_command_center.modules.demo_core.ports.gateways import (
    TutorSearchQuery,
    VerifiedSubscriptionActivation,
)


class NxtutorsWebsiteGateway:
    """Allow-listed client for the authoritative Laravel/MySQL integration gateway."""

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
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        scopes: tuple[str, ...],
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        raw = (
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            if body is not None
            else b""
        )
        headers = self._signer.headers(
            method=method,
            path=path,
            body=raw,
            scopes=scopes,
            idempotency_key=idempotency_key,
        )
        try:
            response = await self._client.request(
                method,
                fixed_provider_url(self._base_url, path),
                headers=headers,
                content=raw or None,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "The website integration gateway is unavailable",
            ) from exc
        if not isinstance(payload, dict):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "The website integration gateway returned an invalid response",
            )
        return payload

    async def search_tutor_candidates(
        self, query: TutorSearchQuery
    ) -> Sequence[Mapping[str, Any]]:
        parameters: dict[str, str | int] = {
            "page": query.page,
            "per_page": query.per_page,
        }
        optional = {
            "subject": query.subject,
            "board": query.board,
            "class": query.class_level,
            "mode": query.mode,
            "city": query.city,
            "district": query.district,
            "state": query.state,
            "class_type": query.class_type,
        }
        parameters.update({key: value for key, value in optional.items() if value is not None})
        target = (
            "/internal/api/v1/demo-command-center/tutors/candidates?"
            + urlencode(parameters)
        )
        payload = await self._request(
            "GET",
            target,
            scopes=("tutors:read",),
        )
        candidates = payload.get("data", [])
        if not isinstance(candidates, list) or not all(isinstance(item, dict) for item in candidates):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "Tutor search returned an invalid projection",
            )
        return candidates

    async def get_plan_quote(self, plan_ref: str, customer_ref: str) -> Mapping[str, Any]:
        safe_plan = quote(plan_ref, safe="")
        safe_customer = quote(customer_ref, safe="")
        payload = await self._request(
            "GET",
            (
                f"/internal/api/v1/demo-command-center/plans/{safe_plan}/quote"
                f"?user_ref={safe_customer}"
            ),
            scopes=("plans:read",),
        )
        quote_payload = payload.get("data")
        if not isinstance(quote_payload, dict):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "Plan quote returned an invalid projection",
            )
        return quote_payload

    async def activate_verified_subscription(
        self,
        activation: VerifiedSubscriptionActivation,
        idempotency_key: IdempotencyKey,
    ) -> Mapping[str, Any]:
        payload = await self._request(
            "POST",
            "/internal/api/v1/demo-command-center/subscriptions/activations",
            scopes=("subscriptions:activate",),
            body={
                "demo_ref": activation.demo_ref,
                "website_user_ref": activation.website_user_ref,
                "plan_id": activation.plan_id,
                "plan_version": activation.plan_version,
                "amount_minor": activation.amount_minor,
                "currency": activation.currency,
                "provider_order_ref": activation.provider_order_ref,
                "payment_evidence_ref": activation.payment_evidence_ref,
                "payment_verified_at": activation.payment_verified_at.isoformat(),
                "correlation_id": activation.correlation_id,
            },
            idempotency_key=str(idempotency_key),
        )
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("activation_ref"), str):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "Subscription activation acknowledgement is invalid",
            )
        return data
