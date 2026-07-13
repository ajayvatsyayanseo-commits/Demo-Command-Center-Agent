from __future__ import annotations

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
