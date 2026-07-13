from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from demo_command_center.modules.demo_core.domain.identifiers import RegionId, TutorId
from demo_command_center.modules.demo_core.domain.money import Money


class DemoMode(StrEnum):
    ONLINE = "online"
    HOME = "home"


class RankingSignal(StrEnum):
    LANGUAGE = "language"
    BUDGET = "budget"
    QUALITY = "quality"
    RELIABILITY = "reliability"


@dataclass(frozen=True, slots=True)
class TutorCandidate:
    tutor_id: TutorId
    display_name: str
    snapshot_version: str
    captured_at: datetime
    boards: frozenset[str]
    class_levels: frozenset[str]
    subjects: frozenset[str]
    modes: frozenset[DemoMode]
    region_ids: frozenset[RegionId]
    languages: frozenset[str]
    price: Money | None
    availability_confirmed: bool
    quality_score: Decimal | None = None
    no_show_rate: Decimal | None = None

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None:
            raise ValueError("candidate snapshot time must be timezone-aware")
        if not self.snapshot_version.strip():
            raise ValueError("candidate snapshot version is required")
        if self.quality_score is not None and not Decimal(0) <= self.quality_score <= Decimal(1):
            raise ValueError("quality score must be between zero and one")
        if self.no_show_rate is not None and not Decimal(0) <= self.no_show_rate <= Decimal(1):
            raise ValueError("no-show rate must be between zero and one")


@dataclass(frozen=True, slots=True)
class MatchRequirement:
    board: str
    class_level: str
    subject: str
    mode: DemoMode
    region_id: RegionId | None
    accepted_languages: frozenset[str]
    maximum_price: Money | None = None
    explicitly_selected_tutor_id: TutorId | None = None


@dataclass(frozen=True, slots=True)
class RankingPolicy:
    version: str
    weights: dict[RankingSignal, Decimal]
    maximum_snapshot_age: timedelta
    shortlist_limit: int

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("ranking policy version is required")
        if self.maximum_snapshot_age <= timedelta(0):
            raise ValueError("maximum snapshot age must be positive")
        if self.shortlist_limit <= 0:
            raise ValueError("shortlist limit must be positive")
        if any(weight < 0 for weight in self.weights.values()):
            raise ValueError("ranking weights cannot be negative")
        if sum(self.weights.values(), start=Decimal(0)) <= 0:
            raise ValueError("at least one positive ranking weight is required")


@dataclass(frozen=True, slots=True)
class RankedTutor:
    tutor_id: TutorId
    display_name: str
    score: Decimal
    reasons: tuple[str, ...]
    snapshot_version: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class MatchDecision:
    shortlist: tuple[RankedTutor, ...]
    excluded: dict[TutorId, tuple[str, ...]]
    relaxation_options: tuple[str, ...]
    needs_human_handoff: bool
    ranking_version: str


def _hard_constraint_failures(
    candidate: TutorCandidate, requirement: MatchRequirement, now: datetime, policy: RankingPolicy
) -> tuple[str, ...]:
    failures: list[str] = []
    if now - candidate.captured_at > policy.maximum_snapshot_age:
        failures.append("stale_snapshot")
    if requirement.board not in candidate.boards:
        failures.append("board_unavailable")
    if requirement.class_level not in candidate.class_levels:
        failures.append("class_unavailable")
    if requirement.subject not in candidate.subjects:
        failures.append("subject_unavailable")
    if requirement.mode not in candidate.modes:
        failures.append("mode_unavailable")
    if requirement.region_id is not None and requirement.region_id not in candidate.region_ids:
        failures.append("region_unavailable")
    if not candidate.availability_confirmed:
        failures.append("availability_unverified")
    if requirement.maximum_price is not None:
        if candidate.price is None:
            failures.append("price_unverified")
        else:
            requirement.maximum_price.require_same_currency(candidate.price)
            if candidate.price.amount_minor > requirement.maximum_price.amount_minor:
                failures.append("over_budget")
    return tuple(failures)


def _score(
    candidate: TutorCandidate, requirement: MatchRequirement, policy: RankingPolicy
) -> tuple[Decimal, tuple[str, ...]]:
    signals: dict[RankingSignal, Decimal] = {
        RankingSignal.LANGUAGE: Decimal(
            bool(requirement.accepted_languages.intersection(candidate.languages))
        ),
        RankingSignal.BUDGET: Decimal(
            requirement.maximum_price is None
            or (candidate.price is not None and candidate.price <= requirement.maximum_price)
        ),
        RankingSignal.QUALITY: candidate.quality_score or Decimal(0),
        RankingSignal.RELIABILITY: (
            Decimal(1) - candidate.no_show_rate
            if candidate.no_show_rate is not None
            else Decimal(0)
        ),
    }
    denominator = sum(policy.weights.values(), start=Decimal(0))
    score = (
        sum(
            (policy.weights.get(signal, Decimal(0)) * value for signal, value in signals.items()),
            start=Decimal(0),
        )
        / denominator
    )
    reasons = tuple(
        signal.value
        for signal, value in signals.items()
        if value > 0 and policy.weights.get(signal, 0) > 0
    )
    return score, reasons


def rank_tutors(
    candidates: tuple[TutorCandidate, ...],
    requirement: MatchRequirement,
    policy: RankingPolicy,
    *,
    now: datetime,
) -> MatchDecision:
    if now.tzinfo is None:
        raise ValueError("matching time must be timezone-aware")
    excluded: dict[TutorId, tuple[str, ...]] = {}
    ranked: list[RankedTutor] = []
    for candidate in candidates:
        failures = _hard_constraint_failures(candidate, requirement, now, policy)
        if (
            requirement.explicitly_selected_tutor_id is not None
            and candidate.tutor_id != requirement.explicitly_selected_tutor_id
        ):
            failures = (*failures, "not_explicit_selection")
        if failures:
            excluded[candidate.tutor_id] = failures
            continue
        score, reasons = _score(candidate, requirement, policy)
        ranked.append(
            RankedTutor(
                candidate.tutor_id,
                candidate.display_name,
                score,
                reasons,
                candidate.snapshot_version,
                candidate.captured_at,
            )
        )
    ranked.sort(key=lambda item: (-item.score, str(item.tutor_id)))
    shortlist = tuple(ranked[: policy.shortlist_limit])
    relaxation_options = (
        () if shortlist else ("alternate_time", "alternate_mode", "relax_nonessential_preferences")
    )
    return MatchDecision(
        shortlist,
        excluded,
        relaxation_options,
        not shortlist,
        policy.version,
    )
