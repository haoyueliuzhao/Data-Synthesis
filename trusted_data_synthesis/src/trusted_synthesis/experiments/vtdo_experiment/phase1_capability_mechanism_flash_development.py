from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import ActionType
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
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (
    CapabilityMechanismDevelopmentPopulation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_ir import (
    MECHANISM_IDS,
    MechanismTier,
    VariantRole,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
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

CAPABILITY_MECHANISM_FLASH_CONTRACT_VERSION = (
    "finance_capability_mechanism_flash_development_contract.v1"
)
CAPABILITY_MECHANISM_BEHAVIOR_VERSION = "finance_capability_mechanism_behavior.v1"
CAPABILITY_MECHANISM_FLASH_REPORT_VERSION = (
    "finance_capability_mechanism_flash_development_report.v3"
)

DEVELOPMENT_REPLICAS = 3
EXPECTED_GROUP_COUNT = 84
EXPECTED_TASK_COUNT = EXPECTED_GROUP_COUNT * 2
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * DEVELOPMENT_REPLICAS


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceCapabilityMechanismFlashContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    stage: RuntimeResolutionStage = RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
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
    task_group_ids: dict[str, str]
    task_mechanism_ids: dict[str, str]
    task_mechanism_tiers: dict[str, MechanismTier]
    task_variant_roles: dict[str, VariantRole]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=EXPECTED_TASK_COUNT,
        max_length=EXPECTED_TASK_COUNT,
    )
    replicas: Literal[3] = 3
    requested_rollout_count: int = Field(ge=EXPECTED_ROLLOUT_COUNT, le=EXPECTED_ROLLOUT_COUNT)
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    confirmation_response_access_during_selection: Literal["forbidden"] = "forbidden"
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_mechanism_development"] = "flash_mechanism_development"
    schema_version: str = CAPABILITY_MECHANISM_FLASH_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceCapabilityMechanismFlashContract:
        if self.stage != RuntimeResolutionStage.RESIDUAL_DEVELOPMENT:
            raise ValueError("mechanism Flash stage must remain Development")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("mechanism Development is Flash-only")
        if self.requested_rollout_count != len(self.bindings) * self.replicas:
            raise ValueError("mechanism Development rollout denominator is inconsistent")
        task_ids = {item.artifact_id for item in self.tasks}
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("mechanism Development task/binding identity is incomplete")
        maps = (
            self.task_group_ids,
            self.task_mechanism_ids,
            self.task_mechanism_tiers,
            self.task_variant_roles,
        )
        if any(set(item) != task_ids for item in maps):
            raise ValueError("mechanism Development task metadata maps are incomplete")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("mechanism Development rollout identities are incomplete")
        if set(self.task_mechanism_ids.values()) != set(MECHANISM_IDS):
            raise ValueError("mechanism Development omits a preregistered mechanism")
        if self.contract_id != mechanism_flash_contract_id(self):
            raise ValueError("mechanism Development contract identity is invalid")
        return self


class MechanismBehaviorObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    mechanism_tier: MechanismTier
    variant_role: VariantRole
    replicate: int = Field(ge=0)
    runtime_eligible: bool
    semantic_answer_correct: bool
    valid_success: bool
    mechanism_evaluable: bool
    mechanism_success: bool
    behavior_checks: dict[str, bool]
    observed_tool_ids: tuple[str, ...]
    failed_tool_call_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    decision_depth: int = Field(ge=0)
    schema_version: str = CAPABILITY_MECHANISM_BEHAVIOR_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> MechanismBehaviorObservation:
        if self.mechanism_id not in MECHANISM_IDS:
            raise ValueError("mechanism behavior uses an unknown mechanism")
        if self.mechanism_success and not self.mechanism_evaluable:
            raise ValueError("mechanism success lacks an evaluable trajectory")
        if self.mechanism_success != (
            self.mechanism_evaluable and all(self.behavior_checks.values())
        ):
            raise ValueError("mechanism behavior decision is inconsistent")
        if self.observation_id != mechanism_behavior_observation_id(self):
            raise ValueError("mechanism behavior identity is invalid")
        return self


class MechanismCellSummary(FrozenModel):
    mechanism_id: str = Field(min_length=1)
    mechanism_tier: MechanismTier
    variant_role: VariantRole
    attempted_count: int = Field(ge=1)
    runtime_eligible_count: int = Field(ge=0)
    runtime_eligibility_rate: float = Field(ge=0, le=1)
    semantic_accuracy_given_runtime_eligible: float = Field(ge=0, le=1)
    valid_success_rate: float = Field(ge=0, le=1)
    mechanism_evaluable_count: int = Field(ge=0)
    mechanism_success_rate_given_evaluable: float = Field(ge=0, le=1)
    mechanism_success_wilson_lower: float = Field(ge=0, le=1)
    mechanism_success_wilson_upper: float = Field(ge=0, le=1)
    mean_tool_call_count: float = Field(ge=0)
    mean_decision_depth: float = Field(ge=0)


class MatchedMechanismEffect(FrozenModel):
    mechanism_id: str = Field(min_length=1)
    mechanism_tier: MechanismTier
    matched_group_count: int = Field(ge=1)
    control_success_rate: float = Field(ge=0, le=1)
    mechanism_success_rate: float = Field(ge=0, le=1)
    mechanism_requirement_penalty: float = Field(ge=-1, le=1)
    informative_group_count: int = Field(ge=0)
    boundary_group_count: int = Field(ge=0)


class MechanismSelectionDecision(FrozenModel):
    mechanism_id: str = Field(min_length=1)
    runtime_qualified: bool
    bridge_or_frontier_evaluable_count: int = Field(ge=0)
    bridge_or_frontier_informative_group_count: int = Field(ge=0)
    bridge_or_frontier_control_supported_group_count: int = Field(ge=0)
    bridge_or_frontier_mechanism_nonzero_group_count: int = Field(ge=0)
    bridge_or_frontier_boundary_group_count: int = Field(ge=0)
    bridge_or_frontier_matched_difference_group_count: int = Field(ge=0)
    bridge_or_frontier_mechanism_behavior_success_count: int = Field(ge=0)
    bridge_or_frontier_mechanism_behavior_success_rate: float = Field(ge=0, le=1)
    matched_behavior_detected: bool
    selected_for_confirmation: bool
    reasons: tuple[str, ...]


class FinanceCapabilityMechanismFlashReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=1)
    runtime_eligible_rollout_count: int = Field(ge=0)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    runtime_pathology_rate: float = Field(ge=0, le=1)
    semantic_accuracy_given_runtime_eligible: float = Field(ge=0, le=1)
    end_to_end_valid_success_rate: float = Field(ge=0, le=1)
    cells: tuple[MechanismCellSummary, ...]
    matched_effects: tuple[MatchedMechanismEffect, ...]
    selection_decisions: tuple[MechanismSelectionDecision, ...]
    selected_mechanism_ids: tuple[str, ...]
    runtime_qualification_passed: bool
    mechanism_selection_freeze_authorized: bool
    failure_codes: tuple[str, ...]
    outcome_set_hash: str = Field(min_length=1)
    behavior_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "fresh_mechanism_confirmation_preparation",
        "mechanism_task_repair_only",
        "runtime_measurement_repair_only",
    ]
    schema_version: str = CAPABILITY_MECHANISM_FLASH_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceCapabilityMechanismFlashReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("mechanism Development lacks its complete denominator")
        selected = tuple(
            item.mechanism_id for item in self.selection_decisions if item.selected_for_confirmation
        )
        if self.selected_mechanism_ids != selected:
            raise ValueError("mechanism selection list differs from decisions")
        authorized = self.runtime_qualification_passed and bool(selected)
        if self.mechanism_selection_freeze_authorized != authorized:
            raise ValueError("mechanism selection authorization is inconsistent")
        expected = (
            "runtime_measurement_repair_only"
            if not self.runtime_qualification_passed
            else (
                "fresh_mechanism_confirmation_preparation"
                if selected
                else "mechanism_task_repair_only"
            )
        )
        if self.next_permitted_stage != expected:
            raise ValueError("mechanism Development transition is not fail-closed")
        if self.report_id != mechanism_flash_report_id(self):
            raise ValueError("mechanism Development report identity is invalid")
        return self


