from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from demo_command_center.modules.demo_core.domain.identifiers import DemoId
from demo_command_center.modules.scheduling.domain.policy import (
    Confirmation,
    ConfirmationDecision,
    SchedulingPolicy,
    SlotHold,
    SlotOption,
    create_hold,
    evaluate_confirmations,
)


@dataclass(frozen=True, slots=True)
class SchedulingDecisionService:
    policy: SchedulingPolicy

    def hold(self, demo_id: DemoId, option: SlotOption, *, now: datetime) -> SlotHold:
        return create_hold(demo_id, option, self.policy, now=now)

    def confirm(
        self,
        hold: SlotHold,
        confirmations: tuple[Confirmation, ...],
        *,
        now: datetime,
    ) -> ConfirmationDecision:
        return evaluate_confirmations(hold, confirmations, self.policy, now=now)
