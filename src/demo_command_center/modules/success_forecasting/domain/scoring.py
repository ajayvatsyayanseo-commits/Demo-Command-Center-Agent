from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    name: str
    minimum: Decimal
    maximum: Decimal
    fallback: Decimal
    reason_code: str

    def __post_init__(self) -> None:
        if self.maximum <= self.minimum or not self.minimum <= self.fallback <= self.maximum:
            raise ValueError("feature bounds or fallback are invalid")


@dataclass(frozen=True, slots=True)
class FeatureObservation:
    name: str
    value: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("feature observation time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ForecastModel:
    version: str
    feature_registry_version: str
    intercept: Decimal
    coefficients: dict[str, Decimal]
    features: tuple[FeatureDefinition, ...]
    missing_feature_confidence_penalty: Decimal
    maximum_reason_codes: int
    logit_floor: Decimal
    logit_ceiling: Decimal

    def __post_init__(self) -> None:
        names = [feature.name for feature in self.features]
        if not self.version.strip() or not self.feature_registry_version.strip():
            raise ValueError("model and feature registry versions are required")
        if len(names) != len(set(names)) or set(names) != set(self.coefficients):
            raise ValueError("model coefficients must exactly match the feature registry")
        if not Decimal(0) <= self.missing_feature_confidence_penalty <= Decimal(1):
            raise ValueError("missing feature penalty must be between zero and one")
        if self.maximum_reason_codes <= 0 or self.logit_floor >= self.logit_ceiling:
            raise ValueError("model output policy is invalid")


@dataclass(frozen=True, slots=True)
class ThresholdPolicy:
    version: str
    lower_threshold: Decimal
    upper_threshold: Decimal

    def __post_init__(self) -> None:
        if not Decimal(0) <= self.lower_threshold < self.upper_threshold <= Decimal(1):
            raise ValueError("forecast thresholds are invalid")


class ForecastBand(StrEnum):
    LOWER = "lower"
    MIDDLE = "middle"
    UPPER = "upper"


@dataclass(frozen=True, slots=True)
class ForecastPrediction:
    model_version: str
    feature_registry_version: str
    threshold_policy_version: str
    feature_timestamp: datetime
    prediction_timestamp: datetime
    probability: Decimal
    confidence: Decimal
    band: ForecastBand
    reason_codes: tuple[str, ...]
    fallback_used: bool
    missing_features: frozenset[str]


def predict_conversion(
    observations: tuple[FeatureObservation, ...],
    model: ForecastModel,
    thresholds: ThresholdPolicy,
    *,
    feature_timestamp: datetime,
    prediction_timestamp: datetime,
) -> ForecastPrediction:
    if feature_timestamp.tzinfo is None or prediction_timestamp.tzinfo is None:
        raise ValueError("forecast timestamps must be timezone-aware")
    if feature_timestamp > prediction_timestamp:
        raise ValueError("feature timestamp cannot be after prediction time")
    supplied: dict[str, FeatureObservation] = {}
    registry = {feature.name: feature for feature in model.features}
    for observation in observations:
        if observation.name not in registry:
            raise ValueError("observation is outside the feature registry")
        if observation.observed_at > feature_timestamp:
            raise ValueError("future information cannot be used for prediction")
        if observation.name in supplied:
            raise ValueError("duplicate feature observation")
        supplied[observation.name] = observation
    missing: set[str] = set()
    contributions: list[tuple[str, Decimal]] = []
    logit = model.intercept
    for feature in model.features:
        feature_observation = supplied.get(feature.name)
        value = feature.fallback if feature_observation is None else feature_observation.value
        if feature_observation is None:
            missing.add(feature.name)
        if not feature.minimum <= value <= feature.maximum:
            raise ValueError("feature value falls outside registry bounds")
        normalized = (value - feature.minimum) / (feature.maximum - feature.minimum)
        contribution = normalized * model.coefficients[feature.name]
        logit += contribution
        contributions.append((feature.reason_code, contribution))
    bounded_logit = min(max(logit, model.logit_floor), model.logit_ceiling)
    probability = Decimal(1) / (Decimal(1) + (-bounded_logit).exp())
    missing_fraction = Decimal(len(missing)) / Decimal(len(model.features))
    confidence = max(
        Decimal(0), Decimal(1) - missing_fraction * model.missing_feature_confidence_penalty
    )
    if probability < thresholds.lower_threshold:
        band = ForecastBand.LOWER
    elif probability >= thresholds.upper_threshold:
        band = ForecastBand.UPPER
    else:
        band = ForecastBand.MIDDLE
    contributions.sort(key=lambda item: (-abs(item[1]), item[0]))
    reasons = tuple(item[0] for item in contributions[: model.maximum_reason_codes] if item[1])
    return ForecastPrediction(
        model.version,
        model.feature_registry_version,
        thresholds.version,
        feature_timestamp,
        prediction_timestamp,
        probability,
        confidence,
        band,
        reasons,
        bool(missing),
        frozenset(missing),
    )


@dataclass(frozen=True, slots=True)
class LabeledPrediction:
    probability: Decimal
    converted: bool
    predicted_at: datetime
    labeled_at: datetime

    def __post_init__(self) -> None:
        if not Decimal(0) <= self.probability <= Decimal(1):
            raise ValueError("probability must be between zero and one")
        if self.predicted_at.tzinfo is None or self.labeled_at.tzinfo is None:
            raise ValueError("evaluation timestamps must be timezone-aware")
        if self.labeled_at < self.predicted_at:
            raise ValueError("label cannot predate prediction")


@dataclass(frozen=True, slots=True)
class EvaluationPolicy:
    version: str
    minimum_sample_size: int
    maximum_brier_score: Decimal
    minimum_roc_auc: Decimal

    def __post_init__(self) -> None:
        if self.minimum_sample_size <= 0:
            raise ValueError("minimum evaluation sample size must be positive")
        if not Decimal(0) <= self.maximum_brier_score <= Decimal(1):
            raise ValueError("maximum Brier score must be between zero and one")
        if not Decimal(0) <= self.minimum_roc_auc <= Decimal(1):
            raise ValueError("minimum ROC AUC must be between zero and one")


@dataclass(frozen=True, slots=True)
class ForecastEvaluation:
    sample_size: int
    brier_score: Decimal | None
    roc_auc: Decimal | None
    meets_promotion_policy: bool
    reason: str
    policy_version: str


def _roc_auc(samples: tuple[LabeledPrediction, ...]) -> Decimal | None:
    positives = tuple(sample for sample in samples if sample.converted)
    negatives = tuple(sample for sample in samples if not sample.converted)
    if not positives or not negatives:
        return None
    wins = Decimal(0)
    for positive in positives:
        for negative in negatives:
            if positive.probability > negative.probability:
                wins += Decimal(1)
            elif positive.probability == negative.probability:
                wins += Decimal("0.5")
    return wins / Decimal(len(positives) * len(negatives))


def evaluate_forecast(
    samples: tuple[LabeledPrediction, ...], policy: EvaluationPolicy
) -> ForecastEvaluation:
    if len(samples) < policy.minimum_sample_size:
        return ForecastEvaluation(
            len(samples), None, None, False, "insufficient_sample", policy.version
        )
    brier = sum(
        ((sample.probability - Decimal(int(sample.converted))) ** 2 for sample in samples),
        start=Decimal(0),
    ) / Decimal(len(samples))
    roc_auc = _roc_auc(samples)
    passes = brier <= policy.maximum_brier_score and (
        roc_auc is not None and roc_auc >= policy.minimum_roc_auc
    )
    return ForecastEvaluation(
        len(samples),
        brier,
        roc_auc,
        passes,
        "promotion_thresholds_met" if passes else "promotion_thresholds_not_met",
        policy.version,
    )


def time_aware_split(
    samples: tuple[LabeledPrediction, ...],
    *,
    training_ends_at: datetime,
    validation_ends_at: datetime,
) -> tuple[
    tuple[LabeledPrediction, ...],
    tuple[LabeledPrediction, ...],
    tuple[LabeledPrediction, ...],
]:
    if training_ends_at >= validation_ends_at:
        raise ValueError("training cutoff must precede validation cutoff")
    ordered = sorted(samples, key=lambda item: item.predicted_at)
    training = tuple(item for item in ordered if item.predicted_at < training_ends_at)
    validation = tuple(
        item for item in ordered if training_ends_at <= item.predicted_at < validation_ends_at
    )
    testing = tuple(item for item in ordered if item.predicted_at >= validation_ends_at)
    return training, validation, testing
