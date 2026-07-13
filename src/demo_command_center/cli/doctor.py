from __future__ import annotations

import json
from typing import Any

from demo_command_center.config.settings import get_settings


def _status(configured: bool) -> dict[str, bool]:
    return {
        "configuration_present": configured,
        "connection_validated": False,
        "sandbox_validated": False,
        "live_integration_tested": False,
    }


def diagnostic_report() -> dict[str, Any]:
    settings = get_settings()
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "provider_profile": settings.provider_profile,
        "checks": {
            "postgresql": _status(bool(settings.database_url.get_secret_value())),
            "redis": _status(bool(settings.redis_url.get_secret_value())),
            "lead_intake": _status(
                settings.lead_intake_base_url is not None
                and bool(settings.lead_intake_shared_secret.get_secret_value())
            ),
            "website_gateway": _status(
                settings.nxtutors_website_internal_base_url is not None
                and bool(settings.nxtutors_website_shared_secret.get_secret_value())
            ),
            "onboarding": _status(
                settings.onboarding_agent_base_url is not None
                and bool(settings.onboarding_agent_shared_secret.get_secret_value())
            ),
            "google_calendar": _status(
                bool(settings.google_calendar_id and settings.google_credential_secret_arn)
            ),
            "cashfree": _status(
                bool(
                    settings.cashfree_app_id.get_secret_value()
                    and settings.cashfree_secret_key.get_secret_value()
                )
            ),
            "amazon_ses": _status(bool(settings.ses_from_address)),
            "openai": _status(bool(settings.openai_api_key.get_secret_value())),
        },
        "note": "Presence is not connectivity; no live integration is claimed by this report.",
    }


def main() -> None:
    print(json.dumps(diagnostic_report(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
