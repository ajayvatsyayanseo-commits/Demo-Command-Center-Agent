from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from demo_command_center.modules.post_demo_conversion.domain.policy import (
    ConversionContext,
    ConversionPolicy,
    NextBestAction,
    choose_next_action,
)


@dataclass(frozen=True, slots=True)
class NextBestActionUseCase:
    policy: ConversionPolicy

    def execute(self, context: ConversionContext, *, now: datetime) -> NextBestAction:
        return choose_next_action(context, self.policy, now=now)
