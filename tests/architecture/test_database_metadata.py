from demo_command_center.infrastructure.database import models  # noqa: F401
from demo_command_center.infrastructure.database.base import Base


def test_initial_owned_tables_are_registered() -> None:
    required = {
        "demo_cases",
        "demo_state_transitions",
        "agent_inbox_events",
        "agent_outbox_events",
        "idempotency_records",
        "human_handoff_tickets",
        "audit_events",
    }
    assert required <= set(Base.metadata.tables)
