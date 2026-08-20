from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_preflight import (  # noqa: E501
    BudgetClosedInstrumentContract,
    BudgetClosedInstrumentJob,
    BudgetClosedInstrumentJobManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_requalification import (  # noqa: E501
    EXPECTED_CONTRACT_ID,
    EXPECTED_JOB_COUNT,
    EXPECTED_MANIFEST_ID,
    EXPECTED_PROVIDER_BUDGET_CONTRACT_ID,
    ONLINE_IMPLEMENTATION_SOURCE_PATHS,
    BudgetClosedExecutionBinding,
    BudgetClosedInstrumentRollout,
    BudgetClosedMechanismSummary,
    BudgetClosedOnlineSourceReplayAudit,
    BudgetClosedRawExecution,
    BudgetClosedRawProviderCall,
    BudgetClosedRolloutDiagnostic,
    ExecutionKind,
    RawFileDescriptor,
    _AttemptPromptJournalClient,
    _diagnostic,
    _mechanism_summaries,
    _provider_call_path,
    _provider_telemetry_equal_before_host_augmentation,
    _raw_execution_path,
    _RawFirstJournalClient,
    _recursive_noninterference,
    _runtime,
    _safe_error,
    _score_with_failure_capture,
    _sha256,
    _sha256_text,
    _trace_diversity,
    _write_json_atomic,
    _write_raw_atomic,
    prepare_budget_closed_instrument_execution,
    provider_call_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
    OperationalTaskRecord,
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
from trusted_synthesis.runtime.agent.budget_closed import (
    BudgetClosedJsonClient,
    ProviderTokenBudgetAudit,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

FAILED_EXECUTION_RUN_ID = (
    "finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820"
)
FAILED_EXECUTION_BINDING_ID = (
    "finance_v26_budget_closed_instrument_execution_binding:"
    "772d296b3c42aa43e786affa35f8759b47d056384719524f19fdc8c57fd6a40c"
)
FAILED_SOURCE_REPLAY_AUDIT_ID = (
    "finance_v26_budget_closed_online_source_replay:"
    "14a5c9a0b5800611c6986aa581f42afb565b2cf4cca31f1efe54b2ae85c701e2"
)
FAILED_EXPOSED_JOB_COUNT: Literal[20] = 20
UNOPENED_CONTINUATION_JOB_COUNT: Literal[12] = 12
FAILED_PROVIDER_CALL_COUNT: Literal[152] = 152
FAILED_PROVIDER_TOTAL_TOKENS: Literal[1380628] = 1_380_628
FAILED_ESTIMATED_COST_USD = "0.17555657840000001851"
FAILED_RAW_EXECUTION_COUNT: Literal[4] = 4
FAILED_CHECKPOINT_COUNT: Literal[3] = 3
FAILED_RUNNER_FAILURE_COUNT: Literal[1] = 1

V26_BUDGET_RECOVERY_SOURCE_REPLAY_VERSION = "finance_v26_budget_recovery_source_replay.v1"
V26_BUDGET_FAILED_JOB_AUDIT_VERSION = "finance_v26_budget_failed_job_audit.v1"
V26_BUDGET_FAILED_RUN_AUDIT_VERSION = "finance_v26_budget_failed_run_audit.v1"
V26_BUDGET_RECOVERY_CONTRACT_VERSION = "finance_v26_budget_recovery_contract.v1"
V26_BUDGET_RECOVERY_JOB_VERSION = "finance_v26_budget_recovery_job.v1"
V26_BUDGET_RECOVERY_MANIFEST_VERSION = "finance_v26_budget_recovery_manifest.v1"
V26_BUDGET_RECOVERY_BINDING_VERSION = "finance_v26_budget_recovery_binding.v1"
V26_BUDGET_RECOVERY_PREFLIGHT_VERSION = "finance_v26_budget_recovery_preflight.v1"
V26_BUDGET_RECOVERY_RAW_EXECUTION_VERSION = "finance_v26_budget_recovery_raw_execution.v1"
V26_BUDGET_RECOVERY_LINEAGE_VERSION = "finance_v26_budget_recovery_raw_lineage.v1"
V26_BUDGET_RECOVERY_REPORT_VERSION = "finance_v26_budget_recovery_report.v1"

RECOVERY_MODULE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_budget_closed_instrument_recovery.py"
)
RECOVERY_IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted({*ONLINE_IMPLEMENTATION_SOURCE_PATHS, RECOVERY_MODULE_PATH})
)

RecoveryRole = Literal["zero_generation_replay", "unopened_model_continuation"]
ReplayTerminal = Literal[
    "completed_trajectory",
    "model_contract_failure",
    "budget_exhausted_no_call",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BudgetRecoverySourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "frozen_online_source",
        "failed_execution_artifact",
        "recovery_implementation",
    ]
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> BudgetRecoverySourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("budget Recovery source bytes changed")
        return self


class BudgetRecoverySourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_source_replay_audit_id: str = FAILED_SOURCE_REPLAY_AUDIT_ID
    entries: tuple[BudgetRecoverySourceReplayEntry, ...] = Field(min_length=1)
    replayed_file_count: int = Field(ge=1)
    replay_pass_count: int = Field(ge=1)
    source_replay_before_client_construction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_RECOVERY_SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetRecoverySourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("budget Recovery source paths are not canonical")
        if self.replayed_file_count != len(self.entries) or (
            self.replay_pass_count != self.replayed_file_count
        ):
            raise ValueError("budget Recovery source denominator changed")
        if self.audit_id != budget_recovery_source_replay_audit_id(self):
            raise ValueError("budget Recovery source audit identity is invalid")
        return self


class BudgetFailedJobAudit(FrozenModel):
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
    attempted_prompt_count: int = Field(ge=1)
    certificate_count: int = Field(ge=1)
    permitted_request_count: int = Field(ge=1)
    denied_no_call_count: int = Field(ge=0, le=1)
    post_terminal_short_circuit_prompt_count: int = Field(ge=0)
    raw_execution_artifact_present: bool
    rollout_checkpoint_present: bool
    prompts_exact: Literal[True] = True
    provider_telemetry_equal_before_host_augmentation: Literal[True] = True
    response_payloads_complete: Literal[True] = True
    budget_audit_passed: Literal[True] = True
    zero_generation_replay_passed: Literal[True] = True
    schema_version: str = V26_BUDGET_FAILED_JOB_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetFailedJobAudit:
        if not (
            self.recorded_call_count
            == self.consumed_call_count
            == self.provider_call_count
            == self.permitted_request_count
        ):
            raise ValueError("failed Job Replay did not consume its exact Provider stream")
        if self.attempted_prompt_count != (
            self.certificate_count + self.post_terminal_short_circuit_prompt_count
        ):
            raise ValueError("failed Job Host-attempt partition changed")
        if self.replay_terminal == "budget_exhausted_no_call":
            if self.denied_no_call_count != 1 or (
                self.certificate_count != self.provider_call_count + 1
            ):
                raise ValueError("failed Job no-call denominator changed")
        elif self.denied_no_call_count != 0 or (self.certificate_count != self.provider_call_count):
            raise ValueError("failed Job non-no-call denominator changed")
        if self.audit_id != budget_failed_job_audit_id(self):
            raise ValueError("failed Job audit identity is invalid")
        return self


class BudgetFailedRunAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_execution_run_id: str = FAILED_EXECUTION_RUN_ID
    failed_execution_binding_id: str = FAILED_EXECUTION_BINDING_ID
    source_replay_audit_id: str = FAILED_SOURCE_REPLAY_AUDIT_ID
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    exposed_job_ids: tuple[str, ...] = Field(min_length=20, max_length=20)
    unopened_job_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    exposed_job_count: Literal[20] = FAILED_EXPOSED_JOB_COUNT
    unopened_job_count: Literal[12] = UNOPENED_CONTINUATION_JOB_COUNT
    raw_provider_call_artifact_count: Literal[152] = FAILED_PROVIDER_CALL_COUNT
    raw_provider_artifact_manifest_hash: str = Field(min_length=1)
    provider_total_tokens: Literal[1380628] = FAILED_PROVIDER_TOTAL_TOKENS
    estimated_cost_usd: str = FAILED_ESTIMATED_COST_USD
    http_success_count: Literal[152] = FAILED_PROVIDER_CALL_COUNT
    exact_model_count: Literal[152] = FAILED_PROVIDER_CALL_COUNT
    raw_execution_artifact_count: Literal[4] = FAILED_RAW_EXECUTION_COUNT
    rollout_checkpoint_count: Literal[3] = FAILED_CHECKPOINT_COUNT
    runner_failure_record_count: Literal[1] = FAILED_RUNNER_FAILURE_COUNT
    completed_trajectory_replay_count: int = Field(ge=0, le=20)
    model_contract_failure_replay_count: int = Field(ge=0, le=20)
    budget_exhausted_no_call_replay_count: int = Field(ge=0, le=20)
    recovered_observation_count: int = Field(ge=0)
    post_terminal_short_circuit_prompt_count: int = Field(ge=0)
    job_audits: tuple[BudgetFailedJobAudit, ...] = Field(min_length=20, max_length=20)
    failure_stage: Literal["post_provider_pre_raw_execution"] = "post_provider_pre_raw_execution"
    failure_cause: Literal[
        "raw_execution_validator_equated_all_host_attempts_with_certificate_bearing_attempts"
    ] = "raw_execution_validator_equated_all_host_attempts_with_certificate_bearing_attempts"
    provider_budget_contract_failed: Literal[False] = False
    historical_model_calls_repeated: Literal[False] = False
    historical_outcomes_reclassified: Literal[False] = False
    status: Literal["instrument_execution_failed"] = "instrument_execution_failed"
    next_permitted_stage: Literal["frozen_budget_recovery_preflight_only"] = (
        "frozen_budget_recovery_preflight_only"
    )
    schema_version: str = V26_BUDGET_FAILED_RUN_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetFailedRunAudit:
        groups = (self.exposed_job_ids, self.unopened_job_ids)
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("failed-run Job sets are not canonical")
        if (
            set(self.exposed_job_ids) & set(self.unopened_job_ids)
            or len(set(self.exposed_job_ids) | set(self.unopened_job_ids)) != EXPECTED_JOB_COUNT
        ):
            raise ValueError("failed-run Job partition changed")
        if len(self.job_audits) != self.exposed_job_count:
            raise ValueError("failed-run audit loses Job diagnostics")
        if (
            self.completed_trajectory_replay_count
            + self.model_contract_failure_replay_count
            + self.budget_exhausted_no_call_replay_count
            != self.exposed_job_count
        ):
            raise ValueError("failed-run Replay terminal denominator changed")
        if self.audit_id != budget_failed_run_audit_id(self):
            raise ValueError("failed-run audit identity is invalid")
        return self


class BudgetRecoveryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    recovery_run_id: str = Field(min_length=1)
    failed_run_audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    original_contract_id: str = EXPECTED_CONTRACT_ID
    original_job_manifest_id: str = EXPECTED_MANIFEST_ID
    original_execution_binding_id: str = FAILED_EXECUTION_BINDING_ID
    provider_token_budget_contract_id: str = EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
    exposed_job_ids: tuple[str, ...] = Field(min_length=20, max_length=20)
    unopened_job_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    zero_generation_replay_job_count: Literal[20] = FAILED_EXPOSED_JOB_COUNT
    unopened_model_continuation_job_count: Literal[12] = UNOPENED_CONTINUATION_JOB_COUNT
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    maximum_total_model_tokens_per_rollout: Literal[120000] = 120000
    maximum_total_estimated_cost_usd: float = Field(default=2.0, ge=2.0, le=2.0)
    exposed_job_model_calls_forbidden: Literal[True] = True
    unopened_job_exactly_once_execution_required: Literal[True] = True
    recorded_payload_replay_must_consume_all_calls: Literal[True] = True
    recorded_prompt_exact_equality_required: Literal[True] = True
    certificate_attempt_binding_rule: Literal[
        "certificate_hashes_equal_host_attempt_prefix;post_terminal_short_circuits_equal_suffix"
    ] = "certificate_hashes_equal_host_attempt_prefix;post_terminal_short_circuits_equal_suffix"
    terminal_short_circuit_provider_call_count: Literal[0] = 0
    provider_and_host_telemetry_separately_bound: Literal[True] = True
    raw_lineage_and_scoring_failures_separated: Literal[True] = True
    invalid_model_and_typed_no_call_outcomes_retained: Literal[True] = True
    compiler_witness_empirical_count: Literal[0] = 0
    historical_diagnostic_candidate_count: Literal[0] = 0
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=1)
    schema_version: str = V26_BUDGET_RECOVERY_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> BudgetRecoveryContract:
        if (
            set(self.exposed_job_ids) & set(self.unopened_job_ids)
            or len(set(self.exposed_job_ids) | set(self.unopened_job_ids)) != EXPECTED_JOB_COUNT
        ):
            raise ValueError("budget Recovery Contract Job partition changed")
        paths = tuple(item.relative_path for item in self.implementation_source_files)
        if paths != RECOVERY_IMPLEMENTATION_SOURCE_PATHS:
            raise ValueError("budget Recovery implementation manifest changed")
        if self.contract_id != budget_recovery_contract_id(self):
            raise ValueError("budget Recovery Contract identity is invalid")
        return self


