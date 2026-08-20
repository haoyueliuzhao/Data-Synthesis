from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
    OperationalTaskRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_preflight import (  # noqa: E501
    VerifierBoundInstrumentContract,
    VerifierBoundInstrumentJob,
    VerifierBoundInstrumentJobManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_requalification import (  # noqa: E501
    EXPECTED_CONTRACT_ID,
    EXPECTED_JOB_COUNT,
    EXPECTED_MANIFEST_ID,
    ONLINE_IMPLEMENTATION_SOURCE_PATHS,
    InstrumentMechanismSummary,
    OnlineSourceReplayAudit,
    RawFileDescriptor,
    RawProviderCallArtifact,
    VerifierBoundInstrumentDiagnostic,
    VerifierBoundInstrumentExecutionBinding,
    VerifierBoundInstrumentRawAudit,
    VerifierBoundInstrumentRequalificationReport,
    VerifierBoundInstrumentRollout,
    VerifierBoundRawExecutionArtifact,
    _append_jsonl,
    _diagnostic,
    _load_raw_execution,
    _make_report,
    _provider_call_path,
    _raw_execution_path,
    _RawFirstJournalClient,
    _recursive_noninterference,
    _safe_error,
    _score_with_failure_capture,
    _sha256,
    _write_json_atomic,
    _write_raw_atomic,
    provider_call_id,
    raw_execution_artifact_id,
    verifier_bound_instrument_raw_audit_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    VerifierV2TaskReplayBinding,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    IterativeAgentFailureArtifact,
    IterativeAgentProtocolProfile,
    IterativeAgentSolver,
    IterativeAgentSolveResult,
    LLMClientError,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

V26_FAILED_RUN_JOB_AUDIT_VERSION = "finance_v26_verifier_bound_failed_job_audit.v1"
V26_FAILED_RUN_AUDIT_VERSION = "finance_v26_verifier_bound_failed_run_audit.v1"
V26_RECOVERY_CONTRACT_VERSION = "finance_v26_verifier_bound_recovery_contract.v1"
V26_RECOVERY_SOURCE_REPLAY_VERSION = "finance_v26_verifier_bound_recovery_source_replay.v1"
V26_RECOVERY_JOB_VERSION = "finance_v26_verifier_bound_recovery_job.v1"
V26_RECOVERY_MANIFEST_VERSION = "finance_v26_verifier_bound_recovery_manifest.v1"
V26_RECOVERY_BINDING_VERSION = "finance_v26_verifier_bound_recovery_binding.v1"
V26_RECOVERY_PREFLIGHT_VERSION = "finance_v26_verifier_bound_recovery_preflight.v1"
V26_RECOVERY_REPORT_VERSION = "finance_v26_verifier_bound_recovery_report.v1"

FAILED_EXECUTION_BINDING_ID = (
    "finance_v26_verifier_bound_instrument_execution_binding:"
    "27250c6b577243a7c87f321c72877dd7ff3ccfaa0d5ea48a92d7a6db6eda2ae2"
)
FAILED_SOURCE_REPLAY_AUDIT_ID = (
    "finance_v26_verifier_bound_online_source_replay:"
    "3ac3660b7884fb0afeb5c5c7c809a577e73ce9f819adc8ad32016ffb1d72d766"
)
FAILED_EXPOSED_JOB_COUNT: Literal[17] = 17
UNOPENED_CONTINUATION_JOB_COUNT: Literal[15] = 15
FAILED_PROVIDER_CALL_COUNT: Literal[146] = 146
FAILED_PROVIDER_TOTAL_TOKENS: Literal[1336075] = 1_336_075
FAILED_ESTIMATED_COST_USD = "0.168894560800000016264"
DEFAULT_WORKERS = 15

RECOVERY_IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted(
        {
            *ONLINE_IMPLEMENTATION_SOURCE_PATHS,
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_verifier_bound_instrument_recovery.py"
            ),
        }
    )
)

RecoveryRole = Literal["zero_generation_replay", "unopened_model_continuation"]
ReplayTerminal = Literal["completed_trajectory", "model_contract_failure"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecoverySourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> RecoverySourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("Recovery source replay hash changed")
        return self


class RecoverySourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_source_replay_audit_id: str = FAILED_SOURCE_REPLAY_AUDIT_ID
    entries: tuple[RecoverySourceReplayEntry, ...] = Field(min_length=67)
    replayed_file_count: int = Field(ge=67)
    replay_pass_count: int = Field(ge=67)
    source_replay_before_client_construction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_RECOVERY_SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RecoverySourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("Recovery source replay paths are not canonical")
        if self.replayed_file_count != len(self.entries) or (
            self.replay_pass_count != self.replayed_file_count
        ):
            raise ValueError("Recovery source replay denominator is incomplete")
        if self.audit_id != recovery_source_replay_audit_id(self):
            raise ValueError("Recovery source replay identity is invalid")
        return self


class FailedRunJobAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    provider_call_count: int = Field(ge=1)
    provider_total_tokens: int = Field(ge=1)
    estimated_cost_usd: str = Field(min_length=1)
    replay_terminal: ReplayTerminal
    observation_count: int = Field(ge=0)
    recorded_call_count: int = Field(ge=1)
    consumed_call_count: int = Field(ge=1)
    prompts_exact: Literal[True] = True
    provider_telemetry_equal_before_host_augmentation: Literal[True] = True
    response_payloads_complete: Literal[True] = True
    response_shape_only_host_augmentation: Literal["prompt_component_bytes"] = (
        "prompt_component_bytes"
    )
    zero_generation_replay_passed: Literal[True] = True
    schema_version: str = V26_FAILED_RUN_JOB_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FailedRunJobAudit:
        if self.recorded_call_count != self.consumed_call_count or (
            self.provider_call_count != self.recorded_call_count
        ):
            raise ValueError("failed-run Job Replay did not consume its exact Provider stream")
        if self.audit_id != failed_run_job_audit_id(self):
            raise ValueError("failed-run Job audit identity is invalid")
        return self


class FailedRunAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_execution_run_id: str = Field(min_length=1)
    failed_execution_binding_id: str = FAILED_EXECUTION_BINDING_ID
    source_replay_audit_id: str = FAILED_SOURCE_REPLAY_AUDIT_ID
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    exposed_job_ids: tuple[str, ...] = Field(min_length=17, max_length=17)
    unopened_job_ids: tuple[str, ...] = Field(min_length=15, max_length=15)
    exposed_job_count: Literal[17] = FAILED_EXPOSED_JOB_COUNT
    unopened_job_count: Literal[15] = UNOPENED_CONTINUATION_JOB_COUNT
    raw_provider_call_artifact_count: Literal[146] = FAILED_PROVIDER_CALL_COUNT
    raw_provider_artifact_manifest_hash: str = Field(min_length=1)
    provider_total_tokens: Literal[1336075] = FAILED_PROVIDER_TOTAL_TOKENS
    estimated_cost_usd: str = FAILED_ESTIMATED_COST_USD
    http_success_count: Literal[146] = FAILED_PROVIDER_CALL_COUNT
    json_contract_success_count: Literal[146] = FAILED_PROVIDER_CALL_COUNT
    raw_execution_artifact_count: Literal[0] = 0
    rollout_checkpoint_count: Literal[0] = 0
    model_result_row_count: Literal[0] = 0
    completed_trajectory_replay_count: int = Field(ge=0, le=17)
    model_contract_failure_replay_count: int = Field(ge=0, le=17)
    recovered_observation_count: int = Field(ge=0)
    job_audits: tuple[FailedRunJobAudit, ...] = Field(min_length=17, max_length=17)
    failure_stage: Literal["post_provider_pre_raw_execution"] = "post_provider_pre_raw_execution"
    failure_cause: Literal[
        "provider_telemetry_compared_to_host_augmented_telemetry_by_full_object_equality"
    ] = "provider_telemetry_compared_to_host_augmented_telemetry_by_full_object_equality"
    historical_model_calls_repeated: Literal[False] = False
    historical_outcomes_rescored: Literal[False] = False
    status: Literal["instrument_execution_failed"] = "instrument_execution_failed"
    next_permitted_stage: Literal["frozen_raw_recovery_protocol_only"] = (
        "frozen_raw_recovery_protocol_only"
    )
    schema_version: str = V26_FAILED_RUN_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FailedRunAudit:
        if self.failed_execution_binding_id != FAILED_EXECUTION_BINDING_ID or (
            self.source_replay_audit_id != FAILED_SOURCE_REPLAY_AUDIT_ID
        ):
            raise ValueError("failed-run audit crosses the executed binding")
        groups = (self.exposed_job_ids, self.unopened_job_ids)
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("failed-run Job sets are not canonical")
        if set(self.exposed_job_ids) & set(self.unopened_job_ids):
            raise ValueError("failed-run exposed and unopened Job sets overlap")
        if len(self.job_audits) != len(self.exposed_job_ids):
            raise ValueError("failed-run audit loses exposed Job diagnostics")
        if (
            self.completed_trajectory_replay_count + (self.model_contract_failure_replay_count)
            != self.exposed_job_count
        ):
            raise ValueError("failed-run Replay terminal denominator is incomplete")
        if self.audit_id != failed_run_audit_id(self):
            raise ValueError("failed-run audit identity is invalid")
        return self


class RecoveryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    recovery_run_id: str = Field(min_length=1)
    failed_run_audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    original_contract_id: str = EXPECTED_CONTRACT_ID
    original_job_manifest_id: str = EXPECTED_MANIFEST_ID
    original_execution_binding_id: str = FAILED_EXECUTION_BINDING_ID
    exposed_job_ids: tuple[str, ...] = Field(min_length=17, max_length=17)
    unopened_job_ids: tuple[str, ...] = Field(min_length=15, max_length=15)
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    zero_generation_replay_job_count: Literal[17] = FAILED_EXPOSED_JOB_COUNT
    unopened_model_continuation_job_count: Literal[15] = UNOPENED_CONTINUATION_JOB_COUNT
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    maximum_total_model_tokens_per_rollout: Literal[120000] = 120000
    maximum_total_estimated_cost_usd: float = Field(default=2.0, ge=2.0, le=2.0)
    exposed_job_model_calls_forbidden: Literal[True] = True
    unopened_job_exactly_once_execution_required: Literal[True] = True
    recorded_payload_replay_must_consume_all_calls: Literal[True] = True
    recorded_prompt_exact_equality_required: Literal[True] = True
    provider_vs_host_telemetry_comparison_rule: Literal[
        "provider_fields_equal_before_prompt_component_bytes_augmentation"
    ] = "provider_fields_equal_before_prompt_component_bytes_augmentation"
    no_job_selected_by_model_outcome: Literal[True] = True
    raw_execution_before_verifier_scoring_required: Literal[True] = True
    invalid_model_outcomes_retained: Literal[True] = True
    compiler_witness_empirical_count: Literal[0] = 0
    historical_diagnostic_candidate_count: Literal[0] = 0
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=18)
    schema_version: str = V26_RECOVERY_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> RecoveryContract:
        if (
            self.original_contract_id != EXPECTED_CONTRACT_ID
            or self.original_job_manifest_id != EXPECTED_MANIFEST_ID
            or self.original_execution_binding_id != FAILED_EXECUTION_BINDING_ID
        ):
            raise ValueError("Recovery Contract crosses original execution identities")
        if set(self.exposed_job_ids) & set(self.unopened_job_ids) or (
            len(set(self.exposed_job_ids) | set(self.unopened_job_ids)) != EXPECTED_JOB_COUNT
        ):
            raise ValueError("Recovery Contract Job partition is invalid")
        paths = tuple(item.relative_path for item in self.implementation_source_files)
        if paths != RECOVERY_IMPLEMENTATION_SOURCE_PATHS:
            raise ValueError("Recovery Contract implementation manifest is incomplete")
        if self.contract_id != recovery_contract_id(self):
            raise ValueError("Recovery Contract identity is invalid")
        return self


