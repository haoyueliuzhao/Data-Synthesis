from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    evaluate_mechanism_estimand,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_calibration_execution import (  # noqa: E501
    ExactGrammarExecutionReport,
    ExactGrammarJobResult,
    ExecutionSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_execution import (  # noqa: E501
    load_exact_grammar_static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    RawStageOneProviderCall,
    TwoStageRawExecution,
    load_canonical_json,
    replay_v3,
    sha256_file,
    two_stage_runtime_binding,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    build_public_action_state,
    decompile_public_call,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_exact_response_grammar import (
    DECISION_FIELD_RULES,
    EXACT_RESPONSE_PROTOCOL_VERSION,
    EXACT_STAGE,
    FIELD_ORDER,
    ExactStageOneSemanticProposalPayload,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    STAGE_ONE_MODEL_ID,
)

RUN_ID: Final = "finance_v26_115_exact_response_grammar_calibration_postrun_audit_v1_20260823"
EXECUTION_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_114_exact_response_grammar_calibration_execution_v1_20260823"
)
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_115_exact_response_grammar_calibration_postrun_audit_v1_20260823"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_exact_response_grammar_calibration_postrun_audit.py"
)
EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_exact_grammar_execution_report:"
    "7b531b1887f1a244ecb0154975946f6e3739d1773bb850e1e5c91a9aa72a5ca3"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_two_stage_runner_contract:"
    "02340ee6c14e53831b6057e92c8d2e694572cfbfb9e7432835cb7e6f28053506"
)
NEXT_STAGE: Final = "fresh_host_bound_stage_metadata_semantic_proposal_preflight_only"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = Field(min_length=1)
    predecessor_transitive_file_count: Literal[2049] = 2049
    execution_file_count: Literal[122] = 122
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2172] = 2172
    replay_pass_count: Literal[2172] = 2172
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2172, max_length=2172)
    replay_before_execution_parsing: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_grammar_postrun_source_replay.v1"] = (
        "finance_v26_exact_grammar_postrun_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(paths)) or len(set(paths)) != 2172:
            raise ValueError("v26.115 source replay paths are not canonical and unique")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_grammar_postrun_source:"
        ):
            raise ValueError("v26.115 source replay identity changed")
        return self


class ExecutionLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    execution_file_count: Literal[122] = 122
    canonical_json_file_count: Literal[121] = 121
    canonical_jsonl_file_count: Literal[1] = 1
    checkpoint_row_count: Literal[32] = 32
    job_result_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    provider_artifact_count: Literal[81] = 81
    unique_provider_artifact_id_count: Literal[81] = 81
    raw_descriptor_count: Literal[113] = 113
    exact_byte_replay_pass_count: Literal[122] = 122
    parent_binding_pass_count: Literal[81] = 81
    certificate_triple_pass_count: Literal[81] = 81
    provider_usage_sum_passed: Literal[True] = True
    checkpoint_result_match_count: Literal[32] = 32
    private_reasoning_payload_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_grammar_execution_lineage_audit.v1"] = (
        "finance_v26_exact_grammar_execution_lineage_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionLineageAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_grammar_execution_lineage:"
        ):
            raise ValueError("v26.115 execution lineage identity changed")
        return self


class ResponseFunnelAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    provider_call_count: Literal[81] = 81
    http_success_count: Literal[81] = 81
    public_json_payload_count: Literal[81] = 81
    exact_ten_field_set_count: Literal[81] = 81
    registered_protocol_count: Literal[81] = 81
    exact_state_binding_count: Literal[81] = 81
    registered_decision_kind_count: Literal[81] = 81
    conditional_semantic_field_rule_count: Literal[81] = 81
    exact_stage_constant_count: Literal[54] = 54
    exact_schema_count: Literal[54] = 54
    parser_accepted_count: Literal[54] = 54
    semantic_proposal_commit_count: Literal[30] = 30
    public_observation_count: Literal[30] = 30
    program_closed_job_count: Literal[0] = 0
    independently_valid_job_count: Literal[0] = 0
    parser_independent_diagnostic_agreement_count: Literal[81] = 81
    mechanical_failure_count: Literal[27] = 27
    mechanical_failure_field_counts: dict[str, int]
    stage_value_counts: dict[str, int]
    decision_kind_counts: dict[str, int]
    exact_abi_failure_counts_by_logical_request_index: dict[str, int]
    schema_version: Literal["finance_v26_exact_response_funnel_audit.v1"] = (
        "finance_v26_exact_response_funnel_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ResponseFunnelAudit:
        if self.mechanical_failure_field_counts != {"stage_constant": 27}:
            raise ValueError("v26.115 mechanical ABI failure partition changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_exact_response_funnel:"):
            raise ValueError("v26.115 response funnel identity changed")
        return self


class SemanticRuntimeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_abi_accepted_count: Literal[54] = 54
    semantic_commit_count: Literal[30] = 30
    accepted_without_commit_count: Literal[24] = 24
    reversible_commit_count: Literal[30] = 30
    independently_decompiled_commit_count: Literal[30] = 30
    host_semantic_choice_inserted_count: Literal[0] = 0
    semantic_compile_rejection_job_count: Literal[21] = 21
    duplicate_failed_proposal_job_count: Literal[3] = 3
    terminal_exact_abi_failure_job_count: Literal[8] = 8
    semantic_compile_rejection_counts: dict[str, int]
    committed_decision_kind_counts: dict[str, int]
    observation_tool_status_counts: dict[str, int]
    failed_observation_error_counts: dict[str, int]
    observation_count: Literal[30] = 30
    successful_observation_count: Literal[23] = 23
    failed_observation_count: Literal[7] = 7
    verifier_v3_replay_pass_count: Literal[32] = 32
    mechanism_success_count: Literal[2] = 2
    requested_path_adherence_count: Literal[5] = 5
    program_closed_count: Literal[0] = 0
    independently_valid_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    interpretation: Literal["exact_abi_crossed_and_semantic_proposal_quality_measured_negative"] = (
        "exact_abi_crossed_and_semantic_proposal_quality_measured_negative"
    )
    schema_version: Literal["finance_v26_semantic_runtime_audit.v1"] = (
        "finance_v26_semantic_runtime_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticRuntimeAudit:
        expected = {
            "compiled public call violates the exposed tool grammar": 10,
            "semantic proposal changes registered public operand sources": 4,
            "semantic proposal selects an unresolved public Operation": 7,
        }
        if self.semantic_compile_rejection_counts != expected:
            raise ValueError("v26.115 semantic compile rejection partition changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_semantic_runtime_audit:"):
            raise ValueError("v26.115 semantic runtime identity changed")
        return self


class PhaseUsage(FrozenModel):
    phase: Literal["primary", "rescue"]
    call_count: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    reasoning_completion_fraction: str = Field(min_length=1)


class RescueResourceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    no_rescue_job_count: Literal[13] = 13
    rescue_job_count: Literal[19] = 19
    rescue_recovered_job_count: Literal[12] = 12
    rescue_failed_job_count: Literal[7] = 7
    rescue_recovered_then_later_rescuable_failure_job_count: Literal[1] = 1
    primary_exact_abi_failure_count: Literal[20] = 20
    rescue_exact_abi_failure_count: Literal[7] = 7
    provider_call_count: Literal[81] = 81
    provider_total_tokens: Literal[577078] = 577078
    prompt_tokens: Literal[147995] = 147995
    completion_tokens: Literal[429083] = 429083
    reasoning_tokens: Literal[410643] = 410643
    estimated_cost_usd: Literal["0.1398790904000000131"] = "0.1398790904000000131"
    phase_usage: tuple[PhaseUsage, PhaseUsage]
    minimum_rollout_headroom_tokens: int = Field(ge=0)
    maximum_rollout_headroom_tokens: int = Field(ge=0)
    typed_no_call_job_count: Literal[0] = 0
    completion_unusable_job_count: Literal[0] = 0
    transport_failure_job_count: Literal[0] = 0
    instrument_failure_job_count: Literal[0] = 0
    exact_model_passed: Literal[True] = True
    thinking_continuity_passed: Literal[True] = True
    provider_usage_complete: Literal[True] = True
    native_tool_absence_passed: Literal[True] = True
    fallback_absence_passed: Literal[True] = True
    schema_version: Literal["finance_v26_rescue_resource_audit.v1"] = (
        "finance_v26_rescue_resource_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RescueResourceAudit:
        if tuple(item.phase for item in self.phase_usage) != ("primary", "rescue"):
            raise ValueError("v26.115 phase Usage order changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_rescue_resource_audit:"):
            raise ValueError("v26.115 Rescue/resource identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    observed_result: Literal[
        "residual_fixed_stage_serialization_and_negative_semantic_proposal_quality"
    ] = "residual_fixed_stage_serialization_and_negative_semantic_proposal_quality"
    response_grammar_hidden_gap_closed: Literal[True] = True
    exact_abi_was_empirically_crossed: Literal[True] = True
    semantic_behavior_was_empirically_measured: Literal[True] = True
    only_residual_mechanical_field: Literal["stage"] = "stage"
    host_may_bind_fixed_stage_metadata_prospectively: Literal[True] = True
    host_may_select_or_repair_semantic_fields: Literal[False] = False
    response_grammar_optimization_must_stop_for_semantic_rejections: Literal[True] = True
    fresh_protocol_identity_required: Literal[True] = True
    fresh_task_contract_manifest_job_runner_identities_required: Literal[True] = True
    credential_free_preflight_required_before_provider_call: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    v26_114_rerun_authorized: Literal[False] = False
    model_profile_completion_rollout_change_authorized: Literal[False] = False
    additional_rescue_authorized: Literal[False] = False
    role_experiment_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal[
        "fresh_host_bound_stage_metadata_semantic_proposal_preflight_only"
    ] = NEXT_STAGE
    schema_version: Literal["finance_v26_exact_grammar_postrun_transition.v1"] = (
        "finance_v26_exact_grammar_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_exact_grammar_postrun_transition:"
        ):
            raise ValueError("v26.115 transition identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[20] = 20
    rejection_count: Literal[20] = 20
    mutations: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_grammar_postrun_destructive.v1"] = (
        "finance_v26_exact_grammar_postrun_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_grammar_postrun_destructive:"
        ):
            raise ValueError("v26.115 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal[
        "finance_v26_115_exact_response_grammar_calibration_postrun_audit_v1_20260823"
    ] = RUN_ID
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    execution_lineage_audit_id: str = Field(min_length=1)
    response_funnel_audit_id: str = Field(min_length=1)
    semantic_runtime_audit_id: str = Field(min_length=1)
    rescue_resource_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=7, max_length=7)
    exact_job_denominator: Literal[32] = 32
    execution_result: Literal["32_model_invalid_trajectories"] = "32_model_invalid_trajectories"
    exact_abi_accepted_count: Literal[54] = 54
    semantic_commit_count: Literal[30] = 30
    program_closed_count: Literal[0] = 0
    independently_valid_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_reclassified: Literal[0] = 0
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    status: Literal["exact_grammar_calibration_independently_audited"] = (
        "exact_grammar_calibration_independently_audited"
    )
    next_permitted_stage: Literal[
        "fresh_host_bound_stage_metadata_semantic_proposal_preflight_only"
    ] = NEXT_STAGE
    schema_version: Literal["finance_v26_exact_grammar_postrun_audit_report.v1"] = (
        "finance_v26_exact_grammar_postrun_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_exact_grammar_postrun_audit_report:"
        ):
            raise ValueError("v26.115 report identity changed")
        return self


class LoadedExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    report: ExactGrammarExecutionReport
    results: tuple[ExactGrammarJobResult, ...]
    raws: tuple[TwoStageRawExecution, ...]
    providers: tuple[RawStageOneProviderCall, ...]
    providers_by_artifact_id: dict[str, RawStageOneProviderCall]
    providers_by_relative_path: dict[str, RawStageOneProviderCall]
    execution_paths: tuple[Path, ...]


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


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
    raise ValueError(f"v26.115 cannot replay bound file: {relative_path}")


def _source_entry(path: Path, relative_path: str, source_kind: str) -> SourceReplayEntry:
    observed = sha256_file(path)
    return SourceReplayEntry(
        relative_path=relative_path,
        source_kind=source_kind,
        expected_sha256=observed,
        observed_sha256=observed,
        byte_count=path.stat().st_size,
    )


def _build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> PostrunSourceReplayAudit:
    predecessor = ExecutionSourceReplayAudit.model_validate(
        _load_json(execution_dir / "online_source_replay_audit.json")
    )
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
            source_kind="v26_114_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=sha256_file(path),
            byte_count=path.stat().st_size,
        )
    relative_execution_root = Path(EXECUTION_DIR)
    execution_paths = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if len(execution_paths) != 122:
        raise ValueError("v26.115 execution file denominator changed")
    for path in execution_paths:
        relative = str(relative_execution_root / path.relative_to(execution_dir))
        entries[relative] = _source_entry(path, relative, "v26_114_execution_file")
    implementation = implementation_root / IMPLEMENTATION_PATH
    entries[IMPLEMENTATION_PATH] = _source_entry(
        implementation, IMPLEMENTATION_PATH, "v26_115_implementation"
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values: dict[str, Any] = {
        "predecessor_source_replay_id": predecessor.audit_id,
        "entries": ordered,
    }
    provisional = PostrunSourceReplayAudit.model_construct(audit_id="pending", **values)
    return PostrunSourceReplayAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_exact_grammar_postrun_source:"),
        **values,
    )


def _load_execution(execution_dir: Path) -> LoadedExecution:
    report = ExactGrammarExecutionReport.model_validate(_load_json(execution_dir / "report.json"))
    if (
        report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or report.runner_contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or report.next_permitted_stage != "exact_response_grammar_calibration_postrun_audit_only"
    ):
        raise ValueError("v26.115 execution authorization changed")
    results = tuple(
        ExactGrammarJobResult.model_validate(item)
        for item in _load_json(execution_dir / "two_stage_job_results.json")
    )
    raw_paths = tuple(sorted((execution_dir / "raw_execution").glob("*.json")))
    raws = tuple(TwoStageRawExecution.model_validate(_load_json(path)) for path in raw_paths)
    provider_paths = tuple(sorted((execution_dir / "raw_provider_calls").glob("*/*.json")))
    providers = tuple(
        RawStageOneProviderCall.model_validate(_load_json(path)) for path in provider_paths
    )
    return LoadedExecution(
        report=report,
        results=results,
        raws=raws,
        providers=providers,
        providers_by_artifact_id={item.artifact_id: item for item in providers},
        providers_by_relative_path={
            str(path.relative_to(execution_dir)): artifact
            for path, artifact in zip(provider_paths, providers, strict=True)
        },
        execution_paths=tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file())),
    )


