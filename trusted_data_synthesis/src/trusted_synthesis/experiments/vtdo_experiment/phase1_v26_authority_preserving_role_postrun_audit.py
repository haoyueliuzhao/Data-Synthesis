from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import StaticModelAuthorityPathCatalog
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_role_runner import (  # noqa: E501
    AuthorityPreservingPreflightAudit,
    AuthorityPreservingRawIntegrityAudit,
    AuthorityPreservingRoleContract,
    AuthorityPreservingRoleJob,
    AuthorityPreservingRoleJobManifest,
    AuthorityPreservingRoleReport,
    AuthorityPreservingRolloutDiagnostic,
    EmpiricalRole,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    EmpiricalPilotRollout,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_capability_population import (  # noqa: E501
    FreshCapabilityPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.tools import AgentToolObservation

V26_ROLE_POSTRUN_AUDIT_VERSION = "finance_v26_authority_role_postrun_audit.v3"
V26_ROLE_ROLLOUT_REPLAY_VERSION = "finance_v26_authority_role_rollout_replay.v3"
V26_CROSS_ROLE_ISOLATION_VERSION = "finance_v26_cross_role_isolation.v1"
V26_CONDITION_ADHERENCE_VERSION = "finance_v26_condition_adherence.v1"

IMPLEMENTATION_SOURCE_PATHS = (
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_role_postrun_audit.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_role_runner.py"
    ),
)

_PROGRESS_ACTION_BINDING_FIELDS = frozenset(
    {
        "allowed_operators",
        "argument_contract",
        "expected_arguments",
        "operator",
        "operator_selection_rule",
        "parameters",
        "tool_id",
    }
)
_PRIVATE_PROMPT_FIELD_NAMES = frozenset(
    {
        "expected_operator_id",
        "mechanism_private_state",
        "semantic_source_id",
        "source_program_dag_hash",
        "source_program_node_id",
        "source_verifier_dag_hash",
        "target_program_evidence_ids",
        "verifier_binding_id",
    }
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
_STOP_GATE_REJECTION_CODES = frozenset(
    {
        "missing_observed_evidence",
        "missing_required_evidence_selection",
        "missing_required_calculation",
        "missing_required_verification",
    }
)
_MECHANISMS = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AuditImplementationSource(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class AuditArtifactFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class RoleRolloutReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    role: EmpiricalRole
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_design_job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    sampling_mode: str = Field(min_length=1)
    raw_artifact_sha256: str = Field(min_length=64, max_length=64)
    raw_byte_replay_passed: Literal[True] = True
    prompt_hash_replay_passed: Literal[True] = True
    recursive_noninterference_passed: Literal[True] = True
    condition_noninterference_passed: Literal[True] = True
    authority_contract_passed: Literal[True] = True
    terminal_target_passed: Literal[True] = True
    repair_prompt_action_neutral: Literal[True] = True
    failed_observation_action_neutral: Literal[True] = True
    independent_validity: bool
    path_assignment_present: bool
    failure_stage: str = Field(min_length=1)
    schema_version: str = V26_ROLE_ROLLOUT_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RoleRolloutReplayAudit:
        if self.path_assignment_present and not self.independent_validity:
            raise ValueError("post-run audit maps an invalid trajectory")
        if self.audit_id != role_rollout_replay_audit_id(self):
            raise ValueError("role rollout replay identity is invalid")
        return self


class ConditionAdherenceSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    requested_strategy: Literal["structured_direct", "search_then_structured", "search_then_open"]
    attempt_count: Literal[72] = 72
    observed_strategy_counts: dict[str, int]
    adherence_count: int = Field(ge=0, le=72)
    independently_valid_count: int = Field(ge=0, le=72)
    on_target_valid_count: int = Field(ge=0, le=72)
    diagnostic_only: Literal[True] = True
    creates_state_support: Literal[False] = False
    schema_version: str = V26_CONDITION_ADHERENCE_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> ConditionAdherenceSummary:
        if sum(self.observed_strategy_counts.values()) != self.attempt_count:
            raise ValueError("condition adherence denominator is incomplete")
        if self.summary_id != condition_adherence_summary_id(self):
            raise ValueError("condition adherence identity is invalid")
        return self


class CrossRoleIsolationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    capability_task_count: Literal[12] = 12
    reachability_task_count: Literal[12] = 12
    channel_overlap_counts: dict[str, int]
    provider_call_identity_overlap_count: Literal[0] = 0
    trajectory_identity_overlap_count: Literal[0] = 0
    source_design_job_identity_overlap_count: Literal[0] = 0
    execution_job_identity_overlap_count: Literal[0] = 0
    capability_results_used_for_reachability_selection: Literal[False] = False
    role_denominators_combined: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_CROSS_ROLE_ISOLATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CrossRoleIsolationAudit:
        expected = {
            "task_package_id",
            "semantic_source_id",
            "evidence_id",
            "evidence_version_id",
            "source_record_id",
        }
        if set(self.channel_overlap_counts) != expected or any(
            self.channel_overlap_counts.values()
        ):
            raise ValueError("cross-role empirical inputs are not disjoint")
        if self.audit_id != cross_role_isolation_audit_id(self):
            raise ValueError("cross-role isolation identity is invalid")
        return self


class RoleReplaySummary(FrozenModel):
    role: EmpiricalRole
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    expected_rollout_count: Literal[96, 360]
    observed_rollout_count: Literal[96, 360]
    preflight_contract_byte_identical: Literal[True] = True
    preflight_manifest_byte_identical: Literal[True] = True
    preflight_audit_byte_identical: Literal[True] = True
    contract_source_replay_pass_count: int = Field(ge=1)
    contract_source_file_count: int = Field(ge=1)
    implementation_source_replay_pass_count: Literal[13] = 13
    rollout_replay_pass_count: Literal[96, 360]
    raw_audit_reproduced: Literal[True] = True
    diagnostics_reproduced: Literal[True] = True
    report_reproduced: Literal[True] = True
    provider_call_count: int = Field(ge=1)
    provider_total_tokens: int = Field(ge=1)
    estimated_cost_usd: str = Field(min_length=1)
    terminal_counts: dict[str, int]
    failure_stage_counts: dict[str, int]
    mechanism_valid_counts: dict[str, int]
    mechanism_local_success_counts: dict[str, int]
    sampling_mode_valid_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_summary(self) -> RoleReplaySummary:
        if self.contract_source_replay_pass_count != self.contract_source_file_count:
            raise ValueError("post-run contract source replay is incomplete")
        if self.rollout_replay_pass_count != self.observed_rollout_count:
            raise ValueError("post-run rollout replay denominator is incomplete")
        if sum(self.terminal_counts.values()) != self.observed_rollout_count:
            raise ValueError("post-run terminal denominator is incomplete")
        return self


class AuthorityPreservingRolePostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    capability: RoleReplaySummary
    reachability: RoleReplaySummary
    cross_role_isolation: CrossRoleIsolationAudit
    condition_adherence_summaries: tuple[ConditionAdherenceSummary, ...] = Field(
        min_length=3, max_length=3
    )
    capability_independently_valid_count: Literal[4] = 4
    capability_mechanisms_with_valid_trajectory_count: Literal[1] = 1
    capability_all_mechanisms_have_valid_trajectory: Literal[False] = False
    reachability_independently_valid_count: Literal[21] = 21
    reachability_mapped_valid_count: Literal[21] = 21
    natural_state_hit_count: Literal[5] = 5
    natural_hit_state_count: int = Field(ge=1, le=5)
    conditioned_on_target_count: Literal[2] = 2
    conditioned_on_target_state_count: int = Field(ge=1, le=2)
    released_realization_count: Literal[2] = 2
    admitted_state_count: Literal[0] = 0
    admitted_task_count: Literal[0] = 0
    state_support_freeze_id: str = Field(min_length=1)
    state_support_freeze_status: Literal["blocked"] = "blocked"
    authority_preserving_instrument_retained: Literal[True] = True
    capability_distribution_measured: Literal[True] = True
    empirical_state_support_admitted: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    capability_confirmation_authorized: Literal[False] = False
    state_support_confirmation_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal["capability_task_or_reachability_condition_redesign_only"] = (
        "capability_task_or_reachability_condition_redesign_only"
    )
    immutable_artifact_files: tuple[AuditArtifactFile, ...] = Field(min_length=4, max_length=4)
    implementation_source_files: tuple[AuditImplementationSource, ...] = Field(
        min_length=2, max_length=2
    )
    api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    status: Literal["completed_negative_state_support"] = "completed_negative_state_support"
    schema_version: str = V26_ROLE_POSTRUN_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> AuthorityPreservingRolePostrunAuditReport:
        if tuple(item.requested_strategy for item in self.condition_adherence_summaries) != (
            "structured_direct",
            "search_then_structured",
            "search_then_open",
        ):
            raise ValueError("condition adherence summaries are not canonical")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("post-run audit implementation manifest is incomplete")
        if self.report_id != authority_preserving_role_postrun_audit_report_id(self):
            raise ValueError("authority-preserving role post-run report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 1


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"post-run audit immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _artifact_file(path: Path, output_dir: Path, count: int) -> AuditArtifactFile:
    return AuditArtifactFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=count,
    )


def _implementation_sources(package_root: Path) -> tuple[AuditImplementationSource, ...]:
    return tuple(
        AuditImplementationSource(relative_path=value, sha256=_sha256(package_root / value))
        for value in sorted(IMPLEMENTATION_SOURCE_PATHS)
    )


def _load_task_inputs(
    role: EmpiricalRole,
    task_source_dir: Path,
) -> tuple[tuple[OperationalTaskRecord, ...], tuple[StaticModelAuthorityPathCatalog, ...]]:
    if role == "capability_development":
        source = FreshCapabilityPopulationReport.model_validate_json(
            (task_source_dir / "report.json").read_text(encoding="utf-8")
        )
        records = tuple(source.task_records)
    else:
        source65 = AuthorityPreservingHardeningReport.model_validate_json(
            (task_source_dir / "report.json").read_text(encoding="utf-8")
        )
        records = tuple(
            item
            for item in source65.task_records
            if item.intended_use == "vtdo_multistate_candidate"
        )
    task_ids = {item.task_package.package_id for item in records}
    catalogs = tuple(
        item
        for item in (
            StaticModelAuthorityPathCatalog.model_validate(value)
            for value in json.loads(
                (task_source_dir / "static_model_authority_path_catalogs.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        if item.task_package_id in task_ids
    )
    if len(records) != 12 or len(catalogs) != 12:
        raise ValueError("post-run audit task source denominator changed")
    return records, catalogs


def _load_raw_payload(
    rollout: EmpiricalPilotRollout,
    run_dir: Path,
) -> dict[str, Any]:
    path = Path(rollout.raw_artifact_uri).resolve()
    try:
        path.relative_to(run_dir.resolve())
    except ValueError as error:
        raise ValueError("role raw Artifact is outside its frozen execution") from error
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != rollout.raw_artifact_sha256:
        raise ValueError("role raw Artifact hash replay failed")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("role raw Artifact is not a JSON object")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError("role raw Artifact is not canonical JSON")
    return cast(dict[str, Any], payload)


def _parse_observations(payload: Mapping[str, Any]) -> tuple[AgentToolObservation, ...]:
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
    try:
        value = json.loads(context_text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, Mapping) else None


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
        if context is None or context.get("failed_action_repair") is None:
            continue
        repair = context["failed_action_repair"]
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


def _semantic_progress_projection_passed(prompt: str) -> bool:
    context = _prompt_context(prompt)
    if context is None:
        return False
    progress = context.get("operation_execution_progress")
    if not isinstance(progress, Mapping):
        return False
    if (
        progress.get("action_binding_fields_exposed") is not False
        or "unresolved_variable_requirements" not in progress
        or "terminal_node_completed" not in progress
        or "all_steps_completed" not in progress
    ):
        return False
    nodes = list(progress.get("ready_nodes") or ())
    next_step = progress.get("next_required_step")
    if next_step is not None:
        nodes.append(next_step)
    return all(
        isinstance(item, Mapping) and not (_PROGRESS_ACTION_BINDING_FIELDS & set(item))
        for item in nodes
    )


def _premature_verification(
    record: OperationalTaskRecord,
    observations: tuple[AgentToolObservation, ...],
) -> bool:
    terminal_index = None
    task = record.task_package.task.public
    for index in range(1, len(observations) + 1):
        progress = public_operation_progress(task, observations[:index])
        if progress is not None and progress["terminal_node_completed"]:
            terminal_index = index - 1
            break
    return any(
        item.call.tool_id == "cross_check_evidence"
        and item.status == "succeeded"
        and item.result.get("verified") is True
        and (terminal_index is None or index < terminal_index)
        for index, item in enumerate(observations)
    )


def _is_stop_gate_rejection(value: Mapping[str, Any]) -> bool:
    reason = str(value.get("reason_code") or value.get("host_rejection_reason") or "")
    feedback = str(value.get("feedback") or value.get("host_feedback") or "")
    return reason in _STOP_GATE_REJECTION_CODES or any(
        marker in feedback
        for marker in (
            "stopped before public Program closure",
            "stopped before completing the public operation contract",
        )
    )


def _stop_decision_readiness(
    record: OperationalTaskRecord,
    payload: Mapping[str, Any],
) -> tuple[tuple[bool, bool, bool, bool], ...]:
    task = record.task_package.task.public
    trajectory = payload.get("trajectory")
    rows: list[tuple[bool, bool, bool, bool]] = []
    if isinstance(trajectory, Mapping):
        observed: list[AgentToolObservation] = []
        raw_steps = trajectory.get("steps")
        if not isinstance(raw_steps, (list, tuple)):
            raise ValueError("role trajectory has no replayable steps")
        for step in raw_steps:
            if not isinstance(step, Mapping):
                raise ValueError("role trajectory contains a malformed step")
            observation = step.get("observation")
            if isinstance(observation, Mapping) and "observation_id" in observation:
                observed.append(AgentToolObservation.model_validate(observation))
                continue
            if str(step.get("action") or "") != "answer":
                continue
            progress = public_operation_progress(task, tuple(observed))
            if progress is None:
                raise ValueError("role stop decision lost its public Operation contract")
            status = str(step.get("status") or "")
            if status not in {"succeeded", "failed"}:
                raise ValueError("role answer step has an invalid status")
            rejected = status == "failed"
            rows.append(
                (
                    status == "succeeded",
                    rejected,
                    bool(progress["stop_ready"]),
                    bool(
                        rejected
                        and isinstance(observation, Mapping)
                        and _is_stop_gate_rejection(observation)
                    ),
                )
            )
        return tuple(rows)

    failure = payload.get("failure_artifact")
    if not isinstance(failure, Mapping):
        return ()
    observations = tuple(
        AgentToolObservation.model_validate(item) for item in failure.get("observations") or ()
    )
    decisions = failure.get("decisions") or ()
    rejections = failure.get("stop_rejections") or ()
    rejection_by_index = {
        int(item["decision_index"]): item
        for item in rejections
        if isinstance(item, Mapping) and "decision_index" in item
    }
    observed = []
    observation_index = 0
    for decision_index, decision in enumerate(decisions):
        if not isinstance(decision, Mapping):
            raise ValueError("role failure Artifact contains a malformed decision")
        if decision.get("decision_type") == "tool_call":
            if observation_index >= len(observations):
                break
            observed.append(observations[observation_index])
            observation_index += 1
            continue
        if decision.get("decision_type") != "final_answer":
            raise ValueError("role failure Artifact contains an unknown decision")
        rejection = rejection_by_index.get(decision_index)
        if rejection is None:
            raise ValueError("role failure Artifact has an unclassified final decision")
        progress = public_operation_progress(task, tuple(observed))
        if progress is None:
            raise ValueError("role stop decision lost its public Operation contract")
        rows.append((False, True, bool(progress["stop_ready"]), _is_stop_gate_rejection(rejection)))
    return tuple(rows)


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
            raise ValueError("role terminal-target replay lost its public Operation contract")
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


def _independent_diagnostic(
    rollout: EmpiricalPilotRollout,
    job: AuthorityPreservingRoleJob,
    record: OperationalTaskRecord,
    run_dir: Path,
) -> AuthorityPreservingRolloutDiagnostic:
    payload = _load_raw_payload(rollout, run_dir)
    observations = _parse_observations(payload)
    progress = public_operation_progress(record.task_package.task.public, observations)
    if progress is None:
        raise ValueError("role rollout lost its public Operation contract")
    prompts = tuple(str(item) for item in payload["actual_model_request_prompts"])
    initial = prompts[0] if prompts else ""
    decision_prompts = tuple(item for item in prompts if '"operation_execution_progress"' in item)
    repair_count, repair_exposure = _repair_prompt_counts(prompts)
    failed_count, failed_exposure = _failed_observation_counts(observations)
    stop_rows = _stop_decision_readiness(record, payload)
    package = record.task_package
    private_values = (
        *record.target_program_evidence_ids,
        package.semantic_source.semantic_source_id,
        package.verifier_binding.binding_id,
        package.verifier_binding.source_program_dag_hash,
        package.verifier_binding.source_verifier_dag_hash,
    )
    independent_validity = bool(rollout.verification and rollout.verification.valid)
    target_acceptance_count = _terminal_target_acceptance_count(record, observations)
    values: dict[str, Any] = {
        "source_design_job_id": job.source_design_job_id,
        "rollout_id": rollout.rollout_id,
        "job_id": rollout.job_id,
        "task_package_id": rollout.task_package_id,
        "mechanism_id": rollout.mechanism_id,
        "sampling_mode": rollout.sampling_mode,
        "replicate_index": rollout.replicate_index,
        "terminal_category": rollout.terminal_category,
        "exact_requested_model": rollout.exact_requested_model,
        "fallback_used": rollout.fallback_used,
        "required_node_count": len(package.stop_readiness_contract.required_node_ids),
        "completed_node_count": len(progress["completed_node_ids"]),
        "full_program_lineage_completed": bool(progress["all_steps_completed"]),
        "terminal_node_completed": bool(progress["terminal_node_completed"]),
        "postterminal_verification_completed": target_acceptance_count > 0,
        "stop_ready": bool(progress["stop_ready"]),
        "premature_verification_observed": _premature_verification(record, observations),
        "postcompletion_violation": bool(progress["postcompletion_violation"]),
        "final_answer_before_stop_ready_rejected": any(
            rejected and not stop_ready for _, rejected, stop_ready, _ in stop_rows
        ),
        "stop_ready_false_positive": any(
            accepted and not stop_ready for accepted, _, stop_ready, _ in stop_rows
        ),
        "stop_ready_false_negative": any(
            rejected and stop_ready for _, _, stop_ready, rejected in stop_rows
        ),
        "independent_validity": independent_validity,
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
        "repair_prompt_count": repair_count,
        "action_bearing_repair_prompt_count": repair_exposure,
        "failed_observation_count": failed_count,
        "action_bearing_failed_observation_count": failed_exposure,
        "repair_prompts_action_neutral": repair_exposure == 0,
        "failed_observations_action_neutral": failed_exposure == 0,
        "condition_noninterference_passed": rollout.condition_noninterference_passed,
        "state_mapping_eligible": independent_validity
        and rollout.sampling_mode != "capability_unconditional",
        "path_assignment_present": rollout.path_assignment is not None,
    }
    provisional = AuthorityPreservingRolloutDiagnostic.model_construct(
        diagnostic_id="pending", **values
    )
    diagnostic_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_authority_preserving_role_diagnostic:",
    )
    return AuthorityPreservingRolloutDiagnostic(diagnostic_id=diagnostic_id, **values)


def _independent_raw_audit(
    *,
    role: EmpiricalRole,
    run_dir: Path,
    rollouts: Sequence[EmpiricalPilotRollout],
    diagnostics: Sequence[AuthorityPreservingRolloutDiagnostic],
    manifest: AuthorityPreservingRoleJobManifest,
) -> AuthorityPreservingRawIntegrityAudit:
    job_by_id = {item.job_id: item for item in manifest.jobs}
    diagnostic_by_job = {item.job_id: item for item in diagnostics}
    passes: Counter[str] = Counter()
    failures: list[str] = []
    provider_ids: list[str] = []
    for rollout in rollouts:
        try:
            payload = _load_raw_payload(rollout, run_dir)
            passes["byte"] += 1
            job = job_by_id[rollout.job_id]
            diagnostic = diagnostic_by_job[rollout.job_id]
            raw_job = payload["job"]
            if not isinstance(raw_job, Mapping) or not (
                payload["contract_id"] == rollout.contract_id
                and raw_job["job_id"] == rollout.job_id
                and raw_job["source_design_job_id"] == job.source_design_job_id
                and payload["task_package_id"] == rollout.task_package_id
                and payload["terminal_category"] == rollout.terminal_category
                and tuple(payload["provider_call_ids"]) == rollout.provider_call_ids
            ):
                raise ValueError("role raw identity mismatch")
            passes["identity"] += 1
            prompts = tuple(str(item) for item in payload["actual_model_request_prompts"])
            hashes = tuple(hashlib.sha256(item.encode()).hexdigest() for item in prompts)
            if hashes != rollout.actual_prompt_hashes:
                raise ValueError("role raw Prompt hash mismatch")
            passes["prompt"] += 1
            if payload["recursive_noninterference_passed"] is not True or not (
                rollout.recursive_noninterference_passed
            ):
                raise ValueError("role recursive noninterference mismatch")
            passes["recursive"] += 1
            if payload["condition_noninterference_passed"] is not True or not (
                diagnostic.condition_noninterference_passed
            ):
                raise ValueError("role condition noninterference mismatch")
            passes["condition"] += 1
            if not (
                diagnostic.authority_contract_in_initial_prompt
                and diagnostic.initial_prompt_private_identity_free
            ):
                raise ValueError("role authority contract audit failed")
            passes["authority"] += 1
            if not diagnostic.terminal_target_in_initial_prompt:
                raise ValueError("role terminal target audit failed")
            passes["target"] += 1
            if not (
                diagnostic.repair_prompts_action_neutral
                and diagnostic.failed_observations_action_neutral
            ):
                raise ValueError("role repair-neutrality audit failed")
            passes["repair"] += 1
            provider_ids.extend(rollout.provider_call_ids)
        except Exception:
            failures.append(rollout.raw_artifact_uri)
    duplicates = tuple(sorted(key for key, count in Counter(provider_ids).items() if count > 1))
    expected = 96 if role == "capability_development" else 360
    count_values = tuple(
        passes[key]
        for key in (
            "byte",
            "identity",
            "prompt",
            "recursive",
            "condition",
            "authority",
            "target",
            "repair",
        )
    )
    complete = len(rollouts) == expected and all(item == expected for item in count_values)
    partial = all(item == len(rollouts) for item in count_values)
    values: dict[str, Any] = {
        "role": role,
        "expected_rollout_count": expected,
        "observed_rollout_count": len(rollouts),
        "byte_hash_pass_count": passes["byte"],
        "identity_pass_count": passes["identity"],
        "prompt_hash_pass_count": passes["prompt"],
        "recursive_noninterference_pass_count": passes["recursive"],
        "condition_noninterference_pass_count": passes["condition"],
        "authority_contract_pass_count": passes["authority"],
        "terminal_target_pass_count": passes["target"],
        "repair_neutrality_pass_count": passes["repair"],
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
    provisional = AuthorityPreservingRawIntegrityAudit.model_construct(audit_id="pending", **values)
    audit_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_authority_preserving_role_raw_audit:",
    )
    return AuthorityPreservingRawIntegrityAudit(audit_id=audit_id, **values)


def _failure_stage(item: EmpiricalPilotRollout) -> str:
    if item.terminal_category == "model_valid_trajectory":
        return "valid"
    if item.verification is not None:
        return item.verification.earliest_failure_stage or "independent_verification"
    if item.terminal_category == "model_invalid_trajectory":
        return "model_contract"
    return item.terminal_category


def _wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 1.0
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    lower = 0.0 if successes == 0 else max(0.0, center - radius)
    upper = 1.0 if successes == total else min(1.0, center + radius)
    return lower, upper


def _independent_capability_summaries(
    rollouts: Sequence[EmpiricalPilotRollout],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    by_task: dict[str, list[EmpiricalPilotRollout]] = {}
    for rollout in rollouts:
        if rollout.sampling_mode != "capability_unconditional":
            continue
        by_task.setdefault(rollout.task_package_id, []).append(rollout)
    task_summaries: list[dict[str, Any]] = []
    for task_id, rows in sorted(by_task.items()):
        if len(rows) != 8:
            raise ValueError("independent Capability replay lost a task denominator")
        runtime_eligible = sum(
            item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
            for item in rows
        )
        evaluable = sum(item.mechanism_estimand.evaluated for item in rows)
        mechanism_success = sum(item.mechanism_estimand.success for item in rows)
        valid = sum(item.terminal_category == "model_valid_trajectory" for item in rows)
        mechanism_rate = mechanism_success / len(rows)
        valid_rate = valid / len(rows)
        mechanism_interval = _wilson_interval(mechanism_success, len(rows))
        valid_interval = _wilson_interval(valid, len(rows))
        task_summaries.append(
            {
                "task_package_id": task_id,
                "mechanism_id": rows[0].mechanism_id,
                "attempted_count": 8,
                "runtime_eligible_count": runtime_eligible,
                "model_contract_failure_count": sum(
                    _failure_stage(item) == "model_contract" for item in rows
                ),
                "runtime_or_instrument_failure_count": len(rows) - runtime_eligible,
                "mechanism_evaluable_count": evaluable,
                "mechanism_success_count": mechanism_success,
                "independent_valid_count": valid,
                "mechanism_success_rate": mechanism_rate,
                "valid_rate": valid_rate,
                "valid_given_mechanism_success_rate": (
                    valid / mechanism_success if mechanism_success else None
                ),
                "mechanism_wilson_lcb95": mechanism_interval[0],
                "mechanism_wilson_ucb95": mechanism_interval[1],
                "valid_wilson_lcb95": valid_interval[0],
                "valid_wilson_ucb95": valid_interval[1],
                "boundary_response": 0.125 <= mechanism_rate <= 0.875,
                "earliest_failure_stage_counts": dict(
                    sorted(Counter(_failure_stage(item) for item in rows).items())
                ),
            }
        )
    if len(task_summaries) != 12:
        raise ValueError("independent Capability replay lacks twelve task summaries")
    mechanism_summaries: list[dict[str, Any]] = []
    for mechanism in _MECHANISMS:
        mechanism_rows = tuple(item for item in task_summaries if item["mechanism_id"] == mechanism)
        if len(mechanism_rows) != 3:
            raise ValueError("independent Capability replay lost mechanism balance")
        mechanism_rates = tuple(float(item["mechanism_success_rate"]) for item in mechanism_rows)
        valid_rates = tuple(float(item["valid_rate"]) for item in mechanism_rows)
        mechanism_summaries.append(
            {
                "mechanism_id": mechanism,
                "task_count": 3,
                "rollout_count": 24,
                "mechanism_success_count": sum(
                    int(item["mechanism_success_count"]) for item in mechanism_rows
                ),
                "independent_valid_count": sum(
                    int(item["independent_valid_count"]) for item in mechanism_rows
                ),
                "boundary_task_count": sum(
                    bool(item["boundary_response"]) for item in mechanism_rows
                ),
                "task_mechanism_success_range": [min(mechanism_rates), max(mechanism_rates)],
                "task_validity_range": [min(valid_rates), max(valid_rates)],
            }
        )
    return tuple(task_summaries), tuple(mechanism_summaries)


def _independent_state_summaries(
    rollouts: Sequence[EmpiricalPilotRollout],
    catalogs: Sequence[StaticModelAuthorityPathCatalog],
) -> tuple[dict[str, Any], ...]:
    natural = tuple(item for item in rollouts if item.sampling_mode == "reachability_unconditional")
    conditioned = tuple(
        item for item in rollouts if item.sampling_mode == "reachability_conditioned"
    )
    output = []
    for catalog in sorted(catalogs, key=lambda item: item.task_package_id):
        natural_rows = tuple(
            item for item in natural if item.task_package_id == catalog.task_package_id
        )
        if len(natural_rows) != 12:
            raise ValueError("independent Reachability replay lost a natural denominator")
        for path in sorted(catalog.paths, key=lambda item: item.path_strategy_id):
            rows = sorted(
                (
                    item
                    for item in conditioned
                    if item.task_package_id == catalog.task_package_id
                    and item.requested_static_path_id == path.path_id
                ),
                key=lambda item: item.replicate_index,
            )
            if len(rows) != 6:
                raise ValueError("independent Reachability replay lost a conditioned denominator")
            natural_valid = sum(
                item.terminal_category == "model_valid_trajectory" for item in natural_rows
            )
            natural_hits = sum(
                item.path_assignment is not None
                and item.path_assignment.quotient_state_id == path.quotient_state_id
                for item in natural_rows
            )
            valid = sum(item.terminal_category == "model_valid_trajectory" for item in rows)
            on_target = tuple(
                item
                for item in rows
                if item.path_assignment is not None
                and item.path_assignment.quotient_state_id == path.quotient_state_id
            )
            off_target = sum(
                item.path_assignment is not None
                and item.path_assignment.quotient_state_id != path.quotient_state_id
                for item in rows
            )
            unmapped = sum(
                item.terminal_category == "model_valid_trajectory" and item.path_assignment is None
                for item in rows
            )
            seen_content: set[str] = set()
            seen_traces: set[str] = set()
            released: list[EmpiricalPilotRollout] = []
            duplicate_content = duplicate_trace = 0
            for item in on_target:
                content = item.trajectory_content_hash or ""
                trace = item.decision_trace_hash or ""
                content_duplicate = not content or content in seen_content
                trace_duplicate = not trace or trace in seen_traces
                duplicate_content += int(content_duplicate)
                duplicate_trace += int(trace_duplicate)
                if content_duplicate or trace_duplicate:
                    continue
                seen_content.add(content)
                seen_traces.add(trace)
                released.append(item)
            rate = len(on_target) / len(rows)
            lower, upper = _wilson_interval(len(on_target), len(rows))
            estimated_attempts = 3 / rate if rate > 0 else None
            checks = {
                "natural_hit_missing": natural_hits >= 1,
                "conditioned_acceptance_lcb_not_positive": lower > 0.0,
                "three_independent_realizations_missing": len(released) >= 3,
                "stable_remapping_failed": all(
                    item.path_assignment is not None
                    and item.path_assignment.path_strategy == path.path_strategy_id
                    and item.path_assignment.quotient_state_id == path.quotient_state_id
                    for item in released
                ),
                "non_model_realization_detected": all(item.model_generated for item in released),
                "materialization_budget_exceeded": bool(
                    estimated_attempts is not None and estimated_attempts <= 60.0
                ),
            }
            blockers = tuple(sorted(key for key, passed in checks.items() if not passed))
            output.append(
                {
                    "task_package_id": catalog.task_package_id,
                    "static_path_id": path.path_id,
                    "path_strategy": path.path_strategy_id,
                    "quotient_state_id": path.quotient_state_id,
                    "natural_attempted_count": 12,
                    "natural_valid_count": natural_valid,
                    "natural_on_state_hit_count": natural_hits,
                    "requested_count": 6,
                    "conditioned_attempted_count": 6,
                    "conditioned_valid_count": valid,
                    "conditioned_on_target_count": len(on_target),
                    "conditioned_off_target_count": off_target,
                    "conditioned_valid_unmapped_count": unmapped,
                    "duplicate_content_count": duplicate_content,
                    "duplicate_decision_trace_count": duplicate_trace,
                    "released_count": len(released),
                    "released_rollout_ids": [item.rollout_id for item in released],
                    "conditioned_acceptance_rate": rate,
                    "conditioned_acceptance_lcb95": lower,
                    "conditioned_acceptance_ucb95": upper,
                    "estimated_attempts_for_three_releases": estimated_attempts,
                    "provider_call_count": sum(item.provider_call_count for item in rows),
                    "provider_total_tokens": sum(item.provider_total_tokens for item in rows),
                    "estimated_cost_usd": str(sum(float(item.estimated_cost_usd) for item in rows)),
                    "natural_hit_passed": checks["natural_hit_missing"],
                    "conditioned_lcb_passed": checks["conditioned_acceptance_lcb_not_positive"],
                    "independent_realization_yield_passed": checks[
                        "three_independent_realizations_missing"
                    ],
                    "stable_remapping_passed": checks["stable_remapping_failed"],
                    "model_generated_only_passed": checks["non_model_realization_detected"],
                    "budget_passed": checks["materialization_budget_exceeded"],
                    "admitted": not blockers,
                    "blockers": list(blockers),
                }
            )
    if len(output) != 36:
        raise ValueError("independent Reachability replay lacks 36 state summaries")
    return tuple(output)


def _validate_report_aggregates(
    *,
    contract: AuthorityPreservingRoleContract,
    manifest: AuthorityPreservingRoleJobManifest,
    preflight: AuthorityPreservingPreflightAudit,
    report: AuthorityPreservingRoleReport,
    raw_audit: AuthorityPreservingRawIntegrityAudit,
    diagnostics: Sequence[AuthorityPreservingRolloutDiagnostic],
    rollouts: Sequence[EmpiricalPilotRollout],
    records: Sequence[OperationalTaskRecord],
    catalogs: Sequence[StaticModelAuthorityPathCatalog],
) -> None:
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in rollouts).items()))
    sampling_counts = dict(sorted(Counter(item.sampling_mode for item in rollouts).items()))
    total_cost = sum((Decimal(item.estimated_cost_usd) for item in rollouts), Decimal("0"))
    resource_ok = total_cost <= Decimal(str(contract.maximum_total_estimated_cost_usd))
    scalar_expectations = {
        "run_id": contract.run_id,
        "role": contract.role,
        "contract_id": contract.contract_id,
        "job_manifest_id": manifest.manifest_id,
        "completed_rollout_count": len(rollouts),
        "sampling_mode_counts": sampling_counts,
        "terminal_counts": terminal_counts,
        "provider_call_count": sum(item.provider_call_count for item in rollouts),
        "provider_total_tokens": sum(item.provider_total_tokens for item in rollouts),
        "estimated_cost_usd": str(total_cost),
        "model_outcome_count": sum(
            item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
            for item in diagnostics
        ),
        "runtime_failure_count": terminal_counts.get("runtime_failure", 0),
        "instrument_failure_count": terminal_counts.get("instrument_failure", 0),
        "independently_valid_trajectory_count": sum(
            item.independent_validity for item in diagnostics
        ),
        "mapped_valid_trajectory_count": sum(item.path_assignment_present for item in diagnostics),
        "full_program_lineage_count": sum(
            item.full_program_lineage_completed for item in diagnostics
        ),
        "terminal_node_completion_count": sum(item.terminal_node_completed for item in diagnostics),
        "postterminal_verification_count": sum(
            item.postterminal_verification_completed for item in diagnostics
        ),
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
        "resource_budget_passed": resource_ok,
        "instrument_ready": True,
        "status": "passed",
        "next_permitted_stage": (
            "capability_postrun_read_only_audit_only"
            if contract.role == "capability_development"
            else "reachability_postrun_read_only_audit_only"
        ),
        "model_execution_authorized": False,
        "capability_development_complete": contract.role == "capability_development",
        "state_reachability_complete": contract.role == "state_reachability",
    }
    report_values = report.model_dump(mode="json")
    for key, expected in scalar_expectations.items():
        if report_values[key] != expected:
            raise ValueError(f"{contract.role} report aggregate mismatch: {key}")
    if report.preflight_audit != preflight or report.raw_integrity_audit != raw_audit:
        raise ValueError(f"{contract.role} report embeds a foreign preflight or raw audit")
    if tuple(report.diagnostics) != tuple(diagnostics):
        raise ValueError(f"{contract.role} report embeds different diagnostics")
    if not all(item.exact_requested_model and not item.fallback_used for item in rollouts):
        raise ValueError(f"{contract.role} exact-model execution failed")
    if not all(
        item.public_contract_in_initial_prompt
        and item.public_progress_projection_passed
        and item.initial_prompt_private_identity_free
        and item.authority_contract_in_initial_prompt
        and item.terminal_target_in_initial_prompt
        and item.repair_prompts_action_neutral
        and item.failed_observations_action_neutral
        and item.condition_noninterference_passed
        and not item.stop_ready_false_positive
        and not item.stop_ready_false_negative
        for item in diagnostics
    ):
        raise ValueError(f"{contract.role} independent instrument conjunction failed")

    if contract.role == "capability_development":
        tasks, mechanisms = _independent_capability_summaries(rollouts)
        observed_tasks = tuple(
            item.model_dump(mode="json") for item in report.capability_task_summaries
        )
        observed_mechanisms = tuple(
            item.model_dump(mode="json") for item in report.capability_mechanism_summaries
        )
        if tasks != observed_tasks or mechanisms != observed_mechanisms:
            raise ValueError("Capability task or mechanism aggregation does not replay")
        if report.state_reachability_summaries or report.state_support_freeze is not None:
            raise ValueError("Capability report contains Reachability outputs")
        return

    states = _independent_state_summaries(rollouts, catalogs)
    observed_states = tuple(
        item.model_dump(mode="json") for item in report.state_reachability_summaries
    )
    if states != observed_states:
        raise ValueError("Reachability state aggregation does not replay")
    if report.capability_task_summaries or report.capability_mechanism_summaries:
        raise ValueError("Reachability report contains Capability outputs")
    freeze = report.state_support_freeze
    if freeze is None:
        raise ValueError("Reachability report lacks its State Support Freeze")
    mechanism_by_task = {item.task_package.package_id: item.mechanism_id for item in records}
    expected_tasks: list[dict[str, Any]] = []
    for task_id, mechanism in sorted(mechanism_by_task.items()):
        rows = tuple(item for item in states if item["task_package_id"] == task_id)
        admitted = sorted(str(item["quotient_state_id"]) for item in rows if item["admitted"])
        expected_tasks.append(
            {
                "task_package_id": task_id,
                "mechanism_id": mechanism,
                "registered_state_count": 3,
                "admitted_state_count": len(admitted),
                "admitted_state_ids": admitted,
                "all_three_states_admitted": len(admitted) == 3,
            }
        )
    if tuple(item.model_dump(mode="json") for item in freeze.task_summaries) != tuple(
        expected_tasks
    ):
        raise ValueError("Reachability task State Support Freeze does not replay")
    admitted_task_count = sum(item["all_three_states_admitted"] for item in expected_tasks)
    if (
        freeze.admitted_task_count != admitted_task_count
        or freeze.global_support_admitted != (admitted_task_count == 12)
        or freeze.compiler_witness_count != 0
        or freeze.status != "blocked"
        or freeze.next_transition != "capability_task_or_reachability_condition_redesign_only"
    ):
        raise ValueError("Reachability global State Support Freeze does not replay")


def _rollout_audits(
    *,
    role: EmpiricalRole,
    run_dir: Path,
    rollouts: Sequence[EmpiricalPilotRollout],
    diagnostics: Sequence[AuthorityPreservingRolloutDiagnostic],
    manifest: AuthorityPreservingRoleJobManifest,
) -> tuple[RoleRolloutReplayAudit, ...]:
    diagnostic_by_job = {item.job_id: item for item in diagnostics}
    job_by_id = {item.job_id: item for item in manifest.jobs}
    output = []
    for rollout in rollouts:
        diagnostic = diagnostic_by_job[rollout.job_id]
        job = job_by_id[rollout.job_id]
        _load_raw_payload(rollout, run_dir)
        values: dict[str, Any] = {
            "role": role,
            "rollout_id": rollout.rollout_id,
            "job_id": rollout.job_id,
            "source_design_job_id": job.source_design_job_id,
            "task_package_id": rollout.task_package_id,
            "mechanism_id": rollout.mechanism_id,
            "sampling_mode": rollout.sampling_mode,
            "raw_artifact_sha256": rollout.raw_artifact_sha256,
            "recursive_noninterference_passed": rollout.recursive_noninterference_passed,
            "condition_noninterference_passed": diagnostic.condition_noninterference_passed,
            "authority_contract_passed": diagnostic.authority_contract_in_initial_prompt
            and diagnostic.initial_prompt_private_identity_free,
            "terminal_target_passed": diagnostic.terminal_target_in_initial_prompt,
            "repair_prompt_action_neutral": diagnostic.repair_prompts_action_neutral,
            "failed_observation_action_neutral": diagnostic.failed_observations_action_neutral,
            "independent_validity": diagnostic.independent_validity,
            "path_assignment_present": diagnostic.path_assignment_present,
            "failure_stage": _failure_stage(rollout),
        }
        provisional = RoleRolloutReplayAudit.model_construct(audit_id="pending", **values)
        output.append(
            RoleRolloutReplayAudit(
                audit_id=role_rollout_replay_audit_id(provisional),
                **values,
            )
        )
    return tuple(sorted(output, key=lambda item: item.audit_id))


def _audit_run(
    *,
    role: EmpiricalRole,
    run_dir: Path,
    preflight_dir: Path,
    task_source_dir: Path,
    package_root: Path,
) -> tuple[
    RoleReplaySummary,
    tuple[RoleRolloutReplayAudit, ...],
    AuthorityPreservingRoleReport,
    AuthorityPreservingRoleJobManifest,
    tuple[EmpiricalPilotRollout, ...],
    tuple[OperationalTaskRecord, ...],
]:
    contract = AuthorityPreservingRoleContract.model_validate_json(
        (run_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = AuthorityPreservingRoleJobManifest.model_validate_json(
        (run_dir / "job_manifest.json").read_text(encoding="utf-8")
    )
    preflight = AuthorityPreservingPreflightAudit.model_validate_json(
        (run_dir / "static_preflight_audit.json").read_text(encoding="utf-8")
    )
    report = AuthorityPreservingRoleReport.model_validate_json(
        (run_dir / "report.json").read_text(encoding="utf-8")
    )
    raw_audit = AuthorityPreservingRawIntegrityAudit.model_validate_json(
        (run_dir / "raw_integrity_audit.json").read_text(encoding="utf-8")
    )
    rollouts = tuple(
        EmpiricalPilotRollout.model_validate(item)
        for item in json.loads((run_dir / "empirical_rollouts.json").read_text(encoding="utf-8"))
    )
    diagnostics = tuple(
        AuthorityPreservingRolloutDiagnostic.model_validate(item)
        for item in json.loads((run_dir / "rollout_diagnostics.json").read_text(encoding="utf-8"))
    )
    records, catalogs = _load_task_inputs(role, task_source_dir)
    record_by_id = {item.record_id: item for item in records}
    job_by_id = {item.job_id: item for item in manifest.jobs}
    recomputed_diagnostics = tuple(
        _independent_diagnostic(
            item,
            job_by_id[item.job_id],
            record_by_id[item.task_record_id],
            run_dir,
        )
        for item in rollouts
    )
    recomputed_raw = _independent_raw_audit(
        role=role,
        run_dir=run_dir,
        rollouts=rollouts,
        diagnostics=recomputed_diagnostics,
        manifest=manifest,
    )
    if recomputed_diagnostics != diagnostics:
        raise ValueError(f"{role} rollout diagnostics do not independently replay")
    if recomputed_raw != raw_audit:
        raise ValueError(f"{role} raw audit does not independently replay")
    _validate_report_aggregates(
        contract=contract,
        manifest=manifest,
        preflight=preflight,
        report=report,
        raw_audit=recomputed_raw,
        diagnostics=recomputed_diagnostics,
        rollouts=rollouts,
        records=records,
        catalogs=catalogs,
    )
    for relative in (
        "execution_contract.json",
        "job_manifest.json",
        "static_preflight_audit.json",
    ):
        if (run_dir / relative).read_bytes() != (preflight_dir / relative).read_bytes():
            raise ValueError(f"{role} execution differs from frozen preflight: {relative}")
    source_pass = sum(
        (package_root / item.relative_path).is_file()
        and _sha256(package_root / item.relative_path) == item.sha256
        and _record_count(package_root / item.relative_path) == item.record_count
        for item in contract.source_artifact_files
    )
    implementation_pass = sum(
        (package_root / item.relative_path).is_file()
        and _sha256(package_root / item.relative_path) == item.sha256
        for item in contract.implementation_source_files
    )
    if source_pass != len(contract.source_artifact_files) or implementation_pass != 13:
        raise ValueError(f"{role} source or implementation bytes changed")
    replay_audits = _rollout_audits(
        role=role,
        run_dir=run_dir,
        rollouts=rollouts,
        diagnostics=diagnostics,
        manifest=manifest,
    )
    values: dict[str, Any] = {
        "role": role,
        "source_report_id": report.report_id,
        "source_report_sha256": _sha256(run_dir / "report.json"),
        "expected_rollout_count": contract.expected_job_count,
        "observed_rollout_count": len(rollouts),
        "contract_source_replay_pass_count": source_pass,
        "contract_source_file_count": len(contract.source_artifact_files),
        "rollout_replay_pass_count": len(replay_audits),
        "provider_call_count": report.provider_call_count,
        "provider_total_tokens": report.provider_total_tokens,
        "estimated_cost_usd": report.estimated_cost_usd,
        "terminal_counts": report.terminal_counts,
        "failure_stage_counts": dict(
            sorted(Counter(_failure_stage(item) for item in rollouts).items())
        ),
        "mechanism_valid_counts": {
            mechanism: sum(
                item.mechanism_id == mechanism
                and item.terminal_category == "model_valid_trajectory"
                for item in rollouts
            )
            for mechanism in (
                "context_conditioned_action",
                "semantic_reconciliation",
                "failure_recovery",
                "state_dependent_stopping",
            )
        },
        "mechanism_local_success_counts": {
            mechanism: sum(
                item.mechanism_id == mechanism and item.mechanism_estimand.success
                for item in rollouts
            )
            for mechanism in (
                "context_conditioned_action",
                "semantic_reconciliation",
                "failure_recovery",
                "state_dependent_stopping",
            )
        },
        "sampling_mode_valid_counts": dict(
            sorted(
                Counter(
                    item.sampling_mode
                    for item in rollouts
                    if item.terminal_category == "model_valid_trajectory"
                ).items()
            )
        ),
    }
    return (
        RoleReplaySummary(**values),
        replay_audits,
        report,
        manifest,
        rollouts,
        records,
    )


def _observed_acquisition_strategy(rollout: EmpiricalPilotRollout, run_dir: Path) -> str:
    observations = _parse_observations(_load_raw_payload(rollout, run_dir))
    successful = set()
    for item in observations:
        if item.call.tool_id == "calculator":
            break
        if item.status == "succeeded":
            successful.add(item.call.tool_id)
    if "open_document" in successful:
        return "search_then_open"
    if "search_archive" in successful:
        return "search_then_structured"
    if "query_structured_fact" in successful:
        return "structured_direct"
    return "no_successful_precalculation_acquisition"


def _condition_adherence(
    manifest: AuthorityPreservingRoleJobManifest,
    rollouts: Sequence[EmpiricalPilotRollout],
    run_dir: Path,
) -> tuple[ConditionAdherenceSummary, ...]:
    job_by_id = {item.job_id: item for item in manifest.jobs}
    by_strategy: dict[str, list[EmpiricalPilotRollout]] = {
        "structured_direct": [],
        "search_then_structured": [],
        "search_then_open": [],
    }
    for rollout in rollouts:
        job = job_by_id[rollout.job_id]
        if job.requested_path_strategy is not None:
            by_strategy[job.requested_path_strategy].append(rollout)
    output = []
    for strategy in ("structured_direct", "search_then_structured", "search_then_open"):
        rows = by_strategy[strategy]
        observed = Counter(_observed_acquisition_strategy(item, run_dir) for item in rows)
        values: dict[str, Any] = {
            "requested_strategy": strategy,
            "attempt_count": len(rows),
            "observed_strategy_counts": dict(sorted(observed.items())),
            "adherence_count": observed[strategy],
            "independently_valid_count": sum(
                item.terminal_category == "model_valid_trajectory" for item in rows
            ),
            "on_target_valid_count": sum(
                item.path_assignment is not None
                and item.path_assignment.quotient_state_id == item.requested_quotient_state_id
                for item in rows
            ),
        }
        provisional = ConditionAdherenceSummary.model_construct(summary_id="pending", **values)
        output.append(
            ConditionAdherenceSummary(
                summary_id=condition_adherence_summary_id(provisional),
                **values,
            )
        )
    return tuple(output)


def _record_channels(records: Sequence[OperationalTaskRecord]) -> dict[str, set[str]]:
    return {
        "task_package_id": {item.task_package.package_id for item in records},
        "semantic_source_id": {
            item.task_package.semantic_source.semantic_source_id for item in records
        },
        "evidence_id": {
            evidence.evidence_id for item in records for evidence in item.public_corpus.evidence
        },
        "evidence_version_id": {
            evidence.evidence_version_id
            for item in records
            for evidence in item.public_corpus.evidence
        },
        "source_record_id": {
            evidence.provenance.source_record_id
            for item in records
            for evidence in item.public_corpus.evidence
        },
    }


def _cross_role_isolation(
    *,
    capability_records: Sequence[OperationalTaskRecord],
    reachability_records: Sequence[OperationalTaskRecord],
    capability_manifest: AuthorityPreservingRoleJobManifest,
    reachability_manifest: AuthorityPreservingRoleJobManifest,
    capability_rollouts: Sequence[EmpiricalPilotRollout],
    reachability_rollouts: Sequence[EmpiricalPilotRollout],
) -> CrossRoleIsolationAudit:
    capability = _record_channels(capability_records)
    reachability = _record_channels(reachability_records)
    overlaps = {channel: len(capability[channel] & reachability[channel]) for channel in capability}
    provider_overlap = {
        value for item in capability_rollouts for value in item.provider_call_ids
    } & {value for item in reachability_rollouts for value in item.provider_call_ids}
    trajectory_overlap = {
        item.trajectory_id for item in capability_rollouts if item.trajectory_id is not None
    } & {item.trajectory_id for item in reachability_rollouts if item.trajectory_id is not None}
    source_design_overlap = {item.source_design_job_id for item in capability_manifest.jobs} & {
        item.source_design_job_id for item in reachability_manifest.jobs
    }
    job_overlap = {item.job_id for item in capability_manifest.jobs} & {
        item.job_id for item in reachability_manifest.jobs
    }
    values: dict[str, Any] = {
        "channel_overlap_counts": dict(sorted(overlaps.items())),
        "provider_call_identity_overlap_count": len(provider_overlap),
        "trajectory_identity_overlap_count": len(trajectory_overlap),
        "source_design_job_identity_overlap_count": len(source_design_overlap),
        "execution_job_identity_overlap_count": len(job_overlap),
    }
    provisional = CrossRoleIsolationAudit.model_construct(audit_id="pending", **values)
    return CrossRoleIsolationAudit(
        audit_id=cross_role_isolation_audit_id(provisional),
        **values,
    )


def build_authority_preserving_role_postrun_audit(
    *,
    run_id: str,
    capability_run_dir: Path,
    capability_preflight_dir: Path,
    capability_task_source_dir: Path,
    reachability_run_dir: Path,
    reachability_preflight_dir: Path,
    reachability_task_source_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> AuthorityPreservingRolePostrunAuditReport:
    (
        capability_summary,
        capability_replays,
        capability_report,
        capability_manifest,
        capability_rollouts,
        capability_records,
    ) = _audit_run(
        role="capability_development",
        run_dir=capability_run_dir,
        preflight_dir=capability_preflight_dir,
        task_source_dir=capability_task_source_dir,
        package_root=package_root,
    )
    (
        reachability_summary,
        reachability_replays,
        reachability_report,
        reachability_manifest,
        reachability_rollouts,
        reachability_records,
    ) = _audit_run(
        role="state_reachability",
        run_dir=reachability_run_dir,
        preflight_dir=reachability_preflight_dir,
        task_source_dir=reachability_task_source_dir,
        package_root=package_root,
    )
    isolation = _cross_role_isolation(
        capability_records=capability_records,
        reachability_records=reachability_records,
        capability_manifest=capability_manifest,
        reachability_manifest=reachability_manifest,
        capability_rollouts=capability_rollouts,
        reachability_rollouts=reachability_rollouts,
    )
    adherence = _condition_adherence(
        reachability_manifest,
        reachability_rollouts,
        reachability_run_dir,
    )
    freeze = reachability_report.state_support_freeze
    if freeze is None or freeze.status != "blocked":
        raise ValueError("post-run audit expected a blocked Reachability Freeze")
    states = reachability_report.state_reachability_summaries
    natural_hit_count = sum(item.natural_on_state_hit_count for item in states)
    conditioned_on_target_count = sum(item.conditioned_on_target_count for item in states)
    released_count = sum(item.released_count for item in states)
    admitted_state_count = sum(item.admitted for item in states)
    if (
        natural_hit_count != 5
        or conditioned_on_target_count != 2
        or released_count != 2
        or admitted_state_count != 0
        or freeze.admitted_task_count != 0
    ):
        raise ValueError("post-run state-support result differs from the frozen aggregation")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "replays": output_dir / "rollout_replay_audits.json",
        "conditions": output_dir / "condition_adherence_summaries.json",
        "isolation": output_dir / "cross_role_isolation_audit.json",
        "roles": output_dir / "role_replay_summaries.json",
    }
    _write_json(
        paths["replays"],
        [
            item.model_dump(mode="json")
            for item in sorted(
                (*capability_replays, *reachability_replays), key=lambda value: value.audit_id
            )
        ],
    )
    _write_json(paths["conditions"], [item.model_dump(mode="json") for item in adherence])
    _write_json(paths["isolation"], isolation.model_dump(mode="json"))
    _write_json(
        paths["roles"],
        [capability_summary.model_dump(mode="json"), reachability_summary.model_dump(mode="json")],
    )
    files = tuple(
        _artifact_file(
            path,
            output_dir,
            {
                "replays": len(capability_replays) + len(reachability_replays),
                "conditions": len(adherence),
                "isolation": 1,
                "roles": 2,
            }[key],
        )
        for key, path in sorted(paths.items())
    )
    values: dict[str, Any] = {
        "run_id": run_id,
        "capability": capability_summary,
        "reachability": reachability_summary,
        "cross_role_isolation": isolation,
        "condition_adherence_summaries": adherence,
        "natural_hit_state_count": sum(item.natural_on_state_hit_count > 0 for item in states),
        "conditioned_on_target_state_count": sum(
            item.conditioned_on_target_count > 0 for item in states
        ),
        "state_support_freeze_id": freeze.freeze_id,
        "immutable_artifact_files": files,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional = AuthorityPreservingRolePostrunAuditReport.model_construct(
        report_id="pending", **values
    )
    report = AuthorityPreservingRolePostrunAuditReport(
        report_id=authority_preserving_role_postrun_audit_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def role_rollout_replay_audit_id(value: RoleRolloutReplayAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_authority_role_rollout_replay:",
    )


def condition_adherence_summary_id(value: ConditionAdherenceSummary) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_id"}),
        prefix="finance_v26_condition_adherence:",
    )


def cross_role_isolation_audit_id(value: CrossRoleIsolationAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_cross_role_isolation:",
    )


def authority_preserving_role_postrun_audit_report_id(
    value: AuthorityPreservingRolePostrunAuditReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_authority_role_postrun_audit:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the Finance v26.71 Capability and v26.72 Reachability runs"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--capability-run-dir", type=Path, required=True)
    parser.add_argument("--capability-preflight-dir", type=Path, required=True)
    parser.add_argument("--capability-task-source-dir", type=Path, required=True)
    parser.add_argument("--reachability-run-dir", type=Path, required=True)
    parser.add_argument("--reachability-preflight-dir", type=Path, required=True)
    parser.add_argument("--reachability-task-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_authority_preserving_role_postrun_audit(
        run_id=args.run_id,
        capability_run_dir=args.capability_run_dir,
        capability_preflight_dir=args.capability_preflight_dir,
        capability_task_source_dir=args.capability_task_source_dir,
        reachability_run_dir=args.reachability_run_dir,
        reachability_preflight_dir=args.reachability_preflight_dir,
        reachability_task_source_dir=args.reachability_task_source_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "status": report.status,
                "capability_valid": report.capability_independently_valid_count,
                "reachability_valid": report.reachability_independently_valid_count,
                "admitted_states": report.admitted_state_count,
                "admitted_tasks": report.admitted_task_count,
                "next_permitted_stage": report.next_permitted_stage,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
