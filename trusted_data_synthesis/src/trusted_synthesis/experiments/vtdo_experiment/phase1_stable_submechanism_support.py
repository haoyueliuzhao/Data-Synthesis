from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_decision_stable_protocol import (  # noqa: E501
    FinanceCapabilityDecisionStableProtocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    _normalize_demand,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (  # noqa: E501
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismDirectionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    SubmechanismBehaviorObservation,
    _make_terminals,
    make_submechanism_behavior_observations,
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    RuntimeResolutionStage,
    RuntimeTerminalOutcome,
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_geometry import (  # noqa: E501
    StableBootstrapSummary,
    StableIdentifiableSubspacePolicy,
    StableSubspaceAlignment,
    StableSubspaceEstimate,
    StableTaskResponse,
    bootstrap_stable_subspace,
    compare_stable_subspaces,
    estimate_stable_subspace,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

STABLE_SUPPORT_CONTRACT_VERSION = "finance_stable_support_contract.v2"
STABLE_SUPPORT_GATE_VERSION = "finance_stable_support_gate.v2"
STABLE_SUPPORT_REPORT_VERSION = "finance_stable_support_report.v2"
STABLE_SUPPORT_MANIFEST_VERSION = "finance_stable_support_manifest.v2"

StableSupportStage = Literal["development", "confirmation"]
EXPECTED_POPULATION_COUNT = 3
EXPECTED_SUBMECHANISM_COUNT = 20
EXPECTED_TASK_COUNT = 60
EXPECTED_REPLICAS = 8
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * EXPECTED_REPLICAS
EXPECTED_PARENT_COUNT = 4
EXPECTED_TASKS_PER_PARENT = EXPECTED_TASK_COUNT // EXPECTED_PARENT_COUNT


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StablePopulationReference(FrozenModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    population_id: str = Field(min_length=1)


class StableDevelopmentManifestReference(FrozenModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    manifest_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)


class StableDevelopmentReference(FrozenModel):
    contract_path: str = Field(min_length=1)
    contract_sha256: str = Field(min_length=64, max_length=64)
    contract_id: str = Field(min_length=1)
    report_path: str = Field(min_length=1)
    report_sha256: str = Field(min_length=64, max_length=64)
    report_id: str = Field(min_length=1)
    behavior_path: str = Field(min_length=1)
    behavior_sha256: str = Field(min_length=64, max_length=64)
    manifest: StableDevelopmentManifestReference


class FinanceStableSupportContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_33_capability_decision_stable_support"] = (
        "finance_v25_33_capability_decision_stable_support"
    )
    stage: StableSupportStage
    source_protocol_path: str = Field(min_length=1)
    source_protocol_sha256: str = Field(min_length=64, max_length=64)
    source_protocol_id: str = Field(min_length=1)
    source_model_contract_path: str = Field(min_length=1)
    source_model_contract_sha256: str = Field(min_length=64, max_length=64)
    source_model_contract_id: str = Field(min_length=1)
    source_direction_report_path: str = Field(min_length=1)
    source_direction_report_sha256: str = Field(min_length=64, max_length=64)
    source_direction_report_id: str = Field(min_length=1)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    population_references: tuple[StablePopulationReference, ...] = Field(
        min_length=EXPECTED_POPULATION_COUNT,
        max_length=EXPECTED_POPULATION_COUNT,
    )
    development_reference: StableDevelopmentReference | None = None
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
    task_scenario_ids: dict[str, str]
    task_expected_host_events: dict[str, tuple[str, str]]
    task_raw_capability_demands: dict[str, dict[str, float]]
    task_instance_ids: dict[str, str]
    task_population_ids: dict[str, str]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=EXPECTED_TASK_COUNT,
        max_length=EXPECTED_TASK_COUNT,
    )
    replicas: Literal[8] = 8
    requested_rollout_count: Literal[480] = 480
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    stable_subspace_policy: StableIdentifiableSubspacePolicy
    primary_response_variable: Literal["capability_contract_success"] = (
        "capability_contract_success"
    )
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "stable_support_development",
        "stable_support_confirmation",
    ]
    schema_version: str = STABLE_SUPPORT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStableSupportContract:
        expected_next = (
            "stable_support_development"
            if self.stage == "development"
            else "stable_support_confirmation"
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("stable-support contract transition is inconsistent")
        if self.primary_response_variable != "capability_contract_success":
            raise ValueError("stable-support primary response changed")
        if (self.stage == "confirmation") != (self.development_reference is not None):
            raise ValueError("stable-support Development lineage is inconsistent")
        task_ids = {item.artifact_id for item in self.tasks}
        if len(task_ids) != EXPECTED_TASK_COUNT:
            raise ValueError("stable-support task identities are duplicated")
        maps = (
            self.task_submechanism_ids,
            self.task_parent_mechanism_ids,
            self.task_scenario_ids,
            self.task_expected_host_events,
            self.task_raw_capability_demands,
            self.task_instance_ids,
            self.task_population_ids,
        )
        if any(set(item) != task_ids for item in maps):
            raise ValueError("stable-support task maps are incomplete")
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("stable-support bindings differ from tasks")
        if len({item.binding_id for item in self.bindings}) != EXPECTED_TASK_COUNT:
            raise ValueError("stable-support binding identities are duplicated")
        submechanism_counts = Counter(self.task_submechanism_ids.values())
        if len(submechanism_counts) != EXPECTED_SUBMECHANISM_COUNT or set(
            submechanism_counts.values()
        ) != {EXPECTED_POPULATION_COUNT}:
            raise ValueError("stable-support lacks three task instances per submechanism")
        parent_counts = Counter(self.task_parent_mechanism_ids.values())
        if len(parent_counts) != EXPECTED_PARENT_COUNT or set(parent_counts.values()) != {
            EXPECTED_TASKS_PER_PARENT
        }:
            raise ValueError("stable-support parent task support is imbalanced")
        if len(set(self.task_instance_ids.values())) != EXPECTED_TASK_COUNT:
            raise ValueError("stable-support task instances are duplicated")
        population_ids = {item.population_id for item in self.population_references}
        if len(population_ids) != EXPECTED_POPULATION_COUNT:
            raise ValueError("stable-support population identities are duplicated")
        if set(self.task_population_ids.values()) != population_ids:
            raise ValueError("stable-support task population map is incomplete")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("stable-support rollout identities are incomplete")
        if len(self.model_contracts) != 1 or self.model_contracts[0].arm != ExplorerArm.FLASH:
            raise ValueError("stable-support stages must remain Flash-only")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stable_support_implementation:",
        ):
            raise ValueError("stable-support implementation manifest is invalid")
        if self.contract_id != stable_support_contract_id(self):
            raise ValueError("stable-support contract identity is invalid")
        return self


class StableSupportGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    category: Literal["runtime", "coverage", "stable_geometry", "parent_support", "alignment"]
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool
    schema_version: str = STABLE_SUPPORT_GATE_VERSION


class FinanceStableSupportReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: StableSupportStage
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
    capability_contract_success_rate: float = Field(ge=0, le=1)
    primary_response_variable: Literal["capability_contract_success"]
    stable_estimate: StableSubspaceEstimate
    bootstrap_summary: StableBootstrapSummary
    alignment_summary: StableSubspaceAlignment | None
    gates: tuple[StableSupportGate, ...] = Field(min_length=18)
    runtime_measurement_ready: bool
    capability_support_admitted: bool
    failure_codes: tuple[str, ...]
    outcome_set_hash: str = Field(min_length=1)
    behavior_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    fresh_confirmation_authorized: bool
    pro_sparse_anchor_authorized: bool
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "fresh_stable_support_confirmation_preparation",
        "pro_sparse_anchor_preparation",
        "stable_support_redesign_only",
        "runtime_measurement_repair_only",
    ]
    schema_version: str = STABLE_SUPPORT_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStableSupportReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("stable-support report lacks its complete denominator")
        runtime_gates = tuple(item for item in self.gates if item.category == "runtime")
        support_gates = tuple(item for item in self.gates if item.category != "runtime")
        runtime_ready = bool(runtime_gates) and all(item.passed for item in runtime_gates)
        admitted = (
            runtime_ready and bool(support_gates) and all(item.passed for item in support_gates)
        )
        if self.runtime_measurement_ready != runtime_ready:
            raise ValueError("stable-support Runtime readiness is inconsistent")
        if self.capability_support_admitted != admitted:
            raise ValueError("stable-support admission decision is inconsistent")
        expected_confirmation = self.stage == "development" and admitted
        expected_pro = self.stage == "confirmation" and admitted
        if self.fresh_confirmation_authorized != expected_confirmation:
            raise ValueError("stable-support Confirmation authorization is inconsistent")
        if self.pro_sparse_anchor_authorized != expected_pro:
            raise ValueError("stable-support Pro authorization is inconsistent")
        expected_next = (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "stable_support_redesign_only"
                if not admitted
                else (
                    "fresh_stable_support_confirmation_preparation"
                    if self.stage == "development"
                    else "pro_sparse_anchor_preparation"
                )
            )
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("stable-support report transition is not fail-closed")
        if (self.stage == "confirmation") != (self.alignment_summary is not None):
            raise ValueError("stable-support alignment stage is inconsistent")
        if self.report_id != stable_support_report_id(self):
            raise ValueError("stable-support report identity is invalid")
        return self


