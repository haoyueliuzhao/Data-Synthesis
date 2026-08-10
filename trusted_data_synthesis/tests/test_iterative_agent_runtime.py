from __future__ import annotations

import hashlib
from typing import Any

import pytest

from trusted_synthesis.core.task.answer_schema import required_answer_fields
from trusted_synthesis.core.trajectory.schema import ActionType
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.runtime.agent import IterativeAgentSolver
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolResult,
    AgentToolSpec,
    make_agent_tool_environment_manifest,
)


class _ScriptedClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = iter(payloads)
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


class _ToolRuntime:
    def __init__(self, *, fail_first: bool = False) -> None:
        self._manifest = _tool_manifest(maximum_failed_tool_calls=1 if fail_first else 0)
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
    assert result.trajectory.final_answer == answer
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


def test_scripted_agent_cannot_change_host_tool_order() -> None:
    task, _ = _task_and_answer()
    client = _ScriptedClient([_plan(), _tool_decision("verify_result", value=10)])
    solver = IterativeAgentSolver(
        client,
        mode="scripted_tool",
        maximum_total_tokens=100,
        scripted_tool_sequence=("lookup", "verify_result"),
    )

    with pytest.raises(LLMClientError, match="changed the frozen tool sequence"):
        solver.solve_with_audit(task, _ToolRuntime())


def test_agent_cannot_stop_without_observed_evidence() -> None:
    task, answer = _task_and_answer()
    client = _ScriptedClient([_plan(), _answer_decision(answer)])

    with pytest.raises(LLMClientError, match="without using a tool"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(
            task,
            _ToolRuntime(),
        )


def test_iterative_agent_rejects_missing_required_tool_arguments() -> None:
    task, _ = _task_and_answer()
    client = _ScriptedClient([_plan(), _tool_decision("lookup")])

    with pytest.raises(LLMClientError, match="lacks required fields.*query"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, _ToolRuntime())


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
            _answer_decision({**answer, "unsupported_extension": 1}),
        ]
    )

    with pytest.raises(LLMClientError, match="answer contains unknown fields"):
        IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=100,
        ).solve_with_audit(task, _ToolRuntime())


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
