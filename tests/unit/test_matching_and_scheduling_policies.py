from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest

from demo_command_center.modules.demo_core.domain.identifiers import (
    DemoId,
    RegionId,
    TutorId,
)
from demo_command_center.modules.demo_core.domain.money import Money
from demo_command_center.modules.scheduling.domain.policy import (
    Confirmation,
    ConfirmationStatus,
    HoldStatus,
    LocalTimeError,
    Participant,
    SchedulingPolicy,
    TimeWindow,
    create_hold,
    evaluate_confirmations,
    expire_hold,
    hold_is_active,
    holds_collide,
    propose_slots,
    release_hold,
    resolve_local_datetime,
)
from demo_command_center.modules.tutor_matching.application.use_cases import TutorShortlistUseCase
from demo_command_center.modules.tutor_matching.domain.matching import (
    DemoMode,
    MatchRequirement,
    RankingPolicy,
    RankingSignal,
    TutorCandidate,
)

NOW = datetime(2026, 7, 13, 8, tzinfo=UTC)


def _ranking_policy() -> RankingPolicy:
    return RankingPolicy(
        "ranking-v1",
        {
            RankingSignal.LANGUAGE: Decimal("1"),
            RankingSignal.BUDGET: Decimal("1"),
            RankingSignal.QUALITY: Decimal("2"),
            RankingSignal.RELIABILITY: Decimal("2"),
        },
        timedelta(minutes=30),
        2,
    )


def _candidate(
    tutor_id: str,
    *,
    captured_at: datetime = NOW,
    subject: str = "maths",
    available: bool = True,
    price_minor: int = 80000,
    quality: str = "0.8",
) -> TutorCandidate:
    return TutorCandidate(
        TutorId(tutor_id),
        f"Tutor {tutor_id}",
        "website-snapshot-v2",
        captured_at,
        frozenset({"CBSE"}),
        frozenset({"10"}),
        frozenset({subject}),
        frozenset({DemoMode.ONLINE}),
        frozenset({RegionId("north")}),
        frozenset({"en", "hi"}),
        Money(price_minor, "INR"),
        available,
        Decimal(quality),
        Decimal("0.1"),
    )


def _requirement(explicit: str | None = None) -> MatchRequirement:
    return MatchRequirement(
        "CBSE",
        "10",
        "maths",
        DemoMode.ONLINE,
        RegionId("north"),
        frozenset({"en"}),
        Money(100000, "INR"),
        TutorId(explicit) if explicit else None,
    )


def _scheduling_policy() -> SchedulingPolicy:
    return SchedulingPolicy(
        "schedule-v3",
        timedelta(hours=1),
        timedelta(minutes=15),
        timedelta(minutes=15),
        timedelta(minutes=20),
        timedelta(minutes=15),
        timedelta(hours=2),
        2,
        frozenset({Participant.LEARNER_OR_GUARDIAN, Participant.TUTOR}),
    )


def test_matching_ranks_authoritative_candidates_and_hides_stale_results() -> None:
    decision = TutorShortlistUseCase(_ranking_policy()).execute(
        (
            _candidate("lower", quality="0.5"),
            _candidate("higher", quality="0.9"),
            _candidate("stale", captured_at=NOW - timedelta(hours=1)),
            _candidate("wrong-subject", subject="science"),
            _candidate("unavailable", available=False),
        ),
        _requirement(),
        now=NOW,
    )

    assert [item.tutor_id for item in decision.shortlist] == [TutorId("higher"), TutorId("lower")]
    assert decision.shortlist[0].reasons == ("language", "budget", "quality", "reliability")
    assert decision.excluded[TutorId("stale")] == ("stale_snapshot",)
    assert "subject_unavailable" in decision.excluded[TutorId("wrong-subject")]
    assert "availability_unverified" in decision.excluded[TutorId("unavailable")]
    assert not decision.needs_human_handoff


def test_explicit_tutor_selection_never_silently_substitutes_another_tutor() -> None:
    decision = TutorShortlistUseCase(_ranking_policy()).execute(
        (_candidate("selected"), _candidate("other")), _requirement("selected"), now=NOW
    )
    assert [item.tutor_id for item in decision.shortlist] == [TutorId("selected")]
    assert "not_explicit_selection" in decision.excluded[TutorId("other")]


def test_no_match_returns_relaxation_and_human_handoff_without_booking_claim() -> None:
    decision = TutorShortlistUseCase(_ranking_policy()).execute(
        (_candidate("wrong", subject="science"),), _requirement(), now=NOW
    )
    assert decision.shortlist == ()
    assert decision.needs_human_handoff
    assert decision.relaxation_options == (
        "alternate_time",
        "alternate_mode",
        "relax_nonessential_preferences",
    )


