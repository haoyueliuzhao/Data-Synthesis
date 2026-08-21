from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from math import comb
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    BudgetFeasibleRoleRematerializationReport,
    BudgetFeasibleRoleTaskPackage,
    BudgetQualifiedPathAudit,
    CompactPromptContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
    OperationalTaskRecord,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_budget_calibration_preflight import (  # noqa: E501
    CalibrationTaskPackage,
    ThinkingBudgetCalibrationManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_calibration_postrun_audit import (  # noqa: E501
    ThinkingCalibrationPostrunAuditReport,
    ThinkingTelemetryRepairContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import (
    render_compact_witness_prompts,
)
from trusted_synthesis.runtime.agent.prospective_thinking import (
    PROSPECTIVE_THINKING_MODE_POLICY,
    require_prospective_thinking,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionFailureKind,
    CompletionRequestKind,
    ProspectiveThinkingCompletionProtocol,
    RedactedProviderResponseEnvelope,
    capture_redacted_provider_response_envelope,
    capture_redacted_provider_response_fields,
    host_plan_attestation,
    make_prospective_thinking_completion_protocol,
    make_prospective_thinking_failure_artifact,
    project_model_completion,
    render_primary_completion_prompt,
    render_rescue_completion_prompt,
    require_admitted_response_envelope,
    serialize_validated_failure_artifact,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import AgentToolObservation

V26_94_VERSION: Final = "finance_v26_thinking_completion_telemetry_repair_preflight.v1"
V26_94_SOURCE_REPLAY_VERSION: Final = "finance_v26_thinking_repair_source_replay.v1"
V26_94_RETIREMENT_VERSION: Final = "finance_v26_role_population_retirement.v1"
V26_94_TASK_PACKAGE_VERSION: Final = "finance_v26_thinking_repair_task_package.v1"
V26_94_PATH_VERSION: Final = "finance_v26_thinking_repair_path.v1"
V26_94_TELEMETRY_FIXTURE_VERSION: Final = "finance_v26_thinking_telemetry_fixture.v1"
V26_94_CONTRACT_VERSION: Final = "finance_v26_thinking_repair_contract.v1"
V26_94_JOB_VERSION: Final = "finance_v26_thinking_repair_job.v1"
V26_94_MANIFEST_VERSION: Final = "finance_v26_thinking_repair_manifest.v1"
V26_94_FRESHNESS_VERSION: Final = "finance_v26_thinking_repair_freshness.v1"
V26_94_DESTRUCTIVE_VERSION: Final = "finance_v26_thinking_repair_destructive.v1"

V26_90_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821"
)
V26_91_DIR = (
    "artifacts/vtdo_experiment/finance_v26_91_thinking_budget_calibration_preflight_v1_20260821"
)
V26_92_DIR = (
    "artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821"
)
V26_93_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821"
)
MODEL_PROFILE_PATH = "config/deepseek_v4_flash_agent_thinking_v1.json"
PREFLIGHT_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_completion_telemetry_repair_preflight.py"
)
COMPLETION_SOURCE_PATH = "src/trusted_synthesis/runtime/agent/prospective_thinking_completion.py"
CLIENT_SOURCE_PATH = "src/trusted_synthesis/runtime/agent/prospective_thinking_client.py"

EXPECTED_V26_93_REPORT_ID: Final = (
    "finance_v26_thinking_postrun_audit_report:"
    "c6cb718b06f403e8603f4a2520bef8e374aefea2357245a16a8b982071529d44"
)
EXPECTED_V26_92_REPORT_ID: Final = (
    "finance_v26_thinking_budget_calibration_execution:"
    "f3bd9954b1c1f8e465bcca968ef5165d037a7da52b0c0f54ec87e1b9a34aec9b"
)
EXPECTED_V26_90_REPORT_ID: Final = (
    "finance_v26_budget_feasible_role_rematerialization_report:"
    "9d6e1de192bf267aa45dfbf7b49c1270c0ec995e03b734f208663763a01ef17e"
)
FUTURE_EXECUTION_RUN_ID: Final = (
    "finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821"
)
TARGET_MECHANISMS = (
    "context_conditioned_action",
    "failure_recovery",
    "semantic_reconciliation",
    "state_dependent_stopping",
)
RESCUE_FAILURE_TYPES: tuple[CompletionFailureKind, ...] = (
    "empty_final_content",
    "invalid_json",
    "invalid_response_contract",
    "length_truncated_content",
    "reasoning_only_length_truncation",
)
STATIC_MARGIN_TOKENS = 64
COMPLETION_UPPER_BOUND = 4096
ROLLOUT_UPPER_BOUND = 120000
PROMPT_UPPER_BOUND = 60000
CHAT_ENVELOPE_TOKENS = 256
ZERO_FAILURE_CP95_AT_32 = 0.08936819898626475
ONE_FAILURE_CP95_AT_32 = 0.13984946027422601


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=0)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_digest(self) -> ReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.94 source replay digest mismatch")
        return self


class ThinkingRepairSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v26_93_report_id: str = EXPECTED_V26_93_REPORT_ID
    v26_90_report_id: str = EXPECTED_V26_90_REPORT_ID
    entries: tuple[ReplayEntry, ...] = Field(min_length=1)
    replayed_file_count: int = Field(gt=0)
    all_files_passed: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_source_replay.v1"] = (
        V26_94_SOURCE_REPLAY_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ThinkingRepairSourceReplayAudit:
        if self.v26_93_report_id != EXPECTED_V26_93_REPORT_ID:
            raise ValueError("v26.93 predecessor report changed")
        if self.v26_90_report_id != EXPECTED_V26_90_REPORT_ID:
            raise ValueError("v26.90 source report changed")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("v26.94 source replay count differs")
        paths = tuple(item.relative_path for item in self.entries)
        if len(set(paths)) != len(paths):
            raise ValueError("v26.94 source replay paths must be unique")
        if self.audit_id != thinking_repair_source_replay_audit_id(self):
            raise ValueError("v26.94 source replay identity mismatch")
        return self


class RolePopulationRetirementAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_90_REPORT_ID
    source_role_task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    source_task_artifact_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    operational_task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    role_mechanism_counts: dict[str, dict[str, int]]
    source_empirical_job_count: Literal[0] = 0
    source_model_api_calls: Literal[0] = 0
    v26_92_source_task_overlap_count: Literal[0] = 0
    v26_92_operational_package_overlap_count: Literal[0] = 0
    retired_source_task_count: Literal[24] = 24
    retired_from_capability_role_count: Literal[12] = 12
    retired_from_reachability_role_count: Literal[12] = 12
    future_role_execution_allowed: Literal[False] = False
    compiler_fixtures_enter_empirical_denominator: Literal[False] = False
    selection_uses_v26_92_model_outcomes: Literal[False] = False
    schema_version: Literal["finance_v26_role_population_retirement.v1"] = V26_94_RETIREMENT_VERSION

    @model_validator(mode="after")
    def validate_retirement(self) -> RolePopulationRetirementAudit:
        if self.predecessor_report_id != EXPECTED_V26_90_REPORT_ID:
            raise ValueError("retired role Population predecessor changed")
        for values in (
            self.source_role_task_package_ids,
            self.source_task_artifact_ids,
            self.operational_task_package_ids,
        ):
            if len(set(values)) != 24:
                raise ValueError("retired v26.90 task identities must be unique")
        expected = {
            mechanism: {"capability": 3, "reachability": 3} for mechanism in TARGET_MECHANISMS
        }
        if self.role_mechanism_counts != expected:
            raise ValueError("v26.90 retirement balance changed")
        if self.audit_id != role_population_retirement_audit_id(self):
            raise ValueError("role retirement identity mismatch")
        return self


class ThinkingRepairTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    source_role_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    compact_prompt_contract_id: str = Field(min_length=1)
    thinking_completion_protocol_id: str = Field(min_length=1)
    telemetry_repair_contract_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    source_role_package_retired: Literal[True] = True
    source_model_exposed_before_freeze: Literal[False] = False
    compiler_fixture_only_before_execution: Literal[True] = True
    schema_version: Literal["finance_v26_thinking_repair_task_package.v1"] = (
        V26_94_TASK_PACKAGE_VERSION
    )

    @model_validator(mode="after")
    def validate_identity(self) -> ThinkingRepairTaskPackage:
        if self.task_package_id != thinking_repair_task_package_id(self):
            raise ValueError("Thinking repair TaskPackage identity mismatch")
        return self


