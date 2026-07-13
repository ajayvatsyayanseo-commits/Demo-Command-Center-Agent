from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from demo_command_center.infrastructure.database.base import Base
from demo_command_center.infrastructure.database.models.operational import TimestampMixin


class DemoRequirement(TimestampMixin, Base):
    __tablename__ = "demo_requirements"
    __table_args__ = (UniqueConstraint("demo_case_id", name="uq_demo_requirement_case"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    board: Mapped[str | None] = mapped_column(String(100))
    class_level: Mapped[str | None] = mapped_column(String(100))
    subject: Mapped[str | None] = mapped_column(String(160))
    learning_goal: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(String(32))
    location_region: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str | None] = mapped_column(String(64))
    budget_min_minor: Mapped[int | None] = mapped_column(Integer)
    budget_max_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    preferred_times: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class DemoParticipant(TimestampMixin, Base):
    __tablename__ = "demo_participants"
    __table_args__ = (
        UniqueConstraint("demo_case_id", "participant_type", "external_ref"),
        Index("ix_demo_participants_case_type", "demo_case_id", "participant_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    participant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    contact_key_reference: Mapped[str | None] = mapped_column(String(255))
    is_minor: Mapped[bool | None] = mapped_column(Boolean)
    communication_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ExternalIdentityMapping(TimestampMixin, Base):
    __tablename__ = "external_identity_mappings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "system", "entity_type", "external_id"),
        Index("ix_identity_internal", "tenant_id", "entity_type", "internal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    system: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    external_version: Mapped[str | None] = mapped_column(String(100))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationState(TimestampMixin, Base):
    __tablename__ = "conversation_states"
    __table_args__ = (UniqueConstraint("tenant_id", "conversation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    demo_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    current_step: Mapped[str] = mapped_column(String(100), nullable=False)
    safe_summary: Mapped[str | None] = mapped_column(Text)
    restricted_context_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    context_key_reference: Mapped[str | None] = mapped_column(String(255))
    flow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TutorCandidate(TimestampMixin, Base):
    __tablename__ = "tutor_candidates"
    __table_args__ = (
        UniqueConstraint("demo_case_id", "website_tutor_ref", "ranking_version"),
        Index("ix_tutor_candidates_case_rank", "demo_case_id", "rank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    website_tutor_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    ranking_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    hard_constraints_met: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_version: Mapped[str | None] = mapped_column(String(100))
    source_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AvailabilitySnapshot(TimestampMixin, Base):
    __tablename__ = "availability_snapshots"
    __table_args__ = (Index("ix_availability_tutor_window", "tutor_ref", "starts_at", "ends_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    tutor_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(100))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    available_windows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SlotProposal(TimestampMixin, Base):
    __tablename__ = "slot_proposals"
    __table_args__ = (
        UniqueConstraint("demo_case_id", "option_id"),
        CheckConstraint("ends_at > starts_at", name="proposal_positive_duration"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    tutor_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    option_id: Mapped[str] = mapped_column(String(100), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    display_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("availability_snapshots.id"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SlotHold(TimestampMixin, Base):
    __tablename__ = "slot_holds"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="hold_positive_duration"),
        Index(
            "uq_slot_hold_active_tutor_start",
            "tenant_id",
            "tutor_ref",
            "starts_at",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_slot_holds_expiry", "expires_at", postgresql_where=text("status = 'active'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slot_proposals.id"), nullable=False)
    tutor_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DemoConfirmation(TimestampMixin, Base):
    __tablename__ = "demo_confirmations"
    __table_args__ = (UniqueConstraint("slot_hold_id", "participant_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slot_hold_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("slot_holds.id", ondelete="CASCADE"), nullable=False
    )
    participant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    participant_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_ref: Mapped[str | None] = mapped_column(String(255))
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DemoSession(TimestampMixin, Base):
    __tablename__ = "demo_sessions"
    __table_args__ = (
        UniqueConstraint("demo_case_id"),
        CheckConstraint("ends_at > starts_at", name="session_positive_duration"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    slot_hold_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slot_holds.id"), nullable=False)
    tutor_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class CalendarEventState(TimestampMixin, Base):
    __tablename__ = "calendar_event_states"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id"),
        UniqueConstraint("conference_request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_sessions.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    organizer_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(255))
    provider_etag: Mapped[str | None] = mapped_column(String(255))
    conference_request_id: Mapped[str] = mapped_column(String(255), nullable=False)
    conference_status: Mapped[str] = mapped_column(String(32), nullable=False)
    meeting_uri_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    meeting_uri_key_reference: Mapped[str | None] = mapped_column(String(255))
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentRecord(TimestampMixin, Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "subject_ref", "purpose", "evidence_ref"),
        Index("ix_consent_subject_purpose", "tenant_id", "subject_ref", "purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    guardian_ref: Mapped[str | None] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommunicationOptOut(TimestampMixin, Base):
    __tablename__ = "communication_opt_outs"
    __table_args__ = (UniqueConstraint("tenant_id", "recipient_ref", "channel"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(100))
    source_event_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    opted_out_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
