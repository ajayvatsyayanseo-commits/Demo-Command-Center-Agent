from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from demo_command_center.modules.communications.domain.message_policy import Channel, MessageClass


class DemoOutcome(StrEnum):
    COMPLETED = "completed"
    LEARNER_NO_SHOW = "learner_no_show"
    TUTOR_NO_SHOW = "tutor_no_show"
    TECHNICAL_FAILURE = "technical_failure"
    DISPUTED = "disputed"


class OfferApproval(StrEnum):
    NONE = "none"
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class FollowUpRule:
    rule_id: str
    outcomes: frozenset[DemoOutcome]
    delay: timedelta
    channel: Channel
    message_class: MessageClass
    template_ref: str
    required_fact_refs: frozenset[str]
    permitted_offer_approvals: frozenset[OfferApproval]
    requires_human_review: bool


@dataclass(frozen=True, slots=True)
class ConversionPolicy:
    version: str
    rules: tuple[FollowUpRule, ...]
    allowed_after_opt_out: frozenset[MessageClass]
    prohibited_claim_types: frozenset[str]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("conversion policy version is required")
        ids = [rule.rule_id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("conversion rule IDs must be unique")
        if any(rule.delay < timedelta(0) for rule in self.rules):
            raise ValueError("follow-up delay cannot be negative")


@dataclass(frozen=True, slots=True)
class ConversionContext:
    outcome: DemoOutcome
    outcome_verified: bool
    available_fact_refs: frozenset[str]
    offer_approval: OfferApproval
    opted_out: bool
    communication_allowed: bool
    high_risk_case: bool


@dataclass(frozen=True, slots=True)
class NextBestAction:
    follow_up: bool
    rule_id: str | None
    execute_at: datetime | None
    channel: Channel | None
    message_class: MessageClass | None
    template_ref: str | None
    required_fact_refs: frozenset[str]
    requires_human_review: bool
    reason: str
    policy_version: str


@dataclass(frozen=True, slots=True)
class DraftClaim:
    text: str
    claim_type: str
    source_ref: str | None


@dataclass(frozen=True, slots=True)
class DraftValidation:
    approved: bool
    violations: tuple[str, ...]
    content_source_refs: frozenset[str]


def choose_next_action(
    context: ConversionContext, policy: ConversionPolicy, *, now: datetime
) -> NextBestAction:
    if now.tzinfo is None:
        raise ValueError("conversion decision time must be timezone-aware")
    if not context.outcome_verified:
        return NextBestAction(
            False,
            None,
            None,
            None,
            None,
            None,
            frozenset(),
            True,
            "outcome_unverified",
            policy.version,
        )
    if not context.communication_allowed:
        return NextBestAction(
            False,
            None,
            None,
            None,
            None,
            None,
            frozenset(),
            False,
            "communication_not_allowed",
            policy.version,
        )
    for rule in policy.rules:
        if context.outcome not in rule.outcomes:
            continue
        if context.offer_approval not in rule.permitted_offer_approvals:
            continue
        if not rule.required_fact_refs.issubset(context.available_fact_refs):
            continue
        if context.opted_out and rule.message_class not in policy.allowed_after_opt_out:
            return NextBestAction(
                False,
                None,
                None,
                None,
                None,
                None,
                frozenset(),
                False,
                "recipient_opted_out",
                policy.version,
            )
        return NextBestAction(
            True,
            rule.rule_id,
            now + rule.delay,
            rule.channel,
            rule.message_class,
            rule.template_ref,
            rule.required_fact_refs,
            rule.requires_human_review or context.high_risk_case,
            "rule_selected",
            policy.version,
        )
    return NextBestAction(
        False,
        None,
        None,
        None,
        None,
        None,
        frozenset(),
        context.high_risk_case,
        "no_applicable_rule",
        policy.version,
    )


def validate_draft(
    claims: tuple[DraftClaim, ...],
    approved_source_refs: frozenset[str],
    policy: ConversionPolicy,
) -> DraftValidation:
    violations: list[str] = []
    used_sources: set[str] = set()
    for claim in claims:
        if claim.claim_type in policy.prohibited_claim_types:
            violations.append(f"prohibited_claim:{claim.claim_type}")
        if claim.source_ref is None or claim.source_ref not in approved_source_refs:
            violations.append(f"ungrounded_claim:{claim.claim_type}")
        else:
            used_sources.add(claim.source_ref)
    return DraftValidation(not violations, tuple(violations), frozenset(used_sources))
