from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from demo_command_center.infrastructure.database.models import AuditEvent


async def append_audit_event(
    session: AsyncSession,
    *,
    tenant_id: str,
    event_type: str,
    actor_type: str,
    actor_ref: str,
    correlation_id: str,
    details: Mapping[str, Any],
    hash_key: str,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    """Append a PII-minimized, keyed tamper-evident audit record."""
    if not hash_key or not tenant_id or not actor_ref:
        raise ValueError("audit tenant, actor, and hash key are required")
    timestamp = occurred_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("audit timestamp must be timezone-aware")
    previous_hash = await session.scalar(
        select(AuditEvent.event_hash)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(1)
        .with_for_update()
    )
    safe_details = dict(details)
    canonical = json.dumps(
        {
            "tenant_id": tenant_id,
            "event_type": event_type,
            "actor_type": actor_type,
            "correlation_id": correlation_id,
            "details": safe_details,
            "occurred_at": timestamp.isoformat(),
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    key = hash_key.encode()
    event = AuditEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_ref_hash=hmac.new(key, actor_ref.encode(), hashlib.sha256).hexdigest(),
        correlation_id=correlation_id,
        details=safe_details,
        occurred_at=timestamp,
        previous_hash=previous_hash,
        event_hash=hmac.new(key, canonical, hashlib.sha256).hexdigest(),
        export_sanitized=True,
    )
    session.add(event)
    return event
