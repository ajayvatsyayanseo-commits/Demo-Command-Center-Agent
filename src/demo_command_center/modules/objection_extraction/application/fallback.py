from __future__ import annotations

from dataclasses import dataclass

from demo_command_center.modules.objection_extraction.domain.pipeline import (
    Objection,
    ObjectionEvidence,
    ObjectionPolicy,
    deterministic_extract,
)


@dataclass(frozen=True, slots=True)
class DeterministicObjectionFallback:
    policy: ObjectionPolicy

    def execute(self, evidence: tuple[ObjectionEvidence, ...]) -> tuple[Objection, ...]:
        return deterministic_extract(evidence, self.policy)
