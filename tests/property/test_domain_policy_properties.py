from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from hypothesis import given
from hypothesis import strategies as st

from demo_command_center.modules.demo_core.domain.identifiers import DemoId, TutorId
from demo_command_center.modules.demo_core.domain.money import Money
from demo_command_center.modules.scheduling.domain.policy import (
    HoldStatus,
    SlotHold,
    TimeWindow,
    holds_collide,
    resolve_local_datetime,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


@given(
    amount=st.integers(min_value=0, max_value=10**9),
    basis_points=st.integers(min_value=0, max_value=10_000),
)
def test_discounted_money_never_negative_or_above_list_price(
    amount: int, basis_points: int
) -> None:
    original = Money(amount, "INR")
    discounted = original.discounted_by_basis_points(basis_points)
    assert 0 <= discounted.amount_minor <= original.amount_minor
    assert discounted.currency == original.currency


@given(
    hour=st.integers(min_value=0, max_value=23),
    minute=st.integers(min_value=0, max_value=59),
)
def test_india_local_time_round_trips_without_ambiguity(hour: int, minute: int) -> None:
    local = resolve_local_datetime(date(2026, 7, 13), time(hour, minute), "Asia/Kolkata")
    round_trip = local.astimezone(UTC).astimezone(local.tzinfo)
    assert round_trip.date() == local.date()
    assert round_trip.time().replace(tzinfo=None) == local.time().replace(tzinfo=None)


@given(
    first_start=st.integers(min_value=0, max_value=240),
    first_duration=st.integers(min_value=1, max_value=120),
    second_start=st.integers(min_value=0, max_value=240),
    second_duration=st.integers(min_value=1, max_value=120),
)
def test_slot_hold_collision_is_symmetric_and_matches_half_open_intervals(
    first_start: int,
    first_duration: int,
    second_start: int,
    second_duration: int,
) -> None:
    first_window = TimeWindow(
        NOW + timedelta(minutes=first_start),
        NOW + timedelta(minutes=first_start + first_duration),
    )
    second_window = TimeWindow(
        NOW + timedelta(minutes=second_start),
        NOW + timedelta(minutes=second_start + second_duration),
    )
    first = SlotHold(
        "hold-a",
        DemoId("demo-a"),
        TutorId("tutor"),
        first_window,
        NOW,
        NOW + timedelta(days=1),
        HoldStatus.ACTIVE,
        "policy-v1",
    )
    second = SlotHold(
        "hold-b",
        DemoId("demo-b"),
        TutorId("tutor"),
        second_window,
        NOW,
        NOW + timedelta(days=1),
        HoldStatus.ACTIVE,
        "policy-v1",
    )
    expected = (
        first_window.starts_at < second_window.ends_at
        and second_window.starts_at < first_window.ends_at
    )
    assert holds_collide(first, second, now=NOW) is expected
    assert holds_collide(second, first, now=NOW) is expected
