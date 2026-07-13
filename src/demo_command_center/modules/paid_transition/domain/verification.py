from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from demo_command_center.modules.demo_core.domain.identifiers import DemoId, UserId
from demo_command_center.modules.demo_core.domain.money import Money


class EvidenceSource(StrEnum):
    SIGNED_WEBHOOK = "signed_webhook"
    AUTHENTICATED_RECONCILIATION = "authenticated_reconciliation"
    BROWSER_RETURN = "browser_return"
    CLIENT_CALLBACK = "client_callback"
    USER_MESSAGE = "user_message"


class PaymentDecisionKind(StrEnum):
    TRANSITION_PAID = "transition_paid"
    DUPLICATE = "duplicate"
    REVIEW = "review"
    RECONCILE = "reconcile"
    FAILED = "failed"
    EXPIRED = "expired"
    PENDING = "pending"
    REJECTED_EVIDENCE = "rejected_evidence"


@dataclass(frozen=True, slots=True)
class PaymentOrderBinding:
    domain_order_id: str
    provider_order_id: str
    demo_id: DemoId
    user_id: UserId
    customer_ref: str
    plan_ref: str
    offer_ref: str | None
    amount: Money
    purpose: str
    environment: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PaymentEvidence:
    provider_event_id: str
    provider_order_id: str
    source: EvidenceSource
    status: str
    amount: Money
    customer_ref: str
    purpose: str
    environment: str
    occurred_at: datetime
    signature_verified: bool
    replay_window_verified: bool
    provider_authentication_verified: bool


@dataclass(frozen=True, slots=True)
class PaymentVerificationPolicy:
    version: str
    successful_terminal_statuses: frozenset[str]
    failed_terminal_statuses: frozenset[str]
    expired_terminal_statuses: frozenset[str]
    review_statuses: frozenset[str]

    def __post_init__(self) -> None:
        groups = (
            self.successful_terminal_statuses,
            self.failed_terminal_statuses,
            self.expired_terminal_statuses,
            self.review_statuses,
        )
        if not self.version.strip() or not self.successful_terminal_statuses:
            raise ValueError("payment policy version and success statuses are required")
        flattened = [status for group in groups for status in group]
        if len(flattened) != len(set(flattened)):
            raise ValueError("payment statuses cannot map to multiple decisions")


@dataclass(frozen=True, slots=True)
class PaymentDecision:
    kind: PaymentDecisionKind
    reason_codes: tuple[str, ...]
    should_transition_paid: bool
    activation_key: str | None
    paid_outbox_key: str | None
    policy_version: str


def _operation_key(prefix: str, order: PaymentOrderBinding) -> str:
    material = f"{prefix}|{order.domain_order_id}|{order.provider_order_id}|{order.demo_id}"
    return sha256(material.encode()).hexdigest()


def verify_payment(
    order: PaymentOrderBinding,
    evidence: PaymentEvidence,
    policy: PaymentVerificationPolicy,
    *,
    processed_event_ids: frozenset[str],
    paid_activation_already_applied: bool,
    now: datetime,
) -> PaymentDecision:
    if now.tzinfo is None or order.expires_at.tzinfo is None or evidence.occurred_at.tzinfo is None:
        raise ValueError("payment timestamps must be timezone-aware")
    if evidence.provider_event_id in processed_event_ids:
        return PaymentDecision(
            PaymentDecisionKind.DUPLICATE,
            ("provider_event_duplicate",),
            False,
            None,
            None,
            policy.version,
        )
    if evidence.source is EvidenceSource.SIGNED_WEBHOOK:
        authoritative = evidence.signature_verified and evidence.replay_window_verified
    elif evidence.source is EvidenceSource.AUTHENTICATED_RECONCILIATION:
        authoritative = evidence.provider_authentication_verified
    else:
        authoritative = False
    if not authoritative:
        return PaymentDecision(
            PaymentDecisionKind.REJECTED_EVIDENCE,
            ("non_authoritative_payment_evidence",),
            False,
            None,
            None,
            policy.version,
        )
    mismatches: list[str] = []
    if evidence.provider_order_id != order.provider_order_id:
        mismatches.append("order_mismatch")
    try:
        evidence.amount.require_same_currency(order.amount)
    except ValueError:
        mismatches.append("currency_mismatch")
    else:
        if evidence.amount.amount_minor != order.amount.amount_minor:
            mismatches.append("amount_mismatch")
    if evidence.customer_ref != order.customer_ref:
        mismatches.append("customer_mismatch")
    if evidence.purpose != order.purpose:
        mismatches.append("purpose_mismatch")
    if evidence.environment != order.environment:
        mismatches.append("environment_mismatch")
    if mismatches:
        return PaymentDecision(
            PaymentDecisionKind.REVIEW,
            tuple(mismatches),
            False,
            None,
            None,
            policy.version,
        )
    if evidence.status in policy.successful_terminal_statuses:
        if paid_activation_already_applied:
            return PaymentDecision(
                PaymentDecisionKind.DUPLICATE,
                ("paid_activation_already_applied",),
                False,
                _operation_key("activation", order),
                _operation_key("paid-outbox", order),
                policy.version,
            )
        return PaymentDecision(
            PaymentDecisionKind.TRANSITION_PAID,
            ("verified_terminal_success",),
            True,
            _operation_key("activation", order),
            _operation_key("paid-outbox", order),
            policy.version,
        )
    if evidence.status in policy.failed_terminal_statuses:
        return PaymentDecision(
            PaymentDecisionKind.FAILED,
            ("verified_terminal_failure",),
            False,
            None,
            None,
            policy.version,
        )
    if evidence.status in policy.expired_terminal_statuses or now >= order.expires_at:
        return PaymentDecision(
            PaymentDecisionKind.EXPIRED,
            ("payment_expired",),
            False,
            None,
            None,
            policy.version,
        )
    if evidence.status in policy.review_statuses:
        return PaymentDecision(
            PaymentDecisionKind.REVIEW,
            ("provider_status_requires_review",),
            False,
            None,
            None,
            policy.version,
        )
    if evidence.source is EvidenceSource.SIGNED_WEBHOOK:
        return PaymentDecision(
            PaymentDecisionKind.RECONCILE,
            ("nonterminal_status_requires_reconciliation",),
            False,
            None,
            None,
            policy.version,
        )
    return PaymentDecision(
        PaymentDecisionKind.PENDING,
        ("verified_nonterminal_status",),
        False,
        None,
        None,
        policy.version,
    )
