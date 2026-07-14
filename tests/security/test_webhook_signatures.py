import base64
import hashlib
import hmac

from demo_command_center.security.signatures.webhook import (
    verify_cashfree_signature,
    verify_meta_signature,
)


def test_meta_signature_uses_raw_body() -> None:
    body = b'{"ordered":true}'
    secret = "test-secret"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body, f"sha256={digest}", secret)
    assert not verify_meta_signature(b'{"ordered": false}', f"sha256={digest}", secret)
    assert not verify_meta_signature(body, None, secret)
    assert not verify_meta_signature(body, digest, secret)
    assert not verify_meta_signature(body, f"sha256={digest}", "")


def test_cashfree_signature_binds_timestamp_and_body() -> None:
    body = b'{"type":"PAYMENT_SUCCESS"}'
    timestamp = "1700000000"
    secret = "test-secret"
    signature = base64.b64encode(
        hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
    ).decode()
    assert verify_cashfree_signature(body, timestamp, signature, secret)
    assert not verify_cashfree_signature(body, "1700000001", signature, secret)
    assert not verify_cashfree_signature(body, None, signature, secret)
    assert not verify_cashfree_signature(body, timestamp, None, secret)
    assert not verify_cashfree_signature(body, timestamp, signature, "")
    assert not verify_cashfree_signature(
        body,
        "not-a-time",
        signature,
        secret,
        replay_window_seconds=60,
        now_seconds=1_700_000_000,
    )
    assert not verify_cashfree_signature(
        body,
        timestamp,
        signature,
        secret,
        replay_window_seconds=60,
        now_seconds=1_700_001_000,
    )
    assert verify_cashfree_signature(
        body,
        timestamp,
        signature,
        secret,
        replay_window_seconds=60,
        now_seconds=1_700_000_000,
    )
