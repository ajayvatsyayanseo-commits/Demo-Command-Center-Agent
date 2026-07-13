from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from demo_command_center.infrastructure.database.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DemoCase(TimestampMixin, Base):
    __tablename__ = "demo_cases"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_demo_cases_tenant_region_state", "tenant_id", "region_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    region_id: Mapped[str | None] = mapped_column(String(100))
    external_lead_id: Mapped[str | None] = mapped_column(String(255))
    external_user_id: Mapped[str | None] = mapped_column(String(255))
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    participant_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    flow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DemoStateTransition(Base):
    __tablename__ = "demo_state_transitions"
    __table_args__ = (
        UniqueConstraint("demo_case_id", "idempotency_key"),
        Index("ix_demo_transitions_demo_occurred", "demo_case_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    state_before: Mapped[str] = mapped_column(String(64), nullable=False)
    state_after: Mapped[str] = mapped_column(String(64), nullable=False)
    command: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    flow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(64))
    side_effects_requested: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    side_effects_completed: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    compensation_state: Mapped[str | None] = mapped_column(String(64))


class AgentInboxEvent(Base):
    __tablename__ = "agent_inbox_events"
    __table_args__ = (
        UniqueConstraint("source_agent", "event_id", "schema_version"),
        UniqueConstraint("tenant_id", "idempotency_key"),
        Index(
            "ix_agent_inbox_unprocessed",
            "received_at",
            postgresql_where=text("processed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    source_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_key_reference: Mapped[str | None] = mapped_column(String(255))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))


class AgentOutboxEvent(Base):
    __tablename__ = "agent_outbox_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        Index(
            "ix_agent_outbox_pending", "available_at", postgresql_where=text("published_at IS NULL")
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    target_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("tenant_id", "scope", "idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_reference: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HumanHandoffTicket(TimestampMixin, Base):
    __tablename__ = "human_handoff_tickets"
    __table_args__ = (
        Index(
            "uq_handoff_open_reason",
            "demo_case_id",
            "reason_code",
            unique=True,
            postgresql_where=text("status IN ('open', 'assigned')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    region_id: Mapped[str | None] = mapped_column(String(100))
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    redacted_summary: Mapped[str] = mapped_column(Text, nullable=False)
    next_action: Mapped[str] = mapped_column(Text, nullable=False)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_tenant_occurred", "tenant_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    region_id: Mapped[str | None] = mapped_column(String(100))
    demo_case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    export_sanitized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
