from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from collections.abc import Mapping, Set
from dataclasses import dataclass
from typing import Protocol


class ReplayStore(Protocol):
    async def consume(self, key: str, ttl_seconds: int) -> bool:
        """Return true only when the key has not already been consumed."""


class InMemoryReplayStore:
    """Bounded-process replay protection for tests and local development only."""

    def __init__(self) -> None:
        self._expires: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def consume(self, key: str, ttl_seconds: int) -> bool:
        now = time.monotonic()
        async with self._lock:
            self._expires = {item: expiry for item, expiry in self._expires.items() if expiry > now}
            if key in self._expires:
                return False
            self._expires[key] = now + ttl_seconds
            return True


class RedisReplayStore:
    def __init__(self, redis_client: object) -> None:
        self._redis = redis_client

    async def consume(self, key: str, ttl_seconds: int) -> bool:
        set_method = getattr(self._redis, "set")
        result = await set_method(key, b"1", ex=ttl_seconds, nx=True)
        return bool(result)


@dataclass(frozen=True, slots=True)
class InternalIdentity:
    source: str
    audience: str
    scopes: frozenset[str]
    key_id: str
    legacy: bool = False


class InternalAuthenticationError(ValueError):
    """A safe authentication failure with no secret-bearing context."""


def canonical_request(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    source: str,
    audience: str,
    scopes: str,
    body: bytes,
) -> bytes:
    body_digest = hashlib.sha256(body).hexdigest()
    fields = (
        method.upper(),
        path,
        timestamp,
        nonce,
        source,
        audience,
        scopes,
        body_digest,
    )
    return "\n".join(fields).encode("utf-8")


def sign_internal_request(secret: str, canonical: bytes) -> str:
    return "v1=" + hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


class HmacRequestVerifier:
    def __init__(
        self,
        *,
        keys: Mapping[str, str],
        issuer: str,
        audience: str,
        replay_window_seconds: int,
        replay_store: ReplayStore,
    ) -> None:
        self._keys = {key_id: value for key_id, value in keys.items() if key_id and value}
        self._issuer = issuer
        self._audience = audience
        self._replay_window = replay_window_seconds
        self._replay_store = replay_store

    @property
    def configured(self) -> bool:
        return bool(self._keys) and self._replay_window > 0

    async def verify(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
        headers: Mapping[str, str],
        required_scopes: Set[str],
        now: int | None = None,
    ) -> InternalIdentity:
        key_id = headers.get("x-nxtutors-key-id", "")
        timestamp = headers.get("x-nxtutors-timestamp", "")
        nonce = headers.get("x-nxtutors-nonce", "")
        source = headers.get("x-nxtutors-source", "")
        issuer = headers.get("x-nxtutors-issuer", "")
        audience = headers.get("x-nxtutors-audience", "")
        scopes_value = " ".join(headers.get("x-nxtutors-scopes", "").split())
        signature = headers.get("x-nxtutors-signature", "")
        if not all((key_id, timestamp, nonce, source, issuer, audience, scopes_value, signature)):
            raise InternalAuthenticationError("missing signed request headers")
        if issuer != self._issuer or audience != self._audience:
            raise InternalAuthenticationError("invalid issuer or audience")
        if len(nonce) < 16 or len(nonce) > 128:
            raise InternalAuthenticationError("invalid nonce")
        try:
            signed_at = int(timestamp)
        except ValueError as exc:
            raise InternalAuthenticationError("invalid timestamp") from exc
        current_time = int(time.time()) if now is None else now
        if abs(current_time - signed_at) > self._replay_window:
            raise InternalAuthenticationError("request timestamp is outside the replay window")
        secret = self._keys.get(key_id)
        if secret is None:
            raise InternalAuthenticationError("unknown signing key")
        canonical = canonical_request(
            method=method,
            path=path,
            timestamp=timestamp,
            nonce=nonce,
            source=source,
            audience=audience,
            scopes=scopes_value,
            body=body,
        )
        expected = sign_internal_request(secret, canonical)
        if not hmac.compare_digest(expected.encode("ascii"), signature.encode("ascii")):
            raise InternalAuthenticationError("invalid signature")
        scopes = frozenset(scopes_value.split(" "))
        if not required_scopes.issubset(scopes):
            raise InternalAuthenticationError("insufficient scope")
        replay_key = f"dcc:auth-replay:{key_id}:{source}:{nonce}"
        if not await self._replay_store.consume(replay_key, self._replay_window):
            raise InternalAuthenticationError("request replay detected")
        return InternalIdentity(
            source=source,
            audience=audience,
            scopes=scopes,
            key_id=key_id,
        )
