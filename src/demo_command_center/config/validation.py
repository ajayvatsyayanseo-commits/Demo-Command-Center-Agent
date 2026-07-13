from __future__ import annotations

from dataclasses import dataclass

from demo_command_center.config.settings import Settings


@dataclass(frozen=True, slots=True)
class ConfigurationStatus:
    present: bool
    connection_validated: bool = False
    sandbox_validated: bool = False
    live_tested: bool = False


def safe_configuration_inventory(settings: Settings) -> dict[str, ConfigurationStatus]:
    return {
        "database": ConfigurationStatus(bool(settings.database_url.get_secret_value())),
        "redis": ConfigurationStatus(bool(settings.redis_url.get_secret_value())),
        "cashfree": ConfigurationStatus(bool(settings.cashfree_app_id.get_secret_value())),
        "google_calendar": ConfigurationStatus(bool(settings.google_calendar_id)),
        "openai": ConfigurationStatus(bool(settings.openai_api_key.get_secret_value())),
    }
