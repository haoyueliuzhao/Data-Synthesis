from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.scaffolding import ScaffoldLevel
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    BridgeMechanism,
    CompilerAssistedBridgeConfirmation,
    CompilerAssistedBridgeContract,
    ConfirmedBridgeTaskCondition,
)
from trusted_synthesis.hashing import canonical_hash

STATE_SUPPORT_DISCOVERY_CONTRACT_VERSION = "finance_state_support_discovery_contract.v1"
STATE_SUPPORT_DISCOVERY_PLAN_VERSION = "finance_state_support_discovery_plan.v1"
STATE_ACCEPTANCE_ESTIMATE_VERSION = "finance_state_acceptance_estimate.v1"
TASK_STATE_SUPPORT_OBSERVATION_VERSION = "finance_task_state_support_observation.v1"
STATE_SUPPORT_FREEZE_VERSION = "finance_state_support_freeze.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateSupportDiscoveryPlan(FrozenModel):
    plan_id: str = Field(min_length=1)
    bridge_contract_id: str = Field(min_length=1)
    task_count: Literal[24] = 24
    tasks_per_mechanism: Literal[8] = 8
    confirmation_rollouts_per_task: Literal[6] = 6
    additional_unconditional_rollouts_per_task: Literal[12] = 12
    total_unconditional_rollouts_per_task: Literal[18] = 18
    planned_additional_unconditional_rollout_count: Literal[288] = 288
    minimum_accepted_state_count: Literal[3] = 3
    maximum_accepted_state_count: Literal[5] = 5
    minimum_state_conditioned_attempt_count: Literal[6] = 6
    target_realizations_per_state: Literal[3] = 3
    maximum_estimated_attempts_per_state: Literal[60] = 60
    confidence_bound_method: Literal["wilson_lcb95"] = "wilson_lcb95"
    bridge_boundary_result_not_state_support_proof: Literal[True] = True
    support_freeze_required_before_no_c: Literal[True] = True
    schema_version: str = STATE_SUPPORT_DISCOVERY_PLAN_VERSION

    @model_validator(mode="after")
    def validate_plan(self) -> StateSupportDiscoveryPlan:
        if (
            self.total_unconditional_rollouts_per_task
            != self.confirmation_rollouts_per_task + self.additional_unconditional_rollouts_per_task
        ):
            raise ValueError("State-support plan rollout budget is inconsistent")
        if (
            self.planned_additional_unconditional_rollout_count
            != self.task_count * self.additional_unconditional_rollouts_per_task
        ):
            raise ValueError("State-support plan total rollout count is inconsistent")
        if self.plan_id != state_support_discovery_plan_id(self):
            raise ValueError("State-support discovery plan identity is invalid")
        return self


class StateSupportDiscoveryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    bridge_contract_id: str = Field(min_length=1)
    discovery_plan_id: str = Field(min_length=1)
    bridge_confirmation_id: str = Field(min_length=1)
    confirmed_task_conditions: tuple[ConfirmedBridgeTaskCondition, ...] = Field(
        min_length=24,
        max_length=24,
    )
    task_count: Literal[24] = 24
    tasks_per_mechanism: Literal[8] = 8
    confirmation_rollouts_per_task: Literal[6] = 6
    additional_unconditional_rollouts_per_task: Literal[12] = 12
    total_unconditional_rollouts_per_task: Literal[18] = 18
    planned_additional_unconditional_rollout_count: Literal[288] = 288
    minimum_accepted_state_count: Literal[3] = 3
    maximum_accepted_state_count: Literal[5] = 5
    minimum_state_conditioned_attempt_count: Literal[6] = 6
    target_realizations_per_state: Literal[3] = 3
    maximum_estimated_attempts_per_state: Literal[60] = 60
    confidence_bound_method: Literal["wilson_lcb95"] = "wilson_lcb95"
    positive_hit_rate_lower_bound_required: Literal[True] = True
    positive_acceptance_rate_lower_bound_required: Literal[True] = True
    scaffold_invariant_state_mapping_required: Literal[True] = True
    independent_state_acceptance_required: Literal[True] = True
    state_quota_transfer_forbidden: Literal[True] = True
    task_quota_reallocation_forbidden: Literal[True] = True
    bridge_boundary_result_not_state_support_proof: Literal[True] = True
    api_authorized_before_bridge_confirmation: Literal[False] = False
    gpu_authorized_before_support_freeze: Literal[False] = False
    next_permitted_stage: Literal["state_support_discovery"] = "state_support_discovery"
    schema_version: str = STATE_SUPPORT_DISCOVERY_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> StateSupportDiscoveryContract:
        plan_values = {
            "bridge_contract_id": self.bridge_contract_id,
            "schema_version": STATE_SUPPORT_DISCOVERY_PLAN_VERSION,
        }
        expected_plan = StateSupportDiscoveryPlan.model_construct(
            plan_id="pending",
            **plan_values,
        )
        if self.discovery_plan_id != state_support_discovery_plan_id(expected_plan):
            raise ValueError("State-support contract differs from the frozen discovery plan")
        if len({item.task_id for item in self.confirmed_task_conditions}) != self.task_count:
            raise ValueError("State-support contract task identities are incomplete")
        for mechanism in BRIDGE_MECHANISMS:
            count = sum(item.mechanism_id == mechanism for item in self.confirmed_task_conditions)
            if count != self.tasks_per_mechanism:
                raise ValueError("State-support contract mechanism allocation is inconsistent")
        expected_total = (
            self.confirmation_rollouts_per_task + self.additional_unconditional_rollouts_per_task
        )
        if self.total_unconditional_rollouts_per_task != expected_total:
            raise ValueError("State-support unconditional rollout budget is inconsistent")
        if (
            self.planned_additional_unconditional_rollout_count
            != self.task_count * self.additional_unconditional_rollouts_per_task
        ):
            raise ValueError("State-support additional rollout count is inconsistent")
        if self.contract_id != state_support_discovery_contract_id(self):
            raise ValueError("State-support discovery contract identity is invalid")
        return self


class StateAcceptanceEstimate(FrozenModel):
    estimate_id: str = Field(min_length=1)
    quotient_state_id: str = Field(min_length=1)
    unconditional_rollout_count: int = Field(ge=1)
    unconditional_hit_count: int = Field(ge=0)
    unconditional_hit_rate: float = Field(ge=0, le=1)
    unconditional_hit_rate_lcb95: float = Field(ge=0, le=1)
    conditioned_attempt_count: int = Field(ge=1)
    conditioned_accepted_count: int = Field(ge=0)
    conditioned_acceptance_rate: float = Field(ge=0, le=1)
    conditioned_acceptance_rate_lcb95: float = Field(ge=0, le=1)
    independently_verified: bool
    target_realization_quota: int = Field(ge=1)
    estimated_attempts_for_quota: int = Field(ge=1)
    passed: bool
    failure_reasons: tuple[str, ...]
    schema_version: str = STATE_ACCEPTANCE_ESTIMATE_VERSION

    @model_validator(mode="after")
    def validate_estimate(self) -> StateAcceptanceEstimate:
        if self.unconditional_hit_count > self.unconditional_rollout_count:
            raise ValueError("state hits exceed unconditional rollouts")
        if self.conditioned_accepted_count > self.conditioned_attempt_count:
            raise ValueError("state acceptances exceed conditioned attempts")
        expected_hit_rate = self.unconditional_hit_count / self.unconditional_rollout_count
        expected_acceptance_rate = self.conditioned_accepted_count / self.conditioned_attempt_count
        if not math.isclose(self.unconditional_hit_rate, expected_hit_rate, abs_tol=1e-12):
            raise ValueError("state hit rate is inconsistent")
        if not math.isclose(
            self.conditioned_acceptance_rate,
            expected_acceptance_rate,
            abs_tol=1e-12,
        ):
            raise ValueError("state acceptance rate is inconsistent")
        expected_hit_lcb = wilson_lower_bound_95(
            self.unconditional_hit_count,
            self.unconditional_rollout_count,
        )
        expected_acceptance_lcb = wilson_lower_bound_95(
            self.conditioned_accepted_count,
            self.conditioned_attempt_count,
        )
        if not math.isclose(self.unconditional_hit_rate_lcb95, expected_hit_lcb, abs_tol=1e-12):
            raise ValueError("state hit-rate confidence bound is inconsistent")
        if not math.isclose(
            self.conditioned_acceptance_rate_lcb95,
            expected_acceptance_lcb,
            abs_tol=1e-12,
        ):
            raise ValueError("state acceptance confidence bound is inconsistent")
        expected_attempts = _estimated_attempts(
            self.target_realization_quota,
            expected_acceptance_lcb,
        )
        if self.estimated_attempts_for_quota != expected_attempts:
            raise ValueError("state materialization budget estimate is inconsistent")
        expected_failures = _state_estimate_failures(self)
        if self.failure_reasons != expected_failures:
            raise ValueError("state acceptance failure reasons are inconsistent")
        if self.passed != (not expected_failures):
            raise ValueError("state acceptance status is inconsistent")
        if self.estimate_id != state_acceptance_estimate_id(self):
            raise ValueError("state acceptance estimate identity is invalid")
        return self


class TaskStateSupportObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    bridge_confirmation_id: str = Field(min_length=1)
    condition_ref_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    scaffold_level: ScaffoldLevel
    compiled_task_condition_id: str = Field(min_length=1)
    state_mapping_contract_id: str = Field(min_length=1)
    unconditional_rollout_count: Literal[18] = 18
    unconditional_valid_trajectory_count: int = Field(ge=0, le=18)
    state_estimates: tuple[StateAcceptanceEstimate, ...] = Field(min_length=1, max_length=5)
    scaffold_invariant_mapping_replayed: bool
    scaffold_trace_side_channel_archived: bool
    quota_transfer_used: Literal[False] = False
    task_quota_reallocated: Literal[False] = False
    status: Literal["passed", "blocked"]
    blockers: tuple[str, ...]
    schema_version: str = TASK_STATE_SUPPORT_OBSERVATION_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> TaskStateSupportObservation:
        if len({item.quotient_state_id for item in self.state_estimates}) != len(
            self.state_estimates
        ):
            raise ValueError("task state-support observation duplicates quotient states")
        if (
            sum(item.unconditional_hit_count for item in self.state_estimates)
            > self.unconditional_valid_trajectory_count
        ):
            raise ValueError("state hit counts exceed valid unconditional trajectories")
        expected_blockers = _task_support_blockers(self)
        if self.blockers != expected_blockers:
            raise ValueError("task state-support blockers are inconsistent")
        expected_status = "blocked" if expected_blockers else "passed"
        if self.status != expected_status:
            raise ValueError("task state-support status is inconsistent")
        if self.observation_id != task_state_support_observation_id(self):
            raise ValueError("task state-support observation identity is invalid")
        return self


class StateSupportFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    contract: StateSupportDiscoveryContract
    observations: tuple[TaskStateSupportObservation, ...] = Field(min_length=24, max_length=24)
    status: Literal["passed", "blocked"]
    blocker_task_ids: tuple[str, ...]
    next_transition: Literal[
        "frozen_condition_no_c_population_compilation",
        "state_support_repair_only",
    ]
    state_quota_transfer_used: Literal[False] = False
    task_quota_reallocation_used: Literal[False] = False
    scaffold_condition_changed_across_vtdo_arms: Literal[False] = False
    no_c_vtdo_support_compilation_authorized: bool
    contribution_authorized: Literal[False] = False
    schema_version: str = STATE_SUPPORT_FREEZE_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> StateSupportFreeze:
        conditions = {item.task_id: item for item in self.contract.confirmed_task_conditions}
        expected_tasks = set(conditions)
        observed_tasks = {item.task_id for item in self.observations}
        if expected_tasks != observed_tasks or len(observed_tasks) != len(self.observations):
            raise ValueError("State-support freeze task coverage is incomplete or duplicated")
        for item in self.observations:
            condition = conditions[item.task_id]
            if (
                item.contract_id != self.contract.contract_id
                or item.bridge_confirmation_id != self.contract.bridge_confirmation_id
                or item.condition_ref_id != condition.condition_ref_id
                or item.mechanism_id != condition.mechanism_id
                or item.scaffold_level != condition.scaffold_level
                or item.compiled_task_condition_id != condition.compiled_task_condition_id
                or item.state_mapping_contract_id != condition.state_mapping_contract_id
            ):
                raise ValueError("State-support freeze contains a changed task condition")
        expected_blockers = tuple(
            sorted(item.task_id for item in self.observations if item.status != "passed")
        )
        if self.blocker_task_ids != expected_blockers:
            raise ValueError("State-support freeze blockers are inconsistent")
        expected_status = "blocked" if expected_blockers else "passed"
        if self.status != expected_status:
            raise ValueError("State-support freeze status is inconsistent")
        expected_transition = (
            "state_support_repair_only"
            if expected_blockers
            else "frozen_condition_no_c_population_compilation"
        )
        if self.next_transition != expected_transition:
            raise ValueError("State-support freeze transition is inconsistent")
        if self.no_c_vtdo_support_compilation_authorized != (not expected_blockers):
            raise ValueError("State-support No-C authorization is inconsistent")
        if self.freeze_id != state_support_freeze_id(self):
            raise ValueError("State-support freeze identity is invalid")
        return self


def make_state_support_discovery_contract(
    bridge_contract: CompilerAssistedBridgeContract,
    confirmation: CompilerAssistedBridgeConfirmation,
) -> StateSupportDiscoveryContract:
    if confirmation.contract_id != bridge_contract.contract_id or confirmation.status != "passed":
        raise ValueError("State-support discovery requires a passing fresh Bridge confirmation")
    plan = make_state_support_discovery_plan(bridge_contract)
    values = {
        "bridge_contract_id": bridge_contract.contract_id,
        "discovery_plan_id": plan.plan_id,
        "bridge_confirmation_id": confirmation.confirmation_id,
        "confirmed_task_conditions": confirmation.confirmed_task_conditions,
        "schema_version": STATE_SUPPORT_DISCOVERY_CONTRACT_VERSION,
    }
    provisional = StateSupportDiscoveryContract.model_construct(contract_id="pending", **values)
    return StateSupportDiscoveryContract(
        contract_id=state_support_discovery_contract_id(provisional),
        **values,
    )


def make_state_support_discovery_plan(
    bridge_contract: CompilerAssistedBridgeContract,
) -> StateSupportDiscoveryPlan:
    values = {
        "bridge_contract_id": bridge_contract.contract_id,
        "schema_version": STATE_SUPPORT_DISCOVERY_PLAN_VERSION,
    }
    provisional = StateSupportDiscoveryPlan.model_construct(plan_id="pending", **values)
    return StateSupportDiscoveryPlan(
        plan_id=state_support_discovery_plan_id(provisional),
        **values,
    )


