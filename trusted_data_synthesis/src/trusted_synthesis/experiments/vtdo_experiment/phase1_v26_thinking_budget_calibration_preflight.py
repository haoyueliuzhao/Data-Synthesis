from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingTaskAudit,
    _harden_environment,
    _harden_record,
    _task_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    replay_authority_preserving_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument import (
    CompletedTrajectoryScore,
    compiler_witness_trajectory,
    score_completed_trajectory,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    DEVELOPMENT_POPULATION_PATH,
    FRESHNESS_CHANNELS,
    SOURCE_POPULATION_PATHS,
    VERIFIER_QUALIFICATION_DIR,
    BudgetFeasibleRoleRematerializationReport,
    BudgetFeasibleRoleTaskPackage,
    BudgetQualifiedPathAudit,
    CompactPromptContract,
    _atomic_leaf_node,
    _bind_verifier_v2,
    _load_and_replay_verifier_qualification,
    _load_historical_manifest_values,
    _load_historical_records,
    _load_population,
    _load_predecessor,
    _load_thinking_binding,
    _make_budget_qualified_path,
    _make_compact_prompt_contract,
    _merge_channel_values,
    _record_values,
    _role_draft,
    _sha256,
    _sha256_text,
    _source_task_values,
    _task_replay_binding,
    _upgrade_task,
    _verifier_bound_environment,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    TargetMechanism,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
    load_v26_selected_source_tasks,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_builder import (
    MECHANISM_SOURCE_FAMILY,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    ImplementationSourceFile,
    OperationalTaskAdmission,
    OperationalTaskRecord,
    OperationClosureAudit,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (
    build_operation_closure_audit,
    build_operational_admission,
    compile_operational_witness,
    mechanism_necessity_and_catalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    VerifierV2TaskReplayBinding,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.budget_closed import (
    ProviderTokenBudgetContract,
    _provider_request_kind,
    _required_reserves,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import (
    render_compact_witness_prompts,
)
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry
from trusted_synthesis.runtime.agent.thinking_history import (
    CompletionOutcome,
    CompletionUsabilityClassification,
    ThinkingContinuityContract,
    ThinkingHistoryAudit,
    attest_thinking_turn,
    audit_thinking_history,
    classify_completion_usability,
    make_thinking_continuity_contract,
)
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

V26_91_VERSION = "finance_v26_thinking_budget_calibration_preflight.v1"
V26_91_SOURCE_REPLAY_VERSION = "finance_v26_thinking_calibration_source_replay.v1"
V26_91_SOURCE_SELECTION_VERSION = "finance_v26_thinking_calibration_source_selection.v1"
V26_91_PREFIX_ENVELOPE_VERSION = "finance_v26_role_prefix_budget_envelope.v1"
V26_91_STRESS_PATH_VERSION = "finance_v26_calibration_stress_path.v1"
V26_91_TASK_PACKAGE_VERSION = "finance_v26_calibration_task_package.v1"
V26_91_CONTINUITY_FIXTURE_VERSION = "finance_v26_thinking_continuity_fixture_audit.v1"
V26_91_COMPLETION_CONTRACT_VERSION = "finance_v26_completion_usability_contract.v1"
V26_91_COMPLETION_FIXTURE_VERSION = "finance_v26_completion_usability_fixture_audit.v1"
V26_91_CALIBRATION_CONTRACT_VERSION = "finance_v26_thinking_budget_calibration_contract.v1"
V26_91_JOB_VERSION = "finance_v26_thinking_budget_calibration_job.v1"
V26_91_MANIFEST_VERSION = "finance_v26_thinking_budget_calibration_manifest.v1"
V26_91_FRESHNESS_VERSION = "finance_v26_thinking_budget_calibration_freshness.v1"
V26_91_COVERAGE_VERSION = "finance_v26_thinking_budget_shape_coverage.v1"
V26_91_DESTRUCTIVE_VERSION = "finance_v26_thinking_calibration_destructive_preflight.v1"
V26_91_REPORT_VERSION = "finance_v26_thinking_budget_calibration_preflight_report.v1"

V26_90_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821"
)
CALIBRATION_TASK_COUNT: Literal[31] = 31
CALIBRATION_JOB_COUNT: Literal[32] = 32
PREFIX_STRESS_MARGIN: Literal[64] = 64
ROLE_PREFIX_ENVELOPE_COUNT: Literal[12] = 12
BASE_COMPILER_PATH_COUNT: Literal[93] = 93
CALIBRATION_PATH_STRATEGIES: tuple[PathStrategy, ...] = (
    "structured_direct",
    "search_then_structured",
    "search_then_open",
)

MECHANISM_TASK_COUNTS: dict[TargetMechanism, int] = {
    "context_conditioned_action": 5,
    "semantic_reconciliation": 10,
    "failure_recovery": 8,
    "state_dependent_stopping": 8,
}
CELL_JOB_COUNTS: dict[str, int] = {
    "context_conditioned_action:structured_direct": 2,
    "context_conditioned_action:search_then_structured": 2,
    "context_conditioned_action:search_then_open": 2,
    "semantic_reconciliation:structured_direct": 2,
    "semantic_reconciliation:search_then_structured": 4,
    "semantic_reconciliation:search_then_open": 4,
    "failure_recovery:structured_direct": 2,
    "failure_recovery:search_then_structured": 3,
    "failure_recovery:search_then_open": 3,
    "state_dependent_stopping:structured_direct": 2,
    "state_dependent_stopping:search_then_structured": 3,
    "state_dependent_stopping:search_then_open": 3,
}
MECHANISM_JOB_SLOTS: dict[TargetMechanism, tuple[PathStrategy, ...]] = {
    "context_conditioned_action": (
        "structured_direct",
        "search_then_structured",
        "search_then_open",
        "structured_direct",
        "search_then_structured",
        "search_then_open",
    ),
    "semantic_reconciliation": (
        "structured_direct",
        "search_then_structured",
        "search_then_open",
        "structured_direct",
        "search_then_structured",
        "search_then_open",
        "search_then_structured",
        "search_then_open",
        "search_then_structured",
        "search_then_open",
    ),
    "failure_recovery": (
        "structured_direct",
        "search_then_structured",
        "search_then_open",
        "structured_direct",
        "search_then_structured",
        "search_then_open",
        "search_then_structured",
        "search_then_open",
    ),
    "state_dependent_stopping": (
        "structured_direct",
        "search_then_structured",
        "search_then_open",
        "structured_direct",
        "search_then_structured",
        "search_then_open",
        "search_then_structured",
        "search_then_open",
    ),
}

IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted(
        {
            "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_budget_calibration_preflight.py",
            "src/trusted_synthesis/runtime/agent/thinking_history.py",
        }
    )
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    source_kind: Literal[
        "v26_90_report",
        "v26_90_detail",
        "v26_90_source",
        "v26_90_implementation",
    ]
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> ReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.90 replay source bytes changed")
        return self


class PredecessorReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    entries: tuple[ReplayEntry, ...] = Field(min_length=100)
    replayed_file_count: int = Field(ge=100)
    v26_90_output_file_count: Literal[25] = 25
    v26_90_source_file_count: Literal[57] = 57
    v26_90_implementation_file_count: Literal[22] = 22
    replay_before_contract_and_manifest: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_91_SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorReplayAudit:
        keys = tuple((item.source_kind, item.relative_path) for item in self.entries)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("v26.90 replay entries are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("v26.90 replay denominator changed")
        if self.audit_id != predecessor_replay_audit_id(self):
            raise ValueError("v26.90 replay audit identity is invalid")
        return self


class CalibrationSourceSelectionRow(FrozenModel):
    row_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    source_task_artifact_id: str = Field(min_length=1)
    source_task_hash: str = Field(min_length=1)
    rank_hash: str = Field(min_length=1)
    selected_for_static_shape_only: Literal[True] = True
    historical_outcome_loaded: Literal[False] = False
    schema_version: str = V26_91_SOURCE_SELECTION_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> CalibrationSourceSelectionRow:
        if self.row_id != calibration_source_selection_row_id(self):
            raise ValueError("calibration source selection identity is invalid")
        return self


class CalibrationSourceCapacityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    eligible_counts: dict[TargetMechanism, int]
    selected_counts: dict[TargetMechanism, int]
    selected_rows: tuple[CalibrationSourceSelectionRow, ...] = Field(
        min_length=CALIBRATION_TASK_COUNT,
        max_length=CALIBRATION_TASK_COUNT,
    )
    selected_task_count: Literal[31] = CALIBRATION_TASK_COUNT
    selection_salt: str = Field(min_length=1)
    internal_source_overlap_count: Literal[0] = 0
    historical_model_outcomes_loaded: Literal[False] = False
    historical_model_outcomes_used: Literal[False] = False
    compiler_fixture_outcomes_loaded: Literal[False] = False
    compiler_fixture_outcomes_used: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_91_SOURCE_SELECTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CalibrationSourceCapacityAudit:
        if self.selected_counts != MECHANISM_TASK_COUNTS:
            raise ValueError("calibration source quotas changed")
        if len(self.selected_rows) != self.selected_task_count:
            raise ValueError("calibration source denominator changed")
        if self.audit_id != calibration_source_capacity_audit_id(self):
            raise ValueError("calibration source capacity identity is invalid")
        return self


class RolePrefixBudgetEnvelope(FrozenModel):
    envelope_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    path_strategy_id: PathStrategy
    source_role_path_audit_ids: tuple[str, ...] = Field(min_length=3)
    source_role_path_count: int = Field(ge=3)
    request_count: int = Field(ge=1)
    maximum_role_prefix_bounds: tuple[int, ...] = Field(min_length=1)
    maximum_role_path_upper_bound: int = Field(ge=1, le=120000)
    derived_without_model_outcomes: Literal[True] = True
    schema_version: str = V26_91_PREFIX_ENVELOPE_VERSION

    @model_validator(mode="after")
    def validate_envelope(self) -> RolePrefixBudgetEnvelope:
        if self.source_role_path_count != len(self.source_role_path_audit_ids):
            raise ValueError("role prefix source denominator changed")
        if self.request_count != len(self.maximum_role_prefix_bounds):
            raise ValueError("role prefix request denominator changed")
        if self.maximum_role_path_upper_bound != max(self.maximum_role_prefix_bounds):
            raise ValueError("role prefix maximum changed")
        if self.envelope_id != role_prefix_budget_envelope_id(self):
            raise ValueError("role prefix envelope identity is invalid")
        return self


class PrefixStressRow(FrozenModel):
    request_index: int = Field(ge=0)
    request_kind: str = Field(min_length=1)
    unpadded_prompt_sha256: str = Field(min_length=64, max_length=64)
    padded_prompt_sha256: str = Field(min_length=64, max_length=64)
    unpadded_prompt_utf8_bytes: int = Field(ge=1)
    trailing_ascii_space_padding_bytes: int = Field(ge=0)
    padded_prompt_utf8_bytes: int = Field(ge=1)
    role_prefix_upper_bound: int = Field(ge=1)
    required_prefix_upper_bound: int = Field(ge=1)
    calibration_prefix_upper_bound: int = Field(ge=1)
    coverage_margin_tokens: int = Field(ge=PREFIX_STRESS_MARGIN)
    prompt_ceiling_passed: Literal[True] = True
    rollout_ceiling_passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> PrefixStressRow:
        if self.padded_prompt_utf8_bytes != (
            self.unpadded_prompt_utf8_bytes + self.trailing_ascii_space_padding_bytes
        ):
            raise ValueError("calibration padding arithmetic changed")
        if self.required_prefix_upper_bound != (
            self.role_prefix_upper_bound + PREFIX_STRESS_MARGIN
        ):
            raise ValueError("calibration prefix stress margin changed")
        if self.coverage_margin_tokens != (
            self.calibration_prefix_upper_bound - self.role_prefix_upper_bound
        ):
            raise ValueError("calibration prefix coverage arithmetic changed")
        return self


class CalibrationStressPathAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    path_strategy_id: PathStrategy
    base_path_audit_id: str = Field(min_length=1)
    role_prefix_envelope_id: str = Field(min_length=1)
    rows: tuple[PrefixStressRow, ...] = Field(min_length=1)
    request_count: int = Field(ge=1)
    maximum_path_upper_bound: int = Field(ge=1, le=120000)
    minimum_headroom_tokens: int = Field(ge=0)
    maximum_prompt_utf8_bytes: int = Field(ge=1, le=60000)
    minimum_prefix_coverage_margin: int = Field(ge=PREFIX_STRESS_MARGIN)
    padding_policy: Literal["trailing_ascii_space_per_registered_prefix"] = (
        "trailing_ascii_space_per_registered_prefix"
    )
    padding_is_calibration_stress_only: Literal[True] = True
    padding_semantic_equivalence_not_assumed: Literal[True] = True
    empirical_usability_requires_calibration: Literal[True] = True
    full_path_budget_qualified: Literal[True] = True
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_91_STRESS_PATH_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CalibrationStressPathAudit:
        if self.request_count != len(self.rows):
            raise ValueError("calibration stress request denominator changed")
        if tuple(item.request_index for item in self.rows) != tuple(range(len(self.rows))):
            raise ValueError("calibration stress request order changed")
        if self.maximum_path_upper_bound != max(
            item.calibration_prefix_upper_bound for item in self.rows
        ):
            raise ValueError("calibration stress path maximum changed")
        if self.minimum_headroom_tokens != 120000 - self.maximum_path_upper_bound:
            raise ValueError("calibration stress headroom changed")
        if self.maximum_prompt_utf8_bytes != max(
            item.padded_prompt_utf8_bytes for item in self.rows
        ):
            raise ValueError("calibration stress Prompt maximum changed")
        if self.minimum_prefix_coverage_margin != min(
            item.coverage_margin_tokens for item in self.rows
        ):
            raise ValueError("calibration stress prefix margin changed")
        if self.audit_id != calibration_stress_path_audit_id(self):
            raise ValueError("calibration stress path identity is invalid")
        return self


class CalibrationTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    verifier_replay_binding_id: str = Field(min_length=1)
    compact_prompt_contract_id: str = Field(min_length=1)
    base_path_audit_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    base_path_strategy_ids: tuple[PathStrategy, ...] = CALIBRATION_PATH_STRATEGIES
    underlying_operational_intended_use: Literal["vtdo_multistate_candidate"] = (
        "vtdo_multistate_candidate"
    )
    calibration_only_override: Literal[True] = True
    capability_denominator_eligible: Literal[False] = False
    reachability_denominator_eligible: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    empirical_job_count_at_preflight: Literal[0] = 0
    schema_version: str = V26_91_TASK_PACKAGE_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> CalibrationTaskPackage:
        if self.base_path_strategy_ids != CALIBRATION_PATH_STRATEGIES:
            raise ValueError("calibration task path catalog changed")
        if self.task_package_id != calibration_task_package_id(self):
            raise ValueError("calibration TaskPackage identity is invalid")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_kind: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejection_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.mutation_id != mutation_result_id(self):
            raise ValueError("mutation result identity is invalid")
        return self


class ThinkingContinuityFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    continuity_contract_id: str = Field(min_length=1)
    history_audit: ThinkingHistoryAudit
    successful_turn_count: Literal[3] = 3
    mutation_results: tuple[MutationResult, ...] = Field(min_length=4)
    rejected_mutation_count: int = Field(ge=4)
    provider_calls: Literal[0] = 0
    private_reasoning_content_persisted: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_91_CONTINUITY_FIXTURE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ThinkingContinuityFixtureAudit:
        if self.rejected_mutation_count != len(self.mutation_results):
            raise ValueError("thinking fixture mutation denominator changed")
        if self.audit_id != thinking_continuity_fixture_audit_id(self):
            raise ValueError("thinking fixture audit identity is invalid")
        return self


class CompletionUsabilityContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    completion_upper_bound_tokens: Literal[4096] = 4096
    maximum_contract_repair_attempts: Literal[1] = 1
    job_is_primary_sampling_unit: Literal[True] = True
    minimum_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    typed_no_call_confidence_rule: Literal["one_sided_clopper_pearson_95_upper_bound_lte_0.10"] = (
        "one_sided_clopper_pearson_95_upper_bound_lte_0.10"
    )
    completion_unusable_confidence_rule: Literal[
        "one_sided_clopper_pearson_95_upper_bound_lte_0.10"
    ] = "one_sided_clopper_pearson_95_upper_bound_lte_0.10"
    zero_failures_required_at_32_jobs: Literal[True] = True
    frozen_upper_bound_threshold: float = Field(default=0.1, ge=0.1, le=0.1)
    zero_failure_cp95_upper_bound_at_32: float = Field(default=0.08936819898626475, gt=0, lt=0.1)
    one_failure_cp95_upper_bound_at_32: float = Field(default=0.13984946027422601, gt=0.1, lt=1)
    typed_no_call_job_rule: Literal["any_typed_no_call_terminal"] = "any_typed_no_call_terminal"
    completion_unusable_job_rule: Literal[
        "terminal_request_lacks_usable_structured_decision_after_at_most_one_repair"
    ] = "terminal_request_lacks_usable_structured_decision_after_at_most_one_repair"
    typed_no_call_and_completion_unusable_separate: Literal[True] = True
    provider_transport_failure_reported_separately: Literal[True] = True
    completion_limit_hit_reported_separately: Literal[True] = True
    reasoning_presence_required_per_http_success: Literal[True] = True
    reasoning_length_required_per_http_success: Literal[True] = True
    reasoning_tokens_required_per_http_success: Literal[True] = True
    reasoning_token_fraction_reported: Literal[True] = True
    decision_contract_after_reasoning_required: Literal[True] = True
    contract_repair_rate_reported: Literal[True] = True
    identical_failed_call_replays_allowed: Literal[0] = 0
    request_count_reported: Literal[True] = True
    provider_usage_reported: Literal[True] = True
    failed_observation_count_reported: Literal[True] = True
    repeated_call_signature_count_reported: Literal[True] = True
    repeated_failed_call_signature_count_reported: Literal[True] = True
    program_completion_reported_descriptively: Literal[True] = True
    independent_validity_reported_descriptively: Literal[True] = True
    mechanism_success_reported_descriptively: Literal[True] = True
    requested_path_adherence_reported_descriptively: Literal[True] = True
    cell_floor_and_saturation_reported_descriptively: Literal[True] = True
    behavior_diagnostics_are_non_authorizing: Literal[True] = True
    task_depth_adequacy_remains_unresolved: Literal[True] = True
    completion_outcomes: tuple[CompletionOutcome, ...] = (
        "typed_no_call",
        "provider_transport_failure",
        "thinking_telemetry_missing_or_empty",
        "reasoning_only_length_truncation",
        "length_truncated_content",
        "empty_final_content",
        "invalid_json_after_repair",
        "invalid_decision_contract_after_repair",
        "usable_after_contract_repair",
        "usable_structured_completion",
    )
    classification_schema_version: Literal["completion_usability_classification.v1"] = (
        "completion_usability_classification.v1"
    )
    semantic_validity_is_not_completion_usability: Literal[True] = True
    calibration_valid_trajectories_role_ineligible: Literal[True] = True
    threshold_selected_without_model_outcomes: Literal[True] = True
    schema_version: str = V26_91_COMPLETION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CompletionUsabilityContract:
        if len(self.completion_outcomes) != len(set(self.completion_outcomes)):
            raise ValueError("completion usability taxonomy contains duplicates")
        if self.frozen_upper_bound_threshold != 0.1:
            raise ValueError("completion usability threshold changed")
        if not math.isclose(
            self.zero_failure_cp95_upper_bound_at_32,
            _cp_upper(0, CALIBRATION_JOB_COUNT),
            rel_tol=0,
            abs_tol=1e-15,
        ):
            raise ValueError("zero-failure Clopper-Pearson boundary changed")
        if not math.isclose(
            self.one_failure_cp95_upper_bound_at_32,
            _cp_upper(1, CALIBRATION_JOB_COUNT),
            rel_tol=0,
            abs_tol=1e-15,
        ):
            raise ValueError("one-failure Clopper-Pearson boundary changed")
        if self.contract_id != completion_usability_contract_id(self):
            raise ValueError("completion usability Contract identity is invalid")
        return self


class CompletionUsabilityFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    completion_usability_contract_id: str = Field(min_length=1)
    classifications: tuple[CompletionUsabilityClassification, ...] = Field(
        min_length=10,
        max_length=10,
    )
    outcome_counts: dict[str, int]
    resource_no_call_count: Literal[1] = 1
    completion_unusable_count: Literal[6] = 6
    transport_failure_count: Literal[1] = 1
    usable_completion_count: Literal[2] = 2
    no_call_and_completion_denominators_separate: Literal[True] = True
    mutation_results: tuple[MutationResult, ...] = Field(min_length=2)
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_91_COMPLETION_FIXTURE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompletionUsabilityFixtureAudit:
        if tuple(item.request_index for item in self.classifications) != tuple(
            range(len(self.classifications))
        ):
            raise ValueError("completion fixture request order changed")
        observed = dict(
            sorted(Counter(item.completion_outcome for item in self.classifications).items())
        )
        if self.outcome_counts != observed:
            raise ValueError("completion fixture outcome accounting changed")
        if self.resource_no_call_count != sum(
            item.resource_no_call for item in self.classifications
        ):
            raise ValueError("completion fixture resource denominator changed")
        if self.completion_unusable_count != sum(
            item.completion_unusable for item in self.classifications
        ):
            raise ValueError("completion fixture unusable denominator changed")
        if self.transport_failure_count != observed.get("provider_transport_failure", 0):
            raise ValueError("completion fixture transport denominator changed")
        usable_outcomes = {"usable_after_contract_repair", "usable_structured_completion"}
        if self.usable_completion_count != sum(
            item.completion_outcome in usable_outcomes for item in self.classifications
        ):
            raise ValueError("completion fixture usable denominator changed")
        if self.audit_id != completion_usability_fixture_audit_id(self):
            raise ValueError("completion fixture audit identity is invalid")
        return self


class ThinkingBudgetCalibrationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_replay_audit_id: str = Field(min_length=1)
    budget_adequacy_contract_id: str = Field(min_length=1)
    provider_budget_contract_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_continuity_contract_id: str = Field(min_length=1)
    completion_usability_contract_id: str = Field(min_length=1)
    calibration_population_id: str = Field(min_length=1)
    calibration_task_package_ids: tuple[str, ...] = Field(
        min_length=CALIBRATION_TASK_COUNT,
        max_length=CALIBRATION_TASK_COUNT,
    )
    calibration_task_count: Literal[31] = CALIBRATION_TASK_COUNT
    calibration_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    mechanism_task_counts: dict[TargetMechanism, int] = MECHANISM_TASK_COUNTS
    mechanism_path_job_counts: dict[str, int] = CELL_JOB_COUNTS
    role_prefix_envelope_ids: tuple[str, ...] = Field(
        min_length=ROLE_PREFIX_ENVELOPE_COUNT,
        max_length=ROLE_PREFIX_ENVELOPE_COUNT,
    )
    prefix_stress_margin_tokens: Literal[64] = PREFIX_STRESS_MARGIN
    every_calibration_prefix_dominates_role_prefix: Literal[True] = True
    calibration_padding_policy: Literal["trailing_ascii_space_per_registered_prefix"] = (
        "trailing_ascii_space_per_registered_prefix"
    )
    calibration_padding_not_used_for_role_measurement: Literal[True] = True
    exact_model_required: Literal[True] = True
    fallback_forbidden: Literal[True] = True
    thinking_type: Literal["enabled"] = "enabled"
    provider_native_tool_calls_forbidden: Literal[True] = True
    provider_ignored_sampling_fields: tuple[str, ...] = ("temperature", "top_p")
    ignored_sampling_fields_not_interpreted_as_controls: Literal[True] = True
    calibration_rows_capability_ineligible: Literal[True] = True
    calibration_rows_reachability_ineligible: Literal[True] = True
    calibration_rows_state_mapping_ineligible: Literal[True] = True
    calibration_rows_release_ineligible: Literal[True] = True
    passing_result_authorizes_only: Literal["thinking_role_protocol_freeze_only"] = (
        "thinking_role_protocol_freeze_only"
    )
    execution_permitted_during_preflight: Literal[False] = False
    schema_version: str = V26_91_CALIBRATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ThinkingBudgetCalibrationContract:
        if self.calibration_task_package_ids != tuple(
            sorted(set(self.calibration_task_package_ids))
        ):
            raise ValueError("calibration TaskPackage identities are not canonical")
        if self.mechanism_task_counts != MECHANISM_TASK_COUNTS:
            raise ValueError("calibration mechanism task quotas changed")
        if self.mechanism_path_job_counts != CELL_JOB_COUNTS:
            raise ValueError("calibration mechanism-path quotas changed")
        if self.provider_ignored_sampling_fields != ("temperature", "top_p"):
            raise ValueError("Provider ignored sampling controls changed")
        if self.contract_id != thinking_budget_calibration_contract_id(self):
            raise ValueError("Thinking Budget Calibration Contract identity is invalid")
        return self


class ThinkingBudgetCalibrationJob(FrozenModel):
    job_id: str = Field(min_length=1)
    calibration_contract_id: str = Field(min_length=1)
    calibration_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    path_strategy_id: PathStrategy
    stress_path_audit_id: str = Field(min_length=1)
    job_seed: int = Field(ge=0)
    model_config_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    thinking_continuity_contract_id: str = Field(min_length=1)
    completion_usability_contract_id: str = Field(min_length=1)
    independent_job_identity: Literal[True] = True
    capability_denominator_eligible: Literal[False] = False
    reachability_denominator_eligible: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    execution_permitted_during_preflight: Literal[False] = False
    schema_version: str = V26_91_JOB_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> ThinkingBudgetCalibrationJob:
        if self.job_id != thinking_budget_calibration_job_id(self):
            raise ValueError("Thinking Budget Calibration Job identity is invalid")
        return self


class ThinkingBudgetCalibrationManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    calibration_contract_id: str = Field(min_length=1)
    jobs: tuple[ThinkingBudgetCalibrationJob, ...] = Field(
        min_length=CALIBRATION_JOB_COUNT,
        max_length=CALIBRATION_JOB_COUNT,
    )
    job_count: Literal[32] = CALIBRATION_JOB_COUNT
    distinct_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    distinct_task_count: Literal[31] = CALIBRATION_TASK_COUNT
    mechanism_path_job_counts: dict[str, int] = CELL_JOB_COUNTS
    historical_job_overlap_count: Literal[0] = 0
    role_task_overlap_count: Literal[0] = 0
    calibration_execution_completed: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_91_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ThinkingBudgetCalibrationManifest:
        if self.job_count != len(self.jobs):
            raise ValueError("calibration Job denominator changed")
        if self.distinct_job_count != len({item.job_id for item in self.jobs}):
            raise ValueError("calibration Jobs are not unique")
        if self.distinct_task_count != len(
            {item.calibration_task_package_id for item in self.jobs}
        ):
            raise ValueError("calibration task denominator changed")
        observed = dict(
            sorted(
                Counter(
                    f"{item.mechanism_id}:{item.path_strategy_id}" for item in self.jobs
                ).items()
            )
        )
        if self.mechanism_path_job_counts != observed or observed != CELL_JOB_COUNTS:
            raise ValueError("calibration mechanism-path Job cells changed")
        if self.manifest_id != thinking_budget_calibration_manifest_id(self):
            raise ValueError("Thinking Budget Calibration Manifest identity is invalid")
        return self


class CalibrationFreshnessChannel(FrozenModel):
    channel: str = Field(min_length=1)
    prior_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    prior_overlap_count: Literal[0] = 0
    internal_duplicate_count: Literal[0] = 0
    prior_set_hash: str = Field(min_length=1)
    selected_set_hash: str = Field(min_length=1)


class CalibrationFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    channels: tuple[CalibrationFreshnessChannel, ...] = Field(min_length=9, max_length=9)
    calibration_task_count: Literal[31] = CALIBRATION_TASK_COUNT
    calibration_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    historical_task_record_count: int = Field(ge=1)
    historical_job_identity_count: int = Field(ge=1)
    v26_90_role_task_count: Literal[24] = 24
    historical_model_outcomes_used: Literal[False] = False
    role_tasks_used_for_calibration: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_91_FRESHNESS_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CalibrationFreshnessAudit:
        if tuple(item.channel for item in self.channels) != FRESHNESS_CHANNELS:
            raise ValueError("calibration freshness channels changed")
        if self.audit_id != calibration_freshness_audit_id(self):
            raise ValueError("calibration freshness audit identity is invalid")
        return self


class BudgetShapeCoverageCell(FrozenModel):
    mechanism_id: TargetMechanism
    path_strategy_id: PathStrategy
    role_prefix_envelope_id: str = Field(min_length=1)
    role_maximum_path_upper_bound: int = Field(ge=1)
    calibration_job_count: int = Field(ge=2)
    calibration_minimum_path_upper_bound: int = Field(ge=1)
    calibration_maximum_path_upper_bound: int = Field(ge=1)
    minimum_prefix_margin: int = Field(ge=PREFIX_STRESS_MARGIN)
    every_job_dominates_every_role_prefix: Literal[True] = True


class BudgetShapeCoverageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    cells: tuple[BudgetShapeCoverageCell, ...] = Field(
        min_length=ROLE_PREFIX_ENVELOPE_COUNT,
        max_length=ROLE_PREFIX_ENVELOPE_COUNT,
    )
    cell_count: Literal[12] = ROLE_PREFIX_ENVELOPE_COUNT
    calibration_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    covered_mechanism_count: Literal[4] = 4
    covered_path_strategy_count: Literal[3] = 3
    every_cell_covered: Literal[True] = True
    every_job_prefix_dominates_role_envelope: Literal[True] = True
    maximum_calibration_path_upper_bound: int = Field(ge=1, le=120000)
    minimum_calibration_headroom_tokens: int = Field(ge=0)
    status: Literal["passed"] = "passed"
    schema_version: str = V26_91_COVERAGE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetShapeCoverageAudit:
        keys = tuple((item.mechanism_id, item.path_strategy_id) for item in self.cells)
        expected = tuple(
            sorted(
                (mechanism, path)
                for mechanism in TARGET_MECHANISMS
                for path in CALIBRATION_PATH_STRATEGIES
            )
        )
        if keys != expected:
            raise ValueError("calibration budget-shape cells changed")
        if self.audit_id != budget_shape_coverage_audit_id(self):
            raise ValueError("Budget Shape Coverage Audit identity is invalid")
        return self


class DestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=10)
    rejected_mutation_count: int = Field(ge=10)
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_91_DESTRUCTIVE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DestructivePreflightAudit:
        if self.rejected_mutation_count != len(self.mutation_results):
            raise ValueError("destructive preflight denominator changed")
        if self.audit_id != destructive_preflight_audit_id(self):
            raise ValueError("destructive preflight identity is invalid")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ThinkingBudgetCalibrationPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_replay_audit_id: str = Field(min_length=1)
    source_capacity_audit_id: str = Field(min_length=1)
    calibration_contract_id: str = Field(min_length=1)
    calibration_manifest_id: str = Field(min_length=1)
    calibration_freshness_audit_id: str = Field(min_length=1)
    budget_shape_coverage_audit_id: str = Field(min_length=1)
    thinking_continuity_contract_id: str = Field(min_length=1)
    thinking_continuity_fixture_audit_id: str = Field(min_length=1)
    completion_usability_contract_id: str = Field(min_length=1)
    completion_usability_fixture_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    calibration_task_count: Literal[31] = CALIBRATION_TASK_COUNT
    calibration_job_count: Literal[32] = CALIBRATION_JOB_COUNT
    base_compiler_path_count: Literal[93] = BASE_COMPILER_PATH_COUNT
    stress_path_count: Literal[32] = CALIBRATION_JOB_COUNT
    role_prefix_envelope_count: Literal[12] = ROLE_PREFIX_ENVELOPE_COUNT
    predecessor_replayed_file_count: int = Field(ge=100)
    maximum_calibration_path_upper_bound: int = Field(ge=1, le=120000)
    minimum_calibration_headroom_tokens: int = Field(ge=0)
    maximum_calibration_prompt_utf8_bytes: int = Field(ge=1, le=60000)
    model_config_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=20)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=20)
    formal_independent_rebuild_required: Literal[True] = True
    empirical_result_count: Literal[0] = 0
    calibration_execution_completed: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    calibration_execution_authorized: Literal[True] = True
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["thinking_budget_calibration_execution_only"] = (
        "thinking_budget_calibration_execution_only"
    )
    schema_version: str = V26_91_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ThinkingBudgetCalibrationPreflightReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("preflight detail files are not canonical")
        if self.report_id != thinking_budget_calibration_preflight_report_id(self):
            raise ValueError("Thinking Budget Calibration Preflight report identity is invalid")
        return self


def _identity(value: BaseModel, *, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def predecessor_replay_audit_id(value: PredecessorReplayAudit) -> str:
    return _identity(
        value, field="audit_id", prefix="finance_v26_thinking_calibration_source_replay:"
    )


def calibration_source_selection_row_id(value: CalibrationSourceSelectionRow) -> str:
    return _identity(value, field="row_id", prefix="finance_v26_thinking_calibration_source_row:")


def calibration_source_capacity_audit_id(value: CalibrationSourceCapacityAudit) -> str:
    return _identity(
        value, field="audit_id", prefix="finance_v26_thinking_calibration_source_capacity:"
    )


def role_prefix_budget_envelope_id(value: RolePrefixBudgetEnvelope) -> str:
    return _identity(value, field="envelope_id", prefix="finance_v26_role_prefix_budget_envelope:")


def calibration_stress_path_audit_id(value: CalibrationStressPathAudit) -> str:
    return _identity(value, field="audit_id", prefix="finance_v26_calibration_stress_path:")


def calibration_task_package_id(value: CalibrationTaskPackage) -> str:
    return _identity(value, field="task_package_id", prefix="finance_v26_calibration_task_package:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(
        value, field="mutation_id", prefix="finance_v26_thinking_calibration_mutation:"
    )


def thinking_continuity_fixture_audit_id(value: ThinkingContinuityFixtureAudit) -> str:
    return _identity(
        value, field="audit_id", prefix="finance_v26_thinking_continuity_fixture_audit:"
    )


def completion_usability_contract_id(value: CompletionUsabilityContract) -> str:
    return _identity(
        value, field="contract_id", prefix="finance_v26_completion_usability_contract:"
    )


def completion_usability_fixture_audit_id(value: CompletionUsabilityFixtureAudit) -> str:
    return _identity(
        value, field="audit_id", prefix="finance_v26_completion_usability_fixture_audit:"
    )


def thinking_budget_calibration_contract_id(value: ThinkingBudgetCalibrationContract) -> str:
    return _identity(
        value, field="contract_id", prefix="finance_v26_thinking_budget_calibration_contract:"
    )


def thinking_budget_calibration_job_id(value: ThinkingBudgetCalibrationJob) -> str:
    return _identity(value, field="job_id", prefix="finance_v26_thinking_budget_calibration_job:")


def thinking_budget_calibration_manifest_id(value: ThinkingBudgetCalibrationManifest) -> str:
    return _identity(
        value, field="manifest_id", prefix="finance_v26_thinking_budget_calibration_manifest:"
    )


def calibration_freshness_audit_id(value: CalibrationFreshnessAudit) -> str:
    return _identity(
        value, field="audit_id", prefix="finance_v26_thinking_budget_calibration_freshness:"
    )


def budget_shape_coverage_audit_id(value: BudgetShapeCoverageAudit) -> str:
    return _identity(value, field="audit_id", prefix="finance_v26_thinking_budget_shape_coverage:")


def destructive_preflight_audit_id(value: DestructivePreflightAudit) -> str:
    return _identity(
        value, field="audit_id", prefix="finance_v26_thinking_calibration_destructive_preflight:"
    )


def thinking_budget_calibration_preflight_report_id(
    value: ThinkingBudgetCalibrationPreflightReport,
) -> str:
    return _identity(
        value, field="report_id", prefix="finance_v26_thinking_budget_calibration_preflight_report:"
    )


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _write_models(
    path: Path,
    values: Sequence[BaseModel],
    identity_field: str,
) -> None:
    ordered = sorted(values, key=lambda item: str(getattr(item, identity_field)))
    _write_json(path, [item.model_dump(mode="json") for item in ordered])


def _rows(path: Path, model: type[BaseModel]) -> tuple[BaseModel, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def _detail(path: Path, output_dir: Path, count: int) -> DetailFile:
    return DetailFile(
        relative_path=path.relative_to(output_dir).as_posix(),
        sha256=_sha256(path),
        record_count=count,
    )


def _replay_predecessor(
    package_root: Path,
) -> tuple[BudgetFeasibleRoleRematerializationReport, PredecessorReplayAudit]:
    predecessor_dir = package_root / V26_90_DIR
    report_path = predecessor_dir / "report.json"
    report = BudgetFeasibleRoleRematerializationReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    if report.next_permitted_stage != "thinking_budget_calibration_preflight_only":
        raise ValueError("v26.90 does not authorize a Thinking Budget Calibration preflight")
    entries: list[ReplayEntry] = []

    def append(relative_path: str, expected: str, kind: str, path: Path) -> None:
        entries.append(
            ReplayEntry(
                relative_path=relative_path,
                expected_sha256=expected,
                observed_sha256=_sha256(path),
                source_kind=cast(Any, kind),
            )
        )

    append(
        f"{V26_90_DIR}/report.json",
        _sha256(report_path),
        "v26_90_report",
        report_path,
    )
    for item in report.immutable_artifact_files:
        append(
            f"{V26_90_DIR}/{item.relative_path}",
            item.sha256,
            "v26_90_detail",
            predecessor_dir / item.relative_path,
        )
    for item in report.source_artifact_files:
        append(
            item.relative_path,
            item.sha256,
            "v26_90_source",
            package_root / item.relative_path,
        )
    for item in report.implementation_source_files:
        append(
            item.relative_path,
            item.sha256,
            "v26_90_implementation",
            package_root / item.relative_path,
        )
    ordered = tuple(sorted(entries, key=lambda item: (item.source_kind, item.relative_path)))
    values = {
        "predecessor_report_id": report.report_id,
        "entries": ordered,
        "replayed_file_count": len(ordered),
    }
    provisional = PredecessorReplayAudit.model_construct(audit_id="pending", **values)
    return report, PredecessorReplayAudit(
        audit_id=predecessor_replay_audit_id(provisional),
        **values,
    )


def _selection_rank(
    task: CapabilitySensitiveTaskArtifact,
    mechanism: TargetMechanism,
    selection_salt: str,
) -> str:
    return canonical_hash(
        {
            "selection_salt": selection_salt,
            "mechanism": mechanism,
            "source_task_artifact_id": task.artifact_id,
        },
        prefix="finance_v26_thinking_calibration_source_rank:",
    )


def _load_selection_inputs(
    package_root: Path,
) -> tuple[
    tuple[CapabilitySensitiveFrontierPopulation, ...],
    dict[str, set[str]],
    tuple[OperationalTaskRecord, ...],
    tuple[BudgetFeasibleRoleTaskPackage, ...],
    set[str],
    int,
    int,
]:
    sources = tuple(_load_population(package_root / item) for item in SOURCE_POPULATION_PATHS)
    all_tasks = tuple(task for source in sources for task in source.tasks)
    source_by_id = {task.artifact_id: task for task in all_tasks}
    development = V26FreshTaskPopulation.model_validate_json(
        (package_root / DEVELOPMENT_POPULATION_PATH).read_text(encoding="utf-8")
    )
    development_tasks = load_v26_selected_source_tasks(development)
    historical_records, _ = _load_historical_records(package_root)
    historical_job_ids, manifest_package_ids, _ = _load_historical_manifest_values(package_root)
    role_dir = package_root / V26_90_DIR
    role_records = cast(
        tuple[OperationalTaskRecord, ...],
        _rows(role_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    role_packages = cast(
        tuple[BudgetFeasibleRoleTaskPackage, ...],
        _rows(role_dir / "budget_feasible_role_task_packages.json", BudgetFeasibleRoleTaskPackage),
    )
    historical_source_ids = {
        source_id for record in historical_records for source_id in record.source_task_artifact_ids
    }
    role_source_ids = {
        source_id for record in role_records for source_id in record.source_task_artifact_ids
    }
    prior_source_tasks = tuple(
        source_by_id[source_id]
        for source_id in sorted(historical_source_ids | role_source_ids)
        if source_id in source_by_id
    )
    source_prior = _source_task_values((*development_tasks, *prior_source_tasks))
    source_prior_extended = {
        **source_prior,
        "semantic_source_id": set(),
        "task_package_id": set(),
        "job_id": set(),
    }
    record_prior = _record_values((*historical_records, *role_records))
    prior_values = _merge_channel_values(source_prior_extended, record_prior)
    prior_values["job_id"].update(historical_job_ids)
    prior_values["task_package_id"].update(manifest_package_ids)
    prior_values["task_package_id"].update(item.task_package_id for item in role_packages)
    return (
        sources,
        prior_values,
        role_records,
        role_packages,
        historical_job_ids,
        len(historical_records),
        len(historical_job_ids),
    )


def _select_calibration_sources(
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    prior_values: Mapping[str, set[str]],
    selection_salt: str,
) -> tuple[
    dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]],
    CalibrationSourceCapacityAudit,
]:
    all_tasks = tuple(task for source in sources for task in source.tasks)
    family_by_mechanism = {
        **MECHANISM_SOURCE_FAMILY,
        "semantic_reconciliation": "finance.definition_reconciliation",
    }
    selected: dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]] = {}
    selected_values: dict[str, set[str]] = {channel: set() for channel in FRESHNESS_CHANNELS[:6]}
    eligible_counts: dict[TargetMechanism, int] = {}
    rows: list[CalibrationSourceSelectionRow] = []
    for mechanism in TARGET_MECHANISMS:
        eligible = []
        for task in all_tasks:
            if task.family != family_by_mechanism[mechanism]:
                continue
            try:
                _atomic_leaf_node(task)
            except ValueError:
                continue
            task_channel_values = _source_task_values((task,))
            if any(
                task_channel_values[channel] & prior_values[channel]
                for channel in FRESHNESS_CHANNELS[:6]
            ):
                continue
            eligible.append(task)
        eligible_counts[mechanism] = len(eligible)
        eligible.sort(key=lambda task: _selection_rank(task, mechanism, selection_salt))
        chosen = []
        for task in eligible:
            task_channel_values = _source_task_values((task,))
            if any(
                task_channel_values[channel] & selected_values[channel]
                for channel in FRESHNESS_CHANNELS[:6]
            ):
                continue
            chosen.append(task)
            for channel in FRESHNESS_CHANNELS[:6]:
                selected_values[channel].update(task_channel_values[channel])
            if len(chosen) == MECHANISM_TASK_COUNTS[mechanism]:
                break
        if len(chosen) != MECHANISM_TASK_COUNTS[mechanism]:
            raise ValueError(f"fresh calibration source capacity failed for {mechanism}")
        selected[mechanism] = tuple(chosen)
        for task in chosen:
            row_values: dict[str, object] = {
                "mechanism_id": mechanism,
                "source_task_artifact_id": task.artifact_id,
                "source_task_hash": task.task.task_hash,
                "rank_hash": _selection_rank(task, mechanism, selection_salt),
            }
            provisional = CalibrationSourceSelectionRow.model_construct(
                row_id="pending", **row_values
            )
            rows.append(
                CalibrationSourceSelectionRow(
                    row_id=calibration_source_selection_row_id(provisional),
                    **row_values,
                )
            )
    ordered_rows = tuple(sorted(rows, key=lambda item: item.row_id))
    audit_values: dict[str, object] = {
        "eligible_counts": eligible_counts,
        "selected_counts": dict(MECHANISM_TASK_COUNTS),
        "selected_rows": ordered_rows,
        "selection_salt": selection_salt,
    }
    provisional = CalibrationSourceCapacityAudit.model_construct(audit_id="pending", **audit_values)
    return selected, CalibrationSourceCapacityAudit(
        audit_id=calibration_source_capacity_audit_id(provisional),
        **audit_values,
    )


def _make_role_prefix_envelopes(
    role_paths: Sequence[BudgetQualifiedPathAudit],
) -> tuple[RolePrefixBudgetEnvelope, ...]:
    grouped: dict[tuple[TargetMechanism, PathStrategy], list[BudgetQualifiedPathAudit]] = (
        defaultdict(list)
    )
    for item in role_paths:
        grouped[(item.mechanism_id, item.path_strategy_id)].append(item)
    output = []
    for mechanism in TARGET_MECHANISMS:
        for strategy in CALIBRATION_PATH_STRATEGIES:
            rows = grouped[(mechanism, strategy)]
            request_counts = {item.request_count for item in rows}
            if len(request_counts) != 1:
                raise ValueError("Role cell has inconsistent request counts")
            request_count = next(iter(request_counts))
            prefix_bounds = tuple(
                max(item.request_bounds[index].projected_path_upper_bound for item in rows)
                for index in range(request_count)
            )
            values = {
                "mechanism_id": mechanism,
                "path_strategy_id": strategy,
                "source_role_path_audit_ids": tuple(sorted(item.audit_id for item in rows)),
                "source_role_path_count": len(rows),
                "request_count": request_count,
                "maximum_role_prefix_bounds": prefix_bounds,
                "maximum_role_path_upper_bound": max(prefix_bounds),
            }
            provisional = RolePrefixBudgetEnvelope.model_construct(
                envelope_id="pending",
                **values,
            )
            output.append(
                RolePrefixBudgetEnvelope(
                    envelope_id=role_prefix_budget_envelope_id(provisional),
                    **values,
                )
            )
    return tuple(sorted(output, key=lambda item: (item.mechanism_id, item.path_strategy_id)))


def _stress_path(
    *,
    source_task_artifact_id: str,
    record: OperationalTaskRecord,
    prompt_contract: CompactPromptContract,
    observations: tuple[AgentToolObservation, ...],
    strategy: PathStrategy,
    base_path: BudgetQualifiedPathAudit,
    envelope: RolePrefixBudgetEnvelope,
    provider_contract: ProviderTokenBudgetContract,
) -> CalibrationStressPathAudit:
    prompts = render_compact_witness_prompts(
        prompt_contract.public_context,
        record.task_package.task.public,
        observations,
        public_path_condition=strategy,
    )
    if len(prompts) != envelope.request_count:
        raise ValueError("calibration path request count differs from Role envelope")
    cumulative = 0
    rows = []
    for index, prompt in enumerate(prompts):
        request_kind, repaired_kind = _provider_request_kind(prompt)
        if request_kind in {"unknown", "contract_repair"} or repaired_kind is not None:
            raise ValueError("calibration stress path has an unknown request kind")
        prompt_bytes = len(prompt.encode("utf-8"))
        base_request = (
            prompt_bytes
            + provider_contract.provider_chat_envelope_token_upper_bound
            + provider_contract.maximum_output_tokens
        )
        repair_reserve, final_reserve = _required_reserves(
            request_kind,
            None,
            provider_contract,
        )
        reserve = repair_reserve + final_reserve
        unpadded_projected = cumulative + base_request + reserve
        required = envelope.maximum_role_prefix_bounds[index] + PREFIX_STRESS_MARGIN
        padding = max(0, required - unpadded_projected)
        padded_prompt = prompt + (" " * padding)
        padded_bytes = len(padded_prompt.encode("utf-8"))
        request_upper = (
            padded_bytes
            + provider_contract.provider_chat_envelope_token_upper_bound
            + provider_contract.maximum_output_tokens
        )
        cumulative += request_upper
        projected = cumulative + reserve
        rows.append(
            PrefixStressRow(
                request_index=index,
                request_kind=request_kind,
                unpadded_prompt_sha256=_sha256_text(prompt),
                padded_prompt_sha256=_sha256_text(padded_prompt),
                unpadded_prompt_utf8_bytes=prompt_bytes,
                trailing_ascii_space_padding_bytes=padding,
                padded_prompt_utf8_bytes=padded_bytes,
                role_prefix_upper_bound=envelope.maximum_role_prefix_bounds[index],
                required_prefix_upper_bound=required,
                calibration_prefix_upper_bound=projected,
                coverage_margin_tokens=(projected - envelope.maximum_role_prefix_bounds[index]),
                prompt_ceiling_passed=(padded_bytes <= provider_contract.maximum_prompt_utf8_bytes),
                rollout_ceiling_passed=(projected <= provider_contract.maximum_total_tokens),
            )
        )
    stress_rows = tuple(rows)
    if not all(item.prompt_ceiling_passed and item.rollout_ceiling_passed for item in stress_rows):
        raise ValueError("calibration stress path exceeds the frozen budget")
    values = {
        "operational_task_package_id": record.task_package.package_id,
        "source_task_artifact_id": source_task_artifact_id,
        "mechanism_id": record.mechanism_id,
        "path_strategy_id": strategy,
        "base_path_audit_id": base_path.audit_id,
        "role_prefix_envelope_id": envelope.envelope_id,
        "rows": stress_rows,
        "request_count": len(stress_rows),
        "maximum_path_upper_bound": max(
            item.calibration_prefix_upper_bound for item in stress_rows
        ),
        "minimum_headroom_tokens": (
            provider_contract.maximum_total_tokens
            - max(item.calibration_prefix_upper_bound for item in stress_rows)
        ),
        "maximum_prompt_utf8_bytes": max(item.padded_prompt_utf8_bytes for item in stress_rows),
        "minimum_prefix_coverage_margin": min(item.coverage_margin_tokens for item in stress_rows),
    }
    provisional = CalibrationStressPathAudit.model_construct(audit_id="pending", **values)
    return CalibrationStressPathAudit(
        audit_id=calibration_stress_path_audit_id(provisional),
        **values,
    )


def _make_completion_contract() -> CompletionUsabilityContract:
    provisional = CompletionUsabilityContract.model_construct(contract_id="pending")
    return CompletionUsabilityContract(contract_id=completion_usability_contract_id(provisional))


def _fixture_telemetry(
    index: int,
    *,
    http_success: bool = True,
    json_success: bool = True,
    finish_reason: str = "stop",
    reasoning_present: bool = True,
    response_length: int = 12,
) -> ModelCallTelemetry:
    reasoning_length = 24 if reasoning_present else 0
    reasoning_tokens = 8 if reasoning_present else 0
    completion_tokens = 12
    return ModelCallTelemetry(
        provider="deepseek",
        endpoint_host="api.deepseek.com",
        model_requested="deepseek-v4-flash",
        model_selected="deepseek-v4-flash",
        response_model="deepseek-v4-flash",
        request_hash=hashlib.sha256(f"request-{index}".encode()).hexdigest(),
        response_hash=hashlib.sha256(f"response-{index}".encode()).hexdigest(),
        http_status=200 if http_success else None,
        http_success=http_success,
        json_contract_success=json_success,
        finish_reason=finish_reason,
        response_content_length=response_length,
        reasoning_content_present=reasoning_present,
        reasoning_content_length=reasoning_length,
        reasoning_tokens=reasoning_tokens,
        prompt_tokens=20,
        completion_tokens=completion_tokens,
        total_tokens=32,
    )


def _mutation(kind: str, callback: Any) -> MutationResult:
    try:
        callback()
    except (ValueError, ValidationError, TypeError) as exc:
        values = {
            "mutation_kind": kind,
            "rejection_type": type(exc).__name__,
        }
        provisional = MutationResult.model_construct(mutation_id="pending", **values)
        return MutationResult(
            mutation_id=mutation_result_id(provisional),
            **values,
        )
    raise ValueError(f"destructive mutation unexpectedly passed: {kind}")


def _make_continuity_fixture(
    contract: ThinkingContinuityContract,
) -> ThinkingContinuityFixtureAudit:
    turns = []
    parent = None
    for index in range(3):
        turn = attest_thinking_turn(
            contract=contract,
            call_index=index,
            telemetry=_fixture_telemetry(index),
            parent_attestation_id=parent,
        )
        turns.append(turn)
        parent = turn.attestation_id
    history = audit_thinking_history(contract, tuple(turns))
    history_payload = history.model_dump(mode="json")
    mutations = (
        _mutation(
            "thinking_history_out_of_order",
            lambda: ThinkingHistoryAudit.model_validate(
                {**history_payload, "turns": list(reversed(history_payload["turns"]))}
            ),
        ),
        _mutation(
            "thinking_history_missing_parent",
            lambda: ThinkingHistoryAudit.model_validate(
                {
                    **history_payload,
                    "turns": [
                        history_payload["turns"][0],
                        {**history_payload["turns"][1], "parent_attestation_id": None},
                        history_payload["turns"][2],
                    ],
                }
            ),
        ),
        _mutation(
            "provider_native_tool_call",
            lambda: attest_thinking_turn(
                contract=contract,
                call_index=0,
                telemetry=_fixture_telemetry(20),
                parent_attestation_id=None,
                provider_native_tool_call_observed=True,
            ),
        ),
        _mutation(
            "thinking_response_without_reasoning",
            lambda: attest_thinking_turn(
                contract=contract,
                call_index=0,
                telemetry=_fixture_telemetry(21, reasoning_present=False),
                parent_attestation_id=None,
            ),
        ),
        _mutation(
            "thinking_response_without_reasoning_usage",
            lambda: attest_thinking_turn(
                contract=contract,
                call_index=0,
                telemetry=ModelCallTelemetry.model_validate(
                    {
                        **_fixture_telemetry(22).model_dump(mode="json"),
                        "reasoning_tokens": None,
                    }
                ),
                parent_attestation_id=None,
            ),
        ),
        _mutation(
            "private_reasoning_content_persistence",
            lambda: type(turns[0]).model_validate(
                {**turns[0].model_dump(mode="json"), "reasoning_content": "forbidden"}
            ),
        ),
    )
    values = {
        "continuity_contract_id": contract.contract_id,
        "history_audit": history,
        "mutation_results": mutations,
        "rejected_mutation_count": len(mutations),
    }
    provisional = ThinkingContinuityFixtureAudit.model_construct(audit_id="pending", **values)
    return ThinkingContinuityFixtureAudit(
        audit_id=thinking_continuity_fixture_audit_id(provisional),
        **values,
    )


def _make_completion_fixture(
    contract: CompletionUsabilityContract,
) -> CompletionUsabilityFixtureAudit:
    classifications = (
        classify_completion_usability(request_index=0, telemetry=None, typed_no_call=True),
        classify_completion_usability(
            request_index=1,
            telemetry=_fixture_telemetry(1, http_success=False),
        ),
        classify_completion_usability(
            request_index=2,
            telemetry=_fixture_telemetry(2, reasoning_present=False),
        ),
        classify_completion_usability(
            request_index=3,
            telemetry=_fixture_telemetry(2, finish_reason="length", response_length=0),
            final_content_present=False,
        ),
        classify_completion_usability(
            request_index=4,
            telemetry=_fixture_telemetry(3, finish_reason="length"),
        ),
        classify_completion_usability(
            request_index=5,
            telemetry=_fixture_telemetry(4, response_length=0),
            final_content_present=False,
        ),
        classify_completion_usability(
            request_index=6,
            telemetry=_fixture_telemetry(5, json_success=False),
            contract_repair_attempted=True,
        ),
        classify_completion_usability(
            request_index=7,
            telemetry=_fixture_telemetry(6),
            decision_contract_valid=False,
            contract_repair_attempted=True,
        ),
        classify_completion_usability(
            request_index=8,
            telemetry=_fixture_telemetry(7),
            contract_repair_attempted=True,
            contract_repair_succeeded=True,
        ),
        classify_completion_usability(
            request_index=9,
            telemetry=_fixture_telemetry(8),
        ),
    )
    first = classifications[0].model_dump(mode="json")
    mutations = (
        _mutation(
            "typed_no_call_with_provider_call",
            lambda: CompletionUsabilityClassification.model_validate(
                {**first, "provider_call_made": True}
            ),
        ),
        _mutation(
            "typed_no_call_in_completion_denominator",
            lambda: CompletionUsabilityClassification.model_validate(
                {**first, "completion_unusable": True}
            ),
        ),
    )
    values = {
        "completion_usability_contract_id": contract.contract_id,
        "classifications": classifications,
        "outcome_counts": dict(
            sorted(Counter(item.completion_outcome for item in classifications).items())
        ),
        "mutation_results": mutations,
    }
    provisional = CompletionUsabilityFixtureAudit.model_construct(audit_id="pending", **values)
    return CompletionUsabilityFixtureAudit(
        audit_id=completion_usability_fixture_audit_id(provisional),
        **values,
    )


def _cp_upper(failures: int, jobs: int, alpha: float = 0.05) -> float:
    if failures < 0 or failures > jobs:
        raise ValueError("invalid Clopper-Pearson denominator")
    if failures == jobs:
        return 1.0

    def cdf(probability: float) -> float:
        return sum(
            math.comb(jobs, index) * probability**index * (1 - probability) ** (jobs - index)
            for index in range(failures + 1)
        )

    lower = 0.0
    upper = 1.0
    for _ in range(120):
        candidate = (lower + upper) / 2
        if cdf(candidate) > alpha:
            lower = candidate
        else:
            upper = candidate
    return (lower + upper) / 2


def _selected_values(
    tasks: Sequence[CapabilitySensitiveTaskArtifact],
    records: Sequence[OperationalTaskRecord],
    packages: Sequence[CalibrationTaskPackage],
    jobs: Sequence[ThinkingBudgetCalibrationJob],
) -> dict[str, set[str]]:
    source = _source_task_values(tasks)
    record = _record_values(records)
    merged = _merge_channel_values(
        {
            **source,
            "semantic_source_id": set(),
            "task_package_id": set(),
            "job_id": set(),
        },
        record,
    )
    merged["task_package_id"].update(item.task_package_id for item in packages)
    merged["job_id"].update(item.job_id for item in jobs)
    return merged


def _make_freshness_audit(
    *,
    prior_values: Mapping[str, set[str]],
    selected_tasks: Sequence[CapabilitySensitiveTaskArtifact],
    records: Sequence[OperationalTaskRecord],
    packages: Sequence[CalibrationTaskPackage],
    jobs: Sequence[ThinkingBudgetCalibrationJob],
    historical_record_count: int,
    historical_job_count: int,
) -> CalibrationFreshnessAudit:
    selected = _selected_values(selected_tasks, records, packages, jobs)
    selected_source_values = _source_task_values(selected_tasks)
    expected_counts = {
        **{channel: len(selected_source_values[channel]) for channel in FRESHNESS_CHANNELS[:6]},
        "semantic_source_id": CALIBRATION_TASK_COUNT,
        "task_package_id": CALIBRATION_TASK_COUNT * 2,
        "job_id": CALIBRATION_JOB_COUNT,
    }
    channels = []
    for channel in FRESHNESS_CHANNELS:
        values = selected[channel]
        expected_count = expected_counts[channel]
        if len(values) != expected_count:
            raise ValueError(
                f"calibration internal freshness failed for {channel}: "
                f"{len(values)} != {expected_count}"
            )
        overlap = values & prior_values[channel]
        if overlap:
            raise ValueError(f"calibration historical overlap on {channel}")
        channels.append(
            CalibrationFreshnessChannel(
                channel=channel,
                prior_count=len(prior_values[channel]),
                selected_count=len(values),
                prior_set_hash=canonical_hash(
                    sorted(prior_values[channel]),
                    prefix=f"finance_v26_calibration_prior_{channel}:",
                ),
                selected_set_hash=canonical_hash(
                    sorted(values),
                    prefix=f"finance_v26_calibration_selected_{channel}:",
                ),
            )
        )
    audit_values: dict[str, object] = {
        "channels": tuple(channels),
        "historical_task_record_count": historical_record_count,
        "historical_job_identity_count": historical_job_count,
    }
    provisional = CalibrationFreshnessAudit.model_construct(audit_id="pending", **audit_values)
    return CalibrationFreshnessAudit(
        audit_id=calibration_freshness_audit_id(provisional),
        **audit_values,
    )


def _make_coverage_audit(
    envelopes: Sequence[RolePrefixBudgetEnvelope],
    stress_paths: Sequence[CalibrationStressPathAudit],
) -> BudgetShapeCoverageAudit:
    envelope_by_key = {(item.mechanism_id, item.path_strategy_id): item for item in envelopes}
    grouped: dict[tuple[TargetMechanism, PathStrategy], list[CalibrationStressPathAudit]] = (
        defaultdict(list)
    )
    for item in stress_paths:
        grouped[(item.mechanism_id, item.path_strategy_id)].append(item)
    cells = []
    for key in sorted(envelope_by_key):
        envelope = envelope_by_key[key]
        rows = grouped[key]
        if len(rows) != CELL_JOB_COUNTS[f"{key[0]}:{key[1]}"]:
            raise ValueError("calibration budget-shape Job cell changed")
        cells.append(
            BudgetShapeCoverageCell(
                mechanism_id=key[0],
                path_strategy_id=key[1],
                role_prefix_envelope_id=envelope.envelope_id,
                role_maximum_path_upper_bound=envelope.maximum_role_path_upper_bound,
                calibration_job_count=len(rows),
                calibration_minimum_path_upper_bound=min(
                    item.maximum_path_upper_bound for item in rows
                ),
                calibration_maximum_path_upper_bound=max(
                    item.maximum_path_upper_bound for item in rows
                ),
                minimum_prefix_margin=min(item.minimum_prefix_coverage_margin for item in rows),
            )
        )
    values = {
        "cells": tuple(cells),
        "maximum_calibration_path_upper_bound": max(
            item.maximum_path_upper_bound for item in stress_paths
        ),
        "minimum_calibration_headroom_tokens": min(
            item.minimum_headroom_tokens for item in stress_paths
        ),
    }
    provisional = BudgetShapeCoverageAudit.model_construct(audit_id="pending", **values)
    return BudgetShapeCoverageAudit(
        audit_id=budget_shape_coverage_audit_id(provisional),
        **values,
    )


def _make_destructive_audit(
    *,
    continuity_contract: ThinkingContinuityContract,
    completion_contract: CompletionUsabilityContract,
    calibration_contract: ThinkingBudgetCalibrationContract,
    manifest: ThinkingBudgetCalibrationManifest,
    freshness: CalibrationFreshnessAudit,
    coverage: BudgetShapeCoverageAudit,
    stress_path: CalibrationStressPathAudit,
    task_package: CalibrationTaskPackage,
) -> DestructivePreflightAudit:
    contract_payload = calibration_contract.model_dump(mode="json")
    manifest_payload = manifest.model_dump(mode="json")
    freshness_payload = freshness.model_dump(mode="json")
    coverage_payload = coverage.model_dump(mode="json")
    stress_payload = stress_path.model_dump(mode="json")
    task_payload = task_package.model_dump(mode="json")
    continuity_payload = continuity_contract.model_dump(mode="json")
    completion_payload = completion_contract.model_dump(mode="json")
    mutations = (
        _mutation(
            "provider_native_tool_calls_enabled",
            lambda: ThinkingContinuityContract.model_validate(
                {**continuity_payload, "provider_native_tool_calls_allowed": True}
            ),
        ),
        _mutation(
            "private_reasoning_hash_enabled",
            lambda: ThinkingContinuityContract.model_validate(
                {**continuity_payload, "private_reasoning_content_hashed": True}
            ),
        ),
        _mutation(
            "completion_no_call_conflation",
            lambda: CompletionUsabilityContract.model_validate(
                {
                    **completion_payload,
                    "typed_no_call_and_completion_unusable_separate": False,
                }
            ),
        ),
        _mutation(
            "completion_threshold_relaxation",
            lambda: CompletionUsabilityContract.model_validate(
                {**completion_payload, "minimum_job_count": 31}
            ),
        ),
        _mutation(
            "completion_cp_boundary_change",
            lambda: CompletionUsabilityContract.model_validate(
                {**completion_payload, "zero_failure_cp95_upper_bound_at_32": 0.09}
            ),
        ),
        _mutation(
            "calibration_cell_ablation",
            lambda: ThinkingBudgetCalibrationContract.model_validate(
                {
                    **contract_payload,
                    "mechanism_path_job_counts": {
                        **contract_payload["mechanism_path_job_counts"],
                        "semantic_reconciliation:search_then_open": 3,
                    },
                }
            ),
        ),
        _mutation(
            "calibration_preflight_execution",
            lambda: ThinkingBudgetCalibrationContract.model_validate(
                {**contract_payload, "execution_permitted_during_preflight": True}
            ),
        ),
        _mutation(
            "calibration_job_ablation",
            lambda: ThinkingBudgetCalibrationManifest.model_validate(
                {**manifest_payload, "jobs": manifest_payload["jobs"][:-1], "job_count": 31}
            ),
        ),
        _mutation(
            "calibration_duplicate_job",
            lambda: ThinkingBudgetCalibrationManifest.model_validate(
                {
                    **manifest_payload,
                    "jobs": [
                        *manifest_payload["jobs"][:-1],
                        manifest_payload["jobs"][0],
                    ],
                }
            ),
        ),
        _mutation(
            "calibration_historical_overlap",
            lambda: CalibrationFreshnessAudit.model_validate(
                {
                    **freshness_payload,
                    "channels": [
                        {**freshness_payload["channels"][0], "prior_overlap_count": 1},
                        *freshness_payload["channels"][1:],
                    ],
                }
            ),
        ),
        _mutation(
            "budget_shape_cell_ablation",
            lambda: BudgetShapeCoverageAudit.model_validate(
                {**coverage_payload, "cells": coverage_payload["cells"][:-1], "cell_count": 11}
            ),
        ),
        _mutation(
            "prefix_padding_stale_identity",
            lambda: CalibrationStressPathAudit.model_validate(
                {
                    **stress_payload,
                    "rows": [
                        {
                            **stress_payload["rows"][0],
                            "trailing_ascii_space_padding_bytes": (
                                stress_payload["rows"][0]["trailing_ascii_space_padding_bytes"] + 1
                            ),
                        },
                        *stress_payload["rows"][1:],
                    ],
                }
            ),
        ),
        _mutation(
            "calibration_role_eligibility",
            lambda: CalibrationTaskPackage.model_validate(
                {**task_payload, "capability_denominator_eligible": True}
            ),
        ),
    )
    values = {
        "mutation_results": mutations,
        "rejected_mutation_count": len(mutations),
    }
    provisional = DestructivePreflightAudit.model_construct(audit_id="pending", **values)
    return DestructivePreflightAudit(
        audit_id=destructive_preflight_audit_id(provisional),
        **values,
    )


def build_thinking_budget_calibration_preflight(
    *,
    run_id: str,
    selection_salt: str,
    output_dir: Path,
    package_root: Path,
) -> ThinkingBudgetCalibrationPreflightReport:
    predecessor, replay_audit = _replay_predecessor(package_root)
    (
        sources,
        prior_values,
        role_records,
        role_packages,
        historical_job_ids,
        historical_record_count,
        historical_job_count,
    ) = _load_selection_inputs(package_root)
    selected, capacity_audit = _select_calibration_sources(
        sources,
        prior_values,
        selection_salt,
    )
    selected_tasks = tuple(task for mechanism in TARGET_MECHANISMS for task in selected[mechanism])
    role_dir = package_root / V26_90_DIR
    role_paths = cast(
        tuple[BudgetQualifiedPathAudit, ...],
        _rows(role_dir / "budget_qualified_path_audits.json", BudgetQualifiedPathAudit),
    )
    envelopes = _make_role_prefix_envelopes(role_paths)
    envelope_by_key = {(item.mechanism_id, item.path_strategy_id): item for item in envelopes}
    _, predecessor_contract, provider_contract, _ = _load_predecessor(package_root)
    model_config, thinking_binding, _ = _load_thinking_binding(package_root)
    continuity_contract = make_thinking_continuity_contract()
    continuity_fixture = _make_continuity_fixture(continuity_contract)
    completion_contract = _make_completion_contract()
    completion_fixture = _make_completion_fixture(completion_contract)
    if _cp_upper(0, 32) > 0.10 or _cp_upper(1, 32) <= 0.10:
        raise ValueError("32-Job Clopper-Pearson boundary changed")

    qualification_dir = package_root / VERIFIER_QUALIFICATION_DIR
    qualification, replay_contract = _load_and_replay_verifier_qualification(
        qualification_dir,
        package_root,
    )
    qualification_sha256 = _sha256(qualification_dir / "report.json")

    records: list[OperationalTaskRecord] = []
    environments: list[AgentToolEnvironmentManifest] = []
    replay_bindings: list[VerifierV2TaskReplayBinding] = []
    prompt_contracts: list[CompactPromptContract] = []
    base_paths: list[BudgetQualifiedPathAudit] = []
    task_packages: list[CalibrationTaskPackage] = []
    witnesses = []
    observations: list[AgentToolObservation] = []
    closures: list[OperationClosureAudit] = []
    admissions: list[OperationalTaskAdmission] = []
    necessities = []
    counterfactuals: list[MechanismCounterfactualReplayRecord] = []
    catalogs = []
    authority_audits: list[AuthorityPreservingTaskAudit] = []
    replay_results = []
    compiler_trajectories = []
    compiler_scores: list[CompletedTrajectoryScore] = []
    histories_by_key: dict[tuple[str, PathStrategy], tuple[AgentToolObservation, ...]] = {}
    base_path_by_key: dict[tuple[str, PathStrategy], BudgetQualifiedPathAudit] = {}
    record_by_source: dict[str, OperationalTaskRecord] = {}
    prompt_by_source: dict[str, CompactPromptContract] = {}
    package_by_source: dict[str, CalibrationTaskPackage] = {}

    for mechanism in TARGET_MECHANISMS:
        for source_task in selected[mechanism]:
            draft = _role_draft(source_task, role="reachability", mechanism=mechanism)
            source_record, source_environment = _upgrade_task(draft)
            environment = _verifier_bound_environment(_harden_environment(source_environment))
            authority_record = _harden_record(source_record, environment)
            replay_binding = _task_replay_binding(
                authority_record,
                environment,
                qualification,
                qualification_sha256,
                replay_contract,
            )
            record = _bind_verifier_v2(authority_record, replay_binding)
            task_witnesses = []
            task_histories = []
            for strategy in CALIBRATION_PATH_STRATEGIES:
                witness, history = compile_operational_witness(
                    record,
                    environment,
                    strategy=strategy,
                )
                task_witnesses.append(witness)
                task_histories.append(history)
            necessity, task_counterfactuals, catalog = mechanism_necessity_and_catalog(
                record,
                task_witnesses,
            )
            closure = build_operation_closure_audit(
                record,
                task_witnesses,
                task_histories,
                necessity,
                catalog,
            )
            admission = build_operational_admission(
                record,
                task_witnesses[0],
                necessity,
                catalog,
                closure,
            )
            authority_audit = _task_audit(
                record,
                environment,
                task_witnesses[0],
                task_histories[0],
                necessity,
                closure,
            )
            prompt_contract = _make_compact_prompt_contract(
                role="reachability",
                record=record,
                environment=environment,
            )
            task_paths = []
            for strategy, witness, history in zip(
                CALIBRATION_PATH_STRATEGIES,
                task_witnesses,
                task_histories,
                strict=True,
            ):
                replay = replay_authority_preserving_observations(
                    replay_contract,
                    record,
                    environment,
                    history,
                )
                if not replay.passed:
                    raise ValueError("calibration Compiler path failed Verifier v2 Replay")
                trajectory = compiler_witness_trajectory(
                    record=record,
                    environment=environment,
                    witness=witness,
                    observations=history,
                )
                score = score_completed_trajectory(
                    trajectory=trajectory,
                    source_kind="compiler_fixture",
                    replay_result_id=replay.replay_id,
                    replay_passed=replay.passed,
                    non_replay_checks={
                        "action_neutral_repair": authority_audit.repair_prompt_audit.status
                        == "passed",
                        "answer_projection": witness.answer_projection_complete,
                        "citation": witness.citation_complete,
                        "evidence_support": witness.evidence_support_complete,
                        "mechanism": witness.mechanism_complete,
                        "no_postcompletion_violation": witness.no_postcompletion_violation,
                        "operation_lineage": witness.operation_lineage_complete,
                        "stop_readiness": authority_audit.runtime_witness_stop_ready,
                        "terminal_target": authority_audit.exact_terminal_reference_accepted,
                        "verification": witness.verification_complete,
                    },
                    independent_valid=witness.full_validity_passed,
                    resource_budget_audit_id=provider_contract.contract_id,
                    resource_budget_status="not_applicable_no_provider_calls",
                )
                if score.core_terminal != "valid_trajectory" or not score.instrument_admitted:
                    raise ValueError("calibration Compiler score failed")
                base_path = _make_budget_qualified_path(
                    role="reachability",
                    record=record,
                    prompt_contract=prompt_contract,
                    predecessor_contract=predecessor_contract,
                    provider_contract=provider_contract,
                    thinking_binding=thinking_binding,
                    strategy=strategy,
                    witness=witness,
                    trajectory_id=trajectory.trajectory_id,
                    observations=history,
                )
                task_paths.append(base_path)
                histories_by_key[(source_task.artifact_id, strategy)] = history
                base_path_by_key[(source_task.artifact_id, strategy)] = base_path
                witnesses.append(witness)
                observations.extend(history)
                base_paths.append(base_path)
                replay_results.append(replay)
                compiler_trajectories.append(trajectory)
                compiler_scores.append(score)
            package_values = {
                "source_task_artifact_id": source_task.artifact_id,
                "mechanism_id": mechanism,
                "operational_record_id": record.record_id,
                "operational_task_package_id": record.task_package.package_id,
                "semantic_source_id": record.task_package.semantic_source.semantic_source_id,
                "environment_manifest_id": environment.manifest_id,
                "verifier_replay_binding_id": replay_binding.contract_id,
                "compact_prompt_contract_id": prompt_contract.contract_id,
                "base_path_audit_ids": tuple(item.audit_id for item in task_paths),
            }
            provisional_package = CalibrationTaskPackage.model_construct(
                task_package_id="pending",
                **package_values,
            )
            package = CalibrationTaskPackage(
                task_package_id=calibration_task_package_id(provisional_package),
                **package_values,
            )
            records.append(record)
            environments.append(environment)
            replay_bindings.append(replay_binding)
            prompt_contracts.append(prompt_contract)
            task_packages.append(package)
            closures.append(closure)
            admissions.append(admission)
            necessities.append(necessity)
            counterfactuals.extend(task_counterfactuals)
            catalogs.append(catalog)
            authority_audits.append(authority_audit)
            record_by_source[source_task.artifact_id] = record
            prompt_by_source[source_task.artifact_id] = prompt_contract
            package_by_source[source_task.artifact_id] = package

    if len(records) != CALIBRATION_TASK_COUNT or len(base_paths) != BASE_COMPILER_PATH_COUNT:
        raise ValueError("calibration static task denominator is incomplete")
    population_id = canonical_hash(
        sorted(item.task_package_id for item in task_packages),
        prefix="finance_v26_thinking_budget_calibration_population:",
    )
    contract_values = {
        "predecessor_report_id": predecessor.report_id,
        "predecessor_replay_audit_id": replay_audit.audit_id,
        "budget_adequacy_contract_id": predecessor.predecessor_budget_adequacy_contract_id,
        "provider_budget_contract_id": predecessor.provider_budget_contract_id,
        "thinking_policy_id": predecessor.thinking_policy_id,
        "thinking_binding_id": thinking_binding.binding_id,
        "model_config_id": model_config.public_manifest_hash,
        "thinking_continuity_contract_id": continuity_contract.contract_id,
        "completion_usability_contract_id": completion_contract.contract_id,
        "calibration_population_id": population_id,
        "calibration_task_package_ids": tuple(
            sorted(item.task_package_id for item in task_packages)
        ),
        "role_prefix_envelope_ids": tuple(item.envelope_id for item in envelopes),
    }
    provisional_contract = ThinkingBudgetCalibrationContract.model_construct(
        contract_id="pending",
        **contract_values,
    )
    calibration_contract = ThinkingBudgetCalibrationContract(
        contract_id=thinking_budget_calibration_contract_id(provisional_contract),
        **contract_values,
    )

    stress_paths = []
    job_values = []
    for mechanism in TARGET_MECHANISMS:
        tasks = selected[mechanism]
        slots = MECHANISM_JOB_SLOTS[mechanism]
        for slot_index, strategy in enumerate(slots):
            source_task = tasks[slot_index % len(tasks)]
            record = record_by_source[source_task.artifact_id]
            prompt_contract = prompt_by_source[source_task.artifact_id]
            base_path = base_path_by_key[(source_task.artifact_id, strategy)]
            stress = _stress_path(
                source_task_artifact_id=source_task.artifact_id,
                record=record,
                prompt_contract=prompt_contract,
                observations=histories_by_key[(source_task.artifact_id, strategy)],
                strategy=strategy,
                base_path=base_path,
                envelope=envelope_by_key[(mechanism, strategy)],
                provider_contract=provider_contract,
            )
            stress_paths.append(stress)
            package = package_by_source[source_task.artifact_id]
            job_seed = int(
                hashlib.sha256(
                    f"{run_id}|{mechanism}|{strategy}|{slot_index}|{source_task.artifact_id}".encode()
                ).hexdigest()[:16],
                16,
            )
            job_values.append(
                {
                    "calibration_contract_id": calibration_contract.contract_id,
                    "calibration_task_package_id": package.task_package_id,
                    "source_task_artifact_id": source_task.artifact_id,
                    "operational_record_id": record.record_id,
                    "operational_task_package_id": record.task_package.package_id,
                    "environment_manifest_id": record.environment_manifest_id,
                    "mechanism_id": mechanism,
                    "path_strategy_id": strategy,
                    "stress_path_audit_id": stress.audit_id,
                    "job_seed": job_seed,
                    "model_config_id": model_config.public_manifest_hash,
                    "thinking_binding_id": thinking_binding.binding_id,
                    "thinking_continuity_contract_id": continuity_contract.contract_id,
                    "completion_usability_contract_id": completion_contract.contract_id,
                }
            )
    jobs = []
    for values in job_values:
        provisional_job = ThinkingBudgetCalibrationJob.model_construct(job_id="pending", **values)
        jobs.append(
            ThinkingBudgetCalibrationJob(
                job_id=thinking_budget_calibration_job_id(provisional_job),
                **values,
            )
        )
    ordered_jobs = tuple(sorted(jobs, key=lambda item: item.job_id))
    manifest_values = {
        "calibration_contract_id": calibration_contract.contract_id,
        "jobs": ordered_jobs,
        "historical_job_overlap_count": len(
            {item.job_id for item in ordered_jobs} & historical_job_ids
        ),
        "role_task_overlap_count": len(
            {item.calibration_task_package_id for item in ordered_jobs}
            & {item.task_package_id for item in role_packages}
        ),
    }
    provisional_manifest = ThinkingBudgetCalibrationManifest.model_construct(
        manifest_id="pending",
        **manifest_values,
    )
    manifest = ThinkingBudgetCalibrationManifest(
        manifest_id=thinking_budget_calibration_manifest_id(provisional_manifest),
        **manifest_values,
    )
    freshness = _make_freshness_audit(
        prior_values=prior_values,
        selected_tasks=selected_tasks,
        records=records,
        packages=task_packages,
        jobs=ordered_jobs,
        historical_record_count=historical_record_count,
        historical_job_count=historical_job_count,
    )
    coverage = _make_coverage_audit(envelopes, stress_paths)
    destructive = _make_destructive_audit(
        continuity_contract=continuity_contract,
        completion_contract=completion_contract,
        calibration_contract=calibration_contract,
        manifest=manifest,
        freshness=freshness,
        coverage=coverage,
        stress_path=stress_paths[0],
        task_package=task_packages[0],
    )

    paths = {
        "source_replay": output_dir / "predecessor_replay_audit.json",
        "source_capacity": output_dir / "calibration_source_capacity_audit.json",
        "prefix_envelopes": output_dir / "role_prefix_budget_envelopes.json",
        "records": output_dir / "calibration_operational_task_records.json",
        "environments": output_dir / "calibration_tool_environment_manifests.json",
        "replay_bindings": output_dir / "calibration_verifier_replay_bindings.json",
        "prompt_contracts": output_dir / "calibration_compact_prompt_contracts.json",
        "base_paths": output_dir / "calibration_base_path_audits.json",
        "task_packages": output_dir / "calibration_task_packages.json",
        "witnesses": output_dir / "calibration_compiler_witnesses.json",
        "observations": output_dir / "calibration_witness_observations.json",
        "closures": output_dir / "calibration_operation_closure_audits.json",
        "admissions": output_dir / "calibration_operational_admissions.json",
        "necessities": output_dir / "calibration_mechanism_necessity_artifacts.json",
        "counterfactuals": output_dir / "calibration_mechanism_counterfactual_replays.json",
        "catalogs": output_dir / "calibration_static_path_catalogs.json",
        "authority_audits": output_dir / "calibration_authority_task_audits.json",
        "replay_results": output_dir / "calibration_verifier_replay_results.json",
        "trajectories": output_dir / "calibration_compiler_trajectories.json",
        "scores": output_dir / "calibration_completed_trajectory_scores.json",
        "continuity_contract": output_dir / "thinking_continuity_contract.json",
        "continuity_fixture": output_dir / "thinking_continuity_fixture_audit.json",
        "completion_contract": output_dir / "completion_usability_contract.json",
        "completion_fixture": output_dir / "completion_usability_fixture_audit.json",
        "calibration_contract": output_dir / "calibration_contract.json",
        "stress_paths": output_dir / "calibration_stress_path_audits.json",
        "manifest": output_dir / "calibration_job_manifest.json",
        "freshness": output_dir / "calibration_freshness_audit.json",
        "coverage": output_dir / "budget_shape_coverage_audit.json",
        "destructive": output_dir / "destructive_preflight_audit.json",
    }
    _write_json(paths["source_replay"], replay_audit.model_dump(mode="json"))
    _write_json(paths["source_capacity"], capacity_audit.model_dump(mode="json"))
    _write_models(paths["prefix_envelopes"], envelopes, "envelope_id")
    _write_models(paths["records"], records, "record_id")
    _write_models(paths["environments"], environments, "manifest_id")
    _write_models(paths["replay_bindings"], replay_bindings, "contract_id")
    _write_models(paths["prompt_contracts"], prompt_contracts, "contract_id")
    _write_models(paths["base_paths"], base_paths, "audit_id")
    _write_models(paths["task_packages"], task_packages, "task_package_id")
    _write_models(paths["witnesses"], witnesses, "witness_id")
    _write_models(paths["observations"], observations, "observation_id")
    _write_models(paths["closures"], closures, "audit_id")
    _write_models(paths["admissions"], admissions, "admission_id")
    _write_models(paths["necessities"], necessities, "artifact_id")
    _write_models(paths["counterfactuals"], counterfactuals, "replay_id")
    _write_models(paths["catalogs"], catalogs, "catalog_id")
    _write_models(paths["authority_audits"], authority_audits, "audit_id")
    _write_models(paths["replay_results"], replay_results, "replay_id")
    _write_models(paths["trajectories"], compiler_trajectories, "trajectory_id")
    _write_models(paths["scores"], compiler_scores, "score_id")
    _write_json(paths["continuity_contract"], continuity_contract.model_dump(mode="json"))
    _write_json(paths["continuity_fixture"], continuity_fixture.model_dump(mode="json"))
    _write_json(paths["completion_contract"], completion_contract.model_dump(mode="json"))
    _write_json(paths["completion_fixture"], completion_fixture.model_dump(mode="json"))
    _write_json(paths["calibration_contract"], calibration_contract.model_dump(mode="json"))
    _write_models(paths["stress_paths"], stress_paths, "audit_id")
    _write_json(paths["manifest"], manifest.model_dump(mode="json"))
    _write_json(paths["freshness"], freshness.model_dump(mode="json"))
    _write_json(paths["coverage"], coverage.model_dump(mode="json"))
    _write_json(paths["destructive"], destructive.model_dump(mode="json"))

    counts = {
        "source_replay": 1,
        "source_capacity": 1,
        "prefix_envelopes": len(envelopes),
        "records": len(records),
        "environments": len(environments),
        "replay_bindings": len(replay_bindings),
        "prompt_contracts": len(prompt_contracts),
        "base_paths": len(base_paths),
        "task_packages": len(task_packages),
        "witnesses": len(witnesses),
        "observations": len(observations),
        "closures": len(closures),
        "admissions": len(admissions),
        "necessities": len(necessities),
        "counterfactuals": len(counterfactuals),
        "catalogs": len(catalogs),
        "authority_audits": len(authority_audits),
        "replay_results": len(replay_results),
        "trajectories": len(compiler_trajectories),
        "scores": len(compiler_scores),
        "continuity_contract": 1,
        "continuity_fixture": 1,
        "completion_contract": 1,
        "completion_fixture": 1,
        "calibration_contract": 1,
        "stress_paths": len(stress_paths),
        "manifest": 1,
        "freshness": 1,
        "coverage": 1,
        "destructive": 1,
    }
    detail_files = tuple(
        sorted(
            (_detail(path, output_dir, counts[key]) for key, path in paths.items()),
            key=lambda item: item.relative_path,
        )
    )
    predecessor_implementation = {
        item.relative_path: item for item in predecessor.implementation_source_files
    }
    implementation_paths = tuple(
        sorted({*predecessor_implementation, *IMPLEMENTATION_SOURCE_PATHS})
    )
    implementation_files = tuple(
        ImplementationSourceFile(
            relative_path=path,
            sha256=_sha256(package_root / path),
        )
        for path in implementation_paths
    )
    report_values = {
        "run_id": run_id,
        "predecessor_report_id": predecessor.report_id,
        "predecessor_replay_audit_id": replay_audit.audit_id,
        "source_capacity_audit_id": capacity_audit.audit_id,
        "calibration_contract_id": calibration_contract.contract_id,
        "calibration_manifest_id": manifest.manifest_id,
        "calibration_freshness_audit_id": freshness.audit_id,
        "budget_shape_coverage_audit_id": coverage.audit_id,
        "thinking_continuity_contract_id": continuity_contract.contract_id,
        "thinking_continuity_fixture_audit_id": continuity_fixture.audit_id,
        "completion_usability_contract_id": completion_contract.contract_id,
        "completion_usability_fixture_audit_id": completion_fixture.audit_id,
        "destructive_preflight_audit_id": destructive.audit_id,
        "predecessor_replayed_file_count": replay_audit.replayed_file_count,
        "maximum_calibration_path_upper_bound": max(
            item.maximum_path_upper_bound for item in stress_paths
        ),
        "minimum_calibration_headroom_tokens": min(
            item.minimum_headroom_tokens for item in stress_paths
        ),
        "maximum_calibration_prompt_utf8_bytes": max(
            item.maximum_prompt_utf8_bytes for item in stress_paths
        ),
        "model_config_id": model_config.public_manifest_hash,
        "thinking_binding_id": thinking_binding.binding_id,
        "detail_files": detail_files,
        "implementation_source_files": implementation_files,
    }
    provisional_report = ThinkingBudgetCalibrationPreflightReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = ThinkingBudgetCalibrationPreflightReport(
        report_id=thinking_budget_calibration_preflight_report_id(provisional_report),
        **report_values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.91 Thinking Budget Calibration preflight"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--selection-salt", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_thinking_budget_calibration_preflight(
        run_id=args.run_id,
        selection_salt=args.selection_salt,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