def mechanism_flash_contract_id(value: FinanceCapabilityMechanismFlashContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_mechanism_flash_contract:",
    )


def mechanism_behavior_observation_id(value: MechanismBehaviorObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="finance_capability_mechanism_behavior:",
    )


def mechanism_flash_report_id(value: FinanceCapabilityMechanismFlashReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_mechanism_flash_report:",
    )


def prepare_mechanism_flash_development(
    *,
    source_population_path: Path,
    source_v25_20_contract_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceCapabilityMechanismFlashContract:
    if output_path.exists():
        raise ValueError("mechanism Flash Development contract is immutable")
    population = CapabilityMechanismDevelopmentPopulation.model_validate_json(
        source_population_path.read_text(encoding="utf-8")
    )
    source = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        source_v25_20_contract_path.read_text(encoding="utf-8")
    )
    if not population.static_audit.development_ready:
        raise ValueError("mechanism Flash Development lacks a passing static audit")
    model_contracts = tuple(
        item for item in source.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("source contract does not freeze exactly one Flash model")
    variants = tuple(
        (group, variant)
        for group in population.groups
        for variant in (group.control, group.mechanism)
    )
    tasks = tuple(variant.artifact for _, variant in variants)
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            source.protocol_profile,
        )
        for task in tasks
    )
    group_ids = {variant.artifact.artifact_id: group.group_id for group, variant in variants}
    mechanism_ids = {
        variant.artifact.artifact_id: group.mechanism_id for group, variant in variants
    }
    tiers = {variant.artifact.artifact_id: group.mechanism_tier for group, variant in variants}
    roles = {variant.artifact.artifact_id: variant.role for _, variant in variants}
    tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "population_id": population.population_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
            },
            prefix="finance_capability_mechanism_flash_rollout:",
        )
        for binding in bindings
        for replicate in range(DEVELOPMENT_REPLICAS)
    }
    implementation = _implementation_manifest()
    finance_config = Path(source.finance_archive_config_path)
    values = {
        "run_id": run_id,
        "source_population_path": str(source_population_path.resolve()),
        "source_population_sha256": _sha256(source_population_path),
        "source_population_id": population.population_id,
        "source_v25_20_contract_path": str(source_v25_20_contract_path.resolve()),
        "source_v25_20_contract_sha256": _sha256(source_v25_20_contract_path),
        "source_v25_20_contract_id": source.contract_id,
        "finance_archive_config_path": str(finance_config.resolve()),
        "finance_archive_config_sha256": _sha256(finance_config),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_capability_mechanism_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": source.protocol_profile,
        "tasks": tasks,
        "task_group_ids": group_ids,
        "task_mechanism_ids": mechanism_ids,
        "task_mechanism_tiers": tiers,
        "task_variant_roles": roles,
        "bindings": bindings,
        "requested_rollout_count": len(bindings) * DEVELOPMENT_REPLICAS,
        "maximum_model_tokens_per_rollout": source.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": source.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": source.maximum_public_context_bytes,
        "model_contract_repair_attempts": source.model_contract_repair_attempts,
        "rollout_identity_tokens": tokens,
    }
    provisional = FinanceCapabilityMechanismFlashContract.model_construct(
        contract_id="pending", **values
    )
    contract = FinanceCapabilityMechanismFlashContract(
        contract_id=mechanism_flash_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_mechanism_flash_development(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceCapabilityMechanismFlashReport:
    contract = FinanceCapabilityMechanismFlashContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_inputs(contract)
    prefix = "capability_mechanism_flash_development"
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
    records = _load_records(records_path)
    terminals = _make_terminals(contract, records, outcomes)
    behaviors = make_mechanism_behavior_observations(contract, records, terminals)
    _write_jsonl_atomic(
        output_dir / f"{prefix}_terminal_outcomes.jsonl",
        (item.model_dump(mode="json") for item in terminals),
    )
    _write_jsonl_atomic(
        output_dir / f"{prefix}_behavior_observations.jsonl",
        (item.model_dump(mode="json") for item in behaviors),
    )
    report = make_mechanism_flash_report(contract, outcomes, terminals, behaviors)
    report_path = output_dir / "finance_capability_mechanism_flash_report.json"
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_capability_mechanism_flash_report.md",
        _render_report(report),
    )
    _write_json_atomic(
        output_dir / "finance_capability_mechanism_flash_manifest.json",
        {
            "contract_id": contract.contract_id,
            "report_id": report.report_id,
            "requested_model": contract.model_contracts[0].requested_model,
            "discovered_models": discovered,
            "records_sha256": _sha256(records_path),
            "report_sha256": _sha256(report_path),
            "pro_api_call_count": 0,
            "beneficiary_screening_authorized": False,
            "exact_target_evaluated": False,
            "gp_c_evaluated": False,
        },
    )
    return report


def make_mechanism_behavior_observations(
    contract: FinanceCapabilityMechanismFlashContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    terminals: Sequence[RuntimeTerminalOutcome],
) -> tuple[MechanismBehaviorObservation, ...]:
    terminal_by_key = {(item.binding_id, item.replicate): item for item in terminals}
    rows = []
    for record in sorted(records, key=lambda item: (item.binding_id, item.replicate)):
        terminal = terminal_by_key[(record.binding_id, record.replicate)]
        mechanism_id = contract.task_mechanism_ids[record.task_artifact_id]
        role = contract.task_variant_roles[record.task_artifact_id]
        checks = _mechanism_behavior_checks(mechanism_id, role, record)
        evaluable = bool(terminal.runtime_eligible_for_capability_denominator and checks)
        observations = _record_observations(record)
        values = {
            "contract_id": contract.contract_id,
            "record_id": record.record_id,
            "binding_id": record.binding_id,
            "task_artifact_id": record.task_artifact_id,
            "group_id": contract.task_group_ids[record.task_artifact_id],
            "mechanism_id": mechanism_id,
            "mechanism_tier": contract.task_mechanism_tiers[record.task_artifact_id],
            "variant_role": role,
            "replicate": record.replicate,
            "runtime_eligible": terminal.runtime_eligible_for_capability_denominator,
            "semantic_answer_correct": terminal.semantic_answer_correct,
            "valid_success": terminal.valid_success,
            "mechanism_evaluable": evaluable,
            "mechanism_success": evaluable and all(checks.values()),
            "behavior_checks": checks,
            "observed_tool_ids": tuple(item.call.tool_id for item in observations),
            "failed_tool_call_count": sum(item.status == "failed" for item in observations),
            "successful_tool_call_count": sum(item.status == "succeeded" for item in observations),
            "decision_depth": len(record.trajectory.steps) if record.trajectory else 0,
        }
        provisional = MechanismBehaviorObservation.model_construct(
            observation_id="pending", **values
        )
        rows.append(
            MechanismBehaviorObservation(
                observation_id=mechanism_behavior_observation_id(provisional), **values
            )
        )
    return tuple(rows)


def make_mechanism_flash_report(
    contract: FinanceCapabilityMechanismFlashContract,
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[MechanismBehaviorObservation],
) -> FinanceCapabilityMechanismFlashReport:
    if not (len(outcomes) == len(terminals) == len(behaviors) == contract.requested_rollout_count):
        raise ValueError("mechanism Development has an incomplete denominator")
    cells = _cell_summaries(behaviors)
    effects = _matched_effects(contract, behaviors)
    api_resolved = _rate(item.api_transport_resolved for item in terminals)
    json_resolved = _rate(item.bounded_json_resolution_success for item in terminals)
    replay = _rate(item.observation_replay_success for item in terminals)
    authority = _rate(item.authority_integrity_success for item in terminals)
    pathology = _rate(item.runtime_pathology for item in terminals)
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    runtime_passed = (
        api_resolved >= 0.98
        and json_resolved >= 0.95
        and replay >= 0.98
        and authority >= 0.98
        and pathology <= 0.02
    )
    decisions = _selection_decisions(contract, behaviors, runtime_passed)
    selected = tuple(item.mechanism_id for item in decisions if item.selected_for_confirmation)
    failure_codes = []
    if not runtime_passed:
        failure_codes.append("flash_runtime_qualification_failed")
    if runtime_passed and not selected:
        failure_codes.append("no_mechanism_is_confirmation_ready")
    values = {
        "contract_id": contract.contract_id,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(outcomes),
        "runtime_eligible_rollout_count": len(eligible),
        "api_transport_resolution_rate": api_resolved,
        "bounded_json_resolution_rate": json_resolved,
        "observation_replay_rate": replay,
        "authority_integrity_rate": authority,
        "runtime_pathology_rate": pathology,
        "semantic_accuracy_given_runtime_eligible": _rate(
            item.semantic_answer_correct for item in eligible
        ),
        "end_to_end_valid_success_rate": _rate(item.valid_success for item in outcomes),
        "cells": cells,
        "matched_effects": effects,
        "selection_decisions": decisions,
        "selected_mechanism_ids": selected,
        "runtime_qualification_passed": runtime_passed,
        "mechanism_selection_freeze_authorized": runtime_passed and bool(selected),
        "failure_codes": tuple(failure_codes),
        "outcome_set_hash": canonical_hash(
            tuple(sorted(item.outcome_id for item in outcomes)),
            prefix="finance_capability_mechanism_outcomes:",
        ),
        "behavior_set_hash": canonical_hash(
            tuple(sorted(item.observation_id for item in behaviors)),
            prefix="finance_capability_mechanism_behaviors:",
        ),
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_passed
            else (
                "fresh_mechanism_confirmation_preparation"
                if selected
                else "mechanism_task_repair_only"
            )
        ),
    }
    provisional = FinanceCapabilityMechanismFlashReport.model_construct(
        report_id="pending", **values
    )
    return FinanceCapabilityMechanismFlashReport(
        report_id=mechanism_flash_report_id(provisional), **values
    )


