from __future__ import annotations

import argparse
import json
import tempfile
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from math import comb
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import (
    matching_sufficient_support_set,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingVerificationReport,
    authority_preserving_verification_report_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    VERIFICATION_CHECK_IDS,
    MechanismEstimandOutcome,
    evaluate_mechanism_estimand,
    match_empirical_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501  # noqa: E501
    RawFileDescriptor,
    ThinkingRepairCompletedResult,
    _actual_route,
    _earliest_failure_stage,
    _progress_diagnostic,
    _project_answer,
    _repetition_counts,
    _replace_runtime_references,
    _successful_observations,
    thinking_repair_completed_result_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_profile_and_manifest_preflight import (  # noqa: E501
    TwoStageJob,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    RawStageOneProviderCall,
    TwoStageRawExecution,
    TwoStageRunnerContract,
    TwoStageStaticInputs,
    execute_two_stage_job_raw,
    load_two_stage_static_inputs,
    make_runner_contract,
    raw_execution_path,
    raw_provider_path,
    replay_v3,
    sha256_file,
    two_stage_runtime_binding,
    write_json_atomic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_runner_preflight import (  # noqa: E501
    OutcomeInterpretationContract,
    RunnerPreflightReport,
    RunnerSourceReplayAudit,
    ScriptedStageOneClient,
    _compiler_calls,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    STAGE_ONE_MODEL_ID,
    StageOneProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

RUN_ID: Final = "finance_v26_110_two_stage_semantic_proposal_calibration_v1"
RUNNER_PREFLIGHT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_109_two_stage_semantic_proposal_runner_preflight_v1_20260822"
)
EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_two_stage_runner_preflight_report:"
    "1b907cbb962f68dd798764a514db4a4cbf7e3091cfadd35a6702f1e85a0d633b"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_two_stage_runner_contract:"
    "34c9bc91fbab6fb571127a3904b318bf33ca533fa670aa4ca3eccf1de611bac1"
)
EXPECTED_INTERPRETATION_ID: Final = (
    "finance_v26_two_stage_outcome_interpretation:"
    "b0dbdf510758848d0a977d5b56f98dd2f25a7978951f6655408cfa73fbced859"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_two_stage_semantic_proposal_calibration_execution.py"
)
POSTRUN_AUDIT_TRANSITION: Final = "two_stage_semantic_proposal_calibration_postrun_audit_only"

TerminalCategory = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "completion_unusable",
    "typed_budget_no_call",
    "provider_transport_failure",
    "instrument_failure",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExecutionSourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: bool


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = Field(min_length=1)
    predecessor_transitive_file_count: Literal[1900] = 1900
    predecessor_output_file_count: Literal[10] = 10
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[1911] = 1911
    replay_pass_count: Literal[1911] = 1911
    entries: tuple[ExecutionSourceReplayEntry, ...] = Field(min_length=1911, max_length=1911)
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_execution_source_replay.v1"] = (
        "finance_v26_two_stage_execution_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        if tuple(item.relative_path for item in self.entries) != tuple(
            sorted(item.relative_path for item in self.entries)
        ):
            raise ValueError("v26.110 source replay entries are not canonical")
        if len({item.relative_path for item in self.entries}) != 1911:
            raise ValueError("v26.110 source replay contains duplicate paths")
        if not all(item.passed for item in self.entries):
            raise ValueError("v26.110 source replay contains a failed file")
        if self.audit_id != execution_source_replay_audit_id(self):
            raise ValueError("v26.110 source replay identity changed")
        return self


class TwoStageJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    requested_path_strategy_id: str = Field(min_length=1)
    terminal_category: TerminalCategory
    raw_terminal_disposition: str = Field(min_length=1)
    terminal_failure_type: str | None = None
    provider_call_count: int = Field(ge=0, le=11)
    http_success_call_count: int = Field(ge=0, le=11)
    provider_total_tokens: int = Field(ge=0, le=260000)
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    reasoning_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    primary_attempt_count: int = Field(ge=1, le=10)
    rescue_attempt_count: int = Field(ge=0, le=1)
    direct_usable_request_count: int = Field(ge=0, le=10)
    rescued_usable_request_count: int = Field(ge=0, le=1)
    rescue_success: bool
    completion_failure_counts: dict[str, int]
    model_failure_family_counts: dict[str, int]
    model_failure_subtype_counts: dict[str, int]
    semantic_compile_rejection_count: int = Field(ge=0, le=1)
    duplicate_failed_proposal_count: int = Field(ge=0, le=1)
    typed_no_call: bool
    completion_unusable: bool
    provider_transport_failure: bool
    instrument_failure: bool
    exact_model_passed: bool
    native_tool_absent: bool
    thinking_continuity_passed: bool
    provider_usage_complete: bool
    fallback_absent: bool
    dynamic_precall_binding_passed: bool
    exact_request_binding_passed: bool
    rollout_budget_passed: bool
    stage_two_provider_call_count: Literal[0] = 0
    reversible_commit_passed: bool
    host_semantic_action_inserted: Literal[False] = False
    observation_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    repeated_call_signature_count: int = Field(ge=0)
    repeated_failed_call_signature_count: int = Field(ge=0)
    completed_program_node_count: int = Field(ge=0)
    program_node_count: int = Field(ge=0)
    program_closed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    mechanism_evaluated: bool
    mechanism_success: bool
    independent_validity: bool
    actual_route: str = Field(min_length=1)
    requested_path_adhered: bool
    replay_v3_passed: bool
    verification_report: AuthorityPreservingVerificationReport | None = None
    mechanism_outcome: MechanismEstimandOutcome
    raw_execution_artifact: RawFileDescriptor
    engineering_calibration_only: Literal[True] = True
    capability_denominator_eligible: Literal[False] = False
    reachability_denominator_eligible: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_two_stage_job_result.v1"] = (
        "finance_v26_two_stage_job_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> TwoStageJobResult:
        if self.reasoning_tokens_total > self.completion_tokens_total:
            raise ValueError("v26.110 reasoning Usage exceeds Completion Usage")
        if self.requested_path_adhered != (self.actual_route == self.requested_path_strategy_id):
            raise ValueError("v26.110 path adherence accounting changed")
        if self.independent_validity != (self.terminal_category == "model_valid_trajectory"):
            raise ValueError("v26.110 valid terminal accounting changed")
        if self.rescue_success and not self.rescue_attempt_count:
            raise ValueError("v26.110 Rescue success lacks a Rescue attempt")
        if self.result_id != two_stage_job_result_id(self):
            raise ValueError("v26.110 Job result identity changed")
        return self


class TwoStageCellSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    job_count: int = Field(ge=2)
    model_invalid_count: int = Field(ge=0)
    completion_unusable_count: int = Field(ge=0)
    typed_no_call_count: int = Field(ge=0)
    transport_failure_count: int = Field(ge=0)
    instrument_failure_count: int = Field(ge=0)
    rescue_job_count: int = Field(ge=0)
    program_closed_count: int = Field(ge=0)
    mechanism_success_count: int = Field(ge=0)
    independently_valid_count: int = Field(ge=0)
    requested_path_adherence_count: int = Field(ge=0)
    descriptive_only: Literal[True] = True
    schema_version: Literal["finance_v26_two_stage_cell_summary.v1"] = (
        "finance_v26_two_stage_cell_summary.v1"
    )

    @model_validator(mode="after")
    def validate_summary(self) -> TwoStageCellSummary:
        if self.summary_id != two_stage_cell_summary_id(self):
            raise ValueError("v26.110 Cell summary identity changed")
        return self


class TwoStageRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    job_result_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    provider_call_count: int = Field(ge=0, le=352)
    unique_provider_artifact_id_count: int = Field(ge=0, le=352)
    file_count: int = Field(ge=32)
    files: tuple[RawFileDescriptor, ...] = Field(min_length=32)
    exact_byte_replay_pass_count: int = Field(ge=32)
    private_reasoning_payload_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_raw_lineage.v1"] = (
        "finance_v26_two_stage_raw_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> TwoStageRawLineageAudit:
        if self.file_count != len(self.files):
            raise ValueError("v26.110 Raw Lineage file count changed")
        if self.exact_byte_replay_pass_count != self.file_count:
            raise ValueError("v26.110 Raw Lineage replay denominator changed")
        if self.unique_provider_artifact_id_count != self.provider_call_count:
            raise ValueError("v26.110 Provider identities are not unique")
        if self.audit_id != two_stage_raw_lineage_audit_id(self):
            raise ValueError("v26.110 Raw Lineage identity changed")
        return self


class PreexecutionValidityRow(FrozenModel):
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    stage_one_scripted_provider_call_count: int = Field(gt=0, le=10)
    stage_two_commit_count: int = Field(gt=0, le=9)
    final_answer_envelope_projected: Literal[True] = True
    replay_v3_passed: Literal[True] = True
    independent_validity_passed: Literal[True] = True
    mechanism_score_passed: Literal[True] = True
    stage_two_provider_call_count: Literal[0] = 0


class PreexecutionValidityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    rows: tuple[PreexecutionValidityRow, ...] = Field(min_length=32, max_length=32)
    job_count: Literal[32] = 32
    completed_count: Literal[32] = 32
    replay_v3_pass_count: Literal[32] = 32
    independently_valid_count: Literal[32] = 32
    mechanism_success_count: Literal[32] = 32
    stage_one_scripted_provider_call_count: Literal[256] = 256
    stage_two_provider_call_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    v26_109_default_count_replaced_by_computed_rows: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_preexecution_validity_audit.v1"] = (
        "finance_v26_preexecution_validity_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionValidityAudit:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted(item.job_id for item in self.rows)
        ):
            raise ValueError("v26.110 pre-execution validity rows are not canonical")
        if self.audit_id != preexecution_validity_audit_id(self):
            raise ValueError("v26.110 pre-execution validity identity changed")
        return self


class TwoStageExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal["finance_v26_110_two_stage_semantic_proposal_calibration_v1"] = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_interpretation_contract_id: str = EXPECTED_INTERPRETATION_ID
    preexecution_validity_audit_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = 32
    completed_job_result_count: Literal[32] = 32
    terminal_counts: dict[str, int]
    provider_call_count: int = Field(ge=0, le=352)
    http_success_call_count: int = Field(ge=0, le=352)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    reasoning_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    primary_attempt_count: int = Field(ge=32, le=320)
    rescue_attempt_count: int = Field(ge=0, le=32)
    rescue_success_count: int = Field(ge=0, le=32)
    direct_usable_request_count: int = Field(ge=0)
    rescued_usable_request_count: int = Field(ge=0)
    completion_failure_counts: dict[str, int]
    model_failure_family_counts: dict[str, int]
    model_failure_subtype_counts: dict[str, int]
    semantic_compile_rejection_job_count: int = Field(ge=0, le=32)
    duplicate_failed_proposal_job_count: int = Field(ge=0, le=32)
    typed_no_call_job_count: int = Field(ge=0, le=32)
    typed_no_call_cp95_upper_32: float = Field(ge=0.0, le=1.0)
    completion_unusable_job_count: int = Field(ge=0, le=32)
    completion_unusable_cp95_upper_32: float = Field(ge=0.0, le=1.0)
    provider_transport_failure_job_count: int = Field(ge=0, le=32)
    instrument_failure_job_count: int = Field(ge=0, le=32)
    model_invalid_trajectory_count: int = Field(ge=0, le=32)
    program_closed_count: int = Field(ge=0, le=32)
    mechanism_success_count: int = Field(ge=0, le=32)
    independently_valid_trajectory_count: int = Field(ge=0, le=32)
    requested_path_adherence_count: int = Field(ge=0, le=32)
    cell_summaries: tuple[TwoStageCellSummary, ...] = Field(min_length=12, max_length=12)
    exact_model_passed: bool
    native_tool_absence_passed: bool
    thinking_continuity_passed: bool
    provider_usage_complete: bool
    fallback_absence_passed: bool
    dynamic_precall_binding_passed: bool
    exact_request_binding_passed: bool
    empirical_budget_adequacy_passed: bool
    stage_two_provider_call_count: Literal[0] = 0
    stage_two_authority_passed: bool
    replay_v3_passed: bool
    exact_denominator_complete: Literal[True] = True
    engineering_calibration_only: Literal[True] = True
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    execution_status: Literal["completed_pending_independent_audit"] = (
        "completed_pending_independent_audit"
    )
    next_permitted_stage: Literal["two_stage_semantic_proposal_calibration_postrun_audit_only"] = (
        POSTRUN_AUDIT_TRANSITION
    )
    schema_version: Literal["finance_v26_two_stage_execution_report.v1"] = (
        "finance_v26_two_stage_execution_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> TwoStageExecutionReport:
        if sum(self.terminal_counts.values()) != 32:
            raise ValueError("v26.110 terminal denominator changed")
        if self.report_id != two_stage_execution_report_id(self):
            raise ValueError("v26.110 execution report identity changed")
        return self


class PreparedExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    source_replay: ExecutionSourceReplayAudit
    preflight_report: RunnerPreflightReport
    runner_contract: TwoStageRunnerContract
    interpretation_contract: OutcomeInterpretationContract
    preexecution_validity: PreexecutionValidityAudit
    static: TwoStageStaticInputs


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def execution_source_replay_audit_id(value: ExecutionSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_execution_source_replay:")


def two_stage_job_result_id(value: TwoStageJobResult) -> str:
    return _identity(value, "result_id", "finance_v26_two_stage_job_result:")


def two_stage_cell_summary_id(value: TwoStageCellSummary) -> str:
    return _identity(value, "summary_id", "finance_v26_two_stage_cell_summary:")


def two_stage_raw_lineage_audit_id(value: TwoStageRawLineageAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_raw_lineage:")


def preexecution_validity_audit_id(value: PreexecutionValidityAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_preexecution_validity_audit:")


def two_stage_execution_report_id(value: TwoStageExecutionReport) -> str:
    return _identity(value, "report_id", "finance_v26_two_stage_execution_report:")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _descriptor(path: Path, output_dir: Path) -> RawFileDescriptor:
    return RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=sha256_file(path),
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
        if candidate.is_file() and sha256_file(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.110 cannot replay bound file: {relative_path}")


def build_execution_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    runner_preflight_dir: Path,
) -> ExecutionSourceReplayAudit:
    predecessor = RunnerSourceReplayAudit.model_validate(
        _load(runner_preflight_dir / "source_replay_audit.json")
    )
    report = RunnerPreflightReport.model_validate(_load(runner_preflight_dir / "report.json"))
    entries: dict[str, ExecutionSourceReplayEntry] = {}
    for item in predecessor.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = ExecutionSourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_109_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=sha256_file(path),
            byte_count=path.stat().st_size,
            passed=True,
        )
    output_paths = {"report.json": runner_preflight_dir / "report.json"}
    output_paths.update(
        {
            item.relative_path: runner_preflight_dir / item.relative_path
            for item in report.detail_files
        }
    )
    if len(output_paths) != 10:
        raise ValueError("v26.110 expected exactly ten v26.109 outputs")
    relative_runner_root = Path(RUNNER_PREFLIGHT_DIR)
    for name, path in output_paths.items():
        relative = str(relative_runner_root / name)
        observed = sha256_file(path)
        entries[relative] = ExecutionSourceReplayEntry(
            relative_path=relative,
            source_kind="v26_109_output",
            expected_sha256=observed,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
            passed=True,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    observed = sha256_file(implementation_path)
    entries[IMPLEMENTATION_PATH] = ExecutionSourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_110_implementation",
        expected_sha256=observed,
        observed_sha256=observed,
        byte_count=implementation_path.stat().st_size,
        passed=True,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values: dict[str, Any] = {
        "predecessor_source_replay_id": predecessor.audit_id,
        "entries": ordered,
    }
    provisional = ExecutionSourceReplayAudit.model_construct(audit_id="pending", **values)
    return ExecutionSourceReplayAudit(
        audit_id=execution_source_replay_audit_id(provisional),
        **values,
    )


def prepare_two_stage_execution(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> PreparedExecution:
    source_replay = build_execution_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        runner_preflight_dir=runner_preflight_dir,
    )
    write_json_atomic(
        output_dir / "online_source_replay_audit.json",
        source_replay.model_dump(mode="json"),
    )
    report = RunnerPreflightReport.model_validate(_load(runner_preflight_dir / "report.json"))
    contract = TwoStageRunnerContract.model_validate(
        _load(runner_preflight_dir / "execution_contract.json")
    )
    interpretation = OutcomeInterpretationContract.model_validate(
        _load(runner_preflight_dir / "outcome_interpretation_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or report.execution_contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or report.outcome_interpretation_contract_id != EXPECTED_INTERPRETATION_ID
        or not report.runner_preflight_passed
        or not report.execution_authorized
        or report.execution_started
        or report.exact_job_denominator != 32
        or report.next_permitted_stage != "two_stage_semantic_proposal_calibration_execution_only"
        or contract.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or interpretation.contract_id != EXPECTED_INTERPRETATION_ID
    ):
        raise ValueError("v26.110 predecessor authorization changed")
    static = load_two_stage_static_inputs(package_root, implementation_root)
    if (
        make_runner_contract(static) != contract
        or tuple(sorted(item.job_id for item in static.manifest.jobs))
        != tuple(sorted(contract_job_ids(static)))
        or static.resource.rollout_upper_bound_tokens != 260000
        or static.stage_two.provider_call_upper_bound != 0
    ):
        raise ValueError("v26.110 static execution denominator changed")
    preexecution_validity = build_preexecution_validity_audit(
        static=static,
        contract=contract,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        output_dir / "execution_contract.json",
        contract.model_dump(mode="json"),
    )
    write_json_atomic(
        output_dir / "outcome_interpretation_contract.json",
        interpretation.model_dump(mode="json"),
    )
    write_json_atomic(
        output_dir / "frozen_two_stage_job_manifest.json",
        static.manifest.model_dump(mode="json"),
    )
    write_json_atomic(
        output_dir / "preexecution_independent_validity_audit.json",
        preexecution_validity.model_dump(mode="json"),
    )
    return PreparedExecution(
        source_replay=source_replay,
        preflight_report=report,
        runner_contract=contract,
        interpretation_contract=interpretation,
        preexecution_validity=preexecution_validity,
        static=static,
    )


def contract_job_ids(static: TwoStageStaticInputs) -> tuple[str, ...]:
    return tuple(item.job_id for item in static.manifest.jobs)


def _telemetry_flags(
    telemetry: Sequence[ModelCallTelemetry],
) -> tuple[bool, bool, bool, bool, bool]:
    http_success = tuple(item for item in telemetry if item.http_success)
    exact_model = all(
        item.model_requested == STAGE_ONE_MODEL_ID
        and item.model_selected == STAGE_ONE_MODEL_ID
        and (not item.http_success or item.response_model == STAGE_ONE_MODEL_ID)
        for item in telemetry
    )
    fallback_absent = all(
        not item.fallback_used and not item.discovery_attempted for item in telemetry
    )
    native_absent = all(
        item.response_shape.get("provider_native_tool_call_observed") is False
        for item in http_success
    )
    thinking = all(
        item.reasoning_content_present
        and (item.reasoning_content_length or 0) > 0
        and (item.reasoning_tokens or 0) > 0
        for item in http_success
    )
    usage = all(
        item.prompt_tokens is not None
        and item.completion_tokens is not None
        and item.total_tokens is not None
        and item.prompt_tokens + item.completion_tokens == item.total_tokens
        for item in http_success
    )
    return exact_model, fallback_absent, native_absent, thinking, usage


def _completed_verification(
    *,
    raw: TwoStageRawExecution,
    replay: Any,
    binding: Any,
) -> tuple[AuthorityPreservingVerificationReport, MechanismEstimandOutcome]:
    if raw.completed_result is None:
        raise ValueError("v26.110 completed verification lacks a completed result")
    completed_values: dict[str, Any] = {
        "job_id": raw.job.job_id,
        "observations": raw.observations,
        "answer": raw.completed_result.answer,
        "cited_evidence_ids": raw.completed_result.cited_evidence_ids,
        "final_request_id": raw.completed_result.final_attempt_id,
    }
    provisional_completed = ThinkingRepairCompletedResult.model_construct(
        result_id="pending", **completed_values
    )
    completed = ThinkingRepairCompletedResult(
        result_id=thinking_repair_completed_result_id(provisional_completed),
        **completed_values,
    )
    public_result = completed.answer.get("result")
    answer_for_projection = (
        cast(Mapping[str, Any], public_result)
        if isinstance(public_result, Mapping)
        else completed.answer
    )
    record = binding.record
    observations = completed.observations
    program_complete, matched_nodes, runtime_to_node, operation_lineage = match_empirical_program(
        record, observations
    )
    normalized_answer = _project_answer(
        cast(
            dict[str, Any],
            _replace_runtime_references(answer_for_projection, runtime_to_node),
        ),
        record.answer_projection,
    )
    lattice = record.task_package.evidence_support_lattice
    selected_support = matching_sufficient_support_set(
        lattice,
        replay.selected_evidence_ids,
    )
    citation_support = matching_sufficient_support_set(
        lattice,
        completed.cited_evidence_ids,
    )
    verification_support = tuple(
        sorted(
            {
                str(evidence_id)
                for item in _successful_observations(observations, "cross_check_evidence")
                if item.result.get("verified") is True
                for evidence_id in item.result.get("support") or ()
            }
        )
    )
    mechanism = evaluate_mechanism_estimand(
        record,
        observations,
        stopped_by_model=True,
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
    necessary = set(lattice.necessary_evidence_ids)
    checks = {
        "runtime_replay_passed": replay.passed,
        "model_input_noninterference_passed": True,
        "only_allowed_tools": {item.call.tool_id for item in observations}
        <= set(record.task_package.tool_closure.allowed_tool_ids),
        "operation_lineage_complete": (program_complete and necessary <= set(operation_lineage)),
        "evidence_support_complete": selected_support is not None,
        "verification_complete": necessary <= set(verification_support),
        "answer_projection_complete": (normalized_answer == record.projected_expected_output),
        "citation_complete": citation_support is not None,
        "mechanism_complete": mechanism.success,
        "no_postcompletion_violation": (
            first_verified is None or first_verified == len(observations) - 1
        ),
    }
    if set(checks) != set(VERIFICATION_CHECK_IDS):
        raise ValueError("v26.110 Verifier Gate vector changed")
    values: dict[str, Any] = {
        "replay_id": replay.replay_id,
        "task_package_id": record.task_package.package_id,
        "verifier_binding_id": record.task_package.verifier_binding.binding_id,
        "trajectory_id": canonical_hash(
            completed,
            prefix="finance_v26_two_stage_trajectory:",
        ),
        "checks": checks,
        "selected_evidence_ids": replay.selected_evidence_ids,
        "operation_lineage_evidence_ids": operation_lineage,
        "verification_support_ids": verification_support,
        "cited_evidence_ids": completed.cited_evidence_ids,
        "satisfying_selected_support_set_id": (
            selected_support.support_set_id if selected_support is not None else None
        ),
        "satisfying_citation_support_set_id": (
            citation_support.support_set_id if citation_support is not None else None
        ),
        "mechanism_event_ids": mechanism.observed_event_ids,
        "normalized_answer": normalized_answer,
        "matched_program_node_ids": matched_nodes,
        "earliest_failure_stage": _earliest_failure_stage(checks),
        "valid": all(checks.values()),
    }
    provisional = AuthorityPreservingVerificationReport.model_construct(
        report_id="pending", **values
    )
    return (
        AuthorityPreservingVerificationReport(
            report_id=authority_preserving_verification_report_id(provisional),
            **values,
        ),
        mechanism,
    )


def build_preexecution_validity_audit(
    *,
    static: TwoStageStaticInputs,
    contract: TwoStageRunnerContract,
) -> PreexecutionValidityAudit:
    rows: list[PreexecutionValidityRow] = []
    with tempfile.TemporaryDirectory(prefix="v26_110_preexecution_validity_") as temporary:
        root = Path(temporary)
        for job in sorted(static.manifest.jobs, key=lambda item: item.job_id):
            binding = two_stage_runtime_binding(static, job)
            raw = execute_two_stage_job_raw(
                job=job,
                runner_contract=contract,
                static=static,
                binding=binding,
                client=ScriptedStageOneClient(
                    static.agent_model_config,
                    compiler_calls=_compiler_calls(binding),
                    final_answer=binding.compiler_trajectory.final_answer,
                ),
                output_dir=root,
            )
            replay = replay_v3(raw, static=static, binding=binding)
            verification, mechanism = _completed_verification(
                raw=raw,
                replay=replay,
                binding=binding,
            )
            if (
                raw.terminal_disposition != "completed"
                or raw.completed_result is None
                or not replay.passed
                or not verification.valid
                or not mechanism.success
                or raw.stage_two_provider_call_count
            ):
                raise ValueError(f"v26.110 pre-execution Independent Validity failed: {job.job_id}")
            rows.append(
                PreexecutionValidityRow(
                    job_id=job.job_id,
                    raw_execution_id=raw.artifact_id,
                    stage_one_scripted_provider_call_count=(raw.stage_one_provider_call_count),
                    stage_two_commit_count=len(raw.commits),
                )
            )
    values: dict[str, Any] = {
        "rows": tuple(rows),
        "stage_one_scripted_provider_call_count": sum(
            item.stage_one_scripted_provider_call_count for item in rows
        ),
    }
    provisional = PreexecutionValidityAudit.model_construct(audit_id="pending", **values)
    return PreexecutionValidityAudit(
        audit_id=preexecution_validity_audit_id(provisional),
        **values,
    )


def project_job_result(
    *,
    raw: TwoStageRawExecution,
    prepared: PreparedExecution,
    output_dir: Path,
) -> TwoStageJobResult:
    binding = two_stage_runtime_binding(prepared.static, raw.job)
    replay = replay_v3(raw, static=prepared.static, binding=binding)
    mechanism = evaluate_mechanism_estimand(
        binding.record,
        raw.observations,
        stopped_by_model=raw.completed_result is not None,
    )
    verification: AuthorityPreservingVerificationReport | None = None
    if raw.completed_result is not None:
        verification, mechanism = _completed_verification(
            raw=raw,
            replay=replay,
            binding=binding,
        )
    exact_model, fallback_absent, native_absent, thinking, usage = _telemetry_flags(
        raw.provider_telemetry
    )
    dynamic = all(
        item.dynamic_certificate_id is not None and item.resource_certificate_id is not None
        for item in raw.attempts
        if item.provider_call_made
    )
    exact_request = all(
        item.request_binding_certificate_id is not None
        for item in raw.attempts
        if item.provider_call_made
    )
    reversible = all(
        item.reversible_mapping_passed
        and not item.semantic_choice_inserted_by_host
        and item.stage_two_provider_calls == 0
        for item in raw.commits
    )
    instrument = bool(
        raw.terminal_disposition == "instrument_failure"
        or not exact_model
        or not fallback_absent
        or not native_absent
        or not thinking
        or not usage
        or not dynamic
        or not exact_request
        or not reversible
        or not replay.passed
        or raw.stage_two_provider_call_count
        or raw.cumulative_provider_tokens > 260000
    )
    transport = raw.terminal_disposition == "provider_transport_failure"
    typed = raw.terminal_disposition == "typed_budget_no_call"
    completion = raw.terminal_disposition == "completion_unusable"
    valid = bool(
        verification is not None
        and verification.valid
        and not instrument
        and not transport
        and not typed
        and not completion
    )
    terminal: TerminalCategory
    if instrument:
        terminal = "instrument_failure"
    elif transport:
        terminal = "provider_transport_failure"
    elif typed:
        terminal = "typed_budget_no_call"
    elif completion:
        terminal = "completion_unusable"
    elif valid:
        terminal = "model_valid_trajectory"
    else:
        terminal = "model_invalid_trajectory"
    family_counts = Counter(
        item.model_failure_classification.family
        for item in raw.attempts
        if item.model_failure_classification is not None
    )
    subtype_counts = Counter(
        item.model_failure_classification.subtype
        for item in raw.attempts
        if item.model_failure_classification is not None
    )
    completion_counts = Counter(
        str(item.completion_failure_type)
        for item in raw.attempts
        if item.completion_failure_type is not None
    )
    repeated, repeated_failed = _repetition_counts(raw.observations)
    completed_nodes, node_count, program_closed, terminal_completed, verified = (
        _progress_diagnostic(binding.record, raw.observations)
    )
    route = _actual_route(raw.observations)
    cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    rescued_usable = sum(
        item.phase == "rescue" and item.disposition == "usable" for item in raw.attempts
    )
    values: dict[str, Any] = {
        "job_id": raw.job.job_id,
        "source_task_artifact_id": raw.job.source_task_artifact_id,
        "mechanism_id": raw.job.mechanism_id,
        "requested_path_strategy_id": raw.job.path_strategy_id,
        "terminal_category": terminal,
        "raw_terminal_disposition": raw.terminal_disposition,
        "terminal_failure_type": raw.terminal_failure_type,
        "provider_call_count": raw.stage_one_provider_call_count,
        "http_success_call_count": sum(item.http_success for item in raw.provider_telemetry),
        "provider_total_tokens": sum(item.total_tokens or 0 for item in raw.provider_telemetry),
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length or 0 for item in raw.provider_telemetry
        ),
        "reasoning_tokens_total": sum(
            item.reasoning_tokens or 0 for item in raw.provider_telemetry
        ),
        "completion_tokens_total": sum(
            item.completion_tokens or 0 for item in raw.provider_telemetry
        ),
        "primary_attempt_count": sum(item.phase == "primary" for item in raw.attempts),
        "rescue_attempt_count": raw.rescue_attempt_count,
        "direct_usable_request_count": sum(
            item.phase == "primary" and item.disposition == "usable" for item in raw.attempts
        ),
        "rescued_usable_request_count": rescued_usable,
        "rescue_success": bool(rescued_usable),
        "completion_failure_counts": dict(sorted(completion_counts.items())),
        "model_failure_family_counts": dict(sorted(family_counts.items())),
        "model_failure_subtype_counts": dict(sorted(subtype_counts.items())),
        "semantic_compile_rejection_count": int(
            raw.terminal_failure_type == "semantic_compile_rejection"
        ),
        "duplicate_failed_proposal_count": int(
            raw.terminal_failure_type == "duplicate_failed_semantic_proposal"
        ),
        "typed_no_call": typed,
        "completion_unusable": completion,
        "provider_transport_failure": transport,
        "instrument_failure": instrument,
        "exact_model_passed": exact_model,
        "native_tool_absent": native_absent,
        "thinking_continuity_passed": thinking,
        "provider_usage_complete": usage,
        "fallback_absent": fallback_absent,
        "dynamic_precall_binding_passed": dynamic,
        "exact_request_binding_passed": exact_request,
        "rollout_budget_passed": raw.cumulative_provider_tokens <= 260000,
        "reversible_commit_passed": reversible,
        "observation_count": len(raw.observations),
        "failed_observation_count": sum(item.status == "failed" for item in raw.observations),
        "repeated_call_signature_count": repeated,
        "repeated_failed_call_signature_count": repeated_failed,
        "completed_program_node_count": completed_nodes,
        "program_node_count": node_count,
        "program_closed": program_closed,
        "terminal_node_completed": terminal_completed,
        "postterminal_verification_completed": verified,
        "mechanism_evaluated": mechanism.evaluated,
        "mechanism_success": mechanism.success,
        "independent_validity": valid,
        "actual_route": route,
        "requested_path_adhered": route == raw.job.path_strategy_id,
        "replay_v3_passed": replay.passed,
        "verification_report": verification,
        "mechanism_outcome": mechanism,
        "raw_execution_artifact": _descriptor(raw_execution_path(output_dir, raw.job), output_dir),
    }
    provisional = TwoStageJobResult.model_construct(result_id="pending", **values)
    return TwoStageJobResult(
        result_id=two_stage_job_result_id(provisional),
        **values,
    )


def _cp_upper(failures: int, denominator: int, *, alpha: float = 0.05) -> float:
    if not 0 <= failures <= denominator or denominator <= 0:
        raise ValueError("invalid Clopper-Pearson inputs")
    if failures == denominator:
        return 1.0
    if failures == 0:
        return 1.0 - alpha ** (1.0 / denominator)

    def cdf(probability: float) -> float:
        return sum(
            comb(denominator, index)
            * probability**index
            * (1.0 - probability) ** (denominator - index)
            for index in range(failures + 1)
        )

    low = failures / denominator
    high = 1.0
    for _ in range(160):
        middle = (low + high) / 2.0
        if cdf(middle) > alpha:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _cell_summaries(
    results: Sequence[TwoStageJobResult],
) -> tuple[TwoStageCellSummary, ...]:
    cells: dict[tuple[str, str], list[TwoStageJobResult]] = defaultdict(list)
    for item in results:
        cells[(item.mechanism_id, item.requested_path_strategy_id)].append(item)
    summaries: list[TwoStageCellSummary] = []
    for (mechanism, path), rows in sorted(cells.items()):
        values: dict[str, Any] = {
            "mechanism_id": mechanism,
            "path_strategy_id": path,
            "job_count": len(rows),
            "model_invalid_count": sum(
                item.terminal_category == "model_invalid_trajectory" for item in rows
            ),
            "completion_unusable_count": sum(item.completion_unusable for item in rows),
            "typed_no_call_count": sum(item.typed_no_call for item in rows),
            "transport_failure_count": sum(item.provider_transport_failure for item in rows),
            "instrument_failure_count": sum(item.instrument_failure for item in rows),
            "rescue_job_count": sum(bool(item.rescue_attempt_count) for item in rows),
            "program_closed_count": sum(item.program_closed for item in rows),
            "mechanism_success_count": sum(item.mechanism_success for item in rows),
            "independently_valid_count": sum(item.independent_validity for item in rows),
            "requested_path_adherence_count": sum(item.requested_path_adhered for item in rows),
        }
        provisional = TwoStageCellSummary.model_construct(summary_id="pending", **values)
        summaries.append(
            TwoStageCellSummary(
                summary_id=two_stage_cell_summary_id(provisional),
                **values,
            )
        )
    return tuple(summaries)


def _recursive_keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _recursive_keys(item)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(key for item in value for key in _recursive_keys(item))
    return ()


def raw_lineage_audit(
    *,
    results: Sequence[TwoStageJobResult],
    raw_by_job: Mapping[str, TwoStageRawExecution],
    output_dir: Path,
) -> TwoStageRawLineageAudit:
    files: list[RawFileDescriptor] = []
    provider_ids: list[str] = []
    private_hits = 0
    for result in results:
        raw = raw_by_job[result.job_id]
        raw_path = raw_execution_path(output_dir, raw.job)
        replayed = TwoStageRawExecution.model_validate(_load(raw_path))
        if replayed.model_dump(mode="json") != raw.model_dump(mode="json"):
            raise ValueError(f"v26.110 Raw replay changed: {result.job_id}")
        files.append(_descriptor(raw_path, output_dir))
        for descriptor in raw.provider_call_artifacts:
            path = output_dir / descriptor.relative_path
            payload = _load(path)
            artifact = RawStageOneProviderCall.model_validate(payload)
            if (
                sha256_file(path) != descriptor.sha256
                or descriptor.byte_count != path.stat().st_size
            ):
                raise ValueError("v26.110 Provider Artifact binding changed")
            provider_ids.append(artifact.artifact_id)
            private_hits += int(
                any(
                    key in {"private_reasoning", "reasoning_content"}
                    for key in _recursive_keys(payload)
                )
            )
            files.append(_descriptor(path, output_dir))
    ordered = tuple(sorted(files, key=lambda item: item.relative_path))
    values: dict[str, Any] = {
        "provider_call_count": len(provider_ids),
        "unique_provider_artifact_id_count": len(set(provider_ids)),
        "file_count": len(ordered),
        "files": ordered,
        "exact_byte_replay_pass_count": len(ordered),
        "private_reasoning_payload_count": private_hits,
    }
    provisional = TwoStageRawLineageAudit.model_construct(audit_id="pending", **values)
    return TwoStageRawLineageAudit(
        audit_id=two_stage_raw_lineage_audit_id(provisional),
        **values,
    )


def make_execution_report(
    *,
    prepared: PreparedExecution,
    results: Sequence[TwoStageJobResult],
    lineage: TwoStageRawLineageAudit,
) -> TwoStageExecutionReport:
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in results).items()))
    completion_failures = Counter(
        {
            key: sum(item.completion_failure_counts.get(key, 0) for item in results)
            for key in {key for item in results for key in item.completion_failure_counts}
        }
    )
    family_counts = Counter(
        {
            key: sum(item.model_failure_family_counts.get(key, 0) for item in results)
            for key in {key for item in results for key in item.model_failure_family_counts}
        }
    )
    subtype_counts = Counter(
        {
            key: sum(item.model_failure_subtype_counts.get(key, 0) for item in results)
            for key in {key for item in results for key in item.model_failure_subtype_counts}
        }
    )
    cost = sum((Decimal(item.estimated_cost_usd) for item in results), Decimal("0"))
    typed = sum(item.typed_no_call for item in results)
    completion = sum(item.completion_unusable for item in results)
    values: dict[str, Any] = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "preexecution_validity_audit_id": prepared.preexecution_validity.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "terminal_counts": terminal_counts,
        "provider_call_count": sum(item.provider_call_count for item in results),
        "http_success_call_count": sum(item.http_success_call_count for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length_total for item in results
        ),
        "reasoning_tokens_total": sum(item.reasoning_tokens_total for item in results),
        "completion_tokens_total": sum(item.completion_tokens_total for item in results),
        "primary_attempt_count": sum(item.primary_attempt_count for item in results),
        "rescue_attempt_count": sum(item.rescue_attempt_count for item in results),
        "rescue_success_count": sum(item.rescue_success for item in results),
        "direct_usable_request_count": sum(item.direct_usable_request_count for item in results),
        "rescued_usable_request_count": sum(item.rescued_usable_request_count for item in results),
        "completion_failure_counts": dict(sorted(completion_failures.items())),
        "model_failure_family_counts": dict(sorted(family_counts.items())),
        "model_failure_subtype_counts": dict(sorted(subtype_counts.items())),
        "semantic_compile_rejection_job_count": sum(
            bool(item.semantic_compile_rejection_count) for item in results
        ),
        "duplicate_failed_proposal_job_count": sum(
            bool(item.duplicate_failed_proposal_count) for item in results
        ),
        "typed_no_call_job_count": typed,
        "typed_no_call_cp95_upper_32": _cp_upper(typed, 32),
        "completion_unusable_job_count": completion,
        "completion_unusable_cp95_upper_32": _cp_upper(completion, 32),
        "provider_transport_failure_job_count": sum(
            item.provider_transport_failure for item in results
        ),
        "instrument_failure_job_count": sum(item.instrument_failure for item in results),
        "model_invalid_trajectory_count": sum(
            item.terminal_category == "model_invalid_trajectory" for item in results
        ),
        "program_closed_count": sum(item.program_closed for item in results),
        "mechanism_success_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(item.independent_validity for item in results),
        "requested_path_adherence_count": sum(item.requested_path_adhered for item in results),
        "cell_summaries": _cell_summaries(results),
        "exact_model_passed": all(item.exact_model_passed for item in results),
        "native_tool_absence_passed": all(item.native_tool_absent for item in results),
        "thinking_continuity_passed": all(item.thinking_continuity_passed for item in results),
        "provider_usage_complete": all(item.provider_usage_complete for item in results),
        "fallback_absence_passed": all(item.fallback_absent for item in results),
        "dynamic_precall_binding_passed": all(
            item.dynamic_precall_binding_passed for item in results
        ),
        "exact_request_binding_passed": all(item.exact_request_binding_passed for item in results),
        "empirical_budget_adequacy_passed": typed == 0,
        "stage_two_authority_passed": all(
            item.reversible_commit_passed and not item.host_semantic_action_inserted
            for item in results
        ),
        "replay_v3_passed": all(item.replay_v3_passed for item in results),
    }
    provisional = TwoStageExecutionReport.model_construct(report_id="pending", **values)
    return TwoStageExecutionReport(
        report_id=two_stage_execution_report_id(provisional),
        **values,
    )


def _load_checkpoint(
    path: Path,
    *,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[TwoStageJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        TwoStageJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.static.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.110 checkpoint contains duplicate Jobs")
    for result in rows:
        job = jobs.get(result.job_id)
        if job is None or result.runner_contract_id != prepared.runner_contract.contract_id:
            raise ValueError("v26.110 checkpoint crosses the frozen denominator")
        path = raw_execution_path(output_dir, job)
        if sha256_file(path) != result.raw_execution_artifact.sha256:
            raise ValueError("v26.110 checkpoint Raw binding changed")
    return rows


ClientFactory = Callable[[AgentModelConfig, TwoStageJob, Any], Any]


def _default_client_factory(
    config: AgentModelConfig,
    _job: TwoStageJob,
    _binding: Any,
) -> StageOneProspectiveThinkingJsonClient:
    return StageOneProspectiveThinkingJsonClient(config)


def _run_one_job(
    *,
    job: TwoStageJob,
    prepared: PreparedExecution,
    client_factory: ClientFactory | None,
    output_dir: Path,
) -> tuple[TwoStageJobResult, TwoStageRawExecution]:
    binding = two_stage_runtime_binding(prepared.static, job)
    client = (
        None
        if client_factory is None
        else client_factory(prepared.static.agent_model_config, job, binding)
    )
    raw = execute_two_stage_job_raw(
        job=job,
        runner_contract=prepared.runner_contract,
        static=prepared.static,
        binding=binding,
        client=client,
        output_dir=output_dir,
    )
    result = project_job_result(
        raw=raw,
        prepared=prepared,
        output_dir=output_dir,
    )
    return result, raw


def _write_checkpoint(path: Path, rows: Sequence[TwoStageJobResult]) -> None:
    payload = b"\n".join(_canonical_bytes(item.model_dump(mode="json")) for item in rows)
    if payload:
        payload += b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def run_two_stage_calibration(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
    workers: int,
    client_factory: ClientFactory = _default_client_factory,
) -> TwoStageExecutionReport:
    prepared = prepare_two_stage_execution(
        runner_preflight_dir=runner_preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint_path = output_dir / "two_stage_job_results.checkpoint.jsonl"
    existing = _load_checkpoint(
        checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.job_id: item for item in existing}
    jobs = prepared.static.manifest.jobs
    pending = [item for item in jobs if item.job_id not in completed]
    report_path = output_dir / "report.json"
    if pending and report_path.exists():
        raise ValueError("v26.110 completed report exists while Jobs remain pending")
    if not pending and report_path.exists():
        report = TwoStageExecutionReport.model_validate(_load(report_path))
        if report.runner_contract_id != prepared.runner_contract.contract_id:
            raise ValueError("v26.110 completed report crosses Runner Contracts")
        return report
    raw_recovery_jobs = [item for item in pending if raw_execution_path(output_dir, item).exists()]
    model_pending_jobs = [
        item for item in pending if not raw_execution_path(output_dir, item).exists()
    ]
    for job in model_pending_jobs:
        provider_dir = raw_provider_path(output_dir, job, 0).parent
        if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
            raise ValueError("orphan v26.110 Provider Artifacts require a fresh Recovery Contract")
    print(
        f"[v26.110] resuming {len(completed)}/32; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, TwoStageRawExecution] = {}
    for job in jobs:
        path = raw_execution_path(output_dir, job)
        if path.exists() and job.job_id in completed:
            raw_by_job[job.job_id] = TwoStageRawExecution.model_validate(_load(path))
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                client_factory=(None if job in raw_recovery_jobs else client_factory),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(future_map):
            job = future_map[future]
            result, raw = future.result()
            with lock:
                completed[job.job_id] = result
                raw_by_job[job.job_id] = raw
                ordered = tuple(completed[item.job_id] for item in jobs if item.job_id in completed)
                _write_checkpoint(checkpoint_path, ordered)
    results = tuple(completed[item.job_id] for item in jobs)
    if len(results) != 32:
        raise ValueError("v26.110 execution denominator is incomplete")
    for job in jobs:
        raw_by_job.setdefault(
            job.job_id,
            TwoStageRawExecution.model_validate(_load(raw_execution_path(output_dir, job))),
        )
    lineage = raw_lineage_audit(
        results=results,
        raw_by_job=raw_by_job,
        output_dir=output_dir,
    )
    report = make_execution_report(
        prepared=prepared,
        results=results,
        lineage=lineage,
    )
    write_json_atomic(
        output_dir / "two_stage_job_results.json",
        [item.model_dump(mode="json") for item in results],
    )
    write_json_atomic(
        output_dir / "raw_lineage_audit.json",
        lineage.model_dump(mode="json"),
    )
    write_json_atomic(report_path, report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the exact v26.110 two-stage semantic Proposal calibration"
    )
    parser.add_argument(
        "--runner-preflight-dir",
        type=Path,
        default=Path(RUNNER_PREFLIGHT_DIR),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument(
        "--implementation-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_two_stage_execution(
            runner_preflight_dir=args.runner_preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
            implementation_root=args.implementation_root,
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "source_replay_audit_id": prepared.source_replay.audit_id,
                    "runner_contract_id": prepared.runner_contract.contract_id,
                    "expected_jobs": len(prepared.static.manifest.jobs),
                    "model_client_constructed": False,
                    "provider_calls": 0,
                },
                indent=2,
            )
        )
        return
    report = run_two_stage_calibration(
        runner_preflight_dir=args.runner_preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