class RecoveryJob(FrozenModel):
    recovery_job_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    original_job: VerifierBoundInstrumentJob
    recovery_role: RecoveryRole
    original_provider_capture_binding_id: str | None = None
    model_call_permitted: bool
    schema_version: str = V26_RECOVERY_JOB_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> RecoveryJob:
        replay = self.recovery_role == "zero_generation_replay"
        if replay != (self.original_provider_capture_binding_id == FAILED_EXECUTION_BINDING_ID):
            raise ValueError("Recovery Job Provider-capture lineage is inconsistent")
        if self.model_call_permitted == replay:
            raise ValueError("Recovery Job model-call authority is inconsistent")
        if self.recovery_job_id != recovery_job_id(self):
            raise ValueError("Recovery Job identity is invalid")
        return self


class RecoveryManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    jobs: tuple[RecoveryJob, ...] = Field(min_length=32, max_length=32)
    schema_version: str = V26_RECOVERY_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> RecoveryManifest:
        if any(item.recovery_contract_id != self.recovery_contract_id for item in self.jobs):
            raise ValueError("Recovery Manifest crosses Contracts")
        identities = tuple(item.recovery_job_id for item in self.jobs)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("Recovery Job identities are not canonical")
        original_ids = {item.original_job.job_id for item in self.jobs}
        if len(original_ids) != EXPECTED_JOB_COUNT:
            raise ValueError("Recovery Manifest loses original Jobs")
        counts = Counter(item.recovery_role for item in self.jobs)
        if counts != Counter(
            {
                "zero_generation_replay": FAILED_EXPOSED_JOB_COUNT,
                "unopened_model_continuation": UNOPENED_CONTINUATION_JOB_COUNT,
            }
        ):
            raise ValueError("Recovery Manifest role denominator changed")
        if self.manifest_id != recovery_manifest_id(self):
            raise ValueError("Recovery Manifest identity is invalid")
        return self


class RecoveryExecutionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    recovery_run_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    original_execution_binding_id: str = FAILED_EXECUTION_BINDING_ID
    original_provider_call_artifact_count: Literal[146] = FAILED_PROVIDER_CALL_COUNT
    original_provider_payloads_replayed_before_continuation: Literal[True] = True
    source_replay_before_client_construction: Literal[True] = True
    raw_only_recovery_supported: Literal[True] = True
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=18)
    schema_version: str = V26_RECOVERY_BINDING_VERSION

    @property
    def execution_run_id(self) -> str:
        """Expose the interface used by the frozen v26.78 aggregate builder."""
        return self.recovery_run_id

    @model_validator(mode="after")
    def validate_binding(self) -> RecoveryExecutionBinding:
        if self.original_execution_binding_id != FAILED_EXECUTION_BINDING_ID:
            raise ValueError("Recovery Binding crosses the failed execution")
        paths = tuple(item.relative_path for item in self.implementation_source_files)
        if paths != RECOVERY_IMPLEMENTATION_SOURCE_PATHS:
            raise ValueError("Recovery Binding implementation manifest is incomplete")
        if self.binding_id != recovery_execution_binding_id(self):
            raise ValueError("Recovery Binding identity is invalid")
        return self


class RecoveryRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    recovery_execution_binding_id: str = Field(min_length=1)
    original_execution_binding_id: str = FAILED_EXECUTION_BINDING_ID
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    observed_job_count: int = Field(ge=0, le=32)
    zero_generation_replay_job_count: int = Field(ge=0, le=17)
    continuation_job_count: int = Field(ge=0, le=15)
    exposed_job_model_call_count: Literal[0] = 0
    original_provider_artifact_count: int = Field(ge=0)
    continuation_provider_artifact_count: int = Field(ge=0)
    original_provider_exact_byte_pass_count: int = Field(ge=0)
    provider_artifact_binding_pass_count: int = Field(ge=0)
    provider_telemetry_pre_host_augmentation_pass_count: int = Field(ge=0)
    raw_execution_recovery_binding_pass_count: int = Field(ge=0, le=32)
    provider_call_ids_unique: bool
    duplicate_provider_call_ids: tuple[str, ...] = ()
    failed_artifacts: tuple[str, ...] = ()
    status: Literal["passed", "partial", "failed"]
    schema_version: str = "finance_v26_verifier_bound_recovery_raw_lineage_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> RecoveryRawLineageAudit:
        observed_provider_count = (
            self.original_provider_artifact_count + self.continuation_provider_artifact_count
        )
        complete = bool(
            self.observed_job_count == EXPECTED_JOB_COUNT
            and self.zero_generation_replay_job_count == FAILED_EXPOSED_JOB_COUNT
            and self.continuation_job_count == UNOPENED_CONTINUATION_JOB_COUNT
            and self.original_provider_artifact_count == FAILED_PROVIDER_CALL_COUNT
            and self.original_provider_exact_byte_pass_count == FAILED_PROVIDER_CALL_COUNT
            and self.provider_artifact_binding_pass_count == observed_provider_count
            and self.provider_telemetry_pre_host_augmentation_pass_count == observed_provider_count
            and self.raw_execution_recovery_binding_pass_count == EXPECTED_JOB_COUNT
        )
        partial = bool(
            self.zero_generation_replay_job_count + self.continuation_job_count
            == self.observed_job_count
            and self.original_provider_exact_byte_pass_count
            == self.original_provider_artifact_count
            and self.provider_artifact_binding_pass_count == observed_provider_count
            and self.provider_telemetry_pre_host_augmentation_pass_count == observed_provider_count
            and self.raw_execution_recovery_binding_pass_count == self.observed_job_count
        )
        expected = (
            "passed"
            if complete and self.provider_call_ids_unique and not self.failed_artifacts
            else "partial"
            if partial and self.provider_call_ids_unique and not self.failed_artifacts
            else "failed"
        )
        if self.status != expected:
            raise ValueError("Recovery raw-lineage status is inconsistent")
        if self.audit_id != recovery_raw_lineage_audit_id(self):
            raise ValueError("Recovery raw-lineage audit identity is invalid")
        return self


class RecoveryPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    recovery_run_id: str = Field(min_length=1)
    failed_run_audit_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    recovery_execution_binding_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    source_replay_file_count: int = Field(ge=18)
    source_replay_pass_count: int = Field(ge=18)
    original_provider_artifact_replay_count: Literal[146] = FAILED_PROVIDER_CALL_COUNT
    exposed_job_zero_generation_replay_count: Literal[17] = FAILED_EXPOSED_JOB_COUNT
    unopened_job_count: Literal[15] = UNOPENED_CONTINUATION_JOB_COUNT
    exposed_job_model_call_count: Literal[0] = 0
    historical_job_retry_count: Literal[0] = 0
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal[
        "zero_generation_replay_17_and_exact_unopened_15_continuation_only"
    ] = "zero_generation_replay_17_and_exact_unopened_15_continuation_only"
    recovery_execution_authorized: Literal[True] = True
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_RECOVERY_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> RecoveryPreflightReport:
        if self.source_replay_pass_count != self.source_replay_file_count:
            raise ValueError("Recovery preflight source replay is incomplete")
        if self.report_id != recovery_preflight_report_id(self):
            raise ValueError("Recovery preflight report identity is invalid")
        return self


class RecoveryExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    recovery_run_id: str = Field(min_length=1)
    failed_run_audit_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    recovery_execution_binding_id: str = Field(min_length=1)
    zero_generation_replayed_job_count: Literal[17] = FAILED_EXPOSED_JOB_COUNT
    continuation_model_job_count: Literal[15] = UNOPENED_CONTINUATION_JOB_COUNT
    exposed_job_model_call_count: Literal[0] = 0
    original_provider_call_count: Literal[146] = FAILED_PROVIDER_CALL_COUNT
    continuation_provider_call_count: int = Field(ge=0)
    total_provider_call_count: int = Field(ge=146)
    original_provider_total_tokens: Literal[1336075] = FAILED_PROVIDER_TOTAL_TOKENS
    continuation_provider_total_tokens: int = Field(ge=0)
    total_provider_tokens: int = Field(ge=1336075)
    original_estimated_cost_usd: str = FAILED_ESTIMATED_COST_USD
    continuation_estimated_cost_usd: str = Field(min_length=1)
    total_estimated_cost_usd: str = Field(min_length=1)
    instrument_result: VerifierBoundInstrumentRequalificationReport
    mechanism_summaries: tuple[InstrumentMechanismSummary, ...]
    raw_lineage_audit: RecoveryRawLineageAudit
    raw_first_recovery_lineage_passed: bool
    resource_budget_passed: bool
    recovery_instrument_ready: bool
    status: Literal["passed", "blocked"]
    next_permitted_stage: Literal[
        "verifier_bound_recovery_postrun_audit_only",
        "verifier_bound_recovery_failure_audit_only",
        "resource_budget_audit_only",
    ]
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_RECOVERY_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> RecoveryExecutionReport:
        if self.total_provider_call_count != (
            self.original_provider_call_count + self.continuation_provider_call_count
        ):
            raise ValueError("Recovery report Provider-call accounting is inconsistent")
        if self.total_provider_tokens != (
            self.original_provider_total_tokens + self.continuation_provider_total_tokens
        ):
            raise ValueError("Recovery report token accounting is inconsistent")
        if Decimal(self.total_estimated_cost_usd) != (
            Decimal(self.original_estimated_cost_usd)
            + Decimal(self.continuation_estimated_cost_usd)
        ):
            raise ValueError("Recovery report cost accounting is inconsistent")
        if (
            self.total_provider_call_count != self.instrument_result.provider_call_count
            or self.total_provider_tokens != self.instrument_result.provider_total_tokens
            or Decimal(self.total_estimated_cost_usd)
            != Decimal(self.instrument_result.estimated_cost_usd)
            or self.mechanism_summaries != self.instrument_result.mechanism_summaries
        ):
            raise ValueError("Recovery report differs from its Instrument aggregate")
        if self.raw_first_recovery_lineage_passed != (self.raw_lineage_audit.status == "passed"):
            raise ValueError("Recovery report lineage status is inconsistent")
        expected_status = "passed" if self.recovery_instrument_ready else "blocked"
        if self.status != expected_status:
            raise ValueError("Recovery report status is inconsistent")
        expected_stage = (
            "verifier_bound_recovery_postrun_audit_only"
            if self.status == "passed"
            else "resource_budget_audit_only"
            if not self.resource_budget_passed
            else "verifier_bound_recovery_failure_audit_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Recovery report transition is inconsistent")
        if self.report_id != recovery_execution_report_id(self):
            raise ValueError("Recovery execution report identity is invalid")
        return self


class _RecordedReplayClient:
    def __init__(
        self,
        config: AgentModelConfig,
        calls: tuple[RawProviderCallArtifact, ...],
    ) -> None:
        self.config = config
        self.calls = calls
        self.index = 0

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if self.index >= len(self.calls):
            raise RuntimeError("recorded Replay requested an unobserved Provider call")
        call = self.calls[self.index]
        if prompt != call.prompt or hashlib.sha256(prompt.encode()).hexdigest() != (
            call.prompt_sha256
        ):
            raise RuntimeError(f"recorded Replay Prompt mismatch at call {self.index}")
        if call.response_payload is None:
            raise RuntimeError(f"recorded Replay call {self.index} has no response payload")
        self.index += 1
        return call.response_payload, call.telemetry


class _RecoveryPrepared:
    def __init__(
        self,
        *,
        original_contract: VerifierBoundInstrumentContract,
        original_manifest: VerifierBoundInstrumentJobManifest,
        failed_execution_binding: VerifierBoundInstrumentExecutionBinding,
        failed_audit: FailedRunAudit,
        source_replay: RecoverySourceReplayAudit,
        recovery_contract: RecoveryContract,
        recovery_manifest: RecoveryManifest,
        recovery_binding: RecoveryExecutionBinding,
        preflight: RecoveryPreflightReport,
        records: tuple[OperationalTaskRecord, ...],
        environments: tuple[AgentToolEnvironmentManifest, ...],
        task_bindings: tuple[VerifierV2TaskReplayBinding, ...],
        replay_contract: AuthorityPreservingReplayContract,
        calls_by_job: Mapping[str, tuple[RawProviderCallArtifact, ...]],
        provider_manifest: tuple[dict[str, Any], ...],
    ) -> None:
        self.original_contract = original_contract
        self.original_manifest = original_manifest
        self.failed_execution_binding = failed_execution_binding
        self.failed_audit = failed_audit
        self.source_replay = source_replay
        self.recovery_contract = recovery_contract
        self.recovery_manifest = recovery_manifest
        self.recovery_binding = recovery_binding
        self.preflight = preflight
        self.records = records
        self.environments = environments
        self.task_bindings = task_bindings
        self.replay_contract = replay_contract
        self.calls_by_job = calls_by_job
        self.provider_manifest = provider_manifest


def _implementation_sources(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(relative_path=relative, sha256=_sha256(package_root / relative))
        for relative in RECOVERY_IMPLEMENTATION_SOURCE_PATHS
    )


def _load_rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _provider_telemetry_equal_before_host_augmentation(
    raw: ModelCallTelemetry,
    replayed: ModelCallTelemetry,
) -> bool:
    raw_payload = raw.model_dump(mode="json")
    replayed_payload = replayed.model_dump(mode="json")
    if raw_payload == replayed_payload:
        return True
    response_shape = dict(replayed_payload["response_shape"])
    prompt_component_bytes = response_shape.pop("prompt_component_bytes", None)
    replayed_payload["response_shape"] = response_shape
    return prompt_component_bytes is not None and raw_payload == replayed_payload


def _runtime(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
) -> FinanceExecutableSupportRuntime:
    recovery = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    return FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery,
    )


def _replay_recorded_job(
    *,
    job: VerifierBoundInstrumentJob,
    contract: VerifierBoundInstrumentContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    calls: tuple[RawProviderCallArtifact, ...],
) -> tuple[
    IterativeAgentSolveResult | None,
    IterativeAgentFailureArtifact | None,
    str | None,
    FailedRunJobAudit,
]:
    if tuple(item.call_index for item in calls) != tuple(range(len(calls))):
        raise ValueError(f"recorded Provider call indices are incomplete: {job.job_id}")
    client = _RecordedReplayClient(
        AgentModelConfig.model_validate(contract.model_invocation_config),
        calls,
    )
    result: IterativeAgentSolveResult | None = None
    failure: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    replay_terminal: ReplayTerminal
    try:
        result = IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=contract.maximum_total_model_tokens_per_rollout,
            protocol_profile=IterativeAgentProtocolProfile(),
        ).solve_with_audit(record.task_package.task.public, _runtime(record, environment))
        replay_terminal = "completed_trajectory"
        replay_prompts = result.audit.model_request_prompts
        replay_telemetry = result.audit.telemetry
        observation_count = len(result.observations)
    except LLMClientError as exc:
        execution_error = _safe_error(exc)
        failure = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact)
            else None
        )
        if failure is None:
            raise ValueError("recorded HTTP-success stream lost its failure Artifact") from exc
        replay_terminal = "model_contract_failure"
        replay_prompts = failure.model_request_prompts
        replay_telemetry = failure.telemetry
        observation_count = len(failure.observations)
    prompts_exact = tuple(item.prompt for item in calls) == replay_prompts
    telemetry_equal = len(calls) == len(replay_telemetry) and all(
        _provider_telemetry_equal_before_host_augmentation(item.telemetry, replayed)
        for item, replayed in zip(calls, replay_telemetry, strict=True)
    )
    values = {
        "job_id": job.job_id,
        "task_package_id": job.task_package_id,
        "mechanism_id": job.mechanism_id,
        "provider_call_count": len(calls),
        "provider_total_tokens": sum(item.telemetry.total_tokens or 0 for item in calls),
        "estimated_cost_usd": str(
            sum(
                (Decimal(str(item.telemetry.estimated_cost or 0)) for item in calls),
                Decimal("0"),
            )
        ),
        "replay_terminal": replay_terminal,
        "observation_count": observation_count,
        "recorded_call_count": len(calls),
        "consumed_call_count": client.index,
        "prompts_exact": prompts_exact,
        "provider_telemetry_equal_before_host_augmentation": telemetry_equal,
        "response_payloads_complete": all(item.response_payload is not None for item in calls),
        "zero_generation_replay_passed": bool(
            client.index == len(calls)
            and prompts_exact
            and telemetry_equal
            and all(item.response_payload is not None for item in calls)
        ),
    }
    provisional = FailedRunJobAudit.model_construct(audit_id="pending", **values)
    audit = FailedRunJobAudit(audit_id=failed_run_job_audit_id(provisional), **values)
    return result, failure, execution_error, audit


