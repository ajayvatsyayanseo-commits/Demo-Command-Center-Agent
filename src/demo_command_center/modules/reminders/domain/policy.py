from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256

from demo_command_center.modules.communications.domain.message_policy import Channel, MessageClass
from demo_command_center.modules.demo_core.domain.identifiers import DemoId


class ReminderAudience(StrEnum):
    LEARNER_OR_GUARDIAN = "learner_or_guardian"
    TUTOR = "tutor"


class AttendanceOutcome(StrEnum):
    PRESENT_OR_UNKNOWN = "present_or_unknown"
    LEARNER_NO_SHOW = "learner_no_show"
    TUTOR_NO_SHOW = "tutor_no_show"
    TECHNICAL_FAILURE = "technical_failure"
    DISPUTED = "disputed"


class AttendanceSignal(StrEnum):
    LEARNER_CONFIRMED_ABSENT = "learner_confirmed_absent"
    TUTOR_CONFIRMED_LEARNER_ABSENT = "tutor_confirmed_learner_absent"
    TUTOR_CONFIRMED_ABSENT = "tutor_confirmed_absent"
    LEARNER_CONFIRMED_TUTOR_ABSENT = "learner_confirmed_tutor_absent"
    CONSENTED_ATTENDANCE_LEARNER_MISSING = "consented_attendance_learner_missing"
    CONSENTED_ATTENDANCE_TUTOR_MISSING = "consented_attendance_tutor_missing"
    TECHNICAL_INCIDENT = "technical_incident"
    OUTCOME_DISPUTED = "outcome_disputed"


@dataclass(frozen=True, slots=True)
class ReminderRule:
    rule_id: str
    relative_to_start: timedelta
    audiences: frozenset[ReminderAudience]
    message_class: MessageClass
    channels: frozenset[Channel]
    template_ref: str
    active_case_states: frozenset[str]


@dataclass(frozen=True, slots=True)
class ReminderPolicy:
    version: str
    rules: tuple[ReminderRule, ...]
    provider_retry_limit: int
    risk_threshold: int
    risk_rule_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("reminder policy version is required")
        if self.provider_retry_limit < 0 or self.risk_threshold < 0:
            raise ValueError("retry and risk thresholds cannot be negative")
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("reminder rule IDs must be unique")
        if not self.risk_rule_ids.issubset(rule_ids):
            raise ValueError("risk rule IDs must reference configured rules")


@dataclass(frozen=True, slots=True)
class ReminderPlan:
    reminder_key: str
    rule_id: str
    audience: ReminderAudience
    run_at: datetime
    channels: frozenset[Channel]
    template_ref: str
    message_class: MessageClass
    policy_version: str
    session_version: int


@dataclass(frozen=True, slots=True)
class NoShowPolicy:
    version: str
    minimum_independent_signals: int
    decision_delay: timedelta

    def __post_init__(self) -> None:
        if self.minimum_independent_signals <= 0 or self.decision_delay < timedelta(0):
            raise ValueError("no-show evidence and delay policy are invalid")


@dataclass(frozen=True, slots=True)
class NoShowDecision:
    outcome: AttendanceOutcome
    requires_human_review: bool
    evidence: frozenset[AttendanceSignal]
    policy_version: str


def plan_reminders(
    demo_id: DemoId,
    session_starts_at: datetime,
    session_version: int,
    case_state: str,
    audience: ReminderAudience,
    risk_score: int,
    policy: ReminderPolicy,
    *,
    now: datetime,
) -> tuple[ReminderPlan, ...]:
    if session_starts_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("reminder times must be timezone-aware")
    plans: list[ReminderPlan] = []
    for rule in policy.rules:
        if (
            audience not in rule.audiences
            or case_state not in rule.active_case_states
            or (rule.rule_id in policy.risk_rule_ids and risk_score < policy.risk_threshold)
        ):
            continue
        run_at = session_starts_at + rule.relative_to_start
        if run_at < now:
            continue
        material = f"{demo_id}|{session_version}|{policy.version}|{rule.rule_id}|{audience}"
        plans.append(
            ReminderPlan(
                sha256(material.encode()).hexdigest(),
                rule.rule_id,
                audience,
                run_at,
                rule.channels,
                rule.template_ref,
                rule.message_class,
                policy.version,
                session_version,
            )
        )
    return tuple(sorted(plans, key=lambda item: (item.run_at, item.rule_id)))


def reminder_is_current(
    plan: ReminderPlan,
    *,
    current_session_version: int,
    current_case_state: str,
    rule: ReminderRule,
) -> bool:
    return (
        plan.session_version == current_session_version
        and plan.rule_id == rule.rule_id
        and current_case_state in rule.active_case_states
    )


def determine_no_show(
    signals: frozenset[AttendanceSignal],
    session_starts_at: datetime,
    policy: NoShowPolicy,
    *,
    now: datetime,
) -> NoShowDecision:
    if AttendanceSignal.OUTCOME_DISPUTED in signals:
        return NoShowDecision(AttendanceOutcome.DISPUTED, True, signals, policy.version)
    if AttendanceSignal.TECHNICAL_INCIDENT in signals:
        return NoShowDecision(AttendanceOutcome.TECHNICAL_FAILURE, True, signals, policy.version)
    if now < session_starts_at + policy.decision_delay:
        return NoShowDecision(AttendanceOutcome.PRESENT_OR_UNKNOWN, False, signals, policy.version)
    learner = signals.intersection(
        {
            AttendanceSignal.LEARNER_CONFIRMED_ABSENT,
            AttendanceSignal.TUTOR_CONFIRMED_LEARNER_ABSENT,
            AttendanceSignal.CONSENTED_ATTENDANCE_LEARNER_MISSING,
        }
    )
    tutor = signals.intersection(
        {
            AttendanceSignal.TUTOR_CONFIRMED_ABSENT,
            AttendanceSignal.LEARNER_CONFIRMED_TUTOR_ABSENT,
            AttendanceSignal.CONSENTED_ATTENDANCE_TUTOR_MISSING,
        }
    )
    learner_sufficient = len(learner) >= policy.minimum_independent_signals
    tutor_sufficient = len(tutor) >= policy.minimum_independent_signals
    if learner_sufficient and tutor_sufficient:
        return NoShowDecision(AttendanceOutcome.DISPUTED, True, signals, policy.version)
    if learner_sufficient:
        return NoShowDecision(AttendanceOutcome.LEARNER_NO_SHOW, False, signals, policy.version)
    if tutor_sufficient:
        return NoShowDecision(AttendanceOutcome.TUTOR_NO_SHOW, False, signals, policy.version)
    return NoShowDecision(AttendanceOutcome.PRESENT_OR_UNKNOWN, False, signals, policy.version)
