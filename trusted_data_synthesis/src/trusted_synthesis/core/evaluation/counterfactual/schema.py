from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.mutations.schema import MutationFamily
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


class CounterfactualMutationDraft(BaseModel):
    """Operator-produced parameters before the planner binds contract lineage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameters: dict[str, Any] = Field(default_factory=dict)
    allowed_json_path_prefixes: tuple[str, ...] = Field(min_length=1)


class CounterfactualOpportunity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    opportunity_id: str
    source_sample_id: str
    source_certificate_hash: str
    source_trajectory_id: str
    quality_contract_hash: str
    source_clause_id: str
    source_clause_kind: str
    mutation_family: MutationFamily
    mutation_operator_id: str
    mutation_operator_version: str
    target_object_type: str
    target_object_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    allowed_json_path_prefixes: tuple[str, ...] = Field(min_length=1)
    expected_root_clause_id: str
    expected_failed_clause_ids: tuple[str, ...] = Field(min_length=1)
    planner_version: str

    @model_validator(mode="after")
    def validate_identity(self) -> CounterfactualOpportunity:
        identity = counterfactual_opportunity_identity(self)
        if self.opportunity_id != canonical_hash(identity, prefix="counterfactual_opportunity:"):
            raise ValueError("counterfactual opportunity identity is invalid")
        if self.expected_root_clause_id not in self.expected_failed_clause_ids:
            raise ValueError("expected failure closure must include its root clause")
        return self


class MinimalityReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    changed_json_paths: tuple[str, ...] = Field(min_length=1)
    allowed_json_path_prefixes: tuple[str, ...] = Field(min_length=1)
    unexpected_json_paths: tuple[str, ...] = ()
    source_leaf_count: int = Field(ge=1)
    edit_count: int = Field(ge=1)
    semantic_factor_count: int = Field(ge=1)
    normalized_edit_distance: float = Field(ge=0, le=1)
    minimality_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    passed: bool
    validator_version: str


class CounterfactualCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    counterfactual_id: str
    opportunity_id: str
    source_sample_id: str
    source_certificate_hash: str
    source_trajectory_id: str
    quality_contract_hash: str
    source_clause_id: str
    source_clause_kind: str
    mutation_family: MutationFamily
    mutation_operator_id: str
    mutation_operator_version: str
    target_object_type: str
    target_object_id: str
    original_hash: str
    mutated_hash: str
    expected_failed_clauses: tuple[str, ...]
    expected_root_clause: str
    minimality: MinimalityReport
    trajectory: Trajectory
    generated_by: str
    version: str

    @model_validator(mode="after")
    def validate_identity(self) -> CounterfactualCase:
        if self.trajectory.trajectory_hash != self.mutated_hash:
            raise ValueError("counterfactual mutated hash does not bind its trajectory")
        identity = counterfactual_case_identity(self)
        if self.counterfactual_id != canonical_hash(identity, prefix="counterfactual_case:"):
            raise ValueError("counterfactual case identity is invalid")
        return self

    @property
    def minimality_score(self) -> float:
        return self.minimality.minimality_score


class CounterfactualCaseEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    counterfactual_id: str
    assessment_id: str
    source_clause_id: str
    source_clause_kind: str
    mutation_family: MutationFamily
    mutation_operator_id: str
    detected: bool
    expected_root_clause_ids: tuple[str, ...]
    expected_root_clause_kinds: tuple[str, ...] = ()
    observed_root_clause_ids: tuple[str, ...]
    expected_failed_clause_ids: tuple[str, ...]
    observed_failed_clause_ids: tuple[str, ...]
    root_precision: float = Field(ge=0, le=1)
    root_recall: float = Field(ge=0, le=1)
    root_f1: float = Field(ge=0, le=1)
    closure_precision: float = Field(ge=0, le=1)
    closure_recall: float = Field(ge=0, le=1)
    closure_f1: float = Field(ge=0, le=1)


class CounterfactualSliceMetrics(BaseModel):
    """Calibration metrics for one operator, failure family, or clause kind."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    generated_case_count: int = Field(ge=0)
    valid_case_count: int = Field(ge=0)
    detected_case_count: int = Field(ge=0)
    mutation_validity_rate: float = Field(ge=0, le=1)
    detection_rate: float = Field(ge=0, le=1)
    minimality_pass_rate: float = Field(ge=0, le=1)
    mean_minimality_score: float = Field(ge=0, le=1)
    root_cause_f1: float = Field(ge=0, le=1)
    failure_closure_f1: float = Field(ge=0, le=1)


class CounterfactualCalibrationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    calibration_id: str
    engine_version: str
    operator_manifest_hash: str
    source_sample_count: int = Field(ge=0)
    clean_false_positive_count: int = Field(ge=0)
    opportunity_count: int = Field(ge=0)
    generated_case_count: int = Field(ge=0)
    valid_case_count: int = Field(ge=0)
    detected_case_count: int = Field(ge=0)
    mutation_validity_rate: float = Field(ge=0, le=1)
    minimality_pass_rate: float = Field(ge=0, le=1)
    mean_minimality_score: float = Field(ge=0, le=1)
    detection_precision: float = Field(ge=0, le=1)
    detection_recall: float = Field(ge=0, le=1)
    detection_f1: float = Field(ge=0, le=1)
    root_cause_precision: float = Field(ge=0, le=1)
    root_cause_recall: float = Field(ge=0, le=1)
    root_cause_f1: float = Field(ge=0, le=1)
    failure_closure_precision: float = Field(ge=0, le=1)
    failure_closure_recall: float = Field(ge=0, le=1)
    failure_closure_f1: float = Field(ge=0, le=1)
    mutable_clause_count: int = Field(ge=0)
    covered_mutable_clause_count: int = Field(ge=0)
    uncovered_mutable_clause_ids: tuple[str, ...]
    clause_coverage_rate: float = Field(ge=0, le=1)
    registered_operator_count: int = Field(ge=0)
    exercised_operator_count: int = Field(ge=0)
    operator_coverage_rate: float = Field(ge=0, le=1)
    mutation_family_counts: dict[str, int]
    operator_counts: dict[str, int]
    mutation_family_metrics: dict[str, CounterfactualSliceMetrics]
    operator_metrics: dict[str, CounterfactualSliceMetrics]
    source_clause_kind_metrics: dict[str, CounterfactualSliceMetrics]
    expected_root_clause_kind_metrics: dict[
        str, CounterfactualSliceMetrics
    ] = Field(default_factory=dict)
    case_evaluations: tuple[CounterfactualCaseEvaluation, ...]
    status: str
    failures: tuple[str, ...] = ()


def counterfactual_opportunity_identity(
    value: CounterfactualOpportunity,
) -> dict[str, Any]:
    return value.model_dump(mode="json", exclude={"opportunity_id"})


def counterfactual_case_identity(value: CounterfactualCase) -> dict[str, Any]:
    return value.model_dump(
        mode="json",
        exclude={"counterfactual_id", "trajectory"},
    )
