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
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument import (  # noqa: E501
    CompletedTrajectoryScore,
    InstrumentFailureChannels,
    build_instrument_failure_channels,
    score_completed_trajectory,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_preflight import (  # noqa: E501
    IMPLEMENTATION_SOURCE_PATHS as PREFLIGHT_IMPLEMENTATION_SOURCE_PATHS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_preflight import (  # noqa: E501
    BudgetClosedInstrumentContract,
    BudgetClosedInstrumentJob,
    BudgetClosedInstrumentJobManifest,
    BudgetClosedInstrumentPreflightReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_task_rematerialization import (  # noqa: E501
    BudgetClosedInstrumentPopulationReport,
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
    SourceReplayEntry,
    VerifierBoundSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    V26_VERIFIER_IMPLEMENTATION_VERSION,
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
    ProviderBudgetNoCallTerminal,
    ProviderTokenBudgetAudit,
)
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation

V26_BUDGET_CLOSED_ONLINE_SOURCE_REPLAY_VERSION = "finance_v26_budget_closed_online_source_replay.v1"
V26_BUDGET_CLOSED_EXECUTION_BINDING_VERSION = (
    "finance_v26_budget_closed_instrument_execution_binding.v1"
)
V26_BUDGET_CLOSED_PROVIDER_CALL_VERSION = "finance_v26_budget_closed_raw_provider_call.v1"
V26_BUDGET_CLOSED_RAW_EXECUTION_VERSION = "finance_v26_budget_closed_raw_execution.v1"
V26_BUDGET_CLOSED_NON_REPLAY_AUDIT_VERSION = "finance_v26_budget_closed_non_replay_gate_audit.v1"
V26_BUDGET_CLOSED_ROLLOUT_VERSION = "finance_v26_budget_closed_instrument_rollout.v1"
V26_BUDGET_CLOSED_DIAGNOSTIC_VERSION = "finance_v26_budget_closed_instrument_diagnostic.v1"
V26_BUDGET_CLOSED_RAW_LINEAGE_AUDIT_VERSION = "finance_v26_budget_closed_raw_lineage_audit.v1"
V26_BUDGET_CLOSED_MECHANISM_SUMMARY_VERSION = (
    "finance_v26_budget_closed_instrument_mechanism_summary.v1"
)
V26_BUDGET_CLOSED_REQUALIFICATION_REPORT_VERSION = (
    "finance_v26_budget_closed_instrument_requalification.v1"
)

EXPECTED_PREFLIGHT_REPORT_ID = (
    "finance_v26_budget_closed_instrument_preflight:"
    "6c279f69cb080458952dfb000633f17c4f901aa8098dfac0cb423656ad9684a7"
)
EXPECTED_CONTRACT_ID = (
    "finance_v26_budget_closed_instrument_contract:"
    "12c9789ccbe3d557411cf5428a15ee0e3d26337b846f47b61b830c86e1415121"
)
EXPECTED_MANIFEST_ID = (
    "finance_v26_budget_closed_instrument_manifest:"
    "38f4a8f5b40c2c576c690c3069c66bc1f43a64f52ef554a16ea28a4656c2434c"
)
EXPECTED_TASK_SOURCE_REPORT_ID = (
    "finance_v26_budget_closed_verifier_bound_instrument_population_report:"
    "9f60f8d7c7522a1fd934bb5a7cdfefb2c91becc73f7e68b2f815dea352ad6484"
)
EXPECTED_VERIFIER_REPORT_ID = (
    "finance_v26_authority_verifier_qualification:"
    "f61be6be022c2c8506e818e3bb9690e71fa316c6820fec69458c7ab7c8fa7bb1"
)
EXPECTED_PROVIDER_BUDGET_CONTRACT_ID = (
    "provider_token_budget_contract:"
    "27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150"
)
EXPECTED_JOB_COUNT: Literal[32] = 32
DEFAULT_WORKERS = 16

ONLINE_IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted(
        {
            *PREFLIGHT_IMPLEMENTATION_SOURCE_PATHS,
            "src/trusted_synthesis/core/trajectory/schema.py",
            "src/trusted_synthesis/core/trajectory/state.py",
            "src/trusted_synthesis/domains/finance/interactive_agent_runtime.py",
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_budget_closed_instrument_requalification.py"
            ),
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_empirical_support_pilot.py"
            ),
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_operation_closure_regression.py"
            ),
            "src/trusted_synthesis/runtime/agent/client.py",
            "src/trusted_synthesis/runtime/agent/iterative.py",
            "src/trusted_synthesis/runtime/agent/schema.py",
        }
    )
)

