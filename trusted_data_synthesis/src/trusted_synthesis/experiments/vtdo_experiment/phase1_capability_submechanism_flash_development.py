from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    CapabilityBoundaryRolloutRecord,
    _all_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    _condition_number,
    _effective_rank,
    _eigenvalues,
    _matrices,
    _normalize_demand,
    _positive_eigenvalues,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismDirectionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    CapabilitySubmechanismPopulation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_support_confirmation import (
    FinanceCapabilitySupportConfirmationContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    _execute_stage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    RuntimeResolutionStage,
    RuntimeTerminalOutcome,
    _load_records,
    _make_terminal_outcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

SUBMECHANISM_FLASH_CONTRACT_VERSION = (
    "finance_capability_submechanism_flash_development_contract.v2"
)
SUBMECHANISM_BEHAVIOR_VERSION = "finance_capability_submechanism_behavior.v2"
SUBMECHANISM_GEOMETRY_VERSION = "finance_capability_submechanism_geometry.v1"
SUBMECHANISM_GATE_VERSION = "finance_capability_submechanism_gate.v1"
SUBMECHANISM_FLASH_REPORT_VERSION = "finance_capability_submechanism_flash_development_report.v2"

EXPECTED_TASK_COUNT = 20
EXPECTED_PARENT_COUNT = 4
DEVELOPMENT_REPLICAS = 3
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * DEVELOPMENT_REPLICAS
DiagnosticResponse = Literal["tool", "verification", "recovery", "stopping"]
DIAGNOSTIC_RESPONSES: tuple[DiagnosticResponse, ...] = (
    "tool",
    "verification",
    "recovery",
    "stopping",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SubmechanismGeometryThresholds(FrozenModel):
    minimum_api_transport_rate: float = Field(default=0.98, ge=0, le=1)
    minimum_bounded_json_rate: float = Field(default=0.95, ge=0, le=1)
    minimum_observation_replay_rate: float = Field(default=0.98, ge=0, le=1)
    minimum_authority_integrity_rate: float = Field(default=0.98, ge=0, le=1)
    maximum_runtime_pathology_rate: float = Field(default=0.02, ge=0, le=1)
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    minimum_boundary_task_fraction: float = Field(default=0.25, ge=0, le=1)
    minimum_nonzero_weight_task_count: int = Field(default=5, ge=1)
    minimum_residual_rank: int = Field(default=4, ge=1)
    minimum_residual_effective_rank: float = Field(default=3.0, ge=1)
    maximum_residual_condition_number: float = Field(default=100.0, gt=1)
    maximum_general_factor_fraction: float = Field(default=0.85, ge=0, le=1)
    minimum_marginal_axis_information: float = Field(default=1e-4, gt=0)
    minimum_informative_axis_count: int = Field(default=4, ge=1)
    maximum_parent_information_share: float = Field(default=0.60, gt=0, le=1)

    @model_validator(mode="after")
    def validate_thresholds(self) -> SubmechanismGeometryThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("submechanism boundary probability interval is empty")
        if self.minimum_informative_axis_count > len(CAPABILITY_AXES):
            raise ValueError("submechanism geometry requires too many informative axes")
        return self


class FinanceSubmechanismFlashContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    stage: RuntimeResolutionStage = RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
    source_direction_report_path: str = Field(min_length=1)
    source_direction_report_sha256: str = Field(min_length=64, max_length=64)
    source_direction_report_id: str = Field(min_length=1)
    source_v25_20_contract_path: str = Field(min_length=1)
    source_v25_20_contract_sha256: str = Field(min_length=64, max_length=64)
    source_v25_20_contract_id: str = Field(min_length=1)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=1, max_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_submechanism_ids: dict[str, str]
    task_parent_mechanism_ids: dict[str, str]
    task_scenario_ids: dict[str, str]
    task_expected_host_events: dict[str, tuple[str, str]]
    task_raw_capability_demands: dict[str, dict[str, float]]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    replicas: Literal[3] = 3
    requested_rollout_count: int = Field(ge=EXPECTED_ROLLOUT_COUNT, le=EXPECTED_ROLLOUT_COUNT)
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    thresholds: SubmechanismGeometryThresholds = Field(
        default_factory=SubmechanismGeometryThresholds
    )
    primary_response_variable: Literal["valid_success"] = "valid_success"
    diagnostic_response_variables: tuple[DiagnosticResponse, ...] = DIAGNOSTIC_RESPONSES
    diagnostics_can_rescue_primary: Literal[False] = False
    confirmation_response_access_during_development: Literal["forbidden"] = "forbidden"
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_submechanism_development"] = (
        "flash_submechanism_development"
    )
    schema_version: str = SUBMECHANISM_FLASH_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceSubmechanismFlashContract:
        if self.stage != RuntimeResolutionStage.RESIDUAL_DEVELOPMENT:
            raise ValueError("submechanism Flash stage must remain Development")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("submechanism Development is Flash-only")
        if self.requested_rollout_count != len(self.bindings) * self.replicas:
            raise ValueError("submechanism rollout denominator is inconsistent")
        task_ids = {item.artifact_id for item in self.tasks}
        maps = (
            self.task_submechanism_ids,
            self.task_parent_mechanism_ids,
            self.task_scenario_ids,
            self.task_expected_host_events,
            self.task_raw_capability_demands,
        )
        if any(set(item) != task_ids for item in maps):
            raise ValueError("submechanism contract task maps are incomplete")
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("submechanism tasks and Runtime bindings differ")
        if any(item.runtime_arm != CapabilityRuntimeArm.AUTONOMOUS_AGENT for item in self.bindings):
            raise ValueError("submechanism Development must use Autonomous Agent Runtime")
        if len(set(self.task_submechanism_ids.values())) != EXPECTED_TASK_COUNT:
            raise ValueError("submechanism contract duplicates a selected direction")
        parent_counts = Counter(self.task_parent_mechanism_ids.values())
        if len(parent_counts) != EXPECTED_PARENT_COUNT or set(parent_counts.values()) != {5}:
            raise ValueError("submechanism parent coverage is not balanced 5 x 4")
        if any(
            set(value) != set(CAPABILITY_AXES)
            for value in self.task_raw_capability_demands.values()
        ):
            raise ValueError("submechanism capability demand omits an axis")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("submechanism rollout identities are incomplete")
        if self.diagnostic_response_variables != DIAGNOSTIC_RESPONSES:
            raise ValueError("submechanism diagnostic responses changed")
        if self.contract_id != submechanism_flash_contract_id(self):
            raise ValueError("submechanism Flash contract identity is invalid")
        return self


class SubmechanismBehaviorObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    submechanism_id: str = Field(min_length=1)
    parent_mechanism_id: str = Field(min_length=1)
    replicate: int = Field(ge=0)
    runtime_eligible: bool
    expected_host_events: tuple[str, str]
    observed_host_events: tuple[str, ...]
    trigger_observed: bool
    resolution_observed: bool
    host_event_ordered: bool
    behavior_evaluable: bool
    behavior_success: bool
    primary_valid_success: bool
    tool_response: bool
    verification_response: bool
    recovery_response: bool
    stopping_response: bool
    observed_tool_ids: tuple[str, ...]
    failed_tool_call_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    decision_depth: int = Field(ge=0)
    schema_version: str = SUBMECHANISM_BEHAVIOR_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> SubmechanismBehaviorObservation:
        if self.behavior_evaluable != self.runtime_eligible:
            raise ValueError("submechanism behavior denominator is inconsistent")
        expected_success = self.runtime_eligible and self.host_event_ordered
        if self.behavior_success != expected_success:
            raise ValueError("submechanism behavior success is inconsistent")
        if self.host_event_ordered and not (self.trigger_observed and self.resolution_observed):
            raise ValueError("ordered submechanism behavior lacks both Host events")
        if self.observation_id != submechanism_behavior_observation_id(self):
            raise ValueError("submechanism behavior identity is invalid")
        return self


class SubmechanismGeometrySpectrum(FrozenModel):
    response_variable: str = Field(min_length=1)
    task_count: int = Field(ge=0)
    rollout_count: int = Field(ge=0)
    distinct_normalized_demand_count: int = Field(ge=0)
    nonzero_weight_task_count: int = Field(ge=0)
    conditional_response_rate: float = Field(ge=0, le=1)
    boundary_task_fraction: float = Field(ge=0, le=1)
    raw_matrix: tuple[tuple[float, ...], ...]
    residual_matrix: tuple[tuple[float, ...], ...]
    raw_eigenvalues: tuple[float, ...]
    residual_eigenvalues: tuple[float, ...]
    raw_numerical_rank: int = Field(ge=0)
    raw_effective_rank: float = Field(ge=0)
    raw_condition_number: float = Field(ge=1)
    residual_numerical_rank: int = Field(ge=0)
    residual_effective_rank: float = Field(ge=0)
    residual_condition_number: float = Field(ge=1)
    general_factor_fraction: float = Field(ge=0, le=1)
    marginal_axis_information: dict[str, float]
    informative_axis_count: int = Field(ge=0)
    parent_information_share: dict[str, float]
    maximum_parent_information_share: float = Field(ge=0, le=1)
    task_response_probability: dict[str, float]
    schema_version: str = SUBMECHANISM_GEOMETRY_VERSION

    @model_validator(mode="after")
    def validate_spectrum(self) -> SubmechanismGeometrySpectrum:
        size = len(CAPABILITY_AXES)
        for matrix in (self.raw_matrix, self.residual_matrix):
            if len(matrix) != size or any(len(row) != size for row in matrix):
                raise ValueError("submechanism geometry matrix shape is invalid")
        if len(self.raw_eigenvalues) != size or len(self.residual_eigenvalues) != size:
            raise ValueError("submechanism geometry spectrum is incomplete")
        if set(self.marginal_axis_information) != set(CAPABILITY_AXES):
            raise ValueError("submechanism marginal information is incomplete")
        observed_max = max(self.parent_information_share.values(), default=0.0)
        if not math.isclose(self.maximum_parent_information_share, observed_max, abs_tol=1e-12):
            raise ValueError("submechanism parent information share is inconsistent")
        return self


class SubmechanismDevelopmentGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    category: Literal["runtime", "coverage", "primary_geometry"]
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool
    schema_version: str = SUBMECHANISM_GATE_VERSION


class FinanceSubmechanismFlashReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    runtime_eligible_rollout_count: int = Field(ge=0)
    complete_runtime_eligible_task_count: int = Field(ge=0)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    runtime_pathology_rate: float = Field(ge=0, le=1)
    semantic_accuracy_given_runtime_eligible: float = Field(ge=0, le=1)
    end_to_end_valid_success_rate: float = Field(ge=0, le=1)
    host_trigger_observation_rate: float = Field(ge=0, le=1)
    host_resolution_observation_rate: float = Field(ge=0, le=1)
    ordered_behavior_success_rate: float = Field(ge=0, le=1)
    primary_spectrum: SubmechanismGeometrySpectrum
    diagnostic_spectra: dict[DiagnosticResponse, SubmechanismGeometrySpectrum]
    gates: tuple[SubmechanismDevelopmentGate, ...] = Field(min_length=10)
    runtime_measurement_ready: bool
    primary_information_geometry_ready: bool
    failure_codes: tuple[str, ...]
    outcome_set_hash: str = Field(min_length=1)
    behavior_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    diagnostics_rescued_primary: Literal[False] = False
    fresh_submechanism_confirmation_authorized: bool
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "fresh_submechanism_confirmation_preparation",
        "submechanism_task_redesign_only",
        "runtime_measurement_repair_only",
    ]
    schema_version: str = SUBMECHANISM_FLASH_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceSubmechanismFlashReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("submechanism Development lacks its complete denominator")
        runtime_gates = tuple(item for item in self.gates if item.category == "runtime")
        geometry_gates = tuple(
            item for item in self.gates if item.category in {"coverage", "primary_geometry"}
        )
        runtime_ready = bool(runtime_gates) and all(item.passed for item in runtime_gates)
        geometry_ready = (
            runtime_ready and bool(geometry_gates) and all(item.passed for item in geometry_gates)
        )
        if self.runtime_measurement_ready != runtime_ready:
            raise ValueError("submechanism Runtime readiness is inconsistent")
        if self.primary_information_geometry_ready != geometry_ready:
            raise ValueError("submechanism primary geometry readiness is inconsistent")
        if self.fresh_submechanism_confirmation_authorized != geometry_ready:
            raise ValueError("submechanism confirmation authorization is inconsistent")
        expected = (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "fresh_submechanism_confirmation_preparation"
                if geometry_ready
                else "submechanism_task_redesign_only"
            )
        )
        if self.next_permitted_stage != expected:
            raise ValueError("submechanism Development transition is not fail-closed")
        if set(self.diagnostic_spectra) != set(DIAGNOSTIC_RESPONSES):
            raise ValueError("submechanism diagnostics are incomplete")
        if self.report_id != submechanism_flash_report_id(self):
            raise ValueError("submechanism Flash report identity is invalid")
        return self


