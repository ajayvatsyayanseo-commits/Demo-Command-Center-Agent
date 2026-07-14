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


class ReminderPolicy(TimestampMixin, Base):
    __tablename__ = "reminder_policies"
    __table_args__ = (UniqueConstraint("tenant_id", "policy_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    quiet_hours: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReminderJob(TimestampMixin, Base):
    __tablename__ = "reminder_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        Index("ix_reminder_jobs_due", "due_at", postgresql_where=text("status = 'pending'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("demo_sessions.id"))
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reminder_policies.id"), nullable=False)
    reminder_type: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_preference: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CommunicationMessage(TimestampMixin, Base):
    __tablename__ = "communication_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        Index("ix_communication_recipient_created", "recipient_ref", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    demo_case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("demo_cases.id"))
    reminder_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reminder_jobs.id"))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    message_category: Mapped[str] = mapped_column(String(32), nullable=False)
    template_ref: Mapped[str | None] = mapped_column(String(255))
    content_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_key_reference: Mapped[str | None] = mapped_column(String(255))
    content_source_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    message_version: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    service_window_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legal_hold: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class CommunicationDelivery(Base):
    __tablename__ = "communication_deliveries"
    __table_args__ = (
        UniqueConstraint("provider", "provider_message_id", "status", "occurred_at"),
        Index("ix_delivery_message_occurred", "message_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("communication_messages.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(100))


class ProviderRequest(TimestampMixin, Base):
    __tablename__ = "provider_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "idempotency_key"),
        Index("ix_provider_requests_reconcile", "provider", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    safe_error_code: Mapped[str | None] = mapped_column(String(100))
    reconcile_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderWebhookEvent(Base):
    __tablename__ = "provider_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_event_id", name="uq_provider_webhook_provider_event"
        ),
        UniqueConstraint("provider", "payload_hash", name="uq_provider_webhook_payload_hash"),
        Index(
            "ix_provider_webhook_unprocessed",
            "received_at",
            postgresql_where=text("processed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_key_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_key_id: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    safe_error_code: Mapped[str | None] = mapped_column(String(100))
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legal_hold: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class DemoOutcome(TimestampMixin, Base):
    __tablename__ = "demo_outcomes"
    __table_args__ = (UniqueConstraint("demo_case_id", "outcome_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    determined_by: Mapped[str] = mapped_column(String(32), nullable=False)
    disputed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DemoFeedback(TimestampMixin, Base):
    __tablename__ = "demo_feedback"
    __table_args__ = (UniqueConstraint("demo_case_id", "source_type", "source_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    permitted_text_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    text_key_reference: Mapped[str | None] = mapped_column(String(255))
    consent_ref: Mapped[str | None] = mapped_column(String(255))


class QualityAssessment(TimestampMixin, Base):
    __tablename__ = "quality_assessments"
    __table_args__ = (UniqueConstraint("demo_case_id", "rubric_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    component_scores: Mapped[dict[str, float | None]] = mapped_column(JSON, nullable=False)
    missing_components: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    final_score: Mapped[float | None] = mapped_column(Numeric(7, 4))
    human_override_score: Mapped[float | None] = mapped_column(Numeric(7, 4))
    override_reason: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ObjectionRecord(TimestampMixin, Base):
    __tablename__ = "objections"
    __table_args__ = (
        UniqueConstraint("demo_case_id", "objection_id"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="objection_confidence_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    objection_id: Mapped[str] = mapped_column(String(100), nullable=False)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    taxonomy_category: Mapped[str] = mapped_column(String(100), nullable=False)
    explicit_or_implicit: Mapped[str] = mapped_column(String(16), nullable=False)
    normalized_objection: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    alternative_interpretation: Mapped[str | None] = mapped_column(Text)
    recommended_next_question: Mapped[str | None] = mapped_column(Text)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(64))


class ModelVersion(TimestampMixin, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_name", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_registry_version: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_uri: Mapped[str | None] = mapped_column(String(1024))
    artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    promotion_status: Mapped[str] = mapped_column(String(32), nullable=False)
    trained_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "evaluation_type",
            "subject_version",
            "policy_reference",
            "window_end",
            name="uq_model_evaluation_window",
        ),
        Index("ix_model_evaluations_status_time", "tenant_id", "status", "evaluated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    threshold_breaches: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConversionPrediction(TimestampMixin, Base):
    __tablename__ = "conversion_predictions"
    __table_args__ = (
        UniqueConstraint("demo_case_id", "model_version_id", "feature_timestamp"),
        CheckConstraint(
            "probability >= 0 AND probability <= 1", name="prediction_probability_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_versions.id"))
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prediction_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    probability: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fallback_status: Mapped[str | None] = mapped_column(String(64))
    missing_features: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class ConversionStrategy(TimestampMixin, Base):
    __tablename__ = "conversion_strategies"
    __table_args__ = (UniqueConstraint("demo_case_id", "strategy_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    next_action: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(32))
    execute_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_offer_ref: Mapped[str | None] = mapped_column(String(255))
