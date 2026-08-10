from __future__ import annotations

import statistics
from collections import Counter
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import MODEL_FORBIDDEN_FIELD_NAMES
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

AGENT_RUNTIME_PILOT_CONTRACT_VERSION = "agent_runtime_pilot_contract.v1"
AGENT_RUNTIME_PILOT_REPORT_VERSION = "agent_runtime_pilot_report.v1"
AGENT_RUNTIME_PILOT_CONTRACT_PREFIX = "agent_runtime_pilot_contract:"
AGENT_RUNTIME_PILOT_REPORT_PREFIX = "agent_runtime_pilot_report:"

REQUIRED_HIDDEN_FIELDS = MODEL_FORBIDDEN_FIELD_NAMES


class AgentPilotArm(str, Enum):
    DIRECT_BARE = "direct_bare"
    SCRIPTED_TOOL = "scripted_tool"
    AUTONOMOUS_AGENT = "autonomous_agent"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AgentPilotArmContract(FrozenModel):
    arm: AgentPilotArm
    model_decision_authorities: tuple[str, ...] = Field(min_length=1)
    host_decision_authorities: tuple[str, ...] = Field(min_length=1)
    uses_tool_environment: bool
    script_policy_hash: str | None = None
    token_budget: int = Field(ge=1)
    tool_call_budget: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_arm(self) -> AgentPilotArmContract:
        model_authority = set(self.model_decision_authorities)
        host_authority = set(self.host_decision_authorities)
        if model_authority & host_authority:
            raise ValueError("Agent Pilot model and Host authorities overlap")
        if self.arm == AgentPilotArm.DIRECT_BARE:
            if self.uses_tool_environment or self.tool_call_budget or self.script_policy_hash:
                raise ValueError("Direct/Bare arm cannot use the Agent tool environment")
        elif self.arm == AgentPilotArm.SCRIPTED_TOOL:
            if not self.uses_tool_environment or not self.script_policy_hash:
                raise ValueError("Scripted Tool arm requires a frozen script policy")
            if "tool_selection" in model_authority:
                raise ValueError("Scripted Tool arm cannot grant tool selection to the model")
        else:
            if not self.uses_tool_environment or self.script_policy_hash:
                raise ValueError("Autonomous Agent arm must choose tools without a Host script")
            required = {
                "tool_selection",
                "query_construction",
                "continue_or_stop",
                "failure_recovery",
                "answer_generation",
            }
            if not required <= model_authority:
                raise ValueError("Autonomous Agent arm lacks required model decisions")
        return self


class AgentRuntimePilotThresholds(FrozenModel):
    minimum_validity_rate: float = Field(ge=0, le=1)
    maximum_validity_drop_vs_scripted: float = Field(ge=0, le=1)
    minimum_state_entropy_gain: float = Field(ge=0)
    minimum_accepted_state_gain: float = Field(ge=0)
    minimum_paired_diversity_task_fraction: float = Field(gt=0, le=1)
    minimum_nontrivial_agent_state_rate: float = Field(gt=0, le=1)
    minimum_tool_call_success_rate: float = Field(gt=0, le=1)
    minimum_evidence_provenance_completeness: float = Field(gt=0, le=1)
    minimum_stop_decision_quality_rate: float = Field(gt=0, le=1)
    near_mpe_ratio_threshold: float = Field(gt=0, le=1)
    minimum_near_mpe_rate_gain: float = Field(ge=0, le=1)
    minimum_meaningful_coordinate_rate_gain: float = Field(ge=0, le=1)
    minimum_differential_token_fraction: float = Field(gt=0, le=1)
    minimum_differential_gradient_fraction: float = Field(gt=0, le=1)


class AgentRuntimePilotContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    run_role: Literal["development_agent_runtime_pilot_only"] = (
        "development_agent_runtime_pilot_only"
    )
    task_population_manifest_hash: str = Field(min_length=1)
    task_family_by_id: dict[str, str] = Field(min_length=24, max_length=30)
    exact_target_task_ids: tuple[str, ...] = Field(min_length=12, max_length=18)
    model_config_hash: str = Field(min_length=1)
    beneficiary_checkpoint_hash: str = Field(min_length=1)
    validity_verifier_manifest_hash: str = Field(min_length=1)
    quotient_state_mapper_manifest_hash: str = Field(min_length=1)
    exact_target_design_manifest_hash: str = Field(min_length=1)
    tool_environment: AgentToolEnvironmentManifest
    arms: tuple[AgentPilotArmContract, ...] = Field(min_length=3, max_length=3)
    unconditional_runs_per_task_arm: int = Field(ge=8, le=12)
    state_conditioned_attempts_per_state: int = Field(ge=5, le=8)
    explorer_identity: str = Field(min_length=1)
    trajectory_state_catalog_version: str = Field(min_length=1)
    reachability_manifest_version: str = Field(min_length=1)
    initial_distribution_version: str = Field(min_length=1)
    materialization_contract_version: str = Field(min_length=1)
    excluded_population_manifest_hashes: tuple[str, ...] = Field(min_length=1)
    hidden_model_fields: tuple[str, ...] = Field(min_length=len(REQUIRED_HIDDEN_FIELDS))
    thresholds: AgentRuntimePilotThresholds
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    gp_c_evaluated: Literal[False] = False
    contribution_approximation_authorized: Literal[False] = False
    production_contribution: float = Field(default=0.0, ge=0, le=0)
    schema_version: str = AGENT_RUNTIME_PILOT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> AgentRuntimePilotContract:
        family_counts = Counter(self.task_family_by_id.values())
        if len(family_counts) != 6 or any(count not in {4, 5} for count in family_counts.values()):
            raise ValueError("Agent Pilot requires six task families with four or five tasks each")
        if len(self.exact_target_task_ids) != len(set(self.exact_target_task_ids)):
            raise ValueError("Agent Pilot exact-target tasks are duplicated")
        if not set(self.exact_target_task_ids) <= set(self.task_family_by_id):
            raise ValueError("Agent Pilot exact-target tasks must belong to the Pilot population")
        exact_family_counts = Counter(
            self.task_family_by_id[task_id] for task_id in self.exact_target_task_ids
        )
        if set(exact_family_counts) != set(family_counts) or any(
            count not in {2, 3} for count in exact_family_counts.values()
        ):
            raise ValueError("Agent Pilot exact-target subset must contain two or three per family")
        arm_by_id = {item.arm: item for item in self.arms}
        if set(arm_by_id) != set(AgentPilotArm):
            raise ValueError("Agent Pilot requires Direct, Scripted, and Autonomous arms")
        if len(arm_by_id) != len(self.arms):
            raise ValueError("Agent Pilot arms are duplicated")
        scripted = arm_by_id[AgentPilotArm.SCRIPTED_TOOL]
        autonomous = arm_by_id[AgentPilotArm.AUTONOMOUS_AGENT]
        if (
            scripted.token_budget != autonomous.token_budget
            or scripted.tool_call_budget != autonomous.tool_call_budget
        ):
            raise ValueError("Scripted and Autonomous arms require identical budgets")
        if scripted.tool_call_budget > self.tool_environment.maximum_tool_calls:
            raise ValueError("Agent Pilot arm exceeds the frozen environment tool budget")
        if len(self.excluded_population_manifest_hashes) != len(
            set(self.excluded_population_manifest_hashes)
        ):
            raise ValueError("Agent Pilot exclusion manifests are duplicated")
        if not REQUIRED_HIDDEN_FIELDS <= set(self.hidden_model_fields):
            raise ValueError("Agent Pilot does not hide every Oracle-only field")
        if self.contract_id != agent_runtime_pilot_contract_id(self):
            raise ValueError("Agent Runtime Pilot contract identity is invalid")
        return self


