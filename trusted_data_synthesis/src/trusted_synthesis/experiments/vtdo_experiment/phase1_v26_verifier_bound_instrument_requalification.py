from __future__ import annotations

import argparse
import hashlib
import json
import math
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import (
    matching_sufficient_support_set,
)
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingTaskAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingReplayResult,
    AuthorityPreservingVerificationReport,
    replay_authority_preserving_observations,
    verify_authority_preserving_agent_result,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    MechanismEstimandOutcome,
    evaluate_mechanism_estimand,
    failure_artifact_mechanism_estimand,
    match_empirical_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_regression import (  # noqa: E501
    _failed_observation_counts,
    _premature_verification,
    _repair_prompt_counts,
    _semantic_progress_projection_passed,
    _stop_decision_readiness,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    ImplementationSourceFile,
    OperationalTaskRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_preflight import (  # noqa: E501
    IMPLEMENTATION_SOURCE_PATHS as PREFLIGHT_IMPLEMENTATION_SOURCE_PATHS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_preflight import (  # noqa: E501
    SourceReplayEntry,
    VerifierBoundInstrumentContract,
    VerifierBoundInstrumentJob,
    VerifierBoundInstrumentJobManifest,
    VerifierBoundInstrumentPreflightReport,
    VerifierBoundSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    V26_VERIFIER_IMPLEMENTATION_VERSION,
    VerifierBoundInstrumentPopulationReport,
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
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation

V26_VERIFIER_BOUND_ONLINE_SOURCE_REPLAY_VERSION = (
    "finance_v26_verifier_bound_online_source_replay.v1"
)
V26_VERIFIER_BOUND_EXECUTION_BINDING_VERSION = (
    "finance_v26_verifier_bound_instrument_execution_binding.v1"
)
V26_VERIFIER_BOUND_PROVIDER_CALL_VERSION = "finance_v26_verifier_bound_raw_provider_call.v1"
V26_VERIFIER_BOUND_RAW_EXECUTION_VERSION = "finance_v26_verifier_bound_raw_execution.v1"
V26_VERIFIER_BOUND_NON_REPLAY_AUDIT_VERSION = "finance_v26_verifier_bound_non_replay_gate_audit.v1"
V26_VERIFIER_BOUND_ROLLOUT_VERSION = "finance_v26_verifier_bound_instrument_rollout.v1"
V26_VERIFIER_BOUND_DIAGNOSTIC_VERSION = "finance_v26_verifier_bound_instrument_diagnostic.v1"
V26_VERIFIER_BOUND_RAW_AUDIT_VERSION = "finance_v26_verifier_bound_instrument_raw_audit.v1"
V26_VERIFIER_BOUND_MECHANISM_SUMMARY_VERSION = (
    "finance_v26_verifier_bound_instrument_mechanism_summary.v1"
)
V26_VERIFIER_BOUND_REQUALIFICATION_REPORT_VERSION = (
    "finance_v26_verifier_bound_instrument_requalification.v1"
)

EXPECTED_PREFLIGHT_REPORT_ID = (
    "finance_v26_verifier_bound_instrument_preflight:"
    "d8c88785a217da74a6772a51a658ff7a0ee40ee77d3a11ebe5454f795721b263"
)
EXPECTED_CONTRACT_ID = (
    "finance_v26_verifier_bound_instrument_contract:"
    "3ecdc9bff3a2a846ede932c28763abbac1c67c345553eacfec69b2de0985afda"
)
EXPECTED_MANIFEST_ID = (
    "finance_v26_verifier_bound_instrument_manifest:"
    "300bc703e726e04bbf22138a01bf8e09302a54906be8e7510ffa012d7256e724"
)
EXPECTED_TASK_SOURCE_REPORT_ID = (
    "finance_v26_verifier_bound_instrument_population_report:"
    "4c810296a03f0491d60b20d6e74061a269e70eb35f8054cfa34eb34ea5547cb0"
)
EXPECTED_VERIFIER_REPORT_ID = (
    "finance_v26_authority_verifier_qualification:"
    "f61be6be022c2c8506e818e3bb9690e71fa316c6820fec69458c7ab7c8fa7bb1"
)
EXPECTED_JOB_COUNT: Literal[32] = 32
DEFAULT_WORKERS = 16

ONLINE_IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted(
        {
            *PREFLIGHT_IMPLEMENTATION_SOURCE_PATHS,
            "src/trusted_synthesis/domains/finance/interactive_agent_runtime.py",
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_empirical_support_pilot.py"
            ),
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_operation_closure_regression.py"
            ),
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_verifier_bound_instrument_requalification.py"
            ),
            "src/trusted_synthesis/runtime/agent/client.py",
            "src/trusted_synthesis/runtime/agent/iterative.py",
            "src/trusted_synthesis/runtime/agent/schema.py",
        }
    )
)

NON_REPLAY_CHECK_IDS = (
    "model_input_noninterference_passed",
    "only_allowed_tools",
    "operation_lineage_complete",
    "evidence_support_complete",
    "verification_complete",
    "answer_projection_complete",
    "citation_complete",
    "mechanism_complete",
    "no_postcompletion_violation",
)

_PRIVATE_PROMPT_FIELD_NAMES = frozenset(
    {
        "expected_operator_id",
        "mechanism_private_state",
        "qualified_replay_contract_id",
        "qualified_verifier_report_id",
        "semantic_source_id",
        "source_program_dag_hash",
        "source_program_node_id",
        "source_verifier_dag_hash",
        "target_program_evidence_ids",
        "task_replay_binding_contract_id",
        "verifier_binding_id",
        "verifier_implementation_id",
    }
)

RolloutTerminal = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "runtime_failure",
    "instrument_failure",
]
ExecutionKind = Literal[
    "completed_trajectory",
    "captured_model_contract_failure",
    "provider_or_runtime_failure",
    "unexpected_execution_failure",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OnlineSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = Field(min_length=1)
    frozen_source_replay_audit_id: str = Field(min_length=1)
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=50)
    replayed_file_count: int = Field(ge=50)
    replay_pass_count: int = Field(ge=50)
    source_replay_before_client_construction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_VERIFIER_BOUND_ONLINE_SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OnlineSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("online source replay paths are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("online source replay denominator changed")
        if self.replay_pass_count != self.replayed_file_count:
            raise ValueError("online source replay is incomplete")
        if self.audit_id != online_source_replay_audit_id(self):
            raise ValueError("online source replay identity is invalid")
        return self


class VerifierBoundInstrumentExecutionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    execution_run_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    task_source_report_id: str = EXPECTED_TASK_SOURCE_REPORT_ID
    verifier_qualification_report_id: str = EXPECTED_VERIFIER_REPORT_ID
    replay_contract_id: str = Field(min_length=1)
    online_source_replay_audit_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    maximum_total_model_tokens_per_rollout: Literal[120000] = 120000
    maximum_total_estimated_cost_usd: float = Field(default=2.0, ge=2.0, le=2.0)
    raw_provider_calls_persisted_before_agent_contract_scoring: Literal[True] = True
    raw_execution_persisted_before_verifier_replay_and_scoring: Literal[True] = True
    raw_only_zero_generation_recovery_required: Literal[True] = True
    compiler_witness_empirical_count: Literal[0] = 0
    historical_diagnostic_candidate_count: Literal[0] = 0
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=16)
    schema_version: str = V26_VERIFIER_BOUND_EXECUTION_BINDING_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> VerifierBoundInstrumentExecutionBinding:
        identities = (
            self.preflight_report_id == EXPECTED_PREFLIGHT_REPORT_ID,
            self.contract_id == EXPECTED_CONTRACT_ID,
            self.job_manifest_id == EXPECTED_MANIFEST_ID,
            self.task_source_report_id == EXPECTED_TASK_SOURCE_REPORT_ID,
            self.verifier_qualification_report_id == EXPECTED_VERIFIER_REPORT_ID,
        )
        if not all(identities):
            raise ValueError("online execution binding crosses frozen identities")
        paths = tuple(item.relative_path for item in self.implementation_source_files)
        if paths != ONLINE_IMPLEMENTATION_SOURCE_PATHS:
            raise ValueError("online execution implementation manifest is incomplete")
        if self.binding_id != verifier_bound_execution_binding_id(self):
            raise ValueError("online execution binding identity is invalid")
        return self


