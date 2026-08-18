from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    EmpiricalPilotRollout,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_regression import (  # noqa: E501
    EXPECTED_ROLLOUT_COUNT,
    OperationClosureRawIntegrityAudit,
    OperationClosureRegressionContract,
    OperationClosureRegressionJobManifest,
    OperationClosureRegressionReport,
    OperationClosureRolloutDiagnostic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_regression import (
    _diagnostic as regression_diagnostic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_regression import (
    _raw_integrity_audit as regression_raw_integrity_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.tools import AgentToolObservation

V26_AUTHORITY_PRESERVING_POSTRUN_AUDIT_VERSION = "finance_v26_authority_preserving_postrun_audit.v1"
V26_AUTHORITY_PRESERVING_ROLLOUT_AUDIT_VERSION = "finance_v26_authority_preserving_rollout_audit.v1"
V26_AUTHORITY_PRESERVING_MECHANISM_SUMMARY_VERSION = (
    "finance_v26_authority_preserving_mechanism_summary.v1"
)
V26_FINALIZATION_RECOVERY_AUDIT_VERSION = "finance_v26_finalization_recovery_audit.v1"

IMPLEMENTATION_SOURCE_PATH: Literal[
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_authority_preserving_postrun_audit.py"
] = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_authority_preserving_postrun_audit.py"
)

_REPAIR_CONTEXT_FIELDS = frozenset(
    {
        "error_category",
        "failed_tool_id",
        "identical_arguments_forbidden",
        "unresolved_public_variables",
        "unresolved_semantic_requirements",
    }
)
_ACTION_BINDING_FIELDS = frozenset(
    {
        "available_resolution_actions",
        "correct_operator",
        "correct_parameters",
        "correct_tool_id",
        "expected_arguments",
        "operator",
        "parameters",
        "required_argument_patch",
        "required_next_tools",
        "required_prerequisite_action",
        "suggested_argument_patch",
    }
)
_RECOVERY_EQUAL_FILES = (
    "execution_contract.json",
    "job_manifest.json",
    "rollout_observations.checkpoint.jsonl",
    "empirical_rollouts.json",
    "raw_integrity_audit.json",
    "rollout_diagnostics.json",
)
_RECOVERY_SOURCE_FILES = {
    "empirical_rollouts.json": EXPECTED_ROLLOUT_COUNT,
    "execution_contract.json": 1,
    "job_manifest.json": 1,
    "raw_integrity_audit.json": 1,
    "report.json": 1,
    "rollout_diagnostics.json": EXPECTED_ROLLOUT_COUNT,
    "rollout_observations.checkpoint.jsonl": EXPECTED_ROLLOUT_COUNT,
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AuditSourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class AuditImplementationSource(FrozenModel):
    relative_path: Literal[
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_authority_preserving_postrun_audit.py"
    ] = IMPLEMENTATION_SOURCE_PATH
    sha256: str = Field(min_length=64, max_length=64)


class RecoveryFileComparison(FrozenModel):
    relative_path: str = Field(min_length=1)
    interrupted_sha256: str = Field(min_length=64, max_length=64)
    recovery_sha256: str = Field(min_length=64, max_length=64)
    byte_identical: Literal[True] = True

    @model_validator(mode="after")
    def validate_comparison(self) -> RecoveryFileComparison:
        if self.interrupted_sha256 != self.recovery_sha256:
            raise ValueError("finalization recovery changed a frozen source byte")
        return self


class FinalizationRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    job_manifest_id: str = Field(min_length=1)
    interrupted_preflight_report_id: str = Field(min_length=1)
    interrupted_preflight_report_sha256: str = Field(min_length=64, max_length=64)
    recovered_report_id: str = Field(min_length=1)
    recovered_report_sha256: str = Field(min_length=64, max_length=64)
    file_comparisons: tuple[RecoveryFileComparison, ...] = Field(min_length=6, max_length=6)
    checkpoint_rollout_count_before: Literal[32] = 32
    checkpoint_rollout_count_after: Literal[32] = 32
    checkpoint_job_identity_count_before: Literal[32] = 32
    checkpoint_job_identity_count_after: Literal[32] = 32
    missing_job_count_before_recovery: Literal[0] = 0
    duplicate_job_count_before_recovery: Literal[0] = 0
    preflight_report_preserved: Literal[True] = True
    raw_model_jobs_repeated: Literal[False] = False
    recovery_model_job_count: Literal[0] = 0
    recovery_api_call_count: Literal[0] = 0
    recovery_gpu_job_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_FINALIZATION_RECOVERY_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FinalizationRecoveryAudit:
        if tuple(item.relative_path for item in self.file_comparisons) != tuple(
            sorted(_RECOVERY_EQUAL_FILES)
        ):
            raise ValueError("finalization recovery comparison matrix is incomplete")
        if self.audit_id != finalization_recovery_audit_id(self):
            raise ValueError("finalization recovery audit identity is invalid")
        return self


class AuthorityPreservingRolloutAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    terminal_category: str = Field(min_length=1)
    failure_reason: str = Field(min_length=1)
    exact_requested_model: Literal[True] = True
    fallback_used: Literal[False] = False
    raw_artifact_hash_replayed: Literal[True] = True
    public_contract_in_initial_prompt: Literal[True] = True
    public_progress_projection_passed: Literal[True] = True
    private_identity_absent: Literal[True] = True
    authority_contract_in_initial_prompt: Literal[True] = True
    terminal_target_in_initial_prompt: Literal[True] = True
    repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    action_bearing_failed_observation_count: int = Field(ge=0)
    full_program_lineage_completed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    stop_ready: bool
    stop_ready_false_positive: Literal[False] = False
    stop_ready_false_negative: Literal[False] = False
    exact_terminal_target_acceptance_count: int = Field(ge=0)
    independently_valid: bool
    acquisition_path: Literal[
        "structured_direct",
        "search_then_structured",
        "search_then_open",
        "unclassified",
    ]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    schema_version: str = V26_AUTHORITY_PRESERVING_ROLLOUT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorityPreservingRolloutAudit:
        if self.action_bearing_repair_prompt_count or self.action_bearing_failed_observation_count:
            raise ValueError("authority-preserving rollout contains action-bearing repair feedback")
        if self.postterminal_verification_completed != (
            self.exact_terminal_target_acceptance_count > 0
        ):
            raise ValueError("terminal verification target replay differs from frozen Progress")
        if self.independently_valid and not (
            self.full_program_lineage_completed
            and self.terminal_node_completed
            and self.postterminal_verification_completed
            and self.stop_ready
        ):
            raise ValueError("independently valid rollout lacks public terminal closure")
        if self.audit_id != authority_preserving_rollout_audit_id(self):
            raise ValueError("authority-preserving rollout audit identity is invalid")
        return self


class AuthorityPreservingMechanismSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    task_count: Literal[2] = 2
    rollout_count: Literal[8] = 8
    full_program_lineage_count: int = Field(ge=0, le=8)
    terminal_node_completion_count: int = Field(ge=0, le=8)
    postterminal_verification_count: int = Field(ge=0, le=8)
    independently_valid_count: int = Field(ge=0, le=8)
    valid_task_count: int = Field(ge=0, le=2)
    repair_prompt_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    failure_reason_counts: dict[str, int]
    acquisition_path_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    schema_version: str = V26_AUTHORITY_PRESERVING_MECHANISM_SUMMARY_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> AuthorityPreservingMechanismSummary:
        if sum(self.failure_reason_counts.values()) != self.rollout_count:
            raise ValueError("mechanism failure reasons have an incomplete denominator")
        if sum(self.acquisition_path_counts.values()) != self.rollout_count:
            raise ValueError("mechanism acquisition paths have an incomplete denominator")
        if self.summary_id != authority_preserving_mechanism_summary_id(self):
            raise ValueError("authority-preserving mechanism summary identity is invalid")
        return self


class AuthorityPreservingPostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    source_contract_id: str = Field(min_length=1)
    source_job_manifest_id: str = Field(min_length=1)
    task_source_report_id: str = Field(min_length=1)
    task_source_report_sha256: str = Field(min_length=64, max_length=64)
    source_files: tuple[AuditSourceFile, ...] = Field(min_length=50)
    implementation_source: AuditImplementationSource
    finalization_recovery: FinalizationRecoveryAudit
    source_integrity_passed: Literal[True] = True
    source_instrument_result_retained: Literal[True] = True
    source_outcomes_rescored: Literal[False] = False
    completed_rollout_count: Literal[32] = 32
    model_outcome_count: Literal[32] = 32
    runtime_failure_count: Literal[0] = 0
    instrument_failure_count: Literal[0] = 0
    exact_model_rollout_count: Literal[32] = 32
    fallback_rollout_count: Literal[0] = 0
    provider_call_count: int = Field(ge=1)
    provider_total_tokens: int = Field(ge=1)
    estimated_cost_usd: str = Field(min_length=1)
    public_contract_prompt_count: Literal[32] = 32
    public_progress_prompt_count: Literal[32] = 32
    private_identity_free_count: Literal[32] = 32
    authority_contract_prompt_count: Literal[32] = 32
    terminal_target_prompt_count: Literal[32] = 32
    repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: Literal[0] = 0
    failed_observation_count: int = Field(ge=0)
    action_bearing_failed_observation_count: Literal[0] = 0
    full_program_lineage_count: int = Field(ge=0, le=32)
    terminal_node_completion_count: int = Field(ge=0, le=32)
    postterminal_verification_count: int = Field(ge=0, le=32)
    exact_terminal_target_acceptance_count: int = Field(ge=0)
    independently_valid_count: int = Field(ge=0, le=32)
    valid_task_count: int = Field(ge=0, le=8)
    valid_mechanism_counts: dict[str, int]
    stop_ready_false_positive_count: Literal[0] = 0
    stop_ready_false_negative_count: Literal[0] = 0
    mechanism_summaries: tuple[AuthorityPreservingMechanismSummary, ...] = Field(
        min_length=4, max_length=4
    )
    rollout_audits: tuple[AuthorityPreservingRolloutAudit, ...] = Field(
        min_length=32, max_length=32
    )
    static_public_support_established: Literal[True] = True
    operational_instrument_established: Literal[True] = True
    authority_preserving_instrument_established: Literal[True] = True
    model_validity_smoke_observed: bool
    all_mechanisms_empirically_supported: Literal[False] = False
    capability_support_admitted: Literal[False] = False
    state_reachability_evaluable: Literal[False] = False
    state_support_established: Literal[False] = False
    compiler_witnesses_in_empirical_count: Literal[0] = 0
    capability_protocol_design_ready: Literal[True] = True
    state_reachability_protocol_design_ready: Literal[True] = True
    api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    task_selection_performed: Literal[False] = False
    model_comparison_performed: Literal[False] = False
    state_mapping_performed: Literal[False] = False
    status: Literal["authority_preserving_operation_instrument_passed"] = (
        "authority_preserving_operation_instrument_passed"
    )
    next_permitted_stage: Literal["capability_development_and_state_reachability_protocol_only"] = (
        "capability_development_and_state_reachability_protocol_only"
    )
    capability_development_authorized: Literal[False] = False
    state_reachability_pilot_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_AUTHORITY_PRESERVING_POSTRUN_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> AuthorityPreservingPostrunAuditReport:
        if self.source_files != tuple(
            sorted(self.source_files, key=lambda item: item.relative_path)
        ):
            raise ValueError("authority-preserving audit source files are not canonical")
        if len({item.relative_path for item in self.source_files}) != len(self.source_files):
            raise ValueError("authority-preserving audit source files contain duplicates")
        rows = self.rollout_audits
        expected = {
            "repair_prompt_count": sum(item.repair_prompt_count for item in rows),
            "failed_observation_count": sum(item.failed_observation_count for item in rows),
            "full_program_lineage_count": sum(item.full_program_lineage_completed for item in rows),
            "terminal_node_completion_count": sum(item.terminal_node_completed for item in rows),
            "postterminal_verification_count": sum(
                item.postterminal_verification_completed for item in rows
            ),
            "exact_terminal_target_acceptance_count": sum(
                item.exact_terminal_target_acceptance_count for item in rows
            ),
            "independently_valid_count": sum(item.independently_valid for item in rows),
            "provider_call_count": sum(item.provider_call_count for item in rows),
            "provider_total_tokens": sum(item.provider_total_tokens for item in rows),
        }
        if any(getattr(self, key) != value for key, value in expected.items()):
            raise ValueError("authority-preserving report differs from rollout audits")
        valid_rows = tuple(item for item in rows if item.independently_valid)
        if self.valid_task_count != len({item.task_package_id for item in valid_rows}):
            raise ValueError("valid task count differs from rollout audits")
        if self.valid_mechanism_counts != dict(
            sorted(Counter(item.mechanism_id for item in valid_rows).items())
        ):
            raise ValueError("valid mechanism counts differ from rollout audits")
        if self.model_validity_smoke_observed != bool(valid_rows):
            raise ValueError("model-validity smoke decision is inconsistent")
        if tuple(item.mechanism_id for item in self.mechanism_summaries) != TARGET_MECHANISMS:
            raise ValueError("authority-preserving mechanism summaries are incomplete")
        if self.finalization_recovery.recovered_report_id != self.source_report_id:
            raise ValueError("finalization recovery does not bind the audited report")
        if self.report_id != authority_preserving_postrun_report_id(self):
            raise ValueError("authority-preserving post-run report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    if path.suffix == ".jsonl":
        return sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines())
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 1


def _source_file(prefix: str, root: Path, relative: str, expected: int) -> AuditSourceFile:
    path = root / relative
    if not path.is_file() or _record_count(path) != expected:
        raise ValueError(f"authority-preserving source denominator changed: {path}")
    return AuditSourceFile(
        relative_path=f"{prefix}/{relative}",
        sha256=_sha256(path),
        record_count=expected,
    )


def _write_json_atomic(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"authority-preserving immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _load_checkpoint(path: Path) -> tuple[EmpiricalPilotRollout, ...]:
    return tuple(
        EmpiricalPilotRollout.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _raw_payload(
    rollout: EmpiricalPilotRollout,
    interrupted_dir: Path,
) -> tuple[dict[str, Any], AuditSourceFile]:
    path = Path(rollout.raw_artifact_uri).resolve()
    try:
        relative = path.relative_to(interrupted_dir.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("v26.66 raw Artifact is outside the interrupted execution") from error
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != rollout.raw_artifact_sha256:
        raise ValueError("v26.66 raw Artifact hash replay failed")
    payload = cast(dict[str, Any], json.loads(raw))
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError("v26.66 raw Artifact is not canonical JSON")
    return payload, AuditSourceFile(
        relative_path=f"execution/{relative}",
        sha256=rollout.raw_artifact_sha256,
        record_count=1,
    )


def _observations(payload: Mapping[str, Any]) -> tuple[AgentToolObservation, ...]:
    failure = payload.get("failure_artifact")
    if isinstance(failure, Mapping):
        return tuple(
            AgentToolObservation.model_validate(item) for item in failure.get("observations") or ()
        )
    trajectory = payload.get("trajectory")
    if not isinstance(trajectory, Mapping):
        return ()
    output = []
    for step in trajectory.get("steps") or ():
        observation = step.get("observation") if isinstance(step, Mapping) else None
        if isinstance(observation, Mapping) and "observation_id" in observation:
            output.append(AgentToolObservation.model_validate(observation))
    return tuple(output)


def _prompt_context(prompt: str) -> Mapping[str, Any] | None:
    _, marker, remainder = prompt.partition("\nPUBLIC_CONTEXT_JSON:\n")
    if not marker:
        return None
    context_text, _, _ = remainder.partition("\nCONTRACT_REPAIR_JSON:\n")
    value = json.loads(context_text)
    if not isinstance(value, Mapping):
        raise ValueError("v26.66 Prompt public Context is not a mapping")
    return value


def _contains_action_binding(value: Any) -> bool:
    if isinstance(value, Mapping):
        if _ACTION_BINDING_FIELDS & set(value):
            return True
        return any(_contains_action_binding(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_action_binding(item) for item in value)
    return False


def _repair_prompt_counts(prompts: Sequence[str]) -> tuple[int, int]:
    observed = action_bearing = 0
    for prompt in prompts:
        context = _prompt_context(prompt)
        if context is None or "failed_action_repair" not in context:
            continue
        repair = context["failed_action_repair"]
        if repair is None:
            continue
        observed += 1
        if (
            not isinstance(repair, Mapping)
            or set(repair) != _REPAIR_CONTEXT_FIELDS
            or _contains_action_binding(repair)
        ):
            action_bearing += 1
    return observed, action_bearing


def _failed_observation_counts(
    observations: Sequence[AgentToolObservation],
) -> tuple[int, int]:
    failed = tuple(item for item in observations if item.status == "failed")
    return len(failed), sum(_contains_action_binding(item.result) for item in failed)


def _acquisition_path(
    observations: Sequence[AgentToolObservation],
) -> Literal[
    "structured_direct",
    "search_then_structured",
    "search_then_open",
    "unclassified",
]:
    tools = []
    for observation in observations:
        if observation.call.tool_id == "calculator" and observation.status == "succeeded":
            break
        if observation.status == "succeeded":
            tools.append(observation.call.tool_id)
    if "open_document" in tools:
        return "search_then_open"
    if "search_archive" in tools:
        return "search_then_structured"
    if "query_structured_fact" in tools:
        return "structured_direct"
    return "unclassified"


def _terminal_target_acceptance_count(
    record: OperationalTaskRecord,
    observations: Sequence[AgentToolObservation],
) -> int:
    terminal_seen = False
    terminal_ref: str | None = None
    count = 0
    task = record.task_package.task.public
    for index, observation in enumerate(observations, start=1):
        progress = public_operation_progress(task, tuple(observations[:index]))
        if progress is None:
            raise ValueError("v26.66 replay lost its public Operation contract")
        if not terminal_seen and progress["terminal_node_completed"]:
            terminal_seen = True
            terminal_ref = cast(str | None, progress["terminal_operation_ref"])
        if (
            terminal_seen
            and observation.call.tool_id == "cross_check_evidence"
            and observation.status == "succeeded"
            and observation.result.get("verified") is True
            and observation.call.arguments.get("claim_or_result") == {"operation_ref": terminal_ref}
        ):
            count += 1
    return count


def _failure_reason(rollout: EmpiricalPilotRollout) -> str:
    if rollout.verification is not None and rollout.verification.valid:
        return "valid"
    if rollout.verification is not None and rollout.verification.earliest_failure_stage:
        return f"verification:{rollout.verification.earliest_failure_stage}"
    attribution = rollout.failure_attribution
    if isinstance(attribution, Mapping) and attribution.get("reason"):
        return str(attribution["reason"])
    return "model_invalid_without_failure_attribution"


def _rollout_audit(
    rollout: EmpiricalPilotRollout,
    frozen: OperationClosureRolloutDiagnostic,
    record: OperationalTaskRecord,
    payload: Mapping[str, Any],
) -> AuthorityPreservingRolloutAudit:
    observations = _observations(payload)
    prompts = tuple(str(item) for item in payload["actual_model_request_prompts"])
    repair_prompt_count, repair_exposure = _repair_prompt_counts(prompts)
    failed_count, failed_exposure = _failed_observation_counts(observations)
    target_acceptance_count = _terminal_target_acceptance_count(record, observations)
    values: dict[str, Any] = {
        "rollout_id": rollout.rollout_id,
        "job_id": rollout.job_id,
        "task_package_id": rollout.task_package_id,
        "mechanism_id": rollout.mechanism_id,
        "replicate_index": rollout.replicate_index,
        "terminal_category": rollout.terminal_category,
        "failure_reason": _failure_reason(rollout),
        "exact_requested_model": rollout.exact_requested_model,
        "fallback_used": rollout.fallback_used,
        "public_contract_in_initial_prompt": frozen.public_contract_in_initial_prompt,
        "public_progress_projection_passed": frozen.public_progress_in_decision_prompt,
        "private_identity_absent": frozen.initial_prompt_private_identity_free,
        "authority_contract_in_initial_prompt": frozen.authority_contract_in_initial_prompt,
        "terminal_target_in_initial_prompt": frozen.terminal_target_in_initial_prompt,
        "repair_prompt_count": repair_prompt_count,
        "action_bearing_repair_prompt_count": repair_exposure,
        "failed_observation_count": failed_count,
        "action_bearing_failed_observation_count": failed_exposure,
        "full_program_lineage_completed": frozen.full_program_lineage_completed,
        "terminal_node_completed": frozen.terminal_node_completed,
        "postterminal_verification_completed": frozen.postterminal_verification_completed,
        "stop_ready": frozen.stop_ready,
        "stop_ready_false_positive": frozen.stop_ready_false_positive,
        "stop_ready_false_negative": frozen.stop_ready_false_negative,
        "exact_terminal_target_acceptance_count": target_acceptance_count,
        "independently_valid": frozen.independent_validity,
        "acquisition_path": _acquisition_path(observations),
        "provider_call_count": rollout.provider_call_count,
        "provider_total_tokens": rollout.provider_total_tokens,
    }
    provisional = AuthorityPreservingRolloutAudit.model_construct(audit_id="pending", **values)
    return AuthorityPreservingRolloutAudit(
        audit_id=authority_preserving_rollout_audit_id(provisional),
        **values,
    )


def _mechanism_summary(
    mechanism: str,
    rows: Sequence[AuthorityPreservingRolloutAudit],
) -> AuthorityPreservingMechanismSummary:
    selected = tuple(item for item in rows if item.mechanism_id == mechanism)
    values: dict[str, Any] = {
        "mechanism_id": mechanism,
        "task_count": len({item.task_package_id for item in selected}),
        "rollout_count": len(selected),
        "full_program_lineage_count": sum(item.full_program_lineage_completed for item in selected),
        "terminal_node_completion_count": sum(item.terminal_node_completed for item in selected),
        "postterminal_verification_count": sum(
            item.postterminal_verification_completed for item in selected
        ),
        "independently_valid_count": sum(item.independently_valid for item in selected),
        "valid_task_count": len(
            {item.task_package_id for item in selected if item.independently_valid}
        ),
        "repair_prompt_count": sum(item.repair_prompt_count for item in selected),
        "failed_observation_count": sum(item.failed_observation_count for item in selected),
        "failure_reason_counts": dict(
            sorted(Counter(item.failure_reason for item in selected).items())
        ),
        "acquisition_path_counts": dict(
            sorted(Counter(item.acquisition_path for item in selected).items())
        ),
        "provider_call_count": sum(item.provider_call_count for item in selected),
        "provider_total_tokens": sum(item.provider_total_tokens for item in selected),
    }
    provisional = AuthorityPreservingMechanismSummary.model_construct(
        summary_id="pending", **values
    )
    return AuthorityPreservingMechanismSummary(
        summary_id=authority_preserving_mechanism_summary_id(provisional),
        **values,
    )


def _finalization_recovery_audit(
    interrupted_dir: Path,
    recovery_dir: Path,
    preflight: OperationClosureRegressionReport,
    recovered: OperationClosureRegressionReport,
    manifest: OperationClosureRegressionJobManifest,
) -> FinalizationRecoveryAudit:
    comparisons = tuple(
        RecoveryFileComparison(
            relative_path=relative,
            interrupted_sha256=_sha256(interrupted_dir / relative),
            recovery_sha256=_sha256(recovery_dir / relative),
        )
        for relative in sorted(_RECOVERY_EQUAL_FILES)
    )
    before = _load_checkpoint(interrupted_dir / "rollout_observations.checkpoint.jsonl")
    after = _load_checkpoint(recovery_dir / "rollout_observations.checkpoint.jsonl")
    expected_jobs = {item.job_id for item in manifest.jobs}
    before_jobs = [item.job_id for item in before]
    after_jobs = [item.job_id for item in after]
    values: dict[str, Any] = {
        "run_id": recovered.run_id,
        "contract_id": recovered.contract_id,
        "job_manifest_id": recovered.job_manifest_id,
        "interrupted_preflight_report_id": preflight.report_id,
        "interrupted_preflight_report_sha256": _sha256(interrupted_dir / "report.json"),
        "recovered_report_id": recovered.report_id,
        "recovered_report_sha256": _sha256(recovery_dir / "report.json"),
        "file_comparisons": comparisons,
        "checkpoint_rollout_count_before": len(before),
        "checkpoint_rollout_count_after": len(after),
        "checkpoint_job_identity_count_before": len(set(before_jobs)),
        "checkpoint_job_identity_count_after": len(set(after_jobs)),
        "missing_job_count_before_recovery": len(expected_jobs - set(before_jobs)),
        "duplicate_job_count_before_recovery": len(before_jobs) - len(set(before_jobs)),
    }
    provisional = FinalizationRecoveryAudit.model_construct(audit_id="pending", **values)
    return FinalizationRecoveryAudit(
        audit_id=finalization_recovery_audit_id(provisional),
        **values,
    )


def _load_sources(
    interrupted_dir: Path,
    recovery_dir: Path,
    task_source_dir: Path,
    package_root: Path,
) -> tuple[
    OperationClosureRegressionReport,
    tuple[EmpiricalPilotRollout, ...],
    tuple[OperationalTaskRecord, ...],
    FinalizationRecoveryAudit,
    tuple[AuditSourceFile, ...],
]:
    preflight = OperationClosureRegressionReport.model_validate_json(
        (interrupted_dir / "report.json").read_text(encoding="utf-8")
    )
    report = OperationClosureRegressionReport.model_validate_json(
        (recovery_dir / "report.json").read_text(encoding="utf-8")
    )
    contract = OperationClosureRegressionContract.model_validate_json(
        (recovery_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = OperationClosureRegressionJobManifest.model_validate_json(
        (recovery_dir / "job_manifest.json").read_text(encoding="utf-8")
    )
    raw_audit = OperationClosureRawIntegrityAudit.model_validate_json(
        (recovery_dir / "raw_integrity_audit.json").read_text(encoding="utf-8")
    )
    if preflight.status != "preflight" or preflight.completed_rollout_count != 0:
        raise ValueError("interrupted v26.66 preflight report was not preserved")
    if (
        not report.instrument_ready
        or report.status != "passed"
        or report.completed_rollout_count != EXPECTED_ROLLOUT_COUNT
        or report.model_outcome_count != EXPECTED_ROLLOUT_COUNT
        or report.runtime_failure_count
        or report.instrument_failure_count
        or report.next_permitted_stage
        != "capability_development_and_state_reachability_protocol_only"
    ):
        raise ValueError("recovered v26.66 instrument result is not passing")
    if (
        preflight.contract_id != report.contract_id
        or preflight.job_manifest_id != report.job_manifest_id
        or report.contract_id != contract.contract_id
        or report.job_manifest_id != manifest.manifest_id
        or manifest.contract_id != contract.contract_id
        or report.raw_integrity_audit != raw_audit
        or raw_audit.status != "passed"
    ):
        raise ValueError("v26.66 reports differ from their frozen inputs")
    if not (
        contract.authority_preserving_contract_required
        and contract.action_neutral_repair_required
        and contract.unified_terminal_verification_required
    ):
        raise ValueError("v26.66 execution contract lacks authority-preserving gates")
    for item in contract.implementation_source_files:
        if _sha256(package_root / item.relative_path) != item.sha256:
            raise ValueError(f"v26.66 implementation source changed: {item.relative_path}")

    task_report_path = task_source_dir / "report.json"
    task_report = AuthorityPreservingHardeningReport.model_validate_json(
        task_report_path.read_text(encoding="utf-8")
    )
    if (
        contract.source_report_id != task_report.report_id
        or contract.source_report_sha256 != _sha256(task_report_path)
    ):
        raise ValueError("v26.66 task source differs from its execution contract")
    for item in contract.source_artifact_files:
        if _sha256(task_source_dir / item.relative_path) != item.sha256:
            raise ValueError(f"v26.65 source Artifact changed: {item.relative_path}")

    rollouts = tuple(
        EmpiricalPilotRollout.model_validate(item)
        for item in json.loads((recovery_dir / "empirical_rollouts.json").read_text())
    )
    checkpoint = _load_checkpoint(recovery_dir / "rollout_observations.checkpoint.jsonl")
    checkpoint_by_job = {item.job_id: item for item in checkpoint}
    rollout_by_job = {item.job_id: item for item in rollouts}
    if len(checkpoint_by_job) != EXPECTED_ROLLOUT_COUNT or checkpoint_by_job != rollout_by_job:
        raise ValueError("v26.66 recovery aggregate differs from its checkpoint")
    if tuple(item.job_id for item in rollouts) != tuple(item.job_id for item in manifest.jobs):
        raise ValueError("v26.66 rollout order differs from its Job Manifest")
    frozen_diagnostics = tuple(
        OperationClosureRolloutDiagnostic.model_validate(item)
        for item in json.loads((recovery_dir / "rollout_diagnostics.json").read_text())
    )
    if frozen_diagnostics != report.diagnostics:
        raise ValueError("v26.66 detail diagnostics differ from its report")
    record_by_id = {item.record_id: item for item in task_report.task_records}
    selected_ids = {item.task_record_id for item in manifest.jobs}
    if selected_ids - record_by_id.keys():
        raise ValueError("v26.66 selected task records are unavailable")
    selected = tuple(record_by_id[item] for item in sorted(selected_ids))
    if regression_raw_integrity_audit(rollouts) != raw_audit:
        raise ValueError("v26.66 raw-integrity audit did not replay")
    replayed_diagnostics = tuple(
        regression_diagnostic(rollout, record_by_id[rollout.task_record_id]) for rollout in rollouts
    )
    if {item.rollout_id: item for item in replayed_diagnostics} != {
        item.rollout_id: item for item in report.diagnostics
    }:
        raise ValueError("v26.66 rollout diagnostics did not replay")

    recovery_audit = _finalization_recovery_audit(
        interrupted_dir,
        recovery_dir,
        preflight,
        report,
        manifest,
    )
    source_files = [
        _source_file("recovery", recovery_dir, relative, count)
        for relative, count in sorted(_RECOVERY_SOURCE_FILES.items())
    ]
    source_files.extend(
        (
            _source_file("interrupted", interrupted_dir, "report.json", 1),
            _source_file(
                "interrupted",
                interrupted_dir,
                "rollout_observations.checkpoint.jsonl",
                EXPECTED_ROLLOUT_COUNT,
            ),
            AuditSourceFile(
                relative_path="task_source/report.json",
                sha256=_sha256(task_report_path),
                record_count=1,
            ),
        )
    )
    source_files.extend(
        AuditSourceFile(
            relative_path=f"task_source/{item.relative_path}",
            sha256=item.sha256,
            record_count=item.record_count,
        )
        for item in task_report.immutable_artifact_files
    )
    for rollout in rollouts:
        _, source_file = _raw_payload(rollout, interrupted_dir)
        source_files.append(source_file)
    return (
        report,
        rollouts,
        selected,
        recovery_audit,
        tuple(sorted(source_files, key=lambda item: item.relative_path)),
    )


def build_authority_preserving_postrun_audit(
    *,
    run_id: str,
    interrupted_dir: Path,
    recovery_dir: Path,
    task_source_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> AuthorityPreservingPostrunAuditReport:
    (
        source_report,
        rollouts,
        records,
        recovery_audit,
        source_files,
    ) = _load_sources(
        interrupted_dir,
        recovery_dir,
        task_source_dir,
        package_root,
    )
    frozen_by_rollout = {item.rollout_id: item for item in source_report.diagnostics}
    record_by_id = {item.record_id: item for item in records}
    rows = []
    for rollout in rollouts:
        payload, _ = _raw_payload(rollout, interrupted_dir)
        rows.append(
            _rollout_audit(
                rollout,
                frozen_by_rollout[rollout.rollout_id],
                record_by_id[rollout.task_record_id],
                payload,
            )
        )
    rows.sort(key=lambda item: item.audit_id)
    frozen_rows = tuple(rows)
    summaries = tuple(_mechanism_summary(mechanism, frozen_rows) for mechanism in TARGET_MECHANISMS)
    valid_rows = tuple(item for item in frozen_rows if item.independently_valid)
    task_report_path = task_source_dir / "report.json"
    values: dict[str, Any] = {
        "run_id": run_id,
        "source_run_id": source_report.run_id,
        "source_report_id": source_report.report_id,
        "source_report_sha256": _sha256(recovery_dir / "report.json"),
        "source_contract_id": source_report.contract_id,
        "source_job_manifest_id": source_report.job_manifest_id,
        "task_source_report_id": AuthorityPreservingHardeningReport.model_validate_json(
            task_report_path.read_text(encoding="utf-8")
        ).report_id,
        "task_source_report_sha256": _sha256(task_report_path),
        "source_files": source_files,
        "implementation_source": AuditImplementationSource(
            sha256=_sha256(package_root / IMPLEMENTATION_SOURCE_PATH)
        ),
        "finalization_recovery": recovery_audit,
        "provider_call_count": source_report.provider_call_count,
        "provider_total_tokens": source_report.provider_total_tokens,
        "estimated_cost_usd": source_report.estimated_cost_usd,
        "repair_prompt_count": sum(item.repair_prompt_count for item in frozen_rows),
        "failed_observation_count": sum(item.failed_observation_count for item in frozen_rows),
        "full_program_lineage_count": sum(
            item.full_program_lineage_completed for item in frozen_rows
        ),
        "terminal_node_completion_count": sum(item.terminal_node_completed for item in frozen_rows),
        "postterminal_verification_count": sum(
            item.postterminal_verification_completed for item in frozen_rows
        ),
        "exact_terminal_target_acceptance_count": sum(
            item.exact_terminal_target_acceptance_count for item in frozen_rows
        ),
        "independently_valid_count": len(valid_rows),
        "valid_task_count": len({item.task_package_id for item in valid_rows}),
        "valid_mechanism_counts": dict(
            sorted(Counter(item.mechanism_id for item in valid_rows).items())
        ),
        "mechanism_summaries": summaries,
        "rollout_audits": frozen_rows,
        "model_validity_smoke_observed": bool(valid_rows),
    }
    provisional = AuthorityPreservingPostrunAuditReport.model_construct(
        report_id="pending", **values
    )
    report = AuthorityPreservingPostrunAuditReport(
        report_id=authority_preserving_postrun_report_id(provisional),
        **values,
    )
    _write_json_atomic(
        output_dir / "finalization_recovery_audit.json",
        recovery_audit.model_dump(mode="json"),
    )
    _write_json_atomic(
        output_dir / "rollout_authority_audits.json",
        [item.model_dump(mode="json") for item in frozen_rows],
    )
    _write_json_atomic(
        output_dir / "mechanism_authority_summaries.json",
        [item.model_dump(mode="json") for item in summaries],
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def finalization_recovery_audit_id(value: FinalizationRecoveryAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_finalization_recovery_audit:",
    )


def authority_preserving_rollout_audit_id(
    value: AuthorityPreservingRolloutAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_authority_preserving_rollout_audit:",
    )


def authority_preserving_mechanism_summary_id(
    value: AuthorityPreservingMechanismSummary,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_id"}),
        prefix="finance_v26_authority_preserving_mechanism_summary:",
    )


def authority_preserving_postrun_report_id(
    value: AuthorityPreservingPostrunAuditReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_authority_preserving_postrun_audit:",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the credential-free v26.67 authority-preserving post-run audit"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--interrupted-dir", type=Path, required=True)
    parser.add_argument("--recovery-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    report = build_authority_preserving_postrun_audit(
        run_id=args.run_id,
        interrupted_dir=args.interrupted_dir,
        recovery_dir=args.recovery_dir,
        task_source_dir=args.task_source_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "status": report.status,
                "next_permitted_stage": report.next_permitted_stage,
                "independently_valid_count": report.independently_valid_count,
                "api_call_count": report.api_call_count,
                "gpu_job_count": report.gpu_job_count,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
