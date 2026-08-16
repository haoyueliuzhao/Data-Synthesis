from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.admission import (
    DESTRUCTIVE_MUTATION_CHECKS,
    JOINT_COMPILATION_GATES,
)
from trusted_synthesis.core.trajectory.state import TRAJECTORY_CANONICALIZER_VERSION
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
    FAMILY_PRIMARY_CAPABILITY,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_context_sufficiency_decision import (  # noqa: E501
    ContextSufficiencyScientificDecision,
)
from trusted_synthesis.hashing import canonical_hash

FINANCE_V26_MAINLINE_VERSION = "finance_v26_capability_heterogeneous_vtdo_mainline.v1"
MAINLINE_SUPPORT_OBSERVATION_VERSION = "vtdo_mainline_support_observation.v1"
MAINLINE_SUPPORT_PARTITION_VERSION = "vtdo_mainline_support_partition.v1"
MAINLINE_PREFLIGHT_VERSION = "finance_v26_mainline_preflight.v1"

CapabilityAxis = Literal[
    "retrieval",
    "planning",
    "calculation",
    "reconciliation",
    "verification",
    "recovery",
    "stopping",
]
MainlineSplit = Literal[
    "synthesis_training",
    "internal_agent_evaluation",
    "exact_target_development",
    "exact_target_validation",
]
NoCArm = Literal[
    "B1_raw",
    "B2_validity",
    "B4_random_state",
    "B2_novelty_only",
    "B5_no_c_round_1",
    "B5_no_c_round_3",
    "B3_ccgr",
]