class AgentPilotTaskArmMetrics(FrozenModel):
    task_id: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    arm: AgentPilotArm
    unconditional_run_count: int = Field(ge=1)
    valid_run_count: int = Field(ge=0)
    validity_rate: float = Field(ge=0, le=1)
    accepted_state_count: int = Field(ge=0)
    natural_state_entropy: float = Field(ge=0)
    decision_trace_diversity_rate: float = Field(ge=0, le=1)
    tool_call_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    failed_tool_call_count: int = Field(ge=0)
    tool_call_success_rate: float = Field(ge=0, le=1)
    query_reformulation_rate: float = Field(ge=0, le=1)
    error_recovery_rate: float = Field(ge=0, le=1)
    evidence_provenance_completeness: float = Field(ge=0, le=1)
    verification_success_rate: float = Field(ge=0, le=1)
    stop_decision_quality_rate: float = Field(ge=0, le=1)
    nontrivial_agent_state_rate: float = Field(ge=0, le=1)
    off_target_transition_rate: float = Field(ge=0, le=1)
    state_conditioned_attempt_count: int = Field(ge=0)
    state_conditioned_on_target_rate: float = Field(ge=0, le=1)
    reachability_interval_mean_width: float = Field(ge=0, le=1)
    differential_token_fraction: float = Field(ge=0, le=1)
    differential_gradient_fraction: float = Field(ge=0, le=1)
    mean_update_vector_distance: float = Field(ge=0)
    exact_target_coordinate_count: int = Field(ge=0)
    near_mpe_ratio_threshold: float = Field(gt=0, le=1)
    near_mpe_coordinate_count: int = Field(ge=0)
    meaningful_coordinate_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_metrics(self) -> AgentPilotTaskArmMetrics:
        if self.valid_run_count > self.unconditional_run_count:
            raise ValueError("Agent Pilot valid runs exceed attempts")
        if abs(self.validity_rate - self.valid_run_count / self.unconditional_run_count) > 1e-9:
            raise ValueError("Agent Pilot validity rate is inconsistent")
        if self.successful_tool_call_count + self.failed_tool_call_count != self.tool_call_count:
            raise ValueError("Agent Pilot tool-call accounting is inconsistent")
        expected_tool_rate = (
            self.successful_tool_call_count / self.tool_call_count if self.tool_call_count else 0.0
        )
        if abs(self.tool_call_success_rate - expected_tool_rate) > 1e-9:
            raise ValueError("Agent Pilot tool success rate is inconsistent")
        if self.near_mpe_coordinate_count > self.exact_target_coordinate_count:
            raise ValueError("near-MPE coordinates exceed exact-target support")
        if self.meaningful_coordinate_count > self.near_mpe_coordinate_count:
            raise ValueError("meaningful coordinates must be included in near-MPE support")
        if self.arm == AgentPilotArm.DIRECT_BARE and self.tool_call_count:
            raise ValueError("Direct/Bare metrics cannot contain Host tool calls")
        return self


class AgentPilotArmSummary(FrozenModel):
    arm: AgentPilotArm
    task_count: int = Field(ge=1)
    mean_validity_rate: float = Field(ge=0, le=1)
    mean_accepted_state_count: float = Field(ge=0)
    mean_natural_state_entropy: float = Field(ge=0)
    mean_decision_trace_diversity_rate: float = Field(ge=0, le=1)
    mean_tool_call_success_rate: float = Field(ge=0, le=1)
    mean_evidence_provenance_completeness: float = Field(ge=0, le=1)
    mean_stop_decision_quality_rate: float = Field(ge=0, le=1)
    mean_nontrivial_agent_state_rate: float = Field(ge=0, le=1)
    mean_query_reformulation_rate: float = Field(ge=0, le=1)
    mean_error_recovery_rate: float = Field(ge=0, le=1)
    mean_differential_token_fraction: float = Field(ge=0, le=1)
    mean_differential_gradient_fraction: float = Field(ge=0, le=1)
    exact_target_coordinate_count: int = Field(ge=0)
    near_mpe_coordinate_rate: float = Field(ge=0, le=1)
    meaningful_coordinate_rate: float = Field(ge=0, le=1)


class AgentPilotGateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    passed: bool
    observed: dict[str, float]
    requirement: str = Field(min_length=1)


class AgentRuntimePilotReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    metrics_hash: str = Field(min_length=1)
    arm_trajectory_manifest_hashes: dict[AgentPilotArm, str] = Field(min_length=3, max_length=3)
    state_catalog_manifest_hash: str = Field(min_length=1)
    reachability_manifest_hash: str = Field(min_length=1)
    exact_target_report_hash: str = Field(min_length=1)
    arm_summaries: tuple[AgentPilotArmSummary, ...] = Field(min_length=3, max_length=3)
    paired_diversity_improvement_task_fraction: float = Field(ge=0, le=1)
    gates: tuple[AgentPilotGateResult, ...] = Field(min_length=5)
    decision: Literal["advance_to_frontier_screening", "stop_and_redesign_agent_environment"]
    next_permitted_stage: Literal[
        "beneficiary_frontier_screening",
        "agent_environment_redesign",
    ]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    gp_c_evaluated: Literal[False] = False
    contribution_approximation_authorized: Literal[False] = False
    production_contribution: float = Field(default=0.0, ge=0, le=0)
    status: Literal["passed", "failed"]
    schema_version: str = AGENT_RUNTIME_PILOT_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> AgentRuntimePilotReport:
        if set(self.arm_trajectory_manifest_hashes) != set(AgentPilotArm):
            raise ValueError("Agent Pilot report lacks a trajectory manifest for every arm")
        passed = all(item.passed for item in self.gates)
        if passed != (self.status == "passed"):
            raise ValueError("Agent Pilot report status differs from its gates")
        expected_decision = (
            "advance_to_frontier_screening" if passed else "stop_and_redesign_agent_environment"
        )
        expected_stage = (
            "beneficiary_frontier_screening" if passed else "agent_environment_redesign"
        )
        if self.decision != expected_decision or self.next_permitted_stage != expected_stage:
            raise ValueError("Agent Pilot report violates the fail-closed transition")
        if self.report_id != agent_runtime_pilot_report_id(self):
            raise ValueError("Agent Runtime Pilot report identity is invalid")
        return self


def make_agent_runtime_pilot_contract(
    *,
    run_id: str,
    task_population_manifest_hash: str,
    task_family_by_id: dict[str, str],
    exact_target_task_ids: tuple[str, ...],
    model_config_hash: str,
    beneficiary_checkpoint_hash: str,
    validity_verifier_manifest_hash: str,
    quotient_state_mapper_manifest_hash: str,
    exact_target_design_manifest_hash: str,
    tool_environment: AgentToolEnvironmentManifest,
    arms: tuple[AgentPilotArmContract, ...],
    unconditional_runs_per_task_arm: int,
    state_conditioned_attempts_per_state: int,
    explorer_identity: str,
    trajectory_state_catalog_version: str,
    reachability_manifest_version: str,
    initial_distribution_version: str,
    materialization_contract_version: str,
    excluded_population_manifest_hashes: tuple[str, ...],
    thresholds: AgentRuntimePilotThresholds,
) -> AgentRuntimePilotContract:
    values = {
        "run_id": run_id,
        "run_role": "development_agent_runtime_pilot_only",
        "task_population_manifest_hash": task_population_manifest_hash,
        "task_family_by_id": task_family_by_id,
        "exact_target_task_ids": exact_target_task_ids,
        "model_config_hash": model_config_hash,
        "beneficiary_checkpoint_hash": beneficiary_checkpoint_hash,
        "validity_verifier_manifest_hash": validity_verifier_manifest_hash,
        "quotient_state_mapper_manifest_hash": quotient_state_mapper_manifest_hash,
        "exact_target_design_manifest_hash": exact_target_design_manifest_hash,
        "tool_environment": tool_environment,
        "arms": arms,
        "unconditional_runs_per_task_arm": unconditional_runs_per_task_arm,
        "state_conditioned_attempts_per_state": state_conditioned_attempts_per_state,
        "explorer_identity": explorer_identity,
        "trajectory_state_catalog_version": trajectory_state_catalog_version,
        "reachability_manifest_version": reachability_manifest_version,
        "initial_distribution_version": initial_distribution_version,
        "materialization_contract_version": materialization_contract_version,
        "excluded_population_manifest_hashes": excluded_population_manifest_hashes,
        "hidden_model_fields": tuple(sorted(REQUIRED_HIDDEN_FIELDS)),
        "thresholds": thresholds,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "schema_version": AGENT_RUNTIME_PILOT_CONTRACT_VERSION,
    }
    provisional = AgentRuntimePilotContract.model_construct(contract_id="pending", **values)
    return AgentRuntimePilotContract(
        contract_id=agent_runtime_pilot_contract_id(provisional),
        **values,
    )


