from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    FinanceCapabilityBoundaryContract,
    RuntimeTaskBinding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
    _symmetric_eigenvalues,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.hashing import canonical_hash

CAPABILITY_ROLLOUT_OUTCOME_VERSION = "finance_capability_rollout_outcome.v7"
QUALIFICATION_REPORT_VERSION = "finance_capability_qualification_report.v8"
TIER_LOCALIZATION_REPORT_VERSION = "finance_capability_tier_localization_report.v1"
EMPIRICAL_INFORMATION_AUDIT_VERSION = "empirical_capability_information_audit.v8"
BENEFICIARY_SCREENING_VERSION = "beneficiary_frontier_screening.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BoundaryStage(str, Enum):
    RUNTIME_QUALIFICATION = "runtime_qualification"
    TIER_LOCALIZATION = "tier_localization"
    PAIRED_CALIBRATION = "paired_calibration"
    BENEFICIARY_SCREENING = "beneficiary_screening"


class CapabilityRolloutOutcome(FrozenModel):
    outcome_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: BoundaryStage
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    replicate: int = Field(ge=0)
    completed: bool
    raw_json_contract_success: bool
    bounded_json_resolution_success: bool
    api_call_count: int = Field(ge=0)
    json_contract_success_count: int = Field(ge=0)
    contract_repair_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    semantically_successful_tool_call_count: int = Field(ge=0)
    bounded_tool_resolution_count: int = Field(ge=0)
    runtime_infrastructure_failure_count: int = Field(ge=0)
    final_answer_emitted: bool
    terminal_result_emitted: bool
    observation_replay_success: bool
    authority_integrity_success: bool
    host_verification_repair_count: int = Field(ge=0)
    budget_exhausted: bool
    deterministic_valid: bool
    semantic_answer_correct: bool
    valid_success: bool
    tool_semantic_success: bool
    verification_success: bool
    query_reformulated: bool
    recovery_opportunity: bool
    recovery_success: bool
    stop_quality_success: bool
    state_id: str | None = None
    decision_trace_hash: str | None = None
    tool_sequence_hash: str | None = None
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    mean_api_latency_ms: float = Field(ge=0)
    schema_version: str = CAPABILITY_ROLLOUT_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_outcome(self) -> CapabilityRolloutOutcome:
        if self.schema_version != CAPABILITY_ROLLOUT_OUTCOME_VERSION:
            raise ValueError("capability rollout outcome version is unsupported")
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("capability outcome uses an unknown family")
        if self.semantically_successful_tool_call_count > self.tool_call_count:
            raise ValueError("successful tool calls exceed attempted tool calls")
        if self.bounded_tool_resolution_count > self.tool_call_count:
            raise ValueError("bounded tool resolutions exceed attempted tool calls")
        if (
            self.bounded_tool_resolution_count + self.runtime_infrastructure_failure_count
            != self.tool_call_count
        ):
            raise ValueError("tool calls lack an exhaustive technical resolution class")
        if self.json_contract_success_count > self.api_call_count:
            raise ValueError("JSON successes exceed API calls")
        if self.contract_repair_count > self.api_call_count:
            raise ValueError("contract repairs exceed API calls")
        if self.valid_success != (self.deterministic_valid and self.semantic_answer_correct):
            raise ValueError("valid-success outcome is inconsistent")
        if self.recovery_success and not self.recovery_opportunity:
            raise ValueError("recovery success lacks a recovery opportunity")
        if self.query_reformulated and self.tool_call_count < 2:
            raise ValueError("query reformulation lacks multiple tool calls")
        if self.tool_sequence_hash is not None and self.tool_call_count == 0:
            raise ValueError("tool-sequence identity lacks tool calls")
        if not self.completed and any(
            (
                self.final_answer_emitted,
                self.terminal_result_emitted,
                self.deterministic_valid,
                self.semantic_answer_correct,
                self.valid_success,
                self.tool_semantic_success,
                self.verification_success,
                self.query_reformulated,
                self.recovery_opportunity,
                self.recovery_success,
                self.stop_quality_success,
                self.state_id is not None,
                self.decision_trace_hash is not None,
                self.tool_sequence_hash is not None,
            )
        ):
            raise ValueError("incomplete outcome contains a completed semantic result")
        if self.state_id is not None and not self.valid_success:
            raise ValueError("only valid-success outcomes may enter the state space")
        if self.decision_trace_hash is not None and not self.completed:
            raise ValueError("failed outcome contains a decision trace")
        if self.outcome_id != capability_rollout_outcome_id(self):
            raise ValueError("capability outcome identity is invalid")
        return self


class TechnicalGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    passed: bool
    observed: dict[str, float]
    requirement: str = Field(min_length=1)


