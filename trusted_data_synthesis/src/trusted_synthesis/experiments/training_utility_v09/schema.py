from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.feedback import (
    PatternClauseFailure,
    RefinementAllocation,
)
from trusted_synthesis.core.refinement import (
    ClauseFeedback,
    PolicyUpdateResult,
    SynthesisCell,
)
from trusted_synthesis.hashing import canonical_hash

TRAINING_UTILITY_V09_VERSION = "training_utility_v09.v2"

CCGR_ABLATION_IDS = (
    "static_verified",
    "raw_failure_reweighting",
    "no_defect_suppression",
    "no_coverage_regularization",
    "random_same_shift",
    "full_ccgr",
)


class V09Cohort(str, Enum):
    CONVENTIONAL_SYNTHETIC = "C1_conventional_synthetic"
    EVIDENCE_GROUNDED = "C2_evidence_grounded"
    VERIFIED_STATIC = "C3_verified_static"
    FEEDBACK_REFINED = "C4_feedback_refined_verified"


class V09RefinementConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    base_model_revision: str = "a09a35458c702b33eeacc393d103063234e8bc28"
    training_seed: int = 20260728
    cohort_example_budget: int = Field(default=600, ge=12, le=100000)
    supervised_token_budget: int = Field(default=1_200_000, ge=1000)
    lambda_values: tuple[float, ...] = (0.0, 0.5, 1.0)
    primary_lambda: float = Field(default=0.5, ge=0, le=1)
    alpha: float = Field(default=1.0, gt=0)
    epsilon: float = Field(default=0.01, gt=0)
    ccgr_eta: float = Field(default=1.0, gt=0)
    ccgr_beta: float = Field(default=1.0, ge=0)
    ccgr_gamma: float = Field(default=0.5, ge=0)
    ccgr_binding_tightening_threshold: float = Field(default=0.25, ge=0)
    ccgr_uncalibrated_reliability: float = Field(default=0.0, ge=0, le=1)
    ccgr_ablation_ids: tuple[str, ...] = CCGR_ABLATION_IDS
    domain_weights: dict[str, float] = {
        "finance": 0.8,
        "legal": 0.1,
        "science": 0.1,
    }
    student_training_format: Literal["host_instrumented_joint"] = (
        "host_instrumented_joint"
    )
    allowed_refinement_controls: tuple[str, ...] = (
        "pattern_clause_weight",
        "difficulty_bucket",
        "distractor_type",
        "distractor_count",
        "binding_constraint",
    )
    external_benchmark_status: Literal["not_executed"] = "not_executed"
    online_minimum_action_plan_contract_rate: float = Field(default=0.9, ge=0, le=1)
    online_minimum_host_execution_evaluable_rate: float = Field(
        default=0.9,
        ge=0,
        le=1,
    )
    online_minimum_answer_decision_contract_rate: float = Field(
        default=0.9,
        ge=0,
        le=1,
    )
    online_minimum_contract_acceptance_rate: float = Field(default=0.6, ge=0, le=1)
    offline_minimality_threshold: float = Field(default=0.9, ge=0, le=1)
    offline_minimum_valid_case_rate: float = Field(default=0.95, ge=0, le=1)
    offline_minimum_root_match_rate: float = Field(default=0.9, ge=0, le=1)
    offline_minimum_calibration_coverage: float = Field(default=0.6, ge=0, le=1)
    random_seed: int = 20260728

    @classmethod
    def from_json(cls, path: str | Path) -> V09RefinementConfig:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    @model_validator(mode="after")
    def validate_experiment_contract(self) -> V09RefinementConfig:
        if set(self.domain_weights) != {"finance", "legal", "science"}:
            raise ValueError("v0.9 must freeze finance, legal, and science domain weights")
        if abs(sum(self.domain_weights.values()) - 1.0) > 1e-9:
            raise ValueError("v0.9 domain weights must sum to one")
        if set(self.lambda_values) != {0.0, 0.5, 1.0}:
            raise ValueError("v0.9 must retain lambda=0, 0.5, and 1 ablations")
        if self.primary_lambda not in set(self.lambda_values):
            raise ValueError("primary lambda must be one of the frozen ablation values")
        if self.ccgr_ablation_ids != CCGR_ABLATION_IDS:
            raise ValueError("v0.9 must freeze all CCGR algorithm ablations")
        frozen_controls = {
            "pattern_clause_weight",
            "difficulty_bucket",
            "distractor_type",
            "distractor_count",
            "binding_constraint",
        }
        if set(self.allowed_refinement_controls) != frozen_controls:
            raise ValueError("v0.9 refinement controls cannot expand the framework")
        return self

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="training_utility_v09_config:")


class V09CohortContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: V09Cohort
    base_model: str = Field(min_length=1)
    base_model_revision: str = Field(min_length=1)
    training_seed: int
    pattern_catalog_hash: str = Field(min_length=1)
    evidence_grounded: bool
    proof_graph_required: bool
    executable_program_contract: bool
    quality_contract_required: bool
    feedback_refined: bool
    training_format: Literal["host_instrumented_joint"]
    supervised_token_budget: int = Field(ge=1000)
    domain_weights: dict[str, float]


