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
    agent_tool_argument_rejection,
    make_agent_tool_observation,
)

ITERATIVE_AGENT_SOLVER_VERSION = "iterative_agent_solver.v14"
ITERATIVE_AGENT_PLAN_PROMPT_VERSION = "iterative_agent_plan_prompt.v8"
ITERATIVE_AGENT_DECISION_PROMPT_VERSION = "iterative_agent_decision_prompt.v12"
ITERATIVE_AGENT_AUDIT_VERSION = "iterative_agent_audit.v13"

ITERATIVE_AGENT_FAILURE_ARTIFACT_VERSION = "iterative_agent_failure_artifact.v10"
MAXIMUM_STOP_REJECTIONS = 2
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
InitialPlanMode = Literal["model_contract", "implicit_public"]
ObservationView = Literal["full", "compact"]
DecisionType = Literal["tool_call", "final_answer"]
StopRejectionCode = Literal[
    "missing_observed_evidence",
    "missing_required_verification",
    "missing_required_evidence_selection",
    "missing_required_calculation",
    "invalid_final_answer_contract",
]
ContractT = TypeVar("ContractT", bound=BaseModel)


class IterativeAgentProtocolProfile(BaseModel):
    """Domain-neutral controls that isolate protocol friction from Agent capability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    initial_plan_mode: InitialPlanMode = "model_contract"
    observation_view: ObservationView = "full"
    contract_repair_token_reserve: int = Field(default=0, ge=0)
    final_answer_token_reserve: int = Field(default=0, ge=0)
    host_repair_missing_verification: bool = False

    @property
    def profile_hash(self) -> str:
        return canonical_hash(self, prefix="iterative_agent_protocol_profile:")


class PublicAgentStateCondition(BaseModel):
    """Model-visible behavior recipe; opaque quotient-state identities stay Host-only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_sequence: tuple[ActionType, ...] = Field(min_length=1)
    tool_sequence: tuple[str, ...] = Field(min_length=1)
    minimum_successful_tool_calls: int = Field(ge=1)
    minimum_verification_calls: int = Field(ge=0)
    query_policy: Literal[
        "single_query_allowed",
        "reformulation_allowed",
        "reformulation_required",
    ]
    recovery_policy: Literal[
        "recovery_not_required",
        "recover_if_tool_fails",
    ]
    stop_policy: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_condition(self) -> PublicAgentStateCondition:
        if len(self.tool_sequence) != len(self.action_sequence):
            raise ValueError("public Agent condition actions and tools must align")
        if self.minimum_successful_tool_calls > len(self.tool_sequence):
            raise ValueError("public Agent condition requires more calls than its tool sequence")
        if self.minimum_verification_calls > self.tool_sequence.count("cross_check_evidence"):
            raise ValueError("public Agent condition verification count exceeds its tool sequence")
        return self

    @property
    def condition_hash(self) -> str:
        return canonical_hash(self, prefix="public_agent_state_condition:")


class AgentLoopPlanContract(BaseModel):
    """Compact public plan, not hidden chain-of-thought."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_summary: str = Field(min_length=1, max_length=240)
    subgoal_labels: tuple[str, ...] = Field(min_length=2, max_length=6)
    stop_conditions: tuple[str, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def validate_compact_plan(self) -> AgentLoopPlanContract:
        if any(len(item) > 64 for item in self.subgoal_labels):
            raise ValueError("Agent plan subgoal labels must not exceed 64 characters")
        if any(len(item) > 96 for item in self.stop_conditions):
            raise ValueError("Agent plan stop conditions must not exceed 96 characters")
        return self


class AgentLoopDecisionContract(BaseModel):
    """One model decision. Tool execution and observations remain Host-owned."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_type: DecisionType
    rationale_summary: str = Field(min_length=1, max_length=512)
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


class AgentScriptedToolContract(BaseModel):
    """Arguments for one Host-selected tool in the scripted control arm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rationale_summary: str = Field(min_length=1, max_length=512)
    arguments: dict[str, Any]


class AgentFinalAnswerContract(BaseModel):
    """Final public answer, separated from action selection to reduce ambiguity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rationale_summary: str = Field(min_length=1, max_length=512)
    answer: dict[str, Any]
    cited_evidence_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_citations(self) -> AgentFinalAnswerContract:
        if len(self.cited_evidence_ids) != len(set(self.cited_evidence_ids)):
            raise ValueError("final_answer contains duplicate Evidence citations")
        return self


class AgentStopRejection(BaseModel):
    """Host feedback for a premature or structurally invalid stop decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_index: int = Field(ge=0)
    reason_code: StopRejectionCode
    feedback: str = Field(min_length=1, max_length=600)


class IterativeAgentAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    mode: InteractiveAgentMode
    model_config_hash: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    protocol_profile_hash: str = Field(min_length=1)
    public_state_condition_hash: str | None = None
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
    host_forced_verification_call_count: int = Field(default=0, ge=0)
    stopped_by_model: bool = True
    host_forced_final_answer: bool = False
    completed: Literal[True] = True
    stop_rejections: tuple[AgentStopRejection, ...] = ()
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
        if self.mode == "scripted_tool" and self.host_forced_verification_call_count:
            raise ValueError("scripted Agent audit cannot contain Host-forced verification calls")
        if self.stopped_by_model == self.host_forced_final_answer:
            raise ValueError("Agent stop authority accounting is inconsistent")
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


class IterativeAgentFailureArtifact(BaseModel):
    """Replayable public progress retained when an iterative solve fails closed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    mode: InteractiveAgentMode
    environment_manifest_id: str = Field(min_length=1)
    protocol_profile_hash: str = Field(min_length=1)
    plan: AgentLoopPlanContract | None = None
    decisions: tuple[AgentLoopDecisionContract, ...] = ()
    observations: tuple[AgentToolObservation, ...] = ()
    telemetry: tuple[ModelCallTelemetry, ...]
    failure_message: str = Field(min_length=1)
    stop_rejections: tuple[AgentStopRejection, ...] = ()
    schema_version: str = ITERATIVE_AGENT_FAILURE_ARTIFACT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> IterativeAgentFailureArtifact:
        if self.artifact_id != iterative_agent_failure_artifact_id(self):
            raise ValueError("iterative Agent failure Artifact identity is invalid")
        return self