class CompletionRequestAudit(FrozenModel):
    request_index: int = Field(ge=0)
    request_kind: CompletionRequestKind
    predecessor_request_index: int = Field(ge=1)
    predecessor_prompt_sha256: str = Field(min_length=64, max_length=64)
    predecessor_prompt_utf8_bytes: int = Field(gt=0)
    primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    primary_prompt_utf8_bytes: int = Field(gt=0)
    primary_prompt_token_upper_bound: int = Field(gt=0)
    primary_request_token_upper_bound: int = Field(gt=0)
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0)
    minimum_rescue_size_reduction_bytes: int = Field(gt=0)
    minimum_rescue_size_reduction_basis_points: int = Field(ge=1000)
    every_rescue_prompt_strictly_shorter_than_primary: Literal[True] = True
    primary_not_larger_than_predecessor: Literal[True] = True
    private_reasoning_content_present: Literal[False] = False
    free_text_rationale_requested: Literal[False] = False


class ThinkingRepairPathAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    repair_task_package_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    predecessor_role_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: PathStrategy
    predecessor_request_count: int = Field(gt=1)
    model_plan_request_removed: Literal[True] = True
    host_plan_attestation_id: str = Field(min_length=1)
    primary_request_count: int = Field(gt=0)
    request_audits: tuple[CompletionRequestAudit, ...] = Field(min_length=1)
    compiler_projection_count: int = Field(gt=0)
    compiler_projection_pass_count: int = Field(gt=0)
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0)
    maximum_rescue_prompt_token_upper_bound: int = Field(gt=0)
    maximum_rescue_request_token_upper_bound: int = Field(gt=0)
    maximum_rescue_failure_type: CompletionFailureKind
    minimum_rescue_size_reduction_bytes: int = Field(gt=0)
    minimum_rescue_size_reduction_basis_points: int = Field(ge=1000)
    all_rescue_prompts_strictly_shorter_than_primary: Literal[True] = True
    removed_plan_request_token_upper_bound: int = Field(gt=0)
    predecessor_repair_reserve_tokens: Literal[4096] = 4096
    rescue_funded_by_removed_plan_and_repair_reserve: Literal[True] = True
    full_path_upper_bound: int = Field(gt=0)
    minimum_headroom_tokens: int = Field(ge=0)
    maximum_prompt_utf8_bytes: int = Field(gt=0)
    prompt_ceiling_passed: Literal[True] = True
    rollout_ceiling_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_path.v1"] = V26_94_PATH_VERSION

    @model_validator(mode="after")
    def validate_path(self) -> ThinkingRepairPathAudit:
        if self.primary_request_count != len(self.request_audits):
            raise ValueError("Thinking repair primary request count differs")
        if self.predecessor_request_count != self.primary_request_count + 1:
            raise ValueError("Thinking repair path must remove exactly one model Plan request")
        if self.compiler_projection_count != self.compiler_projection_pass_count:
            raise ValueError("Thinking repair Compiler projection failed")
        if self.full_path_upper_bound > ROLLOUT_UPPER_BOUND:
            raise ValueError("Thinking repair path exceeds rollout bound")
        if self.maximum_prompt_utf8_bytes > PROMPT_UPPER_BOUND:
            raise ValueError("Thinking repair path exceeds Prompt bound")
        if self.minimum_headroom_tokens != ROLLOUT_UPPER_BOUND - self.full_path_upper_bound:
            raise ValueError("Thinking repair path headroom differs")
        if self.audit_id != thinking_repair_path_audit_id(self):
            raise ValueError("Thinking repair path identity mismatch")
        return self


class TelemetryFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_valid_envelope: RedactedProviderResponseEnvelope
    reasoning_exhausted_envelope: RedactedProviderResponseEnvelope
    invalid_json_envelope: RedactedProviderResponseEnvelope
    native_tool_envelope: RedactedProviderResponseEnvelope
    response_model_retained_on_reasoning_exhaustion: Literal[True] = True
    response_model_retained_on_invalid_json: Literal[True] = True
    native_tool_presence_retained_before_parse: Literal[True] = True
    malformed_usage_response_model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    malformed_usage_native_tool_observed: Literal[False] = False
    malformed_usage_strict_envelope_rejected: Literal[True] = True
    malformed_usage_private_reasoning_hit_count: Literal[0] = 0
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    typed_failure_artifact_count: Literal[3] = 3
    typed_failure_artifacts_validated_before_serialization: Literal[True] = True
    serialized_private_reasoning_hit_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_telemetry_fixture.v1"] = (
        V26_94_TELEMETRY_FIXTURE_VERSION
    )

    @model_validator(mode="after")
    def validate_fixture(self) -> TelemetryFixtureAudit:
        if self.native_tool_envelope.provider_native_tool_call_observed is not True:
            raise ValueError("native-tool fixture did not preserve presence")
        if self.audit_id != telemetry_fixture_audit_id(self):
            raise ValueError("Thinking telemetry fixture identity mismatch")
        return self


class ThinkingCompletionRepairContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_postrun_report_id: str = EXPECTED_V26_93_REPORT_ID
    predecessor_execution_report_id: str = EXPECTED_V26_92_REPORT_ID
    source_role_report_id: str = EXPECTED_V26_90_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    role_retirement_audit_id: str = Field(min_length=1)
    thinking_completion_protocol_id: str = Field(min_length=1)
    telemetry_repair_contract_id: str = Field(min_length=1)
    telemetry_fixture_audit_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    repair_task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    repair_path_audit_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    prospective_execution_run_id: str = FUTURE_EXECUTION_RUN_ID
    completion_upper_bound_tokens: Literal[4096] = 4096
    rollout_upper_bound_tokens: Literal[120000] = 120000
    prompt_upper_bound_bytes: Literal[60000] = 60000
    maximum_rescue_calls_per_job: Literal[1] = 1
    model_plan_calls_per_job: Literal[0] = 0
    exact_job_denominator: Literal[32] = 32
    failure_gate_threshold: float = 0.10
    zero_failure_cp95_upper_bound: float = ZERO_FAILURE_CP95_AT_32
    one_failure_cp95_upper_bound: float = ONE_FAILURE_CP95_AT_32
    typed_no_call_gate_requires_zero_failures: Literal[True] = True
    completion_unusable_gate_requires_zero_failures: Literal[True] = True
    provider_transport_failure_is_separate: Literal[True] = True
    semantic_validity_cannot_rescue_failure_gates: Literal[True] = True
    all_provider_calls_require_thinking: Literal[True] = True
    completion_threshold_relaxation_forbidden: Literal[True] = True
    historical_v26_92_rerun_allowed: Literal[False] = False
    historical_v26_92_reclassification_allowed: Literal[False] = False
    v26_90_role_execution_allowed: Literal[False] = False
    compiler_rows_enter_empirical_denominator: Literal[False] = False
    execution_runner_materialized: Literal[False] = False
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_thinking_repair_contract.v1"] = V26_94_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ThinkingCompletionRepairContract:
        if self.predecessor_postrun_report_id != EXPECTED_V26_93_REPORT_ID:
            raise ValueError("v26.93 predecessor report changed")
        if self.predecessor_execution_report_id != EXPECTED_V26_92_REPORT_ID:
            raise ValueError("v26.92 predecessor report changed")
        if self.source_role_report_id != EXPECTED_V26_90_REPORT_ID:
            raise ValueError("v26.90 source role report changed")
        if self.prospective_execution_run_id != FUTURE_EXECUTION_RUN_ID:
            raise ValueError("prospective execution run changed")
        if self.failure_gate_threshold != 0.10:
            raise ValueError("Thinking repair failure Gate threshold changed")
        if self.zero_failure_cp95_upper_bound != ZERO_FAILURE_CP95_AT_32:
            raise ValueError("Thinking repair zero-failure bound changed")
        if self.one_failure_cp95_upper_bound != ONE_FAILURE_CP95_AT_32:
            raise ValueError("Thinking repair one-failure bound changed")
        if not (
            self.zero_failure_cp95_upper_bound
            <= self.failure_gate_threshold
            < self.one_failure_cp95_upper_bound
        ):
            raise ValueError("Thinking repair exact denominator no longer requires zero failures")
        if len(set(self.repair_task_package_ids)) != 24:
            raise ValueError("Thinking repair Contract TaskPackages must be unique")
        if len(set(self.repair_path_audit_ids)) != 48:
            raise ValueError("Thinking repair Contract paths must be unique")
        if self.contract_id != thinking_completion_repair_contract_id(self):
            raise ValueError("Thinking Completion repair Contract identity mismatch")
        return self


