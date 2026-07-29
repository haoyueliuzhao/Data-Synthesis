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
    SynthesisMaterializationReport,
)
from trusted_synthesis.experiments.training_utility_mvp.schema import (
    CohortEvaluationResult,
    CohortTrainingResult,
)
from trusted_synthesis.hashing import canonical_hash

TRAINING_UTILITY_V09_VERSION = "training_utility_v09.v4"

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


class V09ExperimentAxis(BaseModel):
    """Frozen interpretation boundary for one family of training contrasts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    axis_id: Literal["co_compilation", "ccgr_refinement"]
    members: tuple[str, ...] = Field(min_length=2)
    primary_contrast: tuple[str, str]
    causal_status: Literal["identified", "exploratory", "requires_materialization"]
    controlled_variables: tuple[str, ...]
    unresolved_confounds: tuple[str, ...] = ()


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
    ccgr_minimum_cell_exposure: int = Field(default=3, ge=1)
    ccgr_pattern_shrinkage_strength: float = Field(default=5.0, ge=0)
    ccgr_clause_confidence_prior_count: float = Field(default=5.0, ge=0)
    ccgr_normalize_root_mass: bool = True
    materialization_seed: int = 20260729
    materialization_superpool_size: int = Field(default=20_000_000, ge=10_000)
    materialization_scan_multiplier: int = Field(default=48, ge=8)
    finance_archive_config_path: Path | None = None
    ccgr_ablation_ids: tuple[str, ...] = CCGR_ABLATION_IDS
    domain_weights: dict[str, float] = {
        "finance": 0.8,
        "legal": 0.1,
        "science": 0.1,
    }
    student_training_format: Literal["host_instrumented_joint"] = "host_instrumented_joint"
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
        config_path = Path(path).resolve()
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        archive_config = payload.get("finance_archive_config_path")
        if archive_config:
            value = Path(archive_config).expanduser()
            if not value.is_absolute():
                value = config_path.parent / value
            payload["finance_archive_config_path"] = value.resolve()
        return cls.model_validate(payload)

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
    experiment_axes: tuple[V09ExperimentAxis, ...] = ()
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
        domain_weights = {canonical_hash(item.domain_weights) for item in self.cohort_contracts}
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
        if self.version == "training_utility_v09.v4":
            axes = {item.axis_id: item for item in self.experiment_axes}
            if set(axes) != {"co_compilation", "ccgr_refinement"}:
                raise ValueError("v0.9.4 must freeze co-compilation and CCGR axes")
            if axes["ccgr_refinement"].primary_contrast != (
                V09Cohort.VERIFIED_STATIC.value,
                V09Cohort.FEEDBACK_REFINED.value,
            ):
                raise ValueError("the identified CCGR contrast must be C3 versus C4")
            if set(axes["ccgr_refinement"].members) != {
                V09Cohort.VERIFIED_STATIC.value,
                V09Cohort.FEEDBACK_REFINED.value,
            }:
                raise ValueError(
                    "the identified CCGR axis may only contain materialized C3/C4 cohorts"
                )
        if {item.ablation_id for item in self.ccgr_updates} != set(CCGR_ABLATION_IDS):
            raise ValueError("v0.9 manifest must contain every frozen CCGR ablation")
        full = next(item for item in self.ccgr_updates if item.ablation_id == "full_ccgr")
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


class V09CohortDatasetManifest(BaseModel):
    """Auditable materialization of one causal training cohort."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: V09Cohort
    record_count: int = Field(ge=1)
    domain_counts: dict[str, int]
    source_kind_counts: dict[str, int]
    pattern_counts: dict[str, int]
    synthesis_cell_counts: dict[str, int]
    selection_policy_id: str = Field(min_length=1)
    selection_policy_hash: str = Field(min_length=1)
    eligible_source_record_count: int = Field(ge=1)
    eligible_source_domain_counts: dict[str, int]
    eligible_source_pool_hash: str = Field(min_length=1)
    accepted_real_link_count: int = Field(ge=0)
    real_feedback_link_count: int = Field(default=0, ge=0)
    materialization_mode: Literal["selection", "new_compilation"] = "selection"
    materialization_report: SynthesisMaterializationReport | None = None
    compiler_contract_hash: str | None = None
    record_ids: tuple[str, ...]
    task_ids: tuple[str, ...]
    dataset_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dataset_identity(self) -> V09CohortDatasetManifest:
        if len(self.record_ids) != self.record_count:
            raise ValueError("cohort record IDs must cover every record")
        if len(set(self.record_ids)) != self.record_count:
            raise ValueError("cohort record IDs must be unique")
        if len(self.task_ids) != self.record_count or len(set(self.task_ids)) != self.record_count:
            raise ValueError("one v0.9 cohort may contain only one record per task")
        if sum(self.domain_counts.values()) != self.record_count:
            raise ValueError("cohort domain counts must sum to the record count")
        if sum(self.source_kind_counts.values()) != self.record_count:
            raise ValueError("cohort source-kind counts must sum to the record count")
        if sum(self.pattern_counts.values()) != self.record_count:
            raise ValueError("cohort pattern counts must sum to the record count")
        if self.synthesis_cell_counts and (
            sum(self.synthesis_cell_counts.values()) != self.record_count
        ):
            raise ValueError("cohort synthesis-cell counts must cover every record")
        if sum(self.eligible_source_domain_counts.values()) != self.eligible_source_record_count:
            raise ValueError("eligible source domain counts must cover the source pool")
        if self.accepted_real_link_count > self.real_feedback_link_count:
            raise ValueError("accepted links cannot exceed all real-feedback links")
        if self.real_feedback_link_count > self.record_count:
            raise ValueError("real-feedback links cannot exceed the cohort size")
        if self.materialization_mode == "new_compilation":
            if self.materialization_report is None or self.compiler_contract_hash is None:
                raise ValueError(
                    "new compilation requires a materialization report and compiler contract"
                )
            report = self.materialization_report
            if report.status != "passed":
                raise ValueError("a blocked materialization report cannot back a cohort")
            if (
                report.policy_update_id != self.selection_policy_id
                or report.requested_sample_count != self.record_count
                or report.successfully_materialized_count != self.record_count
            ):
                raise ValueError("materialization report does not cover this cohort")
            materialized_counts = {
                cell_id: count
                for cell_id, count in report.materialized_cell_counts.items()
                if count
            }
            if materialized_counts != self.synthesis_cell_counts:
                raise ValueError("materialization report Cell counts disagree with the cohort")
            if self.compiler_contract_hash != report.compiler_contract_hash:
                raise ValueError("cohort compiler contract is not pinned by its report")
        elif self.materialization_report is not None or self.compiler_contract_hash is not None:
            raise ValueError("selection materialization cannot attach a compiler report")
        return self