class V09OnlineGate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attempted_rate: float | None = Field(default=None, ge=0, le=1)
    action_plan_contract_rate: float | None = Field(default=None, ge=0, le=1)
    host_execution_evaluable_rate: float | None = Field(default=None, ge=0, le=1)
    answer_decision_contract_rate: float | None = Field(default=None, ge=0, le=1)
    contract_acceptance_rate: float | None = Field(default=None, ge=0, le=1)
    accepted_domains: tuple[str, ...] = ()
    accepted_patterns: tuple[str, ...] = ()
    first_call_action_success_count: int = Field(default=0, ge=0)
    repaired_action_success_count: int = Field(default=0, ge=0)
    first_call_answer_success_count: int = Field(default=0, ge=0)
    repaired_answer_success_count: int = Field(default=0, ge=0)
    resume_completed_api_call_count: int | None = Field(default=None, ge=0)
    failures: tuple[str, ...] = ()
    status: Literal["passed", "failed", "not_run"]


class V09RefinementManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_id: str
    config_hash: str
    pattern_catalog_hash: str
    feedback_source: str
    round0_real_agent_feedback: bool
    feedback_exposure_count: int = Field(ge=0)
    feedback_signal_count: int = Field(ge=0)
    feedback_route_counts: dict[str, int]
    pattern_clause_failures: tuple[PatternClauseFailure, ...]
    allocations: tuple[RefinementAllocation, ...]
    primary_allocation_id: str | None = None
    synthesis_cells: tuple[SynthesisCell, ...]
    clause_feedback: tuple[ClauseFeedback, ...]
    clause_calibration: dict[str, float]
    calibration_manifest_hash: str
    calibration_coverage_rate: float = Field(ge=0, le=1)
    ccgr_updates: tuple[PolicyUpdateResult, ...]
    primary_ccgr_update_id: str | None = None
    cohort_contracts: tuple[V09CohortContract, ...]
    online_gate: V09OnlineGate
    external_benchmark_status: Literal["not_executed"] = "not_executed"
    limitations: tuple[str, ...]
    status: Literal["initial_ready", "ready_for_online_gate", "blocked"]
    version: str = TRAINING_UTILITY_V09_VERSION

    @model_validator(mode="after")
    def validate_causal_comparison(self) -> V09RefinementManifest:
        by_cohort = {item.cohort: item for item in self.cohort_contracts}
        if set(by_cohort) != set(V09Cohort):
            raise ValueError("v0.9 manifest must contain C1 through C4")
        formats = {item.training_format for item in self.cohort_contracts}
        token_budgets = {item.supervised_token_budget for item in self.cohort_contracts}
        base_models = {
            (item.base_model, item.base_model_revision) for item in self.cohort_contracts
        }
        training_seeds = {item.training_seed for item in self.cohort_contracts}
        pattern_catalogs = {item.pattern_catalog_hash for item in self.cohort_contracts}
        domain_weights = {
            canonical_hash(item.domain_weights) for item in self.cohort_contracts
        }
        if any(
            len(values) != 1
            for values in (
                formats,
                token_budgets,
                base_models,
                training_seeds,
                pattern_catalogs,
                domain_weights,
            )
        ):
            raise ValueError(
                "C1-C4 must share model revision, seed, pattern catalog, format, "
                "supervised tokens, and domain weights"
            )
        if self.pattern_catalog_hash not in pattern_catalogs:
            raise ValueError("manifest and cohort pattern catalog hashes must match")
        if {item.ablation_id for item in self.ccgr_updates} != set(
            CCGR_ABLATION_IDS
        ):
            raise ValueError("v0.9 manifest must contain every frozen CCGR ablation")
        full = next(
            item for item in self.ccgr_updates if item.ablation_id == "full_ccgr"
        )
        if self.primary_ccgr_update_id != full.update_id:
            raise ValueError("the primary CCGR update must be the full algorithm")
        c3 = by_cohort[V09Cohort.VERIFIED_STATIC]
        c4 = by_cohort[V09Cohort.FEEDBACK_REFINED]
        comparable = (
            c3.evidence_grounded == c4.evidence_grounded
            and c3.proof_graph_required == c4.proof_graph_required
            and c3.executable_program_contract == c4.executable_program_contract
            and c3.quality_contract_required == c4.quality_contract_required
        )
        if not comparable or c3.feedback_refined or not c4.feedback_refined:
            raise ValueError("C4 may differ from C3 only through feedback refinement")
        return self


class V09InitialBuildReport(BaseModel):
    """Offline contract-pipeline evidence for the initial v0.9 control plane."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str
    config_hash: str
    manifest_id: str
    tasks_per_domain: int = Field(ge=1)
    source_task_count: int = Field(ge=1)
    clean_accepted_count: int = Field(ge=0)
    opportunity_count: int = Field(ge=0)
    generated_case_count: int = Field(ge=0)
    detected_case_count: int = Field(ge=0)
    valid_case_count: int = Field(ge=0)
    expected_root_match_count: int = Field(ge=0)
    domain_task_counts: dict[str, int]
    domain_valid_case_counts: dict[str, int]
    feedback_route_counts: dict[str, int]
    clean_acceptance_rate: float = Field(ge=0, le=1)
    detection_rate: float = Field(ge=0, le=1)
    valid_case_rate: float = Field(ge=0, le=1)
    expected_root_match_rate: float = Field(ge=0, le=1)
    synthesis_cell_count: int = Field(ge=1)
    calibrated_clause_kind_count: int = Field(ge=0)
    calibration_coverage_rate: float = Field(ge=0, le=1)
    ccgr_ablation_count: int = Field(ge=0)
    full_ccgr_kl_divergence: float = Field(ge=0)
    full_ccgr_total_variation_distance: float = Field(ge=0, le=1)
    round0_real_agent_feedback: Literal[False] = False
    external_benchmark_status: Literal["not_executed"] = "not_executed"
    status: Literal["passed", "failed"]
    failures: tuple[str, ...] = ()
    limitations: tuple[str, ...]
    version: str = TRAINING_UTILITY_V09_VERSION
