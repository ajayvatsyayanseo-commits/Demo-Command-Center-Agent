from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.api.schemas.ingress import IngressReceipt, IngressStatus
from demo_command_center.config.feature_flags import FeatureFlags
from demo_command_center.config.settings import Settings
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.database.session import (
    DatabaseResources,
    build_database_resources,
)
from demo_command_center.infrastructure.inbox import (
    DatabaseEventIngress,
    DefaultInboxEventHandler,
    DurableInboxProcessor,
)
from demo_command_center.infrastructure.outbox import DurableOutboxPublisher
from demo_command_center.infrastructure.outbox.lifecycle import LifecycleOutboxDeliveryRecorder
from demo_command_center.infrastructure.payments import PaymentOrderJobService
from demo_command_center.infrastructure.payments.outbox_recorder import (
    CompositeOutboxDeliveryRecorder,
    DeliveryRecorder,
    PaymentOutboxDeliveryRecorder,
)
from demo_command_center.integrations.cashfree import CashfreePaymentGateway
from demo_command_center.integrations.http_security import InternalRequestSigner
from demo_command_center.integrations.lead_intake import LeadIntakeOutboundGateway
from demo_command_center.integrations.nxtutors_website import NxtutorsWebsiteGateway
from demo_command_center.integrations.onboarding import OnboardingEventGateway
from demo_command_center.integrations.outbox_router import RoutingOutboxTransport
from demo_command_center.security.authentication import (
    HmacKeyGrant,
    HmacRequestVerifier,
    InMemoryReplayStore,
    RedisReplayStore,
    ReplayStore,
)
from demo_command_center.security.encryption import PayloadCipher


class EventIngress(Protocol):
    async def accept(self, event: AgentEventEnvelope) -> IngressReceipt: ...

    async def status(self, event_id: UUID) -> IngressStatus | None: ...


@dataclass(slots=True)
class LocalEventIngress:
    """Explicit local-development adapter. It is never selected in production."""

    seen: dict[UUID, datetime] = field(default_factory=dict)

    async def accept(self, event: AgentEventEnvelope) -> IngressReceipt:
        status = "duplicate" if event.event_id in self.seen else "accepted"
        self.seen.setdefault(event.event_id, datetime.now(UTC))
        return IngressReceipt(
            event_id=event.event_id,
            status=status,
            correlation_id=event.correlation_id,
        )

    async def status(self, event_id: UUID) -> IngressStatus | None:
        received_at = self.seen.get(event_id)
        if received_at is None:
            return None
        return IngressStatus(
            event_id=event_id,
            status="pending",
            received_at=received_at,
            processed_at=None,
            processing_attempts=0,
            error_code=None,
        )


class UnconfiguredEventIngress:
    async def accept(self, event: AgentEventEnvelope) -> IngressReceipt:
        del event
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Durable event ingress is not configured",
        )

    async def status(self, event_id: UUID) -> IngressStatus | None:
        del event_id
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Durable event ingress is not configured",
        )


