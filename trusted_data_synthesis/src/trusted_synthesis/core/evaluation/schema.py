from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReleaseDecision(str, Enum):
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


class HardGateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    gate_id: str
    passed: bool
    details: tuple[str, ...] = ()


class DiagnosticQualityVector(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_validity: float = Field(ge=0, le=1)
    proof_graph_coverage: float = Field(ge=0, le=1)
    operation_replay: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)
    workflow_completeness: float = Field(ge=0, le=1)
    program_depth: int = Field(ge=1)


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
    hard_gates: tuple[HardGateResult, ...]
    required_check_manifest_hash: str
    diagnostic_vector: DiagnosticQualityVector
    dimensions: tuple[DimensionScore, ...]
    total_score: float = Field(ge=0, le=100)
    decision: ReleaseDecision
    fatal_failures: tuple[str, ...]
    evaluator_version: str