def _build_lineage(loaded: LoadedExecution, execution_dir: Path) -> ExecutionLineageAudit:
    canonical_json = 0
    canonical_jsonl = 0
    for path in loaded.execution_paths:
        if path.suffix == ".json":
            if path.read_bytes() != _canonical_bytes(_load_json(path)):
                raise ValueError(f"v26.115 noncanonical JSON: {path}")
            canonical_json += 1
        elif path.suffix == ".jsonl":
            rows = tuple(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            expected = b"\n".join(_canonical_bytes(item) for item in rows) + b"\n"
            if path.read_bytes() != expected:
                raise ValueError("v26.115 noncanonical checkpoint JSONL")
            canonical_jsonl += 1
    checkpoint = tuple(
        ExactGrammarJobResult.model_validate_json(line)
        for line in (execution_dir / "two_stage_job_results.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    if checkpoint != loaded.results:
        raise ValueError("v26.115 checkpoint and final result rows differ")
    provider_ids: list[str] = []
    descriptors = 0
    parent_pass = 0
    certificate_pass = 0
    private_hits = 0
    for raw in loaded.raws:
        descriptors += 1 + len(raw.provider_call_artifacts)
        for descriptor in raw.provider_call_artifacts:
            path = execution_dir / descriptor.relative_path
            artifact = RawStageOneProviderCall.model_validate(load_canonical_json(path))
            if (
                sha256_file(path) != descriptor.sha256
                or path.stat().st_size != descriptor.byte_count
                or artifact.job_id != raw.job.job_id
                or artifact.runner_contract_id != raw.runner_contract_id
            ):
                raise ValueError("v26.115 Raw Provider parent binding changed")
            parent_pass += 1
            if not (
                artifact.dynamic_certificate.certificate_id
                and artifact.request_binding_certificate.certificate_id
                and artifact.resource_certificate_id
            ):
                raise ValueError("v26.115 Provider certificate triple is incomplete")
            certificate_pass += 1
            provider_ids.append(artifact.artifact_id)
            payload = _load_json(path)
            private_hits += int(
                any(
                    key in {"private_reasoning", "reasoning_content"}
                    for key in _recursive_keys(payload)
                )
            )
    usage = sum(item.provider_telemetry.total_tokens or 0 for item in loaded.providers)
    if usage != loaded.report.provider_total_tokens:
        raise ValueError("v26.115 Provider Usage sum changed")
    if (
        len(loaded.execution_paths) != 122
        or canonical_json != 121
        or canonical_jsonl != 1
        or len(checkpoint) != 32
        or len(loaded.results) != 32
        or len(loaded.raws) != 32
        or len(loaded.providers) != 81
        or len(set(provider_ids)) != 81
        or descriptors != 113
        or parent_pass != 81
        or certificate_pass != 81
        or private_hits
        or any(raw.stage_two_provider_call_count for raw in loaded.raws)
    ):
        raise ValueError("v26.115 execution lineage denominator or Gate changed")
    values: dict[str, Any] = {
        "execution_file_count": len(loaded.execution_paths),
        "canonical_json_file_count": canonical_json,
        "canonical_jsonl_file_count": canonical_jsonl,
        "checkpoint_row_count": len(checkpoint),
        "job_result_count": len(loaded.results),
        "raw_execution_count": len(loaded.raws),
        "provider_artifact_count": len(loaded.providers),
        "unique_provider_artifact_id_count": len(set(provider_ids)),
        "raw_descriptor_count": descriptors,
        "exact_byte_replay_pass_count": len(loaded.execution_paths),
        "parent_binding_pass_count": parent_pass,
        "certificate_triple_pass_count": certificate_pass,
        "checkpoint_result_match_count": len(checkpoint),
        "private_reasoning_payload_count": private_hits,
        "stage_two_provider_call_count": sum(
            raw.stage_two_provider_call_count for raw in loaded.raws
        ),
    }
    provisional = ExecutionLineageAudit.model_construct(audit_id="pending", **values)
    return ExecutionLineageAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_exact_grammar_execution_lineage:"),
        **values,
    )


def _recursive_keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _recursive_keys(item)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(key for item in value for key in _recursive_keys(item))
    return ()


def _conditional_rules_pass(payload: Mapping[str, Any]) -> bool:
    kind = payload.get("decision_kind")
    if kind not in DECISION_FIELD_RULES:
        return False
    rule = DECISION_FIELD_RULES[str(kind)]
    for field in rule["required_non_null"]:
        if payload.get(field) in (None, ""):
            return False
    for field in rule["required_null"]:
        if payload.get(field) is not None:
            return False
    for field in rule["required_non_empty"]:
        if not payload.get(field):
            return False
    for field in rule["required_empty"]:
        if payload.get(field):
            return False
    return True


def _build_funnel(loaded: LoadedExecution) -> ResponseFunnelAudit:
    field_counts: Counter[str] = Counter()
    stage_values: Counter[str] = Counter()
    decision_kinds: Counter[str] = Counter()
    logical_positions: Counter[str] = Counter()
    ten_fields = protocol = state = decision = conditional = stage = schema = accepted = 0
    for raw in loaded.raws:
        artifacts = {
            item.provider_call_index: item
            for item in (
                loaded.providers_by_relative_path[descriptor.relative_path]
                for descriptor in raw.provider_call_artifacts
            )
        }
        for attempt in raw.attempts:
            if not attempt.provider_call_made or attempt.provider_call_index is None:
                continue
            artifact = artifacts[attempt.provider_call_index]
            payload = artifact.response_payload
            if payload is None:
                raise ValueError("v26.115 expected a public JSON payload for every call")
            ten_fields += int(set(payload) == set(FIELD_ORDER))
            protocol += int(payload.get("protocol") == EXACT_RESPONSE_PROTOCOL_VERSION)
            state += int(payload.get("state_id") == artifact.dynamic_certificate.public_state_id)
            decision += int(payload.get("decision_kind") in DECISION_FIELD_RULES)
            conditional += int(_conditional_rules_pass(payload))
            stage_values[str(payload.get("stage"))] += 1
            decision_kinds[str(payload.get("decision_kind"))] += 1
            stage_ok = payload.get("stage") == EXACT_STAGE
            stage += int(stage_ok)
            if not stage_ok:
                field_counts["stage_constant"] += 1
                logical_positions[str(attempt.logical_request_index)] += 1
            try:
                ExactStageOneSemanticProposalPayload.model_validate(payload)
                schema_ok = True
            except ValidationError:
                schema_ok = False
            schema += int(schema_ok)
            parser_ok = attempt.disposition == "usable"
            accepted += int(parser_ok)
            if parser_ok != bool(
                schema_ok
                and payload.get("state_id") == artifact.dynamic_certificate.public_state_id
            ):
                raise ValueError("v26.115 Parser and independent ABI diagnosis disagree")
    commits = sum(len(raw.commits) for raw in loaded.raws)
    observations = sum(len(raw.observations) for raw in loaded.raws)
    agreement = len(loaded.providers)
    if (
        len(loaded.providers) != 81
        or ten_fields != 81
        or protocol != 81
        or state != 81
        or decision != 81
        or conditional != 81
        or stage != 54
        or schema != 54
        or accepted != 54
        or commits != 30
        or observations != 30
        or sum(field_counts.values()) != 27
    ):
        raise ValueError("v26.115 response Funnel denominator changed")
    values: dict[str, Any] = {
        "provider_call_count": len(loaded.providers),
        "http_success_count": sum(
            item.provider_telemetry.http_success for item in loaded.providers
        ),
        "public_json_payload_count": sum(
            item.response_payload is not None for item in loaded.providers
        ),
        "exact_ten_field_set_count": ten_fields,
        "registered_protocol_count": protocol,
        "exact_state_binding_count": state,
        "registered_decision_kind_count": decision,
        "conditional_semantic_field_rule_count": conditional,
        "exact_stage_constant_count": stage,
        "exact_schema_count": schema,
        "parser_accepted_count": accepted,
        "semantic_proposal_commit_count": commits,
        "public_observation_count": observations,
        "program_closed_job_count": sum(item.program_closed for item in loaded.results),
        "independently_valid_job_count": sum(item.independent_validity for item in loaded.results),
        "parser_independent_diagnostic_agreement_count": agreement,
        "mechanical_failure_count": sum(field_counts.values()),
        "mechanical_failure_field_counts": dict(sorted(field_counts.items())),
        "stage_value_counts": dict(sorted(stage_values.items())),
        "decision_kind_counts": dict(sorted(decision_kinds.items())),
        "exact_abi_failure_counts_by_logical_request_index": dict(
            sorted(logical_positions.items())
        ),
    }
    provisional = ResponseFunnelAudit.model_construct(audit_id="pending", **values)
    return ResponseFunnelAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_exact_response_funnel:"),
        **values,
    )


def _build_semantic_runtime(
    loaded: LoadedExecution,
    *,
    package_root: Path,
    implementation_root: Path,
) -> SemanticRuntimeAudit:
    static, _ = load_exact_grammar_static_inputs(package_root, implementation_root)
    rejections: Counter[str] = Counter()
    decisions: Counter[str] = Counter()
    tool_status: Counter[str] = Counter()
    observation_errors: Counter[str] = Counter()
    decompiled = 0
    replay_passes = 0
    mechanism_successes = 0
    host_insertions = 0
    stage_two_provider_calls = 0
    for raw in loaded.raws:
        binding = two_stage_runtime_binding(static, raw.job)
        replay_passes += int(replay_v3(raw, static=static, binding=binding).passed)
        mechanism_successes += int(
            evaluate_mechanism_estimand(
                cast(Any, binding.record),
                raw.observations,
                stopped_by_model=raw.completed_result is not None,
            ).success
        )
        if raw.terminal_failure_type == "semantic_compile_rejection":
            rejections[str(raw.execution_error)] += 1
        for index, commit in enumerate(raw.commits):
            decisions[commit.proposal.decision_kind] += 1
            host_insertions += int(commit.semantic_choice_inserted_by_host)
            stage_two_provider_calls += commit.stage_two_provider_calls
            if commit.commit.call is None:
                raise ValueError("v26.115 observed a semantic Commit without a public call")
            state = build_public_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                raw.observations[:index],
            )
            if decompile_public_call(state, commit.commit.call) != commit.proposal:
                raise ValueError("v26.115 Stage 2 Commit did not independently decompile")
            decompiled += 1
        for observation in raw.observations:
            tool_status[f"{observation.call.tool_id}:{observation.status}"] += 1
            if observation.status == "failed":
                observation_errors[str(observation.error_code)] += 1
    commit_count = sum(len(raw.commits) for raw in loaded.raws)
    observation_count = sum(len(raw.observations) for raw in loaded.raws)
    successful_observations = sum(
        observation.status == "succeeded" for raw in loaded.raws for observation in raw.observations
    )
    failed_observations = observation_count - successful_observations
    compile_jobs = sum(
        raw.terminal_failure_type == "semantic_compile_rejection" for raw in loaded.raws
    )
    duplicate_jobs = sum(
        raw.terminal_failure_type == "duplicate_failed_semantic_proposal" for raw in loaded.raws
    )
    abi_terminal_jobs = sum(
        raw.terminal_failure_type == "semantic_proposal_not_exact_response_grammar"
        for raw in loaded.raws
    )
    path_adherence = sum(item.requested_path_adhered for item in loaded.results)
    program_closed = sum(item.program_closed for item in loaded.results)
    valid = sum(item.independent_validity for item in loaded.results)
    if (
        commit_count != 30
        or decompiled != 30
        or host_insertions
        or stage_two_provider_calls
        or compile_jobs != 21
        or duplicate_jobs != 3
        or abi_terminal_jobs != 8
        or observation_count != 30
        or successful_observations != 23
        or failed_observations != 7
        or replay_passes != 32
        or mechanism_successes != 2
        or path_adherence != 5
        or program_closed
        or valid
    ):
        raise ValueError("v26.115 semantic Runtime denominator or Gate changed")
    values: dict[str, Any] = {
        "semantic_commit_count": commit_count,
        "accepted_without_commit_count": 54 - commit_count,
        "reversible_commit_count": sum(
            commit.reversible_mapping_passed for raw in loaded.raws for commit in raw.commits
        ),
        "independently_decompiled_commit_count": decompiled,
        "host_semantic_choice_inserted_count": host_insertions,
        "semantic_compile_rejection_job_count": compile_jobs,
        "duplicate_failed_proposal_job_count": duplicate_jobs,
        "terminal_exact_abi_failure_job_count": abi_terminal_jobs,
        "semantic_compile_rejection_counts": dict(sorted(rejections.items())),
        "committed_decision_kind_counts": dict(sorted(decisions.items())),
        "observation_tool_status_counts": dict(sorted(tool_status.items())),
        "failed_observation_error_counts": dict(sorted(observation_errors.items())),
        "observation_count": observation_count,
        "successful_observation_count": successful_observations,
        "failed_observation_count": failed_observations,
        "verifier_v3_replay_pass_count": replay_passes,
        "mechanism_success_count": mechanism_successes,
        "requested_path_adherence_count": path_adherence,
        "program_closed_count": program_closed,
        "independently_valid_count": valid,
        "stage_two_provider_call_count": stage_two_provider_calls,
    }
    provisional = SemanticRuntimeAudit.model_construct(audit_id="pending", **values)
    return SemanticRuntimeAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_semantic_runtime_audit:"),
        **values,
    )


