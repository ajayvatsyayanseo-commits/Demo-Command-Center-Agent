from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.config.settings import Settings, get_settings
from demo_command_center.infrastructure.audit import append_audit_event
from demo_command_center.infrastructure.database.models import (
    ConversionPrediction,
    DemoCase,
    DemoOutcome,
    ModelEvaluation,
    ModelVersion,
)
from demo_command_center.infrastructure.database.session import build_database_resources


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    subject_version: str
    sample_size: int
    brier_score: float | None
    calibration_error: float | None
    status: str
    threshold_breaches: tuple[str, ...]


async def evaluate_forecasting_drift(
    sessions: async_sessionmaker[AsyncSession],
    *,
    policy_reference: str,
    window_days: int,
    minimum_samples: int,
    brier_threshold: float,
    calibration_error_threshold: float,
    positive_outcomes: frozenset[str],
    tenant_id: str,
    audit_hash_key: str,
    now: datetime | None = None,
) -> EvaluationResult:
    if (
        window_days <= 0
        or minimum_samples <= 0
        or not 0 < brier_threshold <= 1
        or not 0 < calibration_error_threshold <= 1
        or not positive_outcomes
    ):
        raise ValueError("model evaluation policy is invalid")
    effective_now = (now or datetime.now(UTC)).replace(minute=0, second=0, microsecond=0)
    if effective_now.tzinfo is None:
        raise ValueError("evaluation timestamp must be timezone-aware")
    window_start = effective_now - timedelta(days=window_days)
    async with sessions() as session, session.begin():
        model = await session.scalar(
            select(ModelVersion)
            .where(ModelVersion.promotion_status.in_({"active", "promoted"}))
            .order_by(ModelVersion.promoted_at.desc().nullslast(), ModelVersion.created_at.desc())
            .limit(1)
        )
        subject_version = model.version if model is not None else "deterministic-fallback"
        latest_outcome_at = (
            select(func.max(DemoOutcome.occurred_at))
            .where(DemoOutcome.demo_case_id == ConversionPrediction.demo_case_id)
            .correlate(ConversionPrediction)
            .scalar_subquery()
        )
        rows = (
            await session.execute(
                select(ConversionPrediction.probability, DemoOutcome.outcome)
                .join(
                    DemoOutcome,
                    DemoOutcome.demo_case_id == ConversionPrediction.demo_case_id,
                )
                .join(DemoCase, DemoCase.id == ConversionPrediction.demo_case_id)
                .where(
                    DemoCase.tenant_id == tenant_id,
                    ConversionPrediction.feature_timestamp >= window_start,
                    ConversionPrediction.feature_timestamp < effective_now,
                    ConversionPrediction.model_version == subject_version,
                    DemoOutcome.occurred_at == latest_outcome_at,
                    DemoOutcome.disputed.is_(False),
                )
            )
        ).all()
        sample_size = len(rows)
        brier_score: float | None = None
        calibration_error: float | None = None
        breaches: list[str] = []
        if sample_size >= minimum_samples:
            probabilities = [float(row.probability) for row in rows]
            labels = [1.0 if row.outcome in positive_outcomes else 0.0 for row in rows]
            brier_score = (
                sum(
                    (probability - label) ** 2
                    for probability, label in zip(probabilities, labels, strict=True)
                )
                / sample_size
            )
            calibration_error = abs(sum(probabilities) / sample_size - sum(labels) / sample_size)
            if brier_score > brier_threshold:
                breaches.append("BRIER_SCORE_THRESHOLD")
            if calibration_error > calibration_error_threshold:
                breaches.append("CALIBRATION_ERROR_THRESHOLD")
            status = "breach" if breaches else "passed"
        else:
            status = "insufficient_data"
        metrics: dict[str, float | int | None] = {
            "brier_score": brier_score,
            "calibration_error": calibration_error,
            "minimum_samples": minimum_samples,
            "brier_threshold": brier_threshold,
            "calibration_error_threshold": calibration_error_threshold,
        }
        existing = await session.scalar(
            select(ModelEvaluation).where(
                ModelEvaluation.tenant_id == tenant_id,
                ModelEvaluation.evaluation_type == "forecast_calibration",
                ModelEvaluation.subject_version == subject_version,
                ModelEvaluation.policy_reference == policy_reference,
                ModelEvaluation.window_end == effective_now,
            )
        )
        if existing is None:
            session.add(
                ModelEvaluation(
                    tenant_id=tenant_id,
                    evaluation_type="forecast_calibration",
                    subject_version=subject_version,
                    policy_reference=policy_reference,
                    window_start=window_start,
                    window_end=effective_now,
                    sample_size=sample_size,
                    metrics=metrics,
                    threshold_breaches=breaches,
                    status=status,
                    evaluated_at=effective_now,
                )
            )
        await append_audit_event(
            session,
            tenant_id=tenant_id,
            event_type="evaluation.forecast.completed.v1",
            actor_type="scheduled_task",
            actor_ref="model-evaluation",
            correlation_id=str(uuid4()),
            details={
                "policy_reference": policy_reference,
                "subject_version": subject_version,
                "sample_size": sample_size,
                "status": status,
                "threshold_breaches": breaches,
            },
            hash_key=audit_hash_key,
            occurred_at=effective_now,
        )
        return EvaluationResult(
            subject_version=subject_version,
            sample_size=sample_size,
            brier_score=brier_score,
            calibration_error=calibration_error,
            status=status,
            threshold_breaches=tuple(breaches),
        )


async def _run(settings: Settings) -> EvaluationResult:
    tenant_id = settings.tenant_id
    policy = settings.evaluation_policy_reference
    window_days = settings.evaluation_window_days
    minimum_samples = settings.evaluation_min_samples
    brier_threshold = settings.forecast_brier_threshold
    calibration_threshold = settings.forecast_calibration_error_threshold
    audit_hash_key = settings.audit_hash_key.get_secret_value()
    if (
        settings.provider_profile != "real"
        or not settings.model_evaluation_enabled
        or not tenant_id
        or policy is None
        or window_days is None
        or minimum_samples is None
        or brier_threshold is None
        or calibration_threshold is None
        or not audit_hash_key
        or not settings.evaluation_positive_outcomes
    ):
        raise RuntimeError("model evaluation is disabled or its threshold policy is incomplete")
    database = build_database_resources(settings)
    try:
        return await evaluate_forecasting_drift(
            database.sessions,
            policy_reference=policy,
            window_days=window_days,
            minimum_samples=minimum_samples,
            brier_threshold=brier_threshold,
            calibration_error_threshold=calibration_threshold,
            positive_outcomes=frozenset(settings.evaluation_positive_outcomes),
            tenant_id=tenant_id,
            audit_hash_key=audit_hash_key,
        )
    finally:
        await database.close()


def main() -> None:
    argparse.ArgumentParser(description="Evaluate configured forecasting drift").parse_args()
    result = asyncio.run(_run(get_settings()))
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
