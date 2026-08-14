from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismDirectionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    SubmechanismBehaviorObservation,
    _make_terminals,
    _rate,
    make_submechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    _implementation_manifest as _base_implementation_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    CapabilitySubmechanismPopulation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_support_confirmation import (  # noqa: E501
    FinanceCapabilitySupportConfirmationContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    _execute_stage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (  # noqa: E501
    RuntimeResolutionStage,
    RuntimeTerminalOutcome,
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

STOPPING_BOUNDARY_CALIBRATION_CONTRACT_VERSION = (
    "finance_stopping_boundary_calibration_contract.v1"
)
STOPPING_BOUNDARY_CALIBRATION_REPORT_VERSION = (
    "finance_stopping_boundary_calibration_report.v1"
)
STOPPING_BOUNDARY_CALIBRATION_MANIFEST_VERSION = (
    "finance_stopping_boundary_calibration_manifest.v1"
)
STOPPING_BOUNDARY_CALIBRATION_RUNNER_VERSION = (
    "finance_stopping_boundary_calibration_runner.v1"
)

STOPPING_PARENT_ID = "finance.state_dependent_control_and_stopping"
STOPPING_SUBMECHANISM_IDS = (
    f"{STOPPING_PARENT_ID}.incomplete_continue",
    f"{STOPPING_PARENT_ID}.post_complete_cost",
    f"{STOPPING_PARENT_ID}.post_complete_error_risk",
    f"{STOPPING_PARENT_ID}.uncertain_source_coverage",
    f"{STOPPING_PARENT_ID}.unresolved_conflict_cannot_stop",
)
SOURCE_COVERAGE_ID = f"{STOPPING_PARENT_ID}.uncertain_source_coverage"
UNRESOLVED_CONFLICT_ID = f"{STOPPING_PARENT_ID}.unresolved_conflict_cannot_stop"
CONTROL_SUBMECHANISM_IDS = frozenset(STOPPING_SUBMECHANISM_IDS) - {
    SOURCE_COVERAGE_ID,
    UNRESOLVED_CONFLICT_ID,
}

EXPECTED_TASK_COUNT = 5
CALIBRATION_REPLICAS = 12
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * CALIBRATION_REPLICAS


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StoppingBoundaryCalibrationThresholds(FrozenModel):
    minimum_api_transport_rate: float = Field(default=0.98, ge=0, le=1)
    minimum_bounded_json_rate: float = Field(default=0.95, ge=0, le=1)
    minimum_observation_replay_rate: float = Field(default=0.98, ge=0, le=1)
    minimum_authority_integrity_rate: float = Field(default=0.98, ge=0, le=1)
    maximum_runtime_pathology_rate: float = Field(default=0.02, ge=0, le=1)
    minimum_trigger_rate: float = Field(default=0.95, ge=0, le=1)
    minimum_source_coverage_resolution_rate: float = Field(default=0.50, ge=0, le=1)
    minimum_conflict_resolution_rate: float = Field(default=0.10, ge=0, le=1)
    maximum_locator_precondition_failure_count: int = Field(default=0, ge=0)
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    minimum_repair_target_boundary_count: int = Field(default=1, ge=1, le=2)

    @model_validator(mode="after")
    def validate_thresholds(self) -> StoppingBoundaryCalibrationThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("stopping boundary interval is empty")
        return self


class FinanceStoppingBoundaryCalibrationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_34_stopping_boundary_calibration"] = (
        "finance_v25_34_stopping_boundary_calibration"
    )
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
        min_length=EXPECTED_TASK_COUNT,
        max_length=EXPECTED_TASK_COUNT,
    )
    task_submechanism_ids: dict[str, str]
    task_parent_mechanism_ids: dict[str, str]
    task_expected_host_events: dict[str, tuple[str, str]]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=EXPECTED_TASK_COUNT,
        max_length=EXPECTED_TASK_COUNT,
    )
    replicas: Literal[12] = 12
    requested_rollout_count: Literal[60] = 60
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    thresholds: StoppingBoundaryCalibrationThresholds = Field(
        default_factory=StoppingBoundaryCalibrationThresholds
    )
    primary_response_variable: Literal["capability_contract_success"] = (
        "capability_contract_success"
    )
    historical_result_reclassification_authorized: Literal[False] = False
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["stopping_boundary_calibration"] = (
        "stopping_boundary_calibration"
    )
    schema_version: str = STOPPING_BOUNDARY_CALIBRATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStoppingBoundaryCalibrationContract:
        if self.stage != RuntimeResolutionStage.RESIDUAL_DEVELOPMENT:
            raise ValueError("stopping calibration must remain Development-only")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("stopping calibration is Flash-only")
        if self.requested_rollout_count != len(self.bindings) * self.replicas:
            raise ValueError("stopping calibration denominator is inconsistent")
        if any(item.tier != DifficultyTier.EASY_CONTROL for item in self.tasks):
            raise ValueError("stopping calibration must use frozen Easy-control tasks")
        task_ids = {item.artifact_id for item in self.tasks}
        if set(self.task_submechanism_ids) != task_ids:
            raise ValueError("stopping submechanism map is incomplete")
        if set(self.task_parent_mechanism_ids) != task_ids:
            raise ValueError("stopping parent map is incomplete")
        if set(self.task_expected_host_events) != task_ids:
            raise ValueError("stopping host-event map is incomplete")
        if set(self.task_submechanism_ids.values()) != set(STOPPING_SUBMECHANISM_IDS):
            raise ValueError("stopping calibration does not cover all five mechanisms")
        if set(self.task_parent_mechanism_ids.values()) != {STOPPING_PARENT_ID}:
            raise ValueError("stopping calibration includes another parent mechanism")
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("stopping tasks and Runtime bindings differ")
        if any(
            item.runtime_arm != CapabilityRuntimeArm.AUTONOMOUS_AGENT
            for item in self.bindings
        ):
            raise ValueError("stopping calibration requires Autonomous Agent Runtime")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("stopping rollout identity coverage is incomplete")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_boundary_calibration_implementation:",
        ):
            raise ValueError("stopping implementation identity is invalid")
        if self.contract_id != stopping_boundary_calibration_contract_id(self):
            raise ValueError("stopping calibration contract identity is invalid")
        return self


