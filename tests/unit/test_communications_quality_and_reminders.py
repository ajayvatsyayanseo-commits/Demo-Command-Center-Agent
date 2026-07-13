from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

import pytest

from demo_command_center.modules.communications.domain.message_policy import (
    Channel,
    CommunicationPreference,
    MessageClass,
    MessagePolicy,
    MessageRequest,
    QuietHours,
    evaluate_message,
    record_opt_out,
)
from demo_command_center.modules.demo_core.domain.identifiers import DemoId, RegionId
from demo_command_center.modules.demo_core.domain.quality import (
    QualityComponentDefinition,
    QualityObservation,
    QualityRubric,
    aggregate_region,
    assess_quality,
    override_assessment,
)
from demo_command_center.modules.reminders.domain.policy import (
    AttendanceOutcome,
    AttendanceSignal,
    NoShowPolicy,
    ReminderAudience,
    ReminderPolicy,
    ReminderRule,
    determine_no_show,
    plan_reminders,
    reminder_is_current,
)

NOW = datetime(2026, 7, 13, 16, 30, tzinfo=UTC)  # 22:00 Asia/Kolkata


def _message_policy() -> MessagePolicy:
    return MessagePolicy(
        "message-v4",
        QuietHours(time(21), time(8)),
        frozenset({MessageClass.TRANSACTIONAL}),
        True,
        3,
        20,
        frozenset({"stop", "unsubscribe"}),
    )


def _preference(*, opted_out: bool = False) -> CommunicationPreference:
    return CommunicationPreference(
        "Asia/Kolkata",
        (Channel.WHATSAPP, Channel.EMAIL),
        NOW if opted_out else None,
    )


def _request(
    message_class: MessageClass = MessageClass.UTILITY,
    *,
    template: str | None = "demo-reminder-v1",
    service_window: bool = False,
    cost: int = 10,
) -> MessageRequest:
    return MessageRequest(
        message_class,
        frozenset({Channel.WHATSAPP, Channel.EMAIL}),
        template,
        service_window,
        cost,
    )


def _reminder_policy() -> ReminderPolicy:
    return ReminderPolicy(
        "reminders-v2",
        (
            ReminderRule(
                "standard",
                timedelta(hours=-2),
                frozenset({ReminderAudience.LEARNER_OR_GUARDIAN, ReminderAudience.TUTOR}),
                MessageClass.UTILITY,
                frozenset({Channel.WHATSAPP}),
                "standard-template",
                frozenset({"SCHEDULED", "REMINDERS_ACTIVE"}),
            ),
            ReminderRule(
                "risk-extra",
                timedelta(minutes=-30),
                frozenset({ReminderAudience.LEARNER_OR_GUARDIAN}),
                MessageClass.UTILITY,
                frozenset({Channel.WHATSAPP, Channel.EMAIL}),
                "risk-template",
                frozenset({"SCHEDULED", "REMINDERS_ACTIVE"}),
            ),
        ),
        4,
        7,
        frozenset({"risk-extra"}),
    )


def _rubric(minimum_cohort: int = 2) -> QualityRubric:
    return QualityRubric(
        "quality-v5",
        (
            QualityComponentDefinition(
                "punctuality", Decimal("2"), Decimal("0"), Decimal("10"), True
            ),
            QualityComponentDefinition("clarity", Decimal("1"), Decimal("1"), Decimal("5"), False),
        ),
        frozenset({"safeguarding"}),
        minimum_cohort,
    )


def test_message_policy_honors_quiet_hours_service_window_and_template() -> None:
    decision = evaluate_message(_request(), _preference(), _message_policy(), now=NOW)
    assert decision.allowed
    assert decision.channel is Channel.WHATSAPP
    assert decision.not_before == datetime(2026, 7, 14, 2, 30, tzinfo=UTC)

    no_template = evaluate_message(
        _request(template=None), _preference(), _message_policy(), now=NOW
    )
    assert not no_template.allowed
    assert no_template.reason == "approved_template_required"

    open_window = evaluate_message(
        _request(template=None, service_window=True), _preference(), _message_policy(), now=NOW
    )
    assert open_window.allowed


def test_opt_out_blocks_nontransactional_content_but_preserves_configured_exception() -> None:
    opted_out = record_opt_out(_preference(), " STOP ", _message_policy(), now=NOW)
    assert opted_out.opted_out_at == NOW
    blocked = evaluate_message(_request(), opted_out, _message_policy(), now=NOW)
    assert not blocked.allowed and blocked.reason == "recipient_opted_out"
    transactional = evaluate_message(
        _request(MessageClass.TRANSACTIONAL), opted_out, _message_policy(), now=NOW
    )
    assert transactional.allowed
    assert (
        record_opt_out(_preference(), "continue", _message_policy(), now=NOW).opted_out_at is None
    )


def test_message_policy_rejects_cost_and_channel_mismatch() -> None:
    expensive = evaluate_message(_request(cost=21), _preference(), _message_policy(), now=NOW)
    assert expensive.reason == "cost_limit_exceeded"
    unavailable = MessageRequest(MessageClass.UTILITY, frozenset(), "template", False, 0)
    assert (
        evaluate_message(unavailable, _preference(), _message_policy(), now=NOW).reason
        == "no_permitted_channel"
    )


def test_reminders_have_stable_dedupe_keys_risk_rules_and_state_invalidation() -> None:
    session = NOW + timedelta(hours=5)
    policy = _reminder_policy()
    low_risk = plan_reminders(
        DemoId("demo-1"),
        session,
        3,
        "SCHEDULED",
        ReminderAudience.LEARNER_OR_GUARDIAN,
        6,
        policy,
        now=NOW,
    )
    high_risk = plan_reminders(
        DemoId("demo-1"),
        session,
        3,
        "SCHEDULED",
        ReminderAudience.LEARNER_OR_GUARDIAN,
        7,
        policy,
        now=NOW,
    )
    repeated = plan_reminders(
        DemoId("demo-1"),
        session,
        3,
        "SCHEDULED",
        ReminderAudience.LEARNER_OR_GUARDIAN,
        7,
        policy,
        now=NOW,
    )
    assert [plan.rule_id for plan in low_risk] == ["standard"]
    assert [plan.rule_id for plan in high_risk] == ["standard", "risk-extra"]
    assert high_risk == repeated
    assert reminder_is_current(
        high_risk[0],
        current_session_version=3,
        current_case_state="SCHEDULED",
        rule=policy.rules[0],
    )
    assert not reminder_is_current(
        high_risk[0],
        current_session_version=4,
        current_case_state="SCHEDULED",
        rule=policy.rules[0],
    )


def test_no_show_requires_multiple_signals_and_distinguishes_failures() -> None:
    policy = NoShowPolicy("attendance-v1", 2, timedelta(minutes=15))
    session = NOW - timedelta(hours=1)
    insufficient = determine_no_show(
        frozenset({AttendanceSignal.LEARNER_CONFIRMED_ABSENT}), session, policy, now=NOW
    )
    assert insufficient.outcome is AttendanceOutcome.PRESENT_OR_UNKNOWN
    learner = determine_no_show(
        frozenset(
            {
                AttendanceSignal.LEARNER_CONFIRMED_ABSENT,
                AttendanceSignal.TUTOR_CONFIRMED_LEARNER_ABSENT,
            }
        ),
        session,
        policy,
        now=NOW,
    )
    assert learner.outcome is AttendanceOutcome.LEARNER_NO_SHOW
    tutor = determine_no_show(
        frozenset(
            {
                AttendanceSignal.TUTOR_CONFIRMED_ABSENT,
                AttendanceSignal.LEARNER_CONFIRMED_TUTOR_ABSENT,
            }
        ),
        session,
        policy,
        now=NOW,
    )
    assert tutor.outcome is AttendanceOutcome.TUTOR_NO_SHOW
    disputed = determine_no_show(
        frozenset({AttendanceSignal.OUTCOME_DISPUTED}), session, policy, now=NOW
    )
    assert disputed.outcome is AttendanceOutcome.DISPUTED and disputed.requires_human_review
    technical = determine_no_show(
        frozenset({AttendanceSignal.TECHNICAL_INCIDENT}), session, policy, now=NOW
    )
    assert technical.outcome is AttendanceOutcome.TECHNICAL_FAILURE


def test_quality_preserves_not_measured_and_component_evidence() -> None:
    assessment = assess_quality(
        (
            QualityObservation("punctuality", Decimal("0"), ("attendance:1",)),
            QualityObservation("clarity", None, ()),
        ),
        frozenset(),
        _rubric(),
    )
    assert assessment.component_scores["punctuality"] == Decimal(0)
    assert assessment.component_scores["clarity"] is None
    assert assessment.score == Decimal(0)
    assert assessment.missing_components == frozenset({"clarity"})
    assert assessment.evidence_refs["punctuality"] == ("attendance:1",)


def test_quality_flags_override_and_privacy_preserving_aggregate() -> None:
    assessment = assess_quality(
        (QualityObservation("punctuality", Decimal("10"), ("attendance:2",)),),
        frozenset({"safeguarding"}),
        _rubric(),
    )
    assert assessment.requires_human_review
    with pytest.raises(PermissionError):
        override_assessment(assessment, Decimal("0.5"), "reviewed", authorized=False)
    overridden = override_assessment(assessment, Decimal(0), "verified evidence", authorized=True)
    assert overridden.override_score == Decimal(0)
    suppressed = aggregate_region(RegionId("north"), (overridden,), _rubric())
    assert suppressed.suppressed and suppressed.mean_score is None
    visible = aggregate_region(RegionId("north"), (overridden, assessment), _rubric())
    assert not visible.suppressed
    assert visible.mean_score == Decimal("0.5")
