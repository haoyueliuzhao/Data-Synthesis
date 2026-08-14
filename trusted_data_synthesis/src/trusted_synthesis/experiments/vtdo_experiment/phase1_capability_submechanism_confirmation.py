from __future__ import annotations

import argparse
import hashlib
import json
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    DIAGNOSTIC_RESPONSES,
    DiagnosticResponse,
    FinanceSubmechanismFlashContract,
    FinanceSubmechanismFlashReport,
    SubmechanismBehaviorObservation,
    SubmechanismGeometrySpectrum,
    SubmechanismGeometryThresholds,
    _geometry_rows,
    _make_spectrum,
    _make_terminals,
    make_submechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    _verify_inputs as _verify_development_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    CapabilitySubmechanismPopulation,
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
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

SUBMECHANISM_CONFIRMATION_CONTRACT_VERSION = (
    "finance_capability_submechanism_confirmation_contract.v1"
)
SUBMECHANISM_CONFIRMATION_GATE_VERSION = (
    "finance_capability_submechanism_confirmation_gate.v1"
)
SUBMECHANISM_CONFIRMATION_REPORT_VERSION = (
    "finance_capability_submechanism_confirmation_report.v1"
)

EXPECTED_TASK_COUNT = 20
CONFIRMATION_REPLICAS = 5
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * CONFIRMATION_REPLICAS


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SubmechanismConfirmationGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    category: Literal["runtime", "coverage", "primary_geometry"]
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool
    schema_version: str = SUBMECHANISM_CONFIRMATION_GATE_VERSION


class FinanceSubmechanismConfirmationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_29_fresh_submechanism_confirmation"] = (
        "finance_v25_29_fresh_submechanism_confirmation"
    )
    stage: RuntimeResolutionStage = RuntimeResolutionStage.HELDOUT_CONFIRMATION
    source_development_contract_path: str = Field(min_length=1)
    source_development_contract_sha256: str = Field(min_length=64, max_length=64)
    source_development_contract_id: str = Field(min_length=1)
    source_development_report_path: str = Field(min_length=1)
    source_development_report_sha256: str = Field(min_length=64, max_length=64)
    source_development_report_id: str = Field(min_length=1)
    source_development_population_path: str = Field(min_length=1)
    source_development_population_sha256: str = Field(min_length=64, max_length=64)
    source_development_population_id: str = Field(min_length=1)
    source_confirmation_population_path: str = Field(min_length=1)
    source_confirmation_population_sha256: str = Field(min_length=64, max_length=64)
    source_confirmation_population_id: str = Field(min_length=1)
    source_direction_report_id: str = Field(min_length=1)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    development_evidence_disjoint: Literal[True]
    development_evidence_version_disjoint: Literal[True]
    development_task_disjoint: Literal[True]
    development_semantic_signature_disjoint: Literal[True]
    shared_submechanism_set_hash: str = Field(min_length=1)
    development_primary_spectrum_hash: str = Field(min_length=1)
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
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=EXPECTED_TASK_COUNT,
        max_length=EXPECTED_TASK_COUNT,
    )
    replicas: Literal[5] = 5
    requested_rollout_count: Literal[100] = 100
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    thresholds: SubmechanismGeometryThresholds
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_submechanism_confirmation"] = (
        "flash_submechanism_confirmation"
    )
    schema_version: str = SUBMECHANISM_CONFIRMATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceSubmechanismConfirmationContract:
        if self.stage != RuntimeResolutionStage.HELDOUT_CONFIRMATION:
            raise ValueError("submechanism Confirmation uses another Runtime stage")
        task_ids = tuple(item.artifact_id for item in self.tasks)
        task_id_set = set(task_ids)
        if len(task_id_set) != EXPECTED_TASK_COUNT:
            raise ValueError("submechanism Confirmation task identities are duplicated")
        if self.source_development_population_id == self.source_confirmation_population_id:
            raise ValueError("submechanism Confirmation reused its Development population")
        mappings = (
            self.task_submechanism_ids,
            self.task_parent_mechanism_ids,
            self.task_scenario_ids,
            self.task_expected_host_events,
            self.task_raw_capability_demands,
        )
        if any(set(item) != task_id_set for item in mappings):
            raise ValueError("submechanism Confirmation task maps are incomplete")
        binding_task_ids = {item.task_artifact_id for item in self.bindings}
        unique_binding_count = len({item.binding_id for item in self.bindings})
        if binding_task_ids != task_id_set or unique_binding_count != len(self.bindings):
            raise ValueError("submechanism Confirmation bindings are invalid")
        if len(set(self.task_submechanism_ids.values())) != EXPECTED_TASK_COUNT:
            raise ValueError("submechanism Confirmation does not cover 20 distinct submechanisms")
        parent_counts: dict[str, int] = defaultdict(int)
        for parent in self.task_parent_mechanism_ids.values():
            parent_counts[parent] += 1
        if sorted(parent_counts.values()) != [5, 5, 5, 5]:
            raise ValueError("submechanism Confirmation parent support is imbalanced")
        expected_token_keys = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_token_keys:
            raise ValueError("submechanism Confirmation rollout identities are incomplete")
        for binding in self.bindings:
            for replicate in range(self.replicas):
                key = f"{binding.binding_id}|{replicate}"
                expected = canonical_hash(
                    {
                        "run_id": self.run_id,
                        "population_id": self.source_confirmation_population_id,
                        "binding_id": binding.binding_id,
                        "replicate": replicate,
                    },
                    prefix="finance_capability_submechanism_confirmation_rollout:",
                )
                if self.rollout_identity_tokens[key] != expected:
                    raise ValueError("submechanism Confirmation rollout identity is invalid")
        if (
            len(self.model_contracts) != 1
            or self.model_contracts[0].arm != ExplorerArm.FLASH
        ):
            raise ValueError("submechanism Confirmation must remain Flash-only")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_capability_submechanism_confirmation_implementation:",
        ):
            raise ValueError("submechanism Confirmation implementation manifest is invalid")
        if self.contract_id != submechanism_confirmation_contract_id(self):
            raise ValueError("submechanism Confirmation contract identity is invalid")
        return self


class FinanceSubmechanismConfirmationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_29_fresh_submechanism_confirmation"]
    source_development_report_id: str = Field(min_length=1)
    source_development_population_id: str = Field(min_length=1)
    source_confirmation_population_id: str = Field(min_length=1)
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
    gates: tuple[SubmechanismConfirmationGate, ...] = Field(min_length=10)
    runtime_measurement_ready: bool
    primary_information_geometry_confirmed: bool
    failure_codes: tuple[str, ...]
    outcome_set_hash: str = Field(min_length=1)
    behavior_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    diagnostics_rescued_primary: Literal[False] = False
    pro_sparse_anchor_authorized: bool
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "pro_sparse_anchor_preparation",
        "submechanism_confirmation_failed",
        "runtime_measurement_repair_only",
    ]
    schema_version: str = SUBMECHANISM_CONFIRMATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceSubmechanismConfirmationReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("submechanism Confirmation lacks its complete denominator")
        runtime_gates = tuple(item for item in self.gates if item.category == "runtime")
        geometry_gates = tuple(
            item for item in self.gates if item.category in {"coverage", "primary_geometry"}
        )
        runtime_ready = bool(runtime_gates) and all(item.passed for item in runtime_gates)
        geometry_ready = (
            runtime_ready and bool(geometry_gates) and all(item.passed for item in geometry_gates)
        )
        if self.runtime_measurement_ready != runtime_ready:
            raise ValueError("submechanism Confirmation Runtime readiness is inconsistent")
        if self.primary_information_geometry_confirmed != geometry_ready:
            raise ValueError("submechanism Confirmation geometry decision is inconsistent")
        if self.pro_sparse_anchor_authorized != geometry_ready:
            raise ValueError("submechanism Confirmation Pro transition is inconsistent")
        expected = (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "pro_sparse_anchor_preparation"
                if geometry_ready
                else "submechanism_confirmation_failed"
            )
        )
        if self.next_permitted_stage != expected:
            raise ValueError("submechanism Confirmation transition is not fail-closed")
        if set(self.diagnostic_spectra) != set(DIAGNOSTIC_RESPONSES):
            raise ValueError("submechanism Confirmation diagnostics are incomplete")
        if self.report_id != submechanism_confirmation_report_id(self):
            raise ValueError("submechanism Confirmation report identity is invalid")
        return self


