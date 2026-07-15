from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from demo_command_center.bootstrap.application_factory import create_application
from demo_command_center.config.settings import Settings
from demo_command_center.integrations.http_security import InternalRequestSigner


def _event() -> dict[str, object]:
    return {
        "event_id": str(uuid4()),
        "event_type": "whatsapp.handoff.demo.v1",
        "schema_version": "1.0",
        "occurred_at": "2026-07-13T06:00:00Z",
        "source_agent": "lead-intake-agent",
        "target_agent": "demo-command-center-agent",
        "tenant_id": "nxtutors",
        "region_id": None,
        "correlation_id": "corr-security-route",
        "causation_id": "provider-message-ref",
        "conversation_id": "conversation-ref",
        "actor": {"type": "user", "id": "opaque-user"},
        "subject": {"lead_id": "lead-ref", "user_id": None, "tutor_id": None, "demo_id": None},
        "idempotency_key": "lead:message:security-route",
        "traceparent": None,
        "pii_classification": "restricted",
        "payload": {
            "provider_message_ref": "provider-message-ref",
            "intent": "demo_request",
            "lead_ref": "lead-ref",
            "user_ref": None,
            "message": {"type": "text", "text": "I need a demo"},
            "service_window": {
                "last_user_message_at": "2026-07-13T06:00:00Z",
                "expires_at": "2026-07-14T06:00:00Z",
            },
            "consent_refs": [],
        },
    }


def _settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "provider_profile": "local",
        "internal_signing_key_id": "key-v1",
        "internal_hmac_key_grants": {
            "key-v1": {
                "secret": SecretStr("signing-secret"),
                "source": "lead-intake-agent",
                "scopes": [
                    "events:read",
                    "events:write",
                    "handoffs:write",
                    "health:read",
                ],
            }
        },
        "internal_replay_window_seconds": 300,
        "internal_legacy_shared_secret_enabled": False,
    }
    values.update(updates)
    return Settings.model_validate(values)


def _signer() -> InternalRequestSigner:
    return InternalRequestSigner(
        key_id="key-v1",
        secret="signing-secret",
        source="lead-intake-agent",
        issuer="nxtutors-internal",
        audience="demo-command-center",
    )


def _signed_headers(method: str, path: str, raw: bytes, *scopes: str) -> dict[str, str]:
    return _signer().headers(method=method, path=path, body=raw, scopes=scopes)


