from __future__ import annotations

from typing import Protocol

from trusted_synthesis.core.evaluation.critic.schema import (
    AnnotationSource,
    QualityAnnotation,
    QualityCriticExample,
    QualityCriticPrediction,
)
from trusted_synthesis.hashing import canonical_hash


class QualityCritic(Protocol):
    def predict(self, example: QualityCriticExample) -> QualityCriticPrediction: ...


def prediction_as_advisory_annotation(
    prediction: QualityCriticPrediction,
) -> QualityAnnotation:
    identity = {
        "prediction_id": prediction.prediction_id,
        "model_id": prediction.model_id,
        "purpose": "model_advisory_only",
    }
    return QualityAnnotation(
        annotation_id=canonical_hash(identity, prefix="model_advisory_annotation:"),
        source=AnnotationSource.MODEL_ADVISORY,
        acceptability=prediction.predicted_acceptability,
        failure_families=prediction.failure_families,
        root_locations=prediction.root_locations,
        confidence=max(
            prediction.accept_probability,
            1 - prediction.accept_probability,
        ),
        model_id=prediction.model_id,
        notes=("Model advisory labels do not count as human calibration.",),
    )
