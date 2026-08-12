from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.contracts.compiler import QualityContractCompiler
from trusted_synthesis.core.operations.program import ProgramExecutionError, TaskProgramExecutor
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.builder import allowed_tools_for_program, public_program_skeleton
from trusted_synthesis.core.task.materialization import resolved_retrieval_scope
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack, TaskRequirement
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.specification import (
    TrajectoryVerificationContext,
    make_omega_component_manifest,
    make_oracle_execution_specification,
    make_trajectory_verification_context,
)
from trusted_synthesis.domains.finance.agent_tools import (
    make_finance_archive_agent_tool_manifest,
)
from trusted_synthesis.domains.finance.quality_clauses import FinanceQualityClauseProvider
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
    FAMILY_PRIMARY_CAPABILITY,
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
    _minimum_mismatch_fields,
    capability_sensitive_task_artifact_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
    FinanceProFlashPilotContract,
    _paired_sampling_contract_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_satisfiability import (
    ScriptedSequenceCompilation,
    compile_scripted_tool_sequence,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

CAPABILITY_BOUNDARY_CONTRACT_VERSION = "finance_capability_boundary_contract.v9"
CAPABILITY_NECESSITY_AUDIT_VERSION = "finance_capability_necessity_audit.v2"
RUNTIME_VISIBLE_DEMAND_VERSION = "model_visible_capability_demand.v2"
RUNTIME_BINDING_VERSION = "finance_capability_runtime_binding.v7"

QUALIFICATION_TASKS_PER_FAMILY = 1
LOCALIZATION_TASKS_PER_FAMILY_TIER = 1
CALIBRATION_TASKS_PER_FAMILY = 4
QUALIFICATION_REPLICAS = 3
LOCALIZATION_REPLICAS = 5
CALIBRATION_REPLICAS = 10
MAXIMUM_REQUIRED_TOOL_CALLS = 20
MAXIMUM_FAILED_TOOL_CALLS = 3
MAXIMUM_TOOL_CALLS = MAXIMUM_REQUIRED_TOOL_CALLS + MAXIMUM_FAILED_TOOL_CALLS
MAXIMUM_OBSERVATION_BYTES = 1_000_000
MODEL_TOKEN_BUDGET = 90_000


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilityRuntimeArm(str, Enum):
    DIRECT_FIXED_RETRIEVAL = "direct_fixed_retrieval"
    SCRIPTED_TOOL = "scripted_tool"
    AUTONOMOUS_AGENT = "autonomous_agent"


RUNTIME_AXIS_RESPONSIBILITY: dict[CapabilityRuntimeArm, dict[str, float]] = {
    CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL: {
        "retrieval": 0.0,
        "planning": 0.0,
        "calculation": 1.0,
        "reconciliation": 1.0,
        "verification": 1.0,
        "recovery": 0.0,
        "stopping": 0.0,
    },
    CapabilityRuntimeArm.SCRIPTED_TOOL: {
        "retrieval": 1.0,
        "planning": 0.0,
        "calculation": 1.0,
        "reconciliation": 1.0,
        "verification": 1.0,
        "recovery": 1.0,
        "stopping": 0.0,
    },
    CapabilityRuntimeArm.AUTONOMOUS_AGENT: {axis: 1.0 for axis in CAPABILITY_AXES},
}


class RuntimeAuthorityContract(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    model_authorities: tuple[str, ...]
    host_authorities: tuple[str, ...]
    axis_responsibility: dict[str, float]
    authority_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_authority(self) -> RuntimeAuthorityContract:
        if self.axis_responsibility != RUNTIME_AXIS_RESPONSIBILITY[self.runtime_arm]:
            raise ValueError("runtime authority differs from the frozen axis responsibility")
        if set(self.model_authorities) & set(self.host_authorities):
            raise ValueError("model and Host authorities overlap")
        if self.authority_hash != runtime_authority_hash(self):
            raise ValueError("runtime authority identity is invalid")
        return self


class ModelVisibleCapabilityDemand(FrozenModel):
    task_artifact_id: str = Field(min_length=1)
    runtime_arm: CapabilityRuntimeArm
    values: dict[str, float]
    model_visible_axes: tuple[str, ...]
    host_controlled_axes: tuple[str, ...]
    demand_hash: str = Field(min_length=1)
    schema_version: str = RUNTIME_VISIBLE_DEMAND_VERSION

    @model_validator(mode="after")
    def validate_demand(self) -> ModelVisibleCapabilityDemand:
        if self.schema_version != RUNTIME_VISIBLE_DEMAND_VERSION:
            raise ValueError("model-visible demand version is unsupported")
        if set(self.values) != set(CAPABILITY_AXES):
            raise ValueError("model-visible demand does not cover the frozen axes")
        expected_visible = tuple(axis for axis in CAPABILITY_AXES if self.values[axis] > 0)
        expected_host = tuple(axis for axis in CAPABILITY_AXES if self.values[axis] == 0)
        if (
            self.model_visible_axes != expected_visible
            or self.host_controlled_axes != expected_host
        ):
            raise ValueError("model-visible and Host-controlled axes are inconsistent")
        if any(value < 0 or not math.isfinite(value) for value in self.values.values()):
            raise ValueError("model-visible demand values must be finite and non-negative")
        if self.demand_hash != model_visible_demand_hash(self):
            raise ValueError("model-visible demand identity is invalid")
        return self


class CapabilityNecessityProbe(FrozenModel):
    task_artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    capability_axis: str = Field(min_length=1)
    intervention_kind: str = Field(min_length=1)
    baseline_contract_passed: bool
    ablated_contract_failed: bool
    affected_contracts: tuple[str, ...] = Field(min_length=1)
    details: dict[str, Any]
    passed: bool
    probe_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_probe(self) -> CapabilityNecessityProbe:
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("necessity probe uses an unknown family")
        if self.capability_axis != FAMILY_PRIMARY_CAPABILITY[self.family]:
            raise ValueError("necessity probe targets the wrong primary capability")
        expected = self.baseline_contract_passed and self.ablated_contract_failed
        if self.passed != expected:
            raise ValueError("necessity probe decision is inconsistent")
        if self.probe_hash != capability_necessity_probe_hash(self):
            raise ValueError("necessity probe identity is invalid")
        return self


class CapabilityNecessityAudit(FrozenModel):
    population_id: str = Field(min_length=1)
    scope: Literal["frontier_contract_necessity_not_model_causal_effect"] = (
        "frontier_contract_necessity_not_model_causal_effect"
    )
    probes: tuple[CapabilityNecessityProbe, ...] = Field(min_length=1)
    family_passes: dict[str, bool]
    passed_probe_count: int = Field(ge=0)
    contract_necessity_ready: bool
    audit_hash: str = Field(min_length=1)
    schema_version: str = CAPABILITY_NECESSITY_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CapabilityNecessityAudit:
        if self.schema_version != CAPABILITY_NECESSITY_AUDIT_VERSION:
            raise ValueError("capability necessity audit version is unsupported")
        if set(self.family_passes) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("necessity audit does not cover every capability family")
        expected_count = sum(item.passed for item in self.probes)
        if self.passed_probe_count != expected_count:
            raise ValueError("necessity audit pass count is inconsistent")
        expected_ready = all(self.family_passes.values()) and expected_count == len(self.probes)
        if self.contract_necessity_ready != expected_ready:
            raise ValueError("necessity audit authorization is inconsistent")
        if self.audit_hash != capability_necessity_audit_hash(self):
            raise ValueError("necessity audit identity is invalid")
        return self


class RuntimeTaskBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    tier: DifficultyTier
    general_difficulty: float = Field(ge=0)
    runtime_arm: CapabilityRuntimeArm
    omega_context_id: str = Field(min_length=1)
    omega_context_hash: str = Field(min_length=1)
    component_manifest_id: str = Field(min_length=1)
    quality_contract_id: str = Field(min_length=1)
    quality_contract_hash: str = Field(min_length=1)
    reference_trajectory_id: str = Field(min_length=1)
    reference_trajectory_hash: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    environment_manifest_hash: str = Field(min_length=1)
    public_allowed_tools: tuple[str, ...] = Field(min_length=1)
    visible_demand: ModelVisibleCapabilityDemand
    scripted_compilation: ScriptedSequenceCompilation | None = None
    schema_version: str = RUNTIME_BINDING_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> RuntimeTaskBinding:
        if self.schema_version != RUNTIME_BINDING_VERSION:
            raise ValueError("runtime task binding version is unsupported")
        if self.visible_demand.task_artifact_id != self.task_artifact_id:
            raise ValueError("runtime binding and visible demand use different tasks")
        if self.visible_demand.runtime_arm != self.runtime_arm:
            raise ValueError("runtime binding and visible demand use different arms")
        if self.public_allowed_tools != tuple(dict.fromkeys(self.public_allowed_tools)):
            raise ValueError("runtime binding allowed tools are not canonical")
        if (
            self.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
            and "evidence.search" not in self.public_allowed_tools
        ):
            raise ValueError("Direct Runtime lacks its evidence-search capability")
        if self.runtime_arm == CapabilityRuntimeArm.SCRIPTED_TOOL:
            if self.scripted_compilation is None:
                raise ValueError("Scripted Tool binding lacks a frozen sequence")
            if self.scripted_compilation.task_artifact_id != self.task_artifact_id:
                raise ValueError("Scripted compilation belongs to another task")
        elif self.scripted_compilation is not None:
            raise ValueError("only Scripted Tool bindings may contain a sequence")
        if (
            self.scripted_compilation is not None
            and self.scripted_compilation.minimum_tool_calls > MAXIMUM_REQUIRED_TOOL_CALLS
        ):
            raise ValueError("Scripted Tool sequence exceeds the required-call budget")
        if self.binding_id != runtime_task_binding_id(self):
            raise ValueError("runtime task binding identity is invalid")
        return self


class TechnicalQualificationThresholds(FrozenModel):
    minimum_completion_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_raw_json_contract_rate: float = Field(default=0.85, ge=0, le=1)
    minimum_bounded_json_resolution_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_tool_bounded_resolution_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_terminal_result_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_observation_replay_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_authority_integrity_rate: float = Field(default=1.0, ge=0, le=1)
    maximum_host_verification_repair_rate: float = Field(default=0.15, ge=0, le=1)
    maximum_budget_exhaustion_count: int = Field(default=0, ge=0)
    semantic_correctness_is_nonblocking: Literal[True] = True


class RuntimeInformationThreshold(FrozenModel):
    minimum_rank: int = Field(ge=1)
    minimum_effective_rank: float = Field(ge=1)
    maximum_condition_number: float = Field(ge=1)
    minimum_boundary_task_fraction: float = Field(ge=0, le=1)
    maximum_general_factor_fraction: float = Field(ge=0, le=1)
    minimum_informative_axis_count: int = Field(ge=1)


class EmpiricalInformationThresholds(FrozenModel):
    by_runtime: dict[CapabilityRuntimeArm, RuntimeInformationThreshold]
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    minimum_marginal_axis_information: float = Field(default=1e-4, gt=0)
    minimum_separating_family_count: int = Field(default=2, ge=1)
    minimum_family_model_gap: float = Field(default=0.05, ge=0, le=1)
    bootstrap_replicates: int = Field(default=400, ge=100)

    @model_validator(mode="after")
    def validate_thresholds(self) -> EmpiricalInformationThresholds:
        if set(self.by_runtime) != set(CapabilityRuntimeArm):
            raise ValueError("empirical thresholds do not cover every Runtime")
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("empirical boundary probability interval is empty")
        return self


class TierLocalizationThresholds(FrozenModel):
    minimum_technical_resolution_rate: float = Field(default=0.80, ge=0, le=1)
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    minimum_runtime_boundary_families: dict[CapabilityRuntimeArm, int] = Field(
        default_factory=lambda: {
            CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL: 2,
            CapabilityRuntimeArm.SCRIPTED_TOOL: 3,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT: 4,
        }
    )

    @model_validator(mode="after")
    def validate_thresholds(self) -> TierLocalizationThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("tier-localization boundary interval is empty")
        if set(self.minimum_runtime_boundary_families) != set(CapabilityRuntimeArm):
            raise ValueError("tier-localization thresholds do not cover every Runtime")
        if any(
            value < 1 or value > len(CAPABILITY_SENSITIVE_FAMILIES)
            for value in self.minimum_runtime_boundary_families.values()
        ):
            raise ValueError("tier-localization family threshold is invalid")
        return self


def default_information_thresholds() -> EmpiricalInformationThresholds:
    return EmpiricalInformationThresholds(
        by_runtime={
            CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL: RuntimeInformationThreshold(
                minimum_rank=2,
                minimum_effective_rank=1.5,
                maximum_condition_number=100.0,
                minimum_boundary_task_fraction=0.25,
                maximum_general_factor_fraction=0.85,
                minimum_informative_axis_count=2,
            ),
            CapabilityRuntimeArm.SCRIPTED_TOOL: RuntimeInformationThreshold(
                minimum_rank=3,
                minimum_effective_rank=2.0,
                maximum_condition_number=100.0,
                minimum_boundary_task_fraction=0.25,
                maximum_general_factor_fraction=0.85,
                minimum_informative_axis_count=3,
            ),
            CapabilityRuntimeArm.AUTONOMOUS_AGENT: RuntimeInformationThreshold(
                minimum_rank=4,
                minimum_effective_rank=3.0,
                maximum_condition_number=100.0,
                minimum_boundary_task_fraction=0.25,
                maximum_general_factor_fraction=0.85,
                minimum_informative_axis_count=4,
            ),
        }
    )


class HierarchicalAnalysisPlan(FrozenModel):
    diagnostic_binary_formula: str = (
        "success ~ model * runtime + family + model:family + general_difficulty + "
        "residual_axis_demands + (1|task_id)"
    )
    primary_estimator: Literal["task_cluster_paired_nested_bootstrap"] = (
        "task_cluster_paired_nested_bootstrap"
    )
    paired_unit: Literal["task_id"] = "task_id"
    cluster_unit: Literal["task_id"] = "task_id"
    realization_resampling_required: Literal[True] = True
    general_difficulty_residualization_required: Literal[True] = True
    task_level_pairing_required: Literal[True] = True
    family_separation_uses_ci_lower_bound: Literal[True] = True
    axis_information_uses_ci_lower_bound: Literal[True] = True
    raw_information_uses_uncentered_demand: Literal[True] = True
    residual_information_removes_intercept_and_general_difficulty: Literal[True] = True
    simple_unpaired_percentage_test_forbidden: Literal[True] = True


class FinanceCapabilityBoundaryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    population_path: str = Field(min_length=1)
    population_sha256: str = Field(min_length=64, max_length=64)
    population_id: str = Field(min_length=1)
    model_source_contract_path: str = Field(min_length=1)
    model_source_contract_sha256: str = Field(min_length=64, max_length=64)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=2, max_length=2)
    paired_sampling_contract_hash: str = Field(min_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    authority_contracts: tuple[RuntimeAuthorityContract, ...] = Field(min_length=3, max_length=3)
    necessity_audit: CapabilityNecessityAudit
    qualification_bindings: tuple[RuntimeTaskBinding, ...] = Field(min_length=21, max_length=21)
    localization_bindings: tuple[RuntimeTaskBinding, ...] = Field(min_length=63, max_length=63)
    calibration_bindings: tuple[RuntimeTaskBinding, ...] = Field(min_length=84, max_length=84)
    qualification_replicas: int = Field(default=QUALIFICATION_REPLICAS, ge=3, le=3)
    localization_replicas: int = Field(default=LOCALIZATION_REPLICAS, ge=5, le=5)
    calibration_replicas: int = Field(default=CALIBRATION_REPLICAS, ge=10, le=10)
    requested_qualification_rollouts: int = Field(ge=1)
    requested_localization_rollouts: int = Field(ge=1)
    requested_calibration_rollouts: int = Field(ge=1)
    maximum_tool_calls: int = Field(default=MAXIMUM_TOOL_CALLS, ge=1)
    maximum_failed_tool_calls: int = Field(default=MAXIMUM_FAILED_TOOL_CALLS, ge=0)
    maximum_total_observation_bytes: int = Field(default=MAXIMUM_OBSERVATION_BYTES, ge=1)
    maximum_model_tokens_per_rollout: int = Field(default=MODEL_TOKEN_BUDGET, ge=1)
    model_contract_repair_attempts: int = Field(default=2, ge=2, le=2)
    technical_thresholds: TechnicalQualificationThresholds
    localization_thresholds: TierLocalizationThresholds
    information_thresholds: EmpiricalInformationThresholds
    analysis_plan: HierarchicalAnalysisPlan
    random_seed: int
    sampling_salt: str = Field(min_length=1)
    next_permitted_stage: Literal["v25_native_runtime_qualification"] = (
        "v25_native_runtime_qualification"
    )
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = CAPABILITY_BOUNDARY_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceCapabilityBoundaryContract:
        if self.schema_version != CAPABILITY_BOUNDARY_CONTRACT_VERSION:
            raise ValueError("capability boundary contract version is unsupported")
        if self.maximum_failed_tool_calls != MAXIMUM_FAILED_TOOL_CALLS:
            raise ValueError("capability boundary failed-tool budget changed")
        if self.maximum_tool_calls != (
            MAXIMUM_REQUIRED_TOOL_CALLS + self.maximum_failed_tool_calls
        ):
            raise ValueError("capability boundary total tool budget lacks recovery capacity")
        if {item.arm for item in self.model_contracts} != set(ExplorerArm):
            raise ValueError("capability boundary contract requires exactly Pro and Flash")
        if self.paired_sampling_contract_hash != _paired_sampling_contract_hash(
            self.model_contracts
        ):
            raise ValueError("Pro and Flash sampling contracts differ")
        if {item.runtime_arm for item in self.authority_contracts} != set(CapabilityRuntimeArm):
            raise ValueError("capability boundary contract lacks a Runtime authority")
        if not self.necessity_audit.contract_necessity_ready:
            raise ValueError("capability boundary contract requires necessity authorization")
        _validate_binding_partition(
            self.qualification_bindings,
            expected_tasks_per_family=QUALIFICATION_TASKS_PER_FAMILY,
        )
        _validate_localization_partition(self.localization_bindings)
        _validate_binding_partition(
            self.calibration_bindings,
            expected_tasks_per_family=CALIBRATION_TASKS_PER_FAMILY,
        )
        qualification_tasks = {item.task_artifact_id for item in self.qualification_bindings}
        localization_tasks = {item.task_artifact_id for item in self.localization_bindings}
        calibration_tasks = {item.task_artifact_id for item in self.calibration_bindings}
        if not qualification_tasks <= localization_tasks:
            raise ValueError("Qualification Frontier tasks must anchor Tier Localization")
        if localization_tasks & calibration_tasks:
            raise ValueError("Tier Localization and Calibration tasks overlap")
        if qualification_tasks & calibration_tasks:
            raise ValueError("Qualification and Calibration tasks overlap")
        expected_qualification = (
            len(qualification_tasks)
            * len(self.model_contracts)
            * len(CapabilityRuntimeArm)
            * self.qualification_replicas
        )
        expected_calibration = (
            len(calibration_tasks)
            * len(self.model_contracts)
            * len(CapabilityRuntimeArm)
            * self.calibration_replicas
        )
        expected_localization = (
            len(localization_tasks)
            * len(self.model_contracts)
            * len(CapabilityRuntimeArm)
            * self.localization_replicas
        )
        if self.requested_qualification_rollouts != expected_qualification:
            raise ValueError("Qualification rollout count is inconsistent")
        if self.requested_localization_rollouts != expected_localization:
            raise ValueError("Tier Localization rollout count is inconsistent")
        if self.requested_calibration_rollouts != expected_calibration:
            raise ValueError("Calibration rollout count is inconsistent")
        if self.contract_id != capability_boundary_contract_id(self):
            raise ValueError("capability boundary contract identity is invalid")
        return self


def runtime_authority_contracts() -> tuple[RuntimeAuthorityContract, ...]:
    values = {
        CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL: (
            ("calculation", "reconciliation", "verification", "answer_generation"),
            ("evidence_retrieval", "tool_selection", "planning", "recovery", "stopping"),
        ),
        CapabilityRuntimeArm.SCRIPTED_TOOL: (
            (
                "query_construction",
                "tool_arguments",
                "calculation",
                "reconciliation",
                "verification",
                "failure_recovery",
                "answer_generation",
            ),
            ("tool_selection", "planning", "stopping", "tool_execution"),
        ),
        CapabilityRuntimeArm.AUTONOMOUS_AGENT: (
            (
                "tool_selection",
                "query_construction",
                "planning",
                "calculation",
                "reconciliation",
                "verification",
                "failure_recovery",
                "continue_or_stop",
                "answer_generation",
            ),
            ("tool_execution", "validity_verification", "budget_enforcement"),
        ),
    }
    output = []
    for arm in CapabilityRuntimeArm:
        model, host = values[arm]
        payload = {
            "runtime_arm": arm,
            "model_authorities": model,
            "host_authorities": host,
            "axis_responsibility": RUNTIME_AXIS_RESPONSIBILITY[arm],
        }
        provisional = RuntimeAuthorityContract.model_construct(authority_hash="pending", **payload)
        output.append(
            RuntimeAuthorityContract(authority_hash=runtime_authority_hash(provisional), **payload)
        )
    return tuple(output)


def make_model_visible_demand(
    task: CapabilitySensitiveTaskArtifact,
    runtime_arm: CapabilityRuntimeArm,
) -> ModelVisibleCapabilityDemand:
    mask = RUNTIME_AXIS_RESPONSIBILITY[runtime_arm]
    values = {
        axis: round(task.capability_demand.values[axis] * mask[axis], 9) for axis in CAPABILITY_AXES
    }
    payload = {
        "task_artifact_id": task.artifact_id,
        "runtime_arm": runtime_arm,
        "values": values,
        "model_visible_axes": tuple(axis for axis in CAPABILITY_AXES if values[axis] > 0),
        "host_controlled_axes": tuple(axis for axis in CAPABILITY_AXES if values[axis] == 0),
    }
    provisional = ModelVisibleCapabilityDemand.model_construct(demand_hash="pending", **payload)
    return ModelVisibleCapabilityDemand(
        demand_hash=model_visible_demand_hash(provisional), **payload
    )


def make_capability_necessity_audit(
    population: CapabilitySensitiveFrontierPopulation,
) -> CapabilityNecessityAudit:
    tasks = tuple(item for item in population.tasks if item.tier == DifficultyTier.FRONTIER)
    probes = tuple(_necessity_probe(item) for item in tasks)
    family_passes = {
        family: all(item.passed for item in probes if item.family == family)
        and any(item.family == family for item in probes)
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    payload = {
        "population_id": population.population_id,
        "probes": probes,
        "family_passes": family_passes,
        "passed_probe_count": sum(item.passed for item in probes),
        "contract_necessity_ready": all(family_passes.values())
        and all(item.passed for item in probes),
    }
    provisional = CapabilityNecessityAudit.model_construct(audit_hash="pending", **payload)
    return CapabilityNecessityAudit(
        audit_hash=capability_necessity_audit_hash(provisional), **payload
    )


def prepare_capability_boundary_contract(
    *,
    population_path: Path,
    model_source_contract_path: Path,
    finance_archive_config_path: Path,
    output_path: Path,
    run_id: str,
    random_seed: int,
    sampling_salt: str,
) -> FinanceCapabilityBoundaryContract:
    if output_path.exists():
        raise ValueError("capability boundary contract is immutable and already exists")
    population_path = population_path.resolve()
    model_source_contract_path = model_source_contract_path.resolve()
    finance_archive_config_path = finance_archive_config_path.resolve()
    population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    if not population.audit.structural_frontier_ready:
        raise ValueError("v25 structural Frontier is not authorized")
    necessity = make_capability_necessity_audit(population)
    if not necessity.contract_necessity_ready:
        raise ValueError("v25 capability contract necessity is not authorized")
    model_source = FinanceProFlashPilotContract.model_validate_json(
        model_source_contract_path.read_text(encoding="utf-8")
    )
    protocol = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        observation_view="compact",
        contract_repair_token_reserve=8_000,
        final_answer_token_reserve=12_000,
        host_repair_missing_verification=True,
    )
    qualification_tasks, localization_tasks, calibration_tasks = _select_boundary_tasks(
        population, sampling_salt=sampling_salt
    )
    qualification_bindings = tuple(
        _make_runtime_binding(task, arm, protocol)
        for task in qualification_tasks
        for arm in CapabilityRuntimeArm
    )
    localization_bindings = tuple(
        _make_runtime_binding(task, arm, protocol)
        for task in localization_tasks
        for arm in CapabilityRuntimeArm
    )
    calibration_bindings = tuple(
        _make_runtime_binding(task, arm, protocol)
        for task in calibration_tasks
        for arm in CapabilityRuntimeArm
    )
    values = {
        "run_id": run_id,
        "population_path": str(population_path),
        "population_sha256": _sha256(population_path),
        "population_id": population.population_id,
        "model_source_contract_path": str(model_source_contract_path),
        "model_source_contract_sha256": _sha256(model_source_contract_path),
        "finance_archive_config_path": str(finance_archive_config_path),
        "finance_archive_config_sha256": _sha256(finance_archive_config_path),
        "model_contracts": model_source.model_contracts,
        "paired_sampling_contract_hash": _paired_sampling_contract_hash(
            model_source.model_contracts
        ),
        "protocol_profile": protocol,
        "authority_contracts": runtime_authority_contracts(),
        "necessity_audit": necessity,
        "qualification_bindings": qualification_bindings,
        "localization_bindings": localization_bindings,
        "calibration_bindings": calibration_bindings,
        "qualification_replicas": QUALIFICATION_REPLICAS,
        "localization_replicas": LOCALIZATION_REPLICAS,
        "calibration_replicas": CALIBRATION_REPLICAS,
        "requested_qualification_rollouts": 126,
        "requested_localization_rollouts": 630,
        "requested_calibration_rollouts": 1_680,
        "maximum_tool_calls": MAXIMUM_TOOL_CALLS,
        "maximum_failed_tool_calls": MAXIMUM_FAILED_TOOL_CALLS,
        "maximum_total_observation_bytes": MAXIMUM_OBSERVATION_BYTES,
        "maximum_model_tokens_per_rollout": MODEL_TOKEN_BUDGET,
        "model_contract_repair_attempts": 2,
        "technical_thresholds": TechnicalQualificationThresholds(),
        "localization_thresholds": TierLocalizationThresholds(),
        "information_thresholds": default_information_thresholds(),
        "analysis_plan": HierarchicalAnalysisPlan(),
        "random_seed": random_seed,
        "sampling_salt": sampling_salt,
        "next_permitted_stage": "v25_native_runtime_qualification",
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = FinanceCapabilityBoundaryContract.model_construct(contract_id="pending", **values)
    contract = FinanceCapabilityBoundaryContract(
        contract_id=capability_boundary_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def make_v25_native_runtime_context(
    task: CapabilitySensitiveTaskArtifact,
    runtime_arm: CapabilityRuntimeArm,
    protocol: IterativeAgentProtocolProfile,
) -> tuple[TrajectoryVerificationContext, Any, Any]:
    registry = default_registry()
    corpus = task.public_corpus
    snapshot_id = str(corpus.build_id or f"corpus:{corpus.corpus_hash}")
    manifest = make_finance_archive_agent_tool_manifest(
        environment_id=f"finance_v25:{runtime_arm.value}:{task.artifact_id}",
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        archive_snapshot_id=snapshot_id,
        archive_snapshot_hash=corpus.corpus_hash,
        maximum_tool_calls=MAXIMUM_TOOL_CALLS,
        maximum_failed_tool_calls=MAXIMUM_FAILED_TOOL_CALLS,
        maximum_total_observation_bytes=MAXIMUM_OBSERVATION_BYTES,
    )
    direct_fixed = runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
    public_allowed_tools = runtime_public_allowed_tools(
        task,
        runtime_arm,
        manifest,
        registry=registry,
    )
    retrieval_track = RetrievalTrack.RESOLVED if direct_fixed else task.task.public.retrieval_track
    planning_track = PlanningTrack.PLAN_GIVEN if direct_fixed else task.task.public.planning_track
    agent_contract_guidance = _capability_agent_contract_guidance(
        task.task.oracle.task_program,
        existing=task.task.public.metadata.get("agent_contract_guidance"),
    )
    program_skeleton = (
        public_program_skeleton(
            task.task.oracle.task_program, default_registry(), task.evidence_bundle.evidence
        )
        if direct_fixed
        else task.task.public.program_skeleton
    )
    public = task.task.public.model_copy(
        update={
            "allowed_tools": public_allowed_tools,
            "retrieval_track": retrieval_track,
            "planning_track": planning_track,
            "program_skeleton": program_skeleton,
            "retrieval_scope": (
                resolved_retrieval_scope(task.evidence_bundle.evidence)
                if direct_fixed
                else task.task.public.retrieval_scope
            ),
            "metadata": {
                **task.task.public.metadata,
                "agent_contract_guidance": agent_contract_guidance,
                "v25_native_runtime": {
                    "version": CAPABILITY_BOUNDARY_CONTRACT_VERSION,
                    "runtime_arm": runtime_arm.value,
                    "protocol_profile_hash": protocol.profile_hash,
                    "capability_labels_hidden": True,
                    "oracle_identities_hidden": True,
                    "fixed_gold_retrieval": direct_fixed,
                    "fixed_public_program": direct_fixed,
                },
            },
        }
    )
    runtime_task = task.task.model_copy(update={"public": public})
    quality = QualityContractCompiler(
        registry, domain_provider=FinanceQualityClauseProvider()
    ).compile(runtime_task, task.evidence_bundle, task.proof_graph)
    reference = ReferenceWorkflowCompiler(registry).compile(runtime_task, task.evidence_bundle)
    oracle = make_oracle_execution_specification(
        runtime_task,
        task.evidence_bundle,
        corpus,
        task.proof_graph,
        quality,
        reference_examples=(reference,),
    )
    context = make_trajectory_verification_context(
        runtime_task,
        task.evidence_bundle,
        corpus,
        task.proof_graph,
        quality,
        oracle,
    )
    return context, manifest, reference


def _capability_agent_contract_guidance(
    program: TaskProgram,
    *,
    existing: Any,
) -> dict[str, Any]:
    existing_guidance = dict(existing) if isinstance(existing, dict) else {}
    operation_selectors = tuple(
        sorted(
            {
                item.selector
                for node in program.nodes
                for item in node.input_refs
                if item.kind == InputRefKind.OPERATION and item.selector is not None
            }
        )
    )
    ratio_pairs = tuple(
        sorted(
            {
                str(node.parameters["registered_pair"])
                for node in program.nodes
                if node.operator_id == "ratio"
                and isinstance(node.parameters.get("registered_pair"), str)
            }
        )
    )
    return {
        **existing_guidance,
        "calculator_operation_reference_contract": {
            "copy_operation_ref_from": (
                "successful calculator observation result.result.operation_ref"
            ),
            "selector_base": "prior calculator observation result.result.output",
            "allowed_selectors": operation_selectors,
            "scalar_selector": "value",
            "forbidden_selectors": (
                "output",
                "output.value",
                "result",
                "result.output",
                "result.output.value",
            ),
            "literal_operation_names_are_forbidden": True,
        },
        "registered_ratio_pairs": ratio_pairs,
    }


def runtime_public_allowed_tools(
    task: CapabilitySensitiveTaskArtifact,
    runtime_arm: CapabilityRuntimeArm,
    manifest: Any,
    *,
    registry: OperationRegistry | None = None,
) -> tuple[str, ...]:
    if runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
        return allowed_tools_for_program(
            task.task.oracle.task_program,
            registry or default_registry(),
        )
    return tuple(item.tool_id for item in manifest.tools)


def _make_runtime_binding(
    task: CapabilitySensitiveTaskArtifact,
    runtime_arm: CapabilityRuntimeArm,
    protocol: IterativeAgentProtocolProfile,
) -> RuntimeTaskBinding:
    context, manifest, reference = make_v25_native_runtime_context(task, runtime_arm, protocol)
    component = make_omega_component_manifest(context)
    values = {
        "task_artifact_id": task.artifact_id,
        "task_id": task.task.task_id,
        "family": task.family,
        "tier": task.tier,
        "general_difficulty": task.structure.semantic_score,
        "runtime_arm": runtime_arm,
        "omega_context_id": context.context_id,
        "omega_context_hash": canonical_hash(context, prefix="v25_runtime_omega:"),
        "component_manifest_id": component.manifest_id,
        "quality_contract_id": context.quality_contract.contract_id,
        "quality_contract_hash": context.quality_contract.contract_hash,
        "reference_trajectory_id": reference.trajectory_id,
        "reference_trajectory_hash": reference.trajectory_hash,
        "environment_manifest_id": manifest.manifest_id,
        "environment_manifest_hash": canonical_hash(manifest, prefix="v25_tool_environment:"),
        "public_allowed_tools": context.task.public.allowed_tools,
        "visible_demand": make_model_visible_demand(task, runtime_arm),
        "scripted_compilation": (
            compile_scripted_tool_sequence(
                task,
                maximum_required_tool_calls=MAXIMUM_REQUIRED_TOOL_CALLS,
            )
            if runtime_arm == CapabilityRuntimeArm.SCRIPTED_TOOL
            else None
        ),
    }
    provisional = RuntimeTaskBinding.model_construct(binding_id="pending", **values)
    return RuntimeTaskBinding(binding_id=runtime_task_binding_id(provisional), **values)


def _select_boundary_tasks(
    population: CapabilitySensitiveFrontierPopulation,
    *,
    sampling_salt: str,
) -> tuple[
    tuple[CapabilitySensitiveTaskArtifact, ...],
    tuple[CapabilitySensitiveTaskArtifact, ...],
    tuple[CapabilitySensitiveTaskArtifact, ...],
]:
    qualification = []
    localization = []
    calibration = []
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        frontier_candidates = [
            item
            for item in population.tasks
            if item.family == family and item.tier == DifficultyTier.FRONTIER
        ]
        ordered_frontier = sorted(
            frontier_candidates,
            key=lambda item: canonical_hash(
                {"salt": sampling_salt, "artifact_id": item.artifact_id},
                prefix="v25_boundary_task_selection:",
            ),
        )
        if len(ordered_frontier) != (
            QUALIFICATION_TASKS_PER_FAMILY + CALIBRATION_TASKS_PER_FAMILY
        ):
            raise ValueError("v25 Frontier does not contain exactly five tasks per family")
        frontier_anchor = ordered_frontier[0]
        qualification.append(frontier_anchor)
        localization.append(frontier_anchor)
        calibration.extend(ordered_frontier[QUALIFICATION_TASKS_PER_FAMILY:])
        for tier in (DifficultyTier.EASY_CONTROL, DifficultyTier.HARD_CONTROL):
            tier_candidates = sorted(
                (
                    item
                    for item in population.tasks
                    if item.family == family and item.tier == tier
                ),
                key=lambda item: canonical_hash(
                    {"salt": sampling_salt, "artifact_id": item.artifact_id},
                    prefix="v25_localization_task_selection:",
                ),
            )
            if len(tier_candidates) < LOCALIZATION_TASKS_PER_FAMILY_TIER:
                raise ValueError(f"v25 {tier.value} lacks a localization task for {family}")
            localization.extend(tier_candidates[:LOCALIZATION_TASKS_PER_FAMILY_TIER])
    return tuple(qualification), tuple(localization), tuple(calibration)


def _necessity_probe(task: CapabilitySensitiveTaskArtifact) -> CapabilityNecessityProbe:
    axis = FAMILY_PRIMARY_CAPABILITY[task.family]
    baseline = task.verification.passed
    affected: tuple[str, ...]
    details: dict[str, Any]
    if axis == "retrieval":
        ablated = _missing_required_evidence_fails(task)
        intervention = "withhold_program_required_evidence"
        affected = ("answer_replay", "evidence_coverage")
        details = {"gold_evidence_count": len(task.evidence_bundle.evidence)}
    elif axis == "planning":
        ablated = _remove_required_program_branch_fails(task)
        intervention = "remove_required_program_branch"
        affected = ("program_dag", "answer_replay")
        details = {"operation_branch_count": task.structure.operation_branch_count}
    elif axis == "calculation":
        ablated = _remove_program_output_fails(task)
        intervention = "remove_final_calculation_node"
        affected = ("operation_contract", "answer_schema")
        details = {"operation_count": task.structure.operation_count}
    elif axis == "reconciliation":
        mismatch = _registered_reconciliation_mismatch(task)
        reconciliation_axis = (
            _reconciliation_axis_for_mismatch(mismatch) if mismatch is not None else None
        )
        ablated = bool(
            reconciliation_axis
            and _artifact_contract_ablation_fails(
                task,
                field="reconciliation_axes",
                value=tuple(
                    item for item in task.reconciliation_axes if item != reconciliation_axis
                ),
            )
        )
        intervention = "remove_required_reconciliation_constraint"
        affected = ("semantic_binding", "evidence_selection")
        details = {
            "registered_mismatch": mismatch,
            "removed_reconciliation_axis": reconciliation_axis,
        }
    elif axis == "verification":
        ablated = (
            TaskRequirement.VERIFY_RESULT in task.task.public.requirements
            and "cross_check_evidence" in task.required_tool_ids
            and "selected_branch_cross_check" in task.verification_checkpoints
            and task.structure.distractor_branch_count > 0
            and _artifact_contract_ablation_fails(
                task,
                field="verification_checkpoints",
                value=tuple(
                    item
                    for item in task.verification_checkpoints
                    if item != "selected_branch_cross_check"
                ),
            )
        )
        intervention = "remove_selected_branch_cross_check"
        affected = ("quality_contract", "stop_quality")
        details = {"verification_checkpoints": task.verification_checkpoints}
    elif axis == "recovery":
        actions = tuple(item.action for item in task.query_stages)
        ablated = (
            bool(task.recovery_branches)
            and "broad_search" in actions
            and "typed_refinement" in actions
            and _artifact_contract_ablation_fails(
                task,
                field="recovery_branches",
                value=task.recovery_branches[1:],
            )
        )
        intervention = "remove_required_recovery_transition"
        affected = ("recovery_transition", "answer_replay")
        details = {
            "recovery_branch_count": len(task.recovery_branches),
            "query_actions": actions,
        }
    else:
        ablated = (
            len(task.stopping_conditions) >= 3
            and task.structure.distractor_branch_count > 0
            and _artifact_contract_ablation_fails(
                task,
                field="stopping_conditions",
                value=task.stopping_conditions[:-1],
            )
        )
        intervention = "remove_final_sufficiency_condition"
        affected = ("stopping_contract", "evidence_sufficiency")
        details = {"stopping_conditions": task.stopping_conditions}
    values = {
        "task_artifact_id": task.artifact_id,
        "task_id": task.task.task_id,
        "family": task.family,
        "capability_axis": axis,
        "intervention_kind": intervention,
        "baseline_contract_passed": baseline,
        "ablated_contract_failed": ablated,
        "affected_contracts": affected,
        "details": details,
        "passed": baseline and ablated,
    }
    provisional = CapabilityNecessityProbe.model_construct(probe_hash="pending", **values)
    return CapabilityNecessityProbe(
        probe_hash=capability_necessity_probe_hash(provisional), **values
    )


def _missing_required_evidence_fails(task: CapabilitySensitiveTaskArtifact) -> bool:
    evidence = {item.evidence_id: item for item in task.evidence_bundle.evidence}
    referenced = next(
        ref.ref_id
        for node in task.task.oracle.task_program.nodes
        for ref in node.input_refs
        if ref.kind == InputRefKind.EVIDENCE
    )
    evidence.pop(referenced)
    try:
        TaskProgramExecutor(default_registry()).execute(task.task.oracle.task_program, evidence)
    except ProgramExecutionError:
        return True
    return False


def _remove_required_program_branch_fails(task: CapabilitySensitiveTaskArtifact) -> bool:
    program = task.task.oracle.task_program
    candidate = next(
        (
            node
            for node in program.nodes
            if node.node_id != program.output_node_id and not node.dependencies
        ),
        None,
    )
    if candidate is None or task.structure.operation_branch_count < 2:
        return False
    try:
        TaskProgram(
            program_id=program.program_id,
            nodes=tuple(node for node in program.nodes if node.node_id != candidate.node_id),
            output_node_id=program.output_node_id,
        )
    except ValueError:
        return True
    return False


def _remove_program_output_fails(task: CapabilitySensitiveTaskArtifact) -> bool:
    program = task.task.oracle.task_program
    try:
        TaskProgram(
            program_id=program.program_id,
            nodes=tuple(node for node in program.nodes if node.node_id != program.output_node_id),
            output_node_id=program.output_node_id,
        )
    except ValueError:
        return True
    return False


def _registered_reconciliation_mismatch(
    task: CapabilitySensitiveTaskArtifact,
) -> str | None:
    by_id = task.public_corpus.by_id()
    gold = task.evidence_bundle.evidence
    mapping = {
        "period": "period_alignment",
        "definition": "metric_definition",
        "payload_context": "unit_currency_context",
        "source": "source_or_scope_disambiguation",
        "subject": "source_or_scope_disambiguation",
        "predicate": "metric_definition",
    }
    for branch in task.recovery_branches:
        mismatch = _minimum_mismatch_fields(by_id[branch.distractor_evidence_id], gold)
        if len(mismatch) == 1 and mapping.get(mismatch[0]) in task.reconciliation_axes:
            return mismatch[0]
    return None


def _reconciliation_axis_for_mismatch(mismatch: str) -> str | None:
    return {
        "period": "period_alignment",
        "definition": "metric_definition",
        "payload_context": "unit_currency_context",
        "source": "source_or_scope_disambiguation",
        "subject": "source_or_scope_disambiguation",
        "predicate": "metric_definition",
    }.get(mismatch)


def _artifact_contract_ablation_fails(
    task: CapabilitySensitiveTaskArtifact,
    *,
    field: str,
    value: Any,
) -> bool:
    provisional = task.model_copy(
        update={
            "artifact_id": "pending",
            field: value,
        }
    )
    payload = provisional.model_dump(mode="python")
    payload["artifact_id"] = capability_sensitive_task_artifact_id(provisional)
    try:
        CapabilitySensitiveTaskArtifact.model_validate(payload)
    except ValueError:
        return True
    return False


def _validate_localization_partition(
    bindings: tuple[RuntimeTaskBinding, ...],
) -> None:
    by_task: dict[str, list[RuntimeTaskBinding]] = defaultdict(list)
    for item in bindings:
        by_task[item.task_artifact_id].append(item)
    for values in by_task.values():
        if {item.runtime_arm for item in values} != set(CapabilityRuntimeArm):
            raise ValueError("a Tier Localization task lacks a Runtime binding")
        if len(values) != len(CapabilityRuntimeArm):
            raise ValueError("a Tier Localization task duplicates a Runtime binding")
    counts = {
        (family, tier): len(
            {
                item.task_artifact_id
                for item in bindings
                if item.family == family and item.tier == tier
            }
        )
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for tier in DifficultyTier
    }
    expected = {
        (family, tier): LOCALIZATION_TASKS_PER_FAMILY_TIER
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for tier in DifficultyTier
    }
    if counts != expected:
        raise ValueError("Tier Localization is not balanced by family and difficulty tier")


def _validate_binding_partition(
    bindings: tuple[RuntimeTaskBinding, ...],
    *,
    expected_tasks_per_family: int,
) -> None:
    by_task: dict[str, list[RuntimeTaskBinding]] = defaultdict(list)
    for item in bindings:
        if item.tier != DifficultyTier.FRONTIER:
            raise ValueError("v25 boundary calibration may use only Frontier tasks")
        by_task[item.task_artifact_id].append(item)
    for values in by_task.values():
        if {item.runtime_arm for item in values} != set(CapabilityRuntimeArm):
            raise ValueError("a boundary task lacks a Runtime binding")
        if len(values) != len(CapabilityRuntimeArm):
            raise ValueError("a boundary task duplicates a Runtime binding")
    counts = {
        family: len({item.task_artifact_id for item in bindings if item.family == family})
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    expected = {family: expected_tasks_per_family for family in CAPABILITY_SENSITIVE_FAMILIES}
    if counts != expected:
        raise ValueError("boundary task partition is not balanced by capability family")


def runtime_authority_hash(value: RuntimeAuthorityContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"authority_hash"}),
        prefix="runtime_capability_authority:",
    )


def model_visible_demand_hash(value: ModelVisibleCapabilityDemand) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"demand_hash"}),
        prefix="model_visible_capability_demand:",
    )


