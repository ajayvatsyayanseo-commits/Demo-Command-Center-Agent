from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from demo_command_center.modules.paid_transition.domain.verification import (
    PaymentDecision,
    PaymentEvidence,
    PaymentOrderBinding,
    PaymentVerificationPolicy,
    verify_payment,
)


@dataclass(frozen=True, slots=True)
class PaymentVerificationUseCase:
    policy: PaymentVerificationPolicy

    def execute(
        self,
        order: PaymentOrderBinding,
        evidence: PaymentEvidence,
        *,
        processed_event_ids: frozenset[str],
        paid_activation_already_applied: bool,
        now: datetime,
    ) -> PaymentDecision:
        return verify_payment(
            order,
            evidence,
            self.policy,
            processed_event_ids=processed_event_ids,
            paid_activation_already_applied=paid_activation_already_applied,
            now=now,
        )