class V09TrainingDataManifest(BaseModel):
    """Frozen C1-C4 datasets and the shared held-out evaluation contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_id: str = Field(min_length=1)
    refinement_config_hash: str = Field(min_length=1)
    training_config_hash: str = Field(min_length=1)
    refinement_manifest_id: str = Field(min_length=1)
    canonical_base_model: str = Field(min_length=1)
    canonical_model_revision: str = Field(min_length=1)
    runtime_base_model: str = Field(min_length=1)
    runtime_model_revision: str = Field(min_length=1)
    source_agent_run_id: str = Field(min_length=1)
    source_critic_dataset_id: str = Field(min_length=1)
    source_critic_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_migration_policy_id: str = Field(min_length=1)
    task_migration_policy_hash: str = Field(min_length=1)
    source_real_candidate_count: int = Field(ge=1)
    mapped_real_candidate_count: int = Field(ge=0)
    unmapped_real_candidate_count: int = Field(ge=0)
    semantic_migration_count: int = Field(ge=0)
    semantic_migration_domain_counts: dict[str, int]
    representable_real_candidate_count: int = Field(ge=0)
    representable_real_domain_counts: dict[str, int]
    accepted_mapped_candidate_count: int = Field(ge=0)
    round0_real_agent_feedback: bool
    offline_refinement_override: bool
    causal_status: Literal["online_ready", "offline_pilot_only"]
    full_ccgr_update_id: str = Field(min_length=1)
    supervised_token_budget: int = Field(ge=1000)
    cohort_example_budget: int = Field(ge=1)
    expected_domain_counts: dict[str, int]
    cohorts: tuple[V09CohortDatasetManifest, ...]
    evaluation_record_count: int = Field(ge=1)
    evaluation_domain_counts: dict[str, int]
    evaluation_record_ids: tuple[str, ...]
    evaluation_dataset_hash: str = Field(min_length=1)
    train_evaluation_task_overlap_count: int = Field(ge=0)
    train_evaluation_subject_overlap_count: int = Field(ge=0)
    train_evaluation_evidence_overlap_count: int = Field(ge=0)
    train_evaluation_evidence_version_overlap_count: int = Field(ge=0)
    train_evaluation_source_record_overlap_count: int = Field(ge=0)
    train_evaluation_binding_overlap_count: int = Field(ge=0)
    c3_c4_task_overlap_count: int = Field(ge=0)
    c3_c4_binding_overlap_count: int = Field(default=0, ge=0)
    c3_c4_evidence_version_overlap_count: int = Field(default=0, ge=0)
    c3_c4_source_pool_shared: bool
    c3_c4_compiler_contract_shared: bool = False
    finance_source_adapter_ids: tuple[str, ...] = ()
    finance_archive_provider_used: bool = False
    c3_c4_candidate_superpool_shared: bool = False
    c3_c4_sampling_partitions_disjoint: bool = False
    c3_c4_materialization_seed_shared: bool = False
    experiment_axes: tuple[V09ExperimentAxis, ...] = ()
    synthesis_closed_loop_status: Literal[
        "legacy_reallocation",
        "new_binding_compilation",
    ] = "legacy_reallocation"
    external_benchmark_status: Literal["not_executed"] = "not_executed"
    limitations: tuple[str, ...]
    status: Literal["ready", "pilot_ready", "blocked"]
    version: str = TRAINING_UTILITY_V09_VERSION

    @model_validator(mode="after")
    def validate_causal_data_contract(self) -> V09TrainingDataManifest:
        by_cohort = {item.cohort: item for item in self.cohorts}
        if set(by_cohort) != set(V09Cohort):
            raise ValueError("v0.9 training data must contain C1 through C4")
        if self.version == "training_utility_v09.v4":
            axes = {item.axis_id: item for item in self.experiment_axes}
            if set(axes) != {"co_compilation", "ccgr_refinement"}:
                raise ValueError("training data must preserve both experiment axes")
            if axes["ccgr_refinement"].causal_status != "identified":
                raise ValueError("C3/C4 must remain the identified refinement contrast")
            if axes["co_compilation"].causal_status != "exploratory":
                raise ValueError("C1/C2/C3 remain an exploratory co-compilation axis")
            if self.finance_archive_provider_used and set(self.finance_source_adapter_ids) != {
                "finance_archive.v1"
            }:
                raise ValueError(
                    "the Finance Archive Provider requires archive-backed source feedback"
                )
        if (
            self.mapped_real_candidate_count + self.unmapped_real_candidate_count
            != self.source_real_candidate_count
        ):
            raise ValueError("mapped and unmapped candidates must cover the real source pool")
        if self.unmapped_real_candidate_count:
            raise ValueError("v0.9 cannot train with unmapped real-agent source candidates")
        if self.semantic_migration_count != sum(self.semantic_migration_domain_counts.values()):
            raise ValueError("semantic migration domain counts are inconsistent")
        if self.representable_real_candidate_count != sum(
            self.representable_real_domain_counts.values()
        ):
            raise ValueError("representable candidate domain counts are inconsistent")
        if self.representable_real_candidate_count > self.mapped_real_candidate_count:
            raise ValueError("representable candidates cannot exceed mapped candidates")
        if self.accepted_mapped_candidate_count > self.representable_real_candidate_count:
            raise ValueError("accepted mapped candidates must be representable")
        if any(item.record_count != self.cohort_example_budget for item in self.cohorts):
            raise ValueError("all v0.9 cohorts must have the frozen example budget")
        if any(item.domain_counts != self.expected_domain_counts for item in self.cohorts):
            raise ValueError("all v0.9 cohorts must have identical domain quotas")
        hard_overlaps = {
            "task": self.train_evaluation_task_overlap_count,
            "subject": self.train_evaluation_subject_overlap_count,
            "evidence": self.train_evaluation_evidence_overlap_count,
            "evidence_version": self.train_evaluation_evidence_version_overlap_count,
            "source_record": self.train_evaluation_source_record_overlap_count,
            "binding": self.train_evaluation_binding_overlap_count,
        }
        observed = {key: value for key, value in hard_overlaps.items() if value}
        if observed:
            raise ValueError(f"v0.9 train/evaluation identities overlap: {observed}")
        c3 = by_cohort[V09Cohort.VERIFIED_STATIC]
        c4 = by_cohort[V09Cohort.FEEDBACK_REFINED]
        if c3.real_feedback_link_count != c3.record_count:
            raise ValueError("every C3 record must link to an evaluated real candidate")
        if c4.real_feedback_link_count != c4.record_count:
            raise ValueError("every C4 record must link to an evaluated real candidate")
        if (
            not self.c3_c4_source_pool_shared
            or c3.eligible_source_pool_hash != c4.eligible_source_pool_hash
            or c3.eligible_source_record_count != c4.eligible_source_record_count
        ):
            raise ValueError("C3 and C4 must share the same mapped feedback source pool")
        if self.synthesis_closed_loop_status == "new_binding_compilation":
            if (
                c3.materialization_mode != "new_compilation"
                or c4.materialization_mode != "new_compilation"
            ):
                raise ValueError("the synthesis closed loop requires newly compiled C3 and C4")
            if (
                not self.c3_c4_compiler_contract_shared
                or c3.compiler_contract_hash != c4.compiler_contract_hash
            ):
                raise ValueError("C3 and C4 must share one frozen compiler contract")
            if (
                not self.c3_c4_candidate_superpool_shared
                or not self.c3_c4_sampling_partitions_disjoint
                or not self.c3_c4_materialization_seed_shared
            ):
                raise ValueError(
                    "C3/C4 must use one candidate super-pool, one seed, "
                    "and disjoint sampling partitions"
                )
            overlaps = {
                "task": self.c3_c4_task_overlap_count,
                "binding": self.c3_c4_binding_overlap_count,
                "evidence_version": self.c3_c4_evidence_version_overlap_count,
            }
            if any(overlaps.values()):
                raise ValueError(f"newly compiled C3/C4 identities overlap: {overlaps}")
        elif c3.materialization_mode != "selection" or c4.materialization_mode != "selection":
            raise ValueError("legacy reallocation may only use selected source records")
        if self.round0_real_agent_feedback:
            if self.offline_refinement_override or self.causal_status != "online_ready":
                raise ValueError("real Round-0 data must use the online-ready causal status")
            if self.status != "ready":
                raise ValueError("online-ready data must have ready status")
        else:
            if not self.offline_refinement_override:
                raise ValueError("offline refinement requires an explicit operator override")
            if self.causal_status != "offline_pilot_only" or self.status != "pilot_ready":
                raise ValueError("offline refinement can only produce pilot-ready data")
        return self


class V09TrainingUtilityReport(BaseModel):
    """Final C1-C4 training comparison with an explicit causal boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    data_manifest_id: str = Field(min_length=1)
    causal_status: Literal["online_ready", "offline_pilot_only"]
    causal_claim_status: Literal["identified", "not_identified"]
    base_evaluation: CohortEvaluationResult
    cohort_training: tuple[CohortTrainingResult, ...]
    cohort_evaluations: tuple[CohortEvaluationResult, ...]
    cohort_deltas_vs_base: dict[str, dict[str, float]]
    c4_minus_c3: dict[str, float]
    cohort_ranking: tuple[str, ...]
    completed_cohort_count: int = Field(ge=0, le=4)
    external_benchmark_status: Literal["not_executed"] = "not_executed"
    limitations: tuple[str, ...]
    status: Literal["completed", "partial", "failed"]
