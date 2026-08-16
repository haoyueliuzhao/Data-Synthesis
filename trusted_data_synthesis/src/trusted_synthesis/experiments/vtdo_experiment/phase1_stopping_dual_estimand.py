from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (  # noqa: E501
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (  # noqa: E501
    CapabilityBoundaryRolloutRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (  # noqa: E501
    CAPABILITY_AXES,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    SubmechanismBehaviorObservation,
    _make_terminals,
    make_submechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (  # noqa: E501
    _execute_stage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (  # noqa: E501
    FailureLayer,
    RuntimeResolutionStage,
    RuntimeTerminalOutcome,
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (  # noqa: E501
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_boundary_calibration import (  # noqa: E501
    FinanceStoppingBoundaryCalibrationContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_dual_estimand_protocol import (  # noqa: E501
    ALL_SHAPES,
    EXPECTED_ROLLOUT_COUNT,
    EXPECTED_TASK_COUNT,
    PROSPECTIVE_RECHECK_SHAPES,
    REPLICAS,
    STRUCTURAL_REDESIGN_SHAPES,
    STRUCTURAL_STRATA,
    TASKS_PER_SHAPE,
    FinanceStoppingDualEstimandPopulation,
    FinanceStoppingDualEstimandProtocol,
    StoppingDualEstimandDefinition,
    StoppingDualEstimandThresholds,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (  # noqa: E501
    FrozenArtifactReference,
    StoppingShapeDifficultyVector,
    StoppingShapeTask,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

STOPPING_DUAL_ESTIMAND_CONTRACT_VERSION = "finance_stopping_dual_estimand_contract.v1"
STOPPING_DUAL_ESTIMAND_RESULT_VERSION = "finance_stopping_dual_estimand_result.v1"
STOPPING_DUAL_ESTIMAND_POLICY_VERSION = "finance_stopping_dual_estimand_policy.v1"
STOPPING_DUAL_ESTIMAND_REPORT_VERSION = "finance_stopping_dual_estimand_report.v1"
STOPPING_DUAL_ESTIMAND_MANIFEST_VERSION = "finance_stopping_dual_estimand_manifest.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceStoppingDualEstimandContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_38_stopping_dual_estimand_development"] = (
        "finance_v25_38_stopping_dual_estimand_development"
    )
    stage: RuntimeResolutionStage = RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
    source_protocol: FrozenArtifactReference
    source_population: FrozenArtifactReference
    source_calibration_contract: FrozenArtifactReference
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=1, max_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    estimand_definition: StoppingDualEstimandDefinition
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_records: tuple[StoppingShapeTask, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_shape_ids: dict[str, str]
    task_shape_roles: dict[str, Literal["boundary_candidate", "runtime_control"]]
    task_design_statuses: dict[str, Literal["prospective_estimand_recheck", "structural_redesign"]]
    task_stratum_ids: dict[str, str]
    task_stratum_instance_indices: dict[str, int]
    task_submechanism_ids: dict[str, str]
    task_parent_mechanism_ids: dict[str, str]
    task_instance_ids: dict[str, str]
    task_expected_host_events: dict[str, tuple[str, str]]
    task_raw_capability_demands: dict[str, dict[str, float]]
    task_difficulty_vectors: dict[str, StoppingShapeDifficultyVector]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    replicas: Literal[8] = 8
    requested_rollout_count: Literal[384] = 384
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    thresholds: StoppingDualEstimandThresholds
    primary_response_variable: Literal["stopping_behavior_success"] = "stopping_behavior_success"
    valid_training_response_variable: Literal["full_valid_trajectory_success"] = (
        "full_valid_trajectory_success"
    )
    diagnostic_response_variable: Literal["answer_semantic_success"] = "answer_semantic_success"
    support_layers: tuple[
        Literal["mechanism_observable_support"],
        Literal["valid_training_support"],
        Literal["contribution_authorized_support"],
    ] = (
        "mechanism_observable_support",
        "valid_training_support",
        "contribution_authorized_support",
    )
    task_instance_is_primary_sampling_unit: Literal[True] = True
    hierarchical_bootstrap_levels: tuple[
        Literal["independent_task"],
        Literal["realization"],
    ] = (
        "independent_task",
        "realization",
    )
    pooled_result_may_rescue_shape_failure: Literal[False] = False
    cross_estimand_rescue_forbidden: Literal[True] = True
    invalid_trajectory_training_use_forbidden: Literal[True] = True
    posthoc_task_selection_authorized: Literal[False] = False
    posthoc_task_deletion_authorized: Literal[False] = False
    historical_results_reclassified: Literal[False] = False
    historical_results_transfer_authorized: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_stopping_dual_estimand_development"] = (
        "flash_stopping_dual_estimand_development"
    )
    schema_version: str = STOPPING_DUAL_ESTIMAND_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStoppingDualEstimandContract:
        if self.stage != RuntimeResolutionStage.RESIDUAL_DEVELOPMENT:
            raise ValueError("Stopping dual-estimand must remain Development-only")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("Stopping dual-estimand Development must remain Flash-only")
        if self.estimand_definition != StoppingDualEstimandDefinition():
            raise ValueError("Stopping dual-estimand definition changed")
        if self.requested_rollout_count != len(self.bindings) * self.replicas:
            raise ValueError("Stopping dual-estimand rollout denominator is inconsistent")
        task_ids = {item.artifact_id for item in self.tasks}
        record_ids = {item.artifact.artifact_id for item in self.task_records}
        if task_ids != record_ids:
            raise ValueError("Stopping dual-estimand task and record identities differ")
        maps: tuple[Mapping[str, Any], ...] = (
            self.task_shape_ids,
            self.task_shape_roles,
            self.task_design_statuses,
            self.task_stratum_ids,
            self.task_stratum_instance_indices,
            self.task_submechanism_ids,
            self.task_parent_mechanism_ids,
            self.task_instance_ids,
            self.task_expected_host_events,
            self.task_raw_capability_demands,
            self.task_difficulty_vectors,
        )
        if any(set(item) != task_ids for item in maps):
            raise ValueError("Stopping dual-estimand task maps are incomplete")
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("Stopping dual-estimand Runtime bindings are incomplete")
        if any(item.runtime_arm != CapabilityRuntimeArm.AUTONOMOUS_AGENT for item in self.bindings):
            raise ValueError("Stopping dual-estimand requires Autonomous Agent Runtime")
        if set(self.task_shape_ids.values()) != ALL_SHAPES:
            raise ValueError("Stopping dual-estimand coverage is incomplete")
        if any(
            set(value) != set(CAPABILITY_AXES)
            for value in self.task_raw_capability_demands.values()
        ):
            raise ValueError("Stopping dual-estimand capability demand omits an axis")
        shape_stratum_indices: dict[tuple[str, str], set[int]] = defaultdict(set)
        for task_id in task_ids:
            shape_stratum_indices[
                (self.task_shape_ids[task_id], self.task_stratum_ids[task_id])
            ].add(self.task_stratum_instance_indices[task_id])
        expected_cells = {
            (shape_id, stratum[0]) for shape_id in ALL_SHAPES for stratum in STRUCTURAL_STRATA
        }
        if set(shape_stratum_indices) != expected_cells or any(
            value != {0, 1} for value in shape_stratum_indices.values()
        ):
            raise ValueError("Stopping dual-estimand task pairing is incomplete")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("Stopping dual-estimand rollout identities are incomplete")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_dual_estimand_implementation:",
        ):
            raise ValueError("Stopping dual-estimand execution identity is invalid")
        if self.contract_id != stopping_dual_estimand_contract_id(self):
            raise ValueError("Stopping dual-estimand contract identity is invalid")
        return self


class StoppingDualEstimandObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    source_behavior_observation_id: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    shape_id: str = Field(min_length=1)
    stratum_id: str = Field(min_length=1)
    replicate: int = Field(ge=0)
    runtime_eligible: bool
    host_event_ordered: bool
    post_completion_violation_observed: bool
    stopping_behavior_success: bool
    terminal_valid_success: bool
    full_valid_trajectory_success: bool
    answer_semantic_success: bool
    final_answer_emitted: bool
    stop_quality_success: bool
    terminalization_success: bool
    cross_estimand_rescue_used: Literal[False] = False
    training_eligible: bool
    schema_version: str = "finance_stopping_dual_estimand_observation.v1"

    @model_validator(mode="after")
    def validate_observation(self) -> StoppingDualEstimandObservation:
        expected_stop = (
            self.runtime_eligible
            and self.host_event_ordered
            and not self.post_completion_violation_observed
        )
        if self.stopping_behavior_success != expected_stop:
            raise ValueError("Stopping behavior estimand is inconsistent")
        if self.full_valid_trajectory_success != (
            self.stopping_behavior_success and self.terminal_valid_success
        ):
            raise ValueError("Full-valid trajectory estimand is inconsistent")
        if self.terminalization_success != (
            self.final_answer_emitted and self.stop_quality_success
        ):
            raise ValueError("Stopping terminalization diagnostic is inconsistent")
        if self.training_eligible != self.full_valid_trajectory_success:
            raise ValueError("Invalid trajectory entered valid training support")
        if self.observation_id != stopping_dual_estimand_observation_id(self):
            raise ValueError("Stopping dual-estimand observation identity is invalid")
        return self


class StoppingDualEstimandTaskResponse(FrozenModel):
    task_artifact_id: str = Field(min_length=1)
    stratum_id: str = Field(min_length=1)
    stratum_instance_index: int = Field(ge=0, le=1)
    stopping_realizations: tuple[int, ...] = Field(min_length=REPLICAS, max_length=REPLICAS)
    full_valid_realizations: tuple[int, ...] = Field(min_length=REPLICAS, max_length=REPLICAS)
    semantic_realizations: tuple[int, ...] = Field(min_length=REPLICAS, max_length=REPLICAS)
    stopping_probability: float = Field(ge=0, le=1)
    full_valid_probability: float = Field(ge=0, le=1)
    semantic_probability: float = Field(ge=0, le=1)
    stopping_fisher_information: float = Field(ge=0, le=0.25)
    full_valid_fisher_information: float = Field(ge=0, le=0.25)

    @model_validator(mode="after")
    def validate_response(self) -> StoppingDualEstimandTaskResponse:
        rows = (
            (self.stopping_realizations, self.stopping_probability),
            (self.full_valid_realizations, self.full_valid_probability),
            (self.semantic_realizations, self.semantic_probability),
        )
        if any(value not in {0, 1} for values, _ in rows for value in values):
            raise ValueError("Stopping dual-estimand realizations must be binary")
        if any(
            not math.isclose(sum(values) / len(values), probability, abs_tol=1e-12)
            for values, probability in rows
        ):
            raise ValueError("Stopping dual-estimand task probability is inconsistent")
        if not math.isclose(
            self.stopping_fisher_information,
            self.stopping_probability * (1.0 - self.stopping_probability),
            abs_tol=1e-12,
        ):
            raise ValueError("Stopping Fisher information is inconsistent")
        if not math.isclose(
            self.full_valid_fisher_information,
            self.full_valid_probability * (1.0 - self.full_valid_probability),
            abs_tol=1e-12,
        ):
            raise ValueError("Full-valid Fisher information is inconsistent")
        if any(
            full_valid > stopping
            for full_valid, stopping in zip(
                self.full_valid_realizations,
                self.stopping_realizations,
                strict=True,
            )
        ):
            raise ValueError("Full-valid support exceeds stopping-behavior support")
        return self


class StoppingDualEstimandResult(FrozenModel):
    shape_id: str = Field(min_length=1)
    shape_role: Literal["boundary_candidate", "runtime_control"]
    design_status: Literal["prospective_estimand_recheck", "structural_redesign"]
    task_count: Literal[8] = 8
    rollout_count: Literal[64] = 64
    task_responses: tuple[StoppingDualEstimandTaskResponse, ...] = Field(
        min_length=TASKS_PER_SHAPE, max_length=TASKS_PER_SHAPE
    )
    admission_response_variable: Literal["stopping_behavior_success"] = "stopping_behavior_success"
    valid_information_used_for_admission: Literal[False] = False
    semantic_information_used_for_admission: Literal[False] = False
    mean_stopping_success_rate: float = Field(ge=0, le=1)
    mean_full_valid_success_rate: float = Field(ge=0, le=1)
    mean_semantic_success_rate: float = Field(ge=0, le=1)
    minimum_stopping_task_probability: float = Field(ge=0, le=1)
    maximum_stopping_task_probability: float = Field(ge=0, le=1)
    between_task_stopping_probability_range: float = Field(ge=0, le=1)
    stopping_boundary_task_count: int = Field(ge=0, le=TASKS_PER_SHAPE)
    stopping_nonzero_information_task_count: int = Field(ge=0, le=TASKS_PER_SHAPE)
    total_stopping_fisher_information: float = Field(ge=0)
    total_full_valid_fisher_information: float = Field(ge=0)
    stopping_effective_task_count: float = Field(ge=0, le=TASKS_PER_SHAPE)
    stopping_maximum_single_task_information_share: float = Field(ge=0, le=1)
    stopping_bootstrap_information_interval95: tuple[float, float]
    stopping_bootstrap_information_lcb: float = Field(ge=0)
    valid_training_trajectory_count: int = Field(ge=0, le=64)
    valid_training_support_rate: float = Field(ge=0, le=1)
    gate_results: dict[str, bool]
    admitted: bool
    failure_codes: tuple[str, ...]
    schema_version: str = STOPPING_DUAL_ESTIMAND_RESULT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> StoppingDualEstimandResult:
        observed = {(item.stratum_id, item.stratum_instance_index) for item in self.task_responses}
        expected = {(stratum[0], instance) for stratum in STRUCTURAL_STRATA for instance in (0, 1)}
        if observed != expected:
            raise ValueError("Stopping dual-estimand response pairing is incomplete")
        if self.admitted != all(self.gate_results.values()):
            raise ValueError("Stopping dual-estimand admission is inconsistent")
        if self.failure_codes != tuple(
            sorted(key for key, passed in self.gate_results.items() if not passed)
        ):
            raise ValueError("Stopping dual-estimand failure codes are inconsistent")
        if self.valid_training_trajectory_count != sum(
            sum(item.full_valid_realizations) for item in self.task_responses
        ):
            raise ValueError("Valid training-support count is inconsistent")
        if not math.isclose(
            self.valid_training_support_rate,
            self.valid_training_trajectory_count / self.rollout_count,
            abs_tol=1e-12,
        ):
            raise ValueError("Valid training-support rate is inconsistent")
        return self


class FrozenStoppingDualEstimandPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    shape_task_quotas: dict[str, Literal[8]]
    shape_stratum_task_quota: Literal[2] = 2
    structural_strata: tuple[tuple[str, str, Any], ...]
    thresholds: StoppingDualEstimandThresholds
    capability_response: Literal["stopping_behavior_success"] = "stopping_behavior_success"
    training_response: Literal["full_valid_trajectory_success"] = "full_valid_trajectory_success"
    cross_estimand_rescue_forbidden: Literal[True] = True
    primary_sampling_unit: Literal["independent_finance_task"] = "independent_finance_task"
    per_population_evaluation_required: Literal[True] = True
    hierarchical_bootstrap_required: Literal[True] = True
    pooled_rescue_forbidden: Literal[True] = True
    posthoc_task_selection_forbidden: Literal[True] = True
    fresh_population_disjointness_dimensions: tuple[str, ...] = (
        "task_artifact_id",
        "evidence_id",
        "evidence_version_id",
        "source_semantic_signature",
        "materializer_hash",
    )
    schema_version: str = STOPPING_DUAL_ESTIMAND_POLICY_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> FrozenStoppingDualEstimandPolicy:
        if set(self.shape_task_quotas) != ALL_SHAPES:
            raise ValueError("Stopping dual-estimand policy lacks a Shape")
        if set(self.shape_task_quotas.values()) != {TASKS_PER_SHAPE}:
            raise ValueError("Stopping dual-estimand policy changed Shape quota")
        if self.policy_id != stopping_dual_estimand_policy_id(self):
            raise ValueError("Stopping dual-estimand policy identity is invalid")
        return self


class FinanceStoppingDualEstimandReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    requested_rollout_count: Literal[384] = 384
    recorded_rollout_count: int = Field(ge=0, le=EXPECTED_ROLLOUT_COUNT)
    execution_integrity_rate: float = Field(ge=0, le=1)
    terminal_resolution_rate: float = Field(ge=0, le=1)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    runtime_pathology_rate: float = Field(ge=0, le=1)
    l0_l2_failure_count: int = Field(ge=0)
    stopping_behavior_success_rate: float = Field(ge=0, le=1)
    full_valid_trajectory_success_rate: float = Field(ge=0, le=1)
    answer_semantic_success_rate: float = Field(ge=0, le=1)
    terminalization_success_rate: float = Field(ge=0, le=1)
    valid_training_trajectory_count: int = Field(ge=0, le=EXPECTED_ROLLOUT_COUNT)
    valid_training_support_ready: bool
    runtime_measurement_ready: bool
    shape_results: tuple[StoppingDualEstimandResult, ...] = Field(
        min_length=len(ALL_SHAPES), max_length=len(ALL_SHAPES)
    )
    prospective_recheck_failure_count: int = Field(ge=0, le=3)
    structural_redesign_admission_count: int = Field(ge=0, le=3)
    mechanism_observable_shape_count: int = Field(ge=0, le=6)
    all_shapes_admitted: bool
    policy: FrozenStoppingDualEstimandPolicy | None
    policy_frozen: bool
    pooled_result_used_for_admission: Literal[False] = False
    cross_estimand_rescue_used: Literal[False] = False
    posthoc_task_selection_used: Literal[False] = False
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    discovered_models: tuple[str, ...]
    failure_codes: tuple[str, ...]
    fresh_three_population_preparation_authorized: bool
    contribution_authorized_support: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "fresh_three_population_dual_estimand_preparation",
        "runtime_measurement_repair_only",
        "stopping_shape_redesign_only",
        "valid_training_support_repair_only",
    ]
    schema_version: str = STOPPING_DUAL_ESTIMAND_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStoppingDualEstimandReport:
        by_shape = {item.shape_id: item for item in self.shape_results}
        if set(by_shape) != ALL_SHAPES:
            raise ValueError("Stopping dual-estimand report coverage is incomplete")
        recheck_failures = sum(
            not by_shape[shape_id].admitted for shape_id in PROSPECTIVE_RECHECK_SHAPES
        )
        redesigns = sum(by_shape[shape_id].admitted for shape_id in STRUCTURAL_REDESIGN_SHAPES)
        if self.prospective_recheck_failure_count != recheck_failures:
            raise ValueError("Prospective Shape recheck accounting is invalid")
        if self.structural_redesign_admission_count != redesigns:
            raise ValueError("Structural Shape redesign accounting is invalid")
        shape_ready = all(item.admitted for item in self.shape_results)
        if self.mechanism_observable_shape_count != sum(
            item.admitted for item in self.shape_results
        ):
            raise ValueError("Mechanism-observable support count is inconsistent")
        if self.all_shapes_admitted != shape_ready:
            raise ValueError("Stopping Shape aggregate admission is inconsistent")
        if self.valid_training_trajectory_count != sum(
            item.valid_training_trajectory_count for item in self.shape_results
        ):
            raise ValueError("Aggregate valid training-support count is inconsistent")
        mechanism_ready = self.runtime_measurement_ready and shape_ready
        valid_support_ready = all(
            item.valid_training_trajectory_count > 0 for item in self.shape_results
        )
        if self.valid_training_support_ready != valid_support_ready:
            raise ValueError("Valid training-support decision is inconsistent")
        if self.policy_frozen != mechanism_ready:
            raise ValueError("Stopping dual-estimand policy decision is inconsistent")
        if (self.policy is not None) != mechanism_ready:
            raise ValueError("Stopping dual-estimand policy presence is inconsistent")
        preparation_ready = mechanism_ready and valid_support_ready
        if self.fresh_three_population_preparation_authorized != preparation_ready:
            raise ValueError("Stopping dual-estimand authorization is inconsistent")
        expected_stage = (
            "runtime_measurement_repair_only"
            if not self.runtime_measurement_ready
            else (
                "stopping_shape_redesign_only"
                if not shape_ready
                else (
                    "fresh_three_population_dual_estimand_preparation"
                    if valid_support_ready
                    else "valid_training_support_repair_only"
                )
            )
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Stopping dual-estimand transition is not fail-closed")
        if self.report_id != stopping_dual_estimand_report_id(self):
            raise ValueError("Stopping dual-estimand report identity is invalid")
        return self


def stopping_dual_estimand_contract_id(value: FinanceStoppingDualEstimandContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_stopping_dual_estimand_contract:",
    )


def stopping_dual_estimand_observation_id(
    value: StoppingDualEstimandObservation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="finance_stopping_dual_estimand_observation:",
    )


def stopping_dual_estimand_policy_id(value: FrozenStoppingDualEstimandPolicy) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"policy_id"}),
        prefix="finance_stopping_dual_estimand_policy:",
    )


def stopping_dual_estimand_report_id(value: FinanceStoppingDualEstimandReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_stopping_dual_estimand_report:",
    )


def prepare_stopping_dual_estimand_contract(
    *,
    protocol_path: Path,
    population_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStoppingDualEstimandContract:
    if output_path.exists():
        raise ValueError("Stopping dual-estimand contract is immutable")
    protocol_path = protocol_path.resolve()
    population_path = population_path.resolve()
    protocol = FinanceStoppingDualEstimandProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    population = FinanceStoppingDualEstimandPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    _verify_population(protocol, population, population_path)
    if not population.static_audit.ready:
        raise ValueError("Stopping dual-estimand population did not pass static gates")
    calibration_path = Path(protocol.source_calibration_contract.path).resolve()
    calibration = FinanceStoppingBoundaryCalibrationContract.model_validate_json(
        calibration_path.read_text(encoding="utf-8")
    )
    model_contracts = tuple(
        item for item in calibration.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("Stopping dual-estimand contract lacks exactly one Flash model")
    tasks = tuple(item.artifact for item in population.tasks)
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            calibration.protocol_profile,
        )
        for task in tasks
    )
    record_by_task = {item.artifact.artifact_id: item for item in population.tasks}
    design_by_shape = {item.shape_id: item for item in protocol.shape_designs}
    task_instances = {
        task_id: canonical_hash(
            {
                "task_record_id": item.task_record_id,
                "shape_id": item.shape_id,
                "stratum_id": item.stratum_id,
                "stratum_instance_index": population.task_stratum_instance_indices[task_id],
                "design_status": population.task_design_statuses[task_id],
                "semantic_signature": item.source_semantic_signature,
                "materializer_hash": item.materializer_hash,
                "estimand_definition": protocol.estimand_definition,
            },
            prefix="finance_stopping_dual_estimand_task_instance:",
        )
        for task_id, item in record_by_task.items()
    }
    rollout_tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
                "task_instance_id": task_instances[binding.task_artifact_id],
            },
            prefix="finance_stopping_dual_estimand_rollout:",
        )
        for binding in bindings
        for replicate in range(REPLICAS)
    }
    implementation = _implementation_manifest()
    finance_config = Path(calibration.finance_archive_config_path).resolve()
    values = {
        "run_id": run_id,
        "source_protocol": _reference(protocol_path, protocol.protocol_id),
        "source_population": _reference(population_path, population.population_id),
        "source_calibration_contract": _reference(calibration_path, calibration.contract_id),
        "finance_archive_config_path": str(finance_config),
        "finance_archive_config_sha256": _sha256(finance_config),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stopping_dual_estimand_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": calibration.protocol_profile,
        "estimand_definition": protocol.estimand_definition,
        "tasks": tasks,
        "task_records": population.tasks,
        "task_shape_ids": {task_id: item.shape_id for task_id, item in record_by_task.items()},
        "task_shape_roles": {task_id: item.shape_role for task_id, item in record_by_task.items()},
        "task_design_statuses": population.task_design_statuses,
        "task_stratum_instance_indices": population.task_stratum_instance_indices,
        "task_stratum_ids": {task_id: item.stratum_id for task_id, item in record_by_task.items()},
        "task_submechanism_ids": {
            task_id: item.scenario.submechanism_id for task_id, item in record_by_task.items()
        },
        "task_parent_mechanism_ids": {
            task_id: item.scenario.parent_mechanism_id for task_id, item in record_by_task.items()
        },
        "task_instance_ids": task_instances,
        "task_expected_host_events": population.task_expected_host_events,
        "task_raw_capability_demands": {
            task_id: design_by_shape[item.shape_id].spec.raw_capability_demand
            for task_id, item in record_by_task.items()
        },
        "task_difficulty_vectors": {
            task_id: item.difficulty for task_id, item in record_by_task.items()
        },
        "bindings": bindings,
        "maximum_model_tokens_per_rollout": calibration.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": calibration.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": calibration.maximum_public_context_bytes,
        "model_contract_repair_attempts": calibration.model_contract_repair_attempts,
        "rollout_identity_tokens": rollout_tokens,
        "thresholds": protocol.thresholds,
    }
    provisional = FinanceStoppingDualEstimandContract.model_construct(
        contract_id="pending", **values
    )
    contract = FinanceStoppingDualEstimandContract(
        contract_id=stopping_dual_estimand_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, contract.model_dump(mode="json"))
    return contract


def make_stopping_dual_estimand_observations(
    contract: FinanceStoppingDualEstimandContract,
    behaviors: Sequence[SubmechanismBehaviorObservation],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
) -> tuple[StoppingDualEstimandObservation, ...]:
    outcome_by_key = {(item.binding_id, item.replicate): item for item in outcomes}
    terminal_by_key = {(item.binding_id, item.replicate): item for item in terminals}
    rows = []
    for behavior in sorted(behaviors, key=lambda item: (item.binding_id, item.replicate)):
        key = (behavior.binding_id, behavior.replicate)
        outcome = outcome_by_key[key]
        terminal = terminal_by_key[key]
        stopping = bool(
            behavior.runtime_eligible
            and behavior.host_event_ordered
            and not behavior.post_completion_violation_observed
        )
        full_valid = stopping and terminal.valid_success
        values = {
            "contract_id": contract.contract_id,
            "source_behavior_observation_id": behavior.observation_id,
            "record_id": behavior.record_id,
            "binding_id": behavior.binding_id,
            "task_artifact_id": behavior.task_artifact_id,
            "shape_id": contract.task_shape_ids[behavior.task_artifact_id],
            "stratum_id": contract.task_stratum_ids[behavior.task_artifact_id],
            "replicate": behavior.replicate,
            "runtime_eligible": behavior.runtime_eligible,
            "host_event_ordered": behavior.host_event_ordered,
            "post_completion_violation_observed": (behavior.post_completion_violation_observed),
            "stopping_behavior_success": stopping,
            "terminal_valid_success": terminal.valid_success,
            "full_valid_trajectory_success": full_valid,
            "answer_semantic_success": terminal.semantic_answer_correct,
            "final_answer_emitted": outcome.final_answer_emitted,
            "stop_quality_success": outcome.stop_quality_success,
            "terminalization_success": bool(
                outcome.final_answer_emitted and outcome.stop_quality_success
            ),
            "training_eligible": full_valid,
        }
        provisional = StoppingDualEstimandObservation.model_construct(
            observation_id="pending", **values
        )
        rows.append(
            StoppingDualEstimandObservation(
                observation_id=stopping_dual_estimand_observation_id(provisional),
                **values,
            )
        )
    if len(rows) != contract.requested_rollout_count:
        raise ValueError("Stopping dual-estimand observation denominator is incomplete")
    return tuple(rows)


def run_stopping_dual_estimand(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceStoppingDualEstimandReport:
    contract = FinanceStoppingDualEstimandContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_contract_inputs(contract)
    prefix = "stopping_dual_estimand_development"
    outcomes, discovered = _execute_stage(
        contract=cast(Any, contract),
        tasks={item.artifact_id: item for item in contract.tasks},
        bindings=contract.bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=contract.replicas,
        output_dir=output_dir,
        prefix=prefix,
        workers=workers,
    )
    records_path = output_dir / f"{prefix}_records.jsonl"
    outcomes_path = output_dir / f"{prefix}_outcomes.jsonl"
    records = _load_records(records_path)
    terminals = _make_terminals(cast(Any, contract), records, outcomes)
    legacy_behaviors = make_submechanism_behavior_observations(
        cast(Any, contract), records, outcomes, terminals
    )
    observations = make_stopping_dual_estimand_observations(
        contract,
        legacy_behaviors,
        outcomes,
        terminals,
    )
    terminal_path = output_dir / f"{prefix}_terminal_outcomes.jsonl"
    legacy_path = output_dir / f"{prefix}_legacy_behavior_diagnostics.jsonl"
    observation_path = output_dir / f"{prefix}_dual_estimand_observations.jsonl"
    _write_jsonl(terminal_path, (item.model_dump(mode="json") for item in terminals))
    _write_jsonl(legacy_path, (item.model_dump(mode="json") for item in legacy_behaviors))
    _write_jsonl(observation_path, (item.model_dump(mode="json") for item in observations))
    report = make_stopping_dual_estimand_report(
        contract,
        records,
        outcomes,
        terminals,
        observations,
        discovered_models=discovered,
    )
    report_path = output_dir / "finance_stopping_dual_estimand_report.json"
    _write_json(report_path, report.model_dump(mode="json"))
    (output_dir / "finance_stopping_dual_estimand_report.md").write_text(
        _render_report(report), encoding="utf-8"
    )
    manifest = {
        "schema_version": STOPPING_DUAL_ESTIMAND_MANIFEST_VERSION,
        "contract_id": contract.contract_id,
        "report_id": report.report_id,
        "requested_model": contract.model_contracts[0].requested_model,
        "discovered_models": discovered,
        "records_sha256": _sha256(records_path),
        "outcomes_sha256": _sha256(outcomes_path),
        "terminal_outcomes_sha256": _sha256(terminal_path),
        "legacy_behavior_diagnostics_sha256": _sha256(legacy_path),
        "dual_estimand_observations_sha256": _sha256(observation_path),
        "report_sha256": _sha256(report_path),
        "primary_response_variable": contract.primary_response_variable,
        "valid_training_response_variable": contract.valid_training_response_variable,
        "cross_estimand_rescue_used": False,
        "policy_frozen": report.policy_frozen,
        "pooled_result_used_for_admission": False,
        "posthoc_task_selection_used": False,
        "pro_api_call_count": 0,
        "beneficiary_screening_authorized": False,
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    _write_json(output_dir / "finance_stopping_dual_estimand_manifest.json", manifest)
    return report


def make_stopping_dual_estimand_report(
    contract: FinanceStoppingDualEstimandContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    observations: Sequence[StoppingDualEstimandObservation],
    *,
    discovered_models: Sequence[str],
) -> FinanceStoppingDualEstimandReport:
    if not (
        len(records)
        == len(outcomes)
        == len(terminals)
        == len(observations)
        == contract.requested_rollout_count
    ):
        raise ValueError("Stopping dual-estimand report has an incomplete denominator")
    execution = _rate(item.execution_integrity_passed for item in terminals)
    terminal_resolution = _rate(item.terminal_resolved for item in terminals)
    api = _rate(item.api_transport_resolved for item in terminals)
    bounded = _rate(item.bounded_json_resolution_success for item in terminals)
    replay = _rate(item.observation_replay_success for item in terminals)
    authority = _rate(item.authority_integrity_success for item in terminals)
    pathology = _rate(item.runtime_pathology for item in terminals)
    l0_l2 = sum(
        item.primary_failure_layer
        in {
            FailureLayer.L0_EXTERNAL_INFRASTRUCTURE,
            FailureLayer.L1_TASK_RUNTIME_CONTRACT,
            FailureLayer.L2_TOOL_ENVIRONMENT,
        }
        for item in terminals
    )
    runtime_ready = bool(
        execution >= contract.thresholds.minimum_runtime_execution_integrity
        and terminal_resolution >= contract.thresholds.minimum_terminal_resolution_rate
        and replay >= contract.thresholds.minimum_observation_replay_rate
        and authority >= contract.thresholds.minimum_authority_integrity_rate
        and pathology <= contract.thresholds.maximum_runtime_pathology_rate
        and l0_l2 <= contract.thresholds.maximum_l0_l2_failure_count
    )
    grouped: dict[str, list[StoppingDualEstimandObservation]] = defaultdict(list)
    for item in observations:
        grouped[item.shape_id].append(item)
    shape_results = tuple(
        _make_dual_estimand_shape_result(
            contract,
            shape_id,
            tuple(grouped[shape_id]),
        )
        for shape_id in sorted(set(contract.task_shape_ids.values()))
    )
    by_shape = {item.shape_id: item for item in shape_results}
    recheck_failures = sum(
        not by_shape[shape_id].admitted for shape_id in PROSPECTIVE_RECHECK_SHAPES
    )
    redesign_admissions = sum(
        by_shape[shape_id].admitted for shape_id in STRUCTURAL_REDESIGN_SHAPES
    )
    all_shapes = all(item.admitted for item in shape_results)
    admitted = runtime_ready and all_shapes
    policy = _make_dual_estimand_policy(contract) if admitted else None
    failure_codes = tuple(
        [
            code
            for code, passed in (
                ("execution_integrity", execution == 1.0),
                ("terminal_resolution", terminal_resolution == 1.0),
                ("observation_replay", replay == 1.0),
                ("authority_integrity", authority == 1.0),
                ("runtime_pathology", pathology == 0.0),
                ("l0_l2_failure", l0_l2 == 0),
            )
            if not passed
        ]
        + [f"shape:{item.shape_id}:{code}" for item in shape_results for code in item.failure_codes]
    )
    valid_count = sum(item.full_valid_trajectory_success for item in observations)
    values = {
        "contract_id": contract.contract_id,
        "recorded_rollout_count": len(records),
        "execution_integrity_rate": execution,
        "terminal_resolution_rate": terminal_resolution,
        "api_transport_resolution_rate": api,
        "bounded_json_resolution_rate": bounded,
        "observation_replay_rate": replay,
        "authority_integrity_rate": authority,
        "runtime_pathology_rate": pathology,
        "l0_l2_failure_count": l0_l2,
        "stopping_behavior_success_rate": _rate(
            item.stopping_behavior_success for item in observations
        ),
        "full_valid_trajectory_success_rate": _rate(
            item.full_valid_trajectory_success for item in observations
        ),
        "answer_semantic_success_rate": _rate(
            item.answer_semantic_success for item in observations
        ),
        "terminalization_success_rate": _rate(
            item.terminalization_success for item in observations
        ),
        "valid_training_trajectory_count": valid_count,
        "valid_training_support_ready": all(
            item.valid_training_trajectory_count > 0 for item in shape_results
        ),
        "runtime_measurement_ready": runtime_ready,
        "shape_results": shape_results,
        "prospective_recheck_failure_count": recheck_failures,
        "structural_redesign_admission_count": redesign_admissions,
        "mechanism_observable_shape_count": sum(item.admitted for item in shape_results),
        "all_shapes_admitted": all_shapes,
        "policy": policy,
        "policy_frozen": admitted,
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "discovered_models": tuple(discovered_models),
        "failure_codes": failure_codes,
        "fresh_three_population_preparation_authorized": (
            admitted and all(item.valid_training_trajectory_count > 0 for item in shape_results)
        ),
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "stopping_shape_redesign_only"
                if not all_shapes
                else (
                    "fresh_three_population_dual_estimand_preparation"
                    if all(item.valid_training_trajectory_count > 0 for item in shape_results)
                    else "valid_training_support_repair_only"
                )
            )
        ),
    }
    provisional = FinanceStoppingDualEstimandReport.model_construct(report_id="pending", **values)
    return FinanceStoppingDualEstimandReport(
        report_id=stopping_dual_estimand_report_id(provisional), **values
    )


def _make_dual_estimand_shape_result(
    contract: FinanceStoppingDualEstimandContract,
    shape_id: str,
    observations: Sequence[StoppingDualEstimandObservation],
) -> StoppingDualEstimandResult:
    by_task: dict[str, list[StoppingDualEstimandObservation]] = defaultdict(list)
    for item in observations:
        by_task[item.task_artifact_id].append(item)
    if len(by_task) != TASKS_PER_SHAPE or any(len(items) != REPLICAS for items in by_task.values()):
        raise ValueError(f"Stopping dual-estimand denominator is incomplete: {shape_id}")
    responses: list[StoppingDualEstimandTaskResponse] = []
    for task_id, items in sorted(by_task.items()):
        ordered = sorted(items, key=lambda row: row.replicate)
        stopping = tuple(int(item.stopping_behavior_success) for item in ordered)
        full_valid = tuple(int(item.full_valid_trajectory_success) for item in ordered)
        semantic = tuple(int(item.answer_semantic_success) for item in ordered)
        p_stop = sum(stopping) / len(stopping)
        p_valid = sum(full_valid) / len(full_valid)
        p_semantic = sum(semantic) / len(semantic)
        responses.append(
            StoppingDualEstimandTaskResponse(
                task_artifact_id=task_id,
                stratum_id=contract.task_stratum_ids[task_id],
                stratum_instance_index=contract.task_stratum_instance_indices[task_id],
                stopping_realizations=stopping,
                full_valid_realizations=full_valid,
                semantic_realizations=semantic,
                stopping_probability=p_stop,
                full_valid_probability=p_valid,
                semantic_probability=p_semantic,
                stopping_fisher_information=p_stop * (1.0 - p_stop),
                full_valid_fisher_information=p_valid * (1.0 - p_valid),
            )
        )
    frozen = tuple(responses)
    probabilities = tuple(item.stopping_probability for item in frozen)
    stop_information = tuple(item.stopping_fisher_information for item in frozen)
    valid_information = tuple(item.full_valid_fisher_information for item in frozen)
    total_stop = sum(stop_information)
    shares = tuple(value / total_stop if total_stop else 0.0 for value in stop_information)
    effective = 1.0 / sum(value * value for value in shares) if total_stop else 0.0
    interval = _stopping_information_bootstrap(
        frozen,
        contract.thresholds,
        shape_id=shape_id,
    )
    boundary_count = sum(
        contract.thresholds.boundary_probability_lower
        <= value
        <= contract.thresholds.boundary_probability_upper
        for value in probabilities
    )
    nonzero = sum(value > 0 for value in stop_information)
    role = next(contract.task_shape_roles[task_id] for task_id in by_task)
    design_status = next(contract.task_design_statuses[task_id] for task_id in by_task)
    probability_range = max(probabilities) - min(probabilities)
    common = {
        "complete_task_denominator": len(frozen) == TASKS_PER_SHAPE,
        "between_task_heterogeneity": probability_range
        <= contract.thresholds.maximum_between_task_probability_range,
    }
    if role == "boundary_candidate":
        gates = {
            **common,
            "minimum_boundary_tasks": boundary_count
            >= contract.thresholds.minimum_boundary_tasks_per_candidate_shape,
            "minimum_nonzero_tasks": nonzero
            >= contract.thresholds.minimum_nonzero_tasks_per_candidate_shape,
            "minimum_effective_task_count": effective
            >= contract.thresholds.minimum_effective_task_count,
            "maximum_single_task_information_share": max(shares, default=0.0)
            <= contract.thresholds.maximum_single_task_information_share,
            "positive_bootstrap_information_lcb": interval[0] > 0.0,
        }
    else:
        gates = {
            **common,
            "minimum_control_success": fmean(probabilities)
            >= contract.thresholds.minimum_control_shape_success_rate,
        }
    failures = tuple(sorted(key for key, passed in gates.items() if not passed))
    valid_count = sum(sum(item.full_valid_realizations) for item in frozen)
    return StoppingDualEstimandResult(
        shape_id=shape_id,
        shape_role=role,
        design_status=design_status,
        task_responses=frozen,
        mean_stopping_success_rate=fmean(probabilities),
        mean_full_valid_success_rate=fmean(item.full_valid_probability for item in frozen),
        mean_semantic_success_rate=fmean(item.semantic_probability for item in frozen),
        minimum_stopping_task_probability=min(probabilities),
        maximum_stopping_task_probability=max(probabilities),
        between_task_stopping_probability_range=probability_range,
        stopping_boundary_task_count=boundary_count,
        stopping_nonzero_information_task_count=nonzero,
        total_stopping_fisher_information=total_stop,
        total_full_valid_fisher_information=sum(valid_information),
        stopping_effective_task_count=effective,
        stopping_maximum_single_task_information_share=max(shares, default=0.0),
        stopping_bootstrap_information_interval95=interval,
        stopping_bootstrap_information_lcb=interval[0],
        valid_training_trajectory_count=valid_count,
        valid_training_support_rate=valid_count / (TASKS_PER_SHAPE * REPLICAS),
        gate_results=gates,
        admitted=not failures,
        failure_codes=failures,
    )


def _stopping_information_bootstrap(
    responses: Sequence[StoppingDualEstimandTaskResponse],
    thresholds: StoppingDualEstimandThresholds,
    *,
    shape_id: str,
) -> tuple[float, float]:
    seed = int(
        canonical_hash(
            {"seed": thresholds.bootstrap_seed, "shape_id": shape_id},
            prefix="finance_stopping_dual_estimand_bootstrap_seed:",
        ).rsplit(":", 1)[-1][:16],
        16,
    )
    rng = random.Random(seed)
    totals: list[float] = []
    for _ in range(thresholds.bootstrap_replicates):
        sampled = [rng.choice(responses) for _ in range(len(responses))]
        total = 0.0
        for source in sampled:
            realizations = [
                rng.choice(source.stopping_realizations)
                for _ in range(len(source.stopping_realizations))
            ]
            probability = sum(realizations) / len(realizations)
            total += probability * (1.0 - probability)
        totals.append(total)
    return _interval95(totals)


def _make_dual_estimand_policy(
    contract: FinanceStoppingDualEstimandContract,
) -> FrozenStoppingDualEstimandPolicy:
    values = {
        "source_contract_id": contract.contract_id,
        "shape_task_quotas": {shape_id: TASKS_PER_SHAPE for shape_id in sorted(ALL_SHAPES)},
        "structural_strata": STRUCTURAL_STRATA,
        "thresholds": contract.thresholds,
    }
    provisional = FrozenStoppingDualEstimandPolicy.model_construct(policy_id="pending", **values)
    return FrozenStoppingDualEstimandPolicy(
        policy_id=stopping_dual_estimand_policy_id(provisional), **values
    )


def _verify_population(
    protocol: FinanceStoppingDualEstimandProtocol,
    population: FinanceStoppingDualEstimandPopulation,
    population_path: Path,
) -> None:
    if population.protocol_id != protocol.protocol_id:
        raise ValueError("Stopping shape population belongs to another protocol")
    if _sha256(Path(population.protocol_path)) != population.protocol_sha256:
        raise ValueError("Stopping shape population protocol hash changed")
    if not population.static_audit.ready:
        raise ValueError("Stopping shape population static audit failed")
    if not population_path.is_file():
        raise ValueError("Stopping shape population path is not a file")


def _verify_contract_inputs(contract: FinanceStoppingDualEstimandContract) -> None:
    for reference in (
        contract.source_protocol,
        contract.source_population,
        contract.source_calibration_contract,
    ):
        if _sha256(Path(reference.path)) != reference.sha256:
            raise ValueError(f"frozen Stopping shape input changed: {reference.path}")
    if (
        _sha256(Path(contract.finance_archive_config_path))
        != contract.finance_archive_config_sha256
    ):
        raise ValueError("Stopping shape Finance Archive configuration changed")
    current = _implementation_manifest()
    if current != contract.implementation_manifest:
        raise ValueError("Stopping shape implementation changed after contract freeze")
    if (
        canonical_hash(
            current,
            prefix="finance_stopping_dual_estimand_implementation:",
        )
        != contract.implementation_manifest_hash
    ):
        raise ValueError("Stopping shape implementation manifest hash changed")


def _reference(path: Path, artifact_id: str) -> FrozenArtifactReference:
    return FrozenArtifactReference(path=str(path), sha256=_sha256(path), artifact_id=artifact_id)


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary_runner.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_confirmation.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_dual_estimand_protocol.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_dual_estimand.py",
    )
    return {item: _sha256(root / item) for item in paths}