def stable_support_contract_id(value: FinanceStableSupportContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_stable_support_contract:",
    )


def stable_support_report_id(value: FinanceStableSupportReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_stable_support_report:",
    )


def prepare_stable_support_contract(
    *,
    stage: StableSupportStage,
    protocol_path: Path,
    source_model_contract_path: Path,
    population_paths: tuple[Path, ...],
    output_path: Path,
    run_id: str,
    development_contract_path: Path | None = None,
    development_report_path: Path | None = None,
    development_behavior_path: Path | None = None,
    development_manifest_path: Path | None = None,
) -> FinanceStableSupportContract:
    if output_path.exists():
        raise ValueError("stable-support contract is immutable")
    if len(population_paths) != EXPECTED_POPULATION_COUNT:
        raise ValueError("stable-support requires exactly three populations")
    protocol_path = protocol_path.resolve()
    source_model_contract_path = source_model_contract_path.resolve()
    protocol = FinanceCapabilityDecisionStableProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    source = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        source_model_contract_path.read_text(encoding="utf-8")
    )
    populations = tuple(
        CapabilitySubmechanismPopulation.model_validate_json(
            path.resolve().read_text(encoding="utf-8")
        )
        for path in population_paths
    )
    _validate_populations(populations)
    direction_path = Path(populations[0].source_direction_report_path).resolve()
    direction = CapabilitySubmechanismDirectionReport.model_validate_json(
        direction_path.read_text(encoding="utf-8")
    )
    if any(item.source_direction_report_id != direction.report_id for item in populations):
        raise ValueError("stable-support populations changed the direction design")
    development_reference = _make_development_reference(
        stage=stage,
        contract_path=development_contract_path,
        report_path=development_report_path,
        behavior_path=development_behavior_path,
        manifest_path=development_manifest_path,
        confirmation_populations=populations,
    )
    selected_specs = {
        item.submechanism_id: item
        for item in direction.candidate_specs
        if item.submechanism_id in set(direction.selected_submechanism_ids)
    }
    task_records = tuple(item for population in populations for item in population.tasks)
    tasks = tuple(item.artifact for item in task_records)
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            source.protocol_profile,
        )
        for task in tasks
    )
    population_by_task = {
        item.artifact.artifact_id: population.population_id
        for population in populations
        for item in population.tasks
    }
    record_by_task = {item.artifact.artifact_id: item for item in task_records}
    task_submechanisms = {task_id: item.submechanism_id for task_id, item in record_by_task.items()}
    task_parents = {task_id: item.parent_mechanism_id for task_id, item in record_by_task.items()}
    task_scenarios = {
        task_id: item.scenario.scenario_id for task_id, item in record_by_task.items()
    }
    task_events = {
        task_id: item.scenario.expected_host_events for task_id, item in record_by_task.items()
    }
    task_demands = {
        task_id: selected_specs[item.submechanism_id].raw_capability_demand
        for task_id, item in record_by_task.items()
    }
    task_instances = {
        task_id: canonical_hash(
            {
                "task_record_id": item.task_record_id,
                "semantic_signature": item.source_semantic_signature,
                "materializer_hash": item.materializer_hash,
            },
            prefix="finance_stable_support_task_instance:",
        )
        for task_id, item in record_by_task.items()
    }
    tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "stage": stage,
                "binding_id": binding.binding_id,
                "replicate": replicate,
                "task_instance_id": task_instances[binding.task_artifact_id],
            },
            prefix="finance_stable_support_rollout:",
        )
        for binding in bindings
        for replicate in range(EXPECTED_REPLICAS)
    }
    model_contracts = tuple(
        item for item in source.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("stable-support source does not freeze exactly one Flash model")
    finance_config = Path(source.finance_archive_config_path).resolve()
    implementation = _implementation_manifest()
    references = tuple(
        StablePopulationReference(
            path=str(path.resolve()),
            sha256=_sha256(path.resolve()),
            population_id=population.population_id,
        )
        for path, population in zip(population_paths, populations, strict=True)
    )
    values = {
        "run_id": run_id,
        "stage": stage,
        "source_protocol_path": str(protocol_path),
        "source_protocol_sha256": _sha256(protocol_path),
        "source_protocol_id": protocol.protocol_id,
        "source_model_contract_path": str(source_model_contract_path),
        "source_model_contract_sha256": _sha256(source_model_contract_path),
        "source_model_contract_id": source.contract_id,
        "source_direction_report_path": str(direction_path),
        "source_direction_report_sha256": _sha256(direction_path),
        "source_direction_report_id": direction.report_id,
        "finance_archive_config_path": str(finance_config),
        "finance_archive_config_sha256": _sha256(finance_config),
        "population_references": references,
        "development_reference": development_reference,
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stable_support_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": source.protocol_profile,
        "tasks": tasks,
        "task_submechanism_ids": task_submechanisms,
        "task_parent_mechanism_ids": task_parents,
        "task_scenario_ids": task_scenarios,
        "task_expected_host_events": task_events,
        "task_raw_capability_demands": task_demands,
        "task_instance_ids": task_instances,
        "task_population_ids": population_by_task,
        "bindings": bindings,
        "maximum_model_tokens_per_rollout": source.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": source.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": source.maximum_public_context_bytes,
        "model_contract_repair_attempts": source.model_contract_repair_attempts,
        "rollout_identity_tokens": tokens,
        "stable_subspace_policy": protocol.stable_subspace_policy,
        "primary_response_variable": protocol.primary_response_variable,
        "next_permitted_stage": (
            "stable_support_development"
            if stage == "development"
            else "stable_support_confirmation"
        ),
    }
    provisional = FinanceStableSupportContract.model_construct(contract_id="pending", **values)
    contract = FinanceStableSupportContract(
        contract_id=stable_support_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_stable_support(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceStableSupportReport:
    contract = FinanceStableSupportContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_inputs(contract)
    prefix = f"stable_support_{contract.stage}"
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
    terminal_contract = contract.model_copy(
        update={"stage": _runtime_resolution_stage(contract.stage)}
    )
    terminals = _make_terminals(cast(Any, terminal_contract), records, outcomes)
    behaviors = make_submechanism_behavior_observations(
        cast(Any, contract),
        records,
        outcomes,
        terminals,
    )
    terminal_path = output_dir / f"{prefix}_terminal_outcomes.jsonl"
    behavior_path = output_dir / f"{prefix}_behavior_observations.jsonl"
    _write_jsonl_atomic(
        terminal_path,
        (item.model_dump(mode="json") for item in terminals),
    )
    _write_jsonl_atomic(
        behavior_path,
        (item.model_dump(mode="json") for item in behaviors),
    )
    report = make_stable_support_report(contract, outcomes, terminals, behaviors)
    report_path = output_dir / "finance_stable_support_report.json"
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_stable_support_report.md",
        _render_report(report),
    )
    manifest = {
        "schema_version": STABLE_SUPPORT_MANIFEST_VERSION,
        "contract_id": contract.contract_id,
        "report_id": report.report_id,
        "stage": contract.stage,
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
        "production_contribution": 0.0,
    }
    _write_json_atomic(output_dir / "finance_stable_support_manifest.json", manifest)
    return report


def make_stable_support_report(
    contract: FinanceStableSupportContract,
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[SubmechanismBehaviorObservation],
) -> FinanceStableSupportReport:
    if not (len(outcomes) == len(terminals) == len(behaviors) == contract.requested_rollout_count):
        raise ValueError("stable-support report has an incomplete denominator")
    rows, complete_task_ids = _stable_rows(contract, behaviors)
    estimate = estimate_stable_subspace(rows, contract.stable_subspace_policy)
    bootstrap = bootstrap_stable_subspace(rows, contract.stable_subspace_policy)
    alignment = _make_alignment(contract, rows)
    gates = _make_gates(
        contract,
        terminals,
        estimate,
        bootstrap,
        alignment,
        len(complete_task_ids),
    )
    runtime_ready = all(item.passed for item in gates if item.category == "runtime")
    admitted = runtime_ready and all(item.passed for item in gates if item.category != "runtime")
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    values = {
        "contract_id": contract.contract_id,
        "stage": contract.stage,
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
        "capability_contract_success_rate": _rate(
            item.capability_contract_success for item in behaviors
        ),
        "primary_response_variable": contract.primary_response_variable,
        "stable_estimate": estimate,
        "bootstrap_summary": bootstrap,
        "alignment_summary": alignment,
        "gates": gates,
        "runtime_measurement_ready": runtime_ready,
        "capability_support_admitted": admitted,
        "failure_codes": tuple(item.gate_id for item in gates if not item.passed),
        "outcome_set_hash": canonical_hash(
            tuple(item.terminal_outcome_id for item in terminals),
            prefix="finance_stable_support_terminal_set:",
        ),
        "behavior_set_hash": canonical_hash(
            tuple(item.observation_id for item in behaviors),
            prefix="finance_stable_support_behavior_set:",
        ),
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "fresh_confirmation_authorized": contract.stage == "development" and admitted,
        "pro_sparse_anchor_authorized": contract.stage == "confirmation" and admitted,
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "stable_support_redesign_only"
                if not admitted
                else (
                    "fresh_stable_support_confirmation_preparation"
                    if contract.stage == "development"
                    else "pro_sparse_anchor_preparation"
                )
            )
        ),
    }
    provisional = FinanceStableSupportReport.model_construct(report_id="pending", **values)
    return FinanceStableSupportReport(
        report_id=stable_support_report_id(provisional),
        **values,
    )


