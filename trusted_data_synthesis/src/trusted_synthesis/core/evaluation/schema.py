from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class ReleaseDecision(str, Enum):
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


class GateScope(str, Enum):
    UNIVERSAL = "universal"
    DOMAIN = "domain"


class HardGateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    gate_id: str
    scope: GateScope = GateScope.UNIVERSAL
    passed: bool
    details: tuple[str, ...] = ()


class DiagnosticQualityVector(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_validity: float = Field(ge=0, le=1)
    proof_graph_coverage: float = Field(ge=0, le=1)
    operation_replay: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)
    workflow_completeness: float = Field(ge=0, le=1)
    execution_coverage: float = Field(default=1.0, ge=0, le=1)
    operation_grounding: float = Field(default=1.0, ge=0, le=1)
    tool_necessity: float = Field(default=1.0, ge=0, le=1)
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
    universal_gates: tuple[HardGateResult, ...] = ()
    domain_gates: tuple[HardGateResult, ...] = ()
    required_check_manifest_hash: str
    diagnostic_vector: DiagnosticQualityVector
    dimensions: tuple[DimensionScore, ...]
    total_score: float = Field(ge=0, le=100)
    decision: ReleaseDecision
    fatal_failures: tuple[str, ...]
    failed_check_ids: tuple[str, ...] = ()
    check_failure_details: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    evaluator_version: str
    schema_version: str = "quality_assessment.v2"

    @model_validator(mode="after")
    def validate_identity(self) -> QualityAssessment:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"assessment_id"}),
            prefix="quality_assessment:",
        )
        if self.assessment_id != expected:
            raise ValueError("quality assessment content identity is invalid")
        return self

    @property
    def assessment_hash(self) -> str:
        return canonical_hash(self, prefix="quality_assessment_content:")
