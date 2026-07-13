from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from demo_command_center.modules.discount_suggestions.domain.policy import (
    DiscountContext,
    DiscountDecision,
    DiscountPolicy,
    decide_discount,
)


@dataclass(frozen=True, slots=True)
class DiscountDecisionUseCase:
    policy: DiscountPolicy

    def execute(self, context: DiscountContext, *, now: datetime) -> DiscountDecision:
        return decide_discount(context, self.policy, now=now)
