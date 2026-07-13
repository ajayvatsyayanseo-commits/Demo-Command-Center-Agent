from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from tests.unit.test_conversion_discount_and_payment_policies import (
    NOW,
    _discount_context,
    _discount_policy,
    _evidence,
    _order,
    _payment_policy,
)
from tests.unit.test_matching_and_scheduling_policies import _scheduling_policy

from demo_command_center.modules.communications.domain.message_policy import (
    Channel,
    CommunicationPreference,
    MessageClass,
    MessagePolicy,
    QuietHours,
)
from demo_command_center.modules.demo_core.domain.identifiers import DemoId, TutorId
from demo_command_center.modules.demo_core.domain.money import Money
from demo_command_center.modules.demo_core.domain.quality import (
    QualityComponentDefinition,
    QualityRubric,
)
from demo_command_center.modules.discount_suggestions.domain.policy import (
    ApprovalLevel,
    ApprovalTier,
    bind_offer,
    decide_discount,
)
from demo_command_center.modules.objection_extraction.domain.pipeline import (
    FallbackRule,
    ObjectionExpression,
    ObjectionPolicy,
)
from demo_command_center.modules.paid_transition.domain.verification import (
    EvidenceSource,
    PaymentDecisionKind,
    PaymentVerificationPolicy,
    verify_payment,
)
from demo_command_center.modules.post_demo_conversion.domain.policy import (
    ConversionPolicy,
    FollowUpRule,
)
from demo_command_center.modules.regional_monitoring.domain.policy import UnderperformancePolicy
from demo_command_center.modules.reminders.domain.policy import (
    NoShowPolicy,
    ReminderPolicy,
)
from demo_command_center.modules.scheduling.domain.policy import (
    LocalTimeError,
    SchedulingPolicy,
    TimeWindow,
    create_hold,
    propose_slots,
    resolve_local_datetime,
)
from demo_command_center.modules.success_forecasting.domain.scoring import (
    EvaluationPolicy,
    FeatureDefinition,
    ForecastModel,
    LabeledPrediction,
    ThresholdPolicy,
    time_aware_split,
)
from demo_command_center.modules.tutor_matching.domain.matching import (
    RankingPolicy,
    RankingSignal,
    TutorCandidate,
)


@pytest.mark.parametrize(
    "money",
    [
        lambda: Money(-1, "INR"),
        lambda: Money(1, "rupee"),
    ],
)
def test_money_rejects_invalid_values(money: object) -> None:
    with pytest.raises(ValueError):
        money()  # type: ignore[operator]


def test_money_currency_and_subtraction_boundaries() -> None:
    with pytest.raises(ValueError, match="currency mismatch"):
        Money(1, "INR").require_same_currency(Money(1, "USD"))
    with pytest.raises(ValueError, match="cannot be negative"):
        Money(1, "INR").subtract(Money(2, "INR"))
    assert Money(3, "INR").subtract(Money(2, "INR")) == Money(1, "INR")
    with pytest.raises(ValueError, match="basis points"):
        Money(1, "INR").discounted_by_basis_points(10_001)


@pytest.mark.parametrize(
    "policy",
    [
        lambda: SchedulingPolicy(
            "",
            timedelta(hours=1),
            timedelta(0),
            timedelta(0),
            timedelta(minutes=1),
            timedelta(minutes=1),
            timedelta(0),
            1,
            frozenset(),
        ),
        lambda: replace(_scheduling_policy(), session_duration=timedelta(0)),
        lambda: replace(_scheduling_policy(), buffer_before=timedelta(seconds=-1)),
        lambda: replace(_scheduling_policy(), maximum_options=0),
        lambda: replace(_scheduling_policy(), required_confirmations=frozenset()),
    ],
)
def test_scheduling_policy_rejects_unsafe_configuration(policy: object) -> None:
    with pytest.raises(ValueError):
        policy()  # type: ignore[operator]