class RawFileDescriptor(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class RawProviderCallArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    contract_id: str = EXPECTED_CONTRACT_ID
    job_id: str = Field(min_length=1)
    call_index: int = Field(ge=0)
    provider_call_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    prompt_sha256: str = Field(min_length=64, max_length=64)
    response_payload: dict[str, Any] | None = None
    telemetry: ModelCallTelemetry
    captured_before_agent_contract_scoring: Literal[True] = True
    schema_version: str = V26_VERIFIER_BOUND_PROVIDER_CALL_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> RawProviderCallArtifact:
        if self.contract_id != EXPECTED_CONTRACT_ID:
            raise ValueError("raw Provider call crosses frozen Contracts")
        if self.prompt_sha256 != _sha256_text(self.prompt):
            raise ValueError("raw Provider Prompt hash changed")
        if self.telemetry.request_hash != self.prompt_sha256:
            raise ValueError("raw Provider Prompt differs from telemetry")
        if self.provider_call_id != provider_call_id(self.job_id, self.call_index, self.telemetry):
            raise ValueError("raw Provider call identity is invalid")
        if self.artifact_id != raw_provider_call_artifact_id(self):
            raise ValueError("raw Provider Artifact identity is invalid")
        return self


class VerifierBoundRawExecutionArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    job: VerifierBoundInstrumentJob
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    execution_kind: ExecutionKind
    provider_call_artifacts: tuple[RawFileDescriptor, ...]
    provider_call_ids: tuple[str, ...]
    provider_telemetry: tuple[ModelCallTelemetry, ...]
    actual_model_request_prompts: tuple[str, ...]
    solve_result: IterativeAgentSolveResult | None = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    recursive_noninterference_passed: bool
    captured_before_verifier_replay_and_scoring: Literal[True] = True
    verifier_replay_or_score_fields_present: Literal[False] = False
    schema_version: str = V26_VERIFIER_BOUND_RAW_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> VerifierBoundRawExecutionArtifact:
        if self.contract_id != EXPECTED_CONTRACT_ID or (
            self.job_manifest_id != EXPECTED_MANIFEST_ID
        ):
            raise ValueError("raw execution crosses frozen inputs")
        if self.job.contract_id != self.contract_id:
            raise ValueError("raw execution Job crosses Contracts")
        if (
            self.task_record_id != self.job.task_record_id
            or self.task_package_id != self.job.task_package_id
            or self.environment_manifest_id != self.job.environment_manifest_id
            or self.replay_binding_contract_id != self.job.replay_binding_contract_id
        ):
            raise ValueError("raw execution loses a frozen Job identity")
        if not (
            len(self.provider_call_artifacts)
            == len(self.provider_call_ids)
            == len(self.provider_telemetry)
            == len(self.actual_model_request_prompts)
        ):
            raise ValueError("raw execution Provider accounting is incomplete")
        expected_calls = tuple(
            provider_call_id(self.job.job_id, index, telemetry)
            for index, telemetry in enumerate(self.provider_telemetry)
        )
        if self.provider_call_ids != expected_calls:
            raise ValueError("raw execution Provider identities changed")
        if tuple(item.request_hash for item in self.provider_telemetry) != tuple(
            _sha256_text(item) for item in self.actual_model_request_prompts
        ):
            raise ValueError("raw execution Prompts differ from Provider telemetry")
        if self.execution_kind == "completed_trajectory":
            if (
                self.solve_result is None
                or self.failure_artifact is not None
                or self.execution_error
            ):
                raise ValueError("completed raw execution has inconsistent payloads")
        elif self.execution_kind == "captured_model_contract_failure":
            if self.failure_artifact is None or self.solve_result is not None:
                raise ValueError("captured model failure lacks its replay Artifact")
        elif self.solve_result is not None or self.failure_artifact is not None:
            raise ValueError("failed raw execution unexpectedly contains a solve result")
        if self.execution_kind != "completed_trajectory" and not self.execution_error:
            raise ValueError("failed raw execution lacks an error attribution")
        if self.artifact_id != raw_execution_artifact_id(self):
            raise ValueError("raw execution Artifact identity is invalid")
        return self


class OnlineNonReplayGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    trajectory_id: str | None = None
    checks: dict[str, bool]
    selected_evidence_ids: tuple[str, ...]
    operation_lineage_evidence_ids: tuple[str, ...]
    verification_support_ids: tuple[str, ...]
    cited_evidence_ids: tuple[str, ...]
    mechanism_event_ids: tuple[str, ...]
    normalized_answer: dict[str, Any]
    matched_program_node_ids: tuple[str, ...]
    complete_solve_result: bool
    verifier_report_non_replay_agreement: bool | None = None
    independently_computed: Literal[True] = True
    schema_version: str = V26_VERIFIER_BOUND_NON_REPLAY_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OnlineNonReplayGateAudit:
        if set(self.checks) != set(NON_REPLAY_CHECK_IDS):
            raise ValueError("online non-Replay Gate vector is incomplete")
        if self.complete_solve_result != (self.trajectory_id is not None):
            raise ValueError("online non-Replay completion status is inconsistent")
        if self.complete_solve_result and self.verifier_report_non_replay_agreement is not True:
            raise ValueError("online non-Replay Gates disagree with Verifier v2")
        if not self.complete_solve_result and self.verifier_report_non_replay_agreement is not None:
            raise ValueError("incomplete model result claims Verifier report agreement")
        if self.audit_id != online_non_replay_gate_audit_id(self):
            raise ValueError("online non-Replay Gate audit identity is invalid")
        return self


class VerifierBoundInstrumentRollout(FrozenModel):
    rollout_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    job_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    terminal_category: RolloutTerminal
    provider_call_ids: tuple[str, ...]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    provider_usage_complete: bool
    estimated_cost_usd: str = Field(min_length=1)
    exact_requested_model: bool
    fallback_used: bool
    actual_prompt_hashes: tuple[str, ...]
    recursive_noninterference_passed: bool
    observation_count: int = Field(ge=0)
    replay_result: AuthorityPreservingReplayResult | None = None
    non_replay_gate_audit: OnlineNonReplayGateAudit | None = None
    verification: AuthorityPreservingVerificationReport | None = None
    mechanism_estimand: MechanismEstimandOutcome
    trajectory_id: str | None = None
    trajectory_content_hash: str | None = None
    decision_trace_hash: str | None = None
    model_generated: bool
    raw_execution_artifact_uri: str = Field(min_length=1)
    raw_execution_artifact_sha256: str = Field(min_length=64, max_length=64)
    raw_provider_call_artifacts: tuple[RawFileDescriptor, ...]
    raw_persisted_before_replay_and_scoring: Literal[True] = True
    state_mapping_permitted: Literal[False] = False
    path_assignment_present: Literal[False] = False
    failure_attribution: dict[str, Any] | None = None
    schema_version: str = V26_VERIFIER_BOUND_ROLLOUT_VERSION

    @model_validator(mode="after")
    def validate_rollout(self) -> VerifierBoundInstrumentRollout:
        if self.contract_id != EXPECTED_CONTRACT_ID or (
            self.job_manifest_id != EXPECTED_MANIFEST_ID
        ):
            raise ValueError("Instrument rollout crosses frozen inputs")
        if self.provider_call_count != len(self.provider_call_ids):
            raise ValueError("Instrument rollout Provider accounting is inconsistent")
        if len(self.raw_provider_call_artifacts) != self.provider_call_count:
            raise ValueError("Instrument rollout lost raw Provider artifacts")
        valid = bool(self.verification and self.verification.valid)
        if valid != (self.terminal_category == "model_valid_trajectory"):
            raise ValueError("Instrument rollout terminal differs from Verifier v2")
        if self.verification is not None:
            if self.replay_result is None or (
                self.verification.replay_id != self.replay_result.replay_id
            ):
                raise ValueError("Instrument rollout crosses Replay results")
            if self.non_replay_gate_audit is None:
                raise ValueError("completed Instrument rollout lacks non-Replay Gates")
        if self.replay_result is not None:
            if self.replay_result.task_package_id != self.task_package_id:
                raise ValueError("Instrument rollout Replay crosses TaskPackages")
            if self.replay_result.observation_count != self.observation_count:
                raise ValueError("Instrument rollout Replay denominator changed")
            if not self.replay_result.passed and self.terminal_category != "instrument_failure":
                raise ValueError("Replay mismatch was misclassified as a model outcome")
        if self.non_replay_gate_audit is not None and (
            self.non_replay_gate_audit.job_id != self.job_id
            or self.non_replay_gate_audit.task_package_id != self.task_package_id
        ):
            raise ValueError("Instrument rollout crosses non-Replay Gate audits")
        if valid and (self.fallback_used or not self.exact_requested_model):
            raise ValueError("wrong-model rollout cannot be independently valid")
        if self.rollout_id != verifier_bound_instrument_rollout_id(self):
            raise ValueError("Verifier-bound Instrument rollout identity is invalid")
        return self


class VerifierBoundInstrumentDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    terminal_category: RolloutTerminal
    exact_requested_model: bool
    fallback_used: bool
    observation_count: int = Field(ge=0)
    replayed_observation_count: int = Field(ge=0)
    replay_failure_ids: tuple[str, ...]
    replay_passed: bool
    non_replay_gate_audit_present: bool
    complete_verifier_gate_agreement: bool | None = None
    required_node_count: int = Field(ge=1)
    completed_node_count: int = Field(ge=0)
    full_program_lineage_completed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    stop_ready: bool
    premature_verification_observed: bool
    postcompletion_violation: bool
    final_answer_before_stop_ready_rejected: bool
    stop_ready_false_positive: bool
    stop_ready_false_negative: bool
    independent_validity: bool
    local_mechanism_success: bool
    public_contract_in_initial_prompt: bool
    decision_prompt_observed: bool
    public_progress_projection_passed: bool
    initial_prompt_private_identity_free: bool
    authority_contract_in_initial_prompt: bool
    terminal_target_in_initial_prompt: bool
    repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    action_bearing_failed_observation_count: int = Field(ge=0)
    repair_prompts_action_neutral: bool
    failed_observations_action_neutral: bool
    successful_tool_sequence: tuple[str, ...]
    state_mapping_eligible: Literal[False] = False
    schema_version: str = V26_VERIFIER_BOUND_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> VerifierBoundInstrumentDiagnostic:
        if self.completed_node_count > self.required_node_count:
            raise ValueError("Instrument diagnostic completed too many Program nodes")
        if self.full_program_lineage_completed != (
            self.completed_node_count == self.required_node_count
        ):
            raise ValueError("Instrument diagnostic Program closure is inconsistent")
        if self.replay_passed != (not self.replay_failure_ids):
            raise ValueError("Instrument diagnostic Replay status is inconsistent")
        if self.replay_passed and self.replayed_observation_count != self.observation_count:
            raise ValueError("Instrument diagnostic Replay did not cover every Observation")
        if self.repair_prompts_action_neutral != (
            self.action_bearing_repair_prompt_count == 0
        ) or self.failed_observations_action_neutral != (
            self.action_bearing_failed_observation_count == 0
        ):
            raise ValueError("Instrument diagnostic repair neutrality is inconsistent")
        if self.diagnostic_id != verifier_bound_instrument_diagnostic_id(self):
            raise ValueError("Verifier-bound Instrument diagnostic identity is invalid")
        return self


class VerifierBoundInstrumentRawAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    expected_rollout_count: Literal[32] = EXPECTED_JOB_COUNT
    observed_rollout_count: int = Field(ge=0, le=32)
    raw_execution_byte_pass_count: int = Field(ge=0, le=32)
    raw_execution_identity_pass_count: int = Field(ge=0, le=32)
    raw_before_scoring_pass_count: int = Field(ge=0, le=32)
    raw_provider_artifact_rollout_pass_count: int = Field(ge=0, le=32)
    raw_provider_call_artifact_count: int = Field(ge=0)
    prompt_telemetry_pass_count: int = Field(ge=0, le=32)
    recursive_noninterference_pass_count: int = Field(ge=0, le=32)
    replay_pass_count: int = Field(ge=0, le=32)
    non_replay_gate_audit_pass_count: int = Field(ge=0, le=32)
    authority_contract_pass_count: int = Field(ge=0, le=32)
    terminal_target_pass_count: int = Field(ge=0, le=32)
    repair_neutrality_pass_count: int = Field(ge=0, le=32)
    stop_readiness_audit_pass_count: int = Field(ge=0, le=32)
    provider_call_ids_unique: bool
    duplicate_provider_call_ids: tuple[str, ...] = ()
    failed_artifacts: tuple[str, ...] = ()
    status: Literal["passed", "partial", "failed"]
    schema_version: str = V26_VERIFIER_BOUND_RAW_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> VerifierBoundInstrumentRawAudit:
        counts = (
            self.raw_execution_byte_pass_count,
            self.raw_execution_identity_pass_count,
            self.raw_before_scoring_pass_count,
            self.raw_provider_artifact_rollout_pass_count,
            self.prompt_telemetry_pass_count,
            self.recursive_noninterference_pass_count,
            self.replay_pass_count,
            self.non_replay_gate_audit_pass_count,
            self.authority_contract_pass_count,
            self.terminal_target_pass_count,
            self.repair_neutrality_pass_count,
            self.stop_readiness_audit_pass_count,
        )
        complete = self.observed_rollout_count == EXPECTED_JOB_COUNT and all(
            item == EXPECTED_JOB_COUNT for item in counts
        )
        partial = all(item == self.observed_rollout_count for item in counts)
        expected = (
            "passed"
            if complete and self.provider_call_ids_unique and not self.failed_artifacts
            else "partial"
            if partial and self.provider_call_ids_unique and not self.failed_artifacts
            else "failed"
        )
        if self.status != expected:
            raise ValueError("Instrument raw audit status is inconsistent")
        if self.audit_id != verifier_bound_instrument_raw_audit_id(self):
            raise ValueError("Verifier-bound Instrument raw audit identity is invalid")
        return self


class InstrumentMechanismSummary(FrozenModel):
    mechanism_id: str = Field(min_length=1)
    attempted_count: Literal[8] = 8
    model_outcome_count: int = Field(ge=0, le=8)
    replay_pass_count: int = Field(ge=0, le=8)
    full_program_lineage_count: int = Field(ge=0, le=8)
    local_mechanism_success_count: int = Field(ge=0, le=8)
    independently_valid_count: int = Field(ge=0, le=8)
    descriptive_only: Literal[True] = True
    schema_version: str = V26_VERIFIER_BOUND_MECHANISM_SUMMARY_VERSION


class VerifierBoundInstrumentRequalificationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    execution_run_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    discovered_models: tuple[str, ...]
    expected_rollout_count: Literal[32] = EXPECTED_JOB_COUNT
    completed_rollout_count: int = Field(ge=0, le=32)
    terminal_counts: dict[str, int]
    model_outcome_count: int = Field(ge=0, le=32)
    runtime_failure_count: int = Field(ge=0, le=32)
    instrument_failure_count: int = Field(ge=0, le=32)
    exact_requested_model_count: int = Field(ge=0, le=32)
    fallback_count: int = Field(ge=0, le=32)
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    raw_integrity_audit: VerifierBoundInstrumentRawAudit
    diagnostics: tuple[VerifierBoundInstrumentDiagnostic, ...]
    mechanism_summaries: tuple[InstrumentMechanismSummary, ...]
    replay_pass_count: int = Field(ge=0, le=32)
    replay_failure_count: int = Field(ge=0, le=32)
    independently_valid_trajectory_count: int = Field(ge=0, le=32)
    full_program_lineage_count: int = Field(ge=0, le=32)
    terminal_node_completion_count: int = Field(ge=0, le=32)
    postterminal_verification_count: int = Field(ge=0, le=32)
    local_mechanism_success_count: int = Field(ge=0, le=32)
    repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    action_bearing_failed_observation_count: int = Field(ge=0)
    stop_ready_false_positive_count: int = Field(ge=0, le=32)
    stop_ready_false_negative_count: int = Field(ge=0, le=32)
    unique_successful_tool_sequence_count: int = Field(ge=0)
    effective_successful_tool_sequence_count: float = Field(ge=0.0)
    maximum_successful_tool_sequence_share: float = Field(ge=0.0, le=1.0)
    resource_budget_passed: bool
    instrument_ready: bool
    compiler_witness_empirical_count: Literal[0] = 0
    historical_diagnostic_candidate_count: Literal[0] = 0
    capability_support_evaluated: Literal[False] = False
    state_reachability_evaluated: Literal[False] = False
    state_mapping_count: Literal[0] = 0
    released_realization_count: Literal[0] = 0
    status: Literal["partial", "passed", "blocked"]
    next_permitted_stage: Literal[
        "frozen_verifier_v2_bound_instrument_resume_only",
        "fresh_capability_and_reachability_protocol_design_only",
        "verifier_bound_online_instrument_failure_audit_only",
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
    schema_version: str = V26_VERIFIER_BOUND_REQUALIFICATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> VerifierBoundInstrumentRequalificationReport:
        if (
            self.preflight_report_id != EXPECTED_PREFLIGHT_REPORT_ID
            or self.contract_id != EXPECTED_CONTRACT_ID
            or self.job_manifest_id != EXPECTED_MANIFEST_ID
        ):
            raise ValueError("Instrument report crosses frozen inputs")
        if sum(self.terminal_counts.values()) != self.completed_rollout_count:
            raise ValueError("Instrument report terminal denominator is incomplete")
        if len(self.diagnostics) != self.completed_rollout_count:
            raise ValueError("Instrument report diagnostic denominator is incomplete")
        if self.replay_failure_count != self.completed_rollout_count - self.replay_pass_count:
            raise ValueError("Instrument report Replay denominator is inconsistent")
        expected_status = (
            "partial"
            if self.completed_rollout_count < EXPECTED_JOB_COUNT
            else "passed"
            if self.instrument_ready
            else "blocked"
        )
        if self.status != expected_status:
            raise ValueError("Instrument report status is inconsistent")
        expected_stage = (
            "frozen_verifier_v2_bound_instrument_resume_only"
            if self.status == "partial"
            else "fresh_capability_and_reachability_protocol_design_only"
            if self.status == "passed"
            else "resource_budget_audit_only"
            if not self.resource_budget_passed
            else "verifier_bound_online_instrument_failure_audit_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Instrument report transition is inconsistent")
        if self.report_id != verifier_bound_requalification_report_id(self):
            raise ValueError("Verifier-bound Instrument report identity is invalid")
        return self


class _PreparedInputs:
    def __init__(
        self,
        *,
        preflight: VerifierBoundInstrumentPreflightReport,
        contract: VerifierBoundInstrumentContract,
        manifest: VerifierBoundInstrumentJobManifest,
        task_report: VerifierBoundInstrumentPopulationReport,
        replay_contract: AuthorityPreservingReplayContract,
        records: tuple[OperationalTaskRecord, ...],
        environments: tuple[AgentToolEnvironmentManifest, ...],
        bindings: tuple[VerifierV2TaskReplayBinding, ...],
        source_audit: OnlineSourceReplayAudit,
        execution_binding: VerifierBoundInstrumentExecutionBinding,
    ) -> None:
        self.preflight = preflight
        self.contract = contract
        self.manifest = manifest
        self.task_report = task_report
        self.replay_contract = replay_contract
        self.records = records
        self.environments = environments
        self.bindings = bindings
        self.source_audit = source_audit
        self.execution_binding = execution_binding


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json_atomic(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"immutable Instrument JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _write_raw_atomic(path: Path, payload: Any) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()
    if path.exists():
        if path.read_bytes() != serialized:
            raise ValueError(f"immutable raw Instrument Artifact changed: {path}")
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(serialized)
    temporary.replace(path)
    return digest


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _load_models(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _implementation_sources(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(relative_path=relative, sha256=_sha256(package_root / relative))
        for relative in ONLINE_IMPLEMENTATION_SOURCE_PATHS
    )


def _relative_to_package(path: Path, package_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(package_root.resolve()))
    except ValueError as exc:
        raise ValueError(f"online source path escapes package root: {path}") from exc


def _validate_detail_files(
    report: VerifierBoundInstrumentPreflightReport,
    preflight_dir: Path,
) -> None:
    for descriptor in report.immutable_detail_files:
        path = preflight_dir / descriptor.relative_path
        if not path.is_file() or _sha256(path) != descriptor.sha256:
            raise ValueError(f"frozen preflight detail changed: {path}")


def _build_online_source_replay(
    *,
    preflight: VerifierBoundInstrumentPreflightReport,
    frozen_source_replay: VerifierBoundSourceReplayAudit,
    preflight_dir: Path,
    package_root: Path,
) -> OnlineSourceReplayAudit:
    expected: dict[str, tuple[str, str]] = {}

    def register(path: Path, expected_sha256: str, source_kind: str) -> None:
        relative = _relative_to_package(path, package_root)
        prior = expected.get(relative)
        value = (expected_sha256, source_kind)
        if prior is not None and prior[0] != expected_sha256:
            raise ValueError(f"online source manifests disagree for {relative}")
        expected[relative] = prior or value

    for item in frozen_source_replay.entries:
        register(package_root / item.relative_path, item.expected_sha256, item.source_kind)
    register(preflight_dir / "report.json", _sha256(preflight_dir / "report.json"), "task_detail")
    for descriptor in preflight.immutable_detail_files:
        register(
            preflight_dir / descriptor.relative_path,
            descriptor.sha256,
            "task_detail",
        )
    for descriptor in _implementation_sources(package_root):
        register(
            package_root / descriptor.relative_path,
            descriptor.sha256,
            "task_implementation",
        )
    entries = []
    for relative, (expected_sha256, source_kind) in sorted(expected.items()):
        path = package_root / relative
        observed = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=relative,
                source_kind=cast(Any, source_kind),
                expected_sha256=expected_sha256,
                observed_sha256=observed,
                byte_count=path.stat().st_size,
            )
        )
    values = {
        "preflight_report_id": preflight.report_id,
        "frozen_source_replay_audit_id": frozen_source_replay.audit_id,
        "entries": tuple(entries),
        "replayed_file_count": len(entries),
        "replay_pass_count": len(entries),
    }
    provisional = OnlineSourceReplayAudit.model_construct(audit_id="pending", **values)
    return OnlineSourceReplayAudit(
        audit_id=online_source_replay_audit_id(provisional),
        **values,
    )


def _validate_online_bindings(
    *,
    contract: VerifierBoundInstrumentContract,
    manifest: VerifierBoundInstrumentJobManifest,
    replay_contract: AuthorityPreservingReplayContract,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    bindings: Sequence[VerifierV2TaskReplayBinding],
    task_audits: Sequence[AuthorityPreservingTaskAudit],
) -> None:
    if manifest.contract_id != contract.contract_id:
        raise ValueError("online Instrument Manifest crosses Contracts")
    record_by_id = {item.record_id: item for item in records}
    environment_by_id = {item.manifest_id: item for item in environments}
    binding_by_id = {item.contract_id: item for item in bindings}
    audit_by_task = {item.task_package_id: item for item in task_audits}
    if not (
        len(record_by_id) == len(environment_by_id) == len(binding_by_id) == len(audit_by_task) == 8
    ):
        raise ValueError("online Instrument task denominator changed")
    if contract.qualified_replay_contract_id != replay_contract.contract_id:
        raise ValueError("online Instrument uses another Replay Contract")
    for job in manifest.jobs:
        record = record_by_id.get(job.task_record_id)
        environment = environment_by_id.get(job.environment_manifest_id)
        binding = binding_by_id.get(job.replay_binding_contract_id)
        if record is None or environment is None or binding is None:
            raise ValueError(f"online Job loses a frozen input: {job.job_id}")
        package = record.task_package
        repair = package.action_neutral_repair_contract
        target = package.terminal_verification_target
        task_audit = audit_by_task.get(package.package_id)
        oracle_binding = package.task.oracle.selection_contract.get(
            "authority_preserving_verifier_v2_binding"
        )
        if (
            package.package_id != job.task_package_id
            or record.environment_manifest_id != environment.manifest_id
            or binding.semantic_source_id != package.semantic_source.semantic_source_id
            or binding.environment_manifest_id != environment.manifest_id
            or binding.environment_manifest_hash != record.environment_manifest_hash
            or package.verifier_binding.verifier_implementation_id != binding.contract_id
            or package.verifier_binding.verifier_version != V26_VERIFIER_IMPLEMENTATION_VERSION
            or repair is None
            or target is None
            or binding.public_operation_contract_id != package.operation_contract.contract_id
            or binding.action_neutral_repair_contract_id != repair.contract_id
            or binding.terminal_verification_target_id != target.target_id
            or not isinstance(oracle_binding, Mapping)
            or oracle_binding.get("task_replay_binding_contract_id") != binding.contract_id
            or task_audit is None
            or task_audit.status != "passed"
            or task_audit.repair_prompt_audit.action_binding_paths
        ):
            raise ValueError(f"online Instrument binding changed: {job.job_id}")


def prepare_verifier_bound_instrument_execution(
    *,
    execution_run_id: str,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> _PreparedInputs:
    preflight = VerifierBoundInstrumentPreflightReport.model_validate_json(
        (preflight_dir / "report.json").read_text(encoding="utf-8")
    )
    contract = VerifierBoundInstrumentContract.model_validate_json(
        (preflight_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = VerifierBoundInstrumentJobManifest.model_validate_json(
        (preflight_dir / "job_manifest.json").read_text(encoding="utf-8")
    )
    frozen_source_replay = VerifierBoundSourceReplayAudit.model_validate_json(
        (preflight_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    if (
        preflight.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or contract.contract_id != EXPECTED_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or preflight.contract_id != contract.contract_id
        or preflight.job_manifest_id != manifest.manifest_id
        or preflight.source_replay_audit_id != frozen_source_replay.audit_id
    ):
        raise ValueError("online execution did not receive the authoritative v26.77 preflight")
    _validate_detail_files(preflight, preflight_dir)

    task_report = VerifierBoundInstrumentPopulationReport.model_validate_json(
        (task_source_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        task_report.report_id != EXPECTED_TASK_SOURCE_REPORT_ID
        or task_report.report_id != contract.task_source_report_id
        or _sha256(task_source_dir / "report.json") != contract.task_source_report_sha256
    ):
        raise ValueError("online execution received another v26.76 task source")
    qualification_payload = json.loads(
        (verifier_qualification_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        qualification_payload.get("report_id") != EXPECTED_VERIFIER_REPORT_ID
        or qualification_payload.get("report_id") != contract.verifier_qualification_report_id
        or _sha256(verifier_qualification_dir / "report.json")
        != contract.verifier_qualification_report_sha256
    ):
        raise ValueError("online execution received another Verifier qualification")
    replay_contract = AuthorityPreservingReplayContract.model_validate_json(
        (verifier_qualification_dir / "replay_contract.json").read_text(encoding="utf-8")
    )

    records = cast(
        tuple[OperationalTaskRecord, ...],
        _load_models(task_source_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    environments = cast(
        tuple[AgentToolEnvironmentManifest, ...],
        _load_models(
            task_source_dir / "tool_environment_manifests.json",
            AgentToolEnvironmentManifest,
        ),
    )
    bindings = cast(
        tuple[VerifierV2TaskReplayBinding, ...],
        _load_models(
            task_source_dir / "verifier_v2_replay_bindings.json",
            VerifierV2TaskReplayBinding,
        ),
    )
    task_audits = cast(
        tuple[AuthorityPreservingTaskAudit, ...],
        _load_models(
            task_source_dir / "authority_preserving_task_audits.json",
            AuthorityPreservingTaskAudit,
        ),
    )
    _validate_online_bindings(
        contract=contract,
        manifest=manifest,
        replay_contract=replay_contract,
        records=records,
        environments=environments,
        bindings=bindings,
        task_audits=task_audits,
    )
    source_audit = _build_online_source_replay(
        preflight=preflight,
        frozen_source_replay=frozen_source_replay,
        preflight_dir=preflight_dir,
        package_root=package_root,
    )
    binding_values = {
        "execution_run_id": execution_run_id,
        "replay_contract_id": replay_contract.contract_id,
        "online_source_replay_audit_id": source_audit.audit_id,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional_binding = VerifierBoundInstrumentExecutionBinding.model_construct(
        binding_id="pending", **binding_values
    )
    execution_binding = VerifierBoundInstrumentExecutionBinding(
        binding_id=verifier_bound_execution_binding_id(provisional_binding),
        **binding_values,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        output_dir / "online_source_replay_audit.json",
        source_audit.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "execution_binding.json",
        execution_binding.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "frozen_execution_contract.json",
        contract.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "frozen_job_manifest.json",
        manifest.model_dump(mode="json"),
    )
    return _PreparedInputs(
        preflight=preflight,
        contract=contract,
        manifest=manifest,
        task_report=task_report,
        replay_contract=replay_contract,
        records=records,
        environments=environments,
        bindings=bindings,
        source_audit=source_audit,
        execution_binding=execution_binding,
    )


def provider_call_id(
    job_id: str,
    call_index: int,
    telemetry: ModelCallTelemetry,
) -> str:
    return canonical_hash(
        {
            "job_id": job_id,
            "call_index": call_index,
            "request_hash": telemetry.request_hash,
            "response_hash": telemetry.response_hash,
            "model_selected": telemetry.model_selected,
            "http_status": telemetry.http_status,
        },
        prefix="finance_v26_verifier_bound_provider_call:",
    )


def _provider_call_path(
    output_dir: Path,
    job: VerifierBoundInstrumentJob,
    call_index: int,
) -> Path:
    task_hash = hashlib.sha256(job.task_package_id.encode("utf-8")).hexdigest()[:16]
    return (
        output_dir
        / "raw_provider_calls"
        / task_hash
        / f"replicate_{job.replicate_index}"
        / f"call_{call_index:04d}.json"
    )


def _raw_execution_path(output_dir: Path, job: VerifierBoundInstrumentJob) -> Path:
    task_hash = hashlib.sha256(job.task_package_id.encode("utf-8")).hexdigest()[:16]
    return output_dir / "raw_execution" / task_hash / f"replicate_{job.replicate_index}.json"


class _RawFirstJournalClient:
    """Persist each model payload before Agent contract validation or experiment scoring."""

    def __init__(
        self,
        delegate: OpenAICompatibleJsonClient,
        *,
        execution_binding: VerifierBoundInstrumentExecutionBinding,
        job: VerifierBoundInstrumentJob,
        output_dir: Path,
    ) -> None:
        self._delegate = delegate
        self._execution_binding = execution_binding
        self._job = job
        self._output_dir = output_dir
        self.telemetry: list[ModelCallTelemetry] = []
        self.prompts: list[str] = []
        self.descriptors: list[RawFileDescriptor] = []

    @property
    def config(self) -> AgentModelConfig:
        return self._delegate.config

    def _record(
        self,
        prompt: str,
        response_payload: dict[str, Any] | None,
        telemetry: ModelCallTelemetry,
    ) -> None:
        call_index = len(self.telemetry)
        values = {
            "execution_binding_id": self._execution_binding.binding_id,
            "job_id": self._job.job_id,
            "call_index": call_index,
            "provider_call_id": provider_call_id(self._job.job_id, call_index, telemetry),
            "prompt": prompt,
            "prompt_sha256": _sha256_text(prompt),
            "response_payload": response_payload,
            "telemetry": telemetry,
        }
        provisional = RawProviderCallArtifact.model_construct(artifact_id="pending", **values)
        artifact = RawProviderCallArtifact(
            artifact_id=raw_provider_call_artifact_id(provisional),
            **values,
        )
        path = _provider_call_path(self._output_dir, self._job, call_index)
        digest = _write_raw_atomic(path, artifact.model_dump(mode="json"))
        self.telemetry.append(telemetry)
        self.prompts.append(prompt)
        self.descriptors.append(
            RawFileDescriptor(
                relative_path=str(path.relative_to(self._output_dir)),
                sha256=digest,
                byte_count=path.stat().st_size,
            )
        )

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        try:
            payload, telemetry = self._delegate.complete_json(prompt)
        except LLMClientError as exc:
            for telemetry in exc.telemetry:
                self._record(prompt, None, telemetry)
            raise
        self._record(prompt, payload, telemetry)
        return payload, telemetry


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}:{str(exc)[:1200]}"


def _recursive_noninterference(
    *,
    result: IterativeAgentSolveResult | None,
    failure_artifact: IterativeAgentFailureArtifact | None,
    prompts: Sequence[str],
) -> bool:
    if result is not None:
        return len(prompts) == len(
            result.audit.model_request_prompt_noninterference_attestation_hashes
        )
    if failure_artifact is not None:
        return len(prompts) == len(
            failure_artifact.model_request_prompt_noninterference_attestation_hashes
        )
    return not prompts


def _load_raw_execution(path: Path) -> VerifierBoundRawExecutionArtifact:
    raw = path.read_bytes()
    payload = json.loads(raw)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError(f"raw execution Artifact is not canonical JSON: {path}")
    return VerifierBoundRawExecutionArtifact.model_validate(payload)


def _execute_and_persist_raw(
    *,
    job: VerifierBoundInstrumentJob,
    contract: VerifierBoundInstrumentContract,
    execution_binding: VerifierBoundInstrumentExecutionBinding,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    client: OpenAICompatibleJsonClient | None,
    output_dir: Path,
) -> VerifierBoundRawExecutionArtifact:
    raw_path = _raw_execution_path(output_dir, job)
    if raw_path.exists():
        artifact = _load_raw_execution(raw_path)
        if artifact.execution_binding_id != execution_binding.binding_id or artifact.job != job:
            raise ValueError("recoverable raw execution crosses frozen identities")
        return artifact
    provider_directory = _provider_call_path(output_dir, job, 0).parent
    if provider_directory.exists() and any(provider_directory.glob("call_*.json")):
        raise ValueError(
            "orphan raw Provider calls exist without a raw execution Artifact; "
            "automatic model retry is forbidden"
        )
    if client is None:
        raise ValueError("pending Instrument Job has no model client")
    if record.task_package.package_id != job.task_package_id:
        raise ValueError("online Job and TaskPackage identities differ")
    if record.environment_manifest_id != environment.manifest_id or (
        environment.manifest_id != job.environment_manifest_id
    ):
        raise ValueError("online Job environment identity changed")
    observed_environment_hash = canonical_hash(
        environment,
        prefix="finance_v26_executable_environment:",
    )
    if observed_environment_hash != record.environment_manifest_hash or (
        observed_environment_hash
        != record.task_package.public_runtime_contract.environment_manifest_hash
    ):
        raise ValueError("online Job environment bytes changed")
    recovery = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    runtime = FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery,
    )
    recording_client = _RawFirstJournalClient(
        client,
        execution_binding=execution_binding,
        job=job,
        output_dir=output_dir,
    )
    result: IterativeAgentSolveResult | None = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    execution_kind: ExecutionKind
    try:
        result = IterativeAgentSolver(
            recording_client,
            mode="autonomous_agent",
            maximum_total_tokens=contract.maximum_total_model_tokens_per_rollout,
            protocol_profile=IterativeAgentProtocolProfile(),
        ).solve_with_audit(record.task_package.task.public, runtime)
        execution_kind = "completed_trajectory"
    except LLMClientError as exc:
        failure_artifact = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact)
            else None
        )
        execution_error = _safe_error(exc)
        execution_kind = (
            "captured_model_contract_failure"
            if failure_artifact is not None
            else "provider_or_runtime_failure"
        )
    except Exception as exc:
        execution_error = _safe_error(exc)
        execution_kind = "unexpected_execution_failure"

    telemetry = tuple(recording_client.telemetry)
    prompts = tuple(recording_client.prompts)
    if result is not None and (
        telemetry != result.audit.telemetry or prompts != result.audit.model_request_prompts
    ):
        raise ValueError("raw-first Provider journal differs from completed Agent audit")
    if failure_artifact is not None and (
        telemetry != failure_artifact.telemetry or prompts != failure_artifact.model_request_prompts
    ):
        raise ValueError("raw-first Provider journal differs from failure Artifact")
    values = {
        "execution_binding_id": execution_binding.binding_id,
        "job_manifest_id": EXPECTED_MANIFEST_ID,
        "job": job,
        "task_record_id": record.record_id,
        "task_package_id": record.task_package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "replay_binding_contract_id": job.replay_binding_contract_id,
        "execution_kind": execution_kind,
        "provider_call_artifacts": tuple(recording_client.descriptors),
        "provider_call_ids": tuple(
            provider_call_id(job.job_id, index, item) for index, item in enumerate(telemetry)
        ),
        "provider_telemetry": telemetry,
        "actual_model_request_prompts": prompts,
        "solve_result": result,
        "failure_artifact": failure_artifact,
        "execution_error": execution_error,
        "recursive_noninterference_passed": _recursive_noninterference(
            result=result,
            failure_artifact=failure_artifact,
            prompts=prompts,
        ),
    }
    provisional = VerifierBoundRawExecutionArtifact.model_construct(artifact_id="pending", **values)
    artifact = VerifierBoundRawExecutionArtifact(
        artifact_id=raw_execution_artifact_id(provisional),
        **values,
    )
    _write_raw_atomic(raw_path, artifact.model_dump(mode="json"))
    return artifact


def _replace_runtime_references(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, Mapping):
        return {key: _replace_runtime_references(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime_references(item, mapping) for item in value]
    return value


def _project_answer(value: Mapping[str, Any], projection: Mapping[str, str]) -> dict[str, Any]:
    output = dict(value)
    for field in ("higher_ref", "selected_ref"):
        reference = output.get(field)
        if reference is not None and str(reference) in projection:
            output[field] = projection[str(reference)]
    return output


def _answer_and_citations(
    result: IterativeAgentSolveResult | None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    if result is None:
        return {}, ()
    final = result.trajectory.final_answer
    answer = final.get("result") if isinstance(final, Mapping) else None
    citations = final.get("citations") if isinstance(final, Mapping) else None
    if not isinstance(answer, Mapping) or not isinstance(citations, list):
        return {}, ()
    evidence_ids = tuple(
        str(item["evidence_id"])
        for item in citations
        if isinstance(item, Mapping) and item.get("evidence_id")
    )
    return dict(answer), evidence_ids


def _observations_from_raw(
    raw: VerifierBoundRawExecutionArtifact,
) -> tuple[AgentToolObservation, ...]:
    if raw.solve_result is not None:
        return raw.solve_result.observations
    if raw.failure_artifact is not None:
        return raw.failure_artifact.observations
    return ()


def _compute_non_replay_gate_audit(
    *,
    execution_binding: VerifierBoundInstrumentExecutionBinding,
    job: VerifierBoundInstrumentJob,
    record: OperationalTaskRecord,
    raw: VerifierBoundRawExecutionArtifact,
    replay: AuthorityPreservingReplayResult,
    mechanism: MechanismEstimandOutcome,
    verification: AuthorityPreservingVerificationReport | None,
) -> OnlineNonReplayGateAudit:
    result = raw.solve_result
    observations = _observations_from_raw(raw)
    program_complete, matched_nodes, runtime_to_node, operation_lineage = match_empirical_program(
        record, observations
    )
    answer, citations = _answer_and_citations(result)
    normalized_answer = _project_answer(
        cast(dict[str, Any], _replace_runtime_references(answer, runtime_to_node)),
        record.answer_projection,
    )
    lattice = record.task_package.evidence_support_lattice
    selected_support = matching_sufficient_support_set(lattice, replay.selected_evidence_ids)
    citation_support = matching_sufficient_support_set(lattice, citations)
    verification_support = tuple(
        sorted(
            {
                str(evidence_id)
                for item in observations
                if item.call.tool_id == "cross_check_evidence"
                and item.status == "succeeded"
                and item.result.get("verified") is True
                for evidence_id in item.result.get("support") or ()
            }
        )
    )
    first_verified = next(
        (
            index
            for index, item in enumerate(observations)
            if item.call.tool_id == "cross_check_evidence"
            and item.status == "succeeded"
            and item.result.get("verified") is True
        ),
        None,
    )
    no_postcompletion = first_verified is None or first_verified == len(observations) - 1
    necessary = set(lattice.necessary_evidence_ids)
    checks = {
        "model_input_noninterference_passed": raw.recursive_noninterference_passed,
        "only_allowed_tools": {item.call.tool_id for item in observations}
        <= set(record.task_package.tool_closure.allowed_tool_ids),
        "operation_lineage_complete": program_complete and necessary <= set(operation_lineage),
        "evidence_support_complete": selected_support is not None,
        "verification_complete": necessary <= set(verification_support),
        "answer_projection_complete": normalized_answer == record.projected_expected_output,
        "citation_complete": citation_support is not None,
        "mechanism_complete": mechanism.success,
        "no_postcompletion_violation": no_postcompletion,
    }
    agreement = None
    if verification is not None:
        agreement = checks == {
            key: value
            for key, value in verification.checks.items()
            if key != "runtime_replay_passed"
        }
    values = {
        "execution_binding_id": execution_binding.binding_id,
        "job_id": job.job_id,
        "task_package_id": record.task_package.package_id,
        "trajectory_id": result.trajectory.trajectory_id if result is not None else None,
        "checks": checks,
        "selected_evidence_ids": replay.selected_evidence_ids,
        "operation_lineage_evidence_ids": operation_lineage,
        "verification_support_ids": verification_support,
        "cited_evidence_ids": citations,
        "mechanism_event_ids": mechanism.observed_event_ids,
        "normalized_answer": normalized_answer,
        "matched_program_node_ids": matched_nodes,
        "complete_solve_result": result is not None,
        "verifier_report_non_replay_agreement": agreement,
    }
    provisional = OnlineNonReplayGateAudit.model_construct(audit_id="pending", **values)
    return OnlineNonReplayGateAudit(
        audit_id=online_non_replay_gate_audit_id(provisional),
        **values,
    )


def _mechanism_outcome(
    record: OperationalTaskRecord,
    raw: VerifierBoundRawExecutionArtifact,
) -> MechanismEstimandOutcome:
    if raw.solve_result is not None:
        return evaluate_mechanism_estimand(
            record,
            raw.solve_result.observations,
            stopped_by_model=raw.solve_result.audit.stopped_by_model,
        )
    if raw.failure_artifact is not None:
        return failure_artifact_mechanism_estimand(record, raw.failure_artifact)
    return evaluate_mechanism_estimand(record, (), stopped_by_model=False)


def _telemetry_summary(
    contract: VerifierBoundInstrumentContract,
    telemetry: Sequence[ModelCallTelemetry],
) -> tuple[int, bool, Decimal, bool, bool]:
    total_tokens = sum(item.total_tokens or 0 for item in telemetry)
    usage_complete = bool(telemetry) and all(item.total_tokens is not None for item in telemetry)
    estimated_cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    exact_model = bool(telemetry) and all(
        item.model_selected == contract.model_id
        and item.model_requested == contract.model_id
        and item.http_success
        for item in telemetry
    )
    fallback_used = any(item.fallback_used for item in telemetry)
    return total_tokens, usage_complete, estimated_cost, exact_model, fallback_used


def _raw_reference(
    output_dir: Path,
    job: VerifierBoundInstrumentJob,
) -> tuple[str, str]:
    path = _raw_execution_path(output_dir, job)
    return str(path.resolve()), _sha256(path)


def _score_raw_execution(
    *,
    job: VerifierBoundInstrumentJob,
    contract: VerifierBoundInstrumentContract,
    execution_binding: VerifierBoundInstrumentExecutionBinding,
    replay_contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    raw: VerifierBoundRawExecutionArtifact,
    output_dir: Path,
) -> VerifierBoundInstrumentRollout:
    observations = _observations_from_raw(raw)
    replay = replay_authority_preserving_observations(
        replay_contract,
        record,
        environment,
        observations,
    )
    verification = (
        verify_authority_preserving_agent_result(
            replay_contract,
            record,
            environment,
            raw.solve_result,
        )
        if raw.solve_result is not None
        else None
    )
    if verification is not None and verification.replay_id != replay.replay_id:
        raise ValueError("online Verifier v2 returned another Replay result")
    mechanism = _mechanism_outcome(record, raw)
    non_replay = _compute_non_replay_gate_audit(
        execution_binding=execution_binding,
        job=job,
        record=record,
        raw=raw,
        replay=replay,
        mechanism=mechanism,
        verification=verification,
    )
    if not replay.passed:
        terminal: RolloutTerminal = "instrument_failure"
        failure_attribution: dict[str, Any] | None = {
            "category": "runtime_verifier_replay_mismatch",
            "failure_ids": list(replay.failure_ids),
        }
    elif raw.solve_result is not None:
        terminal = (
            "model_valid_trajectory"
            if verification is not None and verification.valid
            else "model_invalid_trajectory"
        )
        failure_attribution = (
            None
            if terminal == "model_valid_trajectory"
            else {
                "category": "independent_verification_failed",
                "earliest_failure_stage": (
                    verification.earliest_failure_stage if verification is not None else None
                ),
                "failed_check_ids": (
                    sorted(key for key, passed in verification.checks.items() if not passed)
                    if verification is not None
                    else []
                ),
            }
        )
    elif (
        raw.failure_artifact is not None
        and raw.provider_telemetry
        and all(item.http_success for item in raw.provider_telemetry)
    ):
        terminal = "model_invalid_trajectory"
        failure_attribution = {
            "category": "model_contract_failure",
            "reason": raw.execution_error,
        }
    elif raw.execution_kind == "unexpected_execution_failure":
        terminal = "instrument_failure"
        failure_attribution = {
            "category": "instrument_failure",
            "reason": raw.execution_error,
        }
    else:
        terminal = "runtime_failure"
        failure_attribution = {
            "category": "runtime_failure",
            "reason": raw.execution_error,
        }
    total_tokens, usage_complete, estimated_cost, exact_model, fallback_used = _telemetry_summary(
        contract, raw.provider_telemetry
    )
    trajectory = raw.solve_result.trajectory if raw.solve_result is not None else None
    raw_uri, raw_sha = _raw_reference(output_dir, job)
    values = {
        "execution_binding_id": execution_binding.binding_id,
        "job_manifest_id": EXPECTED_MANIFEST_ID,
        "job_id": job.job_id,
        "task_record_id": job.task_record_id,
        "task_package_id": job.task_package_id,
        "environment_manifest_id": job.environment_manifest_id,
        "replay_binding_contract_id": job.replay_binding_contract_id,
        "mechanism_id": job.mechanism_id,
        "replicate_index": job.replicate_index,
        "terminal_category": terminal,
        "provider_call_ids": raw.provider_call_ids,
        "provider_call_count": len(raw.provider_call_ids),
        "provider_total_tokens": total_tokens,
        "provider_usage_complete": usage_complete,
        "estimated_cost_usd": str(estimated_cost),
        "exact_requested_model": exact_model,
        "fallback_used": fallback_used,
        "actual_prompt_hashes": tuple(
            _sha256_text(item) for item in raw.actual_model_request_prompts
        ),
        "recursive_noninterference_passed": raw.recursive_noninterference_passed,
        "observation_count": len(observations),
        "replay_result": replay,
        "non_replay_gate_audit": non_replay,
        "verification": verification,
        "mechanism_estimand": mechanism,
        "trajectory_id": trajectory.trajectory_id if trajectory is not None else None,
        "trajectory_content_hash": (
            canonical_hash(
                trajectory.model_dump(mode="json", exclude={"trajectory_id"}),
                prefix="finance_v26_verifier_bound_trajectory_content:",
            )
            if trajectory is not None
            else None
        ),
        "decision_trace_hash": (
            canonical_hash(
                tuple((step.action, step.status, step.observation_id) for step in trajectory.steps),
                prefix="finance_v26_verifier_bound_decision_trace:",
            )
            if trajectory is not None
            else None
        ),
        "model_generated": bool(raw.provider_call_ids) and terminal.startswith("model_"),
        "raw_execution_artifact_uri": raw_uri,
        "raw_execution_artifact_sha256": raw_sha,
        "raw_provider_call_artifacts": raw.provider_call_artifacts,
        "failure_attribution": failure_attribution,
    }
    provisional = VerifierBoundInstrumentRollout.model_construct(rollout_id="pending", **values)
    return VerifierBoundInstrumentRollout(
        rollout_id=verifier_bound_instrument_rollout_id(provisional),
        **values,
    )


def _score_with_failure_capture(
    *,
    job: VerifierBoundInstrumentJob,
    contract: VerifierBoundInstrumentContract,
    execution_binding: VerifierBoundInstrumentExecutionBinding,
    replay_contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    raw: VerifierBoundRawExecutionArtifact,
    output_dir: Path,
) -> VerifierBoundInstrumentRollout:
    try:
        return _score_raw_execution(
            job=job,
            contract=contract,
            execution_binding=execution_binding,
            replay_contract=replay_contract,
            record=record,
            environment=environment,
            raw=raw,
            output_dir=output_dir,
        )
    except Exception as exc:
        observations = _observations_from_raw(raw)
        try:
            replay: AuthorityPreservingReplayResult | None = (
                replay_authority_preserving_observations(
                    replay_contract,
                    record,
                    environment,
                    observations,
                )
            )
        except Exception:
            replay = None
        mechanism = _mechanism_outcome(record, raw)
        total_tokens, usage_complete, estimated_cost, exact_model, fallback_used = (
            _telemetry_summary(contract, raw.provider_telemetry)
        )
        trajectory = raw.solve_result.trajectory if raw.solve_result is not None else None
        raw_uri, raw_sha = _raw_reference(output_dir, job)
        values = {
            "execution_binding_id": execution_binding.binding_id,
            "job_manifest_id": EXPECTED_MANIFEST_ID,
            "job_id": job.job_id,
            "task_record_id": job.task_record_id,
            "task_package_id": job.task_package_id,
            "environment_manifest_id": job.environment_manifest_id,
            "replay_binding_contract_id": job.replay_binding_contract_id,
            "mechanism_id": job.mechanism_id,
            "replicate_index": job.replicate_index,
            "terminal_category": "instrument_failure",
            "provider_call_ids": raw.provider_call_ids,
            "provider_call_count": len(raw.provider_call_ids),
            "provider_total_tokens": total_tokens,
            "provider_usage_complete": usage_complete,
            "estimated_cost_usd": str(estimated_cost),
            "exact_requested_model": exact_model,
            "fallback_used": fallback_used,
            "actual_prompt_hashes": tuple(
                _sha256_text(item) for item in raw.actual_model_request_prompts
            ),
            "recursive_noninterference_passed": raw.recursive_noninterference_passed,
            "observation_count": len(observations),
            "replay_result": replay,
            "non_replay_gate_audit": None,
            "verification": None,
            "mechanism_estimand": mechanism,
            "trajectory_id": trajectory.trajectory_id if trajectory is not None else None,
            "trajectory_content_hash": (
                canonical_hash(
                    trajectory.model_dump(mode="json", exclude={"trajectory_id"}),
                    prefix="finance_v26_verifier_bound_trajectory_content:",
                )
                if trajectory is not None
                else None
            ),
            "decision_trace_hash": None,
            "model_generated": bool(raw.provider_call_ids),
            "raw_execution_artifact_uri": raw_uri,
            "raw_execution_artifact_sha256": raw_sha,
            "raw_provider_call_artifacts": raw.provider_call_artifacts,
            "failure_attribution": {
                "category": "online_scoring_instrument_failure",
                "reason": _safe_error(exc),
            },
        }
        provisional = VerifierBoundInstrumentRollout.model_construct(rollout_id="pending", **values)
        return VerifierBoundInstrumentRollout(
            rollout_id=verifier_bound_instrument_rollout_id(provisional),
            **values,
        )


def _raw_stop_payload(raw: VerifierBoundRawExecutionArtifact) -> dict[str, Any]:
    return {
        "trajectory": (
            raw.solve_result.trajectory.model_dump(mode="json")
            if raw.solve_result is not None
            else None
        ),
        "failure_artifact": (
            raw.failure_artifact.model_dump(mode="json")
            if raw.failure_artifact is not None
            else None
        ),
    }


def _diagnostic(
    *,
    rollout: VerifierBoundInstrumentRollout,
    raw: VerifierBoundRawExecutionArtifact,
    record: OperationalTaskRecord,
    binding: VerifierV2TaskReplayBinding,
) -> VerifierBoundInstrumentDiagnostic:
    observations = _observations_from_raw(raw)
    progress = public_operation_progress(record.task_package.task.public, observations)
    if progress is None:
        raise ValueError("online Instrument lost its public Operation contract")
    prompts = raw.actual_model_request_prompts
    initial = prompts[0] if prompts else ""
    decision_prompts = tuple(item for item in prompts if '"operation_execution_progress"' in item)
    repair_prompt_count, action_bearing_repair_prompt_count = _repair_prompt_counts(prompts)
    failed_observation_count, action_bearing_failed_observation_count = _failed_observation_counts(
        observations
    )
    stop_rows = _stop_decision_readiness(record, _raw_stop_payload(raw))
    early_stop_rejected = any(
        rejected and not stop_ready for _, rejected, stop_ready, _ in stop_rows
    )
    false_positive = any(accepted and not stop_ready for accepted, _, stop_ready, _ in stop_rows)
    false_negative = any(
        stop_gate_rejection and stop_ready for _, _, stop_ready, stop_gate_rejection in stop_rows
    )
    package = record.task_package
    private_values = (
        *record.target_program_evidence_ids,
        package.semantic_source.semantic_source_id,
        package.verifier_binding.binding_id,
        package.verifier_binding.source_program_dag_hash,
        package.verifier_binding.source_verifier_dag_hash,
        binding.contract_id,
        binding.qualified_replay_contract_id,
        binding.qualified_verifier_report_id,
    )
    replay = rollout.replay_result
    non_replay = rollout.non_replay_gate_audit
    values = {
        "rollout_id": rollout.rollout_id,
        "job_id": rollout.job_id,
        "task_package_id": rollout.task_package_id,
        "mechanism_id": rollout.mechanism_id,
        "replicate_index": rollout.replicate_index,
        "terminal_category": rollout.terminal_category,
        "exact_requested_model": rollout.exact_requested_model,
        "fallback_used": rollout.fallback_used,
        "observation_count": len(observations),
        "replayed_observation_count": (
            replay.replayed_observation_count if replay is not None else 0
        ),
        "replay_failure_ids": (
            replay.failure_ids if replay is not None else ("replay_not_computed",)
        ),
        "replay_passed": bool(replay and replay.passed),
        "non_replay_gate_audit_present": non_replay is not None,
        "complete_verifier_gate_agreement": (
            non_replay.verifier_report_non_replay_agreement
            if non_replay is not None and non_replay.complete_solve_result
            else None
        ),
        "required_node_count": len(package.stop_readiness_contract.required_node_ids),
        "completed_node_count": len(progress["completed_node_ids"]),
        "full_program_lineage_completed": bool(progress["all_steps_completed"]),
        "terminal_node_completed": bool(progress["terminal_node_completed"]),
        "postterminal_verification_completed": bool(
            progress["verification_after_terminal_completed"]
        ),
        "stop_ready": bool(progress["stop_ready"]),
        "premature_verification_observed": _premature_verification(record, observations),
        "postcompletion_violation": bool(progress["postcompletion_violation"]),
        "final_answer_before_stop_ready_rejected": early_stop_rejected,
        "stop_ready_false_positive": false_positive,
        "stop_ready_false_negative": false_negative,
        "independent_validity": bool(rollout.verification and rollout.verification.valid),
        "local_mechanism_success": rollout.mechanism_estimand.success,
        "public_contract_in_initial_prompt": "public_operation_execution_contract" in initial,
        "decision_prompt_observed": bool(decision_prompts),
        "public_progress_projection_passed": all(
            _semantic_progress_projection_passed(item) for item in decision_prompts
        ),
        "initial_prompt_private_identity_free": bool(initial)
        and all(str(value) not in initial for value in private_values)
        and all(f'"{field}"' not in initial for field in _PRIVATE_PROMPT_FIELD_NAMES),
        "authority_contract_in_initial_prompt": (
            "public_action_neutral_repair_contract" in initial
            and "public_terminal_verification_target" in initial
        ),
        "terminal_target_in_initial_prompt": (
            '"public_terminal_verification_target"' in initial
            and '"additional_claim_fields_policy":"forbid"' in initial
            and '"terminal_reference_field":"operation_ref"' in initial
        ),
        "repair_prompt_count": repair_prompt_count,
        "action_bearing_repair_prompt_count": action_bearing_repair_prompt_count,
        "failed_observation_count": failed_observation_count,
        "action_bearing_failed_observation_count": action_bearing_failed_observation_count,
        "repair_prompts_action_neutral": action_bearing_repair_prompt_count == 0,
        "failed_observations_action_neutral": action_bearing_failed_observation_count == 0,
        "successful_tool_sequence": tuple(
            item.call.tool_id for item in observations if item.status == "succeeded"
        ),
    }
    provisional = VerifierBoundInstrumentDiagnostic.model_construct(
        diagnostic_id="pending", **values
    )
    return VerifierBoundInstrumentDiagnostic(
        diagnostic_id=verifier_bound_instrument_diagnostic_id(provisional),
        **values,
    )


def _raw_integrity_audit(
    *,
    execution_binding: VerifierBoundInstrumentExecutionBinding,
    manifest: VerifierBoundInstrumentJobManifest,
    rollouts: Sequence[VerifierBoundInstrumentRollout],
    diagnostics: Sequence[VerifierBoundInstrumentDiagnostic],
    output_dir: Path,
) -> VerifierBoundInstrumentRawAudit:
    job_by_id = {item.job_id: item for item in manifest.jobs}
    diagnostic_by_job = {item.job_id: item for item in diagnostics}
    byte_pass = identity_pass = before_pass = provider_rollout_pass = 0
    prompt_pass = recursive_pass = replay_pass = non_replay_pass = 0
    authority_pass = target_pass = repair_pass = stop_pass = 0
    provider_artifact_count = 0
    provider_ids: list[str] = []
    failures: list[str] = []
    for rollout in rollouts:
        try:
            raw_path = Path(rollout.raw_execution_artifact_uri)
            if _sha256(raw_path) != rollout.raw_execution_artifact_sha256:
                raise ValueError("raw execution byte hash changed")
            raw = _load_raw_execution(raw_path)
            byte_pass += 1
            job = job_by_id[rollout.job_id]
            diagnostic = diagnostic_by_job[rollout.job_id]
            if (
                raw.execution_binding_id == execution_binding.binding_id
                and raw.job == job
                and raw.artifact_id
                and raw.task_package_id == rollout.task_package_id
            ):
                identity_pass += 1
            else:
                raise ValueError("raw execution identity changed")
            if raw.captured_before_verifier_replay_and_scoring and (
                not raw.verifier_replay_or_score_fields_present
            ):
                before_pass += 1
            else:
                raise ValueError("raw execution was not persisted before scoring")
            provider_artifacts = []
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
                    artifact.execution_binding_id != execution_binding.binding_id
                    or artifact.job_id != rollout.job_id
                    or artifact.call_index != index
                    or artifact.provider_call_id != rollout.provider_call_ids[index]
                ):
                    raise ValueError("raw Provider call identity changed")
                provider_artifacts.append(artifact)
            if len(provider_artifacts) == rollout.provider_call_count:
                provider_rollout_pass += 1
                provider_artifact_count += len(provider_artifacts)
            if (
                tuple(_sha256_text(item) for item in raw.actual_model_request_prompts)
                == rollout.actual_prompt_hashes
                and tuple(item.provider_call_id for item in provider_artifacts)
                == rollout.provider_call_ids
            ):
                prompt_pass += 1
            else:
                raise ValueError("raw Prompt or telemetry changed")
            if raw.recursive_noninterference_passed and (rollout.recursive_noninterference_passed):
                recursive_pass += 1
            else:
                raise ValueError("raw noninterference audit failed")
            if diagnostic.replay_passed:
                replay_pass += 1
            else:
                raise ValueError("online Replay failed")
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
                raise ValueError("online authority Prompt audit failed")
            if diagnostic.terminal_target_in_initial_prompt:
                target_pass += 1
            else:
                raise ValueError("online terminal-target audit failed")
            if diagnostic.repair_prompts_action_neutral and (
                diagnostic.failed_observations_action_neutral
            ):
                repair_pass += 1
            else:
                raise ValueError("online repair-neutrality audit failed")
            if not diagnostic.stop_ready_false_positive and (
                not diagnostic.stop_ready_false_negative
            ):
                stop_pass += 1
            else:
                raise ValueError("online Stop Readiness audit failed")
            provider_ids.extend(rollout.provider_call_ids)
        except Exception:
            failures.append(rollout.raw_execution_artifact_uri)
    duplicates = tuple(sorted(key for key, count in Counter(provider_ids).items() if count > 1))
    counts = (
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
    complete = len(rollouts) == EXPECTED_JOB_COUNT and all(
        item == EXPECTED_JOB_COUNT for item in counts
    )
    partial = all(item == len(rollouts) for item in counts)
    values = {
        "execution_binding_id": execution_binding.binding_id,
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
            if complete and not duplicates and not failures
            else "partial"
            if partial and not duplicates and not failures
            else "failed"
        ),
    }
    provisional = VerifierBoundInstrumentRawAudit.model_construct(audit_id="pending", **values)
    return VerifierBoundInstrumentRawAudit(
        audit_id=verifier_bound_instrument_raw_audit_id(provisional),
        **values,
    )


def _mechanism_summaries(
    diagnostics: Sequence[VerifierBoundInstrumentDiagnostic],
) -> tuple[InstrumentMechanismSummary, ...]:
    output = []
    for mechanism in TARGET_MECHANISMS:
        rows = tuple(item for item in diagnostics if item.mechanism_id == mechanism)
        output.append(
            InstrumentMechanismSummary(
                mechanism_id=mechanism,
                model_outcome_count=sum(
                    item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
                    for item in rows
                ),
                replay_pass_count=sum(item.replay_passed for item in rows),
                full_program_lineage_count=sum(
                    item.full_program_lineage_completed for item in rows
                ),
                local_mechanism_success_count=sum(item.local_mechanism_success for item in rows),
                independently_valid_count=sum(item.independent_validity for item in rows),
            )
        )
    return tuple(output)


def _trace_diversity(
    diagnostics: Sequence[VerifierBoundInstrumentDiagnostic],
) -> tuple[int, float, float]:
    sequences = tuple(item.successful_tool_sequence for item in diagnostics)
    if not sequences:
        return 0, 0.0, 0.0
    counts = Counter(sequences)
    total = len(sequences)
    probabilities = tuple(value / total for value in counts.values())
    entropy = -sum(value * math.log(value) for value in probabilities if value > 0.0)
    return len(counts), math.exp(entropy), max(probabilities)


def _make_report(
    *,
    execution_binding: VerifierBoundInstrumentExecutionBinding,
    contract: VerifierBoundInstrumentContract,
    manifest: VerifierBoundInstrumentJobManifest,
    discovered_models: Sequence[str],
    rollouts: Sequence[VerifierBoundInstrumentRollout],
    diagnostics: Sequence[VerifierBoundInstrumentDiagnostic],
    raw_audit: VerifierBoundInstrumentRawAudit,
) -> VerifierBoundInstrumentRequalificationReport:
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in rollouts).items()))
    model_outcomes = sum(
        item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
        for item in rollouts
    )
    runtime_failures = terminal_counts.get("runtime_failure", 0)
    instrument_failures = terminal_counts.get("instrument_failure", 0)
    exact_count = sum(item.exact_requested_model for item in rollouts)
    fallback_count = sum(item.fallback_used for item in rollouts)
    total_cost = sum(
        (Decimal(item.estimated_cost_usd) for item in rollouts),
        Decimal("0"),
    )
    resource_budget_passed = bool(
        total_cost <= Decimal(str(contract.maximum_total_estimated_cost_usd))
        and all(
            item.provider_total_tokens <= contract.maximum_total_model_tokens_per_rollout
            for item in rollouts
        )
        and all(item.provider_usage_complete for item in rollouts)
    )
    replay_pass_count = sum(item.replay_passed for item in diagnostics)
    instrument_ready = bool(
        len(rollouts) == EXPECTED_JOB_COUNT
        and raw_audit.status == "passed"
        and runtime_failures == 0
        and instrument_failures == 0
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
    status: Literal["partial", "passed", "blocked"] = (
        "partial"
        if len(rollouts) < EXPECTED_JOB_COUNT
        else "passed"
        if instrument_ready
        else "blocked"
    )
    next_stage = (
        "frozen_verifier_v2_bound_instrument_resume_only"
        if status == "partial"
        else "fresh_capability_and_reachability_protocol_design_only"
        if status == "passed"
        else "resource_budget_audit_only"
        if not resource_budget_passed
        else "verifier_bound_online_instrument_failure_audit_only"
    )
    unique_sequences, effective_sequences, maximum_sequence_share = _trace_diversity(diagnostics)
    values = {
        "execution_run_id": execution_binding.execution_run_id,
        "execution_binding_id": execution_binding.binding_id,
        "discovered_models": tuple(discovered_models),
        "completed_rollout_count": len(rollouts),
        "terminal_counts": terminal_counts,
        "model_outcome_count": model_outcomes,
        "runtime_failure_count": runtime_failures,
        "instrument_failure_count": instrument_failures,
        "exact_requested_model_count": exact_count,
        "fallback_count": fallback_count,
        "provider_call_count": sum(item.provider_call_count for item in rollouts),
        "provider_total_tokens": sum(item.provider_total_tokens for item in rollouts),
        "estimated_cost_usd": str(total_cost),
        "raw_integrity_audit": raw_audit,
        "diagnostics": tuple(diagnostics),
        "mechanism_summaries": _mechanism_summaries(diagnostics),
        "replay_pass_count": replay_pass_count,
        "replay_failure_count": len(rollouts) - replay_pass_count,
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
        "repair_prompt_count": sum(item.repair_prompt_count for item in diagnostics),
        "action_bearing_repair_prompt_count": sum(
            item.action_bearing_repair_prompt_count for item in diagnostics
        ),
        "failed_observation_count": sum(item.failed_observation_count for item in diagnostics),
        "action_bearing_failed_observation_count": sum(
            item.action_bearing_failed_observation_count for item in diagnostics
        ),
        "stop_ready_false_positive_count": sum(
            item.stop_ready_false_positive for item in diagnostics
        ),
        "stop_ready_false_negative_count": sum(
            item.stop_ready_false_negative for item in diagnostics
        ),
        "unique_successful_tool_sequence_count": unique_sequences,
        "effective_successful_tool_sequence_count": effective_sequences,
        "maximum_successful_tool_sequence_share": maximum_sequence_share,
        "resource_budget_passed": resource_budget_passed,
        "instrument_ready": instrument_ready,
        "status": status,
        "next_permitted_stage": next_stage,
    }
    provisional = VerifierBoundInstrumentRequalificationReport.model_construct(
        report_id="pending", **values
    )
    return VerifierBoundInstrumentRequalificationReport(
        report_id=verifier_bound_requalification_report_id(provisional),
        **values,
    )


def _load_checkpoint(
    *,
    path: Path,
    execution_binding: VerifierBoundInstrumentExecutionBinding,
    manifest: VerifierBoundInstrumentJobManifest,
) -> tuple[VerifierBoundInstrumentRollout, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        VerifierBoundInstrumentRollout.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("Instrument checkpoint contains duplicate Job identities")
    for item in rows:
        job = jobs.get(item.job_id)
        if (
            job is None
            or item.execution_binding_id != execution_binding.binding_id
            or item.task_record_id != job.task_record_id
            or item.task_package_id != job.task_package_id
            or item.environment_manifest_id != job.environment_manifest_id
            or item.replay_binding_contract_id != job.replay_binding_contract_id
            or item.replicate_index != job.replicate_index
        ):
            raise ValueError("Instrument checkpoint differs from a frozen Job")
        if _sha256(Path(item.raw_execution_artifact_uri)) != item.raw_execution_artifact_sha256:
            raise ValueError("Instrument checkpoint raw Artifact hash changed")
    return rows


def _run_one_job(
    *,
    job: VerifierBoundInstrumentJob,
    prepared: _PreparedInputs,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    client: OpenAICompatibleJsonClient | None,
    output_dir: Path,
) -> VerifierBoundInstrumentRollout:
    raw = _execute_and_persist_raw(
        job=job,
        contract=prepared.contract,
        execution_binding=prepared.execution_binding,
        record=record,
        environment=environment,
        client=client,
        output_dir=output_dir,
    )
    return _score_with_failure_capture(
        job=job,
        contract=prepared.contract,
        execution_binding=prepared.execution_binding,
        replay_contract=prepared.replay_contract,
        record=record,
        environment=environment,
        raw=raw,
        output_dir=output_dir,
    )


def run_verifier_bound_instrument_requalification(
    *,
    execution_run_id: str,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    workers: int,
    client_factory: Callable[[AgentModelConfig], OpenAICompatibleJsonClient] = (
        OpenAICompatibleJsonClient
    ),
) -> VerifierBoundInstrumentRequalificationReport:
    prepared = prepare_verifier_bound_instrument_execution(
        execution_run_id=execution_run_id,
        task_source_dir=task_source_dir,
        verifier_qualification_dir=verifier_qualification_dir,
        preflight_dir=preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
    )
    checkpoint_path = output_dir / "rollout_observations.checkpoint.jsonl"
    existing = _load_checkpoint(
        path=checkpoint_path,
        execution_binding=prepared.execution_binding,
        manifest=prepared.manifest,
    )
    completed = {item.job_id: item for item in existing}
    pending = [item for item in prepared.manifest.jobs if item.job_id not in completed]
    raw_recovery_jobs = [item for item in pending if _raw_execution_path(output_dir, item).exists()]
    model_pending_jobs = [
        item for item in pending if not _raw_execution_path(output_dir, item).exists()
    ]
    prior_report_path = output_dir / "report.json"
    if pending and prior_report_path.exists():
        raise ValueError("completed Instrument report exists while frozen Jobs remain pending")
    model_config = AgentModelConfig.model_validate(prepared.contract.model_invocation_config)
    client: OpenAICompatibleJsonClient | None = None
    if model_pending_jobs:
        client = client_factory(model_config)
        discovered_models = client.discover_models()
        if prepared.contract.model_id not in discovered_models:
            raise ValueError("frozen DeepSeek V4-Flash identity is unavailable")
    elif prior_report_path.exists():
        prior_report = VerifierBoundInstrumentRequalificationReport.model_validate_json(
            prior_report_path.read_text(encoding="utf-8")
        )
        if (
            prior_report.execution_binding_id != prepared.execution_binding.binding_id
            or prior_report.contract_id != prepared.contract.contract_id
            or prior_report.job_manifest_id != prepared.manifest.manifest_id
        ):
            raise ValueError("completed Instrument report crosses frozen inputs")
        discovered_models = prior_report.discovered_models
    else:
        discovered_models = (prepared.contract.model_id,)
    print(
        f"[v26.78] resuming {len(completed)}/{EXPECTED_JOB_COUNT}; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} jobs with {workers} workers",
        flush=True,
    )
    record_by_id = {item.record_id: item for item in prepared.records}
    environment_by_id = {item.manifest_id: item for item in prepared.environments}
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                record=record_by_id[job.task_record_id],
                environment=environment_by_id[job.environment_manifest_id],
                client=(None if job in raw_recovery_jobs else client),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(future_map):
            job = future_map[future]
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
                    "Verifier-bound Instrument worker failed; raw-only recovery is required"
                ) from exc
            with lock:
                if rollout.job_id in completed:
                    raise ValueError("Instrument runner produced a duplicate Job result")
                completed[rollout.job_id] = rollout
                _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
            if len(completed) % max(1, workers) == 0 or len(completed) == EXPECTED_JOB_COUNT:
                print(
                    f"[v26.78] completed {len(completed)}/{EXPECTED_JOB_COUNT}",
                    flush=True,
                )
    ordered = tuple(
        completed[item.job_id] for item in prepared.manifest.jobs if item.job_id in completed
    )
    job_by_id = {item.job_id: item for item in prepared.manifest.jobs}
    binding_by_id = {item.contract_id: item for item in prepared.bindings}
    diagnostics = tuple(
        _diagnostic(
            rollout=item,
            raw=_load_raw_execution(Path(item.raw_execution_artifact_uri)),
            record=record_by_id[item.task_record_id],
            binding=binding_by_id[job_by_id[item.job_id].replay_binding_contract_id],
        )
        for item in ordered
    )
    raw_audit = _raw_integrity_audit(
        execution_binding=prepared.execution_binding,
        manifest=prepared.manifest,
        rollouts=ordered,
        diagnostics=diagnostics,
        output_dir=output_dir,
    )
    report = _make_report(
        execution_binding=prepared.execution_binding,
        contract=prepared.contract,
        manifest=prepared.manifest,
        discovered_models=tuple(discovered_models),
        rollouts=ordered,
        diagnostics=diagnostics,
        raw_audit=raw_audit,
    )
    _write_json_atomic(
        output_dir / "instrument_rollouts.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "online_replay_results.json",
        [
            cast(AuthorityPreservingReplayResult, item.replay_result).model_dump(mode="json")
            for item in ordered
            if item.replay_result is not None
        ],
    )
    _write_json_atomic(
        output_dir / "independent_non_replay_gate_audits.json",
        [
            cast(OnlineNonReplayGateAudit, item.non_replay_gate_audit).model_dump(mode="json")
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
        output_dir / "mechanism_summaries.json",
        [item.model_dump(mode="json") for item in report.mechanism_summaries],
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def online_source_replay_audit_id(value: OnlineSourceReplayAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_online_source_replay:",
    )


def verifier_bound_execution_binding_id(
    value: VerifierBoundInstrumentExecutionBinding,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"binding_id"}),
        prefix="finance_v26_verifier_bound_instrument_execution_binding:",
    )


def raw_provider_call_artifact_id(value: RawProviderCallArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="finance_v26_verifier_bound_raw_provider_call:",
    )


def raw_execution_artifact_id(value: VerifierBoundRawExecutionArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="finance_v26_verifier_bound_raw_execution:",
    )


def online_non_replay_gate_audit_id(value: OnlineNonReplayGateAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_non_replay_gate_audit:",
    )


def verifier_bound_instrument_rollout_id(value: VerifierBoundInstrumentRollout) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"rollout_id"}),
        prefix="finance_v26_verifier_bound_instrument_rollout:",
    )


def verifier_bound_instrument_diagnostic_id(
    value: VerifierBoundInstrumentDiagnostic,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_verifier_bound_instrument_diagnostic:",
    )


def verifier_bound_instrument_raw_audit_id(
    value: VerifierBoundInstrumentRawAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_instrument_raw_audit:",
    )


def verifier_bound_requalification_report_id(
    value: VerifierBoundInstrumentRequalificationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_verifier_bound_instrument_requalification:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the frozen Finance v26.77 32-job Verifier-v2-bound Instrument requalification"
        )
    )
    parser.add_argument("--execution-run-id", required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument("--preflight-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_verifier_bound_instrument_execution(
            execution_run_id=args.execution_run_id,
            task_source_dir=args.task_source_dir,
            verifier_qualification_dir=args.verifier_qualification_dir,
            preflight_dir=args.preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
        )
        print(
            json.dumps(
                {
                    "execution_binding_id": prepared.execution_binding.binding_id,
                    "online_source_replay_audit_id": prepared.source_audit.audit_id,
                    "expected_job_count": len(prepared.manifest.jobs),
                    "model_client_constructed": False,
                    "model_api_calls": 0,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return
    report = run_verifier_bound_instrument_requalification(
        execution_run_id=args.execution_run_id,
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
