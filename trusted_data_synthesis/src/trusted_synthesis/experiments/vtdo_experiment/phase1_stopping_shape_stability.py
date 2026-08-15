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
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (  # noqa: E501
    EXPECTED_ROLLOUT_COUNT,
    EXPECTED_TASK_COUNT,
    REPLICAS,
    SHAPE_COUNT,
    SHAPE_TASKS,
    STRUCTURAL_STRATA,
    FinanceStoppingShapePopulation,
    FinanceStoppingShapeStabilityProtocol,
    FrozenArtifactReference,
    StoppingShapeDifficultyVector,
    StoppingShapeTask,
    StoppingShapeThresholds,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

STOPPING_SHAPE_CONTRACT_VERSION = "finance_stopping_shape_stability_contract.v1"
STOPPING_SHAPE_RESULT_VERSION = "finance_stopping_shape_result.v1"
STOPPING_SHAPE_POLICY_VERSION = "finance_stopping_difficulty_policy.v1"
STOPPING_SHAPE_REPORT_VERSION = "finance_stopping_shape_stability_report.v1"
STOPPING_SHAPE_MANIFEST_VERSION = "finance_stopping_shape_stability_manifest.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceStoppingShapeStabilityContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_36_stopping_shape_stability_development"] = (
        "finance_v25_36_stopping_shape_stability_development"
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
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_records: tuple[StoppingShapeTask, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_shape_ids: dict[str, str]
    task_shape_roles: dict[str, Literal["boundary_candidate", "runtime_control"]]
    task_stratum_ids: dict[str, str]
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
    requested_rollout_count: Literal[192] = 192
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    thresholds: StoppingShapeThresholds
    primary_response_variable: Literal["capability_contract_success"] = (
        "capability_contract_success"
    )
    task_instance_is_primary_sampling_unit: Literal[True] = True
    pooled_result_may_rescue_shape_failure: Literal[False] = False
    posthoc_task_selection_authorized: Literal[False] = False
    historical_results_reclassified: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_stopping_shape_development"] = (
        "flash_stopping_shape_development"
    )
    schema_version: str = STOPPING_SHAPE_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStoppingShapeStabilityContract:
        if self.stage != RuntimeResolutionStage.RESIDUAL_DEVELOPMENT:
            raise ValueError("Stopping shape contract must remain Development-only")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("Stopping shape Development must remain Flash-only")
        if self.requested_rollout_count != len(self.bindings) * self.replicas:
            raise ValueError("Stopping shape rollout denominator is inconsistent")
        task_ids = {item.artifact_id for item in self.tasks}
        record_ids = {item.artifact.artifact_id for item in self.task_records}
        if task_ids != record_ids:
            raise ValueError("Stopping shape task and record identities differ")
        maps: tuple[Mapping[str, Any], ...] = (
            self.task_shape_ids,
            self.task_shape_roles,
            self.task_stratum_ids,
            self.task_submechanism_ids,
            self.task_parent_mechanism_ids,
            self.task_instance_ids,
            self.task_expected_host_events,
            self.task_raw_capability_demands,
            self.task_difficulty_vectors,
        )
        if any(set(item) != task_ids for item in maps):
            raise ValueError("Stopping shape task maps are incomplete")
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("Stopping shape Runtime bindings are incomplete")
        if any(
            item.runtime_arm != CapabilityRuntimeArm.AUTONOMOUS_AGENT
            for item in self.bindings
        ):
            raise ValueError("Stopping shape Development requires Autonomous Agent Runtime")
        if len(set(self.task_shape_ids.values())) != SHAPE_COUNT:
            raise ValueError("Stopping shape contract has incomplete Shape coverage")
        if any(
            set(value) != set(CAPABILITY_AXES)
            for value in self.task_raw_capability_demands.values()
        ):
            raise ValueError("Stopping shape capability demand omits an axis")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("Stopping shape rollout identities are incomplete")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_shape_stability_implementation:",
        ):
            raise ValueError("Stopping shape execution implementation identity is invalid")
        if self.contract_id != stopping_shape_contract_id(self):
            raise ValueError("Stopping shape contract identity is invalid")
        return self