@dataclass(slots=True)
class DependencyContainer:
    settings: Settings
    feature_flags: FeatureFlags
    event_ingress: EventIngress
    internal_auth: HmacRequestVerifier
    database: DatabaseResources | None = None
    redis: Redis | None = None
    inbox_processor: DurableInboxProcessor | None = None
    outbox_publisher: DurableOutboxPublisher | None = None
    outbox_transport: RoutingOutboxTransport | None = None
    payment_order_jobs: PaymentOrderJobService | None = None

    @classmethod
    def build(cls, settings: Settings) -> DependencyContainer:
        ingress: EventIngress = UnconfiguredEventIngress()
        database: DatabaseResources | None = None
        redis_client: Redis | None = None
        inbox_processor: DurableInboxProcessor | None = None
        outbox_publisher: DurableOutboxPublisher | None = None
        outbox_transport: RoutingOutboxTransport | None = None
        payment_order_jobs: PaymentOrderJobService | None = None
        replay_store: ReplayStore
        if settings.provider_profile == "real":
            database = build_database_resources(settings)
            redis_url = settings.redis_url.get_secret_value()
            if not redis_url:
                raise ValueError("REDIS_URL is required for real provider profile")
            redis_client = Redis.from_url(redis_url, decode_responses=False)
            key = settings.field_encryption_key.get_secret_value()
            key_reference = settings.field_encryption_key_reference
            if not key or not key_reference:
                raise ValueError("durable ingress requires a field encryption key and reference")
            cipher = PayloadCipher.from_encoded_key(key)
            blocked_event_types: set[str] = set()
            if not settings.demo_command_center_enabled:
                blocked_event_types.update(DefaultInboxEventHandler.SUPPORTED_EVENT_TYPES)
            else:
                if settings.demo_new_bookings_paused:
                    blocked_event_types.add("whatsapp.handoff.demo.v1")
                if not settings.demo_payments_enabled:
                    blocked_event_types.add("cashfree.payment.webhook.received.v1")
                if not settings.demo_post_conversion_enabled:
                    blocked_event_types.update(
                        {
                            "onboarding.handoff.accepted.v1",
                            "onboarding.completed.v1",
                        }
                    )
            if settings.cashfree_order_enabled:
                hash_key = settings.audit_hash_key.get_secret_value()
                tenant_id = settings.tenant_id
                if not hash_key or not tenant_id:
                    raise ValueError("Cashfree order creation requires tenant and request hashing")
                payment_order_jobs = PaymentOrderJobService(
                    sessions=database.sessions,
                    cipher=cipher,
                    key_reference=key_reference,
                    request_hash_key=hash_key,
                    tenant_id=tenant_id,
                )
            ingress = DatabaseEventIngress(
                sessions=database.sessions,
                cipher=cipher,
                key_reference=key_reference,
            )
            website: NxtutorsWebsiteGateway | None = None
            website_url = settings.nxtutors_website_internal_base_url
            website_secret = settings.nxtutors_website_shared_secret.get_secret_value()
            signing_key_id = settings.internal_signing_key_id
            if (
                website_url is not None
                and website_secret
                and signing_key_id
                and settings.nxtutors_website_timeout_seconds is not None
            ):
                website = NxtutorsWebsiteGateway(
                    base_url=str(website_url),
                    signer=InternalRequestSigner(
                        key_id=signing_key_id,
                        secret=website_secret,
                        source="demo-command-center",
                        issuer=settings.internal_auth_issuer,
                        audience="nxtutors-website-gateway",
                    ),
                    timeout_seconds=settings.nxtutors_website_timeout_seconds,
                    require_https=settings.app_env in {"staging", "prod"},
                )
            inbox_processor = DurableInboxProcessor(
                sessions=database.sessions,
                cipher=cipher,
                handler=DefaultInboxEventHandler(
                    default_timezone=settings.default_timezone,
                    cipher=cipher,
                    key_reference=key_reference,
                    cashfree_environment=settings.cashfree_env or "sandbox",
                    onboarding_policy_reference=settings.onboarding_handoff_policy_reference,
                    message_policy_reference=settings.message_policy_reference,
                    welcome_template_reference=settings.welcome_template_reference,
                    welcome_message_version=settings.welcome_message_version,
                    website=website,
                ),
                blocked_event_types=frozenset(blocked_event_types),
            )
            lead_intake: LeadIntakeOutboundGateway | None = None
            lead_url = settings.outbound_message_gateway_base_url or settings.lead_intake_base_url
            lead_secret = settings.lead_intake_shared_secret.get_secret_value()
            if (
                lead_url is not None
                and lead_secret
                and signing_key_id
                and settings.lead_intake_timeout_seconds is not None
            ):
                lead_intake = LeadIntakeOutboundGateway(
                    base_url=str(lead_url),
                    signer=InternalRequestSigner(
                        key_id=signing_key_id,
                        secret=lead_secret,
                        source=settings.app_name,
                        issuer=settings.internal_auth_issuer,
                        audience="lead-intake-agent",
                    ),
                    timeout_seconds=settings.lead_intake_timeout_seconds,
                    require_https=settings.app_env in {"staging", "prod"},
                )
            onboarding: OnboardingEventGateway | None = None
            onboarding_secret = settings.onboarding_agent_shared_secret.get_secret_value()
            if (
                settings.onboarding_agent_auth_mode == "canonical-hmac"
                and settings.onboarding_agent_base_url is not None
                and onboarding_secret
                and signing_key_id
                and settings.onboarding_agent_timeout_seconds is not None
            ):
                onboarding = OnboardingEventGateway(
                    base_url=str(settings.onboarding_agent_base_url),
                    signer=InternalRequestSigner(
                        key_id=signing_key_id,
                        secret=onboarding_secret,
                        source=settings.app_name,
                        issuer=settings.internal_auth_issuer,
                        audience="onboarding-agent",
                    ),
                    timeout_seconds=settings.onboarding_agent_timeout_seconds,
                    require_https=settings.app_env in {"staging", "prod"},
                )
            cashfree: CashfreePaymentGateway | None = None
            if settings.cashfree_order_enabled:
                cashfree_timeout = settings.cashfree_timeout_seconds
                cashfree_environment = settings.cashfree_env
                cashfree_api_version = settings.cashfree_api_version
                if (
                    cashfree_timeout is None
                    or cashfree_environment is None
                    or cashfree_api_version is None
                ):
                    raise ValueError("Cashfree order creation is incompletely configured")
                cashfree = CashfreePaymentGateway(
                    environment=cashfree_environment,
                    app_id=settings.cashfree_app_id.get_secret_value(),
                    secret_key=settings.cashfree_secret_key.get_secret_value(),
                    api_version=cashfree_api_version,
                    timeout_seconds=cashfree_timeout,
                )
            outbox_transport = RoutingOutboxTransport(
                website=website,
                lead_intake=lead_intake,
                onboarding=onboarding,
                cashfree=cashfree,
            )
            recorders: list[DeliveryRecorder] = []
            if settings.cashfree_order_enabled:
                payment_expiry_seconds = settings.payment_expiry_seconds
                cashfree_environment = settings.cashfree_env
                if payment_expiry_seconds is None or cashfree_environment is None:
                    raise ValueError("Cashfree order policy is incompletely configured")
                recorders.append(
                    PaymentOutboxDeliveryRecorder(
                        cipher=cipher,
                        key_reference=key_reference,
                        cashfree_environment=cashfree_environment,
                        payment_expiry=timedelta(seconds=payment_expiry_seconds),
                    )
                )
            if (
                settings.demo_post_conversion_enabled
                and settings.default_locale
                and settings.onboarding_handoff_policy_reference
            ):
                recorders.append(
                    LifecycleOutboxDeliveryRecorder(
                        cipher=cipher,
                        source_agent=settings.app_name,
                        onboarding_locale=settings.default_locale,
                        onboarding_policy_reference=settings.onboarding_handoff_policy_reference,
                    )
                )
            recorder = CompositeOutboxDeliveryRecorder(tuple(recorders)) if recorders else None
            outbox_publisher = DurableOutboxPublisher(
                sessions=database.sessions,
                cipher=cipher,
                transport=outbox_transport,
                recorder=recorder,
                blocked_targets=frozenset(
                    {
                        *(
                            {"lead-intake", "lead-intake-agent"}
                            if settings.demo_outbound_paused
                            else set()
                        ),
                        *(
                            {"onboarding-agent"}
                            if not settings.demo_post_conversion_enabled
                            else set()
                        ),
                        *(
                            {"cashfree"}
                            if not (
                                settings.demo_payments_enabled and settings.cashfree_order_enabled
                            )
                            else set()
                        ),
                    }
                ),
            )
            replay_store = RedisReplayStore(redis_client)
        elif not settings.is_production:
            ingress = LocalEventIngress()
            replay_store = InMemoryReplayStore()
        else:
            raise ValueError("production cannot use local adapters")
        key_grants = {
            key_id: HmacKeyGrant(
                secret=grant.secret.get_secret_value(),
                source=grant.source,
                scopes=grant.scopes,
            )
            for key_id, grant in settings.internal_hmac_key_grants.items()
        }
        auth = HmacRequestVerifier(
            key_grants=key_grants,
            issuer=settings.internal_auth_issuer,
            audience=settings.internal_auth_audience,
            replay_window_seconds=settings.internal_replay_window_seconds or 300,
            replay_store=replay_store,
        )
        return cls(
            settings=settings,
            feature_flags=FeatureFlags.from_settings(settings),
            event_ingress=ingress,
            internal_auth=auth,
            database=database,
            redis=redis_client,
            inbox_processor=inbox_processor,
            outbox_publisher=outbox_publisher,
            outbox_transport=outbox_transport,
            payment_order_jobs=payment_order_jobs,
        )

    async def close(self) -> None:
        if self.outbox_transport is not None:
            await self.outbox_transport.close()
        if self.redis is not None:
            await self.redis.aclose()
        if self.database is not None:
            await self.database.close()

    async def dependency_health(self) -> dict[str, bool]:
        database_ok = self.database is not None and await self.database.ping()
        redis_ok = False
        if self.redis is not None:
            try:
                redis_ok = bool(await self.redis.ping())
            except Exception:
                redis_ok = False
        if self.settings.provider_profile == "local":
            database_ok = True
            redis_ok = True
        return {
            "postgresql": database_ok,
            "redis": redis_ok,
            "durable_ingress": not isinstance(self.event_ingress, UnconfiguredEventIngress),
            "durable_outbox": (
                self.outbox_publisher is not None or self.settings.provider_profile == "local"
            ),
        }
