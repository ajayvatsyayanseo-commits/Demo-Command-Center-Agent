"""Complete demo lifecycle persistence.

Revision ID: 20260713_000002
Revises: 20260713_000001

The explicit table allow-list prevents this migration from taking ownership of
website data or of any future model added to the metadata registry.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from demo_command_center.infrastructure.database import models  # noqa: F401
from demo_command_center.infrastructure.database.base import Base

revision: str = "20260713_000002"
down_revision: str | None = "20260713_000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAMES = (
    "demo_requirements",
    "demo_participants",
    "external_identity_mappings",
    "conversation_states",
    "tutor_candidates",
    "availability_snapshots",
    "slot_proposals",
    "slot_holds",
    "demo_confirmations",
    "demo_sessions",
    "calendar_event_states",
    "consent_records",
    "communication_opt_outs",
    "reminder_policies",
    "reminder_jobs",
    "communication_messages",
    "communication_deliveries",
    "provider_requests",
    "provider_webhook_events",
    "demo_outcomes",
    "demo_feedback",
    "quality_assessments",
    "objections",
    "model_versions",
    "model_evaluations",
    "conversion_predictions",
    "conversion_strategies",
    "discount_policies",
    "discount_decisions",
    "payment_orders",
    "payment_links",
    "payment_attempts",
    "payment_reconciliations",
    "paid_transitions",
    "onboarding_handoffs",
    "runtime_feature_flags",
    "regional_aggregates",
    "regional_alerts",
)


def upgrade() -> None:
    for table_name in ("demo_cases", "agent_inbox_events", "agent_outbox_events", "audit_events"):
        op.add_column(table_name, sa.Column("retain_until", sa.DateTime(timezone=True)))
        op.add_column(
            table_name,
            sa.Column("legal_hold", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    op.add_column(
        "agent_outbox_events",
        sa.Column("provider_reference", sa.String(length=255)),
    )
    tables = [Base.metadata.tables[name] for name in TABLE_NAMES]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables, checkfirst=False)


def downgrade() -> None:
    for table_name in reversed(TABLE_NAMES):
        op.drop_table(table_name)
    for table_name in ("audit_events", "agent_outbox_events", "agent_inbox_events", "demo_cases"):
        op.drop_column(table_name, "legal_hold")
        op.drop_column(table_name, "retain_until")
    op.drop_column("agent_outbox_events", "provider_reference")
