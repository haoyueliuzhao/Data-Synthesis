from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.scaffolding import SCAFFOLD_LEVELS, ScaffoldLevel
from trusted_synthesis.hashing import canonical_hash

COMPILER_ASSISTED_BRIDGE_CONTRACT_VERSION = "finance_compiler_assisted_bridge.v2"
BRIDGE_STATIC_CONSTRUCT_AUDIT_VERSION = "finance_bridge_static_construct_audit.v1"
BRIDGE_DEVELOPMENT_AUTHORIZATION_VERSION = "finance_bridge_development_authorization.v1"
BRIDGE_CONFIRMATION_AUTHORIZATION_VERSION = "finance_bridge_confirmation_authorization.v1"
BRIDGE_ESTIMAND_OBSERVATION_VERSION = "finance_bridge_estimand_observation.v1"
BRIDGE_CELL_OBSERVATION_VERSION = "finance_compiler_assisted_bridge_cell.v3"
BRIDGE_MECHANISM_SELECTION_VERSION = "finance_compiler_assisted_bridge_selection.v2"
BRIDGE_SUPPORT_FREEZE_VERSION = "finance_compiler_assisted_bridge_support_freeze.v3"
BRIDGE_CONFIRMED_TASK_CONDITION_VERSION = "finance_bridge_confirmed_task_condition.v1"
BRIDGE_CONFIRMATION_VERSION = "finance_compiler_assisted_bridge_confirmation.v2"

BridgeMechanism = Literal[
    "context_conditioned_action",
    "semantic_reconciliation",
    "recovery_and_stopping",
]
BridgePhase = Literal["development", "fresh_confirmation"]
EstimandId = Literal[
    "context_action_alignment",
    "counterfactual_branch_flip",
    "semantic_reconciliation",
    "failure_recovery",
    "stopping_calibration",
]
WithdrawalCondition = Literal[
    "unassisted_train_unassisted_eval",
    "scaffold_train_scaffold_eval",
    "scaffold_train_unassisted_eval",
    "scaffold_train_weaker_scaffold_eval",
]