def _load_provider_calls(
    failed_run_dir: Path,
) -> tuple[
    dict[str, tuple[RawProviderCallArtifact, ...]],
    tuple[dict[str, Any], ...],
]:
    grouped: dict[str, list[tuple[Path, RawProviderCallArtifact]]] = defaultdict(list)
    for path in sorted((failed_run_dir / "raw_provider_calls").glob("**/call_*.json")):
        artifact = RawProviderCallArtifact.model_validate_json(path.read_text(encoding="utf-8"))
        grouped[artifact.job_id].append((path, artifact))
    calls_by_job: dict[str, tuple[RawProviderCallArtifact, ...]] = {}
    manifest_rows = []
    provider_ids = []
    for job_id, rows in sorted(grouped.items()):
        ordered = tuple(item for _, item in sorted(rows, key=lambda pair: pair[1].call_index))
        calls_by_job[job_id] = ordered
        for path, artifact in sorted(rows, key=lambda pair: pair[1].call_index):
            manifest_rows.append(
                {
                    "relative_path": str(path.relative_to(failed_run_dir)),
                    "sha256": _sha256(path),
                    "byte_count": path.stat().st_size,
                    "artifact_id": artifact.artifact_id,
                    "provider_call_id": artifact.provider_call_id,
                    "job_id": artifact.job_id,
                    "call_index": artifact.call_index,
                }
            )
            provider_ids.append(artifact.provider_call_id)
    if len(provider_ids) != len(set(provider_ids)):
        raise ValueError("failed run contains duplicate Provider call identities")
    return calls_by_job, tuple(manifest_rows)


def _build_failed_run_audit(
    *,
    failed_run_id: str,
    failed_run_dir: Path,
    contract: VerifierBoundInstrumentContract,
    manifest: VerifierBoundInstrumentJobManifest,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    calls_by_job: Mapping[str, tuple[RawProviderCallArtifact, ...]],
    provider_manifest: tuple[dict[str, Any], ...],
) -> FailedRunAudit:
    if any((failed_run_dir / "raw_execution").glob("**/*.json")):
        raise ValueError("failed run unexpectedly contains raw execution Artifacts")
    checkpoint = failed_run_dir / "rollout_observations.checkpoint.jsonl"
    checkpoint_count = (
        sum(bool(line.strip()) for line in checkpoint.read_text().splitlines())
        if checkpoint.exists()
        else 0
    )
    if checkpoint_count:
        raise ValueError("failed run unexpectedly contains model result rows")
    job_by_id = {item.job_id: item for item in manifest.jobs}
    record_by_id = {item.record_id: item for item in records}
    environment_by_id = {item.manifest_id: item for item in environments}
    exposed_ids = tuple(sorted(calls_by_job))
    unopened_ids = tuple(sorted(set(job_by_id) - set(exposed_ids)))
    audits = []
    for job_id in exposed_ids:
        job = job_by_id[job_id]
        _, _, _, audit = _replay_recorded_job(
            job=job,
            contract=contract,
            record=record_by_id[job.task_record_id],
            environment=environment_by_id[job.environment_manifest_id],
            calls=calls_by_job[job_id],
        )
        audits.append(audit)
    ordered_audits = tuple(sorted(audits, key=lambda item: item.job_id))
    all_calls = tuple(item for calls in calls_by_job.values() for item in calls)
    values = {
        "failed_execution_run_id": failed_run_id,
        "exposed_job_ids": exposed_ids,
        "unopened_job_ids": unopened_ids,
        "raw_provider_artifact_manifest_hash": canonical_hash(
            provider_manifest,
            prefix="finance_v26_failed_raw_provider_artifact_manifest:",
        ),
        "estimated_cost_usd": str(
            sum(
                (Decimal(str(item.telemetry.estimated_cost or 0)) for item in all_calls),
                Decimal("0"),
            )
        ),
        "rollout_checkpoint_count": checkpoint_count,
        "completed_trajectory_replay_count": sum(
            item.replay_terminal == "completed_trajectory" for item in ordered_audits
        ),
        "model_contract_failure_replay_count": sum(
            item.replay_terminal == "model_contract_failure" for item in ordered_audits
        ),
        "recovered_observation_count": sum(item.observation_count for item in ordered_audits),
        "job_audits": ordered_audits,
    }
    provisional = FailedRunAudit.model_construct(audit_id="pending", **values)
    return FailedRunAudit(audit_id=failed_run_audit_id(provisional), **values)


def _build_source_replay(
    *,
    failed_run_dir: Path,
    package_root: Path,
    failed_source_replay: OnlineSourceReplayAudit,
) -> RecoverySourceReplayAudit:
    expected: dict[str, str] = {
        item.relative_path: item.expected_sha256 for item in failed_source_replay.entries
    }
    for descriptor in _implementation_sources(package_root):
        prior = expected.get(descriptor.relative_path)
        if prior is not None and prior != descriptor.sha256:
            raise ValueError(
                f"Recovery implementation changed a failed-run source: {descriptor.relative_path}"
            )
        expected[descriptor.relative_path] = descriptor.sha256
    for path in (
        failed_run_dir / "execution_binding.json",
        failed_run_dir / "online_source_replay_audit.json",
        failed_run_dir / "frozen_execution_contract.json",
        failed_run_dir / "frozen_job_manifest.json",
        failed_run_dir / "runner_failures.checkpoint.jsonl",
    ):
        relative = str(path.resolve().relative_to(package_root.resolve()))
        expected[relative] = _sha256(path)
    entries = tuple(
        RecoverySourceReplayEntry(
            relative_path=relative,
            expected_sha256=expected_sha,
            observed_sha256=_sha256(package_root / relative),
            byte_count=(package_root / relative).stat().st_size,
        )
        for relative, expected_sha in sorted(expected.items())
    )
    values = {
        "entries": entries,
        "replayed_file_count": len(entries),
        "replay_pass_count": len(entries),
    }
    provisional = RecoverySourceReplayAudit.model_construct(audit_id="pending", **values)
    return RecoverySourceReplayAudit(
        audit_id=recovery_source_replay_audit_id(provisional),
        **values,
    )