def _phase_usage(loaded: LoadedExecution, phase: Literal["primary", "rescue"]) -> PhaseUsage:
    rows = tuple(item for item in loaded.providers if item.phase == phase)
    prompt = sum(item.provider_telemetry.prompt_tokens or 0 for item in rows)
    completion = sum(item.provider_telemetry.completion_tokens or 0 for item in rows)
    reasoning = sum(item.provider_telemetry.reasoning_tokens or 0 for item in rows)
    total = sum(item.provider_telemetry.total_tokens or 0 for item in rows)
    fraction = Decimal(reasoning) / Decimal(completion) if completion else Decimal("0")
    return PhaseUsage(
        phase=phase,
        call_count=len(rows),
        prompt_tokens=prompt,
        completion_tokens=completion,
        reasoning_tokens=reasoning,
        total_tokens=total,
        reasoning_completion_fraction=format(fraction, ".12f"),
    )


def _build_rescue_resource(loaded: LoadedExecution) -> RescueResourceAudit:
    headrooms = tuple(260000 - raw.cumulative_provider_tokens for raw in loaded.raws)
    primary_failures = sum(
        item.phase == "primary"
        and item.model_failure_classification is not None
        and item.model_failure_classification.family == "response_serialization_failure"
        for raw in loaded.raws
        for item in raw.attempts
    )
    rescue_failures = sum(
        item.phase == "rescue"
        and item.model_failure_classification is not None
        and item.model_failure_classification.family == "response_serialization_failure"
        for raw in loaded.raws
        for item in raw.attempts
    )
    phase_usage = (_phase_usage(loaded, "primary"), _phase_usage(loaded, "rescue"))
    prompt_tokens = sum(item.provider_telemetry.prompt_tokens or 0 for item in loaded.providers)
    completion_tokens = sum(
        item.provider_telemetry.completion_tokens or 0 for item in loaded.providers
    )
    reasoning_tokens = sum(
        item.provider_telemetry.reasoning_tokens or 0 for item in loaded.providers
    )
    total_tokens = sum(item.provider_telemetry.total_tokens or 0 for item in loaded.providers)
    cost = sum(
        (
            Decimal(str(item.provider_telemetry.estimated_cost))
            for item in loaded.providers
            if item.provider_telemetry.estimated_cost is not None
        ),
        Decimal("0"),
    )
    exact_model = all(
        item.provider_telemetry.model_requested == STAGE_ONE_MODEL_ID
        and item.provider_telemetry.model_selected == STAGE_ONE_MODEL_ID
        and item.provider_telemetry.response_model == STAGE_ONE_MODEL_ID
        for item in loaded.providers
    )
    fallback = all(
        not item.provider_telemetry.fallback_used
        and not item.provider_telemetry.discovery_attempted
        for item in loaded.providers
    )
    native = all(
        item.provider_telemetry.response_shape.get("provider_native_tool_call_observed") is False
        for item in loaded.providers
    )
    thinking = all(
        item.provider_telemetry.reasoning_content_present
        and (item.provider_telemetry.reasoning_content_length or 0) > 0
        and (item.provider_telemetry.reasoning_tokens or 0) > 0
        for item in loaded.providers
    )
    usage = all(
        item.provider_telemetry.prompt_tokens is not None
        and item.provider_telemetry.completion_tokens is not None
        and item.provider_telemetry.total_tokens
        == item.provider_telemetry.prompt_tokens + item.provider_telemetry.completion_tokens
        for item in loaded.providers
    )
    rescue_jobs = sum(bool(item.rescue_attempt_count) for item in loaded.results)
    rescued = sum(item.rescue_success for item in loaded.results)
    later_failure = sum(
        item.rescue_recovered_then_later_rescuable_failure for item in loaded.results
    )
    if (
        rescue_jobs != 19
        or rescued != 12
        or later_failure != 1
        or primary_failures != 20
        or rescue_failures != 7
        or len(loaded.providers) != 81
        or prompt_tokens != 147995
        or completion_tokens != 429083
        or reasoning_tokens != 410643
        or total_tokens != 577078
        or format(cost, "f") != "0.1398790904000000131"
        or not all((exact_model, fallback, native, thinking, usage))
        or any(
            (
                loaded.report.typed_no_call_job_count,
                loaded.report.completion_unusable_job_count,
                loaded.report.provider_transport_failure_job_count,
                loaded.report.instrument_failure_job_count,
            )
        )
    ):
        raise ValueError("v26.115 Rescue/resource denominator or Gate changed")
    values: dict[str, Any] = {
        "no_rescue_job_count": len(loaded.results) - rescue_jobs,
        "rescue_job_count": rescue_jobs,
        "rescue_recovered_job_count": rescued,
        "rescue_failed_job_count": rescue_jobs - rescued,
        "rescue_recovered_then_later_rescuable_failure_job_count": later_failure,
        "primary_exact_abi_failure_count": primary_failures,
        "rescue_exact_abi_failure_count": rescue_failures,
        "provider_call_count": len(loaded.providers),
        "provider_total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "estimated_cost_usd": format(cost, "f"),
        "phase_usage": phase_usage,
        "minimum_rollout_headroom_tokens": min(headrooms),
        "maximum_rollout_headroom_tokens": max(headrooms),
        "typed_no_call_job_count": loaded.report.typed_no_call_job_count,
        "completion_unusable_job_count": loaded.report.completion_unusable_job_count,
        "transport_failure_job_count": loaded.report.provider_transport_failure_job_count,
        "instrument_failure_job_count": loaded.report.instrument_failure_job_count,
        "exact_model_passed": exact_model,
        "thinking_continuity_passed": thinking,
        "provider_usage_complete": usage,
        "native_tool_absence_passed": native,
        "fallback_absence_passed": fallback,
    }
    provisional = RescueResourceAudit.model_construct(audit_id="pending", **values)
    return RescueResourceAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_rescue_resource_audit:"),
        **values,
    )