def evaluate_agent_runtime_pilot(
    contract: AgentRuntimePilotContract,
    metrics: tuple[AgentPilotTaskArmMetrics, ...],
    *,
    arm_trajectory_manifest_hashes: dict[AgentPilotArm, str],
    state_catalog_manifest_hash: str,
    reachability_manifest_hash: str,
    exact_target_report_hash: str,
) -> AgentRuntimePilotReport:
    expected_keys = {
        (task_id, arm) for task_id in contract.task_family_by_id for arm in AgentPilotArm
    }
    observed_keys = {(item.task_id, item.arm) for item in metrics}
    if observed_keys != expected_keys or len(observed_keys) != len(metrics):
        raise ValueError("Agent Pilot metrics do not exactly cover Task x Arm")
    by_key = {(item.task_id, item.arm): item for item in metrics}
    for item in metrics:
        if item.task_family != contract.task_family_by_id[item.task_id]:
            raise ValueError("Agent Pilot metric uses the wrong task family")
        if item.unconditional_run_count != contract.unconditional_runs_per_task_arm:
            raise ValueError("Agent Pilot metric violates the frozen run count")
        is_target = item.task_id in contract.exact_target_task_ids
        if is_target and item.exact_target_coordinate_count < 1:
            raise ValueError("exact-target Pilot task has no measured coordinate")
        if not is_target and item.exact_target_coordinate_count:
            raise ValueError("non-target Pilot task contains exact-target outcomes")
        if is_target and item.state_conditioned_attempt_count < (
            item.exact_target_coordinate_count * contract.state_conditioned_attempts_per_state
        ):
            raise ValueError("Agent Pilot state-conditioned support is incomplete")
        if (
            abs(item.near_mpe_ratio_threshold - contract.thresholds.near_mpe_ratio_threshold)
            > 1e-12
        ):
            raise ValueError("Agent Pilot near-MPE threshold differs from its contract")

    summaries = tuple(_summarize_arm(arm, metrics) for arm in AgentPilotArm)
    summary = {item.arm: item for item in summaries}
    direct = summary[AgentPilotArm.DIRECT_BARE]
    scripted = summary[AgentPilotArm.SCRIPTED_TOOL]
    autonomous = summary[AgentPilotArm.AUTONOMOUS_AGENT]
    paired_improvements = []
    for task_id in contract.task_family_by_id:
        auto_row = by_key[(task_id, AgentPilotArm.AUTONOMOUS_AGENT)]
        baselines = (
            by_key[(task_id, AgentPilotArm.DIRECT_BARE)],
            by_key[(task_id, AgentPilotArm.SCRIPTED_TOOL)],
        )
        paired_improvements.append(
            auto_row.accepted_state_count > max(item.accepted_state_count for item in baselines)
            or auto_row.natural_state_entropy
            > max(item.natural_state_entropy for item in baselines)
        )
    paired_fraction = statistics.fmean(paired_improvements)
    thresholds = contract.thresholds
    entropy_gain = autonomous.mean_natural_state_entropy - max(
        direct.mean_natural_state_entropy,
        scripted.mean_natural_state_entropy,
    )
    state_gain = autonomous.mean_accepted_state_count - max(
        direct.mean_accepted_state_count,
        scripted.mean_accepted_state_count,
    )
    diversity_pass = (
        entropy_gain >= thresholds.minimum_state_entropy_gain
        or state_gain >= thresholds.minimum_accepted_state_gain
    ) and paired_fraction >= thresholds.minimum_paired_diversity_task_fraction
    behavior_pass = (
        autonomous.mean_nontrivial_agent_state_rate
        >= thresholds.minimum_nontrivial_agent_state_rate
        and (
            autonomous.mean_query_reformulation_rate > 0 or autonomous.mean_error_recovery_rate > 0
        )
    )
    validity_pass = (
        autonomous.mean_validity_rate >= thresholds.minimum_validity_rate
        and autonomous.mean_validity_rate
        >= scripted.mean_validity_rate - thresholds.maximum_validity_drop_vs_scripted
        and autonomous.mean_tool_call_success_rate >= thresholds.minimum_tool_call_success_rate
        and autonomous.mean_evidence_provenance_completeness
        >= thresholds.minimum_evidence_provenance_completeness
        and autonomous.mean_stop_decision_quality_rate
        >= thresholds.minimum_stop_decision_quality_rate
    )
    near_gain = autonomous.near_mpe_coordinate_rate - max(
        direct.near_mpe_coordinate_rate,
        scripted.near_mpe_coordinate_rate,
    )
    meaningful_gain = autonomous.meaningful_coordinate_rate - max(
        direct.meaningful_coordinate_rate,
        scripted.meaningful_coordinate_rate,
    )
    target_pass = (
        near_gain > thresholds.minimum_near_mpe_rate_gain
        or meaningful_gain > thresholds.minimum_meaningful_coordinate_rate_gain
    )
    differential_pass = (
        autonomous.mean_differential_token_fraction
        >= thresholds.minimum_differential_token_fraction
        and autonomous.mean_differential_gradient_fraction
        >= thresholds.minimum_differential_gradient_fraction
    )
    gates = (
        AgentPilotGateResult(
            gate_id="state_space_gain",
            passed=diversity_pass,
            observed={
                "entropy_gain": entropy_gain,
                "accepted_state_gain": state_gain,
                "paired_improvement_task_fraction": paired_fraction,
            },
            requirement="aggregate entropy or state coverage gain plus paired task support",
        ),
        AgentPilotGateResult(
            gate_id="nontrivial_agent_behavior",
            passed=behavior_pass,
            observed={
                "nontrivial_agent_state_rate": autonomous.mean_nontrivial_agent_state_rate,
                "query_reformulation_rate": autonomous.mean_query_reformulation_rate,
                "error_recovery_rate": autonomous.mean_error_recovery_rate,
            },
            requirement="nontrivial planning, verification, reformulation, or recovery states",
        ),
        AgentPilotGateResult(
            gate_id="validity_and_grounding",
            passed=validity_pass,
            observed={
                "validity_rate": autonomous.mean_validity_rate,
                "scripted_validity_rate": scripted.mean_validity_rate,
                "tool_call_success_rate": autonomous.mean_tool_call_success_rate,
                "evidence_provenance_completeness": (
                    autonomous.mean_evidence_provenance_completeness
                ),
                "stop_decision_quality_rate": autonomous.mean_stop_decision_quality_rate,
            },
            requirement="acceptable validity without sacrificing provenance or stop quality",
        ),
        AgentPilotGateResult(
            gate_id="exact_target_sensitivity",
            passed=target_pass,
            observed={
                "near_mpe_rate_gain": near_gain,
                "meaningful_coordinate_rate_gain": meaningful_gain,
            },
            requirement="more near-MPE or meaningful coordinates than both baselines",
        ),
        AgentPilotGateResult(
            gate_id="not_length_only",
            passed=differential_pass,
            observed={
                "differential_token_fraction": autonomous.mean_differential_token_fraction,
                "differential_gradient_fraction": autonomous.mean_differential_gradient_fraction,
            },
            requirement="Agent differences must affect both supervision tokens and gradients",
        ),
    )
    passed = all(item.passed for item in gates)
    values = {
        "contract_id": contract.contract_id,
        "metrics_hash": canonical_hash(
            tuple(item.model_dump(mode="json") for item in metrics),
            prefix="agent_runtime_pilot_metrics:",
        ),
        "arm_trajectory_manifest_hashes": arm_trajectory_manifest_hashes,
        "state_catalog_manifest_hash": state_catalog_manifest_hash,
        "reachability_manifest_hash": reachability_manifest_hash,
        "exact_target_report_hash": exact_target_report_hash,
        "arm_summaries": summaries,
        "paired_diversity_improvement_task_fraction": paired_fraction,
        "gates": gates,
        "decision": (
            "advance_to_frontier_screening" if passed else "stop_and_redesign_agent_environment"
        ),
        "next_permitted_stage": (
            "beneficiary_frontier_screening" if passed else "agent_environment_redesign"
        ),
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "status": "passed" if passed else "failed",
        "schema_version": AGENT_RUNTIME_PILOT_REPORT_VERSION,
    }
    provisional = AgentRuntimePilotReport.model_construct(report_id="pending", **values)
    return AgentRuntimePilotReport(
        report_id=agent_runtime_pilot_report_id(provisional),
        **values,
    )