def _mechanism_behavior_checks(
    mechanism_id: str,
    role: VariantRole,
    record: CapabilityBoundaryRolloutRecord,
) -> dict[str, bool]:
    if record.status != "completed" or record.trajectory is None:
        return {}
    observations = _record_observations(record)
    tool_ids = tuple(item.call.tool_id for item in observations)
    successful = tuple(item for item in observations if item.status == "succeeded")
    failed = tuple(item for item in observations if item.status == "failed")
    steps = record.trajectory.steps
    if role == "resolved_control":
        return {
            "completed": True,
            "used_calculator": "calculator" in tool_ids,
            "verification_or_valid_answer": (
                "cross_check_evidence" in tool_ids
                or bool(record.verification and record.verification.valid)
            ),
        }
    if mechanism_id == MECHANISM_IDS[0]:
        return {
            "multiple_information_actions": sum(
                item in {"search_archive", "query_structured_fact"} for item in tool_ids
            )
            >= 2,
            "evidence_joined": len({eid for item in successful for eid in item.evidence_ids}) >= 2,
            "verification_action": "cross_check_evidence" in tool_ids,
        }
    if mechanism_id == MECHANISM_IDS[1]:
        return {
            "typed_failure_observed": bool(failed),
            "argument_retry_observed": _failure_followed_by_retry(observations),
            "post_retry_success": bool(successful) and bool(failed),
        }
    if mechanism_id == MECHANISM_IDS[2]:
        calculator_steps = tuple(item for item in successful if item.call.tool_id == "calculator")
        return {
            "normalization_before_calculation": (
                "normalize_metric_unit_period" in tool_ids
                and "calculator" in tool_ids
                and tool_ids.index("normalize_metric_unit_period") < tool_ids.index("calculator")
            ),
            "three_dependent_calculations": len(calculator_steps) >= 3,
            "intermediate_lineage": _has_operation_reference_chain(calculator_steps),
        }
    if mechanism_id == MECHANISM_IDS[3]:
        normalized = tuple(
            item for item in successful if item.call.tool_id == "normalize_metric_unit_period"
        )
        return {
            "semantic_context_inspected": bool(successful),
            "compatibility_rule_applied": bool(normalized),
            "compatibility_decision_verified": "cross_check_evidence" in tool_ids,
        }
    if mechanism_id == MECHANISM_IDS[4]:
        return {
            "independent_replay": "calculator" in tool_ids,
            "candidate_cross_checked": "cross_check_evidence" in tool_ids,
            "answer_emitted_after_check": bool(steps and steps[-1].action == ActionType.ANSWER),
        }
    if mechanism_id == MECHANISM_IDS[5]:
        return {
            "typed_failure_observed": bool(failed),
            "failure_specific_retry": _failure_followed_by_retry(observations),
            "post_repair_verification": ("cross_check_evidence" in tool_ids and bool(failed)),
        }
    if mechanism_id == MECHANISM_IDS[6]:
        verification = record.verification
        return {
            "completeness_check": "cross_check_evidence" in tool_ids,
            "all_required_roles_resolved": bool(
                verification and verification.evidence_provenance_completeness == 1.0
            ),
            "stop_decision_quality": bool(verification and verification.stop_decision_quality),
        }
    raise ValueError(f"unknown mechanism: {mechanism_id}")


