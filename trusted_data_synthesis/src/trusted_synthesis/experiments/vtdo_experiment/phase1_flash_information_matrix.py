from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    ConfidenceInterval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
    _symmetric_eigenvalues,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_tier_localization import (
    WORKFLOW_RUNTIME_ARMS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    FinanceRuntimeResolutionContract,
    FinanceRuntimeResolutionReport,
    RuntimeResolutionStage,
    RuntimeTerminalOutcome,
    make_runtime_resolution_report,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_workflow_information_audit import (
    WorkflowInformationThresholds,
)
from trusted_synthesis.hashing import canonical_hash

FLASH_INFORMATION_CONTRACT_VERSION = "finance_flash_information_matrix_contract.v2"
FLASH_INFORMATION_REPORT_VERSION = "finance_flash_information_matrix_report.v2"
FLASH_INFORMATION_CELL_VERSION = "finance_flash_information_matrix_cell.v2"
FLASH_INFORMATION_SPECTRUM_VERSION = "finance_flash_information_spectrum.v2"
FLASH_INFORMATION_RUNNER_VERSION = "finance_flash_information_matrix_runner.v2"
RESPONSE_VARIABLES = (*CAPABILITY_AXES, "final_valid")


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceFlashInformationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_runtime_contract_path: str = Field(min_length=1)
    source_runtime_contract_sha256: str = Field(min_length=64, max_length=64)
    source_runtime_contract_id: str = Field(min_length=1)
    source_runtime_report_path: str = Field(min_length=1)
    source_runtime_report_sha256: str = Field(min_length=64, max_length=64)
    source_runtime_report_id: str = Field(min_length=1)
    source_terminal_outcomes_path: str = Field(min_length=1)
    source_terminal_outcomes_sha256: str = Field(min_length=64, max_length=64)
    source_outcome_set_hash: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    thresholds: WorkflowInformationThresholds
    random_seed: int
    bootstrap_replicates: int = Field(ge=100)
    workflow_runtime_arms: tuple[CapabilityRuntimeArm, ...] = WORKFLOW_RUNTIME_ARMS
    response_variables: tuple[str, ...] = RESPONSE_VARIABLES
    outcome_conditioning: Literal["runtime_eligible_only"] = "runtime_eligible_only"
    probability_estimator: Literal["conditional_empirical_task_mean"] = (
        "conditional_empirical_task_mean"
    )
    demand_normalization: Literal["task_l2"] = "task_l2"
    general_factor_adjustment: Literal["linear_residualization"] = "linear_residualization"
    joint_matrix_policy: Literal["equal_observed_axis_mean"] = "equal_observed_axis_mean"
    final_valid_matrix_role: Literal["primary_authorizing"] = "primary_authorizing"
    axis_specific_matrix_role: Literal["diagnostic_non_authorizing"] = "diagnostic_non_authorizing"
    runner_version: str = FLASH_INFORMATION_RUNNER_VERSION
    pro_api_calls_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_information_matrix_evaluation"] = (
        "flash_information_matrix_evaluation"
    )
    schema_version: str = FLASH_INFORMATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceFlashInformationContract:
        if self.schema_version != FLASH_INFORMATION_CONTRACT_VERSION:
            raise ValueError("Flash information contract version is unsupported")
        if self.workflow_runtime_arms != WORKFLOW_RUNTIME_ARMS:
            raise ValueError("Flash information contract includes another Runtime")
        if self.response_variables != RESPONSE_VARIABLES:
            raise ValueError("Flash information contract omits a capability response")
        if self.bootstrap_replicates != self.thresholds.bootstrap_replicates:
            raise ValueError("Flash information bootstrap contract is inconsistent")
        if self.contract_id != flash_information_contract_id(self):
            raise ValueError("Flash information contract identity is invalid")
        return self