BRIDGE_MECHANISMS: tuple[BridgeMechanism, ...] = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "recovery_and_stopping",
)
MECHANISM_ESTIMANDS: dict[BridgeMechanism, tuple[EstimandId, ...]] = {
    "context_conditioned_action": (
        "context_action_alignment",
        "counterfactual_branch_flip",
    ),
    "semantic_reconciliation": ("semantic_reconciliation",),
    "recovery_and_stopping": (
        "failure_recovery",
        "stopping_calibration",
    ),
}
ESTIMAND_DEFINITIONS: dict[EstimandId, str] = {
    "context_action_alignment": "first_registered_action_matches_public_context",
    "counterfactual_branch_flip": (
        "both_counterfactual_branches_choose_the_context_consistent_action"
    ),
    "semantic_reconciliation": (
        "relation_difference_identified_and_normalization_correct_with_nontarget_semantics_preserved"
    ),
    "failure_recovery": ("failure_observed_root_cause_repaired_and_subsequent_action_succeeds"),
    "stopping_calibration": (
        "incomplete_state_continues_complete_state_stops_and_no_postcompletion_violation_occurs"
    ),
}
STATIC_CONSTRUCT_CHECKS: tuple[str, ...] = (
    "estimand_definition_frozen",
    "estimand_evaluator_replayable",
    "public_mutation_preserves_nontarget_semantics",
    "oracle_fields_absent",
    "host_only_labels_absent",
    "construct_fidelity_exact",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilityEstimandContract(FrozenModel):
    estimand_id: EstimandId
    mechanism_id: BridgeMechanism
    definition: str = Field(min_length=1)
    outcome_type: Literal["bernoulli"] = "bernoulli"
    fixed_policy_baseline_required: Literal[True] = True
    model_behavior_outcome: Literal[True] = True
    static_construct_gate_forbidden: Literal[True] = True

    @model_validator(mode="after")
    def validate_estimand(self) -> CapabilityEstimandContract:
        if self.estimand_id not in MECHANISM_ESTIMANDS[self.mechanism_id]:
            raise ValueError("Bridge Estimand belongs to another mechanism")
        if self.definition != ESTIMAND_DEFINITIONS[self.estimand_id]:
            raise ValueError("Bridge Estimand definition differs from the frozen contract")
        return self


class BridgeMechanismContract(FrozenModel):
    mechanism_id: BridgeMechanism
    target_capability_ids: tuple[str, ...] = Field(min_length=1)
    estimands: tuple[CapabilityEstimandContract, ...] = Field(min_length=1)
    development_task_count: Literal[8] = 8
    fresh_confirmation_task_count: Literal[8] = 8
    support_selected_per_mechanism: Literal[True] = True
    per_task_scaffold_selection_forbidden: Literal[True] = True

    @model_validator(mode="after")
    def validate_mechanism(self) -> BridgeMechanismContract:
        if (
            tuple(item.estimand_id for item in self.estimands)
            != MECHANISM_ESTIMANDS[self.mechanism_id]
        ):
            raise ValueError("Bridge mechanism Estimands are incomplete or reordered")
        if any(item.mechanism_id != self.mechanism_id for item in self.estimands):
            raise ValueError("Bridge mechanism contains a foreign Estimand")
        return self


class ScaffoldSelectionThresholds(FrozenModel):
    estimand_rate_minimum: float = Field(default=0.15, ge=0, le=1)
    estimand_rate_maximum: float = Field(default=0.85, ge=0, le=1)
    valid_trajectory_rate_minimum: float = Field(default=0.20, ge=0, le=1)
    fixed_policy_gain_minimum: float = Field(default=0.05, ge=-1, le=1)
    instrument_valid_rate_required: float = Field(default=1.0, ge=1.0, le=1.0)
    maximum_host_interference_count: Literal[0] = 0
    maximum_oracle_leakage_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_thresholds(self) -> ScaffoldSelectionThresholds:
        if self.estimand_rate_minimum >= self.estimand_rate_maximum:
            raise ValueError("Bridge Estimand boundary band must be non-empty")
        return self


class ScaffoldWithdrawalTransferContract(FrozenModel):
    conditions: tuple[WithdrawalCondition, ...] = (
        "unassisted_train_unassisted_eval",
        "scaffold_train_scaffold_eval",
        "scaffold_train_unassisted_eval",
        "scaffold_train_weaker_scaffold_eval",
    )
    primary_transfer_estimand: Literal[
        "trained_scaffold_to_unassisted_delta_over_unassisted_baseline"
    ] = "trained_scaffold_to_unassisted_delta_over_unassisted_baseline"
    empirical_only_after_student_training: Literal[True] = True
    not_a_pretraining_scaffold_gate: Literal[True] = True
    weaker_scaffold_annealing_required: Literal[True] = True
    same_heldout_task_set_required: Literal[True] = True
    same_student_checkpoint_family_required: Literal[True] = True


class BridgeVTDOCausalSeparationContract(FrozenModel):
    bridge_experiment_changes_scaffold_condition: Literal[True] = True
    bridge_experiment_is_not_vtdo_distribution_comparison: Literal[True] = True
    vtdo_requires_one_frozen_scaffold_condition: Literal[True] = True
    allowed_vtdo_arm_ids: tuple[str, ...] = (
        "validity",
        "random",
        "novelty",
        "aevtdr_no_c",
    )
    gamma_change_inside_vtdo_comparison_forbidden: Literal[True] = True
    same_compiled_task_condition_for_all_vtdo_arms: Literal[True] = True


class CompilerAssistedBridgeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    bridge_label: Literal["finance_v26_compiler_assisted_capability_bridge"] = (
        "finance_v26_compiler_assisted_capability_bridge"
    )
    explorer_model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    runtime_id: Literal["autonomous"] = "autonomous"
    mechanisms: tuple[BridgeMechanismContract, ...] = Field(min_length=3, max_length=3)
    scaffold_levels: tuple[ScaffoldLevel, ...] = SCAFFOLD_LEVELS
    assisted_scaffold_level_count: Literal[3] = 3
    rollouts_per_task_level: Literal[6] = 6
    development_task_count: Literal[24] = 24
    fresh_confirmation_task_count: Literal[24] = 24
    planned_development_rollout_count: Literal[576] = 576
    planned_confirmation_rollout_count: Literal[144] = 144
    selection_thresholds: ScaffoldSelectionThresholds
    withdrawal_transfer: ScaffoldWithdrawalTransferContract
    experiment_separation: BridgeVTDOCausalSeparationContract
    task_identity_includes_scaffold: Literal[True] = True
    compiled_condition_identity: Literal["task_runtime_capability_scaffold_policy_version"] = (
        "task_runtime_capability_scaffold_policy_version"
    )
    same_scaffold_for_all_methods_in_causal_comparison: Literal[True] = True
    same_oracle_across_scaffold_levels: Literal[True] = True
    capability_outcome_not_a_runtime_gate: Literal[True] = True
    estimand_compression_forbidden: Literal[True] = True
    static_construct_fidelity_required: float = Field(default=1.0, ge=1.0, le=1.0)
    withdrawal_readiness_is_static_gate: Literal[True] = True
    withdrawal_transfer_is_post_training_estimand: Literal[True] = True
    support_discovery_separate_from_bridge: Literal[True] = True
    development_state_diversity_diagnostic_only: Literal[True] = True
    development_three_state_gate_forbidden: Literal[True] = True
    confirmation_authorizes_only_state_support_discovery: Literal[True] = True
    inverse_success_weighting_forbidden: Literal[True] = True
    support_freeze_before_fresh_confirmation: Literal[True] = True
    support_selected_per_mechanism_not_task: Literal[True] = True
    api_authorized_before_static_construct_audit: Literal[False] = False
    gpu_authorized_before_state_support_freeze: Literal[False] = False
    next_permitted_stage: Literal["bridge_joint_compilation_admission"] = (
        "bridge_joint_compilation_admission"
    )
    schema_version: str = COMPILER_ASSISTED_BRIDGE_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CompilerAssistedBridgeContract:
        if tuple(item.mechanism_id for item in self.mechanisms) != BRIDGE_MECHANISMS:
            raise ValueError("Bridge mechanisms differ from the frozen v26 design")
        if self.scaffold_levels != SCAFFOLD_LEVELS:
            raise ValueError("Bridge scaffold ladder differs from Core")
        expected_development = (
            self.development_task_count * len(self.scaffold_levels) * self.rollouts_per_task_level
        )
        if self.planned_development_rollout_count != expected_development:
            raise ValueError("Bridge Development rollout budget is inconsistent")
        expected_confirmation = self.fresh_confirmation_task_count * self.rollouts_per_task_level
        if self.planned_confirmation_rollout_count != expected_confirmation:
            raise ValueError("Bridge confirmation rollout budget is inconsistent")
        if self.contract_id != compiler_assisted_bridge_contract_id(self):
            raise ValueError("Compiler-assisted Bridge contract identity is invalid")
        return self


class BridgeStaticConstructAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    task_admission_ids: dict[str, str] = Field(min_length=8, max_length=8)
    checks_by_task: dict[str, dict[str, bool]] = Field(min_length=8, max_length=8)
    passed_task_count: int = Field(ge=0, le=8)
    construct_fidelity_rate: float = Field(ge=0, le=1)
    status: Literal["passed", "blocked"]
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = BRIDGE_STATIC_CONSTRUCT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BridgeStaticConstructAudit:
        if set(self.task_admission_ids) != set(self.checks_by_task):
            raise ValueError("Bridge static audit task identities are incomplete")
        if len(set(self.task_admission_ids.values())) != len(self.task_admission_ids):
            raise ValueError("Bridge static audit reuses scaffold admissions")
        for checks in self.checks_by_task.values():
            if tuple(sorted(checks)) != tuple(sorted(STATIC_CONSTRUCT_CHECKS)):
                raise ValueError("Bridge static construct checks are incomplete")
        expected_passed = sum(all(checks.values()) for checks in self.checks_by_task.values())
        if self.passed_task_count != expected_passed:
            raise ValueError("Bridge static audit pass count is inconsistent")
        expected_rate = expected_passed / len(self.checks_by_task)
        if self.construct_fidelity_rate != expected_rate:
            raise ValueError("Bridge static construct fidelity is inconsistent")
        expected_status = "passed" if expected_rate == 1.0 else "blocked"
        if self.status != expected_status:
            raise ValueError("Bridge static audit status is inconsistent")
        if self.audit_id != bridge_static_construct_audit_id(self):
            raise ValueError("Bridge static construct audit identity is invalid")
        return self


class BridgeDevelopmentAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    static_audits: tuple[BridgeStaticConstructAudit, ...] = Field(min_length=3, max_length=3)
    development_task_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    status: Literal["authorized", "blocked"]
    blockers: tuple[BridgeMechanism, ...]
    next_transition: Literal[
        "bridge_development_rollouts",
        "bridge_static_construct_repair_only",
    ]
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = BRIDGE_DEVELOPMENT_AUTHORIZATION_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> BridgeDevelopmentAuthorization:
        if tuple(item.mechanism_id for item in self.static_audits) != BRIDGE_MECHANISMS:
            raise ValueError("Bridge Development authorization audits are incomplete")
        expected_tasks = tuple(
            sorted(task_id for item in self.static_audits for task_id in item.task_admission_ids)
        )
        if self.development_task_ids != expected_tasks or len(set(expected_tasks)) != 24:
            raise ValueError("Bridge Development tasks are incomplete or overlapping")
        expected_blockers = tuple(
            item.mechanism_id for item in self.static_audits if item.status != "passed"
        )
        if self.blockers != expected_blockers:
            raise ValueError("Bridge Development authorization blockers are inconsistent")
        expected_status = "blocked" if expected_blockers else "authorized"
        if self.status != expected_status:
            raise ValueError("Bridge Development authorization status is inconsistent")
        expected_transition = (
            "bridge_static_construct_repair_only"
            if expected_blockers
            else "bridge_development_rollouts"
        )
        if self.next_transition != expected_transition:
            raise ValueError("Bridge Development authorization transition is inconsistent")
        if self.authorization_id != bridge_development_authorization_id(self):
            raise ValueError("Bridge Development authorization identity is invalid")
        return self


class BridgeConfirmationAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    support_freeze_id: str = Field(min_length=1)
    static_audits: tuple[BridgeStaticConstructAudit, ...] = Field(min_length=3, max_length=3)
    development_task_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    confirmation_task_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    selected_scaffold_by_mechanism: dict[BridgeMechanism, ScaffoldLevel]
    status: Literal["authorized", "blocked"]
    blockers: tuple[BridgeMechanism, ...]
    next_transition: Literal[
        "fresh_bridge_confirmation",
        "bridge_confirmation_static_repair_only",
    ]
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = BRIDGE_CONFIRMATION_AUTHORIZATION_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> BridgeConfirmationAuthorization:
        if tuple(item.mechanism_id for item in self.static_audits) != BRIDGE_MECHANISMS:
            raise ValueError("Bridge confirmation authorization audits are incomplete")
        if any(item.contract_id != self.contract_id for item in self.static_audits):
            raise ValueError("Bridge confirmation static audits cross contract identities")
        expected_tasks = tuple(
            sorted(task_id for item in self.static_audits for task_id in item.task_admission_ids)
        )
        if self.confirmation_task_ids != expected_tasks or len(set(expected_tasks)) != 24:
            raise ValueError("Bridge confirmation tasks are incomplete or overlapping")
        if set(self.development_task_ids) & set(self.confirmation_task_ids):
            raise ValueError("Bridge confirmation authorization reuses Development tasks")
        if tuple(self.selected_scaffold_by_mechanism) != BRIDGE_MECHANISMS:
            raise ValueError("Bridge confirmation scaffold selections are incomplete")
        expected_blockers = tuple(
            item.mechanism_id for item in self.static_audits if item.status != "passed"
        )
        if self.blockers != expected_blockers:
            raise ValueError("Bridge confirmation authorization blockers are inconsistent")
        expected_status = "blocked" if expected_blockers else "authorized"
        if self.status != expected_status:
            raise ValueError("Bridge confirmation authorization status is inconsistent")
        expected_transition = (
            "bridge_confirmation_static_repair_only"
            if expected_blockers
            else "fresh_bridge_confirmation"
        )
        if self.next_transition != expected_transition:
            raise ValueError("Bridge confirmation authorization transition is inconsistent")
        if self.authorization_id != bridge_confirmation_authorization_id(self):
            raise ValueError("Bridge confirmation authorization identity is invalid")
        return self


class BridgeEstimandObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    estimand_id: EstimandId
    evaluation_count: int = Field(ge=1, le=48)
    success_count: int = Field(ge=0, le=48)
    fixed_policy_success_count: int = Field(ge=0, le=48)
    schema_version: str = BRIDGE_ESTIMAND_OBSERVATION_VERSION

    @property
    def success_rate(self) -> float:
        return self.success_count / self.evaluation_count

    @property
    def fixed_policy_success_rate(self) -> float:
        return self.fixed_policy_success_count / self.evaluation_count

    @property
    def fixed_policy_gain(self) -> float:
        return self.success_rate - self.fixed_policy_success_rate

    @model_validator(mode="after")
    def validate_observation(self) -> BridgeEstimandObservation:
        if self.success_count > self.evaluation_count:
            raise ValueError("Bridge Estimand successes exceed evaluations")
        if self.fixed_policy_success_count > self.evaluation_count:
            raise ValueError("Bridge fixed-policy successes exceed evaluations")
        if self.observation_id != bridge_estimand_observation_id(self):
            raise ValueError("Bridge Estimand observation identity is invalid")
        return self


class BridgeCellObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    phase_authorization_id: str = Field(min_length=1)
    phase: BridgePhase
    mechanism_id: BridgeMechanism
    scaffold_level: ScaffoldLevel
    scaffold_rank: Literal[0, 1, 2, 3]
    task_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    compiled_task_condition_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    state_mapping_contract_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    rollout_count: Literal[48] = 48
    instrument_valid_rollout_count: int = Field(ge=0, le=48)
    model_outcome_count: int = Field(ge=0, le=48)
    valid_trajectory_count: int = Field(ge=0, le=48)
    estimand_observations: tuple[BridgeEstimandObservation, ...] = Field(min_length=1)
    preliminary_unique_state_count: int = Field(ge=0)
    tasks_with_multiple_observed_states_count: int = Field(ge=0, le=8)
    state_entropy: float = Field(ge=0)
    host_interference_count: int = Field(ge=0, le=48)
    oracle_leakage_count: int = Field(ge=0, le=48)
    runtime_failure_count: int = Field(ge=0, le=48)
    schema_version: str = BRIDGE_CELL_OBSERVATION_VERSION

    @property
    def instrument_valid_rate(self) -> float:
        return self.instrument_valid_rollout_count / self.rollout_count

    @property
    def valid_trajectory_rate(self) -> float:
        return _ratio(self.valid_trajectory_count, self.model_outcome_count)

    @model_validator(mode="after")
    def validate_observation(self) -> BridgeCellObservation:
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("Bridge cell task identities must be unique")
        if len(self.compiled_task_condition_ids) != len(set(self.compiled_task_condition_ids)):
            raise ValueError("Bridge cell compiled conditions must be unique")
        if len(self.state_mapping_contract_ids) != len(set(self.state_mapping_contract_ids)):
            raise ValueError("Bridge cell state mapping contracts must be unique")
        if self.scaffold_rank != SCAFFOLD_LEVELS.index(self.scaffold_level):
            raise ValueError("Bridge cell scaffold rank differs from its level")
        if self.model_outcome_count + self.runtime_failure_count != self.rollout_count:
            raise ValueError("Bridge rollout accounting is incomplete")
        if self.instrument_valid_rollout_count + self.runtime_failure_count != self.rollout_count:
            raise ValueError("Bridge instrument-valid accounting is incomplete")
        if self.valid_trajectory_count > self.model_outcome_count:
            raise ValueError("Bridge valid trajectories exceed model outcomes")
        observed_estimands = tuple(item.estimand_id for item in self.estimand_observations)
        if observed_estimands != MECHANISM_ESTIMANDS[self.mechanism_id]:
            raise ValueError("Bridge cell mechanism Estimands are incomplete or reordered")
        if any(
            item.evaluation_count > self.model_outcome_count for item in self.estimand_observations
        ):
            raise ValueError("Bridge Estimand evaluations exceed model outcomes")
        if self.observation_id != bridge_cell_observation_id(self):
            raise ValueError("Bridge cell observation identity is invalid")
        return self


class MechanismScaffoldSelection(FrozenModel):
    selection_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    selected_scaffold_level: ScaffoldLevel | None = None
    passing_scaffold_levels: tuple[ScaffoldLevel, ...]
    status: Literal["selected", "blocked"]
    failure_reasons_by_level: dict[str, tuple[str, ...]]
    global_minimum_passing_level_only: Literal[True] = True
    higher_levels_are_diagnostic_only: Literal[True] = True
    schema_version: str = BRIDGE_MECHANISM_SELECTION_VERSION

    @model_validator(mode="after")
    def validate_selection(self) -> MechanismScaffoldSelection:
        if tuple(self.failure_reasons_by_level) != SCAFFOLD_LEVELS:
            raise ValueError("Bridge selection does not cover the complete scaffold ladder")
        passing = tuple(
            level for level in SCAFFOLD_LEVELS if not self.failure_reasons_by_level[level]
        )
        if self.passing_scaffold_levels != passing:
            raise ValueError("Bridge passing levels are inconsistent")
        expected_level = passing[0] if passing else None
        if self.selected_scaffold_level != expected_level:
            raise ValueError("Bridge did not select the global minimum passing level")
        expected_status = "selected" if expected_level else "blocked"
        if self.status != expected_status:
            raise ValueError("Bridge selection status is inconsistent")
        if self.selection_id != mechanism_scaffold_selection_id(self):
            raise ValueError("Bridge mechanism selection identity is invalid")
        return self


class CompilerAssistedBridgeSupportFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    development_authorization_id: str = Field(min_length=1)
    observations: tuple[BridgeCellObservation, ...] = Field(min_length=12, max_length=12)
    selections: tuple[MechanismScaffoldSelection, ...] = Field(min_length=3, max_length=3)
    status: Literal["passed", "blocked"]
    blockers: tuple[BridgeMechanism, ...]
    next_transition: Literal[
        "fresh_bridge_confirmation",
        "capability_task_or_scaffold_redesign_only",
    ]
    task_reallocation_used: Literal[False] = False
    inverse_success_weighting_used: Literal[False] = False
    per_task_scaffold_selection_used: Literal[False] = False
    three_state_support_evaluated: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    schema_version: str = BRIDGE_SUPPORT_FREEZE_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> CompilerAssistedBridgeSupportFreeze:
        if tuple(item.mechanism_id for item in self.selections) != BRIDGE_MECHANISMS:
            raise ValueError("Bridge support selections are incomplete")
        expected_blockers = tuple(
            item.mechanism_id for item in self.selections if item.status == "blocked"
        )
        if self.blockers != expected_blockers:
            raise ValueError("Bridge support blockers are inconsistent")
        expected_status = "blocked" if expected_blockers else "passed"
        if self.status != expected_status:
            raise ValueError("Bridge support freeze status is inconsistent")
        expected_transition = (
            "capability_task_or_scaffold_redesign_only"
            if expected_blockers
            else "fresh_bridge_confirmation"
        )
        if self.next_transition != expected_transition:
            raise ValueError("Bridge support transition is inconsistent")
        if self.freeze_id != bridge_support_freeze_id(self):
            raise ValueError("Bridge support freeze identity is invalid")
        return self


class ConfirmedBridgeTaskCondition(FrozenModel):
    condition_ref_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    scaffold_level: ScaffoldLevel
    compiled_task_condition_id: str = Field(min_length=1)
    state_mapping_contract_id: str = Field(min_length=1)
    schema_version: str = BRIDGE_CONFIRMED_TASK_CONDITION_VERSION

    @model_validator(mode="after")
    def validate_condition(self) -> ConfirmedBridgeTaskCondition:
        if self.condition_ref_id != confirmed_bridge_task_condition_id(self):
            raise ValueError("confirmed Bridge task condition identity is invalid")
        return self


class CompilerAssistedBridgeConfirmation(FrozenModel):
    confirmation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    support_freeze_id: str = Field(min_length=1)
    confirmation_authorization_id: str = Field(min_length=1)
    selection_thresholds: ScaffoldSelectionThresholds
    observations: tuple[BridgeCellObservation, ...] = Field(min_length=3, max_length=3)
    confirmed_task_conditions: tuple[ConfirmedBridgeTaskCondition, ...] = Field(
        min_length=24,
        max_length=24,
    )
    status: Literal["passed", "blocked"]
    blockers: tuple[BridgeMechanism, ...]
    next_transition: Literal[
        "state_support_discovery",
        "capability_task_or_scaffold_redesign_only",
    ]
    state_support_evaluated: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    schema_version: str = BRIDGE_CONFIRMATION_VERSION

    @model_validator(mode="after")
    def validate_confirmation(self) -> CompilerAssistedBridgeConfirmation:
        if tuple(item.mechanism_id for item in self.observations) != BRIDGE_MECHANISMS:
            raise ValueError("Bridge confirmation observations are incomplete")
        if any(item.phase != "fresh_confirmation" for item in self.observations):
            raise ValueError("Bridge confirmation contains a non-confirmation observation")
        expected_conditions = tuple(
            sorted(
                (
                    _confirmed_task_condition(item, task_id, compiled_id, mapping_id)
                    for item in self.observations
                    for task_id, compiled_id, mapping_id in zip(
                        item.task_ids,
                        item.compiled_task_condition_ids,
                        item.state_mapping_contract_ids,
                        strict=True,
                    )
                ),
                key=lambda item: (item.mechanism_id, item.task_id),
            )
        )
        if self.confirmed_task_conditions != expected_conditions:
            raise ValueError("Bridge confirmed task conditions differ from observations")
        expected_blockers = tuple(
            item.mechanism_id
            for item in self.observations
            if _cell_failure_reasons(item, self.selection_thresholds)
        )
        if self.blockers != expected_blockers:
            raise ValueError("Bridge confirmation blockers are inconsistent")
        expected_status = "blocked" if expected_blockers else "passed"
        if self.status != expected_status:
            raise ValueError("Bridge confirmation status is inconsistent")
        expected_transition = (
            "capability_task_or_scaffold_redesign_only"
            if expected_blockers
            else "state_support_discovery"
        )
        if self.next_transition != expected_transition:
            raise ValueError("Bridge confirmation transition is inconsistent")
        if self.confirmation_id != bridge_confirmation_id(self):
            raise ValueError("Bridge confirmation identity is invalid")
        return self


def default_compiler_assisted_bridge_contract() -> CompilerAssistedBridgeContract:
    mechanisms = (
        _mechanism_contract(
            "context_conditioned_action",
            ("planning", "semantic_alignment"),
        ),
        _mechanism_contract("semantic_reconciliation", ("reconciliation",)),
        _mechanism_contract("recovery_and_stopping", ("recovery", "stopping")),
    )
    values = {
        "mechanisms": mechanisms,
        "selection_thresholds": ScaffoldSelectionThresholds(),
        "withdrawal_transfer": ScaffoldWithdrawalTransferContract(),
        "experiment_separation": BridgeVTDOCausalSeparationContract(),
        "schema_version": COMPILER_ASSISTED_BRIDGE_CONTRACT_VERSION,
    }
    provisional = CompilerAssistedBridgeContract.model_construct(contract_id="pending", **values)
    return CompilerAssistedBridgeContract(
        contract_id=compiler_assisted_bridge_contract_id(provisional),
        **values,
    )


def make_bridge_static_construct_audit(
    *,
    contract_id: str,
    mechanism_id: BridgeMechanism,
    task_admission_ids: Mapping[str, str],
    checks_by_task: Mapping[str, Mapping[str, bool]],
) -> BridgeStaticConstructAudit:
    if len(task_admission_ids) != 8 or len(checks_by_task) != 8:
        raise ValueError("Bridge static construct audit requires exactly eight tasks")
    if set(task_admission_ids) != set(checks_by_task):
        raise ValueError("Bridge static construct audit task identities are incomplete")
    normalized_checks = {
        task_id: dict(sorted(checks.items())) for task_id, checks in sorted(checks_by_task.items())
    }
    passed = sum(all(checks.values()) for checks in normalized_checks.values())
    values = {
        "contract_id": contract_id,
        "mechanism_id": mechanism_id,
        "task_admission_ids": dict(sorted(task_admission_ids.items())),
        "checks_by_task": normalized_checks,
        "passed_task_count": passed,
        "construct_fidelity_rate": passed / len(normalized_checks),
        "status": "passed" if passed == len(normalized_checks) else "blocked",
        "schema_version": BRIDGE_STATIC_CONSTRUCT_AUDIT_VERSION,
    }
    provisional = BridgeStaticConstructAudit.model_construct(audit_id="pending", **values)
    return BridgeStaticConstructAudit(
        audit_id=bridge_static_construct_audit_id(provisional),
        **values,
    )


def authorize_bridge_development(
    contract: CompilerAssistedBridgeContract,
    audits: Iterable[BridgeStaticConstructAudit],
) -> BridgeDevelopmentAuthorization:
    rows = tuple(sorted(audits, key=lambda item: BRIDGE_MECHANISMS.index(item.mechanism_id)))
    if any(item.contract_id != contract.contract_id for item in rows):
        raise ValueError("Bridge static audits belong to another contract")
    tasks = tuple(sorted(task_id for item in rows for task_id in item.task_admission_ids))
    blockers = tuple(item.mechanism_id for item in rows if item.status != "passed")
    values = {
        "contract_id": contract.contract_id,
        "static_audits": rows,
        "development_task_ids": tasks,
        "status": "blocked" if blockers else "authorized",
        "blockers": blockers,
        "next_transition": (
            "bridge_static_construct_repair_only" if blockers else "bridge_development_rollouts"
        ),
        "schema_version": BRIDGE_DEVELOPMENT_AUTHORIZATION_VERSION,
    }
    provisional = BridgeDevelopmentAuthorization.model_construct(
        authorization_id="pending",
        **values,
    )
    return BridgeDevelopmentAuthorization(
        authorization_id=bridge_development_authorization_id(provisional),
        **values,
    )


def authorize_bridge_confirmation(
    contract: CompilerAssistedBridgeContract,
    support_freeze: CompilerAssistedBridgeSupportFreeze,
    audits: Iterable[BridgeStaticConstructAudit],
) -> BridgeConfirmationAuthorization:
    if support_freeze.contract_id != contract.contract_id or support_freeze.status != "passed":
        raise ValueError("Bridge confirmation authorization requires a passing support freeze")
    rows = tuple(sorted(audits, key=lambda item: BRIDGE_MECHANISMS.index(item.mechanism_id)))
    if any(item.contract_id != contract.contract_id for item in rows):
        raise ValueError("Bridge confirmation static audits belong to another contract")
    development_tasks = tuple(
        sorted({task_id for item in support_freeze.observations for task_id in item.task_ids})
    )
    confirmation_tasks = tuple(
        sorted(task_id for item in rows for task_id in item.task_admission_ids)
    )
    blockers = tuple(item.mechanism_id for item in rows if item.status != "passed")
    selected = {
        item.mechanism_id: item.selected_scaffold_level
        for item in support_freeze.selections
        if item.selected_scaffold_level is not None
    }
    values = {
        "contract_id": contract.contract_id,
        "support_freeze_id": support_freeze.freeze_id,
        "static_audits": rows,
        "development_task_ids": development_tasks,
        "confirmation_task_ids": confirmation_tasks,
        "selected_scaffold_by_mechanism": selected,
        "status": "blocked" if blockers else "authorized",
        "blockers": blockers,
        "next_transition": (
            "bridge_confirmation_static_repair_only" if blockers else "fresh_bridge_confirmation"
        ),
        "schema_version": BRIDGE_CONFIRMATION_AUTHORIZATION_VERSION,
    }
    provisional = BridgeConfirmationAuthorization.model_construct(
        authorization_id="pending",
        **values,
    )
    return BridgeConfirmationAuthorization(
        authorization_id=bridge_confirmation_authorization_id(provisional),
        **values,
    )


def make_bridge_estimand_observation(
    *,
    estimand_id: EstimandId,
    evaluation_count: int,
    success_count: int,
    fixed_policy_success_count: int,
) -> BridgeEstimandObservation:
    values = {
        "estimand_id": estimand_id,
        "evaluation_count": evaluation_count,
        "success_count": success_count,
        "fixed_policy_success_count": fixed_policy_success_count,
        "schema_version": BRIDGE_ESTIMAND_OBSERVATION_VERSION,
    }
    provisional = BridgeEstimandObservation.model_construct(observation_id="pending", **values)
    return BridgeEstimandObservation(
        observation_id=bridge_estimand_observation_id(provisional),
        **values,
    )


def make_bridge_cell_observation(**values: Any) -> BridgeCellObservation:
    provisional = BridgeCellObservation.model_construct(observation_id="pending", **values)
    return BridgeCellObservation(
        observation_id=bridge_cell_observation_id(provisional),
        **values,
    )


def freeze_compiler_assisted_bridge_support(
    contract: CompilerAssistedBridgeContract,
    authorization: BridgeDevelopmentAuthorization,
    observations: Iterable[BridgeCellObservation],
) -> CompilerAssistedBridgeSupportFreeze:
    if authorization.contract_id != contract.contract_id or authorization.status != "authorized":
        raise ValueError("Bridge Development lacks a passing static authorization")
    rows = tuple(
        sorted(
            observations,
            key=lambda item: (BRIDGE_MECHANISMS.index(item.mechanism_id), item.scaffold_rank),
        )
    )
    if any(
        item.contract_id != contract.contract_id
        or item.phase_authorization_id != authorization.authorization_id
        or item.phase != "development"
        for item in rows
    ):
        raise ValueError("Bridge Development observations cross phase or authorization identities")
    by_mechanism = {
        mechanism: tuple(item for item in rows if item.mechanism_id == mechanism)
        for mechanism in BRIDGE_MECHANISMS
    }
    all_task_ids: set[str] = set()
    for mechanism, items in by_mechanism.items():
        if tuple(item.scaffold_level for item in items) != SCAFFOLD_LEVELS:
            raise ValueError(f"Bridge mechanism has incomplete levels: {mechanism}")
        task_sets = {item.task_ids for item in items}
        if len(task_sets) != 1:
            raise ValueError("Bridge scaffold levels must use the same tasks within a mechanism")
        task_ids = set(items[0].task_ids)
        if len({item.state_mapping_contract_ids for item in items}) != 1:
            raise ValueError("Bridge scaffold levels changed the state mapping contract")
        for compiled_conditions in zip(
            *(item.compiled_task_condition_ids for item in items),
            strict=True,
        ):
            if len(set(compiled_conditions)) != len(SCAFFOLD_LEVELS):
                raise ValueError("Bridge scaffold levels reused a compiled task condition")
        if all_task_ids & task_ids:
            raise ValueError("Bridge mechanisms must use disjoint task identities")
        all_task_ids.update(task_ids)
    if all_task_ids != set(authorization.development_task_ids):
        raise ValueError("Bridge observations differ from statically admitted tasks")
    selections = tuple(
        _select_mechanism_scaffold(
            mechanism,
            by_mechanism[mechanism],
            contract.selection_thresholds,
        )
        for mechanism in BRIDGE_MECHANISMS
    )
    blockers = tuple(item.mechanism_id for item in selections if item.status == "blocked")
    values = {
        "contract_id": contract.contract_id,
        "development_authorization_id": authorization.authorization_id,
        "observations": rows,
        "selections": selections,
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "next_transition": (
            "capability_task_or_scaffold_redesign_only" if blockers else "fresh_bridge_confirmation"
        ),
        "schema_version": BRIDGE_SUPPORT_FREEZE_VERSION,
    }
    provisional = CompilerAssistedBridgeSupportFreeze.model_construct(freeze_id="pending", **values)
    return CompilerAssistedBridgeSupportFreeze(
        freeze_id=bridge_support_freeze_id(provisional),
        **values,
    )


def confirm_compiler_assisted_bridge(
    contract: CompilerAssistedBridgeContract,
    support_freeze: CompilerAssistedBridgeSupportFreeze,
    authorization: BridgeConfirmationAuthorization,
    observations: Iterable[BridgeCellObservation],
) -> CompilerAssistedBridgeConfirmation:
    if support_freeze.contract_id != contract.contract_id or support_freeze.status != "passed":
        raise ValueError("Bridge confirmation requires a passing mechanism-level support freeze")
    if (
        authorization.contract_id != contract.contract_id
        or authorization.support_freeze_id != support_freeze.freeze_id
        or authorization.status != "authorized"
    ):
        raise ValueError("Bridge confirmation lacks a passing fresh-task static authorization")
    rows = tuple(sorted(observations, key=lambda item: BRIDGE_MECHANISMS.index(item.mechanism_id)))
    if len(rows) != len(BRIDGE_MECHANISMS):
        raise ValueError("Bridge confirmation needs one cell per mechanism")
    selected = authorization.selected_scaffold_by_mechanism
    development_tasks = {
        task_id for item in support_freeze.observations for task_id in item.task_ids
    }
    confirmation_tasks: set[str] = set()
    for item in rows:
        if (
            item.contract_id != contract.contract_id
            or item.phase_authorization_id != authorization.authorization_id
            or item.phase != "fresh_confirmation"
        ):
            raise ValueError("Bridge confirmation crosses phase or authorization identities")
        if item.scaffold_level != selected[item.mechanism_id]:
            raise ValueError("Bridge confirmation did not use the frozen mechanism scaffold")
        if development_tasks & set(item.task_ids):
            raise ValueError("Bridge confirmation reuses Development tasks")
        if confirmation_tasks & set(item.task_ids):
            raise ValueError("Bridge confirmation mechanisms overlap tasks")
        confirmation_tasks.update(item.task_ids)
        admitted_tasks = next(
            set(audit.task_admission_ids)
            for audit in authorization.static_audits
            if audit.mechanism_id == item.mechanism_id
        )
        if set(item.task_ids) != admitted_tasks:
            raise ValueError(
                "Bridge confirmation observations differ from statically admitted tasks"
            )
    blockers = tuple(
        item.mechanism_id
        for item in rows
        if _cell_failure_reasons(item, contract.selection_thresholds)
    )
    conditions = tuple(
        _confirmed_task_condition(item, task_id, compiled_id, mapping_id)
        for item in rows
        for task_id, compiled_id, mapping_id in zip(
            item.task_ids,
            item.compiled_task_condition_ids,
            item.state_mapping_contract_ids,
            strict=True,
        )
    )
    values = {
        "contract_id": contract.contract_id,
        "support_freeze_id": support_freeze.freeze_id,
        "confirmation_authorization_id": authorization.authorization_id,
        "selection_thresholds": contract.selection_thresholds,
        "observations": rows,
        "confirmed_task_conditions": tuple(
            sorted(conditions, key=lambda item: (item.mechanism_id, item.task_id))
        ),
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "next_transition": (
            "capability_task_or_scaffold_redesign_only" if blockers else "state_support_discovery"
        ),
        "schema_version": BRIDGE_CONFIRMATION_VERSION,
    }
    provisional = CompilerAssistedBridgeConfirmation.model_construct(
        confirmation_id="pending",
        **values,
    )
    return CompilerAssistedBridgeConfirmation(
        confirmation_id=bridge_confirmation_id(provisional),
        **values,
    )


def compiler_assisted_bridge_contract_id(value: CompilerAssistedBridgeContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_compiler_assisted_bridge_contract:",
    )


def bridge_static_construct_audit_id(value: BridgeStaticConstructAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_bridge_static_construct_audit:",
    )


def bridge_development_authorization_id(value: BridgeDevelopmentAuthorization) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"authorization_id"}),
        prefix="finance_bridge_development_authorization:",
    )