@dataclass(frozen=True)
class _GeometryRow:
    task_id: str
    group_id: str
    mechanism_id: str
    probability: float
    general_difficulty: float
    demand: tuple[float, ...]
    realizations: tuple[int, ...]


def submechanism_flash_contract_id(value: FinanceSubmechanismFlashContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_submechanism_flash_contract:",
    )


def submechanism_behavior_observation_id(
    value: SubmechanismBehaviorObservation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="finance_capability_submechanism_behavior:",
    )


def submechanism_flash_report_id(value: FinanceSubmechanismFlashReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_submechanism_flash_report:",
    )


def prepare_submechanism_flash_development(
    *,
    source_population_path: Path,
    source_v25_20_contract_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceSubmechanismFlashContract:
    if output_path.exists():
        raise ValueError("submechanism Flash Development contract is immutable")
    population_path = source_population_path.resolve()
    source_contract_path = source_v25_20_contract_path.resolve()
    population = CapabilitySubmechanismPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    source = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        source_contract_path.read_text(encoding="utf-8")
    )
    direction_path = Path(population.source_direction_report_path).resolve()
    direction = CapabilitySubmechanismDirectionReport.model_validate_json(
        direction_path.read_text(encoding="utf-8")
    )
    if (
        not population.static_audit.ready
        or population.next_permitted_stage != "flash_submechanism_development"
    ):
        raise ValueError("submechanism Flash Development lacks a passing Runtime population")
    selected_specs = {
        item.submechanism_id: item
        for item in direction.candidate_specs
        if item.submechanism_id in set(direction.selected_submechanism_ids)
    }
    model_contracts = tuple(
        item for item in source.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("source contract does not freeze exactly one Flash model")
    tasks = tuple(item.artifact for item in population.tasks)
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            source.protocol_profile,
        )
        for task in tasks
    )
    task_rows = {item.artifact.artifact_id: item for item in population.tasks}
    submechanism_ids = {task_id: item.submechanism_id for task_id, item in task_rows.items()}
    parent_ids = {task_id: item.parent_mechanism_id for task_id, item in task_rows.items()}
    scenario_ids = {task_id: item.scenario.scenario_id for task_id, item in task_rows.items()}
    expected_events = {
        task_id: item.scenario.expected_host_events for task_id, item in task_rows.items()
    }
    raw_demands = {
        task_id: selected_specs[item.submechanism_id].raw_capability_demand
        for task_id, item in task_rows.items()
    }
    tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "population_id": population.population_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
            },
            prefix="finance_capability_submechanism_flash_rollout:",
        )
        for binding in bindings
        for replicate in range(DEVELOPMENT_REPLICAS)
    }
    implementation = _implementation_manifest()
    finance_config = Path(source.finance_archive_config_path).resolve()
    values = {
        "run_id": run_id,
        "source_population_path": str(population_path),
        "source_population_sha256": _sha256(population_path),
        "source_population_id": population.population_id,
        "source_direction_report_path": str(direction_path),
        "source_direction_report_sha256": _sha256(direction_path),
        "source_direction_report_id": direction.report_id,
        "source_v25_20_contract_path": str(source_contract_path),
        "source_v25_20_contract_sha256": _sha256(source_contract_path),
        "source_v25_20_contract_id": source.contract_id,
        "finance_archive_config_path": str(finance_config),
        "finance_archive_config_sha256": _sha256(finance_config),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_capability_submechanism_flash_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": source.protocol_profile,
        "tasks": tasks,
        "task_submechanism_ids": submechanism_ids,
        "task_parent_mechanism_ids": parent_ids,
        "task_scenario_ids": scenario_ids,
        "task_expected_host_events": expected_events,
        "task_raw_capability_demands": raw_demands,
        "bindings": bindings,
        "requested_rollout_count": len(bindings) * DEVELOPMENT_REPLICAS,
        "maximum_model_tokens_per_rollout": source.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": source.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": source.maximum_public_context_bytes,
        "model_contract_repair_attempts": source.model_contract_repair_attempts,
        "rollout_identity_tokens": tokens,
    }
    provisional = FinanceSubmechanismFlashContract.model_construct(contract_id="pending", **values)
    contract = FinanceSubmechanismFlashContract(
        contract_id=submechanism_flash_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_submechanism_flash_development(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceSubmechanismFlashReport:
    contract = FinanceSubmechanismFlashContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_inputs(contract)
    prefix = "capability_submechanism_flash_development"
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
    terminals = _make_terminals(contract, records, outcomes)
    behaviors = make_submechanism_behavior_observations(contract, records, outcomes, terminals)
    terminal_path = output_dir / f"{prefix}_terminal_outcomes.jsonl"
    behavior_path = output_dir / f"{prefix}_behavior_observations.jsonl"
    _write_jsonl_atomic(terminal_path, (item.model_dump(mode="json") for item in terminals))
    _write_jsonl_atomic(behavior_path, (item.model_dump(mode="json") for item in behaviors))
    report = make_submechanism_flash_report(contract, outcomes, terminals, behaviors)
    report_path = output_dir / "finance_capability_submechanism_flash_report.json"
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_capability_submechanism_flash_report.md",
        _render_report(report),
    )
    _write_json_atomic(
        output_dir / "finance_capability_submechanism_flash_manifest.json",
        {
            "contract_id": contract.contract_id,
            "report_id": report.report_id,
            "requested_model": contract.model_contracts[0].requested_model,
            "discovered_models": discovered,
            "records_sha256": _sha256(records_path),
            "outcomes_sha256": _sha256(outcomes_path),
            "terminal_outcomes_sha256": _sha256(terminal_path),
            "behavior_observations_sha256": _sha256(behavior_path),
            "report_sha256": _sha256(report_path),
            "pro_api_call_count": 0,
            "beneficiary_screening_authorized": False,
            "exact_target_evaluated": False,
            "gp_c_evaluated": False,
        },
    )
    return report


def make_submechanism_behavior_observations(
    contract: FinanceSubmechanismFlashContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
) -> tuple[SubmechanismBehaviorObservation, ...]:
    terminal_by_key = {(item.binding_id, item.replicate): item for item in terminals}
    outcome_by_key = {(item.binding_id, item.replicate): item for item in outcomes}
    rows = []
    for record in sorted(records, key=lambda item: (item.binding_id, item.replicate)):
        key = (record.binding_id, record.replicate)
        terminal = terminal_by_key[key]
        outcome = outcome_by_key[key]
        expected = contract.task_expected_host_events[record.task_artifact_id]
        observations = _all_observations(record)
        events = _host_event_sequence(observations, expected)
        trigger = expected[0] in events
        resolution = expected[1] in events
        ordered = bool(
            trigger and resolution and events.index(expected[0]) <= events.index(expected[1])
        )
        tool_ids = tuple(item.call.tool_id for item in observations)
        values = {
            "contract_id": contract.contract_id,
            "record_id": record.record_id,
            "binding_id": record.binding_id,
            "task_artifact_id": record.task_artifact_id,
            "submechanism_id": contract.task_submechanism_ids[record.task_artifact_id],
            "parent_mechanism_id": contract.task_parent_mechanism_ids[record.task_artifact_id],
            "replicate": record.replicate,
            "runtime_eligible": terminal.runtime_eligible_for_capability_denominator,
            "expected_host_events": expected,
            "observed_host_events": events,
            "trigger_observed": trigger,
            "resolution_observed": resolution,
            "host_event_ordered": ordered,
            "behavior_evaluable": terminal.runtime_eligible_for_capability_denominator,
            "behavior_success": (terminal.runtime_eligible_for_capability_denominator and ordered),
            "primary_valid_success": terminal.valid_success,
            "tool_response": bool(tool_ids and trigger),
            "verification_response": bool(
                "cross_check_evidence" in tool_ids and outcome.verification_success
            ),
            "recovery_response": ordered,
            "stopping_response": bool(
                outcome.final_answer_emitted and outcome.stop_quality_success
            ),
            "observed_tool_ids": tool_ids,
            "failed_tool_call_count": sum(item.status == "failed" for item in observations),
            "successful_tool_call_count": sum(item.status == "succeeded" for item in observations),
            "decision_depth": len(record.trajectory.steps) if record.trajectory else 0,
        }
        provisional = SubmechanismBehaviorObservation.model_construct(
            observation_id="pending", **values
        )
        rows.append(
            SubmechanismBehaviorObservation(
                observation_id=submechanism_behavior_observation_id(provisional),
                **values,
            )
        )
    return tuple(rows)


def make_submechanism_flash_report(
    contract: FinanceSubmechanismFlashContract,
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[SubmechanismBehaviorObservation],
) -> FinanceSubmechanismFlashReport:
    if not (len(outcomes) == len(terminals) == len(behaviors) == contract.requested_rollout_count):
        raise ValueError("submechanism report has an incomplete rollout denominator")
    grouped: dict[str, list[SubmechanismBehaviorObservation]] = defaultdict(list)
    for item in behaviors:
        grouped[item.task_artifact_id].append(item)
    complete_task_ids = {
        task_id
        for task_id, values in grouped.items()
        if len(values) == contract.replicas and all(item.runtime_eligible for item in values)
    }
    primary = _make_spectrum(
        contract,
        _geometry_rows(
            contract,
            behaviors,
            complete_task_ids=complete_task_ids,
            response_variable="primary_valid_success",
        ),
        response_variable="valid_success",
    )
    diagnostics = {
        response: _make_spectrum(
            contract,
            _geometry_rows(
                contract,
                behaviors,
                complete_task_ids=complete_task_ids,
                response_variable=f"{response}_response",
            ),
            response_variable=response,
        )
        for response in DIAGNOSTIC_RESPONSES
    }
    gates = _make_gates(contract, terminals, primary, len(complete_task_ids))
    runtime_ready = all(item.passed for item in gates if item.category == "runtime")
    geometry_ready = runtime_ready and all(
        item.passed for item in gates if item.category in {"coverage", "primary_geometry"}
    )
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    values = {
        "contract_id": contract.contract_id,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(terminals),
        "runtime_eligible_rollout_count": len(eligible),
        "complete_runtime_eligible_task_count": len(complete_task_ids),
        "api_transport_resolution_rate": _rate(item.api_transport_resolved for item in terminals),
        "bounded_json_resolution_rate": _rate(
            item.bounded_json_resolution_success for item in terminals
        ),
        "observation_replay_rate": _rate(item.observation_replay_success for item in terminals),
        "authority_integrity_rate": _rate(item.authority_integrity_success for item in terminals),
        "runtime_pathology_rate": _rate(item.runtime_pathology for item in terminals),
        "semantic_accuracy_given_runtime_eligible": (
            _rate(item.semantic_answer_correct for item in eligible) if eligible else 0.0
        ),
        "end_to_end_valid_success_rate": _rate(item.valid_success for item in terminals),
        "host_trigger_observation_rate": _rate(item.trigger_observed for item in behaviors),
        "host_resolution_observation_rate": _rate(item.resolution_observed for item in behaviors),
        "ordered_behavior_success_rate": _rate(item.behavior_success for item in behaviors),
        "primary_spectrum": primary,
        "diagnostic_spectra": diagnostics,
        "gates": gates,
        "runtime_measurement_ready": runtime_ready,
        "primary_information_geometry_ready": geometry_ready,
        "failure_codes": tuple(item.gate_id for item in gates if not item.passed),
        "outcome_set_hash": canonical_hash(
            tuple(item.terminal_outcome_id for item in terminals),
            prefix="finance_capability_submechanism_terminal_set:",
        ),
        "behavior_set_hash": canonical_hash(
            tuple(item.observation_id for item in behaviors),
            prefix="finance_capability_submechanism_behavior_set:",
        ),
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "fresh_submechanism_confirmation_authorized": geometry_ready,
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "fresh_submechanism_confirmation_preparation"
                if geometry_ready
                else "submechanism_task_redesign_only"
            )
        ),
    }
    provisional = FinanceSubmechanismFlashReport.model_construct(report_id="pending", **values)
    return FinanceSubmechanismFlashReport(
        report_id=submechanism_flash_report_id(provisional), **values
    )