class InformationSpectrum(FrozenModel):
    response_variable: str = Field(min_length=1)
    runtime_arm: CapabilityRuntimeArm
    task_count: int = Field(ge=1)
    observed_task_count: int = Field(ge=0)
    rollout_count: int = Field(ge=0)
    conditional_success_rate: float | None = Field(default=None, ge=0, le=1)
    boundary_task_fraction: float | None = Field(default=None, ge=0, le=1)
    raw_information_eigenvalues: tuple[float, ...]
    residual_information_eigenvalues: tuple[float, ...]
    residual_numerical_rank: int = Field(ge=0)
    residual_effective_rank: float = Field(ge=0)
    residual_condition_number: float = Field(ge=1)
    general_factor_fraction: float = Field(ge=0, le=1)
    marginal_axis_information: dict[str, float]
    family_information_share: dict[str, float]
    maximum_family_information_share: float = Field(ge=0, le=1)
    schema_version: str = FLASH_INFORMATION_SPECTRUM_VERSION

    @model_validator(mode="after")
    def validate_spectrum(self) -> InformationSpectrum:
        if self.schema_version != FLASH_INFORMATION_SPECTRUM_VERSION:
            raise ValueError("Flash information spectrum version is unsupported")
        if len(self.raw_information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("Flash raw information spectrum is incomplete")
        if len(self.residual_information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("Flash residual information spectrum is incomplete")
        if set(self.marginal_axis_information) != set(CAPABILITY_AXES):
            raise ValueError("Flash marginal information is incomplete")
        if set(self.family_information_share) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("Flash family information is incomplete")
        if self.maximum_family_information_share != max(self.family_information_share.values()):
            raise ValueError("Flash family information maximum is inconsistent")
        if self.observed_task_count == 0 and (
            self.conditional_success_rate is not None or self.boundary_task_fraction is not None
        ):
            raise ValueError("empty Flash information spectrum has response statistics")
        return self


class InformationGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    category: Literal[
        "final_valid_information",
        "joint_capability_information",
        "capability_outcome_coverage",
    ]
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool


class FlashInformationCell(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    final_valid: InformationSpectrum
    joint_capability: InformationSpectrum
    axis_specific: tuple[InformationSpectrum, ...] = Field(
        min_length=len(CAPABILITY_AXES), max_length=len(CAPABILITY_AXES)
    )
    final_valid_marginal_axis_intervals: dict[str, ConfidenceInterval]
    final_valid_informative_axis_count: int = Field(ge=0)
    visible_capability_axes: tuple[str, ...] = Field(min_length=1)
    observed_capability_axes: tuple[str, ...] = Field(min_length=1)
    gates: tuple[InformationGate, ...] = Field(min_length=12)
    passed: bool
    schema_version: str = FLASH_INFORMATION_CELL_VERSION

    @model_validator(mode="after")
    def validate_cell(self) -> FlashInformationCell:
        if self.schema_version != FLASH_INFORMATION_CELL_VERSION:
            raise ValueError("Flash information cell version is unsupported")
        if self.final_valid.runtime_arm != self.runtime_arm:
            raise ValueError("Final Valid spectrum uses another Runtime")
        if self.joint_capability.runtime_arm != self.runtime_arm:
            raise ValueError("joint capability spectrum uses another Runtime")
        if {item.response_variable for item in self.axis_specific} != set(CAPABILITY_AXES):
            raise ValueError("axis-specific Flash information is incomplete")
        if any(item.runtime_arm != self.runtime_arm for item in self.axis_specific):
            raise ValueError("axis-specific Flash information uses another Runtime")
        if set(self.final_valid_marginal_axis_intervals) != set(CAPABILITY_AXES):
            raise ValueError("Final Valid marginal intervals are incomplete")
        if not set(self.visible_capability_axes).issubset(CAPABILITY_AXES):
            raise ValueError("Flash visible capability axes are invalid")
        if not set(self.observed_capability_axes).issubset(self.visible_capability_axes):
            raise ValueError("Flash observed capability axes are not model-visible")
        if self.passed != all(item.passed for item in self.gates):
            raise ValueError("Flash information cell decision is inconsistent")
        return self


class FinanceFlashInformationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    source_runtime_report_id: str = Field(min_length=1)
    source_outcome_set_hash: str = Field(min_length=1)
    source_requested_rollout_count: int = Field(ge=1)
    source_recorded_rollout_count: int = Field(ge=1)
    runtime_eligible_rollout_count: int = Field(ge=1)
    cells: tuple[FlashInformationCell, ...] = Field(min_length=2, max_length=2)
    all_runtime_cells_ready: bool
    information_matrix_ready: bool
    failure_codes: tuple[str, ...]
    next_permitted_stage: Literal[
        "pro_sparse_anchor_preparation",
        "capability_task_support_redesign_only",
    ]
    source_api_call_count: int = Field(ge=0)
    source_model_tokens: int = Field(ge=0)
    source_estimated_cost_usd: float = Field(ge=0)
    pro_api_call_count: Literal[0] = 0
    pro_sparse_anchor_authorized: bool
    model_ranking_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = FLASH_INFORMATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceFlashInformationReport:
        if self.schema_version != FLASH_INFORMATION_REPORT_VERSION:
            raise ValueError("Flash information report version is unsupported")
        if self.source_recorded_rollout_count != self.source_requested_rollout_count:
            raise ValueError("Flash information source denominator is incomplete")
        if {item.runtime_arm for item in self.cells} != set(WORKFLOW_RUNTIME_ARMS):
            raise ValueError("Flash information report omits a Workflow Runtime")
        ready = all(item.passed for item in self.cells)
        if self.all_runtime_cells_ready != ready or self.information_matrix_ready != ready:
            raise ValueError("Flash information readiness is inconsistent")
        if self.pro_sparse_anchor_authorized != ready:
            raise ValueError("Pro sparse-anchor authorization is inconsistent")
        expected_stage = (
            "pro_sparse_anchor_preparation" if ready else "capability_task_support_redesign_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Flash information transition is not fail-closed")
        if self.report_id != flash_information_report_id(self):
            raise ValueError("Flash information report identity is invalid")
        return self


@dataclass(frozen=True)
class _OutcomeRow:
    task_artifact_id: str
    family: str
    probability: float
    general_difficulty: float
    demand: tuple[float, ...]
    realizations: tuple[int, ...]


@dataclass(frozen=True)
class _MatrixBundle:
    raw_matrix: tuple[tuple[float, ...], ...]
    centered_matrix: tuple[tuple[float, ...], ...]
    residual_matrix: tuple[tuple[float, ...], ...]
    family_contributions: dict[str, float]


def prepare_flash_information_contract(
    *,
    source_runtime_contract_path: Path,
    source_runtime_report_path: Path,
    source_terminal_outcomes_path: Path,
    output_path: Path,
    run_id: str,
    random_seed: int,
) -> FinanceFlashInformationContract:
    if output_path.exists():
        raise ValueError("Flash information contract is immutable and already exists")
    source_contract, source_report, terminals = _load_and_replay_source(
        source_runtime_contract_path,
        source_runtime_report_path,
        source_terminal_outcomes_path,
    )
    if source_contract.stage != RuntimeResolutionStage.HELDOUT_CONFIRMATION:
        raise ValueError("Flash information requires the fresh Held-out stage")
    if not source_report.information_matrix_evaluation_authorized:
        raise ValueError("Held-out Runtime report does not authorize information evaluation")
    thresholds = WorkflowInformationThresholds()
    values = {
        "run_id": run_id,
        "source_runtime_contract_path": str(source_runtime_contract_path.resolve()),
        "source_runtime_contract_sha256": _sha256(source_runtime_contract_path),
        "source_runtime_contract_id": source_contract.contract_id,
        "source_runtime_report_path": str(source_runtime_report_path.resolve()),
        "source_runtime_report_sha256": _sha256(source_runtime_report_path),
        "source_runtime_report_id": source_report.report_id,
        "source_terminal_outcomes_path": str(source_terminal_outcomes_path.resolve()),
        "source_terminal_outcomes_sha256": _sha256(source_terminal_outcomes_path),
        "source_outcome_set_hash": source_report.outcome_set_hash,
        "source_population_id": source_contract.source_population_id,
        "thresholds": thresholds,
        "random_seed": random_seed,
        "bootstrap_replicates": thresholds.bootstrap_replicates,
    }
    provisional = FinanceFlashInformationContract.model_construct(contract_id="pending", **values)
    contract = FinanceFlashInformationContract(
        contract_id=flash_information_contract_id(provisional), **values
    )
    if len(terminals) != source_report.recorded_rollout_count:
        raise ValueError("Flash information source outcome count changed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return contract


def run_flash_information_evaluation(
    *,
    contract_path: Path,
    output_path: Path,
    markdown_report_path: Path,
) -> FinanceFlashInformationReport:
    if output_path.exists() or markdown_report_path.exists():
        raise ValueError("Flash information report is immutable and already exists")
    contract = FinanceFlashInformationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_frozen_inputs(contract)
    source_contract, source_report, terminals = _load_and_replay_source(
        Path(contract.source_runtime_contract_path),
        Path(contract.source_runtime_report_path),
        Path(contract.source_terminal_outcomes_path),
    )
    if (
        source_contract.contract_id != contract.source_runtime_contract_id
        or source_report.report_id != contract.source_runtime_report_id
        or source_report.outcome_set_hash != contract.source_outcome_set_hash
    ):
        raise ValueError("Flash information source identity changed")
    cells = tuple(
        _make_information_cell(
            contract=contract,
            source_contract=source_contract,
            terminals=terminals,
            runtime=runtime,
        )
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    ready = all(item.passed for item in cells)
    failure_codes = tuple(
        sorted(
            f"{cell.runtime_arm.value}:{gate.gate_id}"
            for cell in cells
            for gate in cell.gates
            if not gate.passed
        )
    )
    values = {
        "contract_id": contract.contract_id,
        "source_runtime_report_id": source_report.report_id,
        "source_outcome_set_hash": source_report.outcome_set_hash,
        "source_requested_rollout_count": source_report.requested_rollout_count,
        "source_recorded_rollout_count": source_report.recorded_rollout_count,
        "runtime_eligible_rollout_count": sum(
            item.runtime_eligible_for_capability_denominator for item in terminals
        ),
        "cells": cells,
        "all_runtime_cells_ready": ready,
        "information_matrix_ready": ready,
        "failure_codes": failure_codes,
        "next_permitted_stage": (
            "pro_sparse_anchor_preparation" if ready else "capability_task_support_redesign_only"
        ),
        "source_api_call_count": source_report.api_call_count,
        "source_model_tokens": source_report.total_model_tokens,
        "source_estimated_cost_usd": source_report.estimated_cost_usd,
        "pro_sparse_anchor_authorized": ready,
    }
    provisional = FinanceFlashInformationReport.model_construct(report_id="pending", **values)
    report = FinanceFlashInformationReport(
        report_id=flash_information_report_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_report_path.write_text(_render_markdown(report), encoding="utf-8")
    return report


def _make_information_cell(
    *,
    contract: FinanceFlashInformationContract,
    source_contract: FinanceRuntimeResolutionContract,
    terminals: tuple[RuntimeTerminalOutcome, ...],
    runtime: CapabilityRuntimeArm,
) -> FlashInformationCell:
    binding_by_task = {
        item.task_artifact_id: item
        for item in source_contract.bindings
        if item.runtime_arm == runtime
    }
    eligible = tuple(
        item
        for item in terminals
        if item.runtime_arm == runtime and item.runtime_eligible_for_capability_denominator
    )
    final_rows = _rows_for_response(
        eligible,
        binding_by_task=binding_by_task,
        response_variable="final_valid",
    )
    if len(final_rows) != len(binding_by_task):
        raise ValueError("Flash Final Valid matrix lacks a Runtime-eligible task")
    final_valid = _spectrum(
        runtime=runtime,
        response_variable="final_valid",
        rows=final_rows,
        task_count=len(binding_by_task),
        boundary_lower=contract.thresholds.boundary_probability_lower,
        boundary_upper=contract.thresholds.boundary_probability_upper,
    )
    axis_rows = {
        axis: _rows_for_response(
            eligible,
            binding_by_task=binding_by_task,
            response_variable=axis,
        )
        for axis in CAPABILITY_AXES
    }
    axis_specific = tuple(
        _spectrum(
            runtime=runtime,
            response_variable=axis,
            rows=axis_rows[axis],
            task_count=len(binding_by_task),
            boundary_lower=contract.thresholds.boundary_probability_lower,
            boundary_upper=contract.thresholds.boundary_probability_upper,
        )
        for axis in CAPABILITY_AXES
    )
    joint = _joint_spectrum(
        runtime=runtime,
        axis_rows=axis_rows,
        task_count=len(binding_by_task),
    )
    intervals = _bootstrap_axis_intervals(
        final_rows,
        replicates=contract.bootstrap_replicates,
        seed=_stable_seed(contract.contract_id, runtime.value),
    )
    visible_axes = tuple(
        axis
        for axis in CAPABILITY_AXES
        if any(binding.visible_demand.values[axis] > 0 for binding in binding_by_task.values())
    )
    observed_axes = tuple(axis for axis in visible_axes if axis_rows[axis])
    informative = sum(
        intervals[axis].lower >= contract.thresholds.minimum_marginal_axis_information
        for axis in visible_axes
    )
    threshold = contract.thresholds.by_runtime[runtime]
    gates = (
        _gate(
            "visible_capability_outcome_coverage",
            set(observed_axes) == set(visible_axes),
            len(observed_axes) / len(visible_axes),
            "=1.0",
            "capability_outcome_coverage",
        ),
        _gate(
            "final_valid_residual_rank",
            final_valid.residual_numerical_rank >= threshold.minimum_rank,
            final_valid.residual_numerical_rank,
            f">={threshold.minimum_rank}",
            "final_valid_information",
        ),
        _gate(
            "final_valid_effective_rank",
            final_valid.residual_effective_rank >= threshold.minimum_effective_rank,
            final_valid.residual_effective_rank,
            f">={threshold.minimum_effective_rank}",
            "final_valid_information",
        ),
        _gate(
            "final_valid_condition_number",
            final_valid.residual_condition_number <= threshold.maximum_condition_number,
            final_valid.residual_condition_number,
            f"<={threshold.maximum_condition_number}",
            "final_valid_information",
        ),
        _gate(
            "final_valid_boundary_fraction",
            (final_valid.boundary_task_fraction or 0) >= threshold.minimum_boundary_task_fraction,
            final_valid.boundary_task_fraction or 0,
            f">={threshold.minimum_boundary_task_fraction}",
            "final_valid_information",
        ),
        _gate(
            "final_valid_general_factor_fraction",
            final_valid.general_factor_fraction <= threshold.maximum_general_factor_fraction,
            final_valid.general_factor_fraction,
            f"<={threshold.maximum_general_factor_fraction}",
            "final_valid_information",
        ),
        _gate(
            "final_valid_informative_axis_count",
            informative >= threshold.minimum_informative_axis_count,
            informative,
            f">={threshold.minimum_informative_axis_count}",
            "final_valid_information",
        ),
        _gate(
            "final_valid_family_dominance",
            final_valid.maximum_family_information_share
            <= contract.thresholds.maximum_family_information_share,
            final_valid.maximum_family_information_share,
            f"<={contract.thresholds.maximum_family_information_share}",
            "final_valid_information",
        ),
        _gate(
            "joint_residual_rank",
            joint.residual_numerical_rank >= threshold.minimum_rank,
            joint.residual_numerical_rank,
            f">={threshold.minimum_rank}",
            "joint_capability_information",
        ),
        _gate(
            "joint_effective_rank",
            joint.residual_effective_rank >= threshold.minimum_effective_rank,
            joint.residual_effective_rank,
            f">={threshold.minimum_effective_rank}",
            "joint_capability_information",
        ),
        _gate(
            "joint_condition_number",
            joint.residual_condition_number <= threshold.maximum_condition_number,
            joint.residual_condition_number,
            f"<={threshold.maximum_condition_number}",
            "joint_capability_information",
        ),
        _gate(
            "joint_family_dominance",
            joint.maximum_family_information_share
            <= contract.thresholds.maximum_family_information_share,
            joint.maximum_family_information_share,
            f"<={contract.thresholds.maximum_family_information_share}",
            "joint_capability_information",
        ),
    )
    return FlashInformationCell(
        runtime_arm=runtime,
        final_valid=final_valid,
        joint_capability=joint,
        axis_specific=axis_specific,
        final_valid_marginal_axis_intervals=intervals,
        final_valid_informative_axis_count=informative,
        visible_capability_axes=visible_axes,
        observed_capability_axes=observed_axes,
        gates=gates,
        passed=all(item.passed for item in gates),
    )


def _rows_for_response(
    terminals: Sequence[RuntimeTerminalOutcome],
    *,
    binding_by_task: Mapping[str, RuntimeTaskBinding],
    response_variable: str,
) -> list[_OutcomeRow]:
    by_task: dict[str, list[RuntimeTerminalOutcome]] = defaultdict(list)
    for item in terminals:
        by_task[item.task_artifact_id].append(item)
    rows = []
    for task_id, outcomes in sorted(by_task.items()):
        binding = binding_by_task[task_id]
        if response_variable == "final_valid":
            values = tuple(int(item.valid_success) for item in outcomes)
        else:
            values = tuple(
                int(value)
                for item in outcomes
                for value in (item.capability_outcomes[response_variable],)
                if value is not None
            )
        if not values:
            continue
        rows.append(
            _OutcomeRow(
                task_artifact_id=task_id,
                family=binding.family,
                probability=sum(values) / len(values),
                general_difficulty=binding.general_difficulty,
                demand=_normalize_demand(binding.visible_demand.values),
                realizations=values,
            )
        )
    return rows


def _spectrum(
    *,
    runtime: CapabilityRuntimeArm,
    response_variable: str,
    rows: Sequence[_OutcomeRow],
    task_count: int,
    boundary_lower: float,
    boundary_upper: float,
) -> InformationSpectrum:
    if not rows:
        return _empty_spectrum(runtime, response_variable, task_count)
    bundle = _matrix_bundle(rows)
    return _spectrum_from_bundle(
        runtime=runtime,
        response_variable=response_variable,
        task_count=task_count,
        observed_task_count=len(rows),
        rollout_count=sum(len(item.realizations) for item in rows),
        conditional_success_rate=fmean(item.probability for item in rows),
        boundary_task_fraction=sum(
            boundary_lower <= item.probability <= boundary_upper for item in rows
        )
        / len(rows),
        bundle=bundle,
    )


def _joint_spectrum(
    *,
    runtime: CapabilityRuntimeArm,
    axis_rows: Mapping[str, Sequence[_OutcomeRow]],
    task_count: int,
) -> InformationSpectrum:
    bundles = [_matrix_bundle(rows) for rows in axis_rows.values() if rows]
    if not bundles:
        return _empty_spectrum(runtime, "joint_capability", task_count)
    divisor = len(bundles)
    size = len(CAPABILITY_AXES)
    averaged = _MatrixBundle(
        raw_matrix=tuple(
            tuple(
                sum(item.raw_matrix[row][column] for item in bundles) / divisor
                for column in range(size)
            )
            for row in range(size)
        ),
        centered_matrix=tuple(
            tuple(
                sum(item.centered_matrix[row][column] for item in bundles) / divisor
                for column in range(size)
            )
            for row in range(size)
        ),
        residual_matrix=tuple(
            tuple(
                sum(item.residual_matrix[row][column] for item in bundles) / divisor
                for column in range(size)
            )
            for row in range(size)
        ),
        family_contributions={
            family: sum(item.family_contributions[family] for item in bundles) / divisor
            for family in CAPABILITY_SENSITIVE_FAMILIES
        },
    )
    probabilities = [item.probability for rows in axis_rows.values() for item in rows]
    rollouts = sum(len(item.realizations) for rows in axis_rows.values() for item in rows)
    return _spectrum_from_bundle(
        runtime=runtime,
        response_variable="joint_capability",
        task_count=task_count,
        observed_task_count=len(
            {item.task_artifact_id for rows in axis_rows.values() for item in rows}
        ),
        rollout_count=rollouts,
        conditional_success_rate=fmean(probabilities),
        boundary_task_fraction=None,
        bundle=averaged,
    )


def _matrix_bundle(rows: Sequence[_OutcomeRow]) -> _MatrixBundle:
    demands = [list(item.demand) for item in rows]
    centered = _center_columns(demands)
    residual = _residualize(centered, [item.general_difficulty for item in rows])
    weights = [item.probability * (1 - item.probability) for item in rows]
    return _MatrixBundle(
        raw_matrix=_weighted_second_moment(demands, weights),
        centered_matrix=_weighted_second_moment(centered, weights),
        residual_matrix=_weighted_second_moment(residual, weights),
        family_contributions={
            family: sum(
                weights[index] * sum(value * value for value in residual[index])
                for index, item in enumerate(rows)
                if item.family == family
            )
            / len(rows)
            for family in CAPABILITY_SENSITIVE_FAMILIES
        },
    )


def _spectrum_from_bundle(
    *,
    runtime: CapabilityRuntimeArm,
    response_variable: str,
    task_count: int,
    observed_task_count: int,
    rollout_count: int,
    conditional_success_rate: float | None,
    boundary_task_fraction: float | None,
    bundle: _MatrixBundle,
) -> InformationSpectrum:
    raw_values = _eigenvalues(bundle.raw_matrix)
    residual_values = _eigenvalues(bundle.residual_matrix)
    positive = _positive_eigenvalues(residual_values)
    residual_trace = sum(
        bundle.residual_matrix[index][index] for index in range(len(CAPABILITY_AXES))
    )
    centered_trace = sum(
        bundle.centered_matrix[index][index] for index in range(len(CAPABILITY_AXES))
    )
    family_shares = {
        family: (min(1.0, max(0.0, value / residual_trace)) if residual_trace else 0.0)
        for family, value in bundle.family_contributions.items()
    }
    return InformationSpectrum(
        response_variable=response_variable,
        runtime_arm=runtime,
        task_count=task_count,
        observed_task_count=observed_task_count,
        rollout_count=rollout_count,
        conditional_success_rate=conditional_success_rate,
        boundary_task_fraction=boundary_task_fraction,
        raw_information_eigenvalues=raw_values,
        residual_information_eigenvalues=residual_values,
        residual_numerical_rank=len(positive),
        residual_effective_rank=_effective_rank(positive),
        residual_condition_number=(positive[0] / positive[-1] if positive else 1e12),
        general_factor_fraction=(
            min(1.0, max(0.0, 1 - residual_trace / centered_trace)) if centered_trace else 1.0
        ),
        marginal_axis_information={
            axis: bundle.residual_matrix[index][index] for index, axis in enumerate(CAPABILITY_AXES)
        },
        family_information_share=family_shares,
        maximum_family_information_share=max(family_shares.values()),
    )


def _empty_spectrum(
    runtime: CapabilityRuntimeArm,
    response_variable: str,
    task_count: int,
) -> InformationSpectrum:
    zeros = tuple(0.0 for _ in CAPABILITY_AXES)
    return InformationSpectrum(
        response_variable=response_variable,
        runtime_arm=runtime,
        task_count=task_count,
        observed_task_count=0,
        rollout_count=0,
        conditional_success_rate=None,
        boundary_task_fraction=None,
        raw_information_eigenvalues=zeros,
        residual_information_eigenvalues=zeros,
        residual_numerical_rank=0,
        residual_effective_rank=0,
        residual_condition_number=1e12,
        general_factor_fraction=1.0,
        marginal_axis_information={axis: 0.0 for axis in CAPABILITY_AXES},
        family_information_share={family: 0.0 for family in CAPABILITY_SENSITIVE_FAMILIES},
        maximum_family_information_share=0.0,
    )


def _bootstrap_axis_intervals(
    rows: Sequence[_OutcomeRow],
    *,
    replicates: int,
    seed: int,
) -> dict[str, ConfidenceInterval]:
    rng = random.Random(seed)
    by_family = {
        family: [item for item in rows if item.family == family]
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    point = _spectrum(
        runtime=CapabilityRuntimeArm.AUTONOMOUS_AGENT,
        response_variable="bootstrap",
        rows=rows,
        task_count=len(rows),
        boundary_lower=0.1,
        boundary_upper=0.9,
    ).marginal_axis_information
    samples: dict[str, list[float]] = {axis: [] for axis in CAPABILITY_AXES}
    for _ in range(replicates):
        resampled = []
        for family_rows in by_family.values():
            for _ in range(len(family_rows)):
                row = rng.choice(family_rows)
                realizations = tuple(
                    rng.choice(row.realizations) for _ in range(len(row.realizations))
                )
                resampled.append(
                    _OutcomeRow(
                        task_artifact_id=row.task_artifact_id,
                        family=row.family,
                        probability=sum(realizations) / len(realizations),
                        general_difficulty=row.general_difficulty,
                        demand=row.demand,
                        realizations=realizations,
                    )
                )
        observed = _matrix_bundle(resampled).residual_matrix
        for index, axis in enumerate(CAPABILITY_AXES):
            samples[axis].append(observed[index][index])
    return {
        axis: ConfidenceInterval(
            lower=min(_quantile(values, 0.025), point[axis]),
            point=point[axis],
            upper=max(_quantile(values, 0.975), point[axis]),
        )
        for axis, values in samples.items()
    }


def _load_and_replay_source(
    contract_path: Path,
    report_path: Path,
    outcomes_path: Path,
) -> tuple[
    FinanceRuntimeResolutionContract,
    FinanceRuntimeResolutionReport,
    tuple[RuntimeTerminalOutcome, ...],
]:
    source_contract = FinanceRuntimeResolutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    source_report = FinanceRuntimeResolutionReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    with outcomes_path.open(encoding="utf-8") as handle:
        terminals = tuple(
            RuntimeTerminalOutcome.model_validate_json(line) for line in handle if line.strip()
        )
    if source_report.contract_id != source_contract.contract_id:
        raise ValueError("Flash information report belongs to another Runtime contract")
    expected = {
        (binding.binding_id, replicate)
        for binding in source_contract.bindings
        for replicate in range(source_contract.replicas)
    }
    observed = {(item.binding_id, item.replicate) for item in terminals}
    if len(observed) != len(terminals) or observed != expected:
        raise ValueError("Flash information outcomes do not cover frozen rollouts")
    binding_by_id = {item.binding_id: item for item in source_contract.bindings}
    for item in terminals:
        binding = binding_by_id[item.binding_id]
        if (
            item.contract_id != source_contract.contract_id
            or item.stage != source_contract.stage
            or item.task_artifact_id != binding.task_artifact_id
            or item.family != binding.family
            or item.tier != binding.tier
            or item.runtime_arm != binding.runtime_arm
        ):
            raise ValueError("Flash information outcome identity differs from its binding")
    replayed = make_runtime_resolution_report(source_contract, terminals)
    if replayed != source_report:
        raise ValueError("Flash information Runtime report does not replay from outcomes")
    return source_contract, source_report, terminals


def _verify_frozen_inputs(contract: FinanceFlashInformationContract) -> None:
    for path, expected in (
        (Path(contract.source_runtime_contract_path), contract.source_runtime_contract_sha256),
        (Path(contract.source_runtime_report_path), contract.source_runtime_report_sha256),
        (Path(contract.source_terminal_outcomes_path), contract.source_terminal_outcomes_sha256),
    ):
        if _sha256(path) != expected:
            raise ValueError(f"frozen Flash information input changed:{path}")


def _normalize_demand(values: Mapping[str, float]) -> tuple[float, ...]:
    raw = tuple(float(values[axis]) for axis in CAPABILITY_AXES)
    norm = math.sqrt(sum(value * value for value in raw))
    if norm <= 0:
        raise ValueError("Flash information demand vector is empty")
    return tuple(value / norm for value in raw)


def _center_columns(values: Sequence[Sequence[float]]) -> list[list[float]]:
    means = [fmean(row[index] for row in values) for index in range(len(values[0]))]
    return [[value - means[index] for index, value in enumerate(row)] for row in values]


def _residualize(values: Sequence[Sequence[float]], general: Sequence[float]) -> list[list[float]]:
    mean_general = fmean(general)
    centered_general = [value - mean_general for value in general]
    variance = sum(value * value for value in centered_general)
    if variance <= 1e-15:
        return [list(row) for row in values]
    output = [[0.0 for _ in row] for row in values]
    for axis in range(len(values[0])):
        slope = (
            sum(centered_general[index] * row[axis] for index, row in enumerate(values)) / variance
        )
        for index, row in enumerate(values):
            output[index][axis] = row[axis] - slope * centered_general[index]
    return output


def _weighted_second_moment(
    values: Sequence[Sequence[float]], weights: Sequence[float]
) -> tuple[tuple[float, ...], ...]:
    size = len(values[0])
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    for value, weight in zip(values, weights, strict=True):
        for row in range(size):
            for column in range(size):
                matrix[row][column] += weight * value[row] * value[column] / len(values)
    return tuple(tuple(row) for row in matrix)


def _eigenvalues(matrix: Sequence[Sequence[float]]) -> tuple[float, ...]:
    return tuple(
        0.0 if abs(value) <= 1e-15 else max(0.0, value)
        for value in sorted(_symmetric_eigenvalues([list(row) for row in matrix]), reverse=True)
    )


def _positive_eigenvalues(values: Sequence[float]) -> list[float]:
    maximum = max(values, default=0.0)
    tolerance = max(1e-12, maximum * 1e-6)
    return [value for value in values if maximum > tolerance and value > tolerance]


def _effective_rank(values: Sequence[float]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    probabilities = [value / total for value in values]
    return math.exp(-sum(value * math.log(value) for value in probabilities if value > 0))


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _gate(
    gate_id: str,
    passed: bool,
    observed: float,
    requirement: str,
    category: Literal[
        "final_valid_information",
        "joint_capability_information",
        "capability_outcome_coverage",
    ],
) -> InformationGate:
    return InformationGate(
        gate_id=gate_id,
        category=category,
        observed=float(observed),
        requirement=requirement,
        passed=passed,
    )


def flash_information_contract_id(value: FinanceFlashInformationContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_flash_information_matrix_contract:",
    )


def flash_information_report_id(value: FinanceFlashInformationReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_flash_information_matrix_report:",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_seed(*values: str) -> int:
    return int(hashlib.sha256("|".join(values).encode()).hexdigest()[:16], 16)


def _render_markdown(report: FinanceFlashInformationReport) -> str:
    lines = [
        "# Finance v25.18 Flash Information Matrix Evaluation",
        "",
        f"- Report ID: `{report.report_id}`",
        f"- Runtime-eligible denominator: {report.runtime_eligible_rollout_count}",
        f"- Information matrix ready: {report.information_matrix_ready}",
        f"- Pro sparse anchor authorized: {report.pro_sparse_anchor_authorized}",
        f"- Next permitted stage: `{report.next_permitted_stage}`",
        "",
        "## Runtime Cells",
        "",
        "| Runtime | Final p | Boundary | Final rank | Final erank | Final cond "
        "| Joint rank | Joint erank | Joint cond | Passed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cell in report.cells:
        final = cell.final_valid
        joint = cell.joint_capability
        lines.append(
            "| "
            + " | ".join(
                (
                    cell.runtime_arm.value,
                    f"{final.conditional_success_rate or 0:.4f}",
                    f"{final.boundary_task_fraction or 0:.4f}",
                    str(final.residual_numerical_rank),
                    f"{final.residual_effective_rank:.4f}",
                    f"{final.residual_condition_number:.4f}",
                    str(joint.residual_numerical_rank),
                    f"{joint.residual_effective_rank:.4f}",
                    f"{joint.residual_condition_number:.4f}",
                    str(cell.passed),
                )
            )
            + " |"
        )
    lines.extend(("", "## Failed Gates", ""))
    if report.failure_codes:
        lines.extend(f"- `{item}`" for item in report.failure_codes)
    else:
        lines.append("- None")
    lines.extend(
        (
            "",
            "Axis-specific matrices are diagnostic only. Correctness is conditioned "
            "on Runtime eligibility and never serves as a Runtime qualification gate.",
            "",
        )
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Flash capability information matrices")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--runtime-contract", type=Path, required=True)
    prepare.add_argument("--runtime-report", type=Path, required=True)
    prepare.add_argument("--terminal-outcomes", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--random-seed", type=int, default=2026081304)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--report", type=Path, required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.command == "prepare":
        contract = prepare_flash_information_contract(
            source_runtime_contract_path=args.runtime_contract,
            source_runtime_report_path=args.runtime_report,
            source_terminal_outcomes_path=args.terminal_outcomes,
            output_path=args.output,
            run_id=args.run_id,
            random_seed=args.random_seed,
        )
        print(
            json.dumps(
                {
                    "contract_id": contract.contract_id,
                    "source_runtime_report_id": contract.source_runtime_report_id,
                    "bootstrap_replicates": contract.bootstrap_replicates,
                },
                indent=2,
            )
        )
        return
    report = run_flash_information_evaluation(
        contract_path=args.contract,
        output_path=args.output,
        markdown_report_path=args.report,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "information_matrix_ready": report.information_matrix_ready,
                "failure_codes": report.failure_codes,
                "next_permitted_stage": report.next_permitted_stage,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
