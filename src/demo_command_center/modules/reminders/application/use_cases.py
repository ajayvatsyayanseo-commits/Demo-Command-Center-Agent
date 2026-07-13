from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from demo_command_center.modules.demo_core.domain.identifiers import DemoId
from demo_command_center.modules.reminders.domain.policy import (
    ReminderAudience,
    ReminderPlan,
    ReminderPolicy,
    plan_reminders,
)


@dataclass(frozen=True, slots=True)
class ReminderPlanningUseCase:
    policy: ReminderPolicy

    def execute(
        self,
        demo_id: DemoId,
        session_starts_at: datetime,
        session_version: int,
        case_state: str,
        audience: ReminderAudience,
        risk_score: int,
        *,
        now: datetime,
    ) -> tuple[ReminderPlan, ...]:
        return plan_reminders(
            demo_id,
            session_starts_at,
            session_version,
            case_state,
            audience,
            risk_score,
            self.policy,
            now=now,
        )
