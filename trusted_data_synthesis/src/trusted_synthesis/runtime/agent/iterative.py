from __future__ import annotations

import json
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.core.task.answer_schema import allowed_result_fields, required_answer_fields
from trusted_synthesis.core.task.schema import TaskPublicSpec, TaskRequirement
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import JsonCompletionClient, LLMClientError
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolObservation,
    AgentToolResult,
    InteractiveAgentToolRuntime,
    make_agent_tool_observation,
)

ITERATIVE_AGENT_SOLVER_VERSION = "iterative_agent_solver.v1"
ITERATIVE_AGENT_PLAN_PROMPT_VERSION = "iterative_agent_plan_prompt.v1"
ITERATIVE_AGENT_DECISION_PROMPT_VERSION = "iterative_agent_decision_prompt.v1"
ITERATIVE_AGENT_AUDIT_VERSION = "iterative_agent_audit.v1"

MODEL_FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "answer_payload",
        "gold_evidence_ids",
        "gold_answer",
        "oracle",
        "oracle_contract",
        "oracle_program",
        "task_program",
        "reference_answer",
        "proof_graph",
        "target_quotient_state",
        "target_state_id",
    }
)

InteractiveAgentMode = Literal["scripted_tool", "autonomous_agent"]
DecisionType = Literal["tool_call", "final_answer"]
ContractT = TypeVar("ContractT", bound=BaseModel)


class AgentLoopPlanContract(BaseModel):
    """Compact public plan, not hidden chain-of-thought."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_summary: str = Field(min_length=1)
    subgoal_labels: tuple[str, ...] = Field(min_length=1)
    stop_conditions: tuple[str, ...] = Field(min_length=1)


class AgentLoopDecisionContract(BaseModel):
    """One model decision. Tool execution and observations remain Host-owned."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_type: DecisionType
    rationale_summary: str = Field(min_length=1)
    tool_id: str | None = None
    arguments: dict[str, Any] | None = None
    answer: dict[str, Any] | None = None
    cited_evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_decision(self) -> AgentLoopDecisionContract:
        if self.decision_type == "tool_call":
            if not self.tool_id or self.arguments is None:
                raise ValueError("tool_call requires tool_id and arguments")
            if self.answer is not None or self.cited_evidence_ids:
                raise ValueError("tool_call cannot contain a final answer or citations")
        else:
            if self.tool_id is not None or self.arguments is not None:
                raise ValueError("final_answer cannot contain a tool call")
            if self.answer is None or not self.cited_evidence_ids:
                raise ValueError("final_answer requires an answer and Evidence citations")
            if len(self.cited_evidence_ids) != len(set(self.cited_evidence_ids)):
                raise ValueError("final_answer contains duplicate Evidence citations")
        return self


class IterativeAgentAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    mode: InteractiveAgentMode
    model_config_hash: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    plan_prompt_hash: str = Field(min_length=1)
    decision_prompt_hashes: tuple[str, ...] = Field(min_length=1)
    observation_ids: tuple[str, ...] = Field(min_length=1)
    observation_content_hashes: tuple[str, ...] = Field(min_length=1)
    scripted_tool_sequence: tuple[str, ...] = ()
    successful_tool_call_count: int = Field(ge=0)
    failed_tool_call_count: int = Field(ge=0)
    error_recovery_count: int = Field(ge=0)
    verification_tool_call_count: int = Field(ge=0)
    total_observation_bytes: int = Field(ge=0)
    maximum_total_tokens: int = Field(ge=1)
    total_model_tokens: int = Field(ge=1)
    contract_repair_count: int = Field(ge=0)
    telemetry: tuple[ModelCallTelemetry, ...] = Field(min_length=1)
    stopped_by_model: Literal[True] = True
    completed: Literal[True] = True
    schema_version: str = ITERATIVE_AGENT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IterativeAgentAudit:
        if len(self.observation_ids) != len(self.observation_content_hashes):
            raise ValueError("Agent audit observation identity accounting is inconsistent")
        if self.successful_tool_call_count + self.failed_tool_call_count != len(
            self.observation_ids
        ):
            raise ValueError("Agent audit tool-call accounting is inconsistent")
        if self.total_model_tokens > self.maximum_total_tokens:
            raise ValueError("Agent audit exceeds its frozen model-token budget")
        if self.mode == "scripted_tool" and not self.scripted_tool_sequence:
            raise ValueError("scripted Agent audit requires a tool sequence")
        if self.mode == "autonomous_agent" and self.scripted_tool_sequence:
            raise ValueError("autonomous Agent audit cannot contain a scripted sequence")
        if self.audit_id != iterative_agent_audit_id(self):
            raise ValueError("iterative Agent audit identity is invalid")
        return self


class IterativeAgentSolveResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trajectory: Trajectory
    audit: IterativeAgentAudit
    observations: tuple[AgentToolObservation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result(self) -> IterativeAgentSolveResult:
        if self.trajectory.task_id != self.audit.task_id:
            raise ValueError("iterative Agent result crosses task identities")
        if tuple(item.observation_id for item in self.observations) != self.audit.observation_ids:
            raise ValueError("iterative Agent result lost Host observations")
        return self


class IterativeAgentSolver:
    """Model decides one public action at a time; Host executes and records every observation."""

    def __init__(
        self,
        client: JsonCompletionClient,
        *,
        mode: InteractiveAgentMode,
        maximum_total_tokens: int,
        scripted_tool_sequence: tuple[str, ...] = (),
    ) -> None:
        if maximum_total_tokens < 1:
            raise ValueError("interactive Agent requires a positive token budget")
        if mode == "scripted_tool" and not scripted_tool_sequence:
            raise ValueError("scripted Agent mode requires a nonempty tool sequence")
        if mode == "autonomous_agent" and scripted_tool_sequence:
            raise ValueError("autonomous Agent mode cannot receive a scripted tool sequence")
        self._client = client
        self._mode = mode
        self._maximum_total_tokens = maximum_total_tokens
        self._scripted_tool_sequence = scripted_tool_sequence

    def solve_with_audit(
        self,
        task: TaskPublicSpec,
        runtime: InteractiveAgentToolRuntime,
    ) -> IterativeAgentSolveResult:
        manifest = runtime.manifest
        _assert_no_model_forbidden_fields(task.model_dump(mode="json", exclude_none=True))
        _assert_no_model_forbidden_fields(manifest.model_dump(mode="json", exclude_none=True))
        selectable = {item.tool_id: item for item in manifest.tools if item.model_selectable}
        if not selectable:
            raise ValueError("interactive Agent runtime exposes no selectable tool")
        unknown_scripted = set(self._scripted_tool_sequence) - set(selectable)
        if unknown_scripted:
            raise ValueError(f"scripted Agent sequence contains unknown tools: {unknown_scripted}")
        if len(self._scripted_tool_sequence) > manifest.maximum_tool_calls:
            raise ValueError("scripted Agent sequence exceeds the environment tool budget")

        telemetry: list[ModelCallTelemetry] = []
        plan_prompt = _plan_prompt(task, manifest.model_dump(mode="json"), self._mode)
        plan, plan_telemetry, plan_repairs = _request_contract(
            self._client,
            plan_prompt,
            AgentLoopPlanContract,
        )
        telemetry.extend(plan_telemetry)
        _enforce_token_budget(telemetry, self._maximum_total_tokens)
        repair_count = plan_repairs
        observations: list[AgentToolObservation] = []
        decisions: list[AgentLoopDecisionContract] = []
        prompt_hashes: list[str] = []
        failed_count = 0
        total_observation_bytes = 0
        final_decision: AgentLoopDecisionContract | None = None

        while final_decision is None:
            if len(observations) > manifest.maximum_tool_calls:
                raise LLMClientError("Agent exceeded the frozen tool-call budget", tuple(telemetry))
            expected_tool = (
                self._scripted_tool_sequence[len(observations)]
                if self._mode == "scripted_tool"
                and len(observations) < len(self._scripted_tool_sequence)
                else None
            )
            decision_prompt = _decision_prompt(
                task,
                manifest.model_dump(mode="json"),
                plan,
                tuple(observations),
                mode=self._mode,
                expected_tool=expected_tool,
            )
            prompt_hashes.append(canonical_hash(decision_prompt, prefix="agent_decision_prompt:"))
            decision, decision_telemetry, decision_repairs = _request_contract(
                self._client,
                decision_prompt,
                AgentLoopDecisionContract,
            )
            telemetry.extend(decision_telemetry)
            _enforce_token_budget(telemetry, self._maximum_total_tokens)
            repair_count += decision_repairs
            _assert_no_model_forbidden_fields(decision.model_dump(mode="json", exclude_none=True))
            decisions.append(decision)
            if expected_tool is not None and (
                decision.decision_type != "tool_call" or decision.tool_id != expected_tool
            ):
                raise LLMClientError(
                    "scripted Agent changed the frozen tool sequence",
                    tuple(telemetry),
                )
            if (
                self._mode == "scripted_tool"
                and expected_tool is None
                and decision.decision_type != "final_answer"
            ):
                raise LLMClientError(
                    "scripted Agent attempted an extra tool call",
                    tuple(telemetry),
                )
            if decision.decision_type == "final_answer":
                if not observations:
                    raise LLMClientError(
                        "interactive Agent stopped without using a tool",
                        tuple(telemetry),
                    )
                final_decision = decision
                break
            if len(observations) >= manifest.maximum_tool_calls:
                raise LLMClientError(
                    "Agent exhausted the frozen tool-call budget", tuple(telemetry)
                )
            tool_id = decision.tool_id or ""
            _assert_no_model_forbidden_fields(decision.arguments or {})
            spec = selectable.get(tool_id)
            if spec is None:
                raise LLMClientError(
                    f"Agent selected an unavailable tool: {tool_id}", tuple(telemetry)
                )
            try:
                spec.validate_arguments(decision.arguments or {})
            except ValueError as exc:
                raise LLMClientError(str(exc), tuple(telemetry)) from exc
            call = AgentToolCall(
                call_index=len(observations) + 1,
                tool_id=tool_id,
                arguments=decision.arguments or {},
            )
            result = _execute_tool(runtime, call)
            _assert_no_model_forbidden_fields(result.result)
            if result.status == "succeeded":
                try:
                    spec.validate_output(result.result)
                except ValueError as exc:
                    raise LLMClientError(str(exc), tuple(telemetry)) from exc
            observation = make_agent_tool_observation(
                environment_manifest_id=manifest.manifest_id,
                call=call,
                result=result,
                observation_time_hash=canonical_hash(
                    {
                        "snapshot_id": manifest.snapshot_id,
                        "call_index": call.call_index,
                    },
                    prefix="agent_observation_time:",
                ),
            )
            observation_bytes = len(
                json.dumps(
                    observation.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            total_observation_bytes += observation_bytes
            if total_observation_bytes > manifest.maximum_total_observation_bytes:
                raise LLMClientError(
                    "Agent exceeded the frozen observation-byte budget",
                    tuple(telemetry),
                )
            observations.append(observation)
            failed_count += int(observation.status == "failed")
            if failed_count > manifest.maximum_failed_tool_calls:
                raise LLMClientError(
                    "Agent exceeded the frozen failed-tool budget",
                    tuple(telemetry),
                )

        _validate_final_answer(task, final_decision, tuple(observations), selectable)
        trajectory = _make_trajectory(
            task,
            plan,
            tuple(decisions),
            tuple(observations),
            final_decision,
            manifest.manifest_id,
            {tool_id: item.trajectory_action for tool_id, item in selectable.items()},
        )
        successful_count = sum(item.status == "succeeded" for item in observations)
        verification_count = sum(
            item.status == "succeeded" and selectable[item.call.tool_id].semantic_role == "verify"
            for item in observations
        )
        audit_values = {
            "task_id": task.task_id,
            "mode": self._mode,
            "model_config_hash": self._client.config.public_manifest_hash,
            "environment_manifest_id": manifest.manifest_id,
            "plan_prompt_hash": canonical_hash(plan_prompt, prefix="agent_plan_prompt:"),
            "decision_prompt_hashes": tuple(prompt_hashes),
            "observation_ids": tuple(item.observation_id for item in observations),
            "observation_content_hashes": tuple(item.content_hash for item in observations),
            "scripted_tool_sequence": self._scripted_tool_sequence,
            "successful_tool_call_count": successful_count,
            "failed_tool_call_count": failed_count,
            "error_recovery_count": _error_recovery_count(tuple(observations)),
            "verification_tool_call_count": verification_count,
            "total_observation_bytes": total_observation_bytes,
            "maximum_total_tokens": self._maximum_total_tokens,
            "total_model_tokens": _total_model_tokens(telemetry),
            "contract_repair_count": repair_count,
            "telemetry": tuple(telemetry),
            "stopped_by_model": True,
            "completed": True,
            "schema_version": ITERATIVE_AGENT_AUDIT_VERSION,
        }
        provisional = IterativeAgentAudit.model_construct(audit_id="pending", **audit_values)
        audit = IterativeAgentAudit(
            audit_id=iterative_agent_audit_id(provisional),
            **audit_values,
        )
        return IterativeAgentSolveResult(
            trajectory=trajectory,
            audit=audit,
            observations=tuple(observations),
        )


def iterative_agent_audit_id(value: IterativeAgentAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="iterative_agent_audit:",
    )


def _request_contract(
    client: JsonCompletionClient,
    base_prompt: str,
    model_type: type[ContractT],
) -> tuple[ContractT, tuple[ModelCallTelemetry, ...], int]:
    telemetry: list[ModelCallTelemetry] = []
    validation_error = ""
    previous_payload: dict[str, Any] | None = None
    for attempt in range(client.config.contract_repair_attempts + 1):
        prompt = (
            base_prompt
            if attempt == 0
            else base_prompt
            + "\nThe previous JSON failed validation. Return a corrected JSON object only.\n"
            + json.dumps(
                {"previous_payload": previous_payload, "validation_error": validation_error},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        payload, call = client.complete_json(prompt)
        previous_payload = payload
        try:
            return model_type.model_validate(payload), (*telemetry, call), attempt
        except ValidationError as exc:
            validation_error = "; ".join(
                f"{'.'.join(str(item) for item in error['loc'])}:{error['msg']}"
                for error in exc.errors()
            )
            telemetry.append(
                call.model_copy(
                    update={
                        "json_contract_success": False,
                        "error_type": "IterativeAgentContractError",
                        "error_message": validation_error,
                        "contract_errors": (validation_error,),
                    }
                )
            )
    raise LLMClientError("model failed the iterative Agent contract", tuple(telemetry))


def _total_model_tokens(telemetry: list[ModelCallTelemetry]) -> int:
    totals = [item.total_tokens for item in telemetry]
    if any(item is None for item in totals):
        raise LLMClientError(
            "Agent provider omitted required token usage telemetry",
            tuple(telemetry),
        )
    return sum(int(item) for item in totals if item is not None)


def _enforce_token_budget(
    telemetry: list[ModelCallTelemetry],
    maximum_total_tokens: int,
) -> None:
    if _total_model_tokens(telemetry) > maximum_total_tokens:
        raise LLMClientError("Agent exceeded the frozen model-token budget", tuple(telemetry))


def _execute_tool(
    runtime: InteractiveAgentToolRuntime,
    call: AgentToolCall,
) -> AgentToolResult:
    try:
        return runtime.execute(call)
    except Exception as exc:
        return AgentToolResult(
            status="failed",
            result={},
            error_code=f"runtime_exception:{type(exc).__name__}",
            error_message=str(exc) or type(exc).__name__,
        )


def _validate_final_answer(
    task: TaskPublicSpec,
    decision: AgentLoopDecisionContract,
    observations: tuple[AgentToolObservation, ...],
    tools_by_id: dict[str, Any],
) -> None:
    answer = decision.answer or {}
    missing_fields = set(required_answer_fields(task.answer_schema)) - set(answer)
    if missing_fields:
        raise LLMClientError(f"Agent final answer is missing fields: {sorted(missing_fields)}")
    unknown_fields = set(answer) - allowed_result_fields(task.answer_schema)
    if unknown_fields:
        raise LLMClientError(
            f"Agent final answer contains unknown fields: {sorted(unknown_fields)}"
        )
    available_evidence = {evidence_id for item in observations for evidence_id in item.evidence_ids}
    unknown_citations = set(decision.cited_evidence_ids) - available_evidence
    if unknown_citations:
        raise LLMClientError(f"Agent cited unobserved Evidence: {sorted(unknown_citations)}")
    if TaskRequirement.VERIFY_RESULT in task.requirements and not any(
        item.status == "succeeded" and tools_by_id[item.call.tool_id].semantic_role == "verify"
        for item in observations
    ):
        raise LLMClientError("Agent stopped without required result verification")


def _make_trajectory(
    task: TaskPublicSpec,
    plan: AgentLoopPlanContract,
    decisions: tuple[AgentLoopDecisionContract, ...],
    observations: tuple[AgentToolObservation, ...],
    final_decision: AgentLoopDecisionContract,
    environment_manifest_id: str,
    action_by_tool_id: dict[str, ActionType],
) -> Trajectory:
    steps = [
        TrajectoryStep(
            step_index=1,
            action=ActionType.PLAN,
            observation={
                "subgoal_labels": plan.subgoal_labels,
                "stop_conditions": plan.stop_conditions,
            },
            rationale_summary=plan.plan_summary,
            status=StepStatus.SUCCEEDED,
        )
    ]
    tool_decisions = [item for item in decisions if item.decision_type == "tool_call"]
    for index, (decision, observation) in enumerate(
        zip(tool_decisions, observations, strict=True),
        start=2,
    ):
        steps.append(
            TrajectoryStep(
                step_index=index,
                action=action_by_tool_id[observation.call.tool_id],
                tool_name=observation.call.tool_id,
                tool_input=observation.call.arguments,
                observation=observation.model_dump(mode="json"),
                evidence_ids=observation.evidence_ids,
                input_refs=(
                    (f"observation:{observations[index - 3].observation_id}",) if index > 2 else ()
                ),
                output_ref=f"observation:{observation.observation_id}",
                rationale_summary=decision.rationale_summary,
                status=(
                    StepStatus.SUCCEEDED if observation.status == "succeeded" else StepStatus.FAILED
                ),
            )
        )
    steps.append(
        TrajectoryStep(
            step_index=len(steps) + 1,
            action=ActionType.ANSWER,
            observation={"cited_evidence_ids": final_decision.cited_evidence_ids},
            evidence_ids=final_decision.cited_evidence_ids,
            input_refs=tuple(f"observation:{item.observation_id}" for item in observations),
            rationale_summary=final_decision.rationale_summary,
            status=StepStatus.SUCCEEDED,
        )
    )
    values = {
        "task_id": task.task_id,
        "workflow_kind": WorkflowKind.CANDIDATE,
        "steps": tuple(steps),
        "program_execution": {
            "execution_source": "host_iterative_tool_runtime",
            "environment_manifest_id": environment_manifest_id,
            "observation_ids": tuple(item.observation_id for item in observations),
        },
        "final_answer": final_decision.answer or {},
        "generator_version": ITERATIVE_AGENT_SOLVER_VERSION,
    }
    return Trajectory(
        trajectory_id=canonical_hash(values, prefix="iterative_agent_trajectory:"),
        **values,
    )


def _error_recovery_count(observations: tuple[AgentToolObservation, ...]) -> int:
    return sum(
        current.status == "failed" and later.status == "succeeded"
        for current, later in zip(observations, observations[1:], strict=False)
    )


def _assert_no_model_forbidden_fields(value: Any, *, path: str = "public") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in MODEL_FORBIDDEN_FIELD_NAMES:
                raise ValueError(f"model-visible payload contains forbidden field at {path}.{key}")
            _assert_no_model_forbidden_fields(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_model_forbidden_fields(item, path=f"{path}[{index}]")


def _plan_prompt(
    task: TaskPublicSpec,
    environment_manifest: dict[str, Any],
    mode: InteractiveAgentMode,
) -> str:
    return json.dumps(
        {
            "prompt_version": ITERATIVE_AGENT_PLAN_PROMPT_VERSION,
            "instruction": (
                "Return a compact public plan. Do not provide hidden chain-of-thought. "
                "You cannot see Gold Evidence IDs, the Oracle program, or the reference answer."
            ),
            "mode": mode,
            "task": task.model_dump(mode="json", exclude_none=True),
            "tool_environment": environment_manifest,
            "response_contract": {
                "plan_summary": "string",
                "subgoal_labels": ["short public labels"],
                "stop_conditions": ["observable conditions"],
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _decision_prompt(
    task: TaskPublicSpec,
    environment_manifest: dict[str, Any],
    plan: AgentLoopPlanContract,
    observations: tuple[AgentToolObservation, ...],
    *,
    mode: InteractiveAgentMode,
    expected_tool: str | None,
) -> str:
    return json.dumps(
        {
            "prompt_version": ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
            "instruction": (
                "Choose exactly one next public action. The Host executes tools. Return only "
                "a rationale summary, never hidden chain-of-thought. Stop only when the answer "
                "is supported by observed Evidence and required verification is complete."
            ),
            "mode": mode,
            "expected_scripted_tool": expected_tool,
            "task": task.model_dump(mode="json", exclude_none=True),
            "plan": plan.model_dump(mode="json"),
            "tool_environment": environment_manifest,
            "observations": [item.model_dump(mode="json") for item in observations],
            "response_contract": {
                "tool_call": {
                    "decision_type": "tool_call",
                    "rationale_summary": "string",
                    "tool_id": "string",
                    "arguments": {},
                    "answer": None,
                    "cited_evidence_ids": [],
                },
                "final_answer": {
                    "decision_type": "final_answer",
                    "rationale_summary": "string",
                    "tool_id": None,
                    "arguments": None,
                    "answer": {},
                    "cited_evidence_ids": ["observed Evidence IDs"],
                },
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )
