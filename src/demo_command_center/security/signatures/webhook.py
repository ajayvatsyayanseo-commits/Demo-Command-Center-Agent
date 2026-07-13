from __future__ import annotations

import base64
import hashlib
import hmac
import time


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not app_secret or not signature_header.startswith("sha256="):
        return False
    supplied = signature_header.removeprefix("sha256=")
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)


def verify_cashfree_signature(
    raw_body: bytes,
    timestamp_header: str | None,
    signature_header: str | None,
    secret: str,
    *,
    replay_window_seconds: int | None = None,
    now_seconds: int | None = None,
) -> bool:
    if not timestamp_header or not signature_header or not secret:
        return False
    if replay_window_seconds is not None:
        try:
            timestamp = int(timestamp_header)
        except ValueError:
            return False
        if timestamp > 10_000_000_000:
            timestamp //= 1_000
        now = int(time.time()) if now_seconds is None else now_seconds
        if replay_window_seconds <= 0 or abs(now - timestamp) > replay_window_seconds:
            return False
    signed = timestamp_header.encode("utf-8") + raw_body
    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest()
    ).decode("ascii")
    return hmac.compare_digest(expected, signature_header)
