from __future__ import annotations

import hashlib
from typing import Any

import pytest
from pydantic import BaseModel

from trusted_synthesis.core.task.answer_schema import required_answer_fields
from trusted_synthesis.core.task.schema import TaskRequirement
from trusted_synthesis.core.trajectory.schema import ActionType, StepStatus
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.runtime.agent import (
    IterativeAgentProtocolProfile,
    IterativeAgentSolver,
)
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.iterative import (
    TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS,
    _bounded_observation_summary,
    _compact_public_value,
    _failed_action_repair_context,
    _operation_execution_progress,
    _operation_step_rejection,
    _request_contract,
    _scripted_operation_execution_progress,
    _validate_answer_observation_constraints,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolResult,
    AgentToolSpec,
    make_agent_tool_environment_manifest,
    make_agent_tool_observation,
)


class _ScriptedClient:
    def __init__(
        self, payloads: list[dict[str, Any]], *, contract_repair_attempts: int = 0
    ) -> None:
        self._payloads = iter(payloads)
        self.prompts: list[str] = []
        self._config = AgentModelConfig(
            provider="fixture",
            endpoint="https://fixture.invalid/v1/chat/completions",
            model="fixture-model",
            api_key_env="FIXTURE_API_KEY",
            contract_repair_attempts=contract_repair_attempts,
        )

    @property
    def config(self) -> AgentModelConfig:
        return self._config

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        self.prompts.append(prompt)
        payload = next(self._payloads)
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return payload, ModelCallTelemetry(
            provider="fixture",
            endpoint_host="fixture.invalid",
            model_requested="fixture-model",
            model_selected="fixture-model",
            response_model="fixture-model",
            request_hash=request_hash,
            response_hash=hashlib.sha256(repr(payload).encode("utf-8")).hexdigest(),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            prompt_tokens=6,
            completion_tokens=4,
            total_tokens=10,
        )


class _ScalarContract(BaseModel):
    value: int


class _TransientThenValidClient:
    def __init__(self, *, failure_count: int) -> None:
        self._failure_count = failure_count
        self.prompts: list[str] = []
        self._config = AgentModelConfig(
            provider="fixture",
            endpoint="https://fixture.invalid/v1/chat/completions",
            model="fixture-model",
            api_key_env="FIXTURE_API_KEY",
            contract_repair_attempts=0,
        )

    @property
    def config(self) -> AgentModelConfig:
        return self._config

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        self.prompts.append(prompt)
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if len(self.prompts) <= self._failure_count:
            telemetry = ModelCallTelemetry(
                provider="fixture",
                endpoint_host="fixture.invalid",
                model_requested="fixture-model",
                model_selected="fixture-model",
                request_hash=request_hash,
                http_success=False,
                json_contract_success=False,
                error_type="URLError",
                error_message="temporary TLS transport failure",
            )
            raise LLMClientError("temporary TLS transport failure", (telemetry,))
        return {"value": 7}, ModelCallTelemetry(
            provider="fixture",
            endpoint_host="fixture.invalid",
            model_requested="fixture-model",
            model_selected="fixture-model",
            request_hash=request_hash,
            response_hash="response:valid",
            http_status=200,
            http_success=True,
            json_contract_success=True,
            prompt_tokens=6,
            completion_tokens=4,
            total_tokens=10,
        )


class _MissingUsageThenValidClient(_TransientThenValidClient):
    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        self.prompts.append(prompt)
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        missing = len(self.prompts) <= self._failure_count
        return {"value": 7}, ModelCallTelemetry(
            provider="fixture",
            endpoint_host="fixture.invalid",
            model_requested="fixture-model",
            model_selected="fixture-model",
            response_model="fixture-model",
            request_hash=request_hash,
            response_hash=f"response:{len(self.prompts)}",
            http_status=200,
            http_success=True,
            json_contract_success=True,
            prompt_tokens=None if missing else 6,
            completion_tokens=None if missing else 4,
            total_tokens=None if missing else 10,
        )


class _ToolRuntime:
    def __init__(
        self,
        *,
        fail_first: bool = False,
        maximum_failed_tool_calls: int | None = None,
    ) -> None:
        failed_budget = (
            (1 if fail_first else 0)
            if maximum_failed_tool_calls is None
            else maximum_failed_tool_calls
        )
        self._manifest = _tool_manifest(maximum_failed_tool_calls=failed_budget)
        self._fail_first = fail_first
        self.calls: list[AgentToolCall] = []

    @property
    def manifest(self) -> AgentToolEnvironmentManifest:
        return self._manifest

    def execute(self, call: AgentToolCall) -> AgentToolResult:
        self.calls.append(call)
        if self._fail_first and len(self.calls) == 1:
            return AgentToolResult(
                status="failed",
                result={},
                error_code="query_miss",
                error_message="no match",
            )
        return AgentToolResult(
            status="succeeded",
            result={"value": 10, "verified": call.tool_id == "verify_result"},
            evidence_ids=("evidence:public:1",),
            provenance_hashes=("provenance:test",),
        )


class _MalformedOutputRuntime(_ToolRuntime):
    def execute(self, call: AgentToolCall) -> AgentToolResult:
        self.calls.append(call)
        return AgentToolResult(
            status="succeeded",
            result={},
            evidence_ids=("evidence:public:1",),
            provenance_hashes=("provenance:test",),
        )


