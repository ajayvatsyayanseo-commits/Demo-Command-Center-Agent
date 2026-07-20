from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import SecretStr, ValidationError

from demo_command_center.config.settings import Settings


def test_local_settings_are_safe_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.provider_profile == "local"
    assert settings.meta_outbound_paused is True
    assert settings.demo_payments_enabled is False
    assert settings.demo_automatic_discount_enabled is False


def test_production_rejects_local_adapter_profile() -> None:
    with pytest.raises(ValidationError, match="PROVIDER_PROFILE"):
        Settings(app_env="prod", provider_profile="local", _env_file=None)


def test_production_rejects_enabled_payment_without_configuration() -> None:
    with pytest.raises(ValidationError, match="payments require Cashfree"):
        Settings(
            app_env="staging",
            provider_profile="real",
            demo_payments_enabled=True,
            _env_file=None,
        )


def test_secret_defaults_are_empty() -> None:
    settings = Settings(_env_file=None)
    for field_name in Settings.model_fields:
        value = getattr(settings, field_name)
        if isinstance(value, SecretStr):
            assert value.get_secret_value() == ""


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"max_request_body_bytes": 100}, "MAX_REQUEST_BODY_BYTES"),
        ({"demo_scheduling_enabled": True}, "scheduling requires"),
        ({"google_meet_enabled": True}, "Google Meet requires"),
        (
            {
                "openai_enabled": True,
                "openai_api_key": SecretStr("test-key"),
                "openai_model": "test-model",
            },
            "daily and monthly budgets",
        ),
        ({"meta_direct_webhook_enabled": True}, "direct Meta webhook"),
        (
            {"meta_outbound_enabled": True, "meta_outbound_paused": False},
            "Meta outbound requires",
        ),
        (
            {"demo_post_conversion_enabled": True},
            "post-conversion requires the canonical onboarding event gateway",
        ),
        (
            {
                "internal_hmac_key_grants": {
                    "invalid key": {
                        "secret": SecretStr("test-secret"),
                        "source": "lead-intake-agent",
                        "scopes": ["events:write"],
                    }
                }
            },
            "INTERNAL_HMAC_KEY_GRANTS contains an invalid key ID",
        ),
        ({"demo_automatic_discount_enabled": True}, "prohibited"),
        (
            {"demo_automatic_payment_link_enabled": True},
            "payment-link creation is unavailable",
        ),
        (
            {"cashfree_payment_link_enabled": True},
            "payment-link creation is unavailable",
        ),
        (
            {"cashfree_order_enabled": True},
            "Cashfree order creation requires",
        ),
    ],
)
def test_capabilities_fail_closed(values: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **cast(dict[str, Any], values))


def test_production_rejects_debug_insecure_transport_and_wildcards() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            app_env="prod",
            provider_profile="real",
            app_debug=True,
            tenant_id="tenant",
            database_url=SecretStr("postgresql+asyncpg://db/internal"),
            redis_url=SecretStr("rediss://redis/internal"),
            aws_region="ap-south-1",
            public_base_url="https://public.invalid",
            internal_base_url="https://internal.invalid",
            internal_signing_key_id="key-v1",
            internal_hmac_key_grants={
                "key-v1": {
                    "secret": SecretStr("signing-secret"),
                    "source": "lead-intake-agent",
                    "scopes": ["events:write"],
                }
            },
            field_encryption_key=SecretStr("hex:" + "11" * 32),
            field_encryption_key_reference="kms:test",
            audit_hash_key=SecretStr("test-audit-key"),
            audit_hash_key_reference="kms:audit-test",
            internal_replay_window_seconds=300,
            internal_legacy_shared_secret_enabled=True,
            cors_allowed_origins=["*"],
            allowed_hosts=["*"],
            _env_file=None,
        )
    message = str(error.value)
    assert "APP_DEBUG" in message
    assert "DATABASE_URL must require TLS" in message
    assert "INTERNAL_LEGACY" in message
    assert "CORS_ALLOWED_ORIGINS" in message
    assert "ALLOWED_HOSTS" in message


def test_fully_configured_optional_capabilities_validate() -> None:
    settings = Settings(
        demo_scheduling_enabled=True,
        slot_hold_ttl_seconds=300,
        confirmation_ttl_seconds=900,
        nxtutors_website_internal_base_url="https://website.invalid",
        google_meet_enabled=True,
        google_calendar_id="calendar",
        google_calendar_auth_mode="workspace-delegation",
        google_credential_secret_arn="arn:test",
        openai_enabled=True,
        openai_api_key=SecretStr("test-key"),
        openai_model="test-model",
        openai_daily_budget=1,
        openai_monthly_budget=10,
        _env_file=None,
    )
    assert settings.demo_scheduling_enabled and settings.openai_enabled


def test_fully_configured_post_conversion_capability_validates() -> None:
    settings = Settings(
        demo_post_conversion_enabled=True,
        internal_signing_key_id="dcc-v1",
        internal_hmac_key_grants={
            "onboarding-v1": {
                "secret": SecretStr("test-onboarding-secret"),
                "source": "onboarding-agent",
                "scopes": ["events:write"],
            }
        },
        onboarding_agent_base_url="https://onboarding.invalid",
        onboarding_agent_auth_mode="canonical-hmac",
        onboarding_agent_shared_secret=SecretStr("test-onboarding-secret"),
        onboarding_agent_timeout_seconds=3,
        onboarding_handoff_policy_reference="onboarding-policy-v1",
        default_locale="en-IN",
        message_policy_reference="message-policy-v1",
        welcome_template_reference="paid.welcome.v1",
        welcome_message_version="welcome-v1",
        _env_file=None,
    )

    assert settings.demo_post_conversion_enabled is True