_EXPECTED_SPLIT_COUNTS: dict[str, int] = {
    "synthesis_training": 100,
    "internal_agent_evaluation": 60,
    "exact_target_development": 30,
    "exact_target_validation": 60,
}
_EXPECTED_NO_C_ARMS: tuple[NoCArm, ...] = (
    "B1_raw",
    "B2_validity",
    "B4_random_state",
    "B2_novelty_only",
    "B5_no_c_round_1",
    "B5_no_c_round_3",
    "B3_ccgr",
)
_PRIMARY_CAUSAL_NO_C_ARMS: tuple[NoCArm, ...] = (
    "B2_validity",
    "B4_random_state",
    "B2_novelty_only",
    "B5_no_c_round_1",
    "B5_no_c_round_3",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImmutableArtifactReference(FrozenModel):
    role: Literal["historical_measurement_hypothesis_only"]
    artifact_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    historical_task_promotion_count: Literal[0] = 0
    authorizes_current_population: Literal[False] = False


class MainlineDataSplitContract(FrozenModel):
    split_id: MainlineSplit
    task_count: int = Field(ge=1)
    purpose: str = Field(min_length=1)
    state_discovery_enabled: bool
    explorer_rollouts_per_task: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_split(self) -> MainlineDataSplitContract:
        if self.task_count != _EXPECTED_SPLIT_COUNTS[self.split_id]:
            raise ValueError("mainline split task count differs from the frozen protocol")
        expected_rollouts = 8 if self.split_id == "synthesis_training" else 0
        if self.explorer_rollouts_per_task != expected_rollouts:
            raise ValueError("mainline split Explorer rollout count is inconsistent")
        if self.state_discovery_enabled != (self.split_id == "synthesis_training"):
            raise ValueError("state discovery is restricted to the synthesis/training split")
        return self


class MainlinePopulationContract(FrozenModel):
    splits: tuple[MainlineDataSplitContract, ...] = Field(min_length=4, max_length=4)
    capability_axes: tuple[CapabilityAxis, ...]
    finance_task_families: tuple[str, ...]
    explorer_model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    explorer_replicas_per_training_task: Literal[8] = 8
    task_marginal: Literal["uniform_over_100_synthesis_tasks"] = "uniform_over_100_synthesis_tasks"
    task_marginal_probability: float = Field(default=0.01, ge=0, le=1)
    equal_success_rate_required: Literal[False] = False
    outcome_conditioned_task_weighting: Literal[False] = False
    pro_anchor_rate: float = Field(default=0.0, ge=0, le=0.2)
    isolation_dimensions: tuple[str, ...] = (
        "task_id",
        "evidence_id",
        "evidence_version_id",
        "semantic_signature",
        "trajectory_id",
    )

    @model_validator(mode="after")
    def validate_population(self) -> MainlinePopulationContract:
        if {item.split_id for item in self.splits} != set(_EXPECTED_SPLIT_COUNTS):
            raise ValueError("mainline data splits are incomplete")
        if len({item.split_id for item in self.splits}) != len(self.splits):
            raise ValueError("mainline data splits are duplicated")
        if self.capability_axes != CAPABILITY_AXES:
            raise ValueError("mainline capability axes differ from the frozen registry")
        if self.finance_task_families != CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("mainline Finance task families differ from the frozen registry")
        if set(FAMILY_PRIMARY_CAPABILITY.values()) != set(self.capability_axes):
            raise ValueError("Finance task families do not cover the frozen capability axes")
        if abs(self.task_marginal_probability - 0.01) > 1e-12:
            raise ValueError("the 100-task synthesis marginal must remain fixed")
        return self


class MainlineStateMaterializationContract(FrozenModel):
    minimum_states_per_task: Literal[3] = 3
    maximum_states_per_task: Literal[5] = 5
    minimum_train_realizations_per_state: Literal[3] = 3
    exact_target_realizations_per_state: Literal[5] = 5
    discovery_materialization_identity_separated: Literal[True] = True
    independent_validity_replay_required: Literal[True] = True
    quotient_state_mapping_required: Literal[True] = True
    duplicate_decision_trace_rejected: Literal[True] = True
    failed_quota_reallocation_forbidden: Literal[True] = True
    task_replacement_if_state_capacity_fails: Literal[True] = True


class JointCompilationAdmissionContract(FrozenModel):
    phase_id: Literal["v26_1_joint_compilation_admission"] = "v26_1_joint_compilation_admission"
    required_outputs: tuple[str, ...] = (
        "oracle_verification_context",
        "runtime_specific_public_projection",
        "versioned_state_catalog",
        "state_mapper",
        "independent_verifier",
        "materialization_contract",
    )
    required_gates: tuple[str, ...] = JOINT_COMPILATION_GATES
    required_runtime_projections: tuple[str, ...] = ("scripted", "autonomous")
    state_mapper_version: str = TRAJECTORY_CANONICALIZER_VERSION
    destructive_mutation_checks: tuple[str, ...] = DESTRUCTIVE_MUTATION_CHECKS
    cross_domain_contract_domains: tuple[Literal["legal", "science"], ...] = (
        "legal",
        "science",
    )
    all_population_tasks_must_be_admitted: Literal[True] = True
    shared_compilation_lineage_required: Literal[True] = True
    pre_model_admission_required: Literal[True] = True
    failure_transition: Literal["joint_compilation_repair_only"] = "joint_compilation_repair_only"
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0

    @model_validator(mode="after")
    def validate_admission_contract(self) -> JointCompilationAdmissionContract:
        if self.required_gates != JOINT_COMPILATION_GATES:
            raise ValueError("v26 Joint Compilation gates differ from Core admission")
        if self.destructive_mutation_checks != DESTRUCTIVE_MUTATION_CHECKS:
            raise ValueError("v26 destructive mutation checks differ from Core admission")
        return self


class MainlineSupportContract(FrozenModel):
    measurement_support_definition: str = (
        "construct-valid, observable, interference-free runtime outcomes, including model failures"
    )
    training_support_definition: str = (
        "independently valid, replayable, on-target materialization trajectories only"
    )
    contribution_support_definition: str = (
        "training support additionally authorized by meaningful Exact Target and independent GP-C"
    )
    inverse_success_weighting_forbidden: Literal[True] = True
    model_failures_allowed_in_measurement: Literal[True] = True
    model_failures_allowed_in_positive_sft: Literal[False] = False
    contribution_support_subset_of_training: Literal[True] = True


class NoCStudentArmContract(FrozenModel):
    arm_id: NoCArm
    role: Literal["quality_lower_bound", "primary_causal", "secondary_comparison"]
    contribution_used: Literal[False] = False
    fixed_task_marginal_required: bool
    training_round: Literal[0, 1, 3]


class NoCDistributionContract(FrozenModel):
    method_label: Literal["AEVTDR-NoC"] = "AEVTDR-NoC"
    claim_label: Literal["novelty_anchored_vtdo_not_full_c_plus_n"] = (
        "novelty_anchored_vtdo_not_full_c_plus_n"
    )
    uniform_coverage_prior_is_primary: Literal[True] = True
    reachability_prior_is_sensitivity_only: Literal[True] = True
    materialized_training_rounds: tuple[Literal[1, 3], ...] = (1, 3)
    dynamics_only_rounds: tuple[Literal[5], ...] = (5,)
    intermediate_rounds_required: tuple[Literal[0, 1, 2, 3, 5], ...] = (0, 1, 2, 3, 5)
    stabilization_is_not_global_convergence: Literal[True] = True
    dynamic_metrics: tuple[str, ...] = (
        "kl_shift",
        "total_variation",
        "jensen_shannon",
        "entropy",
        "active_support",
        "capability_slice_mass",
        "state_entry_exit",
        "quota_fill",
        "state_conditioned_hit_rate",
        "reachability",
        "expected_log_potential",
        "potential_drift",
        "materialization_cost",
        "error_type_distribution",
    )
    student_arms: tuple[NoCStudentArmContract, ...] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_no_c(self) -> NoCDistributionContract:
        if tuple(item.arm_id for item in self.student_arms) != _EXPECTED_NO_C_ARMS:
            raise ValueError("No-C Student arms differ from the frozen v26 matrix")
        by_id = {item.arm_id: item for item in self.student_arms}
        if any(by_id[item].role != "primary_causal" for item in _PRIMARY_CAUSAL_NO_C_ARMS):
            raise ValueError("the primary No-C causal arm set is incomplete")
        if any(not by_id[item].fixed_task_marginal_required for item in _PRIMARY_CAUSAL_NO_C_ARMS):
            raise ValueError("all primary No-C arms must preserve the task marginal")
        if by_id["B1_raw"].role != "quality_lower_bound":
            raise ValueError("B1 Raw must remain a quality lower bound")
        if by_id["B3_ccgr"].role != "secondary_comparison":
            raise ValueError("B3 CCGR must remain a secondary comparison")
        return self


class ContributionRecoveryContract(FrozenModel):
    branch_id: Literal["finance_v26_contribution_recovery.v1"] = (
        "finance_v26_contribution_recovery.v1"
    )
    beneficiary_model_family: Literal["Qwen2.5-7B"] = "Qwen2.5-7B"
    development_task_count: Literal[30] = 30
    validation_task_count: Literal[60] = 60
    realizations_per_state: Literal[5] = 5
    objective_record_count: Literal[128] = 128
    objective_micro_split_count: Literal[16] = 16
    objective_records_per_micro_split: Literal[8] = 8
    exact_target_kind: Literal["strict_fp32_one_step_adamw_chain_rule"] = (
        "strict_fp32_one_step_adamw_chain_rule"
    )
    meaningful_coordinate_gate_required: Literal[True] = True
    gp_c_before_meaningful_coordinate_forbidden: Literal[True] = True
    gp_c_independent_authorization_required: Literal[True] = True
    development_validation_authorization_isolated: Literal[True] = True
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    full_c_plus_n_authorized: Literal[False] = False
    production_contribution: float = Field(default=0.0, ge=0.0, le=0.0)


class StudentEvaluationContract(FrozenModel):
    student_model_family: Literal["Qwen2.5-7B"] = "Qwen2.5-7B"
    supervised_token_budget: Literal[500000] = 500000
    training_seed_count: Literal[3] = 3
    external_benchmarks: tuple[Literal["FinQA", "TAT-QA"], ...] = ("FinQA", "TAT-QA")
    required_internal_slices: tuple[CapabilityAxis, ...] = cast(
        tuple[CapabilityAxis, ...], CAPABILITY_AXES
    )
    required_comparisons: tuple[str, ...] = (
        "overall_delta",
        "weak_slice_delta",
        "boundary_slice_delta",
        "strong_slice_delta",
        "strong_slice_retention",
        "round_1_vs_round_3",
        "overcompensation",
        "catastrophic_forgetting",
    )


class CapabilityHeterogeneousMainlineProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    prior_evidence: tuple[ImmutableArtifactReference, ...] = Field(min_length=1)
    population: MainlinePopulationContract
    joint_compilation: JointCompilationAdmissionContract
    materialization: MainlineStateMaterializationContract
    support: MainlineSupportContract
    no_c: NoCDistributionContract
    contribution: ContributionRecoveryContract
    student_evaluation: StudentEvaluationContract
    explorer_config_sha256: str = Field(min_length=64, max_length=64)
    student_config_sha256: str = Field(min_length=64, max_length=64)
    archive_config_sha256: str = Field(min_length=64, max_length=64)
    historical_task_promotion_count: Literal[0] = 0
    current_permitted_stage: Literal["v26_1_joint_compilation_admission"] = (
        "v26_1_joint_compilation_admission"
    )
    flash_api_calls_authorized: Literal[False] = False
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_gpu_jobs_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = FINANCE_V26_MAINLINE_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> CapabilityHeterogeneousMainlineProtocol:
        if any(item.authorizes_current_population for item in self.prior_evidence):
            raise ValueError("historical evidence cannot authorize the v26 population")
        if any(item.historical_task_promotion_count for item in self.prior_evidence):
            raise ValueError("historical tasks cannot be promoted into v26")
        if self.protocol_id != capability_heterogeneous_mainline_protocol_id(self):
            raise ValueError("v26 mainline protocol identity is invalid")
        return self


class MainlineSupportObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    capability_axis: CapabilityAxis
    split_id: MainlineSplit
    phase: Literal["discovery", "materialization"]
    terminal_status: Literal["completed", "model_failed", "runtime_failed"]
    construct_valid: bool
    runtime_eligible_for_capability_denominator: bool
    observable: bool
    interference_free: bool
    independent_validity_passed: bool = False
    quotient_state_id: str | None = Field(default=None, min_length=1)
    state_mapping_on_target: bool = False
    replayable: bool = False
    decision_trace_hash: str | None = Field(default=None, min_length=64, max_length=64)
    beneficiary_boundary_id: str | None = Field(default=None, min_length=1)
    contribution_authorization_id: str | None = Field(default=None, min_length=1)
    exact_target_exceeds_mpe: bool = False
    gp_c_independently_validated: bool = False
    distribution_update_contract_passed: bool = False
    schema_version: str = MAINLINE_SUPPORT_OBSERVATION_VERSION

    @property
    def measurement_eligible(self) -> bool:
        return all(
            (
                self.construct_valid,
                self.runtime_eligible_for_capability_denominator,
                self.observable,
                self.interference_free,
            )
        )

    @property
    def training_eligible(self) -> bool:
        return all(
            (
                self.measurement_eligible,
                self.split_id == "synthesis_training",
                self.phase == "materialization",
                self.terminal_status == "completed",
                self.independent_validity_passed,
                bool(self.quotient_state_id),
                self.state_mapping_on_target,
                self.replayable,
                bool(self.decision_trace_hash),
            )
        )

    @property
    def contribution_eligible(self) -> bool:
        return all(
            (
                self.training_eligible,
                bool(self.beneficiary_boundary_id),
                bool(self.contribution_authorization_id),
                self.exact_target_exceeds_mpe,
                self.gp_c_independently_validated,
                self.distribution_update_contract_passed,
            )
        )

    @model_validator(mode="after")
    def validate_observation(self) -> MainlineSupportObservation:
        if self.observation_id != mainline_support_observation_id(self):
            raise ValueError("mainline support observation identity is invalid")
        if self.state_mapping_on_target and not self.quotient_state_id:
            raise ValueError("on-target state mapping requires a Quotient State identity")
        if self.replayable and not self.decision_trace_hash:
            raise ValueError("replayable trajectories require a decision-trace hash")
        if self.independent_validity_passed and self.terminal_status != "completed":
            raise ValueError("failed outcomes cannot pass independent trajectory validity")
        if (
            self.terminal_status == "runtime_failed"
            and self.runtime_eligible_for_capability_denominator
        ):
            raise ValueError("runtime failures cannot enter the capability denominator")
        if self.gp_c_independently_validated and not self.exact_target_exceeds_mpe:
            raise ValueError("GP-C cannot pass before a meaningful Exact Target")
        if self.distribution_update_contract_passed and not self.gp_c_independently_validated:
            raise ValueError("distribution update cannot pass before independent GP-C")
        if self.contribution_authorization_id and not self.contribution_eligible:
            raise ValueError("Contribution authorization requires the complete sealed chain")
        return self


class MainlineSupportPartition(FrozenModel):
    partition_id: str = Field(min_length=1)
    observation_count: int = Field(ge=1)
    measurement_observation_ids: tuple[str, ...]
    training_observation_ids: tuple[str, ...]
    contribution_observation_ids: tuple[str, ...]
    excluded_from_measurement: dict[str, tuple[str, ...]]
    excluded_from_training: dict[str, tuple[str, ...]]
    excluded_from_contribution: dict[str, tuple[str, ...]]
    measurement_count_by_capability: dict[str, int]
    training_count_by_capability: dict[str, int]
    contribution_count_by_capability: dict[str, int]
    terminal_status_counts: dict[str, int]
    failed_outcome_measurement_count: int = Field(ge=0)
    failed_outcome_training_count: Literal[0] = 0
    inverse_success_weighting_used: Literal[False] = False
    schema_version: str = MAINLINE_SUPPORT_PARTITION_VERSION

    @model_validator(mode="after")
    def validate_partition(self) -> MainlineSupportPartition:
        measurement = set(self.measurement_observation_ids)
        training = set(self.training_observation_ids)
        contribution = set(self.contribution_observation_ids)
        if not contribution <= training <= measurement:
            raise ValueError("support sets must satisfy S_C subset S_train subset S_measure")
        if any(
            values != tuple(sorted(set(values)))
            for values in (
                self.measurement_observation_ids,
                self.training_observation_ids,
                self.contribution_observation_ids,
            )
        ):
            raise ValueError("support partition identities are not unique and sorted")
        if self.partition_id != mainline_support_partition_id(self):
            raise ValueError("mainline support partition identity is invalid")
        return self


class MainlinePreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    checks: dict[str, bool]
    source_sha256: dict[str, str]
    code_sha256: dict[str, str]
    planned_task_count_by_split: dict[str, int]
    planned_explorer_rollout_count: int = Field(ge=0)
    historical_task_promotion_count: Literal[0] = 0
    fresh_population_task_count: Literal[0] = 0
    flash_api_call_count: Literal[0] = 0
    pro_api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    status: Literal["passed", "blocked"]
    blockers: tuple[str, ...]
    next_permitted_stage: Literal["v26_1_joint_compilation_admission", "blocked"]
    schema_version: str = MAINLINE_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> MainlinePreflightReport:
        expected_status = "passed" if self.checks and all(self.checks.values()) else "blocked"
        if self.status != expected_status:
            raise ValueError("mainline preflight status is inconsistent with its checks")
        expected_stage = (
            "v26_1_joint_compilation_admission" if self.status == "passed" else "blocked"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("mainline preflight transition is inconsistent")
        if bool(self.blockers) != (self.status == "blocked"):
            raise ValueError("mainline preflight blockers are inconsistent")
        if self.report_id != mainline_preflight_report_id(self):
            raise ValueError("mainline preflight identity is invalid")
        return self


def capability_heterogeneous_mainline_protocol_id(
    value: CapabilityHeterogeneousMainlineProtocol,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_v26_capability_heterogeneous_vtdo_mainline:",
    )


def mainline_support_observation_id(value: MainlineSupportObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="vtdo_mainline_support_observation:",
    )


def mainline_support_partition_id(value: MainlineSupportPartition) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"partition_id"}),
        prefix="vtdo_mainline_support_partition:",
    )