def _interval95(values: Sequence[float]) -> tuple[float, float]:
    ordered = sorted(values)
    if not ordered:
        return (0.0, 0.0)
    lower = ordered[max(0, int(0.025 * len(ordered)) - 1)]
    upper = ordered[min(len(ordered) - 1, int(math.ceil(0.975 * len(ordered))) - 1)]
    return (lower, upper)


def _render_report(report: FinanceStoppingDualEstimandReport) -> str:
    lines = [
        "# Finance v25.38 Stopping Dual-Estimand Development",
        "",
        "## Decision",
        "",
        f"- Runtime measurement ready: `{str(report.runtime_measurement_ready).lower()}`",
        f"- All Shapes admitted on `Y_stop`: `{str(report.all_shapes_admitted).lower()}`",
        f"- Dual-estimand policy frozen: `{str(report.policy_frozen).lower()}`",
        f"- Next stage: `{report.next_permitted_stage}`",
        "",
        "## Estimand Separation",
        "",
        "| Response | Purpose | Rate | May rescue another response? |",
        "| --- | --- | ---: | --- |",
        f"| `stopping_behavior_success` | capability / Shape information | "
        f"{report.stopping_behavior_success_rate:.4f} | no |",
        f"| `full_valid_trajectory_success` | valid training support | "
        f"{report.full_valid_trajectory_success_rate:.4f} | no |",
        f"| `answer_semantic_success` | diagnostic only | "
        f"{report.answer_semantic_success_rate:.4f} | no |",
        f"| `terminalization_success` | diagnostic only | "
        f"{report.terminalization_success_rate:.4f} | no |",
        "",
        "## Shape Results",
        "",
        "| Shape | Role | Y_stop | Y_valid | Y_sem | I_stop | I_valid | "
        "Boundary | Nonzero | Effective | Max share | LCB | Train-valid | Admit |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.shape_results:
        lines.append(
            f"| `{item.shape_id}` | `{item.shape_role}` | "
            f"{item.mean_stopping_success_rate:.4f} | "
            f"{item.mean_full_valid_success_rate:.4f} | "
            f"{item.mean_semantic_success_rate:.4f} | "
            f"{item.total_stopping_fisher_information:.4f} | "
            f"{item.total_full_valid_fisher_information:.4f} | "
            f"{item.stopping_boundary_task_count} | "
            f"{item.stopping_nonzero_information_task_count} | "
            f"{item.stopping_effective_task_count:.3f} | "
            f"{item.stopping_maximum_single_task_information_share:.3f} | "
            f"{item.stopping_bootstrap_information_lcb:.6f} | "
            f"{item.valid_training_trajectory_count}/64 | "
            f"{'yes' if item.admitted else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Support Layers",
            "",
            f"- Mechanism-observable Shapes: `{report.mechanism_observable_shape_count}/6`",
            f"- Valid training trajectories: "
            f"`{report.valid_training_trajectory_count}/{report.recorded_rollout_count}`",
            f"- Valid training support ready: `{str(report.valid_training_support_ready).lower()}`",
            "- Contribution-authorized support: `false`",
            "- Cross-estimand rescue: `false`",
            "",
            "## Accounting",
            "",
            f"- Rollouts: `{report.recorded_rollout_count}/{report.requested_rollout_count}`",
            f"- API calls: `{report.api_call_count}`",
            f"- Model tokens: `{report.total_model_tokens}`",
            f"- Configured cost estimate: `${report.estimated_cost_usd:.6f}`",
            "- Pro calls: `0`",
            "- Beneficiary / Exact Target / GP-C / Contribution: `not evaluated`",
            "",
        ]
    )
    if report.failure_codes:
        lines.extend(["## Failures", "", *(f"- `{item}`" for item in report.failure_codes), ""])
    return "\n".join(lines)


def _rate(values: Any) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in values),
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run v25.38 Stopping Dual Estimand Development")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--protocol", required=True, type=Path)
    prepare.add_argument("--population", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=32)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        contract = prepare_stopping_dual_estimand_contract(
            protocol_path=args.protocol,
            population_path=args.population,
            output_path=args.output,
            run_id=args.run_id,
        )
        print(contract.model_dump_json(indent=2))
    else:
        report = run_stopping_dual_estimand(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