class BudgetRecoveryJob(FrozenModel):
    recovery_job_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    original_job: BudgetClosedInstrumentJob
    recovery_role: RecoveryRole
    original_provider_capture_binding_id: str | None = None
    model_call_permitted: bool
    schema_version: str = V26_BUDGET_RECOVERY_JOB_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> BudgetRecoveryJob:
        replay = self.recovery_role == "zero_generation_replay"
        if replay != (self.original_provider_capture_binding_id == FAILED_EXECUTION_BINDING_ID):
            raise ValueError("budget Recovery Job capture lineage changed")
        if self.model_call_permitted == replay:
            raise ValueError("budget Recovery Job model authority changed")
        if self.recovery_job_id != budget_recovery_job_id(self):
            raise ValueError("budget Recovery Job identity is invalid")
        return self


class BudgetRecoveryManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    jobs: tuple[BudgetRecoveryJob, ...] = Field(min_length=32, max_length=32)
    schema_version: str = V26_BUDGET_RECOVERY_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> BudgetRecoveryManifest:
        if any(item.recovery_contract_id != self.recovery_contract_id for item in self.jobs):
            raise ValueError("budget Recovery Manifest crosses Contracts")
        identities = tuple(item.recovery_job_id for item in self.jobs)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("budget Recovery Job identities are not canonical")
        if len({item.original_job.job_id for item in self.jobs}) != EXPECTED_JOB_COUNT:
            raise ValueError("budget Recovery Manifest loses original Jobs")
        if Counter(item.recovery_role for item in self.jobs) != Counter(
            {
                "zero_generation_replay": FAILED_EXPOSED_JOB_COUNT,
                "unopened_model_continuation": UNOPENED_CONTINUATION_JOB_COUNT,
            }
        ):
            raise ValueError("budget Recovery role denominator changed")
        if self.manifest_id != budget_recovery_manifest_id(self):
            raise ValueError("budget Recovery Manifest identity is invalid")
        return self


class BudgetRecoveryExecutionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    recovery_run_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    original_execution_binding_id: str = FAILED_EXECUTION_BINDING_ID
    original_provider_call_artifact_count: Literal[152] = FAILED_PROVIDER_CALL_COUNT
    original_provider_payloads_replayed_before_continuation: Literal[True] = True
    source_replay_before_client_construction: Literal[True] = True
    raw_only_recovery_supported: Literal[True] = True
    post_terminal_short_circuits_explicitly_bound: Literal[True] = True
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=1)
    schema_version: str = V26_BUDGET_RECOVERY_BINDING_VERSION

    @property
    def execution_run_id(self) -> str:
        return self.recovery_run_id

    @model_validator(mode="after")
    def validate_binding(self) -> BudgetRecoveryExecutionBinding:
        paths = tuple(item.relative_path for item in self.implementation_source_files)
        if paths != RECOVERY_IMPLEMENTATION_SOURCE_PATHS:
            raise ValueError("budget Recovery Binding source manifest changed")
        if self.binding_id != budget_recovery_execution_binding_id(self):
            raise ValueError("budget Recovery Binding identity is invalid")
        return self


class BudgetRecoveryPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    recovery_run_id: str = Field(min_length=1)
    failed_run_audit_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    recovery_execution_binding_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    source_replay_file_count: int = Field(ge=1)
    source_replay_pass_count: int = Field(ge=1)
    original_provider_artifact_replay_count: Literal[152] = FAILED_PROVIDER_CALL_COUNT
    exposed_job_zero_generation_replay_count: Literal[20] = FAILED_EXPOSED_JOB_COUNT
    unopened_job_count: Literal[12] = UNOPENED_CONTINUATION_JOB_COUNT
    exposed_job_model_call_count: Literal[0] = 0
    historical_job_retry_count: Literal[0] = 0
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal[
        "zero_generation_replay_20_and_exact_unopened_12_continuation_only"
    ] = "zero_generation_replay_20_and_exact_unopened_12_continuation_only"
    recovery_execution_authorized: Literal[True] = True
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_BUDGET_RECOVERY_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetRecoveryPreflightReport:
        if self.source_replay_pass_count != self.source_replay_file_count:
            raise ValueError("budget Recovery preflight source replay changed")
        if self.report_id != budget_recovery_preflight_report_id(self):
            raise ValueError("budget Recovery preflight identity is invalid")
        return self


class BudgetRecoveryRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    recovery_execution_binding_id: str = Field(min_length=1)
    recovery_job_id: str = Field(min_length=1)
    recovery_role: RecoveryRole
    original_execution_binding_id: str | None = None
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    job: BudgetClosedInstrumentJob
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    execution_kind: ExecutionKind
    provider_call_artifacts: tuple[RawFileDescriptor, ...]
    provider_call_ids: tuple[str, ...]
    provider_telemetry: tuple[ModelCallTelemetry, ...]
    provider_request_prompts: tuple[str, ...]
    host_telemetry: tuple[ModelCallTelemetry, ...]
    host_request_prompts: tuple[str, ...]
    attempted_model_prompts: tuple[str, ...] = Field(min_length=1)
    post_terminal_short_circuit_prompts: tuple[str, ...]
    provider_budget_audit: ProviderTokenBudgetAudit
    solve_result: IterativeAgentSolveResult | None = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    recursive_noninterference_passed: bool
    captured_before_verifier_replay_and_scoring: Literal[True] = True
    verifier_replay_or_score_fields_present: Literal[False] = False
    schema_version: str = V26_BUDGET_RECOVERY_RAW_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> BudgetRecoveryRawExecution:
        replay = self.recovery_role == "zero_generation_replay"
        if replay != (self.original_execution_binding_id == FAILED_EXECUTION_BINDING_ID):
            raise ValueError("recovered raw execution capture lineage changed")
        if (
            self.task_record_id != self.job.task_record_id
            or self.task_package_id != self.job.task_package_id
            or self.environment_manifest_id != self.job.environment_manifest_id
            or self.replay_binding_contract_id != self.job.replay_binding_contract_id
        ):
            raise ValueError("recovered raw execution loses a Job identity")
        call_count = len(self.provider_call_ids)
        if not (
            call_count
            == len(self.provider_call_artifacts)
            == len(self.provider_telemetry)
            == len(self.provider_request_prompts)
            == len(self.host_telemetry)
            == len(self.host_request_prompts)
        ):
            raise ValueError("recovered raw Provider denominator changed")
        expected_calls = tuple(
            provider_call_id(self.job.job_id, index, telemetry)
            for index, telemetry in enumerate(self.provider_telemetry)
        )
        if self.provider_call_ids != expected_calls:
            raise ValueError("recovered raw Provider identities changed")
        provider_hashes = tuple(_sha256_text(item) for item in self.provider_request_prompts)
        if provider_hashes != tuple(item.request_hash for item in self.provider_telemetry):
            raise ValueError("recovered raw Provider Prompt accounting changed")
        if self.provider_request_prompts != self.host_request_prompts or any(
            not _provider_telemetry_equal_before_host_augmentation(provider, host)
            for provider, host in zip(self.provider_telemetry, self.host_telemetry, strict=True)
        ):
            raise ValueError("recovered Provider and Host telemetry changed")
        audit = self.provider_budget_audit
        certificates = audit.certificates
        attempted_hashes = tuple(_sha256_text(item) for item in self.attempted_model_prompts)
        certificate_hashes = tuple(item.request_hash for item in certificates)
        if certificate_hashes != attempted_hashes[: len(certificates)]:
            raise ValueError("budget certificates do not bind the Host-attempt prefix")
        suffix = self.attempted_model_prompts[len(certificates) :]
        if self.post_terminal_short_circuit_prompts != suffix:
            raise ValueError("post-terminal short-circuit Prompt suffix changed")
        permitted = tuple(item for item in certificates if item.provider_call_permitted)
        if (
            audit.contract_id != EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
            or audit.provider_call_count != call_count
            or audit.permitted_request_count != call_count
            or len(permitted) != call_count
            or tuple(item.request_hash for item in permitted) != provider_hashes
            or audit.actual_request_prompt_hashes != provider_hashes
            or tuple(item.certificate_id for item in permitted)
            != tuple(item.certificate_id for item in audit.usage_records)
        ):
            raise ValueError("recovered raw budget accounting changed")
        if self.post_terminal_short_circuit_prompts and (
            audit.no_call_terminal is None and audit.status != "failed"
        ):
            raise ValueError("uncertified Prompt was not blocked by a frozen budget terminal")
        if self.execution_kind == "completed_trajectory":
            if (
                self.solve_result is None
                or self.failure_artifact is not None
                or self.execution_error
            ):
                raise ValueError("recovered completed execution payload changed")
        elif self.execution_kind == "typed_budget_no_call":
            if self.solve_result is not None or audit.no_call_terminal is None:
                raise ValueError("recovered typed no-call payload changed")
        elif self.execution_kind == "captured_model_contract_failure":
            if self.solve_result is not None or self.failure_artifact is None:
                raise ValueError("recovered model-contract failure payload changed")
        elif self.execution_kind == "provider_budget_contract_failure":
            if audit.status != "failed":
                raise ValueError("recovered budget failure has a passing audit")
        if self.artifact_id != budget_recovery_raw_execution_id(self):
            raise ValueError("recovered raw execution identity is invalid")
        return self


class BudgetRecoveryRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    recovery_execution_binding_id: str = Field(min_length=1)
    original_execution_binding_id: str = FAILED_EXECUTION_BINDING_ID
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    observed_job_count: int = Field(ge=0, le=32)
    zero_generation_replay_job_count: int = Field(ge=0, le=20)
    continuation_job_count: int = Field(ge=0, le=12)
    exposed_job_model_call_count: Literal[0] = 0
    original_provider_artifact_count: int = Field(ge=0)
    continuation_provider_artifact_count: int = Field(ge=0)
    original_provider_exact_byte_pass_count: int = Field(ge=0)
    raw_execution_byte_pass_count: int = Field(ge=0, le=32)
    raw_execution_identity_pass_count: int = Field(ge=0, le=32)
    provider_capture_pass_count: int = Field(ge=0, le=32)
    provider_budget_binding_pass_count: int = Field(ge=0, le=32)
    provider_host_telemetry_pass_count: int = Field(ge=0, le=32)
    prompt_partition_pass_count: int = Field(ge=0, le=32)
    post_terminal_short_circuit_prompt_count: int = Field(ge=0)
    provider_call_ids_unique: bool
    duplicate_provider_call_ids: tuple[str, ...] = ()
    failed_artifacts: tuple[str, ...] = ()
    status: Literal["passed", "partial", "failed"]
    schema_version: str = V26_BUDGET_RECOVERY_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetRecoveryRawLineageAudit:
        observed_provider = (
            self.original_provider_artifact_count + self.continuation_provider_artifact_count
        )
        per_job = (
            self.raw_execution_byte_pass_count,
            self.raw_execution_identity_pass_count,
            self.provider_capture_pass_count,
            self.provider_budget_binding_pass_count,
            self.provider_host_telemetry_pass_count,
            self.prompt_partition_pass_count,
        )
        complete = bool(
            self.observed_job_count == EXPECTED_JOB_COUNT
            and self.zero_generation_replay_job_count == FAILED_EXPOSED_JOB_COUNT
            and self.continuation_job_count == UNOPENED_CONTINUATION_JOB_COUNT
            and self.original_provider_artifact_count == FAILED_PROVIDER_CALL_COUNT
            and self.original_provider_exact_byte_pass_count == FAILED_PROVIDER_CALL_COUNT
            and all(item == EXPECTED_JOB_COUNT for item in per_job)
        )
        partial = bool(
            self.zero_generation_replay_job_count + self.continuation_job_count
            == self.observed_job_count
            and self.original_provider_exact_byte_pass_count
            == self.original_provider_artifact_count
            and all(item == self.observed_job_count for item in per_job)
            and observed_provider >= self.original_provider_artifact_count
        )
        expected = (
            "passed"
            if complete and self.provider_call_ids_unique and not self.failed_artifacts
            else "partial"
            if partial and self.provider_call_ids_unique and not self.failed_artifacts
            else "failed"
        )
        if self.status != expected:
            raise ValueError("budget Recovery raw-lineage status changed")
        if self.audit_id != budget_recovery_raw_lineage_audit_id(self):
            raise ValueError("budget Recovery raw-lineage identity is invalid")
        return self


class BudgetRecoveryReport(FrozenModel):
    report_id: str = Field(min_length=1)
    recovery_run_id: str = Field(min_length=1)
    failed_run_audit_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    recovery_execution_binding_id: str = Field(min_length=1)
    discovered_models: tuple[str, ...]
    completed_rollout_count: Literal[32] = EXPECTED_JOB_COUNT
    zero_generation_replayed_job_count: Literal[20] = FAILED_EXPOSED_JOB_COUNT
    continuation_model_job_count: Literal[12] = UNOPENED_CONTINUATION_JOB_COUNT
    exposed_job_model_call_count: Literal[0] = 0
    terminal_counts: dict[str, int]
    core_terminal_counts: dict[str, int]
    model_outcome_count: int = Field(ge=0, le=32)
    model_valid_trajectory_count: int = Field(ge=0, le=32)
    model_invalid_trajectory_count: int = Field(ge=0, le=32)
    budget_exhausted_no_call_count: int = Field(ge=0, le=32)
    no_call_phase_counts: dict[str, int]
    runtime_failure_count: int = Field(ge=0, le=32)
    instrument_gate_failure_count: int = Field(ge=0, le=32)
    report_completeness_failure_count: int = Field(ge=0, le=32)
    exact_requested_model_count: int = Field(ge=0, le=32)
    fallback_count: int = Field(ge=0, le=32)
    original_provider_call_count: Literal[152] = FAILED_PROVIDER_CALL_COUNT
    continuation_provider_call_count: int = Field(ge=0)
    total_provider_call_count: int = Field(ge=152)
    original_provider_total_tokens: Literal[1380628] = FAILED_PROVIDER_TOTAL_TOKENS
    continuation_provider_total_tokens: int = Field(ge=0)
    total_provider_tokens: int = Field(ge=1380628)
    original_estimated_cost_usd: str = FAILED_ESTIMATED_COST_USD
    continuation_estimated_cost_usd: str = Field(min_length=1)
    total_estimated_cost_usd: str = Field(min_length=1)
    post_terminal_short_circuit_prompt_count: int = Field(ge=0)
    raw_lineage_audit: BudgetRecoveryRawLineageAudit
    diagnostics: tuple[BudgetClosedRolloutDiagnostic, ...] = Field(min_length=32, max_length=32)
    mechanism_summaries: tuple[BudgetClosedMechanismSummary, ...] = Field(
        min_length=4, max_length=4
    )
    replay_pass_count: int = Field(ge=0, le=32)
    replay_failure_count: int = Field(ge=0, le=32)
    independent_non_replay_audit_count: int = Field(ge=0, le=32)
    completed_shared_score_count: int = Field(ge=0, le=32)
    schema_closed_sidecar_pass_count: int = Field(ge=0, le=32)
    independently_valid_trajectory_count: int = Field(ge=0, le=32)
    full_program_lineage_count: int = Field(ge=0, le=32)
    terminal_node_completion_count: int = Field(ge=0, le=32)
    postterminal_verification_count: int = Field(ge=0, le=32)
    local_mechanism_success_count: int = Field(ge=0, le=32)
    unique_successful_tool_sequence_count: int = Field(ge=0)
    effective_successful_tool_sequence_count: float = Field(ge=0.0)
    maximum_successful_tool_sequence_share: float = Field(ge=0.0, le=1.0)
    resource_budget_passed: bool
    recovery_instrument_ready: bool
    status: Literal["passed", "blocked"]
    next_permitted_stage: Literal[
        "fresh_capability_and_reachability_protocol_design_only",
        "budget_closed_recovery_resource_failure_audit_only",
        "budget_closed_recovery_instrument_failure_audit_only",
    ]
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_BUDGET_RECOVERY_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetRecoveryReport:
        if self.total_provider_call_count != (
            self.original_provider_call_count + self.continuation_provider_call_count
        ):
            raise ValueError("budget Recovery Provider-call accounting changed")
        if self.total_provider_tokens != (
            self.original_provider_total_tokens + self.continuation_provider_total_tokens
        ):
            raise ValueError("budget Recovery token accounting changed")
        if Decimal(self.total_estimated_cost_usd) != (
            Decimal(self.original_estimated_cost_usd)
            + Decimal(self.continuation_estimated_cost_usd)
        ):
            raise ValueError("budget Recovery cost accounting changed")
        expected_status = "passed" if self.recovery_instrument_ready else "blocked"
        if self.status != expected_status:
            raise ValueError("budget Recovery report status changed")
        expected_stage = (
            "fresh_capability_and_reachability_protocol_design_only"
            if self.status == "passed"
            else "budget_closed_recovery_resource_failure_audit_only"
            if not self.resource_budget_passed
            else "budget_closed_recovery_instrument_failure_audit_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("budget Recovery transition changed")
        if self.report_id != budget_recovery_report_id(self):
            raise ValueError("budget Recovery report identity is invalid")
        return self


class _StoredReplayResult:
    def __init__(
        self,
        *,
        result: IterativeAgentSolveResult | None,
        failure: IterativeAgentFailureArtifact | None,
        execution_error: str | None,
        execution_kind: ExecutionKind,
        provider_telemetry: tuple[ModelCallTelemetry, ...],
        provider_prompts: tuple[str, ...],
        host_telemetry: tuple[ModelCallTelemetry, ...],
        host_prompts: tuple[str, ...],
        attempted_prompts: tuple[str, ...],
        budget_audit: ProviderTokenBudgetAudit,
        consumed_call_count: int,
    ) -> None:
        self.result = result
        self.failure = failure
        self.execution_error = execution_error
        self.execution_kind = execution_kind
        self.provider_telemetry = provider_telemetry
        self.provider_prompts = provider_prompts
        self.host_telemetry = host_telemetry
        self.host_prompts = host_prompts
        self.attempted_prompts = attempted_prompts
        self.budget_audit = budget_audit
        self.consumed_call_count = consumed_call_count


class _RecoveryPrepared:
    def __init__(
        self,
        *,
        original_contract: BudgetClosedInstrumentContract,
        original_manifest: BudgetClosedInstrumentJobManifest,
        original_execution_binding: BudgetClosedExecutionBinding,
        failed_run_audit: BudgetFailedRunAudit,
        source_replay: BudgetRecoverySourceReplayAudit,
        recovery_contract: BudgetRecoveryContract,
        recovery_manifest: BudgetRecoveryManifest,
        recovery_binding: BudgetRecoveryExecutionBinding,
        preflight: BudgetRecoveryPreflightReport,
        records: tuple[OperationalTaskRecord, ...],
        environments: tuple[AgentToolEnvironmentManifest, ...],
        bindings: tuple[VerifierV2TaskReplayBinding, ...],
        replay_contract: Any,
        calls_by_job: Mapping[str, tuple[BudgetClosedRawProviderCall, ...]],
        provider_manifest: tuple[dict[str, Any], ...],
    ) -> None:
        self.original_contract = original_contract
        self.original_manifest = original_manifest
        self.original_execution_binding = original_execution_binding
        self.failed_run_audit = failed_run_audit
        self.source_replay = source_replay
        self.recovery_contract = recovery_contract
        self.recovery_manifest = recovery_manifest
        self.recovery_binding = recovery_binding
        self.preflight = preflight
        self.records = records
        self.environments = environments
        self.bindings = bindings
        self.replay_contract = replay_contract
        self.calls_by_job = calls_by_job
        self.provider_manifest = provider_manifest


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _implementation_sources(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(
            relative_path=relative,
            sha256=_sha256(package_root / relative),
        )
        for relative in RECOVERY_IMPLEMENTATION_SOURCE_PATHS
    )


def _relative_to_package(path: Path, package_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(package_root.resolve()))
    except ValueError as exc:
        raise ValueError(f"budget Recovery path escapes package root: {path}") from exc


class _StoredBudgetReplayClient:
    def __init__(
        self,
        config: AgentModelConfig,
        calls: tuple[BudgetClosedRawProviderCall, ...],
    ) -> None:
        self.config = config
        self.calls = calls
        self.index = 0

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if self.index >= len(self.calls):
            raise RuntimeError("stored Replay requested an unobserved Provider call")
        call = self.calls[self.index]
        if prompt != call.prompt or _sha256_text(prompt) != call.prompt_sha256:
            raise RuntimeError(f"stored Replay Prompt mismatch at call {self.index}")
        if call.response_payload is None:
            raise RuntimeError(f"stored Replay response missing at call {self.index}")
        self.index += 1
        return call.response_payload, call.provider_telemetry


def _load_provider_calls(
    *,
    failed_run_dir: Path,
    manifest: BudgetClosedInstrumentJobManifest,
) -> tuple[
    dict[str, tuple[BudgetClosedRawProviderCall, ...]],
    tuple[dict[str, Any], ...],
]:
    jobs = {item.job_id: item for item in manifest.jobs}
    grouped: dict[str, list[tuple[Path, BudgetClosedRawProviderCall]]] = defaultdict(list)
    for path in sorted((failed_run_dir / "raw_provider_calls").glob("**/call_*.json")):
        raw_bytes = path.read_bytes()
        payload = json.loads(raw_bytes)
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if raw_bytes != canonical:
            raise ValueError(f"failed raw Provider Artifact is not canonical: {path}")
        artifact = BudgetClosedRawProviderCall.model_validate(payload)
        if (
            artifact.execution_binding_id != FAILED_EXECUTION_BINDING_ID
            or artifact.job_id not in jobs
            or artifact.contract_id != EXPECTED_CONTRACT_ID
            or artifact.response_payload is None
            or not artifact.provider_telemetry.http_success
            or artifact.provider_telemetry.model_requested != "deepseek-v4-flash"
            or artifact.provider_telemetry.model_selected != "deepseek-v4-flash"
            or artifact.provider_telemetry.response_model != "deepseek-v4-flash"
            or artifact.provider_telemetry.fallback_used
        ):
            raise ValueError(f"failed raw Provider binding changed: {path}")
        grouped[artifact.job_id].append((path, artifact))
    calls_by_job: dict[str, tuple[BudgetClosedRawProviderCall, ...]] = {}
    provider_manifest: list[dict[str, Any]] = []
    provider_ids: list[str] = []
    for job_id, rows in sorted(grouped.items()):
        ordered_rows = tuple(sorted(rows, key=lambda pair: pair[1].call_index))
        calls = tuple(item for _, item in ordered_rows)
        if tuple(item.call_index for item in calls) != tuple(range(len(calls))):
            raise ValueError(f"failed Provider stream is not contiguous: {job_id}")
        calls_by_job[job_id] = calls
        for path, artifact in ordered_rows:
            provider_ids.append(artifact.provider_call_id)
            provider_manifest.append(
                {
                    "relative_path": str(path.relative_to(failed_run_dir)),
                    "sha256": _sha256(path),
                    "byte_count": path.stat().st_size,
                    "artifact_id": artifact.artifact_id,
                    "job_id": artifact.job_id,
                    "call_index": artifact.call_index,
                    "provider_call_id": artifact.provider_call_id,
                    "provider_total_tokens": artifact.provider_telemetry.total_tokens,
                    "estimated_cost_usd": str(
                        Decimal(str(artifact.provider_telemetry.estimated_cost or 0))
                    ),
                }
            )
    if len(provider_ids) != len(set(provider_ids)):
        raise ValueError("failed Provider call identities are not unique")
    return calls_by_job, tuple(provider_manifest)


def _replay_stored_job(
    *,
    job: BudgetClosedInstrumentJob,
    contract: BudgetClosedInstrumentContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    calls: tuple[BudgetClosedRawProviderCall, ...],
) -> _StoredReplayResult:
    if tuple(item.call_index for item in calls) != tuple(range(len(calls))):
        raise ValueError(f"stored Provider call indices changed: {job.job_id}")
    stored = _StoredBudgetReplayClient(
        AgentModelConfig.model_validate(contract.model_invocation_config),
        calls,
    )
    budget = BudgetClosedJsonClient(stored, contract.provider_token_budget_contract)
    attempts = _AttemptPromptJournalClient(budget)
    result: IterativeAgentSolveResult | None = None
    failure: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    try:
        result = IterativeAgentSolver(
            attempts,
            mode="autonomous_agent",
            maximum_total_tokens=contract.provider_token_budget_contract.maximum_total_tokens,
            protocol_profile=IterativeAgentProtocolProfile(),
        ).solve_with_audit(record.task_package.task.public, _runtime(record, environment))
    except LLMClientError as exc:
        failure = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact)
            else None
        )
        execution_error = _safe_error(exc)
    audit = budget.audit()
    provider_telemetry = tuple(item.provider_telemetry for item in calls)
    provider_prompts = tuple(item.prompt for item in calls)
    if result is not None:
        host_telemetry = result.audit.telemetry
        host_prompts = result.audit.model_request_prompts
    elif failure is not None:
        host_telemetry = failure.telemetry
        host_prompts = failure.model_request_prompts
    else:
        raise ValueError(f"stored Replay produced no terminal Artifact: {job.job_id}")
    if stored.index != len(calls):
        raise ValueError(f"stored Replay did not consume every response: {job.job_id}")
    if provider_prompts != host_prompts or len(provider_telemetry) != len(host_telemetry):
        raise ValueError(f"stored Replay changed the Provider stream: {job.job_id}")
    if any(
        not _provider_telemetry_equal_before_host_augmentation(provider, host)
        for provider, host in zip(provider_telemetry, host_telemetry, strict=True)
    ):
        raise ValueError(f"stored Replay changed Provider telemetry: {job.job_id}")
    if audit.status != "passed" or audit.provider_call_count != len(calls):
        raise ValueError(f"stored Replay budget audit failed: {job.job_id}")
    if audit.actual_request_prompt_hashes != tuple(_sha256_text(item) for item in provider_prompts):
        raise ValueError(f"stored Replay changed actual Prompt accounting: {job.job_id}")
    if tuple(item.request_hash for item in audit.certificates) != tuple(
        _sha256_text(item) for item in attempts.prompts[: len(audit.certificates)]
    ):
        raise ValueError(f"stored Replay certificate prefix changed: {job.job_id}")
    execution_kind: ExecutionKind
    if result is not None:
        execution_kind = "completed_trajectory"
    elif audit.no_call_terminal is not None:
        execution_kind = "typed_budget_no_call"
    elif failure is not None:
        execution_kind = "captured_model_contract_failure"
    else:
        execution_kind = "unexpected_execution_failure"
    return _StoredReplayResult(
        result=result,
        failure=failure,
        execution_error=execution_error,
        execution_kind=execution_kind,
        provider_telemetry=provider_telemetry,
        provider_prompts=provider_prompts,
        host_telemetry=tuple(host_telemetry),
        host_prompts=tuple(host_prompts),
        attempted_prompts=tuple(attempts.prompts),
        budget_audit=audit,
        consumed_call_count=stored.index,
    )


