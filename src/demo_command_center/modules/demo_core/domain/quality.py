from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from demo_command_center.modules.demo_core.domain.identifiers import RegionId


@dataclass(frozen=True, slots=True)
class QualityComponentDefinition:
    component_id: str
    weight: Decimal
    minimum: Decimal
    maximum: Decimal
    required: bool

    def __post_init__(self) -> None:
        if self.weight < 0 or self.maximum <= self.minimum:
            raise ValueError("quality component bounds or weight are invalid")


@dataclass(frozen=True, slots=True)
class QualityRubric:
    version: str
    components: tuple[QualityComponentDefinition, ...]
    blocking_flags: frozenset[str]
    minimum_aggregate_cohort: int

    def __post_init__(self) -> None:
        ids = [component.component_id for component in self.components]
        if not self.version.strip() or not self.components:
            raise ValueError("quality rubric version and components are required")
        if len(ids) != len(set(ids)):
            raise ValueError("quality component IDs must be unique")
        if sum((component.weight for component in self.components), start=Decimal(0)) <= 0:
            raise ValueError("quality rubric must have positive total weight")
        if self.minimum_aggregate_cohort <= 0:
            raise ValueError("aggregate cohort threshold must be positive")


@dataclass(frozen=True, slots=True)
class QualityObservation:
    component_id: str
    value: Decimal | None
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    score: Decimal | None
    component_scores: dict[str, Decimal | None]
    evidence_refs: dict[str, tuple[str, ...]]
    missing_components: frozenset[str]
    completeness: Decimal
    rubric_version: str
    requires_human_review: bool
    flags: frozenset[str]
    override_score: Decimal | None = None
    override_reason: str | None = None


@dataclass(frozen=True, slots=True)
class RegionalQualityAggregate:
    region_id: RegionId
    cohort_size: int
    mean_score: Decimal | None
    suppressed: bool
    rubric_version: str


def assess_quality(
    observations: tuple[QualityObservation, ...],
    flags: frozenset[str],
    rubric: QualityRubric,
) -> QualityAssessment:
    supplied = {observation.component_id: observation for observation in observations}
    unknown = set(supplied).difference(component.component_id for component in rubric.components)
    if unknown:
        raise ValueError("quality observations contain unknown components")
    component_scores: dict[str, Decimal | None] = {}
    evidence: dict[str, tuple[str, ...]] = {}
    missing: set[str] = set()
    weighted = Decimal(0)
    measured_weight = Decimal(0)
    total_weight = sum((component.weight for component in rubric.components), start=Decimal(0))
    for component in rubric.components:
        observation = supplied.get(component.component_id)
        if observation is None or observation.value is None:
            component_scores[component.component_id] = None
            missing.add(component.component_id)
            continue
        if not component.minimum <= observation.value <= component.maximum:
            raise ValueError("quality observation falls outside rubric bounds")
        normalized = (observation.value - component.minimum) / (
            component.maximum - component.minimum
        )
        component_scores[component.component_id] = normalized
        evidence[component.component_id] = observation.evidence_refs
        weighted += normalized * component.weight
        measured_weight += component.weight
    score = None if measured_weight == 0 else weighted / measured_weight
    completeness = measured_weight / total_weight
    requires_review = bool(flags.intersection(rubric.blocking_flags)) or any(
        component.required and component.component_id in missing for component in rubric.components
    )
    return QualityAssessment(
        score,
        component_scores,
        evidence,
        frozenset(missing),
        completeness,
        rubric.version,
        requires_review,
        flags,
    )


def override_assessment(
    assessment: QualityAssessment,
    score: Decimal,
    reason: str,
    *,
    authorized: bool,
) -> QualityAssessment:
    if not authorized:
        raise PermissionError("quality override requires authorization")
    if not Decimal(0) <= score <= Decimal(1):
        raise ValueError("override score must be between zero and one")
    if not reason.strip():
        raise ValueError("quality override reason is required")
    return QualityAssessment(
        assessment.score,
        assessment.component_scores,
        assessment.evidence_refs,
        assessment.missing_components,
        assessment.completeness,
        assessment.rubric_version,
        assessment.requires_human_review,
        assessment.flags,
        score,
        reason.strip(),
    )


def aggregate_region(
    region_id: RegionId,
    assessments: tuple[QualityAssessment, ...],
    rubric: QualityRubric,
) -> RegionalQualityAggregate:
    scores = tuple(
        assessment.override_score if assessment.override_score is not None else assessment.score
        for assessment in assessments
        if (
            assessment.override_score if assessment.override_score is not None else assessment.score
        )
        is not None
    )
    if len(scores) < rubric.minimum_aggregate_cohort:
        return RegionalQualityAggregate(region_id, len(scores), None, True, rubric.version)
    concrete_scores = tuple(score for score in scores if score is not None)
    return RegionalQualityAggregate(
        region_id,
        len(concrete_scores),
        sum(concrete_scores, start=Decimal(0)) / len(concrete_scores),
        False,
        rubric.version,
    )