class StoppingShapeTaskResponse(FrozenModel):
    task_artifact_id: str = Field(min_length=1)
    stratum_id: str = Field(min_length=1)
    realizations: tuple[int, ...] = Field(min_length=REPLICAS, max_length=REPLICAS)
    probability: float = Field(ge=0, le=1)
    fisher_information: float = Field(ge=0, le=0.25)

    @model_validator(mode="after")
    def validate_response(self) -> StoppingShapeTaskResponse:
        if any(item not in {0, 1} for item in self.realizations):
            raise ValueError("Stopping shape realizations must be binary")
        observed = sum(self.realizations) / len(self.realizations)
        if not math.isclose(self.probability, observed, abs_tol=1e-12):
            raise ValueError("Stopping shape task probability is inconsistent")
        expected_information = observed * (1.0 - observed)
        if not math.isclose(self.fisher_information, expected_information, abs_tol=1e-12):
            raise ValueError("Stopping shape task information is inconsistent")
        return self


class StoppingShapeResult(FrozenModel):
    shape_id: str = Field(min_length=1)
    shape_role: Literal["boundary_candidate", "runtime_control"]
    task_count: Literal[4] = 4
    rollout_count: Literal[32] = 32
    task_responses: tuple[StoppingShapeTaskResponse, ...] = Field(
        min_length=SHAPE_TASKS, max_length=SHAPE_TASKS
    )
    mean_success_rate: float = Field(ge=0, le=1)
    minimum_task_probability: float = Field(ge=0, le=1)
    maximum_task_probability: float = Field(ge=0, le=1)
    between_task_probability_range: float = Field(ge=0, le=1)
    boundary_task_count: int = Field(ge=0, le=SHAPE_TASKS)
    nonzero_information_task_count: int = Field(ge=0, le=SHAPE_TASKS)
    total_fisher_information: float = Field(ge=0)
    effective_task_count: float = Field(ge=0, le=SHAPE_TASKS)
    maximum_single_task_information_share: float = Field(ge=0, le=1)
    bootstrap_information_interval95: tuple[float, float]
    bootstrap_information_lcb: float = Field(ge=0)
    gate_results: dict[str, bool]
    admitted: bool
    failure_codes: tuple[str, ...]
    schema_version: str = STOPPING_SHAPE_RESULT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> StoppingShapeResult:
        if set(item.stratum_id for item in self.task_responses) != {
            item[0] for item in STRUCTURAL_STRATA
        }:
            raise ValueError("Stopping shape response lacks a structural stratum")
        if self.admitted != all(self.gate_results.values()):
            raise ValueError("Stopping shape admission is inconsistent")
        if self.failure_codes != tuple(
            sorted(key for key, passed in self.gate_results.items() if not passed)
        ):
            raise ValueError("Stopping shape failure codes are inconsistent")
        return self


class FrozenStoppingDifficultyPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    shape_task_quotas: dict[str, Literal[4]]
    structural_strata: tuple[tuple[str, str, Any], ...]
    thresholds: StoppingShapeThresholds
    primary_sampling_unit: Literal["independent_finance_task"] = (
        "independent_finance_task"
    )
    per_population_evaluation_required: Literal[True] = True
    pooled_rescue_forbidden: Literal[True] = True
    fresh_population_disjointness_dimensions: tuple[str, ...] = (
        "task_artifact_id",
        "evidence_id",
        "evidence_version_id",
        "source_semantic_signature",
        "materializer_hash",
    )
    schema_version: str = STOPPING_SHAPE_POLICY_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> FrozenStoppingDifficultyPolicy:
        if set(self.shape_task_quotas.values()) != {SHAPE_TASKS}:
            raise ValueError("Stopping difficulty policy changed Shape quota")
        if self.policy_id != stopping_difficulty_policy_id(self):
            raise ValueError("Stopping difficulty policy identity is invalid")
        return self


class FinanceStoppingShapeStabilityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    requested_rollout_count: Literal[192] = 192
    recorded_rollout_count: int = Field(ge=0, le=EXPECTED_ROLLOUT_COUNT)
    execution_integrity_rate: float = Field(ge=0, le=1)
    terminal_resolution_rate: float = Field(ge=0, le=1)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    runtime_pathology_rate: float = Field(ge=0, le=1)
    l0_l2_failure_count: int = Field(ge=0)
    behavior_success_rate: float = Field(ge=0, le=1)
    primary_valid_success_rate: float = Field(ge=0, le=1)
    capability_contract_success_rate: float = Field(ge=0, le=1)
    runtime_measurement_ready: bool
    shape_results: tuple[StoppingShapeResult, ...] = Field(
        min_length=SHAPE_COUNT, max_length=SHAPE_COUNT
    )
    all_shapes_admitted: bool
    difficulty_policy: FrozenStoppingDifficultyPolicy | None
    difficulty_policy_frozen: bool
    pooled_result_used_for_admission: Literal[False] = False
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    discovered_models: tuple[str, ...]
    failure_codes: tuple[str, ...]
    posthoc_finalizer_fix_applied: Literal[False] = False
    fresh_cross_population_preparation_authorized: bool
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "fresh_stable_support_population_preparation",
        "runtime_measurement_repair_only",
        "stopping_shape_support_redesign_only",
    ]
    schema_version: str = STOPPING_SHAPE_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStoppingShapeStabilityReport:
        shape_ready = all(item.admitted for item in self.shape_results)
        if self.all_shapes_admitted != shape_ready:
            raise ValueError("Stopping Shape aggregate admission is inconsistent")
        admitted = self.runtime_measurement_ready and shape_ready
        if self.difficulty_policy_frozen != admitted:
            raise ValueError("Stopping difficulty policy decision is inconsistent")
        if (self.difficulty_policy is not None) != admitted:
            raise ValueError("Stopping difficulty policy presence is inconsistent")
        if self.fresh_cross_population_preparation_authorized != admitted:
            raise ValueError("Stopping Shape next-population authorization is inconsistent")
        expected_stage = (
            "runtime_measurement_repair_only"
            if not self.runtime_measurement_ready
            else (
                "fresh_stable_support_population_preparation"
                if shape_ready
                else "stopping_shape_support_redesign_only"
            )
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Stopping Shape transition is not fail-closed")
        if self.report_id != stopping_shape_report_id(self):
            raise ValueError("Stopping Shape report identity is invalid")
        return self


def stopping_shape_contract_id(value: FinanceStoppingShapeStabilityContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_stopping_shape_stability_contract:",
    )


def stopping_difficulty_policy_id(value: FrozenStoppingDifficultyPolicy) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"policy_id"}),
        prefix="finance_stopping_difficulty_policy:",
    )


def stopping_shape_report_id(value: FinanceStoppingShapeStabilityReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_stopping_shape_stability_report:",
    )