def _geometry_rows(
    contract: FinanceSubmechanismFlashContract,
    observations: Sequence[SubmechanismBehaviorObservation],
    *,
    complete_task_ids: set[str],
    response_variable: str,
) -> tuple[_GeometryRow, ...]:
    binding_by_task = {item.task_artifact_id: item for item in contract.bindings}
    grouped: dict[str, list[SubmechanismBehaviorObservation]] = defaultdict(list)
    for item in observations:
        if item.task_artifact_id in complete_task_ids:
            grouped[item.task_artifact_id].append(item)
    rows = []
    for task_id, values in sorted(grouped.items()):
        realizations = tuple(int(bool(getattr(item, response_variable))) for item in values)
        rows.append(
            _GeometryRow(
                task_id=task_id,
                group_id=task_id,
                mechanism_id=contract.task_parent_mechanism_ids[task_id],
                probability=sum(realizations) / len(realizations),
                general_difficulty=binding_by_task[task_id].general_difficulty,
                demand=_normalize_demand(contract.task_raw_capability_demands[task_id]),
                realizations=realizations,
            )
        )
    return tuple(rows)


def _make_spectrum(
    contract: FinanceSubmechanismFlashContract,
    rows: Sequence[_GeometryRow],
    *,
    response_variable: str,
) -> SubmechanismGeometrySpectrum:
    parent_ids = tuple(sorted(set(contract.task_parent_mechanism_ids.values())))
    if rows:
        raw, residual, general_fraction = _matrices(cast(Any, rows))
    else:
        size = len(CAPABILITY_AXES)
        raw = residual = tuple(tuple(0.0 for _ in range(size)) for _ in range(size))
        general_fraction = 1.0
    raw_values = _eigenvalues(raw)
    residual_values = _eigenvalues(residual)
    raw_positive = _positive_eigenvalues(raw_values)
    residual_positive = _positive_eigenvalues(residual_values)
    weights = [item.probability * (1 - item.probability) for item in rows]
    total_weight = sum(weights)
    parent_weights = {
        parent: sum(
            weight for row, weight in zip(rows, weights, strict=True) if row.mechanism_id == parent
        )
        for parent in parent_ids
    }
    parent_shares = {
        parent: value / total_weight if total_weight else 0.0
        for parent, value in parent_weights.items()
    }
    thresholds = contract.thresholds
    return SubmechanismGeometrySpectrum(
        response_variable=response_variable,
        task_count=len(rows),
        rollout_count=sum(len(item.realizations) for item in rows),
        distinct_normalized_demand_count=len(
            {tuple(round(value, 12) for value in item.demand) for item in rows}
        ),
        nonzero_weight_task_count=sum(value > 0 for value in weights),
        conditional_response_rate=(fmean(item.probability for item in rows) if rows else 0.0),
        boundary_task_fraction=(
            sum(
                thresholds.boundary_probability_lower
                <= item.probability
                <= thresholds.boundary_probability_upper
                for item in rows
            )
            / len(rows)
            if rows
            else 0.0
        ),
        raw_matrix=raw,
        residual_matrix=residual,
        raw_eigenvalues=raw_values,
        residual_eigenvalues=residual_values,
        raw_numerical_rank=len(raw_positive),
        raw_effective_rank=_effective_rank(raw_positive),
        raw_condition_number=_condition_number(raw_positive),
        residual_numerical_rank=len(residual_positive),
        residual_effective_rank=_effective_rank(residual_positive),
        residual_condition_number=_condition_number(residual_positive),
        general_factor_fraction=general_fraction,
        marginal_axis_information={
            axis: raw[index][index] for index, axis in enumerate(CAPABILITY_AXES)
        },
        informative_axis_count=sum(
            raw[index][index] >= thresholds.minimum_marginal_axis_information
            for index in range(len(CAPABILITY_AXES))
        ),
        parent_information_share=parent_shares,
        maximum_parent_information_share=max(parent_shares.values(), default=0.0),
        task_response_probability={item.task_id: item.probability for item in rows},
    )


