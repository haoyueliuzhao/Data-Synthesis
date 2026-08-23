from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_transport_recovery_postrun_audit as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
    build_capability_sensitive_frontier_population,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    core_task_semantic_signature,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    _harden_environment,
    _harden_record,
    _task_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    VERIFIER_QUALIFICATION_DIR,
    _make_compact_prompt_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    TargetMechanism,
    _base_draft,
    _TaskDraft,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exposure_clean_population import (  # noqa: E501
    ExposureCleanPopulationReceipt,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_builder import (
    _upgrade_task,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    PATH_STRATEGIES,
    TARGET_MECHANISMS,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (  # noqa: E501
    build_operation_closure_audit,
    build_operational_admission,
    compile_operational_witness,
    mechanism_necessity_and_catalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    _execute_observation,
    _runtime,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    _bind_verifier_v2,
    _load_and_replay_verifier_qualification,
    _task_replay_binding,
    _verifier_bound_environment,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    prospective_semantic_action_response_grammar as action_abi,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    ExactFinalResponseGrammar,
    render_exact_final_primary_prompt,
    render_exact_final_rescue_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    DecisionKind,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
    make_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseGrammar,
    independently_enumerate_visible_actions,
    parse_prompt_only_reference_payload,
    validate_candidate_space_completeness,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionProjection,
)
from trusted_synthesis.runtime.tools import AgentToolObservation

RUN_ID: Final = "finance_v26_129_fresh_role_kernel_compatibility_preflight_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_129_fresh_role_kernel_compatibility_preflight_v1_20260824"
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_role_kernel_compatibility_preflight.py"
)
SNAPSHOT_PATH: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v25_44_hardened_stopping_evidence_snapshot_v3_20260816/"
    "finance_stopping_evidence_snapshot.jsonl"
)
EXPOSURE_RECEIPT_PATH: Final = (
    "artifacts/vtdo_experiment/finance_v26_29_exposure_grounded_source_20260817/"
    "exposure_clean_receipt.json"
)
ACTION_GRAMMAR_PATH: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_118_semantic_action_rematerialization_v1_20260823/"
    "semantic_action_response_grammar.json"
)
FINAL_GRAMMAR_PATH: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_122_final_grammar_privacy_rematerialization_v1_20260823/"
    "exact_final_response_grammar.json"
)
PRIVACY_FIRST_RUNNER_CONTRACT_PATH: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_123_privacy_first_exact_final_runner_preflight_v1_20260823/"
    "runner_contract.json"
)
SOURCE_POPULATION_PATHS: Final = (
    "artifacts/vtdo_experiment/finance_v26_29_exposure_grounded_source_20260817/population.json",
    "artifacts/vtdo_experiment/finance_v26_36_no_api_joint_scaffold_20260817/"
    "population/confirmation_source.json",
    "artifacts/vtdo_experiment/finance_v26_40_no_api_joint_scaffold_20260817/"
    "population/confirmation_source.json",
    "artifacts/vtdo_experiment/finance_v26_42_no_api_joint_scaffold_20260817/"
    "population/confirmation_source.json",
)
SELECTED_POPULATION_PATHS: Final = tuple(
    f"artifacts/vtdo_experiment/finance_v26_{version}_no_api_joint_scaffold_20260817/"
    f"population/{name}.json"
    for version in (36, 40, 42)
    for name in ("development", "confirmation")
)
ADDITIONAL_ROLE_IDENTITY_PATHS: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v1_20260821/"
    "budget_feasible_role_task_packages.json",
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v1_20260821/"
    "operational_task_records.json",
    "artifacts/vtdo_experiment/"
    "finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/"
    "calibration_operational_task_records.json",
    "artifacts/vtdo_experiment/"
    "finance_v26_91_thinking_budget_calibration_preflight_v1_20260821/"
    "calibration_task_packages.json",
)
HISTORICAL_ROLE_IDENTITY_INPUT_PATHS: Final = (
    *SELECTED_POPULATION_PATHS,
    *ADDITIONAL_ROLE_IDENTITY_PATHS,
)
PREDECESSOR_OUTPUT_NAMES: Final = (
    "destructive_audit.json",
    "engineering_kernel_freeze.json",
    "full_endpoint_outcome_audit.json",
    "model_invalid_localization_audit.json",
    "prospective_transition_contract.json",
    "raw_lineage_reaudit.json",
    "report.json",
    "source_replay_audit.json",
    "transport_recovery_outcome_audit.json",
)
EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_transport_recovery_postrun_audit_report:"
    "e923f02843376424c783cb47a1e3f59f7704426f2b151f1432c65408e8c4731f"
)
EXPECTED_PREDECESSOR_SOURCE_REPLAY_ID: Final = (
    "finance_v26_transport_recovery_postrun_source_replay:"
    "80c28ec93ffa9a698a25c6a8b99053ce504e465fff66891cf225f862605ab797"
)
EXPECTED_KERNEL_FREEZE_ID: Final = (
    "finance_v26_engineering_kernel_freeze:"
    "eab0c2d085b78e77a487077931df58009380d279f74f93fc5aebc627bb523e77"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_transport_recovery_postrun_transition:"
    "adb995a0efd3a04313bd325f80cef2b612492b379f762aad9c88614cc394217a"
)
EXPECTED_PRIVACY_FIRST_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_privacy_first_runner_contract:"
    "a1d2c225906c57742340cf34c07e6d8643bbc4ef293bcf357cecd29b13221a66"
)
SOURCE_RUN_ID: Final = "finance_v26_129_fresh_role_kernel_binding_source_v1_20260823"
SOURCE_SAMPLING_SALT: Final = "finance-v26.129-fresh-role-kernel-binding-source-v1"
ROLE_SELECTION_SALT: Final = "finance-v26.129-fresh-role-selection-v1"
NEXT_STAGE: Final = "frozen_role_population_kernel_scalability_design_only"

Role = Literal["capability", "reachability"]
Tier = Literal["easy_control", "frontier", "hard_control"]
FreshnessChannel = Literal[
    "task_id",
    "source_task_id",
    "evidence_id",
    "evidence_version_id",
    "core_semantic_signature",
    "task_signature",
    "mechanism_instance_signature",
    "source_record_id",
]
FRESHNESS_CHANNELS: Final = (
    "task_id",
    "source_task_id",
    "evidence_id",
    "evidence_version_id",
    "core_semantic_signature",
    "task_signature",
    "mechanism_instance_signature",
    "source_record_id",
)
TIERS: Final = ("easy_control", "frontier", "hard_control")
ROLES: Final = ("capability", "reachability")
FIRST_GATE_MECHANISM: Final = "context_conditioned_action"
ROLE_MECHANISM_SOURCE_FAMILY: Final = {
    "context_conditioned_action": "finance.branching_operation_plan",
    "semantic_reconciliation": "finance.definition_reconciliation",
    "failure_recovery": "finance.recovery_guided_search",
    "state_dependent_stopping": "finance.stopping_decision_control",
}
PROMPT_CEILING_BYTES: Final = 60_000
COMPLETION_REQUEST_BOUND: Final = 16_384
PROVIDER_ACCOUNTING_MARGIN: Final = 1
ROLLOUT_BOUND: Final = 400_000
MINIMUM_HEADROOM: Final = 20_000
MAXIMUM_PRIMARY_REQUESTS: Final = 11
MAXIMUM_PROVIDER_CALLS_WITH_RECOVERY: Final = 12


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_128_transitive_binding",
        "v26_128_output",
        "historical_role_population_input",
        "source_snapshot_input",
        "v26_129_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_PREDECESSOR_SOURCE_REPLAY_ID
    predecessor_kernel_freeze_id: str = EXPECTED_KERNEL_FREEZE_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[3134] = 3134
    predecessor_output_file_count: Literal[9] = 9
    additional_historical_identity_file_count: Literal[9] = 9
    additional_source_snapshot_file_count: Literal[1] = 1
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[3154] = 3154
    replay_pass_count: Literal[3154] = 3154
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=3154, max_length=3154)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_fresh_role_source_replay.v1"] = (
        "finance_v26_fresh_role_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.129 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.129 source replay contains a hash mismatch")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_fresh_role_source_replay:"):
            raise ValueError("v26.129 source replay identity changed")
        return self


class FreshnessChannelAudit(FrozenModel):
    channel: FreshnessChannel
    prior_count: int = Field(ge=0)
    capability_count: int = Field(ge=1)
    reachability_count: int = Field(ge=1)
    prior_set_hash: str = Field(min_length=1)
    capability_set_hash: str = Field(min_length=1)
    reachability_set_hash: str = Field(min_length=1)
    prior_overlap_count: Literal[0] = 0
    cross_role_overlap_count: Literal[0] = 0


class HistoricalExposureExclusionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    exposure_receipt_id: str = Field(min_length=1)
    source_snapshot_sha256: str = Field(min_length=64, max_length=64)
    identity_file_count: int = Field(ge=1)
    identity_file_paths: tuple[str, ...] = Field(min_length=1)
    historical_source_task_count: int = Field(ge=1)
    mapped_historical_source_task_count: int = Field(ge=1)
    receipt_excluded_evidence_count: int = Field(ge=1)
    historical_selected_evidence_count: int = Field(ge=1)
    effective_excluded_evidence_count: int = Field(ge=1)
    effective_excluded_evidence_set_hash: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    source_frame_task_count: Literal[70] = 70
    source_frame_selected_evidence_count: int = Field(ge=1)
    source_frame_excluded_overlap_count: Literal[0] = 0
    source_selection_used_model_outcomes: Literal[False] = False
    source_selection_used_provider_payloads: Literal[False] = False
    source_selection_used_kernel_resource_values: Literal[False] = False
    historical_exclusions_applied_before_sampling: Literal[True] = True
    provider_exposed_task_lineage_included: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_historical_exposure_exclusion.v1"] = (
        "finance_v26_historical_exposure_exclusion.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> HistoricalExposureExclusionAudit:
        if self.identity_file_paths != tuple(sorted(set(self.identity_file_paths))):
            raise ValueError("v26.129 historical identity-file set changed")
        if self.identity_file_count != len(self.identity_file_paths):
            raise ValueError("v26.129 historical identity-file count changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_historical_exposure_exclusion:",
        ):
            raise ValueError("v26.129 historical exclusion identity changed")
        return self


class RoleSourceTaskBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    role: Role
    mechanism_id: TargetMechanism
    tier: Tier
    role_neutral_rank: Literal[0, 1]
    source_task_artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    core_semantic_signature: str = Field(min_length=1)
    task_signature: str = Field(min_length=1)
    mechanism_instance_signature: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    source_record_ids: tuple[str, ...] = Field(min_length=1)
    program_node_count: int = Field(ge=1)
    public_evidence_count: int = Field(ge=1)
    selected_before_kernel_load: Literal[True] = True
    model_outcomes_used_for_selection: Literal[False] = False
    kernel_resource_values_used_for_selection: Literal[False] = False

    @model_validator(mode="after")
    def validate_binding(self) -> RoleSourceTaskBinding:
        if (
            self.evidence_ids != tuple(sorted(set(self.evidence_ids)))
            or self.evidence_version_ids != tuple(sorted(set(self.evidence_version_ids)))
            or self.source_record_ids != tuple(sorted(set(self.source_record_ids)))
        ):
            raise ValueError("v26.129 role source binding sets changed")
        expected_rank = 0 if self.role == "capability" else 1
        if self.role_neutral_rank != expected_rank:
            raise ValueError("v26.129 role allocation changed after role-neutral ranking")
        if self.binding_id != _identity(
            self, "binding_id", "finance_v26_role_source_task_binding:"
        ):
            raise ValueError("v26.129 role source binding identity changed")
        return self


class FreshRoleSourcePopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    role: Role
    source_frame_population_id: str = Field(min_length=1)
    selection_salt: str = ROLE_SELECTION_SALT
    tasks: tuple[RoleSourceTaskBinding, ...] = Field(min_length=12, max_length=12)
    task_count: Literal[12] = 12
    tasks_per_mechanism: Literal[3] = 3
    easy_task_count: Literal[4] = 4
    frontier_task_count: Literal[4] = 4
    hard_task_count: Literal[4] = 4
    model_api_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_fresh_role_source_population.v1"] = (
        "finance_v26_fresh_role_source_population.v1"
    )

    @model_validator(mode="after")
    def validate_population(self) -> FreshRoleSourcePopulation:
        if any(item.role != self.role for item in self.tasks):
            raise ValueError("v26.129 role source Population mixes roles")
        if len({item.source_task_artifact_id for item in self.tasks}) != self.task_count:
            raise ValueError("v26.129 role source Population repeats a source task")
        mechanism_counts = Counter(item.mechanism_id for item in self.tasks)
        tier_counts = Counter(item.tier for item in self.tasks)
        if (
            set(mechanism_counts) != set(TARGET_MECHANISMS)
            or set(mechanism_counts.values()) != {self.tasks_per_mechanism}
            or tier_counts != Counter({"easy_control": 4, "frontier": 4, "hard_control": 4})
        ):
            raise ValueError("v26.129 role source Population balance changed")
        if self.population_id != _identity(
            self, "population_id", "finance_v26_fresh_role_source_population:"
        ):
            raise ValueError("v26.129 role source Population identity changed")
        return self


class RoleSourceSelectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    historical_exclusion_audit_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    capability_population_id: str = Field(min_length=1)
    reachability_population_id: str = Field(min_length=1)
    selection_salt: str = ROLE_SELECTION_SALT
    selected_task_count: Literal[24] = 24
    capability_task_count: Literal[12] = 12
    reachability_task_count: Literal[12] = 12
    freshness_channels: tuple[FreshnessChannelAudit, ...] = Field(min_length=8, max_length=8)
    source_populations_separate: Literal[True] = True
    role_assignments_frozen_before_kernel_load: Literal[True] = True
    task_depth_balanced_before_resource_audit: Literal[True] = True
    posthoc_task_deletion_or_substitution_allowed: Literal[False] = False
    model_outcomes_used_for_selection: Literal[False] = False
    provider_payloads_used_for_selection: Literal[False] = False
    kernel_resource_values_used_for_selection: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["fresh_role_source_populations_frozen"] = "fresh_role_source_populations_frozen"
    schema_version: Literal["finance_v26_role_source_selection_audit.v1"] = (
        "finance_v26_role_source_selection_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RoleSourceSelectionAudit:
        if self.capability_population_id == self.reachability_population_id:
            raise ValueError("v26.129 role Population identities overlap")
        if tuple(item.channel for item in self.freshness_channels) != FRESHNESS_CHANNELS:
            raise ValueError("v26.129 role freshness channels changed")
        if any(
            item.prior_overlap_count or item.cross_role_overlap_count
            for item in self.freshness_channels
        ):
            raise ValueError("v26.129 role freshness overlap changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_role_source_selection_audit:"):
            raise ValueError("v26.129 role source selection identity changed")
        return self


class CandidateCountRow(FrozenModel):
    candidate_count: int = Field(ge=1)
    state_count: int = Field(ge=1)


class KernelPathCompatibilityRow(FrozenModel):
    path_id: str = Field(min_length=1)
    engineering_kernel_freeze_id: str = EXPECTED_KERNEL_FREEZE_ID
    role_population_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    diagnostic_task_package_id: str = Field(min_length=1)
    diagnostic_environment_manifest_id: str = Field(min_length=1)
    compiler_witness_id: str = Field(min_length=1)
    compiler_trajectory_id: str = Field(min_length=1)
    role: Role
    mechanism_id: Literal["context_conditioned_action"] = FIRST_GATE_MECHANISM
    tier: Tier
    path_strategy_id: PathStrategy
    source_program_node_count: int = Field(ge=1)
    source_public_evidence_count: int = Field(ge=1)
    action_state_count: int = Field(ge=1)
    public_tool_call_count: int = Field(ge=1)
    stage_two_commit_count: int = Field(ge=1)
    maximum_candidate_count: int = Field(ge=1)
    maximum_candidate_list_utf8_bytes: int = Field(ge=1)
    action_primary_prompt_sha256s: tuple[str, ...] = Field(min_length=1)
    final_primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_rescue_prompt_sha256: str = Field(min_length=64, max_length=64)
    maximum_action_primary_prompt_utf8_bytes: int = Field(ge=1)
    maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(ge=1)
    maximum_semantic_recovery_prompt_utf8_bytes: int = Field(ge=1)
    final_primary_prompt_utf8_bytes: int = Field(ge=1)
    final_rescue_prompt_utf8_bytes: int = Field(ge=1)
    maximum_prompt_utf8_bytes: int = Field(ge=1)
    semantic_action_primary_request_count: int = Field(ge=1)
    final_primary_request_count: Literal[1] = 1
    primary_request_count: int = Field(ge=1)
    maximum_provider_calls_with_abi_and_semantic_recovery: int = Field(ge=1)
    maximum_provider_invocations_with_transport_replacement: int = Field(ge=1)
    exact_transport_replacement_upper_bound: Literal[1] = 1
    transport_replacement_reuses_exact_failed_request: Literal[True] = True
    failed_transport_usage_imputed: Literal[False] = False
    provider_billing_and_trajectory_resource_ledgers_separate: Literal[True] = True
    static_complete_path_upper_bound_tokens: int = Field(gt=0)
    static_rollout_headroom_tokens: int
    prompt_ceiling_passed: bool
    primary_request_limit_passed: bool
    provider_call_limit_passed: bool
    rollout_bound_passed: bool
    kernel_compatible: bool
    prompt_only_reference_control: Literal[True] = True
    candidate_completeness_passed: Literal[True] = True
    independent_candidate_enumeration_passed: Literal[True] = True
    program_closed: Literal[True] = True
    terminal_node_completed: Literal[True] = True
    terminal_verification_ready: Literal[True] = True
    final_commit_reached: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["kernel_compatible", "kernel_incompatible"]
    schema_version: Literal["finance_v26_kernel_path_compatibility.v1"] = (
        "finance_v26_kernel_path_compatibility.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> KernelPathCompatibilityRow:
        if (
            self.action_state_count != self.semantic_action_primary_request_count
            or self.stage_two_commit_count != self.action_state_count
            or self.primary_request_count
            != self.semantic_action_primary_request_count + self.final_primary_request_count
            or self.maximum_provider_calls_with_abi_and_semantic_recovery
            != self.primary_request_count + 2
            or self.maximum_provider_invocations_with_transport_replacement
            != self.maximum_provider_calls_with_abi_and_semantic_recovery + 1
        ):
            raise ValueError("v26.129 path request arithmetic changed")
        if self.static_rollout_headroom_tokens != (
            ROLLOUT_BOUND - self.static_complete_path_upper_bound_tokens
        ):
            raise ValueError("v26.129 path headroom arithmetic changed")
        prompt_pass = self.maximum_prompt_utf8_bytes <= PROMPT_CEILING_BYTES
        primary_pass = self.primary_request_count <= MAXIMUM_PRIMARY_REQUESTS
        provider_pass = (
            self.maximum_provider_calls_with_abi_and_semantic_recovery
            <= MAXIMUM_PROVIDER_CALLS_WITH_RECOVERY
        )
        rollout_pass = (
            self.static_complete_path_upper_bound_tokens < ROLLOUT_BOUND
            and self.static_rollout_headroom_tokens >= MINIMUM_HEADROOM
        )
        compatible = prompt_pass and primary_pass and provider_pass and rollout_pass
        if (
            self.prompt_ceiling_passed != prompt_pass
            or self.primary_request_limit_passed != primary_pass
            or self.provider_call_limit_passed != provider_pass
            or self.rollout_bound_passed != rollout_pass
            or self.kernel_compatible != compatible
            or self.status != ("kernel_compatible" if compatible else "kernel_incompatible")
        ):
            raise ValueError("v26.129 path compatibility classification changed")
        if self.path_id != _identity(self, "path_id", "finance_v26_kernel_path_compatibility:"):
            raise ValueError("v26.129 path compatibility identity changed")
        return self


class KernelCompatibilityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    engineering_kernel_freeze_id: str = EXPECTED_KERNEL_FREEZE_ID
    privacy_first_runner_contract_id: str = EXPECTED_PRIVACY_FIRST_RUNNER_CONTRACT_ID
    role_source_selection_audit_id: str = Field(min_length=1)
    capability_population_id: str = Field(min_length=1)
    reachability_population_id: str = Field(min_length=1)
    first_gate_mechanism: Literal["context_conditioned_action"] = FIRST_GATE_MECHANISM
    subsequent_mechanisms_not_evaluated_after_failure: tuple[
        Literal[
            "semantic_reconciliation",
            "failure_recovery",
            "state_dependent_stopping",
        ],
        ...,
    ] = (
        "semantic_reconciliation",
        "failure_recovery",
        "state_dependent_stopping",
    )
    diagnostic_source_task_count: Literal[6] = 6
    diagnostic_fixture_task_package_count: Literal[6] = 6
    future_role_task_package_count: Literal[0] = 0
    diagnostic_path_count: Literal[12] = 12
    capability_path_count: Literal[3] = 3
    reachability_path_count: Literal[9] = 9
    compatible_path_count: int = Field(ge=0)
    incompatible_path_count: int = Field(ge=1)
    prompt_ceiling_failure_count: int = Field(ge=0)
    primary_request_limit_failure_count: int = Field(ge=0)
    provider_call_limit_failure_count: int = Field(ge=0)
    rollout_bound_failure_count: int = Field(ge=0)
    maximum_prompt_utf8_bytes: int = Field(ge=1)
    maximum_primary_request_count: int = Field(ge=1)
    maximum_static_path_upper_bound_tokens: int = Field(gt=0)
    minimum_static_rollout_headroom_tokens: int
    candidate_distribution: tuple[CandidateCountRow, ...] = Field(min_length=1)
    paths: tuple[KernelPathCompatibilityRow, ...] = Field(min_length=12, max_length=12)
    population_frozen_before_kernel_audit: Literal[True] = True
    posthoc_task_deletion_count: Literal[0] = 0
    posthoc_task_substitution_count: Literal[0] = 0
    role_contract_count: Literal[0] = 0
    role_manifest_count: Literal[0] = 0
    role_job_count: Literal[0] = 0
    role_runner_count: Literal[0] = 0
    role_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["role_population_kernel_incompatible"] = "role_population_kernel_incompatible"
    schema_version: Literal["finance_v26_kernel_compatibility_audit.v1"] = (
        "finance_v26_kernel_compatibility_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> KernelCompatibilityAudit:
        rows = self.paths
        if len({item.path_id for item in rows}) != self.diagnostic_path_count:
            raise ValueError("v26.129 diagnostic Path identities changed")
        if (
            sum(item.role == "capability" for item in rows) != self.capability_path_count
            or sum(item.role == "reachability" for item in rows) != self.reachability_path_count
            or self.compatible_path_count != sum(item.kernel_compatible for item in rows)
            or self.incompatible_path_count != sum(not item.kernel_compatible for item in rows)
            or self.prompt_ceiling_failure_count
            != sum(not item.prompt_ceiling_passed for item in rows)
            or self.primary_request_limit_failure_count
            != sum(not item.primary_request_limit_passed for item in rows)
            or self.provider_call_limit_failure_count
            != sum(not item.provider_call_limit_passed for item in rows)
            or self.rollout_bound_failure_count
            != sum(not item.rollout_bound_passed for item in rows)
            or self.maximum_prompt_utf8_bytes
            != max(item.maximum_prompt_utf8_bytes for item in rows)
            or self.maximum_primary_request_count
            != max(item.primary_request_count for item in rows)
            or self.maximum_static_path_upper_bound_tokens
            != max(item.static_complete_path_upper_bound_tokens for item in rows)
            or self.minimum_static_rollout_headroom_tokens
            != min(item.static_rollout_headroom_tokens for item in rows)
        ):
            raise ValueError("v26.129 Kernel compatibility aggregate changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_kernel_compatibility_audit:"):
            raise ValueError("v26.129 Kernel compatibility identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    stage_two_provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[12] = 12
    rejection_count: Literal[12] = 12
    mutations: tuple[MutationResult, ...] = Field(min_length=12, max_length=12)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_role_kernel_destructive.v1"] = (
        "finance_v26_role_kernel_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.129 destructive mutation names changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_role_kernel_destructive:"):
            raise ValueError("v26.129 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    engineering_kernel_freeze_id: str = EXPECTED_KERNEL_FREEZE_ID
    role_source_selection_audit_id: str = Field(min_length=1)
    kernel_compatibility_audit_id: str = Field(min_length=1)
    status: Literal["role_population_kernel_incompatible"] = "role_population_kernel_incompatible"
    next_permitted_stage: str = NEXT_STAGE
    frozen_capability_and_reachability_populations_must_be_preserved: Literal[True] = True
    posthoc_task_deletion_or_substitution_authorized: Literal[False] = False
    role_task_package_contract_manifest_job_or_runner_materialization_authorized: Literal[False] = (
        False
    )
    provider_calls_authorized: Literal[False] = False
    capability_or_reachability_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    threshold_relaxation_authorized: Literal[False] = False
    redesign_may_use_model_outcomes_for_selection: Literal[False] = False
    schema_version: Literal["finance_v26_role_kernel_transition.v1"] = (
        "finance_v26_role_kernel_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_role_kernel_transition:"
        ):
            raise ValueError("v26.129 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RoleKernelCompatibilityPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    historical_exclusion_audit_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    capability_population_id: str = Field(min_length=1)
    reachability_population_id: str = Field(min_length=1)
    role_source_selection_audit_id: str = Field(min_length=1)
    kernel_compatibility_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    source_frame_task_count: Literal[70] = 70
    fresh_role_source_task_count: Literal[24] = 24
    diagnostic_path_count: Literal[12] = 12
    incompatible_path_count: int = Field(ge=1)
    prompt_ceiling_failure_count: int = Field(ge=0)
    request_limit_failure_count: int = Field(ge=0)
    rollout_bound_failure_count: int = Field(ge=0)
    role_task_package_count: Literal[0] = 0
    role_contract_count: Literal[0] = 0
    role_manifest_count: Literal[0] = 0
    role_job_count: Literal[0] = 0
    role_runner_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    production_contribution: Literal[0] = 0
    status: Literal["role_population_kernel_incompatible"] = "role_population_kernel_incompatible"
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_role_kernel_compatibility_preflight_report.v1"] = (
        "finance_v26_role_kernel_compatibility_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RoleKernelCompatibilityPreflightReport:
        if self.capability_population_id == self.reachability_population_id:
            raise ValueError("v26.129 report merges role Populations")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_role_kernel_compatibility_preflight_report:",
        ):
            raise ValueError("v26.129 report identity changed")
        return self


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"immutable v26.129 artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        candidate = root / relative_path
        if candidate.is_file() and _sha256(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.129 cannot replay bound file: {relative_path}")


def build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_dir: Path,
) -> SourceReplayAudit:
    source = predecessor.AuditSourceReplay.model_validate_json(
        (predecessor_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    report = predecessor.PostrunAuditReport.model_validate_json(
        (predecessor_dir / "report.json").read_text(encoding="utf-8")
    )
    kernel = predecessor.EngineeringKernelFreeze.model_validate_json(
        (predecessor_dir / "engineering_kernel_freeze.json").read_text(encoding="utf-8")
    )
    transition = predecessor.ProspectiveTransitionContract.model_validate_json(
        (predecessor_dir / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )
    if (
        source.audit_id != EXPECTED_PREDECESSOR_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or report.source_replay_audit_id != source.audit_id
        or kernel.freeze_id != EXPECTED_KERNEL_FREEZE_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.engineering_kernel_freeze_id != kernel.freeze_id
    ):
        raise ValueError("v26.129 predecessor identity chain changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_128_transitive_binding",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    if tuple(sorted(path.name for path in predecessor_dir.iterdir() if path.is_file())) != (
        PREDECESSOR_OUTPUT_NAMES
    ):
        raise ValueError("v26.129 predecessor output file set changed")
    for name in PREDECESSOR_OUTPUT_NAMES:
        path = predecessor_dir / name
        relative = str(Path(PREDECESSOR_DIR) / name)
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_128_output",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    added = 0
    for relative in HISTORICAL_ROLE_IDENTITY_INPUT_PATHS:
        if relative in entries:
            continue
        path = package_root / relative
        if not path.is_file():
            raise ValueError(f"v26.129 historical role Population is missing: {relative}")
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="historical_role_population_input",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
        added += 1
    if added != 9:
        raise ValueError("v26.129 additional historical identity denominator changed")
    if SNAPSHOT_PATH in entries:
        raise ValueError("v26.129 source Snapshot unexpectedly entered predecessor replay")
    snapshot_path = package_root / SNAPSHOT_PATH
    snapshot_digest = _sha256(snapshot_path)
    entries[SNAPSHOT_PATH] = SourceReplayEntry(
        relative_path=SNAPSHOT_PATH,
        source_kind="source_snapshot_input",
        expected_sha256=snapshot_digest,
        observed_sha256=snapshot_digest,
        byte_count=snapshot_path.stat().st_size,
    )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    digest = _sha256(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_129_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=implementation_path.stat().st_size,
    )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_role_source_replay:",
        ),
        **values,
    )


def _strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, Mapping):
        return set().union(*(_strings(item) for item in value.values())) if value else set()
    if isinstance(value, (list, tuple)):
        return set().union(*(_strings(item) for item in value)) if value else set()
    return set()


def _collect_identifier_values(value: Any) -> dict[str, set[str]]:
    output: dict[str, set[str]] = {channel: set() for channel in FRESHNESS_CHANNELS}
    aliases: dict[str, FreshnessChannel] = {
        "task_id": "task_id",
        "source_task_id": "source_task_id",
        "source_task_artifact_id": "source_task_id",
        "source_task_artifact_ids": "source_task_id",
        "evidence_id": "evidence_id",
        "evidence_ids": "evidence_id",
        "evidence_version_id": "evidence_version_id",
        "evidence_version_ids": "evidence_version_id",
        "core_semantic_signature": "core_semantic_signature",
        "source_task_semantic_signature": "core_semantic_signature",
        "task_signature": "task_signature",
        "source_task_hash": "task_signature",
        "task_hash": "task_signature",
        "mechanism_instance_signature": "mechanism_instance_signature",
        "source_record_id": "source_record_id",
        "source_record_ids": "source_record_id",
    }

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                channel = aliases.get(str(key))
                if channel is not None:
                    output[channel].update(_strings(child))
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return output


def _merge_channels(
    *groups: Mapping[str, set[str]],
) -> dict[str, set[str]]:
    return {
        channel: set().union(*(group.get(channel, set()) for group in groups))
        for channel in FRESHNESS_CHANNELS
    }


def _mechanism_for_task(task: CapabilitySensitiveTaskArtifact) -> str:
    matches = tuple(
        mechanism
        for mechanism, family in ROLE_MECHANISM_SOURCE_FAMILY.items()
        if task.family == family
    )
    if len(matches) == 1:
        return str(matches[0])
    if matches:
        raise ValueError("v26.129 source task maps to multiple role mechanisms")
    return f"historical_non_role_family:{task.family}"


def _source_task_channels(
    tasks: Sequence[CapabilitySensitiveTaskArtifact],
) -> dict[str, set[str]]:
    output: dict[str, set[str]] = {channel: set() for channel in FRESHNESS_CHANNELS}
    for task in tasks:
        mechanism = _mechanism_for_task(task)
        core = core_task_semantic_signature(task)
        output["task_id"].add(task.task.task_id)
        output["source_task_id"].add(task.artifact_id)
        output["core_semantic_signature"].add(core)
        output["task_signature"].add(task.task.task_hash)
        output["mechanism_instance_signature"].add(
            canonical_hash(
                {
                    "mechanism_id": mechanism,
                    "task_family": task.family,
                    "difficulty_tier": task.tier.value,
                    "core_semantic_signature": core,
                    "structure": task.structure.model_dump(mode="json"),
                },
                prefix="finance_v26_mechanism_instance:",
            )
        )
        for evidence in task.public_corpus.evidence:
            output["evidence_id"].add(evidence.evidence_id)
            output["evidence_version_id"].add(evidence.evidence_version_id)
            output["source_record_id"].add(evidence.provenance.source_record_id)
    return output


def _load_json_or_jsonl(path: Path) -> Any:
    if path.suffix == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return json.loads(path.read_text(encoding="utf-8"))


def _historical_identity_paths(source: SourceReplayAudit) -> tuple[str, ...]:
    replay_paths = {item.relative_path for item in source.entries}
    selected = set(SELECTED_POPULATION_PATHS)
    for relative in replay_paths:
        name = Path(relative).name.casefold()
        if (
            relative.endswith(".json")
            and "task" in name
            and ("record" in name or "package" in name)
        ):
            selected.add(relative)
    missing = selected - replay_paths
    if missing:
        raise ValueError(f"v26.129 historical identity files are unbound: {sorted(missing)}")
    return tuple(sorted(selected))


class _HistoricalInputs:
    def __init__(
        self,
        *,
        prior_channels: dict[str, set[str]],
        effective_excluded_evidence_ids: tuple[str, ...],
        identity_paths: tuple[str, ...],
        historical_source_task_count: int,
        mapped_historical_source_task_count: int,
        historical_selected_evidence_count: int,
        receipt: ExposureCleanPopulationReceipt,
    ) -> None:
        self.prior_channels = prior_channels
        self.effective_excluded_evidence_ids = effective_excluded_evidence_ids
        self.identity_paths = identity_paths
        self.historical_source_task_count = historical_source_task_count
        self.mapped_historical_source_task_count = mapped_historical_source_task_count
        self.historical_selected_evidence_count = historical_selected_evidence_count
        self.receipt = receipt


def _build_historical_inputs(
    *,
    source: SourceReplayAudit,
    package_root: Path,
    implementation_root: Path,
) -> _HistoricalInputs:
    path_by_relative = {
        item.relative_path: _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        for item in source.entries
    }
    identity_paths = _historical_identity_paths(source)
    direct: dict[str, set[str]] = {channel: set() for channel in FRESHNESS_CHANNELS}
    for relative in identity_paths:
        direct = _merge_channels(
            direct,
            _collect_identifier_values(_load_json_or_jsonl(path_by_relative[relative])),
        )
    old_tasks: dict[str, CapabilitySensitiveTaskArtifact] = {}
    for relative in SOURCE_POPULATION_PATHS:
        path = path_by_relative.get(relative)
        if path is None:
            raise ValueError(f"v26.129 source Population is unbound: {relative}")
        population = CapabilitySensitiveFrontierPopulation.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        for task in population.tasks:
            old_tasks.setdefault(task.artifact_id, task)
    historical_source_ids = set(direct["source_task_id"])
    mapped = tuple(
        old_tasks[source_id]
        for source_id in sorted(historical_source_ids)
        if source_id in old_tasks
    )
    prior = _merge_channels(direct, _source_task_channels(mapped))
    receipt_path = path_by_relative.get(EXPOSURE_RECEIPT_PATH)
    snapshot_path = path_by_relative.get(SNAPSHOT_PATH)
    if receipt_path is None or snapshot_path is None:
        raise ValueError("v26.129 exposure receipt or source Snapshot is unbound")
    receipt = ExposureCleanPopulationReceipt.model_validate_json(
        receipt_path.read_text(encoding="utf-8")
    )
    if Path(
        receipt.source_artifacts_path
    ).resolve() != snapshot_path.resolve() or receipt.source_artifacts_sha256 != _sha256(
        snapshot_path
    ):
        raise ValueError("v26.129 source Snapshot differs from its exposure receipt")
    historical_selected_evidence_count = len(prior["evidence_id"])
    effective = tuple(sorted(set(receipt.excluded_evidence_ids) | prior["evidence_id"]))
    prior["evidence_id"].update(receipt.excluded_evidence_ids)
    return _HistoricalInputs(
        prior_channels=prior,
        effective_excluded_evidence_ids=effective,
        identity_paths=identity_paths,
        historical_source_task_count=len(historical_source_ids),
        mapped_historical_source_task_count=len(mapped),
        historical_selected_evidence_count=historical_selected_evidence_count,
        receipt=receipt,
    )


def _source_rank(
    task: CapabilitySensitiveTaskArtifact,
    *,
    mechanism: TargetMechanism,
    tier: Tier,
) -> str:
    return canonical_hash(
        {
            "salt": ROLE_SELECTION_SALT,
            "mechanism": mechanism,
            "tier": tier,
            "source_task_artifact_id": task.artifact_id,
        },
        prefix="finance_v26_fresh_role_source_rank:",
    )


def _task_binding(
    task: CapabilitySensitiveTaskArtifact,
    *,
    role: Role,
    mechanism: TargetMechanism,
    tier: Tier,
    role_neutral_rank: Literal[0, 1],
) -> RoleSourceTaskBinding:
    channels = _source_task_channels((task,))
    values = {
        "role": role,
        "mechanism_id": mechanism,
        "tier": tier,
        "role_neutral_rank": role_neutral_rank,
        "source_task_artifact_id": task.artifact_id,
        "task_id": task.task.task_id,
        "core_semantic_signature": next(iter(channels["core_semantic_signature"])),
        "task_signature": task.task.task_hash,
        "mechanism_instance_signature": next(iter(channels["mechanism_instance_signature"])),
        "evidence_ids": tuple(sorted(channels["evidence_id"])),
        "evidence_version_ids": tuple(sorted(channels["evidence_version_id"])),
        "source_record_ids": tuple(sorted(channels["source_record_id"])),
        "program_node_count": len(task.task.oracle.task_program.nodes),
        "public_evidence_count": len(task.public_corpus.evidence),
    }
    provisional = RoleSourceTaskBinding.model_construct(binding_id="pending", **values)
    return RoleSourceTaskBinding(
        binding_id=_identity(
            provisional,
            "binding_id",
            "finance_v26_role_source_task_binding:",
        ),
        **values,
    )


def _freeze_role_populations(
    *,
    frame: CapabilitySensitiveFrontierPopulation,
    prior_channels: Mapping[str, set[str]],
    source_replay_audit_id: str,
    historical_exclusion_audit_id: str,
) -> tuple[
    FreshRoleSourcePopulation,
    FreshRoleSourcePopulation,
    RoleSourceSelectionAudit,
    dict[str, CapabilitySensitiveTaskArtifact],
]:
    selected: dict[Role, list[CapabilitySensitiveTaskArtifact]] = {
        "capability": [],
        "reachability": [],
    }
    bindings: dict[Role, list[RoleSourceTaskBinding]] = {
        "capability": [],
        "reachability": [],
    }
    for mechanism in TARGET_MECHANISMS:
        family = ROLE_MECHANISM_SOURCE_FAMILY[mechanism]
        for raw_tier in TIERS:
            tier = cast(Tier, raw_tier)
            candidates = sorted(
                (task for task in frame.tasks if task.family == family and task.tier.value == tier),
                key=lambda task: _source_rank(task, mechanism=mechanism, tier=tier),
            )
            if len(candidates) < 2:
                raise ValueError("v26.129 source frame lacks a frozen role pair")
            for rank, role in enumerate(ROLES):
                typed_role = cast(Role, role)
                task = candidates[rank]
                selected[typed_role].append(task)
                bindings[typed_role].append(
                    _task_binding(
                        task,
                        role=typed_role,
                        mechanism=mechanism,
                        tier=tier,
                        role_neutral_rank=cast(Literal[0, 1], rank),
                    )
                )
    populations: dict[Role, FreshRoleSourcePopulation] = {}
    for role in ROLES:
        typed_role = cast(Role, role)
        values = {
            "role": typed_role,
            "source_frame_population_id": frame.population_id,
            "tasks": tuple(sorted(bindings[typed_role], key=lambda item: item.binding_id)),
        }
        provisional = FreshRoleSourcePopulation.model_construct(population_id="pending", **values)
        populations[typed_role] = FreshRoleSourcePopulation(
            population_id=_identity(
                provisional,
                "population_id",
                "finance_v26_fresh_role_source_population:",
            ),
            **values,
        )
    selected_channels = {role: _source_task_channels(tuple(selected[role])) for role in ROLES}
    channel_rows = []
    for raw_channel in FRESHNESS_CHANNELS:
        channel = cast(FreshnessChannel, raw_channel)
        prior = set(prior_channels[channel])
        capability = set(selected_channels["capability"][channel])
        reachability = set(selected_channels["reachability"][channel])
        if prior & (capability | reachability):
            raise ValueError(f"v26.129 selected role channel overlaps history: {channel}")
        if capability & reachability:
            raise ValueError(f"v26.129 Capability and Reachability overlap: {channel}")
        channel_rows.append(
            FreshnessChannelAudit(
                channel=channel,
                prior_count=len(prior),
                capability_count=len(capability),
                reachability_count=len(reachability),
                prior_set_hash=canonical_hash(
                    tuple(sorted(prior)), prefix=f"finance_v26_role_prior_{channel}:"
                ),
                capability_set_hash=canonical_hash(
                    tuple(sorted(capability)),
                    prefix=f"finance_v26_role_capability_{channel}:",
                ),
                reachability_set_hash=canonical_hash(
                    tuple(sorted(reachability)),
                    prefix=f"finance_v26_role_reachability_{channel}:",
                ),
            )
        )
    selection_values = {
        "source_replay_audit_id": source_replay_audit_id,
        "historical_exclusion_audit_id": historical_exclusion_audit_id,
        "source_frame_population_id": frame.population_id,
        "capability_population_id": populations["capability"].population_id,
        "reachability_population_id": populations["reachability"].population_id,
        "freshness_channels": tuple(channel_rows),
    }
    provisional_selection = RoleSourceSelectionAudit.model_construct(
        audit_id="pending", **selection_values
    )
    selection_audit = RoleSourceSelectionAudit(
        audit_id=_identity(
            provisional_selection,
            "audit_id",
            "finance_v26_role_source_selection_audit:",
        ),
        **selection_values,
    )
    by_id = {task.artifact_id: task for role in ROLES for task in selected[cast(Role, role)]}
    return (
        populations["capability"],
        populations["reachability"],
        selection_audit,
        by_id,
    )


def _make_historical_exclusion_audit(
    *,
    source: SourceReplayAudit,
    historical: _HistoricalInputs,
    frame: CapabilitySensitiveFrontierPopulation,
    snapshot_path: Path,
) -> HistoricalExposureExclusionAudit:
    selected_evidence = {
        item.evidence_id for task in frame.tasks for item in task.public_corpus.evidence
    }
    excluded = set(historical.effective_excluded_evidence_ids)
    if selected_evidence & excluded:
        raise ValueError("v26.129 source frame overlaps its frozen exclusion set")
    values = {
        "source_replay_audit_id": source.audit_id,
        "exposure_receipt_id": historical.receipt.receipt_id,
        "source_snapshot_sha256": _sha256(snapshot_path),
        "identity_file_count": len(historical.identity_paths),
        "identity_file_paths": historical.identity_paths,
        "historical_source_task_count": historical.historical_source_task_count,
        "mapped_historical_source_task_count": (historical.mapped_historical_source_task_count),
        "receipt_excluded_evidence_count": len(historical.receipt.excluded_evidence_ids),
        "historical_selected_evidence_count": (historical.historical_selected_evidence_count),
        "effective_excluded_evidence_count": len(excluded),
        "effective_excluded_evidence_set_hash": canonical_hash(
            tuple(sorted(excluded)),
            prefix="finance_v26_effective_role_evidence_exclusion:",
        ),
        "source_frame_population_id": frame.population_id,
        "source_frame_selected_evidence_count": len(selected_evidence),
    }
    provisional = HistoricalExposureExclusionAudit.model_construct(audit_id="pending", **values)
    return HistoricalExposureExclusionAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_historical_exposure_exclusion:",
        ),
        **values,
    )


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + 256 + COMPLETION_REQUEST_BOUND + PROVIDER_ACCOUNTING_MARGIN


def _measurement_action_prompt(
    *,
    phase: Literal["primary", "abi_rescue", "semantic_recovery"],
    instruction: str,
    state: SemanticActionState,
    public_path_condition: str | None,
    presentation_salt: str,
    typed_failure: Mapping[str, Any] | None,
    grammar: SemanticActionResponseGrammar,
) -> str:
    validate_candidate_space_completeness(state)
    candidates = action_abi._presentation_order(  # noqa: SLF001
        state.action_candidates, presentation_salt
    )
    prompt_protocol = {
        "primary": action_abi.PRIMARY_PROMPT_VERSION,
        "abi_rescue": action_abi.ABI_RESCUE_PROMPT_VERSION,
        "semantic_recovery": action_abi.SEMANTIC_RECOVERY_PROMPT_VERSION,
    }[phase]
    payload = {
        "prompt_protocol": prompt_protocol,
        "semantic_action_protocol": action_abi.SEMANTIC_ACTION_PROTOCOL_VERSION,
        "instruction": instruction,
        "public_path_condition": public_path_condition,
        "public_state_without_candidate_order": action_abi._state_projection(  # noqa: SLF001
            state
        ),
        "visible_action_candidates": [item.model_dump(mode="json") for item in candidates],
        "candidate_presentation": {
            "order_is_semantically_neutral": True,
            "presentation_salt_sha256": hashlib.sha256(
                presentation_salt.encode("utf-8")
            ).hexdigest(),
        },
        "typed_failure": dict(typed_failure) if typed_failure is not None else None,
        "response_grammar": action_abi._model_visible_grammar(  # noqa: SLF001
            grammar
        ),
        "previous_response_content_reused": False,
        "private_reasoning_reused": False,
    }
    prefix = {
        "primary": "Select one visible action and return exactly one four-field JSON object.",
        "abi_rescue": (
            "Correct only the response ABI and return exactly one four-field JSON object."
        ),
        "semantic_recovery": (
            "Use the public rejection and select one visible action as a four-field JSON object."
        ),
    }[phase]
    return (
        prefix
        + "\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _assert_exact_kernel_prompt_gate(
    measured: str,
    *,
    phase: Literal["primary", "abi_rescue", "semantic_recovery"],
    instruction: str,
    state: SemanticActionState,
    public_path_condition: str | None,
    presentation_salt: str,
    typed_failure: Mapping[str, Any] | None,
    grammar: SemanticActionResponseGrammar,
) -> None:
    try:
        official = action_abi._render(  # noqa: SLF001
            phase=phase,
            instruction=instruction,
            state=state,
            public_path_condition=public_path_condition,
            presentation_salt=presentation_salt,
            typed_failure=typed_failure,
            grammar=grammar,
        )
    except ValueError as exc:
        if (
            len(measured.encode("utf-8")) <= PROMPT_CEILING_BYTES
            or str(exc) != "semantic action response Prompt exceeds its frozen byte ceiling"
        ):
            raise
    else:
        if official != measured or len(measured.encode("utf-8")) > PROMPT_CEILING_BYTES:
            raise ValueError("v26.129 measurement Prompt differs from the frozen renderer")


def _other_decision_kind(value: str) -> str:
    return next(
        item
        for item in (
            "acquire_public_input",
            "execute_public_operation",
            "verify_terminal_operation",
            "emit_final_answer",
        )
        if item != value
    )


def _context_draft(
    task: CapabilitySensitiveTaskArtifact,
    *,
    role: Role,
) -> _TaskDraft:
    intended = "capability_measurement" if role == "capability" else "vtdo_multistate_candidate"
    return _base_draft(
        task,
        mechanism_id="context_conditioned_action",
        intended_use=intended,
    )


def _path_condition(role: Role, strategy: PathStrategy) -> str | None:
    return None if role == "capability" else strategy


def _build_context_kernel_compatibility(
    *,
    package_root: Path,
    capability: FreshRoleSourcePopulation,
    reachability: FreshRoleSourcePopulation,
    selection: RoleSourceSelectionAudit,
    selected_tasks: Mapping[str, CapabilitySensitiveTaskArtifact],
    kernel: predecessor.EngineeringKernelFreeze,
    runner_contract: privacy_runner.PrivacyFirstRunnerContract,
    action_grammar: SemanticActionResponseGrammar,
    final_grammar: ExactFinalResponseGrammar,
) -> KernelCompatibilityAudit:
    if (
        kernel.freeze_id != EXPECTED_KERNEL_FREEZE_ID
        or kernel.exact_request_completion_bound_tokens != COMPLETION_REQUEST_BOUND
        or kernel.rollout_upper_bound_tokens != ROLLOUT_BOUND
        or kernel.maximum_abi_rescue_calls != 1
        or kernel.maximum_semantic_recovery_calls != 1
        or kernel.exact_transport_failure_replacement_upper_bound != 1
        or kernel.semantic_action_response_grammar_id != action_grammar.grammar_id
        or kernel.exact_final_response_grammar_id != final_grammar.grammar_id
        or runner_contract.contract_id != EXPECTED_PRIVACY_FIRST_RUNNER_CONTRACT_ID
        or runner_contract.exact_request_completion_bound_tokens != COMPLETION_REQUEST_BOUND
        or runner_contract.provider_accounting_margin_tokens != PROVIDER_ACCOUNTING_MARGIN
        or runner_contract.rollout_upper_bound_tokens != ROLLOUT_BOUND
        or runner_contract.maximum_primary_stage_one_requests != MAXIMUM_PRIMARY_REQUESTS
        or runner_contract.maximum_stage_one_provider_calls != MAXIMUM_PROVIDER_CALLS_WITH_RECOVERY
        or runner_contract.maximum_abi_rescue_calls != 1
        or runner_contract.maximum_semantic_recovery_calls != 1
    ):
        raise ValueError("v26.129 frozen engineering Kernel changed")
    qualification, replay_contract = _load_and_replay_verifier_qualification(
        package_root / VERIFIER_QUALIFICATION_DIR,
        package_root,
    )
    qualification_sha = _sha256(package_root / VERIFIER_QUALIFICATION_DIR / "report.json")
    rows: list[KernelPathCompatibilityRow] = []
    candidate_counts: Counter[int] = Counter()
    populations = (capability, reachability)
    for population in populations:
        context_bindings = sorted(
            (item for item in population.tasks if item.mechanism_id == FIRST_GATE_MECHANISM),
            key=lambda item: TIERS.index(item.tier),
        )
        if len(context_bindings) != 3:
            raise ValueError("v26.129 Context role source denominator changed")
        for binding in context_bindings:
            task = selected_tasks[binding.source_task_artifact_id]
            draft = _context_draft(task, role=population.role)
            source_record, source_environment = _upgrade_task(draft)
            authority_environment = _harden_environment(source_environment)
            environment = _verifier_bound_environment(authority_environment)
            authority_record = _harden_record(source_record, environment)
            replay_binding = _task_replay_binding(
                authority_record,
                environment,
                qualification,
                qualification_sha,
                replay_contract,
            )
            record = _bind_verifier_v2(authority_record, replay_binding)
            strategies: tuple[PathStrategy, ...] = (
                ("structured_direct",) if population.role == "capability" else PATH_STRATEGIES
            )
            witnesses = []
            histories = []
            for strategy in strategies:
                witness, history = compile_operational_witness(
                    record, environment, strategy=strategy
                )
                witnesses.append(witness)
                histories.append(history)
            necessity, _, catalog = mechanism_necessity_and_catalog(record, witnesses)
            closure = build_operation_closure_audit(
                record, witnesses, histories, necessity, catalog
            )
            build_operational_admission(record, witnesses[0], necessity, catalog, closure)
            _task_audit(
                record,
                environment,
                witnesses[0],
                histories[0],
                necessity,
                closure,
            )
            prompt_contract = _make_compact_prompt_contract(
                role=population.role,
                record=record,
                environment=environment,
            )
            for strategy, witness, history in zip(strategies, witnesses, histories, strict=True):
                condition = _path_condition(population.role, strategy)
                runtime = _runtime(record, environment)
                observations: list[AgentToolObservation] = []
                primary_prompts: list[str] = []
                abi_prompts: list[str] = []
                recovery_prompts: list[str] = []
                maximum_candidate_list_bytes = 0
                maximum_candidate_count = 0
                for logical_index in range(64):
                    state = build_semantic_action_state(
                        record.task_package.task.public,
                        environment,
                        tuple(observations),
                    )
                    validate_candidate_space_completeness(state)
                    if independently_enumerate_visible_actions(state) != state.action_candidates:
                        raise ValueError("v26.129 independent Candidate enumeration changed")
                    candidate_counts[len(state.action_candidates)] += 1
                    maximum_candidate_count = max(
                        maximum_candidate_count, len(state.action_candidates)
                    )
                    salt = canonical_hash(
                        {
                            "selection_audit_id": selection.audit_id,
                            "role_population_id": population.population_id,
                            "source_task_artifact_id": task.artifact_id,
                            "path_strategy_id": strategy,
                            "state_id": state.state_id,
                            "logical_index": logical_index,
                        },
                        prefix="finance_v26_role_candidate_presentation:",
                    )
                    primary = _measurement_action_prompt(
                        phase="primary",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=None,
                        grammar=action_grammar,
                    )
                    _assert_exact_kernel_prompt_gate(
                        primary,
                        phase="primary",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=None,
                        grammar=action_grammar,
                    )
                    maximum_candidate_list_bytes = max(
                        maximum_candidate_list_bytes,
                        action_abi.candidate_prompt_utf8_bytes(primary),
                    )
                    proposal = parse_prompt_only_reference_payload(primary)
                    result = evaluate_canonical_action_proposal(
                        state,
                        proposal,
                        call_index=len(observations) + 1,
                    )
                    if result.commit is None or result.rejection is not None:
                        raise ValueError("v26.129 Prompt-only reference proposal was rejected")
                    primary_prompts.append(primary)
                    abi_failure = {
                        "family": "response_serialization_failure",
                        "subtype": "canonical_action_not_exact_four_field_grammar",
                    }
                    abi_prompt = _measurement_action_prompt(
                        phase="abi_rescue",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=abi_failure,
                        grammar=action_grammar,
                    )
                    _assert_exact_kernel_prompt_gate(
                        abi_prompt,
                        phase="abi_rescue",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=abi_failure,
                        grammar=action_grammar,
                    )
                    abi_prompts.append(abi_prompt)
                    invalid = make_canonical_action_proposal(
                        state_id=state.state_id,
                        action_id=proposal.action_id,
                        decision_kind=cast(
                            DecisionKind,
                            _other_decision_kind(proposal.decision_kind),
                        ),
                    )
                    rejection = evaluate_canonical_action_proposal(
                        state,
                        invalid,
                        call_index=len(observations) + 1,
                    ).rejection
                    if rejection is None:
                        raise ValueError("v26.129 semantic rejection control was accepted")
                    recovery_state = build_semantic_action_state(
                        record.task_package.task.public,
                        environment,
                        tuple(observations),
                        semantic_rejections=(rejection,),
                    )
                    recovery_salt = f"{salt}|semantic_recovery"
                    recovery_failure = {
                        "family": "semantic_action_rejection",
                        "subtype": rejection.error_category,
                        "rejection_id": rejection.rejection_id,
                    }
                    recovery_prompt = _measurement_action_prompt(
                        phase="semantic_recovery",
                        instruction=record.task_package.task.public.instruction,
                        state=recovery_state,
                        public_path_condition=condition,
                        presentation_salt=recovery_salt,
                        typed_failure=recovery_failure,
                        grammar=action_grammar,
                    )
                    _assert_exact_kernel_prompt_gate(
                        recovery_prompt,
                        phase="semantic_recovery",
                        instruction=record.task_package.task.public.instruction,
                        state=recovery_state,
                        public_path_condition=condition,
                        presentation_salt=recovery_salt,
                        typed_failure=recovery_failure,
                        grammar=action_grammar,
                    )
                    recovery_prompts.append(recovery_prompt)
                    if result.commit.action == "emit_final":
                        break
                    if result.commit.call is None:
                        raise ValueError("v26.129 non-final Commit lacks a public call")
                    observations.append(
                        _execute_observation(
                            record=record,
                            environment=environment,
                            runtime=runtime,
                            observations=tuple(observations),
                            projection=CompletionProjection(
                                request_kind="decision",
                                action="call_tool",
                                tool_id=result.commit.call.tool_id,
                                arguments=result.commit.call.arguments,
                            ),
                        )
                    )
                else:
                    raise ValueError("v26.129 Prompt-only reference path did not terminate")
                final_context = render_compact_final_prompt(
                    prompt_contract.public_context,
                    record.task_package.task.public,
                    tuple(observations),
                    public_path_condition=condition,
                )
                final_primary = render_exact_final_primary_prompt(
                    final_context, grammar=final_grammar
                )
                final_rescue = render_exact_final_rescue_prompt(
                    final_primary,
                    failure_family="response_serialization_failure",
                    failure_subtype="final_response_not_exact_shared_grammar",
                )
                upper_bound = sum(_request_bound(item) for item in primary_prompts)
                upper_bound += _request_bound(final_primary)
                upper_bound += max(
                    max(_request_bound(item) for item in abi_prompts),
                    _request_bound(final_rescue),
                )
                upper_bound += max(_request_bound(item) for item in recovery_prompts)
                all_prompts = (
                    *primary_prompts,
                    *abi_prompts,
                    *recovery_prompts,
                    final_primary,
                    final_rescue,
                )
                maximum_prompt = max(len(item.encode("utf-8")) for item in all_prompts)
                primary_count = len(primary_prompts) + 1
                provider_calls_with_recovery = primary_count + 2
                prompt_pass = maximum_prompt <= PROMPT_CEILING_BYTES
                primary_pass = primary_count <= MAXIMUM_PRIMARY_REQUESTS
                provider_pass = provider_calls_with_recovery <= MAXIMUM_PROVIDER_CALLS_WITH_RECOVERY
                headroom = ROLLOUT_BOUND - upper_bound
                rollout_pass = upper_bound < ROLLOUT_BOUND and headroom >= MINIMUM_HEADROOM
                compatible = prompt_pass and primary_pass and provider_pass and rollout_pass
                values = {
                    "role_population_id": population.population_id,
                    "source_task_artifact_id": task.artifact_id,
                    "diagnostic_task_package_id": record.task_package.package_id,
                    "diagnostic_environment_manifest_id": environment.manifest_id,
                    "compiler_witness_id": witness.witness_id,
                    "compiler_trajectory_id": canonical_hash(
                        tuple(item.model_dump(mode="json") for item in history),
                        prefix="finance_v26_role_compiler_trajectory:",
                    ),
                    "role": population.role,
                    "tier": binding.tier,
                    "path_strategy_id": strategy,
                    "source_program_node_count": len(task.task.oracle.task_program.nodes),
                    "source_public_evidence_count": len(task.public_corpus.evidence),
                    "action_state_count": len(primary_prompts),
                    "public_tool_call_count": len(observations),
                    "stage_two_commit_count": len(primary_prompts),
                    "maximum_candidate_count": maximum_candidate_count,
                    "maximum_candidate_list_utf8_bytes": (maximum_candidate_list_bytes),
                    "action_primary_prompt_sha256s": tuple(
                        hashlib.sha256(item.encode("utf-8")).hexdigest() for item in primary_prompts
                    ),
                    "final_primary_prompt_sha256": hashlib.sha256(
                        final_primary.encode("utf-8")
                    ).hexdigest(),
                    "final_rescue_prompt_sha256": hashlib.sha256(
                        final_rescue.encode("utf-8")
                    ).hexdigest(),
                    "maximum_action_primary_prompt_utf8_bytes": max(
                        len(item.encode("utf-8")) for item in primary_prompts
                    ),
                    "maximum_action_abi_rescue_prompt_utf8_bytes": max(
                        len(item.encode("utf-8")) for item in abi_prompts
                    ),
                    "maximum_semantic_recovery_prompt_utf8_bytes": max(
                        len(item.encode("utf-8")) for item in recovery_prompts
                    ),
                    "final_primary_prompt_utf8_bytes": len(final_primary.encode("utf-8")),
                    "final_rescue_prompt_utf8_bytes": len(final_rescue.encode("utf-8")),
                    "maximum_prompt_utf8_bytes": maximum_prompt,
                    "semantic_action_primary_request_count": len(primary_prompts),
                    "primary_request_count": primary_count,
                    "maximum_provider_calls_with_abi_and_semantic_recovery": (
                        provider_calls_with_recovery
                    ),
                    "maximum_provider_invocations_with_transport_replacement": (
                        provider_calls_with_recovery + 1
                    ),
                    "static_complete_path_upper_bound_tokens": upper_bound,
                    "static_rollout_headroom_tokens": headroom,
                    "prompt_ceiling_passed": prompt_pass,
                    "primary_request_limit_passed": primary_pass,
                    "provider_call_limit_passed": provider_pass,
                    "rollout_bound_passed": rollout_pass,
                    "kernel_compatible": compatible,
                    "status": ("kernel_compatible" if compatible else "kernel_incompatible"),
                }
                provisional = KernelPathCompatibilityRow.model_construct(
                    path_id="pending", **values
                )
                rows.append(
                    KernelPathCompatibilityRow(
                        path_id=_identity(
                            provisional,
                            "path_id",
                            "finance_v26_kernel_path_compatibility:",
                        ),
                        **values,
                    )
                )
    ordered = tuple(sorted(rows, key=lambda item: item.path_id))
    values = {
        "privacy_first_runner_contract_id": runner_contract.contract_id,
        "role_source_selection_audit_id": selection.audit_id,
        "capability_population_id": capability.population_id,
        "reachability_population_id": reachability.population_id,
        "compatible_path_count": sum(item.kernel_compatible for item in ordered),
        "incompatible_path_count": sum(not item.kernel_compatible for item in ordered),
        "prompt_ceiling_failure_count": sum(not item.prompt_ceiling_passed for item in ordered),
        "primary_request_limit_failure_count": sum(
            not item.primary_request_limit_passed for item in ordered
        ),
        "provider_call_limit_failure_count": sum(
            not item.provider_call_limit_passed for item in ordered
        ),
        "rollout_bound_failure_count": sum(not item.rollout_bound_passed for item in ordered),
        "maximum_prompt_utf8_bytes": max(item.maximum_prompt_utf8_bytes for item in ordered),
        "maximum_primary_request_count": max(item.primary_request_count for item in ordered),
        "maximum_static_path_upper_bound_tokens": max(
            item.static_complete_path_upper_bound_tokens for item in ordered
        ),
        "minimum_static_rollout_headroom_tokens": min(
            item.static_rollout_headroom_tokens for item in ordered
        ),
        "candidate_distribution": tuple(
            CandidateCountRow(candidate_count=count, state_count=states)
            for count, states in sorted(candidate_counts.items())
        ),
        "paths": ordered,
    }
    provisional = KernelCompatibilityAudit.model_construct(audit_id="pending", **values)
    return KernelCompatibilityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_kernel_compatibility_audit:",
        ),
        **values,
    )


def _expect_rejected(name: str, callback: Any) -> MutationResult:
    try:
        callback()
    except Exception:
        return MutationResult(name=name)
    raise ValueError(f"v26.129 destructive mutation was accepted: {name}")


def _build_destructive(
    *,
    capability: FreshRoleSourcePopulation,
    reachability: FreshRoleSourcePopulation,
    selection: RoleSourceSelectionAudit,
    compatibility: KernelCompatibilityAudit,
) -> DestructiveAudit:
    first_path = compatibility.paths[0]
    incompatible_path = next(item for item in compatibility.paths if not item.kernel_compatible)
    mutations = (
        _expect_rejected(
            "capability_population_relabelled_as_reachability",
            lambda: FreshRoleSourcePopulation.model_validate(
                {
                    **capability.model_dump(mode="json"),
                    "role": "reachability",
                }
            ),
        ),
        _expect_rejected(
            "cross_role_population_identity_merged",
            lambda: RoleSourceSelectionAudit.model_validate(
                {
                    **selection.model_dump(mode="json"),
                    "reachability_population_id": capability.population_id,
                }
            ),
        ),
        _expect_rejected(
            "freshness_channel_deleted",
            lambda: RoleSourceSelectionAudit.model_validate(
                {
                    **selection.model_dump(mode="json"),
                    "freshness_channels": selection.model_dump(mode="json")["freshness_channels"][
                        :-1
                    ],
                }
            ),
        ),
        _expect_rejected(
            "hard_task_replaced_after_resource_audit",
            lambda: FreshRoleSourcePopulation.model_validate(
                {
                    **capability.model_dump(mode="json"),
                    "tasks": (
                        *capability.model_dump(mode="json")["tasks"][:-1],
                        capability.model_dump(mode="json")["tasks"][0],
                    ),
                }
            ),
        ),
        _expect_rejected(
            "incompatible_path_deleted",
            lambda: KernelCompatibilityAudit.model_validate(
                {
                    **compatibility.model_dump(mode="json"),
                    "paths": compatibility.model_dump(mode="json")["paths"][:-1],
                }
            ),
        ),
        _expect_rejected(
            "prompt_ceiling_failure_relabelled_pass",
            lambda: KernelPathCompatibilityRow.model_validate(
                {
                    **incompatible_path.model_dump(mode="json"),
                    "prompt_ceiling_passed": True,
                    "kernel_compatible": True,
                    "status": "kernel_compatible",
                }
            ),
        ),
        _expect_rejected(
            "provider_call_limit_relaxed",
            lambda: KernelPathCompatibilityRow.model_validate(
                {
                    **incompatible_path.model_dump(mode="json"),
                    "provider_call_limit_passed": True,
                    "kernel_compatible": True,
                    "status": "kernel_compatible",
                }
            ),
        ),
        _expect_rejected(
            "rollout_bound_failure_relabelled_pass",
            lambda: KernelPathCompatibilityRow.model_validate(
                {
                    **incompatible_path.model_dump(mode="json"),
                    "rollout_bound_passed": True,
                    "kernel_compatible": True,
                    "status": "kernel_compatible",
                }
            ),
        ),
        _expect_rejected(
            "transport_failure_usage_imputed",
            lambda: KernelPathCompatibilityRow.model_validate(
                {
                    **first_path.model_dump(mode="json"),
                    "failed_transport_usage_imputed": True,
                }
            ),
        ),
        _expect_rejected(
            "kernel_resource_values_used_for_source_selection",
            lambda: RoleSourceSelectionAudit.model_validate(
                {
                    **selection.model_dump(mode="json"),
                    "kernel_resource_values_used_for_selection": True,
                }
            ),
        ),
        _expect_rejected(
            "role_manifest_authorized_after_failed_gate",
            lambda: ProspectiveTransitionContract(
                contract_id="pending",
                role_source_selection_audit_id=selection.audit_id,
                kernel_compatibility_audit_id=compatibility.audit_id,
                role_task_package_contract_manifest_job_or_runner_materialization_authorized=True,
            ),
        ),
        _expect_rejected(
            "role_provider_call_authorized_after_failed_gate",
            lambda: ProspectiveTransitionContract(
                contract_id="pending",
                role_source_selection_audit_id=selection.audit_id,
                kernel_compatibility_audit_id=compatibility.audit_id,
                provider_calls_authorized=True,
            ),
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.name))
    values = {"mutations": ordered}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_role_kernel_destructive:",
        ),
        **values,
    )


