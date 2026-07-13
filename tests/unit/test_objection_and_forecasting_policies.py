from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from demo_command_center.modules.objection_extraction.application.fallback import (
    DeterministicObjectionFallback,
)
from demo_command_center.modules.objection_extraction.domain.pipeline import (
    EvidenceKind,
    FallbackRule,
    Objection,
    ObjectionEvidence,
    ObjectionExpression,
    ObjectionPolicy,
    permitted_evidence,
    validate_extracted_objection,
)
from demo_command_center.modules.success_forecasting.application.predict import (
    DeterministicForecastUseCase,
)
from demo_command_center.modules.success_forecasting.domain.scoring import (
    EvaluationPolicy,
    FeatureDefinition,
    FeatureObservation,
    ForecastBand,
    ForecastModel,
    LabeledPrediction,
    ThresholdPolicy,
    evaluate_forecast,
    time_aware_split,
)

NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)


def _objection_policy() -> ObjectionPolicy:
    return ObjectionPolicy(
        "taxonomy-v2",
        frozenset({"price", "schedule"}),
        (
            FallbackRule(
                "explicit-price",
                "price",
                ("too expensive",),
                ObjectionExpression.EXPLICIT,
                "price concern",
                "budget fit",
                "may need a different plan",
                "Which approved plan range works for you?",
                Decimal("0.95"),
            ),
            FallbackRule(
                "implicit-schedule",
                "schedule",
                ("let me check",),
                ObjectionExpression.IMPLICIT,
                "possible schedule concern",
                "timing uncertainty",
                "may simply need time to decide",
                "Would another approved time help?",
                Decimal("0.55"),
            ),
        ),
        Decimal("0.7"),
        Decimal("0.6"),
        3,
        "deterministic-fallback-v1",
        "none",
    )


def _model() -> ForecastModel:
    return ForecastModel(
        "logistic-v1",
        "features-v3",
        Decimal("-1"),
        {"quality": Decimal("2"), "attendance": Decimal("1")},
        (
            FeatureDefinition(
                "quality", Decimal("0"), Decimal("1"), Decimal("0.4"), "quality_signal"
            ),
            FeatureDefinition(
                "attendance", Decimal("0"), Decimal("1"), Decimal("0"), "attendance_signal"
            ),
        ),
        Decimal("0.8"),
        2,
        Decimal("-10"),
        Decimal("10"),
    )


def _thresholds() -> ThresholdPolicy:
    return ThresholdPolicy("strategy-v1", Decimal("0.3"), Decimal("0.7"))


def test_deterministic_objection_fallback_is_grounded_and_consent_filtered() -> None:
    evidence = (
        ObjectionEvidence(
            "message:1", EvidenceKind.WHATSAPP_MESSAGE, "This is too expensive", True
        ),
        ObjectionEvidence(
            "transcript:1",
            EvidenceKind.CONSENTED_TRANSCRIPT,
            "let me check",
            True,
            transcription_consent=False,
        ),
        ObjectionEvidence("note:blocked", EvidenceKind.APPROVED_NOTE, "too expensive", False),
    )
    objections = DeterministicObjectionFallback(_objection_policy()).execute(evidence)
    assert len(objections) == 1
    assert objections[0].category == "price"
    assert objections[0].evidence_refs == ("message:1",)
    assert not objections[0].requires_human_review
    assert permitted_evidence(evidence, _objection_policy()) == (evidence[0],)


def test_implicit_low_confidence_is_reviewed_and_no_evidence_means_no_objection() -> None:
    objections = DeterministicObjectionFallback(_objection_policy()).execute(
        (ObjectionEvidence("feedback:1", EvidenceKind.POST_DEMO_FEEDBACK, "Let me check", True),)
    )
    assert len(objections) == 1
    assert objections[0].expression is ObjectionExpression.IMPLICIT
    assert objections[0].requires_human_review
    assert DeterministicObjectionFallback(_objection_policy()).execute(()) == ()