def _failure_followed_by_retry(observations: Sequence[Any]) -> bool:
    for index, item in enumerate(observations):
        if item.status != "failed":
            continue
        return any(
            later.call.tool_id == item.call.tool_id and later.status == "succeeded"
            for later in observations[index + 1 :]
        )
    return False


def _has_operation_reference_chain(observations: Sequence[Any]) -> bool:
    references: set[str] = set()
    chained = 0
    for item in observations:
        arguments = item.call.arguments
        if _contains_operation_reference(arguments, references):
            chained += 1
        result = item.result.get("result")
        if isinstance(result, Mapping):
            operation_ref = result.get("operation_ref")
            if isinstance(operation_ref, str):
                references.add(operation_ref)
    return chained >= 2


def _contains_operation_reference(value: Any, references: set[str]) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_operation_reference(item, references) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_operation_reference(item, references) for item in value)
    return isinstance(value, str) and value in references


def _cell_summaries(
    behaviors: Sequence[MechanismBehaviorObservation],
) -> tuple[MechanismCellSummary, ...]:
    grouped: dict[tuple[str, MechanismTier, VariantRole], list[MechanismBehaviorObservation]] = (
        defaultdict(list)
    )
    for item in behaviors:
        grouped[(item.mechanism_id, item.mechanism_tier, item.variant_role)].append(item)
    rows = []
    for (mechanism_id, tier, role), values in sorted(grouped.items()):
        eligible = tuple(item for item in values if item.runtime_eligible)
        evaluable = tuple(item for item in values if item.mechanism_evaluable)
        successes = sum(item.mechanism_success for item in evaluable)
        lower, upper = _wilson(successes, len(evaluable))
        rows.append(
            MechanismCellSummary(
                mechanism_id=mechanism_id,
                mechanism_tier=tier,
                variant_role=role,
                attempted_count=len(values),
                runtime_eligible_count=len(eligible),
                runtime_eligibility_rate=len(eligible) / len(values),
                semantic_accuracy_given_runtime_eligible=_rate(
                    item.semantic_answer_correct for item in eligible
                ),
                valid_success_rate=_rate(item.valid_success for item in values),
                mechanism_evaluable_count=len(evaluable),
                mechanism_success_rate_given_evaluable=_rate(
                    item.mechanism_success for item in evaluable
                ),
                mechanism_success_wilson_lower=lower,
                mechanism_success_wilson_upper=upper,
                mean_tool_call_count=sum(
                    item.failed_tool_call_count + item.successful_tool_call_count for item in values
                )
                / len(values),
                mean_decision_depth=sum(item.decision_depth for item in values) / len(values),
            )
        )
    return tuple(rows)