def _build_failed_job_audit(
    *,
    job: BudgetClosedInstrumentJob,
    contract: BudgetClosedInstrumentContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    calls: tuple[BudgetClosedRawProviderCall, ...],
    raw_job_ids: set[str],
    checkpoint_job_ids: set[str],
) -> BudgetFailedJobAudit:
    replay = _replay_stored_job(
        job=job,
        contract=contract,
        record=record,
        environment=environment,
        calls=calls,
    )
    terminal: ReplayTerminal = (
        "completed_trajectory"
        if replay.result is not None
        else "budget_exhausted_no_call"
        if replay.budget_audit.no_call_terminal is not None
        else "model_contract_failure"
    )
    observations = (
        replay.result.observations
        if replay.result is not None
        else replay.failure.observations
        if replay.failure is not None
        else ()
    )
    cost = sum(
        (Decimal(str(item.provider_telemetry.estimated_cost or 0)) for item in calls),
        Decimal("0"),
    )
    values = {
        "job_id": job.job_id,
        "task_package_id": job.task_package_id,
        "mechanism_id": job.mechanism_id,
        "provider_call_count": len(calls),
        "provider_total_tokens": sum(item.provider_telemetry.total_tokens or 0 for item in calls),
        "estimated_cost_usd": str(cost),
        "replay_terminal": terminal,
        "observation_count": len(observations),
        "recorded_call_count": len(calls),
        "consumed_call_count": replay.consumed_call_count,
        "attempted_prompt_count": len(replay.attempted_prompts),
        "certificate_count": len(replay.budget_audit.certificates),
        "permitted_request_count": replay.budget_audit.permitted_request_count,
        "denied_no_call_count": replay.budget_audit.denied_no_call_count,
        "post_terminal_short_circuit_prompt_count": (
            len(replay.attempted_prompts) - len(replay.budget_audit.certificates)
        ),
        "raw_execution_artifact_present": job.job_id in raw_job_ids,
        "rollout_checkpoint_present": job.job_id in checkpoint_job_ids,
    }
    provisional = BudgetFailedJobAudit.model_construct(audit_id="pending", **values)
    return BudgetFailedJobAudit(
        audit_id=budget_failed_job_audit_id(provisional),
        **values,
    )


def _build_source_replay(
    *,
    failed_run_dir: Path,
    package_root: Path,
    failed_source_replay: BudgetClosedOnlineSourceReplayAudit,
) -> BudgetRecoverySourceReplayAudit:
    expected: dict[str, tuple[str, str]] = {}

    def register(relative: str, sha256: str, kind: str) -> None:
        prior = expected.get(relative)
        if prior is not None and prior[0] != sha256:
            raise ValueError(f"Recovery source manifests disagree for {relative}")
        expected[relative] = prior or (sha256, kind)

    for item in failed_source_replay.entries:
        register(item.relative_path, item.expected_sha256, "frozen_online_source")
    for path in sorted(item for item in failed_run_dir.rglob("*") if item.is_file()):
        register(
            _relative_to_package(path, package_root),
            _sha256(path),
            "failed_execution_artifact",
        )
    for descriptor in _implementation_sources(package_root):
        register(
            descriptor.relative_path,
            descriptor.sha256,
            "recovery_implementation",
        )
    entries = tuple(
        BudgetRecoverySourceReplayEntry(
            relative_path=relative,
            expected_sha256=expected_sha,
            observed_sha256=_sha256(package_root / relative),
            byte_count=(package_root / relative).stat().st_size,
            source_kind=cast(Any, kind),
        )
        for relative, (expected_sha, kind) in sorted(expected.items())
    )
    values = {
        "entries": entries,
        "replayed_file_count": len(entries),
        "replay_pass_count": len(entries),
    }
    provisional = BudgetRecoverySourceReplayAudit.model_construct(audit_id="pending", **values)
    return BudgetRecoverySourceReplayAudit(
        audit_id=budget_recovery_source_replay_audit_id(provisional),
        **values,
    )