def capability_necessity_probe_hash(value: CapabilityNecessityProbe) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"probe_hash"}),
        prefix="capability_necessity_probe:",
    )


def capability_necessity_audit_hash(value: CapabilityNecessityAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_hash"}),
        prefix="capability_necessity_audit:",
    )


def runtime_task_binding_id(value: RuntimeTaskBinding) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"binding_id"}),
        prefix="v25_runtime_task_binding:",
    )


def capability_boundary_contract_id(value: FinanceCapabilityBoundaryContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_boundary_contract:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze the v25-native capability boundary contract"
    )
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--model-source-contract", type=Path, required=True)
    parser.add_argument("--finance-archive-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--random-seed", type=int, default=20260812)
    parser.add_argument("--sampling-salt", required=True)
    args = parser.parse_args(argv)
    contract = prepare_capability_boundary_contract(
        population_path=args.population,
        model_source_contract_path=args.model_source_contract,
        finance_archive_config_path=args.finance_archive_config,
        output_path=args.output,
        run_id=args.run_id,
        random_seed=args.random_seed,
        sampling_salt=args.sampling_salt,
    )
    print(
        json.dumps(
            {
                "contract_id": contract.contract_id,
                "qualification_rollouts": contract.requested_qualification_rollouts,
                "localization_rollouts": contract.requested_localization_rollouts,
                "calibration_rollouts": contract.requested_calibration_rollouts,
                "necessity_ready": contract.necessity_audit.contract_necessity_ready,
                "next_permitted_stage": contract.next_permitted_stage,
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
