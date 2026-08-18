from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.public_operation import (
    PUBLIC_OPERATION_CONTRACT_VERSION,
    PublicOperationContractView,
    PublicOperationInput,
    PublicOperationNode,
    PublicOperationPredicate,
    PublicOperationVariable,
    PublicStopReadinessContract,
    PublicVariableResolutionRule,
    public_operation_contract_view_id,
    public_stop_readiness_contract_id,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.runtime.agent.public_operation import (
    public_operation_progress,
    public_operation_step_rejection,
    public_postcompletion_action_rejection,
)
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolResult,
    make_agent_tool_observation,
)


def _view() -> PublicOperationContractView:
    variables = tuple(
        PublicOperationVariable(
            symbol=symbol,
            semantic_role=f"required_{slot}_record",
            resolution_rules=(
                PublicVariableResolutionRule(
                    source_tool_id="query_structured_fact",
                    collection_selector=("facts",),
                    evidence_id_selector=("evidence_id",),
                    equals=(PublicOperationPredicate(selector=("slot",), value=slot),),
                ),
                PublicVariableResolutionRule(
                    source_tool_id="open_document",
                    collection_selector=("content", "facts"),
                    evidence_id_selector=("evidence_id",),
                    equals=(PublicOperationPredicate(selector=("slot",), value=slot),),
                ),
            ),
        )
        for symbol, slot in (("input_a", "first"), ("input_b", "second"))
    )
    nodes = (
        PublicOperationNode(
            node_id="semantic_stage_1",
            node_kind="calculation",
            semantic_role="context_owned_initial_operation",
            tool_id="calculator",
            inputs=(
                PublicOperationInput(source_symbol="input_a"),
                PublicOperationInput(source_symbol="input_b"),
            ),
            output_symbol="intermediate_result",
            allowed_operator_ids=("compare", "difference"),
            operator_output_schemas={"compare": "comparison", "difference": "scalar"},
            required_output_schema="scalar",
            operator_choice_mode="model_context_choice",
            operator_selection_rule="choose the operator matching the public result schema",
        ),
        PublicOperationNode(
            node_id="semantic_terminal",
            node_kind="calculation",
            semantic_role="terminal_projection_operation",
            tool_id="calculator",
            dependency_node_ids=("semantic_stage_1",),
            inputs=(
                PublicOperationInput(
                    source_symbol="intermediate_result",
                    selector="value",
                ),
                PublicOperationInput(source_symbol="input_a"),
            ),
            output_symbol="terminal_result",
            allowed_operator_ids=("ratio",),
            operator_output_schemas={"ratio": "scalar"},
            required_output_schema="scalar",
            operator_choice_mode="fixed_semantics",
            parameters={"registered_pair": "public_pair"},
            terminal=True,
        ),
    )
    values: dict[str, Any] = {
        "variables": variables,
        "nodes": nodes,
        "terminal_node_id": "semantic_terminal",
        "schema_version": PUBLIC_OPERATION_CONTRACT_VERSION,
    }
    provisional = PublicOperationContractView.model_construct(view_id="pending", **values)
    return PublicOperationContractView(
        view_id=public_operation_contract_view_id(provisional),
        **values,
    )


def _stop(view: PublicOperationContractView) -> PublicStopReadinessContract:
    values = {
        "semantic_source_id": "semantic:test",
        "operation_contract_id": "public_operation:test",
        "required_node_ids": tuple(item.node_id for item in view.nodes),
        "terminal_node_id": view.terminal_node_id,
    }
    provisional = PublicStopReadinessContract.model_construct(contract_id="pending", **values)
    return PublicStopReadinessContract(
        contract_id=public_stop_readiness_contract_id(provisional),
        **values,
    )


def _task():
    task = build_finance_counterfactual_cases(count=1)[0].task.public
    view = _view()
    stop = _stop(view)
    return task.model_copy(
        update={
            "metadata": {
                **task.metadata,
                "agent_contract_guidance": {
                    "public_operation_execution_contract": view.model_dump(mode="json"),
                    "public_stop_readiness_contract": stop.model_dump(mode="json"),
                },
            }
        }
    )


def _observation(
    index: int,
    tool_id: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    *,
    evidence_ids: tuple[str, ...] = (),
):
    return make_agent_tool_observation(
        environment_manifest_id="manifest:public-operation-test",
        call=AgentToolCall(call_index=index, tool_id=tool_id, arguments=arguments),
        result=AgentToolResult(
            status="succeeded",
            result=result,
            evidence_ids=evidence_ids,
        ),
        observation_time_hash=f"time:{index}",
    )


def _selection(index: int, evidence_id: str, slot: str):
    return _observation(
        index,
        "query_structured_fact",
        {"slot": slot},
        {"facts": [{"evidence_id": evidence_id, "slot": slot}]},
        evidence_ids=(evidence_id,),
    )


def _calculation(
    index: int,
    operator: str,
    operands: list[dict[str, Any]],
    parameters: dict[str, Any],
    operation_ref: str,
):
    return _observation(
        index,
        "calculator",
        {"operator": operator, "operands": operands, "parameters": parameters},
        {
            "result": {
                "operator": operator,
                "output": {"value": str(index)},
                "operation_ref": operation_ref,
            },
            "operation_hash": f"hash:{index}",
        },
        evidence_ids=("evidence:public:1", "evidence:public:2"),
    )


