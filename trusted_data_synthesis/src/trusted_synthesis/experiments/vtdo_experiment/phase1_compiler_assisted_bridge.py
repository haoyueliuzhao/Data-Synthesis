from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.scaffolding import SCAFFOLD_LEVELS, ScaffoldLevel
from trusted_synthesis.hashing import canonical_hash

COMPILER_ASSISTED_BRIDGE_CONTRACT_VERSION = "finance_compiler_assisted_bridge.v1"
BRIDGE_CELL_OBSERVATION_VERSION = "finance_compiler_assisted_bridge_cell.v1"
BRIDGE_MECHANISM_SELECTION_VERSION = "finance_compiler_assisted_bridge_selection.v1"
BRIDGE_SUPPORT_FREEZE_VERSION = "finance_compiler_assisted_bridge_support_freeze.v1"

BridgeMechanism = Literal[
    "context_conditioned_action",
    "semantic_reconciliation",
    "recovery_and_stopping",
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


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BridgeMechanismContract(FrozenModel):
    mechanism_id: BridgeMechanism
    target_capability_ids: tuple[str, ...] = Field(min_length=1)
    development_task_count: Literal[8] = 8
    fresh_confirmation_task_count: Literal[8] = 8
    support_selected_per_mechanism: Literal[True] = True
    per_task_scaffold_selection_forbidden: Literal[True] = True


class ScaffoldSelectionThresholds(FrozenModel):
    target_success_rate_minimum: float = Field(default=0.15, ge=0, le=1)
    target_success_rate_maximum: float = Field(default=0.85, ge=0, le=1)
    valid_trajectory_rate_minimum: float = Field(default=0.20, ge=0, le=1)
    tasks_with_three_states_rate_minimum: float = Field(default=0.75, ge=0, le=1)
    counterfactual_fidelity_minimum: float = Field(default=0.95, ge=0, le=1)
    fixed_policy_gain_minimum: float = Field(default=0.05, ge=-1, le=1)
    instrument_valid_rate_required: float = Field(default=1.0, ge=1.0, le=1.0)
    maximum_host_interference_count: Literal[0] = 0
    maximum_oracle_leakage_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_thresholds(self) -> ScaffoldSelectionThresholds:
        if self.target_success_rate_minimum >= self.target_success_rate_maximum:
            raise ValueError("Bridge target success band must be non-empty")
        return self


class ScaffoldWithdrawalContract(FrozenModel):
    conditions: tuple[WithdrawalCondition, ...] = (
        "unassisted_train_unassisted_eval",
        "scaffold_train_scaffold_eval",
        "scaffold_train_unassisted_eval",
        "scaffold_train_weaker_scaffold_eval",
    )
    primary_transfer_estimand: Literal[
        "trained_scaffold_to_unassisted_delta_over_unassisted_baseline"
    ] = "trained_scaffold_to_unassisted_delta_over_unassisted_baseline"
    weaker_scaffold_annealing_required: Literal[True] = True
    same_heldout_task_set_required: Literal[True] = True
    same_student_checkpoint_family_required: Literal[True] = True


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
    withdrawal: ScaffoldWithdrawalContract
    task_identity_includes_scaffold: Literal[True] = True
    compiled_condition_identity: Literal["task_runtime_capability_scaffold_policy_version"] = (
        "task_runtime_capability_scaffold_policy_version"
    )
    same_scaffold_for_all_methods_in_causal_comparison: Literal[True] = True
    same_oracle_across_scaffold_levels: Literal[True] = True
    capability_outcome_not_a_runtime_gate: Literal[True] = True
    inverse_success_weighting_forbidden: Literal[True] = True
    support_freeze_before_fresh_confirmation: Literal[True] = True
    support_selected_per_mechanism_not_task: Literal[True] = True
    api_authorized_before_scaffold_admission: Literal[False] = False
    gpu_authorized_before_support_freeze: Literal[False] = False
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


class BridgeCellObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    scaffold_level: ScaffoldLevel
    scaffold_rank: Literal[0, 1, 2, 3]
    task_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    rollout_count: Literal[48] = 48
    instrument_valid_rollout_count: int = Field(ge=0, le=48)
    model_outcome_count: int = Field(ge=0, le=48)
    target_success_count: int = Field(ge=0, le=48)
    valid_trajectory_count: int = Field(ge=0, le=48)
    fixed_policy_success_count: int = Field(ge=0, le=48)
    tasks_with_three_reachable_states_count: int = Field(ge=0, le=8)
    reachable_state_count: int = Field(ge=0)
    state_entropy: float = Field(ge=0)
    counterfactual_evaluation_count: int = Field(ge=1, le=48)
    counterfactual_faithful_count: int = Field(ge=0, le=48)
    host_interference_count: int = Field(ge=0, le=48)
    oracle_leakage_count: int = Field(ge=0, le=48)
    runtime_failure_count: int = Field(ge=0, le=48)
    schema_version: str = BRIDGE_CELL_OBSERVATION_VERSION

    @property
    def instrument_valid_rate(self) -> float:
        return self.instrument_valid_rollout_count / self.rollout_count

    @property
    def target_success_rate(self) -> float:
        return _ratio(self.target_success_count, self.model_outcome_count)

    @property
    def valid_trajectory_rate(self) -> float:
        return _ratio(self.valid_trajectory_count, self.model_outcome_count)

    @property
    def fixed_policy_success_rate(self) -> float:
        return _ratio(self.fixed_policy_success_count, self.model_outcome_count)

    @property
    def tasks_with_three_states_rate(self) -> float:
        return self.tasks_with_three_reachable_states_count / len(self.task_ids)

    @property
    def counterfactual_fidelity(self) -> float:
        return self.counterfactual_faithful_count / self.counterfactual_evaluation_count

    @model_validator(mode="after")
    def validate_observation(self) -> BridgeCellObservation:
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("Bridge cell task identities must be unique")
        if self.scaffold_rank != SCAFFOLD_LEVELS.index(self.scaffold_level):
            raise ValueError("Bridge cell scaffold rank differs from its level")
        if self.model_outcome_count > self.instrument_valid_rollout_count:
            raise ValueError("Bridge model outcomes exceed instrument-valid rollouts")
        if self.model_outcome_count + self.runtime_failure_count != self.rollout_count:
            raise ValueError("Bridge rollout accounting is incomplete")
        bounded_by_outcomes = (
            self.target_success_count,
            self.valid_trajectory_count,
            self.fixed_policy_success_count,
        )
        if any(value > self.model_outcome_count for value in bounded_by_outcomes):
            raise ValueError("Bridge behavior counts exceed model outcomes")
        if self.counterfactual_faithful_count > self.counterfactual_evaluation_count:
            raise ValueError("Bridge faithful counterfactuals exceed evaluated cases")
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
    selection_scope: Literal["mechanism_not_task"] = "mechanism_not_task"
    schema_version: str = BRIDGE_MECHANISM_SELECTION_VERSION

    @model_validator(mode="after")
    def validate_selection(self) -> MechanismScaffoldSelection:
        expected_status = "selected" if self.selected_scaffold_level else "blocked"
        if self.status != expected_status:
            raise ValueError("Bridge mechanism selection status is inconsistent")
        if self.selected_scaffold_level and (
            not self.passing_scaffold_levels
            or self.selected_scaffold_level != self.passing_scaffold_levels[0]
        ):
            raise ValueError("Bridge mechanism did not select the minimum passing scaffold")
        if self.selection_id != mechanism_scaffold_selection_id(self):
            raise ValueError("Bridge mechanism selection identity is invalid")
        return self


class CompilerAssistedBridgeSupportFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    observations: tuple[BridgeCellObservation, ...] = Field(min_length=12, max_length=12)
    selections: tuple[MechanismScaffoldSelection, ...] = Field(min_length=3, max_length=3)
    status: Literal["passed", "blocked"]
    blockers: tuple[str, ...]
    next_transition: Literal[
        "fresh_bridge_confirmation",
        "capability_task_or_scaffold_redesign_only",
    ]
    task_reallocation_used: Literal[False] = False
    inverse_success_weighting_used: Literal[False] = False
    per_task_scaffold_selection_used: Literal[False] = False
    gpu_jobs: Literal[0] = 0
    schema_version: str = BRIDGE_SUPPORT_FREEZE_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> CompilerAssistedBridgeSupportFreeze:
        expected_cells = {
            (mechanism, level) for mechanism in BRIDGE_MECHANISMS for level in SCAFFOLD_LEVELS
        }
        observed_cells = {(item.mechanism_id, item.scaffold_level) for item in self.observations}
        if observed_cells != expected_cells or len(observed_cells) != len(self.observations):
            raise ValueError("Bridge support observations are incomplete or duplicated")
        if tuple(item.mechanism_id for item in self.selections) != BRIDGE_MECHANISMS:
            raise ValueError("Bridge support selections are incomplete or unordered")
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


def default_compiler_assisted_bridge_contract() -> CompilerAssistedBridgeContract:
    values = {
        "mechanisms": (
            BridgeMechanismContract(
                mechanism_id="context_conditioned_action",
                target_capability_ids=("planning", "semantic_alignment"),
            ),
            BridgeMechanismContract(
                mechanism_id="semantic_reconciliation",
                target_capability_ids=("reconciliation",),
            ),
            BridgeMechanismContract(
                mechanism_id="recovery_and_stopping",
                target_capability_ids=("recovery", "stopping"),
            ),
        ),
        "selection_thresholds": ScaffoldSelectionThresholds(),
        "withdrawal": ScaffoldWithdrawalContract(),
        "schema_version": COMPILER_ASSISTED_BRIDGE_CONTRACT_VERSION,
    }
    provisional = CompilerAssistedBridgeContract.model_construct(contract_id="pending", **values)
    return CompilerAssistedBridgeContract(
        contract_id=compiler_assisted_bridge_contract_id(provisional),
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
    observations: Iterable[BridgeCellObservation],
) -> CompilerAssistedBridgeSupportFreeze:
    rows = tuple(sorted(observations, key=lambda item: (item.mechanism_id, item.scaffold_rank)))
    if any(item.contract_id != contract.contract_id for item in rows):
        raise ValueError("Bridge observations belong to another contract")
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
        if all_task_ids & task_ids:
            raise ValueError("Bridge mechanisms must use disjoint task identities")
        all_task_ids.update(task_ids)
    selections = tuple(
        _select_mechanism_scaffold(
            mechanism,
            by_mechanism[mechanism],
            contract.selection_thresholds,
        )
        for mechanism in BRIDGE_MECHANISMS
    )
    blockers = tuple(item.mechanism_id for item in selections if item.status == "blocked")
    values: dict[str, Any] = {
        "contract_id": contract.contract_id,
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


def compiler_assisted_bridge_contract_id(value: CompilerAssistedBridgeContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_compiler_assisted_bridge_contract:",
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
    checks = (
        (
            item.instrument_valid_rate >= thresholds.instrument_valid_rate_required,
            "instrument_invalid",
        ),
        (
            item.target_success_rate >= thresholds.target_success_rate_minimum,
            "target_success_below_boundary",
        ),
        (
            item.target_success_rate <= thresholds.target_success_rate_maximum,
            "target_success_saturated",
        ),
        (
            item.valid_trajectory_rate >= thresholds.valid_trajectory_rate_minimum,
            "valid_trajectory_rate_low",
        ),
        (
            item.tasks_with_three_states_rate >= thresholds.tasks_with_three_states_rate_minimum,
            "reachable_state_support_low",
        ),
        (
            item.counterfactual_fidelity >= thresholds.counterfactual_fidelity_minimum,
            "counterfactual_fidelity_low",
        ),
        (
            item.target_success_rate - item.fixed_policy_success_rate
            >= thresholds.fixed_policy_gain_minimum,
            "fixed_policy_gain_low",
        ),
        (
            item.host_interference_count <= thresholds.maximum_host_interference_count,
            "host_interference_detected",
        ),
        (
            item.oracle_leakage_count <= thresholds.maximum_oracle_leakage_count,
            "oracle_leakage_detected",
        ),
    )
    return tuple(reason for passed, reason in checks if not passed)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