class _PatchRequiredRuntime(_ToolRuntime):
    def __init__(self) -> None:
        super().__init__(maximum_failed_tool_calls=1)

    def execute(self, call: AgentToolCall) -> AgentToolResult:
        self.calls.append(call)
        if len(self.calls) == 1:
            return AgentToolResult(
                status="failed",
                result={
                    "retry_contract": {
                        "policy": "argument_patch_required",
                        "maximum_identical_replays": 0,
                        "suggested_argument_patch": {"query": "reformulated query"},
                    }
                },
                error_code="selector_revision_required",
                error_message="The environment requires a changed public selector.",
            )
        if call.arguments.get("query") != "reformulated query":
            return AgentToolResult(
                status="failed",
                result={},
                error_code="selector_patch_missing",
                error_message="The required public selector patch was not applied.",
            )
        return AgentToolResult(
            status="succeeded",
            result={"value": 10, "verified": False},
            evidence_ids=("evidence:public:1",),
            provenance_hashes=("provenance:test",),
        )


class _FalseVerificationRuntime(_ToolRuntime):
    def execute(self, call: AgentToolCall) -> AgentToolResult:
        if call.tool_id != "verify_result":
            return super().execute(call)
        self.calls.append(call)
        return AgentToolResult(
            status="succeeded",
            result={"value": 10, "verified": False},
            evidence_ids=("evidence:public:1",),
            provenance_hashes=("provenance:test",),
        )


class _MissingVerificationFlagRuntime(_ToolRuntime):
    def execute(self, call: AgentToolCall) -> AgentToolResult:
        if call.tool_id != "verify_result":
            return super().execute(call)
        self.calls.append(call)
        return AgentToolResult(
            status="succeeded",
            result={"value": 10},
            evidence_ids=("evidence:public:1",),
            provenance_hashes=("provenance:test",),
        )


def _tool_manifest(*, maximum_failed_tool_calls: int) -> AgentToolEnvironmentManifest:
    tools = (
        AgentToolSpec(
            tool_id="lookup",
            tool_version="fixture.v1",
            semantic_role="query",
            trajectory_action=ActionType.SEARCH,
            description="Look up public Evidence.",
            input_contract={"query": "string"},
            output_contract={"value": "number"},
            required_input_fields=("query",),
            required_output_fields=("value",),
            allow_additional_output_fields=True,
        ),
        AgentToolSpec(
            tool_id="verify_result",
            tool_version="fixture.v1",
            semantic_role="verify",
            trajectory_action=ActionType.VERIFY,
            description="Verify a public result.",
            input_contract={"value": "number"},
            output_contract={"verified": "boolean"},
            required_input_fields=("value",),
            required_output_fields=("verified",),
            allow_additional_output_fields=True,
        ),
        AgentToolSpec(
            tool_id="calculator",
            tool_version="fixture.v1",
            semantic_role="calculate",
            trajectory_action=ActionType.CALCULATE,
            description="Calculate from selected public Evidence.",
            input_contract={"value": "number"},
            output_contract={"value": "number"},
            required_input_fields=("value",),
            required_output_fields=("value",),
            allow_additional_output_fields=True,
        ),
    )
    return make_agent_tool_environment_manifest(
        environment_id="fixture_environment",
        corpus_id="fixture_corpus",
        corpus_hash="fixture_corpus_hash",
        snapshot_id="fixture_snapshot",
        snapshot_hash="fixture_snapshot_hash",
        network_policy="forbidden",
        tools=tools,
        maximum_tool_calls=4,
        maximum_failed_tool_calls=maximum_failed_tool_calls,
        maximum_total_observation_bytes=100_000,
        tool_timeout_seconds=5,
    )


def _task_and_answer() -> tuple[Any, dict[str, Any]]:
    task = build_finance_counterfactual_cases(count=1)[0].task.public
    answer = {field: 1 for field in required_answer_fields(task.answer_schema)}
    return task, answer


def _plan() -> dict[str, Any]:
    return {
        "plan_summary": "Find public Evidence, verify it, and answer.",
        "subgoal_labels": ["retrieve", "verify"],
        "stop_conditions": ["verified Evidence supports every answer field"],
    }


def _tool_decision(tool_id: str, **arguments: Any) -> dict[str, Any]:
    return {
        "decision_type": "tool_call",
        "rationale_summary": f"Use {tool_id} for the next public step.",
        "tool_id": tool_id,
        "arguments": arguments,
        "answer": None,
        "cited_evidence_ids": [],
    }


def _answer_decision(answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_type": "final_answer",
        "rationale_summary": "The observed and verified Evidence supports the answer.",
        "tool_id": None,
        "arguments": None,
        "answer": answer,
        "cited_evidence_ids": ["evidence:public:1"],
    }


def _scripted_tool_arguments(**arguments: Any) -> dict[str, Any]:
    return {
        "rationale_summary": "Fill the Host-selected tool arguments from public context.",
        "arguments": arguments,
    }


def _scripted_answer(answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "rationale_summary": "The selected and verified Evidence supports the answer.",
        "answer": answer,
        "cited_evidence_ids": ["evidence:public:1"],
    }