def submechanism_confirmation_contract_id(
    value: FinanceSubmechanismConfirmationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_submechanism_confirmation_contract:",
    )


def submechanism_confirmation_report_id(
    value: FinanceSubmechanismConfirmationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_submechanism_confirmation_report:",
    )


def prepare_submechanism_confirmation(
    *,
    source_population_path: Path,
    development_contract_path: Path,
    development_report_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceSubmechanismConfirmationContract:
    if output_path.exists():
        raise ValueError("submechanism Confirmation contract is immutable")
    population_path = source_population_path.resolve()
    development_contract_path = development_contract_path.resolve()
    development_report_path = development_report_path.resolve()
    development = FinanceSubmechanismFlashContract.model_validate_json(
        development_contract_path.read_text(encoding="utf-8")
    )
    development_report = FinanceSubmechanismFlashReport.model_validate_json(
        development_report_path.read_text(encoding="utf-8")
    )
    _verify_development_inputs(development)
    if (
        development_report.contract_id != development.contract_id
        or not development_report.fresh_submechanism_confirmation_authorized
        or development_report.next_permitted_stage
        != "fresh_submechanism_confirmation_preparation"
    ):
        raise ValueError("submechanism Confirmation lacks Development authorization")
    population = CapabilitySubmechanismPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    if not population.static_audit.ready:
        raise ValueError("submechanism Confirmation population is not statically ready")
    development_population_path = Path(development.source_population_path).resolve()
    development_population = CapabilitySubmechanismPopulation.model_validate_json(
        development_population_path.read_text(encoding="utf-8")
    )
    if development_population_path not in {
        Path(item).resolve() for item in population.exclusion_paths
    }:
        raise ValueError("submechanism Confirmation population did not exclude Development")
    disjoint = _population_disjointness(development_population, population)
    if not all(disjoint.values()):
        raise ValueError(f"submechanism Confirmation population overlaps Development:{disjoint}")
    development_submechanisms = set(development.task_submechanism_ids.values())
    confirmation_submechanisms = {item.submechanism_id for item in population.tasks}
    if development_submechanisms != confirmation_submechanisms:
        raise ValueError("submechanism Confirmation changed the frozen submechanism set")
    development_demand_by_submechanism = {
        development.task_submechanism_ids[task_id]: demand
        for task_id, demand in development.task_raw_capability_demands.items()
    }
    tasks = tuple(item.artifact for item in population.tasks)
    task_rows = {item.artifact.artifact_id: item for item in population.tasks}
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            development.protocol_profile,
        )
        for task in tasks
    )
    task_submechanism_ids = {
        task_id: item.submechanism_id for task_id, item in task_rows.items()
    }
    task_parent_mechanism_ids = {
        task_id: item.parent_mechanism_id for task_id, item in task_rows.items()
    }
    task_scenario_ids = {task_id: item.scenario.scenario_id for task_id, item in task_rows.items()}
    task_expected_host_events = {
        task_id: item.scenario.expected_host_events for task_id, item in task_rows.items()
    }
    task_raw_capability_demands = {
        task_id: development_demand_by_submechanism[item.submechanism_id]
        for task_id, item in task_rows.items()
    }
    rollout_tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "population_id": population.population_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
            },
            prefix="finance_capability_submechanism_confirmation_rollout:",
        )
        for binding in bindings
        for replicate in range(CONFIRMATION_REPLICAS)
    }
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "source_development_contract_path": str(development_contract_path),
        "source_development_contract_sha256": _sha256(development_contract_path),
        "source_development_contract_id": development.contract_id,
        "source_development_report_path": str(development_report_path),
        "source_development_report_sha256": _sha256(development_report_path),
        "source_development_report_id": development_report.report_id,
        "source_development_population_path": str(development_population_path),
        "source_development_population_sha256": _sha256(development_population_path),
        "source_development_population_id": development_population.population_id,
        "source_confirmation_population_path": str(population_path),
        "source_confirmation_population_sha256": _sha256(population_path),
        "source_confirmation_population_id": population.population_id,
        "source_direction_report_id": development.source_direction_report_id,
        "finance_archive_config_path": development.finance_archive_config_path,
        "finance_archive_config_sha256": development.finance_archive_config_sha256,
        "development_evidence_disjoint": disjoint["evidence"],
        "development_evidence_version_disjoint": disjoint["evidence_version"],
        "development_task_disjoint": disjoint["task"],
        "development_semantic_signature_disjoint": disjoint["semantic_signature"],
        "shared_submechanism_set_hash": canonical_hash(
            tuple(sorted(development_submechanisms)),
            prefix="finance_capability_submechanism_confirmation_shared_set:",
        ),
        "development_primary_spectrum_hash": canonical_hash(
            development_report.primary_spectrum,
            prefix="finance_capability_submechanism_development_primary_spectrum:",
        ),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_capability_submechanism_confirmation_implementation:",
        ),
        "model_contracts": development.model_contracts,
        "protocol_profile": development.protocol_profile,
        "tasks": tasks,
        "task_submechanism_ids": task_submechanism_ids,
        "task_parent_mechanism_ids": task_parent_mechanism_ids,
        "task_scenario_ids": task_scenario_ids,
        "task_expected_host_events": task_expected_host_events,
        "task_raw_capability_demands": task_raw_capability_demands,
        "bindings": bindings,
        "maximum_model_tokens_per_rollout": development.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": development.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": development.maximum_public_context_bytes,
        "model_contract_repair_attempts": development.model_contract_repair_attempts,
        "rollout_identity_tokens": rollout_tokens,
        "thresholds": development.thresholds,
    }
    provisional = FinanceSubmechanismConfirmationContract.model_construct(
        contract_id="pending",
        **values,
    )
    contract = FinanceSubmechanismConfirmationContract(
        contract_id=submechanism_confirmation_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_submechanism_confirmation(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceSubmechanismConfirmationReport:
    contract = FinanceSubmechanismConfirmationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_inputs(contract)
    prefix = "capability_submechanism_flash_confirmation"
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
    report = make_submechanism_confirmation_report(contract, outcomes, terminals, behaviors)
    report_path = output_dir / "finance_capability_submechanism_confirmation_report.json"
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_capability_submechanism_confirmation_report.md",
        _render_report(report),
    )
    _write_json_atomic(
        output_dir / "finance_capability_submechanism_confirmation_manifest.json",
        {
            "contract_id": contract.contract_id,
            "report_id": report.report_id,
            "experiment_label": contract.experiment_label,
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


def make_submechanism_confirmation_report(
    contract: FinanceSubmechanismConfirmationContract,
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[SubmechanismBehaviorObservation],
) -> FinanceSubmechanismConfirmationReport:
    if not (
        len(outcomes)
        == len(terminals)
        == len(behaviors)
        == contract.requested_rollout_count
    ):
        raise ValueError("submechanism Confirmation report has an incomplete denominator")
    grouped: dict[str, list[SubmechanismBehaviorObservation]] = defaultdict(list)
    for item in behaviors:
        grouped[item.task_artifact_id].append(item)
    complete_task_ids = {
        task_id
        for task_id, values in grouped.items()
        if len(values) == contract.replicas and all(item.runtime_eligible for item in values)
    }
    primary = _make_spectrum(
        cast(Any, contract),
        _geometry_rows(
            cast(Any, contract),
            behaviors,
            complete_task_ids=complete_task_ids,
            response_variable="primary_valid_success",
        ),
        response_variable="valid_success",
    )
    diagnostics = {
        response: _make_spectrum(
            cast(Any, contract),
            _geometry_rows(
                cast(Any, contract),
                behaviors,
                complete_task_ids=complete_task_ids,
                response_variable=f"{response}_response",
            ),
            response_variable=response,
        )
        for response in DIAGNOSTIC_RESPONSES
    }
    gates = _make_confirmation_gates(
        contract,
        terminals,
        primary,
        len(complete_task_ids),
    )
    runtime_ready = all(item.passed for item in gates if item.category == "runtime")
    geometry_ready = runtime_ready and all(
        item.passed for item in gates if item.category in {"coverage", "primary_geometry"}
    )
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    values = {
        "contract_id": contract.contract_id,
        "experiment_label": contract.experiment_label,
        "source_development_report_id": contract.source_development_report_id,
        "source_development_population_id": contract.source_development_population_id,
        "source_confirmation_population_id": contract.source_confirmation_population_id,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(terminals),
        "runtime_eligible_rollout_count": len(eligible),
        "complete_runtime_eligible_task_count": len(complete_task_ids),
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
        "end_to_end_valid_success_rate": _rate(
            item.valid_success for item in terminals
        ),
        "host_trigger_observation_rate": _rate(
            item.trigger_observed for item in behaviors
        ),
        "host_resolution_observation_rate": _rate(
            item.resolution_observed for item in behaviors
        ),
        "ordered_behavior_success_rate": _rate(
            item.behavior_success for item in behaviors
        ),
        "primary_spectrum": primary,
        "diagnostic_spectra": diagnostics,
        "gates": gates,
        "runtime_measurement_ready": runtime_ready,
        "primary_information_geometry_confirmed": geometry_ready,
        "failure_codes": tuple(item.gate_id for item in gates if not item.passed),
        "outcome_set_hash": canonical_hash(
            tuple(item.terminal_outcome_id for item in terminals),
            prefix="finance_capability_submechanism_confirmation_terminal_set:",
        ),
        "behavior_set_hash": canonical_hash(
            tuple(item.observation_id for item in behaviors),
            prefix="finance_capability_submechanism_confirmation_behavior_set:",
        ),
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "pro_sparse_anchor_authorized": geometry_ready,
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "pro_sparse_anchor_preparation"
                if geometry_ready
                else "submechanism_confirmation_failed"
            )
        ),
    }
    provisional = FinanceSubmechanismConfirmationReport.model_construct(
        report_id="pending",
        **values,
    )
    return FinanceSubmechanismConfirmationReport(
        report_id=submechanism_confirmation_report_id(provisional),
        **values,
    )


def _make_confirmation_gates(
    contract: FinanceSubmechanismConfirmationContract,
    terminals: Sequence[RuntimeTerminalOutcome],
    spectrum: SubmechanismGeometrySpectrum,
    complete_task_count: int,
) -> tuple[SubmechanismConfirmationGate, ...]:
    thresholds = contract.thresholds
    transport = _rate(item.api_transport_resolved for item in terminals)
    bounded = _rate(item.bounded_json_resolution_success for item in terminals)
    replay = _rate(item.observation_replay_success for item in terminals)
    authority = _rate(item.authority_integrity_success for item in terminals)
    pathology = _rate(item.runtime_pathology for item in terminals)
    rows: tuple[tuple[str, bool, float, str, str], ...] = (
        (
            "complete_rollout_denominator",
            len(terminals) == EXPECTED_ROLLOUT_COUNT,
            len(terminals),
            f"={EXPECTED_ROLLOUT_COUNT}",
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
            spectrum.distinct_normalized_demand_count
            >= thresholds.minimum_residual_rank,
            spectrum.distinct_normalized_demand_count,
            f">={thresholds.minimum_residual_rank}",
            "coverage",
        ),
        (
            "nonzero_weight_task_count",
            spectrum.nonzero_weight_task_count
            >= thresholds.minimum_nonzero_weight_task_count,
            spectrum.nonzero_weight_task_count,
            f">={thresholds.minimum_nonzero_weight_task_count}",
            "primary_geometry",
        ),
        (
            "boundary_task_fraction",
            spectrum.boundary_task_fraction
            >= thresholds.minimum_boundary_task_fraction,
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
            spectrum.residual_effective_rank
            >= thresholds.minimum_residual_effective_rank,
            spectrum.residual_effective_rank,
            f">={thresholds.minimum_residual_effective_rank}",
            "primary_geometry",
        ),
        (
            "residual_condition_number",
            spectrum.residual_condition_number
            <= thresholds.maximum_residual_condition_number,
            spectrum.residual_condition_number,
            f"<={thresholds.maximum_residual_condition_number}",
            "primary_geometry",
        ),
        (
            "general_factor_fraction",
            spectrum.general_factor_fraction
            <= thresholds.maximum_general_factor_fraction,
            spectrum.general_factor_fraction,
            f"<={thresholds.maximum_general_factor_fraction}",
            "primary_geometry",
        ),
        (
            "informative_axis_count",
            spectrum.informative_axis_count
            >= thresholds.minimum_informative_axis_count,
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
        SubmechanismConfirmationGate(
            gate_id=gate_id,
            category=cast(Any, category),
            observed=float(observed),
            requirement=requirement,
            passed=passed,
        )
        for gate_id, passed, observed, requirement, category in rows
    )


def _population_disjointness(
    development: CapabilitySubmechanismPopulation,
    confirmation: CapabilitySubmechanismPopulation,
) -> dict[str, bool]:
    development_identity = _population_identity(development)
    confirmation_identity = _population_identity(confirmation)
    return {
        key: not bool(development_identity[key] & confirmation_identity[key])
        for key in development_identity
    }


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
        "semantic_signature": {
            item.source_semantic_signature for item in population.tasks
        },
    }


def _verify_inputs(contract: FinanceSubmechanismConfirmationContract) -> None:
    paths = (
        (
            contract.source_development_contract_path,
            contract.source_development_contract_sha256,
        ),
        (
            contract.source_development_report_path,
            contract.source_development_report_sha256,
        ),
        (
            contract.source_development_population_path,
            contract.source_development_population_sha256,
        ),
        (
            contract.source_confirmation_population_path,
            contract.source_confirmation_population_sha256,
        ),
        (contract.finance_archive_config_path, contract.finance_archive_config_sha256),
    )
    for path_value, expected in paths:
        if _sha256(Path(path_value)) != expected:
            raise ValueError(f"submechanism Confirmation frozen input changed:{path_value}")
    implementation = _implementation_manifest()
    if implementation != contract.implementation_manifest:
        raise ValueError("submechanism Confirmation implementation changed after freeze")
    development = FinanceSubmechanismFlashContract.model_validate_json(
        Path(contract.source_development_contract_path).read_text(encoding="utf-8")
    )
    development_report = FinanceSubmechanismFlashReport.model_validate_json(
        Path(contract.source_development_report_path).read_text(encoding="utf-8")
    )
    _verify_development_inputs(development)
    if (
        development.contract_id != contract.source_development_contract_id
        or development_report.report_id != contract.source_development_report_id
        or development_report.contract_id != development.contract_id
        or not development_report.fresh_submechanism_confirmation_authorized
    ):
        raise ValueError("submechanism Confirmation Development lineage is invalid")
    population = CapabilitySubmechanismPopulation.model_validate_json(
        Path(contract.source_confirmation_population_path).read_text(encoding="utf-8")
    )
    development_population = CapabilitySubmechanismPopulation.model_validate_json(
        Path(contract.source_development_population_path).read_text(encoding="utf-8")
    )
    if (
        population.population_id != contract.source_confirmation_population_id
        or development_population.population_id
        != contract.source_development_population_id
        or not population.static_audit.ready
        or not all(_population_disjointness(development_population, population).values())
    ):
        raise ValueError("submechanism Confirmation population lineage is invalid")
    if (
        contract.model_contracts != development.model_contracts
        or contract.protocol_profile != development.protocol_profile
        or contract.thresholds != development.thresholds
        or contract.maximum_model_tokens_per_rollout
        != development.maximum_model_tokens_per_rollout
        or contract.model_contract_repair_attempts
        != development.model_contract_repair_attempts
    ):
        raise ValueError("submechanism Confirmation changed its Development protocol")


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
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
        root
        / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary.py",
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_boundary_runner.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_multitier_confirmation.py"
        ),
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
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in values
        ),
    )


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _render_report(report: FinanceSubmechanismConfirmationReport) -> str:
    primary = report.primary_spectrum
    return "\n".join(
        (
            "# Finance v25.29 Fresh Flash Submechanism Confirmation",
            "",
            "## Decision",
            "",
            f"- Report ID: `{report.report_id}`",
            (
                "- Complete denominator: "
                f"**{report.recorded_rollout_count}/{report.requested_rollout_count}**"
            ),
            f"- Runtime ready: **{report.runtime_measurement_ready}**",
            f"- Primary geometry confirmed: **{report.primary_information_geometry_confirmed}**",
            (
                "- Pro sparse-anchor preparation authorized: "
                f"**{report.pro_sparse_anchor_authorized}**"
            ),
            f"- Next permitted stage: `{report.next_permitted_stage}`",
            "",
            "## Primary Response Geometry",
            "",
            f"- Valid success: **{report.end_to_end_valid_success_rate:.2%}**",
            f"- Boundary task fraction: **{primary.boundary_task_fraction:.2%}**",
            f"- Nonzero-weight tasks: **{primary.nonzero_weight_task_count}**",
            f"- Residual numerical rank: **{primary.residual_numerical_rank}**",
            f"- Residual effective rank: **{primary.residual_effective_rank:.4f}**",
            f"- Residual condition number: **{primary.residual_condition_number:.4f}**",
            f"- General-factor fraction: **{primary.general_factor_fraction:.2%}**",
            f"- Informative axes: **{primary.informative_axis_count}/{len(CAPABILITY_AXES)}**",
            "",
            "Diagnostics remain descriptive and cannot rescue a failed primary response.",
            "Pro, Beneficiary, Exact Target, GP-C, and production Contribution were not run.",
            "",
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare or run v25.29 fresh Flash submechanism Confirmation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-population", required=True, type=Path)
    prepare.add_argument("--development-contract", required=True, type=Path)
    prepare.add_argument("--development-report", required=True, type=Path)
    prepare.add_argument("--output-path", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "prepare":
        result: Any = prepare_submechanism_confirmation(
            source_population_path=args.source_population,
            development_contract_path=args.development_contract,
            development_report_path=args.development_report,
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
        result = run_submechanism_confirmation(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        summary = {
            "report_id": result.report_id,
            "recorded_rollout_count": result.recorded_rollout_count,
            "runtime_measurement_ready": result.runtime_measurement_ready,
            "primary_information_geometry_confirmed": (
                result.primary_information_geometry_confirmed
            ),
            "next_permitted_stage": result.next_permitted_stage,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