def _stable_rows(
    contract: FinanceStableSupportContract,
    behaviors: Sequence[SubmechanismBehaviorObservation],
) -> tuple[tuple[StableTaskResponse, ...], set[str]]:
    binding_by_task = {item.task_artifact_id: item for item in contract.bindings}
    grouped: dict[str, list[SubmechanismBehaviorObservation]] = defaultdict(list)
    for item in behaviors:
        grouped[item.task_artifact_id].append(item)
    complete = {
        task_id
        for task_id, values in grouped.items()
        if len(values) == contract.replicas and all(item.runtime_eligible for item in values)
    }
    rows = tuple(
        StableTaskResponse(
            task_id=task_id,
            submechanism_id=contract.task_submechanism_ids[task_id],
            parent_mechanism_id=contract.task_parent_mechanism_ids[task_id],
            task_instance_id=contract.task_instance_ids[task_id],
            general_difficulty=binding_by_task[task_id].general_difficulty,
            demand=_normalize_demand(contract.task_raw_capability_demands[task_id]),
            realizations=tuple(
                int(item.capability_contract_success)
                for item in sorted(grouped[task_id], key=lambda value: value.replicate)
            ),
        )
        for task_id in sorted(complete)
    )
    return rows, complete


def _make_alignment(
    contract: FinanceStableSupportContract,
    rows: Sequence[StableTaskResponse],
) -> StableSubspaceAlignment | None:
    reference = contract.development_reference
    if reference is None:
        return None
    development_contract = FinanceStableSupportContract.model_validate_json(
        Path(reference.contract_path).read_text(encoding="utf-8")
    )
    development_behaviors = tuple(
        SubmechanismBehaviorObservation.model_validate_json(line)
        for line in Path(reference.behavior_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    development_rows, complete = _stable_rows(development_contract, development_behaviors)
    if len(complete) != EXPECTED_TASK_COUNT:
        raise ValueError("stable-support Development behavior denominator is incomplete")
    return compare_stable_subspaces(
        development_rows,
        rows,
        contract.stable_subspace_policy,
    )


def _make_gates(
    contract: FinanceStableSupportContract,
    terminals: Sequence[RuntimeTerminalOutcome],
    estimate: StableSubspaceEstimate,
    bootstrap: StableBootstrapSummary,
    alignment: StableSubspaceAlignment | None,
    complete_task_count: int,
) -> tuple[StableSupportGate, ...]:
    policy = contract.stable_subspace_policy
    rows: list[tuple[str, str, bool, float, str]] = [
        (
            "complete_rollout_denominator",
            "runtime",
            len(terminals) == EXPECTED_ROLLOUT_COUNT,
            float(len(terminals)),
            f"={EXPECTED_ROLLOUT_COUNT}",
        ),
        (
            "api_transport_resolution_rate",
            "runtime",
            _rate(item.api_transport_resolved for item in terminals)
            >= policy.minimum_api_transport_rate,
            _rate(item.api_transport_resolved for item in terminals),
            f">={policy.minimum_api_transport_rate}",
        ),
        (
            "bounded_json_resolution_rate",
            "runtime",
            _rate(item.bounded_json_resolution_success for item in terminals)
            >= policy.minimum_bounded_json_rate,
            _rate(item.bounded_json_resolution_success for item in terminals),
            f">={policy.minimum_bounded_json_rate}",
        ),
        (
            "observation_replay_rate",
            "runtime",
            _rate(item.observation_replay_success for item in terminals)
            >= policy.minimum_observation_replay_rate,
            _rate(item.observation_replay_success for item in terminals),
            f">={policy.minimum_observation_replay_rate}",
        ),
        (
            "authority_integrity_rate",
            "runtime",
            _rate(item.authority_integrity_success for item in terminals)
            >= policy.minimum_authority_integrity_rate,
            _rate(item.authority_integrity_success for item in terminals),
            f">={policy.minimum_authority_integrity_rate}",
        ),
        (
            "runtime_pathology_rate",
            "runtime",
            _rate(item.runtime_pathology for item in terminals)
            <= policy.maximum_runtime_pathology_rate,
            _rate(item.runtime_pathology for item in terminals),
            f"<={policy.maximum_runtime_pathology_rate}",
        ),
        (
            "complete_runtime_eligible_task_denominator",
            "runtime",
            complete_task_count == EXPECTED_TASK_COUNT,
            float(complete_task_count),
            f"={EXPECTED_TASK_COUNT}",
        ),
        (
            "primary_geometry_task_denominator",
            "coverage",
            estimate.task_count == EXPECTED_TASK_COUNT,
            float(estimate.task_count),
            f"={EXPECTED_TASK_COUNT}",
        ),
        (
            "primary_geometry_rollout_denominator",
            "coverage",
            estimate.rollout_count == EXPECTED_ROLLOUT_COUNT,
            float(estimate.rollout_count),
            f"={EXPECTED_ROLLOUT_COUNT}",
        ),
        (
            "nonzero_weight_task_count",
            "stable_geometry",
            estimate.nonzero_weight_task_count >= policy.minimum_nonzero_weight_task_count,
            float(estimate.nonzero_weight_task_count),
            f">={policy.minimum_nonzero_weight_task_count}",
        ),
        (
            "boundary_task_fraction",
            "stable_geometry",
            estimate.boundary_task_fraction >= policy.minimum_boundary_task_fraction,
            estimate.boundary_task_fraction,
            f">={policy.minimum_boundary_task_fraction}",
        ),
        (
            "stable_identifiable_rank",
            "stable_geometry",
            estimate.identifiable_rank >= policy.required_rank,
            float(estimate.identifiable_rank),
            f">={policy.required_rank}",
        ),
        (
            "top4_effective_rank",
            "stable_geometry",
            estimate.claimed_effective_rank >= policy.minimum_effective_rank,
            estimate.claimed_effective_rank,
            f">={policy.minimum_effective_rank}",
        ),
        (
            "top4_condition_number",
            "stable_geometry",
            estimate.claimed_condition_number <= policy.maximum_condition_number,
            estimate.claimed_condition_number,
            f"<={policy.maximum_condition_number}",
        ),
        (
            "bootstrap_joint_geometry_pass_rate",
            "stable_geometry",
            bootstrap.joint_geometry_pass_rate >= policy.minimum_bootstrap_geometry_pass_rate,
            bootstrap.joint_geometry_pass_rate,
            f">={policy.minimum_bootstrap_geometry_pass_rate}",
        ),
        (
            "general_factor_fraction",
            "stable_geometry",
            estimate.general_factor_fraction <= policy.maximum_general_factor_fraction,
            estimate.general_factor_fraction,
            f"<={policy.maximum_general_factor_fraction}",
        ),
        (
            "informative_axis_count",
            "stable_geometry",
            estimate.informative_axis_count >= policy.minimum_informative_axis_count,
            float(estimate.informative_axis_count),
            f">={policy.minimum_informative_axis_count}",
        ),
        (
            "minimum_parent_information_share",
            "parent_support",
            estimate.minimum_parent_information_share >= policy.minimum_parent_information_share,
            estimate.minimum_parent_information_share,
            f">={policy.minimum_parent_information_share}",
        ),
        (
            "maximum_parent_information_share",
            "parent_support",
            estimate.maximum_parent_information_share <= policy.maximum_parent_information_share,
            estimate.maximum_parent_information_share,
            f"<={policy.maximum_parent_information_share}",
        ),
        (
            "minimum_parent_share_bootstrap_lcb",
            "parent_support",
            bootstrap.minimum_parent_share_lcb >= policy.minimum_parent_share_bootstrap_lcb,
            bootstrap.minimum_parent_share_lcb,
            f">={policy.minimum_parent_share_bootstrap_lcb}",
        ),
        (
            "minimum_nonzero_tasks_per_parent",
            "parent_support",
            min(estimate.nonzero_task_count_by_parent.values(), default=0)
            >= policy.minimum_nonzero_tasks_per_parent,
            float(min(estimate.nonzero_task_count_by_parent.values(), default=0)),
            f">={policy.minimum_nonzero_tasks_per_parent}",
        ),
    ]
    if contract.stage == "confirmation":
        if alignment is None:
            raise ValueError("stable-support Confirmation lacks alignment statistics")
        rows.extend(
            (
                (
                    "development_confirmation_maximum_principal_angle",
                    "alignment",
                    alignment.maximum_principal_angle_degrees
                    <= policy.maximum_principal_angle_degrees,
                    alignment.maximum_principal_angle_degrees,
                    f"<={policy.maximum_principal_angle_degrees}",
                ),
                (
                    "bootstrap_subspace_alignment_rate",
                    "alignment",
                    alignment.bootstrap_alignment_pass_rate
                    >= policy.minimum_bootstrap_alignment_rate,
                    alignment.bootstrap_alignment_pass_rate,
                    f">={policy.minimum_bootstrap_alignment_rate}",
                ),
            )
        )
    return tuple(
        StableSupportGate(
            gate_id=gate_id,
            category=cast(Any, category),
            passed=passed,
            observed=observed,
            requirement=requirement,
        )
        for gate_id, category, passed, observed, requirement in rows
    )


def _make_development_reference(
    *,
    stage: StableSupportStage,
    contract_path: Path | None,
    report_path: Path | None,
    behavior_path: Path | None,
    manifest_path: Path | None,
    confirmation_populations: Sequence[CapabilitySubmechanismPopulation],
) -> StableDevelopmentReference | None:
    values = (contract_path, report_path, behavior_path, manifest_path)
    if stage == "development":
        if any(item is not None for item in values):
            raise ValueError("stable-support Development cannot consume another Development")
        return None
    if any(item is None for item in values):
        raise ValueError("stable-support Confirmation lacks Development lineage")
    assert contract_path is not None
    assert report_path is not None
    assert behavior_path is not None
    assert manifest_path is not None
    contract_path = contract_path.resolve()
    report_path = report_path.resolve()
    behavior_path = behavior_path.resolve()
    manifest_path = manifest_path.resolve()
    development = FinanceStableSupportContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    report = FinanceStableSupportReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    if (
        development.stage != "development"
        or report.contract_id != development.contract_id
        or not report.capability_support_admitted
        or not report.fresh_confirmation_authorized
        or report.next_permitted_stage != "fresh_stable_support_confirmation_preparation"
    ):
        raise ValueError("stable-support Confirmation lacks Development authorization")
    manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_id, manifest_schema_version = _validate_development_manifest(
        manifest_raw,
        development=development,
        report=report,
        report_path=report_path,
        behavior_path=behavior_path,
    )
    development_populations = tuple(
        CapabilitySubmechanismPopulation.model_validate_json(
            Path(item.path).read_text(encoding="utf-8")
        )
        for item in development.population_references
    )
    for left in development_populations:
        for right in confirmation_populations:
            disjoint = _population_disjointness(left, right)
            if not all(disjoint.values()):
                raise ValueError(f"stable-support Confirmation overlaps Development:{disjoint}")
    return StableDevelopmentReference(
        contract_path=str(contract_path),
        contract_sha256=_sha256(contract_path),
        contract_id=development.contract_id,
        report_path=str(report_path),
        report_sha256=_sha256(report_path),
        report_id=report.report_id,
        behavior_path=str(behavior_path),
        behavior_sha256=_sha256(behavior_path),
        manifest=StableDevelopmentManifestReference(
            path=str(manifest_path),
            sha256=_sha256(manifest_path),
            manifest_id=manifest_id,
            schema_version=manifest_schema_version,
        ),
    )


def _validate_development_manifest(
    raw: Mapping[str, Any],
    *,
    development: FinanceStableSupportContract,
    report: FinanceStableSupportReport,
    report_path: Path,
    behavior_path: Path,
) -> tuple[str, str]:
    schema_version = str(raw.get("schema_version", ""))
    if schema_version == STABLE_SUPPORT_MANIFEST_VERSION:
        if (
            raw.get("contract_id") != development.contract_id
            or raw.get("report_id") != report.report_id
            or raw.get("report_sha256") != _sha256(report_path)
            or raw.get("behavior_observations_sha256") != _sha256(behavior_path)
        ):
            raise ValueError("stable-support Development manifest lineage is invalid")
        return (
            canonical_hash(raw, prefix="finance_stable_support_manifest_snapshot:"),
            schema_version,
        )
    if schema_version in {
        "finance_stable_runtime_repair_manifest.v1",
        "finance_stable_runtime_repair_manifest.v2",
    }:
        artifacts = raw.get("artifacts")
        if not isinstance(artifacts, Mapping):
            raise ValueError("stable-support Runtime-repair manifest lacks artifacts")
        report_artifact = artifacts.get("repaired_report")
        behavior_artifact = artifacts.get("merged_behavior_observations")
        if not isinstance(report_artifact, Mapping) or not isinstance(
            behavior_artifact, Mapping
        ):
            raise ValueError("stable-support Runtime-repair manifest is incomplete")
        if (
            raw.get("source_contract_id") != development.contract_id
            or raw.get("repaired_report_id") != report.report_id
            or report_artifact.get("sha256") != _sha256(report_path)
            or behavior_artifact.get("sha256") != _sha256(behavior_path)
            or raw.get("runtime_measurement_ready") is not True
            or raw.get("capability_support_admitted") is not True
            or raw.get("next_permitted_stage")
            != "fresh_stable_support_confirmation_preparation"
        ):
            raise ValueError("stable-support Runtime-repair authorization is invalid")
        manifest_id = raw.get("manifest_id")
        if not isinstance(manifest_id, str) or not manifest_id:
            raise ValueError("stable-support Runtime-repair manifest lacks identity")
        return manifest_id, schema_version
    raise ValueError("stable-support Development manifest version is unsupported")


def _validate_populations(
    populations: Sequence[CapabilitySubmechanismPopulation],
) -> None:
    if len(populations) != EXPECTED_POPULATION_COUNT:
        raise ValueError("stable-support requires three population instances")
    if any(not item.static_audit.ready for item in populations):
        raise ValueError("stable-support population is not statically ready")
    expected = {item.submechanism_id for item in populations[0].tasks}
    if len(expected) != EXPECTED_SUBMECHANISM_COUNT:
        raise ValueError("stable-support source population lacks 20 submechanisms")
    for population in populations[1:]:
        if {item.submechanism_id for item in population.tasks} != expected:
            raise ValueError("stable-support populations changed the submechanism set")
    for index, left in enumerate(populations):
        for right in populations[index + 1 :]:
            disjoint = _population_disjointness(left, right)
            if not all(disjoint.values()):
                raise ValueError(f"stable-support populations overlap:{disjoint}")


def _population_disjointness(
    left: CapabilitySubmechanismPopulation,
    right: CapabilitySubmechanismPopulation,
) -> dict[str, bool]:
    left_identity = _population_identity(left)
    right_identity = _population_identity(right)
    return {key: not bool(left_identity[key] & right_identity[key]) for key in left_identity}


def _population_identity(
    population: CapabilitySubmechanismPopulation,
) -> dict[str, set[str]]:
    return {
        "evidence": {
            evidence.evidence_id
            for item in population.tasks
            for evidence in item.artifact.public_corpus.evidence
        },
        "evidence_version": {
            evidence.evidence_version_id
            for item in population.tasks
            for evidence in item.artifact.public_corpus.evidence
        },
        "task": {item.artifact.task.task_id for item in population.tasks},
        "semantic_signature": {item.source_semantic_signature for item in population.tasks},
        "submechanism_signature_instance": {item.materializer_hash for item in population.tasks},
    }


def _verify_inputs(contract: FinanceStableSupportContract) -> None:
    paths = [
        (contract.source_protocol_path, contract.source_protocol_sha256),
        (contract.source_model_contract_path, contract.source_model_contract_sha256),
        (contract.source_direction_report_path, contract.source_direction_report_sha256),
        (contract.finance_archive_config_path, contract.finance_archive_config_sha256),
        *((item.path, item.sha256) for item in contract.population_references),
    ]
    if contract.development_reference is not None:
        reference = contract.development_reference
        paths.extend(
            (
                (reference.contract_path, reference.contract_sha256),
                (reference.report_path, reference.report_sha256),
                (reference.behavior_path, reference.behavior_sha256),
                (reference.manifest.path, reference.manifest.sha256),
            )
        )
    for path_value, expected in paths:
        if _sha256(Path(path_value)) != expected:
            raise ValueError(f"stable-support frozen input changed:{path_value}")
    if _implementation_manifest() != contract.implementation_manifest:
        raise ValueError("stable-support implementation changed after freeze")
    protocol = FinanceCapabilityDecisionStableProtocol.model_validate_json(
        Path(contract.source_protocol_path).read_text(encoding="utf-8")
    )
    source = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        Path(contract.source_model_contract_path).read_text(encoding="utf-8")
    )
    populations = tuple(
        CapabilitySubmechanismPopulation.model_validate_json(
            Path(item.path).read_text(encoding="utf-8")
        )
        for item in contract.population_references
    )
    if protocol.protocol_id != contract.source_protocol_id:
        raise ValueError("stable-support protocol lineage is invalid")
    if source.contract_id != contract.source_model_contract_id:
        raise ValueError("stable-support model-contract lineage is invalid")
    if tuple(item.population_id for item in populations) != tuple(
        item.population_id for item in contract.population_references
    ):
        raise ValueError("stable-support population lineage is invalid")
    _validate_populations(populations)
    if contract.stage == "confirmation":
        development_reference = contract.development_reference
        if development_reference is None:
            raise ValueError("stable-support Confirmation lacks Development reference")
        development = FinanceStableSupportContract.model_validate_json(
            Path(development_reference.contract_path).read_text(encoding="utf-8")
        )
        report = FinanceStableSupportReport.model_validate_json(
            Path(development_reference.report_path).read_text(encoding="utf-8")
        )
        if (
            development.contract_id != development_reference.contract_id
            or report.report_id != development_reference.report_id
            or report.contract_id != development.contract_id
            or not report.capability_support_admitted
            or not report.fresh_confirmation_authorized
        ):
            raise ValueError("stable-support Confirmation Development lineage is invalid")


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_stable_submechanism_geometry.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_stable_submechanism_protocol.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_decision_stable_protocol.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_submechanism_flash_development.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_submechanism_population.py"
        ),
        root / "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        root / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_confirmation.py",
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_multitier_runtime_resolution.py"
        ),
        root / "src/trusted_synthesis/runtime/agent/iterative.py",
        root / "src/trusted_synthesis/runtime/agent/client.py",
        root / "src/trusted_synthesis/runtime/agent/llm_agent.py",
        root / "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in paths}


