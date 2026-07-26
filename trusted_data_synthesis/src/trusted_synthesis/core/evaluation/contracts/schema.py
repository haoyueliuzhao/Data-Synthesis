from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.hashing import canonical_hash


class ClauseScope(str, Enum):
    UNIVERSAL = "universal"
    DOMAIN = "domain"


class ClauseSeverity(str, Enum):
    FATAL = "fatal"
    QUARANTINE = "quarantine"
    DIAGNOSTIC = "diagnostic"


class GateAggregation(str, Enum):
    ALL = "all"
    ANY = "any"
    THRESHOLD = "threshold"


class ClauseTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_type: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    json_path: str | None = None


class QualityClause(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    clause_id: str = Field(min_length=1)
    clause_kind: str = Field(min_length=1)
    scope: ClauseScope
    severity: ClauseSeverity
    target: ClauseTarget
    verifier_id: str = Field(min_length=1)
    verifier_version: str = Field(min_length=1)
    expected_ref: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    failure_family: str = Field(min_length=1)
    diagnostic_dimensions: tuple[str, ...] = ()


class QualityGateSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: str = Field(min_length=1)
    scope: ClauseScope
    clause_ids: tuple[str, ...] = Field(min_length=1)
    aggregation: GateAggregation = GateAggregation.ALL
    threshold: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_aggregation(self) -> QualityGateSpec:
        if self.aggregation == GateAggregation.THRESHOLD and self.threshold is None:
            raise ValueError("threshold aggregation requires a threshold")
        if self.aggregation != GateAggregation.THRESHOLD and self.threshold is not None:
            raise ValueError("threshold is only valid for threshold aggregation")
        return self


class QualityContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    clauses: tuple[QualityClause, ...] = Field(min_length=1)
    gates: tuple[QualityGateSpec, ...] = Field(min_length=1)
    contract_hash: str = Field(min_length=1)
    verifier_manifest_hash: str = Field(min_length=1)
    domain_provider_id: str | None = None
    domain_provider_version: str | None = None
    schema_version: str = "quality_contract.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> QualityContract:
        clause_ids = [item.clause_id for item in self.clauses]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError("quality contract contains duplicate clause IDs")
        gate_ids = [item.gate_id for item in self.gates]
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("quality contract contains duplicate gate IDs")
        known: set[str] = set()
        for clause in self.clauses:
            unknown_dependencies = set(clause.dependencies) - known
            if unknown_dependencies:
                raise ValueError(
                    f"quality clause dependencies are not topologically ordered: "
                    f"{sorted(unknown_dependencies)}"
                )
            known.add(clause.clause_id)
        referenced = {clause_id for gate in self.gates for clause_id in gate.clause_ids}
        unknown_references = referenced - set(clause_ids)
        if unknown_references:
            raise ValueError(
                f"quality gates reference unknown clauses: {sorted(unknown_references)}"
            )
        unassigned = set(clause_ids) - referenced
        if unassigned:
            raise ValueError(f"quality clauses are not assigned to a gate: {sorted(unassigned)}")
        if (self.domain_provider_id is None) != (self.domain_provider_version is None):
            raise ValueError("domain quality provider ID and version must be frozen together")
        expected_id, expected_hash = quality_contract_hashes(
            task_id=self.task_id,
            compiler_version=self.compiler_version,
            clauses=self.clauses,
            gates=self.gates,
            verifier_manifest_hash=self.verifier_manifest_hash,
            domain_provider_id=self.domain_provider_id,
            domain_provider_version=self.domain_provider_version,
            schema_version=self.schema_version,
        )
        if self.contract_id != expected_id or self.contract_hash != expected_hash:
            raise ValueError("quality contract identity or hash is invalid")
        return self

    @property
    def domain_provider_identity(self) -> tuple[str, str] | None:
        if self.domain_provider_id is None:
            return None
        if self.domain_provider_version is None:
            raise ValueError("domain quality provider version is not frozen")
        return self.domain_provider_id, self.domain_provider_version


class ClauseResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    clause_id: str
    executed: bool
    passed: bool
    observed_digest: str | None = None
    expected_digest: str | None = None
    failure_code: str | None = None
    location_type: str | None = None
    location_ref: str | None = None
    details: tuple[str, ...] = ()


class QualityGateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: str
    scope: ClauseScope
    passed: bool
    passed_clause_count: int = Field(ge=0)
    clause_count: int = Field(ge=1)
    failed_clause_ids: tuple[str, ...] = ()


class ContractQualityAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assessment_id: str
    task_id: str
    trajectory_id: str
    quality_contract_id: str
    quality_contract_hash: str
    clause_results: tuple[ClauseResult, ...]
    gate_results: tuple[QualityGateResult, ...]
    decision: ReleaseDecision
    failed_clause_ids: tuple[str, ...] = ()
    unexecuted_clause_ids: tuple[str, ...] = ()
    root_failure_clause_ids: tuple[str, ...] = ()
    fatal_failure_gate_ids: tuple[str, ...] = ()
    runtime_version: str


class DecisionParityReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    parity_id: str
    task_id: str
    trajectory_id: str
    legacy_assessment_id: str
    contract_assessment_id: str
    legacy_decision: ReleaseDecision
    contract_decision: ReleaseDecision
    decisions_match: bool


def make_quality_clause(
    *,
    task_id: str,
    clause_kind: str,
    scope: ClauseScope,
    severity: ClauseSeverity,
    target: ClauseTarget,
    verifier_id: str,
    verifier_version: str,
    expected_ref: str | None = None,
    parameters: dict[str, Any] | None = None,
    dependencies: tuple[str, ...] = (),
    failure_family: str,
    diagnostic_dimensions: tuple[str, ...] = (),
) -> QualityClause:
    identity = {
        "task_id": task_id,
        "clause_kind": clause_kind,
        "scope": scope.value,
        "severity": severity.value,
        "target": target.model_dump(mode="json", exclude_none=True),
        "verifier_id": verifier_id,
        "verifier_version": verifier_version,
        "expected_ref": expected_ref,
        "parameters": parameters or {},
        "dependencies": dependencies,
        "failure_family": failure_family,
        "diagnostic_dimensions": diagnostic_dimensions,
    }
    return QualityClause(
        clause_id=canonical_hash(identity, prefix="quality_clause:"),
        clause_kind=clause_kind,
        scope=scope,
        severity=severity,
        target=target,
        verifier_id=verifier_id,
        verifier_version=verifier_version,
        expected_ref=expected_ref,
        parameters=parameters or {},
        dependencies=dependencies,
        failure_family=failure_family,
        diagnostic_dimensions=diagnostic_dimensions,
    )


def make_quality_contract(
    *,
    task_id: str,
    compiler_version: str,
    clauses: tuple[QualityClause, ...],
    gates: tuple[QualityGateSpec, ...],
    verifier_manifest_hash: str,
    domain_provider_id: str | None = None,
    domain_provider_version: str | None = None,
) -> QualityContract:
    contract_id, contract_hash = quality_contract_hashes(
        task_id=task_id,
        compiler_version=compiler_version,
        clauses=clauses,
        gates=gates,
        verifier_manifest_hash=verifier_manifest_hash,
        domain_provider_id=domain_provider_id,
        domain_provider_version=domain_provider_version,
        schema_version="quality_contract.v1",
    )
    return QualityContract(
        contract_id=contract_id,
        task_id=task_id,
        compiler_version=compiler_version,
        clauses=clauses,
        gates=gates,
        contract_hash=contract_hash,
        verifier_manifest_hash=verifier_manifest_hash,
        domain_provider_id=domain_provider_id,
        domain_provider_version=domain_provider_version,
    )


def quality_contract_hashes(
    *,
    task_id: str,
    compiler_version: str,
    clauses: tuple[QualityClause, ...],
    gates: tuple[QualityGateSpec, ...],
    verifier_manifest_hash: str,
    domain_provider_id: str | None,
    domain_provider_version: str | None,
    schema_version: str,
) -> tuple[str, str]:
    identity = {
        "task_id": task_id,
        "compiler_version": compiler_version,
        "clauses": [item.model_dump(mode="json", exclude_none=True) for item in clauses],
        "gates": [item.model_dump(mode="json", exclude_none=True) for item in gates],
        "verifier_manifest_hash": verifier_manifest_hash,
        "domain_provider_id": domain_provider_id,
        "domain_provider_version": domain_provider_version,
        "schema_version": schema_version,
    }
    return (
        canonical_hash(identity, prefix="quality_contract:"),
        canonical_hash(identity, prefix="quality_contract_hash:"),
    )
