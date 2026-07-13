from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import quote

import httpx

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.integrations.http_security import fixed_provider_url
from demo_command_center.modules.demo_core.domain.identifiers import IdempotencyKey
from demo_command_center.modules.demo_core.ports.gateways import (
    PaymentOrderRequest,
    ProviderOrderResult,
    ProviderPaymentStatus,
)


class CashfreePaymentGateway:
    """Server-only Cashfree PG adapter. It never interprets browser return URLs as payment."""

    def __init__(
        self,
        *,
        environment: str,
        app_id: str,
        secret_key: str,
        api_version: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if environment not in {"sandbox", "production"}:
            raise ValueError("Cashfree environment must be sandbox or production")
        if not app_id or not secret_key or not api_version:
            raise ValueError("Cashfree server credentials and API version are required")
        self._base_url = (
            "https://sandbox.cashfree.com/pg/"
            if environment == "sandbox"
            else "https://api.cashfree.com/pg/"
        )
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-client-id": app_id,
            "x-client-secret": secret_key,
            "x-api-version": api_version,
        }
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds), follow_redirects=False
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def create_order(
        self,
        request: PaymentOrderRequest,
        idempotency_key: IdempotencyKey,
    ) -> ProviderOrderResult:
        if request.amount_minor <= 0 or len(request.currency) != 3:
            raise ServiceError(ErrorCode.POLICY_REJECTED, "Payment amount or currency is invalid")
        body: dict[str, Any] = {
            "order_id": request.order_reference,
            "order_amount": str(Decimal(request.amount_minor) / Decimal(100)),
            "order_currency": request.currency.upper(),
            "customer_details": {
                "customer_id": request.customer_ref,
                "customer_phone": request.customer_phone,
            },
            "order_note": request.purpose,
            "order_tags": {
                "purpose": request.purpose,
                "correlation_id": request.correlation_id,
            },
        }
        if request.return_url:
            body["order_meta"] = {"return_url": request.return_url}
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        headers = {
            **self._headers,
            "x-idempotency-key": str(idempotency_key),
            "x-request-id": request.correlation_id,
        }
        payload = await self._request("POST", "/orders", headers=headers, content=raw)
        provider_order_id = payload.get("cf_order_id")
        session_id = payload.get("payment_session_id")
        order_status = payload.get("order_status")
        if not all(isinstance(item, str) and item for item in (provider_order_id, session_id, order_status)):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "Cashfree returned an invalid order acknowledgement",
            )
        return ProviderOrderResult(
            provider_order_id=provider_order_id,
            payment_session_id=session_id,
            status=order_status,
        )

    async def fetch_verified_status(self, provider_order_id: str) -> ProviderPaymentStatus:
        safe_order_id = quote(provider_order_id, safe="")
        payload = await self._request(
            "GET",
            f"/orders/{safe_order_id}",
            headers=self._headers,
        )
        order_id = payload.get("cf_order_id")
        order_status = payload.get("order_status")
        currency = payload.get("order_currency")
        try:
            amount_minor = int(
                (Decimal(str(payload.get("order_amount"))) * 100).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
        except (ValueError, TypeError):
            amount_minor = -1
        if (
            not isinstance(order_id, str)
            or not isinstance(order_status, str)
            or not isinstance(currency, str)
            or amount_minor < 0
        ):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "Cashfree returned an invalid order status",
            )
        return ProviderPaymentStatus(
            provider_order_id=order_id,
            status=order_status,
            amount_minor=amount_minor,
            currency=currency.upper(),
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        content: bytes | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(
                method,
                fixed_provider_url(self._base_url, path),
                headers=headers,
                content=content,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Cashfree is temporarily unavailable; reconciliation is required",
            ) from exc
        if not isinstance(payload, dict):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "Cashfree returned an invalid response",
            )
        return payload
