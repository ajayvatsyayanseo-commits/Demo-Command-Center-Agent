from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import parse_qs, urlsplit

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class InternalHmacKeyGrantSettings(BaseModel):
    """One inbound service identity and its server-authorized scopes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    secret: SecretStr
    source: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    scopes: frozenset[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_grant(self) -> Self:
        if not self.secret.get_secret_value():
            raise ValueError("HMAC key grant secret must not be empty")
        if any(
            not scope or len(scope) > 128 or any(character.isspace() for character in scope)
            for scope in self.scopes
        ):
            raise ValueError("HMAC key grant scopes must be non-empty tokens")
        return self


class Settings(BaseSettings):
    """Environment contract. Policy values have no production defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "test", "dev", "staging", "prod"] = "local"
    app_name: str = "demo-command-center-agent"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    app_debug: bool = False
    max_request_body_bytes: int = 1_048_576
    cors_allowed_origins: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "testserver"])
    public_base_url: AnyHttpUrl | None = None
    internal_base_url: AnyHttpUrl | None = None
    default_timezone: str = "Asia/Kolkata"
    default_locale: str | None = None
    tenant_id: str | None = None
    provider_profile: Literal["local", "real"] = "local"

    database_url: SecretStr = Field(default=SecretStr(""))
    db_pool_min: int | None = None
    db_pool_max: int | None = None
    db_connect_timeout: int | None = None
    db_statement_timeout: int | None = None
    db_require_tls: bool = True
    field_encryption_key: SecretStr = Field(default=SecretStr(""))
    field_encryption_key_reference: str | None = None
    audit_hash_key: SecretStr = Field(default=SecretStr(""))
    audit_hash_key_reference: str | None = None
    redis_url: SecretStr = Field(default=SecretStr(""))
    cache_default_ttl_seconds: int | None = None
    lock_default_ttl_seconds: int | None = None

    aws_region: str | None = None
    aws_account_id: str | None = None
    sqs_inbound_queue_url: str | None = None
    sqs_scheduling_queue_url: str | None = None
    sqs_outbound_queue_url: str | None = None
    sqs_reminders_queue_url: str | None = None
    sqs_payments_queue_url: str | None = None
    sqs_analytics_queue_url: str | None = None
    sqs_model_evaluation_queue_url: str | None = None
    sqs_human_handoff_queue_url: str | None = None
    s3_analytics_bucket: str | None = None
    s3_model_bucket: str | None = None
    ses_from_address: str | None = None
    aws_secrets_prefix: str | None = None
    kms_key_arn: str | None = None
    eventbridge_schedule_group: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    cloudwatch_namespace: str | None = None

    meta_graph_api_version: str | None = None
    meta_whatsapp_access_token: SecretStr = Field(default=SecretStr(""))
    meta_whatsapp_app_secret: SecretStr = Field(default=SecretStr(""))
    meta_whatsapp_verify_token: SecretStr = Field(default=SecretStr(""))
    meta_whatsapp_phone_number_id: str | None = None
    meta_whatsapp_business_account_id: str | None = None
    meta_template_language: str | None = None
    meta_direct_webhook_enabled: bool = False
    meta_outbound_enabled: bool = False
    meta_outbound_paused: bool = True

    lead_intake_base_url: AnyHttpUrl | None = None
    lead_intake_auth_mode: str | None = None
    lead_intake_shared_secret: SecretStr = Field(default=SecretStr(""))
    lead_intake_timeout_seconds: int | None = None
    onboarding_agent_base_url: AnyHttpUrl | None = None
    onboarding_agent_auth_mode: str | None = None
    onboarding_agent_shared_secret: SecretStr = Field(default=SecretStr(""))
    onboarding_agent_timeout_seconds: int | None = None
    onboarding_handoff_policy_reference: str | None = None
    message_policy_reference: str | None = None
    welcome_template_reference: str | None = None
    welcome_message_version: str | None = None
    outbound_message_gateway_base_url: AnyHttpUrl | None = None
    internal_jwt_issuer: str | None = None
    internal_jwt_audience: str | None = None
    internal_signing_key_id: str | None = None
    internal_hmac_key_grants: dict[str, InternalHmacKeyGrantSettings] = Field(default_factory=dict)
    internal_replay_window_seconds: int | None = None
    internal_auth_issuer: str = "nxtutors-internal"
    internal_auth_audience: str = "demo-command-center"
    internal_legacy_shared_secret_enabled: bool = True

    nxtutors_website_base_url: AnyHttpUrl | None = None
    nxtutors_website_internal_base_url: AnyHttpUrl | None = None
    nxtutors_website_auth_mode: str | None = None
    nxtutors_website_shared_secret: SecretStr = Field(default=SecretStr(""))
    nxtutors_website_timeout_seconds: int | None = None

    google_calendar_auth_mode: str | None = None
    google_calendar_id: str | None = None
    google_workspace_delegated_user: str | None = None
    google_credential_secret_arn: str | None = None
    google_calendar_scopes: str | None = None
    google_meet_enabled: bool = False

    cashfree_env: Literal["sandbox", "production"] | None = None
    cashfree_app_id: SecretStr = Field(default=SecretStr(""))
    cashfree_secret_key: SecretStr = Field(default=SecretStr(""))
    cashfree_api_version: str | None = None
    cashfree_timeout_seconds: int | None = None
    cashfree_webhook_replay_window_seconds: int | None = None
    cashfree_payment_link_enabled: bool = False
    cashfree_order_enabled: bool = False

    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str | None = None
    openai_extraction_model: str | None = None
    openai_drafting_model: str | None = None
    openai_request_timeout_seconds: int | None = None
    openai_max_retries: int | None = None
    openai_max_input_tokens: int | None = None
    openai_max_output_tokens: int | None = None
    openai_daily_budget: float | None = None
    openai_monthly_budget: float | None = None
    openai_enabled: bool = False

    reminder_policy_reference: str | None = None
    quiet_hours_policy_reference: str | None = None
    slot_hold_ttl_seconds: int | None = None
    confirmation_ttl_seconds: int | None = None
    discount_policy_source: str | None = None
    payment_expiry_seconds: int | None = None
    rate_limit_policy_reference: str | None = None
    retry_policy_reference: str | None = None
    retention_policy_reference: str | None = None
    evaluation_policy_reference: str | None = None
    evaluation_window_days: int | None = None
    evaluation_min_samples: int | None = None
    forecast_brier_threshold: float | None = None
    forecast_calibration_error_threshold: float | None = None
    payment_reconcile_delay_seconds: int | None = None
    payment_reconciliation_policy_reference: str | None = None
    evaluation_positive_outcomes: list[str] = Field(default_factory=list)

    demo_command_center_enabled: bool = True
    demo_scheduling_enabled: bool = False
    demo_reminders_enabled: bool = False
    demo_forecasting_enabled: bool = False
    demo_objection_extraction_enabled: bool = False
    demo_post_conversion_enabled: bool = False
    demo_discounts_enabled: bool = False
    demo_payments_enabled: bool = False
    demo_outbound_paused: bool = True
    demo_new_bookings_paused: bool = True
    demo_google_meet_enabled: bool = False
    demo_openai_enabled: bool = False
    demo_automatic_discount_enabled: bool = False
    demo_automatic_payment_link_enabled: bool = False
    retention_cleanup_enabled: bool = False
    payment_reconciliation_enabled: bool = False
    model_evaluation_enabled: bool = False
    dlq_redrive_enabled: bool = False

    @staticmethod
    def _database_tls_enabled(database_url: str) -> bool:
        query = parse_qs(urlsplit(database_url).query)
        values = query.get("ssl", []) + query.get("sslmode", [])
        return any(
            value.lower() in {"require", "verify-ca", "verify-full", "true"} for value in values
        )

    @model_validator(mode="after")
    def validate_fail_closed_configuration(self) -> Self:
        errors: list[str] = []
        if any(
            not key_id or len(key_id) > 128 or any(character.isspace() for character in key_id)
            for key_id in self.internal_hmac_key_grants
        ):
            errors.append("INTERNAL_HMAC_KEY_GRANTS contains an invalid key ID")
        if self.max_request_body_bytes < 1_024 or self.max_request_body_bytes > 10_485_760:
            errors.append("MAX_REQUEST_BODY_BYTES must be between 1024 and 10485760")
        if self.app_env == "prod":
            if self.provider_profile != "real":
                errors.append("PROVIDER_PROFILE must be real in prod")
            if self.app_debug:
                errors.append("APP_DEBUG must be false in prod")
            for name, value in (
                ("TENANT_ID", self.tenant_id),
                ("DATABASE_URL", self.database_url.get_secret_value()),
                ("REDIS_URL", self.redis_url.get_secret_value()),
                ("AWS_REGION", self.aws_region),
                ("INTERNAL_SIGNING_KEY_ID", self.internal_signing_key_id),
                ("FIELD_ENCRYPTION_KEY", self.field_encryption_key.get_secret_value()),
                ("FIELD_ENCRYPTION_KEY_REFERENCE", self.field_encryption_key_reference),
                ("AUDIT_HASH_KEY", self.audit_hash_key.get_secret_value()),
                ("AUDIT_HASH_KEY_REFERENCE", self.audit_hash_key_reference),
                ("INTERNAL_REPLAY_WINDOW_SECONDS", self.internal_replay_window_seconds),
                ("INTERNAL_HMAC_KEY_GRANTS", self.internal_hmac_key_grants),
            ):
                if not value:
                    errors.append(f"{name} is required in prod")
            for name, url in (
                ("PUBLIC_BASE_URL", self.public_base_url),
                ("INTERNAL_BASE_URL", self.internal_base_url),
            ):
                if url is None or url.scheme != "https":
                    errors.append(f"{name} must be an HTTPS URL in prod")
            database_url = self.database_url.get_secret_value()
            if (
                self.db_require_tls
                and database_url
                and not self._database_tls_enabled(database_url)
            ):
                errors.append("DATABASE_URL must require TLS in prod")
            if self.internal_legacy_shared_secret_enabled:
                errors.append("INTERNAL_LEGACY_SHARED_SECRET_ENABLED must be false in prod")
            if any(
                origin == "*" or not origin.startswith("https://")
                for origin in self.cors_allowed_origins
            ):
                errors.append(
                    "CORS_ALLOWED_ORIGINS must contain only explicit HTTPS origins in prod"
                )
            if not self.allowed_hosts or "*" in self.allowed_hosts:
                errors.append("ALLOWED_HOSTS must contain explicit hosts in prod")

        if self.demo_scheduling_enabled:
            if self.slot_hold_ttl_seconds is None or self.confirmation_ttl_seconds is None:
                errors.append("scheduling requires slot and confirmation TTL policy values")
            if self.nxtutors_website_internal_base_url is None:
                errors.append("scheduling requires NXTUTORS_WEBSITE_INTERNAL_BASE_URL")
        if self.demo_google_meet_enabled or self.google_meet_enabled:
            if not all(
                [
                    self.google_calendar_id,
                    self.google_calendar_auth_mode,
                    self.google_credential_secret_arn,
                ]
            ):
                errors.append("Google Meet requires calendar ownership and credential reference")
        if self.demo_payments_enabled:
            if not all(
                [
                    self.cashfree_env,
                    self.cashfree_app_id.get_secret_value(),
                    self.cashfree_secret_key.get_secret_value(),
                    self.cashfree_api_version,
                    self.cashfree_timeout_seconds,
                    self.payment_expiry_seconds,
                    self.cashfree_webhook_replay_window_seconds,
                ]
            ):
                errors.append(
                    "payments require Cashfree credentials, API version, and expiry policy"
                )
        if self.cashfree_order_enabled:
            if not all(
                [
                    self.demo_payments_enabled,
                    self.tenant_id,
                    self.nxtutors_website_internal_base_url,
                    self.nxtutors_website_shared_secret.get_secret_value(),
                    self.nxtutors_website_timeout_seconds,
                    self.internal_signing_key_id,
                    self.audit_hash_key.get_secret_value(),
                ]
            ):
                errors.append(
                    "Cashfree order creation requires payments, the authoritative website "
                    "gateway, internal signing, and request hashing"
                )
        if self.retention_cleanup_enabled and not self.retention_policy_reference:
            errors.append("retention cleanup requires an approved policy reference")
        if self.payment_reconciliation_enabled and not all(
            [
                self.demo_payments_enabled,
                self.payment_reconcile_delay_seconds,
                self.payment_reconciliation_policy_reference,
            ]
        ):
            errors.append("payment reconciliation requires payments and a retry delay")
        if self.model_evaluation_enabled and not all(
            [
                self.evaluation_policy_reference,
                self.evaluation_window_days,
                self.evaluation_min_samples,
                self.forecast_brier_threshold,
                self.forecast_calibration_error_threshold,
                self.evaluation_positive_outcomes,
            ]
        ):
            errors.append("model evaluation requires an approved threshold policy")
        if self.demo_openai_enabled or self.openai_enabled:
            if not self.openai_api_key.get_secret_value() or not self.openai_model:
                errors.append("OpenAI capability requires API key and model")
            if self.openai_daily_budget is None or self.openai_monthly_budget is None:
                errors.append("OpenAI capability requires daily and monthly budgets")
        if self.meta_direct_webhook_enabled:
            errors.append(
                "direct Meta webhook is prohibited; Lead Intake must remain the canonical "
                "public Meta ingress"
            )
        if self.meta_outbound_enabled and not self.meta_outbound_paused:
            errors.append(
                "Meta outbound requires the canonical Lead Intake gateway and must remain "
                "paused in Demo Command Center"
            )
        if not self.demo_outbound_paused:
            if self.lead_intake_auth_mode != "canonical-hmac" or not all(
                [
                    self.outbound_message_gateway_base_url or self.lead_intake_base_url,
                    self.lead_intake_shared_secret.get_secret_value(),
                    self.lead_intake_timeout_seconds,
                    self.internal_signing_key_id,
                ]
            ):
                errors.append("unpaused demo outbound requires the canonical Lead Intake gateway")
        if self.demo_post_conversion_enabled:
            onboarding_inbound_grant = any(
                grant.source == "onboarding-agent" and "events:write" in grant.scopes
                for grant in self.internal_hmac_key_grants.values()
            )
            if self.onboarding_agent_auth_mode != "canonical-hmac" or not all(
                [
                    self.onboarding_agent_base_url,
                    self.onboarding_agent_shared_secret.get_secret_value(),
                    self.onboarding_agent_timeout_seconds,
                    self.internal_signing_key_id,
                    onboarding_inbound_grant,
                    self.onboarding_handoff_policy_reference,
                    self.default_locale,
                    self.message_policy_reference,
                    self.welcome_template_reference,
                    self.welcome_message_version,
                ]
            ):
                errors.append("post-conversion requires the canonical onboarding event gateway")
        if self.app_env == "prod" and not all(
            [
                self.nxtutors_website_internal_base_url,
                self.nxtutors_website_shared_secret.get_secret_value(),
                self.nxtutors_website_timeout_seconds,
            ]
        ):
            errors.append("production requires the versioned website integration gateway")
        if self.demo_automatic_discount_enabled:
            errors.append("automatic discount authorization is prohibited")
        if self.demo_automatic_payment_link_enabled or self.cashfree_payment_link_enabled:
            errors.append("payment-link creation is unavailable and must remain disabled")
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