def test_signed_event_acceptance_status_duplicate_and_replay() -> None:
    event = _event()
    raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    path = "/v1/internal/events"
    headers = _signed_headers("POST", path, raw, "events:write")
    with TestClient(create_application(_settings())) as client:
        accepted = client.post(path, content=raw, headers=headers)
        assert accepted.status_code == 202
        assert accepted.json()["status"] == "accepted"
        assert client.post(path, content=raw, headers=headers).status_code == 401

        duplicate = client.post(
            path,
            content=raw,
            headers=_signed_headers("POST", path, raw, "events:write"),
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["status"] == "duplicate"

        status_path = f"/v1/internal/events/{event['event_id']}"
        status_response = client.get(
            status_path,
            headers=_signed_headers("GET", status_path, b"", "events:read"),
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "pending"

        missing_path = f"/v1/internal/events/{uuid4()}"
        assert (
            client.get(
                missing_path,
                headers=_signed_headers("GET", missing_path, b"", "events:read"),
            ).status_code
            == 404
        )


def test_signed_event_source_target_and_handoff_type_are_enforced() -> None:
    path = "/v1/internal/events"
    event = _event()
    event["source_agent"] = "forged-source"
    raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    with TestClient(create_application(_settings())) as client:
        assert (
            client.post(
                path,
                content=raw,
                headers=_signed_headers("POST", path, raw, "events:write"),
            ).status_code
            == 403
        )

        event = _event()
        event["target_agent"] = "other-agent"
        raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
        assert (
            client.post(
                path,
                content=raw,
                headers=_signed_headers("POST", path, raw, "events:write"),
            ).status_code
            == 422
        )

        handoff_path = "/v1/internal/whatsapp/handoffs"
        event = _event()
        event["event_type"] = "lead.generic.event.v1"
        raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
        assert (
            client.post(
                handoff_path,
                content=raw,
                headers=_signed_headers("POST", handoff_path, raw, "handoffs:write"),
            ).status_code
            == 422
        )


def test_hmac_protected_deep_health_and_security_headers() -> None:
    path = "/health/dependencies"
    with TestClient(create_application(_settings())) as client:
        response = client.get(
            path,
            headers=_signed_headers("GET", path, b"", "health:read"),
        )
        assert response.status_code == 200
        assert response.json()["dependencies"] == {
            "postgresql": "healthy",
            "redis": "healthy",
            "durable_ingress": "healthy",
            "durable_outbox": "healthy",
        }
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"


def test_cashfree_webhook_is_verified_and_deduplicated() -> None:
    secret = "cashfree-secret"
    settings = _settings(
        demo_payments_enabled=True,
        cashfree_env="sandbox",
        cashfree_app_id=SecretStr("cashfree-app"),
        cashfree_secret_key=SecretStr(secret),
        cashfree_api_version="2025-01-01",
        cashfree_timeout_seconds=2,
        cashfree_webhook_replay_window_seconds=300,
        payment_expiry_seconds=900,
    )
    payload = {
        "type": "PAYMENT_SUCCESS_WEBHOOK",
        "data": {
            "payment": {"cf_payment_id": 10001},
            "order": {"order_id": "order-1"},
        },
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time() * 1000))
    signature = base64.b64encode(
        hmac.new(secret.encode(), timestamp.encode() + raw, hashlib.sha256).digest()
    ).decode()
    headers = {"X-Webhook-Timestamp": timestamp, "X-Webhook-Signature": signature}
    with TestClient(create_application(settings)) as client:
        accepted = client.post("/v1/provider/cashfree", content=raw, headers=headers)
        assert accepted.status_code == 202
        assert accepted.json()["status"] == "accepted"
        duplicate = client.post("/v1/provider/cashfree", content=raw, headers=headers)
        assert duplicate.status_code == 202
        assert duplicate.json()["status"] == "duplicate"
        updated_payload = deepcopy(payload)
        updated_payload["type"] = "PAYMENT_FAILED_WEBHOOK"
        updated_raw = json.dumps(updated_payload, separators=(",", ":")).encode()
        updated_signature = base64.b64encode(
            hmac.new(
                secret.encode(),
                timestamp.encode() + updated_raw,
                hashlib.sha256,
            ).digest()
        ).decode()
        updated = client.post(
            "/v1/provider/cashfree",
            content=updated_raw,
            headers={
                "X-Webhook-Timestamp": timestamp,
                "X-Webhook-Signature": updated_signature,
            },
        )
        assert updated.status_code == 202
        assert updated.json()["status"] == "accepted"
        assert (
            client.post(
                "/v1/provider/cashfree",
                content=raw,
                headers={**headers, "X-Webhook-Signature": "invalid"},
            ).status_code
            == 403
        )


def test_direct_meta_mode_is_rejected_to_preserve_lead_intake_ownership() -> None:
    with pytest.raises(ValidationError, match="direct Meta webhook"):
        _settings(
            meta_direct_webhook_enabled=True,
            meta_whatsapp_app_secret=SecretStr("meta-secret"),
            meta_whatsapp_verify_token=SecretStr("verify-token"),
        )


def test_request_body_limit_rejects_before_route_processing() -> None:
    with TestClient(create_application(_settings(max_request_body_bytes=1024))) as client:
        response = client.post("/v1/internal/events", content=b"x" * 1025)
        assert response.status_code == 413
        assert response.json()["code"] == "DCC_REQUEST_TOO_LARGE"


def test_signed_event_copy_is_independent() -> None:
    original = _event()
    copied = deepcopy(original)
    assert copied == original and copied is not original
