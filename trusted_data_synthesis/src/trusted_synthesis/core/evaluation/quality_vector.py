from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseResult,
    ClauseSeverity,
    ContractQualityAssessment,
    QualityClause,
    QualityContract,
)
from trusted_synthesis.hashing import canonical_hash

QUALITY_VECTOR_VERSION = "quality_vector.v1"


class QualityDimension(str, Enum):
    EVIDENCE = "evidence"
    PROGRAM = "program"
    TRAJECTORY = "trajectory"
    CITATION = "citation"
    CLAIM = "claim"


class QualityDimensionScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension: QualityDimension
    applicable: bool
    score: float | None = Field(default=None, ge=0, le=1)
    clause_count: int = Field(ge=0)
    passed_clause_count: int = Field(ge=0)
    direct_failure_count: int = Field(ge=0)
    blocked_clause_count: int = Field(ge=0)
    failed_clause_ids: tuple[str, ...] = ()
    root_failure_clause_ids: tuple[str, ...] = ()


class QualityVectorPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = "quality_vector.default.v1"
    dimension_aliases: dict[QualityDimension, tuple[str, ...]] = Field(
        default_factory=lambda: {
            QualityDimension.EVIDENCE: (
                "evidence",
                "retrieval",
                "proof",
                "binding",
                "source_grounding",
            ),
            QualityDimension.PROGRAM: (
                "reasoning",
                "operation",
                "verification",
                "pattern",
                "difficulty",
                "curriculum",
            ),
            QualityDimension.TRAJECTORY: ("workflow", "tool_use"),
            QualityDimension.CITATION: ("citation",),
            QualityDimension.CLAIM: ("answer", "domain_semantics"),
        }
    )
    fatal_weight: float = Field(default=1, gt=0)
    quarantine_weight: float = Field(default=0.6, gt=0)
    diagnostic_weight: float = Field(default=0.25, gt=0)

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self, prefix="quality_vector_policy:")


class QualityVector(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    vector_id: str
    task_id: str
    trajectory_id: str
    assessment_id: str
    quality_contract_hash: str
    policy_hash: str
    dimensions: tuple[QualityDimensionScore, ...]
    overall_score: float = Field(ge=0, le=1)
    minimum_applicable_score: float = Field(ge=0, le=1)
    accepted_by_contract: bool
    version: str = QUALITY_VECTOR_VERSION

    def score_for(self, dimension: QualityDimension) -> float | None:
        return next(item.score for item in self.dimensions if item.dimension == dimension)


class QualityVectorCompiler:
    """Project authoritative clause results onto stable, domain-neutral dimensions."""

    def __init__(self, policy: QualityVectorPolicy | None = None) -> None:
        self._policy = policy or QualityVectorPolicy()
        self._dimension_by_alias = {
            alias: dimension
            for dimension, aliases in self._policy.dimension_aliases.items()
            for alias in aliases
        }

    @property
    def policy(self) -> QualityVectorPolicy:
        return self._policy

    def compile(
        self,
        contract: QualityContract,
        assessment: ContractQualityAssessment,
    ) -> QualityVector:
        if contract.contract_hash != assessment.quality_contract_hash:
            raise ValueError("assessment and quality contract hashes do not match")
        if contract.task_id != assessment.task_id:
            raise ValueError("assessment and quality contract task IDs do not match")
        clause_by_id = {item.clause_id: item for item in contract.clauses}
        result_by_id = {item.clause_id: item for item in assessment.clause_results}
        if set(clause_by_id) != set(result_by_id):
            raise ValueError("quality vector requires a result for every contract clause")
        assigned: dict[QualityDimension, list[tuple[QualityClause, ClauseResult]]] = {
            dimension: [] for dimension in QualityDimension
        }
        unknown: set[str] = set()
        for clause in contract.clauses:
            dimensions: set[QualityDimension] = set()
            for alias in clause.diagnostic_dimensions:
                dimension = self._dimension_by_alias.get(alias)
                if dimension is None:
                    unknown.add(alias)
                else:
                    dimensions.add(dimension)
            if not dimensions:
                unknown.add(f"clause:{clause.clause_kind}")
            for dimension in dimensions:
                assigned[dimension].append((clause, result_by_id[clause.clause_id]))
        if unknown:
            raise ValueError(
                f"quality vector policy does not map diagnostic dimensions: {sorted(unknown)}"
            )
        root_ids = set(assessment.root_failure_clause_ids)
        scores = tuple(
            self._score_dimension(dimension, tuple(assigned[dimension]), root_ids)
            for dimension in QualityDimension
        )
        applicable_scores = tuple(
            item.score for item in scores if item.applicable and item.score is not None
        )
        if not applicable_scores:
            raise ValueError("quality vector has no applicable dimensions")
        identity = {
            "task_id": assessment.task_id,
            "trajectory_id": assessment.trajectory_id,
            "assessment_id": assessment.assessment_id,
            "quality_contract_hash": contract.contract_hash,
            "policy_hash": self._policy.policy_hash,
            "version": QUALITY_VECTOR_VERSION,
        }
        return QualityVector(
            vector_id=canonical_hash(identity, prefix="quality_vector:"),
            task_id=assessment.task_id,
            trajectory_id=assessment.trajectory_id,
            assessment_id=assessment.assessment_id,
            quality_contract_hash=contract.contract_hash,
            policy_hash=self._policy.policy_hash,
            dimensions=scores,
            overall_score=sum(applicable_scores) / len(applicable_scores),
            minimum_applicable_score=min(applicable_scores),
            accepted_by_contract=assessment.decision.value == "accepted",
        )

    def _score_dimension(
        self,
        dimension: QualityDimension,
        items: tuple[tuple[QualityClause, ClauseResult], ...],
        root_ids: set[str],
    ) -> QualityDimensionScore:
        if not items:
            return QualityDimensionScore(
                dimension=dimension,
                applicable=False,
                clause_count=0,
                passed_clause_count=0,
                direct_failure_count=0,
                blocked_clause_count=0,
            )
        total_weight = sum(self._severity_weight(clause.severity) for clause, _ in items)
        passed_weight = sum(
            self._severity_weight(clause.severity)
            for clause, result in items
            if result.passed
        )
        failures = tuple(result.clause_id for _, result in items if not result.passed)
        return QualityDimensionScore(
            dimension=dimension,
            applicable=True,
            score=passed_weight / total_weight,
            clause_count=len(items),
            passed_clause_count=sum(result.passed for _, result in items),
            direct_failure_count=sum(
                not result.passed and result.executed for _, result in items
            ),
            blocked_clause_count=sum(not result.executed for _, result in items),
            failed_clause_ids=failures,
            root_failure_clause_ids=tuple(item for item in failures if item in root_ids),
        )

    def _severity_weight(self, severity: ClauseSeverity) -> float:
        if severity == ClauseSeverity.FATAL:
            return self._policy.fatal_weight
        if severity == ClauseSeverity.QUARANTINE:
            return self._policy.quarantine_weight
        return self._policy.diagnostic_weight
