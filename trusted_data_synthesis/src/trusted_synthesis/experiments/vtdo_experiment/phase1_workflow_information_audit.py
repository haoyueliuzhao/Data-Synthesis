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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    RUNTIME_AXIS_RESPONSIBILITY,
    CapabilityRuntimeArm,
    RuntimeInformationThreshold,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
    ConfidenceInterval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
    FAMILY_PRIMARY_CAPABILITY,
    _symmetric_eigenvalues,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_tier_localization import (
    WORKFLOW_RUNTIME_ARMS,
    FinanceMatchedTierLocalizationContract,
    FinanceMatchedTierLocalizationReport,
    _validate_outcomes,
    make_matched_localization_report,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.hashing import canonical_hash

WORKFLOW_INFORMATION_CONTRACT_VERSION = "finance_workflow_information_contract.v1"
WORKFLOW_INFORMATION_AUDIT_VERSION = "finance_workflow_information_audit.v1"
WORKFLOW_INFORMATION_CELL_VERSION = "finance_workflow_information_cell.v1"
WORKFLOW_INFORMATION_SENSITIVITY_VERSION = (
    "finance_workflow_information_sensitivity.v1"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InformationGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool


class WorkflowInformationThresholds(FrozenModel):
    by_runtime: dict[CapabilityRuntimeArm, RuntimeInformationThreshold] = Field(
        default_factory=lambda: {
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
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    minimum_marginal_axis_information: float = Field(default=1e-4, gt=0)
    maximum_family_information_share: float = Field(default=0.60, gt=0, le=1)
    maximum_group_information_share: float = Field(default=0.45, gt=0, le=1)
    minimum_primary_aligned_family_count: dict[CapabilityRuntimeArm, int] = Field(
        default_factory=lambda: {
            CapabilityRuntimeArm.SCRIPTED_TOOL: 3,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT: 3,
        }
    )
    bootstrap_replicates: int = Field(default=400, ge=100)

    @model_validator(mode="after")
    def validate_thresholds(self) -> WorkflowInformationThresholds:
        if set(self.by_runtime) != set(WORKFLOW_RUNTIME_ARMS):
            raise ValueError("workflow information thresholds omit a workflow Runtime")
        if set(self.minimum_primary_aligned_family_count) != set(
            WORKFLOW_RUNTIME_ARMS
        ):
            raise ValueError("workflow alignment thresholds omit a workflow Runtime")
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("workflow information boundary interval is empty")
        return self


class FinanceWorkflowInformationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    localization_contract_path: str = Field(min_length=1)
    localization_contract_sha256: str = Field(min_length=64, max_length=64)
    localization_contract_id: str = Field(min_length=1)
    localization_report_path: str = Field(min_length=1)
    localization_report_sha256: str = Field(min_length=64, max_length=64)
    localization_report_id: str = Field(min_length=1)
    localization_outcomes_path: str = Field(min_length=1)
    localization_outcomes_sha256: str = Field(min_length=64, max_length=64)
    localization_outcome_set_hash: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    thresholds: WorkflowInformationThresholds
    random_seed: int
    response_variable: Literal["valid_success"] = "valid_success"
    demand_normalization: Literal["task_l2"] = "task_l2"
    primary_population: Literal["selected_shared_tier_only"] = (
        "selected_shared_tier_only"
    )
    sensitivity_population: Literal["complete_ladder_non_authorizing"] = (
        "complete_ladder_non_authorizing"
    )
    workflow_runtime_arms: tuple[CapabilityRuntimeArm, ...] = WORKFLOW_RUNTIME_ARMS
    direct_runtime_role: Literal["positive_execution_control"] = (
        "positive_execution_control"
    )
    direct_runtime_excluded: Literal[True] = True
    model_ranking_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["workflow_information_audit"] = (
        "workflow_information_audit"
    )
    schema_version: str = WORKFLOW_INFORMATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceWorkflowInformationContract:
        if self.schema_version != WORKFLOW_INFORMATION_CONTRACT_VERSION:
            raise ValueError("workflow information contract version is unsupported")
        if self.workflow_runtime_arms != WORKFLOW_RUNTIME_ARMS:
            raise ValueError("workflow information contract includes Direct")
        if self.contract_id != workflow_information_contract_id(self):
            raise ValueError("workflow information contract identity is invalid")
        return self


class WorkflowRuntimeDesignAudit(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    selected_families: tuple[str, ...] = Field(min_length=1)
    selected_tiers: dict[str, DifficultyTier] = Field(min_length=1)
    selected_binding_count: int = Field(ge=1)
    distinct_normalized_demand_count: int = Field(ge=1)
    model_visible_primary_families: tuple[str, ...]
    host_controlled_primary_families: tuple[str, ...]
    family_primary_axis_alignment: dict[str, bool] = Field(min_length=1)
    primary_aligned_family_count: int = Field(ge=0)
    minimum_primary_aligned_family_count: int = Field(ge=1)
    passed: bool

    @model_validator(mode="after")
    def validate_design(self) -> WorkflowRuntimeDesignAudit:
        selected = set(self.selected_families)
        if set(self.selected_tiers) != selected:
            raise ValueError("workflow design selected Tier manifest is incomplete")
        if set(self.family_primary_axis_alignment) != selected:
            raise ValueError("workflow design alignment manifest is incomplete")
        if set(self.model_visible_primary_families) | set(
            self.host_controlled_primary_families
        ) != selected:
            raise ValueError("workflow primary-axis ownership is incomplete")
        if set(self.model_visible_primary_families) & set(
            self.host_controlled_primary_families
        ):
            raise ValueError("workflow primary-axis ownership overlaps")
        expected_count = sum(self.family_primary_axis_alignment.values())
        if self.primary_aligned_family_count != expected_count:
            raise ValueError("workflow design aligned-family count is inconsistent")
        if self.passed != (
            expected_count >= self.minimum_primary_aligned_family_count
        ):
            raise ValueError("workflow design decision is inconsistent")
        return self


class WorkflowInformationCell(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    selected_families: tuple[str, ...] = Field(min_length=1)
    task_count: int = Field(ge=1)
    rollout_count: int = Field(ge=1)
    mean_success_rate: float = Field(ge=0, le=1)
    boundary_task_fraction: float = Field(ge=0, le=1)
    raw_information_eigenvalues: tuple[float, ...]
    residual_information_eigenvalues: tuple[float, ...]
    residual_numerical_rank: int = Field(ge=0)
    residual_effective_rank: float = Field(ge=0)
    residual_condition_number: float = Field(ge=1)
    general_factor_fraction: float = Field(ge=0, le=1)
    marginal_axis_information: dict[str, float]
    marginal_axis_intervals: dict[str, ConfidenceInterval]
    informative_axis_count: int = Field(ge=0)
    family_information_share: dict[str, float]
    group_information_share: dict[str, float] = Field(min_length=1)
    maximum_family_information_share: float = Field(ge=0, le=1)
    maximum_group_information_share: float = Field(ge=0, le=1)
    gates: tuple[InformationGate, ...] = Field(min_length=8)
    passed: bool
    schema_version: str = WORKFLOW_INFORMATION_CELL_VERSION

    @model_validator(mode="after")
    def validate_cell(self) -> WorkflowInformationCell:
        if self.schema_version != WORKFLOW_INFORMATION_CELL_VERSION:
            raise ValueError("workflow information cell version is unsupported")
        if len(self.raw_information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("workflow raw information spectrum is incomplete")
        if len(self.residual_information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("workflow residual information spectrum is incomplete")
        if set(self.marginal_axis_information) != set(CAPABILITY_AXES):
            raise ValueError("workflow marginal axis information is incomplete")
        if set(self.marginal_axis_intervals) != set(CAPABILITY_AXES):
            raise ValueError("workflow axis intervals are incomplete")
        if set(self.family_information_share) != set(
            CAPABILITY_SENSITIVE_FAMILIES
        ):
            raise ValueError("workflow family information shares are incomplete")
        if self.maximum_family_information_share != max(
            self.family_information_share.values()
        ):
            raise ValueError("workflow family dominance is inconsistent")
        if self.maximum_group_information_share != max(
            self.group_information_share.values()
        ):
            raise ValueError("workflow group dominance is inconsistent")
        if self.passed != all(item.passed for item in self.gates):
            raise ValueError("workflow information cell decision is inconsistent")
        return self


class WorkflowInformationSensitivityCell(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    task_count: int = Field(ge=1)
    rollout_count: int = Field(ge=1)
    mean_success_rate: float = Field(ge=0, le=1)
    boundary_task_fraction: float = Field(ge=0, le=1)
    residual_information_eigenvalues: tuple[float, ...]
    residual_numerical_rank: int = Field(ge=0)
    residual_effective_rank: float = Field(ge=0)
    residual_condition_number: float = Field(ge=1)
    general_factor_fraction: float = Field(ge=0, le=1)
    maximum_family_information_share: float = Field(ge=0, le=1)
    authorizing: Literal[False] = False
    schema_version: str = WORKFLOW_INFORMATION_SENSITIVITY_VERSION

    @model_validator(mode="after")
    def validate_sensitivity(self) -> WorkflowInformationSensitivityCell:
        if self.schema_version != WORKFLOW_INFORMATION_SENSITIVITY_VERSION:
            raise ValueError("workflow information sensitivity version is unsupported")
        if len(self.residual_information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("workflow sensitivity spectrum is incomplete")
        return self


class FinanceWorkflowInformationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    audit_contract_id: str = Field(min_length=1)
    localization_contract_id: str = Field(min_length=1)
    localization_report_id: str = Field(min_length=1)
    localization_outcome_set_hash: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    source_requested_rollout_count: int = Field(ge=1)
    source_recorded_rollout_count: int = Field(ge=1)
    selected_task_runtime_count: int = Field(ge=1)
    selected_unique_task_count: int = Field(ge=1)
    analyzed_rollout_count: int = Field(ge=1)
    excluded_source_rollout_count: int = Field(ge=0)
    runtime_designs: tuple[WorkflowRuntimeDesignAudit, ...] = Field(
        min_length=2, max_length=2
    )
    cells: tuple[WorkflowInformationCell, ...] = Field(min_length=4, max_length=4)
    complete_ladder_sensitivity: tuple[
        WorkflowInformationSensitivityCell, ...
    ] = Field(min_length=4, max_length=4)
    all_runtime_designs_ready: bool
    all_information_cells_ready: bool
    empirical_capability_information_ready: bool
    failure_codes: tuple[str, ...]
    next_permitted_stage: Literal[
        "paired_capability_calibration_contract_preparation",
        "workflow_task_redesign_only",
    ]
    direct_runtime_excluded: Literal[True] = True
    complete_ladder_sensitivity_authorizing: Literal[False] = False
    pro_flash_ranking_authorized: Literal[False] = False
    paired_calibration_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    source_api_call_count: int = Field(ge=0)
    source_model_tokens: int = Field(ge=0)
    source_estimated_cost_usd: float = Field(ge=0)
    schema_version: str = WORKFLOW_INFORMATION_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FinanceWorkflowInformationAudit:
        if self.schema_version != WORKFLOW_INFORMATION_AUDIT_VERSION:
            raise ValueError("workflow information audit version is unsupported")
        if self.source_recorded_rollout_count != self.source_requested_rollout_count:
            raise ValueError("workflow information source denominator is incomplete")
        expected_designs = set(WORKFLOW_RUNTIME_ARMS)
        if {item.runtime_arm for item in self.runtime_designs} != expected_designs:
            raise ValueError("workflow information designs omit a Runtime")
        expected_cells = {
            (model, runtime)
            for model in ExplorerArm
            for runtime in WORKFLOW_RUNTIME_ARMS
        }
        if {(item.model_arm, item.runtime_arm) for item in self.cells} != expected_cells:
            raise ValueError("workflow information audit omits a Model x Runtime cell")
        if {
            (item.model_arm, item.runtime_arm)
            for item in self.complete_ladder_sensitivity
        } != expected_cells:
            raise ValueError("workflow sensitivity omits a Model x Runtime cell")
        if sum(item.rollout_count for item in self.cells) != self.analyzed_rollout_count:
            raise ValueError("workflow information analyzed denominator is inconsistent")
        if self.excluded_source_rollout_count != (
            self.source_recorded_rollout_count - self.analyzed_rollout_count
        ):
            raise ValueError("workflow information excluded denominator is inconsistent")
        designs_ready = all(item.passed for item in self.runtime_designs)
        cells_ready = all(item.passed for item in self.cells)
        if self.all_runtime_designs_ready != designs_ready:
            raise ValueError("workflow design readiness is inconsistent")
        if self.all_information_cells_ready != cells_ready:
            raise ValueError("workflow information readiness is inconsistent")
        ready = designs_ready and cells_ready
        if self.empirical_capability_information_ready != ready:
            raise ValueError("workflow empirical information decision is inconsistent")
        expected_next = (
            "paired_capability_calibration_contract_preparation"
            if ready
            else "workflow_task_redesign_only"
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("workflow information transition is not fail-closed")
        if self.audit_id != workflow_information_audit_id(self):
            raise ValueError("workflow information audit identity is invalid")
        return self


@dataclass(frozen=True)
class _InformationRow:
    task_artifact_id: str
    family: str
    group_id: str
    probability: float
    general_difficulty: float
    demand: tuple[float, ...]
    realizations: tuple[int, ...]


@dataclass(frozen=True)
class _InformationComponents:
    raw_eigenvalues: tuple[float, ...]
    residual_eigenvalues: tuple[float, ...]
    numerical_rank: int
    effective_rank: float
    condition_number: float
    general_factor_fraction: float
    marginal_axis_information: dict[str, float]
    family_information_share: dict[str, float]
    group_information_share: dict[str, float]


def prepare_workflow_information_contract(
    *,
    localization_contract_path: Path,
    localization_report_path: Path,
    localization_outcomes_path: Path,
    output_path: Path,
    run_id: str,
    random_seed: int,
) -> FinanceWorkflowInformationContract:
    if output_path.exists():
        raise ValueError("workflow information contract is immutable and exists")
    localization_contract, localization_report, _ = _load_and_replay_source(
        localization_contract_path,
        localization_report_path,
        localization_outcomes_path,
    )
    if (
        localization_report.next_permitted_stage
        != "empirical_capability_information_audit"
    ):
        raise ValueError("localization report does not authorize an information audit")
    values = {
        "run_id": run_id,
        "localization_contract_path": str(localization_contract_path.resolve()),
        "localization_contract_sha256": _sha256(localization_contract_path),
        "localization_contract_id": localization_contract.contract_id,
        "localization_report_path": str(localization_report_path.resolve()),
        "localization_report_sha256": _sha256(localization_report_path),
        "localization_report_id": localization_report.report_id,
        "localization_outcomes_path": str(localization_outcomes_path.resolve()),
        "localization_outcomes_sha256": _sha256(localization_outcomes_path),
        "localization_outcome_set_hash": localization_report.outcome_set_hash,
        "population_id": localization_report.population_id,
        "thresholds": WorkflowInformationThresholds(),
        "random_seed": random_seed,
    }
    provisional = FinanceWorkflowInformationContract.model_construct(
        contract_id="pending",
        **values,
    )
    contract = FinanceWorkflowInformationContract(
        contract_id=workflow_information_contract_id(provisional),
        **values,
    )
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_workflow_information_audit(
    *,
    audit_contract_path: Path,
    output_dir: Path,
) -> FinanceWorkflowInformationAudit:
    audit_contract = FinanceWorkflowInformationContract.model_validate_json(
        audit_contract_path.read_text(encoding="utf-8")
    )
    _verify_audit_contract_inputs(audit_contract)
    localization_contract, localization_report, outcomes = _load_and_replay_source(
        Path(audit_contract.localization_contract_path),
        Path(audit_contract.localization_report_path),
        Path(audit_contract.localization_outcomes_path),
    )
    if (
        localization_contract.contract_id
        != audit_contract.localization_contract_id
        or localization_report.report_id != audit_contract.localization_report_id
        or localization_report.outcome_set_hash
        != audit_contract.localization_outcome_set_hash
        or localization_report.population_id != audit_contract.population_id
    ):
        raise ValueError("workflow information lineage differs from its contract")
    audit = make_workflow_information_audit(
        audit_contract,
        localization_contract,
        localization_report,
        outcomes,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "finance_workflow_information_audit.json"
    if output_path.exists():
        existing = FinanceWorkflowInformationAudit.model_validate_json(
            output_path.read_text(encoding="utf-8")
        )
        if existing != audit:
            raise ValueError("immutable workflow information audit already differs")
        return existing
    _write_json_atomic(output_path, audit.model_dump(mode="json"))
    return audit


def make_workflow_information_audit(
    audit_contract: FinanceWorkflowInformationContract,
    localization_contract: FinanceMatchedTierLocalizationContract,
    localization_report: FinanceMatchedTierLocalizationReport,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> FinanceWorkflowInformationAudit:
    if (
        localization_report.next_permitted_stage
        != "empirical_capability_information_audit"
    ):
        raise ValueError("workflow information audit requires a ready localization")
    binding_by_id = {item.binding_id: item for item in localization_contract.bindings}
    selections = {
        (item.runtime_arm, item.family): item.selected_tier
        for item in localization_report.selections
        if item.selected_tier is not None
    }
    designs = tuple(
        _runtime_design(
            runtime,
            localization_contract,
            selections,
            audit_contract.thresholds,
        )
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    cells = tuple(
        _make_information_cell(
            model=model,
            runtime=runtime,
            rows=_rows_for_scope(
                model=model,
                runtime=runtime,
                outcomes=outcomes,
                binding_by_id=binding_by_id,
                task_group_ids=localization_contract.task_group_ids,
                selections=selections,
            ),
            design=next(item for item in designs if item.runtime_arm == runtime),
            thresholds=audit_contract.thresholds,
            seed=_stable_seed(
                str(audit_contract.random_seed),
                model.value,
                runtime.value,
                "selected",
            ),
        )
        for model in ExplorerArm
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    sensitivity = tuple(
        _make_sensitivity_cell(
            model=model,
            runtime=runtime,
            rows=_rows_for_scope(
                model=model,
                runtime=runtime,
                outcomes=outcomes,
                binding_by_id=binding_by_id,
                task_group_ids=localization_contract.task_group_ids,
                selections=None,
            ),
            thresholds=audit_contract.thresholds,
        )
        for model in ExplorerArm
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    all_designs_ready = all(item.passed for item in designs)
    all_cells_ready = all(item.passed for item in cells)
    ready = all_designs_ready and all_cells_ready
    failure_codes = sorted(
        {
            f"runtime_design:{item.runtime_arm.value}"
            for item in designs
            if not item.passed
        }
        | {
            f"cell:{item.model_arm.value}:{item.runtime_arm.value}:{gate.gate_id}"
            for item in cells
            for gate in item.gates
            if not gate.passed
        }
    )
    selected_binding_keys = {
        (binding.runtime_arm, binding.task_artifact_id)
        for binding in localization_contract.bindings
        if selections.get((binding.runtime_arm, binding.family)) == binding.tier
    }
    selected_unique_tasks = {task_id for _, task_id in selected_binding_keys}
    analyzed_rollouts = sum(item.rollout_count for item in cells)
    values = {
        "audit_contract_id": audit_contract.contract_id,
        "localization_contract_id": localization_contract.contract_id,
        "localization_report_id": localization_report.report_id,
        "localization_outcome_set_hash": localization_report.outcome_set_hash,
        "population_id": localization_report.population_id,
        "source_requested_rollout_count": localization_report.requested_rollout_count,
        "source_recorded_rollout_count": localization_report.recorded_rollout_count,
        "selected_task_runtime_count": len(selected_binding_keys),
        "selected_unique_task_count": len(selected_unique_tasks),
        "analyzed_rollout_count": analyzed_rollouts,
        "excluded_source_rollout_count": (
            localization_report.recorded_rollout_count - analyzed_rollouts
        ),
        "runtime_designs": designs,
        "cells": cells,
        "complete_ladder_sensitivity": sensitivity,
        "all_runtime_designs_ready": all_designs_ready,
        "all_information_cells_ready": all_cells_ready,
        "empirical_capability_information_ready": ready,
        "failure_codes": tuple(failure_codes),
        "next_permitted_stage": (
            "paired_capability_calibration_contract_preparation"
            if ready
            else "workflow_task_redesign_only"
        ),
        "direct_runtime_excluded": True,
        "complete_ladder_sensitivity_authorizing": False,
        "pro_flash_ranking_authorized": False,
        "paired_calibration_authorized": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
        "source_api_call_count": localization_report.api_call_count,
        "source_model_tokens": localization_report.total_model_tokens,
        "source_estimated_cost_usd": localization_report.estimated_cost_usd,
    }
    provisional = FinanceWorkflowInformationAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return FinanceWorkflowInformationAudit(
        audit_id=workflow_information_audit_id(provisional),
        **values,
    )


def _runtime_design(
    runtime: CapabilityRuntimeArm,
    contract: FinanceMatchedTierLocalizationContract,
    selections: Mapping[tuple[CapabilityRuntimeArm, str], DifficultyTier],
    thresholds: WorkflowInformationThresholds,
) -> WorkflowRuntimeDesignAudit:
    selected_tiers = {
        family: tier
        for (selected_runtime, family), tier in selections.items()
        if selected_runtime == runtime
    }
    bindings = [
        item
        for item in contract.bindings
        if item.runtime_arm == runtime
        and selected_tiers.get(item.family) == item.tier
    ]
    normalized = [_normalize_demand(item.visible_demand.values) for item in bindings]
    overall = [
        fmean(row[index] for row in normalized) for index in range(len(CAPABILITY_AXES))
    ]
    alignments = {}
    visible: list[str] = []
    host: list[str] = []
    for family in sorted(selected_tiers):
        family_bindings = [item for item in bindings if item.family == family]
        family_vectors = [
            _normalize_demand(item.visible_demand.values) for item in family_bindings
        ]
        contrast = {
            axis: fmean(row[index] for row in family_vectors) - overall[index]
            for index, axis in enumerate(CAPABILITY_AXES)
        }
        primary = FAMILY_PRIMARY_CAPABILITY[family]
        primary_visible = any(
            item.visible_demand.values[primary] > 0 for item in family_bindings
        )
        (visible if primary_visible else host).append(family)
        other = max(value for axis, value in contrast.items() if axis != primary)
        alignments[family] = primary_visible and contrast[primary] > 0 and (
            contrast[primary] > other
        )
    aligned_count = sum(alignments.values())
    minimum = thresholds.minimum_primary_aligned_family_count[runtime]
    return WorkflowRuntimeDesignAudit(
        runtime_arm=runtime,
        selected_families=tuple(sorted(selected_tiers)),
        selected_tiers=selected_tiers,
        selected_binding_count=len(bindings),
        distinct_normalized_demand_count=len(
            {tuple(round(value, 12) for value in row) for row in normalized}
        ),
        model_visible_primary_families=tuple(sorted(visible)),
        host_controlled_primary_families=tuple(sorted(host)),
        family_primary_axis_alignment=alignments,
        primary_aligned_family_count=aligned_count,
        minimum_primary_aligned_family_count=minimum,
        passed=aligned_count >= minimum,
    )


def _rows_for_scope(
    *,
    model: ExplorerArm,
    runtime: CapabilityRuntimeArm,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
    binding_by_id: Mapping[str, Any],
    task_group_ids: Mapping[str, str],
    selections: Mapping[tuple[CapabilityRuntimeArm, str], DifficultyTier] | None,
) -> list[_InformationRow]:
    by_task: dict[str, list[CapabilityRolloutOutcome]] = defaultdict(list)
    for outcome in outcomes:
        if outcome.model_arm != model or outcome.runtime_arm != runtime:
            continue
        binding = binding_by_id[outcome.binding_id]
        if (
            selections is not None
            and selections.get((runtime, binding.family)) != binding.tier
        ):
            continue
        by_task[outcome.task_artifact_id].append(outcome)
    rows = []
    for task_id, task_outcomes in sorted(by_task.items()):
        binding = binding_by_id[task_outcomes[0].binding_id]
        if len(task_outcomes) == 0:
            raise ValueError("workflow information row has no realizations")
        realizations = tuple(int(item.valid_success) for item in task_outcomes)
        rows.append(
            _InformationRow(
                task_artifact_id=task_id,
                family=binding.family,
                group_id=task_group_ids[task_id],
                probability=sum(realizations) / len(realizations),
                general_difficulty=binding.general_difficulty,
                demand=_normalize_demand(binding.visible_demand.values),
                realizations=realizations,
            )
        )
    if not rows:
        raise ValueError("workflow information scope is empty")
    return rows


def _make_information_cell(
    *,
    model: ExplorerArm,
    runtime: CapabilityRuntimeArm,
    rows: list[_InformationRow],
    design: WorkflowRuntimeDesignAudit,
    thresholds: WorkflowInformationThresholds,
    seed: int,
) -> WorkflowInformationCell:
    components = _information_components(rows)
    intervals = _bootstrap_axis_intervals(
        rows,
        replicates=thresholds.bootstrap_replicates,
        seed=seed,
    )
    visible_axes = {
        axis
        for axis, responsibility in RUNTIME_AXIS_RESPONSIBILITY[runtime].items()
        if responsibility > 0
    }
    informative = sum(
        intervals[axis].lower >= thresholds.minimum_marginal_axis_information
        for axis in visible_axes
    )
    boundary = sum(
        thresholds.boundary_probability_lower
        <= row.probability
        <= thresholds.boundary_probability_upper
        for row in rows
    ) / len(rows)
    runtime_threshold = thresholds.by_runtime[runtime]
    gates = (
        _gate(
            "runtime_selected_design",
            design.passed,
            float(design.primary_aligned_family_count),
            f">={design.minimum_primary_aligned_family_count}",
        ),
        _gate(
            "residual_numerical_rank",
            components.numerical_rank >= runtime_threshold.minimum_rank,
            float(components.numerical_rank),
            f">={runtime_threshold.minimum_rank}",
        ),
        _gate(
            "residual_effective_rank",
            components.effective_rank >= runtime_threshold.minimum_effective_rank,
            components.effective_rank,
            f">={runtime_threshold.minimum_effective_rank}",
        ),
        _gate(
            "residual_condition_number",
            components.condition_number <= runtime_threshold.maximum_condition_number,
            components.condition_number,
            f"<={runtime_threshold.maximum_condition_number}",
        ),
        _gate(
            "boundary_task_fraction",
            boundary >= runtime_threshold.minimum_boundary_task_fraction,
            boundary,
            f">={runtime_threshold.minimum_boundary_task_fraction}",
        ),
        _gate(
            "general_factor_fraction",
            components.general_factor_fraction
            <= runtime_threshold.maximum_general_factor_fraction,
            components.general_factor_fraction,
            f"<={runtime_threshold.maximum_general_factor_fraction}",
        ),
        _gate(
            "informative_axis_count",
            informative >= runtime_threshold.minimum_informative_axis_count,
            float(informative),
            f">={runtime_threshold.minimum_informative_axis_count}",
        ),
        _gate(
            "family_information_dominance",
            max(components.family_information_share.values())
            <= thresholds.maximum_family_information_share,
            max(components.family_information_share.values()),
            f"<={thresholds.maximum_family_information_share}",
        ),
        _gate(
            "ladder_group_information_dominance",
            max(components.group_information_share.values())
            <= thresholds.maximum_group_information_share,
            max(components.group_information_share.values()),
            f"<={thresholds.maximum_group_information_share}",
        ),
    )
    return WorkflowInformationCell(
        model_arm=model,
        runtime_arm=runtime,
        selected_families=design.selected_families,
        task_count=len(rows),
        rollout_count=sum(len(item.realizations) for item in rows),
        mean_success_rate=fmean(item.probability for item in rows),
        boundary_task_fraction=boundary,
        raw_information_eigenvalues=components.raw_eigenvalues,
        residual_information_eigenvalues=components.residual_eigenvalues,
        residual_numerical_rank=components.numerical_rank,
        residual_effective_rank=components.effective_rank,
        residual_condition_number=components.condition_number,
        general_factor_fraction=components.general_factor_fraction,
        marginal_axis_information=components.marginal_axis_information,
        marginal_axis_intervals=intervals,
        informative_axis_count=informative,
        family_information_share=components.family_information_share,
        group_information_share=components.group_information_share,
        maximum_family_information_share=max(
            components.family_information_share.values()
        ),
        maximum_group_information_share=max(
            components.group_information_share.values()
        ),
        gates=gates,
        passed=all(item.passed for item in gates),
    )


def _make_sensitivity_cell(
    *,
    model: ExplorerArm,
    runtime: CapabilityRuntimeArm,
    rows: list[_InformationRow],
    thresholds: WorkflowInformationThresholds,
) -> WorkflowInformationSensitivityCell:
    components = _information_components(rows)
    boundary = sum(
        thresholds.boundary_probability_lower
        <= row.probability
        <= thresholds.boundary_probability_upper
        for row in rows
    ) / len(rows)
    return WorkflowInformationSensitivityCell(
        model_arm=model,
        runtime_arm=runtime,
        task_count=len(rows),
        rollout_count=sum(len(item.realizations) for item in rows),
        mean_success_rate=fmean(item.probability for item in rows),
        boundary_task_fraction=boundary,
        residual_information_eigenvalues=components.residual_eigenvalues,
        residual_numerical_rank=components.numerical_rank,
        residual_effective_rank=components.effective_rank,
        residual_condition_number=components.condition_number,
        general_factor_fraction=components.general_factor_fraction,
        maximum_family_information_share=max(
            components.family_information_share.values()
        ),
        authorizing=False,
    )


def _information_components(rows: Sequence[_InformationRow]) -> _InformationComponents:
    demands = [list(item.demand) for item in rows]
    general = [item.general_difficulty for item in rows]
    centered = _center_columns(demands)
    residual = _residualize(centered, general)
    weights = [item.probability * (1.0 - item.probability) for item in rows]
    raw_matrix = _weighted_second_moment(demands, weights)
    centered_matrix = _weighted_second_moment(centered, weights)
    residual_matrix = _weighted_second_moment(residual, weights)
    raw_eigenvalues = _eigenvalues(raw_matrix)
    residual_eigenvalues = _eigenvalues(residual_matrix)
    positive = _positive_eigenvalues(residual_eigenvalues)
    numerical_rank = len(positive)
    condition = positive[0] / positive[-1] if positive else 1e12
    marginal = {
        axis: residual_matrix[index][index]
        for index, axis in enumerate(CAPABILITY_AXES)
    }
    residual_trace = sum(marginal.values())
    centered_trace = sum(
        centered_matrix[index][index] for index in range(len(CAPABILITY_AXES))
    )
    general_fraction = (
        min(1.0, max(0.0, 1.0 - residual_trace / centered_trace))
        if centered_trace
        else 1.0
    )
    family_shares = {}
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        value = sum(
            weights[index] * sum(component * component for component in residual[index])
            for index, row in enumerate(rows)
            if row.family == family
        ) / len(rows)
        family_shares[family] = (
            min(1.0, max(0.0, value / residual_trace))
            if residual_trace
            else 0.0
        )
    group_shares = {}
    for group_id in sorted({item.group_id for item in rows}):
        value = sum(
            weights[index] * sum(component * component for component in residual[index])
            for index, row in enumerate(rows)
            if row.group_id == group_id
        ) / len(rows)
        group_shares[group_id] = (
            min(1.0, max(0.0, value / residual_trace))
            if residual_trace
            else 0.0
        )
    return _InformationComponents(
        raw_eigenvalues=raw_eigenvalues,
        residual_eigenvalues=residual_eigenvalues,
        numerical_rank=numerical_rank,
        effective_rank=_effective_rank(positive),
        condition_number=condition,
        general_factor_fraction=general_fraction,
        marginal_axis_information=marginal,
        family_information_share=family_shares,
        group_information_share=group_shares,
    )


def _bootstrap_axis_intervals(
    rows: Sequence[_InformationRow],
    *,
    replicates: int,
    seed: int,
) -> dict[str, ConfidenceInterval]:
    rng = random.Random(seed)
    by_family = {
        family: [item for item in rows if item.family == family]
        for family in CAPABILITY_SENSITIVE_FAMILIES
        if any(item.family == family for item in rows)
    }
    samples: dict[str, list[float]] = {axis: [] for axis in CAPABILITY_AXES}
    point = _information_components(rows).marginal_axis_information
    for _ in range(replicates):
        resampled = []
        for family_rows in by_family.values():
            for _ in range(len(family_rows)):
                row = rng.choice(family_rows)
                realizations = tuple(
                    rng.choice(row.realizations) for _ in range(len(row.realizations))
                )
                resampled.append(
                    _InformationRow(
                        task_artifact_id=row.task_artifact_id,
                        family=row.family,
                        group_id=row.group_id,
                        probability=sum(realizations) / len(realizations),
                        general_difficulty=row.general_difficulty,
                        demand=row.demand,
                        realizations=realizations,
                    )
                )
        marginal = _information_components(resampled).marginal_axis_information
        for axis in CAPABILITY_AXES:
            samples[axis].append(marginal[axis])
    return {
        axis: ConfidenceInterval(
            lower=min(_quantile(values, 0.025), point[axis]),
            point=point[axis],
            upper=max(_quantile(values, 0.975), point[axis]),
        )
        for axis, values in samples.items()
    }


def _load_and_replay_source(
    localization_contract_path: Path,
    localization_report_path: Path,
    localization_outcomes_path: Path,
) -> tuple[
    FinanceMatchedTierLocalizationContract,
    FinanceMatchedTierLocalizationReport,
    tuple[CapabilityRolloutOutcome, ...],
]:
    localization_contract = FinanceMatchedTierLocalizationContract.model_validate_json(
        localization_contract_path.read_text(encoding="utf-8")
    )
    localization_report = FinanceMatchedTierLocalizationReport.model_validate_json(
        localization_report_path.read_text(encoding="utf-8")
    )
    with localization_outcomes_path.open(encoding="utf-8") as handle:
        outcomes = tuple(
            CapabilityRolloutOutcome.model_validate_json(line)
            for line in handle
            if line.strip()
        )
    _validate_outcomes(localization_contract, outcomes)
    replayed = make_matched_localization_report(localization_contract, outcomes)
    if replayed != localization_report:
        raise ValueError("workflow localization report does not replay from outcomes")
    return localization_contract, localization_report, outcomes


def _verify_audit_contract_inputs(
    contract: FinanceWorkflowInformationContract,
) -> None:
    for path, expected in (
        (
            Path(contract.localization_contract_path),
            contract.localization_contract_sha256,
        ),
        (Path(contract.localization_report_path), contract.localization_report_sha256),
        (
            Path(contract.localization_outcomes_path),
            contract.localization_outcomes_sha256,
        ),
    ):
        if _sha256(path) != expected:
            raise ValueError(f"frozen workflow information input changed:{path}")


def _normalize_demand(values: Mapping[str, float]) -> tuple[float, ...]:
    raw = tuple(float(values[axis]) for axis in CAPABILITY_AXES)
    norm = math.sqrt(sum(value * value for value in raw))
    if norm <= 0:
        raise ValueError("workflow information demand vector is empty")
    return tuple(value / norm for value in raw)


def _center_columns(values: Sequence[Sequence[float]]) -> list[list[float]]:
    means = [
        fmean(row[index] for row in values) for index in range(len(values[0]))
    ]
    return [
        [value - means[index] for index, value in enumerate(row)] for row in values
    ]


def _residualize(
    values: Sequence[Sequence[float]],
    general: Sequence[float],
) -> list[list[float]]:
    mean_general = fmean(general)
    centered_general = [value - mean_general for value in general]
    variance = sum(value * value for value in centered_general)
    if variance <= 1e-15:
        return [list(row) for row in values]
    output = [[0.0 for _ in row] for row in values]
    for axis in range(len(values[0])):
        slope = (
            sum(
                centered_general[index] * row[axis]
                for index, row in enumerate(values)
            )
            / variance
        )
        for index, row in enumerate(values):
            output[index][axis] = row[axis] - slope * centered_general[index]
    return output


def _weighted_second_moment(
    values: Sequence[Sequence[float]],
    weights: Sequence[float],
) -> list[list[float]]:
    size = len(values[0])
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    for value, weight in zip(values, weights, strict=True):
        for row in range(size):
            for column in range(size):
                matrix[row][column] += (
                    weight * value[row] * value[column] / len(values)
                )
    return matrix


def _eigenvalues(matrix: list[list[float]]) -> tuple[float, ...]:
    return tuple(
        max(0.0, value)
        for value in sorted(_symmetric_eigenvalues(matrix), reverse=True)
    )


def _positive_eigenvalues(values: Sequence[float]) -> list[float]:
    maximum = max(values, default=0.0)
    return [
        value for value in values if maximum > 0 and value > maximum * 1e-6
    ]


def _effective_rank(values: Sequence[float]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    probabilities = [value / total for value in values]
    return math.exp(
        -sum(value * math.log(value) for value in probabilities if value > 0)
    )


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _stable_seed(*values: str) -> int:
    digest = canonical_hash(values, prefix="workflow_information_seed:")
    return int(digest.rsplit(":", 1)[-1][:16], 16)


def _gate(
    gate_id: str,
    passed: bool,
    observed: float,
    requirement: str,
) -> InformationGate:
    return InformationGate(
        gate_id=gate_id,
        observed=observed,
        requirement=requirement,
        passed=passed,
    )


def workflow_information_contract_id(
    value: FinanceWorkflowInformationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_workflow_information_contract:",
    )


def workflow_information_audit_id(
    value: FinanceWorkflowInformationAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_workflow_information_audit:",
    )


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
        description="Freeze or run the workflow-only empirical information audit"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--localization-contract", type=Path, required=True)
    prepare.add_argument("--localization-report", type=Path, required=True)
    prepare.add_argument("--localization-outcomes", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--random-seed", type=int, default=20260813)
    run = subparsers.add_parser("run")
    run.add_argument("--audit-contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result: dict[str, Any]
    if args.command == "prepare":
        contract = prepare_workflow_information_contract(
            localization_contract_path=args.localization_contract,
            localization_report_path=args.localization_report,
            localization_outcomes_path=args.localization_outcomes,
            output_path=args.output,
            run_id=args.run_id,
            random_seed=args.random_seed,
        )
        result = {
            "contract_id": contract.contract_id,
            "output": str(args.output.resolve()),
            "next_permitted_stage": contract.next_permitted_stage,
        }
    else:
        audit = run_workflow_information_audit(
            audit_contract_path=args.audit_contract,
            output_dir=args.output_dir,
        )
        result = {
            "audit_id": audit.audit_id,
            "analyzed_rollouts": audit.analyzed_rollout_count,
            "empirical_capability_information_ready": (
                audit.empirical_capability_information_ready
            ),
            "failure_codes": audit.failure_codes,
            "next_permitted_stage": audit.next_permitted_stage,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