def _runtime_resolution_stage(stage: StableSupportStage) -> RuntimeResolutionStage:
    return (
        RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
        if stage == "development"
        else RuntimeResolutionStage.HELDOUT_CONFIRMATION
    )


def _rate(values: Iterable[bool]) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: object) -> None:
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


def _render_report(report: FinanceStableSupportReport) -> str:
    estimate = report.stable_estimate
    bootstrap = report.bootstrap_summary
    alignment = report.alignment_summary
    alignment_rows = (
        (
            (
                "- Maximum Development–Confirmation principal angle: "
                f"**{alignment.maximum_principal_angle_degrees:.4f}°**"
            ),
            f"- Bootstrap alignment pass rate: **{alignment.bootstrap_alignment_pass_rate:.2%}**",
        )
        if alignment is not None
        else ("- Cross-stage alignment: **not evaluated during Development**",)
    )
    return "\n".join(
        (
            f"# Finance Stable Support {report.stage.title()}",
            "",
            "## Decision",
            "",
            f"- Report ID: `{report.report_id}`",
            (
                "- Complete denominator: "
                f"**{report.recorded_rollout_count}/{report.requested_rollout_count}**"
            ),
            f"- Runtime ready: **{report.runtime_measurement_ready}**",
            f"- Capability support admitted: **{report.capability_support_admitted}**",
            f"- Fresh Confirmation authorized: **{report.fresh_confirmation_authorized}**",
            f"- Pro sparse anchor authorized: **{report.pro_sparse_anchor_authorized}**",
            f"- Primary response: `{report.primary_response_variable}`",
            f"- Next permitted stage: `{report.next_permitted_stage}`",
            "",
            "## Stable Top-4 Geometry",
            "",
            f"- Identifiable rank: **{estimate.identifiable_rank}**",
            f"- Identification floor: **{estimate.identification_floor:.8f}**",
            f"- Top-4 effective rank: **{estimate.claimed_effective_rank:.4f}**",
            f"- Top-4 condition number: **{estimate.claimed_condition_number:.4f}**",
            f"- Bootstrap joint geometry pass: **{bootstrap.joint_geometry_pass_rate:.2%}**",
            (
                "- Parent share range: "
                f"**{estimate.minimum_parent_information_share:.2%}–"
                f"{estimate.maximum_parent_information_share:.2%}**"
            ),
            f"- Minimum parent-share bootstrap LCB: **{bootstrap.minimum_parent_share_lcb:.2%}**",
            *alignment_rows,
            "",
            (
                "v25.29 remains a frozen failure. This fresh stage changes neither the VTDO "
                "Contribution definition nor any historical decision."
            ),
            "Beneficiary, Exact Target, GP-C, and production Contribution were not run.",
            "",
        )
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare or run fresh stable identifiable submechanism support"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--stage", choices=("development", "confirmation"), required=True)
    prepare.add_argument("--protocol", required=True, type=Path)
    prepare.add_argument("--source-model-contract", required=True, type=Path)
    prepare.add_argument("--population", action="append", required=True, type=Path)
    prepare.add_argument("--output-path", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--development-contract", type=Path)
    prepare.add_argument("--development-report", type=Path)
    prepare.add_argument("--development-behavior", type=Path)
    prepare.add_argument("--development-manifest", type=Path)
    run = commands.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=24)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "prepare":
        result: Any = prepare_stable_support_contract(
            stage=args.stage,
            protocol_path=args.protocol,
            source_model_contract_path=args.source_model_contract,
            population_paths=tuple(args.population),
            output_path=args.output_path,
            run_id=args.run_id,
            development_contract_path=args.development_contract,
            development_report_path=args.development_report,
            development_behavior_path=args.development_behavior,
            development_manifest_path=args.development_manifest,
        )
        summary = {
            "contract_id": result.contract_id,
            "stage": result.stage,
            "task_count": len(result.tasks),
            "requested_rollout_count": result.requested_rollout_count,
            "next_permitted_stage": result.next_permitted_stage,
        }
    else:
        result = run_stable_support(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        summary = {
            "report_id": result.report_id,
            "stage": result.stage,
            "recorded_rollout_count": result.recorded_rollout_count,
            "runtime_measurement_ready": result.runtime_measurement_ready,
            "capability_support_admitted": result.capability_support_admitted,
            "next_permitted_stage": result.next_permitted_stage,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