def agent_runtime_pilot_contract_id(value: AgentRuntimePilotContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix=AGENT_RUNTIME_PILOT_CONTRACT_PREFIX,
    )


def agent_runtime_pilot_report_id(value: AgentRuntimePilotReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix=AGENT_RUNTIME_PILOT_REPORT_PREFIX,
    )


def _summarize_arm(
    arm: AgentPilotArm,
    metrics: tuple[AgentPilotTaskArmMetrics, ...],
) -> AgentPilotArmSummary:
    rows = [item for item in metrics if item.arm == arm]
    coordinate_count = sum(item.exact_target_coordinate_count for item in rows)
    near_count = sum(item.near_mpe_coordinate_count for item in rows)
    meaningful_count = sum(item.meaningful_coordinate_count for item in rows)
    return AgentPilotArmSummary(
        arm=arm,
        task_count=len(rows),
        mean_validity_rate=statistics.fmean(item.validity_rate for item in rows),
        mean_accepted_state_count=statistics.fmean(item.accepted_state_count for item in rows),
        mean_natural_state_entropy=statistics.fmean(item.natural_state_entropy for item in rows),
        mean_decision_trace_diversity_rate=statistics.fmean(
            item.decision_trace_diversity_rate for item in rows
        ),
        mean_tool_call_success_rate=statistics.fmean(item.tool_call_success_rate for item in rows),
        mean_evidence_provenance_completeness=statistics.fmean(
            item.evidence_provenance_completeness for item in rows
        ),
        mean_stop_decision_quality_rate=statistics.fmean(
            item.stop_decision_quality_rate for item in rows
        ),
        mean_nontrivial_agent_state_rate=statistics.fmean(
            item.nontrivial_agent_state_rate for item in rows
        ),
        mean_query_reformulation_rate=statistics.fmean(
            item.query_reformulation_rate for item in rows
        ),
        mean_error_recovery_rate=statistics.fmean(item.error_recovery_rate for item in rows),
        mean_differential_token_fraction=statistics.fmean(
            item.differential_token_fraction for item in rows
        ),
        mean_differential_gradient_fraction=statistics.fmean(
            item.differential_gradient_fraction for item in rows
        ),
        exact_target_coordinate_count=coordinate_count,
        near_mpe_coordinate_rate=near_count / coordinate_count if coordinate_count else 0.0,
        meaningful_coordinate_rate=(
            meaningful_count / coordinate_count if coordinate_count else 0.0
        ),
    )
