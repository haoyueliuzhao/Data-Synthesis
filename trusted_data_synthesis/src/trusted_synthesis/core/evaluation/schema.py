from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReleaseDecision(str, Enum):
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


class DimensionScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    checks: tuple[str, ...]


class QualityAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assessment_id: str
    task_id: str
    trajectory_id: str
    dimensions: tuple[DimensionScore, ...]
    total_score: float = Field(ge=0, le=100)
    decision: ReleaseDecision
    fatal_failures: tuple[str, ...]
    evaluator_version: str