NON_REPLAY_CHECK_IDS = (
    "answer_projection_complete",
    "citation_complete",
    "evidence_support_complete",
    "mechanism_complete",
    "model_input_noninterference_passed",
    "no_postcompletion_violation",
    "only_allowed_tools",
    "operation_lineage_complete",
    "verification_complete",
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

ExecutionKind = Literal[
    "completed_trajectory",
    "captured_model_contract_failure",
    "typed_budget_no_call",
    "provider_budget_contract_failure",
    "provider_or_runtime_failure",
    "unexpected_execution_failure",
]
TerminalCategory = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "budget_exhausted_no_call",
    "runtime_failure",
    "instrument_failure",
]
CoreTerminal = Literal[
    "valid_trajectory",
    "invalid_trajectory",
    "model_invalid_resource_terminal",
    "runtime_failure",
    "instrument_failure",
]
NoCallPhase = Literal[
    "initial_prompt_unfit",
    "mid_rollout_budget_exhausted",
    "final_reserve_unavailable",
    "repair_reserve_unavailable",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BudgetClosedOnlineSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    frozen_source_replay_audit_id: str = Field(min_length=1)
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=60)
    replayed_file_count: int = Field(ge=60)
    replay_pass_count: int = Field(ge=60)
    source_replay_before_client_construction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_CLOSED_ONLINE_SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetClosedOnlineSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("budget-closed online source replay paths are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("budget-closed online source replay denominator changed")
        if self.replay_pass_count != self.replayed_file_count:
            raise ValueError("budget-closed online source replay is incomplete")
        if self.audit_id != budget_closed_online_source_replay_audit_id(self):
            raise ValueError("budget-closed online source replay identity is invalid")
        return self


class BudgetClosedExecutionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    execution_run_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    task_source_report_id: str = EXPECTED_TASK_SOURCE_REPORT_ID
    verifier_qualification_report_id: str = EXPECTED_VERIFIER_REPORT_ID
    provider_token_budget_contract_id: str = EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
    replay_contract_id: str = Field(min_length=1)
    online_source_replay_audit_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    maximum_total_model_tokens_per_rollout: Literal[120000] = 120000
    maximum_total_estimated_cost_usd: float = Field(default=2.0, ge=2.0, le=2.0)
    pre_call_budget_certificate_required: Literal[True] = True
    typed_no_call_terminal_retained: Literal[True] = True
    raw_provider_calls_persisted_before_budget_validation: Literal[True] = True
    raw_execution_persisted_before_verifier_replay_and_scoring: Literal[True] = True
    provider_and_host_telemetry_separately_bound: Literal[True] = True
    shared_completed_trajectory_scorer_required: Literal[True] = True
    failure_namespaces_separated: Literal[True] = True
    raw_only_zero_generation_recovery_required: Literal[True] = True
    compiler_witness_empirical_count: Literal[0] = 0
    historical_diagnostic_candidate_count: Literal[0] = 0
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(min_length=20)
    schema_version: str = V26_BUDGET_CLOSED_EXECUTION_BINDING_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> BudgetClosedExecutionBinding:
        if tuple(item.relative_path for item in self.implementation_source_files) != (
            ONLINE_IMPLEMENTATION_SOURCE_PATHS
        ):
            raise ValueError("budget-closed online implementation manifest is incomplete")
        if self.binding_id != budget_closed_execution_binding_id(self):
            raise ValueError("budget-closed online execution binding identity is invalid")
        return self


class RawFileDescriptor(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class BudgetClosedRawProviderCall(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    contract_id: str = EXPECTED_CONTRACT_ID
    job_id: str = Field(min_length=1)
    call_index: int = Field(ge=0)
    provider_call_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    prompt_sha256: str = Field(min_length=64, max_length=64)
    response_payload: dict[str, Any] | None = None
    provider_telemetry: ModelCallTelemetry
    captured_before_budget_usage_validation: Literal[True] = True
    captured_before_agent_contract_scoring: Literal[True] = True
    schema_version: str = V26_BUDGET_CLOSED_PROVIDER_CALL_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> BudgetClosedRawProviderCall:
        if self.prompt_sha256 != _sha256_text(self.prompt):
            raise ValueError("raw Provider Prompt hash changed")
        if self.provider_telemetry.request_hash != self.prompt_sha256:
            raise ValueError("raw Provider Prompt differs from telemetry")
        expected = provider_call_id(self.job_id, self.call_index, self.provider_telemetry)
        if self.provider_call_id != expected:
            raise ValueError("raw Provider call identity is invalid")
        if self.artifact_id != budget_closed_raw_provider_call_id(self):
            raise ValueError("raw Provider Artifact identity is invalid")
        return self


class BudgetClosedRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
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
    provider_budget_audit: ProviderTokenBudgetAudit
    solve_result: IterativeAgentSolveResult | None = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    recursive_noninterference_passed: bool
    captured_before_verifier_replay_and_scoring: Literal[True] = True
    verifier_replay_or_score_fields_present: Literal[False] = False
    schema_version: str = V26_BUDGET_CLOSED_RAW_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> BudgetClosedRawExecution:
        if self.job.contract_id != self.contract_id:
            raise ValueError("raw execution Job crosses Contracts")
        if (
            self.task_record_id != self.job.task_record_id
            or self.task_package_id != self.job.task_package_id
            or self.environment_manifest_id != self.job.environment_manifest_id
            or self.replay_binding_contract_id != self.job.replay_binding_contract_id
        ):
            raise ValueError("raw execution loses a frozen Job identity")
        call_count = len(self.provider_call_ids)
        if not (
            call_count
            == len(self.provider_call_artifacts)
            == len(self.provider_telemetry)
            == len(self.provider_request_prompts)
            == len(self.host_telemetry)
            == len(self.host_request_prompts)
        ):
            raise ValueError("raw execution Provider and Host accounting is incomplete")
        expected_calls = tuple(
            provider_call_id(self.job.job_id, index, telemetry)
            for index, telemetry in enumerate(self.provider_telemetry)
        )
        if self.provider_call_ids != expected_calls:
            raise ValueError("raw execution Provider identities changed")
        if tuple(_sha256_text(item) for item in self.provider_request_prompts) != tuple(
            item.request_hash for item in self.provider_telemetry
        ):
            raise ValueError("raw execution Provider Prompt accounting changed")
        if self.provider_request_prompts != self.host_request_prompts:
            raise ValueError("Provider and Host Prompt views differ")
        if any(
            not _provider_telemetry_equal_before_host_augmentation(raw, host)
            for raw, host in zip(self.provider_telemetry, self.host_telemetry, strict=True)
        ):
            raise ValueError("Provider and Host telemetry differ before Host augmentation")
        audit = self.provider_budget_audit
        if (
            audit.contract_id != EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
            or audit.provider_call_count != call_count
            or audit.permitted_request_count != call_count
            or len(audit.certificates) != len(self.attempted_model_prompts)
        ):
            raise ValueError("raw execution budget accounting changed")
        if tuple(item.request_hash for item in audit.certificates) != tuple(
            _sha256_text(item) for item in self.attempted_model_prompts
        ):
            raise ValueError("raw execution budget Certificates cross attempted Prompts")
        if audit.actual_request_prompt_hashes != tuple(
            _sha256_text(item) for item in self.provider_request_prompts
        ):
            raise ValueError("raw execution budget audit crosses Provider Prompts")
        if self.execution_kind == "completed_trajectory":
            if (
                self.solve_result is None
                or self.failure_artifact is not None
                or self.execution_error
            ):
                raise ValueError("completed raw execution has inconsistent payloads")
        elif self.execution_kind == "typed_budget_no_call":
            if audit.no_call_terminal is None or self.solve_result is not None:
                raise ValueError("typed no-call raw execution lacks its frozen terminal")
        elif self.solve_result is not None:
            raise ValueError("failed raw execution unexpectedly contains a solve result")
        if self.execution_kind != "completed_trajectory" and not self.execution_error:
            raise ValueError("failed raw execution lacks an error attribution")
        if (audit.no_call_terminal is not None) != (self.execution_kind == "typed_budget_no_call"):
            raise ValueError("raw execution no-call classification changed")
        if self.artifact_id != budget_closed_raw_execution_id(self):
            raise ValueError("budget-closed raw execution identity is invalid")
        return self


class BudgetClosedNonReplayGateAudit(FrozenModel):
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
    schema_version: str = V26_BUDGET_CLOSED_NON_REPLAY_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetClosedNonReplayGateAudit:
        if tuple(self.checks) != NON_REPLAY_CHECK_IDS:
            raise ValueError("budget-closed non-Replay Gate vector is incomplete")
        if self.complete_solve_result != (self.trajectory_id is not None):
            raise ValueError("budget-closed non-Replay completion status changed")
        if self.complete_solve_result and self.verifier_report_non_replay_agreement is not True:
            raise ValueError("budget-closed non-Replay Gates disagree with Verifier v2")
        if not self.complete_solve_result and self.verifier_report_non_replay_agreement is not None:
            raise ValueError("incomplete model result claims Verifier Gate agreement")
        if self.audit_id != budget_closed_non_replay_gate_audit_id(self):
            raise ValueError("budget-closed non-Replay Gate identity is invalid")
        return self


class BudgetClosedInstrumentRollout(FrozenModel):
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
    terminal_category: TerminalCategory
    core_terminal: CoreTerminal
    provider_call_ids: tuple[str, ...]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    provider_usage_complete: bool
    estimated_cost_usd: str = Field(min_length=1)
    exact_requested_model: bool
    fallback_used: bool
    actual_prompt_hashes: tuple[str, ...]
    attempted_prompt_hashes: tuple[str, ...] = Field(min_length=1)
    recursive_noninterference_passed: bool
    observation_count: int = Field(ge=0)
    replay_result: AuthorityPreservingReplayResult | None = None
    non_replay_gate_audit: BudgetClosedNonReplayGateAudit | None = None
    verification: AuthorityPreservingVerificationReport | None = None
    completed_trajectory_score: CompletedTrajectoryScore | None = None
    failure_channels: InstrumentFailureChannels
    mechanism_estimand: MechanismEstimandOutcome
    trajectory_id: str | None = None
    no_call_terminal: ProviderBudgetNoCallTerminal | None = None
    no_call_phase: NoCallPhase | None = None
    model_generated: bool
    denominator_retained: Literal[True] = True
    instrument_admitted: bool
    raw_execution_artifact_uri: str = Field(min_length=1)
    raw_execution_artifact_sha256: str = Field(min_length=64, max_length=64)
    raw_provider_call_artifacts: tuple[RawFileDescriptor, ...]
    raw_persisted_before_replay_and_scoring: Literal[True] = True
    state_mapping_permitted: Literal[False] = False
    path_assignment_present: Literal[False] = False
    failure_attribution: dict[str, Any] | None = None
    schema_version: str = V26_BUDGET_CLOSED_ROLLOUT_VERSION

    @model_validator(mode="after")
    def validate_rollout(self) -> BudgetClosedInstrumentRollout:
        if self.provider_call_count != len(self.provider_call_ids):
            raise ValueError("budget-closed rollout Provider accounting changed")
        if len(self.raw_provider_call_artifacts) != self.provider_call_count:
            raise ValueError("budget-closed rollout lost raw Provider artifacts")
        if self.replay_result is not None and (
            self.replay_result.task_package_id != self.task_package_id
            or self.replay_result.observation_count != self.observation_count
        ):
            raise ValueError("budget-closed rollout Replay crosses its Job")
        if self.non_replay_gate_audit is not None and (
            self.non_replay_gate_audit.job_id != self.job_id
            or self.non_replay_gate_audit.task_package_id != self.task_package_id
        ):
            raise ValueError("budget-closed rollout crosses non-Replay Gate audits")
        if (self.no_call_terminal is None) != (
            self.terminal_category != "budget_exhausted_no_call"
        ):
            raise ValueError("budget-closed rollout no-call terminal changed")
        if (self.no_call_phase is None) != (self.no_call_terminal is None):
            raise ValueError("budget-closed rollout no-call phase changed")
        if self.terminal_category == "budget_exhausted_no_call" and (
            self.core_terminal != "model_invalid_resource_terminal"
        ):
            raise ValueError("typed no-call was not retained as a model-invalid resource terminal")
        if self.completed_trajectory_score is not None:
            score = self.completed_trajectory_score
            if score.trajectory_id != self.trajectory_id or score.failure_channels != (
                self.failure_channels
            ):
                raise ValueError("budget-closed rollout crosses shared completed scoring")
            expected = {
                "valid_trajectory": "model_valid_trajectory",
                "invalid_trajectory": "model_invalid_trajectory",
                "instrument_failure": "instrument_failure",
            }[score.core_terminal]
            if self.terminal_category != expected or self.core_terminal != score.core_terminal:
                raise ValueError("budget-closed rollout changed its shared core terminal")
        if self.instrument_admitted != (
            self.failure_channels.instrument_gate_passed
            and self.failure_channels.report_complete
            and self.terminal_category not in {"runtime_failure", "instrument_failure"}
        ):
            raise ValueError("budget-closed rollout Instrument admission changed")
        if self.rollout_id != budget_closed_instrument_rollout_id(self):
            raise ValueError("budget-closed Instrument rollout identity is invalid")
        return self


class BudgetClosedRolloutDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    terminal_category: TerminalCategory
    core_terminal: CoreTerminal
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    budget_certificate_count: int = Field(ge=1)
    no_call_phase: NoCallPhase | None = None
    replay_passed: bool
    replay_failure_ids: tuple[str, ...]
    non_replay_gate_audit_present: bool
    complete_verifier_gate_agreement: bool | None = None
    shared_completed_score_present: bool
    schema_closed_sidecar_passed: bool | None = None
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
    failure_channel_id: str = Field(min_length=1)
    instrument_admitted: bool
    state_mapping_eligible: Literal[False] = False
    schema_version: str = V26_BUDGET_CLOSED_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> BudgetClosedRolloutDiagnostic:
        if self.completed_node_count > self.required_node_count:
            raise ValueError("budget-closed diagnostic completed too many Program nodes")
        if self.full_program_lineage_completed != (
            self.completed_node_count == self.required_node_count
        ):
            raise ValueError("budget-closed diagnostic Program closure changed")
        if self.replay_passed != (not self.replay_failure_ids):
            raise ValueError("budget-closed diagnostic Replay status changed")
        if self.repair_prompts_action_neutral != (
            self.action_bearing_repair_prompt_count == 0
        ) or self.failed_observations_action_neutral != (
            self.action_bearing_failed_observation_count == 0
        ):
            raise ValueError("budget-closed diagnostic repair neutrality changed")
        if self.diagnostic_id != budget_closed_rollout_diagnostic_id(self):
            raise ValueError("budget-closed diagnostic identity is invalid")
        return self


class BudgetClosedRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    expected_rollout_count: Literal[32] = EXPECTED_JOB_COUNT
    observed_rollout_count: int = Field(ge=0, le=32)
    raw_execution_byte_pass_count: int = Field(ge=0, le=32)
    raw_execution_identity_pass_count: int = Field(ge=0, le=32)
    raw_before_scoring_pass_count: int = Field(ge=0, le=32)
    provider_capture_pass_count: int = Field(ge=0, le=32)
    provider_budget_binding_pass_count: int = Field(ge=0, le=32)
    provider_host_telemetry_pass_count: int = Field(ge=0, le=32)
    actual_prompt_binding_pass_count: int = Field(ge=0, le=32)
    raw_provider_call_artifact_count: int = Field(ge=0)
    provider_call_ids_unique: bool
    duplicate_provider_call_ids: tuple[str, ...] = ()
    raw_lineage_failure_ids: tuple[str, ...] = ()
    downstream_failure_ids_present: Literal[False] = False
    status: Literal["passed", "partial", "failed"]
    schema_version: str = V26_BUDGET_CLOSED_RAW_LINEAGE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetClosedRawLineageAudit:
        if self.raw_lineage_failure_ids != tuple(sorted(set(self.raw_lineage_failure_ids))):
            raise ValueError("raw-lineage failures are not canonical")
        if any(not item.startswith("raw_lineage:") for item in self.raw_lineage_failure_ids):
            raise ValueError("raw-lineage audit contains a downstream failure")
        counts = (
            self.raw_execution_byte_pass_count,
            self.raw_execution_identity_pass_count,
            self.raw_before_scoring_pass_count,
            self.provider_capture_pass_count,
            self.provider_budget_binding_pass_count,
            self.provider_host_telemetry_pass_count,
            self.actual_prompt_binding_pass_count,
        )
        complete = self.observed_rollout_count == 32 and all(item == 32 for item in counts)
        partial = all(item == self.observed_rollout_count for item in counts)
        expected = (
            "passed"
            if complete and self.provider_call_ids_unique and not self.raw_lineage_failure_ids
            else "partial"
            if partial and self.provider_call_ids_unique and not self.raw_lineage_failure_ids
            else "failed"
        )
        if self.status != expected:
            raise ValueError("raw-lineage audit status changed")
        if self.audit_id != budget_closed_raw_lineage_audit_id(self):
            raise ValueError("raw-lineage audit identity is invalid")
        return self


class BudgetClosedMechanismSummary(FrozenModel):
    mechanism_id: str = Field(min_length=1)
    attempted_count: Literal[8] = 8
    instrument_admitted_count: int = Field(ge=0, le=8)
    model_outcome_count: int = Field(ge=0, le=8)
    no_call_count: int = Field(ge=0, le=8)
    replay_pass_count: int = Field(ge=0, le=8)
    full_program_lineage_count: int = Field(ge=0, le=8)
    local_mechanism_success_count: int = Field(ge=0, le=8)
    independently_valid_count: int = Field(ge=0, le=8)
    descriptive_only: Literal[True] = True
    schema_version: str = V26_BUDGET_CLOSED_MECHANISM_SUMMARY_VERSION


class BudgetClosedInstrumentRequalificationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    execution_run_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    contract_id: str = EXPECTED_CONTRACT_ID
    job_manifest_id: str = EXPECTED_MANIFEST_ID
    provider_token_budget_contract_id: str = EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
    discovered_models: tuple[str, ...]
    expected_rollout_count: Literal[32] = EXPECTED_JOB_COUNT
    completed_rollout_count: int = Field(ge=0, le=32)
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
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    raw_lineage_audit: BudgetClosedRawLineageAudit
    diagnostics: tuple[BudgetClosedRolloutDiagnostic, ...]
    mechanism_summaries: tuple[BudgetClosedMechanismSummary, ...]
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
        "frozen_budget_closed_instrument_resume_only",
        "fresh_capability_and_reachability_protocol_design_only",
        "budget_closed_online_instrument_failure_audit_only",
        "budget_closed_online_resource_failure_audit_only",
    ]
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_BUDGET_CLOSED_REQUALIFICATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetClosedInstrumentRequalificationReport:
        if sum(self.terminal_counts.values()) != self.completed_rollout_count:
            raise ValueError("budget-closed report terminal denominator changed")
        if sum(self.core_terminal_counts.values()) != self.completed_rollout_count:
            raise ValueError("budget-closed report core-terminal denominator changed")
        if len(self.diagnostics) != self.completed_rollout_count:
            raise ValueError("budget-closed report diagnostic denominator changed")
        if self.replay_failure_count != self.completed_rollout_count - self.replay_pass_count:
            raise ValueError("budget-closed report Replay denominator changed")
        expected_status = (
            "partial"
            if self.completed_rollout_count < EXPECTED_JOB_COUNT
            else "passed"
            if self.instrument_ready
            else "blocked"
        )
        if self.status != expected_status:
            raise ValueError("budget-closed report status changed")
        expected_stage = (
            "frozen_budget_closed_instrument_resume_only"
            if self.status == "partial"
            else "fresh_capability_and_reachability_protocol_design_only"
            if self.status == "passed"
            else "budget_closed_online_resource_failure_audit_only"
            if not self.resource_budget_passed
            else "budget_closed_online_instrument_failure_audit_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("budget-closed report transition changed")
        if self.report_id != budget_closed_requalification_report_id(self):
            raise ValueError("budget-closed requalification report identity is invalid")
        return self


class _PreparedInputs:
    def __init__(
        self,
        *,
        preflight: BudgetClosedInstrumentPreflightReport,
        contract: BudgetClosedInstrumentContract,
        manifest: BudgetClosedInstrumentJobManifest,
        task_report: BudgetClosedInstrumentPopulationReport,
        replay_contract: AuthorityPreservingReplayContract,
        records: tuple[OperationalTaskRecord, ...],
        environments: tuple[AgentToolEnvironmentManifest, ...],
        bindings: tuple[VerifierV2TaskReplayBinding, ...],
        source_audit: BudgetClosedOnlineSourceReplayAudit,
        execution_binding: BudgetClosedExecutionBinding,
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
            raise ValueError(f"immutable budget-closed JSON changed: {path}")
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
            raise ValueError(f"immutable raw budget-closed Artifact changed: {path}")
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
    report: BudgetClosedInstrumentPreflightReport,
    preflight_dir: Path,
) -> None:
    for descriptor in report.immutable_detail_files:
        path = preflight_dir / descriptor.relative_path
        if not path.is_file() or _sha256(path) != descriptor.sha256:
            raise ValueError(f"frozen v26.83 detail changed: {path}")


def _build_online_source_replay(
    *,
    preflight: BudgetClosedInstrumentPreflightReport,
    frozen_source_replay: VerifierBoundSourceReplayAudit,
    preflight_dir: Path,
    package_root: Path,
) -> BudgetClosedOnlineSourceReplayAudit:
    expected: dict[str, tuple[str, str]] = {}

    def register(path: Path, expected_sha256: str, source_kind: str) -> None:
        relative = _relative_to_package(path, package_root)
        prior = expected.get(relative)
        if prior is not None and prior[0] != expected_sha256:
            raise ValueError(f"online source manifests disagree for {relative}")
        expected[relative] = prior or (expected_sha256, source_kind)

    for item in frozen_source_replay.entries:
        register(package_root / item.relative_path, item.expected_sha256, item.source_kind)
    register(preflight_dir / "report.json", _sha256(preflight_dir / "report.json"), "task_detail")
    for descriptor in preflight.immutable_detail_files:
        register(preflight_dir / descriptor.relative_path, descriptor.sha256, "task_detail")
    for descriptor in _implementation_sources(package_root):
        register(
            package_root / descriptor.relative_path,
            descriptor.sha256,
            "task_implementation",
        )
    entries = []
    for relative, (expected_sha256, source_kind) in sorted(expected.items()):
        path = package_root / relative
        entries.append(
            SourceReplayEntry(
                relative_path=relative,
                source_kind=cast(Any, source_kind),
                expected_sha256=expected_sha256,
                observed_sha256=_sha256(path),
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
    provisional = BudgetClosedOnlineSourceReplayAudit.model_construct(audit_id="pending", **values)
    return BudgetClosedOnlineSourceReplayAudit(
        audit_id=budget_closed_online_source_replay_audit_id(provisional),
        **values,
    )


def _validate_online_bindings(
    *,
    contract: BudgetClosedInstrumentContract,
    manifest: BudgetClosedInstrumentJobManifest,
    replay_contract: AuthorityPreservingReplayContract,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    bindings: Sequence[VerifierV2TaskReplayBinding],
    task_audits: Sequence[AuthorityPreservingTaskAudit],
) -> None:
    if manifest.contract_id != contract.contract_id:
        raise ValueError("budget-closed online Manifest crosses Contracts")
    if contract.provider_token_budget_contract.contract_id != (
        EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
    ):
        raise ValueError("budget-closed online run received another Provider budget Contract")
    record_by_id = {item.record_id: item for item in records}
    environment_by_id = {item.manifest_id: item for item in environments}
    binding_by_id = {item.contract_id: item for item in bindings}
    audit_by_task = {item.task_package_id: item for item in task_audits}
    if not (
        len(record_by_id) == len(environment_by_id) == len(binding_by_id) == len(audit_by_task) == 8
    ):
        raise ValueError("budget-closed online task denominator changed")
    if contract.qualified_replay_contract_id != replay_contract.contract_id:
        raise ValueError("budget-closed online run uses another Replay Contract")
    for job in manifest.jobs:
        record = record_by_id.get(job.task_record_id)
        environment = environment_by_id.get(job.environment_manifest_id)
        binding = binding_by_id.get(job.replay_binding_contract_id)
        if record is None or environment is None or binding is None:
            raise ValueError(f"budget-closed online Job loses a frozen input: {job.job_id}")
        package = record.task_package
        repair = package.action_neutral_repair_contract
        target = package.terminal_verification_target
        task_audit = audit_by_task.get(package.package_id)
        oracle_binding = package.task.oracle.selection_contract.get(
            "authority_preserving_verifier_v2_binding"
        )
        if (
            package.package_id != job.task_package_id
            or job.provider_token_budget_contract_id
            != contract.provider_token_budget_contract.contract_id
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
            raise ValueError(f"budget-closed online binding changed: {job.job_id}")


def prepare_budget_closed_instrument_execution(
    *,
    execution_run_id: str,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> _PreparedInputs:
    preflight = BudgetClosedInstrumentPreflightReport.model_validate_json(
        (preflight_dir / "report.json").read_text(encoding="utf-8")
    )
    contract = BudgetClosedInstrumentContract.model_validate_json(
        (preflight_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = BudgetClosedInstrumentJobManifest.model_validate_json(
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
        raise ValueError("online execution did not receive the authoritative v26.83 preflight")
    _validate_detail_files(preflight, preflight_dir)

    task_report = BudgetClosedInstrumentPopulationReport.model_validate_json(
        (task_source_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        task_report.report_id != EXPECTED_TASK_SOURCE_REPORT_ID
        or task_report.report_id != contract.task_source_report_id
        or _sha256(task_source_dir / "report.json") != contract.task_source_report_sha256
    ):
        raise ValueError("online execution received another v26.82 task source")
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
    provisional_binding = BudgetClosedExecutionBinding.model_construct(
        binding_id="pending", **binding_values
    )
    execution_binding = BudgetClosedExecutionBinding(
        binding_id=budget_closed_execution_binding_id(provisional_binding),
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
        prefix="finance_v26_budget_closed_provider_call:",
    )


def _provider_call_path(
    output_dir: Path,
    job: BudgetClosedInstrumentJob,
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


def _raw_execution_path(output_dir: Path, job: BudgetClosedInstrumentJob) -> Path:
    task_hash = hashlib.sha256(job.task_package_id.encode("utf-8")).hexdigest()[:16]
    return output_dir / "raw_execution" / task_hash / f"replicate_{job.replicate_index}.json"


class _RawFirstJournalClient:
    """Persist each returned Provider payload before Usage validation and Agent scoring."""

    def __init__(
        self,
        delegate: Any,
        *,
        execution_binding: BudgetClosedExecutionBinding,
        job: BudgetClosedInstrumentJob,
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
            "provider_telemetry": telemetry,
        }
        provisional = BudgetClosedRawProviderCall.model_construct(artifact_id="pending", **values)
        artifact = BudgetClosedRawProviderCall(
            artifact_id=budget_closed_raw_provider_call_id(provisional),
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


class _AttemptPromptJournalClient:
    """Retain the denied request Prompt as well as every actual Provider Prompt."""

    def __init__(self, delegate: BudgetClosedJsonClient) -> None:
        self._delegate = delegate
        self.prompts: list[str] = []

    @property
    def config(self) -> AgentModelConfig:
        return self._delegate.config

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        self.prompts.append(prompt)
        return self._delegate.complete_json(prompt)


def _provider_telemetry_equal_before_host_augmentation(
    raw: ModelCallTelemetry,
    host: ModelCallTelemetry,
) -> bool:
    raw_payload = raw.model_dump(mode="json")
    host_payload = host.model_dump(mode="json")
    if raw_payload == host_payload:
        return True
    response_shape = dict(host_payload["response_shape"])
    prompt_component_bytes = response_shape.pop("prompt_component_bytes", None)
    host_payload["response_shape"] = response_shape
    return prompt_component_bytes is not None and raw_payload == host_payload


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


def _load_raw_execution(path: Path) -> BudgetClosedRawExecution:
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
    return BudgetClosedRawExecution.model_validate(payload)


def _execute_and_persist_raw(
    *,
    job: BudgetClosedInstrumentJob,
    contract: BudgetClosedInstrumentContract,
    execution_binding: BudgetClosedExecutionBinding,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    client: Any | None,
    output_dir: Path,
) -> BudgetClosedRawExecution:
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
        raise ValueError("pending budget-closed Job has no model client")
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

    recording_client = _RawFirstJournalClient(
        client,
        execution_binding=execution_binding,
        job=job,
        output_dir=output_dir,
    )
    budget_client = BudgetClosedJsonClient(
        recording_client,
        contract.provider_token_budget_contract,
    )
    attempt_client = _AttemptPromptJournalClient(budget_client)
    result: IterativeAgentSolveResult | None = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    execution_error: str | None = None
    execution_kind: ExecutionKind = "unexpected_execution_failure"
    try:
        result = IterativeAgentSolver(
            attempt_client,
            mode="autonomous_agent",
            maximum_total_tokens=contract.provider_token_budget_contract.maximum_total_tokens,
            protocol_profile=IterativeAgentProtocolProfile(),
        ).solve_with_audit(record.task_package.task.public, _runtime(record, environment))
        execution_kind = "completed_trajectory"
    except LLMClientError as exc:
        failure_artifact = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact)
            else None
        )
        execution_error = _safe_error(exc)
    except Exception as exc:
        execution_error = _safe_error(exc)

    budget_audit = budget_client.audit()
    if result is not None:
        host_telemetry = result.audit.telemetry
        host_prompts = result.audit.model_request_prompts
    elif failure_artifact is not None:
        host_telemetry = failure_artifact.telemetry
        host_prompts = failure_artifact.model_request_prompts
    else:
        host_telemetry = tuple(recording_client.telemetry)
        host_prompts = tuple(recording_client.prompts)
    provider_telemetry = tuple(recording_client.telemetry)
    provider_prompts = tuple(recording_client.prompts)
    if (
        host_prompts != provider_prompts
        or len(host_telemetry) != len(provider_telemetry)
        or any(
            not _provider_telemetry_equal_before_host_augmentation(raw, host)
            for raw, host in zip(provider_telemetry, host_telemetry, strict=True)
        )
    ):
        raise ValueError("raw Provider journal differs beyond Host telemetry augmentation")
    if result is None:
        if budget_audit.no_call_terminal is not None:
            execution_kind = "typed_budget_no_call"
        elif budget_audit.status == "failed":
            execution_kind = "provider_budget_contract_failure"
        elif (
            failure_artifact is not None
            and provider_telemetry
            and all(item.http_success for item in provider_telemetry)
        ):
            execution_kind = "captured_model_contract_failure"
        elif failure_artifact is not None:
            execution_kind = "provider_or_runtime_failure"
    values = {
        "execution_binding_id": execution_binding.binding_id,
        "job": job,
        "task_record_id": record.record_id,
        "task_package_id": record.task_package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "replay_binding_contract_id": job.replay_binding_contract_id,
        "execution_kind": execution_kind,
        "provider_call_artifacts": tuple(recording_client.descriptors),
        "provider_call_ids": tuple(
            provider_call_id(job.job_id, index, item)
            for index, item in enumerate(provider_telemetry)
        ),
        "provider_telemetry": provider_telemetry,
        "provider_request_prompts": provider_prompts,
        "host_telemetry": tuple(host_telemetry),
        "host_request_prompts": tuple(host_prompts),
        "attempted_model_prompts": tuple(attempt_client.prompts),
        "provider_budget_audit": budget_audit,
        "solve_result": result,
        "failure_artifact": failure_artifact,
        "execution_error": execution_error,
        "recursive_noninterference_passed": _recursive_noninterference(
            result=result,
            failure_artifact=failure_artifact,
            prompts=host_prompts,
        ),
    }
    provisional = BudgetClosedRawExecution.model_construct(artifact_id="pending", **values)
    artifact = BudgetClosedRawExecution(
        artifact_id=budget_closed_raw_execution_id(provisional),
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


def _observations_from_raw(raw: BudgetClosedRawExecution) -> tuple[AgentToolObservation, ...]:
    if raw.solve_result is not None:
        return raw.solve_result.observations
    if raw.failure_artifact is not None:
        return raw.failure_artifact.observations
    return ()


def _compute_non_replay_gate_audit(
    *,
    execution_binding: BudgetClosedExecutionBinding,
    job: BudgetClosedInstrumentJob,
    record: OperationalTaskRecord,
    raw: BudgetClosedRawExecution,
    replay: AuthorityPreservingReplayResult,
    mechanism: MechanismEstimandOutcome,
    verification: AuthorityPreservingVerificationReport | None,
) -> BudgetClosedNonReplayGateAudit:
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
    checks = dict(
        sorted(
            {
                "model_input_noninterference_passed": raw.recursive_noninterference_passed,
                "only_allowed_tools": {item.call.tool_id for item in observations}
                <= set(record.task_package.tool_closure.allowed_tool_ids),
                "operation_lineage_complete": program_complete
                and necessary <= set(operation_lineage),
                "evidence_support_complete": selected_support is not None,
                "verification_complete": necessary <= set(verification_support),
                "answer_projection_complete": (
                    normalized_answer == record.projected_expected_output
                ),
                "citation_complete": citation_support is not None,
                "mechanism_complete": mechanism.success,
                "no_postcompletion_violation": no_postcompletion,
            }.items()
        )
    )
    agreement = None
    if verification is not None:
        agreement = checks == dict(
            sorted(
                (key, value)
                for key, value in verification.checks.items()
                if key != "runtime_replay_passed"
            )
        )
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
    provisional = BudgetClosedNonReplayGateAudit.model_construct(audit_id="pending", **values)
    return BudgetClosedNonReplayGateAudit(
        audit_id=budget_closed_non_replay_gate_audit_id(provisional),
        **values,
    )


def _mechanism_outcome(
    record: OperationalTaskRecord,
    raw: BudgetClosedRawExecution,
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
    contract: BudgetClosedInstrumentContract,
    raw: BudgetClosedRawExecution,
) -> tuple[int, bool, Decimal, bool, bool]:
    audit = raw.provider_budget_audit
    total_tokens = audit.cumulative_provider_tokens
    usage_complete = audit.status == "passed" and all(item.passed for item in audit.usage_records)
    estimated_cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    exact_model = all(
        item.model_selected == contract.model_id
        and item.model_requested == contract.model_id
        and item.response_model == contract.model_id
        and item.http_success
        for item in raw.provider_telemetry
    )
    fallback_used = any(item.fallback_used for item in raw.provider_telemetry)
    return total_tokens, usage_complete, estimated_cost, exact_model, fallback_used


def _no_call_phase(raw: BudgetClosedRawExecution) -> NoCallPhase | None:
    terminal = raw.provider_budget_audit.no_call_terminal
    if terminal is None:
        return None
    certificate = raw.provider_budget_audit.certificates[-1]
    if certificate.request_index == 0:
        return "initial_prompt_unfit"
    if certificate.request_kind == "final_answer" and (
        certificate.denial_reason == "required_reserve_not_available"
    ):
        return "repair_reserve_unavailable"
    if certificate.request_kind == "contract_repair" and (
        certificate.repaired_request_kind != "final_answer"
        and certificate.denial_reason == "required_reserve_not_available"
    ):
        return "final_reserve_unavailable"
    return "mid_rollout_budget_exhausted"


def _raw_reference(
    output_dir: Path,
    job: BudgetClosedInstrumentJob,
) -> tuple[str, str]:
    path = _raw_execution_path(output_dir, job)
    return str(path.resolve()), _sha256(path)


def _replay_failures(replay: AuthorityPreservingReplayResult | None) -> tuple[str, ...]:
    if replay is None:
        return ("runtime_replay:not_computed",)
    if replay.passed:
        return ()
    return tuple(
        sorted(
            {
                item if item.startswith("runtime_replay:") else f"runtime_replay:{item}"
                for item in replay.failure_ids
            }
        )
    ) or ("runtime_replay:failed_without_attribution",)


def _score_raw_execution(
    *,
    job: BudgetClosedInstrumentJob,
    contract: BudgetClosedInstrumentContract,
    execution_binding: BudgetClosedExecutionBinding,
    replay_contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    raw: BudgetClosedRawExecution,
    output_dir: Path,
) -> BudgetClosedInstrumentRollout:
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
        raise ValueError("budget-closed Verifier v2 returned another Replay result")
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
    resource_failures = raw.provider_budget_audit.contract_failure_ids
    base_channels = build_instrument_failure_channels(
        resource_failures=resource_failures,
    )
    completed_score: CompletedTrajectoryScore | None = None
    if raw.solve_result is not None:
        completed_score = score_completed_trajectory(
            trajectory=raw.solve_result.trajectory,
            source_kind="model_generated",
            replay_result_id=replay.replay_id,
            replay_passed=replay.passed,
            non_replay_checks=non_replay.checks,
            independent_valid=bool(verification and verification.valid),
            resource_budget_audit_id=raw.provider_budget_audit.audit_id,
            resource_budget_status=(
                "passed" if raw.provider_budget_audit.status == "passed" else "failed"
            ),
            base_failure_channels=base_channels,
        )
        terminal = cast(
            TerminalCategory,
            {
                "valid_trajectory": "model_valid_trajectory",
                "invalid_trajectory": "model_invalid_trajectory",
                "instrument_failure": "instrument_failure",
            }[completed_score.core_terminal],
        )
        core_terminal = cast(CoreTerminal, completed_score.core_terminal)
        channels = completed_score.failure_channels
        failure_attribution: dict[str, Any] | None = (
            None
            if terminal == "model_valid_trajectory"
            else {
                "category": (
                    "runtime_verifier_replay_mismatch"
                    if not replay.passed
                    else "independent_verification_failed"
                ),
                "failed_check_ids": (
                    list(replay.failure_ids)
                    if not replay.passed
                    else sorted(
                        key
                        for key, passed in cast(
                            AuthorityPreservingVerificationReport, verification
                        ).checks.items()
                        if not passed
                    )
                ),
            }
        )
    else:
        channels = build_instrument_failure_channels(
            runtime_replay_failures=_replay_failures(replay),
            resource_failures=resource_failures,
        )
        if raw.execution_kind == "typed_budget_no_call":
            terminal = "budget_exhausted_no_call"
            core_terminal = "model_invalid_resource_terminal"
            failure_attribution = {
                "category": "budget_exhausted_no_call",
                "reason_code": cast(
                    ProviderBudgetNoCallTerminal,
                    raw.provider_budget_audit.no_call_terminal,
                ).reason_code,
                "phase": _no_call_phase(raw),
            }
        elif raw.execution_kind == "captured_model_contract_failure":
            terminal = "model_invalid_trajectory"
            core_terminal = "invalid_trajectory"
            failure_attribution = {
                "category": "model_contract_failure",
                "reason": raw.execution_error,
            }
        elif raw.execution_kind == "provider_or_runtime_failure":
            terminal = "runtime_failure"
            core_terminal = "runtime_failure"
            failure_attribution = {
                "category": "runtime_failure",
                "reason": raw.execution_error,
            }
        else:
            terminal = "instrument_failure"
            core_terminal = "instrument_failure"
            if raw.execution_kind == "provider_budget_contract_failure":
                channels = build_instrument_failure_channels(
                    runtime_replay_failures=_replay_failures(replay),
                    resource_failures=(
                        resource_failures
                        or ("resource_budget:provider_contract_failed_without_id",)
                    ),
                )
            else:
                channels = build_instrument_failure_channels(
                    runtime_replay_failures=_replay_failures(replay),
                    scoring_core_failures=("scoring_core:unexpected_execution_failure",),
                    resource_failures=resource_failures,
                )
            failure_attribution = {
                "category": raw.execution_kind,
                "reason": raw.execution_error,
            }
    total_tokens, usage_complete, estimated_cost, exact_model, fallback_used = _telemetry_summary(
        contract, raw
    )
    trajectory = raw.solve_result.trajectory if raw.solve_result is not None else None
    raw_uri, raw_sha = _raw_reference(output_dir, job)
    no_call_terminal = raw.provider_budget_audit.no_call_terminal
    values = {
        "execution_binding_id": execution_binding.binding_id,
        "job_id": job.job_id,
        "task_record_id": job.task_record_id,
        "task_package_id": job.task_package_id,
        "environment_manifest_id": job.environment_manifest_id,
        "replay_binding_contract_id": job.replay_binding_contract_id,
        "mechanism_id": job.mechanism_id,
        "replicate_index": job.replicate_index,
        "terminal_category": terminal,
        "core_terminal": core_terminal,
        "provider_call_ids": raw.provider_call_ids,
        "provider_call_count": len(raw.provider_call_ids),
        "provider_total_tokens": total_tokens,
        "provider_usage_complete": usage_complete,
        "estimated_cost_usd": str(estimated_cost),
        "exact_requested_model": exact_model,
        "fallback_used": fallback_used,
        "actual_prompt_hashes": tuple(_sha256_text(item) for item in raw.provider_request_prompts),
        "attempted_prompt_hashes": tuple(
            _sha256_text(item) for item in raw.attempted_model_prompts
        ),
        "recursive_noninterference_passed": raw.recursive_noninterference_passed,
        "observation_count": len(observations),
        "replay_result": replay,
        "non_replay_gate_audit": non_replay,
        "verification": verification,
        "completed_trajectory_score": completed_score,
        "failure_channels": channels,
        "mechanism_estimand": mechanism,
        "trajectory_id": trajectory.trajectory_id if trajectory is not None else None,
        "no_call_terminal": no_call_terminal,
        "no_call_phase": _no_call_phase(raw),
        "model_generated": bool(raw.provider_call_ids),
        "instrument_admitted": (
            channels.instrument_gate_passed
            and channels.report_complete
            and terminal not in {"runtime_failure", "instrument_failure"}
        ),
        "raw_execution_artifact_uri": raw_uri,
        "raw_execution_artifact_sha256": raw_sha,
        "raw_provider_call_artifacts": raw.provider_call_artifacts,
        "failure_attribution": failure_attribution,
    }
    provisional = BudgetClosedInstrumentRollout.model_construct(rollout_id="pending", **values)
    return BudgetClosedInstrumentRollout(
        rollout_id=budget_closed_instrument_rollout_id(provisional),
        **values,
    )


def _score_with_failure_capture(
    *,
    job: BudgetClosedInstrumentJob,
    contract: BudgetClosedInstrumentContract,
    execution_binding: BudgetClosedExecutionBinding,
    replay_contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    raw: BudgetClosedRawExecution,
    output_dir: Path,
) -> BudgetClosedInstrumentRollout:
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
        channels = build_instrument_failure_channels(
            runtime_replay_failures=_replay_failures(replay),
            scoring_core_failures=(
                "scoring_core:"
                + type(exc).__name__.casefold()
                + ":"
                + canonical_hash(str(exc), prefix="scoring_core_error:").split(":", 1)[-1],
            ),
            resource_failures=raw.provider_budget_audit.contract_failure_ids,
        )
        total_tokens, usage_complete, estimated_cost, exact_model, fallback_used = (
            _telemetry_summary(contract, raw)
        )
        raw_uri, raw_sha = _raw_reference(output_dir, job)
        no_call_terminal = raw.provider_budget_audit.no_call_terminal
        terminal: TerminalCategory = (
            "budget_exhausted_no_call" if no_call_terminal is not None else "instrument_failure"
        )
        core_terminal: CoreTerminal = (
            "model_invalid_resource_terminal"
            if no_call_terminal is not None
            else "instrument_failure"
        )
        values = {
            "execution_binding_id": execution_binding.binding_id,
            "job_id": job.job_id,
            "task_record_id": job.task_record_id,
            "task_package_id": job.task_package_id,
            "environment_manifest_id": job.environment_manifest_id,
            "replay_binding_contract_id": job.replay_binding_contract_id,
            "mechanism_id": job.mechanism_id,
            "replicate_index": job.replicate_index,
            "terminal_category": terminal,
            "core_terminal": core_terminal,
            "provider_call_ids": raw.provider_call_ids,
            "provider_call_count": len(raw.provider_call_ids),
            "provider_total_tokens": total_tokens,
            "provider_usage_complete": usage_complete,
            "estimated_cost_usd": str(estimated_cost),
            "exact_requested_model": exact_model,
            "fallback_used": fallback_used,
            "actual_prompt_hashes": tuple(
                _sha256_text(item) for item in raw.provider_request_prompts
            ),
            "attempted_prompt_hashes": tuple(
                _sha256_text(item) for item in raw.attempted_model_prompts
            ),
            "recursive_noninterference_passed": raw.recursive_noninterference_passed,
            "observation_count": len(observations),
            "replay_result": replay,
            "non_replay_gate_audit": None,
            "verification": None,
            "completed_trajectory_score": None,
            "failure_channels": channels,
            "mechanism_estimand": mechanism,
            "trajectory_id": (
                raw.solve_result.trajectory.trajectory_id if raw.solve_result is not None else None
            ),
            "no_call_terminal": no_call_terminal,
            "no_call_phase": _no_call_phase(raw),
            "model_generated": bool(raw.provider_call_ids),
            "instrument_admitted": False,
            "raw_execution_artifact_uri": raw_uri,
            "raw_execution_artifact_sha256": raw_sha,
            "raw_provider_call_artifacts": raw.provider_call_artifacts,
            "failure_attribution": {
                "category": "online_scoring_core_failure",
                "reason": _safe_error(exc),
            },
        }
        provisional = BudgetClosedInstrumentRollout.model_construct(rollout_id="pending", **values)
        return BudgetClosedInstrumentRollout(
            rollout_id=budget_closed_instrument_rollout_id(provisional),
            **values,
        )


def _raw_stop_payload(raw: BudgetClosedRawExecution) -> dict[str, Any]:
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
    rollout: BudgetClosedInstrumentRollout,
    raw: BudgetClosedRawExecution,
    record: OperationalTaskRecord,
    binding: VerifierV2TaskReplayBinding,
) -> BudgetClosedRolloutDiagnostic:
    observations = _observations_from_raw(raw)
    progress = public_operation_progress(record.task_package.task.public, observations)
    if progress is None:
        raise ValueError("budget-closed Instrument lost its public Operation contract")
    prompts = raw.attempted_model_prompts
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
    score = rollout.completed_trajectory_score
    values = {
        "rollout_id": rollout.rollout_id,
        "job_id": rollout.job_id,
        "task_package_id": rollout.task_package_id,
        "mechanism_id": rollout.mechanism_id,
        "replicate_index": rollout.replicate_index,
        "terminal_category": rollout.terminal_category,
        "core_terminal": rollout.core_terminal,
        "provider_call_count": rollout.provider_call_count,
        "provider_total_tokens": rollout.provider_total_tokens,
        "budget_certificate_count": len(raw.provider_budget_audit.certificates),
        "no_call_phase": rollout.no_call_phase,
        "replay_passed": bool(replay and replay.passed),
        "replay_failure_ids": (
            replay.failure_ids if replay is not None else ("runtime_replay:not_computed",)
        ),
        "non_replay_gate_audit_present": non_replay is not None,
        "complete_verifier_gate_agreement": (
            non_replay.verifier_report_non_replay_agreement
            if non_replay is not None and non_replay.complete_solve_result
            else None
        ),
        "shared_completed_score_present": score is not None,
        "schema_closed_sidecar_passed": (
            score.trace_sidecar is not None if score is not None else None
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
        "failure_channel_id": rollout.failure_channels.channel_id,
        "instrument_admitted": rollout.instrument_admitted,
    }
    provisional = BudgetClosedRolloutDiagnostic.model_construct(diagnostic_id="pending", **values)
    return BudgetClosedRolloutDiagnostic(
        diagnostic_id=budget_closed_rollout_diagnostic_id(provisional),
        **values,
    )


def _raw_lineage_audit(
    *,
    execution_binding: BudgetClosedExecutionBinding,
    manifest: BudgetClosedInstrumentJobManifest,
    rollouts: Sequence[BudgetClosedInstrumentRollout],
    output_dir: Path,
) -> BudgetClosedRawLineageAudit:
    job_by_id = {item.job_id: item for item in manifest.jobs}
    byte_pass = identity_pass = before_pass = provider_pass = 0
    budget_pass = telemetry_pass = prompt_pass = 0
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
                artifact = BudgetClosedRawProviderCall.model_validate_json(
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
            if len(provider_artifacts) != rollout.provider_call_count:
                raise ValueError("raw Provider Artifact denominator changed")
            provider_pass += 1
            provider_artifact_count += len(provider_artifacts)
            audit = raw.provider_budget_audit
            if (
                audit.provider_call_count == rollout.provider_call_count
                and audit.permitted_request_count == rollout.provider_call_count
                and len(audit.certificates) == len(raw.attempted_model_prompts)
                and tuple(
                    item.certificate_id for item in audit.certificates[: len(audit.usage_records)]
                )
                == tuple(item.certificate_id for item in audit.usage_records)
            ):
                budget_pass += 1
            else:
                raise ValueError("raw Provider budget binding changed")
            if all(
                _provider_telemetry_equal_before_host_augmentation(provider, host)
                for provider, host in zip(
                    raw.provider_telemetry,
                    raw.host_telemetry,
                    strict=True,
                )
            ):
                telemetry_pass += 1
            else:
                raise ValueError("raw Provider and Host telemetry changed")
            if (
                tuple(_sha256_text(item) for item in raw.provider_request_prompts)
                == rollout.actual_prompt_hashes
                and tuple(_sha256_text(item) for item in raw.attempted_model_prompts)
                == rollout.attempted_prompt_hashes
                and tuple(item.provider_call_id for item in provider_artifacts)
                == rollout.provider_call_ids
            ):
                prompt_pass += 1
            else:
                raise ValueError("raw Prompt or Provider identity changed")
            provider_ids.extend(rollout.provider_call_ids)
        except Exception as exc:
            failures.append(
                "raw_lineage:"
                + canonical_hash(
                    {"job_id": rollout.job_id, "error": _safe_error(exc)},
                    prefix="raw_lineage_failure:",
                ).split(":", 1)[-1]
            )
    duplicates = tuple(sorted(key for key, count in Counter(provider_ids).items() if count > 1))
    counts = (
        byte_pass,
        identity_pass,
        before_pass,
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
        "execution_binding_id": execution_binding.binding_id,
        "observed_rollout_count": len(rollouts),
        "raw_execution_byte_pass_count": byte_pass,
        "raw_execution_identity_pass_count": identity_pass,
        "raw_before_scoring_pass_count": before_pass,
        "provider_capture_pass_count": provider_pass,
        "provider_budget_binding_pass_count": budget_pass,
        "provider_host_telemetry_pass_count": telemetry_pass,
        "actual_prompt_binding_pass_count": prompt_pass,
        "raw_provider_call_artifact_count": provider_artifact_count,
        "provider_call_ids_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "raw_lineage_failure_ids": tuple(sorted(set(failures))),
        "status": (
            "passed"
            if complete and not duplicates and not failures
            else "partial"
            if partial and not duplicates and not failures
            else "failed"
        ),
    }
    provisional = BudgetClosedRawLineageAudit.model_construct(audit_id="pending", **values)
    return BudgetClosedRawLineageAudit(
        audit_id=budget_closed_raw_lineage_audit_id(provisional),
        **values,
    )


def _mechanism_summaries(
    diagnostics: Sequence[BudgetClosedRolloutDiagnostic],
) -> tuple[BudgetClosedMechanismSummary, ...]:
    output = []
    for mechanism in TARGET_MECHANISMS:
        rows = tuple(item for item in diagnostics if item.mechanism_id == mechanism)
        output.append(
            BudgetClosedMechanismSummary(
                mechanism_id=mechanism,
                instrument_admitted_count=sum(item.instrument_admitted for item in rows),
                model_outcome_count=sum(
                    item.terminal_category
                    in {
                        "model_valid_trajectory",
                        "model_invalid_trajectory",
                        "budget_exhausted_no_call",
                    }
                    for item in rows
                ),
                no_call_count=sum(
                    item.terminal_category == "budget_exhausted_no_call" for item in rows
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
    diagnostics: Sequence[BudgetClosedRolloutDiagnostic],
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
    execution_binding: BudgetClosedExecutionBinding,
    contract: BudgetClosedInstrumentContract,
    discovered_models: Sequence[str],
    rollouts: Sequence[BudgetClosedInstrumentRollout],
    diagnostics: Sequence[BudgetClosedRolloutDiagnostic],
    raw_audit: BudgetClosedRawLineageAudit,
) -> BudgetClosedInstrumentRequalificationReport:
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
    total_cost = sum(
        (Decimal(item.estimated_cost_usd) for item in rollouts),
        Decimal("0"),
    )
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
    instrument_ready = bool(
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
    status: Literal["partial", "passed", "blocked"] = (
        "partial"
        if len(rollouts) < EXPECTED_JOB_COUNT
        else "passed"
        if instrument_ready
        else "blocked"
    )
    next_stage = (
        "frozen_budget_closed_instrument_resume_only"
        if status == "partial"
        else "fresh_capability_and_reachability_protocol_design_only"
        if status == "passed"
        else "budget_closed_online_resource_failure_audit_only"
        if not resource_budget_passed
        else "budget_closed_online_instrument_failure_audit_only"
    )
    unique_sequences, effective_sequences, maximum_sequence_share = _trace_diversity(diagnostics)
    values = {
        "execution_run_id": execution_binding.execution_run_id,
        "execution_binding_id": execution_binding.binding_id,
        "discovered_models": tuple(discovered_models),
        "completed_rollout_count": len(rollouts),
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
        "provider_call_count": sum(item.provider_call_count for item in rollouts),
        "provider_total_tokens": sum(item.provider_total_tokens for item in rollouts),
        "estimated_cost_usd": str(total_cost),
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
    provisional = BudgetClosedInstrumentRequalificationReport.model_construct(
        report_id="pending", **values
    )
    return BudgetClosedInstrumentRequalificationReport(
        report_id=budget_closed_requalification_report_id(provisional),
        **values,
    )


def _load_checkpoint(
    *,
    path: Path,
    execution_binding: BudgetClosedExecutionBinding,
    manifest: BudgetClosedInstrumentJobManifest,
) -> tuple[BudgetClosedInstrumentRollout, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        BudgetClosedInstrumentRollout.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("budget-closed checkpoint contains duplicate Job identities")
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
            raise ValueError("budget-closed checkpoint differs from a frozen Job")
        if _sha256(Path(item.raw_execution_artifact_uri)) != item.raw_execution_artifact_sha256:
            raise ValueError("budget-closed checkpoint raw Artifact hash changed")
    return rows


def _run_one_job(
    *,
    job: BudgetClosedInstrumentJob,
    prepared: _PreparedInputs,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    client: Any | None,
    output_dir: Path,
) -> BudgetClosedInstrumentRollout:
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


def run_budget_closed_instrument_requalification(
    *,
    execution_run_id: str,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    workers: int,
    client_factory: Callable[[AgentModelConfig], Any] = OpenAICompatibleJsonClient,
) -> BudgetClosedInstrumentRequalificationReport:
    prepared = prepare_budget_closed_instrument_execution(
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
        raise ValueError("completed budget-closed report exists while Jobs remain pending")
    model_config = AgentModelConfig.model_validate(prepared.contract.model_invocation_config)
    client: Any | None = None
    if model_pending_jobs:
        client = client_factory(model_config)
        discovered_models = tuple(client.discover_models())
        if prepared.contract.model_id not in discovered_models:
            raise ValueError("frozen DeepSeek V4-Flash identity is unavailable")
    elif prior_report_path.exists():
        prior_report = BudgetClosedInstrumentRequalificationReport.model_validate_json(
            prior_report_path.read_text(encoding="utf-8")
        )
        if (
            prior_report.execution_binding_id != prepared.execution_binding.binding_id
            or prior_report.contract_id != prepared.contract.contract_id
            or prior_report.job_manifest_id != prepared.manifest.manifest_id
        ):
            raise ValueError("completed budget-closed report crosses frozen inputs")
        discovered_models = prior_report.discovered_models
    else:
        discovered_models = (prepared.contract.model_id,)
    print(
        f"[v26.84] resuming {len(completed)}/{EXPECTED_JOB_COUNT}; "
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
                    "budget-closed Instrument worker failed; raw-only recovery is required"
                ) from exc
            with lock:
                if rollout.job_id in completed:
                    raise ValueError("budget-closed runner produced a duplicate Job result")
                completed[rollout.job_id] = rollout
                _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
            if len(completed) % max(1, workers) == 0 or len(completed) == EXPECTED_JOB_COUNT:
                print(f"[v26.84] completed {len(completed)}/{EXPECTED_JOB_COUNT}", flush=True)
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
    raw_audit = _raw_lineage_audit(
        execution_binding=prepared.execution_binding,
        manifest=prepared.manifest,
        rollouts=ordered,
        output_dir=output_dir,
    )
    report = _make_report(
        execution_binding=prepared.execution_binding,
        contract=prepared.contract,
        discovered_models=discovered_models,
        rollouts=ordered,
        diagnostics=diagnostics,
        raw_audit=raw_audit,
    )
    raw_by_job = {
        item.job_id: _load_raw_execution(Path(item.raw_execution_artifact_uri)) for item in ordered
    }
    _write_json_atomic(
        output_dir / "instrument_rollouts.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "provider_budget_audits.json",
        [raw_by_job[item.job_id].provider_budget_audit.model_dump(mode="json") for item in ordered],
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
            cast(BudgetClosedNonReplayGateAudit, item.non_replay_gate_audit).model_dump(mode="json")
            for item in ordered
            if item.non_replay_gate_audit is not None
        ],
    )
    _write_json_atomic(
        output_dir / "completed_trajectory_scores.json",
        [
            cast(CompletedTrajectoryScore, item.completed_trajectory_score).model_dump(mode="json")
            for item in ordered
            if item.completed_trajectory_score is not None
        ],
    )
    _write_json_atomic(
        output_dir / "failure_channels.json",
        [item.failure_channels.model_dump(mode="json") for item in ordered],
    )
    _write_json_atomic(
        output_dir / "typed_no_call_terminals.json",
        [
            cast(ProviderBudgetNoCallTerminal, item.no_call_terminal).model_dump(mode="json")
            for item in ordered
            if item.no_call_terminal is not None
        ],
    )
    _write_json_atomic(
        output_dir / "rollout_diagnostics.json",
        [item.model_dump(mode="json") for item in diagnostics],
    )
    _write_json_atomic(
        output_dir / "raw_lineage_audit.json",
        raw_audit.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "mechanism_summaries.json",
        [item.model_dump(mode="json") for item in report.mechanism_summaries],
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def budget_closed_online_source_replay_audit_id(
    value: BudgetClosedOnlineSourceReplayAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_closed_online_source_replay:",
    )


def budget_closed_execution_binding_id(value: BudgetClosedExecutionBinding) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"binding_id"}),
        prefix="finance_v26_budget_closed_instrument_execution_binding:",
    )


def budget_closed_raw_provider_call_id(value: BudgetClosedRawProviderCall) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="finance_v26_budget_closed_raw_provider_call:",
    )


def budget_closed_raw_execution_id(value: BudgetClosedRawExecution) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="finance_v26_budget_closed_raw_execution:",
    )


def budget_closed_non_replay_gate_audit_id(
    value: BudgetClosedNonReplayGateAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_closed_non_replay_gate_audit:",
    )


def budget_closed_instrument_rollout_id(value: BudgetClosedInstrumentRollout) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"rollout_id"}),
        prefix="finance_v26_budget_closed_instrument_rollout:",
    )


def budget_closed_rollout_diagnostic_id(value: BudgetClosedRolloutDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_budget_closed_instrument_diagnostic:",
    )


def budget_closed_raw_lineage_audit_id(value: BudgetClosedRawLineageAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_closed_raw_lineage_audit:",
    )


def budget_closed_requalification_report_id(
    value: BudgetClosedInstrumentRequalificationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_budget_closed_instrument_requalification:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the frozen Finance v26.83 32-job budget-closed Verifier-v2-bound "
            "Instrument requalification"
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
        prepared = prepare_budget_closed_instrument_execution(
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
    report = run_budget_closed_instrument_requalification(
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
