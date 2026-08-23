from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_final_semantic_action_calibration_online as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_final_grammar_privacy_rematerialization as static_stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_runner_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    _progress_diagnostic,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_125_exact_final_semantic_action_postrun_audit_v1_20260823"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_125_exact_final_semantic_action_postrun_audit_v1_20260823"
)
EXECUTION_DIR: Final = execution.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_exact_final_semantic_action_postrun_audit.py"
)
EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_exact_final_semantic_action_execution_report:"
    "39098697c35cd453f68ddc546cb1bd8cc0d0e9e3d2c8552fc9ff49cbf9794eb3"
)
EXPECTED_EXECUTION_SOURCE_REPLAY_ID: Final = (
    "finance_v26_exact_final_execution_source_replay:"
    "202f2394e2a20d2edd5062b5186f8de875b4bb621a68bc4569fe874ea64d2a01"
)
EXPECTED_RAW_LINEAGE_ID: Final = (
    "finance_v26_exact_final_raw_lineage:"
    "b073a2121fc1a124dc5d59acbac6edee667ade25a59f6b3d15b183b52d993977"
)
NEXT_STAGE: Final = "fresh_exact_failed_call_transport_recovery_contract_and_runner_preflight_only"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_124_transitive_source",
        "v26_124_execution_file",
        "v26_125_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class AuditSourceReplay(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_EXECUTION_SOURCE_REPLAY_ID
    predecessor_transitive_file_count: Literal[2562] = 2562
    execution_file_count: Literal[402] = 402
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2965] = 2965
    replay_pass_count: Literal[2965] = 2965
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2965, max_length=2965)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_final_postrun_source_replay.v1"] = (
        "finance_v26_exact_final_postrun_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> AuditSourceReplay:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 2965:
            raise ValueError("v26.125 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.125 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_exact_final_postrun_source_replay:",
        ):
            raise ValueError("v26.125 source replay identity changed")
        return self


class RawLineageReaudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_raw_lineage_id: str = EXPECTED_RAW_LINEAGE_ID
    execution_file_count: Literal[402] = 402
    top_level_file_count: Literal[12] = 12
    raw_execution_count: Literal[32] = 32
    provider_envelope_count: Literal[179] = 179
    public_payload_projection_count: Literal[179] = 179
    complete_provider_pair_count: Literal[179] = 179
    checkpoint_row_count: Literal[32] = 32
    job_result_count: Literal[32] = 32
    checkpoint_result_match_count: Literal[32] = 32
    raw_descriptor_match_count: Literal[32] = 32
    envelope_descriptor_match_count: Literal[179] = 179
    projection_descriptor_match_count: Literal[179] = 179
    unique_envelope_id_count: Literal[179] = 179
    unique_projection_id_count: Literal[179] = 179
    envelope_only_orphan_count: Literal[0] = 0
    projection_only_orphan_count: Literal[0] = 0
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_content_persistence_count: Literal[0] = 0
    invalid_payload_key_persistence_count: Literal[0] = 0
    replay_v3_pass_count: Literal[32] = 32
    completed_verification_rebuild_count: Literal[17] = 17
    completed_verification_match_count: Literal[17] = 17
    report_terminal_counts_reproduced: Literal[True] = True
    report_provider_counts_reproduced: Literal[True] = True
    report_usage_reproduced: Literal[True] = True
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_final_raw_lineage_reaudit.v1"] = (
        "finance_v26_exact_final_raw_lineage_reaudit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RawLineageReaudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_exact_final_raw_lineage_reaudit:",
        ):
            raise ValueError("v26.125 Raw Lineage reaudit identity changed")
        return self


class FailedCallRecoveryCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    failed_provider_envelope_id: str = Field(min_length=1)
    failed_payload_projection_id: str = Field(min_length=1)
    provider_call_index: int = Field(ge=0, le=2)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: runner.PublicAttemptPhase
    request_prompt_sha256: str = Field(min_length=64, max_length=64)
    dynamic_certificate_id: str = Field(min_length=1)
    request_binding_certificate_id: str = Field(min_length=1)
    resource_certificate_id: str = Field(min_length=1)
    successful_prefix_provider_call_count: int = Field(ge=0, le=2)
    successful_prefix_provider_envelope_ids: tuple[str, ...]
    cumulative_provider_tokens_before_failure: int = Field(ge=0)
    abi_rescue_count_before: int = Field(ge=0, le=1)
    semantic_recovery_count_before: int = Field(ge=0, le=1)
    http_success: bool
    http_status: int | None = None
    error_type: Literal["IncompleteRead", "URLError"]
    failure_artifact_type: str | None = None
    response_model_retained: Literal[False] = False
    usage_retained: Literal[False] = False
    public_payload_retained: Literal[False] = False
    replacement_response_required: Literal[True] = True
    continuation_may_require_further_calls: Literal[True] = True
    historical_job_reclassified: Literal[False] = False
    schema_version: Literal["finance_v26_failed_call_recovery_candidate.v1"] = (
        "finance_v26_failed_call_recovery_candidate.v1"
    )

    @model_validator(mode="after")
    def validate_candidate(self) -> FailedCallRecoveryCandidate:
        if self.successful_prefix_provider_call_count != len(
            self.successful_prefix_provider_envelope_ids
        ):
            raise ValueError("v26.125 recovery prefix denominator changed")
        if self.candidate_id != _identity(
            self,
            "candidate_id",
            "finance_v26_failed_call_recovery_candidate:",
        ):
            raise ValueError("v26.125 recovery Candidate identity changed")
        return self


class ProviderFailureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    provider_call_count: Literal[179] = 179
    http_success_count: Literal[177] = 177
    admitted_complete_success_count: Literal[169] = 169
    http_200_incomplete_read_count: Literal[8] = 8
    no_http_connection_refused_count: Literal[2] = 2
    channel_parse_failure_with_complete_telemetry_count: Literal[1] = 1
    provider_failure_no_payload_projection_count: Literal[11] = 11
    exact_model_complete_success_count: Literal[169] = 169
    thinking_complete_success_count: Literal[169] = 169
    usage_complete_success_count: Literal[169] = 169
    native_tool_absent_complete_success_count: Literal[169] = 169
    fallback_or_discovery_count: Literal[0] = 0
    privacy_rejected_count: Literal[0] = 0
    prompt_tokens: Literal[538841] = 538841
    completion_tokens: Literal[264115] = 264115
    reasoning_tokens: Literal[243484] = 243484
    total_tokens: Literal[802956] = 802956
    estimated_cost_usd: Literal["0.14938994000000001406"] = "0.14938994000000001406"
    instrument_failure_job_count: Literal[10] = 10
    failed_call_recovery_candidate_count: Literal[10] = 10
    failed_call_recovery_candidates: tuple[FailedCallRecoveryCandidate, ...] = Field(
        min_length=10,
        max_length=10,
    )
    historical_instrument_terminals_reclassified: Literal[False] = False
    unique_provider_or_network_cause_claimed: Literal[False] = False
    status: Literal["instrument_recovery_required"] = "instrument_recovery_required"
    schema_version: Literal["finance_v26_exact_final_provider_failure_audit.v1"] = (
        "finance_v26_exact_final_provider_failure_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ProviderFailureAudit:
        jobs = tuple(item.historical_job_id for item in self.failed_call_recovery_candidates)
        if jobs != tuple(sorted(set(jobs))) or len(jobs) != 10:
            raise ValueError("v26.125 recovery Candidate Jobs changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_exact_final_provider_failure_audit:",
        ):
            raise ValueError("v26.125 Provider failure identity changed")
        return self


class FinalOutcomeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_manifest_job_count: Literal[32] = 32
    instrument_failure_job_count: Literal[10] = 10
    complete_model_outcome_job_count: Literal[22] = 22
    program_closed_model_outcome_count: Literal[22] = 22
    terminal_node_completed_model_outcome_count: Literal[22] = 22
    terminal_verification_completed_model_outcome_count: Literal[22] = 22
    final_commit_model_outcome_count: Literal[22] = 22
    final_primary_attempt_count: Literal[22] = 22
    final_rescue_attempt_count: Literal[5] = 5
    final_validated_public_payload_count: Literal[27] = 27
    exact_two_top_level_field_count: Literal[27] = 27
    answer_object_count: Literal[17] = 17
    answer_string_count: Literal[10] = 10
    exact_final_grammar_payload_count: Literal[17] = 17
    final_grammar_failure_attempt_count: Literal[10] = 10
    final_grammar_failure_job_count: Literal[5] = 5
    final_grammar_failure_jobs: tuple[str, ...] = Field(min_length=5, max_length=5)
    final_answer_emitted_count: Literal[17] = 17
    independently_valid_answer_count: Literal[11] = 11
    answer_projection_failure_count: Literal[3] = 3
    mechanism_failure_count: Literal[3] = 3
    citation_failure_count: Literal[0] = 0
    evidence_support_failure_count: Literal[0] = 0
    model_invalid_trajectory_count: Literal[11] = 11
    model_valid_trajectory_count: Literal[11] = 11
    privacy_rejected_count: Literal[0] = 0
    exact_32_job_endpoint_rate_estimable: Literal[False] = False
    model_outcome_subset_descriptive_only: Literal[True] = True
    action_protocol_or_budget_change_supported: Literal[False] = False
    historical_model_results_reclassified: Literal[False] = False
    schema_version: Literal["finance_v26_exact_final_outcome_audit.v1"] = (
        "finance_v26_exact_final_outcome_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FinalOutcomeAudit:
        if self.final_grammar_failure_jobs != tuple(sorted(set(self.final_grammar_failure_jobs))):
            raise ValueError("v26.125 Final Grammar failure Jobs changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_exact_final_outcome_audit:",
        ):
            raise ValueError("v26.125 Final outcome identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    provider_failure_audit_id: str = Field(min_length=1)
    failed_call_recovery_candidate_ids: tuple[str, ...] = Field(
        min_length=10,
        max_length=10,
    )
    exact_recovery_candidate_count: Literal[10] = 10
    preserved_model_outcome_job_count: Literal[22] = 22
    status: Literal["instrument_failure_recovery_preflight_required"] = (
        "instrument_failure_recovery_preflight_required"
    )
    next_permitted_stage: str = NEXT_STAGE
    provider_calls_authorized: Literal[False] = False
    fresh_recovery_contract_manifest_job_and_runner_identities_required: Literal[True] = True
    exact_successful_prefix_zero_generation_replay_required: Literal[True] = True
    exact_failed_request_rebinding_required: Literal[True] = True
    one_replacement_response_per_failed_call_maximum: Literal[True] = True
    continuation_under_original_remaining_resource_and_recovery_bounds_only: Literal[True] = True
    historical_v26_124_job_rerun_or_reclassification_authorized: Literal[False] = False
    completed_model_outcome_rerun_or_reclassification_authorized: Literal[False] = False
    semantic_action_candidate_final_grammar_model_or_resource_change_authorized: Literal[False] = (
        False
    )
    role_state_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_exact_final_postrun_transition.v1"] = (
        "finance_v26_exact_final_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.failed_call_recovery_candidate_ids != tuple(
            sorted(set(self.failed_call_recovery_candidate_ids))
        ):
            raise ValueError("v26.125 transition Candidate IDs changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_exact_final_postrun_transition:",
        ):
            raise ValueError("v26.125 transition identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    stage_two_provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[10] = 10
    rejection_count: Literal[10] = 10
    mutations: tuple[MutationResult, ...] = Field(min_length=10, max_length=10)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_final_postrun_destructive.v1"] = (
        "finance_v26_exact_final_postrun_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))) or len(names) != 10:
            raise ValueError("v26.125 destructive controls changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_exact_final_postrun_destructive:",
        ):
            raise ValueError("v26.125 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    raw_lineage_reaudit_id: str = Field(min_length=1)
    provider_failure_audit_id: str = Field(min_length=1)
    final_outcome_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=6, max_length=6)
    exact_manifest_job_count: Literal[32] = 32
    complete_raw_count: Literal[32] = 32
    provider_call_count: Literal[179] = 179
    complete_model_outcome_count: Literal[22] = 22
    instrument_failure_count: Literal[10] = 10
    independently_valid_count: Literal[11] = 11
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    exact_endpoint_denominator_complete: Literal[False] = False
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["instrument_failure_recovery_preflight_required"] = (
        "instrument_failure_recovery_preflight_required"
    )
    schema_version: Literal["finance_v26_exact_final_postrun_audit_report.v1"] = (
        "finance_v26_exact_final_postrun_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_exact_final_postrun_audit_report:",
        ):
            raise ValueError("v26.125 report identity changed")
        return self


class LoadedExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    report: execution.ExactFinalExecutionReport
    raw_lineage: execution.ExactFinalRawLineageAudit
    results: tuple[execution.ExactFinalJobResult, ...]
    checkpoint: tuple[execution.ExactFinalJobResult, ...]
    raws: tuple[runner.PrivacyFirstRawExecution, ...]
    static: static_stage.FinalGrammarStaticInputs


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    runner.write_json_atomic(path, payload)


def _descriptor(path: Path, root: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(root.resolve())),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def _detail(path: Path, root: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(root)),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def _recursive_keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _recursive_keys(item)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(key for item in value for key in _recursive_keys(item))
    return ()


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        path = root / relative_path
        if path.is_file() and legacy.sha256_file(path) == expected_sha256:
            return path
    raise ValueError(f"v26.125 cannot replay bound file: {relative_path}")


def _build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> AuditSourceReplay:
    predecessor = execution.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "online_source_replay_audit.json")
    )
    report = execution.ExactFinalExecutionReport.model_validate(
        _load(execution_dir / "report.json")
    )
    if (
        predecessor.audit_id != EXPECTED_EXECUTION_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_EXECUTION_REPORT_ID
    ):
        raise ValueError("v26.125 predecessor execution identity changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_124_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    execution_files = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if len(execution_files) != 402:
        raise ValueError("v26.125 execution file denominator changed")
    for path in execution_files:
        relative = str(Path(EXECUTION_DIR) / path.relative_to(execution_dir))
        digest = legacy.sha256_file(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_124_execution_file",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    implementation = implementation_root / IMPLEMENTATION_PATH
    digest = legacy.sha256_file(implementation)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_125_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=implementation.stat().st_size,
    )
    values: dict[str, Any] = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = AuditSourceReplay.model_construct(audit_id="pending", **values)
    return AuditSourceReplay(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_final_postrun_source_replay:",
        ),
        **values,
    )


def _load_execution(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> LoadedExecution:
    report = execution.ExactFinalExecutionReport.model_validate(
        _load(execution_dir / "report.json")
    )
    lineage = execution.ExactFinalRawLineageAudit.model_validate(
        _load(execution_dir / "raw_lineage_audit.json")
    )
    results = tuple(
        execution.ExactFinalJobResult.model_validate(item)
        for item in _load(execution_dir / "exact_final_job_results.json")
    )
    checkpoint = tuple(
        execution.ExactFinalJobResult.model_validate_json(line)
        for line in (execution_dir / "exact_final_job_results.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    static = static_stage.load_final_grammar_static_inputs(package_root, implementation_root)
    jobs = {item.job_id: item for item in static.manifest.jobs}
    raws = tuple(
        runner.PrivacyFirstRawExecution.model_validate(
            _load(runner.raw_execution_path(execution_dir, jobs[result.job_id]))
        )
        for result in results
    )
    if (
        report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or lineage.audit_id != EXPECTED_RAW_LINEAGE_ID
        or len(results) != 32
        or checkpoint != results
        or len(raws) != 32
        or tuple(item.job_id for item in results)
        != tuple(item.job_id for item in static.manifest.jobs)
    ):
        raise ValueError("v26.125 execution aggregate binding changed")
    return LoadedExecution(
        report=report,
        raw_lineage=lineage,
        results=results,
        checkpoint=checkpoint,
        raws=raws,
        static=static,
    )


def _provider_pairs(
    raw: runner.PrivacyFirstRawExecution,
    execution_dir: Path,
) -> tuple[tuple[runner.PrivacyFirstProviderEnvelope, runner.PublicPayloadProjection], ...]:
    envelopes: list[runner.PrivacyFirstProviderEnvelope] = []
    projections: list[runner.PublicPayloadProjection] = []
    for descriptor in raw.provider_envelope_artifacts:
        path = execution_dir / descriptor.relative_path
        if (
            not path.is_file()
            or legacy.sha256_file(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.125 Envelope descriptor changed")
        envelopes.append(runner.PrivacyFirstProviderEnvelope.model_validate(_load(path)))
    for descriptor in raw.public_payload_projection_artifacts:
        path = execution_dir / descriptor.relative_path
        if (
            not path.is_file()
            or legacy.sha256_file(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.125 Projection descriptor changed")
        projections.append(runner.PublicPayloadProjection.model_validate(_load(path)))
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        runner.validate_provider_artifact_pair(envelope, projection)
    return pairs


def _build_lineage_reaudit(
    loaded: LoadedExecution,
    *,
    execution_dir: Path,
) -> RawLineageReaudit:
    result_by_job = {item.job_id: item for item in loaded.results}
    envelope_ids: list[str] = []
    projection_ids: list[str] = []
    private_hits = 0
    raw_descriptors: list[legacy.RawFileDescriptor] = []
    envelope_descriptors: list[legacy.RawFileDescriptor] = []
    projection_descriptors: list[legacy.RawFileDescriptor] = []
    replay_passes = 0
    completed_rebuilds = 0
    completed_matches = 0
    invalid_content_hits = 0
    invalid_key_hits = 0
    for raw in loaded.raws:
        result = result_by_job[raw.job.job_id]
        raw_path = runner.raw_execution_path(execution_dir, raw.job)
        descriptor = _descriptor(raw_path, execution_dir)
        if descriptor != result.raw_execution_artifact:
            raise ValueError("v26.125 Job Result Raw descriptor changed")
        raw_descriptors.append(descriptor)
        pairs = _provider_pairs(raw, execution_dir)
        for index, (envelope, projection) in enumerate(pairs):
            envelope_descriptor = raw.provider_envelope_artifacts[index]
            projection_descriptor = raw.public_payload_projection_artifacts[index]
            envelope_path = execution_dir / envelope_descriptor.relative_path
            projection_path = execution_dir / projection_descriptor.relative_path
            envelope_ids.append(envelope.envelope_id)
            projection_ids.append(projection.projection_id)
            envelope_descriptors.append(_descriptor(envelope_path, execution_dir))
            projection_descriptors.append(_descriptor(projection_path, execution_dir))
            forbidden = {"private_reasoning", "reasoning_content", "reasoning_trace"}
            private_hits += int(bool(forbidden & set(_recursive_keys(_load(envelope_path)))))
            private_hits += int(bool(forbidden & set(_recursive_keys(_load(projection_path)))))
            private_hits += int(
                envelope.private_reasoning_content_persisted
                or envelope.private_reasoning_content_hashed
                or projection.private_reasoning_content_persisted
            )
            invalid_content_hits += int(projection.invalid_payload_content_persisted)
            invalid_key_hits += int(projection.invalid_payload_key_persisted)
        binding = runner.privacy_first_runtime_binding(loaded.static, raw.job)
        replay = legacy.replay_v3(
            cast(Any, raw),
            static=loaded.static.predecessor.historical,
            binding=binding,
        )
        replay_passes += int(replay.passed)
        if raw.completed_result is not None:
            completed_rebuilds += 1
            verification, mechanism = preflight._completed_verification(
                raw=cast(Any, raw),
                replay=replay,
                binding=binding,
            )
            completed_matches += int(
                verification == result.verification_report
                and verification.valid == result.final_answer_semantically_valid
                and mechanism == result.mechanism_outcome
            )
    expected_lineage = tuple(
        sorted(
            (*raw_descriptors, *envelope_descriptors, *projection_descriptors),
            key=lambda item: item.relative_path,
        )
    )
    if expected_lineage != loaded.raw_lineage.files:
        raise ValueError("v26.125 predecessor Raw Lineage file set changed")
    all_files = tuple(path for path in execution_dir.rglob("*") if path.is_file())
    top_level = tuple(path for path in execution_dir.iterdir() if path.is_file())
    terminal_counts = dict(
        sorted(Counter(item.terminal_category for item in loaded.results).items())
    )
    provider_count = sum(item.stage_one_provider_call_count for item in loaded.raws)
    prompt_tokens = sum(
        item.prompt_tokens or 0 for raw in loaded.raws for item in raw.provider_telemetry
    )
    completion_tokens = sum(
        item.completion_tokens or 0 for raw in loaded.raws for item in raw.provider_telemetry
    )
    total_tokens = sum(
        item.total_tokens or 0 for raw in loaded.raws for item in raw.provider_telemetry
    )
    cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for raw in loaded.raws
            for item in raw.provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    if (
        len(all_files) != 402
        or len(top_level) != 12
        or terminal_counts != loaded.report.terminal_counts
        or provider_count != loaded.report.provider_call_count
        or prompt_tokens != loaded.report.provider_prompt_tokens
        or completion_tokens != loaded.report.provider_completion_tokens
        or total_tokens != loaded.report.provider_total_tokens
        or format(cost, "f") != loaded.report.estimated_cost_usd
    ):
        raise ValueError("v26.125 report aggregate did not reproduce")
    values: dict[str, Any] = {
        "checkpoint_result_match_count": sum(
            left == right for left, right in zip(loaded.checkpoint, loaded.results, strict=True)
        ),
        "raw_descriptor_match_count": len(raw_descriptors),
        "envelope_descriptor_match_count": len(envelope_descriptors),
        "projection_descriptor_match_count": len(projection_descriptors),
        "unique_envelope_id_count": len(set(envelope_ids)),
        "unique_projection_id_count": len(set(projection_ids)),
        "envelope_only_orphan_count": 0,
        "projection_only_orphan_count": 0,
        "private_reasoning_payload_count": private_hits,
        "invalid_payload_content_persistence_count": invalid_content_hits,
        "invalid_payload_key_persistence_count": invalid_key_hits,
        "replay_v3_pass_count": replay_passes,
        "completed_verification_rebuild_count": completed_rebuilds,
        "completed_verification_match_count": completed_matches,
    }
    provisional = RawLineageReaudit.model_construct(audit_id="pending", **values)
    return RawLineageReaudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_final_raw_lineage_reaudit:",
        ),
        **values,
    )


def _make_recovery_candidate(
    raw: runner.PrivacyFirstRawExecution,
    pairs: Sequence[tuple[runner.PrivacyFirstProviderEnvelope, runner.PublicPayloadProjection]],
) -> FailedCallRecoveryCandidate:
    envelope, projection = pairs[-1]
    telemetry = envelope.provider_telemetry
    error_type = telemetry.error_type
    if error_type not in {"IncompleteRead", "URLError"}:
        raise ValueError("v26.125 recovery Candidate is not a frozen transport failure")
    prefix = tuple(item[0] for item in pairs[:-1])
    prefix_projections = tuple(item[1] for item in pairs[:-1])
    if (
        projection.projection_status != "provider_failure_no_payload"
        or any(
            item.provider_telemetry.response_model != legacy.STAGE_ONE_MODEL_ID for item in prefix
        )
        or any(item.projection_status != "validated_public_payload" for item in prefix_projections)
    ):
        raise ValueError("v26.125 recovery Candidate prefix or failed Projection changed")
    values: dict[str, Any] = {
        "historical_job_id": raw.job.job_id,
        "failed_provider_envelope_id": envelope.envelope_id,
        "failed_payload_projection_id": projection.projection_id,
        "provider_call_index": envelope.provider_call_index,
        "request_kind": envelope.request_kind,
        "public_attempt_phase": envelope.public_attempt_phase,
        "request_prompt_sha256": envelope.prompt_sha256,
        "dynamic_certificate_id": envelope.dynamic_certificate.certificate_id,
        "request_binding_certificate_id": envelope.request_binding_certificate.certificate_id,
        "resource_certificate_id": envelope.resource_certificate_id,
        "successful_prefix_provider_call_count": len(prefix),
        "successful_prefix_provider_envelope_ids": tuple(item.envelope_id for item in prefix),
        "cumulative_provider_tokens_before_failure": sum(
            item.provider_telemetry.total_tokens or 0 for item in prefix
        ),
        "abi_rescue_count_before": envelope.dynamic_certificate.abi_rescue_count_before,
        "semantic_recovery_count_before": (
            envelope.dynamic_certificate.semantic_recovery_count_before
        ),
        "http_success": telemetry.http_success,
        "http_status": telemetry.http_status,
        "error_type": error_type,
        "failure_artifact_type": (
            envelope.failure_artifact.failure_type
            if envelope.failure_artifact is not None
            else None
        ),
    }
    provisional = FailedCallRecoveryCandidate.model_construct(candidate_id="pending", **values)
    return FailedCallRecoveryCandidate(
        candidate_id=_identity(
            provisional,
            "candidate_id",
            "finance_v26_failed_call_recovery_candidate:",
        ),
        **values,
    )


def _build_provider_failure_audit(
    loaded: LoadedExecution,
    *,
    execution_dir: Path,
) -> ProviderFailureAudit:
    all_pairs: list[tuple[runner.PrivacyFirstProviderEnvelope, runner.PublicPayloadProjection]] = []
    candidates: list[FailedCallRecoveryCandidate] = []
    for raw in loaded.raws:
        pairs = _provider_pairs(raw, execution_dir)
        all_pairs.extend(pairs)
        if raw.terminal_disposition == "instrument_failure":
            candidates.append(_make_recovery_candidate(raw, pairs))
    healthy = tuple(
        (envelope, projection)
        for envelope, projection in all_pairs
        if envelope.provider_telemetry.response_model == legacy.STAGE_ONE_MODEL_ID
    )
    incomplete = tuple(
        envelope
        for envelope, _ in all_pairs
        if envelope.provider_telemetry.error_type == "IncompleteRead"
    )
    refused = tuple(
        envelope
        for envelope, _ in all_pairs
        if envelope.provider_telemetry.error_type == "URLError"
    )
    no_payload = tuple(
        (envelope, projection)
        for envelope, projection in all_pairs
        if projection.projection_status == "provider_failure_no_payload"
    )
    channel_parse = tuple(
        envelope
        for envelope, _ in no_payload
        if envelope.provider_telemetry.response_model == legacy.STAGE_ONE_MODEL_ID
    )
    exact = sum(
        envelope.provider_telemetry.model_requested == legacy.STAGE_ONE_MODEL_ID
        and envelope.provider_telemetry.model_selected == legacy.STAGE_ONE_MODEL_ID
        and envelope.provider_telemetry.response_model == legacy.STAGE_ONE_MODEL_ID
        for envelope, _ in healthy
    )
    thinking = sum(
        envelope.provider_telemetry.reasoning_content_present
        and (envelope.provider_telemetry.reasoning_content_length or 0) > 0
        and (envelope.provider_telemetry.reasoning_tokens or 0) > 0
        for envelope, _ in healthy
    )
    usage = sum(
        envelope.provider_telemetry.prompt_tokens is not None
        and envelope.provider_telemetry.completion_tokens is not None
        and envelope.provider_telemetry.total_tokens is not None
        and envelope.provider_telemetry.prompt_tokens
        + envelope.provider_telemetry.completion_tokens
        == envelope.provider_telemetry.total_tokens
        for envelope, _ in healthy
    )
    native_absent = sum(
        envelope.provider_telemetry.response_shape.get("provider_native_tool_call_observed")
        is False
        for envelope, _ in healthy
    )
    fallback = sum(
        envelope.provider_telemetry.fallback_used or envelope.provider_telemetry.discovery_attempted
        for envelope, _ in all_pairs
    )
    values: dict[str, Any] = {
        "http_success_count": sum(
            envelope.provider_telemetry.http_success for envelope, _ in all_pairs
        ),
        "admitted_complete_success_count": len(healthy),
        "http_200_incomplete_read_count": len(incomplete),
        "no_http_connection_refused_count": len(refused),
        "channel_parse_failure_with_complete_telemetry_count": len(channel_parse),
        "provider_failure_no_payload_projection_count": len(no_payload),
        "exact_model_complete_success_count": exact,
        "thinking_complete_success_count": thinking,
        "usage_complete_success_count": usage,
        "native_tool_absent_complete_success_count": native_absent,
        "fallback_or_discovery_count": fallback,
        "privacy_rejected_count": sum(
            projection.projection_status == "privacy_rejected" for _, projection in all_pairs
        ),
        "prompt_tokens": sum(
            envelope.provider_telemetry.prompt_tokens or 0 for envelope, _ in all_pairs
        ),
        "completion_tokens": sum(
            envelope.provider_telemetry.completion_tokens or 0 for envelope, _ in all_pairs
        ),
        "reasoning_tokens": sum(
            envelope.provider_telemetry.reasoning_tokens or 0 for envelope, _ in all_pairs
        ),
        "total_tokens": sum(
            envelope.provider_telemetry.total_tokens or 0 for envelope, _ in all_pairs
        ),
        "estimated_cost_usd": format(
            sum(
                (
                    Decimal(str(envelope.provider_telemetry.estimated_cost))
                    for envelope, _ in all_pairs
                    if envelope.provider_telemetry.estimated_cost is not None
                ),
                Decimal("0"),
            ),
            "f",
        ),
        "failed_call_recovery_candidates": tuple(
            sorted(candidates, key=lambda item: item.historical_job_id)
        ),
    }
    provisional = ProviderFailureAudit.model_construct(audit_id="pending", **values)
    return ProviderFailureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_final_provider_failure_audit:",
        ),
        **values,
    )


def _build_final_outcome_audit(
    loaded: LoadedExecution,
    *,
    execution_dir: Path,
) -> FinalOutcomeAudit:
    result_by_job = {item.job_id: item for item in loaded.results}
    model_raws = tuple(
        raw
        for raw in loaded.raws
        if result_by_job[raw.job.job_id].terminal_category
        in {"model_invalid_trajectory", "model_valid_trajectory"}
    )
    if len(model_raws) != 22:
        raise ValueError("v26.125 complete model-outcome denominator changed")

    program_closed = 0
    terminal_completed = 0
    terminal_verified = 0
    final_commits = 0
    final_primary_attempts = 0
    final_rescue_attempts = 0
    final_payloads = 0
    exact_top_level = 0
    answer_objects = 0
    answer_strings = 0
    exact_final_payloads = 0
    grammar_failure_attempts = 0
    grammar_failure_jobs: set[str] = set()
    completed_results = 0
    valid_answers = 0
    answer_projection_failures = 0
    mechanism_failures = 0
    citation_failures = 0
    evidence_support_failures = 0
    recomputed_terminals: Counter[str] = Counter()

    for raw in model_raws:
        result = result_by_job[raw.job.job_id]
        binding = runner.privacy_first_runtime_binding(loaded.static, raw.job)
        _, _, closed, completed, verified = _progress_diagnostic(
            binding.record,
            raw.observations,
        )
        program_closed += int(closed)
        terminal_completed += int(completed)
        terminal_verified += int(verified)

        commits = tuple(item for item in raw.commits if item.commit.action == "emit_final")
        if len(commits) != 1:
            raise ValueError("v26.125 model outcome lacks one exact Final Commit")
        final_commits += 1
        final_commit = commits[0]
        host_envelope = runner.make_final_response_host_envelope(
            terminal_state_id=final_commit.public_state_id,
            terminal_commit_id=final_commit.commit.commit_id,
            grammar=loaded.static.final_grammar,
        )

        pairs = _provider_pairs(raw, execution_dir)
        projection_by_call = {
            envelope.provider_call_index: projection for envelope, projection in pairs
        }
        final_attempts = tuple(item for item in raw.attempts if item.request_kind == "final_answer")
        final_primary_attempts += sum(
            item.public_attempt_phase == "primary" for item in final_attempts
        )
        final_rescue_attempts += sum(
            item.public_attempt_phase == "abi_rescue" for item in final_attempts
        )
        accepted_for_job = 0
        for attempt in final_attempts:
            if (
                attempt.provider_call_index is None
                or attempt.final_response_host_envelope_id != host_envelope.envelope_id
            ):
                raise ValueError("v26.125 Final attempt Host Envelope binding changed")
            projection = projection_by_call[attempt.provider_call_index]
            if (
                projection.projection_status != "validated_public_payload"
                or projection.response_payload is None
            ):
                raise ValueError("v26.125 Final public Payload denominator changed")
            payload = projection.response_payload
            final_payloads += 1
            exact_top_level += int(set(payload) == {"answer", "rationale_summary"})
            answer = payload.get("answer")
            answer_objects += int(isinstance(answer, Mapping))
            answer_strings += int(isinstance(answer, str))
            try:
                runner.parse_exact_final_response_payload(
                    payload,
                    grammar=loaded.static.final_grammar,
                    envelope=host_envelope,
                )
            except runner.ExactFinalResponseRejection:
                grammar_failure_attempts += 1
                grammar_failure_jobs.add(raw.job.job_id)
            else:
                accepted_for_job += 1
                exact_final_payloads += 1
        if accepted_for_job != int(raw.completed_result is not None):
            raise ValueError("v26.125 Final parser and completed Result diverged")

        if raw.completed_result is None:
            recomputed_terminals["model_invalid_trajectory"] += 1
            if result.terminal_category != "model_invalid_trajectory":
                raise ValueError("v26.125 Final Grammar terminal changed")
            continue

        completed_results += 1
        if raw.completed_result.final_response_host_envelope != host_envelope:
            raise ValueError("v26.125 completed Final Host Envelope changed")
        replay = legacy.replay_v3(
            cast(Any, raw),
            static=loaded.static.predecessor.historical,
            binding=binding,
        )
        verification, _ = preflight._completed_verification(
            raw=cast(Any, raw),
            replay=replay,
            binding=binding,
        )
        valid_answers += int(verification.valid)
        answer_projection_failures += int(not verification.checks["answer_projection_complete"])
        mechanism_failures += int(not verification.checks["mechanism_complete"])
        citation_failures += int(not verification.checks["citation_complete"])
        evidence_support_failures += int(not verification.checks["evidence_support_complete"])
        terminal = "model_valid_trajectory" if verification.valid else "model_invalid_trajectory"
        recomputed_terminals[terminal] += 1
        if result.terminal_category != terminal or result.verification_report != verification:
            raise ValueError("v26.125 independent Final verification changed")

    if recomputed_terminals != Counter(
        item.terminal_category for item in result_by_job.values() if not item.instrument_failure
    ):
        raise ValueError("v26.125 model terminal partition did not reproduce")
    privacy_rejected = sum(
        projection.projection_status == "privacy_rejected"
        for raw in loaded.raws
        for _, projection in _provider_pairs(raw, execution_dir)
    )
    values: dict[str, Any] = {
        "program_closed_model_outcome_count": program_closed,
        "terminal_node_completed_model_outcome_count": terminal_completed,
        "terminal_verification_completed_model_outcome_count": terminal_verified,
        "final_commit_model_outcome_count": final_commits,
        "final_primary_attempt_count": final_primary_attempts,
        "final_rescue_attempt_count": final_rescue_attempts,
        "final_validated_public_payload_count": final_payloads,
        "exact_two_top_level_field_count": exact_top_level,
        "answer_object_count": answer_objects,
        "answer_string_count": answer_strings,
        "exact_final_grammar_payload_count": exact_final_payloads,
        "final_grammar_failure_attempt_count": grammar_failure_attempts,
        "final_grammar_failure_job_count": len(grammar_failure_jobs),
        "final_grammar_failure_jobs": tuple(sorted(grammar_failure_jobs)),
        "final_answer_emitted_count": completed_results,
        "independently_valid_answer_count": valid_answers,
        "answer_projection_failure_count": answer_projection_failures,
        "mechanism_failure_count": mechanism_failures,
        "citation_failure_count": citation_failures,
        "evidence_support_failure_count": evidence_support_failures,
        "model_invalid_trajectory_count": recomputed_terminals["model_invalid_trajectory"],
        "model_valid_trajectory_count": recomputed_terminals["model_valid_trajectory"],
        "privacy_rejected_count": privacy_rejected,
    }
    provisional = FinalOutcomeAudit.model_construct(audit_id="pending", **values)
    return FinalOutcomeAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_final_outcome_audit:",
        ),
        **values,
    )


def _build_transition(provider: ProviderFailureAudit) -> ProspectiveTransitionContract:
    values: dict[str, Any] = {
        "provider_failure_audit_id": provider.audit_id,
        "failed_call_recovery_candidate_ids": tuple(
            sorted(item.candidate_id for item in provider.failed_call_recovery_candidates)
        ),
    }
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_exact_final_postrun_transition:",
        ),
        **values,
    )