def _matched_effects(
    contract: FinanceCapabilityMechanismFlashContract,
    behaviors: Sequence[MechanismBehaviorObservation],
) -> tuple[MatchedMechanismEffect, ...]:
    grouped: dict[tuple[str, MechanismTier], list[str]] = defaultdict(list)
    for task_id, group_id in contract.task_group_ids.items():
        key = (
            contract.task_mechanism_ids[task_id],
            contract.task_mechanism_tiers[task_id],
        )
        if group_id not in grouped[key]:
            grouped[key].append(group_id)
    by_group_role: dict[tuple[str, VariantRole], list[MechanismBehaviorObservation]] = defaultdict(
        list
    )
    for item in behaviors:
        by_group_role[(item.group_id, item.variant_role)].append(item)
    rows = []
    for (mechanism_id, tier), group_ids in sorted(grouped.items()):
        control_rates = []
        mechanism_rates = []
        informative = 0
        boundary = 0
        for group_id in group_ids:
            controls = by_group_role[(group_id, "resolved_control")]
            mechanisms = by_group_role[(group_id, "mechanism_required")]
            control_rate = _rate(item.valid_success for item in controls)
            mechanism_rate = _rate(item.valid_success for item in mechanisms)
            control_rates.append(control_rate)
            mechanism_rates.append(mechanism_rate)
            informative += not math.isclose(control_rate, mechanism_rate)
            boundary += 0.0 < mechanism_rate < 1.0
        rows.append(
            MatchedMechanismEffect(
                mechanism_id=mechanism_id,
                mechanism_tier=tier,
                matched_group_count=len(group_ids),
                control_success_rate=sum(control_rates) / len(control_rates),
                mechanism_success_rate=sum(mechanism_rates) / len(mechanism_rates),
                mechanism_requirement_penalty=(
                    sum(control_rates) / len(control_rates)
                    - sum(mechanism_rates) / len(mechanism_rates)
                ),
                informative_group_count=informative,
                boundary_group_count=boundary,
            )
        )
    return tuple(rows)