def test_matching_rejects_naive_time_and_invalid_policy() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TutorShortlistUseCase(_ranking_policy()).execute(
            (_candidate("one"),), _requirement(), now=datetime(2026, 1, 1)
        )
    with pytest.raises(ValueError, match="positive ranking"):
        RankingPolicy("v", {}, timedelta(minutes=1), 1)


def test_local_time_resolution_handles_normal_gap_and_fold() -> None:
    normal = resolve_local_datetime(date(2026, 7, 13), time(10, 30), "Asia/Kolkata")
    assert normal.utcoffset() == timedelta(hours=5, minutes=30)

    with pytest.raises(LocalTimeError, match="does not exist"):
        resolve_local_datetime(date(2026, 3, 8), time(2, 30), "America/New_York")
    with pytest.raises(LocalTimeError, match="ambiguous"):
        resolve_local_datetime(date(2026, 11, 1), time(1, 30), "America/New_York")
    first = resolve_local_datetime(date(2026, 11, 1), time(1, 30), "America/New_York", fold=0)
    second = resolve_local_datetime(date(2026, 11, 1), time(1, 30), "America/New_York", fold=1)
    assert first.astimezone(UTC) != second.astimezone(UTC)


def test_slot_proposal_applies_availability_busy_buffer_lead_limit_and_stable_ids() -> None:
    policy = _scheduling_policy()
    starts = (
        NOW + timedelta(hours=1),
        NOW + timedelta(hours=3),
        NOW + timedelta(hours=5),
        NOW + timedelta(hours=7),
    )
    availability = (TimeWindow(NOW, NOW + timedelta(hours=10)),)
    busy = (TimeWindow(NOW + timedelta(hours=3, minutes=50), NOW + timedelta(hours=4)),)
    first = propose_slots(
        TutorId("t1"), starts, availability, busy, policy, now=NOW, display_timezone="Asia/Kolkata"
    )
    second = propose_slots(
        TutorId("t1"), starts, availability, busy, policy, now=NOW, display_timezone="Asia/Kolkata"
    )
    assert [option.starts_at for option in first] == [starts[2], starts[3]]
    assert first == second
    assert len(first) == policy.maximum_options


def test_hold_collision_expiry_release_and_confirmation_guards() -> None:
    option = propose_slots(
        TutorId("t1"),
        (NOW + timedelta(hours=3),),
        (TimeWindow(NOW, NOW + timedelta(hours=8)),),
        (),
        _scheduling_policy(),
        now=NOW,
        display_timezone="Asia/Kolkata",
    )[0]
    first = create_hold(DemoId("demo-1"), option, _scheduling_policy(), now=NOW)
    second = create_hold(DemoId("demo-2"), option, _scheduling_policy(), now=NOW)
    assert holds_collide(first, second, now=NOW)
    assert hold_is_active(first, now=NOW)

    outstanding = evaluate_confirmations(first, (), _scheduling_policy(), now=NOW)
    assert not outstanding.ready_to_schedule
    assert outstanding.outstanding == frozenset(
        {Participant.LEARNER_OR_GUARDIAN, Participant.TUTOR}
    )

    confirmed = evaluate_confirmations(
        first,
        (
            Confirmation(Participant.LEARNER_OR_GUARDIAN, ConfirmationStatus.CONFIRMED, NOW),
            Confirmation(Participant.TUTOR, ConfirmationStatus.CONFIRMED, NOW),
        ),
        _scheduling_policy(),
        now=NOW,
    )
    assert confirmed.ready_to_schedule
    assert confirmed.reason == "all_required_confirmed"

    declined = evaluate_confirmations(
        first,
        (Confirmation(Participant.TUTOR, ConfirmationStatus.DECLINED, NOW),),
        _scheduling_policy(),
        now=NOW,
    )
    assert declined.reason == "participant_declined"

    expired = expire_hold(first, now=first.expires_at)
    assert expired.status is HoldStatus.EXPIRED
    assert not evaluate_confirmations(
        expired, (), _scheduling_policy(), now=first.expires_at
    ).hold_active
    assert release_hold(first).status is HoldStatus.RELEASED
    assert release_hold(expired) is expired


def test_time_window_uses_half_open_collision_semantics() -> None:
    first = TimeWindow(NOW, NOW + timedelta(hours=1))
    touching = TimeWindow(NOW + timedelta(hours=1), NOW + timedelta(hours=2))
    overlapping = TimeWindow(NOW + timedelta(minutes=59), NOW + timedelta(hours=2))
    assert not first.overlaps(touching)
    assert first.overlaps(overlapping)