def build_budget_recovery_preflight(
    *,
    recovery_run_id: str,
    failed_run_dir: Path,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> _RecoveryPrepared:
    prepared = prepare_budget_closed_instrument_execution(
        execution_run_id=FAILED_EXECUTION_RUN_ID,
        task_source_dir=task_source_dir,
        verifier_qualification_dir=verifier_qualification_dir,
        preflight_dir=preflight_dir,
        output_dir=failed_run_dir,
        package_root=package_root,
    )
    original_binding = BudgetClosedExecutionBinding.model_validate_json(
        (failed_run_dir / "execution_binding.json").read_text(encoding="utf-8")
    )
    failed_source_replay = BudgetClosedOnlineSourceReplayAudit.model_validate_json(
        (failed_run_dir / "online_source_replay_audit.json").read_text(encoding="utf-8")
    )
    if (
        original_binding.binding_id != FAILED_EXECUTION_BINDING_ID
        or original_binding.execution_run_id != FAILED_EXECUTION_RUN_ID
        or failed_source_replay.audit_id != FAILED_SOURCE_REPLAY_AUDIT_ID
        or prepared.execution_binding != original_binding
        or prepared.source_audit != failed_source_replay
    ):
        raise ValueError("budget Recovery received another failed execution")
    calls_by_job, provider_manifest = _load_provider_calls(
        failed_run_dir=failed_run_dir,
        manifest=prepared.manifest,
    )
    exposed_job_ids = tuple(sorted(calls_by_job))
    all_job_ids = {item.job_id for item in prepared.manifest.jobs}
    unopened_job_ids = tuple(sorted(all_job_ids - set(exposed_job_ids)))
    if (
        len(exposed_job_ids) != FAILED_EXPOSED_JOB_COUNT
        or len(unopened_job_ids) != UNOPENED_CONTINUATION_JOB_COUNT
        or len(provider_manifest) != FAILED_PROVIDER_CALL_COUNT
    ):
        raise ValueError("budget Recovery failed-run denominator changed")
    raw_paths = tuple(sorted((failed_run_dir / "raw_execution").glob("**/replicate_*.json")))
    raw_rows = tuple(
        BudgetClosedRawExecution.model_validate_json(path.read_text(encoding="utf-8"))
        for path in raw_paths
    )
    if len(raw_rows) != FAILED_RAW_EXECUTION_COUNT:
        raise ValueError("failed-run raw execution denominator changed")
    raw_job_ids = {item.job.job_id for item in raw_rows}
    checkpoint_path = failed_run_dir / "rollout_observations.checkpoint.jsonl"
    checkpoint_rows = tuple(
        BudgetClosedInstrumentRollout.model_validate_json(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(checkpoint_rows) != FAILED_CHECKPOINT_COUNT or len(
        {item.job_id for item in checkpoint_rows}
    ) != len(checkpoint_rows):
        raise ValueError("failed-run checkpoint denominator changed")
    checkpoint_job_ids = {item.job_id for item in checkpoint_rows}
    if not checkpoint_job_ids < raw_job_ids:
        raise ValueError("failed-run checkpoint is not a strict Raw Execution subset")
    runner_failure_rows = tuple(
        json.loads(line)
        for line in (failed_run_dir / "runner_failures.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    if len(runner_failure_rows) != FAILED_RUNNER_FAILURE_COUNT:
        raise ValueError("failed-run Runner failure denominator changed")
    record_by_id = {item.record_id: item for item in prepared.records}
    environment_by_id = {item.manifest_id: item for item in prepared.environments}
    job_by_id = {item.job_id: item for item in prepared.manifest.jobs}
    job_audits = tuple(
        sorted(
            (
                _build_failed_job_audit(
                    job=job_by_id[job_id],
                    contract=prepared.contract,
                    record=record_by_id[job_by_id[job_id].task_record_id],
                    environment=environment_by_id[job_by_id[job_id].environment_manifest_id],
                    calls=calls_by_job[job_id],
                    raw_job_ids=raw_job_ids,
                    checkpoint_job_ids=checkpoint_job_ids,
                )
                for job_id in exposed_job_ids
            ),
            key=lambda item: item.job_id,
        )
    )
    provider_tokens = sum(item.provider_total_tokens for item in job_audits)
    provider_cost = sum(
        (Decimal(item.estimated_cost_usd) for item in job_audits),
        Decimal("0"),
    )
    if provider_tokens != FAILED_PROVIDER_TOTAL_TOKENS or str(provider_cost) != (
        FAILED_ESTIMATED_COST_USD
    ):
        raise ValueError("failed-run resource telemetry changed")
    provider_manifest_hash = canonical_hash(
        provider_manifest,
        prefix="finance_v26_budget_failed_provider_artifact_manifest:",
    )
    failed_values = {
        "exposed_job_ids": exposed_job_ids,
        "unopened_job_ids": unopened_job_ids,
        "raw_provider_artifact_manifest_hash": provider_manifest_hash,
        "completed_trajectory_replay_count": sum(
            item.replay_terminal == "completed_trajectory" for item in job_audits
        ),
        "model_contract_failure_replay_count": sum(
            item.replay_terminal == "model_contract_failure" for item in job_audits
        ),
        "budget_exhausted_no_call_replay_count": sum(
            item.replay_terminal == "budget_exhausted_no_call" for item in job_audits
        ),
        "recovered_observation_count": sum(item.observation_count for item in job_audits),
        "post_terminal_short_circuit_prompt_count": sum(
            item.post_terminal_short_circuit_prompt_count for item in job_audits
        ),
        "job_audits": job_audits,
    }
    provisional_failed = BudgetFailedRunAudit.model_construct(audit_id="pending", **failed_values)
    failed_audit = BudgetFailedRunAudit(
        audit_id=budget_failed_run_audit_id(provisional_failed),
        **failed_values,
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
        "exposed_job_ids": exposed_job_ids,
        "unopened_job_ids": unopened_job_ids,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional_contract = BudgetRecoveryContract.model_construct(
        contract_id="pending", **contract_values
    )
    recovery_contract = BudgetRecoveryContract(
        contract_id=budget_recovery_contract_id(provisional_contract),
        **contract_values,
    )
    exposed = set(exposed_job_ids)
    recovery_jobs: list[BudgetRecoveryJob] = []
    for original_job in prepared.manifest.jobs:
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
        provisional_job = BudgetRecoveryJob.model_construct(recovery_job_id="pending", **values)
        recovery_jobs.append(
            BudgetRecoveryJob(
                recovery_job_id=budget_recovery_job_id(provisional_job),
                **values,
            )
        )
    ordered_jobs = tuple(sorted(recovery_jobs, key=lambda item: item.recovery_job_id))
    manifest_values = {
        "recovery_contract_id": recovery_contract.contract_id,
        "jobs": ordered_jobs,
    }
    provisional_manifest = BudgetRecoveryManifest.model_construct(
        manifest_id="pending", **manifest_values
    )
    recovery_manifest = BudgetRecoveryManifest(
        manifest_id=budget_recovery_manifest_id(provisional_manifest),
        **manifest_values,
    )
    binding_values = {
        "recovery_run_id": recovery_run_id,
        "recovery_contract_id": recovery_contract.contract_id,
        "recovery_manifest_id": recovery_manifest.manifest_id,
        "source_replay_audit_id": source_replay.audit_id,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional_binding = BudgetRecoveryExecutionBinding.model_construct(
        binding_id="pending", **binding_values
    )
    recovery_binding = BudgetRecoveryExecutionBinding(
        binding_id=budget_recovery_execution_binding_id(provisional_binding),
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
    provisional_preflight = BudgetRecoveryPreflightReport.model_construct(
        report_id="pending", **preflight_values
    )
    preflight = BudgetRecoveryPreflightReport(
        report_id=budget_recovery_preflight_report_id(provisional_preflight),
        **preflight_values,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_dir / "failed_run_audit.json", failed_audit.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "failed_run_job_audits.json",
        [item.model_dump(mode="json") for item in job_audits],
    )
    _write_json_atomic(output_dir / "raw_provider_artifact_manifest.json", list(provider_manifest))
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
        original_contract=prepared.contract,
        original_manifest=prepared.manifest,
        original_execution_binding=original_binding,
        failed_run_audit=failed_audit,
        source_replay=source_replay,
        recovery_contract=recovery_contract,
        recovery_manifest=recovery_manifest,
        recovery_binding=recovery_binding,
        preflight=preflight,
        records=prepared.records,
        environments=prepared.environments,
        bindings=prepared.bindings,
        replay_contract=prepared.replay_contract,
        calls_by_job=calls_by_job,
        provider_manifest=provider_manifest,
    )


def _load_recovery_raw(path: Path) -> BudgetRecoveryRawExecution:
    raw_bytes = path.read_bytes()
    payload = json.loads(raw_bytes)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw_bytes != canonical:
        raise ValueError(f"recovered raw execution is not canonical: {path}")
    return BudgetRecoveryRawExecution.model_validate(payload)


def _copy_original_provider_artifact(
    *,
    failed_run_dir: Path,
    output_dir: Path,
    job: BudgetClosedInstrumentJob,
    call: BudgetClosedRawProviderCall,
) -> RawFileDescriptor:
    source = _provider_call_path(failed_run_dir, job, call.call_index)
    target = _provider_call_path(output_dir, job, call.call_index)
    source_bytes = source.read_bytes()
    if BudgetClosedRawProviderCall.model_validate_json(source_bytes) != call:
        raise ValueError("failed Provider Artifact changed before Recovery")
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


def _build_recovery_raw(
    *,
    recovery_job: BudgetRecoveryJob,
    prepared: _RecoveryPrepared,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    descriptors: tuple[RawFileDescriptor, ...],
    replay: _StoredReplayResult,
    output_dir: Path,
) -> BudgetRecoveryRawExecution:
    job = recovery_job.original_job
    raw_path = _raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = _load_recovery_raw(raw_path)
        if (
            raw.recovery_execution_binding_id != prepared.recovery_binding.binding_id
            or raw.recovery_job_id != recovery_job.recovery_job_id
            or raw.job != job
        ):
            raise ValueError("recovered raw execution crosses frozen Recovery identities")
        return raw
    values = {
        "recovery_execution_binding_id": prepared.recovery_binding.binding_id,
        "recovery_job_id": recovery_job.recovery_job_id,
        "recovery_role": recovery_job.recovery_role,
        "original_execution_binding_id": (
            FAILED_EXECUTION_BINDING_ID
            if recovery_job.recovery_role == "zero_generation_replay"
            else None
        ),
        "job": job,
        "task_record_id": record.record_id,
        "task_package_id": record.task_package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "replay_binding_contract_id": job.replay_binding_contract_id,
        "execution_kind": replay.execution_kind,
        "provider_call_artifacts": descriptors,
        "provider_call_ids": tuple(
            provider_call_id(job.job_id, index, telemetry)
            for index, telemetry in enumerate(replay.provider_telemetry)
        ),
        "provider_telemetry": replay.provider_telemetry,
        "provider_request_prompts": replay.provider_prompts,
        "host_telemetry": replay.host_telemetry,
        "host_request_prompts": replay.host_prompts,
        "attempted_model_prompts": replay.attempted_prompts,
        "post_terminal_short_circuit_prompts": replay.attempted_prompts[
            len(replay.budget_audit.certificates) :
        ],
        "provider_budget_audit": replay.budget_audit,
        "solve_result": replay.result,
        "failure_artifact": replay.failure,
        "execution_error": replay.execution_error,
        "recursive_noninterference_passed": _recursive_noninterference(
            result=replay.result,
            failure_artifact=replay.failure,
            prompts=replay.host_prompts,
        ),
    }
    provisional = BudgetRecoveryRawExecution.model_construct(artifact_id="pending", **values)
    raw = BudgetRecoveryRawExecution(
        artifact_id=budget_recovery_raw_execution_id(provisional),
        **values,
    )
    _write_raw_atomic(raw_path, raw.model_dump(mode="json"))
    return raw


def _reconstruct_exposed_raw(
    *,
    recovery_job: BudgetRecoveryJob,
    prepared: _RecoveryPrepared,
    failed_run_dir: Path,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    output_dir: Path,
) -> BudgetRecoveryRawExecution:
    if recovery_job.recovery_role != "zero_generation_replay" or (
        recovery_job.model_call_permitted
    ):
        raise ValueError("exposed Recovery Job received model-call authority")
    calls = prepared.calls_by_job.get(recovery_job.original_job.job_id)
    if calls is None:
        raise ValueError("exposed Recovery Job lost its Provider stream")
    replay = _replay_stored_job(
        job=recovery_job.original_job,
        contract=prepared.original_contract,
        record=record,
        environment=environment,
        calls=calls,
    )
    descriptors = tuple(
        _copy_original_provider_artifact(
            failed_run_dir=failed_run_dir,
            output_dir=output_dir,
            job=recovery_job.original_job,
            call=call,
        )
        for call in calls
    )
    return _build_recovery_raw(
        recovery_job=recovery_job,
        prepared=prepared,
        record=record,
        environment=environment,
        descriptors=descriptors,
        replay=replay,
        output_dir=output_dir,
    )


def _load_continuation_calls(
    *,
    output_dir: Path,
    recovery_job: BudgetRecoveryJob,
    binding: BudgetRecoveryExecutionBinding,
) -> tuple[tuple[BudgetClosedRawProviderCall, ...], tuple[RawFileDescriptor, ...]]:
    job = recovery_job.original_job
    directory = _provider_call_path(output_dir, job, 0).parent
    paths = tuple(sorted(directory.glob("call_*.json"))) if directory.exists() else ()
    calls = tuple(
        BudgetClosedRawProviderCall.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    )
    if tuple(item.call_index for item in calls) != tuple(range(len(calls))):
        raise ValueError("continuation Provider call indices are incomplete")
    if any(
        item.execution_binding_id != binding.binding_id or item.job_id != job.job_id
        for item in calls
    ):
        raise ValueError("continuation Provider stream crosses Recovery Bindings")
    descriptors = tuple(
        RawFileDescriptor(
            relative_path=str(path.relative_to(output_dir)),
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in paths
    )
    return calls, descriptors


def _live_replay_result(
    *,
    result: IterativeAgentSolveResult | None,
    failure: IterativeAgentFailureArtifact | None,
    execution_error: str | None,
    provider_telemetry: tuple[ModelCallTelemetry, ...],
    provider_prompts: tuple[str, ...],
    host_telemetry: tuple[ModelCallTelemetry, ...],
    host_prompts: tuple[str, ...],
    attempted_prompts: tuple[str, ...],
    budget_audit: ProviderTokenBudgetAudit,
) -> _StoredReplayResult:
    if result is not None:
        execution_kind: ExecutionKind = "completed_trajectory"
    elif budget_audit.no_call_terminal is not None:
        execution_kind = "typed_budget_no_call"
    elif budget_audit.status == "failed":
        execution_kind = "provider_budget_contract_failure"
    elif (
        failure is not None
        and provider_telemetry
        and all(item.http_success for item in provider_telemetry)
    ):
        execution_kind = "captured_model_contract_failure"
    elif failure is not None:
        execution_kind = "provider_or_runtime_failure"
    else:
        execution_kind = "unexpected_execution_failure"
    return _StoredReplayResult(
        result=result,
        failure=failure,
        execution_error=execution_error,
        execution_kind=execution_kind,
        provider_telemetry=provider_telemetry,
        provider_prompts=provider_prompts,
        host_telemetry=host_telemetry,
        host_prompts=host_prompts,
        attempted_prompts=attempted_prompts,
        budget_audit=budget_audit,
        consumed_call_count=len(provider_telemetry),
    )


def _execute_continuation_raw(
    *,
    recovery_job: BudgetRecoveryJob,
    prepared: _RecoveryPrepared,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    client: OpenAICompatibleJsonClient | None,
    output_dir: Path,
) -> BudgetRecoveryRawExecution:
    job = recovery_job.original_job
    raw_path = _raw_execution_path(output_dir, job)
    if raw_path.exists():
        return _build_recovery_raw(
            recovery_job=recovery_job,
            prepared=prepared,
            record=record,
            environment=environment,
            descriptors=(),
            replay=cast(Any, None),
            output_dir=output_dir,
        )
    if recovery_job.recovery_role != "unopened_model_continuation" or (
        not recovery_job.model_call_permitted
    ):
        raise ValueError("continuation Recovery Job has invalid model-call authority")
    prior_calls, prior_descriptors = _load_continuation_calls(
        output_dir=output_dir,
        recovery_job=recovery_job,
        binding=prepared.recovery_binding,
    )
    if prior_calls:
        replay = _replay_stored_job(
            job=job,
            contract=prepared.original_contract,
            record=record,
            environment=environment,
            calls=prior_calls,
        )
        return _build_recovery_raw(
            recovery_job=recovery_job,
            prepared=prepared,
            record=record,
            environment=environment,
            descriptors=prior_descriptors,
            replay=replay,
            output_dir=output_dir,
        )
    if client is None:
        raise ValueError("unopened continuation Job has no model client")
    recording = _RawFirstJournalClient(
        client,
        execution_binding=cast(Any, prepared.recovery_binding),
        job=job,
        output_dir=output_dir,
    )
    budget = BudgetClosedJsonClient(
        recording,
        prepared.original_contract.provider_token_budget_contract,
    )
    attempts = _AttemptPromptJournalClient(budget)
    result: IterativeAgentSolveResult | None = None
    failure: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    try:
        result = IterativeAgentSolver(
            attempts,
            mode="autonomous_agent",
            maximum_total_tokens=(
                prepared.original_contract.provider_token_budget_contract.maximum_total_tokens
            ),
            protocol_profile=IterativeAgentProtocolProfile(),
        ).solve_with_audit(record.task_package.task.public, _runtime(record, environment))
    except LLMClientError as exc:
        failure = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact)
            else None
        )
        execution_error = _safe_error(exc)
    except Exception as exc:
        execution_error = _safe_error(exc)
    provider_telemetry = tuple(recording.telemetry)
    provider_prompts = tuple(recording.prompts)
    if result is not None:
        host_telemetry = result.audit.telemetry
        host_prompts = result.audit.model_request_prompts
    elif failure is not None:
        host_telemetry = failure.telemetry
        host_prompts = failure.model_request_prompts
    else:
        host_telemetry = provider_telemetry
        host_prompts = provider_prompts
    if (
        provider_prompts != host_prompts
        or len(provider_telemetry) != len(host_telemetry)
        or any(
            not _provider_telemetry_equal_before_host_augmentation(provider, host)
            for provider, host in zip(provider_telemetry, host_telemetry, strict=True)
        )
    ):
        raise ValueError("continuation Provider journal changed after Host augmentation")
    audit = budget.audit()
    replay = _live_replay_result(
        result=result,
        failure=failure,
        execution_error=execution_error,
        provider_telemetry=provider_telemetry,
        provider_prompts=provider_prompts,
        host_telemetry=tuple(host_telemetry),
        host_prompts=tuple(host_prompts),
        attempted_prompts=tuple(attempts.prompts),
        budget_audit=audit,
    )
    return _build_recovery_raw(
        recovery_job=recovery_job,
        prepared=prepared,
        record=record,
        environment=environment,
        descriptors=tuple(recording.descriptors),
        replay=replay,
        output_dir=output_dir,
    )


def _run_recovery_job(
    *,
    recovery_job: BudgetRecoveryJob,
    prepared: _RecoveryPrepared,
    failed_run_dir: Path,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    client: OpenAICompatibleJsonClient | None,
    output_dir: Path,
) -> BudgetClosedInstrumentRollout:
    if recovery_job.recovery_role == "zero_generation_replay":
        if client is not None:
            raise ValueError("zero-generation Recovery Job received a model client")
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
        raw=cast(Any, raw),
        output_dir=output_dir,
    )


def _load_recovery_checkpoint(
    *,
    path: Path,
    prepared: _RecoveryPrepared,
) -> tuple[BudgetClosedInstrumentRollout, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        BudgetClosedInstrumentRollout.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    recovery_by_job = {item.original_job.job_id: item for item in prepared.recovery_manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("budget Recovery checkpoint contains duplicate Jobs")
    for row in rows:
        recovery_job = recovery_by_job.get(row.job_id)
        if (
            recovery_job is None
            or row.execution_binding_id != prepared.recovery_binding.binding_id
            or row.task_record_id != recovery_job.original_job.task_record_id
            or row.task_package_id != recovery_job.original_job.task_package_id
            or row.environment_manifest_id != recovery_job.original_job.environment_manifest_id
            or row.replay_binding_contract_id
            != recovery_job.original_job.replay_binding_contract_id
            or row.replicate_index != recovery_job.original_job.replicate_index
            or _sha256(Path(row.raw_execution_artifact_uri)) != row.raw_execution_artifact_sha256
        ):
            raise ValueError("budget Recovery checkpoint crosses frozen identities")
        raw = _load_recovery_raw(Path(row.raw_execution_artifact_uri))
        if raw.recovery_job_id != recovery_job.recovery_job_id:
            raise ValueError("budget Recovery checkpoint crosses recovered raw identities")
    return rows


def _raw_lineage_failure(job_id: str, exc: Exception) -> str:
    return canonical_hash(
        {"job_id": job_id, "error": _safe_error(exc)},
        prefix="finance_v26_budget_recovery_raw_lineage_failure:",
    )


def _build_recovery_raw_lineage_audit(
    *,
    prepared: _RecoveryPrepared,
    failed_run_dir: Path,
    output_dir: Path,
    rollouts: Sequence[BudgetClosedInstrumentRollout],
) -> BudgetRecoveryRawLineageAudit:
    recovery_by_job = {item.original_job.job_id: item for item in prepared.recovery_manifest.jobs}
    byte_pass = identity_pass = provider_pass = 0
    budget_pass = telemetry_pass = prompt_pass = 0
    replay_jobs = continuation_jobs = 0
    original_provider_count = continuation_provider_count = 0
    original_exact_pass = 0
    post_terminal_count = 0
    provider_ids: list[str] = []
    failures: list[str] = []
    for rollout in rollouts:
        try:
            recovery_job = recovery_by_job[rollout.job_id]
            job = recovery_job.original_job
            raw_path = Path(rollout.raw_execution_artifact_uri)
            if _sha256(raw_path) != rollout.raw_execution_artifact_sha256:
                raise ValueError("recovered raw execution byte hash changed")
            raw = _load_recovery_raw(raw_path)
            byte_pass += 1
            if (
                raw.recovery_execution_binding_id != prepared.recovery_binding.binding_id
                or raw.recovery_job_id != recovery_job.recovery_job_id
                or raw.recovery_role != recovery_job.recovery_role
                or raw.job != job
                or raw.task_package_id != rollout.task_package_id
                or not raw.captured_before_verifier_replay_and_scoring
                or raw.verifier_replay_or_score_fields_present
            ):
                raise ValueError("recovered raw execution identity changed")
            identity_pass += 1
            replay = recovery_job.recovery_role == "zero_generation_replay"
            replay_jobs += replay
            continuation_jobs += not replay
            artifacts: list[BudgetClosedRawProviderCall] = []
            for index, descriptor in enumerate(raw.provider_call_artifacts):
                path = output_dir / descriptor.relative_path
                if (
                    _sha256(path) != descriptor.sha256
                    or path.stat().st_size != descriptor.byte_count
                ):
                    raise ValueError("recovered raw Provider bytes changed")
                artifact = BudgetClosedRawProviderCall.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                expected_binding = (
                    FAILED_EXECUTION_BINDING_ID if replay else prepared.recovery_binding.binding_id
                )
                if (
                    artifact.execution_binding_id != expected_binding
                    or artifact.job_id != job.job_id
                    or artifact.call_index != index
                    or artifact.provider_call_id != rollout.provider_call_ids[index]
                ):
                    raise ValueError("recovered raw Provider identity changed")
                if replay:
                    original_path = _provider_call_path(failed_run_dir, job, index)
                    if path.read_bytes() != original_path.read_bytes():
                        raise ValueError("original Provider bytes changed during copy")
                    original_exact_pass += 1
                artifacts.append(artifact)
            if len(artifacts) != rollout.provider_call_count:
                raise ValueError("recovered Provider Artifact denominator changed")
            provider_pass += 1
            if replay:
                original_provider_count += len(artifacts)
            else:
                continuation_provider_count += len(artifacts)
            audit = raw.provider_budget_audit
            permitted = tuple(item for item in audit.certificates if item.provider_call_permitted)
            attempted_hashes = tuple(_sha256_text(item) for item in raw.attempted_model_prompts)
            if (
                tuple(item.request_hash for item in audit.certificates)
                != attempted_hashes[: len(audit.certificates)]
                or raw.post_terminal_short_circuit_prompts
                != raw.attempted_model_prompts[len(audit.certificates) :]
                or len(permitted) != len(artifacts)
                or tuple(item.request_hash for item in permitted)
                != tuple(_sha256_text(item) for item in raw.provider_request_prompts)
                or tuple(item.certificate_id for item in permitted)
                != tuple(item.certificate_id for item in audit.usage_records)
            ):
                raise ValueError("recovered budget Prompt partition changed")
            budget_pass += 1
            post_terminal_count += len(raw.post_terminal_short_circuit_prompts)
            if all(
                _provider_telemetry_equal_before_host_augmentation(provider, host)
                for provider, host in zip(raw.provider_telemetry, raw.host_telemetry, strict=True)
            ):
                telemetry_pass += 1
            else:
                raise ValueError("recovered Provider and Host telemetry changed")
            if (
                tuple(_sha256_text(item) for item in raw.provider_request_prompts)
                == rollout.actual_prompt_hashes
                and attempted_hashes == rollout.attempted_prompt_hashes
                and tuple(item.provider_call_id for item in artifacts) == rollout.provider_call_ids
            ):
                prompt_pass += 1
            else:
                raise ValueError("recovered Prompt or Provider binding changed")
            provider_ids.extend(rollout.provider_call_ids)
        except Exception as exc:
            failures.append(_raw_lineage_failure(rollout.job_id, exc))
    duplicates = tuple(sorted(key for key, count in Counter(provider_ids).items() if count > 1))
    counts = (
        byte_pass,
        identity_pass,
        provider_pass,
        budget_pass,
        telemetry_pass,
        prompt_pass,
    )
    complete = len(rollouts) == EXPECTED_JOB_COUNT and all(
        item == EXPECTED_JOB_COUNT for item in counts
    )
    partial = all(item == len(rollouts) for item in counts)
    values = {
        "recovery_execution_binding_id": prepared.recovery_binding.binding_id,
        "observed_job_count": len(rollouts),
        "zero_generation_replay_job_count": replay_jobs,
        "continuation_job_count": continuation_jobs,
        "original_provider_artifact_count": original_provider_count,
        "continuation_provider_artifact_count": continuation_provider_count,
        "original_provider_exact_byte_pass_count": original_exact_pass,
        "raw_execution_byte_pass_count": byte_pass,
        "raw_execution_identity_pass_count": identity_pass,
        "provider_capture_pass_count": provider_pass,
        "provider_budget_binding_pass_count": budget_pass,
        "provider_host_telemetry_pass_count": telemetry_pass,
        "prompt_partition_pass_count": prompt_pass,
        "post_terminal_short_circuit_prompt_count": post_terminal_count,
        "provider_call_ids_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "failed_artifacts": tuple(sorted(set(failures))),
        "status": (
            "passed"
            if complete and not duplicates and not failures
            else "partial"
            if partial and not duplicates and not failures
            else "failed"
        ),
    }
    provisional = BudgetRecoveryRawLineageAudit.model_construct(audit_id="pending", **values)
    return BudgetRecoveryRawLineageAudit(
        audit_id=budget_recovery_raw_lineage_audit_id(provisional),
        **values,
    )


def _make_recovery_report(
    *,
    prepared: _RecoveryPrepared,
    discovered_models: Sequence[str],
    rollouts: Sequence[BudgetClosedInstrumentRollout],
    diagnostics: Sequence[BudgetClosedRolloutDiagnostic],
    raw_audit: BudgetRecoveryRawLineageAudit,
) -> BudgetRecoveryReport:
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in rollouts).items()))
    core_terminal_counts = dict(sorted(Counter(item.core_terminal for item in rollouts).items()))
    model_outcomes = sum(
        item.terminal_category
        in {
            "model_valid_trajectory",
            "model_invalid_trajectory",
            "budget_exhausted_no_call",
        }
        for item in rollouts
    )
    valid_count = terminal_counts.get("model_valid_trajectory", 0)
    invalid_count = terminal_counts.get("model_invalid_trajectory", 0)
    no_call_count = terminal_counts.get("budget_exhausted_no_call", 0)
    runtime_failures = terminal_counts.get("runtime_failure", 0)
    instrument_gate_failures = sum(
        not item.failure_channels.instrument_gate_passed for item in rollouts
    )
    report_failures = sum(not item.failure_channels.report_complete for item in rollouts)
    exact_count = sum(item.exact_requested_model for item in rollouts)
    fallback_count = sum(item.fallback_used for item in rollouts)
    total_cost = sum((Decimal(item.estimated_cost_usd) for item in rollouts), Decimal("0"))
    total_tokens = sum(item.provider_total_tokens for item in rollouts)
    total_calls = sum(item.provider_call_count for item in rollouts)
    continuation_calls = total_calls - FAILED_PROVIDER_CALL_COUNT
    continuation_tokens = total_tokens - FAILED_PROVIDER_TOTAL_TOKENS
    continuation_cost = total_cost - Decimal(FAILED_ESTIMATED_COST_USD)
    contract = prepared.original_contract
    resource_budget_passed = bool(
        total_cost <= Decimal(str(contract.maximum_total_estimated_cost_usd))
        and all(
            item.provider_total_tokens
            <= contract.provider_token_budget_contract.maximum_total_tokens
            for item in rollouts
        )
        and all(item.provider_usage_complete for item in rollouts)
        and all(not item.failure_channels.resource_failures for item in rollouts)
    )
    replay_pass_count = sum(item.replay_passed for item in diagnostics)
    recovery_ready = bool(
        len(rollouts) == EXPECTED_JOB_COUNT
        and raw_audit.status == "passed"
        and runtime_failures == 0
        and instrument_gate_failures == 0
        and report_failures == 0
        and all(item.instrument_admitted for item in rollouts)
        and exact_count == EXPECTED_JOB_COUNT
        and fallback_count == 0
        and replay_pass_count == EXPECTED_JOB_COUNT
        and all(item.non_replay_gate_audit_present for item in diagnostics)
        and all(item.complete_verifier_gate_agreement is not False for item in diagnostics)
        and all(item.repair_prompts_action_neutral for item in diagnostics)
        and all(item.failed_observations_action_neutral for item in diagnostics)
        and all(item.authority_contract_in_initial_prompt for item in diagnostics)
        and all(item.terminal_target_in_initial_prompt for item in diagnostics)
        and not any(item.stop_ready_false_positive for item in diagnostics)
        and not any(item.stop_ready_false_negative for item in diagnostics)
        and resource_budget_passed
    )
    status: Literal["passed", "blocked"] = "passed" if recovery_ready else "blocked"
    next_stage = (
        "fresh_capability_and_reachability_protocol_design_only"
        if recovery_ready
        else "budget_closed_recovery_resource_failure_audit_only"
        if not resource_budget_passed
        else "budget_closed_recovery_instrument_failure_audit_only"
    )
    unique_sequences, effective_sequences, maximum_sequence_share = _trace_diversity(diagnostics)
    values = {
        "recovery_run_id": prepared.recovery_binding.recovery_run_id,
        "failed_run_audit_id": prepared.failed_run_audit.audit_id,
        "recovery_contract_id": prepared.recovery_contract.contract_id,
        "recovery_manifest_id": prepared.recovery_manifest.manifest_id,
        "recovery_execution_binding_id": prepared.recovery_binding.binding_id,
        "discovered_models": tuple(discovered_models),
        "terminal_counts": terminal_counts,
        "core_terminal_counts": core_terminal_counts,
        "model_outcome_count": model_outcomes,
        "model_valid_trajectory_count": valid_count,
        "model_invalid_trajectory_count": invalid_count,
        "budget_exhausted_no_call_count": no_call_count,
        "no_call_phase_counts": dict(
            sorted(Counter(item.no_call_phase for item in rollouts if item.no_call_phase).items())
        ),
        "runtime_failure_count": runtime_failures,
        "instrument_gate_failure_count": instrument_gate_failures,
        "report_completeness_failure_count": report_failures,
        "exact_requested_model_count": exact_count,
        "fallback_count": fallback_count,
        "continuation_provider_call_count": continuation_calls,
        "total_provider_call_count": total_calls,
        "continuation_provider_total_tokens": continuation_tokens,
        "total_provider_tokens": total_tokens,
        "continuation_estimated_cost_usd": str(continuation_cost),
        "total_estimated_cost_usd": str(total_cost),
        "post_terminal_short_circuit_prompt_count": (
            raw_audit.post_terminal_short_circuit_prompt_count
        ),
        "raw_lineage_audit": raw_audit,
        "diagnostics": tuple(diagnostics),
        "mechanism_summaries": _mechanism_summaries(diagnostics),
        "replay_pass_count": replay_pass_count,
        "replay_failure_count": len(rollouts) - replay_pass_count,
        "independent_non_replay_audit_count": sum(
            item.non_replay_gate_audit is not None for item in rollouts
        ),
        "completed_shared_score_count": sum(
            item.completed_trajectory_score is not None for item in rollouts
        ),
        "schema_closed_sidecar_pass_count": sum(
            bool(item.completed_trajectory_score and item.completed_trajectory_score.trace_sidecar)
            for item in rollouts
        ),
        "independently_valid_trajectory_count": sum(
            item.independent_validity for item in diagnostics
        ),
        "full_program_lineage_count": sum(
            item.full_program_lineage_completed for item in diagnostics
        ),
        "terminal_node_completion_count": sum(item.terminal_node_completed for item in diagnostics),
        "postterminal_verification_count": sum(
            item.postterminal_verification_completed for item in diagnostics
        ),
        "local_mechanism_success_count": sum(item.local_mechanism_success for item in diagnostics),
        "unique_successful_tool_sequence_count": unique_sequences,
        "effective_successful_tool_sequence_count": effective_sequences,
        "maximum_successful_tool_sequence_share": maximum_sequence_share,
        "resource_budget_passed": resource_budget_passed,
        "recovery_instrument_ready": recovery_ready,
        "status": status,
        "next_permitted_stage": next_stage,
    }
    provisional = BudgetRecoveryReport.model_construct(report_id="pending", **values)
    return BudgetRecoveryReport(report_id=budget_recovery_report_id(provisional), **values)


def run_budget_closed_instrument_recovery(
    *,
    recovery_run_id: str,
    failed_run_dir: Path,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    preflight_dir: Path,
    recovery_preflight_output_dir: Path,
    output_dir: Path,
    package_root: Path,
    workers: int = UNOPENED_CONTINUATION_JOB_COUNT,
    client_factory: Callable[[AgentModelConfig], OpenAICompatibleJsonClient] = (
        OpenAICompatibleJsonClient
    ),
) -> BudgetRecoveryReport:
    prepared = build_budget_recovery_preflight(
        recovery_run_id=recovery_run_id,
        failed_run_dir=failed_run_dir,
        task_source_dir=task_source_dir,
        verifier_qualification_dir=verifier_qualification_dir,
        preflight_dir=preflight_dir,
        output_dir=recovery_preflight_output_dir,
        package_root=package_root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        output_dir / "frozen_recovery_contract.json",
        prepared.recovery_contract.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "frozen_recovery_manifest.json",
        prepared.recovery_manifest.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "recovery_execution_binding.json",
        prepared.recovery_binding.model_dump(mode="json"),
    )
    checkpoint_path = output_dir / "recovery_rollouts.checkpoint.jsonl"
    checkpoint = _load_recovery_checkpoint(path=checkpoint_path, prepared=prepared)
    completed = {item.job_id: item for item in checkpoint}
    record_by_id = {item.record_id: item for item in prepared.records}
    environment_by_id = {item.manifest_id: item for item in prepared.environments}
    binding_by_id = {item.contract_id: item for item in prepared.bindings}
    replay_jobs = tuple(
        item
        for item in prepared.recovery_manifest.jobs
        if item.recovery_role == "zero_generation_replay"
    )
    for recovery_job in replay_jobs:
        job = recovery_job.original_job
        if job.job_id in completed:
            continue
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
    if not all(item.original_job.job_id in completed for item in replay_jobs):
        raise ValueError(
            "budget Recovery did not replay all exposed Jobs before client construction"
        )
    print(
        f"[v26.86] zero-generation replayed {len(replay_jobs)}/{len(replay_jobs)} exposed Jobs",
        flush=True,
    )
    continuation_jobs = tuple(
        item
        for item in prepared.recovery_manifest.jobs
        if item.recovery_role == "unopened_model_continuation"
    )
    raw_only_recovered = 0
    for recovery_job in continuation_jobs:
        job = recovery_job.original_job
        if job.job_id in completed:
            continue
        raw_path = _raw_execution_path(output_dir, job)
        provider_dir = _provider_call_path(output_dir, job, 0).parent
        if raw_path.exists() or (provider_dir.exists() and any(provider_dir.glob("call_*.json"))):
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
            raw_only_recovered += 1
    model_pending = tuple(
        item for item in continuation_jobs if item.original_job.job_id not in completed
    )
    prior_report_path = output_dir / "report.json"
    if model_pending and prior_report_path.exists():
        raise ValueError("completed Recovery report exists while Jobs remain pending")
    client: OpenAICompatibleJsonClient | None = None
    if model_pending:
        client = client_factory(
            AgentModelConfig.model_validate(prepared.original_contract.model_invocation_config)
        )
        discovered_models = tuple(client.discover_models())
        if prepared.original_contract.model_id not in discovered_models:
            raise ValueError("frozen DeepSeek V4-Flash identity is unavailable")
    elif prior_report_path.exists():
        prior_report = BudgetRecoveryReport.model_validate_json(
            prior_report_path.read_text(encoding="utf-8")
        )
        discovered_models = prior_report.discovered_models
    else:
        discovered_models = (prepared.original_contract.model_id,)
    print(
        f"[v26.86] resuming {len(completed)}/{EXPECTED_JOB_COUNT}; "
        f"continuation raw-only recovery {raw_only_recovered}; "
        f"executing {len(model_pending)} unopened Jobs with {workers} workers",
        flush=True,
    )
    if model_pending:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(model_pending)))) as executor:
            future_map = {
                executor.submit(
                    _run_recovery_job,
                    recovery_job=recovery_job,
                    prepared=prepared,
                    failed_run_dir=failed_run_dir,
                    record=record_by_id[recovery_job.original_job.task_record_id],
                    environment=environment_by_id[
                        recovery_job.original_job.environment_manifest_id
                    ],
                    client=client,
                    output_dir=output_dir,
                ): recovery_job
                for recovery_job in model_pending
            }
            for future in as_completed(future_map):
                recovery_job = future_map[future]
                try:
                    rollout = future.result()
                except Exception as exc:
                    _append_jsonl(
                        output_dir / "recovery_runner_failures.checkpoint.jsonl",
                        {
                            "recovery_job_id": recovery_job.recovery_job_id,
                            "job_id": recovery_job.original_job.job_id,
                            "error": _safe_error(exc),
                        },
                    )
                    for queued in future_map:
                        if queued is not future:
                            queued.cancel()
                    raise RuntimeError(
                        "budget Recovery worker failed; raw-only audit is required"
                    ) from exc
                job_id = recovery_job.original_job.job_id
                if job_id in completed:
                    raise ValueError("budget Recovery produced a duplicate Job result")
                completed[job_id] = rollout
                _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
                print(
                    f"[v26.86] completed {len(completed)}/{EXPECTED_JOB_COUNT}",
                    flush=True,
                )
    if len(completed) != EXPECTED_JOB_COUNT:
        raise ValueError("budget Recovery did not complete its frozen denominator")
    ordered = tuple(completed[item.job_id] for item in prepared.original_manifest.jobs)
    diagnostics = tuple(
        _diagnostic(
            rollout=rollout,
            raw=cast(
                Any,
                _load_recovery_raw(Path(rollout.raw_execution_artifact_uri)),
            ),
            record=record_by_id[rollout.task_record_id],
            binding=binding_by_id[rollout.replay_binding_contract_id],
        )
        for rollout in ordered
    )
    raw_audit = _build_recovery_raw_lineage_audit(
        prepared=prepared,
        failed_run_dir=failed_run_dir,
        output_dir=output_dir,
        rollouts=ordered,
    )
    report = _make_recovery_report(
        prepared=prepared,
        discovered_models=discovered_models,
        rollouts=ordered,
        diagnostics=diagnostics,
        raw_audit=raw_audit,
    )
    _write_json_atomic(
        output_dir / "rollout_aggregate.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "rollout_diagnostics.json",
        [item.model_dump(mode="json") for item in diagnostics],
    )
    _write_json_atomic(output_dir / "raw_lineage_audit.json", raw_audit.model_dump(mode="json"))
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def budget_recovery_source_replay_audit_id(
    value: BudgetRecoverySourceReplayAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_recovery_source_replay:",
    )


def budget_failed_job_audit_id(value: BudgetFailedJobAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_failed_job_audit:",
    )


def budget_failed_run_audit_id(value: BudgetFailedRunAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_failed_run_audit:",
    )


def budget_recovery_contract_id(value: BudgetRecoveryContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_budget_recovery_contract:",
    )


def budget_recovery_job_id(value: BudgetRecoveryJob) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"recovery_job_id"}),
        prefix="finance_v26_budget_recovery_job:",
    )


