from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.infrastructure.database.models import AgentOutboxEvent
from demo_command_center.security.encryption import PayloadCipher


class OutboxTransport(Protocol):
    async def publish(
        self,
        *,
        target: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        correlation_id: str,
    ) -> str | OutboxDeliveryResult: ...


@dataclass(frozen=True, slots=True)
class OutboxDeliveryResult:
    """A safe audit reference plus restricted in-transaction acknowledgement details."""

    provider_reference: str
    restricted_details: Mapping[str, Any]


class OutboxDeliveryRecorder(Protocol):
    async def record(
        self,
        *,
        row: AgentOutboxEvent,
        payload: Mapping[str, Any],
        provider_reference: str,
        restricted_details: Mapping[str, Any],
        session: AsyncSession,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class OutboxBatchResult:
    published: int
    failed: int


@dataclass(frozen=True, slots=True)
class DurableOutboxPublisher:
    sessions: async_sessionmaker[AsyncSession]
    cipher: PayloadCipher
    transport: OutboxTransport
    recorder: OutboxDeliveryRecorder | None = None
    blocked_targets: frozenset[str] = frozenset()
    maximum_attempts: int = 8

    @staticmethod
    def _associated_data(row: AgentOutboxEvent) -> bytes:
        return f"{row.tenant_id}:{row.target_agent}:{row.event_id}".encode()

    async def publish_batch(self, *, batch_size: int = 10) -> OutboxBatchResult:
        now = datetime.now(UTC)
        published = 0
        failed = 0
        async with self.sessions() as session:
            statement = select(AgentOutboxEvent).where(
                AgentOutboxEvent.published_at.is_(None),
                AgentOutboxEvent.available_at <= now,
                AgentOutboxEvent.attempts < self.maximum_attempts,
            )
            if self.blocked_targets:
                statement = statement.where(
                    AgentOutboxEvent.target_agent.not_in(self.blocked_targets)
                )
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(AgentOutboxEvent.available_at)
                        .limit(batch_size)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            for row in rows:
                try:
                    plaintext = self.cipher.decrypt(
                        row.payload_ciphertext,
                        associated_data=self._associated_data(row),
                    )
                    payload = json.loads(plaintext)
                    if not isinstance(payload, dict):
                        raise ValueError("outbox payload is not an object")
                    delivery = await self.transport.publish(
                        target=row.target_agent,
                        payload=payload,
                        idempotency_key=row.idempotency_key,
                        correlation_id=row.correlation_id,
                    )
                    if isinstance(delivery, OutboxDeliveryResult):
                        provider_reference = delivery.provider_reference
                        restricted_details = delivery.restricted_details
                    else:
                        provider_reference = delivery
                        restricted_details = {}
                    if self.recorder is not None:
                        await self.recorder.record(
                            row=row,
                            payload=payload,
                            provider_reference=provider_reference,
                            restricted_details=restricted_details,
                            session=session,
                        )
                    row.published_at = now
                    row.provider_reference = provider_reference[:255]
                    row.last_error_code = None
                    published += 1
                except Exception:  # safe error classification is persisted, provider text is not
                    row.attempts += 1
                    row.last_error_code = "DCC_OUTBOX_DELIVERY_FAILED"
                    row.available_at = now + timedelta(seconds=min(300, 2**row.attempts))
                    failed += 1
            await session.commit()
        return OutboxBatchResult(published=published, failed=failed)