def bridge_confirmation_authorization_id(value: BridgeConfirmationAuthorization) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"authorization_id"}),
        prefix="finance_bridge_confirmation_authorization:",
    )


def bridge_estimand_observation_id(value: BridgeEstimandObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="finance_bridge_estimand_observation:",
    )


def bridge_cell_observation_id(value: BridgeCellObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="finance_compiler_assisted_bridge_cell:",
    )


def mechanism_scaffold_selection_id(value: MechanismScaffoldSelection) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"selection_id"}),
        prefix="finance_compiler_assisted_bridge_selection:",
    )


def bridge_support_freeze_id(value: CompilerAssistedBridgeSupportFreeze) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"freeze_id"}),
        prefix="finance_compiler_assisted_bridge_support_freeze:",
    )


def confirmed_bridge_task_condition_id(value: ConfirmedBridgeTaskCondition) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"condition_ref_id"}),
        prefix="finance_bridge_confirmed_task_condition:",
    )


def bridge_confirmation_id(value: CompilerAssistedBridgeConfirmation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"confirmation_id"}),
        prefix="finance_compiler_assisted_bridge_confirmation:",
    )


def _mechanism_contract(
    mechanism_id: BridgeMechanism,
    target_capability_ids: tuple[str, ...],
) -> BridgeMechanismContract:
    return BridgeMechanismContract(
        mechanism_id=mechanism_id,
        target_capability_ids=target_capability_ids,
        estimands=tuple(
            CapabilityEstimandContract(
                estimand_id=estimand_id,
                mechanism_id=mechanism_id,
                definition=ESTIMAND_DEFINITIONS[estimand_id],
            )
            for estimand_id in MECHANISM_ESTIMANDS[mechanism_id]
        ),
    )


