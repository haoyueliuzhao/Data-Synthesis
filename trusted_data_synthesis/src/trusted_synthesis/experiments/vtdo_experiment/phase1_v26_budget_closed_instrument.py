from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import BoundPublicExecutableWitness
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.core.trajectory.state import trajectory_decision_trace_hash
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

V26_BUDGET_CLOSED_FAILURE_CHANNEL_VERSION = "finance_v26_budget_closed_failure_channels.v1"
V26_SCHEMA_CLOSED_TRACE_VERSION = "finance_v26_schema_closed_trace_sidecar.v1"
V26_COMPLETED_TRAJECTORY_SCORE_VERSION = "finance_v26_budget_closed_completed_trajectory_score.v1"
V26_COMPILER_TRAJECTORY_VERSION = "finance_v26_budget_closed_compiler_trajectory.v1"

TrajectorySourceKind = Literal["compiler_fixture", "model_generated"]
CoreTerminal = Literal[
    "valid_trajectory",
    "invalid_trajectory",
    "instrument_failure",
]
ResourceBudgetStatus = Literal["passed", "not_applicable_no_provider_calls", "failed"]

TRAJECTORY_STEP_SCHEMA_FIELDS = (
    "step_index",
    "action",
    "tool_name",
    "tool_input",
    "observation",
    "evidence_ids",
    "program_node_id",
    "operator_id",
    "input_refs",
    "output_ref",
    "rationale_summary",
    "status",
)

_FAILURE_NAMESPACES = {
    "raw_lineage_failures": "raw_lineage:",
    "provider_capture_failures": "provider_capture:",
    "runtime_replay_failures": "runtime_replay:",
    "scoring_core_failures": "scoring_core:",
    "diagnostic_sidecar_failures": "diagnostic_sidecar:",
    "resource_failures": "resource_budget:",
    "report_aggregation_failures": "report_aggregation:",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InstrumentFailureChannels(FrozenModel):
    channel_id: str = Field(min_length=1)
    raw_lineage_failures: tuple[str, ...] = ()
    provider_capture_failures: tuple[str, ...] = ()
    runtime_replay_failures: tuple[str, ...] = ()
    scoring_core_failures: tuple[str, ...] = ()
    diagnostic_sidecar_failures: tuple[str, ...] = ()
    resource_failures: tuple[str, ...] = ()
    report_aggregation_failures: tuple[str, ...] = ()
    instrument_gate_passed: bool
    report_complete: bool
    schema_version: str = V26_BUDGET_CLOSED_FAILURE_CHANNEL_VERSION

    @model_validator(mode="after")
    def validate_channels(self) -> InstrumentFailureChannels:
        all_failures: list[str] = []
        for field_name, prefix in _FAILURE_NAMESPACES.items():
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} is not canonical")
            if any(not item.startswith(prefix) for item in values):
                raise ValueError(f"{field_name} contains another failure namespace")
            all_failures.extend(values)
        if len(all_failures) != len(set(all_failures)):
            raise ValueError("Instrument failure namespaces overlap")
        gate_failures = tuple(
            item
            for field_name in _FAILURE_NAMESPACES
            if field_name != "diagnostic_sidecar_failures"
            for item in getattr(self, field_name)
        )
        if self.instrument_gate_passed != (not gate_failures):
            raise ValueError("Instrument failure channels do not derive the Gate")
        report_failures = self.diagnostic_sidecar_failures + self.report_aggregation_failures
        if self.report_complete != (not report_failures):
            raise ValueError("Instrument failure channels do not derive report completeness")
        if self.channel_id != instrument_failure_channels_id(self):
            raise ValueError("Instrument failure-channel identity is invalid")
        return self


class SchemaClosedTraceSidecar(FrozenModel):
    sidecar_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    trajectory_step_schema_fields: tuple[str, ...] = Field(min_length=12, max_length=12)
    trajectory_step_schema_hash: str = Field(min_length=1)
    trajectory_content_hash: str = Field(min_length=1)
    decision_trace_hash: str = Field(min_length=1)
    step_count: int = Field(ge=2)
    nonexistent_field_access_count: Literal[0] = 0
    schema_valid: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_SCHEMA_CLOSED_TRACE_VERSION

    @model_validator(mode="after")
    def validate_sidecar(self) -> SchemaClosedTraceSidecar:
        if self.trajectory_step_schema_fields != TRAJECTORY_STEP_SCHEMA_FIELDS:
            raise ValueError("Trace sidecar binds another TrajectoryStep schema")
        if self.trajectory_step_schema_hash != canonical_hash(
            self.trajectory_step_schema_fields,
            prefix="finance_v26_trajectory_step_schema:",
        ):
            raise ValueError("Trace sidecar TrajectoryStep schema hash is invalid")
        if self.sidecar_id != schema_closed_trace_sidecar_id(self):
            raise ValueError("Trace sidecar identity is invalid")
        return self


