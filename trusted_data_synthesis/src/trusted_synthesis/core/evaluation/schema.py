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
        gate_ids = tuple(gate.gate_id for gate in self.hard_gates)
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("quality assessment repeats a hard Gate identity")
        expected_universal = tuple(
            gate for gate in self.hard_gates if gate.scope == GateScope.UNIVERSAL
        )
        expected_domain = tuple(gate for gate in self.hard_gates if gate.scope == GateScope.DOMAIN)
        if self.universal_gates != expected_universal or self.domain_gates != expected_domain:
            raise ValueError("quality assessment Gate scope partitions are invalid")
        expected_fatal = tuple(gate.gate_id for gate in self.hard_gates if not gate.passed)
        if self.fatal_failures != expected_fatal:
            raise ValueError("quality assessment fatal failures disagree with hard Gates")
        dimension_ids = tuple(item.dimension for item in self.dimensions)
        if len(dimension_ids) != len(set(dimension_ids)):
            raise ValueError("quality assessment repeats a score dimension")
        if abs(sum(item.weight for item in self.dimensions) - 1.0) > 1e-9:
            raise ValueError("quality assessment dimension weights do not sum to one")
        expected_total = round(
            sum(item.score * item.weight for item in self.dimensions),
            4,
        )
        if self.total_score != expected_total:
            raise ValueError("quality assessment total score is not derived from dimensions")
        expected_decision = (
            ReleaseDecision.REJECTED
            if expected_fatal
            else ReleaseDecision.ACCEPTED
            if expected_total >= 90
            else ReleaseDecision.QUARANTINED
        )
        if self.decision != expected_decision:
            raise ValueError("quality assessment decision is not derived from Gates and score")
        if len(self.failed_check_ids) != len(set(self.failed_check_ids)):
            raise ValueError("quality assessment repeats a failed check identity")
        if not set(self.check_failure_details).issubset(self.failed_check_ids):
            raise ValueError("quality assessment failure details reference a passing check")
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