def prepare_stopping_shape_contract(
    *,
    protocol_path: Path,
    population_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStoppingShapeStabilityContract:
    if output_path.exists():
        raise ValueError("Stopping shape contract is immutable")
    protocol_path = protocol_path.resolve()
    population_path = population_path.resolve()
    protocol = FinanceStoppingShapeStabilityProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    population = FinanceStoppingShapePopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    _verify_population(protocol, population, population_path)
    if not population.static_audit.ready:
        raise ValueError("Stopping shape population did not pass static gates")
    calibration_path = Path(protocol.source_calibration_contract.path).resolve()
    calibration = FinanceStoppingBoundaryCalibrationContract.model_validate_json(
        calibration_path.read_text(encoding="utf-8")
    )
    model_contracts = tuple(
        item for item in calibration.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("Stopping shape contract lacks exactly one Flash model")
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
                "semantic_signature": item.source_semantic_signature,
                "materializer_hash": item.materializer_hash,
            },
            prefix="finance_stopping_shape_task_instance:",
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
            prefix="finance_stopping_shape_rollout:",
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
        "source_calibration_contract": _reference(
            calibration_path, calibration.contract_id
        ),
        "finance_archive_config_path": str(finance_config),
        "finance_archive_config_sha256": _sha256(finance_config),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stopping_shape_stability_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": calibration.protocol_profile,
        "tasks": tasks,
        "task_records": population.tasks,
        "task_shape_ids": {
            task_id: item.shape_id for task_id, item in record_by_task.items()
        },
        "task_shape_roles": {
            task_id: item.shape_role for task_id, item in record_by_task.items()
        },
        "task_stratum_ids": {
            task_id: item.stratum_id for task_id, item in record_by_task.items()
        },
        "task_submechanism_ids": {
            task_id: item.scenario.submechanism_id
            for task_id, item in record_by_task.items()
        },
        "task_parent_mechanism_ids": {
            task_id: item.scenario.parent_mechanism_id
            for task_id, item in record_by_task.items()
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
    provisional = FinanceStoppingShapeStabilityContract.model_construct(
        contract_id="pending", **values
    )
    contract = FinanceStoppingShapeStabilityContract(
        contract_id=stopping_shape_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, contract.model_dump(mode="json"))
    return contract


def run_stopping_shape_stability(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceStoppingShapeStabilityReport:
    contract = FinanceStoppingShapeStabilityContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_contract_inputs(contract)
    prefix = "stopping_shape_stability_development"
    outcomes, discovered = _execute_stage(
        contract=contract,
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
    _write_jsonl(terminal_path, (item.model_dump(mode="json") for item in terminals))
    _write_jsonl(behavior_path, (item.model_dump(mode="json") for item in behaviors))
    report = make_stopping_shape_report(
        contract,
        records,
        outcomes,
        terminals,
        behaviors,
        discovered_models=discovered,
    )
    report_path = output_dir / "finance_stopping_shape_stability_report.json"
    _write_json(report_path, report.model_dump(mode="json"))
    (output_dir / "finance_stopping_shape_stability_report.md").write_text(
        _render_report(report), encoding="utf-8"
    )
    manifest = {
        "schema_version": STOPPING_SHAPE_MANIFEST_VERSION,
        "contract_id": contract.contract_id,
        "report_id": report.report_id,
        "requested_model": contract.model_contracts[0].requested_model,
        "discovered_models": discovered,
        "records_sha256": _sha256(records_path),
        "outcomes_sha256": _sha256(outcomes_path),
        "terminal_outcomes_sha256": _sha256(terminal_path),
        "behavior_observations_sha256": _sha256(behavior_path),
        "report_sha256": _sha256(report_path),
        "difficulty_policy_frozen": report.difficulty_policy_frozen,
        "pooled_result_used_for_admission": False,
        "pro_api_call_count": 0,
        "beneficiary_screening_authorized": False,
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    _write_json(
        output_dir / "finance_stopping_shape_stability_manifest.json", manifest
    )
    return report


def make_stopping_shape_report(
    contract: FinanceStoppingShapeStabilityContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[SubmechanismBehaviorObservation],
    *,
    discovered_models: Sequence[str],
) -> FinanceStoppingShapeStabilityReport:
    if not (
        len(records)
        == len(outcomes)
        == len(terminals)
        == len(behaviors)
        == contract.requested_rollout_count
    ):
        raise ValueError("Stopping shape report has an incomplete denominator")
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
    grouped: dict[str, list[SubmechanismBehaviorObservation]] = defaultdict(list)
    for item in behaviors:
        grouped[contract.task_shape_ids[item.task_artifact_id]].append(item)
    shape_results = tuple(
        _make_shape_result(
            contract,
            shape_id,
            tuple(grouped[shape_id]),
        )
        for shape_id in sorted(set(contract.task_shape_ids.values()))
    )
    all_shapes = all(item.admitted for item in shape_results)
    admitted = runtime_ready and all_shapes
    policy = _make_difficulty_policy(contract) if admitted else None
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
        + [
            f"shape:{item.shape_id}:{code}"
            for item in shape_results
            for code in item.failure_codes
        ]
    )
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
        "behavior_success_rate": _rate(item.behavior_success for item in behaviors),
        "primary_valid_success_rate": _rate(
            item.primary_valid_success for item in behaviors
        ),
        "capability_contract_success_rate": _rate(
            item.capability_contract_success for item in behaviors
        ),
        "runtime_measurement_ready": runtime_ready,
        "shape_results": shape_results,
        "all_shapes_admitted": all_shapes,
        "difficulty_policy": policy,
        "difficulty_policy_frozen": admitted,
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "discovered_models": tuple(discovered_models),
        "failure_codes": failure_codes,
        "fresh_cross_population_preparation_authorized": admitted,
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "fresh_stable_support_population_preparation"
                if all_shapes
                else "stopping_shape_support_redesign_only"
            )
        ),
    }
    provisional = FinanceStoppingShapeStabilityReport.model_construct(
        report_id="pending", **values
    )
    return FinanceStoppingShapeStabilityReport(
        report_id=stopping_shape_report_id(provisional), **values
    )


def _make_shape_result(
    contract: FinanceStoppingShapeStabilityContract,
    shape_id: str,
    behaviors: Sequence[SubmechanismBehaviorObservation],
) -> StoppingShapeResult:
    by_task: dict[str, list[SubmechanismBehaviorObservation]] = defaultdict(list)
    for item in behaviors:
        by_task[item.task_artifact_id].append(item)
    if len(by_task) != SHAPE_TASKS or any(
        len(items) != REPLICAS for items in by_task.values()
    ):
        raise ValueError(f"Stopping Shape denominator is incomplete: {shape_id}")
    responses: list[StoppingShapeTaskResponse] = []
    for task_id, items in sorted(by_task.items()):
        realizations = tuple(
            int(item.capability_contract_success)
            for item in sorted(items, key=lambda row: row.replicate)
        )
        probability = sum(realizations) / len(realizations)
        responses.append(
            StoppingShapeTaskResponse(
                task_artifact_id=task_id,
                stratum_id=contract.task_stratum_ids[task_id],
                realizations=realizations,
                probability=probability,
                fisher_information=probability * (1.0 - probability),
            )
        )
    frozen = tuple(responses)
    probabilities = tuple(item.probability for item in frozen)
    information = tuple(item.fisher_information for item in frozen)
    total = sum(information)
    shares = tuple(value / total if total else 0.0 for value in information)
    effective = 1.0 / sum(value * value for value in shares) if total else 0.0
    interval = _shape_information_bootstrap(
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
    nonzero = sum(value > 0 for value in information)
    role = next(
        contract.task_shape_roles[task_id]
        for task_id in by_task
    )
    probability_range = max(probabilities) - min(probabilities)
    common = {
        "complete_task_denominator": len(frozen) == SHAPE_TASKS,
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
    return StoppingShapeResult(
        shape_id=shape_id,
        shape_role=role,
        task_responses=frozen,
        mean_success_rate=fmean(probabilities),
        minimum_task_probability=min(probabilities),
        maximum_task_probability=max(probabilities),
        between_task_probability_range=probability_range,
        boundary_task_count=boundary_count,
        nonzero_information_task_count=nonzero,
        total_fisher_information=total,
        effective_task_count=effective,
        maximum_single_task_information_share=max(shares, default=0.0),
        bootstrap_information_interval95=interval,
        bootstrap_information_lcb=interval[0],
        gate_results=gates,
        admitted=not failures,
        failure_codes=failures,
    )


def _shape_information_bootstrap(
    responses: Sequence[StoppingShapeTaskResponse],
    thresholds: StoppingShapeThresholds,
    *,
    shape_id: str,
) -> tuple[float, float]:
    seed = int(
        canonical_hash(
            {"seed": thresholds.bootstrap_seed, "shape_id": shape_id},
            prefix="finance_stopping_shape_bootstrap_seed:",
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
                rng.choice(source.realizations) for _ in range(len(source.realizations))
            ]
            probability = sum(realizations) / len(realizations)
            total += probability * (1.0 - probability)
        totals.append(total)
    return _interval95(totals)


def _make_difficulty_policy(
    contract: FinanceStoppingShapeStabilityContract,
) -> FrozenStoppingDifficultyPolicy:
    values = {
        "source_contract_id": contract.contract_id,
        "shape_task_quotas": {
            shape_id: SHAPE_TASKS for shape_id in sorted(set(contract.task_shape_ids.values()))
        },
        "structural_strata": STRUCTURAL_STRATA,
        "thresholds": contract.thresholds,
    }
    provisional = FrozenStoppingDifficultyPolicy.model_construct(
        policy_id="pending", **values
    )
    return FrozenStoppingDifficultyPolicy(
        policy_id=stopping_difficulty_policy_id(provisional), **values
    )


def _verify_population(
    protocol: FinanceStoppingShapeStabilityProtocol,
    population: FinanceStoppingShapePopulation,
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


def _verify_contract_inputs(contract: FinanceStoppingShapeStabilityContract) -> None:
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
    if canonical_hash(
        current,
        prefix="finance_stopping_shape_stability_implementation:",
    ) != contract.implementation_manifest_hash:
        raise ValueError("Stopping shape implementation manifest hash changed")


def _reference(path: Path, artifact_id: str) -> FrozenArtifactReference:
    return FrozenArtifactReference(path=str(path), sha256=_sha256(path), artifact_id=artifact_id)


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary_runner.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_confirmation.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_stability_protocol.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_stability.py",
    )
    return {item: _sha256(root / item) for item in paths}


def _interval95(values: Sequence[float]) -> tuple[float, float]:
    ordered = sorted(values)
    if not ordered:
        return (0.0, 0.0)
    lower = ordered[max(0, int(0.025 * len(ordered)) - 1)]
    upper = ordered[min(len(ordered) - 1, int(math.ceil(0.975 * len(ordered))) - 1)]
    return (lower, upper)


def _render_report(report: FinanceStoppingShapeStabilityReport) -> str:
    lines = [
        "# Finance v25.36 Stopping Shape Stability Development",
        "",
        "## Decision",
        "",
        f"- Runtime measurement ready: `{str(report.runtime_measurement_ready).lower()}`",
        f"- All Shapes admitted: `{str(report.all_shapes_admitted).lower()}`",
        f"- Difficulty policy frozen: `{str(report.difficulty_policy_frozen).lower()}`",
        f"- Next stage: `{report.next_permitted_stage}`",
        "",
        "## Shape Results",
        "",
        "| Shape | Role | Mean | Range | Boundary tasks | Nonzero tasks | "
        "Effective tasks | Max share | Bootstrap LCB | Admitted |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.shape_results:
        lines.append(
            f"| `{item.shape_id}` | `{item.shape_role}` | {item.mean_success_rate:.4f} | "
            f"{item.between_task_probability_range:.4f} | {item.boundary_task_count} | "
            f"{item.nonzero_information_task_count} | {item.effective_task_count:.3f} | "
            f"{item.maximum_single_task_information_share:.3f} | "
            f"{item.bootstrap_information_lcb:.6f} | "
            f"{'yes' if item.admitted else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Accounting",
            "",
            f"- Rollouts: `{report.recorded_rollout_count}/{report.requested_rollout_count}`",
            f"- API calls: `{report.api_call_count}`",
            f"- Model tokens: `{report.total_model_tokens}`",
            f"- Estimated cost: `${report.estimated_cost_usd:.6f}`",
            "- Pro calls: `0`",
            "- Exact Target / GP-C / Contribution: `not evaluated`",
            "",
        ]
    )
    if report.failure_codes:
        lines.extend(
            ["## Failures", "", *(f"- `{item}`" for item in report.failure_codes), ""]
        )
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
    parser = argparse.ArgumentParser(description="Run v25.36 Stopping Shape Development")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--protocol", required=True, type=Path)
    prepare.add_argument("--population", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=24)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        contract = prepare_stopping_shape_contract(
            protocol_path=args.protocol,
            population_path=args.population,
            output_path=args.output,
            run_id=args.run_id,
        )
        print(contract.model_dump_json(indent=2))
    else:
        report = run_stopping_shape_stability(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