class ThinkingRepairJob(FrozenModel):
    job_id: str = Field(min_length=1)
    repair_contract_id: str = Field(min_length=1)
    repair_task_package_id: str = Field(min_length=1)
    repair_path_audit_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: PathStrategy
    source_role: Literal["capability", "reachability"]
    job_seed: int = Field(ge=0)
    model_config_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    maximum_rescue_calls: Literal[1] = 1
    model_plan_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_job.v1"] = V26_94_JOB_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> ThinkingRepairJob:
        if self.job_id != thinking_repair_job_id(self):
            raise ValueError("Thinking repair Job identity mismatch")
        return self


class ThinkingRepairManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    repair_contract_id: str = Field(min_length=1)
    prospective_execution_run_id: str = FUTURE_EXECUTION_RUN_ID
    jobs: tuple[ThinkingRepairJob, ...] = Field(min_length=32, max_length=32)
    mechanism_job_counts: dict[str, int]
    path_job_counts: dict[str, int]
    cell_job_counts: dict[str, int]
    distinct_task_package_count: Literal[24] = 24
    historical_v26_92_job_overlap_count: Literal[0] = 0
    exact_denominator_frozen: Literal[32] = 32
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_thinking_repair_manifest.v1"] = V26_94_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ThinkingRepairManifest:
        if self.prospective_execution_run_id != FUTURE_EXECUTION_RUN_ID:
            raise ValueError("prospective execution run changed")
        if len({item.job_id for item in self.jobs}) != 32:
            raise ValueError("Thinking repair Jobs must be unique")
        if len({item.repair_task_package_id for item in self.jobs}) != 24:
            raise ValueError("Thinking repair Manifest must cover all TaskPackages")
        if self.mechanism_job_counts != {item: 8 for item in TARGET_MECHANISMS}:
            raise ValueError("Thinking repair mechanism balance changed")
        if self.path_job_counts != {
            "search_then_open": 12,
            "search_then_structured": 8,
            "structured_direct": 12,
        }:
            raise ValueError("Thinking repair path balance changed")
        if set(self.cell_job_counts.values()) - {2, 3}:
            raise ValueError("Thinking repair cells require two or three Jobs")
        if len(self.cell_job_counts) != 12:
            raise ValueError("Thinking repair Manifest must cover all 12 cells")
        if self.manifest_id != thinking_repair_manifest_id(self):
            raise ValueError("Thinking repair Manifest identity mismatch")
        return self


class ThinkingRepairFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_task_overlap_with_v26_92: Literal[0] = 0
    semantic_source_overlap_with_v26_92: Literal[0] = 0
    operational_package_overlap_with_v26_92: Literal[0] = 0
    repair_task_package_overlap_with_v26_92: Literal[0] = 0
    job_overlap_with_v26_92: Literal[0] = 0
    source_role_task_overlap_with_v26_90: Literal[24] = 24
    source_role_task_overlap_is_model_unexposed: Literal[True] = True
    source_role_population_retired: Literal[True] = True
    task_selection_uses_historical_model_outcomes: Literal[False] = False
    compiler_fixture_outcomes_used_for_selection: Literal[False] = False
    schema_version: Literal["finance_v26_thinking_repair_freshness.v1"] = V26_94_FRESHNESS_VERSION

    @model_validator(mode="after")
    def validate_freshness(self) -> ThinkingRepairFreshnessAudit:
        if self.audit_id != thinking_repair_freshness_audit_id(self):
            raise ValueError("Thinking repair freshness identity mismatch")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    failure_type: str = Field(min_length=1)


class DestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=12)
    rejected_mutation_count: int = Field(ge=12)
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_destructive.v1"] = (
        V26_94_DESTRUCTIVE_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructivePreflightAudit:
        if self.rejected_mutation_count != len(self.mutation_results):
            raise ValueError("Thinking repair mutation count differs")
        if self.audit_id != destructive_preflight_audit_id(self):
            raise ValueError("Thinking repair destructive audit identity mismatch")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ThinkingCompletionTelemetryRepairPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    role_retirement_audit_id: str = Field(min_length=1)
    thinking_completion_protocol_id: str = Field(min_length=1)
    telemetry_fixture_audit_id: str = Field(min_length=1)
    repair_contract_id: str = Field(min_length=1)
    repair_manifest_id: str = Field(min_length=1)
    freshness_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    source_replayed_file_count: int = Field(gt=0)
    repair_task_package_count: Literal[24] = 24
    static_path_count: Literal[48] = 48
    compiler_projection_count: int = Field(gt=0)
    repair_job_count: Literal[32] = 32
    maximum_path_upper_bound: int = Field(gt=0)
    minimum_path_headroom_tokens: int = Field(ge=0)
    maximum_prompt_utf8_bytes: int = Field(gt=0)
    prospective_execution_run_id: str = FUTURE_EXECUTION_RUN_ID
    detail_files: tuple[DetailFile, ...] = Field(min_length=10)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=3)
    formal_independent_rebuild_required: Literal[True] = True
    empirical_result_count: Literal[0] = 0
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    execution_runner_materialized: Literal[False] = False
    repair_execution_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal[
        "thinking_completion_telemetry_repair_execution_runner_and_preflight_only"
    ] = "thinking_completion_telemetry_repair_execution_runner_and_preflight_only"
    schema_version: Literal["finance_v26_thinking_completion_telemetry_repair_preflight.v1"] = (
        V26_94_VERSION
    )

    @model_validator(mode="after")
    def validate_report(self) -> ThinkingCompletionTelemetryRepairPreflightReport:
        if self.prospective_execution_run_id != FUTURE_EXECUTION_RUN_ID:
            raise ValueError("prospective execution run changed")
        if self.maximum_path_upper_bound > ROLLOUT_UPPER_BOUND:
            raise ValueError("v26.94 report contains an over-budget path")
        if self.maximum_prompt_utf8_bytes > PROMPT_UPPER_BOUND:
            raise ValueError("v26.94 report contains an oversized Prompt")
        if self.report_id != thinking_repair_preflight_report_id(self):
            raise ValueError("v26.94 report identity mismatch")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def thinking_repair_source_replay_audit_id(
    value: ThinkingRepairSourceReplayAudit,
) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_source_replay:")