def _calculator_observation(
    *,
    call_index: int,
    operator: str,
    operands: list[dict[str, Any]],
    operation_ref: str,
    output: dict[str, Any],
):
    call = AgentToolCall(
        call_index=call_index,
        tool_id="calculator",
        arguments={"operator": operator, "operands": operands, "parameters": {}},
    )
    result = AgentToolResult(
        status="succeeded",
        result={
            "result": {
                "operator": operator,
                "output": output,
                "operation_ref": operation_ref,
            },
            "operation_hash": f"hash:{call_index}",
        },
        evidence_ids=("evidence:public:1", "evidence:public:2"),
        provenance_hashes=("provenance:1", "provenance:2"),
    )
    return make_agent_tool_observation(
        environment_manifest_id="manifest:test",
        call=call,
        result=result,
        observation_time_hash=f"time:{call_index}",
    )


def _selection_observation(*, call_index: int, evidence_id: str, slot: str):
    call = AgentToolCall(
        call_index=call_index,
        tool_id="query_structured_fact",
        arguments={"slot": slot},
    )
    result = AgentToolResult(
        status="succeeded",
        result={"facts": [{"evidence_id": evidence_id, "slot": slot}]},
        evidence_ids=(evidence_id,),
        provenance_hashes=(f"provenance:{slot}",),
    )
    return make_agent_tool_observation(
        environment_manifest_id="manifest:test",
        call=call,
        result=result,
        observation_time_hash=f"selection-time:{call_index}",
    )


def _task_with_operation_contract():
    task, _ = _task_and_answer()
    return task.model_copy(
        update={
            "metadata": {
                **task.metadata,
                "agent_contract_guidance": {
                    "operation_execution_contract": {
                        "contract_version": "operation.test.v1",
                        "variables": [
                            {"symbol": "v1", "label": "first"},
                            {"symbol": "v2", "label": "second"},
                        ],
                        "steps": [
                            {
                                "step_id": "d1",
                                "tool_id": "calculator",
                                "tool_operator": "difference",
                                "inputs": ["v1", "v2"],
                                "input_selectors": [None, None],
                                "parameters": {},
                                "expression": "v2 - v1",
                            },
                            {
                                "step_id": "result",
                                "tool_id": "calculator",
                                "tool_operator": "ratio",
                                "inputs": ["d1", "v1"],
                                "input_selectors": ["value", None],
                                "parameters": {},
                                "expression": "d1 / v1",
                            },
                        ],
                        "output_step_id": "result",
                    }
                },
            }
        }
    )


def _task_with_resolved_operation_contract():
    task = _task_with_operation_contract()
    metadata = task.metadata.copy()
    guidance = metadata["agent_contract_guidance"].copy()
    contract = guidance["operation_execution_contract"].copy()
    contract["variables"] = [
        {
            "symbol": "v1",
            "selection_match": {
                "collection_selector": ["facts"],
                "evidence_id_selector": ["evidence_id"],
                "equals": [{"selector": ["slot"], "value": "first"}],
            },
        },
        {
            "symbol": "v2",
            "selection_match": {
                "collection_selector": ["facts"],
                "evidence_id_selector": ["evidence_id"],
                "equals": [{"selector": ["slot"], "value": "second"}],
            },
        },
    ]
    guidance["operation_execution_contract"] = contract
    metadata["agent_contract_guidance"] = guidance
    return task.model_copy(update={"metadata": metadata})


def test_operation_progress_requires_ordered_real_operation_references() -> None:
    task = _task_with_operation_contract()
    first = _calculator_observation(
        call_index=1,
        operator="difference",
        operands=[
            {"evidence_id": "evidence:public:1"},
            {"evidence_id": "evidence:public:2"},
        ],
        operation_ref="operation:d1",
        output={"value": "2"},
    )
    progress = _operation_execution_progress(task, (first,))

    assert progress is not None
    assert progress["all_steps_completed"] is False
    assert progress["completed_step_operation_refs"] == {"d1": "operation:d1"}
    assert progress["next_required_step"]["input_resolution"][0] == {
        "input_ref": "d1",
        "source": "prior_successful_operation",
        "operation_ref": "operation:d1",
        "selector": "value",
    }

    invented = _calculator_observation(
        call_index=2,
        operator="ratio",
        operands=[
            {"operation_ref": "operation:invented", "selector": "value"},
            {"evidence_id": "evidence:public:1"},
        ],
        operation_ref="operation:wrong-result",
        output={"value": "0.2"},
    )
    unchanged = _operation_execution_progress(task, (first, invented))
    assert unchanged is not None
    assert unchanged["all_steps_completed"] is False
    assert "result" not in unchanged["completed_step_operation_refs"]

    final = _calculator_observation(
        call_index=3,
        operator="ratio",
        operands=[
            {"operation_ref": "operation:d1", "selector": "value"},
            {"evidence_id": "evidence:public:1"},
        ],
        operation_ref="operation:result",
        output={"value": "0.2"},
    )
    completed = _operation_execution_progress(task, (first, invented, final))
    assert completed is not None
    assert completed["all_steps_completed"] is True
    assert completed["terminal_operation_ref"] == "operation:result"