def mainline_preflight_report_id(value: MainlinePreflightReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_mainline_preflight:",
    )


def make_mainline_support_observation(**values: Any) -> MainlineSupportObservation:
    provisional = MainlineSupportObservation.model_construct(observation_id="pending", **values)
    return MainlineSupportObservation(
        observation_id=mainline_support_observation_id(provisional),
        **values,
    )


def partition_mainline_support(
    observations: Iterable[MainlineSupportObservation],
) -> MainlineSupportPartition:
    values = tuple(observations)
    if not values:
        raise ValueError("mainline support partition requires observations")
    if len({item.observation_id for item in values}) != len(values):
        raise ValueError("mainline support observations are duplicated")
    trace_hashes = [item.decision_trace_hash for item in values if item.training_eligible]
    if len(trace_hashes) != len(set(trace_hashes)):
        raise ValueError("positive training support contains duplicate decision traces")

    measurement = tuple(sorted(item.observation_id for item in values if item.measurement_eligible))
    training = tuple(sorted(item.observation_id for item in values if item.training_eligible))
    contribution = tuple(
        sorted(item.observation_id for item in values if item.contribution_eligible)
    )
    excluded_measurement = {
        item.observation_id: _measurement_exclusion_reasons(item)
        for item in values
        if not item.measurement_eligible
    }
    excluded_training = {
        item.observation_id: _training_exclusion_reasons(item)
        for item in values
        if not item.training_eligible
    }
    excluded_contribution = {
        item.observation_id: _contribution_exclusion_reasons(item)
        for item in values
        if not item.contribution_eligible
    }
    payload: dict[str, Any] = {
        "observation_count": len(values),
        "measurement_observation_ids": measurement,
        "training_observation_ids": training,
        "contribution_observation_ids": contribution,
        "excluded_from_measurement": dict(sorted(excluded_measurement.items())),
        "excluded_from_training": dict(sorted(excluded_training.items())),
        "excluded_from_contribution": dict(sorted(excluded_contribution.items())),
        "measurement_count_by_capability": _count_capabilities(
            item for item in values if item.measurement_eligible
        ),
        "training_count_by_capability": _count_capabilities(
            item for item in values if item.training_eligible
        ),
        "contribution_count_by_capability": _count_capabilities(
            item for item in values if item.contribution_eligible
        ),
        "terminal_status_counts": dict(
            sorted(Counter(item.terminal_status for item in values).items())
        ),
        "failed_outcome_measurement_count": sum(
            item.measurement_eligible and item.terminal_status != "completed" for item in values
        ),
        "failed_outcome_training_count": 0,
        "inverse_success_weighting_used": False,
        "schema_version": MAINLINE_SUPPORT_PARTITION_VERSION,
    }
    provisional = MainlineSupportPartition.model_construct(partition_id="pending", **payload)
    return MainlineSupportPartition(
        partition_id=mainline_support_partition_id(provisional),
        **payload,
    )


