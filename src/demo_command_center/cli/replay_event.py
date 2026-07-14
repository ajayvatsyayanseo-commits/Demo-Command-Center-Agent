from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.config.settings import Settings, get_settings
from demo_command_center.infrastructure.audit import append_audit_event
from demo_command_center.infrastructure.database.models import AgentInboxEvent
from demo_command_center.infrastructure.database.session import build_database_resources

_REASON_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_:-]{2,99}$")


@dataclass(frozen=True, slots=True)
class ReplayResult:
    event_id: str
    source_agent: str
    schema_version: str
    previous_attempts: int
    previous_status: str
    status: str


async def replay_inbox_event(
    sessions: async_sessionmaker[AsyncSession],
    *,
    event_id: UUID,
    source_agent: str,
    schema_version: str,
    reason_code: str,
    operator_ref: str,
    confirmation: str,
    tenant_id: str,
    audit_hash_key: str,
    include_processed: bool = False,
) -> ReplayResult:
    if confirmation != f"REPLAY:{event_id}":
        raise ValueError("confirmation must exactly match REPLAY:<event-id>")
    if not _REASON_CODE.fullmatch(reason_code):
        raise ValueError("reason code must be a controlled uppercase code")
    if not source_agent or not schema_version or not operator_ref:
        raise ValueError("source, schema, and operator reference are required")
    async with sessions() as session, session.begin():
        row = await session.scalar(
            select(AgentInboxEvent)
            .where(
                AgentInboxEvent.tenant_id == tenant_id,
                AgentInboxEvent.event_id == event_id,
                AgentInboxEvent.source_agent == source_agent,
                AgentInboxEvent.schema_version == schema_version,
            )
            .with_for_update()
        )
        if row is None:
            raise LookupError("inbox event was not found in the configured tenant")
        previous_status = (
            "processed"
            if row.processed_at is not None
            else "failed"
            if row.error_code is not None
            else "pending"
        )
        if previous_status == "pending":
            raise ValueError("pending events cannot be manually replayed")
        if previous_status == "processed" and not include_processed:
            raise ValueError("processed replay requires --include-processed")
        previous_attempts = row.processing_attempts
        row.processed_at = None
        row.processing_attempts = 0
        row.error_code = None
        correlation_id = str(uuid4())
        await append_audit_event(
            session,
            tenant_id=tenant_id,
            event_type="operations.inbox.replay.authorized.v1",
            actor_type="operator",
            actor_ref=operator_ref,
            correlation_id=correlation_id,
            details={
                "event_id": str(event_id),
                "source_agent": source_agent,
                "schema_version": schema_version,
                "previous_status": previous_status,
                "previous_attempts": previous_attempts,
                "reason_code": reason_code,
            },
            hash_key=audit_hash_key,
        )
        return ReplayResult(
            event_id=str(event_id),
            source_agent=source_agent,
            schema_version=schema_version,
            previous_attempts=previous_attempts,
            previous_status=previous_status,
            status="queued",
        )


async def _run(settings: Settings, arguments: argparse.Namespace) -> ReplayResult:
    tenant_id = settings.tenant_id
    audit_hash_key = settings.audit_hash_key.get_secret_value()
    if settings.provider_profile != "real" or not tenant_id or not audit_hash_key:
        raise RuntimeError("durable persistence, tenant, and audit hash key are required")
    database = build_database_resources(settings)
    try:
        return await replay_inbox_event(
            database.sessions,
            event_id=UUID(arguments.event_id),
            source_agent=arguments.source_agent,
            schema_version=arguments.schema_version,
            reason_code=arguments.reason_code,
            operator_ref=arguments.operator_ref,
            confirmation=arguments.confirm,
            tenant_id=tenant_id,
            audit_hash_key=audit_hash_key,
            include_processed=arguments.include_processed,
        )
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize one durable inbox replay")
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--source-agent", required=True)
    parser.add_argument("--schema-version", required=True)
    parser.add_argument("--reason-code", required=True)
    parser.add_argument("--operator-ref", required=True)
    parser.add_argument("--confirm", required=True, help="Exact value REPLAY:<event-id>")
    parser.add_argument("--include-processed", action="store_true")
    result = asyncio.run(_run(get_settings(), parser.parse_args()))
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