def test_scripted_retrieval_is_not_preempted_by_pending_calculation() -> None:
    task = _task_with_operation_contract()

    assert (
        _scripted_operation_execution_progress(
            task,
            {"tool_id": "query_structured_fact", "semantic_role": "query"},
            (),
        )
        is None
    )
    calculation_progress = _scripted_operation_execution_progress(
        task,
        {"tool_id": "calculator", "semantic_role": "calculate"},
        (),
    )
    assert calculation_progress is not None
    assert calculation_progress["next_required_step"]["step_id"] == "d1"


def test_operation_step_rejection_requires_selection_then_exact_operand_order() -> None:
    task = _task_with_resolved_operation_contract()
    first = _selection_observation(
        call_index=1,
        evidence_id="evidence:public:1",
        slot="first",
    )
    unresolved_call = AgentToolCall(
        call_index=2,
        tool_id="calculator",
        arguments={
            "operator": "difference",
            "operands": [
                {"evidence_id": "evidence:public:1"},
                {"evidence_id": "evidence:public:2"},
            ],
            "parameters": {},
        },
    )
    prerequisite = _operation_step_rejection(task, (first,), unresolved_call)
    assert prerequisite is not None
    assert prerequisite.error_code == "operation_input_not_selected"
    assert prerequisite.result["retry_contract"]["policy"] == ("prerequisite_action_required")

    second = _selection_observation(
        call_index=2,
        evidence_id="evidence:public:2",
        slot="second",
    )
    reversed_call = AgentToolCall(
        call_index=3,
        tool_id="calculator",
        arguments={
            "operator": "difference",
            "operands": [
                {"evidence_id": "evidence:public:2"},
                {"evidence_id": "evidence:public:1"},
            ],
            "parameters": {},
        },
    )
    rejected = _operation_step_rejection(task, (first, second), reversed_call)
    assert rejected is not None
    assert rejected.error_code == "operation_step_contract"
    assert rejected.result["retry_contract"]["suggested_argument_patch"] == {
        "operator": "difference",
        "operands": [
            {"evidence_id": "evidence:public:1"},
            {"evidence_id": "evidence:public:2"},
        ],
        "parameters": {},
    }


def test_terminal_observation_contract_rejects_numeric_coercion() -> None:
    task, answer = _task_and_answer()
    field = next(iter(answer))
    constrained = task.model_copy(
        update={
            "metadata": {
                **task.metadata,
                "agent_contract_guidance": {
                    "answer_observation_constraints": {
                        "source_tool_id": "calculator",
                        "source_result_selector": ["result", "output"],
                        "field_selectors": {field: ["value"]},
                        "exact_fields": [field],
                    }
                },
            }
        }
    )
    observation = _calculator_observation(
        call_index=1,
        operator="lookup",
        operands=[{"evidence_id": "evidence:public:1"}],
        operation_ref="operation:result",
        output={"value": "0.1120998852158529944857593521"},
    )

    with pytest.raises(LLMClientError, match="must exactly copy"):
        _validate_answer_observation_constraints(
            constrained,
            {field: 0.112099885215853},
            (observation,),
        )

    _validate_answer_observation_constraints(
        constrained,
        {field: "0.1120998852158529944857593521"},
        (observation,),
    )


def test_autonomous_agent_loop_preserves_host_owned_observations() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _tool_decision("verify_result", value=10),
            _answer_decision(answer),
        ]
    )
    runtime = _ToolRuntime()

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
    ).solve_with_audit(
        task,
        runtime,
    )

    assert [step.action for step in result.trajectory.steps] == [
        ActionType.PLAN,
        ActionType.SEARCH,
        ActionType.VERIFY,
        ActionType.ANSWER,
    ]
    assert result.trajectory.final_answer["result"] == answer
    assert result.trajectory.final_answer["citations"] == [{"evidence_id": "evidence:public:1"}]
    assert result.audit.successful_tool_call_count == 2
    assert result.audit.verification_tool_call_count == 1
    assert result.audit.error_recovery_count == 0
    assert result.audit.observation_ids == tuple(
        item.observation_id for item in result.observations
    )
    assert all(
        item.environment_manifest_id == runtime.manifest.manifest_id for item in result.observations
    )


def test_autonomous_agent_loop_records_failure_and_recovery() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="bad query"),
            _tool_decision("lookup", query="reformulated query"),
            _tool_decision("verify_result", value=10),
            _answer_decision(answer),
        ]
    )

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
    ).solve_with_audit(
        task,
        _ToolRuntime(fail_first=True),
    )

    assert result.audit.failed_tool_call_count == 1
    assert result.audit.error_recovery_count == 1
    assert result.observations[0].status == "failed"
    assert result.observations[1].status == "succeeded"


def test_agent_blocks_identical_failed_call_and_allows_argument_repair() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="same bad query"),
            _tool_decision("lookup", query="same bad query"),
            _tool_decision("lookup", query="reformulated query"),
            _answer_decision(answer),
        ]
    )
    runtime = _ToolRuntime(fail_first=True, maximum_failed_tool_calls=2)

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
    ).solve_with_audit(task, runtime)

    assert len(runtime.calls) == 2
    assert [item.status for item in result.observations] == [
        "failed",
        "failed",
        "succeeded",
    ]
    assert result.observations[1].error_code == "identical_failed_action_blocked"
    assert '"identical_arguments_forbidden":true' in client.prompts[3]


