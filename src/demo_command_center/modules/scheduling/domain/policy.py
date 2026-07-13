from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from demo_command_center.modules.demo_core.domain.identifiers import DemoId, TutorId


class LocalTimeError(ValueError):
    """A local wall time cannot be resolved safely."""


class Participant(StrEnum):
    LEARNER_OR_GUARDIAN = "learner_or_guardian"
    TUTOR = "tutor"


class ConfirmationStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"


class HoldStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class SchedulingPolicy:
    version: str
    session_duration: timedelta
    buffer_before: timedelta
    buffer_after: timedelta
    hold_ttl: timedelta
    confirmation_ttl: timedelta
    minimum_lead_time: timedelta
    maximum_options: int
    required_confirmations: frozenset[Participant]

    def __post_init__(self) -> None:
        durations = (
            self.session_duration,
            self.hold_ttl,
            self.confirmation_ttl,
        )
        if not self.version.strip():
            raise ValueError("scheduling policy version is required")
        if any(value <= timedelta(0) for value in durations):
            raise ValueError("duration and TTL values must be positive")
        if any(
            value < timedelta(0)
            for value in (self.buffer_before, self.buffer_after, self.minimum_lead_time)
        ):
            raise ValueError("buffers and lead time cannot be negative")
        if self.maximum_options <= 0:
            raise ValueError("maximum options must be positive")
        if not self.required_confirmations:
            raise ValueError("at least one confirmation must be required")


@dataclass(frozen=True, slots=True)
class TimeWindow:
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("time windows must be timezone-aware")
        if self.starts_at >= self.ends_at:
            raise ValueError("time window must have positive duration")

    def overlaps(self, other: TimeWindow) -> bool:
        return self.starts_at < other.ends_at and other.starts_at < self.ends_at


@dataclass(frozen=True, slots=True)
class SlotOption:
    option_id: str
    tutor_id: TutorId
    starts_at: datetime
    ends_at: datetime
    display_timezone: str
    policy_version: str


@dataclass(frozen=True, slots=True)
class SlotHold:
    hold_id: str
    demo_id: DemoId
    tutor_id: TutorId
    slot: TimeWindow
    held_at: datetime
    expires_at: datetime
    status: HoldStatus
    policy_version: str

    @property
    def is_active(self) -> bool:
        return self.status is HoldStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class Confirmation:
    participant: Participant
    status: ConfirmationStatus
    recorded_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConfirmationDecision:
    ready_to_schedule: bool
    outstanding: frozenset[Participant]
    declined: frozenset[Participant]
    hold_active: bool
    reason: str


def resolve_local_datetime(
    local_date: date,
    local_time: time,
    timezone_name: str,
    *,
    fold: int | None = None,
) -> datetime:
    """Resolve a wall time while rejecting DST gaps and unchosen folds."""

    if local_time.tzinfo is not None:
        raise LocalTimeError("local time must not already contain timezone information")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise LocalTimeError("unknown IANA timezone") from exc
    wall = datetime.combine(local_date, local_time)
    valid: dict[int, datetime] = {}
    for candidate_fold in (0, 1):
        candidate = wall.replace(tzinfo=zone, fold=candidate_fold)
        round_trip = candidate.astimezone(UTC).astimezone(zone)
        if round_trip.replace(tzinfo=None) == wall and round_trip.fold == candidate_fold:
            valid[candidate_fold] = candidate
    if not valid:
        raise LocalTimeError("local time does not exist in the selected timezone")
    offsets = {candidate.utcoffset() for candidate in valid.values()}
    if len(offsets) > 1 and fold is None:
        raise LocalTimeError("local time is ambiguous; an explicit fold is required")
    selected_fold = 0 if fold is None else fold
    try:
        return valid[selected_fold]
    except KeyError as exc:
        raise LocalTimeError("invalid fold for local time") from exc


def _slot_id(tutor_id: TutorId, start: datetime, end: datetime, policy_version: str) -> str:
    material = "|".join((str(tutor_id), start.isoformat(), end.isoformat(), policy_version))
    return sha256(material.encode()).hexdigest()