class QualificationCellSummary(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    attempted_count: int = Field(ge=1)
    completed_count: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    raw_json_success_count: int = Field(ge=0)
    contract_repair_count: int = Field(ge=0)
    bounded_json_success_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    semantically_successful_tool_call_count: int = Field(ge=0)
    bounded_tool_resolution_count: int = Field(ge=0)
    runtime_infrastructure_failure_count: int = Field(ge=0)
    final_answer_count: int = Field(ge=0)
    terminal_result_count: int = Field(ge=0)
    replay_success_count: int = Field(ge=0)
    authority_success_count: int = Field(ge=0)
    host_verification_repair_count: int = Field(ge=0)
    budget_exhaustion_count: int = Field(ge=0)
    semantic_correct_count: int = Field(ge=0)
    valid_success_count: int = Field(ge=0)

    @property
    def completion_rate(self) -> float:
        return self.completed_count / self.attempted_count

    @property
    def raw_json_rate(self) -> float:
        return self.raw_json_success_count / self.api_call_count if self.api_call_count else 0.0

    @property
    def bounded_json_rate(self) -> float:
        logical_calls = self.api_call_count - self.contract_repair_count
        return self.bounded_json_success_count / logical_calls if logical_calls > 0 else 0.0

    @property
    def tool_bounded_resolution_rate(self) -> float:
        return (
            self.bounded_tool_resolution_count / self.tool_call_count
            if self.tool_call_count
            else 1.0
        )

    @property
    def final_answer_rate(self) -> float:
        return self.final_answer_count / self.attempted_count

    @property
    def terminal_result_rate(self) -> float:
        return self.terminal_result_count / self.attempted_count

    @property
    def replay_rate(self) -> float:
        return self.replay_success_count / self.attempted_count

    @property
    def authority_rate(self) -> float:
        return self.authority_success_count / self.attempted_count

    @property
    def semantic_accuracy(self) -> float:
        return self.semantic_correct_count / self.attempted_count


class CapabilityQualificationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    cells: tuple[QualificationCellSummary, ...] = Field(min_length=6, max_length=6)
    outcome_set_hash: str = Field(min_length=1)
    technical_gates: tuple[TechnicalGate, ...] = Field(min_length=1)
    semantic_results_are_descriptive_only: Literal[True] = True
    status: Literal["passed", "failed"]
    next_permitted_stage: Literal["capability_tier_localization", "protocol_repair_only"]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = QUALIFICATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityQualificationReport:
        if self.schema_version != QUALIFICATION_REPORT_VERSION:
            raise ValueError("Qualification report version is unsupported")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("Qualification report has an incomplete rollout denominator")
        if sum(item.attempted_count for item in self.cells) != self.recorded_rollout_count:
            raise ValueError("Qualification cell denominators do not cover recorded rollouts")

        expected_cells = {
            (model, runtime) for model in ExplorerArm for runtime in CapabilityRuntimeArm
        }
        if {(item.model_arm, item.runtime_arm) for item in self.cells} != expected_cells:
            raise ValueError("Qualification report lacks a Model x Runtime cell")
        passed = all(item.passed for item in self.technical_gates)
        if (self.status == "passed") != passed:
            raise ValueError("Qualification status differs from technical gates")
        expected_next = "capability_tier_localization" if passed else "protocol_repair_only"
        if self.next_permitted_stage != expected_next:
            raise ValueError("Qualification transition is not fail-closed")
        if self.report_id != qualification_report_id(self):
            raise ValueError("Qualification report identity is invalid")
        return self


class ConfidenceInterval(FrozenModel):
    lower: float = Field(ge=0)
    point: float = Field(ge=0)
    upper: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_interval(self) -> ConfidenceInterval:
        if not self.lower <= self.point <= self.upper:
            raise ValueError("confidence interval does not contain its point estimate")
        return self


class SignedConfidenceInterval(FrozenModel):
    lower: float
    point: float
    upper: float

    @model_validator(mode="after")
    def validate_interval(self) -> SignedConfidenceInterval:
        if not self.lower <= self.point <= self.upper:
            raise ValueError("signed confidence interval does not contain its point estimate")
        return self


class TierLocalizationCell(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    tier: DifficultyTier
    task_artifact_id: str = Field(min_length=1)
    attempted_count: int = Field(ge=1)
    technical_resolution_rate: float = Field(ge=0, le=1)
    semantic_answer_accuracy: float = Field(ge=0, le=1)
    valid_success_rate: float = Field(ge=0, le=1)
    valid_success_interval: ConfidenceInterval
    technical_ready: bool
    boundary_candidate: bool

    @model_validator(mode="after")
    def validate_cell(self) -> TierLocalizationCell:
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("Tier Localization cell uses an unknown family")
        if self.valid_success_interval.point != self.valid_success_rate:
            raise ValueError("Tier Localization interval differs from its point estimate")
        if self.boundary_candidate and not self.technical_ready:
            raise ValueError("an unresolved Tier Localization cell cannot be a boundary")
        return self


class RuntimeFamilyTierSelection(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    selected_tier: DifficultyTier | None = None
    selected_task_artifact_id: str | None = None
    combined_bernoulli_information: float = Field(ge=0, le=0.25)
    pro_success_rate: float = Field(ge=0, le=1)
    flash_success_rate: float = Field(ge=0, le=1)
    both_models_technically_ready: bool
    boundary_identified: bool

    @model_validator(mode="after")
    def validate_selection(self) -> RuntimeFamilyTierSelection:
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("Tier selection uses an unknown family")
        has_selection = self.selected_tier is not None
        if has_selection != (self.selected_task_artifact_id is not None):
            raise ValueError("Tier selection task and tier are inconsistent")
        if self.boundary_identified != (
            has_selection and self.both_models_technically_ready
        ):
            raise ValueError("Tier selection boundary decision is inconsistent")
        return self


class CapabilityTierLocalizationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    qualification_report_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    outcome_set_hash: str = Field(min_length=1)
    cells: tuple[TierLocalizationCell, ...] = Field(min_length=126, max_length=126)
    selections: tuple[RuntimeFamilyTierSelection, ...] = Field(min_length=21, max_length=21)
    boundary_family_count_by_runtime: dict[CapabilityRuntimeArm, int]
    monotonic_response_fraction: float = Field(ge=0, le=1)
    all_runtime_localization_ready: bool
    calibration_frontier_compatible: bool
    next_permitted_stage: Literal[
        "paired_capability_calibration",
        "calibration_contract_refreeze_required",
        "task_or_runtime_redesign_only",
    ]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = TIER_LOCALIZATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityTierLocalizationReport:
        if self.schema_version != TIER_LOCALIZATION_REPORT_VERSION:
            raise ValueError("Tier Localization report version is unsupported")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("Tier Localization has an incomplete rollout denominator")
        expected_cells = {
            (model, runtime, family, tier)
            for model in ExplorerArm
            for runtime in CapabilityRuntimeArm
            for family in CAPABILITY_SENSITIVE_FAMILIES
            for tier in DifficultyTier
        }
        if {
            (item.model_arm, item.runtime_arm, item.family, item.tier)
            for item in self.cells
        } != expected_cells:
            raise ValueError("Tier Localization lacks a Model x Runtime x Family x Tier cell")
        expected_selections = {
            (runtime, family)
            for runtime in CapabilityRuntimeArm
            for family in CAPABILITY_SENSITIVE_FAMILIES
        }
        if {(item.runtime_arm, item.family) for item in self.selections} != expected_selections:
            raise ValueError("Tier Localization lacks a Runtime x Family decision")
        expected_counts = {
            runtime: sum(
                item.boundary_identified
                for item in self.selections
                if item.runtime_arm == runtime
            )
            for runtime in CapabilityRuntimeArm
        }
        if self.boundary_family_count_by_runtime != expected_counts:
            raise ValueError("Tier Localization boundary counts are inconsistent")
        if self.calibration_frontier_compatible and not self.all_runtime_localization_ready:
            raise ValueError("Frontier compatibility lacks Runtime localization readiness")
        expected_next = (
            "task_or_runtime_redesign_only"
            if not self.all_runtime_localization_ready
            else (
                "paired_capability_calibration"
                if self.calibration_frontier_compatible
                else "calibration_contract_refreeze_required"
            )
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("Tier Localization transition is not fail-closed")
        if self.report_id != tier_localization_report_id(self):
            raise ValueError("Tier Localization report identity is invalid")
        return self


class CapabilityBehavioralDiagnostics(FrozenModel):
    tool_semantic_success_rate: float = Field(ge=0, le=1)
    verification_success_rate: float = Field(ge=0, le=1)
    query_reformulation_rate: float = Field(ge=0, le=1)
    recovery_opportunity_count: int = Field(ge=0)
    recovery_success_rate: float = Field(ge=0, le=1)
    stop_quality_success_rate: float = Field(ge=0, le=1)
    accepted_state_count: int = Field(ge=0)
    mean_task_state_entropy: float = Field(ge=0)
    mean_decision_trace_diversity: float = Field(ge=0, le=1)
    mean_tool_sequence_diversity: float = Field(ge=0, le=1)
    mean_tool_calls: float = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    mean_api_latency_ms: float = Field(ge=0)


class EmpiricalCapabilityCell(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
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
    family_information_contribution: dict[str, float]
    family_success_rates: dict[str, float]
    behavioral_diagnostics: CapabilityBehavioralDiagnostics
    passed: bool

    @model_validator(mode="after")
    def validate_cell(self) -> EmpiricalCapabilityCell:
        if len(self.raw_information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("raw empirical information spectrum is incomplete")
        if len(self.residual_information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("residual empirical information spectrum is incomplete")
        if set(self.marginal_axis_information) != set(CAPABILITY_AXES):
            raise ValueError("empirical axis information is incomplete")
        if set(self.marginal_axis_intervals) != set(CAPABILITY_AXES):
            raise ValueError("empirical axis uncertainty is incomplete")
        if set(self.family_information_contribution) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("empirical family information is incomplete")
        if set(self.family_success_rates) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("empirical family success rates are incomplete")
        return self


class EmpiricalCapabilityInformationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    qualification_report_id: str = Field(min_length=1)
    cells: tuple[EmpiricalCapabilityCell, ...] = Field(min_length=6, max_length=6)
    minimum_separating_family_count: int = Field(ge=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    outcome_set_hash: str = Field(min_length=1)
    separating_family_count: int = Field(ge=0)
    paired_family_model_gaps: dict[str, float]
    paired_family_model_gap_intervals: dict[str, SignedConfidenceInterval]
    paired_runtime_model_gap_intervals: dict[str, SignedConfidenceInterval]
    paired_family_runtime_gap_intervals: dict[str, SignedConfidenceInterval]
    primary_analysis_method: Literal["task_cluster_paired_nested_bootstrap"] = (
        "task_cluster_paired_nested_bootstrap"
    )
    all_runtime_information_ready: bool
    empirical_capability_ready: bool
    next_permitted_stage: Literal["beneficiary_frontier_screening", "task_or_runtime_redesign_only"]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = EMPIRICAL_INFORMATION_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> EmpiricalCapabilityInformationAudit:
        if self.schema_version != EMPIRICAL_INFORMATION_AUDIT_VERSION:
            raise ValueError("empirical capability audit version is unsupported")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("empirical audit has an incomplete rollout denominator")
        if sum(item.rollout_count for item in self.cells) != self.recorded_rollout_count:
            raise ValueError("empirical cell denominators do not cover recorded rollouts")
        expected_cells = {
            (model, runtime) for model in ExplorerArm for runtime in CapabilityRuntimeArm
        }
        if {(item.model_arm, item.runtime_arm) for item in self.cells} != expected_cells:
            raise ValueError("empirical audit lacks a Model x Runtime cell")
        if set(self.paired_family_model_gaps) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("paired family gaps are incomplete")
        if set(self.paired_family_model_gap_intervals) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("paired family gap intervals are incomplete")
        if set(self.paired_runtime_model_gap_intervals) != {
            item.value for item in CapabilityRuntimeArm
        }:
            raise ValueError("paired runtime gap intervals are incomplete")
        expected_family_runtime = {
            f"{runtime.value}|{family}"
            for runtime in CapabilityRuntimeArm
            for family in CAPABILITY_SENSITIVE_FAMILIES
        }
        if set(self.paired_family_runtime_gap_intervals) != expected_family_runtime:
            raise ValueError("paired family-runtime intervals are incomplete")
        if self.all_runtime_information_ready != all(item.passed for item in self.cells):
            raise ValueError("runtime information decision is inconsistent")
        expected_ready = (
            self.all_runtime_information_ready
            and self.separating_family_count >= self.minimum_separating_family_count
        )
        if self.empirical_capability_ready != expected_ready:
            raise ValueError("empirical capability decision is inconsistent")
        expected_next = (
            "beneficiary_frontier_screening"
            if self.empirical_capability_ready
            else "task_or_runtime_redesign_only"
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("empirical audit transition is inconsistent")
        if self.audit_id != empirical_information_audit_id(self):
            raise ValueError("empirical information audit identity is invalid")
        return self


def make_qualification_report(
    contract: FinanceCapabilityBoundaryContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> CapabilityQualificationReport:
    _validate_outcomes(
        contract,
        outcomes,
        bindings=contract.qualification_bindings,
        stage=BoundaryStage.RUNTIME_QUALIFICATION,
        replicas=contract.qualification_replicas,
    )
    cells = tuple(
        _qualification_cell(model, runtime, outcomes)
        for model in ExplorerArm
        for runtime in CapabilityRuntimeArm
    )
    threshold = contract.technical_thresholds
    completion = min(item.completion_rate for item in cells)
    raw_json = min(item.raw_json_rate for item in cells)
    bounded_json = min(item.bounded_json_rate for item in cells)
    tool_resolution = min(item.tool_bounded_resolution_rate for item in cells)
    terminal_result = min(item.terminal_result_rate for item in cells)
    replay = min(item.replay_rate for item in cells)
    authority = min(item.authority_rate for item in cells)
    exhausted = sum(item.budget_exhaustion_count for item in cells)
    autonomous = [
        item for item in cells if item.runtime_arm == CapabilityRuntimeArm.AUTONOMOUS_AGENT
    ]
    host_repair_rate = max(
        item.host_verification_repair_count / item.attempted_count for item in autonomous
    )
    gates = (
        _gate(
            "completion",
            completion >= threshold.minimum_completion_rate,
            completion,
            f">={threshold.minimum_completion_rate}",
        ),
        _gate(
            "raw_json_contract",
            raw_json >= threshold.minimum_raw_json_contract_rate,
            raw_json,
            f">={threshold.minimum_raw_json_contract_rate}",
        ),
        _gate(
            "bounded_json_resolution",
            bounded_json >= threshold.minimum_bounded_json_resolution_rate,
            bounded_json,
            f">={threshold.minimum_bounded_json_resolution_rate}",
        ),
        _gate(
            "tool_bounded_resolution",
            tool_resolution >= threshold.minimum_tool_bounded_resolution_rate,
            tool_resolution,
            f">={threshold.minimum_tool_bounded_resolution_rate}",
        ),
        _gate(
            "terminal_result_emission",
            terminal_result >= threshold.minimum_terminal_result_rate,
            terminal_result,
            f">={threshold.minimum_terminal_result_rate}",
        ),
        _gate(
            "observation_replay",
            replay >= threshold.minimum_observation_replay_rate,
            replay,
            f">={threshold.minimum_observation_replay_rate}",
        ),
        _gate(
            "authority_integrity",
            authority >= threshold.minimum_authority_integrity_rate,
            authority,
            f">={threshold.minimum_authority_integrity_rate}",
        ),
        _gate(
            "host_verification_repair",
            host_repair_rate <= threshold.maximum_host_verification_repair_rate,
            host_repair_rate,
            f"<={threshold.maximum_host_verification_repair_rate}",
        ),
        _gate(
            "budget_exhaustion",
            exhausted <= threshold.maximum_budget_exhaustion_count,
            float(exhausted),
            f"<={threshold.maximum_budget_exhaustion_count}",
        ),
    )
    passed = all(item.passed for item in gates)
    values = {
        "contract_id": contract.contract_id,
        "requested_rollout_count": contract.requested_qualification_rollouts,
        "recorded_rollout_count": len(outcomes),
        "cells": cells,
        "technical_gates": gates,
        "semantic_results_are_descriptive_only": True,
        "status": "passed" if passed else "failed",
        "outcome_set_hash": capability_outcome_set_hash(outcomes),
        "next_permitted_stage": (
            "capability_tier_localization" if passed else "protocol_repair_only"
        ),
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = CapabilityQualificationReport.model_construct(report_id="pending", **values)
    return CapabilityQualificationReport(report_id=qualification_report_id(provisional), **values)


def make_tier_localization_report(
    contract: FinanceCapabilityBoundaryContract,
    qualification: CapabilityQualificationReport,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> CapabilityTierLocalizationReport:
    if qualification.contract_id != contract.contract_id or qualification.status != "passed":
        raise ValueError("Tier Localization requires a passing Qualification report")
    _validate_outcomes(
        contract,
        outcomes,
        bindings=contract.localization_bindings,
        stage=BoundaryStage.TIER_LOCALIZATION,
        replicas=contract.localization_replicas,
    )
    bindings = {item.binding_id: item for item in contract.localization_bindings}
    cells = tuple(
        _tier_localization_cell(
            contract,
            model,
            runtime,
            family,
            tier,
            outcomes,
            bindings,
        )
        for model in ExplorerArm
        for runtime in CapabilityRuntimeArm
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for tier in DifficultyTier
    )
    selections = tuple(
        _select_runtime_family_tier(runtime, family, cells)
        for runtime in CapabilityRuntimeArm
        for family in CAPABILITY_SENSITIVE_FAMILIES
    )
    boundary_counts = {
        runtime: sum(
            item.boundary_identified
            for item in selections
            if item.runtime_arm == runtime
        )
        for runtime in CapabilityRuntimeArm
    }
    all_runtime_ready = all(
        boundary_counts[runtime]
        >= contract.localization_thresholds.minimum_runtime_boundary_families[runtime]
        for runtime in CapabilityRuntimeArm
    )
    frontier_compatible = all_runtime_ready and all(
        item.boundary_identified and item.selected_tier == DifficultyTier.FRONTIER
        for item in selections
    )
    by_cell = {
        (item.model_arm, item.runtime_arm, item.family, item.tier): item for item in cells
    }
    monotonic = [
        (
            by_cell[(model, runtime, family, DifficultyTier.EASY_CONTROL)].valid_success_rate
            >= by_cell[(model, runtime, family, DifficultyTier.FRONTIER)].valid_success_rate
            >= by_cell[(model, runtime, family, DifficultyTier.HARD_CONTROL)].valid_success_rate
        )
        for model in ExplorerArm
        for runtime in CapabilityRuntimeArm
        for family in CAPABILITY_SENSITIVE_FAMILIES
    ]
    next_stage = (
        "task_or_runtime_redesign_only"
        if not all_runtime_ready
        else (
            "paired_capability_calibration"
            if frontier_compatible
            else "calibration_contract_refreeze_required"
        )
    )
    values = {
        "contract_id": contract.contract_id,
        "qualification_report_id": qualification.report_id,
        "requested_rollout_count": contract.requested_localization_rollouts,
        "recorded_rollout_count": len(outcomes),
        "outcome_set_hash": capability_outcome_set_hash(outcomes),
        "cells": cells,
        "selections": selections,
        "boundary_family_count_by_runtime": boundary_counts,
        "monotonic_response_fraction": sum(monotonic) / len(monotonic),
        "all_runtime_localization_ready": all_runtime_ready,
        "calibration_frontier_compatible": frontier_compatible,
        "next_permitted_stage": next_stage,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = CapabilityTierLocalizationReport.model_construct(
        report_id="pending", **values
    )
    return CapabilityTierLocalizationReport(
        report_id=tier_localization_report_id(provisional), **values
    )


def make_empirical_information_audit(
    contract: FinanceCapabilityBoundaryContract,
    qualification: CapabilityQualificationReport,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> EmpiricalCapabilityInformationAudit:
    if qualification.contract_id != contract.contract_id or qualification.status != "passed":
        raise ValueError("paired calibration requires a passing Qualification report")
    _validate_outcomes(
        contract,
        outcomes,
        bindings=contract.calibration_bindings,
        stage=BoundaryStage.PAIRED_CALIBRATION,
        replicas=contract.calibration_replicas,
    )
    cells = tuple(
        _empirical_cell(contract, model, runtime, outcomes)
        for model in ExplorerArm
        for runtime in CapabilityRuntimeArm
    )
    family_runtime_intervals = _paired_gap_intervals(
        contract,
        outcomes,
        group_by="family_runtime",
    )
    family_intervals = {
        family: family_runtime_intervals[f"{CapabilityRuntimeArm.AUTONOMOUS_AGENT.value}|{family}"]
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    gaps = {family: interval.point for family, interval in family_intervals.items()}
    separating = sum(
        interval.lower >= contract.information_thresholds.minimum_family_model_gap
        for interval in family_intervals.values()
    )
    all_runtime_ready = all(item.passed for item in cells)
    ready = (
        all_runtime_ready
        and separating >= contract.information_thresholds.minimum_separating_family_count
    )
    values = {
        "contract_id": contract.contract_id,
        "qualification_report_id": qualification.report_id,
        "cells": cells,
        "minimum_separating_family_count": (
            contract.information_thresholds.minimum_separating_family_count
        ),
        "requested_rollout_count": contract.requested_calibration_rollouts,
        "recorded_rollout_count": len(outcomes),
        "outcome_set_hash": capability_outcome_set_hash(outcomes),
        "separating_family_count": separating,
        "paired_family_model_gaps": gaps,
        "paired_family_model_gap_intervals": family_intervals,
        "paired_runtime_model_gap_intervals": _paired_gap_intervals(
            contract,
            outcomes,
            group_by="runtime",
        ),
        "paired_family_runtime_gap_intervals": family_runtime_intervals,
        "primary_analysis_method": "task_cluster_paired_nested_bootstrap",
        "all_runtime_information_ready": all_runtime_ready,
        "empirical_capability_ready": ready,
        "next_permitted_stage": (
            "beneficiary_frontier_screening" if ready else "task_or_runtime_redesign_only"
        ),
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = EmpiricalCapabilityInformationAudit.model_construct(audit_id="pending", **values)
    return EmpiricalCapabilityInformationAudit(
        audit_id=empirical_information_audit_id(provisional), **values
    )


def _tier_localization_cell(
    contract: FinanceCapabilityBoundaryContract,
    model: ExplorerArm,
    runtime: CapabilityRuntimeArm,
    family: str,
    tier: DifficultyTier,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
    bindings: dict[str, RuntimeTaskBinding],
) -> TierLocalizationCell:
    selected = tuple(
        item
        for item in outcomes
        if item.model_arm == model
        and item.runtime_arm == runtime
        and item.family == family
        and bindings[item.binding_id].tier == tier
    )
    task_ids = {item.task_artifact_id for item in selected}
    if len(task_ids) != 1:
        raise ValueError("Tier Localization cell must contain exactly one task")
    technical_flags = [
        item.completed
        and item.bounded_json_resolution_success
        and item.terminal_result_emitted
        and item.observation_replay_success
        and item.authority_integrity_success
        and not item.budget_exhausted
        for item in selected
    ]
    technical_rate = sum(technical_flags) / len(selected)
    success_rate = sum(item.valid_success for item in selected) / len(selected)
    threshold = contract.localization_thresholds
    technical_ready = technical_rate >= threshold.minimum_technical_resolution_rate
    boundary = (
        technical_ready
        and threshold.boundary_probability_lower
        <= success_rate
        <= threshold.boundary_probability_upper
    )
    return TierLocalizationCell(
        model_arm=model,
        runtime_arm=runtime,
        family=family,
        tier=tier,
        task_artifact_id=next(iter(task_ids)),
        attempted_count=len(selected),
        technical_resolution_rate=technical_rate,
        semantic_answer_accuracy=sum(item.semantic_answer_correct for item in selected)
        / len(selected),
        valid_success_rate=success_rate,
        valid_success_interval=_wilson_interval(
            sum(item.valid_success for item in selected), len(selected)
        ),
        technical_ready=technical_ready,
        boundary_candidate=boundary,
    )


def _select_runtime_family_tier(
    runtime: CapabilityRuntimeArm,
    family: str,
    cells: tuple[TierLocalizationCell, ...],
) -> RuntimeFamilyTierSelection:
    by_key = {
        (item.model_arm, item.tier): item
        for item in cells
        if item.runtime_arm == runtime and item.family == family
    }
    tier_priority = {
        DifficultyTier.FRONTIER: 2,
        DifficultyTier.EASY_CONTROL: 1,
        DifficultyTier.HARD_CONTROL: 0,
    }
    options = []
    for tier in DifficultyTier:
        pro = by_key[(ExplorerArm.PRO, tier)]
        flash = by_key[(ExplorerArm.FLASH, tier)]
        information = (
            pro.valid_success_rate * (1.0 - pro.valid_success_rate)
            + flash.valid_success_rate * (1.0 - flash.valid_success_rate)
        ) / 2.0
        both_technical = pro.technical_ready and flash.technical_ready
        eligible = both_technical and (
            pro.boundary_candidate or flash.boundary_candidate
        )
        options.append((information, tier_priority[tier], tier, pro, flash, eligible))
    eligible_options = [item for item in options if item[-1]]
    diagnostic = max(options, key=lambda item: (item[0], item[1]))
    selected = (
        max(eligible_options, key=lambda item: (item[0], item[1]))
        if eligible_options
        else diagnostic
    )
    information, _, tier, pro, flash, eligible = selected
    return RuntimeFamilyTierSelection(
        runtime_arm=runtime,
        family=family,
        selected_tier=tier if eligible else None,
        selected_task_artifact_id=pro.task_artifact_id if eligible else None,
        combined_bernoulli_information=min(0.25, max(0.0, information)),
        pro_success_rate=pro.valid_success_rate,
        flash_success_rate=flash.valid_success_rate,
        both_models_technically_ready=pro.technical_ready and flash.technical_ready,
        boundary_identified=eligible,
    )


def _wilson_interval(successes: int, total: int) -> ConfidenceInterval:
    if total <= 0:
        raise ValueError("Wilson interval requires a positive denominator")
    point = successes / total
    z = 1.959963984540054
    denominator = 1.0 + z * z / total
    center = (point + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(point * (1.0 - point) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return ConfidenceInterval(
        lower=max(0.0, center - radius),
        point=point,
        upper=min(1.0, center + radius),
    )


def _qualification_cell(
    model: ExplorerArm,
    runtime: CapabilityRuntimeArm,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> QualificationCellSummary:
    selected = tuple(
        item for item in outcomes if item.model_arm == model and item.runtime_arm == runtime
    )
    return QualificationCellSummary(
        model_arm=model,
        runtime_arm=runtime,
        attempted_count=len(selected),
        completed_count=sum(item.completed for item in selected),
        api_call_count=sum(item.api_call_count for item in selected),
        raw_json_success_count=sum(item.json_contract_success_count for item in selected),
        contract_repair_count=sum(item.contract_repair_count for item in selected),
        bounded_json_success_count=sum(
            item.api_call_count - item.contract_repair_count
            for item in selected
            if item.bounded_json_resolution_success
        ),
        tool_call_count=sum(item.tool_call_count for item in selected),
        semantically_successful_tool_call_count=sum(
            item.semantically_successful_tool_call_count for item in selected
        ),
        bounded_tool_resolution_count=sum(item.bounded_tool_resolution_count for item in selected),
        runtime_infrastructure_failure_count=sum(
            item.runtime_infrastructure_failure_count for item in selected
        ),
        final_answer_count=sum(item.final_answer_emitted for item in selected),
        terminal_result_count=sum(item.terminal_result_emitted for item in selected),
        replay_success_count=sum(item.observation_replay_success for item in selected),
        authority_success_count=sum(item.authority_integrity_success for item in selected),
        host_verification_repair_count=sum(
            item.host_verification_repair_count for item in selected
        ),
        budget_exhaustion_count=sum(item.budget_exhausted for item in selected),
        semantic_correct_count=sum(item.semantic_answer_correct for item in selected),
        valid_success_count=sum(item.valid_success for item in selected),
    )


def _empirical_cell(
    contract: FinanceCapabilityBoundaryContract,
    model: ExplorerArm,
    runtime: CapabilityRuntimeArm,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> EmpiricalCapabilityCell:
    bindings = {
        item.binding_id: item
        for item in contract.calibration_bindings
        if item.runtime_arm == runtime
    }
    selected = tuple(
        item for item in outcomes if item.model_arm == model and item.runtime_arm == runtime
    )
    by_task: dict[str, list[CapabilityRolloutOutcome]] = defaultdict(list)
    for item in selected:
        by_task[item.task_artifact_id].append(item)
    rows = []
    for task_id, task_outcomes in sorted(by_task.items()):
        binding = bindings[task_outcomes[0].binding_id]
        rows.append(
            (
                task_id,
                binding.family,
                sum(item.valid_success for item in task_outcomes) / len(task_outcomes),
                binding.general_difficulty,
                [binding.visible_demand.values[axis] for axis in CAPABILITY_AXES],
                tuple(int(item.valid_success) for item in task_outcomes),
            )
        )
    raw, residual, marginal, family_info, general_fraction = _information_matrices(rows)
    raw_values = _eigenvalues(raw)
    residual_values = _eigenvalues(residual)
    positive = _positive_eigenvalues(residual_values)
    rank = len(positive)
    effective = _effective_rank(positive)
    condition = positive[0] / positive[-1] if positive else 1e12
    intervals = _bootstrap_axis_intervals(
        rows,
        replicates=contract.information_thresholds.bootstrap_replicates,
        seed=_stable_seed(contract.contract_id, model.value, runtime.value),
    )
    lower = contract.information_thresholds.boundary_probability_lower
    upper = contract.information_thresholds.boundary_probability_upper
    boundary_fraction = sum(lower <= row[2] <= upper for row in rows) / len(rows)
    minimum_axis = contract.information_thresholds.minimum_marginal_axis_information
    visible_axes = {
        axis for index, axis in enumerate(CAPABILITY_AXES) if any(row[4][index] > 0 for row in rows)
    }
    informative = sum(intervals[axis].lower >= minimum_axis for axis in visible_axes)
    threshold = contract.information_thresholds.by_runtime[runtime]
    passed = (
        rank >= threshold.minimum_rank
        and effective >= threshold.minimum_effective_rank
        and condition <= threshold.maximum_condition_number
        and boundary_fraction >= threshold.minimum_boundary_task_fraction
        and general_fraction <= threshold.maximum_general_factor_fraction
        and informative >= threshold.minimum_informative_axis_count
    )
    family_success = {
        family: sum(row[2] for row in rows if row[1] == family)
        / sum(row[1] == family for row in rows)
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    behavior = _behavioral_diagnostics(selected, by_task)
    return EmpiricalCapabilityCell(
        model_arm=model,
        runtime_arm=runtime,
        task_count=len(rows),
        rollout_count=len(selected),
        mean_success_rate=sum(row[2] for row in rows) / len(rows),
        boundary_task_fraction=boundary_fraction,
        raw_information_eigenvalues=raw_values,
        residual_information_eigenvalues=residual_values,
        residual_numerical_rank=rank,
        residual_effective_rank=effective,
        residual_condition_number=condition,
        general_factor_fraction=general_fraction,
        marginal_axis_information=marginal,
        marginal_axis_intervals=intervals,
        informative_axis_count=informative,
        family_information_contribution=family_info,
        family_success_rates=family_success,
        behavioral_diagnostics=behavior,
        passed=passed,
    )


def _behavioral_diagnostics(
    selected: tuple[CapabilityRolloutOutcome, ...],
    by_task: dict[str, list[CapabilityRolloutOutcome]],
) -> CapabilityBehavioralDiagnostics:
    entropies = []
    trace_diversities = []
    tool_sequence_diversities = []
    accepted_states: set[tuple[str, str]] = set()
    for task_id, task_outcomes in by_task.items():
        states = Counter(
            item.state_id
            for item in task_outcomes
            if item.valid_success and item.state_id is not None
        )
        total = sum(states.values())
        entropies.append(
            -sum((count / total) * math.log(count / total) for count in states.values() if total)
        )
        traces = {
            item.decision_trace_hash
            for item in task_outcomes
            if item.decision_trace_hash is not None
        }
        trace_count = sum(item.decision_trace_hash is not None for item in task_outcomes)
        trace_diversities.append(len(traces) / trace_count if trace_count else 0.0)
        tool_sequences = {
            item.tool_sequence_hash for item in task_outcomes if item.tool_sequence_hash is not None
        }
        tool_sequence_count = sum(item.tool_sequence_hash is not None for item in task_outcomes)
        tool_sequence_diversities.append(
            len(tool_sequences) / tool_sequence_count if tool_sequence_count else 0.0
        )
        accepted_states.update((task_id, state_id) for state_id in states)
    recovery_opportunities = sum(item.recovery_opportunity for item in selected)
    return CapabilityBehavioralDiagnostics(
        tool_semantic_success_rate=sum(item.tool_semantic_success for item in selected)
        / len(selected),
        verification_success_rate=sum(item.verification_success for item in selected)
        / len(selected),
        query_reformulation_rate=sum(item.query_reformulated for item in selected) / len(selected),
        recovery_opportunity_count=recovery_opportunities,
        recovery_success_rate=(
            sum(item.recovery_success for item in selected) / recovery_opportunities
            if recovery_opportunities
            else 0.0
        ),
        stop_quality_success_rate=sum(item.stop_quality_success for item in selected)
        / len(selected),
        accepted_state_count=len(accepted_states),
        mean_task_state_entropy=sum(entropies) / len(entropies),
        mean_decision_trace_diversity=sum(trace_diversities) / len(trace_diversities),
        mean_tool_sequence_diversity=(
            sum(tool_sequence_diversities) / len(tool_sequence_diversities)
        ),
        mean_tool_calls=sum(item.tool_call_count for item in selected) / len(selected),
        total_model_tokens=sum(item.total_model_tokens for item in selected),
        estimated_cost_usd=sum(item.estimated_cost_usd for item in selected),
        mean_api_latency_ms=sum(item.mean_api_latency_ms for item in selected) / len(selected),
    )


def _information_matrices(
    rows: list[tuple[str, str, float, float, list[float], tuple[int, ...]]],
) -> tuple[list[list[float]], list[list[float]], dict[str, float], dict[str, float], float]:
    demands = [row[4] for row in rows]
    general = [row[3] for row in rows]
    centered = _center_columns(demands)
    residual = _residualize(centered, general)
    weights = [row[2] * (1.0 - row[2]) for row in rows]
    # This is the preregistered empirical Fisher-style second moment
    # E[p(1-p) a a^T]. Centering belongs only to the axis-specific diagnostic.
    raw_matrix = _weighted_second_moment(demands, weights)
    centered_matrix = _weighted_second_moment(centered, weights)
    residual_matrix = _weighted_second_moment(residual, weights)
    marginal = {
        axis: round(residual_matrix[index][index], 12) for index, axis in enumerate(CAPABILITY_AXES)
    }
    total = sum(marginal.values())
    family_info = {}
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        indices = [index for index, row in enumerate(rows) if row[1] == family]
        value = sum(
            weights[index] * sum(component * component for component in residual[index])
            for index in indices
        ) / len(rows)
        family_info[family] = round(value / total if total else 0.0, 12)
    centered_trace = sum(centered_matrix[index][index] for index in range(len(CAPABILITY_AXES)))
    residual_trace = sum(residual_matrix[index][index] for index in range(len(CAPABILITY_AXES)))
    general_fraction = (
        min(1.0, max(0.0, 1.0 - residual_trace / centered_trace)) if centered_trace else 1.0
    )
    return raw_matrix, residual_matrix, marginal, family_info, general_fraction


def _bootstrap_axis_intervals(
    rows: list[tuple[str, str, float, float, list[float], tuple[int, ...]]],
    *,
    replicates: int,
    seed: int,
) -> dict[str, ConfidenceInterval]:
    rng = random.Random(seed)
    by_family = {
        family: [row for row in rows if row[1] == family]
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    samples: dict[str, list[float]] = {axis: [] for axis in CAPABILITY_AXES}
    point = _information_matrices(rows)[2]
    for _ in range(replicates):
        resampled = []
        for family_rows in by_family.values():
            for _ in range(len(family_rows)):
                row = rng.choice(family_rows)
                realization_sample = tuple(rng.choice(row[5]) for _ in range(len(row[5])))
                resampled.append(
                    (
                        row[0],
                        row[1],
                        sum(realization_sample) / len(realization_sample),
                        row[3],
                        row[4],
                        realization_sample,
                    )
                )
        marginal = _information_matrices(resampled)[2]
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


def _paired_gap_intervals(
    contract: FinanceCapabilityBoundaryContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
    *,
    group_by: Literal["runtime", "family_runtime"],
) -> dict[str, SignedConfidenceInterval]:
    by_task_model: dict[tuple[str, CapabilityRuntimeArm, ExplorerArm], list[int]] = defaultdict(
        list
    )
    family_by_task: dict[str, str] = {}
    for item in outcomes:
        by_task_model[(item.task_artifact_id, item.runtime_arm, item.model_arm)].append(
            int(item.valid_success)
        )
        family_by_task[item.task_artifact_id] = item.family
    grouped_tasks: dict[str, list[tuple[tuple[int, ...], tuple[int, ...]]]] = defaultdict(list)
    for runtime in CapabilityRuntimeArm:
        task_ids = sorted(
            {
                task_id
                for task_id, observed_runtime, _ in by_task_model
                if observed_runtime == runtime
            }
        )
        for task_id in task_ids:
            key = (
                runtime.value
                if group_by == "runtime"
                else f"{runtime.value}|{family_by_task[task_id]}"
            )
            grouped_tasks[key].append(
                (
                    tuple(by_task_model[(task_id, runtime, ExplorerArm.PRO)]),
                    tuple(by_task_model[(task_id, runtime, ExplorerArm.FLASH)]),
                )
            )
    output: dict[str, SignedConfidenceInterval] = {}
    for key, pairs in sorted(grouped_tasks.items()):
        point = sum(_mean_binary(pro) - _mean_binary(flash) for pro, flash in pairs) / len(pairs)
        rng = random.Random(_stable_seed(contract.contract_id, "paired_gap", key))
        estimates = []
        for _ in range(contract.information_thresholds.bootstrap_replicates):
            sampled = [rng.choice(pairs) for _ in range(len(pairs))]
            task_gaps = []
            for pro, flash in sampled:
                pro_sample = tuple(rng.choice(pro) for _ in range(len(pro)))
                flash_sample = tuple(rng.choice(flash) for _ in range(len(flash)))
                task_gaps.append(_mean_binary(pro_sample) - _mean_binary(flash_sample))
            estimates.append(sum(task_gaps) / len(task_gaps))
        point_value = round(point, 9)
        output[key] = SignedConfidenceInterval(
            lower=min(_quantile(estimates, 0.025), point_value),
            point=point_value,
            upper=max(_quantile(estimates, 0.975), point_value),
        )
    return output


def _mean_binary(values: tuple[int, ...]) -> float:
    return sum(values) / len(values)


def _validate_outcomes(
    contract: FinanceCapabilityBoundaryContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
    *,
    bindings: tuple[RuntimeTaskBinding, ...],
    stage: BoundaryStage,
    replicas: int,
) -> None:
    by_id = {item.binding_id: item for item in bindings}
    expected = {
        (model, binding.binding_id, replicate)
        for model in ExplorerArm
        for binding in bindings
        for replicate in range(replicas)
    }
    observed = {(item.model_arm, item.binding_id, item.replicate) for item in outcomes}
    if len(observed) != len(outcomes) or observed != expected:
        raise ValueError("capability outcomes do not exactly cover the frozen jobs")
    for item in outcomes:
        binding = by_id.get(item.binding_id)
        if binding is None:
            raise ValueError("capability outcome uses an unknown binding")
        if item.contract_id != contract.contract_id or item.stage != stage:
            raise ValueError("capability outcome belongs to another contract or stage")
        if (
            item.task_artifact_id != binding.task_artifact_id
            or item.family != binding.family
            or item.runtime_arm != binding.runtime_arm
        ):
            raise ValueError("capability outcome differs from its frozen binding")


def _qualification_cell_values(
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> dict[tuple[ExplorerArm, CapabilityRuntimeArm], tuple[CapabilityRolloutOutcome, ...]]:
    return {
        (model, runtime): tuple(
            item for item in outcomes if item.model_arm == model and item.runtime_arm == runtime
        )
        for model in ExplorerArm
        for runtime in CapabilityRuntimeArm
    }


def _gate(gate_id: str, passed: bool, observed: float, requirement: str) -> TechnicalGate:
    return TechnicalGate(
        gate_id=gate_id,
        passed=passed,
        observed={gate_id: observed},
        requirement=requirement,
    )


def _center_columns(values: list[list[float]]) -> list[list[float]]:
    means = [sum(row[index] for row in values) / len(values) for index in range(len(values[0]))]
    return [[value - means[index] for index, value in enumerate(row)] for row in values]


def _residualize(values: list[list[float]], general: list[float]) -> list[list[float]]:
    mean_general = sum(general) / len(general)
    centered_general = [value - mean_general for value in general]
    variance = sum(value * value for value in centered_general)
    if variance <= 1e-15:
        return values
    output = [[0.0 for _ in row] for row in values]
    for axis in range(len(values[0])):
        slope = (
            sum(centered_general[index] * row[axis] for index, row in enumerate(values)) / variance
        )
        for index, row in enumerate(values):
            output[index][axis] = row[axis] - slope * centered_general[index]
    return output


def _weighted_second_moment(values: list[list[float]], weights: list[float]) -> list[list[float]]:
    size = len(values[0])
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    for value, weight in zip(values, weights, strict=True):
        for row in range(size):
            for column in range(size):
                matrix[row][column] += weight * value[row] * value[column] / len(values)
    return matrix


def _eigenvalues(matrix: list[list[float]]) -> tuple[float, ...]:
    return tuple(
        round(max(0.0, value), 12) for value in sorted(_symmetric_eigenvalues(matrix), reverse=True)
    )


def _positive_eigenvalues(values: tuple[float, ...]) -> list[float]:
    maximum = max(values, default=0.0)
    return [value for value in values if maximum > 0 and value > maximum * 1e-6]


def _effective_rank(values: list[float]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    probabilities = [value / total for value in values]
    return math.exp(-sum(value * math.log(value) for value in probabilities if value > 0))


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _stable_seed(*values: str) -> int:
    digest = canonical_hash(values, prefix="capability_bootstrap_seed:")
    return int(digest.rsplit(":", 1)[-1][:16], 16)


def capability_outcome_set_hash(
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> str:
    return canonical_hash(
        tuple(sorted(item.outcome_id for item in outcomes)),
        prefix="capability_rollout_outcome_set:",
    )


def capability_rollout_outcome_id(value: CapabilityRolloutOutcome) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"outcome_id"}),
        prefix="capability_rollout_outcome:",
    )


def qualification_report_id(value: CapabilityQualificationReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="capability_qualification_report:",
    )


def tier_localization_report_id(value: CapabilityTierLocalizationReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="capability_tier_localization_report:",
    )


def empirical_information_audit_id(value: EmpiricalCapabilityInformationAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="empirical_capability_information_audit:",
    )