def _make_transition(
    *,
    selection: RoleSourceSelectionAudit,
    compatibility: KernelCompatibilityAudit,
) -> ProspectiveTransitionContract:
    values = {
        "role_source_selection_audit_id": selection.audit_id,
        "kernel_compatibility_audit_id": compatibility.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_role_kernel_transition:",
        ),
        **values,
    )


def build_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_dir: Path,
    output_dir: Path,
    source_frame_input: Path | None = None,
) -> RoleKernelCompatibilityPreflightReport:
    if output_dir.exists():
        raise ValueError(f"immutable v26.129 output directory exists: {output_dir}")
    source = build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        predecessor_dir=predecessor_dir,
    )
    historical = _build_historical_inputs(
        source=source,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    output_dir.mkdir(parents=True)
    source_frame_path = output_dir / "fresh_source_sampling_frame.json"
    if source_frame_input is None:
        source_frame = build_capability_sensitive_frontier_population(
            source_artifacts_path=package_root / SNAPSHOT_PATH,
            output_path=source_frame_path,
            run_id=SOURCE_RUN_ID,
            sampling_salt=SOURCE_SAMPLING_SALT,
            excluded_evidence_ids=historical.effective_excluded_evidence_ids,
        )
    else:
        source_frame = CapabilitySensitiveFrontierPopulation.model_validate_json(
            source_frame_input.read_text(encoding="utf-8")
        )
        if (
            source_frame.run_id != SOURCE_RUN_ID
            or source_frame.sampling_salt != SOURCE_SAMPLING_SALT
            or Path(source_frame.source_artifacts_path).resolve()
            != (package_root / SNAPSHOT_PATH).resolve()
            or source_frame.source_artifacts_sha256 != _sha256(package_root / SNAPSHOT_PATH)
        ):
            raise ValueError("v26.129 frozen source-frame input changed")
        selected_evidence = {
            item.evidence_id for task in source_frame.tasks for item in task.public_corpus.evidence
        }
        if selected_evidence & set(historical.effective_excluded_evidence_ids):
            raise ValueError("v26.129 frozen source-frame input overlaps exclusions")
        _write_json_atomic(source_frame_path, source_frame.model_dump(mode="json"))
    historical_audit = _make_historical_exclusion_audit(
        source=source,
        historical=historical,
        frame=source_frame,
        snapshot_path=package_root / SNAPSHOT_PATH,
    )
    capability, reachability, selection, selected_tasks = _freeze_role_populations(
        frame=source_frame,
        prior_channels=historical.prior_channels,
        source_replay_audit_id=source.audit_id,
        historical_exclusion_audit_id=historical_audit.audit_id,
    )
    pre_kernel_outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("historical_exposure_exclusion_audit.json", historical_audit),
        ("capability_source_population.json", capability),
        ("reachability_source_population.json", reachability),
        ("role_source_selection_audit.json", selection),
    )
    for name, value in pre_kernel_outputs:
        _write_json_atomic(output_dir / name, value.model_dump(mode="json"))

    kernel = predecessor.EngineeringKernelFreeze.model_validate_json(
        (predecessor_dir / "engineering_kernel_freeze.json").read_text(encoding="utf-8")
    )
    action_grammar = SemanticActionResponseGrammar.model_validate_json(
        (package_root / ACTION_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    final_grammar = ExactFinalResponseGrammar.model_validate_json(
        (package_root / FINAL_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    runner_contract = privacy_runner.PrivacyFirstRunnerContract.model_validate_json(
        (package_root / PRIVACY_FIRST_RUNNER_CONTRACT_PATH).read_text(encoding="utf-8")
    )
    compatibility = _build_context_kernel_compatibility(
        package_root=package_root,
        capability=capability,
        reachability=reachability,
        selection=selection,
        selected_tasks=selected_tasks,
        kernel=kernel,
        runner_contract=runner_contract,
        action_grammar=action_grammar,
        final_grammar=final_grammar,
    )
    destructive = _build_destructive(
        capability=capability,
        reachability=reachability,
        selection=selection,
        compatibility=compatibility,
    )
    transition = _make_transition(
        selection=selection,
        compatibility=compatibility,
    )
    post_kernel_outputs: tuple[tuple[str, BaseModel], ...] = (
        ("kernel_compatibility_audit.json", compatibility),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    for name, value in post_kernel_outputs:
        _write_json_atomic(output_dir / name, value.model_dump(mode="json"))
    detail_names = tuple(
        sorted(
            (
                "fresh_source_sampling_frame.json",
                *(name for name, _ in pre_kernel_outputs),
                *(name for name, _ in post_kernel_outputs),
            )
        )
    )
    details = tuple(_detail(output_dir / name, output_dir) for name in detail_names)
    request_limit_failures = sum(
        not (item.primary_request_limit_passed and item.provider_call_limit_passed)
        for item in compatibility.paths
    )
    report_values = {
        "source_replay_audit_id": source.audit_id,
        "historical_exclusion_audit_id": historical_audit.audit_id,
        "source_frame_population_id": source_frame.population_id,
        "capability_population_id": capability.population_id,
        "reachability_population_id": reachability.population_id,
        "role_source_selection_audit_id": selection.audit_id,
        "kernel_compatibility_audit_id": compatibility.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
        "incompatible_path_count": compatibility.incompatible_path_count,
        "prompt_ceiling_failure_count": compatibility.prompt_ceiling_failure_count,
        "request_limit_failure_count": request_limit_failures,
        "rollout_bound_failure_count": compatibility.rollout_bound_failure_count,
    }
    provisional_report = RoleKernelCompatibilityPreflightReport.model_construct(
        report_id="pending", **report_values
    )
    report = RoleKernelCompatibilityPreflightReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_role_kernel_compatibility_preflight_report:",
        ),
        **report_values,
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.129 fresh role Kernel compatibility preflight"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--predecessor-dir",
        type=Path,
        default=package_default / PREDECESSOR_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    parser.add_argument("--source-frame-input", type=Path)
    args = parser.parse_args()
    report = build_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        predecessor_dir=args.predecessor_dir,
        output_dir=args.output_dir,
        source_frame_input=args.source_frame_input,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
