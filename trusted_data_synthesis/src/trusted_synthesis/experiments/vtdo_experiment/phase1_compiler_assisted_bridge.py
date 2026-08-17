from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.audit_artifacts import AtomicAuditCaseResult
from trusted_synthesis.core.trajectory.scaffolding import (
    SCAFFOLD_LEVELS,
    CompiledPublicStateSummary,
    CompiledTaskConditionLineage,
    ScaffoldLevel,
)
from trusted_synthesis.hashing import canonical_hash

COMPILER_ASSISTED_BRIDGE_CONTRACT_VERSION = "finance_compiler_assisted_bridge.v4"
BRIDGE_STATIC_CONSTRUCT_AUDIT_VERSION = "finance_bridge_static_construct_audit.v2"
BRIDGE_DEVELOPMENT_AUTHORIZATION_VERSION = "finance_bridge_development_authorization.v2"
BRIDGE_CONFIRMATION_AUTHORIZATION_VERSION = "finance_bridge_confirmation_authorization.v2"
BRIDGE_ESTIMAND_OBSERVATION_VERSION = "finance_bridge_estimand_observation.v1"
BRIDGE_EXECUTION_MANIFEST_VERSION = "finance_bridge_execution_manifest.v1"
BRIDGE_ROLLOUT_OBSERVATION_VERSION = "finance_compiler_assisted_bridge_rollout.v1"
BRIDGE_CELL_OBSERVATION_VERSION = "finance_compiler_assisted_bridge_cell.v4"
BRIDGE_MECHANISM_SELECTION_VERSION = "finance_compiler_assisted_bridge_selection.v2"
BRIDGE_SUPPORT_FREEZE_VERSION = "finance_compiler_assisted_bridge_support_freeze.v3"
BRIDGE_CONFIRMED_TASK_CONDITION_VERSION = "finance_bridge_confirmed_task_condition.v2"
BRIDGE_CONFIRMATION_VERSION = "finance_compiler_assisted_bridge_confirmation.v3"

BridgeMechanism = Literal[
    "context_conditioned_action",
    "semantic_reconciliation",
    "recovery_and_stopping",
]
BridgePhase = Literal["development", "fresh_confirmation"]
BridgeRolloutTerminal = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "runtime_failure",
    "instrument_failure",
]
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


