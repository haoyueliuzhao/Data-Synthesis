from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    EmpiricalPilotRollout,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_regression import (
    EXPECTED_ROLLOUT_COUNT,
    OperationClosureRawIntegrityAudit,
    OperationClosureRegressionContract,
    OperationClosureRegressionJobManifest,
    OperationClosureRegressionReport,
    OperationClosureRolloutDiagnostic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
    PublicOperationRematerializationReport,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.tools import AgentToolObservation

V26_OPERATION_CLOSURE_POSTRUN_AUDIT_VERSION = "finance_v26_operation_closure_postrun_audit.v1"
V26_OPERATION_CLOSURE_POSTRUN_DIAGNOSTIC_VERSION = (
    "finance_v26_operation_closure_postrun_diagnostic.v1"
)
V26_OPERATION_CLOSURE_MECHANISM_SUMMARY_VERSION = (
    "finance_v26_operation_closure_mechanism_summary.v1"
)

TARGET_MECHANISMS = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
)
IMPLEMENTATION_SOURCE_PATH: Literal[
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_operation_closure_postrun_audit.py"
] = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_operation_closure_postrun_audit.py"
)

AcquisitionPath = Literal[
    "structured_direct",
    "search_then_structured",
    "search_then_open",
    "unclassified",
]

_ACTION_BINDING_FIELDS = frozenset(
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
_TOP_LEVEL_SOURCE_FILES = {
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
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_operation_closure_postrun_audit.py"
    ] = IMPLEMENTATION_SOURCE_PATH
    sha256: str = Field(min_length=64, max_length=64)


class OperationClosurePostrunDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    terminal_category: str = Field(min_length=1)
    failure_reason: str = Field(min_length=1)
    required_node_count: int = Field(ge=1)
    completed_node_count: int = Field(ge=0)
    full_program_lineage_completed: bool
    terminal_node_completed: bool
    frozen_postterminal_verification_completed: bool
    independently_valid: bool
    mechanism_estimand_success: bool
    acquisition_path: AcquisitionPath
    successful_tool_sequence: tuple[str, ...]
    successful_trace_id: str = Field(min_length=1)
    successful_cross_check_count: int = Field(ge=0)
    postterminal_local_verification_count: int = Field(ge=0)
    exact_terminal_reference_verification_count: int = Field(ge=0)
    terminal_reference_plus_extra_verification_count: int = Field(ge=0)
    answer_payload_verification_count: int = Field(ge=0)
    other_postterminal_verification_count: int = Field(ge=0)
    progress_action_binding_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_observation_count: int = Field(ge=0)
    stop_rejection_reason_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    schema_version: str = V26_OPERATION_CLOSURE_POSTRUN_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> OperationClosurePostrunDiagnostic:
        if self.completed_node_count > self.required_node_count:
            raise ValueError("post-run completed-node count exceeds its contract")
        if self.full_program_lineage_completed != (
            self.completed_node_count == self.required_node_count
        ):
            raise ValueError("post-run full-lineage flag differs from node completion")
        classified = (
            self.exact_terminal_reference_verification_count
            + self.terminal_reference_plus_extra_verification_count
            + self.answer_payload_verification_count
            + self.other_postterminal_verification_count
        )
        if classified != self.postterminal_local_verification_count:
            raise ValueError("post-terminal verification shapes do not exhaust local passes")
        if not self.terminal_node_completed and self.postterminal_local_verification_count:
            raise ValueError("post-terminal verification exists without terminal completion")
        if self.successful_trace_id != canonical_hash(
            self.successful_tool_sequence,
            prefix="finance_v26_operation_successful_trace:",
        ):
            raise ValueError("post-run successful-trace identity is invalid")
        if self.stop_rejection_reason_counts != dict(
            sorted(self.stop_rejection_reason_counts.items())
        ):
            raise ValueError("post-run stop-rejection counts are not canonical")
        if self.diagnostic_id != operation_closure_postrun_diagnostic_id(self):
            raise ValueError("Operation-closure post-run diagnostic identity is invalid")
        return self


class OperationClosureMechanismSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    rollout_count: int = Field(ge=1)
    completed_node_count_histogram: dict[str, int]
    full_program_lineage_count: int = Field(ge=0)
    terminal_node_completion_count: int = Field(ge=0)
    frozen_postterminal_verification_count: int = Field(ge=0)
    independently_valid_count: int = Field(ge=0)
    mechanism_estimand_success_count: int = Field(ge=0)
    postterminal_local_verification_count: int = Field(ge=0)
    exact_terminal_reference_verification_count: int = Field(ge=0)
    terminal_reference_plus_extra_verification_count: int = Field(ge=0)
    answer_payload_verification_count: int = Field(ge=0)
    other_postterminal_verification_count: int = Field(ge=0)
    progress_action_binding_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_rollout_count: int = Field(ge=0)
    acquisition_path_counts: dict[str, int]
    failure_reason_counts: dict[str, int]
    stop_rejection_reason_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    schema_version: str = V26_OPERATION_CLOSURE_MECHANISM_SUMMARY_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> OperationClosureMechanismSummary:
        if sum(self.completed_node_count_histogram.values()) != self.rollout_count:
            raise ValueError("mechanism node-completion histogram has an incomplete denominator")
        if sum(self.acquisition_path_counts.values()) != self.rollout_count:
            raise ValueError("mechanism acquisition paths have an incomplete denominator")
        if sum(self.failure_reason_counts.values()) != self.rollout_count:
            raise ValueError("mechanism failure reasons have an incomplete denominator")
        mappings = (
            self.completed_node_count_histogram,
            self.acquisition_path_counts,
            self.failure_reason_counts,
            self.stop_rejection_reason_counts,
        )
        if any(item != dict(sorted(item.items())) for item in mappings):
            raise ValueError("mechanism summary mappings are not canonical")
        if self.summary_id != operation_closure_mechanism_summary_id(self):
            raise ValueError("Operation-closure mechanism summary identity is invalid")
        return self


class OperationClosurePostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    source_contract_id: str = Field(min_length=1)
    source_job_manifest_id: str = Field(min_length=1)
    task_source_report_id: str = Field(min_length=1)
    source_files: tuple[AuditSourceFile, ...] = Field(min_length=50)
    implementation_source: AuditImplementationSource
    source_integrity_passed: Literal[True] = True
    source_instrument_ready: Literal[True] = True
    source_instrument_status: Literal["passed"] = "passed"
    source_instrument_transition: Literal[
        "capability_development_and_state_reachability_protocol_only"
    ] = "capability_development_and_state_reachability_protocol_only"
    source_instrument_result_retained: Literal[True] = True
    source_outcomes_rescored: Literal[False] = False
    completed_rollout_count: Literal[32] = 32
    model_outcome_count: Literal[32] = 32
    runtime_failure_count: Literal[0] = 0
    instrument_failure_count: Literal[0] = 0
    progress_action_binding_prompt_count: int = Field(ge=0)
    action_bearing_repair_prompt_count: int = Field(ge=0)
    action_bearing_repair_rollout_count: int = Field(ge=0, le=32)
    action_bearing_repair_observation_count: int = Field(ge=0)
    action_bearing_repair_observation_rollout_count: int = Field(ge=0, le=32)
    full_program_lineage_count: int = Field(ge=0, le=32)
    terminal_node_completion_count: int = Field(ge=0, le=32)
    frozen_postterminal_verification_count: int = Field(ge=0, le=32)
    independently_valid_count: int = Field(ge=0, le=32)
    mechanism_estimand_success_count: int = Field(ge=0, le=32)
    postterminal_local_verification_count: int = Field(ge=0)
    postterminal_local_verification_rollout_count: int = Field(ge=0, le=32)
    exact_terminal_reference_verification_count: int = Field(ge=0)
    terminal_reference_plus_extra_verification_count: int = Field(ge=0)
    answer_payload_verification_count: int = Field(ge=0)
    other_postterminal_verification_count: int = Field(ge=0)
    acquisition_path_counts: dict[str, int]
    unique_successful_trace_count: int = Field(ge=0, le=32)
    effective_successful_trace_count: float = Field(ge=0, le=32)
    maximum_successful_trace_share: float = Field(ge=0, le=1)
    natural_multiroute_support_evaluable: Literal[False] = False
    route_diagnostic_scope: Literal[
        "unconditional_capability_tasks_without_registered_vtdo_path_targets"
    ] = "unconditional_capability_tasks_without_registered_vtdo_path_targets"
    public_progress_action_neutral: bool
    repair_feedback_action_neutral: bool
    postterminal_verification_binding_ready: bool
    capability_protocol_ready: bool
    state_reachability_protocol_ready: Literal[False] = False
    diagnostics: tuple[OperationClosurePostrunDiagnostic, ...] = Field(min_length=32, max_length=32)
    mechanism_summaries: tuple[OperationClosureMechanismSummary, ...] = Field(
        min_length=4, max_length=4
    )
    api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    task_selection_performed: Literal[False] = False
    model_comparison_performed: Literal[False] = False
    state_mapping_performed: Literal[False] = False
    causal_validity_comparison_performed: Literal[False] = False
    status: Literal["public_repair_and_postterminal_verification_contract_gaps_observed"] = (
        "public_repair_and_postterminal_verification_contract_gaps_observed"
    )
    next_permitted_stage: Literal[
        "public_repair_and_postterminal_verification_contract_hardening_only"
    ] = "public_repair_and_postterminal_verification_contract_hardening_only"
    capability_development_authorized: Literal[False] = False
    state_reachability_pilot_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_OPERATION_CLOSURE_POSTRUN_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> OperationClosurePostrunAuditReport:
        if self.source_files != tuple(
            sorted(self.source_files, key=lambda item: item.relative_path)
        ):
            raise ValueError("post-run source files are not canonical")
        if len({item.relative_path for item in self.source_files}) != len(self.source_files):
            raise ValueError("post-run source files contain duplicates")
        diagnostics = self.diagnostics
        expected = {
            "progress_action_binding_prompt_count": sum(
                item.progress_action_binding_prompt_count for item in diagnostics
            ),
            "action_bearing_repair_prompt_count": sum(
                item.action_bearing_repair_prompt_count for item in diagnostics
            ),
            "action_bearing_repair_rollout_count": sum(
                item.action_bearing_repair_prompt_count > 0 for item in diagnostics
            ),
            "action_bearing_repair_observation_count": sum(
                item.action_bearing_repair_observation_count for item in diagnostics
            ),
            "action_bearing_repair_observation_rollout_count": sum(
                item.action_bearing_repair_observation_count > 0 for item in diagnostics
            ),
            "full_program_lineage_count": sum(
                item.full_program_lineage_completed for item in diagnostics
            ),
            "terminal_node_completion_count": sum(
                item.terminal_node_completed for item in diagnostics
            ),
            "frozen_postterminal_verification_count": sum(
                item.frozen_postterminal_verification_completed for item in diagnostics
            ),
            "independently_valid_count": sum(item.independently_valid for item in diagnostics),
            "mechanism_estimand_success_count": sum(
                item.mechanism_estimand_success for item in diagnostics
            ),
            "postterminal_local_verification_count": sum(
                item.postterminal_local_verification_count for item in diagnostics
            ),
            "postterminal_local_verification_rollout_count": sum(
                item.postterminal_local_verification_count > 0 for item in diagnostics
            ),
            "exact_terminal_reference_verification_count": sum(
                item.exact_terminal_reference_verification_count for item in diagnostics
            ),
            "terminal_reference_plus_extra_verification_count": sum(
                item.terminal_reference_plus_extra_verification_count for item in diagnostics
            ),
            "answer_payload_verification_count": sum(
                item.answer_payload_verification_count for item in diagnostics
            ),
            "other_postterminal_verification_count": sum(
                item.other_postterminal_verification_count for item in diagnostics
            ),
        }
        if any(getattr(self, key) != value for key, value in expected.items()):
            raise ValueError("post-run report differs from rollout diagnostics")
        if self.acquisition_path_counts != dict(
            sorted(Counter(item.acquisition_path for item in diagnostics).items())
        ):
            raise ValueError("post-run acquisition paths differ from rollout diagnostics")
        trace_counts = Counter(item.successful_trace_id for item in diagnostics)
        if self.unique_successful_trace_count != len(trace_counts):
            raise ValueError("post-run unique trace count is inconsistent")
        if not math.isclose(
            self.effective_successful_trace_count,
            _effective_count(trace_counts),
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ValueError("post-run effective trace count is inconsistent")
        if not math.isclose(
            self.maximum_successful_trace_share,
            max(trace_counts.values()) / len(diagnostics),
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ValueError("post-run maximum trace share is inconsistent")
        if self.public_progress_action_neutral != (self.progress_action_binding_prompt_count == 0):
            raise ValueError("post-run Progress action-neutral decision is inconsistent")
        if self.repair_feedback_action_neutral != (self.action_bearing_repair_prompt_count == 0):
            raise ValueError("post-run repair-feedback decision is inconsistent")
        verification_ready = (
            self.terminal_node_completion_count > 0
            and self.frozen_postterminal_verification_count == self.terminal_node_completion_count
            and self.exact_terminal_reference_verification_count > 0
        )
        if self.postterminal_verification_binding_ready != verification_ready:
            raise ValueError("post-run verification-binding decision is inconsistent")
        protocol_ready = (
            self.public_progress_action_neutral
            and self.repair_feedback_action_neutral
            and self.postterminal_verification_binding_ready
        )
        if self.capability_protocol_ready != protocol_ready:
            raise ValueError("post-run capability-protocol decision is inconsistent")
        if self.capability_protocol_ready:
            raise ValueError("v26.64 unexpectedly authorized an empirical protocol")
        if tuple(item.mechanism_id for item in self.mechanism_summaries) != TARGET_MECHANISMS:
            raise ValueError("post-run mechanism summaries are incomplete")
        if self.report_id != operation_closure_postrun_report_id(self):
            raise ValueError("Operation-closure post-run report identity is invalid")
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
    if not path.is_file():
        raise ValueError(f"post-run source file is missing: {path}")
    count = _record_count(path)
    if count != expected:
        raise ValueError(f"post-run source denominator changed: {path}")
    return AuditSourceFile(
        relative_path=f"{prefix}/{relative}",
        sha256=_sha256(path),
        record_count=count,
    )


def _write_json_atomic(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"post-run immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _raw_payload(
    rollout: EmpiricalPilotRollout,
    regression_dir: Path,
) -> tuple[dict[str, Any], AuditSourceFile]:
    path = Path(rollout.raw_artifact_uri).resolve()
    try:
        relative = path.relative_to(regression_dir.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("post-run raw Artifact is outside the source experiment") from error
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != rollout.raw_artifact_sha256:
        raise ValueError("post-run raw Artifact hash replay failed")
    payload = cast(dict[str, Any], json.loads(raw))
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError("post-run raw Artifact is not canonical JSON")
    return payload, AuditSourceFile(
        relative_path=f"regression/{relative}",
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
    marker = "\nPUBLIC_CONTEXT_JSON:\n"
    repair_marker = "\nCONTRACT_REPAIR_JSON:\n"
    _, separator, remainder = prompt.partition(marker)
    if not separator:
        return None
    context_text, _, _ = remainder.partition(repair_marker)
    try:
        value = json.loads(context_text)
    except json.JSONDecodeError as error:
        raise ValueError("post-run Prompt contains malformed PUBLIC_CONTEXT_JSON") from error
    if not isinstance(value, Mapping):
        raise ValueError("post-run Prompt public Context is not a mapping")
    return value


def _contains_action_binding(value: Any) -> bool:
    if isinstance(value, Mapping):
        if _ACTION_BINDING_FIELDS & set(value):
            return True
        return any(_contains_action_binding(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_action_binding(item) for item in value)
    return False


def _progress_action_binding_count(prompts: Sequence[str]) -> int:
    count = 0
    for prompt in prompts:
        context = _prompt_context(prompt)
        if context is None:
            continue
        progress = context.get("operation_execution_progress")
        if not isinstance(progress, Mapping):
            continue
        projected_nodes = {
            "ready_nodes": progress.get("ready_nodes"),
            "next_required_step": progress.get("next_required_step"),
        }
        count += _contains_action_binding(projected_nodes)
    return count


def _repair_action_binding_count(prompts: Sequence[str]) -> int:
    count = 0
    for prompt in prompts:
        context = _prompt_context(prompt)
        if context is None:
            continue
        repair = context.get("failed_action_repair")
        if not isinstance(repair, Mapping):
            continue
        patch = repair.get("required_argument_patch")
        count += patch is not None and _contains_action_binding(patch)
    return count


def _repair_observation_count(observations: Sequence[AgentToolObservation]) -> int:
    count = 0
    for observation in observations:
        if observation.status != "failed":
            continue
        retry = observation.result.get("retry_contract")
        if not isinstance(retry, Mapping):
            continue
        patch = retry.get("suggested_argument_patch")
        count += patch is not None and _contains_action_binding(patch)
    return count


def _acquisition_path(observations: Sequence[AgentToolObservation]) -> AcquisitionPath:
    successful_before_calculation = []
    for observation in observations:
        if observation.call.tool_id == "calculator" and observation.status == "succeeded":
            break
        if observation.status == "succeeded":
            successful_before_calculation.append(observation.call.tool_id)
    tools = set(successful_before_calculation)
    if "open_document" in tools:
        return "search_then_open"
    if "search_archive" in tools:
        return "search_then_structured"
    if "query_structured_fact" in tools:
        return "structured_direct"
    return "unclassified"


def _terminal_position(
    record: OperationalTaskRecord,
    observations: Sequence[AgentToolObservation],
) -> tuple[int | None, str | None, Mapping[str, Any]]:
    task = record.task_package.task.public
    terminal_index = None
    terminal_ref = None
    final_progress: Mapping[str, Any] | None = None
    for index in range(1, len(observations) + 1):
        progress = public_operation_progress(task, tuple(observations[:index]))
        if progress is None:
            raise ValueError("post-run replay lost its public Operation contract")
        final_progress = progress
        if terminal_index is None and progress["terminal_node_completed"]:
            terminal_index = index - 1
            terminal_ref = cast(str | None, progress["terminal_operation_ref"])
    if final_progress is None:
        progress = public_operation_progress(task, ())
        if progress is None:
            raise ValueError("post-run task lacks a public Operation contract")
        final_progress = progress
    return terminal_index, terminal_ref, final_progress


def _verification_shape_counts(
    observations: Sequence[AgentToolObservation],
    terminal_index: int | None,
    terminal_ref: str | None,
) -> tuple[int, int, int, int, int, int]:
    successful_cross_checks = 0
    local = exact = plus_extra = answer_payload = other = 0
    for index, observation in enumerate(observations):
        if (
            observation.call.tool_id != "cross_check_evidence"
            or observation.status != "succeeded"
            or observation.result.get("verified") is not True
        ):
            continue
        successful_cross_checks += 1
        if terminal_index is None or index <= terminal_index:
            continue
        local += 1
        claim = observation.call.arguments.get("claim_or_result")
        if not isinstance(claim, Mapping):
            other += 1
        elif "operation_ref" not in claim:
            answer_payload += 1
        elif claim.get("operation_ref") != terminal_ref:
            other += 1
        elif set(claim) == {"operation_ref"}:
            exact += 1
        else:
            plus_extra += 1
    return successful_cross_checks, local, exact, plus_extra, answer_payload, other


def _stop_rejection_counts(payload: Mapping[str, Any]) -> dict[str, int]:
    failure = payload.get("failure_artifact")
    if not isinstance(failure, Mapping):
        return {}
    counts = Counter(
        str(item.get("reason_code") or "unclassified")
        for item in failure.get("stop_rejections") or ()
        if isinstance(item, Mapping)
    )
    return dict(sorted(counts.items()))


def _diagnostic(
    rollout: EmpiricalPilotRollout,
    frozen: OperationClosureRolloutDiagnostic,
    record: OperationalTaskRecord,
    payload: Mapping[str, Any],
) -> OperationClosurePostrunDiagnostic:
    observations = _observations(payload)
    terminal_index, terminal_ref, progress = _terminal_position(record, observations)
    if frozen.completed_node_count != len(progress["completed_node_ids"]):
        raise ValueError("post-run node completion differs from the frozen diagnostic")
    if frozen.terminal_node_completed != bool(progress["terminal_node_completed"]):
        raise ValueError("post-run terminal completion differs from the frozen diagnostic")
    verification_counts = _verification_shape_counts(
        observations,
        terminal_index,
        terminal_ref,
    )
    successful_sequence = tuple(
        item.call.tool_id for item in observations if item.status == "succeeded"
    )
    prompts = tuple(str(item) for item in payload["actual_model_request_prompts"])
    estimand = rollout.mechanism_estimand
    values: dict[str, Any] = {
        "rollout_id": rollout.rollout_id,
        "job_id": rollout.job_id,
        "task_package_id": rollout.task_package_id,
        "mechanism_id": rollout.mechanism_id,
        "replicate_index": rollout.replicate_index,
        "terminal_category": rollout.terminal_category,
        "failure_reason": str(
            rollout.failure_attribution.get("reason")
            if isinstance(rollout.failure_attribution, Mapping)
            else "unattributed_model_outcome"
        ),
        "required_node_count": frozen.required_node_count,
        "completed_node_count": frozen.completed_node_count,
        "full_program_lineage_completed": frozen.full_program_lineage_completed,
        "terminal_node_completed": frozen.terminal_node_completed,
        "frozen_postterminal_verification_completed": (frozen.postterminal_verification_completed),
        "independently_valid": frozen.independent_validity,
        "mechanism_estimand_success": bool(
            estimand is not None and estimand.evaluated and estimand.success
        ),
        "acquisition_path": _acquisition_path(observations),
        "successful_tool_sequence": successful_sequence,
        "successful_trace_id": canonical_hash(
            successful_sequence,
            prefix="finance_v26_operation_successful_trace:",
        ),
        "successful_cross_check_count": verification_counts[0],
        "postterminal_local_verification_count": verification_counts[1],
        "exact_terminal_reference_verification_count": verification_counts[2],
        "terminal_reference_plus_extra_verification_count": verification_counts[3],
        "answer_payload_verification_count": verification_counts[4],
        "other_postterminal_verification_count": verification_counts[5],
        "progress_action_binding_prompt_count": _progress_action_binding_count(prompts),
        "action_bearing_repair_prompt_count": _repair_action_binding_count(prompts),
        "action_bearing_repair_observation_count": _repair_observation_count(observations),
        "stop_rejection_reason_counts": _stop_rejection_counts(payload),
        "provider_call_count": rollout.provider_call_count,
        "provider_total_tokens": rollout.provider_total_tokens,
    }
    provisional = OperationClosurePostrunDiagnostic.model_construct(
        diagnostic_id="pending", **values
    )
    return OperationClosurePostrunDiagnostic(
        diagnostic_id=operation_closure_postrun_diagnostic_id(provisional),
        **values,
    )


def _sum_mappings(values: Sequence[Mapping[str, int]]) -> dict[str, int]:
    total: Counter[str] = Counter()
    for value in values:
        total.update(value)
    return dict(sorted(total.items()))


def _mechanism_summary(
    mechanism: str,
    diagnostics: Sequence[OperationClosurePostrunDiagnostic],
) -> OperationClosureMechanismSummary:
    rows = tuple(item for item in diagnostics if item.mechanism_id == mechanism)
    if len(rows) != 8:
        raise ValueError(f"post-run mechanism denominator changed: {mechanism}")
    values: dict[str, Any] = {
        "mechanism_id": mechanism,
        "rollout_count": len(rows),
        "completed_node_count_histogram": dict(
            sorted(Counter(str(item.completed_node_count) for item in rows).items())
        ),
        "full_program_lineage_count": sum(item.full_program_lineage_completed for item in rows),
        "terminal_node_completion_count": sum(item.terminal_node_completed for item in rows),
        "frozen_postterminal_verification_count": sum(
            item.frozen_postterminal_verification_completed for item in rows
        ),
        "independently_valid_count": sum(item.independently_valid for item in rows),
        "mechanism_estimand_success_count": sum(item.mechanism_estimand_success for item in rows),
        "postterminal_local_verification_count": sum(
            item.postterminal_local_verification_count for item in rows
        ),
        "exact_terminal_reference_verification_count": sum(
            item.exact_terminal_reference_verification_count for item in rows
        ),
        "terminal_reference_plus_extra_verification_count": sum(
            item.terminal_reference_plus_extra_verification_count for item in rows
        ),
        "answer_payload_verification_count": sum(
            item.answer_payload_verification_count for item in rows
        ),
        "other_postterminal_verification_count": sum(
            item.other_postterminal_verification_count for item in rows
        ),
        "progress_action_binding_prompt_count": sum(
            item.progress_action_binding_prompt_count for item in rows
        ),
        "action_bearing_repair_prompt_count": sum(
            item.action_bearing_repair_prompt_count for item in rows
        ),
        "action_bearing_repair_rollout_count": sum(
            item.action_bearing_repair_prompt_count > 0 for item in rows
        ),
        "acquisition_path_counts": dict(
            sorted(Counter(item.acquisition_path for item in rows).items())
        ),
        "failure_reason_counts": dict(
            sorted(Counter(item.failure_reason for item in rows).items())
        ),
        "stop_rejection_reason_counts": _sum_mappings(
            [item.stop_rejection_reason_counts for item in rows]
        ),
        "provider_call_count": sum(item.provider_call_count for item in rows),
        "provider_total_tokens": sum(item.provider_total_tokens for item in rows),
    }
    provisional = OperationClosureMechanismSummary.model_construct(summary_id="pending", **values)
    return OperationClosureMechanismSummary(
        summary_id=operation_closure_mechanism_summary_id(provisional),
        **values,
    )


def _entropy_bits(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    return -math.fsum(
        (count / total) * math.log2(count / total) for count in sorted(counts.values())
    )


def _effective_count(counts: Counter[str]) -> float:
    return 2.0 ** _entropy_bits(counts) if counts else 0.0


def _load_sources(
    regression_dir: Path,
    task_source_dir: Path,
    package_root: Path,
) -> tuple[
    OperationClosureRegressionReport,
    tuple[EmpiricalPilotRollout, ...],
    tuple[OperationalTaskRecord, ...],
    tuple[AuditSourceFile, ...],
]:
    report_path = regression_dir / "report.json"
    report = OperationClosureRegressionReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    contract = OperationClosureRegressionContract.model_validate_json(
        (regression_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = OperationClosureRegressionJobManifest.model_validate_json(
        (regression_dir / "job_manifest.json").read_text(encoding="utf-8")
    )
    raw_audit = OperationClosureRawIntegrityAudit.model_validate_json(
        (regression_dir / "raw_integrity_audit.json").read_text(encoding="utf-8")
    )
    if (
        report.status != "passed"
        or not report.instrument_ready
        or report.completed_rollout_count != EXPECTED_ROLLOUT_COUNT
        or report.model_outcome_count != EXPECTED_ROLLOUT_COUNT
        or report.runtime_failure_count
        or report.instrument_failure_count
        or report.next_permitted_stage
        != "capability_development_and_state_reachability_protocol_only"
    ):
        raise ValueError("v26.63 is not a passing completed instrument regression")
    if (
        report.contract_id != contract.contract_id
        or report.job_manifest_id != manifest.manifest_id
        or manifest.contract_id != contract.contract_id
        or report.raw_integrity_audit != raw_audit
        or raw_audit.status != "passed"
    ):
        raise ValueError("v26.63 report differs from its frozen inputs")
    rollouts = tuple(
        EmpiricalPilotRollout.model_validate(item)
        for item in json.loads((regression_dir / "empirical_rollouts.json").read_text())
    )
    frozen_diagnostics = tuple(
        OperationClosureRolloutDiagnostic.model_validate(item)
        for item in json.loads((regression_dir / "rollout_diagnostics.json").read_text())
    )
    checkpoint = tuple(
        EmpiricalPilotRollout.model_validate_json(line)
        for line in (regression_dir / "rollout_observations.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    checkpoint_by_job = {item.job_id: item for item in checkpoint}
    if len(checkpoint_by_job) != EXPECTED_ROLLOUT_COUNT or checkpoint_by_job != {
        item.job_id: item for item in rollouts
    }:
        raise ValueError("v26.63 aggregate differs from its checkpoint")
    if frozen_diagnostics != report.diagnostics:
        raise ValueError("v26.63 detail diagnostics differ from its report")
    if tuple(item.job_id for item in rollouts) != tuple(item.job_id for item in manifest.jobs):
        raise ValueError("v26.63 rollout order differs from its Job Manifest")
    task_report_path = task_source_dir / "report.json"
    task_report = PublicOperationRematerializationReport.model_validate_json(
        task_report_path.read_text(encoding="utf-8")
    )
    if (
        contract.source_report_id != task_report.report_id
        or contract.source_report_sha256 != _sha256(task_report_path)
    ):
        raise ValueError("v26.63 task source differs from its execution contract")
    for source_item in contract.source_artifact_files:
        if _sha256(task_source_dir / source_item.relative_path) != source_item.sha256:
            raise ValueError(f"v26.63 task-source Artifact changed: {source_item.relative_path}")
    for implementation_item in contract.implementation_source_files:
        if _sha256(package_root / implementation_item.relative_path) != implementation_item.sha256:
            raise ValueError(f"v26.63 implementation changed: {implementation_item.relative_path}")
    records = tuple(
        OperationalTaskRecord.model_validate(item)
        for item in json.loads((task_source_dir / "operational_task_records.json").read_text())
    )
    selected_record_ids = {item.task_record_id for item in manifest.jobs}
    selected = tuple(item for item in records if item.record_id in selected_record_ids)
    if {item.record_id for item in selected} != selected_record_ids:
        raise ValueError("v26.63 selected task records are unavailable")
    source_files = [
        _source_file("regression", regression_dir, relative, count)
        for relative, count in sorted(_TOP_LEVEL_SOURCE_FILES.items())
    ]
    source_files.extend(
        _source_file(
            "task_source",
            task_source_dir,
            source_item.relative_path,
            source_item.record_count,
        )
        for source_item in contract.source_artifact_files
    )
    raw_source_files = []
    for rollout in rollouts:
        _, source_file = _raw_payload(rollout, regression_dir)
        raw_source_files.append(source_file)
    source_files.extend(raw_source_files)
    return (
        report,
        rollouts,
        selected,
        tuple(sorted(source_files, key=lambda item: item.relative_path)),
    )


def build_operation_closure_postrun_audit(
    *,
    run_id: str,
    regression_dir: Path,
    task_source_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> OperationClosurePostrunAuditReport:
    source_report, rollouts, records, source_files = _load_sources(
        regression_dir,
        task_source_dir,
        package_root,
    )
    frozen_by_rollout = {item.rollout_id: item for item in source_report.diagnostics}
    record_by_id = {item.record_id: item for item in records}
    diagnostics = []
    for rollout in rollouts:
        payload, _ = _raw_payload(rollout, regression_dir)
        diagnostics.append(
            _diagnostic(
                rollout,
                frozen_by_rollout[rollout.rollout_id],
                record_by_id[rollout.task_record_id],
                payload,
            )
        )
    diagnostics.sort(key=lambda item: item.diagnostic_id)
    frozen_diagnostics = tuple(diagnostics)
    summaries = tuple(
        _mechanism_summary(mechanism, frozen_diagnostics) for mechanism in TARGET_MECHANISMS
    )
    trace_counts = Counter(item.successful_trace_id for item in frozen_diagnostics)
    progress_exposure = sum(
        item.progress_action_binding_prompt_count for item in frozen_diagnostics
    )
    repair_exposure = sum(item.action_bearing_repair_prompt_count for item in frozen_diagnostics)
    terminal_count = sum(item.terminal_node_completed for item in frozen_diagnostics)
    frozen_verification_count = sum(
        item.frozen_postterminal_verification_completed for item in frozen_diagnostics
    )
    exact_verification_count = sum(
        item.exact_terminal_reference_verification_count for item in frozen_diagnostics
    )
    verification_ready = (
        terminal_count > 0
        and frozen_verification_count == terminal_count
        and exact_verification_count > 0
    )
    source_report_path = regression_dir / "report.json"
    values: dict[str, Any] = {
        "run_id": run_id,
        "source_run_id": source_report.run_id,
        "source_report_id": source_report.report_id,
        "source_report_sha256": _sha256(source_report_path),
        "source_contract_id": source_report.contract_id,
        "source_job_manifest_id": source_report.job_manifest_id,
        "task_source_report_id": PublicOperationRematerializationReport.model_validate_json(
            (task_source_dir / "report.json").read_text(encoding="utf-8")
        ).report_id,
        "source_files": source_files,
        "implementation_source": AuditImplementationSource(
            sha256=_sha256(package_root / IMPLEMENTATION_SOURCE_PATH)
        ),
        "progress_action_binding_prompt_count": progress_exposure,
        "action_bearing_repair_prompt_count": repair_exposure,
        "action_bearing_repair_rollout_count": sum(
            item.action_bearing_repair_prompt_count > 0 for item in frozen_diagnostics
        ),
        "action_bearing_repair_observation_count": sum(
            item.action_bearing_repair_observation_count for item in frozen_diagnostics
        ),
        "action_bearing_repair_observation_rollout_count": sum(
            item.action_bearing_repair_observation_count > 0 for item in frozen_diagnostics
        ),
        "full_program_lineage_count": sum(
            item.full_program_lineage_completed for item in frozen_diagnostics
        ),
        "terminal_node_completion_count": terminal_count,
        "frozen_postterminal_verification_count": frozen_verification_count,
        "independently_valid_count": sum(item.independently_valid for item in frozen_diagnostics),
        "mechanism_estimand_success_count": sum(
            item.mechanism_estimand_success for item in frozen_diagnostics
        ),
        "postterminal_local_verification_count": sum(
            item.postterminal_local_verification_count for item in frozen_diagnostics
        ),
        "postterminal_local_verification_rollout_count": sum(
            item.postterminal_local_verification_count > 0 for item in frozen_diagnostics
        ),
        "exact_terminal_reference_verification_count": exact_verification_count,
        "terminal_reference_plus_extra_verification_count": sum(
            item.terminal_reference_plus_extra_verification_count for item in frozen_diagnostics
        ),
        "answer_payload_verification_count": sum(
            item.answer_payload_verification_count for item in frozen_diagnostics
        ),
        "other_postterminal_verification_count": sum(
            item.other_postterminal_verification_count for item in frozen_diagnostics
        ),
        "acquisition_path_counts": dict(
            sorted(Counter(item.acquisition_path for item in frozen_diagnostics).items())
        ),
        "unique_successful_trace_count": len(trace_counts),
        "effective_successful_trace_count": _effective_count(trace_counts),
        "maximum_successful_trace_share": max(trace_counts.values()) / len(frozen_diagnostics),
        "public_progress_action_neutral": progress_exposure == 0,
        "repair_feedback_action_neutral": repair_exposure == 0,
        "postterminal_verification_binding_ready": verification_ready,
        "capability_protocol_ready": (
            progress_exposure == 0 and repair_exposure == 0 and verification_ready
        ),
        "diagnostics": frozen_diagnostics,
        "mechanism_summaries": summaries,
    }
    provisional = OperationClosurePostrunAuditReport.model_construct(report_id="pending", **values)
    report = OperationClosurePostrunAuditReport(
        report_id=operation_closure_postrun_report_id(provisional),
        **values,
    )
    _write_json_atomic(
        output_dir / "rollout_postrun_diagnostics.json",
        [item.model_dump(mode="json") for item in frozen_diagnostics],
    )
    _write_json_atomic(
        output_dir / "mechanism_postrun_summaries.json",
        [item.model_dump(mode="json") for item in summaries],
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def operation_closure_postrun_diagnostic_id(
    value: OperationClosurePostrunDiagnostic,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_operation_closure_postrun_diagnostic:",
    )


def operation_closure_mechanism_summary_id(
    value: OperationClosureMechanismSummary,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_id"}),
        prefix="finance_v26_operation_closure_mechanism_summary:",
    )


def operation_closure_postrun_report_id(
    value: OperationClosurePostrunAuditReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_operation_closure_postrun_audit:",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the credential-free v26.64 post-run audit")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--regression-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    report = build_operation_closure_postrun_audit(
        run_id=args.run_id,
        regression_dir=args.regression_dir,
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