class CompletedTrajectoryScore(FrozenModel):
    score_id: str = Field(min_length=1)
    source_kind: TrajectorySourceKind
    trajectory_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    replay_result_id: str = Field(min_length=1)
    replay_passed: bool
    non_replay_checks: dict[str, bool]
    independent_valid: bool
    core_terminal: CoreTerminal
    core_classification_frozen_before_sidecar: Literal[True] = True
    trace_sidecar: SchemaClosedTraceSidecar | None
    resource_budget_audit_id: str = Field(min_length=1)
    resource_budget_status: ResourceBudgetStatus
    failure_channels: InstrumentFailureChannels
    instrument_admitted: bool
    empirical_denominator_eligible: bool
    compiler_fixture_excluded_from_empirical_counts: bool
    schema_version: str = V26_COMPLETED_TRAJECTORY_SCORE_VERSION

    @model_validator(mode="after")
    def validate_score(self) -> CompletedTrajectoryScore:
        if tuple(self.non_replay_checks) != tuple(sorted(self.non_replay_checks)):
            raise ValueError("Completed score non-Replay checks are not canonical")
        expected_terminal: CoreTerminal
        if not self.replay_passed:
            expected_terminal = "instrument_failure"
        elif self.independent_valid and all(self.non_replay_checks.values()):
            expected_terminal = "valid_trajectory"
        else:
            expected_terminal = "invalid_trajectory"
        if self.core_terminal != expected_terminal:
            raise ValueError("Completed score core terminal is inconsistent")
        expected_empirical = self.source_kind == "model_generated"
        if self.empirical_denominator_eligible != expected_empirical:
            raise ValueError("Completed score empirical role is inconsistent")
        if self.compiler_fixture_excluded_from_empirical_counts != (not expected_empirical):
            raise ValueError("Compiler fixture empirical exclusion is inconsistent")
        expected_admitted = (
            self.failure_channels.instrument_gate_passed
            and self.failure_channels.report_complete
            and self.resource_budget_status != "failed"
            and self.core_terminal != "instrument_failure"
        )
        if self.instrument_admitted != expected_admitted:
            raise ValueError("Completed score Instrument admission is inconsistent")
        if (self.trace_sidecar is None) != bool(self.failure_channels.diagnostic_sidecar_failures):
            raise ValueError("Completed score sidecar failure accounting is inconsistent")
        if self.trace_sidecar is not None and (
            self.trace_sidecar.trajectory_id != self.trajectory_id
            or self.trace_sidecar.task_id != self.task_id
        ):
            raise ValueError("Completed score sidecar crosses trajectories")
        if self.score_id != completed_trajectory_score_id(self):
            raise ValueError("Completed trajectory score identity is invalid")
        return self


def build_instrument_failure_channels(
    *,
    raw_lineage_failures: Sequence[str] = (),
    provider_capture_failures: Sequence[str] = (),
    runtime_replay_failures: Sequence[str] = (),
    scoring_core_failures: Sequence[str] = (),
    diagnostic_sidecar_failures: Sequence[str] = (),
    resource_failures: Sequence[str] = (),
    report_aggregation_failures: Sequence[str] = (),
) -> InstrumentFailureChannels:
    values: dict[str, Any] = {
        "raw_lineage_failures": tuple(sorted(set(raw_lineage_failures))),
        "provider_capture_failures": tuple(sorted(set(provider_capture_failures))),
        "runtime_replay_failures": tuple(sorted(set(runtime_replay_failures))),
        "scoring_core_failures": tuple(sorted(set(scoring_core_failures))),
        "diagnostic_sidecar_failures": tuple(sorted(set(diagnostic_sidecar_failures))),
        "resource_failures": tuple(sorted(set(resource_failures))),
        "report_aggregation_failures": tuple(sorted(set(report_aggregation_failures))),
    }
    gate_failures = tuple(
        item
        for field_name in _FAILURE_NAMESPACES
        if field_name != "diagnostic_sidecar_failures"
        for item in values[field_name]
    )
    values["instrument_gate_passed"] = not gate_failures
    values["report_complete"] = not (
        values["diagnostic_sidecar_failures"] or values["report_aggregation_failures"]
    )
    provisional = InstrumentFailureChannels.model_construct(channel_id="pending", **values)
    return InstrumentFailureChannels(
        channel_id=instrument_failure_channels_id(provisional),
        **values,
    )


