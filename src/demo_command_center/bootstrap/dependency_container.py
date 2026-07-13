from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass, field
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
from demo_command_center.infrastructure.inbox import DatabaseEventIngress
from demo_command_center.security.authentication import (
    HmacRequestVerifier,
    InMemoryReplayStore,
    RedisReplayStore,
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

    @classmethod
    def build(cls, settings: Settings) -> DependencyContainer:
        ingress: EventIngress = UnconfiguredEventIngress()
        database: DatabaseResources | None = None
        redis_client: Redis | None = None
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
            ingress = DatabaseEventIngress(
                sessions=database.sessions,
                cipher=PayloadCipher.from_encoded_key(key),
                key_reference=key_reference,
            )
            replay_store = RedisReplayStore(redis_client)
        elif not settings.is_production:
            ingress = LocalEventIngress()
            replay_store = InMemoryReplayStore()
        else:
            raise ValueError("production cannot use local adapters")
        keys: dict[str, str] = {}
        if settings.internal_signing_key_id:
            keys[settings.internal_signing_key_id] = (
                settings.internal_signing_secret.get_secret_value()
            )
        if settings.internal_previous_signing_key_id:
            keys[settings.internal_previous_signing_key_id] = (
                settings.internal_previous_signing_secret.get_secret_value()
            )
        auth = HmacRequestVerifier(
            keys=keys,
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
        )

    async def close(self) -> None:
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
        }