class BridgeHierarchicalInferenceContract(FrozenModel):
    primary_sampling_unit: Literal["task"] = "task"
    secondary_sampling_unit: Literal["rollout_within_task"] = "rollout_within_task"
    task_first_rollout_second_bootstrap: Literal[True] = True
    scaffold_levels_paired_within_task: Literal[True] = True
    mechanism_level_confidence_intervals_required: Literal[True] = True
    confidence_level: float = Field(default=0.95, ge=0.9, le=0.99)
    bootstrap_replicates: int = Field(default=5000, ge=1000)
    minimal_passing_level_rule: Literal[
        "lowest_level_with_joint_ci_thresholds_and_all_fidelity_gates"
    ] = "lowest_level_with_joint_ci_thresholds_and_all_fidelity_gates"
    fixed_policy_baseline_paired_by_task: Literal[True] = True
    failure_attribution_coverage_required: float = Field(default=1.0, ge=1.0, le=1.0)
    rollout_pseudoreplication_forbidden: Literal[True] = True
    task_level_success_probability_reported: Literal[True] = True


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
    inference: BridgeHierarchicalInferenceContract
    withdrawal_transfer: ScaffoldWithdrawalTransferContract
    experiment_separation: BridgeVTDOCausalSeparationContract
    task_identity_includes_scaffold: Literal[True] = True
    compiled_condition_identity: Literal[
        "joint_omega_runtime_capability_scaffold_payload_projection_admission"
    ] = "joint_omega_runtime_capability_scaffold_payload_projection_admission"
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
    case_results: tuple[AtomicAuditCaseResult, ...] = Field(min_length=48, max_length=48)
    auditor_id: str = Field(min_length=1)
    auditor_version: str = Field(min_length=1)
    auditor_manifest_hash: str = Field(min_length=1)
    passed_task_count: int = Field(ge=0, le=8)
    construct_fidelity_rate: float = Field(ge=0, le=1)
    status: Literal["passed", "blocked"]
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = BRIDGE_STATIC_CONSTRUCT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BridgeStaticConstructAudit:
        if len(set(self.task_admission_ids.values())) != len(self.task_admission_ids):
            raise ValueError("Bridge static audit reuses scaffold admissions")
        admission_to_task = {
            admission_id: task_id for task_id, admission_id in self.task_admission_ids.items()
        }
        observed = {
            (admission_to_task.get(item.subject_id), item.check_id)
            for item in self.case_results
        }
        expected = {
            (task_id, check_id)
            for task_id in self.task_admission_ids
            for check_id in STATIC_CONSTRUCT_CHECKS
        }
        if observed != expected or len(observed) != len(self.case_results):
            raise ValueError("Bridge static construct atomic checks are incomplete")
        if any(
            self.contract_id not in item.input_artifact_ids
            or item.subject_id not in admission_to_task
            or item.subject_id not in item.input_artifact_ids
            for item in self.case_results
        ):
            raise ValueError("Bridge static construct case crosses contract identities")
        if any(
            item.implementation_manifest
            != {
                "auditor_id": self.auditor_id,
                "auditor_version": self.auditor_version,
                "check_id": item.check_id,
            }
            or item.replay_implementation_manifest
            != {
                "auditor_id": f"{self.auditor_id}.independent",
                "auditor_version": self.auditor_version,
                "check_id": item.check_id,
            }
            for item in self.case_results
        ):
            raise ValueError("Bridge static construct case uses an unknown implementation")
        expected_manifest = canonical_hash(
            {"auditor_id": self.auditor_id, "auditor_version": self.auditor_version},
            prefix="bridge_static_construct_auditor_manifest:",
        )
        if self.auditor_manifest_hash != expected_manifest:
            raise ValueError("Bridge static construct auditor manifest is invalid")
        checks_by_task = self.checks_by_task
        expected_passed = sum(all(checks.values()) for checks in checks_by_task.values())
        if self.passed_task_count != expected_passed:
            raise ValueError("Bridge static audit pass count is inconsistent")
        expected_rate = expected_passed / len(checks_by_task)
        if self.construct_fidelity_rate != expected_rate:
            raise ValueError("Bridge static construct fidelity is inconsistent")
        expected_status = "passed" if expected_rate == 1.0 else "blocked"
        if self.status != expected_status:
            raise ValueError("Bridge static audit status is inconsistent")
        if self.audit_id != bridge_static_construct_audit_id(self):
            raise ValueError("Bridge static construct audit identity is invalid")
        return self

    @property
    def checks_by_task(self) -> dict[str, dict[str, bool]]:
        admission_to_task = {
            admission_id: task_id for task_id, admission_id in self.task_admission_ids.items()
        }
        rows: dict[str, dict[str, bool]] = {
            task_id: {} for task_id in sorted(self.task_admission_ids)
        }
        for item in self.case_results:
            rows[admission_to_task[item.subject_id]][item.check_id] = item.check_passed
        return {task_id: dict(sorted(checks.items())) for task_id, checks in rows.items()}


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


class BridgeEstimandOutcome(FrozenModel):
    estimand_id: EstimandId
    evaluated: bool
    success: bool | None = None
    fixed_policy_success: bool | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> BridgeEstimandOutcome:
        if self.evaluated != (self.success is not None):
            raise ValueError("Bridge Estimand evaluation status is inconsistent")
        if self.evaluated != (self.fixed_policy_success is not None):
            raise ValueError("Bridge fixed-policy evaluation status is inconsistent")
        return self


class BridgeExecutionManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_invocation_config: dict[str, Any]
    model_config_hash: str = Field(min_length=1)
    provider_route: dict[str, Any]
    provider_route_hash: str = Field(min_length=1)
    prompt_manifest: dict[str, Any]
    prompt_manifest_hash: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    runtime_projection_id: str = Field(min_length=1)
    runtime_authority_policy_id: str = Field(min_length=1)
    runtime_manifest: dict[str, Any]
    runtime_manifest_hash: str = Field(min_length=1)
    tool_manifest: dict[str, Any]
    tool_manifest_hash: str = Field(min_length=1)
    schema_version: str = BRIDGE_EXECUTION_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> BridgeExecutionManifest:
        expected_payloads = {
            "model_config": (self.model_invocation_config, self.model_config_hash),
            "provider_route": (self.provider_route, self.provider_route_hash),
            "prompt_manifest": (self.prompt_manifest, self.prompt_manifest_hash),
            "runtime_manifest": (self.runtime_manifest, self.runtime_manifest_hash),
            "tool_manifest": (self.tool_manifest, self.tool_manifest_hash),
        }
        for label, (payload, observed_hash) in expected_payloads.items():
            expected_hash = canonical_hash(
                payload,
                prefix=f"finance_bridge_{label}:",
            )
            if observed_hash != expected_hash:
                raise ValueError(f"Bridge {label} hash is invalid")
            if _contains_sensitive_key(payload):
                raise ValueError(f"Bridge {label} contains credential material")
        if self.model_invocation_config.get("model_id") != self.model_id:
            raise ValueError("Bridge model config identity is inconsistent")
        if (
            self.prompt_manifest.get("compiled_task_condition_id") is None
            or self.runtime_manifest.get("runtime_id") != self.runtime_id
            or self.runtime_manifest.get("runtime_projection_id")
            != self.runtime_projection_id
            or self.runtime_manifest.get("runtime_authority_policy_id")
            != self.runtime_authority_policy_id
        ):
            raise ValueError("Bridge execution manifest is detached from its runtime condition")
        allowed_tools = self.tool_manifest.get("allowed_tools")
        if (
            not isinstance(allowed_tools, list)
            or not allowed_tools
            or any(not isinstance(item, str) or not item for item in allowed_tools)
            or allowed_tools != sorted(set(allowed_tools))
        ):
            raise ValueError("Bridge execution manifest requires a canonical tool manifest")
        if not self.provider_route.get("provider") or not self.provider_route.get("route_id"):
            raise ValueError("Bridge execution manifest requires a frozen provider route")
        if not self.prompt_manifest.get("template_id"):
            raise ValueError("Bridge execution manifest requires a frozen Prompt template")
        if self.manifest_id != bridge_execution_manifest_id(self):
            raise ValueError("Bridge execution manifest identity is invalid")
        return self


