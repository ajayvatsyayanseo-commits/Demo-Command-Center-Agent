from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from demo_command_center.modules.success_forecasting.domain.scoring import (
    FeatureObservation,
    ForecastModel,
    ForecastPrediction,
    ThresholdPolicy,
    predict_conversion,
)


@dataclass(frozen=True, slots=True)
class DeterministicForecastUseCase:
    model: ForecastModel
    thresholds: ThresholdPolicy

    def execute(
        self,
        observations: tuple[FeatureObservation, ...],
        *,
        feature_timestamp: datetime,
        prediction_timestamp: datetime,
    ) -> ForecastPrediction:
        return predict_conversion(
            observations,
            self.model,
            self.thresholds,
            feature_timestamp=feature_timestamp,
            prediction_timestamp=prediction_timestamp,
        )