def _select_mechanism_scaffold(
    mechanism: BridgeMechanism,
    observations: tuple[BridgeCellObservation, ...],
    thresholds: ScaffoldSelectionThresholds,
) -> MechanismScaffoldSelection:
    failures_by_level = {
        item.scaffold_level: _cell_failure_reasons(item, thresholds) for item in observations
    }
    passing = tuple(
        item.scaffold_level for item in observations if not failures_by_level[item.scaffold_level]
    )
    values = {
        "mechanism_id": mechanism,
        "selected_scaffold_level": passing[0] if passing else None,
        "passing_scaffold_levels": passing,
        "status": "selected" if passing else "blocked",
        "failure_reasons_by_level": failures_by_level,
        "schema_version": BRIDGE_MECHANISM_SELECTION_VERSION,
    }
    provisional = MechanismScaffoldSelection.model_construct(selection_id="pending", **values)
    return MechanismScaffoldSelection(
        selection_id=mechanism_scaffold_selection_id(provisional),
        **values,
    )


def _cell_failure_reasons(
    item: BridgeCellObservation,
    thresholds: ScaffoldSelectionThresholds,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if item.instrument_valid_rate < thresholds.instrument_valid_rate_required:
        reasons.append("instrument_invalid")
    if item.valid_trajectory_rate < thresholds.valid_trajectory_rate_minimum:
        reasons.append("valid_trajectory_rate_low")
    for estimand in item.estimand_observations:
        if estimand.success_rate < thresholds.estimand_rate_minimum:
            reasons.append(f"{estimand.estimand_id}:below_boundary")
        if estimand.success_rate > thresholds.estimand_rate_maximum:
            reasons.append(f"{estimand.estimand_id}:saturated")
        if estimand.fixed_policy_gain < thresholds.fixed_policy_gain_minimum:
            reasons.append(f"{estimand.estimand_id}:fixed_policy_gain_low")
    if item.host_interference_count > thresholds.maximum_host_interference_count:
        reasons.append("host_interference_detected")
    if item.oracle_leakage_count > thresholds.maximum_oracle_leakage_count:
        reasons.append("oracle_leakage_detected")
    return tuple(reasons)


def _confirmed_task_condition(
    item: BridgeCellObservation,
    task_id: str,
    compiled_task_condition_id: str,
    state_mapping_contract_id: str,
) -> ConfirmedBridgeTaskCondition:
    values = {
        "task_id": task_id,
        "mechanism_id": item.mechanism_id,
        "scaffold_level": item.scaffold_level,
        "compiled_task_condition_id": compiled_task_condition_id,
        "state_mapping_contract_id": state_mapping_contract_id,
        "schema_version": BRIDGE_CONFIRMED_TASK_CONDITION_VERSION,
    }
    provisional = ConfirmedBridgeTaskCondition.model_construct(
        condition_ref_id="pending",
        **values,
    )
    return ConfirmedBridgeTaskCondition(
        condition_ref_id=confirmed_bridge_task_condition_id(provisional),
        **values,
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