class BernoulliInterval(FrozenModel):
    lower: float = Field(ge=0, le=1)
    upper: float = Field(ge=0, le=1)


class StoppingTaskCalibrationRow(FrozenModel):
    task_artifact_id: str = Field(min_length=1)
    submechanism_id: str = Field(min_length=1)
    rollout_count: Literal[12] = 12
    runtime_eligible_count: int = Field(ge=0, le=CALIBRATION_REPLICAS)
    trigger_rate: float = Field(ge=0, le=1)
    resolution_rate: float = Field(ge=0, le=1)
    ordered_behavior_rate: float = Field(ge=0, le=1)
    semantic_answer_rate: float = Field(ge=0, le=1)
    capability_contract_success_rate: float = Field(ge=0, le=1)
    capability_contract_interval_95: BernoulliInterval
    boundary_task: bool


class StoppingCalibrationGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    category: Literal["runtime", "instrument", "boundary"]
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool


class FinanceStoppingBoundaryCalibrationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_34_stopping_boundary_calibration"] = (
        "finance_v25_34_stopping_boundary_calibration"
    )
    requested_rollout_count: Literal[60] = 60
    recorded_rollout_count: int = Field(ge=0)
    runtime_eligible_rollout_count: int = Field(ge=0)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    runtime_pathology_rate: float = Field(ge=0, le=1)
    semantic_accuracy_given_runtime_eligible: float = Field(ge=0, le=1)
    end_to_end_valid_success_rate: float = Field(ge=0, le=1)
    locator_precondition_failure_count: int = Field(ge=0)
    task_rows: tuple[StoppingTaskCalibrationRow, ...] = Field(
        min_length=EXPECTED_TASK_COUNT,
        max_length=EXPECTED_TASK_COUNT,
    )
    repair_target_boundary_count: int = Field(ge=0, le=2)
    gates: tuple[StoppingCalibrationGate, ...] = Field(min_length=10)
    runtime_measurement_ready: bool
    stopping_instrument_repair_validated: bool
    boundary_signal_observed: bool
    fresh_stable_support_development_permitted: bool
    failure_codes: tuple[str, ...]
    outcome_set_hash: str = Field(min_length=1)
    behavior_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    discovered_models: tuple[str, ...]
    historical_result_reclassified: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "fresh_stable_support_development_population_build",
        "stopping_instrument_redesign_only",
        "runtime_measurement_repair_only",
    ]
    schema_version: str = STOPPING_BOUNDARY_CALIBRATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStoppingBoundaryCalibrationReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("stopping calibration lacks its complete denominator")
        runtime_gates = tuple(item for item in self.gates if item.category == "runtime")
        instrument_gates = tuple(item for item in self.gates if item.category == "instrument")
        boundary_gates = tuple(item for item in self.gates if item.category == "boundary")
        runtime_ready = bool(runtime_gates) and all(item.passed for item in runtime_gates)
        repair_ready = (
            runtime_ready
            and bool(instrument_gates)
            and all(item.passed for item in instrument_gates)
        )
        boundary_ready = (
            repair_ready
            and bool(boundary_gates)
            and all(item.passed for item in boundary_gates)
        )
        if self.runtime_measurement_ready != runtime_ready:
            raise ValueError("stopping Runtime decision is inconsistent")
        if self.stopping_instrument_repair_validated != repair_ready:
            raise ValueError("stopping instrument decision is inconsistent")
        if self.boundary_signal_observed != boundary_ready:
            raise ValueError("stopping boundary decision is inconsistent")
        if self.fresh_stable_support_development_permitted != boundary_ready:
            raise ValueError("stopping fresh-support permission is inconsistent")
        expected_stage = (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "fresh_stable_support_development_population_build"
                if boundary_ready
                else "stopping_instrument_redesign_only"
            )
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("stopping calibration transition is not fail-closed")
        if self.report_id != stopping_boundary_calibration_report_id(self):
            raise ValueError("stopping calibration report identity is invalid")
        return self