class BridgeRolloutObservation(FrozenModel):
    rollout_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    phase_authorization_id: str = Field(min_length=1)
    phase: BridgePhase
    mechanism_id: BridgeMechanism
    scaffold_level: ScaffoldLevel
    scaffold_rank: Literal[0, 1, 2, 3]
    replicate_index: int = Field(ge=0, le=5)
    condition_lineage: CompiledTaskConditionLineage
    execution_manifest: BridgeExecutionManifest
    provider_call_ids: tuple[str, ...] = Field(min_length=1)
    public_state_summary: CompiledPublicStateSummary | None = None
    terminal_category: BridgeRolloutTerminal
    independent_validity_passed: bool
    quotient_state_id: str | None = Field(default=None, min_length=1)
    decision_trace_hash: str | None = Field(default=None, min_length=64, max_length=64)
    estimand_outcomes: tuple[BridgeEstimandOutcome, ...] = Field(min_length=1)
    host_interference_detected: bool = False
    oracle_leakage_detected: bool = False
    failure_reason: str | None = Field(default=None, min_length=1)
    raw_payload: dict[str, Any]
    raw_payload_hash: str = Field(min_length=1)
    raw_artifact_uri: str = Field(min_length=1)
    raw_artifact_sha256: str = Field(min_length=64, max_length=64)
    schema_version: str = BRIDGE_ROLLOUT_OBSERVATION_VERSION

    @property
    def task_id(self) -> str:
        return self.condition_lineage.task_id

    @model_validator(mode="after")
    def validate_rollout(self) -> BridgeRolloutObservation:
        if self.scaffold_rank != SCAFFOLD_LEVELS.index(self.scaffold_level):
            raise ValueError("Bridge rollout scaffold rank differs from its level")
        if self.condition_lineage.scaffold_level != self.scaffold_level:
            raise ValueError("Bridge rollout crosses compiled scaffold conditions")
        if (
            self.execution_manifest.contract_id != self.contract_id
            or self.execution_manifest.runtime_projection_id
            != self.condition_lineage.runtime_projection_id
            or self.execution_manifest.runtime_authority_policy_id
            != self.condition_lineage.runtime_authority_policy_id
            or self.execution_manifest.prompt_manifest.get("compiled_task_condition_id")
            != self.condition_lineage.compiled_task_condition_id
        ):
            raise ValueError("Bridge execution manifest crosses compiled task conditions")
        if len(set(self.provider_call_ids)) != len(self.provider_call_ids):
            raise ValueError("Bridge provider calls are duplicated")
        expected_estimands = MECHANISM_ESTIMANDS[self.mechanism_id]
        if tuple(item.estimand_id for item in self.estimand_outcomes) != expected_estimands:
            raise ValueError("Bridge rollout mechanism Estimands are incomplete or reordered")
        if self.scaffold_rank == 0:
            if self.public_state_summary is not None:
                raise ValueError("unassisted Bridge rollout cannot contain a scaffold summary")
        elif (
            self.public_state_summary is None
            or self.public_state_summary.task_id != self.task_id
            or self.public_state_summary.summary_spec.summary_spec_id
            != self.condition_lineage.public_summary_spec_id
        ):
            raise ValueError("assisted Bridge rollout lacks its compiled public summary")
        model_outcome = self.terminal_category in {
            "model_valid_trajectory",
            "model_invalid_trajectory",
        }
        if self.independent_validity_passed != (
            self.terminal_category == "model_valid_trajectory"
        ):
            raise ValueError("Bridge rollout validity differs from its terminal category")
        if model_outcome != bool(self.decision_trace_hash):
            raise ValueError("Bridge model outcomes require exactly one decision trace")
        if self.independent_validity_passed and not self.quotient_state_id:
            raise ValueError("valid Bridge trajectories require a Quotient State")
        if not model_outcome and any(item.evaluated for item in self.estimand_outcomes):
            raise ValueError("failed Bridge executions cannot enter Estimand denominators")
        if self.terminal_category == "instrument_failure":
            if not (
                self.host_interference_detected
                or self.oracle_leakage_detected
                or self.failure_reason
            ):
                raise ValueError("instrument failure requires an auditable reason")
        elif self.host_interference_detected or self.oracle_leakage_detected:
            raise ValueError("instrument contamination requires instrument_failure")
        if self.terminal_category in {"runtime_failure", "instrument_failure"}:
            if not self.failure_reason:
                raise ValueError("failed Bridge execution requires a failure reason")
        elif self.failure_reason:
            raise ValueError("model outcomes cannot carry a runtime failure reason")
        if (
            self.raw_payload.get("task_id") != self.task_id
            or self.raw_payload.get("terminal_category") != self.terminal_category
            or self.raw_payload.get("execution_manifest_id")
            != self.execution_manifest.manifest_id
            or tuple(self.raw_payload.get("provider_call_ids", ()))
            != self.provider_call_ids
        ):
            raise ValueError("Bridge raw payload identity is inconsistent")
        expected_payload_hash = canonical_hash(
            self.raw_payload,
            prefix="finance_bridge_raw_rollout:",
        )
        if self.raw_payload_hash != expected_payload_hash:
            raise ValueError("Bridge raw payload hash is invalid")
        if self.raw_artifact_sha256 != _sha256_payload(self.raw_payload):
            raise ValueError("Bridge raw artifact SHA-256 is invalid")
        if self.rollout_id != bridge_rollout_observation_id(self):
            raise ValueError("Bridge rollout observation identity is invalid")
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
    condition_lineage_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    rollout_observations: tuple[BridgeRolloutObservation, ...] = Field(
        min_length=48,
        max_length=48,
    )
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
    instrument_failure_count: int = Field(ge=0, le=48)
    schema_version: str = BRIDGE_CELL_OBSERVATION_VERSION

    @property
    def instrument_valid_rate(self) -> float:
        return self.instrument_valid_rollout_count / self.rollout_count

    @property
    def valid_trajectory_rate(self) -> float:
        return _ratio(self.valid_trajectory_count, self.model_outcome_count)

    @model_validator(mode="after")
    def validate_observation(self) -> BridgeCellObservation:
        if tuple(
            sorted(
                self.rollout_observations,
                key=lambda item: (item.task_id, item.replicate_index),
            )
        ) != self.rollout_observations:
            raise ValueError("Bridge atomic rollouts are not canonically ordered")
        if any(
            item.contract_id != self.contract_id
            or item.phase_authorization_id != self.phase_authorization_id
            or item.phase != self.phase
            or item.mechanism_id != self.mechanism_id
            or item.scaffold_level != self.scaffold_level
            for item in self.rollout_observations
        ):
            raise ValueError("Bridge atomic rollouts cross cell identities")
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("Bridge cell task identities must be unique")
        if len(self.compiled_task_condition_ids) != len(set(self.compiled_task_condition_ids)):
            raise ValueError("Bridge cell compiled conditions must be unique")
        if len(self.state_mapping_contract_ids) != len(set(self.state_mapping_contract_ids)):
            raise ValueError("Bridge cell state mapping contracts must be unique")
        if len(self.condition_lineage_ids) != len(set(self.condition_lineage_ids)):
            raise ValueError("Bridge cell condition lineages must be unique")
        if self.scaffold_rank != SCAFFOLD_LEVELS.index(self.scaffold_level):
            raise ValueError("Bridge cell scaffold rank differs from its level")
        expected = _derive_bridge_cell_values(self.rollout_observations)
        derived_fields = {
            "task_ids": self.task_ids,
            "compiled_task_condition_ids": self.compiled_task_condition_ids,
            "state_mapping_contract_ids": self.state_mapping_contract_ids,
            "condition_lineage_ids": self.condition_lineage_ids,
            "instrument_valid_rollout_count": self.instrument_valid_rollout_count,
            "model_outcome_count": self.model_outcome_count,
            "valid_trajectory_count": self.valid_trajectory_count,
            "estimand_observations": self.estimand_observations,
            "preliminary_unique_state_count": self.preliminary_unique_state_count,
            "tasks_with_multiple_observed_states_count": (
                self.tasks_with_multiple_observed_states_count
            ),
            "state_entropy": self.state_entropy,
            "host_interference_count": self.host_interference_count,
            "oracle_leakage_count": self.oracle_leakage_count,
            "runtime_failure_count": self.runtime_failure_count,
            "instrument_failure_count": self.instrument_failure_count,
        }
        if derived_fields != expected:
            raise ValueError("Bridge cell aggregates were not derived from atomic rollouts")
        if (
            self.model_outcome_count
            + self.runtime_failure_count
            + self.instrument_failure_count
            != self.rollout_count
        ):
            raise ValueError("Bridge rollout accounting is incomplete")
        if (
            self.instrument_valid_rollout_count
            + self.runtime_failure_count
            + self.instrument_failure_count
            != self.rollout_count
        ):
            raise ValueError("Bridge instrument-valid accounting is incomplete")
        if self.instrument_valid_rollout_count != self.model_outcome_count:
            raise ValueError("Bridge capability denominator includes a non-model outcome")
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
    condition_lineage_id: str = Field(min_length=1)
    compiled_task_condition_id: str = Field(min_length=1)
    state_mapping_contract_id: str = Field(min_length=1)
    projection_id: str = Field(min_length=1)
    ladder_id: str = Field(min_length=1)
    scaffold_admission_id: str = Field(min_length=1)
    joint_admission_id: str = Field(min_length=1)
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
                    _confirmed_task_condition(item, task_id)
                    for item in self.observations
                    for task_id in item.task_ids
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
        "inference": BridgeHierarchicalInferenceContract(),
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
    case_results: Iterable[AtomicAuditCaseResult],
    auditor_id: str,
    auditor_version: str,
) -> BridgeStaticConstructAudit:
    if len(task_admission_ids) != 8:
        raise ValueError("Bridge static construct audit requires exactly eight tasks")
    rows = tuple(sorted(case_results, key=lambda item: (item.subject_id, item.check_id)))
    admission_to_task = {
        admission_id: task_id for task_id, admission_id in task_admission_ids.items()
    }
    normalized_checks: dict[str, dict[str, bool]] = {
        task_id: {} for task_id in sorted(task_admission_ids)
    }
    for item in rows:
        task_id = admission_to_task.get(item.subject_id)
        if task_id is not None:
            normalized_checks[task_id][item.check_id] = item.check_passed
    passed = sum(all(checks.values()) for checks in normalized_checks.values())
    values = {
        "contract_id": contract_id,
        "mechanism_id": mechanism_id,
        "task_admission_ids": dict(sorted(task_admission_ids.items())),
        "case_results": rows,
        "auditor_id": auditor_id,
        "auditor_version": auditor_version,
        "auditor_manifest_hash": canonical_hash(
            {"auditor_id": auditor_id, "auditor_version": auditor_version},
            prefix="bridge_static_construct_auditor_manifest:",
        ),
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


def make_bridge_rollout_observation(
    *,
    contract_id: str,
    phase_authorization_id: str,
    phase: BridgePhase,
    mechanism_id: BridgeMechanism,
    scaffold_level: ScaffoldLevel,
    replicate_index: int,
    condition_lineage: CompiledTaskConditionLineage,
    execution_manifest: BridgeExecutionManifest,
    provider_call_ids: tuple[str, ...],
    public_state_summary: CompiledPublicStateSummary | None,
    terminal_category: BridgeRolloutTerminal,
    independent_validity_passed: bool,
    quotient_state_id: str | None,
    decision_trace_hash: str | None,
    estimand_outcomes: tuple[BridgeEstimandOutcome, ...],
    raw_payload: Mapping[str, Any],
    raw_artifact_uri: str,
    host_interference_detected: bool = False,
    oracle_leakage_detected: bool = False,
    failure_reason: str | None = None,
) -> BridgeRolloutObservation:
    frozen_raw_payload = {
        **dict(raw_payload),
        "execution_manifest_id": execution_manifest.manifest_id,
        "provider_call_ids": list(provider_call_ids),
    }
    values = {
        "contract_id": contract_id,
        "phase_authorization_id": phase_authorization_id,
        "phase": phase,
        "mechanism_id": mechanism_id,
        "scaffold_level": scaffold_level,
        "scaffold_rank": SCAFFOLD_LEVELS.index(scaffold_level),
        "replicate_index": replicate_index,
        "condition_lineage": condition_lineage,
        "execution_manifest": execution_manifest,
        "provider_call_ids": provider_call_ids,
        "public_state_summary": public_state_summary,
        "terminal_category": terminal_category,
        "independent_validity_passed": independent_validity_passed,
        "quotient_state_id": quotient_state_id,
        "decision_trace_hash": decision_trace_hash,
        "estimand_outcomes": estimand_outcomes,
        "host_interference_detected": host_interference_detected,
        "oracle_leakage_detected": oracle_leakage_detected,
        "failure_reason": failure_reason,
        "raw_payload": frozen_raw_payload,
        "raw_payload_hash": canonical_hash(
            frozen_raw_payload,
            prefix="finance_bridge_raw_rollout:",
        ),
        "raw_artifact_uri": raw_artifact_uri,
        "raw_artifact_sha256": _sha256_payload(frozen_raw_payload),
        "schema_version": BRIDGE_ROLLOUT_OBSERVATION_VERSION,
    }
    provisional = BridgeRolloutObservation.model_construct(rollout_id="pending", **values)
    return BridgeRolloutObservation(
        rollout_id=bridge_rollout_observation_id(provisional),
        **values,
    )


def make_bridge_execution_manifest(
    *,
    contract_id: str,
    condition_lineage: CompiledTaskConditionLineage,
    model_id: str,
    model_config: Mapping[str, Any],
    provider_route: Mapping[str, Any],
    prompt_manifest: Mapping[str, Any],
    runtime_id: str,
    tool_manifest: Mapping[str, Any],
) -> BridgeExecutionManifest:
    frozen_model = {**dict(model_config), "model_id": model_id}
    frozen_provider = dict(provider_route)
    frozen_prompt = {
        **dict(prompt_manifest),
        "compiled_task_condition_id": condition_lineage.compiled_task_condition_id,
    }
    frozen_runtime = {
        "runtime_id": runtime_id,
        "runtime_projection_id": condition_lineage.runtime_projection_id,
        "runtime_authority_policy_id": condition_lineage.runtime_authority_policy_id,
    }
    frozen_tools = dict(tool_manifest)
    values = {
        "contract_id": contract_id,
        "model_id": model_id,
        "model_invocation_config": frozen_model,
        "model_config_hash": canonical_hash(
            frozen_model, prefix="finance_bridge_model_config:"
        ),
        "provider_route": frozen_provider,
        "provider_route_hash": canonical_hash(
            frozen_provider, prefix="finance_bridge_provider_route:"
        ),
        "prompt_manifest": frozen_prompt,
        "prompt_manifest_hash": canonical_hash(
            frozen_prompt, prefix="finance_bridge_prompt_manifest:"
        ),
        "runtime_id": runtime_id,
        "runtime_projection_id": condition_lineage.runtime_projection_id,
        "runtime_authority_policy_id": condition_lineage.runtime_authority_policy_id,
        "runtime_manifest": frozen_runtime,
        "runtime_manifest_hash": canonical_hash(
            frozen_runtime, prefix="finance_bridge_runtime_manifest:"
        ),
        "tool_manifest": frozen_tools,
        "tool_manifest_hash": canonical_hash(
            frozen_tools, prefix="finance_bridge_tool_manifest:"
        ),
        "schema_version": BRIDGE_EXECUTION_MANIFEST_VERSION,
    }
    provisional = BridgeExecutionManifest.model_construct(manifest_id="pending", **values)
    return BridgeExecutionManifest(
        manifest_id=bridge_execution_manifest_id(provisional),
        **values,
    )


def aggregate_bridge_cell_observation(
    *,
    contract_id: str,
    phase_authorization_id: str,
    phase: BridgePhase,
    mechanism_id: BridgeMechanism,
    scaffold_level: ScaffoldLevel,
    rollout_observations: Iterable[BridgeRolloutObservation],
) -> BridgeCellObservation:
    rollouts = tuple(
        sorted(
            rollout_observations,
            key=lambda item: (item.task_id, item.replicate_index),
        )
    )
    if len(rollouts) != 48:
        raise ValueError("Bridge cell requires exactly 48 atomic rollouts")
    if any(
        item.contract_id != contract_id
        or item.phase_authorization_id != phase_authorization_id
        or item.phase != phase
        or item.mechanism_id != mechanism_id
        or item.scaffold_level != scaffold_level
        for item in rollouts
    ):
        raise ValueError("Bridge atomic rollouts cross cell identities")
    derived = _derive_bridge_cell_values(rollouts)
    values = {
        "contract_id": contract_id,
        "phase_authorization_id": phase_authorization_id,
        "phase": phase,
        "mechanism_id": mechanism_id,
        "scaffold_level": scaffold_level,
        "scaffold_rank": SCAFFOLD_LEVELS.index(scaffold_level),
        **derived,
        "rollout_observations": rollouts,
        "schema_version": BRIDGE_CELL_OBSERVATION_VERSION,
    }
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
        _confirmed_task_condition(item, task_id)
        for item in rows
        for task_id in item.task_ids
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


def bridge_execution_manifest_id(value: BridgeExecutionManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_bridge_execution_manifest:",
    )


def bridge_rollout_observation_id(value: BridgeRolloutObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"rollout_id"}),
        prefix="finance_compiler_assisted_bridge_rollout:",
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
) -> ConfirmedBridgeTaskCondition:
    lineage = next(
        rollout.condition_lineage
        for rollout in item.rollout_observations
        if rollout.task_id == task_id
    )
    values = {
        "task_id": task_id,
        "mechanism_id": item.mechanism_id,
        "scaffold_level": item.scaffold_level,
        "condition_lineage_id": lineage.lineage_id,
        "compiled_task_condition_id": lineage.compiled_task_condition_id,
        "state_mapping_contract_id": lineage.state_mapping_contract_id,
        "projection_id": lineage.projection_id,
        "ladder_id": lineage.ladder_id,
        "scaffold_admission_id": lineage.scaffold_admission_id,
        "joint_admission_id": lineage.joint_admission_id,
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


def _derive_bridge_cell_values(
    rollouts: tuple[BridgeRolloutObservation, ...],
) -> dict[str, Any]:
    if len(rollouts) != 48 or len({item.rollout_id for item in rollouts}) != 48:
        raise ValueError("Bridge cell atomic rollout identities are incomplete or duplicated")
    task_ids = tuple(sorted({item.task_id for item in rollouts}))
    if len(task_ids) != 8:
        raise ValueError("Bridge cell must contain exactly eight task identities")
    lineages: list[CompiledTaskConditionLineage] = []
    for task_id in task_ids:
        task_rows = tuple(item for item in rollouts if item.task_id == task_id)
        if tuple(item.replicate_index for item in task_rows) != tuple(range(6)):
            raise ValueError("Bridge task replicates are incomplete or unordered")
        task_lineages = {item.condition_lineage for item in task_rows}
        if len(task_lineages) != 1:
            raise ValueError("Bridge task replicates cross compiled conditions")
        lineages.append(next(iter(task_lineages)))
    model_rows = tuple(
        item
        for item in rollouts
        if item.terminal_category
        in {"model_valid_trajectory", "model_invalid_trajectory"}
    )
    runtime_failures = sum(item.terminal_category == "runtime_failure" for item in rollouts)
    instrument_failures = sum(
        item.terminal_category == "instrument_failure" for item in rollouts
    )
    estimands = tuple(
        make_bridge_estimand_observation(
            estimand_id=estimand_id,
            evaluation_count=len(
                evaluated := tuple(
                    outcome
                    for item in model_rows
                    for outcome in item.estimand_outcomes
                    if outcome.estimand_id == estimand_id and outcome.evaluated
                )
            ),
            success_count=sum(outcome.success is True for outcome in evaluated),
            fixed_policy_success_count=sum(
                outcome.fixed_policy_success is True for outcome in evaluated
            ),
        )
        for estimand_id in MECHANISM_ESTIMANDS[rollouts[0].mechanism_id]
    )
    observed_states = tuple(
        item.quotient_state_id for item in model_rows if item.quotient_state_id
    )
    state_counts = Counter(observed_states)
    state_total = sum(state_counts.values())
    state_entropy = (
        -sum(
            (count / state_total) * math.log(count / state_total)
            for count in state_counts.values()
        )
        if state_total
        else 0.0
    )
    tasks_with_multiple_states = sum(
        len(
            {
                item.quotient_state_id
                for item in model_rows
                if item.task_id == task_id and item.quotient_state_id
            }
        )
        >= 2
        for task_id in task_ids
    )
    return {
        "task_ids": task_ids,
        "compiled_task_condition_ids": tuple(
            item.compiled_task_condition_id for item in lineages
        ),
        "state_mapping_contract_ids": tuple(
            item.state_mapping_contract_id for item in lineages
        ),
        "condition_lineage_ids": tuple(item.lineage_id for item in lineages),
        "instrument_valid_rollout_count": len(model_rows),
        "model_outcome_count": len(model_rows),
        "valid_trajectory_count": sum(
            item.terminal_category == "model_valid_trajectory" for item in rollouts
        ),
        "estimand_observations": estimands,
        "preliminary_unique_state_count": len(state_counts),
        "tasks_with_multiple_observed_states_count": tasks_with_multiple_states,
        "state_entropy": state_entropy,
        "host_interference_count": sum(
            item.host_interference_detected for item in rollouts
        ),
        "oracle_leakage_count": sum(item.oracle_leakage_detected for item in rollouts),
        "runtime_failure_count": runtime_failures,
        "instrument_failure_count": instrument_failures,
    }


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(
                marker in normalized
                for marker in ("api_key", "authorization", "password", "secret", "token")
            ):
                return True
            if _contains_sensitive_key(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