def test_failed_action_repair_preserves_typed_resolution_guidance() -> None:
    first = make_agent_tool_observation(
        environment_manifest_id="manifest:test",
        call=AgentToolCall(
            call_index=1,
            tool_id="cross_check_evidence",
            arguments={"claim_or_result": {"value": 10}},
        ),
        result=AgentToolResult(
            status="failed",
            result={
                "retry_contract": {
                    "policy": "prerequisite_action_required",
                    "observed_conflict_dimensions": [
                        "source_definition_compatibility"
                    ],
                    "available_resolution_actions": [
                        {
                            "tool_id": "normalize_metric_unit_period",
                            "applicable_when": (
                                "source definitions or temporal bases are incompatible"
                            ),
                        },
                        {
                            "tool_id": "open_document",
                            "applicable_when": "source provenance is incomplete",
                        },
                    ],
                    "decision_rule": "Match the observed dimension to one action.",
                }
            },
            error_code="evidence_state_conflicted",
            error_message="Evidence remains conflicted.",
        ),
        observation_time_hash="time:1",
    )
    blocked = make_agent_tool_observation(
        environment_manifest_id="manifest:test",
        call=AgentToolCall(
            call_index=2,
            tool_id="cross_check_evidence",
            arguments={"claim_or_result": {"value": 10}},
        ),
        result=AgentToolResult(
            status="failed",
            result={
                "retry_contract": {
                    "policy": "argument_patch_required",
                    "suggested_argument_patch": {"rule": "change arguments"},
                }
            },
            error_code="identical_failed_action_blocked",
            error_message="Identical failed action blocked.",
        ),
        observation_time_hash="time:2",
    )

    context = _failed_action_repair_context((first, blocked))

    assert context is not None
    assert context["failed_tool_id"] == "cross_check_evidence"
    assert context["repair_source_error_code"] == "evidence_state_conflicted"
    assert context["observed_conflict_dimensions"] == [
        "source_definition_compatibility"
    ]
    assert context["available_resolution_actions"][0]["tool_id"] == (
        "normalize_metric_unit_period"
    )
    assert context["resolution_decision_rule"] == (
        "Match the observed dimension to one action."
    )


def test_successful_intervening_action_reopens_a_failed_tool_call() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="temporarily unavailable"),
            _tool_decision("verify_result", value=10),
            _tool_decision("lookup", query="temporarily unavailable"),
            _answer_decision(answer),
        ]
    )
    runtime = _ToolRuntime(fail_first=True)

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
    ).solve_with_audit(task, runtime)

    assert [item.status for item in result.observations] == [
        "failed",
        "succeeded",
        "succeeded",
    ]
    assert [item.tool_id for item in runtime.calls] == [
        "lookup",
        "verify_result",
        "lookup",
    ]


def test_scripted_agent_host_controls_tool_order() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _scripted_tool_arguments(query="public metric"),
            _scripted_tool_arguments(value=10),
            _scripted_answer(answer),
        ]
    )
    runtime = _ToolRuntime()

    result = IterativeAgentSolver(
        client,
        mode="scripted_tool",
        maximum_total_tokens=100,
        scripted_tool_sequence=("lookup", "verify_result"),
    ).solve_with_audit(task, runtime)

    assert [item.tool_id for item in runtime.calls] == ["lookup", "verify_result"]
    assert result.audit.scripted_tool_sequence == ("lookup", "verify_result")
    assert result.trajectory.final_answer["result"] == answer
    assert all(
        '"tool_id"' not in prompt.split("PUBLIC_CONTEXT_JSON:", 1)[0]
        for prompt in client.prompts[1:]
    )
    assert '"remaining_tool_ids"' in client.prompts[1]
    assert '"verify_result"' in client.prompts[1]
    assert "never shorten a period label" in client.prompts[1]
    assert "actual JSON objects, never encoded strings" in client.prompts[1]


def test_contract_repair_does_not_replay_echoed_payload() -> None:
    task, answer = _task_and_answer()
    echoed = {"prompt_version": "echo", "padding": "x" * 10_000}
    client = _ScriptedClient(
        [
            echoed,
            _plan(),
            _answer_decision(answer),
            _answer_decision(answer),
            _answer_decision(answer),
        ],
        contract_repair_attempts=1,
    )

    with pytest.raises(LLMClientError, match="stop-rejection budget"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, _ToolRuntime())

    assert len(client.prompts) == 5
    assert "x" * 100 not in client.prompts[1]
    assert '"previous_payload":' not in client.prompts[1]
    assert "previous_payload_keys" in client.prompts[1]


def test_transient_provider_retry_preserves_prompt_and_repair_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    monkeypatch.setattr(
        "trusted_synthesis.runtime.agent.iterative.time.sleep", delays.append
    )
    client = _TransientThenValidClient(failure_count=2)

    value, telemetry, repair_count = _request_contract(
        client, "Return a scalar contract.", _ScalarContract
    )

    assert value.value == 7
    assert repair_count == 0
    assert len(telemetry) == 3
    assert [item.http_success for item in telemetry] == [False, False, True]
    assert delays == list(TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS[:2])
    assert len(set(client.prompts)) == 1


def test_transient_provider_retry_exhaustion_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    monkeypatch.setattr(
        "trusted_synthesis.runtime.agent.iterative.time.sleep", delays.append
    )
    client = _TransientThenValidClient(
        failure_count=len(TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS) + 1
    )

    with pytest.raises(LLMClientError, match="iterative Agent contract") as captured:
        _request_contract(client, "Return a scalar contract.", _ScalarContract)

    assert len(captured.value.telemetry) == 4
    assert all(not item.http_success for item in captured.value.telemetry)
    assert delays == list(TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS)
    assert len(set(client.prompts)) == 1


def test_missing_usage_telemetry_retries_without_spending_contract_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    monkeypatch.setattr(
        "trusted_synthesis.runtime.agent.iterative.time.sleep", delays.append
    )
    client = _MissingUsageThenValidClient(failure_count=2)

    value, telemetry, repair_count = _request_contract(
        client, "Return a scalar contract.", _ScalarContract
    )

    assert value.value == 7
    assert repair_count == 0
    assert len(telemetry) == 3
    assert [item.error_type for item in telemetry] == [
        "MissingTokenUsageTelemetry",
        "MissingTokenUsageTelemetry",
        None,
    ]
    assert all(item.http_success for item in telemetry)
    assert delays == list(TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS[:2])
    assert len(set(client.prompts)) == 1


def test_missing_usage_telemetry_exhaustion_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    monkeypatch.setattr(
        "trusted_synthesis.runtime.agent.iterative.time.sleep", delays.append
    )
    client = _MissingUsageThenValidClient(
        failure_count=len(TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS) + 1
    )

    with pytest.raises(LLMClientError, match="iterative Agent contract") as captured:
        _request_contract(client, "Return a scalar contract.", _ScalarContract)

    assert len(captured.value.telemetry) == 4
    assert all(
        item.error_type == "MissingTokenUsageTelemetry"
        for item in captured.value.telemetry
    )
    assert delays == list(TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS)
    assert len(set(client.prompts)) == 1


def test_agent_cannot_stop_without_observed_evidence() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient([_plan(), *(_answer_decision(answer) for _ in range(3))])

    with pytest.raises(LLMClientError, match="stop-rejection budget") as captured:
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(
            task,
            _ToolRuntime(),
        )

    artifact = captured.value.failure_artifact
    assert artifact is not None
    assert len(artifact.stop_rejections) == 3
    assert {item.reason_code for item in artifact.stop_rejections} == {"missing_observed_evidence"}


def test_agent_repairs_premature_stop_after_host_feedback() -> None:
    task, answer = _task_and_answer()
    task = task.model_copy(
        update={
            "requirements": tuple(
                dict.fromkeys((*task.requirements, TaskRequirement.VERIFY_RESULT))
            )
        }
    )
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _answer_decision(answer),
            _tool_decision("verify_result", value=10),
            _answer_decision(answer),
        ]
    )

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
    ).solve_with_audit(task, _ToolRuntime())

    answer_steps = [step for step in result.trajectory.steps if step.action == ActionType.ANSWER]
    assert [step.status for step in answer_steps] == [
        StepStatus.FAILED,
        StepStatus.SUCCEEDED,
    ]
    assert len(result.audit.stop_rejections) == 1
    assert result.audit.stop_rejections[0].reason_code == "missing_required_verification"
    assert "host_feedback" in client.prompts[3]
    assert "verification must return verified=true" in client.prompts[3]
    assert "answer_field_contract" in client.prompts[3]


def test_host_can_auditably_repair_one_missing_verification_call() -> None:
    task, answer = _task_and_answer()
    task = task.model_copy(
        update={
            "requirements": tuple(
                dict.fromkeys((*task.requirements, TaskRequirement.VERIFY_RESULT))
            )
        }
    )
    client = _ScriptedClient(
        [
            _tool_decision("lookup", query="public metric"),
            _answer_decision(answer),
            _scripted_tool_arguments(value=10),
            _answer_decision(answer),
        ]
    )
    profile = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        host_repair_missing_verification=True,
    )

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
        protocol_profile=profile,
    ).solve_with_audit(task, _ToolRuntime())

    assert [item.call.tool_id for item in result.observations] == [
        "lookup",
        "verify_result",
    ]
    assert result.audit.host_forced_verification_call_count == 1
    assert result.audit.stopped_by_model is True
    assert result.audit.host_forced_final_answer is False
    assert len(result.audit.stop_rejections) == 1
    assert result.audit.stop_rejections[0].reason_code == "missing_required_verification"
    assert '"host_control":"repair"' in client.prompts[2]
    assert '"host_repair_reason":"missing_required_verification"' in client.prompts[2]