def stopping_boundary_calibration_contract_id(
    value: FinanceStoppingBoundaryCalibrationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_stopping_boundary_calibration_contract:",
    )


def stopping_boundary_calibration_report_id(
    value: FinanceStoppingBoundaryCalibrationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_stopping_boundary_calibration_report:",
    )


def prepare_stopping_boundary_calibration(
    *,
    source_population_path: Path,
    source_v25_20_contract_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStoppingBoundaryCalibrationContract:
    if output_path.exists():
        raise ValueError("stopping calibration contract is immutable")
    population_path = source_population_path.resolve()
    source_contract_path = source_v25_20_contract_path.resolve()
    population = CapabilitySubmechanismPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    source = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        source_contract_path.read_text(encoding="utf-8")
    )
    if not population.static_audit.ready:
        raise ValueError("stopping calibration lacks a passing fresh population")
    direction_path = Path(population.source_direction_report_path).resolve()
    direction = CapabilitySubmechanismDirectionReport.model_validate_json(
        direction_path.read_text(encoding="utf-8")
    )
    task_rows = {
        item.submechanism_id: item
        for item in population.tasks
        if item.parent_mechanism_id == STOPPING_PARENT_ID
    }
    if set(task_rows) != set(STOPPING_SUBMECHANISM_IDS):
        raise ValueError("fresh population does not contain all stopping mechanisms")
    tasks = tuple(task_rows[item].artifact for item in STOPPING_SUBMECHANISM_IDS)
    model_contracts = tuple(
        item for item in source.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("source contract does not freeze exactly one Flash model")
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            source.protocol_profile,
        )
        for task in tasks
    )
    task_ids = {item.artifact_id for item in tasks}
    selected_rows = {
        item.artifact.artifact_id: item
        for item in task_rows.values()
        if item.artifact.artifact_id in task_ids
    }
    submechanisms = {
        task_id: item.submechanism_id for task_id, item in selected_rows.items()
    }
    parents = {
        task_id: item.parent_mechanism_id for task_id, item in selected_rows.items()
    }
    events = {
        task_id: item.scenario.expected_host_events
        for task_id, item in selected_rows.items()
    }
    tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "population_id": population.population_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
            },
            prefix="finance_stopping_boundary_calibration_rollout:",
        )
        for binding in bindings
        for replicate in range(CALIBRATION_REPLICAS)
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
            prefix="finance_stopping_boundary_calibration_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": source.protocol_profile,
        "tasks": tasks,
        "task_submechanism_ids": submechanisms,
        "task_parent_mechanism_ids": parents,
        "task_expected_host_events": events,
        "bindings": bindings,
        "maximum_model_tokens_per_rollout": source.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": source.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": source.maximum_public_context_bytes,
        "model_contract_repair_attempts": source.model_contract_repair_attempts,
        "rollout_identity_tokens": tokens,
    }
    provisional = FinanceStoppingBoundaryCalibrationContract.model_construct(
        contract_id="pending", **values
    )
    contract = FinanceStoppingBoundaryCalibrationContract(
        contract_id=stopping_boundary_calibration_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_stopping_boundary_calibration(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceStoppingBoundaryCalibrationReport:
    contract = FinanceStoppingBoundaryCalibrationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_inputs(contract)
    prefix = "stopping_boundary_calibration"
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
    behaviors = make_submechanism_behavior_observations(
        cast(Any, contract), records, outcomes, terminals
    )
    terminal_path = output_dir / f"{prefix}_terminal_outcomes.jsonl"
    behavior_path = output_dir / f"{prefix}_behavior_observations.jsonl"
    _write_jsonl_atomic(terminal_path, (item.model_dump(mode="json") for item in terminals))
    _write_jsonl_atomic(behavior_path, (item.model_dump(mode="json") for item in behaviors))
    report = make_stopping_boundary_calibration_report(
        contract, records, outcomes, terminals, behaviors, discovered
    )
    report_path = output_dir / "finance_stopping_boundary_calibration_report.json"
    markdown_path = output_dir / "finance_stopping_boundary_calibration_report.md"
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_text_atomic(markdown_path, _render_report(report))
    manifest_values = {
        "contract_id": contract.contract_id,
        "report_id": report.report_id,
        "experiment_label": contract.experiment_label,
        "runner_version": STOPPING_BOUNDARY_CALIBRATION_RUNNER_VERSION,
        "requested_model": contract.model_contracts[0].requested_model,
        "discovered_models": discovered,
        "records_sha256": _sha256(records_path),
        "outcomes_sha256": _sha256(outcomes_path),
        "terminal_outcomes_sha256": _sha256(terminal_path),
        "behavior_observations_sha256": _sha256(behavior_path),
        "report_sha256": _sha256(report_path),
        "historical_result_reclassified": False,
        "pro_api_call_count": 0,
        "beneficiary_screening_authorized": False,
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
    }
    provisional_manifest = {
        "manifest_id": "pending",
        **manifest_values,
        "schema_version": STOPPING_BOUNDARY_CALIBRATION_MANIFEST_VERSION,
    }
    manifest_id = canonical_hash(
        {key: value for key, value in provisional_manifest.items() if key != "manifest_id"},
        prefix="finance_stopping_boundary_calibration_manifest:",
    )
    _write_json_atomic(
        output_dir / "finance_stopping_boundary_calibration_manifest.json",
        {**provisional_manifest, "manifest_id": manifest_id},
    )
    return report


def make_stopping_boundary_calibration_report(
    contract: FinanceStoppingBoundaryCalibrationContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[SubmechanismBehaviorObservation],
    discovered_models: tuple[str, ...],
) -> FinanceStoppingBoundaryCalibrationReport:
    if not (
        len(records)
        == len(outcomes)
        == len(terminals)
        == len(behaviors)
        == contract.requested_rollout_count
    ):
        raise ValueError("stopping calibration has an incomplete rollout denominator")
    grouped: dict[str, list[SubmechanismBehaviorObservation]] = defaultdict(list)
    terminal_by_key = {(item.binding_id, item.replicate): item for item in terminals}
    for item in behaviors:
        grouped[item.task_artifact_id].append(item)
    rows = []
    for task in contract.tasks:
        task_behaviors = grouped[task.artifact_id]
        if len(task_behaviors) != contract.replicas:
            raise ValueError("stopping task has an incomplete realization denominator")
        submechanism_id = contract.task_submechanism_ids[task.artifact_id]
        successes = sum(item.capability_contract_success for item in task_behaviors)
        probability = successes / len(task_behaviors)
        semantic = tuple(
            terminal_by_key[(item.binding_id, item.replicate)].semantic_answer_correct
            for item in task_behaviors
        )
        rows.append(
            StoppingTaskCalibrationRow(
                task_artifact_id=task.artifact_id,
                submechanism_id=submechanism_id,
                runtime_eligible_count=sum(
                    item.runtime_eligible for item in task_behaviors
                ),
                trigger_rate=_rate(item.trigger_observed for item in task_behaviors),
                resolution_rate=_rate(
                    item.resolution_observed for item in task_behaviors
                ),
                ordered_behavior_rate=_rate(
                    item.behavior_success for item in task_behaviors
                ),
                semantic_answer_rate=_rate(semantic),
                capability_contract_success_rate=probability,
                capability_contract_interval_95=_wilson(
                    successes, len(task_behaviors)
                ),
                boundary_task=(
                    contract.thresholds.boundary_probability_lower
                    <= probability
                    <= contract.thresholds.boundary_probability_upper
                ),
            )
        )
    rows = sorted(rows, key=lambda item: item.submechanism_id)
    row_by_mechanism = {item.submechanism_id: item for item in rows}
    repair_boundary_count = sum(
        row_by_mechanism[item].boundary_task
        for item in (SOURCE_COVERAGE_ID, UNRESOLVED_CONFLICT_ID)
    )
    locator_failures = _locator_precondition_failure_count(records)
    thresholds = contract.thresholds
    runtime_values = (
        (
            "api_transport_resolution_rate",
            _rate(item.api_transport_resolved for item in terminals),
            thresholds.minimum_api_transport_rate,
            ">=",
        ),
        (
            "bounded_json_resolution_rate",
            _rate(item.bounded_json_resolution_success for item in terminals),
            thresholds.minimum_bounded_json_rate,
            ">=",
        ),
        (
            "observation_replay_rate",
            _rate(item.observation_replay_success for item in terminals),
            thresholds.minimum_observation_replay_rate,
            ">=",
        ),
        (
            "authority_integrity_rate",
            _rate(item.authority_integrity_success for item in terminals),
            thresholds.minimum_authority_integrity_rate,
            ">=",
        ),
        (
            "runtime_pathology_rate",
            _rate(item.runtime_pathology for item in terminals),
            thresholds.maximum_runtime_pathology_rate,
            "<=",
        ),
    )
    gates = [
        StoppingCalibrationGate(
            gate_id=gate_id,
            category="runtime",
            observed=observed,
            requirement=f"{operator}{required}",
            passed=(observed >= required if operator == ">=" else observed <= required),
        )
        for gate_id, observed, required, operator in runtime_values
    ]
    source_row = row_by_mechanism[SOURCE_COVERAGE_ID]
    conflict_row = row_by_mechanism[UNRESOLVED_CONFLICT_ID]
    instrument_values = (
        (
            "source_coverage_trigger_rate",
            source_row.trigger_rate,
            thresholds.minimum_trigger_rate,
            ">=",
        ),
        (
            "source_coverage_resolution_rate",
            source_row.resolution_rate,
            thresholds.minimum_source_coverage_resolution_rate,
            ">=",
        ),
        (
            "unresolved_conflict_trigger_rate",
            conflict_row.trigger_rate,
            thresholds.minimum_trigger_rate,
            ">=",
        ),
        (
            "unresolved_conflict_resolution_rate",
            conflict_row.resolution_rate,
            thresholds.minimum_conflict_resolution_rate,
            ">=",
        ),
        (
            "locator_precondition_failure_count",
            float(locator_failures),
            float(thresholds.maximum_locator_precondition_failure_count),
            "<=",
        ),
    )
    gates.extend(
        StoppingCalibrationGate(
            gate_id=gate_id,
            category="instrument",
            observed=observed,
            requirement=f"{operator}{required}",
            passed=(observed >= required if operator == ">=" else observed <= required),
        )
        for gate_id, observed, required, operator in instrument_values
    )
    gates.append(
        StoppingCalibrationGate(
            gate_id="repair_target_boundary_count",
            category="boundary",
            observed=float(repair_boundary_count),
            requirement=f">={thresholds.minimum_repair_target_boundary_count}",
            passed=repair_boundary_count >= thresholds.minimum_repair_target_boundary_count,
        )
    )
    runtime_ready = all(item.passed for item in gates if item.category == "runtime")
    repair_ready = runtime_ready and all(
        item.passed for item in gates if item.category == "instrument"
    )
    boundary_ready = repair_ready and all(
        item.passed for item in gates if item.category == "boundary"
    )
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    report_values = {
        "contract_id": contract.contract_id,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(terminals),
        "runtime_eligible_rollout_count": len(eligible),
        "api_transport_resolution_rate": _rate(
            item.api_transport_resolved for item in terminals
        ),
        "bounded_json_resolution_rate": _rate(
            item.bounded_json_resolution_success for item in terminals
        ),
        "observation_replay_rate": _rate(
            item.observation_replay_success for item in terminals
        ),
        "authority_integrity_rate": _rate(
            item.authority_integrity_success for item in terminals
        ),
        "runtime_pathology_rate": _rate(item.runtime_pathology for item in terminals),
        "semantic_accuracy_given_runtime_eligible": (
            _rate(item.semantic_answer_correct for item in eligible) if eligible else 0.0
        ),
        "end_to_end_valid_success_rate": _rate(item.valid_success for item in terminals),
        "locator_precondition_failure_count": locator_failures,
        "task_rows": tuple(rows),
        "repair_target_boundary_count": repair_boundary_count,
        "gates": tuple(gates),
        "runtime_measurement_ready": runtime_ready,
        "stopping_instrument_repair_validated": repair_ready,
        "boundary_signal_observed": boundary_ready,
        "fresh_stable_support_development_permitted": boundary_ready,
        "failure_codes": tuple(item.gate_id for item in gates if not item.passed),
        "outcome_set_hash": canonical_hash(
            tuple(item.model_dump(mode="json") for item in outcomes),
            prefix="finance_stopping_boundary_calibration_outcomes:",
        ),
        "behavior_set_hash": canonical_hash(
            tuple(item.model_dump(mode="json") for item in behaviors),
            prefix="finance_stopping_boundary_calibration_behaviors:",
        ),
        "api_call_count": sum(item.api_call_count for item in terminals),
        "total_model_tokens": sum(item.total_model_tokens for item in terminals),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in terminals),
        "discovered_models": discovered_models,
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "fresh_stable_support_development_population_build"
                if boundary_ready
                else "stopping_instrument_redesign_only"
            )
        ),
    }
    provisional = FinanceStoppingBoundaryCalibrationReport.model_construct(
        report_id="pending", **report_values
    )
    return FinanceStoppingBoundaryCalibrationReport(
        report_id=stopping_boundary_calibration_report_id(provisional), **report_values
    )