def build_schema_closed_trace_sidecar(trajectory: Trajectory) -> SchemaClosedTraceSidecar:
    observed_fields = tuple(TrajectoryStep.model_fields)
    if observed_fields != TRAJECTORY_STEP_SCHEMA_FIELDS:
        raise ValueError("TrajectoryStep schema changed before trace scoring")
    values = {
        "trajectory_id": trajectory.trajectory_id,
        "task_id": trajectory.task_id,
        "trajectory_step_schema_fields": observed_fields,
        "trajectory_step_schema_hash": canonical_hash(
            observed_fields,
            prefix="finance_v26_trajectory_step_schema:",
        ),
        "trajectory_content_hash": canonical_hash(
            trajectory.model_dump(mode="json", exclude={"trajectory_id"}),
            prefix="finance_v26_budget_closed_trajectory_content:",
        ),
        "decision_trace_hash": trajectory_decision_trace_hash(trajectory),
        "step_count": len(trajectory.steps),
    }
    provisional = SchemaClosedTraceSidecar.model_construct(sidecar_id="pending", **values)
    return SchemaClosedTraceSidecar(
        sidecar_id=schema_closed_trace_sidecar_id(provisional),
        **values,
    )


def score_completed_trajectory(
    *,
    trajectory: Trajectory,
    source_kind: TrajectorySourceKind,
    replay_result_id: str,
    replay_passed: bool,
    non_replay_checks: Mapping[str, bool],
    independent_valid: bool,
    resource_budget_audit_id: str,
    resource_budget_status: ResourceBudgetStatus,
    base_failure_channels: InstrumentFailureChannels | None = None,
    sidecar_builder: Callable[[Trajectory], SchemaClosedTraceSidecar] = (
        build_schema_closed_trace_sidecar
    ),
) -> CompletedTrajectoryScore:
    base = base_failure_channels or build_instrument_failure_channels()
    replay_failures = list(base.runtime_replay_failures)
    resource_failures = list(base.resource_failures)
    if not replay_passed:
        replay_failures.append("runtime_replay:completed_trajectory_mismatch")
    if resource_budget_status == "failed":
        resource_failures.append("resource_budget:completed_trajectory_not_closed")
    sidecar_failures = list(base.diagnostic_sidecar_failures)
    try:
        sidecar = sidecar_builder(trajectory)
    except Exception as exc:
        sidecar = None
        sidecar_failures.append(
            "diagnostic_sidecar:"
            + type(exc).__name__.casefold()
            + ":"
            + canonical_hash(str(exc), prefix="diagnostic_sidecar_error:").split(":", 1)[-1]
        )
    channels = build_instrument_failure_channels(
        raw_lineage_failures=base.raw_lineage_failures,
        provider_capture_failures=base.provider_capture_failures,
        runtime_replay_failures=replay_failures,
        scoring_core_failures=base.scoring_core_failures,
        diagnostic_sidecar_failures=sidecar_failures,
        resource_failures=resource_failures,
        report_aggregation_failures=base.report_aggregation_failures,
    )
    ordered_checks = dict(
        sorted((str(key), bool(value)) for key, value in non_replay_checks.items())
    )
    if not replay_passed:
        terminal: CoreTerminal = "instrument_failure"
    elif independent_valid and all(ordered_checks.values()):
        terminal = "valid_trajectory"
    else:
        terminal = "invalid_trajectory"
    values = {
        "source_kind": source_kind,
        "trajectory_id": trajectory.trajectory_id,
        "task_id": trajectory.task_id,
        "replay_result_id": replay_result_id,
        "replay_passed": replay_passed,
        "non_replay_checks": ordered_checks,
        "independent_valid": independent_valid,
        "core_terminal": terminal,
        "trace_sidecar": sidecar,
        "resource_budget_audit_id": resource_budget_audit_id,
        "resource_budget_status": resource_budget_status,
        "failure_channels": channels,
        "instrument_admitted": (
            channels.instrument_gate_passed
            and channels.report_complete
            and resource_budget_status != "failed"
            and terminal != "instrument_failure"
        ),
        "empirical_denominator_eligible": source_kind == "model_generated",
        "compiler_fixture_excluded_from_empirical_counts": (source_kind == "compiler_fixture"),
    }
    provisional = CompletedTrajectoryScore.model_construct(score_id="pending", **values)
    return CompletedTrajectoryScore(
        score_id=completed_trajectory_score_id(provisional),
        **values,
    )