def build_recovery_preflight(
    *,
    recovery_run_id: str,
    failed_run_id: str,
    failed_run_dir: Path,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> _RecoveryPrepared:
    original_contract = VerifierBoundInstrumentContract.model_validate_json(
        (failed_run_dir / "frozen_execution_contract.json").read_text(encoding="utf-8")
    )
    original_manifest = VerifierBoundInstrumentJobManifest.model_validate_json(
        (failed_run_dir / "frozen_job_manifest.json").read_text(encoding="utf-8")
    )
    failed_execution_binding = VerifierBoundInstrumentExecutionBinding.model_validate_json(
        (failed_run_dir / "execution_binding.json").read_text(encoding="utf-8")
    )
    failed_source_replay = OnlineSourceReplayAudit.model_validate_json(
        (failed_run_dir / "online_source_replay_audit.json").read_text(encoding="utf-8")
    )
    if (
        original_contract.contract_id != EXPECTED_CONTRACT_ID
        or original_manifest.manifest_id != EXPECTED_MANIFEST_ID
        or failed_execution_binding.binding_id != FAILED_EXECUTION_BINDING_ID
        or failed_source_replay.audit_id != FAILED_SOURCE_REPLAY_AUDIT_ID
    ):
        raise ValueError("Recovery preflight received another failed execution")
    records = cast(
        tuple[OperationalTaskRecord, ...],
        _load_rows(task_source_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    environments = cast(
        tuple[AgentToolEnvironmentManifest, ...],
        _load_rows(
            task_source_dir / "tool_environment_manifests.json",
            AgentToolEnvironmentManifest,
        ),
    )
    task_bindings = cast(
        tuple[VerifierV2TaskReplayBinding, ...],
        _load_rows(
            task_source_dir / "verifier_v2_replay_bindings.json",
            VerifierV2TaskReplayBinding,
        ),
    )
    replay_contract = AuthorityPreservingReplayContract.model_validate_json(
        (verifier_qualification_dir / "replay_contract.json").read_text(encoding="utf-8")
    )
    if replay_contract.contract_id != original_contract.qualified_replay_contract_id:
        raise ValueError("Recovery preflight received another Replay Contract")
    calls_by_job, provider_manifest = _load_provider_calls(failed_run_dir)
    failed_audit = _build_failed_run_audit(
        failed_run_id=failed_run_id,
        failed_run_dir=failed_run_dir,
        contract=original_contract,
        manifest=original_manifest,
        records=records,
        environments=environments,
        calls_by_job=calls_by_job,
        provider_manifest=provider_manifest,
    )
    source_replay = _build_source_replay(
        failed_run_dir=failed_run_dir,
        package_root=package_root,
        failed_source_replay=failed_source_replay,
    )
    contract_values = {
        "recovery_run_id": recovery_run_id,
        "failed_run_audit_id": failed_audit.audit_id,
        "source_replay_audit_id": source_replay.audit_id,
        "exposed_job_ids": failed_audit.exposed_job_ids,
        "unopened_job_ids": failed_audit.unopened_job_ids,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional_contract = RecoveryContract.model_construct(
        contract_id="pending", **contract_values
    )
    recovery_contract = RecoveryContract(
        contract_id=recovery_contract_id(provisional_contract),
        **contract_values,
    )
    recovery_jobs = []
    exposed = set(failed_audit.exposed_job_ids)
    for original_job in original_manifest.jobs:
        replay = original_job.job_id in exposed
        values = {
            "recovery_contract_id": recovery_contract.contract_id,
            "original_job": original_job,
            "recovery_role": (
                "zero_generation_replay" if replay else "unopened_model_continuation"
            ),
            "original_provider_capture_binding_id": (
                FAILED_EXECUTION_BINDING_ID if replay else None
            ),
            "model_call_permitted": not replay,
        }
        provisional_job = RecoveryJob.model_construct(recovery_job_id="pending", **values)
        recovery_jobs.append(
            RecoveryJob(recovery_job_id=recovery_job_id(provisional_job), **values)
        )
    ordered_jobs = tuple(sorted(recovery_jobs, key=lambda item: item.recovery_job_id))
    manifest_values = {
        "recovery_contract_id": recovery_contract.contract_id,
        "jobs": ordered_jobs,
    }
    provisional_manifest = RecoveryManifest.model_construct(
        manifest_id="pending", **manifest_values
    )
    recovery_manifest = RecoveryManifest(
        manifest_id=recovery_manifest_id(provisional_manifest),
        **manifest_values,
    )
    binding_values = {
        "recovery_run_id": recovery_run_id,
        "recovery_contract_id": recovery_contract.contract_id,
        "recovery_manifest_id": recovery_manifest.manifest_id,
        "source_replay_audit_id": source_replay.audit_id,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional_binding = RecoveryExecutionBinding.model_construct(
        binding_id="pending", **binding_values
    )
    recovery_binding = RecoveryExecutionBinding(
        binding_id=recovery_execution_binding_id(provisional_binding),
        **binding_values,
    )
    preflight_values = {
        "recovery_run_id": recovery_run_id,
        "failed_run_audit_id": failed_audit.audit_id,
        "recovery_contract_id": recovery_contract.contract_id,
        "recovery_manifest_id": recovery_manifest.manifest_id,
        "recovery_execution_binding_id": recovery_binding.binding_id,
        "source_replay_audit_id": source_replay.audit_id,
        "source_replay_file_count": source_replay.replayed_file_count,
        "source_replay_pass_count": source_replay.replay_pass_count,
    }
    provisional_preflight = RecoveryPreflightReport.model_construct(
        report_id="pending", **preflight_values
    )
    preflight = RecoveryPreflightReport(
        report_id=recovery_preflight_report_id(provisional_preflight),
        **preflight_values,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_dir / "failed_run_audit.json", failed_audit.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "failed_run_job_audits.json",
        [item.model_dump(mode="json") for item in failed_audit.job_audits],
    )
    _write_json_atomic(
        output_dir / "raw_provider_artifact_manifest.json",
        list(provider_manifest),
    )
    _write_json_atomic(
        output_dir / "recovery_source_replay_audit.json",
        source_replay.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_contract.json",
        recovery_contract.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_manifest.json",
        recovery_manifest.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_execution_binding.json",
        recovery_binding.model_dump(mode="json"),
    )
    _write_json_atomic(output_dir / "report.json", preflight.model_dump(mode="json"))
    return _RecoveryPrepared(
        original_contract=original_contract,
        original_manifest=original_manifest,
        failed_execution_binding=failed_execution_binding,
        failed_audit=failed_audit,
        source_replay=source_replay,
        recovery_contract=recovery_contract,
        recovery_manifest=recovery_manifest,
        recovery_binding=recovery_binding,
        preflight=preflight,
        records=records,
        environments=environments,
        task_bindings=task_bindings,
        replay_contract=replay_contract,
        calls_by_job=calls_by_job,
        provider_manifest=provider_manifest,
    )


def _copy_provider_artifact(
    *,
    source_dir: Path,
    output_dir: Path,
    job: VerifierBoundInstrumentJob,
    call: RawProviderCallArtifact,
) -> RawFileDescriptor:
    source = _provider_call_path(source_dir, job, call.call_index)
    target = _provider_call_path(output_dir, job, call.call_index)
    source_bytes = source.read_bytes()
    if RawProviderCallArtifact.model_validate_json(source_bytes) != call:
        raise ValueError("failed-run Provider Artifact changed before recovery")
    if target.exists():
        if target.read_bytes() != source_bytes:
            raise ValueError("immutable copied Provider Artifact changed")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(source_bytes)
        temporary.replace(target)
    return RawFileDescriptor(
        relative_path=str(target.relative_to(output_dir)),
        sha256=_sha256(target),
        byte_count=target.stat().st_size,
    )


def _build_raw_execution(
    *,
    job: VerifierBoundInstrumentJob,
    binding: RecoveryExecutionBinding,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    execution_kind: str,
    descriptors: tuple[RawFileDescriptor, ...],
    telemetry: tuple[ModelCallTelemetry, ...],
    prompts: tuple[str, ...],
    result: IterativeAgentSolveResult | None,
    failure: IterativeAgentFailureArtifact | None,
    execution_error: str | None,
    output_dir: Path,
) -> VerifierBoundRawExecutionArtifact:
    raw_path = _raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = _load_raw_execution(raw_path)
        if raw.execution_binding_id != binding.binding_id or raw.job != job:
            raise ValueError("recovery raw execution crosses frozen identities")
        return raw
    if not (len(descriptors) == len(telemetry) == len(prompts)):
        raise ValueError("recovery raw Provider denominator is incomplete")
    values = {
        "execution_binding_id": binding.binding_id,
        "job_manifest_id": EXPECTED_MANIFEST_ID,
        "job": job,
        "task_record_id": record.record_id,
        "task_package_id": record.task_package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "replay_binding_contract_id": job.replay_binding_contract_id,
        "execution_kind": execution_kind,
        "provider_call_artifacts": descriptors,
        "provider_call_ids": tuple(
            provider_call_id(job.job_id, index, item) for index, item in enumerate(telemetry)
        ),
        "provider_telemetry": telemetry,
        "actual_model_request_prompts": prompts,
        "solve_result": result,
        "failure_artifact": failure,
        "execution_error": execution_error,
        "recursive_noninterference_passed": _recursive_noninterference(
            result=result,
            failure_artifact=failure,
            prompts=prompts,
        ),
    }
    provisional = VerifierBoundRawExecutionArtifact.model_construct(artifact_id="pending", **values)
    raw = VerifierBoundRawExecutionArtifact(
        artifact_id=raw_execution_artifact_id(provisional),
        **values,
    )
    _write_raw_atomic(raw_path, raw.model_dump(mode="json"))
    return raw


def _replayed_payloads(
    *,
    job: VerifierBoundInstrumentJob,
    contract: VerifierBoundInstrumentContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    calls: tuple[RawProviderCallArtifact, ...],
) -> tuple[
    IterativeAgentSolveResult | None,
    IterativeAgentFailureArtifact | None,
    str | None,
    tuple[ModelCallTelemetry, ...],
    tuple[str, ...],
]:
    result, failure, execution_error, _ = _replay_recorded_job(
        job=job,
        contract=contract,
        record=record,
        environment=environment,
        calls=calls,
    )
    if result is not None:
        telemetry = result.audit.telemetry
        prompts = result.audit.model_request_prompts
    elif failure is not None:
        telemetry = failure.telemetry
        prompts = failure.model_request_prompts
    else:
        raise ValueError("recorded Replay produced no terminal Artifact")
    if len(calls) != len(telemetry) or any(
        not _provider_telemetry_equal_before_host_augmentation(item.telemetry, replayed)
        for item, replayed in zip(calls, telemetry, strict=True)
    ):
        raise ValueError("recorded Provider telemetry changed during Host Replay")
    if tuple(item.prompt for item in calls) != prompts:
        raise ValueError("recorded Provider Prompts changed during Host Replay")
    return result, failure, execution_error, telemetry, prompts


def _reconstruct_exposed_raw(
    *,
    recovery_job: RecoveryJob,
    prepared: _RecoveryPrepared,
    failed_run_dir: Path,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    output_dir: Path,
) -> VerifierBoundRawExecutionArtifact:
    job = recovery_job.original_job
    raw_path = _raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = _load_raw_execution(raw_path)
        if raw.execution_binding_id != prepared.recovery_binding.binding_id:
            raise ValueError("zero-generation raw execution crosses Recovery Bindings")
        return raw
    if recovery_job.recovery_role != "zero_generation_replay" or (
        recovery_job.model_call_permitted
    ):
        raise ValueError("exposed Job was granted model-call authority")
    calls = prepared.calls_by_job.get(job.job_id)
    if calls is None:
        raise ValueError("exposed Job lost its failed-run Provider stream")
    result, failure, execution_error, telemetry, prompts = _replayed_payloads(
        job=job,
        contract=prepared.original_contract,
        record=record,
        environment=environment,
        calls=calls,
    )
    descriptors = tuple(
        _copy_provider_artifact(
            source_dir=failed_run_dir,
            output_dir=output_dir,
            job=job,
            call=call,
        )
        for call in calls
    )
    return _build_raw_execution(
        job=job,
        binding=prepared.recovery_binding,
        record=record,
        environment=environment,
        execution_kind=(
            "completed_trajectory" if result is not None else "captured_model_contract_failure"
        ),
        descriptors=descriptors,
        telemetry=telemetry,
        prompts=prompts,
        result=result,
        failure=failure,
        execution_error=execution_error,
        output_dir=output_dir,
    )


def _load_continuation_calls(
    *,
    output_dir: Path,
    job: VerifierBoundInstrumentJob,
    binding: RecoveryExecutionBinding,
) -> tuple[tuple[RawProviderCallArtifact, ...], tuple[RawFileDescriptor, ...]]:
    directory = _provider_call_path(output_dir, job, 0).parent
    paths = tuple(sorted(directory.glob("call_*.json"))) if directory.exists() else ()
    calls = tuple(
        RawProviderCallArtifact.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    )
    if tuple(item.call_index for item in calls) != tuple(range(len(calls))):
        raise ValueError("continuation raw Provider call indices are incomplete")
    if any(
        item.execution_binding_id != binding.binding_id or item.job_id != job.job_id
        for item in calls
    ):
        raise ValueError("continuation raw Provider stream crosses Recovery Bindings")
    descriptors = tuple(
        RawFileDescriptor(
            relative_path=str(path.relative_to(output_dir)),
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in paths
    )
    return calls, descriptors


def _execute_continuation_raw(
    *,
    recovery_job: RecoveryJob,
    prepared: _RecoveryPrepared,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    client: OpenAICompatibleJsonClient | None,
    output_dir: Path,
) -> VerifierBoundRawExecutionArtifact:
    job = recovery_job.original_job
    raw_path = _raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = _load_raw_execution(raw_path)
        if raw.execution_binding_id != prepared.recovery_binding.binding_id:
            raise ValueError("continuation raw execution crosses Recovery Bindings")
        return raw
    if recovery_job.recovery_role != "unopened_model_continuation" or (
        not recovery_job.model_call_permitted
    ):
        raise ValueError("continuation Job has invalid model-call authority")
    prior_calls, prior_descriptors = _load_continuation_calls(
        output_dir=output_dir,
        job=job,
        binding=prepared.recovery_binding,
    )
    if prior_calls:
        if any(item.response_payload is None for item in prior_calls):
            return _build_raw_execution(
                job=job,
                binding=prepared.recovery_binding,
                record=record,
                environment=environment,
                execution_kind="provider_or_runtime_failure",
                descriptors=prior_descriptors,
                telemetry=tuple(item.telemetry for item in prior_calls),
                prompts=tuple(item.prompt for item in prior_calls),
                result=None,
                failure=None,
                execution_error="LLMClientError:captured Provider failure; retry forbidden",
                output_dir=output_dir,
            )
        replayed_result, replayed_failure, replayed_error, telemetry, prompts = _replayed_payloads(
            job=job,
            contract=prepared.original_contract,
            record=record,
            environment=environment,
            calls=prior_calls,
        )
        return _build_raw_execution(
            job=job,
            binding=prepared.recovery_binding,
            record=record,
            environment=environment,
            execution_kind=(
                "completed_trajectory"
                if replayed_result is not None
                else "captured_model_contract_failure"
            ),
            descriptors=prior_descriptors,
            telemetry=telemetry,
            prompts=prompts,
            result=replayed_result,
            failure=replayed_failure,
            execution_error=replayed_error,
            output_dir=output_dir,
        )
    if client is None:
        raise ValueError("unopened continuation Job has no model client")
    recording_client = _RawFirstJournalClient(
        client,
        execution_binding=cast(Any, prepared.recovery_binding),
        job=job,
        output_dir=output_dir,
    )
    result: IterativeAgentSolveResult | None = None
    failure: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    execution_kind = "unexpected_execution_failure"
    try:
        result = IterativeAgentSolver(
            recording_client,
            mode="autonomous_agent",
            maximum_total_tokens=(
                prepared.original_contract.maximum_total_model_tokens_per_rollout
            ),
            protocol_profile=IterativeAgentProtocolProfile(),
        ).solve_with_audit(record.task_package.task.public, _runtime(record, environment))
        execution_kind = "completed_trajectory"
    except LLMClientError as exc:
        failure = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact)
            else None
        )
        execution_error = _safe_error(exc)
        execution_kind = (
            "captured_model_contract_failure"
            if failure is not None
            else "provider_or_runtime_failure"
        )
    except Exception as exc:
        execution_error = _safe_error(exc)
    raw_telemetry = tuple(recording_client.telemetry)
    raw_prompts = tuple(recording_client.prompts)
    if result is not None:
        telemetry = result.audit.telemetry
        prompts = result.audit.model_request_prompts
    elif failure is not None:
        telemetry = failure.telemetry
        prompts = failure.model_request_prompts
    else:
        telemetry = raw_telemetry
        prompts = raw_prompts
    if (
        prompts != raw_prompts
        or len(telemetry) != len(raw_telemetry)
        or any(
            not _provider_telemetry_equal_before_host_augmentation(raw, replayed)
            for raw, replayed in zip(raw_telemetry, telemetry, strict=True)
        )
    ):
        raise ValueError("raw Provider journal differs beyond Host telemetry augmentation")
    return _build_raw_execution(
        job=job,
        binding=prepared.recovery_binding,
        record=record,
        environment=environment,
        execution_kind=execution_kind,
        descriptors=tuple(recording_client.descriptors),
        telemetry=telemetry,
        prompts=prompts,
        result=result,
        failure=failure,
        execution_error=execution_error,
        output_dir=output_dir,
    )


def _load_recovery_checkpoint(
    *,
    path: Path,
    binding: RecoveryExecutionBinding,
    manifest: RecoveryManifest,
) -> tuple[VerifierBoundInstrumentRollout, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        VerifierBoundInstrumentRollout.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.original_job.job_id: item.original_job for item in manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("Recovery checkpoint contains duplicate Job identities")
    for row in rows:
        job = jobs.get(row.job_id)
        if (
            job is None
            or row.execution_binding_id != binding.binding_id
            or row.task_record_id != job.task_record_id
            or row.task_package_id != job.task_package_id
            or row.environment_manifest_id != job.environment_manifest_id
            or row.replay_binding_contract_id != job.replay_binding_contract_id
            or row.replicate_index != job.replicate_index
        ):
            raise ValueError("Recovery checkpoint differs from a frozen Job")
        if _sha256(Path(row.raw_execution_artifact_uri)) != (row.raw_execution_artifact_sha256):
            raise ValueError("Recovery checkpoint raw Artifact hash changed")
    return rows


def _run_recovery_job(
    *,
    recovery_job: RecoveryJob,
    prepared: _RecoveryPrepared,
    failed_run_dir: Path,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    client: OpenAICompatibleJsonClient | None,
    output_dir: Path,
) -> VerifierBoundInstrumentRollout:
    if recovery_job.recovery_role == "zero_generation_replay":
        if client is not None:
            raise ValueError("exposed recovery Job received a model client")
        raw = _reconstruct_exposed_raw(
            recovery_job=recovery_job,
            prepared=prepared,
            failed_run_dir=failed_run_dir,
            record=record,
            environment=environment,
            output_dir=output_dir,
        )
    else:
        raw = _execute_continuation_raw(
            recovery_job=recovery_job,
            prepared=prepared,
            record=record,
            environment=environment,
            client=client,
            output_dir=output_dir,
        )
    return _score_with_failure_capture(
        job=recovery_job.original_job,
        contract=prepared.original_contract,
        execution_binding=cast(Any, prepared.recovery_binding),
        replay_contract=prepared.replay_contract,
        record=record,
        environment=environment,
        raw=raw,
        output_dir=output_dir,
    )


def _has_continuation_provider_calls(
    output_dir: Path,
    job: VerifierBoundInstrumentJob,
) -> bool:
    directory = _provider_call_path(output_dir, job, 0).parent
    return directory.exists() and any(directory.glob("call_*.json"))


def _recovery_raw_audits(
    *,
    prepared: _RecoveryPrepared,
    failed_run_dir: Path,
    rollouts: Sequence[VerifierBoundInstrumentRollout],
    diagnostics: Sequence[VerifierBoundInstrumentDiagnostic],
    output_dir: Path,
) -> tuple[VerifierBoundInstrumentRawAudit, RecoveryRawLineageAudit]:
    recovery_job_by_id = {
        item.original_job.job_id: item for item in prepared.recovery_manifest.jobs
    }
    diagnostic_by_job = {item.job_id: item for item in diagnostics}
    byte_pass = identity_pass = before_pass = provider_rollout_pass = 0
    prompt_pass = recursive_pass = replay_pass = non_replay_pass = 0
    authority_pass = target_pass = repair_pass = stop_pass = 0
    provider_artifact_count = 0
    original_provider_count = continuation_provider_count = 0
    original_byte_pass = binding_pass = telemetry_pass = 0
    raw_recovery_binding_pass = 0
    provider_ids: list[str] = []
    failures: list[str] = []
    replay_jobs = sum(
        recovery_job_by_id[item.job_id].recovery_role == "zero_generation_replay"
        for item in rollouts
    )
    continuation_jobs = len(rollouts) - replay_jobs
    for rollout in rollouts:
        try:
            raw_path = Path(rollout.raw_execution_artifact_uri)
            if _sha256(raw_path) != rollout.raw_execution_artifact_sha256:
                raise ValueError("raw execution byte hash changed")
            raw = _load_raw_execution(raw_path)
            byte_pass += 1
            recovery_job = recovery_job_by_id[rollout.job_id]
            job = recovery_job.original_job
            diagnostic = diagnostic_by_job[rollout.job_id]
            if (
                raw.execution_binding_id == prepared.recovery_binding.binding_id
                and raw.job == job
                and raw.task_package_id == rollout.task_package_id
            ):
                identity_pass += 1
                raw_recovery_binding_pass += 1
            else:
                raise ValueError("raw execution identity changed")
            if raw.captured_before_verifier_replay_and_scoring and (
                not raw.verifier_replay_or_score_fields_present
            ):
                before_pass += 1
            else:
                raise ValueError("raw execution was not persisted before scoring")
            provider_artifacts = []
            expected_provider_binding = (
                FAILED_EXECUTION_BINDING_ID
                if recovery_job.recovery_role == "zero_generation_replay"
                else prepared.recovery_binding.binding_id
            )
            for index, descriptor in enumerate(raw.provider_call_artifacts):
                path = output_dir / descriptor.relative_path
                if (
                    _sha256(path) != descriptor.sha256
                    or path.stat().st_size != descriptor.byte_count
                ):
                    raise ValueError("raw Provider call bytes changed")
                artifact = RawProviderCallArtifact.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                if (
                    artifact.execution_binding_id != expected_provider_binding
                    or artifact.job_id != rollout.job_id
                    or artifact.call_index != index
                    or artifact.provider_call_id != rollout.provider_call_ids[index]
                    or artifact.prompt != raw.actual_model_request_prompts[index]
                ):
                    raise ValueError("raw Provider call identity changed")
                binding_pass += 1
                if not _provider_telemetry_equal_before_host_augmentation(
                    artifact.telemetry, raw.provider_telemetry[index]
                ):
                    raise ValueError("Provider telemetry differs beyond Host augmentation")
                telemetry_pass += 1
                if recovery_job.recovery_role == "zero_generation_replay":
                    original_provider_count += 1
                    source = _provider_call_path(failed_run_dir, job, index)
                    if source.read_bytes() != path.read_bytes():
                        raise ValueError("copied failed-run Provider bytes changed")
                    original_byte_pass += 1
                else:
                    continuation_provider_count += 1
                provider_artifacts.append(artifact)
            if len(provider_artifacts) == rollout.provider_call_count:
                provider_rollout_pass += 1
                provider_artifact_count += len(provider_artifacts)
            else:
                raise ValueError("raw Provider Artifact denominator changed")
            if (
                tuple(item.prompt_sha256 for item in provider_artifacts)
                == rollout.actual_prompt_hashes
                and tuple(item.provider_call_id for item in provider_artifacts)
                == rollout.provider_call_ids
            ):
                prompt_pass += 1
            else:
                raise ValueError("raw Prompt or Provider identity changed")
            if raw.recursive_noninterference_passed and (rollout.recursive_noninterference_passed):
                recursive_pass += 1
            else:
                raise ValueError("recursive noninterference audit failed")
            if diagnostic.replay_passed:
                replay_pass += 1
            else:
                raise ValueError("Verifier v2 Replay failed")
            if diagnostic.non_replay_gate_audit_present and (
                diagnostic.complete_verifier_gate_agreement is not False
            ):
                non_replay_pass += 1
            else:
                raise ValueError("independent non-Replay Gate audit failed")
            if diagnostic.authority_contract_in_initial_prompt and (
                diagnostic.initial_prompt_private_identity_free
            ):
                authority_pass += 1
            else:
                raise ValueError("authority Prompt audit failed")
            if diagnostic.terminal_target_in_initial_prompt:
                target_pass += 1
            else:
                raise ValueError("terminal-target audit failed")
            if diagnostic.repair_prompts_action_neutral and (
                diagnostic.failed_observations_action_neutral
            ):
                repair_pass += 1
            else:
                raise ValueError("repair-neutrality audit failed")
            if not diagnostic.stop_ready_false_positive and (
                not diagnostic.stop_ready_false_negative
            ):
                stop_pass += 1
            else:
                raise ValueError("Stop Readiness audit failed")
            provider_ids.extend(rollout.provider_call_ids)
        except Exception as exc:
            failures.append(f"{rollout.raw_execution_artifact_uri}:{_safe_error(exc)}")
    duplicates = tuple(sorted(key for key, count in Counter(provider_ids).items() if count > 1))
    standard_counts = (
        byte_pass,
        identity_pass,
        before_pass,
        provider_rollout_pass,
        prompt_pass,
        recursive_pass,
        replay_pass,
        non_replay_pass,
        authority_pass,
        target_pass,
        repair_pass,
        stop_pass,
    )
    standard_complete = len(rollouts) == EXPECTED_JOB_COUNT and all(
        item == EXPECTED_JOB_COUNT for item in standard_counts
    )
    standard_partial = all(item == len(rollouts) for item in standard_counts)
    raw_values = {
        "execution_binding_id": prepared.recovery_binding.binding_id,
        "observed_rollout_count": len(rollouts),
        "raw_execution_byte_pass_count": byte_pass,
        "raw_execution_identity_pass_count": identity_pass,
        "raw_before_scoring_pass_count": before_pass,
        "raw_provider_artifact_rollout_pass_count": provider_rollout_pass,
        "raw_provider_call_artifact_count": provider_artifact_count,
        "prompt_telemetry_pass_count": prompt_pass,
        "recursive_noninterference_pass_count": recursive_pass,
        "replay_pass_count": replay_pass,
        "non_replay_gate_audit_pass_count": non_replay_pass,
        "authority_contract_pass_count": authority_pass,
        "terminal_target_pass_count": target_pass,
        "repair_neutrality_pass_count": repair_pass,
        "stop_readiness_audit_pass_count": stop_pass,
        "provider_call_ids_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "failed_artifacts": tuple(sorted(failures)),
        "status": (
            "passed"
            if standard_complete and not duplicates and not failures
            else "partial"
            if standard_partial and not duplicates and not failures
            else "failed"
        ),
    }
    provisional_raw = VerifierBoundInstrumentRawAudit.model_construct(
        audit_id="pending", **raw_values
    )
    raw_audit = VerifierBoundInstrumentRawAudit(
        audit_id=verifier_bound_instrument_raw_audit_id(provisional_raw),
        **raw_values,
    )
    observed_provider_count = original_provider_count + continuation_provider_count
    lineage_complete = bool(
        len(rollouts) == EXPECTED_JOB_COUNT
        and replay_jobs == FAILED_EXPOSED_JOB_COUNT
        and continuation_jobs == UNOPENED_CONTINUATION_JOB_COUNT
        and original_provider_count == FAILED_PROVIDER_CALL_COUNT
        and original_byte_pass == FAILED_PROVIDER_CALL_COUNT
        and binding_pass == observed_provider_count
        and telemetry_pass == observed_provider_count
        and raw_recovery_binding_pass == EXPECTED_JOB_COUNT
    )
    lineage_partial = bool(
        replay_jobs + continuation_jobs == len(rollouts)
        and original_byte_pass == original_provider_count
        and binding_pass == observed_provider_count
        and telemetry_pass == observed_provider_count
        and raw_recovery_binding_pass == len(rollouts)
    )
    lineage_values = {
        "recovery_execution_binding_id": prepared.recovery_binding.binding_id,
        "observed_job_count": len(rollouts),
        "zero_generation_replay_job_count": replay_jobs,
        "continuation_job_count": continuation_jobs,
        "original_provider_artifact_count": original_provider_count,
        "continuation_provider_artifact_count": continuation_provider_count,
        "original_provider_exact_byte_pass_count": original_byte_pass,
        "provider_artifact_binding_pass_count": binding_pass,
        "provider_telemetry_pre_host_augmentation_pass_count": telemetry_pass,
        "raw_execution_recovery_binding_pass_count": raw_recovery_binding_pass,
        "provider_call_ids_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "failed_artifacts": tuple(sorted(failures)),
        "status": (
            "passed"
            if lineage_complete and not duplicates and not failures
            else "partial"
            if lineage_partial and not duplicates and not failures
            else "failed"
        ),
    }
    provisional_lineage = RecoveryRawLineageAudit.model_construct(
        audit_id="pending", **lineage_values
    )
    lineage_audit = RecoveryRawLineageAudit(
        audit_id=recovery_raw_lineage_audit_id(provisional_lineage),
        **lineage_values,
    )
    return raw_audit, lineage_audit


def _persist_recovery_inputs(
    output_dir: Path,
    prepared: _RecoveryPrepared,
) -> None:
    _write_json_atomic(
        output_dir / "failed_run_audit.json",
        prepared.failed_audit.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_source_replay_audit.json",
        prepared.source_replay.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_contract.json",
        prepared.recovery_contract.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_manifest.json",
        prepared.recovery_manifest.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_execution_binding.json",
        prepared.recovery_binding.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_preflight_report.json",
        prepared.preflight.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "raw_provider_artifact_manifest.json",
        list(prepared.provider_manifest),
    )


def run_verifier_bound_instrument_recovery(
    *,
    recovery_run_id: str,
    failed_run_id: str,
    failed_run_dir: Path,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    workers: int,
    client_factory: Callable[[AgentModelConfig], OpenAICompatibleJsonClient] = (
        OpenAICompatibleJsonClient
    ),
) -> RecoveryExecutionReport:
    prepared = build_recovery_preflight(
        recovery_run_id=recovery_run_id,
        failed_run_id=failed_run_id,
        failed_run_dir=failed_run_dir,
        task_source_dir=task_source_dir,
        verifier_qualification_dir=verifier_qualification_dir,
        output_dir=preflight_dir,
        package_root=package_root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _persist_recovery_inputs(output_dir, prepared)
    checkpoint_path = output_dir / "rollout_observations.checkpoint.jsonl"
    existing = _load_recovery_checkpoint(
        path=checkpoint_path,
        binding=prepared.recovery_binding,
        manifest=prepared.recovery_manifest,
    )
    completed = {item.job_id: item for item in existing}
    recovery_job_by_id = {
        item.original_job.job_id: item for item in prepared.recovery_manifest.jobs
    }
    record_by_id = {item.record_id: item for item in prepared.records}
    environment_by_id = {item.manifest_id: item for item in prepared.environments}
    binding_by_id = {item.contract_id: item for item in prepared.task_bindings}
    replay_pending = [
        item
        for item in prepared.recovery_manifest.jobs
        if item.recovery_role == "zero_generation_replay"
        and item.original_job.job_id not in completed
    ]
    print(
        f"[v26.80] zero-generation Replay {len(replay_pending)} pending exposed Jobs",
        flush=True,
    )
    for recovery_job in replay_pending:
        job = recovery_job.original_job
        rollout = _run_recovery_job(
            recovery_job=recovery_job,
            prepared=prepared,
            failed_run_dir=failed_run_dir,
            record=record_by_id[job.task_record_id],
            environment=environment_by_id[job.environment_manifest_id],
            client=None,
            output_dir=output_dir,
        )
        completed[job.job_id] = rollout
        _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
    continuation_pending = [
        item
        for item in prepared.recovery_manifest.jobs
        if item.recovery_role == "unopened_model_continuation"
        and item.original_job.job_id not in completed
    ]
    raw_recovery_jobs = [
        item
        for item in continuation_pending
        if _raw_execution_path(output_dir, item.original_job).exists()
        or _has_continuation_provider_calls(output_dir, item.original_job)
    ]
    for recovery_job in raw_recovery_jobs:
        job = recovery_job.original_job
        rollout = _run_recovery_job(
            recovery_job=recovery_job,
            prepared=prepared,
            failed_run_dir=failed_run_dir,
            record=record_by_id[job.task_record_id],
            environment=environment_by_id[job.environment_manifest_id],
            client=None,
            output_dir=output_dir,
        )
        completed[job.job_id] = rollout
        _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
    fresh_jobs = [item for item in continuation_pending if item not in raw_recovery_jobs]
    report_path = output_dir / "report.json"
    prior_report: RecoveryExecutionReport | None = None
    if report_path.exists():
        prior_report = RecoveryExecutionReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        if fresh_jobs:
            raise ValueError("completed Recovery report exists while Jobs remain unopened")
        if (
            prior_report.recovery_execution_binding_id != prepared.recovery_binding.binding_id
            or prior_report.recovery_contract_id != prepared.recovery_contract.contract_id
            or prior_report.recovery_manifest_id != prepared.recovery_manifest.manifest_id
        ):
            raise ValueError("completed Recovery report crosses frozen inputs")
    client: OpenAICompatibleJsonClient | None = None
    if fresh_jobs:
        model_config = AgentModelConfig.model_validate(
            prepared.original_contract.model_invocation_config
        )
        client = client_factory(model_config)
        discovered_models = tuple(client.discover_models())
        if prepared.original_contract.model_id not in discovered_models:
            raise ValueError("frozen DeepSeek V4-Flash identity is unavailable")
    elif prior_report is not None:
        discovered_models = prior_report.instrument_result.discovered_models
    else:
        discovered_models = (prepared.original_contract.model_id,)
    print(
        f"[v26.80] resumed {len(completed)}/{EXPECTED_JOB_COUNT}; "
        f"raw-only continuation {len(raw_recovery_jobs)}; "
        f"first execution {len(fresh_jobs)} with {workers} workers",
        flush=True,
    )
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(fresh_jobs) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_recovery_job,
                recovery_job=recovery_job,
                prepared=prepared,
                failed_run_dir=failed_run_dir,
                record=record_by_id[recovery_job.original_job.task_record_id],
                environment=environment_by_id[recovery_job.original_job.environment_manifest_id],
                client=client,
                output_dir=output_dir,
            ): recovery_job
            for recovery_job in fresh_jobs
        }
        for future in as_completed(future_map):
            recovery_job = future_map[future]
            job = recovery_job.original_job
            try:
                rollout = future.result()
            except Exception as exc:
                _append_jsonl(
                    output_dir / "runner_failures.checkpoint.jsonl",
                    {"job_id": job.job_id, "error": _safe_error(exc)},
                )
                for queued in future_map:
                    if queued is not future:
                        queued.cancel()
                raise RuntimeError(
                    "Verifier-bound Recovery worker failed; raw-only resume is required"
                ) from exc
            with lock:
                if job.job_id in completed:
                    raise ValueError("Recovery runner produced a duplicate Job result")
                completed[job.job_id] = rollout
                _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
            print(
                f"[v26.80] completed {len(completed)}/{EXPECTED_JOB_COUNT}",
                flush=True,
            )
    ordered = tuple(
        completed[item.job_id]
        for item in prepared.original_manifest.jobs
        if item.job_id in completed
    )
    diagnostics = tuple(
        _diagnostic(
            rollout=rollout,
            raw=_load_raw_execution(Path(rollout.raw_execution_artifact_uri)),
            record=record_by_id[rollout.task_record_id],
            binding=binding_by_id[
                recovery_job_by_id[rollout.job_id].original_job.replay_binding_contract_id
            ],
        )
        for rollout in ordered
    )
    raw_audit, lineage_audit = _recovery_raw_audits(
        prepared=prepared,
        failed_run_dir=failed_run_dir,
        rollouts=ordered,
        diagnostics=diagnostics,
        output_dir=output_dir,
    )
    instrument_result = _make_report(
        execution_binding=cast(Any, prepared.recovery_binding),
        contract=prepared.original_contract,
        manifest=prepared.original_manifest,
        discovered_models=discovered_models,
        rollouts=ordered,
        diagnostics=diagnostics,
        raw_audit=raw_audit,
    )
    continuation_ids = set(prepared.failed_audit.unopened_job_ids)
    continuation_rows = tuple(item for item in ordered if item.job_id in continuation_ids)
    continuation_calls = sum(item.provider_call_count for item in continuation_rows)
    continuation_tokens = sum(item.provider_total_tokens for item in continuation_rows)
    continuation_cost = sum(
        (Decimal(item.estimated_cost_usd) for item in continuation_rows),
        Decimal("0"),
    )
    total_cost = Decimal(FAILED_ESTIMATED_COST_USD) + continuation_cost
    recovery_ready = bool(
        instrument_result.instrument_ready
        and lineage_audit.status == "passed"
        and len(ordered) == EXPECTED_JOB_COUNT
        and len(continuation_rows) == UNOPENED_CONTINUATION_JOB_COUNT
    )
    report_values = {
        "recovery_run_id": recovery_run_id,
        "failed_run_audit_id": prepared.failed_audit.audit_id,
        "recovery_contract_id": prepared.recovery_contract.contract_id,
        "recovery_manifest_id": prepared.recovery_manifest.manifest_id,
        "recovery_execution_binding_id": prepared.recovery_binding.binding_id,
        "continuation_provider_call_count": continuation_calls,
        "total_provider_call_count": FAILED_PROVIDER_CALL_COUNT + continuation_calls,
        "continuation_provider_total_tokens": continuation_tokens,
        "total_provider_tokens": FAILED_PROVIDER_TOTAL_TOKENS + continuation_tokens,
        "continuation_estimated_cost_usd": str(continuation_cost),
        "total_estimated_cost_usd": str(total_cost),
        "instrument_result": instrument_result,
        "mechanism_summaries": instrument_result.mechanism_summaries,
        "raw_lineage_audit": lineage_audit,
        "raw_first_recovery_lineage_passed": lineage_audit.status == "passed",
        "resource_budget_passed": instrument_result.resource_budget_passed,
        "recovery_instrument_ready": recovery_ready,
        "status": "passed" if recovery_ready else "blocked",
        "next_permitted_stage": (
            "verifier_bound_recovery_postrun_audit_only"
            if recovery_ready
            else "resource_budget_audit_only"
            if not instrument_result.resource_budget_passed
            else "verifier_bound_recovery_failure_audit_only"
        ),
    }
    provisional_report = RecoveryExecutionReport.model_construct(
        report_id="pending", **report_values
    )
    report = RecoveryExecutionReport(
        report_id=recovery_execution_report_id(provisional_report),
        **report_values,
    )
    _write_json_atomic(
        output_dir / "instrument_rollouts.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "online_replay_results.json",
        [
            item.replay_result.model_dump(mode="json")
            for item in ordered
            if item.replay_result is not None
        ],
    )
    _write_json_atomic(
        output_dir / "independent_non_replay_gate_audits.json",
        [
            item.non_replay_gate_audit.model_dump(mode="json")
            for item in ordered
            if item.non_replay_gate_audit is not None
        ],
    )
    _write_json_atomic(
        output_dir / "rollout_diagnostics.json",
        [item.model_dump(mode="json") for item in diagnostics],
    )
    _write_json_atomic(
        output_dir / "raw_integrity_audit.json",
        raw_audit.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_raw_lineage_audit.json",
        lineage_audit.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "mechanism_summaries.json",
        [item.model_dump(mode="json") for item in instrument_result.mechanism_summaries],
    )
    _write_json_atomic(
        output_dir / "instrument_result.json",
        instrument_result.model_dump(mode="json"),
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def failed_run_job_audit_id(value: FailedRunJobAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_failed_job_audit:",
    )


def failed_run_audit_id(value: FailedRunAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_failed_run_audit:",
    )


def recovery_source_replay_audit_id(value: RecoverySourceReplayAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_recovery_source_replay:",
    )


def recovery_contract_id(value: RecoveryContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_verifier_bound_recovery_contract:",
    )


def recovery_job_id(value: RecoveryJob) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"recovery_job_id"}),
        prefix="finance_v26_verifier_bound_recovery_job:",
    )


def recovery_manifest_id(value: RecoveryManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_v26_verifier_bound_recovery_manifest:",
    )


def recovery_execution_binding_id(value: RecoveryExecutionBinding) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"binding_id"}),
        prefix="finance_v26_verifier_bound_recovery_execution_binding:",
    )