def test_scheduling_rejects_bad_windows_timezones_and_naive_candidates() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TimeWindow(datetime(2026, 1, 1), datetime(2026, 1, 2))
    with pytest.raises(ValueError, match="positive duration"):
        TimeWindow(NOW, NOW)
    with pytest.raises(LocalTimeError, match="unknown IANA"):
        resolve_local_datetime(date(2026, 1, 1), time(1), "Not/AZone")
    with pytest.raises(LocalTimeError, match="invalid fold"):
        resolve_local_datetime(date(2026, 7, 13), time(1), "Asia/Kolkata", fold=1)
    with pytest.raises(ValueError, match="candidate slot"):
        propose_slots(
            TutorId("t"),
            (datetime(2026, 1, 1),),
            (TimeWindow(NOW, NOW + timedelta(days=1)),),
            (),
            _scheduling_policy(),
            now=NOW,
            display_timezone="Asia/Kolkata",
        )
    option = propose_slots(
        TutorId("t"),
        (NOW + timedelta(hours=3),),
        (TimeWindow(NOW, NOW + timedelta(days=1)),),
        (),
        _scheduling_policy(),
        now=NOW,
        display_timezone="Asia/Kolkata",
    )[0]
    with pytest.raises(ValueError, match="hold time"):
        create_hold(DemoId("d"), option, _scheduling_policy(), now=datetime(2026, 1, 1))


