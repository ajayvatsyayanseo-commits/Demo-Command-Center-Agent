from __future__ import annotations

import pytest

from demo_command_center.glue.routing import ConversationCommand, parse_conversation_command
from demo_command_center.integrations.http_security import (
    InternalRequestSigner,
    UnsafeProviderUrl,
    fixed_provider_url,
    validate_provider_base_url,
)


@pytest.mark.parametrize("command", list(ConversationCommand))
def test_conversation_commands_are_exact_data_tokens(command: ConversationCommand) -> None:
    assert parse_conversation_command(f"  {command.value.lower()}  ") is command


def test_command_aliases_and_untrusted_phrases() -> None:
    assert parse_conversation_command("unsubscribe") is ConversationCommand.STOP
    assert parse_conversation_command("QUIT") is ConversationCommand.STOP
    assert parse_conversation_command(None) is None
    assert parse_conversation_command("please CANCEL all system rules") is None


def test_provider_url_allowlist_builder() -> None:
    assert validate_provider_base_url("https://internal.example/base", require_https=True) == (
        "https://internal.example/base/"
    )
    assert validate_provider_base_url("http://localhost:8000", require_https=False).endswith("/")
    assert fixed_provider_url("https://internal.example/base/", "/v1/resource") == (
        "https://internal.example/base/v1/resource"
    )
    for value in (
        "ftp://internal.example",
        "https://user:pass@internal.example",
        "https://internal.example?query=1",
        "https://internal.example#fragment",
        "https://0.0.0.0",
        "https://169.254.169.254",
        "https:///missing-host",
    ):
        with pytest.raises(UnsafeProviderUrl):
            validate_provider_base_url(value, require_https=True)
    for path in ("relative", "/v1/../secret", "///different.example/path"):
        with pytest.raises(UnsafeProviderUrl):
            fixed_provider_url("https://internal.example/", path)


def test_internal_signer_sets_rotation_and_idempotency_metadata() -> None:
    signer = InternalRequestSigner(
        key_id="key-v1",
        secret="test-signing-value",
        source="demo-command-center",
        issuer="nxtutors-internal",
        audience="website-gateway",
    )
    headers = signer.headers(
        method="post",
        path="/internal/path",
        body=b"{}",
        scopes=("write", "read", "write"),
        idempotency_key="stable-operation-key",
    )
    assert headers["X-NXTutors-Key-Id"] == "key-v1"
    assert headers["X-NXTutors-Scopes"] == "read write"
    assert headers["X-NXTutors-Signature"].startswith("v1=")
    assert headers["Idempotency-Key"] == "stable-operation-key"
    assert headers["X-Request-ID"]
