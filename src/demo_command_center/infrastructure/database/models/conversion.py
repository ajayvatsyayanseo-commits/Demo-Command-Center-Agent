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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from demo_command_center.infrastructure.database.base import Base
from demo_command_center.infrastructure.database.models.operational import TimestampMixin


class DiscountPolicy(TimestampMixin, Base):
    __tablename__ = "discount_policies"
    __table_args__ = (UniqueConstraint("tenant_id", "policy_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    maximum_active_offers: Mapped[int] = mapped_column(Integer, nullable=False)
    approval_thresholds: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DiscountDecision(TimestampMixin, Base):
    __tablename__ = "discount_decisions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint("selected_price_minor >= minimum_price_minor", name="discount_above_minimum"),
        CheckConstraint("selected_price_minor <= list_price_minor", name="discount_below_list"),
        Index(
            "ix_discount_active_binding",
            "tenant_id",
            "user_ref",
            "plan_ref",
            postgresql_where=text("status IN ('approved', 'offered')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discount_policies.id"), nullable=False)
    user_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    list_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_discount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_min_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_max_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    conditions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reusable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_level: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    override_reason: Mapped[str | None] = mapped_column(Text)


class PaymentOrder(TimestampMixin, Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "domain_order_id"),
        UniqueConstraint("provider", "provider_order_id"),
        UniqueConstraint("tenant_id", "creation_idempotency_key"),
        CheckConstraint("amount_minor > 0", name="payment_order_positive_amount"),
        Index("ix_payment_orders_reconcile", "status", "reconcile_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    demo_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("demo_cases.id", ondelete="RESTRICT"), nullable=False
    )
    domain_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(255))
    user_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("discount_decisions.id"))
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_environment: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    creation_idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reconcile_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PaymentLink(TimestampMixin, Base):
    __tablename__ = "payment_links"
    __table_args__ = (
        UniqueConstraint("payment_order_id"),
        UniqueConstraint("provider", "provider_link_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    payment_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_orders.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_link_id: Mapped[str] = mapped_column(String(255), nullable=False)
    checkout_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaymentAttempt(TimestampMixin, Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_payment_id"),
        UniqueConstraint("provider_webhook_event_id"),
        Index("ix_payment_attempts_order_status", "payment_order_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    payment_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_orders.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_webhook_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("provider_webhook_events.id")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    safe_method_category: Mapped[str | None] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaymentReconciliation(TimestampMixin, Base):
    __tablename__ = "payment_reconciliations"
    __table_args__ = (UniqueConstraint("payment_order_id", "provider_snapshot_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    payment_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_orders.id", ondelete="CASCADE"), nullable=False
    )
    provider_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    local_status_before: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_provider_status: Mapped[str] = mapped_column(String(32), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    mismatch_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaidTransition(TimestampMixin, Base):
    __tablename__ = "paid_transitions"
    __table_args__ = (
        UniqueConstraint("payment_order_id"),
        UniqueConstraint("provider_payment_id"),
        UniqueConstraint("website_activation_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    payment_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_orders.id", ondelete="RESTRICT"), nullable=False
    )
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    website_activation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    verified_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    verification_source: Mapped[str] = mapped_column(String(64), nullable=False)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OnboardingHandoff(TimestampMixin, Base):
    __tablename__ = "onboarding_handoffs"
    __table_args__ = (
        UniqueConstraint("paid_transition_id"),
        UniqueConstraint("tenant_id", "idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    paid_transition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paid_transitions.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    onboarding_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    acknowledgement_ref: Mapped[str | None] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    welcome_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communication_messages.id")
    )


class RuntimeFeatureFlag(TimestampMixin, Base):
    __tablename__ = "runtime_feature_flags"
    __table_args__ = (UniqueConstraint("tenant_id", "flag_name", "scope_type", "scope_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    flag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(100), nullable=False, default="global")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegionalAggregate(Base):
    __tablename__ = "regional_aggregates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "region_id", "metric_name", "window_start", "window_end"),
        Index("ix_regional_aggregate_query", "tenant_id", "region_id", "metric_name", "window_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    region_id: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cohort_version: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    numerator: Mapped[int | None] = mapped_column(Integer)
    denominator: Mapped[int | None] = mapped_column(Integer)
    value: Mapped[float | None] = mapped_column(Numeric(14, 6))
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    dimensions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RegionalAlert(TimestampMixin, Base):
    __tablename__ = "regional_alerts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "deduplication_key"),
        Index("ix_regional_alerts_open", "tenant_id", "region_id", postgresql_where=text("status = 'open'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    region_id: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False)
    observed: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5))
    practical_significance: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    safe_summary: Mapped[str] = mapped_column(Text, nullable=False)
    suppression_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