def role_population_retirement_audit_id(value: RolePopulationRetirementAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_role_population_retirement:")


def thinking_repair_task_package_id(value: ThinkingRepairTaskPackage) -> str:
    return _identity(value, "task_package_id", "finance_v26_thinking_repair_task_package:")


def thinking_repair_path_audit_id(value: ThinkingRepairPathAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_path:")


def telemetry_fixture_audit_id(value: TelemetryFixtureAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_telemetry_fixture:")


def thinking_completion_repair_contract_id(value: ThinkingCompletionRepairContract) -> str:
    return _identity(value, "contract_id", "finance_v26_thinking_repair_contract:")


def thinking_repair_job_id(value: ThinkingRepairJob) -> str:
    return _identity(value, "job_id", "finance_v26_thinking_repair_job:")


def thinking_repair_manifest_id(value: ThinkingRepairManifest) -> str:
    return _identity(value, "manifest_id", "finance_v26_thinking_repair_manifest:")


def thinking_repair_freshness_audit_id(value: ThinkingRepairFreshnessAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_freshness:")


def destructive_preflight_audit_id(value: DestructivePreflightAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_destructive:")


def thinking_repair_preflight_report_id(
    value: ThinkingCompletionTelemetryRepairPreflightReport,
) -> str:
    return _identity(
        value,
        "report_id",
        "finance_v26_thinking_completion_telemetry_repair_preflight_report:",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(value)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.94 output differs: {path}")
    path.write_bytes(raw)


def _write_models(path: Path, values: Sequence[BaseModel], identity_field: str) -> None:
    ordered = sorted(values, key=lambda item: str(getattr(item, identity_field)))
    _write_json(path, [item.model_dump(mode="json") for item in ordered])


def _rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _detail(path: Path, output_dir: Path, count: int) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=count,
    )


def _cp_upper(failures: int, denominator: int, *, alpha: float = 0.05) -> float:
    if not 0 <= failures <= denominator or denominator <= 0:
        raise ValueError("invalid Clopper-Pearson inputs")
    if failures == denominator:
        return 1.0

    def cdf(probability: float) -> float:
        return sum(
            comb(denominator, index)
            * probability**index
            * (1.0 - probability) ** (denominator - index)
            for index in range(failures + 1)
        )

    lower = 0.0
    upper = 1.0
    for _ in range(200):
        midpoint = (lower + upper) / 2
        if cdf(midpoint) > alpha:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2


def _build_source_replay(
    package_root: Path,
) -> tuple[
    ThinkingCalibrationPostrunAuditReport,
    ThinkingTelemetryRepairContract,
    BudgetFeasibleRoleRematerializationReport,
    ThinkingRepairSourceReplayAudit,
]:
    v26_93_dir = package_root / V26_93_DIR
    v26_93_report = ThinkingCalibrationPostrunAuditReport.model_validate_json(
        (v26_93_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        v26_93_report.report_id != EXPECTED_V26_93_REPORT_ID
        or v26_93_report.next_permitted_stage
        != "fresh_thinking_completion_and_response_telemetry_repair_preflight_only"
    ):
        raise ValueError("v26.93 does not authorize this repair preflight")
    telemetry_contract = ThinkingTelemetryRepairContract.model_validate_json(
        (v26_93_dir / "telemetry_repair_contract.json").read_text(encoding="utf-8")
    )
    if telemetry_contract.contract_id != v26_93_report.telemetry_repair_contract_id:
        raise ValueError("v26.93 telemetry repair Contract binding differs")

    v26_90_dir = package_root / V26_90_DIR
    v26_90_report = BudgetFeasibleRoleRematerializationReport.model_validate_json(
        (v26_90_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        v26_90_report.report_id != EXPECTED_V26_90_REPORT_ID
        or v26_90_report.model_api_calls != 0
        or v26_90_report.job_manifest_materialized
    ):
        raise ValueError("v26.90 role tasks are not unopened static inputs")

    entries: dict[str, ReplayEntry] = {}

    def add(relative_path: str, expected: str, source_kind: str) -> None:
        path = package_root / relative_path
        observed = _sha256(path)
        entry = ReplayEntry(
            relative_path=relative_path,
            source_kind=source_kind,
            expected_sha256=expected,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
        prior = entries.get(relative_path)
        if prior is not None and prior.expected_sha256 != expected:
            raise ValueError("v26.94 replay sources disagree on an expected digest")
        entries[relative_path] = entry

    add(
        f"{V26_93_DIR}/report.json",
        _sha256(v26_93_dir / "report.json"),
        "v26_93_report",
    )
    for item in v26_93_report.detail_files:
        add(
            f"{V26_93_DIR}/{item.relative_path}",
            item.sha256,
            "v26_93_detail",
        )
    prior_source_replay = json.loads(
        (v26_93_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    for item in prior_source_replay["entries"]:
        add(item["relative_path"], item["expected_sha256"], "v26_93_transitive_replay")

    add(
        f"{V26_90_DIR}/report.json",
        _sha256(v26_90_dir / "report.json"),
        "v26_90_report",
    )
    for item in v26_90_report.immutable_artifact_files:
        add(f"{V26_90_DIR}/{item.relative_path}", item.sha256, "v26_90_detail")
    for item in v26_90_report.source_artifact_files:
        add(item.relative_path, item.sha256, "v26_90_source")
    for item in v26_90_report.implementation_source_files:
        add(item.relative_path, item.sha256, "v26_90_implementation")

    for relative_path in (
        MODEL_PROFILE_PATH,
        COMPLETION_SOURCE_PATH,
        CLIENT_SOURCE_PATH,
        PREFLIGHT_SOURCE_PATH,
    ):
        add(relative_path, _sha256(package_root / relative_path), "v26_94_implementation")

    ordered = tuple(sorted(entries.values(), key=lambda item: item.relative_path))
    values = {
        "entries": ordered,
        "replayed_file_count": len(ordered),
    }
    provisional = ThinkingRepairSourceReplayAudit.model_construct(
        audit_id="pending",
        **values,
    )
    audit = ThinkingRepairSourceReplayAudit(
        audit_id=thinking_repair_source_replay_audit_id(provisional),
        **values,
    )
    return v26_93_report, telemetry_contract, v26_90_report, audit


def _build_retirement(
    *,
    package_root: Path,
    v26_90_report: BudgetFeasibleRoleRematerializationReport,
    role_packages: Sequence[BudgetFeasibleRoleTaskPackage],
) -> RolePopulationRetirementAudit:
    v26_91_dir = package_root / V26_91_DIR
    exposed_packages = cast(
        tuple[CalibrationTaskPackage, ...],
        _rows(v26_91_dir / "calibration_task_packages.json", CalibrationTaskPackage),
    )
    exposed_sources = {item.source_task_artifact_id for item in exposed_packages}
    exposed_operational = {item.operational_task_package_id for item in exposed_packages}
    role_counts: dict[str, dict[str, int]] = {
        mechanism: {"capability": 0, "reachability": 0} for mechanism in TARGET_MECHANISMS
    }
    for item in role_packages:
        role_counts[item.mechanism_id][item.role] += 1
    values = {
        "source_role_task_package_ids": tuple(
            sorted(item.task_package_id for item in role_packages)
        ),
        "source_task_artifact_ids": tuple(
            sorted(item.source_task_artifact_id for item in role_packages)
        ),
        "operational_task_package_ids": tuple(
            sorted(item.operational_task_package_id for item in role_packages)
        ),
        "role_mechanism_counts": role_counts,
        "source_empirical_job_count": 0,
        "source_model_api_calls": v26_90_report.model_api_calls,
        "v26_92_source_task_overlap_count": len(
            {item.source_task_artifact_id for item in role_packages} & exposed_sources
        ),
        "v26_92_operational_package_overlap_count": len(
            {item.operational_task_package_id for item in role_packages} & exposed_operational
        ),
    }
    provisional = RolePopulationRetirementAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return RolePopulationRetirementAudit(
        audit_id=role_population_retirement_audit_id(provisional),
        **values,
    )


def _make_task_packages(
    *,
    role_packages: Sequence[BudgetFeasibleRoleTaskPackage],
    completion_protocol: ProspectiveThinkingCompletionProtocol,
    telemetry_contract: ThinkingTelemetryRepairContract,
) -> tuple[ThinkingRepairTaskPackage, ...]:
    output = []
    for source in role_packages:
        values = {
            "source_role_task_package_id": source.task_package_id,
            "source_task_artifact_id": source.source_task_artifact_id,
            "source_role": source.role,
            "mechanism_id": source.mechanism_id,
            "operational_record_id": source.operational_record_id,
            "operational_task_package_id": source.operational_task_package_id,
            "environment_manifest_id": source.environment_manifest_id,
            "semantic_source_id": source.semantic_source_id,
            "compact_prompt_contract_id": source.compact_prompt_contract_id,
            "thinking_completion_protocol_id": completion_protocol.contract_id,
            "telemetry_repair_contract_id": telemetry_contract.contract_id,
            "model_config_id": source.model_config_id,
            "thinking_binding_id": source.thinking_binding_id,
        }
        provisional = ThinkingRepairTaskPackage.model_construct(
            task_package_id="pending",
            **values,
        )
        output.append(
            ThinkingRepairTaskPackage(
                task_package_id=thinking_repair_task_package_id(provisional),
                **values,
            )
        )
    return tuple(sorted(output, key=lambda item: item.task_package_id))


def _trajectory_observations(trajectory: Trajectory) -> tuple[AgentToolObservation, ...]:
    output = []
    for step in trajectory.steps:
        observation = step.observation
        if (
            isinstance(observation, Mapping)
            and observation.get("schema_version") == "agent_tool_observation.v2"
        ):
            output.append(AgentToolObservation.model_validate(observation))
    return tuple(output)


def _projection_payloads(
    trajectory: Trajectory,
) -> tuple[tuple[CompletionRequestKind, dict[str, Any]], ...]:
    output: list[tuple[CompletionRequestKind, dict[str, Any]]] = []
    for step in trajectory.steps:
        if step.tool_name is None:
            continue
        output.append(
            (
                "decision",
                {
                    "action": "call_tool",
                    "tool_id": step.tool_name,
                    "arguments": step.tool_input,
                },
            )
        )
    final_answer = trajectory.final_answer
    if not isinstance(final_answer, Mapping):
        raise ValueError("Compiler trajectory lacks a structured final answer")
    result = final_answer.get("result")
    if not isinstance(result, Mapping):
        raise ValueError("Compiler trajectory final answer lacks result")
    output.append(("final_answer", {"answer": dict(result)}))
    return tuple(output)


def _build_path_audits(
    *,
    role_packages: Sequence[BudgetFeasibleRoleTaskPackage],
    repair_packages: Sequence[ThinkingRepairTaskPackage],
    role_paths: Sequence[BudgetQualifiedPathAudit],
    prompt_contracts: Sequence[CompactPromptContract],
    records: Sequence[OperationalTaskRecord],
    trajectories: Sequence[Trajectory],
) -> tuple[ThinkingRepairPathAudit, ...]:
    repair_by_source = {item.source_role_task_package_id: item for item in repair_packages}
    path_by_id = {item.audit_id: item for item in role_paths}
    prompt_by_id = {item.contract_id: item for item in prompt_contracts}
    record_by_id = {item.record_id: item for item in records}
    trajectory_by_id = {item.trajectory_id: item for item in trajectories}
    plan_attestation_id = canonical_hash(
        host_plan_attestation(),
        prefix="prospective_host_plan_attestation:",
    )
    output = []
    for role_package in sorted(role_packages, key=lambda item: item.task_package_id):
        repair_package = repair_by_source[role_package.task_package_id]
        record = record_by_id[role_package.operational_record_id]
        prompt_contract = prompt_by_id[role_package.compact_prompt_contract_id]
        path_ids = tuple(role_package.path_audit_ids)
        for path_id in path_ids:
            predecessor = path_by_id[path_id]
            trajectory = trajectory_by_id[predecessor.compiler_trajectory_id]
            observations = _trajectory_observations(trajectory)
            source_prompts = render_compact_witness_prompts(
                prompt_contract.public_context,
                record.task_package.task.public,
                observations,
                public_path_condition=predecessor.public_path_condition,
            )
            if len(source_prompts) != len(predecessor.request_bounds):
                raise ValueError("v26.90 Prompt replay request count differs")
            for prompt, bound in zip(
                source_prompts,
                predecessor.request_bounds,
                strict=True,
            ):
                if (
                    _sha256_text(prompt) != bound.prompt_sha256
                    or len(prompt.encode("utf-8")) != bound.prompt_utf8_bytes
                ):
                    raise ValueError("v26.90 compact Prompt failed exact replay")
            if predecessor.request_bounds[0].request_kind != "plan":
                raise ValueError("Thinking repair funding requires the predecessor Plan request")

            request_audits = []
            rescue_candidates: list[tuple[int, int, CompletionFailureKind]] = []
            maximum_prompt_bytes = 0
            for new_index, (source_prompt, predecessor_bound) in enumerate(
                zip(
                    source_prompts[1:],
                    predecessor.request_bounds[1:],
                    strict=True,
                )
            ):
                request_kind = cast(CompletionRequestKind, predecessor_bound.request_kind)
                primary = render_primary_completion_prompt(request_kind, source_prompt)
                primary_bytes = len(primary.encode("utf-8"))
                primary_prompt_bound = primary_bytes + CHAT_ENVELOPE_TOKENS + STATIC_MARGIN_TOKENS
                primary_request_bound = primary_prompt_bound + COMPLETION_UPPER_BOUND
                if primary_request_bound > predecessor_bound.request_token_upper_bound:
                    raise ValueError(
                        "prospective primary Prompt exceeds predecessor request: "
                        f"{request_kind} {primary_request_bound} > "
                        f"{predecessor_bound.request_token_upper_bound}"
                    )
                maximum_prompt_bytes = max(maximum_prompt_bytes, primary_bytes)
                request_rescue_bytes = []
                for failure_type in RESCUE_FAILURE_TYPES:
                    rescue = render_rescue_completion_prompt(
                        request_kind,
                        source_prompt,
                        failure_type,
                    )
                    rescue_bytes = len(rescue.encode("utf-8"))
                    rescue_prompt_bound = rescue_bytes + CHAT_ENVELOPE_TOKENS + STATIC_MARGIN_TOKENS
                    if rescue_bytes >= primary_bytes:
                        raise ValueError("rescue Prompt is not strictly shorter than primary")
                    request_rescue_bytes.append(rescue_bytes)
                    rescue_candidates.append(
                        (
                            rescue_prompt_bound + COMPLETION_UPPER_BOUND,
                            rescue_bytes,
                            failure_type,
                        )
                    )
                    maximum_prompt_bytes = max(maximum_prompt_bytes, rescue_bytes)
                maximum_request_rescue_bytes = max(request_rescue_bytes)
                request_audits.append(
                    CompletionRequestAudit(
                        request_index=new_index,
                        request_kind=request_kind,
                        predecessor_request_index=predecessor_bound.request_index,
                        predecessor_prompt_sha256=predecessor_bound.prompt_sha256,
                        predecessor_prompt_utf8_bytes=predecessor_bound.prompt_utf8_bytes,
                        primary_prompt_sha256=_sha256_text(primary),
                        primary_prompt_utf8_bytes=primary_bytes,
                        primary_prompt_token_upper_bound=primary_prompt_bound,
                        primary_request_token_upper_bound=primary_request_bound,
                        maximum_rescue_prompt_utf8_bytes=maximum_request_rescue_bytes,
                        minimum_rescue_size_reduction_bytes=(
                            primary_bytes - maximum_request_rescue_bytes
                        ),
                        minimum_rescue_size_reduction_basis_points=(
                            (primary_bytes - maximum_request_rescue_bytes) * 10000 // primary_bytes
                        ),
                    )
                )
            maximum_rescue_bound, maximum_rescue_bytes, maximum_failure = max(
                rescue_candidates,
                key=lambda item: (item[0], item[2]),
            )
            maximum_rescue_prompt_bound = maximum_rescue_bound - COMPLETION_UPPER_BOUND
            full_path_bound = (
                sum(item.primary_request_token_upper_bound for item in request_audits)
                + maximum_rescue_bound
            )
            removed_plan_bound = predecessor.request_bounds[0].request_token_upper_bound
            if full_path_bound > predecessor.maximum_cumulative_path_upper_bound:
                raise ValueError("removed Plan and repair reserve do not fund rescue")

            projection_payloads = _projection_payloads(trajectory)
            if len(projection_payloads) != len(request_audits):
                raise ValueError("Compiler projections and prospective requests differ")
            projection_passes = 0
            for (kind, payload), request_audit in zip(
                projection_payloads,
                request_audits,
                strict=True,
            ):
                if kind != request_audit.request_kind:
                    raise ValueError("Compiler projection request kind differs")
                projection = project_model_completion(kind, payload)
                if kind == "decision":
                    if (
                        projection.tool_id != payload["tool_id"]
                        or projection.arguments != payload["arguments"]
                    ):
                        raise ValueError("Compiler action changed during projection")
                elif projection.answer != payload["answer"]:
                    raise ValueError("Compiler answer changed during projection")
                projection_passes += 1

            values = {
                "repair_task_package_id": repair_package.task_package_id,
                "predecessor_path_audit_id": predecessor.audit_id,
                "predecessor_role_task_package_id": role_package.task_package_id,
                "source_task_artifact_id": role_package.source_task_artifact_id,
                "role": role_package.role,
                "mechanism_id": role_package.mechanism_id,
                "path_strategy_id": predecessor.path_strategy_id,
                "predecessor_request_count": predecessor.request_count,
                "host_plan_attestation_id": plan_attestation_id,
                "primary_request_count": len(request_audits),
                "request_audits": tuple(request_audits),
                "compiler_projection_count": len(projection_payloads),
                "compiler_projection_pass_count": projection_passes,
                "maximum_rescue_prompt_utf8_bytes": maximum_rescue_bytes,
                "maximum_rescue_prompt_token_upper_bound": maximum_rescue_prompt_bound,
                "maximum_rescue_request_token_upper_bound": maximum_rescue_bound,
                "maximum_rescue_failure_type": maximum_failure,
                "minimum_rescue_size_reduction_bytes": min(
                    item.minimum_rescue_size_reduction_bytes for item in request_audits
                ),
                "minimum_rescue_size_reduction_basis_points": min(
                    item.minimum_rescue_size_reduction_basis_points for item in request_audits
                ),
                "removed_plan_request_token_upper_bound": removed_plan_bound,
                "full_path_upper_bound": full_path_bound,
                "minimum_headroom_tokens": ROLLOUT_UPPER_BOUND - full_path_bound,
                "maximum_prompt_utf8_bytes": maximum_prompt_bytes,
            }
            provisional = ThinkingRepairPathAudit.model_construct(
                audit_id="pending",
                **values,
            )
            output.append(
                ThinkingRepairPathAudit(
                    audit_id=thinking_repair_path_audit_id(provisional),
                    **values,
                )
            )
    return tuple(sorted(output, key=lambda item: item.audit_id))


def _provider_fixture(
    *,
    content: str,
    finish_reason: str,
    reasoning: str,
    reasoning_tokens: int,
    tool_calls: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "content": content,
                    "reasoning_content": reasoning,
                    "tool_calls": list(tool_calls),
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": max(reasoning_tokens, 32),
            "total_tokens": 100 + max(reasoning_tokens, 32),
            "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
        },
    }


def _build_telemetry_fixture() -> TelemetryFixtureAudit:
    private_reasoning = "synthetic private reasoning that must not persist"
    valid = capture_redacted_provider_response_envelope(
        _provider_fixture(
            content='{"action":"call_tool","arguments":{},"tool_id":"query"}',
            finish_reason="stop",
            reasoning=private_reasoning,
            reasoning_tokens=80,
        )
    )
    exhausted = capture_redacted_provider_response_envelope(
        _provider_fixture(
            content="",
            finish_reason="length",
            reasoning=private_reasoning,
            reasoning_tokens=4096,
        )
    )
    invalid_json = capture_redacted_provider_response_envelope(
        _provider_fixture(
            content="{not-json",
            finish_reason="stop",
            reasoning=private_reasoning,
            reasoning_tokens=100,
        )
    )
    native_tool = capture_redacted_provider_response_envelope(
        _provider_fixture(
            content='{"action":"call_tool"}',
            finish_reason="stop",
            reasoning=private_reasoning,
            reasoning_tokens=60,
            tool_calls=({"id": "forbidden"},),
        )
    )
    malformed_usage_body = _provider_fixture(
        content='{"action":"call_tool","arguments":{},"tool_id":"query"}',
        finish_reason="stop",
        reasoning=private_reasoning,
        reasoning_tokens=80,
    )
    malformed_usage_body.pop("usage")
    malformed_usage_fields = capture_redacted_provider_response_fields(malformed_usage_body)
    try:
        capture_redacted_provider_response_envelope(malformed_usage_body)
    except Exception:
        malformed_usage_rejected = True
    else:
        malformed_usage_rejected = False
    require_admitted_response_envelope(valid, expected_model="deepseek-v4-flash")
    require_admitted_response_envelope(exhausted, expected_model="deepseek-v4-flash")
    require_admitted_response_envelope(invalid_json, expected_model="deepseek-v4-flash")
    artifacts = (
        make_prospective_thinking_failure_artifact(
            failure_type="reasoning_only_length_truncation",
            request_hash="a" * 64,
            response_envelope=exhausted,
        ),
        make_prospective_thinking_failure_artifact(
            failure_type="invalid_json",
            request_hash="b" * 64,
            response_envelope=invalid_json,
        ),
        make_prospective_thinking_failure_artifact(
            failure_type="provider_native_tool_call",
            request_hash="c" * 64,
            response_envelope=native_tool,
        ),
    )
    serialized = b"".join(serialize_validated_failure_artifact(item) for item in artifacts)
    values = {
        "exact_valid_envelope": valid,
        "reasoning_exhausted_envelope": exhausted,
        "invalid_json_envelope": invalid_json,
        "native_tool_envelope": native_tool,
        "malformed_usage_response_model": malformed_usage_fields["response_model"],
        "malformed_usage_native_tool_observed": malformed_usage_fields[
            "provider_native_tool_call_observed"
        ],
        "malformed_usage_strict_envelope_rejected": malformed_usage_rejected,
        "malformed_usage_private_reasoning_hit_count": _canonical_bytes(
            malformed_usage_fields
        ).count(private_reasoning.encode("utf-8")),
        "serialized_private_reasoning_hit_count": serialized.count(
            private_reasoning.encode("utf-8")
        ),
    }
    provisional = TelemetryFixtureAudit.model_construct(audit_id="pending", **values)
    return TelemetryFixtureAudit(
        audit_id=telemetry_fixture_audit_id(provisional),
        **values,
    )


def _make_contract(
    *,
    source_replay: ThinkingRepairSourceReplayAudit,
    retirement: RolePopulationRetirementAudit,
    completion_protocol: ProspectiveThinkingCompletionProtocol,
    telemetry_contract: ThinkingTelemetryRepairContract,
    telemetry_fixture: TelemetryFixtureAudit,
    repair_packages: Sequence[ThinkingRepairTaskPackage],
    path_audits: Sequence[ThinkingRepairPathAudit],
) -> ThinkingCompletionRepairContract:
    model_config_ids = {item.model_config_id for item in repair_packages}
    thinking_binding_ids = {item.thinking_binding_id for item in repair_packages}
    if len(model_config_ids) != 1 or len(thinking_binding_ids) != 1:
        raise ValueError("v26.94 source packages do not share one model binding")
    values = {
        "source_replay_audit_id": source_replay.audit_id,
        "role_retirement_audit_id": retirement.audit_id,
        "thinking_completion_protocol_id": completion_protocol.contract_id,
        "telemetry_repair_contract_id": telemetry_contract.contract_id,
        "telemetry_fixture_audit_id": telemetry_fixture.audit_id,
        "model_config_id": next(iter(model_config_ids)),
        "thinking_binding_id": next(iter(thinking_binding_ids)),
        "thinking_policy_id": PROSPECTIVE_THINKING_MODE_POLICY.policy_id,
        "repair_task_package_ids": tuple(sorted(item.task_package_id for item in repair_packages)),
        "repair_path_audit_ids": tuple(sorted(item.audit_id for item in path_audits)),
    }
    provisional = ThinkingCompletionRepairContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ThinkingCompletionRepairContract(
        contract_id=thinking_completion_repair_contract_id(provisional),
        **values,
    )


def _make_manifest(
    *,
    run_id: str,
    contract: ThinkingCompletionRepairContract,
    role_packages: Sequence[BudgetFeasibleRoleTaskPackage],
    repair_packages: Sequence[ThinkingRepairTaskPackage],
    path_audits: Sequence[ThinkingRepairPathAudit],
    package_root: Path,
) -> ThinkingRepairManifest:
    repair_by_source = {item.source_role_task_package_id: item for item in repair_packages}
    path_by_source_strategy = {
        (item.predecessor_role_task_package_id, item.path_strategy_id): item for item in path_audits
    }
    grouped: dict[tuple[str, str], list[BudgetFeasibleRoleTaskPackage]] = defaultdict(list)
    for item in role_packages:
        grouped[(item.mechanism_id, item.role)].append(item)
    job_specs: list[tuple[BudgetFeasibleRoleTaskPackage, PathStrategy]] = []
    for mechanism in TARGET_MECHANISMS:
        capability = sorted(
            grouped[(mechanism, "capability")],
            key=lambda item: item.task_package_id,
        )
        reachability = sorted(
            grouped[(mechanism, "reachability")],
            key=lambda item: item.task_package_id,
        )
        job_specs.extend((item, "structured_direct") for item in capability)
        job_specs.extend((item, "search_then_open") for item in reachability)
        job_specs.extend((item, "search_then_structured") for item in reachability[:2])

    jobs: list[ThinkingRepairJob] = []
    for slot, (source, strategy) in enumerate(job_specs):
        repair_package = repair_by_source[source.task_package_id]
        path = path_by_source_strategy[(source.task_package_id, strategy)]
        values = {
            "repair_contract_id": contract.contract_id,
            "repair_task_package_id": repair_package.task_package_id,
            "repair_path_audit_id": path.audit_id,
            "source_task_artifact_id": source.source_task_artifact_id,
            "mechanism_id": source.mechanism_id,
            "path_strategy_id": strategy,
            "source_role": source.role,
            "job_seed": int(
                hashlib.sha256(
                    f"{run_id}|{FUTURE_EXECUTION_RUN_ID}|{slot}|{source.task_package_id}|{strategy}".encode()
                ).hexdigest()[:16],
                16,
            ),
            "model_config_id": source.model_config_id,
            "thinking_binding_id": source.thinking_binding_id,
        }
        provisional = ThinkingRepairJob.model_construct(job_id="pending", **values)
        jobs.append(
            ThinkingRepairJob(
                job_id=thinking_repair_job_id(provisional),
                **values,
            )
        )
    ordered_jobs = tuple(sorted(jobs, key=lambda item: item.job_id))
    old_manifest = ThinkingBudgetCalibrationManifest.model_validate_json(
        (package_root / V26_91_DIR / "calibration_job_manifest.json").read_text(encoding="utf-8")
    )
    old_job_ids = {item.job_id for item in old_manifest.jobs}
    mechanism_counts = dict(Counter(item.mechanism_id for item in ordered_jobs))
    path_counts = dict(Counter(item.path_strategy_id for item in ordered_jobs))
    cell_counts = dict(
        sorted(
            Counter(f"{item.mechanism_id}|{item.path_strategy_id}" for item in ordered_jobs).items()
        )
    )
    values = {
        "repair_contract_id": contract.contract_id,
        "jobs": ordered_jobs,
        "mechanism_job_counts": mechanism_counts,
        "path_job_counts": path_counts,
        "cell_job_counts": cell_counts,
        "historical_v26_92_job_overlap_count": len(
            {item.job_id for item in ordered_jobs} & old_job_ids
        ),
    }
    provisional = ThinkingRepairManifest.model_construct(manifest_id="pending", **values)
    return ThinkingRepairManifest(
        manifest_id=thinking_repair_manifest_id(provisional),
        **values,
    )


def _make_freshness(
    *,
    role_packages: Sequence[BudgetFeasibleRoleTaskPackage],
    repair_packages: Sequence[ThinkingRepairTaskPackage],
    manifest: ThinkingRepairManifest,
    package_root: Path,
) -> ThinkingRepairFreshnessAudit:
    exposed_packages = cast(
        tuple[CalibrationTaskPackage, ...],
        _rows(
            package_root / V26_91_DIR / "calibration_task_packages.json",
            CalibrationTaskPackage,
        ),
    )
    old_manifest = ThinkingBudgetCalibrationManifest.model_validate_json(
        (package_root / V26_91_DIR / "calibration_job_manifest.json").read_text(encoding="utf-8")
    )
    values = {
        "source_task_overlap_with_v26_92": len(
            {item.source_task_artifact_id for item in role_packages}
            & {item.source_task_artifact_id for item in exposed_packages}
        ),
        "semantic_source_overlap_with_v26_92": len(
            {item.semantic_source_id for item in role_packages}
            & {item.semantic_source_id for item in exposed_packages}
        ),
        "operational_package_overlap_with_v26_92": len(
            {item.operational_task_package_id for item in role_packages}
            & {item.operational_task_package_id for item in exposed_packages}
        ),
        "repair_task_package_overlap_with_v26_92": len(
            {item.task_package_id for item in repair_packages}
            & {item.task_package_id for item in exposed_packages}
        ),
        "job_overlap_with_v26_92": len(
            {item.job_id for item in manifest.jobs} & {item.job_id for item in old_manifest.jobs}
        ),
    }
    provisional = ThinkingRepairFreshnessAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return ThinkingRepairFreshnessAudit(
        audit_id=thinking_repair_freshness_audit_id(provisional),
        **values,
    )


def _mutation(name: str, callback: Callable[[], Any]) -> MutationResult:
    try:
        callback()
    except Exception as exc:
        return MutationResult(
            mutation_name=name,
            rejected=True,
            failure_type=type(exc).__name__,
        )
    raise ValueError(f"destructive mutation unexpectedly passed: {name}")


def _make_destructive_audit(
    *,
    completion_protocol: ProspectiveThinkingCompletionProtocol,
    telemetry_fixture: TelemetryFixtureAudit,
    contract: ThinkingCompletionRepairContract,
    manifest: ThinkingRepairManifest,
    freshness: ThinkingRepairFreshnessAudit,
    path: ThinkingRepairPathAudit,
) -> DestructivePreflightAudit:
    valid_decision = {
        "action": "call_tool",
        "arguments": {"query": "public"},
        "tool_id": "query_structured_fact",
    }
    mutation_results = (
        _mutation(
            "missing_response_model",
            lambda: RedactedProviderResponseEnvelope.model_validate(
                {
                    **telemetry_fixture.exact_valid_envelope.model_dump(mode="json"),
                    "response_model": "",
                }
            ),
        ),
        _mutation(
            "changed_response_model",
            lambda: require_admitted_response_envelope(
                telemetry_fixture.exact_valid_envelope.model_copy(
                    update={"response_model": "deepseek-v4-pro"}
                ),
                expected_model="deepseek-v4-flash",
            ),
        ),
        _mutation(
            "provider_native_tool_call",
            lambda: require_admitted_response_envelope(
                telemetry_fixture.native_tool_envelope,
                expected_model="deepseek-v4-flash",
            ),
        ),
        _mutation(
            "missing_thinking_telemetry",
            lambda: require_admitted_response_envelope(
                RedactedProviderResponseEnvelope.model_validate(
                    {
                        **telemetry_fixture.exact_valid_envelope.model_dump(mode="json"),
                        "reasoning_content_length": 0,
                        "reasoning_content_present": False,
                        "reasoning_tokens": 0,
                    }
                ),
                expected_model="deepseek-v4-flash",
            ),
        ),
        _mutation(
            "private_reasoning_persistence_field",
            lambda: RedactedProviderResponseEnvelope.model_validate(
                {
                    **telemetry_fixture.exact_valid_envelope.model_dump(mode="json"),
                    "reasoning_content": "forbidden",
                }
            ),
        ),
        _mutation(
            "raw_http_body_persistence",
            lambda: RedactedProviderResponseEnvelope.model_validate(
                {
                    **telemetry_fixture.exact_valid_envelope.model_dump(mode="json"),
                    "raw_http_body": "forbidden",
                }
            ),
        ),
        _mutation(
            "second_rescue_call",
            lambda: ProspectiveThinkingCompletionProtocol.model_validate(
                {
                    **completion_protocol.model_dump(mode="json"),
                    "maximum_rescue_calls_per_job": 2,
                }
            ),
        ),
        _mutation(
            "rescue_reuses_previous_content",
            lambda: ProspectiveThinkingCompletionProtocol.model_validate(
                {
                    **completion_protocol.model_dump(mode="json"),
                    "rescue_reuses_previous_final_content": True,
                }
            ),
        ),
        _mutation(
            "rescue_repeats_deliberation",
            lambda: ProspectiveThinkingCompletionProtocol.model_validate(
                {
                    **completion_protocol.model_dump(mode="json"),
                    "rescue_requests_repeated_planning_or_deliberation": True,
                }
            ),
        ),
        _mutation(
            "rescue_reduction_below_ten_percent",
            lambda: ThinkingRepairPathAudit.model_validate(
                {
                    **path.model_dump(mode="json"),
                    "minimum_rescue_size_reduction_basis_points": 999,
                }
            ),
        ),
        _mutation(
            "model_plan_call_reintroduced",
            lambda: ProspectiveThinkingCompletionProtocol.model_validate(
                {
                    **completion_protocol.model_dump(mode="json"),
                    "model_plan_request_count": 1,
                }
            ),
        ),
        _mutation(
            "unknown_response_field",
            lambda: project_model_completion(
                "decision",
                {**valid_decision, "corrected_action": "hidden"},
            ),
        ),
        _mutation(
            "early_final_in_decision",
            lambda: project_model_completion(
                "decision",
                {"action": "emit_final", "arguments": {}, "tool_id": "none"},
            ),
        ),
        _mutation(
            "host_selected_tool_inserted",
            lambda: ProspectiveThinkingCompletionProtocol.model_validate(
                {
                    **completion_protocol.model_dump(mode="json"),
                    "model_tool_choice_preserved": False,
                }
            ),
        ),
        _mutation(
            "oracle_response_field",
            lambda: project_model_completion(
                "decision",
                {**valid_decision, "oracle": {"action": "query"}},
            ),
        ),
        _mutation(
            "completion_threshold_relaxation",
            lambda: ThinkingCompletionRepairContract.model_validate(
                {
                    **contract.model_dump(mode="json"),
                    "completion_threshold_relaxation_forbidden": False,
                }
            ),
        ),
        _mutation(
            "numeric_failure_threshold_relaxation",
            lambda: ThinkingCompletionRepairContract.model_validate(
                {
                    **contract.model_dump(mode="json"),
                    "failure_gate_threshold": 0.20,
                }
            ),
        ),
        _mutation(
            "role_population_reenabled",
            lambda: ThinkingCompletionRepairContract.model_validate(
                {
                    **contract.model_dump(mode="json"),
                    "v26_90_role_execution_allowed": True,
                }
            ),
        ),
        _mutation(
            "execution_authorized_without_runner",
            lambda: ThinkingRepairManifest.model_validate(
                {
                    **manifest.model_dump(mode="json"),
                    "execution_authorized": True,
                }
            ),
        ),
        _mutation(
            "one_token_over_rollout",
            lambda: ThinkingRepairPathAudit.model_validate(
                {
                    **path.model_dump(mode="json"),
                    "full_path_upper_bound": ROLLOUT_UPPER_BOUND + 1,
                    "minimum_headroom_tokens": 0,
                }
            ),
        ),
        _mutation(
            "historical_source_overlap",
            lambda: ThinkingRepairFreshnessAudit.model_validate(
                {
                    **freshness.model_dump(mode="json"),
                    "source_task_overlap_with_v26_92": 1,
                }
            ),
        ),
    )
    values = {
        "mutation_results": mutation_results,
        "rejected_mutation_count": len(mutation_results),
    }
    provisional = DestructivePreflightAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return DestructivePreflightAudit(
        audit_id=destructive_preflight_audit_id(provisional),
        **values,
    )


def build_thinking_completion_telemetry_repair_preflight(
    *,
    run_id: str,
    output_dir: Path,
    package_root: Path,
) -> ThinkingCompletionTelemetryRepairPreflightReport:
    v26_93_report, telemetry_contract, v26_90_report, source_replay = _build_source_replay(
        package_root
    )
    role_dir = package_root / V26_90_DIR
    role_packages = cast(
        tuple[BudgetFeasibleRoleTaskPackage, ...],
        _rows(
            role_dir / "budget_feasible_role_task_packages.json",
            BudgetFeasibleRoleTaskPackage,
        ),
    )
    role_paths = cast(
        tuple[BudgetQualifiedPathAudit, ...],
        _rows(role_dir / "budget_qualified_path_audits.json", BudgetQualifiedPathAudit),
    )
    prompt_contracts = cast(
        tuple[CompactPromptContract, ...],
        _rows(role_dir / "compact_prompt_contracts.json", CompactPromptContract),
    )
    records = cast(
        tuple[OperationalTaskRecord, ...],
        _rows(role_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    trajectories = cast(
        tuple[Trajectory, ...],
        _rows(role_dir / "compiler_trajectories.json", Trajectory),
    )
    if (
        len(role_packages) != 24
        or len(role_paths) != 48
        or len(prompt_contracts) != 24
        or len(records) != 24
        or len(trajectories) != 48
    ):
        raise ValueError("v26.90 static role denominator changed")

    model_config = AgentModelConfig.model_validate(
        json.loads((package_root / MODEL_PROFILE_PATH).read_text(encoding="utf-8"))["model"]
    )
    require_prospective_thinking(model_config)
    if model_config.max_output_tokens != COMPLETION_UPPER_BOUND:
        raise ValueError("v26.94 model profile changed Completion bound")
    completion_protocol = make_prospective_thinking_completion_protocol()
    if _cp_upper(0, 32) > 0.10 or _cp_upper(1, 32) <= 0.10:
        raise ValueError("v26.94 zero-failure Completion Gate boundary changed")

    retirement = _build_retirement(
        package_root=package_root,
        v26_90_report=v26_90_report,
        role_packages=role_packages,
    )
    repair_packages = _make_task_packages(
        role_packages=role_packages,
        completion_protocol=completion_protocol,
        telemetry_contract=telemetry_contract,
    )
    path_audits = _build_path_audits(
        role_packages=role_packages,
        repair_packages=repair_packages,
        role_paths=role_paths,
        prompt_contracts=prompt_contracts,
        records=records,
        trajectories=trajectories,
    )
    telemetry_fixture = _build_telemetry_fixture()
    contract = _make_contract(
        source_replay=source_replay,
        retirement=retirement,
        completion_protocol=completion_protocol,
        telemetry_contract=telemetry_contract,
        telemetry_fixture=telemetry_fixture,
        repair_packages=repair_packages,
        path_audits=path_audits,
    )
    manifest = _make_manifest(
        run_id=run_id,
        contract=contract,
        role_packages=role_packages,
        repair_packages=repair_packages,
        path_audits=path_audits,
        package_root=package_root,
    )
    freshness = _make_freshness(
        role_packages=role_packages,
        repair_packages=repair_packages,
        manifest=manifest,
        package_root=package_root,
    )
    destructive = _make_destructive_audit(
        completion_protocol=completion_protocol,
        telemetry_fixture=telemetry_fixture,
        contract=contract,
        manifest=manifest,
        freshness=freshness,
        path=path_audits[0],
    )

    paths = {
        "source_replay": output_dir / "source_replay_audit.json",
        "retirement": output_dir / "role_population_retirement_audit.json",
        "completion_protocol": output_dir / "thinking_completion_protocol.json",
        "task_packages": output_dir / "thinking_repair_task_packages.json",
        "path_audits": output_dir / "thinking_repair_path_audits.json",
        "telemetry_fixture": output_dir / "telemetry_fixture_audit.json",
        "contract": output_dir / "thinking_repair_contract.json",
        "manifest": output_dir / "thinking_repair_job_manifest.json",
        "freshness": output_dir / "thinking_repair_freshness_audit.json",
        "destructive": output_dir / "destructive_preflight_audit.json",
    }
    _write_json(paths["source_replay"], source_replay.model_dump(mode="json"))
    _write_json(paths["retirement"], retirement.model_dump(mode="json"))
    _write_json(
        paths["completion_protocol"],
        completion_protocol.model_dump(mode="json"),
    )
    _write_models(paths["task_packages"], repair_packages, "task_package_id")
    _write_models(paths["path_audits"], path_audits, "audit_id")
    _write_json(paths["telemetry_fixture"], telemetry_fixture.model_dump(mode="json"))
    _write_json(paths["contract"], contract.model_dump(mode="json"))
    _write_json(paths["manifest"], manifest.model_dump(mode="json"))
    _write_json(paths["freshness"], freshness.model_dump(mode="json"))
    _write_json(paths["destructive"], destructive.model_dump(mode="json"))
    counts = {
        "source_replay": 1,
        "retirement": 1,
        "completion_protocol": 1,
        "task_packages": len(repair_packages),
        "path_audits": len(path_audits),
        "telemetry_fixture": 1,
        "contract": 1,
        "manifest": 1,
        "freshness": 1,
        "destructive": 1,
    }
    detail_files = tuple(
        sorted(
            (_detail(path, output_dir, counts[key]) for key, path in paths.items()),
            key=lambda item: item.relative_path,
        )
    )
    implementation_paths = tuple(
        sorted(
            {
                *(item.relative_path for item in v26_90_report.implementation_source_files),
                *(item.relative_path for item in v26_93_report.implementation_source_files),
                COMPLETION_SOURCE_PATH,
                CLIENT_SOURCE_PATH,
                PREFLIGHT_SOURCE_PATH,
            }
        )
    )
    implementation_files = tuple(
        ImplementationSourceFile(
            relative_path=path,
            sha256=_sha256(package_root / path),
        )
        for path in implementation_paths
    )
    values = {
        "run_id": run_id,
        "source_replay_audit_id": source_replay.audit_id,
        "role_retirement_audit_id": retirement.audit_id,
        "thinking_completion_protocol_id": completion_protocol.contract_id,
        "telemetry_fixture_audit_id": telemetry_fixture.audit_id,
        "repair_contract_id": contract.contract_id,
        "repair_manifest_id": manifest.manifest_id,
        "freshness_audit_id": freshness.audit_id,
        "destructive_preflight_audit_id": destructive.audit_id,
        "source_replayed_file_count": source_replay.replayed_file_count,
        "compiler_projection_count": sum(item.compiler_projection_count for item in path_audits),
        "maximum_path_upper_bound": max(item.full_path_upper_bound for item in path_audits),
        "minimum_path_headroom_tokens": min(item.minimum_headroom_tokens for item in path_audits),
        "maximum_prompt_utf8_bytes": max(item.maximum_prompt_utf8_bytes for item in path_audits),
        "detail_files": detail_files,
        "implementation_source_files": implementation_files,
    }
    provisional = ThinkingCompletionTelemetryRepairPreflightReport.model_construct(
        report_id="pending",
        **values,
    )
    report = ThinkingCompletionTelemetryRepairPreflightReport(
        report_id=thinking_repair_preflight_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.94 Thinking Completion and telemetry repair preflight"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_thinking_completion_telemetry_repair_preflight(
        run_id=args.run_id,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
