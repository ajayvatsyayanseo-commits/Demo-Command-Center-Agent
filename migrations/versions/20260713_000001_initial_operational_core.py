"""Initial operational core.

Revision ID: 20260713_000001
Revises: None
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260713_000001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("region_id", sa.String(100)),
        sa.Column("external_lead_id", sa.String(255)),
        sa.Column("external_user_id", sa.String(255)),
        sa.Column("conversation_id", sa.String(255), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("participant_timezone", sa.String(64), nullable=False),
        sa.Column("flow_version", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_demo_cases"),
    )
    op.create_index("ix_demo_cases_tenant_region_state", "demo_cases", ["tenant_id", "region_id", "state"])

    op.create_table(
        "demo_state_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("demo_case_id", sa.Uuid(), nullable=False),
        sa.Column("state_before", sa.String(64), nullable=False),
        sa.Column("state_after", sa.String(64), nullable=False),
        sa.Column("command", sa.String(100), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_ref", sa.String(255), nullable=False),
        sa.Column("reason_code", sa.String(100)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("flow_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64)),
        sa.Column("model_version", sa.String(64)),
        sa.Column("side_effects_requested", sa.JSON(), nullable=False),
        sa.Column("side_effects_completed", sa.JSON(), nullable=False),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("compensation_state", sa.String(64)),
        sa.ForeignKeyConstraint(["demo_case_id"], ["demo_cases.id"], ondelete="CASCADE", name="fk_demo_state_transitions_demo_case_id_demo_cases"),
        sa.PrimaryKeyConstraint("id", name="pk_demo_state_transitions"),
        sa.UniqueConstraint("demo_case_id", "idempotency_key", name="uq_demo_state_transitions_demo_case_id"),
    )
    op.create_index("ix_demo_transitions_demo_occurred", "demo_state_transitions", ["demo_case_id", "occurred_at"])

    op.create_table(
        "agent_inbox_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("source_agent", sa.String(100), nullable=False),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("payload_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("payload_key_reference", sa.String(255)),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("processing_attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.PrimaryKeyConstraint("id", name="pk_agent_inbox_events"),
        sa.UniqueConstraint("source_agent", "event_id", "schema_version", name="uq_agent_inbox_source_event_schema"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_agent_inbox_tenant_idempotency"),
    )
    op.create_index("ix_agent_inbox_unprocessed", "agent_inbox_events", ["received_at"], postgresql_where=sa.text("processed_at IS NULL"))

    op.create_table(
        "agent_outbox_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("target_agent", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("payload_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(100)),
        sa.PrimaryKeyConstraint("id", name="pk_agent_outbox_events"),
        sa.UniqueConstraint("event_id", name="uq_agent_outbox_event_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_agent_outbox_tenant_idempotency"),
    )
    op.create_index("ix_agent_outbox_pending", "agent_outbox_events", ["available_at"], postgresql_where=sa.text("published_at IS NULL"))

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_reference", sa.String(255)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint("tenant_id", "scope", "idempotency_key", name="uq_idempotency_scope_key"),
    )

    op.create_table(
        "human_handoff_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("demo_case_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("region_id", sa.String(100)),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("redacted_summary", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assigned_to", sa.String(255)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["demo_case_id"], ["demo_cases.id"], ondelete="CASCADE", name="fk_human_handoff_tickets_demo_case_id_demo_cases"),
        sa.PrimaryKeyConstraint("id", name="pk_human_handoff_tickets"),
    )
    op.create_index("uq_handoff_open_reason", "human_handoff_tickets", ["demo_case_id", "reason_code"], unique=True, postgresql_where=sa.text("status IN ('open', 'assigned')"))

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("region_id", sa.String(100)),
        sa.Column("demo_case_id", sa.Uuid()),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_ref_hash", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("export_sanitized", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_tenant_occurred", "audit_events", ["tenant_id", "occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("human_handoff_tickets")
    op.drop_table("idempotency_records")
    op.drop_table("agent_outbox_events")
    op.drop_table("agent_inbox_events")
    op.drop_table("demo_state_transitions")
    op.drop_table("demo_cases")