def _locator_precondition_failure_count(
    records: Sequence[CapabilityBoundaryRolloutRecord],
) -> int:
    return sum(
        observation.error_code == "locator_not_discovered"
        for record in records
        for observation in _all_observations(record)
    )


def _wilson(successes: int, total: int) -> BernoulliInterval:
    if total <= 0:
        raise ValueError("Wilson interval requires a positive denominator")
    z = 1.959963984540054
    probability = successes / total
    denominator = 1 + z * z / total
    center = (probability + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(
        probability * (1 - probability) / total + z * z / (4 * total * total)
    ) / denominator
    return BernoulliInterval(lower=max(0.0, center - radius), upper=min(1.0, center + radius))


def _verify_inputs(contract: FinanceStoppingBoundaryCalibrationContract) -> None:
    pairs = (
        (contract.source_population_path, contract.source_population_sha256),
        (contract.source_direction_report_path, contract.source_direction_report_sha256),
        (contract.source_v25_20_contract_path, contract.source_v25_20_contract_sha256),
        (contract.finance_archive_config_path, contract.finance_archive_config_sha256),
    )
    for path_value, expected_hash in pairs:
        if _sha256(Path(path_value)) != expected_hash:
            raise ValueError(f"stopping calibration frozen input changed:{path_value}")
    population = CapabilitySubmechanismPopulation.model_validate_json(
        Path(contract.source_population_path).read_text(encoding="utf-8")
    )
    if population.population_id != contract.source_population_id:
        raise ValueError("stopping calibration loaded another population")
    implementation = _implementation_manifest()
    if implementation != contract.implementation_manifest:
        raise ValueError("stopping calibration implementation changed after freeze")
    if contract.implementation_manifest_hash != canonical_hash(
        implementation,
        prefix="finance_stopping_boundary_calibration_implementation:",
    ):
        raise ValueError("stopping implementation manifest hash is invalid")


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    values = _base_implementation_manifest()
    path = Path(__file__).resolve()
    return {**values, str(path.relative_to(root)): _sha256(path)}


def _render_report(report: FinanceStoppingBoundaryCalibrationReport) -> str:
    lines = [
        "# Finance v25.34 Stopping Boundary Calibration Report",
        "",
        "## Decision",
        "",
        f"- Report ID: `{report.report_id}`",
        f"- Runtime measurement ready: `{report.runtime_measurement_ready}`",
        f"- Stopping instrument repair validated: `{report.stopping_instrument_repair_validated}`",
        f"- Boundary signal observed: `{report.boundary_signal_observed}`",
        (
            "- Fresh stable-support Development permitted: "
            f"`{report.fresh_stable_support_development_permitted}`"
        ),
        f"- Next permitted stage: `{report.next_permitted_stage}`",
        f"- Failure codes: `{list(report.failure_codes)}`",
        "",
        "This diagnostic run neither reclassifies v25.33 nor authorizes Pro, Beneficiary, "
        "Exact Target, GP-C, or production Contribution.",
        "",
        "## Denominator And Runtime",
        "",
        f"- Rollouts: `{report.recorded_rollout_count}/{report.requested_rollout_count}`",
        f"- Runtime eligible: `{report.runtime_eligible_rollout_count}`",
        f"- API transport rate: `{report.api_transport_resolution_rate:.6f}`",
        f"- Bounded JSON rate: `{report.bounded_json_resolution_rate:.6f}`",
        f"- Observation replay rate: `{report.observation_replay_rate:.6f}`",
        f"- Authority integrity rate: `{report.authority_integrity_rate:.6f}`",
        f"- Runtime pathology rate: `{report.runtime_pathology_rate:.6f}`",
        f"- Locator precondition failures: `{report.locator_precondition_failure_count}`",
        "",
        "## Stopping Mechanisms",
        "",
        (
            "| Submechanism | Trigger | Resolution | Ordered | Semantic | Contract | "
            "95% CI | Boundary |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report.task_rows:
        interval = row.capability_contract_interval_95
        lines.append(
            f"| `{row.submechanism_id}` | {row.trigger_rate:.3f} | "
            f"{row.resolution_rate:.3f} | {row.ordered_behavior_rate:.3f} | "
            f"{row.semantic_answer_rate:.3f} | "
            f"{row.capability_contract_success_rate:.3f} | "
            f"[{interval.lower:.3f}, {interval.upper:.3f}] | {row.boundary_task} |"
        )
    lines.extend(
        [
            "",
            "## Gates",
            "",
            "| Gate | Category | Observed | Requirement | Passed |",
            "|---|---|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| `{gate.gate_id}` | {gate.category} | {gate.observed:.6f} | "
        f"`{gate.requirement}` | {gate.passed} |"
        for gate in report.gates
    )
    lines.extend(
        [
            "",
            "## Cost",
            "",
            f"- API calls: `{report.api_call_count}`",
            f"- Model tokens: `{report.total_model_tokens}`",
            f"- Estimated cost: `${report.estimated_cost_usd:.6f}`",
            "",
        ]
    )
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_jsonl_atomic(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")
    temporary.replace(path)


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Finance v25.34 stopping calibration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-population", type=Path, required=True)
    prepare.add_argument("--source-v25-20-contract", type=Path, required=True)
    prepare.add_argument("--output-path", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--workers", type=int, default=24)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "prepare":
        contract = prepare_stopping_boundary_calibration(
            source_population_path=args.source_population,
            source_v25_20_contract_path=args.source_v25_20_contract,
            output_path=args.output_path,
            run_id=args.run_id,
        )
        print(json.dumps({"contract_id": contract.contract_id}, indent=2))
        return 0
    report = run_stopping_boundary_calibration(
        contract_path=args.contract,
        output_dir=args.output_dir,
        workers=args.workers,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