def _expect_transition_rejection(
    name: str,
    transition: ProspectiveTransitionContract,
    changes: Mapping[str, Any],
) -> MutationResult:
    payload = transition.model_dump(mode="json")
    payload.update(changes)
    identity_input = {key: value for key, value in payload.items() if key != "contract_id"}
    identity_input["failed_call_recovery_candidate_ids"] = tuple(
        cast(Sequence[str], identity_input["failed_call_recovery_candidate_ids"])
    )
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **identity_input,
    )
    payload["contract_id"] = _identity(
        provisional,
        "contract_id",
        "finance_v26_exact_final_postrun_transition:",
    )
    try:
        ProspectiveTransitionContract.model_validate(payload)
    except (TypeError, ValueError):
        return MutationResult(name=name)
    raise ValueError(f"v26.125 destructive mutation was accepted: {name}")


def _build_destructive_audit(
    transition: ProspectiveTransitionContract,
) -> DestructiveAudit:
    candidate_ids = transition.failed_call_recovery_candidate_ids
    mutations = (
        _expect_transition_rejection(
            "completed_model_outcome_reclassification_authorized",
            transition,
            {"completed_model_outcome_rerun_or_reclassification_authorized": True},
        ),
        _expect_transition_rejection(
            "exact_failed_request_rebinding_removed",
            transition,
            {"exact_failed_request_rebinding_required": False},
        ),
        _expect_transition_rejection(
            "historical_job_rerun_authorized",
            transition,
            {"historical_v26_124_job_rerun_or_reclassification_authorized": True},
        ),
        _expect_transition_rejection(
            "one_replacement_limit_removed",
            transition,
            {"one_replacement_response_per_failed_call_maximum": False},
        ),
        _expect_transition_rejection(
            "provider_call_authorized_before_preflight",
            transition,
            {"provider_calls_authorized": True},
        ),
        _expect_transition_rejection(
            "recovery_candidate_duplicated",
            transition,
            {"failed_call_recovery_candidate_ids": (*candidate_ids[:-1], candidate_ids[0])},
        ),
        _expect_transition_rejection(
            "recovery_candidate_removed",
            transition,
            {"failed_call_recovery_candidate_ids": candidate_ids[:-1]},
        ),
        _expect_transition_rejection(
            "remaining_resource_bound_change_authorized",
            transition,
            {"continuation_under_original_remaining_resource_and_recovery_bounds_only": False},
        ),
        _expect_transition_rejection(
            "role_or_production_stage_authorized",
            transition,
            {"role_state_training_release_or_production_authorized": True},
        ),
        _expect_transition_rejection(
            "semantic_or_model_change_authorized",
            transition,
            {"semantic_action_candidate_final_grammar_model_or_resource_change_authorized": (True)},
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.name))
    values: dict[str, Any] = {"mutations": ordered}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_final_postrun_destructive:",
        ),
        **values,
    )


def build(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    output_dir: Path,
) -> PostrunAuditReport:
    source = _build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    loaded = _load_execution(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    lineage = _build_lineage_reaudit(loaded, execution_dir=execution_dir)
    provider = _build_provider_failure_audit(loaded, execution_dir=execution_dir)
    outcome = _build_final_outcome_audit(loaded, execution_dir=execution_dir)
    transition = _build_transition(provider)
    destructive = _build_destructive_audit(transition)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("raw_lineage_reaudit.json", lineage),
        ("provider_failure_audit.json", provider),
        ("final_outcome_audit.json", outcome),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    for name, artifact in artifacts:
        _write(output_dir / name, artifact)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in artifacts)
    values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "raw_lineage_reaudit_id": lineage.audit_id,
        "provider_failure_audit_id": provider.audit_id,
        "final_outcome_audit_id": outcome.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = PostrunAuditReport.model_construct(report_id="pending", **values)
    report = PostrunAuditReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_exact_final_postrun_audit_report:",
        ),
        **values,
    )
    _write(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Independently audit the v26.124 exact-Final calibration"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--execution-dir",
        type=Path,
        default=package_default / EXECUTION_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
