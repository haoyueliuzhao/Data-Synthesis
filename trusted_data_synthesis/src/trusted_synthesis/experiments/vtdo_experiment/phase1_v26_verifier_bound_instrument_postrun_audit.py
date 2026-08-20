from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import (
    matching_sufficient_support_set,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    replay_authority_preserving_observations,
    verify_authority_preserving_agent_result,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    evaluate_mechanism_estimand,
    failure_artifact_mechanism_estimand,
    match_empirical_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_recovery import (  # noqa: E501
    FAILED_EXECUTION_BINDING_ID,
    FAILED_PROVIDER_CALL_COUNT,
    RecoveryContract,
    RecoveryExecutionReport,
    RecoveryManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_requalification import (  # noqa: E501
    EXPECTED_JOB_COUNT,
    RawProviderCallArtifact,
    VerifierBoundInstrumentRollout,
    VerifierBoundRawExecutionArtifact,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import IterativeAgentProtocolProfile
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

V26_POSTRUN_SOURCE_REPLAY_VERSION = "finance_v26_verifier_bound_postrun_source_replay.v1"
V26_COMPLETED_TRACE_AUDIT_VERSION = "finance_v26_completed_trace_scoring_audit.v1"
V26_RESOURCE_AUDIT_VERSION = "finance_v26_strict_resource_budget_audit.v1"
V26_LINEAGE_AUDIT_VERSION = "finance_v26_recovery_raw_lineage_independent_audit.v1"
V26_POSTRUN_REPORT_VERSION = "finance_v26_verifier_bound_postrun_audit.v1"

EXPECTED_RECOVERY_PREFLIGHT_ID = (
    "finance_v26_verifier_bound_recovery_preflight:"
    "a25d500a2ea292f2274b7b1e305d4f5bfadc9b82b8ebaa0ee59474368aff8ccc"
)
EXPECTED_RECOVERY_REPORT_ID = (
    "finance_v26_verifier_bound_instrument_recovery:"
    "645531ad63c93055f9a29f6a179e6bce16a65441ea7facca4f2d7e8381e52a67"
)
EXPECTED_RECOVERY_INSTRUMENT_RESULT_ID = (
    "finance_v26_verifier_bound_instrument_requalification:"
    "6a2fd18fdda1e384686d3631316cbb5da809ac3bbef56c79db41caad50886275"
)
AUDIT_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_verifier_bound_instrument_postrun_audit.py"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AuditSourceEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal["implementation", "failed_run", "preflight", "recovery_run"]
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    entries: tuple[AuditSourceEntry, ...] = Field(min_length=400)
    implementation_file_count: int = Field(ge=19)
    artifact_file_count: int = Field(ge=380)
    replayed_file_count: int = Field(ge=400)
    replay_pass_count: int = Field(ge=400)
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_POSTRUN_SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("post-run source paths are not canonical")
        if self.replayed_file_count != len(self.entries) or (
            self.replay_pass_count != self.replayed_file_count
        ):
            raise ValueError("post-run source replay denominator is incomplete")
        if self.implementation_file_count + self.artifact_file_count != len(self.entries):
            raise ValueError("post-run source-kind denominator is incomplete")
        if self.audit_id != postrun_source_replay_audit_id(self):
            raise ValueError("post-run source replay identity is invalid")
        return self


class CompletedTraceScoringRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    raw_execution_sha256: str = Field(min_length=64, max_length=64)
    observation_count: int = Field(ge=1)
    original_terminal_category: Literal["instrument_failure"] = "instrument_failure"
    original_failure_reason: Literal[
        "AttributeError:'TrajectoryStep' object has no attribute 'observation_id'"
    ]
    verifier_v2_replay_passed: Literal[True] = True
    independent_non_replay_gate_agreement: Literal[True] = True
    prospective_terminal_category: Literal["model_valid_trajectory", "model_invalid_trajectory"]
    prospective_independent_validity: bool
    full_program_lineage_completed: bool
    local_mechanism_success: bool
    schema_valid_decision_trace_hash: str = Field(min_length=1)
    diagnostic_only: Literal[True] = True
    historical_terminal_reclassified: Literal[False] = False
    schema_version: str = V26_COMPLETED_TRACE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> CompletedTraceScoringRow:
        if self.prospective_independent_validity != (
            self.prospective_terminal_category == "model_valid_trajectory"
        ):
            raise ValueError("prospective scoring terminal is inconsistent")
        if self.row_id != completed_trace_scoring_row_id(self):
            raise ValueError("completed-trace scoring row identity is invalid")
        return self


class CompletedTraceScoringAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_execution_replay_count: Literal[32] = EXPECTED_JOB_COUNT
    verifier_v2_replay_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    completed_trajectory_count: int = Field(ge=1, le=32)
    captured_model_contract_failure_count: int = Field(ge=0, le=32)
    original_scoring_instrument_failure_count: int = Field(ge=1, le=32)
    scoring_failure_rows: tuple[CompletedTraceScoringRow, ...] = Field(min_length=1)
    schema_field_mismatch_count: int = Field(ge=1)
    prospective_model_outcome_count: Literal[32] = EXPECTED_JOB_COUNT
    prospective_runtime_failure_count: Literal[0] = 0
    prospective_instrument_failure_count: Literal[0] = 0
    prospective_independently_valid_count: int = Field(ge=0, le=32)
    prospective_terminal_counts: dict[str, int]
    historical_rollouts_changed: Literal[False] = False
    historical_report_changed: Literal[False] = False
    status: Literal["completed_trace_scoring_defect_observed"] = (
        "completed_trace_scoring_defect_observed"
    )
    schema_version: str = V26_COMPLETED_TRACE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompletedTraceScoringAudit:
        if self.completed_trajectory_count + self.captured_model_contract_failure_count != 32:
            raise ValueError("scoring audit terminal denominator is incomplete")
        if self.original_scoring_instrument_failure_count != len(
            self.scoring_failure_rows
        ) or self.schema_field_mismatch_count != len(self.scoring_failure_rows):
            raise ValueError("scoring-defect denominator is inconsistent")
        if sum(self.prospective_terminal_counts.values()) != 32:
            raise ValueError("prospective scoring denominator is incomplete")
        if self.audit_id != completed_trace_scoring_audit_id(self):
            raise ValueError("completed-trace scoring audit identity is invalid")
        return self


class TokenBudgetCrossing(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    provider_call_count: int = Field(ge=1)
    pre_crossing_provider_tokens: int = Field(ge=0, le=120000)
    crossing_call_tokens: int = Field(ge=1)
    total_provider_tokens: int = Field(gt=120000)
    overshoot_tokens: int = Field(ge=1)
    raw_execution_error: Literal["LLMClientError:Agent exceeded the frozen model-token budget"]
    enforcement_phase: Literal["after_provider_response"] = "after_provider_response"
    schema_version: str = V26_RESOURCE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> TokenBudgetCrossing:
        if (
            self.pre_crossing_provider_tokens + self.crossing_call_tokens
            != (self.total_provider_tokens)
            or self.overshoot_tokens != self.total_provider_tokens - 120000
        ):
            raise ValueError("token-budget crossing arithmetic is inconsistent")
        if self.row_id != token_budget_crossing_id(self):
            raise ValueError("token-budget crossing identity is invalid")
        return self


class ResourceBudgetAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    per_rollout_token_ceiling: Literal[120000] = 120000
    aggregate_cost_ceiling_usd: str = "2.0"
    aggregate_estimated_cost_usd: str = Field(min_length=1)
    aggregate_cost_passed: Literal[True] = True
    provider_usage_complete_count: Literal[32] = EXPECTED_JOB_COUNT
    per_rollout_token_pass_count: int = Field(ge=0, le=32)
    per_rollout_token_failure_count: int = Field(ge=1, le=32)
    crossings: tuple[TokenBudgetCrossing, ...] = Field(min_length=1)
    maximum_total_provider_tokens: int = Field(gt=120000)
    maximum_overshoot_tokens: int = Field(ge=1)
    contract_repair_token_reserve: Literal[0] = 0
    final_answer_token_reserve: Literal[0] = 0
    post_response_enforcement_count: int = Field(ge=1)
    pre_call_provider_token_upper_bound_present: Literal[False] = False
    strict_resource_budget_passed: Literal[False] = False
    status: Literal["failed"] = "failed"
    root_cause: Literal[
        "post_response_budget_enforcement_without_pre_call_provider_token_upper_bound"
    ] = "post_response_budget_enforcement_without_pre_call_provider_token_upper_bound"
    schema_version: str = V26_RESOURCE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ResourceBudgetAudit:
        if self.per_rollout_token_pass_count + self.per_rollout_token_failure_count != 32:
            raise ValueError("resource audit rollout denominator is incomplete")
        if self.per_rollout_token_failure_count != len(self.crossings) or (
            self.post_response_enforcement_count != len(self.crossings)
        ):
            raise ValueError("resource crossing denominator is inconsistent")
        if Decimal(self.aggregate_estimated_cost_usd) > Decimal(self.aggregate_cost_ceiling_usd):
            raise ValueError("resource audit misclassified aggregate cost")
        if self.audit_id != resource_budget_audit_id(self):
            raise ValueError("resource-budget audit identity is invalid")
        return self


class IndependentRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    expected_job_count: Literal[32] = EXPECTED_JOB_COUNT
    observed_raw_execution_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_execution_recovery_binding_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    zero_generation_replay_job_count: Literal[17] = 17
    continuation_job_count: Literal[15] = 15
    exposed_job_model_call_count: Literal[0] = 0
    original_provider_artifact_count: Literal[146] = FAILED_PROVIDER_CALL_COUNT
    continuation_provider_artifact_count: int = Field(ge=1)
    original_provider_exact_byte_pass_count: Literal[146] = FAILED_PROVIDER_CALL_COUNT
    provider_binding_pass_count: int = Field(ge=146)
    provider_telemetry_pre_host_augmentation_pass_count: int = Field(ge=146)
    provider_call_ids_unique: Literal[True] = True
    historical_report_lineage_status: Literal["failed"] = "failed"
    historical_report_failed_artifact_count: int = Field(ge=1)
    historical_failed_artifacts_are_instrument_gate_failures: Literal[True] = True
    lineage_and_instrument_failure_lists_coupled: Literal[True] = True
    lineage_only_passed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_LINEAGE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRawLineageAudit:
        total = self.original_provider_artifact_count + (self.continuation_provider_artifact_count)
        if self.provider_binding_pass_count != total or (
            self.provider_telemetry_pre_host_augmentation_pass_count != total
        ):
            raise ValueError("raw-lineage Provider denominator is incomplete")
        if self.audit_id != independent_raw_lineage_audit_id(self):
            raise ValueError("independent raw-lineage audit identity is invalid")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class VerifierBoundPostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    scoring_audit_id: str = Field(min_length=1)
    resource_budget_audit_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    audited_recovery_report_id: str = EXPECTED_RECOVERY_REPORT_ID
    audited_instrument_result_id: str = EXPECTED_RECOVERY_INSTRUMENT_RESULT_ID
    immutable_detail_files: tuple[DetailFile, ...] = Field(min_length=4, max_length=4)
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_outcomes_reclassified: Literal[False] = False
    historical_artifacts_changed: Literal[False] = False
    verifier_v2_replay_passed: Literal[True] = True
    completed_trace_scoring_defect_observed: Literal[True] = True
    raw_lineage_only_passed: Literal[True] = True
    strict_resource_budget_passed: Literal[False] = False
    instrument_requalification_passed: Literal[False] = False
    status: Literal["failed"] = "failed"
    next_permitted_stage: Literal[
        "fresh_budget_closed_verifier_bound_task_rematerialization_and_instrument_preflight_only"
    ] = "fresh_budget_closed_verifier_bound_task_rematerialization_and_instrument_preflight_only"
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_POSTRUN_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> VerifierBoundPostrunAuditReport:
        if self.audited_recovery_report_id != EXPECTED_RECOVERY_REPORT_ID or (
            self.audited_instrument_result_id != EXPECTED_RECOVERY_INSTRUMENT_RESULT_ID
        ):
            raise ValueError("post-run audit crosses Recovery results")
        paths = tuple(item.relative_path for item in self.immutable_detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("post-run detail files are not canonical")
        if self.report_id != postrun_audit_report_id(self):
            raise ValueError("post-run audit report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"immutable post-run audit Artifact changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _load_rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _observations(raw: VerifierBoundRawExecutionArtifact) -> tuple[AgentToolObservation, ...]:
    if raw.solve_result is not None:
        return raw.solve_result.observations
    if raw.failure_artifact is not None:
        return raw.failure_artifact.observations
    return ()


def _telemetry_equal_before_host_augmentation(
    captured: ModelCallTelemetry,
    enriched: ModelCallTelemetry,
) -> bool:
    captured_payload = captured.model_dump(mode="json")
    enriched_payload = enriched.model_dump(mode="json")
    if captured_payload == enriched_payload:
        return True
    response_shape = dict(enriched_payload["response_shape"])
    augmented = response_shape.pop("prompt_component_bytes", None)
    enriched_payload["response_shape"] = response_shape
    return augmented is not None and captured_payload == enriched_payload


def _replace_references(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, Mapping):
        return {key: _replace_references(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_references(item, mapping) for item in value]
    return value


def _answer_and_citations(
    raw: VerifierBoundRawExecutionArtifact,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    if raw.solve_result is None:
        return {}, ()
    final = raw.solve_result.trajectory.final_answer
    answer = final.get("result") if isinstance(final, Mapping) else None
    citations = final.get("citations") if isinstance(final, Mapping) else None
    if not isinstance(answer, Mapping) or not isinstance(citations, list):
        return {}, ()
    return dict(answer), tuple(
        str(item["evidence_id"])
        for item in citations
        if isinstance(item, Mapping) and item.get("evidence_id")
    )


def _independent_non_replay_checks(
    record: OperationalTaskRecord,
    raw: VerifierBoundRawExecutionArtifact,
    selected_evidence_ids: tuple[str, ...],
) -> tuple[dict[str, bool], bool, bool]:
    observations = _observations(raw)
    program_complete, _, runtime_to_node, operation_lineage = match_empirical_program(
        record, observations
    )
    answer, citations = _answer_and_citations(raw)
    normalized_answer = cast(dict[str, Any], _replace_references(answer, runtime_to_node))
    for field in ("higher_ref", "selected_ref"):
        reference = normalized_answer.get(field)
        if reference is not None and str(reference) in record.answer_projection:
            normalized_answer[field] = record.answer_projection[str(reference)]
    lattice = record.task_package.evidence_support_lattice
    selected_support = matching_sufficient_support_set(lattice, selected_evidence_ids)
    citation_support = matching_sufficient_support_set(lattice, citations)
    verification_support = {
        str(evidence_id)
        for item in observations
        if item.call.tool_id == "cross_check_evidence"
        and item.status == "succeeded"
        and item.result.get("verified") is True
        for evidence_id in item.result.get("support") or ()
    }
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
    mechanism = (
        evaluate_mechanism_estimand(
            record,
            observations,
            stopped_by_model=raw.solve_result.audit.stopped_by_model,
        )
        if raw.solve_result is not None
        else failure_artifact_mechanism_estimand(record, raw.failure_artifact)
        if raw.failure_artifact is not None
        else evaluate_mechanism_estimand(record, (), stopped_by_model=False)
    )
    necessary = set(lattice.necessary_evidence_ids)
    checks = {
        "model_input_noninterference_passed": raw.recursive_noninterference_passed,
        "only_allowed_tools": {item.call.tool_id for item in observations}
        <= set(record.task_package.tool_closure.allowed_tool_ids),
        "operation_lineage_complete": program_complete and necessary <= set(operation_lineage),
        "evidence_support_complete": selected_support is not None,
        "verification_complete": necessary <= verification_support,
        "answer_projection_complete": normalized_answer == record.projected_expected_output,
        "citation_complete": citation_support is not None,
        "mechanism_complete": mechanism.success,
        "no_postcompletion_violation": first_verified is None
        or first_verified == len(observations) - 1,
    }
    return checks, program_complete, mechanism.success


def _build_source_replay(
    *,
    package_root: Path,
    failed_run_dir: Path,
    preflight_dir: Path,
    recovery_dir: Path,
    recovery_contract: RecoveryContract,
) -> PostrunSourceReplayAudit:
    entries: dict[str, AuditSourceEntry] = {}
    implementation = {
        item.relative_path: item.sha256 for item in recovery_contract.implementation_source_files
    }
    implementation[AUDIT_SOURCE_PATH] = _sha256(package_root / AUDIT_SOURCE_PATH)
    for relative, expected in sorted(implementation.items()):
        path = package_root / relative
        observed = _sha256(path)
        if observed != expected:
            raise ValueError(f"post-run implementation source changed: {relative}")
        entries[relative] = AuditSourceEntry(
            relative_path=relative,
            source_kind="implementation",
            sha256=observed,
            byte_count=path.stat().st_size,
        )
    for directory, kind in (
        (failed_run_dir, "failed_run"),
        (preflight_dir, "preflight"),
        (recovery_dir, "recovery_run"),
    ):
        for path in sorted(item for item in directory.glob("**/*") if item.is_file()):
            relative = str(path.resolve().relative_to(package_root.resolve()))
            if relative in entries:
                raise ValueError(f"post-run source path collision: {relative}")
            entries[relative] = AuditSourceEntry(
                relative_path=relative,
                source_kind=cast(Any, kind),
                sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
    ordered = tuple(entries[key] for key in sorted(entries))
    implementation_count = sum(item.source_kind == "implementation" for item in ordered)
    values = {
        "entries": ordered,
        "implementation_file_count": implementation_count,
        "artifact_file_count": len(ordered) - implementation_count,
        "replayed_file_count": len(ordered),
        "replay_pass_count": len(ordered),
    }
    provisional = PostrunSourceReplayAudit.model_construct(audit_id="pending", **values)
    return PostrunSourceReplayAudit(audit_id=postrun_source_replay_audit_id(provisional), **values)


def _build_scoring_audit(
    *,
    recovery_report: RecoveryExecutionReport,
    rollouts: Sequence[VerifierBoundInstrumentRollout],
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    replay_contract: AuthorityPreservingReplayContract,
) -> CompletedTraceScoringAudit:
    record_by_id = {item.record_id: item for item in records}
    environment_by_id = {item.manifest_id: item for item in environments}
    prospective_counts: Counter[str] = Counter()
    scoring_rows = []
    completed_count = contract_failure_count = prospective_valid_count = 0
    for rollout in rollouts:
        raw_path = Path(rollout.raw_execution_artifact_uri)
        raw = VerifierBoundRawExecutionArtifact.model_validate_json(
            raw_path.read_text(encoding="utf-8")
        )
        record = record_by_id[rollout.task_record_id]
        environment = environment_by_id[rollout.environment_manifest_id]
        replay = replay_authority_preserving_observations(
            replay_contract,
            record,
            environment,
            _observations(raw),
        )
        if not replay.passed:
            raise ValueError(f"post-run Replay failed: {rollout.job_id}")
        if raw.solve_result is None:
            contract_failure_count += 1
            prospective_counts["model_invalid_trajectory"] += 1
            continue
        completed_count += 1
        verification = verify_authority_preserving_agent_result(
            replay_contract,
            record,
            environment,
            raw.solve_result,
        )
        checks, program_complete, mechanism_success = _independent_non_replay_checks(
            record,
            raw,
            replay.selected_evidence_ids,
        )
        verifier_non_replay = {
            key: value
            for key, value in verification.checks.items()
            if key != "runtime_replay_passed"
        }
        if checks != verifier_non_replay:
            raise ValueError(f"independent non-Replay Gates disagree: {rollout.job_id}")
        prospective_terminal = (
            "model_valid_trajectory" if verification.valid else "model_invalid_trajectory"
        )
        prospective_counts[prospective_terminal] += 1
        prospective_valid_count += int(verification.valid)
        if rollout.terminal_category != "instrument_failure" or (
            rollout.failure_attribution or {}
        ).get("reason") != (
            "AttributeError:'TrajectoryStep' object has no attribute 'observation_id'"
        ):
            raise ValueError("completed trajectory lacks the frozen scoring failure")
        trace_payload = tuple(
            {
                "step_index": step.step_index,
                "action": step.action.value,
                "status": step.status.value,
                "observation": step.observation,
            }
            for step in raw.solve_result.trajectory.steps
        )
        row_values = {
            "job_id": rollout.job_id,
            "task_package_id": rollout.task_package_id,
            "mechanism_id": rollout.mechanism_id,
            "replicate_index": rollout.replicate_index,
            "raw_execution_sha256": rollout.raw_execution_artifact_sha256,
            "observation_count": len(raw.solve_result.observations),
            "original_failure_reason": (
                "AttributeError:'TrajectoryStep' object has no attribute 'observation_id'"
            ),
            "prospective_terminal_category": prospective_terminal,
            "prospective_independent_validity": verification.valid,
            "full_program_lineage_completed": program_complete,
            "local_mechanism_success": mechanism_success,
            "schema_valid_decision_trace_hash": canonical_hash(
                trace_payload,
                prefix="finance_v26_schema_valid_decision_trace:",
            ),
        }
        provisional_row = CompletedTraceScoringRow.model_construct(row_id="pending", **row_values)
        scoring_rows.append(
            CompletedTraceScoringRow(
                row_id=completed_trace_scoring_row_id(provisional_row),
                **row_values,
            )
        )
    ordered_rows = tuple(sorted(scoring_rows, key=lambda item: item.job_id))
    values = {
        "completed_trajectory_count": completed_count,
        "captured_model_contract_failure_count": contract_failure_count,
        "original_scoring_instrument_failure_count": len(ordered_rows),
        "scoring_failure_rows": ordered_rows,
        "schema_field_mismatch_count": len(ordered_rows),
        "prospective_independently_valid_count": prospective_valid_count,
        "prospective_terminal_counts": dict(sorted(prospective_counts.items())),
    }
    if recovery_report.instrument_result.replay_pass_count != EXPECTED_JOB_COUNT:
        raise ValueError("Recovery report did not retain all Replay passes")
    provisional = CompletedTraceScoringAudit.model_construct(audit_id="pending", **values)
    return CompletedTraceScoringAudit(
        audit_id=completed_trace_scoring_audit_id(provisional), **values
    )


def _build_resource_audit(
    *,
    recovery_report: RecoveryExecutionReport,
    rollouts: Sequence[VerifierBoundInstrumentRollout],
) -> ResourceBudgetAudit:
    crossings = []
    maximum_tokens = maximum_overshoot = 0
    pass_count = 0
    for rollout in rollouts:
        raw = VerifierBoundRawExecutionArtifact.model_validate_json(
            Path(rollout.raw_execution_artifact_uri).read_text(encoding="utf-8")
        )
        totals = tuple(item.total_tokens or 0 for item in raw.provider_telemetry)
        total = sum(totals)
        maximum_tokens = max(maximum_tokens, total)
        if total <= 120000:
            pass_count += 1
            continue
        prior = sum(totals[:-1])
        crossing = totals[-1]
        overshoot = total - 120000
        maximum_overshoot = max(maximum_overshoot, overshoot)
        row_values = {
            "job_id": rollout.job_id,
            "task_package_id": rollout.task_package_id,
            "mechanism_id": rollout.mechanism_id,
            "provider_call_count": len(totals),
            "pre_crossing_provider_tokens": prior,
            "crossing_call_tokens": crossing,
            "total_provider_tokens": total,
            "overshoot_tokens": overshoot,
            "raw_execution_error": raw.execution_error,
        }
        provisional_row = TokenBudgetCrossing.model_construct(row_id="pending", **row_values)
        crossings.append(
            TokenBudgetCrossing(row_id=token_budget_crossing_id(provisional_row), **row_values)
        )
    ordered = tuple(sorted(crossings, key=lambda item: item.job_id))
    profile = IterativeAgentProtocolProfile()
    values = {
        "aggregate_estimated_cost_usd": recovery_report.total_estimated_cost_usd,
        "per_rollout_token_pass_count": pass_count,
        "per_rollout_token_failure_count": len(ordered),
        "crossings": ordered,
        "maximum_total_provider_tokens": maximum_tokens,
        "maximum_overshoot_tokens": maximum_overshoot,
        "contract_repair_token_reserve": profile.contract_repair_token_reserve,
        "final_answer_token_reserve": profile.final_answer_token_reserve,
        "post_response_enforcement_count": len(ordered),
    }
    provisional = ResourceBudgetAudit.model_construct(audit_id="pending", **values)
    return ResourceBudgetAudit(audit_id=resource_budget_audit_id(provisional), **values)


def _build_lineage_audit(
    *,
    failed_run_dir: Path,
    recovery_dir: Path,
    recovery_report: RecoveryExecutionReport,
    recovery_manifest: RecoveryManifest,
    rollouts: Sequence[VerifierBoundInstrumentRollout],
) -> IndependentRawLineageAudit:
    role_by_job = {item.original_job.job_id: item.recovery_role for item in recovery_manifest.jobs}
    recovery_binding = recovery_report.recovery_execution_binding_id
    raw_binding_pass = replay_jobs = continuation_jobs = 0
    original_count = continuation_count = original_byte_pass = 0
    provider_binding_pass = telemetry_pass = 0
    provider_ids = []
    for rollout in rollouts:
        raw = VerifierBoundRawExecutionArtifact.model_validate_json(
            Path(rollout.raw_execution_artifact_uri).read_text(encoding="utf-8")
        )
        if raw.execution_binding_id != recovery_binding:
            raise ValueError("independent lineage audit found another raw Binding")
        raw_binding_pass += 1
        role = role_by_job[rollout.job_id]
        replay = role == "zero_generation_replay"
        replay_jobs += int(replay)
        continuation_jobs += int(not replay)
        expected_binding = FAILED_EXECUTION_BINDING_ID if replay else recovery_binding
        for index, descriptor in enumerate(raw.provider_call_artifacts):
            path = recovery_dir / descriptor.relative_path
            if _sha256(path) != descriptor.sha256 or (path.stat().st_size != descriptor.byte_count):
                raise ValueError("independent lineage audit found changed Provider bytes")
            artifact = RawProviderCallArtifact.model_validate_json(path.read_text(encoding="utf-8"))
            if (
                artifact.execution_binding_id != expected_binding
                or artifact.job_id != rollout.job_id
                or artifact.call_index != index
            ):
                raise ValueError("independent lineage audit found a Provider identity mismatch")
            provider_binding_pass += 1
            if not _telemetry_equal_before_host_augmentation(
                artifact.telemetry, raw.provider_telemetry[index]
            ):
                raise ValueError("independent lineage telemetry comparison failed")
            telemetry_pass += 1
            if replay:
                original_count += 1
                source = failed_run_dir / descriptor.relative_path
                if source.read_bytes() != path.read_bytes():
                    raise ValueError("zero-generation Provider bytes differ from v26.78")
                original_byte_pass += 1
            else:
                continuation_count += 1
            provider_ids.append(artifact.provider_call_id)
    historical_failures = recovery_report.raw_lineage_audit.failed_artifacts
    values = {
        "observed_raw_execution_count": len(rollouts),
        "raw_execution_recovery_binding_pass_count": raw_binding_pass,
        "zero_generation_replay_job_count": replay_jobs,
        "continuation_job_count": continuation_jobs,
        "original_provider_artifact_count": original_count,
        "continuation_provider_artifact_count": continuation_count,
        "original_provider_exact_byte_pass_count": original_byte_pass,
        "provider_binding_pass_count": provider_binding_pass,
        "provider_telemetry_pre_host_augmentation_pass_count": telemetry_pass,
        "provider_call_ids_unique": len(provider_ids) == len(set(provider_ids)),
        "historical_report_lineage_status": recovery_report.raw_lineage_audit.status,
        "historical_report_failed_artifact_count": len(historical_failures),
        "historical_failed_artifacts_are_instrument_gate_failures": all(
            item.endswith("ValueError:independent non-Replay Gate audit failed")
            for item in historical_failures
        ),
        "lineage_and_instrument_failure_lists_coupled": bool(historical_failures),
        "lineage_only_passed": bool(
            raw_binding_pass == 32
            and replay_jobs == 17
            and continuation_jobs == 15
            and original_count == 146
            and original_byte_pass == 146
            and provider_binding_pass == original_count + continuation_count
            and telemetry_pass == original_count + continuation_count
            and len(provider_ids) == len(set(provider_ids))
        ),
    }
    provisional = IndependentRawLineageAudit.model_construct(audit_id="pending", **values)
    return IndependentRawLineageAudit(
        audit_id=independent_raw_lineage_audit_id(provisional), **values
    )


def build_verifier_bound_postrun_audit(
    *,
    failed_run_dir: Path,
    preflight_dir: Path,
    recovery_dir: Path,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> VerifierBoundPostrunAuditReport:
    recovery_report = RecoveryExecutionReport.model_validate_json(
        (recovery_dir / "report.json").read_text(encoding="utf-8")
    )
    if recovery_report.report_id != EXPECTED_RECOVERY_REPORT_ID or (
        recovery_report.instrument_result.report_id != EXPECTED_RECOVERY_INSTRUMENT_RESULT_ID
    ):
        raise ValueError("post-run audit received another Recovery result")
    recovery_contract = RecoveryContract.model_validate_json(
        (preflight_dir / "recovery_contract.json").read_text(encoding="utf-8")
    )
    recovery_manifest = RecoveryManifest.model_validate_json(
        (preflight_dir / "recovery_manifest.json").read_text(encoding="utf-8")
    )
    preflight_report = json.loads((preflight_dir / "report.json").read_text(encoding="utf-8"))
    if preflight_report["report_id"] != EXPECTED_RECOVERY_PREFLIGHT_ID:
        raise ValueError("post-run audit received another Recovery preflight")
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
    replay_contract = AuthorityPreservingReplayContract.model_validate_json(
        (verifier_qualification_dir / "replay_contract.json").read_text(encoding="utf-8")
    )
    rollouts = cast(
        tuple[VerifierBoundInstrumentRollout, ...],
        _load_rows(recovery_dir / "instrument_rollouts.json", VerifierBoundInstrumentRollout),
    )
    if len(rollouts) != EXPECTED_JOB_COUNT:
        raise ValueError("post-run audit received an incomplete Recovery denominator")
    source_replay = _build_source_replay(
        package_root=package_root,
        failed_run_dir=failed_run_dir,
        preflight_dir=preflight_dir,
        recovery_dir=recovery_dir,
        recovery_contract=recovery_contract,
    )
    scoring = _build_scoring_audit(
        recovery_report=recovery_report,
        rollouts=rollouts,
        records=records,
        environments=environments,
        replay_contract=replay_contract,
    )
    resource = _build_resource_audit(
        recovery_report=recovery_report,
        rollouts=rollouts,
    )
    lineage = _build_lineage_audit(
        failed_run_dir=failed_run_dir,
        recovery_dir=recovery_dir,
        recovery_report=recovery_report,
        recovery_manifest=recovery_manifest,
        rollouts=rollouts,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_payloads = {
        "completed_trace_scoring_audit.json": scoring.model_dump(mode="json"),
        "raw_lineage_independent_audit.json": lineage.model_dump(mode="json"),
        "resource_budget_audit.json": resource.model_dump(mode="json"),
        "source_replay_audit.json": source_replay.model_dump(mode="json"),
    }
    for relative, payload in detail_payloads.items():
        _write_json(output_dir / relative, payload)
    details = tuple(
        DetailFile(
            relative_path=relative,
            sha256=_sha256(output_dir / relative),
            byte_count=(output_dir / relative).stat().st_size,
        )
        for relative in sorted(detail_payloads)
    )
    report_values = {
        "source_replay_audit_id": source_replay.audit_id,
        "scoring_audit_id": scoring.audit_id,
        "resource_budget_audit_id": resource.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "immutable_detail_files": details,
    }
    provisional_report = VerifierBoundPostrunAuditReport.model_construct(
        report_id="pending", **report_values
    )
    report = VerifierBoundPostrunAuditReport(
        report_id=postrun_audit_report_id(provisional_report), **report_values
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def postrun_source_replay_audit_id(value: PostrunSourceReplayAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_postrun_source_replay:",
    )


def completed_trace_scoring_row_id(value: CompletedTraceScoringRow) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"row_id"}),
        prefix="finance_v26_completed_trace_scoring_row:",
    )


def completed_trace_scoring_audit_id(value: CompletedTraceScoringAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_completed_trace_scoring_audit:",
    )


def token_budget_crossing_id(value: TokenBudgetCrossing) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"row_id"}),
        prefix="finance_v26_token_budget_crossing:",
    )


def resource_budget_audit_id(value: ResourceBudgetAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_strict_resource_budget_audit:",
    )


def independent_raw_lineage_audit_id(value: IndependentRawLineageAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_recovery_raw_lineage_independent_audit:",
    )


def postrun_audit_report_id(value: VerifierBoundPostrunAuditReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_verifier_bound_postrun_audit:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the failed v26.80 Verifier-bound Instrument Recovery without API calls"
    )
    parser.add_argument("--failed-run-dir", type=Path, required=True)
    parser.add_argument("--preflight-dir", type=Path, required=True)
    parser.add_argument("--recovery-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    report = build_verifier_bound_postrun_audit(
        failed_run_dir=args.failed_run_dir,
        preflight_dir=args.preflight_dir,
        recovery_dir=args.recovery_dir,
        task_source_dir=args.task_source_dir,
        verifier_qualification_dir=args.verifier_qualification_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
