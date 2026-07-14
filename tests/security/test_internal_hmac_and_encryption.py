from __future__ import annotations

import base64
import hashlib
import hmac
import time

import pytest
from cryptography.exceptions import InvalidTag

from demo_command_center.security.authentication import (
    HmacKeyGrant,
    HmacRequestVerifier,
    InMemoryReplayStore,
    InternalAuthenticationError,
    RedisReplayStore,
    canonical_request,
    sign_internal_request,
)
from demo_command_center.security.encryption import (
    EncryptionConfigurationError,
    PayloadCipher,
)


def _signed_headers(
    *,
    secret: str | None = None,
    key_id: str = "key-v1",
    timestamp: int = 1_700_000_000,
    nonce: str = "0123456789abcdef",
    issuer: str = "issuer",
    audience: str = "audience",
    source: str = "lead-intake",
    scopes: str = "events:read events:write",
    body: bytes = b"{}",
    path: str = "/v1/internal/events",
) -> dict[str, str]:
    resolved_secret = secret or "secret-v1"
    canonical = canonical_request(
        method="POST",
        path=path,
        timestamp=str(timestamp),
        nonce=nonce,
        source=source,
        audience=audience,
        scopes=scopes,
        body=body,
    )
    return {
        "x-nxtutors-key-id": key_id,
        "x-nxtutors-timestamp": str(timestamp),
        "x-nxtutors-nonce": nonce,
        "x-nxtutors-source": source,
        "x-nxtutors-issuer": issuer,
        "x-nxtutors-audience": audience,
        "x-nxtutors-scopes": scopes,
        "x-nxtutors-signature": sign_internal_request(resolved_secret, canonical),
    }


@pytest.mark.asyncio
async def test_hmac_verifier_accepts_once_and_rejects_replay() -> None:
    verifier = HmacRequestVerifier(
        key_grants={
            "key-v1": HmacKeyGrant(
                secret="secret-v1",
                source="lead-intake",
                scopes=frozenset({"events:read", "events:write"}),
            ),
            "key-old": HmacKeyGrant(
                secret="secret-old",
                source="lead-intake",
                scopes=frozenset({"events:read", "events:write"}),
            ),
        },
        issuer="issuer",
        audience="audience",
        replay_window_seconds=300,
        replay_store=InMemoryReplayStore(),
    )
    assert verifier.configured
    headers = _signed_headers()
    identity = await verifier.verify(
        method="POST",
        path="/v1/internal/events",
        body=b"{}",
        headers=headers,
        required_scopes=frozenset({"events:write"}),
        now=1_700_000_000,
    )
    assert identity.key_id == "key-v1"
    with pytest.raises(InternalAuthenticationError, match="replay"):
        await verifier.verify(
            method="POST",
            path="/v1/internal/events",
            body=b"{}",
            headers=headers,
            required_scopes=frozenset({"events:write"}),
            now=1_700_000_000,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"x-nxtutors-key-id": "missing"}, "unknown signing key"),
        ({"x-nxtutors-timestamp": "bad"}, "invalid timestamp"),
        ({"x-nxtutors-timestamp": "1699999000"}, "outside the replay window"),
        ({"x-nxtutors-nonce": "short"}, "invalid nonce"),
        ({"x-nxtutors-issuer": "wrong"}, "invalid issuer or audience"),
        ({"x-nxtutors-audience": "wrong"}, "invalid issuer or audience"),
        ({"x-nxtutors-scopes": "events:read"}, "invalid signature"),
        ({"x-nxtutors-signature": "v1=bad"}, "invalid signature"),
    ],
)
async def test_hmac_verifier_rejects_invalid_headers(changes: dict[str, str], message: str) -> None:
    verifier = HmacRequestVerifier(
        key_grants={
            "key-v1": HmacKeyGrant(
                secret="secret-v1",
                source="lead-intake",
                scopes=frozenset({"events:read", "events:write"}),
            )
        },
        issuer="issuer",
        audience="audience",
        replay_window_seconds=300,
        replay_store=InMemoryReplayStore(),
    )
    headers = {**_signed_headers(), **changes}
    with pytest.raises(InternalAuthenticationError, match=message):
        await verifier.verify(
            method="POST",
            path="/v1/internal/events",
            body=b"{}",
            headers=headers,
            required_scopes=frozenset({"events:write"}),
            now=1_700_000_000,
        )