def compiler_witness_trajectory(
    *,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    witness: BoundPublicExecutableWitness,
    observations: Sequence[AgentToolObservation],
) -> Trajectory:
    history = tuple(observations)
    if tuple(item.observation_id for item in history) != tuple(
        item.observation_id for item in witness.steps
    ):
        raise ValueError("Compiler trajectory observations do not match its Witness")
    tools = environment.tools_by_id
    steps: list[TrajectoryStep] = [
        TrajectoryStep(
            step_index=1,
            action=ActionType.PLAN,
            observation={
                "compiler_witness_id": witness.witness_id,
                "path_strategy_id": witness.path_strategy_id,
            },
            rationale_summary="Compiler-generated public reference plan.",
            status=StepStatus.SUCCEEDED,
        )
    ]
    previous_observation_id: str | None = None
    for item in history:
        spec = tools[item.call.tool_id]
        operator = item.call.arguments.get("operator")
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=spec.trajectory_action,
                tool_name=item.call.tool_id,
                tool_input=item.call.arguments,
                observation=item.model_dump(mode="json"),
                evidence_ids=item.evidence_ids,
                operator_id=operator if isinstance(operator, str) else None,
                input_refs=(
                    (f"observation:{previous_observation_id}",)
                    if previous_observation_id is not None
                    else ()
                ),
                output_ref=f"observation:{item.observation_id}",
                rationale_summary=f"Compiler executed public tool {item.call.tool_id}.",
                status=(StepStatus.SUCCEEDED if item.status == "succeeded" else StepStatus.FAILED),
            )
        )
        previous_observation_id = item.observation_id
    steps.append(
        TrajectoryStep(
            step_index=len(steps) + 1,
            action=ActionType.ANSWER,
            observation={"cited_evidence_ids": witness.cited_evidence_ids},
            evidence_ids=witness.cited_evidence_ids,
            input_refs=tuple(f"observation:{item.observation_id}" for item in history),
            rationale_summary="Compiler projected the verified terminal result.",
            status=StepStatus.SUCCEEDED,
        )
    )
    values = {
        "task_id": record.task_package.task.public.task_id,
        "workflow_kind": WorkflowKind.REFERENCE,
        "steps": tuple(steps),
        "program_execution": {
            "execution_source": "compiler_public_runtime_witness",
            "environment_manifest_id": environment.manifest_id,
            "observation_ids": tuple(item.observation_id for item in history),
            "witness_id": witness.witness_id,
        },
        "final_answer": {
            "result": witness.normalized_answer,
            "citations": [{"evidence_id": item} for item in witness.cited_evidence_ids],
        },
        "generator_version": V26_COMPILER_TRAJECTORY_VERSION,
    }
    provisional = Trajectory(trajectory_id="pending", **values)
    return Trajectory(
        trajectory_id=canonical_hash(
            provisional.model_dump(mode="json", exclude={"trajectory_id"}),
            prefix="finance_v26_budget_closed_compiler_trajectory:",
        ),
        **values,
    )


def instrument_failure_channels_id(value: InstrumentFailureChannels) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"channel_id"}),
        prefix="finance_v26_budget_closed_failure_channels:",
    )


def schema_closed_trace_sidecar_id(value: SchemaClosedTraceSidecar) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"sidecar_id"}),
        prefix="finance_v26_schema_closed_trace_sidecar:",
    )


def completed_trajectory_score_id(value: CompletedTrajectoryScore) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"score_id"}),
        prefix="finance_v26_budget_closed_completed_trajectory_score:",
    )