def iterative_agent_failure_artifact_id(value: IterativeAgentFailureArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="iterative_agent_failure_artifact:",
    )


class IterativeAgentSolver:
    """Model decides one public action at a time; Host executes and records every observation."""

    def __init__(
        self,
        client: JsonCompletionClient,
        *,
        mode: InteractiveAgentMode,
        maximum_total_tokens: int,
        scripted_tool_sequence: tuple[str, ...] = (),
        protocol_profile: IterativeAgentProtocolProfile | None = None,
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
        self._protocol_profile = protocol_profile or IterativeAgentProtocolProfile()
        reserved = (
            self._protocol_profile.contract_repair_token_reserve
            + self._protocol_profile.final_answer_token_reserve
        )
        if reserved >= maximum_total_tokens:
            raise ValueError("interactive Agent protocol reserves exhaust the token budget")

    def solve_with_audit(
        self,
        task: TaskPublicSpec,
        runtime: InteractiveAgentToolRuntime,
        *,
        public_state_condition: PublicAgentStateCondition | None = None,
    ) -> IterativeAgentSolveResult:
        manifest = runtime.manifest
        _assert_no_model_forbidden_fields(task.model_dump(mode="json", exclude_none=True))
        _assert_no_model_forbidden_fields(manifest.model_dump(mode="json", exclude_none=True))
        if public_state_condition is not None:
            condition_payload = public_state_condition.model_dump(mode="json")
            _assert_no_model_forbidden_fields(condition_payload)
        else:
            condition_payload = None
        selectable = {item.tool_id: item for item in manifest.tools if item.model_selectable}
        if not selectable:
            raise ValueError("interactive Agent runtime exposes no selectable tool")
        verification_tool_ids = tuple(
            sorted(
                tool_id for tool_id, spec in selectable.items() if spec.semantic_role == "verify"
            )
        )
        if TaskRequirement.VERIFY_RESULT in task.requirements and not verification_tool_ids:
            raise ValueError("task requires verification but exposes no verification tool")
        unknown_scripted = set(self._scripted_tool_sequence) - set(selectable)
        if unknown_scripted:
            raise ValueError(f"scripted Agent sequence contains unknown tools: {unknown_scripted}")
        if len(self._scripted_tool_sequence) > manifest.maximum_tool_calls:
            raise ValueError("scripted Agent sequence exceeds the environment tool budget")
        if public_state_condition is not None:
            unknown_condition_tools = set(public_state_condition.tool_sequence) - set(selectable)
            if unknown_condition_tools:
                raise ValueError(
                    "public Agent condition contains unknown tools: "
                    f"{sorted(unknown_condition_tools)}"
                )
            if len(public_state_condition.tool_sequence) > manifest.maximum_tool_calls:
                raise ValueError("public Agent condition exceeds the environment tool budget")

        telemetry: list[ModelCallTelemetry] = []
        if self._protocol_profile.initial_plan_mode == "model_contract":
            plan_prompt = _plan_prompt(
                task,
                _model_visible_environment(manifest, consumed_tool_calls=0),
                self._mode,
                condition_payload,
            )
            try:
                plan, plan_telemetry, plan_repairs = _request_contract(
                    self._client,
                    plan_prompt,
                    AgentLoopPlanContract,
                )
            except LLMClientError as exc:
                artifact = _make_failure_artifact(
                    task=task,
                    mode=self._mode,
                    environment_manifest_id=manifest.manifest_id,
                    protocol_profile_hash=self._protocol_profile.profile_hash,
                    plan=None,
                    decisions=(),
                    observations=(),
                    telemetry=exc.telemetry,
                    failure_message=str(exc),
                )
                raise LLMClientError(str(exc), exc.telemetry, failure_artifact=artifact) from exc
            telemetry.extend(plan_telemetry)
            _enforce_token_budget(telemetry, self._maximum_total_tokens)
            repair_count = plan_repairs
        else:
            plan = _implicit_public_plan(task)
            plan_prompt = _implicit_plan_manifest(task, self._mode, condition_payload)
            repair_count = 0
        observations: list[AgentToolObservation] = []
        decisions: list[AgentLoopDecisionContract] = []
        prompt_hashes: list[str] = []
        failed_count = 0
        total_observation_bytes = 0
        final_decision: AgentLoopDecisionContract | None = None
        scripted_step_index = 0
        stop_rejections: list[AgentStopRejection] = []
        host_forced_final_answer = False
        host_forced_verification_call_count = 0

        def failure(message: str) -> LLMClientError:
            return _iterative_failure(
                message,
                task=task,
                mode=self._mode,
                environment_manifest_id=manifest.manifest_id,
                protocol_profile_hash=self._protocol_profile.profile_hash,
                plan=plan,
                decisions=tuple(decisions),
                observations=tuple(observations),
                telemetry=tuple(telemetry),
                stop_rejections=tuple(stop_rejections),
            )

        while final_decision is None:
            if len(observations) > manifest.maximum_tool_calls:
                raise failure("Agent exceeded the frozen tool-call budget")
            host_repair_tool = (
                verification_tool_ids[0]
                if self._mode == "autonomous_agent"
                and self._protocol_profile.host_repair_missing_verification
                and stop_rejections
                and stop_rejections[-1].reason_code == "missing_required_verification"
                and host_forced_verification_call_count < len(stop_rejections)
                and _unmet_action_requirements(task, tuple(observations), selectable)
                == (TaskRequirement.VERIFY_RESULT,)
                else None
            )
            expected_tool = (
                self._scripted_tool_sequence[scripted_step_index]
                if self._mode == "scripted_tool"
                and scripted_step_index < len(self._scripted_tool_sequence)
                else host_repair_tool
            )
            force_final = self._should_reserve_final_answer(
                task,
                tuple(observations),
                selectable,
                telemetry,
            )
            if expected_tool is not None:
                expected_spec = selectable[expected_tool]
                decision_prompt = _scripted_tool_prompt(
                    task,
                    expected_spec.model_dump(mode="json"),
                    plan,
                    tuple(observations),
                    mode=self._mode,
                    scripted_step_index=(
                        scripted_step_index if self._mode == "scripted_tool" else None
                    ),
                    remaining_tool_ids=(
                        self._scripted_tool_sequence[scripted_step_index:]
                        if self._mode == "scripted_tool"
                        else (expected_tool,)
                    ),
                    host_repair_reason=(
                        "missing_required_verification" if host_repair_tool else None
                    ),
                    public_state_condition=condition_payload,
                    host_feedback=tuple(item.feedback for item in stop_rejections),
                    observation_view=self._protocol_profile.observation_view,
                )
                response_type: type[BaseModel] = AgentScriptedToolContract
            elif self._mode == "scripted_tool":
                decision_prompt = _final_answer_prompt(
                    task,
                    plan,
                    tuple(observations),
                    public_state_condition=condition_payload,
                    host_feedback=tuple(item.feedback for item in stop_rejections),
                    mode=self._mode,
                    observation_view=self._protocol_profile.observation_view,
                )
                response_type = AgentFinalAnswerContract
            elif force_final:
                host_forced_final_answer = True
                decision_prompt = _final_answer_prompt(
                    task,
                    plan,
                    tuple(observations),
                    public_state_condition=condition_payload,
                    host_feedback=tuple(item.feedback for item in stop_rejections),
                    mode=self._mode,
                    observation_view=self._protocol_profile.observation_view,
                )
                response_type = AgentFinalAnswerContract
            else:
                decision_prompt = _decision_prompt(
                    task,
                    _model_visible_environment(
                        manifest,
                        consumed_tool_calls=len(observations),
                    ),
                    plan,
                    tuple(observations),
                    mode=self._mode,
                    expected_tool=None,
                    public_state_condition=condition_payload,
                    host_feedback=tuple(item.feedback for item in stop_rejections),
                    observation_view=self._protocol_profile.observation_view,
                )
                response_type = AgentLoopDecisionContract
            prompt_hashes.append(canonical_hash(decision_prompt, prefix="agent_decision_prompt:"))
            try:
                response, decision_telemetry, decision_repairs = _request_contract(
                    self._client,
                    decision_prompt,
                    response_type,
                )
            except LLMClientError as exc:
                telemetry.extend(exc.telemetry)
                raise failure(str(exc)) from exc
            if isinstance(response, AgentScriptedToolContract):
                decision = AgentLoopDecisionContract(
                    decision_type="tool_call",
                    rationale_summary=response.rationale_summary,
                    tool_id=expected_tool,
                    arguments=response.arguments,
                )
                if host_repair_tool is not None:
                    host_forced_verification_call_count += 1
            elif isinstance(response, AgentFinalAnswerContract):
                decision = AgentLoopDecisionContract(
                    decision_type="final_answer",
                    rationale_summary=response.rationale_summary,
                    answer=response.answer,
                    cited_evidence_ids=response.cited_evidence_ids,
                )
            else:
                if not isinstance(response, AgentLoopDecisionContract):
                    raise TypeError("unexpected iterative Agent response contract")
                decision = response
            telemetry.extend(decision_telemetry)
            try:
                _enforce_token_budget(telemetry, self._maximum_total_tokens)
            except LLMClientError as exc:
                raise failure(str(exc)) from exc
            repair_count += decision_repairs
            _assert_no_model_forbidden_fields(decision.model_dump(mode="json", exclude_none=True))
            decisions.append(decision)
            if decision.decision_type == "final_answer":
                rejection_code: StopRejectionCode | None = None
                rejection_feedback = ""
                unmet = _unmet_action_requirements(
                    task,
                    tuple(observations),
                    selectable,
                )
                if not observations or TaskRequirement.RETRIEVE_EVIDENCE in unmet:
                    rejection_code = "missing_observed_evidence"
                    rejection_feedback = (
                        "Final answer rejected: use at least one public tool and observed Evidence "
                        "before stopping."
                    )
                elif TaskRequirement.SELECT_EVIDENCE in unmet:
                    rejection_code = "missing_required_evidence_selection"
                    rejection_feedback = (
                        "Final answer rejected: select exact Evidence with a successful inspect "
                        "or structured-query tool before calculation or stopping."
                    )
                elif TaskRequirement.CALCULATE in unmet:
                    rejection_code = "missing_required_calculation"
                    rejection_feedback = (
                        "Final answer rejected: execute a successful calculation from selected "
                        "Evidence before verification or stopping."
                    )
                elif TaskRequirement.VERIFY_RESULT in unmet:
                    rejection_code = "missing_required_verification"
                    rejection_feedback = (
                        "Final answer rejected: run a verification tool that returns verified=true "
                        "after the required calculation, then stop."
                    )
                else:
                    try:
                        _validate_final_answer(task, decision, tuple(observations), selectable)
                    except LLMClientError as exc:
                        rejection_code = "invalid_final_answer_contract"
                        rejection_feedback = f"Final answer rejected: {exc}"
                if rejection_code is not None:
                    stop_rejections.append(
                        AgentStopRejection(
                            decision_index=len(decisions) - 1,
                            reason_code=rejection_code,
                            feedback=rejection_feedback,
                        )
                    )
                    if len(stop_rejections) > MAXIMUM_STOP_REJECTIONS:
                        raise failure("Agent exceeded the frozen stop-rejection budget")
                    continue
                final_decision = decision
                break
            if len(observations) >= manifest.maximum_tool_calls:
                raise failure("Agent exhausted the frozen tool-call budget")
            tool_id = decision.tool_id or ""
            _assert_no_model_forbidden_fields(decision.arguments or {})
            spec = selectable.get(tool_id)
            if spec is None:
                raise failure(f"Agent selected an unavailable tool: {tool_id}")
            call = AgentToolCall(
                call_index=len(observations) + 1,
                tool_id=tool_id,
                arguments=decision.arguments or {},
            )
            failed_signatures: set[str] = set()
            for item in reversed(observations):
                if item.status == "succeeded":
                    break
                failed_signatures.add(_tool_call_signature(item.call))
            if _tool_call_signature(call) in failed_signatures:
                raise failure("Agent repeated an identical failed tool call")
            result = agent_tool_argument_rejection(spec, call) or _execute_tool(runtime, call)
            _assert_no_model_forbidden_fields(result.result)
            if result.status == "succeeded":
                try:
                    spec.validate_output(result.result)
                except ValueError as exc:
                    raise failure(str(exc)) from exc
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
                raise failure("Agent exceeded the frozen observation-byte budget")
            observations.append(observation)
            if self._mode == "scripted_tool" and observation.status == "succeeded":
                scripted_step_index += 1
            failed_count += int(observation.status == "failed")
            if failed_count > manifest.maximum_failed_tool_calls:
                raise failure("Agent exceeded the frozen failed-tool budget")

        trajectory = _make_trajectory(
            task,
            plan,
            tuple(decisions),
            tuple(observations),
            final_decision,
            tuple(stop_rejections),
            manifest.manifest_id,
            {tool_id: item.trajectory_action for tool_id, item in selectable.items()},
        )
        successful_count = sum(item.status == "succeeded" for item in observations)
        verification_count = sum(
            _successful_verification(item, selectable) for item in observations
        )
        audit_values = {
            "task_id": task.task_id,
            "mode": self._mode,
            "model_config_hash": self._client.config.public_manifest_hash,
            "environment_manifest_id": manifest.manifest_id,
            "protocol_profile_hash": self._protocol_profile.profile_hash,
            "public_state_condition_hash": (
                public_state_condition.condition_hash
                if public_state_condition is not None
                else None
            ),
            "plan_prompt_hash": canonical_hash(plan_prompt, prefix="agent_plan_prompt:"),
            "decision_prompt_hashes": tuple(prompt_hashes),
            "observation_ids": tuple(item.observation_id for item in observations),
            "observation_content_hashes": tuple(item.content_hash for item in observations),
            "scripted_tool_sequence": self._scripted_tool_sequence,
            "successful_tool_call_count": successful_count,
            "stop_rejections": tuple(stop_rejections),
            "failed_tool_call_count": failed_count,
            "error_recovery_count": _error_recovery_count(tuple(observations)),
            "verification_tool_call_count": verification_count,
            "total_observation_bytes": total_observation_bytes,
            "maximum_total_tokens": self._maximum_total_tokens,
            "total_model_tokens": _total_model_tokens(telemetry),
            "contract_repair_count": repair_count,
            "telemetry": tuple(telemetry),
            "stopped_by_model": not host_forced_final_answer,
            "host_forced_verification_call_count": (host_forced_verification_call_count),
            "host_forced_final_answer": host_forced_final_answer,
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

    def _should_reserve_final_answer(
        self,
        task: TaskPublicSpec,
        observations: tuple[AgentToolObservation, ...],
        selectable: dict[str, Any],
        telemetry: list[ModelCallTelemetry],
    ) -> bool:
        if self._mode != "autonomous_agent" or not observations:
            return False
        profile = self._protocol_profile
        reserve = profile.contract_repair_token_reserve + profile.final_answer_token_reserve
        if reserve == 0 or _total_model_tokens(telemetry) < self._maximum_total_tokens - reserve:
            return False
        if not any(item.status == "succeeded" and item.evidence_ids for item in observations):
            return False
        return not _unmet_action_requirements(task, observations, selectable)


def iterative_agent_audit_id(value: IterativeAgentAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="iterative_agent_audit:",
    )


def _make_failure_artifact(
    *,
    task: TaskPublicSpec,
    mode: InteractiveAgentMode,
    environment_manifest_id: str,
    protocol_profile_hash: str,
    plan: AgentLoopPlanContract | None,
    decisions: tuple[AgentLoopDecisionContract, ...],
    observations: tuple[AgentToolObservation, ...],
    stop_rejections: tuple[AgentStopRejection, ...] = (),
    telemetry: tuple[ModelCallTelemetry, ...],
    failure_message: str,
) -> IterativeAgentFailureArtifact:
    values = {
        "task_id": task.task_id,
        "mode": mode,
        "environment_manifest_id": environment_manifest_id,
        "protocol_profile_hash": protocol_profile_hash,
        "plan": plan,
        "decisions": decisions,
        "observations": observations,
        "stop_rejections": stop_rejections,
        "telemetry": telemetry,
        "failure_message": failure_message,
        "schema_version": ITERATIVE_AGENT_FAILURE_ARTIFACT_VERSION,
    }
    provisional = IterativeAgentFailureArtifact.model_construct(
        artifact_id="pending",
        **values,
    )
    return IterativeAgentFailureArtifact(
        artifact_id=iterative_agent_failure_artifact_id(provisional),
        **values,
    )


def _iterative_failure(
    message: str,
    *,
    task: TaskPublicSpec,
    mode: InteractiveAgentMode,
    environment_manifest_id: str,
    protocol_profile_hash: str,
    plan: AgentLoopPlanContract | None,
    decisions: tuple[AgentLoopDecisionContract, ...],
    observations: tuple[AgentToolObservation, ...],
    stop_rejections: tuple[AgentStopRejection, ...] = (),
    telemetry: tuple[ModelCallTelemetry, ...],
) -> LLMClientError:
    artifact = _make_failure_artifact(
        task=task,
        mode=mode,
        environment_manifest_id=environment_manifest_id,
        protocol_profile_hash=protocol_profile_hash,
        plan=plan,
        decisions=decisions,
        observations=observations,
        stop_rejections=stop_rejections,
        telemetry=telemetry,
        failure_message=message,
    )
    return LLMClientError(message, telemetry, failure_artifact=artifact)


def _request_contract(
    client: JsonCompletionClient,
    base_prompt: str,
    model_type: type[ContractT],
) -> tuple[ContractT, tuple[ModelCallTelemetry, ...], int]:
    telemetry: list[ModelCallTelemetry] = []
    validation_error = ""
    previous_payload_keys: tuple[str, ...] = ()
    expected_fields = tuple(model_type.model_fields)
    maximum_attempt = client.config.contract_repair_attempts
    for attempt in range(maximum_attempt + 1):
        repair_note = json.dumps(
            {
                "validation_error": validation_error[:1200],
                "previous_payload_keys": previous_payload_keys,
                "required_json_fields": expected_fields,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        prompt = (
            base_prompt
            if attempt == 0
            else base_prompt
            + "\nCONTRACT_REPAIR_JSON:\n"
            + repair_note
            + "\nReturn only the corrected response object. Do not copy PUBLIC_CONTEXT_JSON."
        )
        try:
            payload, call = client.complete_json(prompt)
        except LLMClientError as exc:
            telemetry.extend(exc.telemetry)
            validation_error = f"provider_or_json_error:{exc}"[:1200]
            previous_payload_keys = ()
            if attempt == maximum_attempt:
                break
            continue
        previous_payload_keys = tuple(sorted(str(key) for key in payload))
        try:
            return model_type.model_validate(payload), (*telemetry, call), attempt
        except ValidationError as exc:
            validation_error = "; ".join(
                f"{'.'.join(str(item) for item in error['loc'])}:{error['msg']}"
                for error in exc.errors()
            )[:1200]
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


def _tool_call_signature(call: AgentToolCall) -> str:
    """Call identity excludes the monotonic Host index so retries are comparable."""

    return canonical_hash(
        {"tool_id": call.tool_id, "arguments": call.arguments},
        prefix="agent_tool_call_semantics:",
    )


_ACTION_REQUIREMENT_ROLES: dict[TaskRequirement, frozenset[str]] = {
    TaskRequirement.RETRIEVE_EVIDENCE: frozenset({"acquire", "inspect", "query"}),
    TaskRequirement.SELECT_EVIDENCE: frozenset({"inspect", "query"}),
    TaskRequirement.CALCULATE: frozenset({"calculate"}),
    TaskRequirement.VERIFY_RESULT: frozenset({"verify"}),
}
_ACTION_REQUIREMENT_ORDER = (
    TaskRequirement.RETRIEVE_EVIDENCE,
    TaskRequirement.SELECT_EVIDENCE,
    TaskRequirement.CALCULATE,
    TaskRequirement.VERIFY_RESULT,
)


def _tool_semantic_role(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("semantic_role") or "")
    return str(getattr(tool, "semantic_role", ""))


def _successful_verification(
    observation: AgentToolObservation,
    tools_by_id: dict[str, Any],
) -> bool:
    if observation.status != "succeeded":
        return False
    tool = tools_by_id.get(observation.call.tool_id)
    if tool is None or _tool_semantic_role(tool) != "verify":
        return False
    verified = observation.result.get("verified")
    return verified is True


def _successful_semantic_roles(
    observations: tuple[AgentToolObservation, ...],
    tools_by_id: dict[str, Any],
) -> frozenset[str]:
    return frozenset(
        _tool_semantic_role(tools_by_id[item.call.tool_id])
        for item in observations
        if item.status == "succeeded" and item.call.tool_id in tools_by_id
    )


def _unmet_action_requirements(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    tools_by_id: dict[str, Any],
) -> tuple[TaskRequirement, ...]:
    roles = _successful_semantic_roles(observations, tools_by_id)
    unmet: list[TaskRequirement] = []
    for requirement in _ACTION_REQUIREMENT_ORDER:
        if requirement not in task.requirements:
            continue
        if requirement == TaskRequirement.VERIFY_RESULT:
            passed = any(_successful_verification(item, tools_by_id) for item in observations)
        else:
            passed = bool(roles & _ACTION_REQUIREMENT_ROLES[requirement])
        if not passed:
            unmet.append(requirement)
    return tuple(unmet)


def _stop_readiness_payload(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    tools_by_id: dict[str, Any],
) -> dict[str, Any]:
    required = tuple(item for item in _ACTION_REQUIREMENT_ORDER if item in task.requirements)
    unmet = _unmet_action_requirements(task, observations, tools_by_id)
    return {
        "required_action_requirements": tuple(item.value for item in required),
        "completed_semantic_roles": tuple(
            sorted(_successful_semantic_roles(observations, tools_by_id))
        ),
        "unmet_action_requirements": tuple(item.value for item in unmet),
        "final_answer_allowed": not unmet,
        "required_order": tuple(item.value for item in required),
    }


def _validate_final_answer(
    task: TaskPublicSpec,
    decision: AgentLoopDecisionContract,
    observations: tuple[AgentToolObservation, ...],
    tools_by_id: dict[str, Any],
) -> None:
    unmet = _unmet_action_requirements(task, observations, tools_by_id)
    if unmet:
        raise LLMClientError(
            f"Agent stopped with unmet public requirements: {[item.value for item in unmet]}"
        )
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


def _make_trajectory(
    task: TaskPublicSpec,
    plan: AgentLoopPlanContract,
    decisions: tuple[AgentLoopDecisionContract, ...],
    observations: tuple[AgentToolObservation, ...],
    final_decision: AgentLoopDecisionContract,
    stop_rejections: tuple[AgentStopRejection, ...],
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
    rejection_by_decision = {item.decision_index: item for item in stop_rejections}
    observation_index = 0
    accepted_answer_count = 0
    for decision_index, decision in enumerate(decisions):
        if decision.decision_type == "tool_call":
            if observation_index >= len(observations):
                raise ValueError("iterative Agent trajectory lost a Host observation")
            observation = observations[observation_index]
            input_refs = (
                (f"observation:{observations[observation_index - 1].observation_id}",)
                if observation_index > 0
                else ()
            )
            steps.append(
                TrajectoryStep(
                    step_index=len(steps) + 1,
                    action=action_by_tool_id[observation.call.tool_id],
                    tool_name=observation.call.tool_id,
                    tool_input=observation.call.arguments,
                    observation=observation.model_dump(mode="json"),
                    evidence_ids=observation.evidence_ids,
                    input_refs=input_refs,
                    output_ref=f"observation:{observation.observation_id}",
                    rationale_summary=decision.rationale_summary,
                    status=(
                        StepStatus.SUCCEEDED
                        if observation.status == "succeeded"
                        else StepStatus.FAILED
                    ),
                )
            )
            observation_index += 1
            continue

        rejection = rejection_by_decision.get(decision_index)
        if rejection is not None:
            steps.append(
                TrajectoryStep(
                    step_index=len(steps) + 1,
                    action=ActionType.ANSWER,
                    observation={
                        "host_rejection_reason": rejection.reason_code,
                        "host_feedback": rejection.feedback,
                        "cited_evidence_ids": decision.cited_evidence_ids,
                    },
                    evidence_ids=decision.cited_evidence_ids,
                    input_refs=tuple(
                        f"observation:{item.observation_id}"
                        for item in observations[:observation_index]
                    ),
                    rationale_summary=decision.rationale_summary,
                    status=StepStatus.FAILED,
                )
            )
            continue

        if decision != final_decision:
            raise ValueError("iterative Agent trajectory contains an unclassified stop decision")
        accepted_answer_count += 1
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType.ANSWER,
                observation={"cited_evidence_ids": final_decision.cited_evidence_ids},
                evidence_ids=final_decision.cited_evidence_ids,
                input_refs=tuple(
                    f"observation:{item.observation_id}"
                    for item in observations[:observation_index]
                ),
                rationale_summary=final_decision.rationale_summary,
                status=StepStatus.SUCCEEDED,
            )
        )
    if observation_index != len(observations):
        raise ValueError("iterative Agent trajectory has unbound Host observations")
    if accepted_answer_count != 1:
        raise ValueError("iterative Agent trajectory requires one accepted final answer")
    values = {
        "task_id": task.task_id,
        "workflow_kind": WorkflowKind.CANDIDATE,
        "steps": tuple(steps),
        "program_execution": {
            "execution_source": "host_iterative_tool_runtime",
            "environment_manifest_id": environment_manifest_id,
            "observation_ids": tuple(item.observation_id for item in observations),
            "stop_rejections": tuple(item.model_dump(mode="json") for item in stop_rejections),
        },
        "final_answer": {
            "result": final_decision.answer or {},
            "citations": [
                {"evidence_id": evidence_id} for evidence_id in final_decision.cited_evidence_ids
            ],
        },
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


def _model_visible_environment(
    manifest: Any,
    *,
    consumed_tool_calls: int,
) -> dict[str, Any]:
    """Compact public tool surface; immutable hashes remain in the Host audit."""

    return {
        "environment_id": manifest.environment_id,
        "snapshot_id": manifest.snapshot_id,
        "network_policy": manifest.network_policy,
        "remaining_tool_calls": max(0, manifest.maximum_tool_calls - consumed_tool_calls),
        "maximum_failed_tool_calls": manifest.maximum_failed_tool_calls,
        "tools": [
            {
                "tool_id": item.tool_id,
                "semantic_role": item.semantic_role,
                "description": item.description,
                "required_input_fields": item.required_input_fields,
                "input_contract": item.input_contract,
            }
            for item in manifest.tools
            if item.model_selectable
        ],
    }


def _model_visible_observations(
    observations: tuple[AgentToolObservation, ...],
    *,
    view: ObservationView,
) -> list[dict[str, Any]]:
    if view == "full":
        return [_full_observation_view(item) for item in observations]
    return [_compact_observation_view(item) for item in observations]


def _full_observation_view(item: AgentToolObservation) -> dict[str, Any]:
    return {
        "observation_id": item.observation_id,
        "call_index": item.call.call_index,
        "tool_id": item.call.tool_id,
        "arguments": item.call.arguments,
        "status": item.status,
        "result": item.result,
        "evidence_ids": item.evidence_ids,
        "error_code": item.error_code,
        "error_message": item.error_message,
    }


def _compact_observation_view(item: AgentToolObservation) -> dict[str, Any]:
    value = {
        "call_index": item.call.call_index,
        "tool_id": item.call.tool_id,
        "arguments": item.call.arguments,
        "status": item.status,
        "evidence_ids": item.evidence_ids,
    }
    if item.status == "succeeded":
        value["result"] = _compact_public_value(item.result)
    else:
        value["error_code"] = item.error_code
        value["error_message"] = item.error_message
    return value


_COMPACT_OMITTED_KEYS = frozenset(
    {
        "content_hash",
        "observation_id",
        "operation_hash",
        "policy_hash",
        "provenance_hash",
        "query_hash",
        "snapshot_hash",
        "source_locator_hash",
        "verification_hash",
    }
)


def _compact_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _compact_public_value(item)
            for key, item in value.items()
            if str(key) not in _COMPACT_OMITTED_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_compact_public_value(item) for item in value]
    return value


def _implicit_public_plan(task: TaskPublicSpec) -> AgentLoopPlanContract:
    labels = [item.value for item in task.requirements[:6]]
    while len(labels) < 2:
        labels.append("produce_answer")
    conditions = ["required Evidence observed", "answer schema satisfied"]
    if TaskRequirement.VERIFY_RESULT in task.requirements:
        conditions.insert(1, "verification succeeded")
    return AgentLoopPlanContract(
        plan_summary="Use public tools to retrieve, compute, verify, and answer the task.",
        subgoal_labels=tuple(labels),
        stop_conditions=tuple(conditions),
    )


def _implicit_plan_manifest(
    task: TaskPublicSpec,
    mode: InteractiveAgentMode,
    public_state_condition: dict[str, Any] | None,
) -> str:
    return _json_contract_prompt(
        "Host-declared implicit public plan; no model call was made.",
        {
            "prompt_version": ITERATIVE_AGENT_PLAN_PROMPT_VERSION,
            "mode": mode,
            "public_behavior_condition": public_state_condition,
            "task_id": task.task_id,
            "requirements": [item.value for item in task.requirements],
        },
    )


def _model_visible_task(task: TaskPublicSpec) -> dict[str, Any]:
    retrieval_scope = {
        key: value for key, value in task.retrieval_scope.items() if key != "corpus_boundary"
    }
    visible = {
        "task_id": task.task_id,
        "domain": task.domain,
        "task_type": task.task_type,
        "instruction": task.instruction,
        "requirements": [item.value for item in task.requirements],
        "retrieval_track": task.retrieval_track.value,
        "retrieval_scope": retrieval_scope,
        "answer_schema": task.answer_schema,
        "answer_field_contract": {
            "required_fields": tuple(sorted(required_answer_fields(task.answer_schema))),
            "allowed_fields": tuple(sorted(allowed_result_fields(task.answer_schema))),
            "additional_fields_allowed": False,
        },
    }
    guidance = task.metadata.get("agent_contract_guidance")
    if guidance is not None:
        visible["agent_contract_guidance"] = guidance
    return visible


def _json_contract_prompt(instruction: str, context: dict[str, Any]) -> str:
    return (
        instruction
        + "\nPUBLIC_CONTEXT_JSON:\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _plan_prompt(
    task: TaskPublicSpec,
    environment_manifest: dict[str, Any],
    mode: InteractiveAgentMode,
    public_state_condition: dict[str, Any] | None,
) -> str:
    tool_summary = [
        {
            "tool_id": item["tool_id"],
            "semantic_role": item["semantic_role"],
            "description": item["description"],
        }
        for item in environment_manifest["tools"]
    ]
    return _json_contract_prompt(
        "Return only one compact JSON object with exactly these keys: plan_summary, "
        "subgoal_labels, stop_conditions. Do not copy the task or context. Use 2-6 short "
        "subgoal labels and 1-4 observable stop conditions. Do not provide hidden "
        "chain-of-thought. plan_summary <=240 characters; each label <=64; each stop "
        "condition <=96.",
        {
            "prompt_version": ITERATIVE_AGENT_PLAN_PROMPT_VERSION,
            "mode": mode,
            "public_behavior_condition": public_state_condition,
            "task": _model_visible_task(task),
            "tool_environment": {
                "network_policy": environment_manifest["network_policy"],
                "remaining_tool_calls": environment_manifest["remaining_tool_calls"],
                "tools": tool_summary,
            },
        },
    )


def _scripted_tool_prompt(
    task: TaskPublicSpec,
    expected_tool: dict[str, Any],
    plan: AgentLoopPlanContract,
    observations: tuple[AgentToolObservation, ...],
    *,
    mode: InteractiveAgentMode,
    scripted_step_index: int | None,
    remaining_tool_ids: tuple[str, ...],
    host_repair_reason: str | None,
    public_state_condition: dict[str, Any] | None,
    host_feedback: tuple[str, ...],
    observation_view: ObservationView,
) -> str:
    return _json_contract_prompt(
        "The Host has frozen the next tool. Return only one JSON object with exactly "
        "rationale_summary and arguments. Do not return tool_id, a final answer, the task, "
        "or the context. Fill arguments for the specified tool contract. Follow scripted "
        "progress in order; when a tool repeats, perform the next unresolved operation and "
        "never reference an operation output before creating it. Search results are "
        "discovered candidates only; Evidence becomes selected only after open_document or "
        "query_structured_fact succeeds. Copy subject, metric, and period selector strings "
        "verbatim from successful public observations; never shorten a period label. JSON "
        "operand forms such as {operation_ref, selector} must be actual JSON objects, never "
        "encoded strings. Copy operation_ref verbatim from the prior successful calculator "
        "observation. A selector is relative to its result.result.output object: use 'value' "
        "for scalar output and never use 'output' or 'output.value'. Never invent a short "
        "operation name. Never repeat identical arguments after a failure. Keep "
        "rationale_summary must be one short sentence of at most 240 characters. Do not "
        "provide hidden chain-of-thought.",
        {
            "prompt_version": ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
            "mode": mode,
            "host_control": "scripted_progress" if scripted_step_index is not None else "repair",
            "public_behavior_condition": public_state_condition,
            "task": _model_visible_task(task),
            "plan": plan.model_dump(mode="json"),
            "expected_tool": {
                "tool_id": expected_tool["tool_id"],
                "description": expected_tool["description"],
                "required_input_fields": expected_tool["required_input_fields"],
                "input_contract": expected_tool["input_contract"],
            },
            "scripted_progress": {
                "step_index": scripted_step_index,
                "remaining_tool_ids": remaining_tool_ids,
                "host_repair_reason": host_repair_reason,
            },
            "host_feedback": host_feedback,
            "observations": _model_visible_observations(observations, view=observation_view),
        },
    )


def _final_answer_prompt(
    task: TaskPublicSpec,
    plan: AgentLoopPlanContract,
    observations: tuple[AgentToolObservation, ...],
    *,
    public_state_condition: dict[str, Any] | None,
    host_feedback: tuple[str, ...],
    mode: InteractiveAgentMode,
    observation_view: ObservationView,
) -> str:
    return _json_contract_prompt(
        "Return only one JSON object with exactly rationale_summary, answer, and "
        "cited_evidence_ids. answer must follow the public answer_schema exactly. Cite only "
        "Evidence IDs present in successful observations. Copy the exact terminal successful "
        "calculator result into the answer: do not round values, rename reference IDs, or "
        "change numeric types. Use exactly the keys listed in task.answer_field_contract; never "
        "add context, unit, result_context, or operation fields unless that exact key is allowed. "
        "Follow answer_schema and agent_contract_guidance exactly. Do not add a tool call or copy "
        "the task/context. rationale_summary must be one short sentence of at most 240 "
        "characters.",
        {
            "prompt_version": ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
            "mode": mode,
            "public_behavior_condition": public_state_condition,
            "task": _model_visible_task(task),
            "plan": plan.model_dump(mode="json"),
            "host_feedback": host_feedback,
            "observations": _model_visible_observations(observations, view=observation_view),
        },
    )


def _decision_prompt(
    task: TaskPublicSpec,
    environment_manifest: dict[str, Any],
    plan: AgentLoopPlanContract,
    observations: tuple[AgentToolObservation, ...],
    *,
    mode: InteractiveAgentMode,
    expected_tool: str | None,
    public_state_condition: dict[str, Any] | None,
    host_feedback: tuple[str, ...],
    observation_view: ObservationView,
) -> str:
    if mode != "autonomous_agent" or expected_tool is not None:
        raise ValueError("autonomous decision prompt received scripted control state")
    tools_by_id = {str(item["tool_id"]): item for item in environment_manifest["tools"]}
    readiness = _stop_readiness_payload(task, observations, tools_by_id)
    return _json_contract_prompt(
        "Return only one compact JSON object. Choose one next public action. For a tool call "
        "use exactly decision_type, rationale_summary, tool_id, arguments, answer=null, and "
        "cited_evidence_ids=[]. For a final answer use decision_type, rationale_summary, "
        "tool_id=null, arguments=null, answer, and cited_evidence_ids. Search results are "
        "discovered candidates only; select Evidence with open_document or "
        "query_structured_fact before normalize, calculator, cross-check, or citation. "
        "stop_readiness is a binding Host contract: final_answer is forbidden while "
        "final_answer_allowed=false. Satisfy the first unmet action requirement with a tool. "
        "When calculation is required, it must succeed before verification; verification must "
        "return verified=true. Never repeat an identical failed call. "
        "Copy subject, metric, and period selector strings verbatim from successful public "
        "observations; never shorten a period label. JSON operand forms such as "
        "{operation_ref, selector} must be actual JSON objects, never encoded strings. "
        "Copy operation_ref verbatim from a successful calculator observation. A selector is "
        "relative to result.result.output: use 'value' for scalar output and never use "
        "'output' or 'output.value'. Never invent a short operation name. "
        "For a final answer, copy the exact terminal successful calculator result without "
        "rounding values, renaming reference IDs, or changing numeric types; follow "
        "answer_schema and agent_contract_guidance exactly. Address any Host feedback before "
        "stopping. rationale_summary must be one short sentence of at most 240 characters. "
        "Do not copy the task/context or "
        "provide hidden chain-of-thought.",
        {
            "prompt_version": ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
            "mode": mode,
            "public_behavior_condition": public_state_condition,
            "task": _model_visible_task(task),
            "plan": plan.model_dump(mode="json"),
            "tool_environment": environment_manifest,
            "stop_readiness": readiness,
            "host_feedback": host_feedback,
            "observations": _model_visible_observations(observations, view=observation_view),
        },
    )