def _make_gates(
    contract: FinanceSubmechanismFlashContract,
    terminals: Sequence[RuntimeTerminalOutcome],
    spectrum: SubmechanismGeometrySpectrum,
    complete_task_count: int,
) -> tuple[SubmechanismDevelopmentGate, ...]:
    thresholds = contract.thresholds
    transport = _rate(item.api_transport_resolved for item in terminals)
    bounded = _rate(item.bounded_json_resolution_success for item in terminals)
    replay = _rate(item.observation_replay_success for item in terminals)
    authority = _rate(item.authority_integrity_success for item in terminals)
    pathology = _rate(item.runtime_pathology for item in terminals)
    values: tuple[tuple[str, bool, float, str, str], ...] = (
        (
            "complete_rollout_denominator",
            len(terminals) == contract.requested_rollout_count,
            len(terminals),
            f"={contract.requested_rollout_count}",
            "runtime",
        ),
        (
            "api_transport_resolution_rate",
            transport >= thresholds.minimum_api_transport_rate,
            transport,
            f">={thresholds.minimum_api_transport_rate}",
            "runtime",
        ),
        (
            "bounded_json_resolution_rate",
            bounded >= thresholds.minimum_bounded_json_rate,
            bounded,
            f">={thresholds.minimum_bounded_json_rate}",
            "runtime",
        ),
        (
            "observation_replay_rate",
            replay >= thresholds.minimum_observation_replay_rate,
            replay,
            f">={thresholds.minimum_observation_replay_rate}",
            "runtime",
        ),
        (
            "authority_integrity_rate",
            authority >= thresholds.minimum_authority_integrity_rate,
            authority,
            f">={thresholds.minimum_authority_integrity_rate}",
            "runtime",
        ),
        (
            "runtime_pathology_rate",
            pathology <= thresholds.maximum_runtime_pathology_rate,
            pathology,
            f"<={thresholds.maximum_runtime_pathology_rate}",
            "runtime",
        ),
        (
            "complete_runtime_eligible_task_denominator",
            complete_task_count == EXPECTED_TASK_COUNT,
            complete_task_count,
            f"={EXPECTED_TASK_COUNT}",
            "runtime",
        ),
        (
            "primary_geometry_task_denominator",
            spectrum.task_count == EXPECTED_TASK_COUNT,
            spectrum.task_count,
            f"={EXPECTED_TASK_COUNT}",
            "coverage",
        ),
        (
            "primary_geometry_rollout_denominator",
            spectrum.rollout_count == EXPECTED_ROLLOUT_COUNT,
            spectrum.rollout_count,
            f"={EXPECTED_ROLLOUT_COUNT}",
            "coverage",
        ),
        (
            "distinct_normalized_demand_coverage",
            spectrum.distinct_normalized_demand_count >= thresholds.minimum_residual_rank,
            spectrum.distinct_normalized_demand_count,
            f">={thresholds.minimum_residual_rank}",
            "coverage",
        ),
        (
            "nonzero_weight_task_count",
            spectrum.nonzero_weight_task_count >= thresholds.minimum_nonzero_weight_task_count,
            spectrum.nonzero_weight_task_count,
            f">={thresholds.minimum_nonzero_weight_task_count}",
            "primary_geometry",
        ),
        (
            "boundary_task_fraction",
            spectrum.boundary_task_fraction >= thresholds.minimum_boundary_task_fraction,
            spectrum.boundary_task_fraction,
            f">={thresholds.minimum_boundary_task_fraction}",
            "primary_geometry",
        ),
        (
            "residual_numerical_rank",
            spectrum.residual_numerical_rank >= thresholds.minimum_residual_rank,
            spectrum.residual_numerical_rank,
            f">={thresholds.minimum_residual_rank}",
            "primary_geometry",
        ),
        (
            "residual_effective_rank",
            spectrum.residual_effective_rank >= thresholds.minimum_residual_effective_rank,
            spectrum.residual_effective_rank,
            f">={thresholds.minimum_residual_effective_rank}",
            "primary_geometry",
        ),
        (
            "residual_condition_number",
            spectrum.residual_condition_number <= thresholds.maximum_residual_condition_number,
            spectrum.residual_condition_number,
            f"<={thresholds.maximum_residual_condition_number}",
            "primary_geometry",
        ),
        (
            "general_factor_fraction",
            spectrum.general_factor_fraction <= thresholds.maximum_general_factor_fraction,
            spectrum.general_factor_fraction,
            f"<={thresholds.maximum_general_factor_fraction}",
            "primary_geometry",
        ),
        (
            "informative_axis_count",
            spectrum.informative_axis_count >= thresholds.minimum_informative_axis_count,
            spectrum.informative_axis_count,
            f">={thresholds.minimum_informative_axis_count}",
            "primary_geometry",
        ),
        (
            "maximum_parent_information_share",
            spectrum.maximum_parent_information_share
            <= thresholds.maximum_parent_information_share,
            spectrum.maximum_parent_information_share,
            f"<={thresholds.maximum_parent_information_share}",
            "primary_geometry",
        ),
    )
    return tuple(
        SubmechanismDevelopmentGate(
            gate_id=gate_id,
            category=cast(Any, category),
            observed=float(observed),
            requirement=requirement,
            passed=passed,
        )
        for gate_id, passed, observed, requirement, category in values
    )