def _selection_decisions(
    contract: FinanceCapabilityMechanismFlashContract,
    behaviors: Sequence[MechanismBehaviorObservation],
    runtime_passed: bool,
) -> tuple[MechanismSelectionDecision, ...]:
    rows = []
    for mechanism_id in MECHANISM_IDS:
        scoped = tuple(
            item
            for item in behaviors
            if item.mechanism_id == mechanism_id and item.mechanism_tier in {"bridge", "frontier"}
        )
        group_ids = sorted({item.group_id for item in scoped})
        informative = 0
        control_supported = 0
        mechanism_nonzero = 0
        boundary = 0
        matched_differences = 0
        for group_id in group_ids:
            controls = tuple(
                item
                for item in scoped
                if item.group_id == group_id
                and item.variant_role == "resolved_control"
                and item.runtime_eligible
            )
            mechanisms = tuple(
                item
                for item in scoped
                if item.group_id == group_id
                and item.variant_role == "mechanism_required"
                and item.runtime_eligible
            )
            control_rate = _rate(item.valid_success for item in controls)
            mechanism_rate = _rate(item.valid_success for item in mechanisms)
            differs = not math.isclose(control_rate, mechanism_rate)
            control_supported += control_rate > 0.0
            mechanism_nonzero += mechanism_rate > 0.0
            boundary += 0.0 < mechanism_rate < 1.0
            matched_differences += differs
            informative += mechanism_rate > 0.0 or differs
        mechanism_scoped = tuple(
            item for item in scoped if item.variant_role == "mechanism_required"
        )
        behavior_successes = sum(item.mechanism_success for item in mechanism_scoped)
        behavior_success_rate = _rate(item.mechanism_success for item in mechanism_scoped)
        matched = matched_differences >= 2 and behavior_successes >= 2
        selected = (
            runtime_passed
            and control_supported >= 4
            and mechanism_nonzero >= 2
            and boundary >= 1
            and matched
        )
        reasons = []
        if not runtime_passed:
            reasons.append("runtime_not_qualified")
        if control_supported < 4:
            reasons.append("resolved_control_support_is_too_low")
        if mechanism_nonzero < 2:
            reasons.append("mechanism_response_is_at_floor")
        if boundary < 1:
            reasons.append("no_bridge_frontier_boundary_group")
        if not matched:
            if matched_differences < 2:
                reasons.append("insufficient_matched_outcome_differences")
            if behavior_successes < 2:
                reasons.append("mechanism_specific_behavior_not_observed")
        rows.append(
            MechanismSelectionDecision(
                mechanism_id=mechanism_id,
                runtime_qualified=runtime_passed,
                bridge_or_frontier_evaluable_count=sum(
                    item.mechanism_evaluable for item in mechanism_scoped
                ),
                bridge_or_frontier_informative_group_count=informative,
                bridge_or_frontier_control_supported_group_count=control_supported,
                bridge_or_frontier_mechanism_nonzero_group_count=mechanism_nonzero,
                bridge_or_frontier_boundary_group_count=boundary,
                bridge_or_frontier_matched_difference_group_count=matched_differences,
                bridge_or_frontier_mechanism_behavior_success_count=behavior_successes,
                bridge_or_frontier_mechanism_behavior_success_rate=behavior_success_rate,
                matched_behavior_detected=matched,
                selected_for_confirmation=selected,
                reasons=tuple(reasons),
            )
        )
    return tuple(rows)


def _make_terminals(
    contract: FinanceCapabilityMechanismFlashContract,
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
) -> tuple[RuntimeTerminalOutcome, ...]:
    if len(records) != contract.requested_rollout_count or len(outcomes) != len(records):
        raise ValueError("mechanism Development has an incomplete Runtime denominator")
    record_by_key = {(item.binding_id, item.replicate): item for item in records}
    outcome_by_key = {(item.binding_id, item.replicate): item for item in outcomes}
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    if set(record_by_key) != set(outcome_by_key):
        raise ValueError("mechanism records and outcomes differ")
    return tuple(
        _make_terminal_outcome(
            cast(Any, contract),
            record_by_key[key],
            outcome_by_key[key],
            binding_by_id[key[0]],
        )
        for key in sorted(record_by_key)
    )


def _record_observations(record: CapabilityBoundaryRolloutRecord) -> tuple[Any, ...]:
    return record.observations


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        root
        / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_mechanism_ir.py",
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_mechanism_development.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_multitier_capability_population.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_multitier_confirmation.py"
        ),
        root / "src/trusted_synthesis/runtime/agent/iterative.py",
        root / "src/trusted_synthesis/runtime/agent/llm_agent.py",
        root / "src/trusted_synthesis/runtime/tools.py",
        root / "src/trusted_synthesis/domains/finance/interactive_agent_runtime.py",
        root / "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
        root / "src/trusted_synthesis/core/evaluation/answer.py",
        root / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary.py",
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary_runner.py"
        ),
    )
    return {str(path.relative_to(root)): _sha256(path) for path in paths}


def _verify_inputs(contract: FinanceCapabilityMechanismFlashContract) -> None:
    pairs = (
        (contract.source_population_path, contract.source_population_sha256),
        (contract.source_v25_20_contract_path, contract.source_v25_20_contract_sha256),
        (contract.finance_archive_config_path, contract.finance_archive_config_sha256),
    )
    for path_value, expected in pairs:
        if _sha256(Path(path_value)) != expected:
            raise ValueError(f"mechanism Development frozen input changed:{path_value}")
    implementation = _implementation_manifest()
    if implementation != contract.implementation_manifest:
        raise ValueError("mechanism Development implementation changed after contract freeze")
    if contract.implementation_manifest_hash != canonical_hash(
        implementation,
        prefix="finance_capability_mechanism_implementation:",
    ):
        raise ValueError("mechanism Development implementation hash is invalid")
    population = CapabilityMechanismDevelopmentPopulation.model_validate_json(
        Path(contract.source_population_path).read_text(encoding="utf-8")
    )
    if population.population_id != contract.source_population_id:
        raise ValueError("mechanism Development loaded another population")


def _wilson(successes: int, count: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if count == 0:
        return 0.0, 1.0
    p = successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    margin = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _rate(values: Sequence[bool] | Any) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def _render_report(value: FinanceCapabilityMechanismFlashReport) -> str:
    lines = [
        "# Finance v25.21 Flash Capability Mechanism Development Report",
        "",
        "## Decision",
        "",
        f"- Report ID: `{value.report_id}`",
        f"- Rollouts: **{value.recorded_rollout_count}/{value.requested_rollout_count}**",
        f"- Runtime qualification: **{value.runtime_qualification_passed}**",
        f"- Selected mechanisms: **{len(value.selected_mechanism_ids)}**",
        f"- Next permitted stage: `{value.next_permitted_stage}`",
        "- Pro calls: **0**",
        "- Beneficiary / Exact Target / GP-C: **not authorized**",
        "",
        "## Runtime Instrument",
        "",
        f"- API transport resolution: **{value.api_transport_resolution_rate:.2%}**",
        f"- Bounded JSON resolution: **{value.bounded_json_resolution_rate:.2%}**",
        f"- Observation replay: **{value.observation_replay_rate:.2%}**",
        f"- Authority integrity: **{value.authority_integrity_rate:.2%}**",
        f"- Runtime pathology: **{value.runtime_pathology_rate:.2%}**",
        "",
        "Correctness is reported as a capability outcome, not a Runtime gate:",
        "",
        (
            f"- Semantic accuracy given Runtime eligible: "
            f"**{value.semantic_accuracy_given_runtime_eligible:.2%}**"
        ),
        f"- End-to-end valid success: **{value.end_to_end_valid_success_rate:.2%}**",
        "",
        "## Mechanism Selection",
        "",
        (
            "| Mechanism | Bridge/Frontier evaluable | Informative groups | "
            "Boundary groups | Selected |"
        ),
        "|---|---:|---:|---:|---:|",
    ]
    for item in value.selection_decisions:
        lines.append(
            f"| `{item.mechanism_id}` | {item.bridge_or_frontier_evaluable_count} | "
            f"{item.bridge_or_frontier_informative_group_count} | "
            f"{item.bridge_or_frontier_boundary_group_count} | "
            f"{item.selected_for_confirmation} |"
        )
    lines.extend(
        (
            "",
            "## Interpretation",
            "",
            "The Development stage compares mechanism-required tasks against matched resolved "
            "controls with identical Programs, Gold answers, Evidence, public Corpus, and answer "
            "schema. Runtime qualification excludes semantic correctness. Mechanism behavior is "
            "replayed from Host-owned tool observations and verified trajectories.",
            "",
            "Selection only permits a fresh Flash Confirmation population. It does not authorize "
            "Pro ranking, Beneficiary screening, Exact Target, GP-C, or VTDO updates.",
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


def _write_jsonl_atomic(path: Path, values: Any) -> None:
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
        description="Prepare or run v25.21 Flash capability mechanism Development."
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
    run.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "prepare":
        result: Any = prepare_mechanism_flash_development(
            source_population_path=args.source_population,
            source_v25_20_contract_path=args.source_v25_20_contract,
            output_path=args.output_path,
            run_id=args.run_id,
        )
        summary = {
            "contract_id": result.contract_id,
            "task_count": len(result.tasks),
            "binding_count": len(result.bindings),
            "requested_rollout_count": result.requested_rollout_count,
            "next_permitted_stage": result.next_permitted_stage,
        }
    else:
        result = run_mechanism_flash_development(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        summary = {
            "report_id": result.report_id,
            "recorded_rollout_count": result.recorded_rollout_count,
            "requested_rollout_count": result.requested_rollout_count,
            "runtime_qualification_passed": result.runtime_qualification_passed,
            "selected_mechanism_ids": result.selected_mechanism_ids,
            "next_permitted_stage": result.next_permitted_stage,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