def recovery_preflight_report_id(value: RecoveryPreflightReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_verifier_bound_recovery_preflight:",
    )


def recovery_raw_lineage_audit_id(value: RecoveryRawLineageAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_recovery_raw_lineage_audit:",
    )


def recovery_execution_report_id(value: RecoveryExecutionReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_verifier_bound_instrument_recovery:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recover the failed v26.78 Verifier-v2-bound Instrument execution without "
            "repeating any exposed model Job"
        )
    )
    parser.add_argument("--recovery-run-id", required=True)
    parser.add_argument("--failed-run-id", required=True)
    parser.add_argument("--failed-run-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument("--preflight-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        prepared = build_recovery_preflight(
            recovery_run_id=args.recovery_run_id,
            failed_run_id=args.failed_run_id,
            failed_run_dir=args.failed_run_dir,
            task_source_dir=args.task_source_dir,
            verifier_qualification_dir=args.verifier_qualification_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
        )
        print(json.dumps(prepared.preflight.model_dump(mode="json"), indent=2))
        return
    if args.preflight_dir is None:
        parser.error("--preflight-dir is required for Recovery execution")
    report = run_verifier_bound_instrument_recovery(
        recovery_run_id=args.recovery_run_id,
        failed_run_id=args.failed_run_id,
        failed_run_dir=args.failed_run_dir,
        task_source_dir=args.task_source_dir,
        verifier_qualification_dir=args.verifier_qualification_dir,
        preflight_dir=args.preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        workers=args.workers,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