def _make_terminals(
    contract: FinanceSubmechanismFlashContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
) -> tuple[RuntimeTerminalOutcome, ...]:
    if len(records) != contract.requested_rollout_count or len(outcomes) != len(records):
        raise ValueError("submechanism Development has an incomplete Runtime denominator")
    record_by_key = {(item.binding_id, item.replicate): item for item in records}
    outcome_by_key = {(item.binding_id, item.replicate): item for item in outcomes}
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    if set(record_by_key) != set(outcome_by_key):
        raise ValueError("submechanism records and outcomes differ")
    return tuple(
        _make_terminal_outcome(
            cast(Any, contract),
            record_by_key[key],
            outcome_by_key[key],
            binding_by_id[key[0]],
        )
        for key in sorted(record_by_key)
    )


def _host_event_sequence(
    observations: Sequence[Any],
    expected: tuple[str, str],
) -> tuple[str, ...]:
    output: list[str] = []
    allowed = set(expected)
    for observation in observations:
        output.extend(_host_events(observation.result, allowed))
    return tuple(output)


def _host_events(value: Any, allowed: set[str]) -> list[str]:
    if isinstance(value, Mapping):
        sequence = value.get("host_event_sequence")
        output: list[str] = []
        if isinstance(sequence, (list, tuple)):
            output.extend(str(item) for item in sequence if str(item) in allowed)
        for key, item in value.items():
            if key == "host_event_sequence" or (sequence is not None and key == "host_event"):
                continue
            output.extend(_host_events(item, allowed))
        return output
    if isinstance(value, (list, tuple)):
        return [event for item in value for event in _host_events(item, allowed)]
    return [value] if isinstance(value, str) and value in allowed else []