def _build_transition() -> ProspectiveTransitionContract:
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending")
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional, "contract_id", "finance_v26_exact_grammar_postrun_transition:"
        )
    )


def _audit_gate(values: Mapping[str, Any]) -> None:
    expected = {
        "execution_report_id": EXPECTED_EXECUTION_REPORT_ID,
        "source_replay_count": 2172,
        "execution_file_count": 122,
        "checkpoint_row_count": 32,
        "raw_execution_count": 32,
        "provider_artifact_count": 81,
        "certificate_triple_count": 81,
        "exact_ten_field_count": 81,
        "exact_stage_count": 54,
        "protocol_count": 81,
        "state_binding_count": 81,
        "parser_accepted_count": 54,
        "commit_count": 30,
        "decompiled_commit_count": 30,
        "host_semantic_insertions": 0,
        "stage_two_provider_calls": 0,
        "private_reasoning_payloads": 0,
        "next_permitted_stage": NEXT_STAGE,
        "provider_calls_authorized": False,
        "production_contribution": 0,
    }
    if dict(values) != expected:
        raise ValueError("v26.115 destructive control changed a frozen audit Gate")


def _build_destructive(
    source: PostrunSourceReplayAudit,
    lineage: ExecutionLineageAudit,
    funnel: ResponseFunnelAudit,
    semantic: SemanticRuntimeAudit,
    transition: ProspectiveTransitionContract,
) -> DestructiveAudit:
    baseline: dict[str, Any] = {
        "execution_report_id": EXPECTED_EXECUTION_REPORT_ID,
        "source_replay_count": source.replayed_file_count,
        "execution_file_count": lineage.execution_file_count,
        "checkpoint_row_count": lineage.checkpoint_row_count,
        "raw_execution_count": lineage.raw_execution_count,
        "provider_artifact_count": lineage.provider_artifact_count,
        "certificate_triple_count": lineage.certificate_triple_pass_count,
        "exact_ten_field_count": funnel.exact_ten_field_set_count,
        "exact_stage_count": funnel.exact_stage_constant_count,
        "protocol_count": funnel.registered_protocol_count,
        "state_binding_count": funnel.exact_state_binding_count,
        "parser_accepted_count": funnel.parser_accepted_count,
        "commit_count": semantic.semantic_commit_count,
        "decompiled_commit_count": semantic.independently_decompiled_commit_count,
        "host_semantic_insertions": semantic.host_semantic_choice_inserted_count,
        "stage_two_provider_calls": semantic.stage_two_provider_call_count,
        "private_reasoning_payloads": lineage.private_reasoning_payload_count,
        "next_permitted_stage": transition.next_permitted_stage,
        "provider_calls_authorized": transition.provider_calls_authorized,
        "production_contribution": transition.production_contribution,
    }
    _audit_gate(baseline)
    names = tuple(baseline)
    mutations: list[MutationResult] = []
    for name in names:
        mutated = dict(baseline)
        current = mutated[name]
        if isinstance(current, bool):
            mutated[name] = not current
        elif isinstance(current, int):
            mutated[name] = current + 1
        else:
            mutated[name] = f"{current}.mutated"
        try:
            _audit_gate(mutated)
        except ValueError:
            mutations.append(MutationResult(name=f"changed_{name}"))
        else:
            raise ValueError(f"v26.115 destructive mutation passed: {name}")
    values: dict[str, Any] = {"mutations": tuple(mutations)}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional, "audit_id", "finance_v26_exact_grammar_postrun_destructive:"
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=sha256_file(path),
        byte_count=path.stat().st_size,
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
    loaded = _load_execution(execution_dir)
    lineage = _build_lineage(loaded, execution_dir)
    funnel = _build_funnel(loaded)
    semantic = _build_semantic_runtime(
        loaded,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    resource = _build_rescue_resource(loaded)
    transition = _build_transition()
    destructive = _build_destructive(source, lineage, funnel, semantic, transition)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("execution_lineage_audit.json", lineage),
        ("response_funnel_audit.json", funnel),
        ("semantic_runtime_audit.json", semantic),
        ("rescue_resource_audit.json", resource),
        ("prospective_transition_contract.json", transition),
        ("destructive_audit.json", destructive),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        _write_json(output_dir / name, value.model_dump(mode="json"))
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "execution_lineage_audit_id": lineage.audit_id,
        "response_funnel_audit_id": funnel.audit_id,
        "semantic_runtime_audit_id": semantic.audit_id,
        "rescue_resource_audit_id": resource.audit_id,
        "transition_contract_id": transition.contract_id,
        "destructive_audit_id": destructive.audit_id,
        "detail_files": details,
    }
    provisional = PostrunAuditReport.model_construct(report_id="pending", **values)
    report = PostrunAuditReport(
        report_id=_identity(
            provisional, "report_id", "finance_v26_exact_grammar_postrun_audit_report:"
        ),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Independently audit v26.114 exact response-Grammar calibration"
    )
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument(
        "--implementation-root", type=Path, default=Path(__file__).resolve().parents[4]
    )
    parser.add_argument("--execution-dir", type=Path, default=Path(EXECUTION_DIR))
    parser.add_argument("--output-dir", type=Path, default=Path(OUTPUT_DIR))
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
