from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from demo_command_center.modules.tutor_matching.domain.matching import (
    MatchDecision,
    MatchRequirement,
    RankingPolicy,
    TutorCandidate,
    rank_tutors,
)


@dataclass(frozen=True, slots=True)
class TutorShortlistUseCase:
    """Coordinates an already-authoritative website snapshot with pure ranking policy."""

    policy: RankingPolicy

    def execute(
        self,
        candidates: tuple[TutorCandidate, ...],
        requirement: MatchRequirement,
        *,
        now: datetime,
    ) -> MatchDecision:
        return rank_tutors(candidates, requirement, self.policy, now=now)
