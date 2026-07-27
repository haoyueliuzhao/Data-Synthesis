from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.quality_vector import QualityVector
from trusted_synthesis.hashing import canonical_hash

QUALITY_CRITIC_DATASET_VERSION = "quality_critic_dataset.v1"


class AnnotationSource(str, Enum):
    CONTRACT = "contract"
    HUMAN = "human"
    MODEL_ADVISORY = "model_advisory"


class AcceptabilityLabel(str, Enum):
    ACCEPT = "accept"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class FailureLocationLabel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    location_type: str = Field(min_length=1)
    location_ref: str = Field(min_length=1)


class QualityAnnotation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    annotation_id: str
    source: AnnotationSource
    acceptability: AcceptabilityLabel
    failure_families: tuple[str, ...] = ()
    root_locations: tuple[FailureLocationLabel, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)
    annotator_id: str | None = None
    model_id: str | None = None
    source_assessment_id: str | None = None
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_source_identity(self) -> QualityAnnotation:
        if self.source == AnnotationSource.HUMAN:
            if not self.annotator_id or self.model_id:
                raise ValueError("human annotations require an annotator and cannot name a model")
        elif self.source == AnnotationSource.MODEL_ADVISORY:
            if not self.model_id or self.annotator_id:
                raise ValueError("model advisory annotations require a model identity")
        elif not self.source_assessment_id:
            raise ValueError("contract annotations require a source assessment")
        return self

    @property
    def counts_as_human(self) -> bool:
        return self.source == AnnotationSource.HUMAN


class QualityCriticExample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    example_id: str
    task_id: str
    trajectory_id: str
    domain: str
    retrieval_track: str
    planning_track: str
    candidate_source: str
    critic_input: dict[str, Any]
    contract_annotation: QualityAnnotation
    quality_vector: QualityVector
    advisory_annotations: tuple[QualityAnnotation, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = QUALITY_CRITIC_DATASET_VERSION


class QualityCriticPrediction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prediction_id: str
    example_id: str
    model_id: str
    model_manifest_hash: str
    accept_probability: float = Field(ge=0, le=1)
    predicted_acceptability: AcceptabilityLabel
    failure_families: tuple[str, ...] = ()
    root_locations: tuple[FailureLocationLabel, ...] = ()
    dimension_scores: dict[str, float] = Field(default_factory=dict)


class QualityCriticDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    examples: tuple[QualityCriticExample, ...]
    contract_positive_count: int = Field(ge=0)
    contract_negative_count: int = Field(ge=0)
    real_agent_count: int = Field(ge=0)
    counterfactual_count: int = Field(ge=0)
    human_annotation_count: int = Field(ge=0)
    model_advisory_count: int = Field(ge=0)
    schema_version: str = QUALITY_CRITIC_DATASET_VERSION

    @property
    def dataset_hash(self) -> str:
        return canonical_hash(self, prefix="quality_critic_dataset:")


class AlignmentReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str
    example_count: int = Field(ge=0)
    human_annotation_count: int = Field(ge=0)
    model_advisory_count: int = Field(ge=0)
    human_contract_acceptability_agreement: float | None = Field(default=None, ge=0, le=1)
    model_contract_acceptability_agreement: float | None = Field(default=None, ge=0, le=1)
    human_failure_classification_f1: float | None = Field(default=None, ge=0, le=1)
    model_failure_classification_f1: float | None = Field(default=None, ge=0, le=1)
    human_root_localization_rate: float | None = Field(default=None, ge=0, le=1)
    model_root_localization_rate: float | None = Field(default=None, ge=0, le=1)
    human_target_met: bool | None = None
    model_advisory_target_met: bool | None = None
    notes: tuple[str, ...] = ()