def build_mainline_protocol_and_preflight(
    *,
    run_id: str,
    prior_decision_path: Path,
    archive_config_path: Path,
    explorer_config_path: Path,
    student_config_path: Path,
    output_dir: Path,
) -> tuple[CapabilityHeterogeneousMainlineProtocol, MainlinePreflightReport]:
    protocol_path = output_dir / "finance_v26_mainline_protocol.json"
    preflight_path = output_dir / "finance_v26_mainline_preflight.json"
    if protocol_path.exists() or preflight_path.exists():
        raise ValueError("v26 mainline protocol artifacts are immutable")

    prior_decision_path = prior_decision_path.resolve()
    archive_config_path = archive_config_path.resolve()
    explorer_config_path = explorer_config_path.resolve()
    student_config_path = student_config_path.resolve()
    decision = ContextSufficiencyScientificDecision.model_validate_json(
        prior_decision_path.read_text(encoding="utf-8")
    )
    archive = FinanceArchiveConfig.from_json(archive_config_path)
    explorer_payload = _read_object(explorer_config_path)
    student_payload = _read_object(student_config_path)
    explorer_model = str(explorer_payload.get("model", {}).get("model", ""))
    student_model = str(student_payload.get("base_model", ""))

    prior = ImmutableArtifactReference(
        role="historical_measurement_hypothesis_only",
        artifact_id=decision.decision_id,
        schema_version=decision.schema_version,
        path=str(prior_decision_path),
        sha256=_sha256(prior_decision_path),
    )
    protocol_values: dict[str, Any] = {
        "run_id": run_id,
        "prior_evidence": (prior,),
        "population": _population_contract(),
        "joint_compilation": JointCompilationAdmissionContract(),
        "materialization": MainlineStateMaterializationContract(),
        "support": MainlineSupportContract(),
        "no_c": _no_c_contract(),
        "contribution": ContributionRecoveryContract(),
        "student_evaluation": StudentEvaluationContract(),
        "explorer_config_sha256": _sha256(explorer_config_path),
        "student_config_sha256": _sha256(student_config_path),
        "archive_config_sha256": _sha256(archive_config_path),
        "schema_version": FINANCE_V26_MAINLINE_VERSION,
    }
    provisional = CapabilityHeterogeneousMainlineProtocol.model_construct(
        protocol_id="pending", **protocol_values
    )
    protocol = CapabilityHeterogeneousMainlineProtocol(
        protocol_id=capability_heterogeneous_mainline_protocol_id(provisional),
        **protocol_values,
    )

    module_root = Path(__file__).resolve().parent
    code_paths = {
        "mainline_protocol": Path(__file__).resolve(),
        "task_population": module_root / "phase1_agent_population.py",
        "task_compiler": module_root / "phase1_capability_sensitive_frontier.py",
        "joint_compilation_admission": (
            Path(__file__).resolve().parents[2] / "core" / "trajectory" / "admission.py"
        ),
        "state_discovery": module_root / "phase1_initial_distribution.py",
        "state_materialization": module_root / "phase1_state_realizations.py",
        "student_training": module_root / "training.py",
    }
    checks = {
        "v25_47_static_construct_valid": decision.static_construct_validity_passed,
        "v25_47_runtime_measurement_valid": decision.runtime_measurement_passed,
        "v25_47_local_mechanism_not_reclassified": (
            not decision.contextual_mechanism_fidelity_passed
        ),
        "v25_47_governance_transition_preserved": (
            decision.governance_transition == "contextual_tool_selection_limitation_recorded"
        ),
        "v25_47_closed_authorizations_preserved": not any(
            (
                decision.pro_api_calls_authorized,
                decision.beneficiary_authorized,
                decision.exact_target_authorized,
                decision.gp_c_authorized,
                decision.additional_flash_rollouts_authorized,
            )
        ),
        "v25_47_production_contribution_zero": decision.production_contribution == 0.0,
        "explorer_is_flash": explorer_model == protocol.population.explorer_model,
        "student_is_qwen2_5_7b": "Qwen2.5-7B" in student_model,
        "archive_contract_files_exist": all(
            path.is_file()
            for path in (archive.kg_nodes_path, archive.kg_edges_path, archive.kg_report_path)
        ),
        "capability_registry_complete": (
            set(FAMILY_PRIMARY_CAPABILITY.values()) == set(CAPABILITY_AXES)
        ),
        "joint_compilation_phase_zero_frozen": (
            protocol.joint_compilation.pre_model_admission_required
            and protocol.joint_compilation.failure_transition == "joint_compilation_repair_only"
        ),
        "support_sets_fail_closed": protocol.support.inverse_success_weighting_forbidden,
        "no_c_claim_boundary_explicit": (
            protocol.no_c.claim_label == "novelty_anchored_vtdo_not_full_c_plus_n"
        ),
        "contribution_branch_remains_blocked": not any(
            (
                protocol.contribution.exact_target_authorized,
                protocol.contribution.gp_c_authorized,
                protocol.contribution.full_c_plus_n_authorized,
            )
        ),
        "historical_task_promotion_zero": protocol.historical_task_promotion_count == 0,
        "implementation_files_present": all(path.is_file() for path in code_paths.values()),
    }
    blockers = tuple(sorted(name for name, passed in checks.items() if not passed))
    report_values: dict[str, Any] = {
        "protocol_id": protocol.protocol_id,
        "checks": checks,
        "source_sha256": {
            "prior_decision": prior.sha256,
            "archive_config": protocol.archive_config_sha256,
            "explorer_config": protocol.explorer_config_sha256,
            "student_config": protocol.student_config_sha256,
        },
        "code_sha256": {name: _sha256(path) for name, path in sorted(code_paths.items())},
        "planned_task_count_by_split": dict(_EXPECTED_SPLIT_COUNTS),
        "planned_explorer_rollout_count": 100 * 8,
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "next_permitted_stage": ("blocked" if blockers else "v26_1_joint_compilation_admission"),
        "schema_version": MAINLINE_PREFLIGHT_VERSION,
    }
    provisional_report = MainlinePreflightReport.model_construct(
        report_id="pending", **report_values
    )
    report = MainlinePreflightReport(
        report_id=mainline_preflight_report_id(provisional_report),
        **report_values,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(protocol_path, protocol.model_dump(mode="json"))
    _write_json_atomic(preflight_path, report.model_dump(mode="json"))
    return protocol, report


def _population_contract() -> MainlinePopulationContract:
    return MainlinePopulationContract(
        splits=(
            MainlineDataSplitContract(
                split_id="synthesis_training",
                task_count=100,
                purpose="state discovery, materialization, No-C rounds, and Student training",
                state_discovery_enabled=True,
                explorer_rollouts_per_task=8,
            ),
            MainlineDataSplitContract(
                split_id="internal_agent_evaluation",
                task_count=60,
                purpose="held-out capability-slice and Agent behavior evaluation",
                state_discovery_enabled=False,
                explorer_rollouts_per_task=0,
            ),
            MainlineDataSplitContract(
                split_id="exact_target_development",
                task_count=30,
                purpose="isolated Exact Target development for new Agent states",
                state_discovery_enabled=False,
                explorer_rollouts_per_task=0,
            ),
            MainlineDataSplitContract(
                split_id="exact_target_validation",
                task_count=60,
                purpose="sealed Exact Target validation opened only after a meaningful coordinate",
                state_discovery_enabled=False,
                explorer_rollouts_per_task=0,
            ),
        ),
        capability_axes=CAPABILITY_AXES,
        finance_task_families=CAPABILITY_SENSITIVE_FAMILIES,
    )


def _no_c_contract() -> NoCDistributionContract:
    return NoCDistributionContract(
        student_arms=(
            NoCStudentArmContract(
                arm_id="B1_raw",
                role="quality_lower_bound",
                fixed_task_marginal_required=False,
                training_round=0,
            ),
            NoCStudentArmContract(
                arm_id="B2_validity",
                role="primary_causal",
                fixed_task_marginal_required=True,
                training_round=0,
            ),
            NoCStudentArmContract(
                arm_id="B4_random_state",
                role="primary_causal",
                fixed_task_marginal_required=True,
                training_round=0,
            ),
            NoCStudentArmContract(
                arm_id="B2_novelty_only",
                role="primary_causal",
                fixed_task_marginal_required=True,
                training_round=0,
            ),
            NoCStudentArmContract(
                arm_id="B5_no_c_round_1",
                role="primary_causal",
                fixed_task_marginal_required=True,
                training_round=1,
            ),
            NoCStudentArmContract(
                arm_id="B5_no_c_round_3",
                role="primary_causal",
                fixed_task_marginal_required=True,
                training_round=3,
            ),
            NoCStudentArmContract(
                arm_id="B3_ccgr",
                role="secondary_comparison",
                fixed_task_marginal_required=False,
                training_round=0,
            ),
        )
    )


def _measurement_exclusion_reasons(item: MainlineSupportObservation) -> tuple[str, ...]:
    reasons = []
    if not item.construct_valid:
        reasons.append("construct_invalid")
    if not item.runtime_eligible_for_capability_denominator:
        reasons.append("runtime_ineligible")
    if not item.observable:
        reasons.append("outcome_unobservable")
    if not item.interference_free:
        reasons.append("host_agent_interference")
    return tuple(reasons)


def _training_exclusion_reasons(item: MainlineSupportObservation) -> tuple[str, ...]:
    reasons = list(_measurement_exclusion_reasons(item))
    predicates = (
        (item.split_id == "synthesis_training", "not_synthesis_training_split"),
        (item.phase == "materialization", "discovery_not_positive_materialization"),
        (item.terminal_status == "completed", "trajectory_not_completed"),
        (item.independent_validity_passed, "independent_validity_failed"),
        (bool(item.quotient_state_id), "quotient_state_missing"),
        (item.state_mapping_on_target, "state_mapping_off_target"),
        (item.replayable, "trajectory_not_replayable"),
        (bool(item.decision_trace_hash), "decision_trace_hash_missing"),
    )
    reasons.extend(reason for passed, reason in predicates if not passed)
    return tuple(reasons)


def _contribution_exclusion_reasons(item: MainlineSupportObservation) -> tuple[str, ...]:
    reasons = list(_training_exclusion_reasons(item))
    predicates = (
        (bool(item.beneficiary_boundary_id), "beneficiary_boundary_missing"),
        (bool(item.contribution_authorization_id), "contribution_authorization_missing"),
        (item.exact_target_exceeds_mpe, "exact_target_not_meaningful"),
        (item.gp_c_independently_validated, "gp_c_not_independently_validated"),
        (item.distribution_update_contract_passed, "distribution_update_contract_failed"),
    )
    reasons.extend(reason for passed, reason in predicates if not passed)
    return tuple(reasons)


def _count_capabilities(values: Iterable[MainlineSupportObservation]) -> dict[str, int]:
    counts = Counter(item.capability_axis for item in values)
    axes = cast(tuple[CapabilityAxis, ...], CAPABILITY_AXES)
    return {axis: counts.get(axis, 0) for axis in axes}


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze the capability-heterogeneous Finance v26 VTDO mainline protocol."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prior-decision-path", type=Path, required=True)
    parser.add_argument("--archive-config-path", type=Path, required=True)
    parser.add_argument("--explorer-config-path", type=Path, required=True)
    parser.add_argument("--student-config-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    protocol, report = build_mainline_protocol_and_preflight(
        run_id=args.run_id,
        prior_decision_path=args.prior_decision_path,
        archive_config_path=args.archive_config_path,
        explorer_config_path=args.explorer_config_path,
        student_config_path=args.student_config_path,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "protocol_id": protocol.protocol_id,
                "preflight_report_id": report.report_id,
                "status": report.status,
                "next_permitted_stage": report.next_permitted_stage,
                "flash_api_call_count": report.flash_api_call_count,
                "gpu_job_count": report.gpu_job_count,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