def _verification(index: int, operation_ref: str):
    return _observation(
        index,
        "cross_check_evidence",
        {
            "evidence_ids": ["evidence:public:1", "evidence:public:2"],
            "claim_or_result": {"operation_ref": operation_ref},
        },
        {
            "verified": True,
            "support": ["evidence:public:1", "evidence:public:2"],
            "conflicts": [],
            "verification_hash": f"verify:{index}",
        },
        evidence_ids=("evidence:public:1", "evidence:public:2"),
    )


def _complete_history():
    first = _selection(1, "evidence:public:1", "first")
    second = _selection(2, "evidence:public:2", "second")
    stage = _calculation(
        3,
        "difference",
        [
            {"evidence_id": "evidence:public:1"},
            {"evidence_id": "evidence:public:2"},
        ],
        {},
        "operation:stage-1",
    )
    terminal = _calculation(
        4,
        "ratio",
        [
            {"operation_ref": "operation:stage-1", "selector": "value"},
            {"evidence_id": "evidence:public:1"},
        ],
        {"registered_pair": "public_pair"},
        "operation:terminal",
    )
    verified = _verification(5, "operation:terminal")
    return first, second, stage, terminal, verified


def test_public_contract_hides_context_choice_and_gold_identity() -> None:
    view = _view()
    payload = view.model_dump(mode="json")
    serialized = str(payload).casefold()

    assert view.exact_tool_sequence_required is False
    assert view.correct_choice_exposed_for_model_choice is False
    assert "evidence:" not in serialized
    assert "expected_operator" not in serialized
    assert payload["nodes"][0]["allowed_operator_ids"] == ["compare", "difference"]

    mutated = payload.copy()
    mutated["variables"] = [
        {
            **mutated["variables"][0],
            "semantic_role": "evidence:gold:forbidden",
        },
        *mutated["variables"][1:],
    ]
    with pytest.raises(ValidationError, match="private identity"):
        PublicOperationContractView.model_validate(mutated)


def test_public_progress_requires_full_terminal_and_postterminal_verification() -> None:
    task = _task()
    first, second, stage, terminal, verified = _complete_history()

    initial = public_operation_progress(task, ())
    selected = public_operation_progress(task, (first, second))
    partial = public_operation_progress(task, (first, second, stage))
    terminal_only = public_operation_progress(task, (first, second, stage, terminal))
    complete = public_operation_progress(task, (first, second, stage, terminal, verified))

    assert initial is not None and initial["stop_ready"] is False
    assert set(initial["unresolved_symbols"]) == {"input_a", "input_b"}
    assert selected is not None
    ready = selected["ready_nodes"][0]
    assert ready["allowed_operators"] == ("compare", "difference")
    assert ready["argument_contract"]["operator"] == (
        "choose_one_allowed_operator_from_public_context"
    )
    assert "expected_arguments" not in ready
    assert partial is not None and partial["terminal_node_completed"] is False
    assert terminal_only is not None and terminal_only["stop_ready"] is False
    assert terminal_only["verification_after_terminal_completed"] is False
    assert complete is not None and complete["stop_ready"] is True
    assert complete["final_answer_allowed"] is True


def test_early_verification_and_reordered_nodes_fail_closed() -> None:
    task = _task()
    first, second, stage, terminal, _ = _complete_history()
    early_verification = _verification(4, "operation:stage-1")
    late_terminal = terminal.model_copy(
        update={"call": terminal.call.model_copy(update={"call_index": 5})}
    )
    early = public_operation_progress(
        task,
        (first, second, stage, early_verification, late_terminal),
    )
    reordered = public_operation_progress(task, (first, second, terminal, stage))

    assert early is not None and early["terminal_node_completed"] is True
    assert early["verification_after_terminal_completed"] is False
    assert early["stop_ready"] is False
    assert reordered is not None
    assert reordered["completed_node_ids"] == ("semantic_stage_1",)
    assert reordered["terminal_node_completed"] is False


def test_runtime_accepts_any_registered_context_choice_without_revealing_gold() -> None:
    task = _task()
    first, second, *_ = _complete_history()
    base = {
        "operands": [
            {"evidence_id": "evidence:public:1"},
            {"evidence_id": "evidence:public:2"},
        ],
        "parameters": {},
    }
    for operator in ("compare", "difference"):
        call = AgentToolCall(
            call_index=3,
            tool_id="calculator",
            arguments={"operator": operator, **base},
        )
        assert public_operation_step_rejection(task, (first, second), call) is None

    rejected = public_operation_step_rejection(
        task,
        (first, second),
        AgentToolCall(
            call_index=3,
            tool_id="calculator",
            arguments={"operator": "growth", **base},
        ),
    )
    assert rejected is not None
    assert rejected.error_code == "public_operation_node_contract"
    assert "compare" in str(rejected.result)
    assert "difference" in str(rejected.result)


def test_postcompletion_tool_action_is_rejected_and_irreparable() -> None:
    task = _task()
    history = _complete_history()
    extra_call = AgentToolCall(
        call_index=6,
        tool_id="query_structured_fact",
        arguments={"slot": "first"},
    )
    rejection = public_postcompletion_action_rejection(task, history, extra_call)
    assert rejection is not None
    assert rejection.error_code == "redundant_action_after_public_operation_completion"

    contaminated = (*history, _selection(6, "evidence:public:1", "first"))
    progress = public_operation_progress(task, contaminated)
    assert progress is not None
    assert progress["postcompletion_violation"] is True
    assert progress["stop_ready"] is False