@pytest.mark.asyncio
async def test_hmac_missing_and_insufficient_scope() -> None:
    verifier = HmacRequestVerifier(
        key_grants={
            "key-v1": HmacKeyGrant(
                secret="secret-v1",
                source="lead-intake",
                scopes=frozenset({"events:read", "events:write"}),
            )
        },
        issuer="issuer",
        audience="audience",
        replay_window_seconds=300,
        replay_store=InMemoryReplayStore(),
    )
    with pytest.raises(InternalAuthenticationError, match="missing"):
        await verifier.verify(
            method="POST",
            path="/v1/internal/events",
            body=b"{}",
            headers={},
            required_scopes=frozenset(),
            now=1_700_000_000,
        )
    headers = _signed_headers(scopes="events:read")
    with pytest.raises(InternalAuthenticationError, match="insufficient"):
        await verifier.verify(
            method="POST",
            path="/v1/internal/events",
            body=b"{}",
            headers=headers,
            required_scopes=frozenset({"events:write"}),
            now=1_700_000_000,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "message"),
    [
        (
            _signed_headers(source="onboarding-agent"),
            "not authorized for this source",
        ),
        (
            _signed_headers(scopes="events:read events:write health:read"),
            "scopes exceed the key grant",
        ),
    ],
)
async def test_hmac_key_grant_rejects_signed_identity_or_scope_escalation(
    headers: dict[str, str], message: str
) -> None:
    verifier = HmacRequestVerifier(
        key_grants={
            "key-v1": HmacKeyGrant(
                secret="secret-v1",
                source="lead-intake",
                scopes=frozenset({"events:read", "events:write"}),
            )
        },
        issuer="issuer",
        audience="audience",
        replay_window_seconds=300,
        replay_store=InMemoryReplayStore(),
    )

    with pytest.raises(InternalAuthenticationError, match=message):
        await verifier.verify(
            method="POST",
            path="/v1/internal/events",
            body=b"{}",
            headers=headers,
            required_scopes=frozenset({"events:write"}),
            now=1_700_000_000,
        )


class _RedisFake:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def set(self, key: str, value: bytes, *, ex: int, nx: bool) -> bool:
        assert value == b"1" and ex > 0 and nx
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


@pytest.mark.asyncio
async def test_redis_replay_store_has_atomic_consume_semantics() -> None:
    store = RedisReplayStore(_RedisFake())
    assert await store.consume("nonce", 30)
    assert not await store.consume("nonce", 30)


def test_payload_cipher_roundtrip_and_configuration_failures() -> None:
    key = bytes(range(32))
    encoded = "base64:" + base64.urlsafe_b64encode(key).decode().rstrip("=")
    cipher = PayloadCipher.from_encoded_key(encoded)
    envelope = cipher.encrypt(b"restricted", associated_data=b"tenant:event")
    assert b"restricted" not in envelope
    assert cipher.decrypt(envelope, associated_data=b"tenant:event") == b"restricted"
    with pytest.raises(InvalidTag):
        cipher.decrypt(envelope, associated_data=b"wrong")
    with pytest.raises(ValueError, match="unsupported"):
        cipher.decrypt(b"bad", associated_data=b"tenant:event")
    assert PayloadCipher.from_encoded_key("hex:" + "11" * 32)
    for invalid in ("plain-secret", "hex:not-hex", "hex:11"):
        with pytest.raises(EncryptionConfigurationError):
            PayloadCipher.from_encoded_key(invalid)


def test_signing_uses_sha256_hmac() -> None:
    canonical = b"POST\n/path"
    expected = hmac.new(b"secret", canonical, hashlib.sha256).hexdigest()
    assert sign_internal_request("secret", canonical) == f"v1={expected}"
    assert int(time.time()) > 0
