from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.config.settings import Settings, get_settings
from demo_command_center.infrastructure.audit import append_audit_event
from demo_command_center.infrastructure.database.models import (
    AgentInboxEvent,
    AgentOutboxEvent,
    CalendarEventState,
    CommunicationMessage,
    DemoCase,
    DemoSession,
    ProviderWebhookEvent,
)
from demo_command_center.infrastructure.database.session import build_database_resources
from demo_command_center.security.encryption import PayloadCipher


@dataclass(frozen=True, slots=True)
class RetentionCleanupResult:
    inbox_deleted: int
    outbox_deleted: int
    provider_payloads_erased: int
    message_payloads_erased: int
    meeting_links_erased: int
    demo_identifiers_erased: int


async def run_retention_cleanup(
    sessions: async_sessionmaker[AsyncSession],
    *,
    tenant_id: str,
    cipher: PayloadCipher,
    key_reference: str,
    policy_reference: str,
    audit_hash_key: str,
    batch_size: int,
    now: datetime | None = None,
) -> RetentionCleanupResult:
    if not 1 <= batch_size <= 10_000:
        raise ValueError("batch size must be between 1 and 10000")
    effective_now = now or datetime.now(UTC)
    if effective_now.tzinfo is None:
        raise ValueError("retention timestamp must be timezone-aware")
    async with sessions() as session, session.begin():
        inbox_ids = list(
            (
                await session.scalars(
                    select(AgentInboxEvent.id)
                    .where(
                        AgentInboxEvent.tenant_id == tenant_id,
                        AgentInboxEvent.processed_at.is_not(None),
                        AgentInboxEvent.retain_until <= effective_now,
                        AgentInboxEvent.legal_hold.is_(False),
                    )
                    .order_by(AgentInboxEvent.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if inbox_ids:
            await session.execute(delete(AgentInboxEvent).where(AgentInboxEvent.id.in_(inbox_ids)))

        outbox_ids = list(
            (
                await session.scalars(
                    select(AgentOutboxEvent.id)
                    .where(
                        AgentOutboxEvent.tenant_id == tenant_id,
                        AgentOutboxEvent.published_at.is_not(None),
                        AgentOutboxEvent.retain_until <= effective_now,
                        AgentOutboxEvent.legal_hold.is_(False),
                    )
                    .order_by(AgentOutboxEvent.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if outbox_ids:
            await session.execute(
                delete(AgentOutboxEvent).where(AgentOutboxEvent.id.in_(outbox_ids))
            )

        provider_rows = list(
            (
                await session.scalars(
                    select(ProviderWebhookEvent)
                    .where(
                        ProviderWebhookEvent.tenant_id == tenant_id,
                        ProviderWebhookEvent.retain_until <= effective_now,
                        ProviderWebhookEvent.legal_hold.is_(False),
                    )
                    .order_by(ProviderWebhookEvent.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for provider_row in provider_rows:
            provider_row.payload_ciphertext = cipher.encrypt(
                b"{}",
                associated_data=(
                    f"{provider_row.provider}:{provider_row.provider_event_id}"
                ).encode(),
            )
            provider_row.payload_key_reference = key_reference
            provider_row.retain_until = None

        message_rows = list(
            (
                await session.scalars(
                    select(CommunicationMessage)
                    .where(
                        CommunicationMessage.tenant_id == tenant_id,
                        CommunicationMessage.retain_until <= effective_now,
                        CommunicationMessage.legal_hold.is_(False),
                        CommunicationMessage.content_ciphertext.is_not(None),
                    )
                    .order_by(CommunicationMessage.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for message_row in message_rows:
            message_row.content_ciphertext = None
            message_row.content_key_reference = None
            message_row.content_source_refs = []
            message_row.retain_until = None

        calendar_rows = list(
            (
                await session.scalars(
                    select(CalendarEventState)
                    .join(DemoSession, DemoSession.id == CalendarEventState.session_id)
                    .join(DemoCase, DemoCase.id == DemoSession.demo_case_id)
                    .where(
                        DemoCase.tenant_id == tenant_id,
                        CalendarEventState.meeting_uri_expires_at <= effective_now,
                        CalendarEventState.legal_hold.is_(False),
                        CalendarEventState.meeting_uri_ciphertext.is_not(None),
                    )
                    .order_by(CalendarEventState.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for calendar_row in calendar_rows:
            calendar_row.meeting_uri_ciphertext = None
            calendar_row.meeting_uri_key_reference = None
            calendar_row.meeting_uri_expires_at = None

        demo_rows = list(
            (
                await session.scalars(
                    select(DemoCase)
                    .where(
                        DemoCase.tenant_id == tenant_id,
                        DemoCase.retain_until <= effective_now,
                        DemoCase.legal_hold.is_(False),
                    )
                    .order_by(DemoCase.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for demo_row in demo_rows:
            demo_row.external_lead_id = None
            demo_row.external_user_id = None
            demo_row.conversation_id = f"retained:{demo_row.id}"
            demo_row.retain_until = None

        result = RetentionCleanupResult(
            inbox_deleted=len(inbox_ids),
            outbox_deleted=len(outbox_ids),
            provider_payloads_erased=len(provider_rows),
            message_payloads_erased=len(message_rows),
            meeting_links_erased=len(calendar_rows),
            demo_identifiers_erased=len(demo_rows),
        )
        await append_audit_event(
            session,
            tenant_id=tenant_id,
            event_type="privacy.retention.cleanup.completed.v1",
            actor_type="scheduled_task",
            actor_ref="retention-cleanup",
            correlation_id=str(uuid4()),
            details={**asdict(result), "policy_reference": policy_reference},
            hash_key=audit_hash_key,
            occurred_at=effective_now,
        )
        return result


def _validate_settings(settings: Settings) -> tuple[str, str, str, str]:
    if settings.provider_profile != "real" or not settings.retention_cleanup_enabled:
        raise RuntimeError("retention cleanup is disabled or not using durable persistence")
    tenant_id = settings.tenant_id
    policy = settings.retention_policy_reference
    key_reference = settings.field_encryption_key_reference
    encryption_key = settings.field_encryption_key.get_secret_value()
    audit_key = settings.audit_hash_key.get_secret_value()
    if (
        tenant_id is None
        or policy is None
        or key_reference is None
        or not encryption_key
        or not audit_key
    ):
        raise RuntimeError(
            "retention cleanup policy, tenant, encryption, and audit keys are required"
        )
    return tenant_id, policy, key_reference, encryption_key


async def _run(settings: Settings, batch_size: int) -> RetentionCleanupResult:
    tenant_id, policy, key_reference, encryption_key = _validate_settings(settings)
    database = build_database_resources(settings)
    try:
        return await run_retention_cleanup(
            database.sessions,
            tenant_id=tenant_id,
            cipher=PayloadCipher.from_encoded_key(encryption_key),
            key_reference=key_reference,
            policy_reference=policy,
            audit_hash_key=settings.audit_hash_key.get_secret_value(),
            batch_size=batch_size,
        )
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply approved restricted-data retention")
    parser.add_argument("--batch-size", type=int, default=500)
    arguments = parser.parse_args()
    result = asyncio.run(_run(get_settings(), arguments.batch_size))
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