def test_objection_validator_rejects_ungrounded_or_unknown_results() -> None:
    valid = DeterministicObjectionFallback(_objection_policy()).execute(
        (ObjectionEvidence("message:1", EvidenceKind.WHATSAPP_MESSAGE, "too expensive", True),)
    )[0]
    assert (
        validate_extracted_objection(valid, frozenset({"message:1"}), _objection_policy()) == valid
    )
    with pytest.raises(ValueError, match="absent or ungrounded"):
        validate_extracted_objection(valid, frozenset(), _objection_policy())
    unknown = Objection(
        valid.objection_id,
        "invented",
        valid.expression,
        valid.normalized_objection,
        valid.root_cause,
        valid.evidence_refs,
        valid.confidence,
        valid.alternative_interpretation,
        valid.recommended_next_question,
        False,
        valid.prompt_version,
        valid.model_version,
    )
    with pytest.raises(ValueError, match="taxonomy"):
        validate_extracted_objection(unknown, frozenset({"message:1"}), _objection_policy())


def test_forecast_is_deterministic_versioned_and_uses_only_point_in_time_features() -> None:
    observations = (
        FeatureObservation("quality", Decimal("0.9"), NOW - timedelta(minutes=2)),
        FeatureObservation("attendance", Decimal("1"), NOW - timedelta(minutes=1)),
    )
    use_case = DeterministicForecastUseCase(_model(), _thresholds())
    first = use_case.execute(
        observations, feature_timestamp=NOW, prediction_timestamp=NOW + timedelta(seconds=1)
    )
    second = use_case.execute(
        observations, feature_timestamp=NOW, prediction_timestamp=NOW + timedelta(seconds=1)
    )
    assert first == second
    assert first.band is ForecastBand.UPPER
    assert first.model_version == "logistic-v1"
    assert first.reason_codes == ("quality_signal", "attendance_signal")
    assert first.confidence == Decimal(1)
    assert not first.fallback_used


def test_forecast_fallback_marks_missing_features_and_rejects_leakage() -> None:
    use_case = DeterministicForecastUseCase(_model(), _thresholds())
    result = use_case.execute((), feature_timestamp=NOW, prediction_timestamp=NOW)
    assert result.fallback_used
    assert result.missing_features == frozenset({"quality", "attendance"})
    assert result.confidence == Decimal("0.2")

    with pytest.raises(ValueError, match="future information"):
        use_case.execute(
            (FeatureObservation("quality", Decimal("0.5"), NOW + timedelta(seconds=1)),),
            feature_timestamp=NOW,
            prediction_timestamp=NOW,
        )
    with pytest.raises(ValueError, match="outside the feature registry"):
        use_case.execute(
            (FeatureObservation("payment_status", Decimal(1), NOW),),
            feature_timestamp=NOW,
            prediction_timestamp=NOW,
        )


def test_forecast_evaluation_and_time_aware_split() -> None:
    samples = (
        LabeledPrediction(Decimal("0.9"), True, NOW - timedelta(days=3), NOW),
        LabeledPrediction(Decimal("0.8"), True, NOW - timedelta(days=2), NOW),
        LabeledPrediction(Decimal("0.2"), False, NOW - timedelta(days=1), NOW),
        LabeledPrediction(Decimal("0.1"), False, NOW, NOW),
    )
    policy = EvaluationPolicy("promotion-v1", 4, Decimal("0.1"), Decimal("0.8"))
    evaluation = evaluate_forecast(samples, policy)
    assert evaluation.meets_promotion_policy
    assert evaluation.roc_auc == Decimal(1)
    assert evaluation.brier_score == Decimal("0.025")

    insufficient = evaluate_forecast(samples[:2], policy)
    assert not insufficient.meets_promotion_policy
    assert insufficient.reason == "insufficient_sample"
    train, validation, test = time_aware_split(
        samples,
        training_ends_at=NOW - timedelta(days=2),
        validation_ends_at=NOW,
    )
    assert len(train) == 1 and len(validation) == 2 and len(test) == 1


def test_forecast_evaluation_with_single_class_does_not_claim_auc() -> None:
    samples = (
        LabeledPrediction(Decimal("0.8"), True, NOW - timedelta(days=1), NOW),
        LabeledPrediction(Decimal("0.9"), True, NOW, NOW),
    )
    result = evaluate_forecast(samples, EvaluationPolicy("promotion-v1", 2, Decimal(1), Decimal(0)))
    assert result.roc_auc is None
    assert not result.meets_promotion_policy
