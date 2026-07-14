from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from demo_command_center.security.authentication import canonical_request, sign_internal_request


class UnsafeProviderUrl(ValueError):
    """Raised when a provider URL violates the fixed-destination policy."""


def validate_provider_base_url(base_url: str, *, require_https: bool) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme not in ({"https"} if require_https else {"http", "https"}):
        raise UnsafeProviderUrl("provider base URL uses a prohibited scheme")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise UnsafeProviderUrl("provider base URL is malformed")
    if parsed.hostname in {"0.0.0.0", "169.254.169.254"}:  # noqa: S104 - URL validation
        raise UnsafeProviderUrl("provider base URL points to a prohibited host")
    return base_url.rstrip("/") + "/"


def fixed_provider_url(base_url: str, path: str) -> str:
    if not path.startswith("/") or ".." in path:
        raise UnsafeProviderUrl("provider path is not an approved absolute path")
    joined = urljoin(base_url, path.removeprefix("/"))
    if urlsplit(joined).netloc != urlsplit(base_url).netloc:
        raise UnsafeProviderUrl("provider path escaped the configured host")
    return joined


@dataclass(frozen=True, slots=True)
class InternalRequestSigner:
    key_id: str
    secret: str
    source: str
    issuer: str
    audience: str

    def headers(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
        scopes: tuple[str, ...],
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        scope_value = " ".join(sorted(set(scopes)))
        canonical = canonical_request(
            method=method,
            path=path,
            timestamp=timestamp,
            nonce=nonce,
            source=self.source,
            audience=self.audience,
            scopes=scope_value,
            body=body,
        )
        headers = {
            "Content-Type": "application/json",
            "X-NXTutors-Key-Id": self.key_id,
            "X-NXTutors-Timestamp": timestamp,
            "X-NXTutors-Nonce": nonce,
            "X-NXTutors-Source": self.source,
            "X-NXTutors-Issuer": self.issuer,
            "X-NXTutors-Audience": self.audience,
            "X-NXTutors-Scopes": scope_value,
            "X-NXTutors-Signature": sign_internal_request(self.secret, canonical),
            "X-Request-ID": str(uuid4()),
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers
