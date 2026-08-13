from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPackage, TaskPublicSpec
from trusted_synthesis.domains.finance.agent_tools import (
    FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
)
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FAMILIES,
    CapabilitySensitiveTaskArtifact,
    capability_sensitive_task_artifact_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_capability_population import (
    FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION,
    MultiTierCapabilityPopulation,
    _public_contract_metadata,
    finance_operation_execution_contract,
    finance_public_calculation_instruction,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    WORKFLOW_RUNTIME_ARMS,
    FinanceMultiTierConfirmationContract,
    FinanceMultiTierFlashReport,
    _execute_stage,
    _outcome_set_hash,
    _write_immutable_json,
    _write_immutable_model,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
    ITERATIVE_AGENT_SOLVER_VERSION,
    IterativeAgentProtocolProfile,
)

RUNTIME_REPAIR_CALIBRATION_VERSION = "finance_multitier_runtime_repair_calibration.v4"
RUNTIME_REPAIR_REPORT_VERSION = "finance_multitier_runtime_repair_report.v4"
RUNTIME_REPAIR_RUNNER_VERSION = "finance_multitier_runtime_repair_runner.v4"
FAILURE_REPAIR_POLICY_VERSION = "agent_failure_repair_policy.v4"
CALIBRATION_GROUP_COUNT = len(CAPABILITY_SENSITIVE_FAMILIES)
CALIBRATION_TASK_COUNT = CALIBRATION_GROUP_COUNT * len(DifficultyTier)
CALIBRATION_BINDING_COUNT = CALIBRATION_TASK_COUNT * len(WORKFLOW_RUNTIME_ARMS)
CALIBRATION_REPLICAS = 2
CALIBRATION_ROLLOUT_COUNT = CALIBRATION_BINDING_COUNT * CALIBRATION_REPLICAS
CALIBRATION_MODEL_TOKEN_BUDGET = 120_000


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceRuntimeRepairCalibrationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
    source_confirmation_contract_path: str = Field(min_length=1)
    source_confirmation_contract_sha256: str = Field(min_length=64, max_length=64)
    source_confirmation_contract_id: str = Field(min_length=1)
    source_flash_report_path: str = Field(min_length=1)
    source_flash_report_sha256: str = Field(min_length=64, max_length=64)
    source_flash_report_id: str = Field(min_length=1)
    source_records_path: str = Field(min_length=1)
    source_records_sha256: str = Field(min_length=64, max_length=64)
    source_outcomes_path: str = Field(min_length=1)
    source_outcomes_sha256: str = Field(min_length=64, max_length=64)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    iterative_agent_solver_version: str = ITERATIVE_AGENT_SOLVER_VERSION
    iterative_agent_decision_prompt_version: str = ITERATIVE_AGENT_DECISION_PROMPT_VERSION
    finance_interactive_runtime_version: str = FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION
    finance_agent_toolset_version: str = FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION
    operation_execution_contract_version: str = FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION
    failure_repair_policy_version: str = FAILURE_REPAIR_POLICY_VERSION
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=1, max_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    selected_group_ids: dict[str, str] = Field(
        min_length=CALIBRATION_GROUP_COUNT,
        max_length=CALIBRATION_GROUP_COUNT,
    )
    repaired_tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(
        min_length=CALIBRATION_TASK_COUNT,
        max_length=CALIBRATION_TASK_COUNT,
    )
    source_task_artifact_ids: dict[str, str] = Field(
        min_length=CALIBRATION_TASK_COUNT,
        max_length=CALIBRATION_TASK_COUNT,
    )
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=CALIBRATION_BINDING_COUNT,
        max_length=CALIBRATION_BINDING_COUNT,
    )
    replicas: int = Field(default=CALIBRATION_REPLICAS, ge=2, le=2)
    requested_rollout_count: int = Field(
        default=CALIBRATION_ROLLOUT_COUNT,
        ge=CALIBRATION_ROLLOUT_COUNT,
        le=CALIBRATION_ROLLOUT_COUNT,
    )
    maximum_model_tokens_per_rollout: int = Field(
        default=CALIBRATION_MODEL_TOKEN_BUDGET,
        ge=CALIBRATION_MODEL_TOKEN_BUDGET,
        le=CALIBRATION_MODEL_TOKEN_BUDGET,
    )
    model_contract_repair_attempts: int = Field(default=2, ge=2, le=2)
    selection_salt: str = Field(min_length=1)
    development_only: Literal[True] = True
    source_confirmation_reuse_declared: Literal[True] = True
    pro_api_calls_authorized: Literal[False] = False
    information_matrix_evaluation_authorized: Literal[False] = False
    model_ranking_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = RUNTIME_REPAIR_CALIBRATION_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceRuntimeRepairCalibrationContract:
        if self.schema_version != RUNTIME_REPAIR_CALIBRATION_VERSION:
            raise ValueError("runtime-repair calibration version is unsupported")
        if (
            self.iterative_agent_solver_version != ITERATIVE_AGENT_SOLVER_VERSION
            or self.iterative_agent_decision_prompt_version
            != ITERATIVE_AGENT_DECISION_PROMPT_VERSION
            or self.finance_interactive_runtime_version
            != FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION
            or self.finance_agent_toolset_version != FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION
            or self.operation_execution_contract_version
            != FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION
            or self.failure_repair_policy_version != FAILURE_REPAIR_POLICY_VERSION
        ):
            raise ValueError("runtime-repair implementation identity is stale")
        if set(self.selected_group_ids) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("runtime-repair calibration omits a capability family")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("runtime-repair calibration is Flash-only")
        task_ids = {item.artifact_id for item in self.repaired_tasks}
        if len(task_ids) != CALIBRATION_TASK_COUNT:
            raise ValueError("runtime-repair calibration duplicates a repaired task")
        if set(self.source_task_artifact_ids) != task_ids:
            raise ValueError("runtime-repair source-task lineage is incomplete")
        counts = Counter((item.family, item.tier) for item in self.repaired_tasks)
        if counts != Counter(
            {
                (family, tier): 1
                for family in CAPABILITY_SENSITIVE_FAMILIES
                for tier in DifficultyTier
            }
        ):
            raise ValueError("runtime-repair tasks are not family/Tier balanced")
        binding_ids = {item.binding_id for item in self.bindings}
        if len(binding_ids) != CALIBRATION_BINDING_COUNT:
            raise ValueError("runtime-repair calibration duplicates a binding")
        binding_counts = Counter(
            (item.task_artifact_id, item.runtime_arm) for item in self.bindings
        )
        if (
            set(binding_counts.values()) != {1}
            or set(item.task_artifact_id for item in self.bindings) != task_ids
        ):
            raise ValueError("runtime-repair tasks lack one binding per workflow Runtime")
        if {item.runtime_arm for item in self.bindings} != set(WORKFLOW_RUNTIME_ARMS):
            raise ValueError("runtime-repair calibration includes another Runtime")
        for item in self.repaired_tasks:
            guidance = item.task.public.metadata.get("agent_contract_guidance")
            if not isinstance(guidance, Mapping):
                raise ValueError("runtime-repair task lacks public Agent guidance")
            observed = guidance.get("operation_execution_contract")
            expected = finance_operation_execution_contract(
                family=item.family,
                tier=item.tier,
                gold=item.evidence_bundle.evidence,
                program=item.task.oracle.task_program,
            )
            if canonical_hash(observed) != canonical_hash(expected):
                raise ValueError(
                    "runtime-repair public Operation Contract differs from Oracle Program"
                )
        if self.contract_id != runtime_repair_calibration_contract_id(self):
            raise ValueError("runtime-repair calibration identity is invalid")
        return self


class RuntimeRepairMetrics(FrozenModel):
    attempted_count: int = Field(ge=1)
    completed_trajectory_rate: float = Field(ge=0, le=1)
    terminal_resolution_rate: float = Field(ge=0, le=1)
    raw_json_contract_rate: float = Field(ge=0, le=1)
    bounded_json_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    budget_success_rate: float = Field(ge=0, le=1)
    infrastructure_success_rate: float = Field(ge=0, le=1)
    full_technical_pass_rate: float = Field(ge=0, le=1)
    deterministic_valid_rate: float = Field(ge=0, le=1)
    semantic_answer_correct_rate: float = Field(ge=0, le=1)
    valid_success_rate: float = Field(ge=0, le=1)
    repeated_failed_call_rate: float = Field(ge=0, le=1)
    recovery_success_rate_given_opportunity: float = Field(ge=0, le=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    failure_code_counts: dict[str, int]


class RuntimeRepairCell(FrozenModel):
    family: str = Field(min_length=1)
    tier: DifficultyTier
    runtime_arm: CapabilityRuntimeArm
    source: RuntimeRepairMetrics
    repaired: RuntimeRepairMetrics
    full_technical_rate_delta: float
    valid_success_rate_delta: float
    repeated_failed_call_rate_delta: float


class FinanceRuntimeRepairCalibrationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    source_flash_report_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=1)
    source_rollout_count: int = Field(ge=1)
    source_metrics: RuntimeRepairMetrics
    repaired_metrics: RuntimeRepairMetrics
    cells: tuple[RuntimeRepairCell, ...] = Field(
        min_length=CALIBRATION_BINDING_COUNT,
        max_length=CALIBRATION_BINDING_COUNT,
    )
    technical_repair_passed: bool
    semantic_direction_improved: bool
    repeated_failure_reduced: bool
    outcome_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pro_api_call_count: Literal[0] = 0
    information_matrix_evaluated: Literal[False] = False
    model_ranking_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "fresh_flash_runtime_confirmation",
        "runtime_contract_repair_only",
    ]
    schema_version: str = RUNTIME_REPAIR_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceRuntimeRepairCalibrationReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("runtime-repair report lacks its complete denominator")
        ready = (
            self.technical_repair_passed
            and self.semantic_direction_improved
            and self.repeated_failure_reduced
        )
        expected = "fresh_flash_runtime_confirmation" if ready else "runtime_contract_repair_only"
        if self.next_permitted_stage != expected:
            raise ValueError("runtime-repair report is not fail-closed")
        if self.report_id != runtime_repair_calibration_report_id(self):
            raise ValueError("runtime-repair report identity is invalid")
        return self


def prepare_runtime_repair_calibration(
    *,
    source_population_path: Path,
    source_confirmation_contract_path: Path,
    source_flash_report_path: Path,
    source_records_path: Path,
    source_outcomes_path: Path,
    output_path: Path,
    run_id: str,
    selection_salt: str,
) -> FinanceRuntimeRepairCalibrationContract:
    if output_path.exists():
        raise ValueError("runtime-repair calibration contract is immutable and exists")
    paths = tuple(
        item.resolve()
        for item in (
            source_population_path,
            source_confirmation_contract_path,
            source_flash_report_path,
            source_records_path,
            source_outcomes_path,
        )
    )
    population_path, confirmation_path, report_path, records_path, outcomes_path = paths
    population = MultiTierCapabilityPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    confirmation = FinanceMultiTierConfirmationContract.model_validate_json(
        confirmation_path.read_text(encoding="utf-8")
    )
    report = FinanceMultiTierFlashReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    if (
        confirmation.population_id != population.population_id
        or report.contract_id != confirmation.contract_id
        or report.next_permitted_stage != "runtime_contract_repair_only"
        or report.pro_stage_authorized
    ):
        raise ValueError("runtime-repair calibration lacks the frozen failed Flash stage")
    selected = _select_groups(population, selection_salt)
    repaired: list[CapabilitySensitiveTaskArtifact] = []
    source_ids: dict[str, str] = {}
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        group = selected[family]
        for source in sorted(group.variants, key=lambda item: item.tier.value):
            task = _repair_task(source, run_id=run_id)
            repaired.append(task)
            source_ids[task.artifact_id] = source.artifact_id
    repaired_tasks = tuple(sorted(repaired, key=lambda item: (item.family, item.tier.value)))
    bindings = tuple(
        _make_runtime_binding(task, runtime, confirmation.protocol_profile)
        for task in repaired_tasks
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    flash = next(item for item in confirmation.model_contracts if item.arm == ExplorerArm.FLASH)
    finance_config = Path(confirmation.finance_archive_config_path).resolve()
    values = {
        "run_id": run_id,
        "source_population_path": str(population_path),
        "source_population_sha256": _sha256(population_path),
        "source_population_id": population.population_id,
        "source_confirmation_contract_path": str(confirmation_path),
        "source_confirmation_contract_sha256": _sha256(confirmation_path),
        "source_confirmation_contract_id": confirmation.contract_id,
        "source_flash_report_path": str(report_path),
        "source_flash_report_sha256": _sha256(report_path),
        "source_flash_report_id": report.report_id,
        "source_records_path": str(records_path),
        "source_records_sha256": _sha256(records_path),
        "source_outcomes_path": str(outcomes_path),
        "source_outcomes_sha256": _sha256(outcomes_path),
        "finance_archive_config_path": str(finance_config),
        "finance_archive_config_sha256": _sha256(finance_config),
        "iterative_agent_solver_version": ITERATIVE_AGENT_SOLVER_VERSION,
        "iterative_agent_decision_prompt_version": ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
        "finance_interactive_runtime_version": FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
        "finance_agent_toolset_version": FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
        "operation_execution_contract_version": FINANCE_OPERATION_EXECUTION_CONTRACT_VERSION,
        "failure_repair_policy_version": FAILURE_REPAIR_POLICY_VERSION,
        "model_contracts": (flash,),
        "protocol_profile": confirmation.protocol_profile,
        "selected_group_ids": {
            family: selected[family].group_id for family in CAPABILITY_SENSITIVE_FAMILIES
        },
        "repaired_tasks": repaired_tasks,
        "source_task_artifact_ids": source_ids,
        "bindings": bindings,
        "replicas": CALIBRATION_REPLICAS,
        "requested_rollout_count": CALIBRATION_ROLLOUT_COUNT,
        "maximum_model_tokens_per_rollout": CALIBRATION_MODEL_TOKEN_BUDGET,
        "model_contract_repair_attempts": confirmation.model_contract_repair_attempts,
        "selection_salt": selection_salt,
    }
    provisional = FinanceRuntimeRepairCalibrationContract.model_construct(
        contract_id="pending", **values
    )
    contract = FinanceRuntimeRepairCalibrationContract(
        contract_id=runtime_repair_calibration_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_runtime_repair_calibration(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceRuntimeRepairCalibrationReport:
    contract = FinanceRuntimeRepairCalibrationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_frozen_inputs(contract)
    outcomes, discovered = _execute_stage(
        contract=contract,
        tasks={item.artifact_id: item for item in contract.repaired_tasks},
        bindings=contract.bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=contract.replicas,
        output_dir=output_dir,
        prefix="runtime_repair_calibration",
        workers=workers,
    )
    records_path = output_dir / "runtime_repair_calibration_records.jsonl"
    records = _load_records(records_path)
    report = make_runtime_repair_report(contract, records, outcomes)
    report_path = output_dir / "finance_runtime_repair_calibration_report.json"
    _write_immutable_model(report_path, report)
    _write_immutable_json(
        output_dir / "runtime_repair_calibration_manifest.json",
        {
            "contract_id": contract.contract_id,
            "runner_version": RUNTIME_REPAIR_RUNNER_VERSION,
            "requested_model": contract.model_contracts[0].requested_model,
            "discovered_models": discovered,
            "records_sha256": _sha256(records_path),
            "outcomes_sha256": _sha256(output_dir / "runtime_repair_calibration_outcomes.jsonl"),
            "report_id": report.report_id,
            "report_sha256": _sha256(report_path),
            "pro_api_call_count": 0,
        },
    )
    return report


def make_runtime_repair_report(
    contract: FinanceRuntimeRepairCalibrationContract,
    records: tuple[CapabilityBoundaryRolloutRecord, ...],
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> FinanceRuntimeRepairCalibrationReport:
    if len(records) != contract.requested_rollout_count or len(outcomes) != len(records):
        raise ValueError("runtime-repair calibration has an incomplete denominator")
    source_records = _load_records(Path(contract.source_records_path))
    source_outcomes = _load_outcomes(Path(contract.source_outcomes_path))
    source_ids = set(contract.source_task_artifact_ids.values())
    source_records = tuple(item for item in source_records if item.task_artifact_id in source_ids)
    source_outcomes = tuple(item for item in source_outcomes if item.task_artifact_id in source_ids)
    source_metrics = _metrics(source_records, source_outcomes)
    repaired_metrics = _metrics(records, outcomes)
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    repaired_by_key = {
        (item.family, item.tier, runtime): item.artifact_id
        for item in contract.repaired_tasks
        for runtime in WORKFLOW_RUNTIME_ARMS
    }
    source_by_repaired = contract.source_task_artifact_ids
    cells = []
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        for tier in DifficultyTier:
            for runtime in WORKFLOW_RUNTIME_ARMS:
                repaired_id = repaired_by_key[(family, tier, runtime)]
                source_id = source_by_repaired[repaired_id]
                repaired_bindings = {
                    item.binding_id
                    for item in contract.bindings
                    if item.task_artifact_id == repaired_id and item.runtime_arm == runtime
                }
                source_cell_records = tuple(
                    item
                    for item in source_records
                    if item.task_artifact_id == source_id and item.runtime_arm == runtime
                )
                source_cell_outcomes = tuple(
                    item
                    for item in source_outcomes
                    if item.task_artifact_id == source_id and item.runtime_arm == runtime
                )
                repaired_cell_records = tuple(
                    item for item in records if item.binding_id in repaired_bindings
                )
                repaired_cell_outcomes = tuple(
                    item for item in outcomes if item.binding_id in repaired_bindings
                )
                if any(
                    binding_by_id[item.binding_id].tier != tier for item in repaired_cell_outcomes
                ):
                    raise ValueError("runtime-repair report crossed Tier identities")
                before = _metrics(source_cell_records, source_cell_outcomes)
                after = _metrics(repaired_cell_records, repaired_cell_outcomes)
                cells.append(
                    RuntimeRepairCell(
                        family=family,
                        tier=tier,
                        runtime_arm=runtime,
                        source=before,
                        repaired=after,
                        full_technical_rate_delta=round(
                            after.full_technical_pass_rate - before.full_technical_pass_rate,
                            9,
                        ),
                        valid_success_rate_delta=round(
                            after.valid_success_rate - before.valid_success_rate,
                            9,
                        ),
                        repeated_failed_call_rate_delta=round(
                            after.repeated_failed_call_rate - before.repeated_failed_call_rate,
                            9,
                        ),
                    )
                )
    technical = bool(
        repaired_metrics.full_technical_pass_rate >= 0.95
        and repaired_metrics.bounded_json_rate == 1.0
        and repaired_metrics.observation_replay_rate == 1.0
        and repaired_metrics.authority_integrity_rate == 1.0
        and repaired_metrics.budget_success_rate == 1.0
        and repaired_metrics.infrastructure_success_rate == 1.0
    )
    semantic = repaired_metrics.valid_success_rate > source_metrics.valid_success_rate
    repeated = repaired_metrics.repeated_failed_call_rate < source_metrics.repeated_failed_call_rate
    ready = technical and semantic and repeated
    values = {
        "contract_id": contract.contract_id,
        "source_flash_report_id": contract.source_flash_report_id,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(records),
        "source_rollout_count": len(source_records),
        "source_metrics": source_metrics,
        "repaired_metrics": repaired_metrics,
        "cells": tuple(cells),
        "technical_repair_passed": technical,
        "semantic_direction_improved": semantic,
        "repeated_failure_reduced": repeated,
        "outcome_set_hash": _outcome_set_hash(outcomes, "runtime_repair"),
        "api_call_count": repaired_metrics.api_call_count,
        "total_model_tokens": repaired_metrics.total_model_tokens,
        "estimated_cost_usd": repaired_metrics.estimated_cost_usd,
        "next_permitted_stage": (
            "fresh_flash_runtime_confirmation" if ready else "runtime_contract_repair_only"
        ),
    }
    provisional = FinanceRuntimeRepairCalibrationReport.model_construct(
        report_id="pending", **values
    )
    return FinanceRuntimeRepairCalibrationReport(
        report_id=runtime_repair_calibration_report_id(provisional), **values
    )


def _select_groups(
    population: MultiTierCapabilityPopulation,
    salt: str,
) -> dict[str, Any]:
    output = {}
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        candidates = tuple(item for item in population.groups if item.family == family)
        if not candidates:
            raise ValueError(f"source population lacks {family}")
        output[family] = min(
            candidates,
            key=lambda item: canonical_hash(
                {"selection_salt": salt, "group_id": item.group_id},
                prefix="finance_runtime_repair_group_selection:",
            ),
        )
    return output


def _repair_task(
    source: CapabilitySensitiveTaskArtifact,
    *,
    run_id: str,
) -> CapabilitySensitiveTaskArtifact:
    gold = source.evidence_bundle.evidence
    repaired_metadata = _public_contract_metadata(
        family=source.family,
        tier=source.tier,
        gold=gold,
        program=source.task.oracle.task_program,
        answer_projection=source.answer_projection,
        recovery_branches=source.recovery_branches,
    )
    public_payload = source.task.public.model_dump(mode="json")
    public_payload.update(
        {
            "instruction": finance_public_calculation_instruction(
                source.task.public.instruction,
                family=source.family,
                tier=source.tier,
                gold=gold,
                program=source.task.oracle.task_program,
            ),
            "metadata": {
                **source.task.public.metadata,
                **repaired_metadata,
                "runtime_repair_calibration": {
                    "version": RUNTIME_REPAIR_CALIBRATION_VERSION,
                    "run_id": run_id,
                    "source_artifact_id": source.artifact_id,
                    "oracle_program_unchanged": True,
                    "public_evidence_unchanged": True,
                },
            },
        }
    )
    public = TaskPublicSpec.model_validate(public_payload)
    task_payload = source.task.model_dump(mode="json")
    task_payload["public"] = public.model_dump(mode="json")
    package = TaskPackage.model_validate(task_payload)
    provisional = source.model_copy(update={"artifact_id": "pending", "task": package})
    payload = source.model_dump(mode="json")
    payload.update(
        {
            "artifact_id": capability_sensitive_task_artifact_id(provisional),
            "task": package.model_dump(mode="json"),
        }
    )
    return CapabilitySensitiveTaskArtifact.model_validate(payload)


def _metrics(
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
) -> RuntimeRepairMetrics:
    if not records or len(records) != len(outcomes):
        raise ValueError("runtime-repair metric slice has an incomplete denominator")
    record_by_key = {(item.binding_id, item.replicate): item for item in records}
    outcome_by_key = {(item.binding_id, item.replicate): item for item in outcomes}
    if set(record_by_key) != set(outcome_by_key):
        raise ValueError("runtime-repair records and outcomes differ")
    count = len(records)
    full = 0
    repeated = 0
    failure_codes: Counter[str] = Counter()
    for key, record in record_by_key.items():
        outcome = outcome_by_key[key]
        full += int(
            record.status == "completed"
            and outcome.bounded_json_resolution_success
            and outcome.observation_replay_success
            and outcome.authority_integrity_success
            and not outcome.budget_exhausted
            and outcome.runtime_infrastructure_failure_count == 0
        )
        repeated_failed_call = bool(
            record.error_message
            and "repeated an identical failed tool call" in record.error_message
        )
        if repeated_failed_call:
            repeated += 1
            failure_codes["identical_failed_tool_call"] += 1
        if record.budget_exhausted:
            failure_codes["model_token_budget"] += 1
        if record.error_type and not record.budget_exhausted and not repeated_failed_call:
            failure_codes[f"runtime:{record.error_type}"] += 1
        payload = record.verification_payload or {}
        checks = payload.get("checks", ())
        if isinstance(checks, list):
            for check in checks:
                if isinstance(check, Mapping) and check.get("passed") is False:
                    failure_codes[f"verifier:{check.get('check_id', 'unknown')}"] += 1
    opportunities = sum(item.recovery_opportunity for item in outcomes)
    return RuntimeRepairMetrics(
        attempted_count=count,
        completed_trajectory_rate=_rate(sum(item.status == "completed" for item in records), count),
        terminal_resolution_rate=_rate(sum(item.completed for item in outcomes), count),
        raw_json_contract_rate=_rate(
            sum(item.raw_json_contract_success for item in outcomes), count
        ),
        bounded_json_rate=_rate(
            sum(item.bounded_json_resolution_success for item in outcomes), count
        ),
        observation_replay_rate=_rate(
            sum(item.observation_replay_success for item in outcomes), count
        ),
        authority_integrity_rate=_rate(
            sum(item.authority_integrity_success for item in outcomes), count
        ),
        budget_success_rate=_rate(sum(not item.budget_exhausted for item in outcomes), count),
        infrastructure_success_rate=_rate(
            sum(item.runtime_infrastructure_failure_count == 0 for item in outcomes),
            count,
        ),
        full_technical_pass_rate=_rate(full, count),
        deterministic_valid_rate=_rate(sum(item.deterministic_valid for item in outcomes), count),
        semantic_answer_correct_rate=_rate(
            sum(item.semantic_answer_correct for item in outcomes), count
        ),
        valid_success_rate=_rate(sum(item.valid_success for item in outcomes), count),
        repeated_failed_call_rate=_rate(repeated, count),
        recovery_success_rate_given_opportunity=(
            _rate(sum(item.recovery_success for item in outcomes), opportunities)
            if opportunities
            else 0.0
        ),
        api_call_count=sum(item.api_call_count for item in outcomes),
        total_model_tokens=sum(item.total_model_tokens for item in outcomes),
        estimated_cost_usd=round(sum(item.estimated_cost_usd for item in outcomes), 9),
        failure_code_counts=dict(sorted(failure_codes.items())),
    )


def runtime_repair_calibration_contract_id(
    value: FinanceRuntimeRepairCalibrationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_multitier_runtime_repair_calibration:",
    )


def runtime_repair_calibration_report_id(
    value: FinanceRuntimeRepairCalibrationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_multitier_runtime_repair_report:",
    )


def _verify_frozen_inputs(contract: FinanceRuntimeRepairCalibrationContract) -> None:
    for path, expected in (
        (Path(contract.source_population_path), contract.source_population_sha256),
        (
            Path(contract.source_confirmation_contract_path),
            contract.source_confirmation_contract_sha256,
        ),
        (Path(contract.source_flash_report_path), contract.source_flash_report_sha256),
        (Path(contract.source_records_path), contract.source_records_sha256),
        (Path(contract.source_outcomes_path), contract.source_outcomes_sha256),
        (Path(contract.finance_archive_config_path), contract.finance_archive_config_sha256),
    ):
        if _sha256(path) != expected:
            raise ValueError(f"frozen runtime-repair input changed:{path}")


def _load_records(path: Path) -> tuple[CapabilityBoundaryRolloutRecord, ...]:
    return tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _load_outcomes(path: Path) -> tuple[CapabilityRolloutOutcome, ...]:
    return tuple(
        CapabilityRolloutOutcome.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise ValueError("rate denominator must be positive")
    return round(numerator / denominator, 9)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or run the v25.16 Flash-only Operation Contract calibration."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-population", type=Path, required=True)
    prepare.add_argument("--source-contract", type=Path, required=True)
    prepare.add_argument("--source-report", type=Path, required=True)
    prepare.add_argument("--source-records", type=Path, required=True)
    prepare.add_argument("--source-outcomes", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--selection-salt", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--workers", type=int, default=24)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        contract = prepare_runtime_repair_calibration(
            source_population_path=args.source_population,
            source_confirmation_contract_path=args.source_contract,
            source_flash_report_path=args.source_report,
            source_records_path=args.source_records,
            source_outcomes_path=args.source_outcomes,
            output_path=args.output,
            run_id=args.run_id,
            selection_salt=args.selection_salt,
        )
        print(
            json.dumps(
                {
                    "contract_id": contract.contract_id,
                    "task_count": len(contract.repaired_tasks),
                    "binding_count": len(contract.bindings),
                    "requested_rollout_count": contract.requested_rollout_count,
                    "pro_api_calls_authorized": contract.pro_api_calls_authorized,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    report = run_runtime_repair_calibration(
        contract_path=args.contract,
        output_dir=args.output_dir,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
