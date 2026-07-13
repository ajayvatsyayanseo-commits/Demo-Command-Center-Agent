from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.api.schemas.ingress import IngressReceipt, IngressStatus
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.database.models import AgentInboxEvent
from demo_command_center.security.encryption import PayloadCipher


@dataclass(frozen=True, slots=True)
class DatabaseEventIngress:
    sessions: async_sessionmaker[AsyncSession]
    cipher: PayloadCipher
    key_reference: str

    @staticmethod
    def _associated_data(event: AgentEventEnvelope) -> bytes:
        return f"{event.tenant_id}:{event.source_agent}:{event.event_id}".encode()

    async def accept(self, event: AgentEventEnvelope) -> IngressReceipt:
        serialized = json.dumps(
            event.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        ciphertext = self.cipher.encrypt(
            serialized,
            associated_data=self._associated_data(event),
        )
        row = AgentInboxEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            source_agent=event.source_agent,
            tenant_id=event.tenant_id,
            idempotency_key=event.idempotency_key,
            correlation_id=event.correlation_id,
            payload_ciphertext=ciphertext,
            payload_key_reference=self.key_reference,
            processing_attempts=0,
        )
        async with self.sessions() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                duplicate = await session.scalar(
                    select(AgentInboxEvent.id).where(
                        or_(
                            (
                                AgentInboxEvent.source_agent == event.source_agent
                            )
                            & (AgentInboxEvent.event_id == event.event_id)
                            & (AgentInboxEvent.schema_version == event.schema_version),
                            (AgentInboxEvent.tenant_id == event.tenant_id)
                            & (AgentInboxEvent.idempotency_key == event.idempotency_key),
                        )
                    )
                )
                if duplicate is None:
                    raise
                return IngressReceipt(
                    event_id=event.event_id,
                    status="duplicate",
                    correlation_id=event.correlation_id,
                )
        return IngressReceipt(
            event_id=event.event_id,
            status="accepted",
            correlation_id=event.correlation_id,
        )

    async def status(self, event_id: UUID) -> IngressStatus | None:
        async with self.sessions() as session:
            row = (
                await session.execute(
                    select(
                        AgentInboxEvent.event_id,
                        AgentInboxEvent.received_at,
                        AgentInboxEvent.processed_at,
                        AgentInboxEvent.processing_attempts,
                        AgentInboxEvent.error_code,
                    ).where(AgentInboxEvent.event_id == event_id)
                )
            ).one_or_none()
        if row is None:
            return None
        state = "failed" if row.error_code else "processed" if row.processed_at else "pending"
        return IngressStatus(
            event_id=row.event_id,
            status=state,
            received_at=row.received_at,
            processed_at=row.processed_at,
            processing_attempts=row.processing_attempts,
            error_code=row.error_code,
        )