def propose_slots(
    tutor_id: TutorId,
    candidate_starts: tuple[datetime, ...],
    availability: tuple[TimeWindow, ...],
    busy: tuple[TimeWindow, ...],
    policy: SchedulingPolicy,
    *,
    now: datetime,
    display_timezone: str,
) -> tuple[SlotOption, ...]:
    if now.tzinfo is None:
        raise ValueError("proposal time must be timezone-aware")
    ZoneInfo(display_timezone)
    options: list[SlotOption] = []
    for start in sorted(set(candidate_starts)):
        if start.tzinfo is None:
            raise ValueError("candidate slot start must be timezone-aware")
        end = start + policy.session_duration
        session = TimeWindow(start, end)
        protected = TimeWindow(start - policy.buffer_before, end + policy.buffer_after)
        is_within_availability = any(
            window.starts_at <= session.starts_at and session.ends_at <= window.ends_at
            for window in availability
        )
        if (
            start < now + policy.minimum_lead_time
            or not is_within_availability
            or any(protected.overlaps(blocked) for blocked in busy)
        ):
            continue
        options.append(
            SlotOption(
                _slot_id(tutor_id, start, end, policy.version),
                tutor_id,
                start,
                end,
                display_timezone,
                policy.version,
            )
        )
        if len(options) == policy.maximum_options:
            break
    return tuple(options)


def create_hold(
    demo_id: DemoId,
    option: SlotOption,
    policy: SchedulingPolicy,
    *,
    now: datetime,
) -> SlotHold:
    if now.tzinfo is None:
        raise ValueError("hold time must be timezone-aware")
    material = f"{demo_id}|{option.option_id}|{policy.version}"
    return SlotHold(
        sha256(material.encode()).hexdigest(),
        demo_id,
        option.tutor_id,
        TimeWindow(option.starts_at, option.ends_at),
        now,
        now + policy.hold_ttl,
        HoldStatus.ACTIVE,
        policy.version,
    )


def holds_collide(first: SlotHold, second: SlotHold, *, now: datetime) -> bool:
    return (
        first.tutor_id == second.tutor_id
        and hold_is_active(first, now=now)
        and hold_is_active(second, now=now)
        and first.slot.overlaps(second.slot)
    )


def hold_is_active(hold: SlotHold, *, now: datetime) -> bool:
    return hold.status is HoldStatus.ACTIVE and now < hold.expires_at


def expire_hold(hold: SlotHold, *, now: datetime) -> SlotHold:
    if hold.status is HoldStatus.ACTIVE and now >= hold.expires_at:
        return replace(hold, status=HoldStatus.EXPIRED)
    return hold


def release_hold(hold: SlotHold) -> SlotHold:
    if hold.status is HoldStatus.ACTIVE:
        return replace(hold, status=HoldStatus.RELEASED)
    return hold


def evaluate_confirmations(
    hold: SlotHold,
    confirmations: tuple[Confirmation, ...],
    policy: SchedulingPolicy,
    *,
    now: datetime,
) -> ConfirmationDecision:
    statuses = {item.participant: item.status for item in confirmations}
    declined = frozenset(
        participant
        for participant in policy.required_confirmations
        if statuses.get(participant) is ConfirmationStatus.DECLINED
    )
    outstanding = frozenset(
        participant
        for participant in policy.required_confirmations
        if statuses.get(participant) is not ConfirmationStatus.CONFIRMED
        and participant not in declined
    )
    active = hold_is_active(hold, now=now) and now < hold.held_at + policy.confirmation_ttl
    if declined:
        return ConfirmationDecision(False, outstanding, declined, active, "participant_declined")
    if not active:
        return ConfirmationDecision(False, outstanding, declined, False, "confirmation_expired")
    if outstanding:
        return ConfirmationDecision(False, outstanding, declined, True, "confirmation_outstanding")
    return ConfirmationDecision(True, outstanding, declined, True, "all_required_confirmed")