def _verify_inputs(contract: FinanceSubmechanismFlashContract) -> None:
    pairs = (
        (contract.source_population_path, contract.source_population_sha256),
        (
            contract.source_direction_report_path,
            contract.source_direction_report_sha256,
        ),
        (
            contract.source_v25_20_contract_path,
            contract.source_v25_20_contract_sha256,
        ),
        (contract.finance_archive_config_path, contract.finance_archive_config_sha256),
    )
    for path_value, expected in pairs:
        if _sha256(Path(path_value)) != expected:
            raise ValueError(f"submechanism frozen input changed:{path_value}")
    implementation = _implementation_manifest()
    if implementation != contract.implementation_manifest:
        raise ValueError("submechanism implementation changed after contract freeze")
    expected_hash = canonical_hash(
        implementation,
        prefix="finance_capability_submechanism_flash_implementation:",
    )
    if contract.implementation_manifest_hash != expected_hash:
        raise ValueError("submechanism implementation manifest hash is invalid")
    population = CapabilitySubmechanismPopulation.model_validate_json(
        Path(contract.source_population_path).read_text(encoding="utf-8")
    )
    if population.population_id != contract.source_population_id:
        raise ValueError("submechanism Development loaded another population")
    if not population.static_audit.ready:
        raise ValueError("submechanism frozen population is no longer eligible")


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        root / "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_submechanism_population.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_submechanism_direction_design.py"
        ),
        root / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary.py",
        root
        / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary_runner.py",
        root / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_confirmation.py",
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_multitier_runtime_resolution.py"
        ),
        root / "src/trusted_synthesis/runtime/agent/iterative.py",
        root / "src/trusted_synthesis/runtime/agent/llm_agent.py",
        root / "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in paths}


