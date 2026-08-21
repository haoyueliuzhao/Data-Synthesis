from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    BudgetQualifiedPathAudit,
    CompactPromptContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
    OperationalTaskRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    EXACT_MODEL_ID,
    EXPECTED_PROVIDER_BUDGET_CONTRACT_ID,
    MODEL_PROFILE_PATH,
    RUNNER_PREFLIGHT_SOURCE_PATH,
    RUNNER_SOURCE_PATH,
    V26_90_DIR,
    V26_94_DIR,
    DetailFile,
    ReplayEntry,
    ThinkingRepairExecutionContract,
    ThinkingRepairExecutionPreflightReport,
    ThinkingRepairOutcomeInterpretationContract,
    ThinkingRepairRawExecution,
    ThinkingRepairRunnerSourceReplayAudit,
    _cell_summaries,
    _JournaledBudgetClient,
    _load_models,
    _make_report,
    _next_transition,
    _raw_execution_path,
    _raw_lineage_audit,
    _raw_provider_path,
    _score_raw_execution,
    _sha256,
    _write_json_atomic,
    execute_thinking_repair_job_raw,
    thinking_repair_execution_contract_id,
    thinking_repair_execution_preflight_report_id,
    thinking_repair_outcome_interpretation_contract_id,
    thinking_repair_runner_source_replay_audit_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_preflight import (  # noqa: E501
    ThinkingCompletionTelemetryRepairPreflightReport,
    ThinkingRepairJob,
    ThinkingRepairManifest,
    ThinkingRepairPathAudit,
    ThinkingRepairSourceReplayAudit,
    ThinkingRepairTaskPackage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    _load_and_replay_verifier_qualification,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import LLMClientError
from trusted_synthesis.runtime.agent.budget_closed import ProviderTokenBudgetContract
from trusted_synthesis.runtime.agent.prospective_thinking import bind_prospective_thinking
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionFailureKind,
    RedactedProviderResponseEnvelope,
    make_prospective_thinking_failure_artifact,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation

V26_95_RUN_ID: Final = (
    "finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821"
)
V26_95_FIXTURE_VERSION: Final = "finance_v26_thinking_repair_runner_fixture.v1"
V26_95_BUDGET_RECOVERY_VERSION: Final = "finance_v26_thinking_repair_budget_recovery_fixture.v1"
V26_95_DESTRUCTIVE_VERSION: Final = "finance_v26_thinking_repair_runner_destructive.v1"
RESCUE_FAILURE_TYPES: tuple[CompletionFailureKind, ...] = (
    "empty_final_content",
    "invalid_json",
    "invalid_response_contract",
    "length_truncated_content",
    "reasoning_only_length_truncation",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DirectRunnerFixtureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    provider_call_count: int = Field(gt=0)
    logical_request_count: int = Field(gt=0)
    observation_count: int = Field(gt=0)
    registered_primary_prompt_match_count: int = Field(gt=0)
    expected_observation_semantic_hashes: tuple[str, ...] = Field(min_length=1)
    observed_observation_semantic_hashes: tuple[str, ...] = Field(min_length=1)
    completed: Literal[True] = True
    observations_match_compiler: Literal[True] = True
    all_primary_prompts_match_registered: Literal[True] = True
    replay_passed: Literal[True] = True
    verifier_valid: Literal[True] = True
    mechanism_success: Literal[True] = True
    rescue_call_count: Literal[0] = 0
    model_plan_call_count: Literal[0] = 0
    provider_calls_are_scripted_fixtures: Literal[True] = True
    empirical_row: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> DirectRunnerFixtureRow:
        if self.expected_observation_semantic_hashes != self.observed_observation_semantic_hashes:
            raise ValueError("v26.95 direct fixture observations changed")
        if self.registered_primary_prompt_match_count != self.logical_request_count:
            raise ValueError("v26.95 direct fixture Prompt replay changed")
        if self.row_id != direct_runner_fixture_row_id(self):
            raise ValueError("v26.95 direct fixture identity mismatch")
        return self


class RescueRunnerFixtureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    failure_type: CompletionFailureKind
    job_id: str = Field(min_length=1)
    provider_call_count: int = Field(gt=1)
    rescue_call_count: Literal[1] = 1
    rescued_usable_request_count: Literal[1] = 1
    completed: Literal[True] = True
    rescue_prompt_strictly_shorter: Literal[True] = True
    previous_final_content_reused: Literal[False] = False
    private_reasoning_reused: Literal[False] = False
    host_action_inserted: Literal[False] = False
    model_plan_call_count: Literal[0] = 0
    provider_calls_are_scripted_fixtures: Literal[True] = True
    empirical_row: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> RescueRunnerFixtureRow:
        if self.row_id != rescue_runner_fixture_row_id(self):
            raise ValueError("v26.95 Rescue fixture identity mismatch")
        return self


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    direct_rows: tuple[DirectRunnerFixtureRow, ...] = Field(
        min_length=32,
        max_length=32,
    )
    rescue_rows: tuple[RescueRunnerFixtureRow, ...] = Field(
        min_length=5,
        max_length=5,
    )
    direct_fixture_job_count: Literal[32] = 32
    direct_fixture_provider_call_count: int = Field(gt=0)
    direct_fixture_logical_request_count: int = Field(gt=0)
    direct_fixture_observation_count: int = Field(gt=0)
    direct_replay_pass_count: Literal[32] = 32
    direct_verifier_valid_count: Literal[32] = 32
    direct_mechanism_success_count: Literal[32] = 32
    direct_cell_summary_count: Literal[12] = 12
    full_aggregate_report_id: str = Field(min_length=1)
    full_aggregate_raw_file_count: Literal[256] = 256
    full_aggregate_provider_call_count: Literal[224] = 224
    full_aggregate_valid_terminal_count: Literal[32] = 32
    full_aggregate_status: Literal["passed"] = "passed"
    rescue_fixture_count: Literal[5] = 5
    global_rescue_exhaustion_terminal: Literal["completion_unusable"] = "completion_unusable"
    global_rescue_exhaustion_rescue_call_count: Literal[1] = 1
    global_rescue_exhaustion_provider_call_count: int = Field(gt=2)
    telemetry_only_terminal: Literal["instrument_failure"] = "instrument_failure"
    telemetry_only_rescue_call_count: Literal[0] = 0
    length_failure_transition_control: Literal[
        "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    ] = "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    telemetry_failure_transition_control: Literal[
        "thinking_response_telemetry_wrapper_repair_only"
    ] = "thinking_response_telemetry_wrapper_repair_only"
    direct_pass_transition_control: Literal["thinking_role_protocol_freeze_only"] = (
        "thinking_role_protocol_freeze_only"
    )
    full_aggregate_transition_control: Literal["thinking_role_protocol_freeze_only"] = (
        "thinking_role_protocol_freeze_only"
    )
    all_direct_paths_completed: Literal[True] = True
    all_direct_observations_match_compiler: Literal[True] = True
    all_registered_primary_prompts_match: Literal[True] = True
    all_rescue_types_recovered: Literal[True] = True
    one_rescue_per_job_enforced: Literal[True] = True
    response_telemetry_failure_not_rescued: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    compiler_fixture_empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_runner_fixture.v1"] = (
        V26_95_FIXTURE_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if tuple(item.failure_type for item in self.rescue_rows) != RESCUE_FAILURE_TYPES:
            raise ValueError("v26.95 Rescue fixture denominator changed")
        if self.audit_id != runner_fixture_audit_id(self):
            raise ValueError("v26.95 Runner fixture identity mismatch")
        return self


class BudgetRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    first_execution_provider_call_count: int = Field(gt=0)
    recovered_artifact_id: str = Field(min_length=1)
    recovery_artifact_id: str = Field(min_length=1)
    raw_only_recovery_provider_call_count: Literal[0] = 0
    raw_only_recovery_byte_identical: Literal[True] = True
    oversized_prompt_denied_before_delegate: Literal[True] = True
    oversized_prompt_delegate_call_count: Literal[0] = 0
    orphan_provider_artifact_rejected: Literal[True] = True
    second_rescue_rejected_by_job_scope: Literal[True] = True
    explicit_request_kind_budget_certificates_passed: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_budget_recovery_fixture.v1"] = (
        V26_95_BUDGET_RECOVERY_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetRecoveryAudit:
        if self.recovered_artifact_id != self.recovery_artifact_id:
            raise ValueError("v26.95 raw-only recovery Artifact changed")
        if self.audit_id != budget_recovery_audit_id(self):
            raise ValueError("v26.95 budget/recovery fixture identity mismatch")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    failure_type: str = Field(min_length=1)


class DestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=16)
    rejected_mutation_count: int = Field(ge=16)
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_thinking_repair_runner_destructive.v1"] = (
        V26_95_DESTRUCTIVE_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructivePreflightAudit:
        if self.rejected_mutation_count != len(self.mutation_results):
            raise ValueError("v26.95 destructive denominator changed")
        if self.audit_id != destructive_preflight_audit_id(self):
            raise ValueError("v26.95 destructive audit identity mismatch")
        return self


class _Inputs(FrozenModel):
    predecessor_report: ThinkingCompletionTelemetryRepairPreflightReport
    predecessor_source_replay: ThinkingRepairSourceReplayAudit
    manifest: ThinkingRepairManifest
    task_packages: tuple[ThinkingRepairTaskPackage, ...]
    path_audits: tuple[ThinkingRepairPathAudit, ...]
    records: tuple[OperationalTaskRecord, ...]
    environments: tuple[AgentToolEnvironmentManifest, ...]
    prompt_contracts: tuple[CompactPromptContract, ...]
    predecessor_paths: tuple[BudgetQualifiedPathAudit, ...]
    trajectories: tuple[Trajectory, ...]
    provider_contract: ProviderTokenBudgetContract
    agent_model_config: AgentModelConfig
    replay_contract: AuthorityPreservingReplayContract


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def direct_runner_fixture_row_id(value: DirectRunnerFixtureRow) -> str:
    return _identity(value, "row_id", "finance_v26_thinking_repair_direct_fixture:")


def rescue_runner_fixture_row_id(value: RescueRunnerFixtureRow) -> str:
    return _identity(value, "row_id", "finance_v26_thinking_repair_rescue_fixture:")


def runner_fixture_audit_id(value: RunnerFixtureAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_thinking_repair_runner_fixture:")


def budget_recovery_audit_id(value: BudgetRecoveryAudit) -> str:
    return _identity(
        value,
        "audit_id",
        "finance_v26_thinking_repair_budget_recovery_fixture:",
    )


def destructive_preflight_audit_id(value: DestructivePreflightAudit) -> str:
    return _identity(
        value,
        "audit_id",
        "finance_v26_thinking_repair_runner_destructive:",
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    return _load_models(path, model)


def _load_inputs(package_root: Path) -> _Inputs:
    predecessor_dir = package_root / V26_94_DIR
    predecessor_report = ThinkingCompletionTelemetryRepairPreflightReport.model_validate_json(
        (predecessor_dir / "report.json").read_text(encoding="utf-8")
    )
    predecessor_source_replay = ThinkingRepairSourceReplayAudit.model_validate_json(
        (predecessor_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    manifest = ThinkingRepairManifest.model_validate_json(
        (predecessor_dir / "thinking_repair_job_manifest.json").read_text(encoding="utf-8")
    )
    task_packages = cast(
        tuple[ThinkingRepairTaskPackage, ...],
        _rows(predecessor_dir / "thinking_repair_task_packages.json", ThinkingRepairTaskPackage),
    )
    path_audits = cast(
        tuple[ThinkingRepairPathAudit, ...],
        _rows(predecessor_dir / "thinking_repair_path_audits.json", ThinkingRepairPathAudit),
    )
    role_dir = package_root / V26_90_DIR
    records = cast(
        tuple[OperationalTaskRecord, ...],
        _rows(role_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    environments = cast(
        tuple[AgentToolEnvironmentManifest, ...],
        _rows(
            role_dir / "tool_environment_manifests.json",
            AgentToolEnvironmentManifest,
        ),
    )
    prompt_contracts = cast(
        tuple[CompactPromptContract, ...],
        _rows(role_dir / "compact_prompt_contracts.json", CompactPromptContract),
    )
    predecessor_paths = cast(
        tuple[BudgetQualifiedPathAudit, ...],
        _rows(role_dir / "budget_qualified_path_audits.json", BudgetQualifiedPathAudit),
    )
    trajectories = cast(
        tuple[Trajectory, ...],
        _rows(role_dir / "compiler_trajectories.json", Trajectory),
    )
    provider_contract = ProviderTokenBudgetContract.model_validate_json(
        (role_dir / "provider_token_budget_contract.json").read_text(encoding="utf-8")
    )
    model_config = AgentModelConfig.model_validate(
        json.loads((package_root / MODEL_PROFILE_PATH).read_text(encoding="utf-8"))["model"]
    )
    thinking_binding = bind_prospective_thinking(model_config)
    _, replay_contract = _load_and_replay_verifier_qualification(
        package_root
        / (
            "artifacts/vtdo_experiment/"
            "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
        ),
        package_root,
    )
    if (
        predecessor_report.report_id
        != (
            "finance_v26_thinking_completion_telemetry_repair_preflight_report:"
            "efae8ea77b8b67a48cb0cfd90559df7fd77b313855a6088ee778ab1dc8926689"
        )
        or predecessor_report.source_replayed_file_count != 485
        or predecessor_source_replay.replayed_file_count != 485
        or manifest.manifest_id != predecessor_report.repair_manifest_id
        or provider_contract.contract_id != EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
        or model_config.public_manifest_hash
        != ("agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1")
        or thinking_binding.binding_id
        != (
            "prospective_thinking_model_binding:"
            "51315bb03b5df2751c0cfada843fc75627c45b544d26efdd9ddac746a780f77d"
        )
    ):
        raise ValueError("v26.95 preflight input identity changed")
    return _Inputs(
        predecessor_report=predecessor_report,
        predecessor_source_replay=predecessor_source_replay,
        manifest=manifest,
        task_packages=task_packages,
        path_audits=path_audits,
        records=records,
        environments=environments,
        prompt_contracts=prompt_contracts,
        predecessor_paths=predecessor_paths,
        trajectories=trajectories,
        provider_contract=provider_contract,
        agent_model_config=model_config,
        replay_contract=replay_contract,
    )


def _build_source_replay(
    *,
    inputs: _Inputs,
    package_root: Path,
) -> ThinkingRepairRunnerSourceReplayAudit:
    entries: list[ReplayEntry] = []

    def add(relative_path: str, source_kind: str, expected: str) -> None:
        path = package_root / relative_path
        observed = _sha256(path)
        entries.append(
            ReplayEntry(
                relative_path=relative_path,
                source_kind=source_kind,
                expected_sha256=expected,
                observed_sha256=observed,
                byte_count=path.stat().st_size,
                passed=expected == observed,
            )
        )

    predecessor_dir = package_root / V26_94_DIR
    report_path = predecessor_dir / "report.json"
    add(
        str(report_path.relative_to(package_root)),
        "v26_94_output",
        _sha256(report_path),
    )
    if len(inputs.predecessor_report.detail_files) != 10:
        raise ValueError("v26.94 output denominator changed")
    for detail in inputs.predecessor_report.detail_files:
        path = predecessor_dir / detail.relative_path
        add(
            str(path.relative_to(package_root)),
            "v26_94_output",
            detail.sha256,
        )
    for entry in inputs.predecessor_source_replay.entries:
        add(
            entry.relative_path,
            "v26_94_replay_binding",
            entry.expected_sha256,
        )
    for relative_path in (RUNNER_SOURCE_PATH, RUNNER_PREFLIGHT_SOURCE_PATH):
        add(
            relative_path,
            "v26_95_implementation",
            _sha256(package_root / relative_path),
        )
    ordered = tuple(sorted(entries, key=lambda item: (item.source_kind, item.relative_path)))
    values = {
        "entries": ordered,
        "replayed_file_count": len(ordered),
        "replay_pass_count": sum(item.passed for item in ordered),
    }
    provisional = ThinkingRepairRunnerSourceReplayAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return ThinkingRepairRunnerSourceReplayAudit(
        audit_id=thinking_repair_runner_source_replay_audit_id(provisional),
        **values,
    )


def _make_interpretation_contract() -> ThinkingRepairOutcomeInterpretationContract:
    provisional = ThinkingRepairOutcomeInterpretationContract.model_construct(contract_id="pending")
    return ThinkingRepairOutcomeInterpretationContract(
        contract_id=thinking_repair_outcome_interpretation_contract_id(provisional)
    )


def _make_execution_contract(
    *,
    inputs: _Inputs,
    replay: ThinkingRepairRunnerSourceReplayAudit,
    interpretation: ThinkingRepairOutcomeInterpretationContract,
    package_root: Path,
) -> ThinkingRepairExecutionContract:
    implementation = tuple(
        ImplementationSourceFile(
            relative_path=path,
            sha256=_sha256(package_root / path),
        )
        for path in sorted((RUNNER_SOURCE_PATH, RUNNER_PREFLIGHT_SOURCE_PATH))
    )
    values = {
        "source_replay_audit_id": replay.audit_id,
        "outcome_interpretation_contract_id": interpretation.contract_id,
        "job_ids": tuple(sorted(item.job_id for item in inputs.manifest.jobs)),
        "runner_implementation_source_files": implementation,
    }
    provisional = ThinkingRepairExecutionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ThinkingRepairExecutionContract(
        contract_id=thinking_repair_execution_contract_id(provisional),
        **values,
    )


class _FixtureEvent(FrozenModel):
    payload: dict[str, Any] | None = None
    failure_type: (
        CompletionFailureKind
        | Literal["response_envelope_invalid", "provider_native_tool_call", "transport"]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_event(self) -> _FixtureEvent:
        if (self.payload is None) == (self.failure_type is None):
            raise ValueError("fixture event requires exactly one payload or failure")
        return self


class _ScriptedProviderClient:
    def __init__(
        self,
        config: AgentModelConfig,
        events: Sequence[_FixtureEvent],
    ) -> None:
        self.config = config
        self._events = tuple(events)
        self.call_count = 0

    def _telemetry(
        self,
        prompt: str,
        *,
        content: str,
        finish_reason: str,
        json_success: bool,
        native_tool: bool = False,
        response_model: str | None = EXACT_MODEL_ID,
        http_success: bool = True,
    ) -> tuple[ModelCallTelemetry, RedactedProviderResponseEnvelope | None]:
        prompt_tokens = max(1, len(prompt.encode("utf-8")) // 4)
        completion_tokens = 64
        total_tokens = prompt_tokens + completion_tokens
        envelope = (
            RedactedProviderResponseEnvelope(
                response_model=response_model or EXACT_MODEL_ID,
                finish_reason=finish_reason,
                public_content_sha256=_sha256_text(content),
                public_content_length=len(content),
                provider_native_tool_call_observed=native_tool,
                reasoning_content_present=True,
                reasoning_content_length=96,
                reasoning_tokens=32,
                completion_tokens=completion_tokens,
            )
            if http_success and response_model is not None
            else None
        )
        response_shape = {
            "provider_native_tool_call_observed": (native_tool if http_success else None),
            "redacted_response_envelope": (
                envelope.model_dump(mode="json")
                if envelope is not None
                else {
                    "response_model": response_model,
                    "finish_reason": finish_reason,
                    "public_content_sha256": _sha256_text(content),
                    "public_content_length": len(content),
                    "provider_native_tool_call_observed": native_tool,
                    "reasoning_content_present": True,
                    "reasoning_content_length": 96,
                    "reasoning_tokens": 32,
                    "completion_tokens": completion_tokens,
                }
            ),
            "response_envelope_captured_before_content_parse": http_success,
            "response_envelope_schema_valid": envelope is not None,
        }
        telemetry = ModelCallTelemetry(
            provider=self.config.provider,
            endpoint_host="fixture.invalid",
            model_requested=EXACT_MODEL_ID,
            model_selected=EXACT_MODEL_ID,
            response_model=response_model,
            request_hash=_sha256_text(prompt),
            response_hash=_sha256_text(content) if http_success else None,
            http_status=200 if http_success else 503,
            http_success=http_success,
            json_contract_success=json_success,
            finish_reason=finish_reason if http_success else None,
            response_content_length=len(content) if http_success else None,
            reasoning_content_present=http_success,
            reasoning_content_length=96 if http_success else None,
            reasoning_tokens=32 if http_success else None,
            prompt_tokens=prompt_tokens if http_success else None,
            completion_tokens=completion_tokens if http_success else None,
            total_tokens=total_tokens if http_success else None,
            estimated_cost=0.0,
            cost_estimation_method="conservative_cache_miss",
            latency_ms=1.0,
            fallback_used=False,
            error_type=None if json_success else "FixtureFailure",
            error_message=None if json_success else "scripted Provider fixture failure",
            response_shape=response_shape,
        )
        return telemetry, envelope

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if self.call_count >= len(self._events):
            raise AssertionError("scripted Provider fixture exhausted")
        event = self._events[self.call_count]
        self.call_count += 1
        if event.payload is not None:
            content = json.dumps(
                event.payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            telemetry, _ = self._telemetry(
                prompt,
                content=content,
                finish_reason="stop",
                json_success=True,
            )
            return event.payload, telemetry
        failure = cast(str, event.failure_type)
        if failure == "transport":
            telemetry, _ = self._telemetry(
                prompt,
                content="",
                finish_reason="",
                json_success=False,
                http_success=False,
            )
            raise LLMClientError("fixture transport failure", (telemetry,))
        if failure == "response_envelope_invalid":
            telemetry, _ = self._telemetry(
                prompt,
                content="",
                finish_reason="stop",
                json_success=False,
                response_model=None,
            )
            artifact = make_prospective_thinking_failure_artifact(
                failure_type="response_envelope_invalid",
                request_hash=telemetry.request_hash,
                response_envelope=None,
            )
            raise LLMClientError(
                "fixture malformed response envelope",
                (telemetry,),
                failure_artifact=artifact,
            )
        content = (
            ""
            if failure
            in {
                "empty_final_content",
                "reasoning_only_length_truncation",
            }
            else '{"truncated":'
        )
        finish_reason = (
            "length"
            if failure in {"length_truncated_content", "reasoning_only_length_truncation"}
            else "stop"
        )
        native_tool = failure == "provider_native_tool_call"
        telemetry, envelope = self._telemetry(
            prompt,
            content=content,
            finish_reason=finish_reason,
            json_success=False,
            native_tool=native_tool,
        )
        artifact = make_prospective_thinking_failure_artifact(
            failure_type=cast(
                Any,
                failure,
            ),
            request_hash=telemetry.request_hash,
            response_envelope=envelope,
        )
        raise LLMClientError(
            f"fixture {failure}",
            (telemetry,),
            failure_artifact=artifact,
        )


def _projection_payloads(trajectory: Trajectory) -> tuple[dict[str, Any], ...]:
    output = [
        {
            "action": "call_tool",
            "tool_id": step.tool_name,
            "arguments": step.tool_input,
        }
        for step in trajectory.steps
        if step.tool_name is not None
    ]
    final = trajectory.final_answer
    result = final.get("result") if isinstance(final, Mapping) else None
    if not isinstance(result, Mapping):
        raise ValueError("v26.95 fixture trajectory lacks a final result")
    output.append({"answer": dict(result)})
    return tuple(output)


def _trajectory_observations(trajectory: Trajectory) -> tuple[AgentToolObservation, ...]:
    return tuple(
        AgentToolObservation.model_validate(step.observation)
        for step in trajectory.steps
        if step.tool_name is not None and step.observation is not None
    )


def _observation_semantic_hash(observation: AgentToolObservation) -> str:
    return canonical_hash(
        observation.model_dump(
            mode="json",
            exclude={"observation_id", "observation_time_hash"},
        ),
        prefix="finance_v26_thinking_repair_observation_semantics:",
    )


def _fixture_bindings(
    inputs: _Inputs,
    job: ThinkingRepairJob,
) -> tuple[
    ThinkingRepairPathAudit,
    OperationalTaskRecord,
    AgentToolEnvironmentManifest,
    CompactPromptContract,
    Trajectory,
]:
    package = next(
        item for item in inputs.task_packages if item.task_package_id == job.repair_task_package_id
    )
    path = next(item for item in inputs.path_audits if item.audit_id == job.repair_path_audit_id)
    predecessor = next(
        item for item in inputs.predecessor_paths if item.audit_id == path.predecessor_path_audit_id
    )
    record = next(
        item for item in inputs.records if item.record_id == package.operational_record_id
    )
    environment = next(
        item for item in inputs.environments if item.manifest_id == package.environment_manifest_id
    )
    prompt = next(
        item
        for item in inputs.prompt_contracts
        if item.contract_id == package.compact_prompt_contract_id
    )
    trajectory = next(
        item
        for item in inputs.trajectories
        if item.trajectory_id == predecessor.compiler_trajectory_id
    )
    return path, record, environment, prompt, trajectory


def _execute_fixture(
    *,
    inputs: _Inputs,
    execution_contract: ThinkingRepairExecutionContract,
    job: ThinkingRepairJob,
    events: Sequence[_FixtureEvent],
    output_dir: Path,
) -> tuple[ThinkingRepairRawExecution, _ScriptedProviderClient, Trajectory]:
    path, record, environment, prompt, trajectory = _fixture_bindings(inputs, job)
    client = _ScriptedProviderClient(inputs.agent_model_config, events)
    raw = execute_thinking_repair_job_raw(
        job=job,
        execution_contract=execution_contract,
        provider_contract=inputs.provider_contract,
        record=record,
        environment=environment,
        prompt_contract=prompt,
        path_audit=path,
        client=client,
        output_dir=output_dir,
    )
    return raw, client, trajectory


def _make_runner_fixture_audit(
    *,
    inputs: _Inputs,
    execution_contract: ThinkingRepairExecutionContract,
) -> RunnerFixtureAudit:
    direct_rows = []
    rescue_rows = []
    direct_results = []
    direct_raw_by_job = {}
    with tempfile.TemporaryDirectory(prefix="v26_95_runner_fixture_") as temporary:
        root = Path(temporary)
        direct_output = root / "direct"
        for job in inputs.manifest.jobs:
            _, _, _, _, trajectory = _fixture_bindings(inputs, job)
            events = tuple(
                _FixtureEvent(payload=payload) for payload in _projection_payloads(trajectory)
            )
            raw, client, _ = _execute_fixture(
                inputs=inputs,
                execution_contract=execution_contract,
                job=job,
                events=events,
                output_dir=direct_output,
            )
            _, record, environment, _, _ = _fixture_bindings(inputs, job)
            scored = _score_raw_execution(
                raw=raw,
                prepared=cast(
                    Any,
                    SimpleNamespace(
                        execution_contract=execution_contract,
                        replay_contract=inputs.replay_contract,
                    ),
                ),
                record=record,
                environment=environment,
                output_dir=direct_output,
            )
            direct_results.append(scored)
            direct_raw_by_job[job.job_id] = raw
            expected = tuple(
                _observation_semantic_hash(item) for item in _trajectory_observations(trajectory)
            )
            observed = tuple(_observation_semantic_hash(item) for item in raw.observations)
            prompt_matches = sum(
                item.registered_primary_prompt_match for item in raw.request_attempts
            )
            values = {
                "job_id": job.job_id,
                "path_audit_id": job.repair_path_audit_id,
                "provider_call_count": client.call_count,
                "logical_request_count": len(raw.logical_requests),
                "observation_count": len(raw.observations),
                "registered_primary_prompt_match_count": prompt_matches,
                "expected_observation_semantic_hashes": expected,
                "observed_observation_semantic_hashes": observed,
                "completed": raw.terminal_disposition == "completed",
                "observations_match_compiler": observed == expected,
                "all_primary_prompts_match_registered": (
                    prompt_matches == len(raw.logical_requests)
                ),
                "replay_passed": bool(scored.replay_result and scored.replay_result.passed),
                "verifier_valid": scored.independent_validity,
                "mechanism_success": scored.mechanism_success,
                "rescue_call_count": raw.rescue_call_count,
            }
            provisional = DirectRunnerFixtureRow.model_construct(row_id="pending", **values)
            direct_rows.append(
                DirectRunnerFixtureRow(
                    row_id=direct_runner_fixture_row_id(provisional),
                    **values,
                )
            )

        representative = inputs.manifest.jobs[0]
        _, _, _, _, trajectory = _fixture_bindings(inputs, representative)
        payloads = _projection_payloads(trajectory)
        for index, failure_type in enumerate(RESCUE_FAILURE_TYPES):
            if failure_type == "invalid_response_contract":
                first = _FixtureEvent(payload={"action": "call_tool"})
            else:
                first = _FixtureEvent(failure_type=failure_type)
            events = (
                first,
                _FixtureEvent(payload=payloads[0]),
                *(_FixtureEvent(payload=item) for item in payloads[1:]),
            )
            raw, client, _ = _execute_fixture(
                inputs=inputs,
                execution_contract=execution_contract,
                job=representative,
                events=events,
                output_dir=root / "rescue" / f"{index:02d}",
            )
            rescue_attempts = tuple(item for item in raw.request_attempts if item.phase == "rescue")
            values = {
                "failure_type": failure_type,
                "job_id": representative.job_id,
                "provider_call_count": client.call_count,
                "rescue_call_count": raw.rescue_call_count,
                "rescued_usable_request_count": sum(
                    item.outcome == "rescued_usable" for item in raw.logical_requests
                ),
                "completed": raw.terminal_disposition == "completed",
                "rescue_prompt_strictly_shorter": all(
                    item.rescue_prompt_strictly_shorter for item in rescue_attempts
                ),
            }
            provisional = RescueRunnerFixtureRow.model_construct(
                row_id="pending",
                **values,
            )
            rescue_rows.append(
                RescueRunnerFixtureRow(
                    row_id=rescue_runner_fixture_row_id(provisional),
                    **values,
                )
            )

        exhaustion_events = (
            _FixtureEvent(failure_type="reasoning_only_length_truncation"),
            _FixtureEvent(payload=payloads[0]),
            *(_FixtureEvent(payload=item) for item in payloads[1:-1]),
            _FixtureEvent(failure_type="invalid_json"),
        )
        exhausted_output = root / "global_rescue_exhaustion"
        exhausted, exhausted_client, _ = _execute_fixture(
            inputs=inputs,
            execution_contract=execution_contract,
            job=representative,
            events=exhaustion_events,
            output_dir=exhausted_output,
        )
        telemetry_output = root / "telemetry_only"
        telemetry_failure, _, _ = _execute_fixture(
            inputs=inputs,
            execution_contract=execution_contract,
            job=representative,
            events=(_FixtureEvent(failure_type="response_envelope_invalid"),),
            output_dir=telemetry_output,
        )
        _, representative_record, representative_environment, _, _ = _fixture_bindings(
            inputs,
            representative,
        )
        prepared_stub = cast(
            Any,
            SimpleNamespace(
                execution_contract=execution_contract,
                replay_contract=inputs.replay_contract,
            ),
        )
        exhausted_result = _score_raw_execution(
            raw=exhausted,
            prepared=prepared_stub,
            record=representative_record,
            environment=representative_environment,
            output_dir=exhausted_output,
        )
        telemetry_result = _score_raw_execution(
            raw=telemetry_failure,
            prepared=prepared_stub,
            record=representative_record,
            environment=representative_environment,
            output_dir=telemetry_output,
        )
        transition_stub = cast(
            Any,
            SimpleNamespace(interpretation_contract=_make_interpretation_contract()),
        )
        aggregate_prepared = cast(
            Any,
            SimpleNamespace(
                execution_contract=execution_contract,
                replay_contract=inputs.replay_contract,
                manifest=inputs.manifest,
                preflight_report=SimpleNamespace(report_id="fixture-only-preflight"),
                interpretation_contract=transition_stub.interpretation_contract,
            ),
        )
        raw_lineage = _raw_lineage_audit(
            prepared=aggregate_prepared,
            results=direct_results,
            raw_by_job=direct_raw_by_job,
            output_dir=direct_output,
        )
        aggregate_report = _make_report(
            prepared=aggregate_prepared,
            results=direct_results,
            raw_lineage=raw_lineage,
        )

    values = {
        "execution_contract_id": execution_contract.contract_id,
        "direct_rows": tuple(direct_rows),
        "rescue_rows": tuple(rescue_rows),
        "direct_fixture_provider_call_count": sum(item.provider_call_count for item in direct_rows),
        "direct_fixture_logical_request_count": sum(
            item.logical_request_count for item in direct_rows
        ),
        "direct_fixture_observation_count": sum(item.observation_count for item in direct_rows),
        "direct_replay_pass_count": sum(item.replay_passed for item in direct_rows),
        "direct_verifier_valid_count": sum(item.verifier_valid for item in direct_rows),
        "direct_mechanism_success_count": sum(item.mechanism_success for item in direct_rows),
        "direct_cell_summary_count": len(_cell_summaries(direct_results)),
        "full_aggregate_report_id": aggregate_report.report_id,
        "full_aggregate_raw_file_count": len(raw_lineage.files),
        "full_aggregate_provider_call_count": aggregate_report.provider_call_count,
        "full_aggregate_valid_terminal_count": aggregate_report.terminal_counts.get(
            "model_valid_trajectory",
            0,
        ),
        "full_aggregate_status": aggregate_report.status,
        "global_rescue_exhaustion_terminal": exhausted.terminal_disposition,
        "global_rescue_exhaustion_rescue_call_count": exhausted.rescue_call_count,
        "global_rescue_exhaustion_provider_call_count": exhausted_client.call_count,
        "telemetry_only_terminal": telemetry_failure.terminal_disposition,
        "telemetry_only_rescue_call_count": telemetry_failure.rescue_call_count,
        "length_failure_transition_control": _next_transition(
            prepared=transition_stub,
            results=(exhausted_result,),
        ),
        "telemetry_failure_transition_control": _next_transition(
            prepared=transition_stub,
            results=(telemetry_result,),
        ),
        "direct_pass_transition_control": _next_transition(
            prepared=transition_stub,
            results=direct_results,
        ),
        "full_aggregate_transition_control": aggregate_report.next_permitted_stage,
        "all_direct_paths_completed": all(item.completed for item in direct_rows),
        "all_direct_observations_match_compiler": all(
            item.observations_match_compiler for item in direct_rows
        ),
        "all_registered_primary_prompts_match": all(
            item.all_primary_prompts_match_registered for item in direct_rows
        ),
        "all_rescue_types_recovered": all(item.completed for item in rescue_rows),
        "one_rescue_per_job_enforced": (
            exhausted.rescue_call_count == 1
            and exhausted.terminal_disposition == "completion_unusable"
        ),
        "response_telemetry_failure_not_rescued": (
            telemetry_failure.rescue_call_count == 0
            and telemetry_failure.terminal_disposition == "instrument_failure"
        ),
    }
    provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **values)
    return RunnerFixtureAudit(
        audit_id=runner_fixture_audit_id(provisional),
        **values,
    )


def _make_budget_recovery_audit(
    *,
    inputs: _Inputs,
    execution_contract: ThinkingRepairExecutionContract,
    runner_fixture: RunnerFixtureAudit,
) -> BudgetRecoveryAudit:
    job = inputs.manifest.jobs[0]
    path, record, environment, prompt, trajectory = _fixture_bindings(inputs, job)
    events = tuple(_FixtureEvent(payload=payload) for payload in _projection_payloads(trajectory))
    with tempfile.TemporaryDirectory(prefix="v26_95_recovery_fixture_") as temporary:
        root = Path(temporary)
        output = root / "recoverable"
        client = _ScriptedProviderClient(inputs.agent_model_config, events)
        first = execute_thinking_repair_job_raw(
            job=job,
            execution_contract=execution_contract,
            provider_contract=inputs.provider_contract,
            record=record,
            environment=environment,
            prompt_contract=prompt,
            path_audit=path,
            client=client,
            output_dir=output,
        )
        before = _raw_execution_path(output, job).read_bytes()
        recovered = execute_thinking_repair_job_raw(
            job=job,
            execution_contract=execution_contract,
            provider_contract=inputs.provider_contract,
            record=record,
            environment=environment,
            prompt_contract=prompt,
            path_audit=path,
            client=None,
            output_dir=output,
        )
        after = _raw_execution_path(output, job).read_bytes()

        oversized_client = _ScriptedProviderClient(inputs.agent_model_config, ())
        ledger = _JournaledBudgetClient(
            oversized_client,
            execution_contract=execution_contract,
            job=job,
            provider_contract=inputs.provider_contract,
            output_dir=root / "oversized",
        )
        oversized_denied = False
        try:
            ledger.call(
                "x" * (inputs.provider_contract.maximum_prompt_utf8_bytes + 1),
                logical_request_index=0,
                phase="primary",
                request_kind="decision",
                rescue_available_before=True,
            )
        except LLMClientError:
            oversized_denied = ledger.no_call_terminal is not None

        orphan_output = root / "orphan"
        orphan_path = _raw_provider_path(orphan_output, job, 0)
        _write_json_atomic(orphan_path, {"orphan_fixture": True})
        orphan_rejected = False
        try:
            execute_thinking_repair_job_raw(
                job=job,
                execution_contract=execution_contract,
                provider_contract=inputs.provider_contract,
                record=record,
                environment=environment,
                prompt_contract=prompt,
                path_audit=path,
                client=_ScriptedProviderClient(inputs.agent_model_config, events),
                output_dir=orphan_output,
            )
        except ValueError:
            orphan_rejected = True

    values = {
        "execution_contract_id": execution_contract.contract_id,
        "first_execution_provider_call_count": client.call_count,
        "recovered_artifact_id": first.artifact_id,
        "recovery_artifact_id": recovered.artifact_id,
        "raw_only_recovery_provider_call_count": 0,
        "raw_only_recovery_byte_identical": before == after,
        "oversized_prompt_denied_before_delegate": oversized_denied,
        "oversized_prompt_delegate_call_count": oversized_client.call_count,
        "orphan_provider_artifact_rejected": orphan_rejected,
        "second_rescue_rejected_by_job_scope": (runner_fixture.one_rescue_per_job_enforced),
        "explicit_request_kind_budget_certificates_passed": (
            first.provider_budget_audit.status == "passed"
            and all(
                item.request_kind in {"decision", "final_answer", "contract_repair"}
                for item in first.provider_budget_audit.certificates
            )
        ),
    }
    provisional = BudgetRecoveryAudit.model_construct(audit_id="pending", **values)
    return BudgetRecoveryAudit(
        audit_id=budget_recovery_audit_id(provisional),
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
    raise AssertionError(f"v26.95 destructive mutation was accepted: {name}")


def _make_destructive_audit(
    *,
    replay: ThinkingRepairRunnerSourceReplayAudit,
    interpretation: ThinkingRepairOutcomeInterpretationContract,
    execution_contract: ThinkingRepairExecutionContract,
    runner_fixture: RunnerFixtureAudit,
) -> DestructivePreflightAudit:
    def validate_contract(**updates: Any) -> None:
        payload = execution_contract.model_dump(mode="json")
        payload.update(updates)
        ThinkingRepairExecutionContract.model_validate(payload)

    def validate_interpretation(**updates: Any) -> None:
        payload = interpretation.model_dump(mode="json")
        payload.update(updates)
        ThinkingRepairOutcomeInterpretationContract.model_validate(payload)

    def mutate_replay_digest() -> None:
        payload = replay.model_dump(mode="json")
        payload["entries"][0]["observed_sha256"] = "0" * 64
        ThinkingRepairRunnerSourceReplayAudit.model_validate(payload)

    mutations = (
        _mutation(
            "second_rescue_call",
            lambda: validate_contract(maximum_rescue_calls_per_job=2),
        ),
        _mutation(
            "provider_plan_call",
            lambda: validate_contract(model_plan_calls_per_job=1),
        ),
        _mutation(
            "transient_provider_retry",
            lambda: validate_contract(transient_provider_retries_per_request=1),
        ),
        _mutation(
            "provider_contract_repair_loop",
            lambda: validate_contract(provider_config_contract_repair_loop_used=True),
        ),
        _mutation(
            "previous_final_content_persistence",
            lambda: validate_contract(previous_final_content_persisted=True),
        ),
        _mutation(
            "private_reasoning_persistence",
            lambda: validate_contract(private_reasoning_content_persisted=True),
        ),
        _mutation(
            "private_reasoning_hash",
            lambda: validate_contract(private_reasoning_content_hashed=True),
        ),
        _mutation(
            "raw_http_body_persistence",
            lambda: validate_contract(raw_http_body_persisted=True),
        ),
        _mutation(
            "execution_deauthorization",
            lambda: validate_contract(execution_authorized=False),
        ),
        _mutation(
            "changed_provider_budget_contract",
            lambda: validate_contract(provider_budget_contract_id="changed"),
        ),
        _mutation(
            "duplicate_job_identity",
            lambda: validate_contract(
                job_ids=(
                    execution_contract.job_ids[0],
                    *execution_contract.job_ids[:-1],
                )
            ),
        ),
        _mutation("changed_source_digest", mutate_replay_digest),
        _mutation(
            "completion_threshold_relaxation",
            lambda: validate_interpretation(zero_failure_gate_threshold=0.20),
        ),
        _mutation(
            "same_bound_prompt_retuning",
            lambda: validate_interpretation(
                same_bound_prompt_only_retuning_after_length_failure_allowed=True
            ),
        ),
        _mutation(
            "capability_claim_from_completion",
            lambda: validate_interpretation(completion_success_cannot_establish_capability=False),
        ),
        _mutation(
            "telemetry_repair_changes_completion",
            lambda: validate_interpretation(
                telemetry_only_repair_must_hold_completion_protocol_fixed=False
            ),
        ),
        _mutation(
            "fixture_empirical_rows",
            lambda: RunnerFixtureAudit.model_validate(
                {
                    **runner_fixture.model_dump(mode="json"),
                    "compiler_fixture_empirical_rows": 1,
                }
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


def _detail(path: Path, output_dir: Path, count: int = 1) -> DetailFile:
    return DetailFile(
        relative_path=path.name,
        sha256=_sha256(path),
        record_count=count,
    )


def build_thinking_repair_execution_preflight(
    *,
    run_id: str,
    output_dir: Path,
    package_root: Path,
) -> ThinkingRepairExecutionPreflightReport:
    if run_id != V26_95_RUN_ID:
        raise ValueError("v26.95 Runner preflight run identity changed")
    inputs = _load_inputs(package_root)
    replay = _build_source_replay(inputs=inputs, package_root=package_root)
    interpretation = _make_interpretation_contract()
    execution_contract = _make_execution_contract(
        inputs=inputs,
        replay=replay,
        interpretation=interpretation,
        package_root=package_root,
    )
    runner_fixture = _make_runner_fixture_audit(
        inputs=inputs,
        execution_contract=execution_contract,
    )
    budget_recovery = _make_budget_recovery_audit(
        inputs=inputs,
        execution_contract=execution_contract,
        runner_fixture=runner_fixture,
    )
    destructive = _make_destructive_audit(
        replay=replay,
        interpretation=interpretation,
        execution_contract=execution_contract,
        runner_fixture=runner_fixture,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", replay),
        ("outcome_interpretation_contract.json", interpretation),
        ("execution_contract.json", execution_contract),
        ("runner_fixture_audit.json", runner_fixture),
        ("budget_recovery_audit.json", budget_recovery),
        ("destructive_preflight_audit.json", destructive),
    )
    for name, payload in payloads:
        _write_json_atomic(output_dir / name, payload.model_dump(mode="json"))
    detail_files = tuple(
        sorted(
            (
                _detail(
                    output_dir / name,
                    output_dir,
                    len(payload.direct_rows)
                    if isinstance(payload, RunnerFixtureAudit)
                    else len(payload.mutation_results)
                    if isinstance(payload, DestructivePreflightAudit)
                    else 1,
                )
                for name, payload in payloads
            ),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "run_id": run_id,
        "source_replay_audit_id": replay.audit_id,
        "outcome_interpretation_contract_id": interpretation.contract_id,
        "execution_contract_id": execution_contract.contract_id,
        "runner_fixture_audit_id": runner_fixture.audit_id,
        "budget_recovery_audit_id": budget_recovery.audit_id,
        "destructive_preflight_audit_id": destructive.audit_id,
        "source_replayed_file_count": replay.replayed_file_count,
        "detail_files": detail_files,
        "implementation_source_files": (execution_contract.runner_implementation_source_files),
    }
    provisional = ThinkingRepairExecutionPreflightReport.model_construct(
        report_id="pending",
        **values,
    )
    report = ThinkingRepairExecutionPreflightReport(
        report_id=thinking_repair_execution_preflight_report_id(provisional),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.95 Thinking repair execution Runner preflight"
    )
    parser.add_argument("--run-id", default=V26_95_RUN_ID)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_thinking_repair_execution_preflight(
        run_id=args.run_id,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