def make_state_acceptance_estimate(
    *,
    quotient_state_id: str,
    unconditional_rollout_count: int,
    unconditional_hit_count: int,
    conditioned_attempt_count: int,
    conditioned_accepted_count: int,
    independently_verified: bool,
    target_realization_quota: int = 3,
) -> StateAcceptanceEstimate:
    hit_lcb = wilson_lower_bound_95(unconditional_hit_count, unconditional_rollout_count)
    acceptance_lcb = wilson_lower_bound_95(
        conditioned_accepted_count,
        conditioned_attempt_count,
    )
    values = {
        "quotient_state_id": quotient_state_id,
        "unconditional_rollout_count": unconditional_rollout_count,
        "unconditional_hit_count": unconditional_hit_count,
        "unconditional_hit_rate": unconditional_hit_count / unconditional_rollout_count,
        "unconditional_hit_rate_lcb95": hit_lcb,
        "conditioned_attempt_count": conditioned_attempt_count,
        "conditioned_accepted_count": conditioned_accepted_count,
        "conditioned_acceptance_rate": conditioned_accepted_count / conditioned_attempt_count,
        "conditioned_acceptance_rate_lcb95": acceptance_lcb,
        "independently_verified": independently_verified,
        "target_realization_quota": target_realization_quota,
        "estimated_attempts_for_quota": _estimated_attempts(
            target_realization_quota,
            acceptance_lcb,
        ),
        "schema_version": STATE_ACCEPTANCE_ESTIMATE_VERSION,
    }
    provisional = StateAcceptanceEstimate.model_construct(
        estimate_id="pending",
        passed=False,
        failure_reasons=(),
        **values,
    )
    failures = _state_estimate_failures(provisional)
    finalized = StateAcceptanceEstimate.model_construct(
        estimate_id="pending",
        passed=not failures,
        failure_reasons=failures,
        **values,
    )
    return StateAcceptanceEstimate(
        estimate_id=state_acceptance_estimate_id(finalized),
        passed=not failures,
        failure_reasons=failures,
        **values,
    )


def make_task_state_support_observation(
    contract: StateSupportDiscoveryContract,
    condition: ConfirmedBridgeTaskCondition,
    *,
    unconditional_valid_trajectory_count: int,
    state_estimates: tuple[StateAcceptanceEstimate, ...],
    scaffold_invariant_mapping_replayed: bool,
    scaffold_trace_side_channel_archived: bool,
) -> TaskStateSupportObservation:
    if condition not in contract.confirmed_task_conditions:
        raise ValueError("task state-support condition is not in the frozen Bridge confirmation")
    values = {
        "contract_id": contract.contract_id,
        "bridge_confirmation_id": contract.bridge_confirmation_id,
        "condition_ref_id": condition.condition_ref_id,
        "task_id": condition.task_id,
        "mechanism_id": condition.mechanism_id,
        "scaffold_level": condition.scaffold_level,
        "compiled_task_condition_id": condition.compiled_task_condition_id,
        "state_mapping_contract_id": condition.state_mapping_contract_id,
        "unconditional_valid_trajectory_count": unconditional_valid_trajectory_count,
        "state_estimates": state_estimates,
        "scaffold_invariant_mapping_replayed": scaffold_invariant_mapping_replayed,
        "scaffold_trace_side_channel_archived": scaffold_trace_side_channel_archived,
        "status": "blocked",
        "blockers": (),
        "schema_version": TASK_STATE_SUPPORT_OBSERVATION_VERSION,
    }
    provisional = TaskStateSupportObservation.model_construct(
        observation_id="pending",
        **values,
    )
    blockers = _task_support_blockers(provisional)
    values["status"] = "blocked" if blockers else "passed"
    values["blockers"] = blockers
    provisional = TaskStateSupportObservation.model_construct(
        observation_id="pending",
        **values,
    )
    return TaskStateSupportObservation(
        observation_id=task_state_support_observation_id(provisional),
        **values,
    )