def budget_recovery_manifest_id(value: BudgetRecoveryManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_v26_budget_recovery_manifest:",
    )


def budget_recovery_execution_binding_id(
    value: BudgetRecoveryExecutionBinding,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"binding_id"}),
        prefix="finance_v26_budget_recovery_execution_binding:",
    )


def budget_recovery_preflight_report_id(
    value: BudgetRecoveryPreflightReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_budget_recovery_preflight:",
    )


def budget_recovery_raw_execution_id(value: BudgetRecoveryRawExecution) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="finance_v26_budget_recovery_raw_execution:",
    )


def budget_recovery_raw_lineage_audit_id(
    value: BudgetRecoveryRawLineageAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_recovery_raw_lineage:",
    )


def budget_recovery_report_id(value: BudgetRecoveryReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_budget_recovery_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Freeze or execute the v26.84 budget-closed raw-only Recovery.")
    )
    parser.add_argument("--recovery-run-id", required=True)
    parser.add_argument("--failed-run-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument("--preflight-dir", type=Path, required=True)
    parser.add_argument("--recovery-preflight-output-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--package-root", type=Path, default=Path("."))
    parser.add_argument("--workers", type=int, default=UNOPENED_CONTINUATION_JOB_COUNT)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = build_budget_recovery_preflight(
            recovery_run_id=args.recovery_run_id,
            failed_run_dir=args.failed_run_dir,
            task_source_dir=args.task_source_dir,
            verifier_qualification_dir=args.verifier_qualification_dir,
            preflight_dir=args.preflight_dir,
            output_dir=args.recovery_preflight_output_dir,
            package_root=args.package_root,
        )
        print(
            json.dumps(
                prepared.preflight.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.output_dir is None:
        parser.error("--output-dir is required unless --prepare-only is used")
    report = run_budget_closed_instrument_recovery(
        recovery_run_id=args.recovery_run_id,
        failed_run_dir=args.failed_run_dir,
        task_source_dir=args.task_source_dir,
        verifier_qualification_dir=args.verifier_qualification_dir,
        preflight_dir=args.preflight_dir,
        recovery_preflight_output_dir=args.recovery_preflight_output_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        workers=args.workers,
    )
    print(
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