def _rate(values: Iterable[bool]) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def _render_report(value: FinanceSubmechanismFlashReport) -> str:
    primary = value.primary_spectrum
    lines = [
        "# Finance v25.25 Flash Submechanism Development Report",
        "",
        "## Decision",
        "",
        f"- Report ID: `{value.report_id}`",
        f"- Rollouts: **{value.recorded_rollout_count}/{value.requested_rollout_count}**",
        f"- Runtime measurement ready: **{value.runtime_measurement_ready}**",
        f"- Primary information geometry ready: **{value.primary_information_geometry_ready}**",
        f"- Next permitted stage: `{value.next_permitted_stage}`",
        "- Pro / Beneficiary / Exact Target / GP-C: **blocked**",
        "",
        "## Runtime Instrument",
        "",
        f"- API transport resolution: **{value.api_transport_resolution_rate:.2%}**",
        f"- Bounded JSON resolution: **{value.bounded_json_resolution_rate:.2%}**",
        f"- Observation replay: **{value.observation_replay_rate:.2%}**",
        f"- Authority integrity: **{value.authority_integrity_rate:.2%}**",
        f"- Runtime pathology: **{value.runtime_pathology_rate:.2%}**",
        f"- Host trigger observed: **{value.host_trigger_observation_rate:.2%}**",
        f"- Host resolution observed: **{value.host_resolution_observation_rate:.2%}**",
        f"- Ordered trigger-resolution behavior: **{value.ordered_behavior_success_rate:.2%}**",
        "",
        "## Primary Response Geometry",
        "",
        "The sole authorizing response is `valid_success`. Diagnostics cannot rescue it.",
        "",
        f"- Conditional valid success: **{primary.conditional_response_rate:.2%}**",
        f"- Boundary task fraction: **{primary.boundary_task_fraction:.2%}**",
        f"- Nonzero-weight tasks: **{primary.nonzero_weight_task_count}**",
        f"- Residual numerical rank: **{primary.residual_numerical_rank}**",
        f"- Residual effective rank: **{primary.residual_effective_rank:.4f}**",
        f"- Residual condition number: **{primary.residual_condition_number:.4f}**",
        f"- General-factor fraction: **{primary.general_factor_fraction:.2%}**",
        f"- Informative axes: **{primary.informative_axis_count}/{len(CAPABILITY_AXES)}**",
        f"- Maximum parent information share: **{primary.maximum_parent_information_share:.2%}**",
        "",
        "## Diagnostic Responses",
        "",
        "| Response | Rate | Residual rank | Effective rank | Condition |",
        "|---|---:|---:|---:|---:|",
    ]
    for response in DIAGNOSTIC_RESPONSES:
        item = value.diagnostic_spectra[response]
        lines.append(
            f"| `{response}` | {item.conditional_response_rate:.2%} | "
            f"{item.residual_numerical_rank} | {item.residual_effective_rank:.4f} | "
            f"{item.residual_condition_number:.4f} |"
        )
    lines.extend(
        (
            "",
            "## Failed Gates",
            "",
            *(f"- `{item}`" for item in value.failure_codes),
            "",
            "This Development result may authorize only a fresh Flash submechanism "
            "Confirmation. It cannot authorize Pro ranking, Beneficiary screening, "
            "Exact Target, GP-C, or VTDO updates.",
            "",
        )
    )
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    _write_text_atomic(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl_atomic(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    _write_text_atomic(
        path,
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in values),
    )


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare or run v25.25 Flash submechanism Development."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-population", required=True, type=Path)
    prepare.add_argument("--source-v25-20-contract", required=True, type=Path)
    prepare.add_argument("--output-path", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=12)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "prepare":
        result: Any = prepare_submechanism_flash_development(
            source_population_path=args.source_population,
            source_v25_20_contract_path=args.source_v25_20_contract,
            output_path=args.output_path,
            run_id=args.run_id,
        )
        summary = {
            "contract_id": result.contract_id,
            "task_count": len(result.tasks),
            "requested_rollout_count": result.requested_rollout_count,
            "next_permitted_stage": result.next_permitted_stage,
        }
    else:
        result = run_submechanism_flash_development(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        summary = {
            "report_id": result.report_id,
            "recorded_rollout_count": result.recorded_rollout_count,
            "runtime_measurement_ready": result.runtime_measurement_ready,
            "primary_information_geometry_ready": (result.primary_information_geometry_ready),
            "next_permitted_stage": result.next_permitted_stage,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