def freeze_state_support_discovery(
    contract: StateSupportDiscoveryContract,
    observations: Iterable[TaskStateSupportObservation],
) -> StateSupportFreeze:
    rows = tuple(sorted(observations, key=lambda item: (item.mechanism_id, item.task_id)))
    if any(
        item.contract_id != contract.contract_id
        or item.bridge_confirmation_id != contract.bridge_confirmation_id
        for item in rows
    ):
        raise ValueError("State-support observations cross frozen contract identities")
    conditions = {item.task_id: item for item in contract.confirmed_task_conditions}
    for item in rows:
        condition = conditions.get(item.task_id)
        if condition is None or (
            item.condition_ref_id != condition.condition_ref_id
            or item.mechanism_id != condition.mechanism_id
            or item.scaffold_level != condition.scaffold_level
            or item.compiled_task_condition_id != condition.compiled_task_condition_id
            or item.state_mapping_contract_id != condition.state_mapping_contract_id
        ):
            raise ValueError("State-support observation changes the frozen task condition")
    blockers = tuple(sorted(item.task_id for item in rows if item.status != "passed"))
    values = {
        "contract": contract,
        "observations": rows,
        "status": "blocked" if blockers else "passed",
        "blocker_task_ids": blockers,
        "next_transition": (
            "state_support_repair_only"
            if blockers
            else "frozen_condition_no_c_population_compilation"
        ),
        "no_c_vtdo_support_compilation_authorized": not blockers,
        "schema_version": STATE_SUPPORT_FREEZE_VERSION,
    }
    provisional = StateSupportFreeze.model_construct(freeze_id="pending", **values)
    return StateSupportFreeze(
        freeze_id=state_support_freeze_id(provisional),
        **values,
    )


def wilson_lower_bound_95(successes: int, trials: int) -> float:
    if trials <= 0:
        raise ValueError("Wilson confidence bound requires a positive trial count")
    if successes < 0 or successes > trials:
        raise ValueError("Wilson confidence bound successes are invalid")
    if successes == 0:
        return 0.0
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = proportion + z * z / (2.0 * trials)
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials)
    )
    return max(0.0, (center - margin) / denominator)


def state_support_discovery_contract_id(value: StateSupportDiscoveryContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_state_support_discovery_contract:",
    )


def state_support_discovery_plan_id(value: StateSupportDiscoveryPlan) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"plan_id"}),
        prefix="finance_state_support_discovery_plan:",
    )


def state_acceptance_estimate_id(value: StateAcceptanceEstimate) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"estimate_id"}),
        prefix="finance_state_acceptance_estimate:",
    )


def task_state_support_observation_id(value: TaskStateSupportObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="finance_task_state_support_observation:",
    )


def state_support_freeze_id(value: StateSupportFreeze) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"freeze_id"}),
        prefix="finance_state_support_freeze:",
    )


def _state_estimate_failures(value: StateAcceptanceEstimate) -> tuple[str, ...]:
    failures: list[str] = []
    if value.unconditional_hit_rate_lcb95 <= 0:
        failures.append("unconditional_hit_rate_lcb_not_positive")
    if value.conditioned_acceptance_rate_lcb95 <= 0:
        failures.append("conditioned_acceptance_rate_lcb_not_positive")
    if not value.independently_verified:
        failures.append("independent_state_acceptance_missing")
    if value.estimated_attempts_for_quota > 60:
        failures.append("materialization_attempt_budget_exceeded")
    return tuple(failures)


def _task_support_blockers(value: TaskStateSupportObservation) -> tuple[str, ...]:
    blockers: list[str] = []
    if not 3 <= len(value.state_estimates) <= 5:
        blockers.append("accepted_state_count_outside_3_5")
    if any(not item.passed for item in value.state_estimates):
        blockers.append("state_level_acceptance_or_budget_failed")
    if any(item.conditioned_attempt_count < 6 for item in value.state_estimates):
        blockers.append("state_conditioned_attempt_count_low")
    if not value.scaffold_invariant_mapping_replayed:
        blockers.append("scaffold_invariant_mapping_not_replayed")
    if not value.scaffold_trace_side_channel_archived:
        blockers.append("scaffold_trace_side_channel_missing")
    return tuple(blockers)


def _estimated_attempts(target_quota: int, acceptance_lcb: float) -> int:
    if acceptance_lcb <= 0:
        return 10**9
    return math.ceil(target_quota / acceptance_lcb)