def test_stop_readiness_requires_calculation_before_verification() -> None:
    task, answer = _task_and_answer()
    task = task.model_copy(
        update={
            "requirements": tuple(
                dict.fromkeys(
                    (
                        *task.requirements,
                        TaskRequirement.CALCULATE,
                        TaskRequirement.VERIFY_RESULT,
                    )
                )
            )
        }
    )
    client = _ScriptedClient(
        [
            _tool_decision("lookup", query="public metric"),
            _answer_decision(answer),
            _tool_decision("calculator", value=10),
            _answer_decision(answer),
            _scripted_tool_arguments(value=10),
            _answer_decision(answer),
        ]
    )
    profile = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        host_repair_missing_verification=True,
    )

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
        protocol_profile=profile,
    ).solve_with_audit(task, _ToolRuntime())

    assert [item.call.tool_id for item in result.observations] == [
        "lookup",
        "calculator",
        "verify_result",
    ]
    assert [item.reason_code for item in result.audit.stop_rejections] == [
        "missing_required_calculation",
        "missing_required_verification",
    ]
    assert result.audit.host_forced_verification_call_count == 1
    assert '"unmet_action_requirements":["calculate","verify_result"]' in client.prompts[1]
    assert '"unmet_action_requirements":["verify_result"]' in client.prompts[3]


def test_verified_false_does_not_unlock_final_answer() -> None:
    task, answer = _task_and_answer()
    task = task.model_copy(
        update={
            "requirements": tuple(
                dict.fromkeys((*task.requirements, TaskRequirement.VERIFY_RESULT))
            )
        }
    )
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _tool_decision("verify_result", value=10),
            *(_answer_decision(answer) for _ in range(3)),
        ]
    )

    with pytest.raises(LLMClientError, match="stop-rejection budget") as captured:
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, _FalseVerificationRuntime())

    artifact = captured.value.failure_artifact
    assert artifact is not None
    assert {item.reason_code for item in artifact.stop_rejections} == {
        "missing_required_verification"
    }


def test_missing_verification_flag_fails_tool_contract() -> None:
    task, _ = _task_and_answer()
    task = task.model_copy(
        update={
            "requirements": tuple(
                dict.fromkeys((*task.requirements, TaskRequirement.VERIFY_RESULT))
            )
        }
    )
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _tool_decision("verify_result", value=10),
        ]
    )

    with pytest.raises(LLMClientError, match="lacks required fields: \\['verified'\\]"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, _MissingVerificationFlagRuntime())


def test_scripted_agent_retries_same_host_tool_after_failed_observation() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _scripted_tool_arguments(query="bad query"),
            _scripted_tool_arguments(query="reformulated query"),
            _scripted_tool_arguments(value=10),
            _scripted_answer(answer),
        ]
    )
    runtime = _ToolRuntime(fail_first=True)

    result = IterativeAgentSolver(
        client,
        mode="scripted_tool",
        maximum_total_tokens=100,
        scripted_tool_sequence=("lookup", "verify_result"),
    ).solve_with_audit(task, runtime)

    assert [item.tool_id for item in runtime.calls] == [
        "lookup",
        "lookup",
        "verify_result",
    ]
    assert result.audit.failed_tool_call_count == 1
    assert result.audit.error_recovery_count == 1


def test_environment_contract_requires_argument_patch_after_failure() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _tool_decision("lookup", query="reformulated query"),
            _answer_decision(answer),
        ]
    )
    runtime = _PatchRequiredRuntime()

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
    ).solve_with_audit(task, runtime)

    assert len(runtime.calls) == 2
    assert runtime.calls[0].arguments != runtime.calls[1].arguments
    assert result.audit.failed_tool_call_count == 1
    assert result.audit.error_recovery_count == 1
    assert '"required_argument_patch":{"query":"reformulated query"}' in client.prompts[2]


def test_environment_contract_never_allows_identical_failed_call_replay() -> None:
    task, _ = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _tool_decision("lookup", query="public metric"),
        ]
    )
    runtime = _PatchRequiredRuntime()

    with pytest.raises(LLMClientError, match="failed-tool budget") as captured:
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, runtime)

    assert len(runtime.calls) == 1
    artifact = captured.value.failure_artifact
    assert artifact is not None
    assert artifact.observations[-1].error_code == "identical_failed_action_blocked"


def test_iterative_agent_recovers_from_missing_required_tool_arguments() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup"),
            _tool_decision("lookup", query="public metric"),
            _answer_decision(answer),
        ]
    )

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
    ).solve_with_audit(task, _ToolRuntime(maximum_failed_tool_calls=1))

    assert result.observations[0].status == "failed"
    assert result.observations[0].error_code == "agent_tool_argument_contract"
    assert result.observations[1].status == "succeeded"
    assert result.audit.error_recovery_count == 1


def test_iterative_agent_rejects_malformed_successful_tool_output() -> None:
    task, _ = _task_and_answer()
    client = _ScriptedClient([_plan(), _tool_decision("lookup", query="public metric")])

    with pytest.raises(LLMClientError, match="result lacks required fields.*value"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, _MalformedOutputRuntime())


def test_iterative_agent_rejects_unknown_final_answer_fields() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _tool_decision("verify_result", value=10),
            *(_answer_decision({**answer, "unsupported_extension": 1}) for _ in range(3)),
        ]
    )

    with pytest.raises(LLMClientError, match="stop-rejection budget") as captured:
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, _ToolRuntime())

    artifact = captured.value.failure_artifact
    assert artifact is not None
    assert len(artifact.stop_rejections) == 3
    assert {item.reason_code for item in artifact.stop_rejections} == {
        "invalid_final_answer_contract"
    }


def test_iterative_agent_repairs_public_answer_field_constraints() -> None:
    task, answer = _task_and_answer()
    field = next(iter(answer))
    guidance = dict(task.metadata.get("agent_contract_guidance", {}))
    constrained = task.model_copy(
        update={
            "metadata": {
                **task.metadata,
                "agent_contract_guidance": {
                    **guidance,
                    "answer_field_constraints": {
                        field: {
                            "allowed_values": [1, 2],
                            "numeric_minimum": "0",
                        }
                    },
                },
            }
        }
    )
    invalid = {**answer, field: -1}
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _answer_decision(invalid),
            _answer_decision(answer),
        ]
    )

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
    ).solve_with_audit(constrained, _ToolRuntime())

    assert result.trajectory.final_answer["result"] == answer
    assert [item.reason_code for item in result.audit.stop_rejections] == [
        "invalid_final_answer_contract"
    ]


def test_iterative_agent_rejects_oracle_fields_in_final_answer() -> None:
    task, answer = _task_and_answer()
    answer_field = next(iter(answer))
    poisoned_answer = {**answer, answer_field: {"oracle": "hidden"}}
    client = _ScriptedClient(
        [
            _plan(),
            _tool_decision("lookup", query="public metric"),
            _answer_decision(poisoned_answer),
        ]
    )

    with pytest.raises(ValueError, match="forbidden field"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, _ToolRuntime())


def test_iterative_agent_rejects_oracle_fields_hidden_in_public_metadata() -> None:
    task, _ = _task_and_answer()
    poisoned = task.model_copy(
        update={
            "metadata": {
                **task.metadata,
                "nested": {"gold_evidence_ids": ["evidence:oracle"]},
            }
        }
    )
    client = _ScriptedClient([_plan()])

    with pytest.raises(ValueError, match="forbidden field"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(
            poisoned,
            _ToolRuntime(),
        )


def test_iterative_agent_enforces_model_token_budget() -> None:
    task, _ = _task_and_answer()
    client = _ScriptedClient([_plan()])

    with pytest.raises(LLMClientError, match="model-token budget"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=9,
        ).solve_with_audit(task, _ToolRuntime())


def test_implicit_public_plan_removes_a_model_protocol_call() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _tool_decision("lookup", query="public metric"),
            _tool_decision("verify_result", value=10),
            _answer_decision(answer),
        ]
    )
    profile = IterativeAgentProtocolProfile(initial_plan_mode="implicit_public")

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
        protocol_profile=profile,
    ).solve_with_audit(task, _ToolRuntime())

    assert len(client.prompts) == 3
    assert result.audit.protocol_profile_hash == profile.profile_hash
    assert result.trajectory.steps[0].action == ActionType.PLAN
    assert "Choose one next public action" in client.prompts[0]
    assert result.audit.stopped_by_model is True
    assert result.audit.host_forced_final_answer is False


def test_compact_observation_view_omits_audit_only_hashes() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _tool_decision("lookup", query="public metric"),
            _tool_decision("verify_result", value=10),
            _answer_decision(answer),
        ]
    )
    profile = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        observation_view="compact",
    )

    IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
        protocol_profile=profile,
    ).solve_with_audit(task, _ToolRuntime())

    assert '"observation_id"' not in client.prompts[1]
    assert '"provenance_hash"' not in client.prompts[1]
    assert '"value":10' in client.prompts[1]
    assert '"evidence_ids"' in client.prompts[1]


def test_compact_public_value_preserves_actionable_public_locator() -> None:
    compact = _compact_public_value(
        {"public_locator": "archive://document/1", "query_hash": "audit-only"}
    )

    assert compact == {"public_locator": "archive://document/1"}


def test_bounded_observation_view_retains_sufficient_public_state() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _tool_decision("lookup", query="public metric"),
            _tool_decision("verify_result", value=10),
            _answer_decision(answer),
        ]
    )
    profile = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        observation_view="bounded_summary",
    )

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=100,
        protocol_profile=profile,
    ).solve_with_audit(task, _ToolRuntime())
    summary = _bounded_observation_summary(result.observations)

    assert summary["observation_count"] == 2
    assert len(summary["selected_evidence_observations"]) == 1
    assert summary["latest_verification_observation"]["tool_id"] == "verify_result"
    assert '"observation_count":2' in client.prompts[-1]
    assert '"operation_execution_contract"' not in client.prompts[-1]
    components = result.audit.telemetry[-1].response_shape["prompt_component_bytes"]
    assert components["public_context.observations"] > 0
    assert components["public_context.task"] > 0


def test_final_answer_reserve_switches_only_after_verified_evidence() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient(
        [
            _tool_decision("lookup", query="public metric"),
            _tool_decision("verify_result", value=10),
            _tool_decision("lookup", query="supporting metric"),
            _scripted_answer(answer),
        ]
    )
    profile = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        observation_view="compact",
        contract_repair_token_reserve=5,
        final_answer_token_reserve=15,
    )

    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=45,
        protocol_profile=profile,
    ).solve_with_audit(task, _ToolRuntime())

    assert len(result.observations) == 3
    assert result.audit.host_forced_final_answer is True
    assert result.audit.stopped_by_model is False
    assert "Return only one JSON object with exactly rationale_summary" in client.prompts[-1]