def test_payment_covers_all_binding_mismatches_expiry_and_pending_reconciliation() -> None:
    evidence = replace(
        _evidence(),
        customer_ref="forged-customer",
        purpose="wrong-purpose",
        environment="production",
        amount=Money(8999, "INR"),
    )
    result = verify_payment(
        _order(),
        evidence,
        _payment_policy(),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert result.kind is PaymentDecisionKind.REVIEW
    assert set(result.reason_codes) == {
        "amount_mismatch",
        "customer_mismatch",
        "purpose_mismatch",
        "environment_mismatch",
    }

    expired = verify_payment(
        _order(),
        _evidence(status="UNMAPPED"),
        _payment_policy(),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=_order().expires_at,
    )
    assert expired.kind is PaymentDecisionKind.EXPIRED
    pending = verify_payment(
        _order(),
        _evidence(
            source=EvidenceSource.AUTHENTICATED_RECONCILIATION,
            status="PENDING",
            provider_auth=True,
        ),
        _payment_policy(),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert pending.kind is PaymentDecisionKind.PENDING


def test_payment_policy_and_timestamp_validation_fail_closed() -> None:
    with pytest.raises(ValueError, match="success statuses"):
        PaymentVerificationPolicy("", frozenset(), frozenset(), frozenset(), frozenset())
    with pytest.raises(ValueError, match="multiple decisions"):
        PaymentVerificationPolicy(
            "v", frozenset({"SUCCESS"}), frozenset({"SUCCESS"}), frozenset(), frozenset()
        )
    naive_order = replace(_order(), expires_at=datetime(2026, 7, 13))
    with pytest.raises(ValueError, match="timezone-aware"):
        verify_payment(
            naive_order,
            _evidence(),
            _payment_policy(),
            processed_event_ids=frozenset(),
            paid_activation_already_applied=False,
            now=NOW,
        )


def test_discount_zero_price_and_unavailable_approval_tier_fail_closed() -> None:
    zero_context = _discount_context(
        list_price=Money(0, "INR"),
        minimum_permitted_price=Money(0, "INR"),
        requested_discount_basis_points=0,
    )
    assert decide_discount(zero_context, _discount_policy(), now=NOW).approved
    sparse_tiers = replace(
        _discount_policy(), approval_tiers=(ApprovalTier(500, ApprovalLevel.AUTOMATIC),)
    )
    rejected = decide_discount(
        _discount_context(requested_discount_basis_points=1000), sparse_tiers, now=NOW
    )
    assert "step_up_approval_unavailable" in rejected.reason_codes
    with pytest.raises(ValueError, match="approved discount"):
        bind_offer(_discount_context(), rejected)


@pytest.mark.parametrize(
    "policy",
    [
        lambda: replace(_discount_policy(), version=""),
        lambda: replace(_discount_policy(), recommendation_minimum_basis_points=2000),
        lambda: replace(_discount_policy(), offer_ttl=timedelta(0)),
        lambda: replace(_discount_policy(), maximum_active_offers=0),
        lambda: replace(
            _discount_policy(),
            approval_tiers=(
                ApprovalTier(1000, ApprovalLevel.AUTOMATIC),
                ApprovalTier(500, ApprovalLevel.OPERATIONS),
            ),
        ),
    ],
)
def test_discount_policy_rejects_unsafe_configuration(policy: object) -> None:
    with pytest.raises(ValueError):
        policy()  # type: ignore[operator]


def test_other_policy_objects_reject_invalid_configuration() -> None:
    with pytest.raises(ValueError):
        CommunicationPreference("Not/AZone", (Channel.EMAIL,))
    with pytest.raises(ValueError):
        MessagePolicy("", QuietHours(time(1), time(2)), frozenset(), True, 0, 0, frozenset())
    with pytest.raises(ValueError):
        QualityComponentDefinition("x", Decimal(1), Decimal(1), Decimal(1), True)
    with pytest.raises(ValueError):
        QualityRubric("", (), frozenset(), 0)
    with pytest.raises(ValueError):
        ReminderPolicy("", (), -1, -1, frozenset())
    with pytest.raises(ValueError):
        NoShowPolicy("v", 0, timedelta(0))
    with pytest.raises(ValueError):
        rule = FollowUpRule(
            "same",
            frozenset(),
            timedelta(0),
            Channel.EMAIL,
            MessageClass.UTILITY,
            "t",
            frozenset(),
            frozenset(),
            False,
        )
        ConversionPolicy(
            "v",
            (rule, rule),
            frozenset(),
            frozenset(),
        )
    with pytest.raises(ValueError):
        UnderperformancePolicy("v", 0, 0, Decimal(0), Decimal(0), Decimal(0), timedelta(0), "owner")


def test_model_policy_validation_and_time_split_order() -> None:
    with pytest.raises(ValueError):
        FeatureDefinition("x", Decimal(1), Decimal(1), Decimal(1), "x")
    with pytest.raises(ValueError):
        ForecastModel(
            "v",
            "r",
            Decimal(0),
            {},
            (FeatureDefinition("x", Decimal(0), Decimal(1), Decimal(0), "x"),),
            Decimal(0),
            1,
            Decimal(-1),
            Decimal(1),
        )
    with pytest.raises(ValueError):
        ThresholdPolicy("v", Decimal("0.8"), Decimal("0.2"))
    with pytest.raises(ValueError):
        LabeledPrediction(Decimal("1.1"), True, NOW, NOW)
    sample = LabeledPrediction(Decimal("0.5"), True, NOW, NOW)
    with pytest.raises(ValueError, match="cutoff"):
        time_aware_split((sample,), training_ends_at=NOW, validation_ends_at=NOW)
    with pytest.raises(ValueError):
        EvaluationPolicy("v", 0, Decimal(1), Decimal(0))


def test_tutor_and_objection_configuration_validation() -> None:
    with pytest.raises(ValueError):
        RankingPolicy("v", {RankingSignal.QUALITY: Decimal(-1)}, timedelta(0), 0)
    with pytest.raises(ValueError):
        TutorCandidate(
            TutorId("t"),
            "Tutor",
            "snapshot",
            datetime(2026, 1, 1),
            frozenset(),
            frozenset(),
            frozenset(),
            frozenset(),
            frozenset(),
            frozenset(),
            None,
            False,
            Decimal("2"),
            None,
        )
    rule = FallbackRule(
        "r",
        "unknown",
        ("phrase",),
        ObjectionExpression.EXPLICIT,
        "normalized",
        "root",
        "alternative",
        "question",
        Decimal("0.5"),
    )
    with pytest.raises(ValueError):
        ObjectionPolicy(
            "v", frozenset({"price"}), (rule,), Decimal("0.5"), Decimal("0.5"), 1, "p", "m"
        )
