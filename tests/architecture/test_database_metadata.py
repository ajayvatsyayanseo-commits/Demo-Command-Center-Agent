from demo_command_center.infrastructure.database import models  # noqa: F401
from demo_command_center.infrastructure.database.base import Base


def test_complete_owned_tables_are_registered() -> None:
    required = {
        "demo_cases",
        "demo_state_transitions",
        "agent_inbox_events",
        "agent_outbox_events",
        "idempotency_records",
        "human_handoff_tickets",
        "audit_events",
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
        "payment_checkout_sessions",
        "payment_reconciliations",
        "paid_transitions",
        "onboarding_handoffs",
        "consent_records",
        "communication_opt_outs",
        "runtime_feature_flags",
        "regional_aggregates",
        "regional_alerts",
    }
    assert required <= set(Base.metadata.tables)


def test_constraint_names_are_unique_within_each_table() -> None:
    for table in Base.metadata.tables.values():
        names = [constraint.name for constraint in table.constraints if constraint.name]
        assert len(names) == len(set(names)), table.name


def test_critical_exactly_once_indexes_exist() -> None:
    expected = {
        "slot_holds": {"uq_slot_hold_active_tutor_start"},
        "human_handoff_tickets": {"uq_handoff_open_reason"},
        "agent_inbox_events": {"ix_agent_inbox_unprocessed"},
        "agent_outbox_events": {"ix_agent_outbox_pending"},
    }
    for table_name, index_names in expected.items():
        actual = {index.name for index in Base.metadata.tables[table_name].indexes}
        assert index_names <= actual
