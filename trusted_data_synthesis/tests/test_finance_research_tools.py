from __future__ import annotations

import json

import pytest

from trusted_synthesis.finance_research.contracts import PublicSource, PublicTask, ToolCall
from trusted_synthesis.finance_research.tools import PublicToolSession, ToolInputError, calculate


@pytest.fixture
def task():
    return PublicTask(
        dataset="fixture",
        task_id="one",
        version="fixture-v1",
        question="Revenue?",
        sources=(
            PublicSource(
                source_id="table",
                kind="table",
                locator="table[0]",
                content=[["Year", "Revenue"], ["2023", "120"]],
            ),
            PublicSource(
                source_id="text",
                kind="text",
                locator="pre_text[0]",
                content="Revenue is in USD millions.",
            ),
        ),
    )


def call(name, args, call_id="call_1", *, raw=None):
    return ToolCall(
        name=name,
        arguments=args,
        call_id=call_id,
        raw_arguments=json.dumps(args) if raw is None else raw,
    )


def test_complete_source_and_real_reference_arguments_are_auditable(task):
    tools = PublicToolSession(task)
    read = tools.execute(call("read_source", {"source_id": "table"}))
    assert read.raw_output["content"] == task.sources[0].content
    calc = tools.execute(
        call(
            "calculate",
            {"expression": "amount / 2", "variables": {"amount": "prev:call_1.content.1.1"}},
            "call_2",
        )
    )
    assert not calc.is_error
    assert calc.normalized_arguments["variables"]["amount"] == "prev:call_1.content.1.1"
    assert calc.executed_arguments["variables"]["amount"] == "120"
    assert calc.raw_output["result"] == "60"
    assert json.loads(calc.visible_output) == calc.raw_output
    final = tools.execute(
        call("final_answer", {"answer": "prev:call_2.result", "scale": "million"}, "call_3")
    )
    assert final.raw_output == {"answer": "60", "scale": "million", "program": None}


def test_no_oracle_or_source_mutation(task):
    tools = PublicToolSession(task)
    event = tools.execute(call("read_source", {"source_id": "table"}))
    event.raw_output["content"][1][1] = "999"
    again = tools.execute(call("read_source", {"source_id": "table"}, "call_2"))
    assert again.raw_output["content"][1][1] == "120"
    output = tools.execute(call("final_answer", {"answer": "wrong"}, "call_3"))
    assert output.raw_output["answer"] == "wrong"
    assert not any(
        key in output.raw_output for key in ("expected_answer", "correct", "gold", "score")
    )


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').getcwd()",
        "open('/etc/passwd').read()",
        "[1][0]",
        "(1).__class__",
        "sum([1, 2])",
        "2 ** 1000000",
        "1 / 0",
        "True + 1",
        "a if 1 else 2",
        "1e101",
    ],
)
def test_arithmetic_is_bounded_and_has_no_python_escape(expression):
    with pytest.raises(ToolInputError):
        calculate(expression)


def test_decimal_arithmetic_has_explicit_precision_and_no_scale_magic():
    assert calculate("0.1 + 0.2")["result"] == "0.3"
    assert calculate("(new - old) / old * 100", {"new": "120", "old": "100"})["result"] == "20.0"
    with pytest.raises(ToolInputError):
        calculate("x", {"x": "$1,200"})


@pytest.mark.parametrize("answer", ["revenue", ["revenue", "expenses"], 12.5, [1, 2]])
def test_final_answer_supports_numeric_span_and_multi_without_calculation(task, answer):
    result = PublicToolSession(task).execute(call("final_answer", {"answer": answer}))
    assert not result.is_error
    assert result.raw_output["answer"] == answer


def test_optional_program_is_only_recorded(task):
    result = PublicToolSession(task).execute(
        call("final_answer", {"answer": "20", "program": "subtract(120, 100)"})
    )
    assert result.raw_output["program"] == "subtract(120, 100)"


def test_failed_unknown_future_and_duplicate_references_are_not_fabricated(task):
    tools = PublicToolSession(task)
    failed = tools.execute(call("read_source", {"source_id": "unknown"}))
    assert failed.is_error and "call_1" not in tools.outputs
    for index, reference in enumerate(
        ("prev:call_1.content", "prev:future.result", "prev:call_1"), 2
    ):
        result = tools.execute(call("final_answer", {"answer": reference}, f"call_{index}"))
        assert result.is_error
    assert tools.execute(call("list_sources", {}, "call_1")).is_error


def test_raw_parsed_and_executed_are_not_silently_coerced(task):
    tools = PublicToolSession(task)
    mismatch = tools.execute(call("final_answer", {"answer": "20"}, raw='{"answer":"30"}'))
    assert mismatch.is_error
    assert mismatch.normalized_arguments == {"answer": "30"}
    assert mismatch.executed_arguments == {}
    duplicate = tools.execute(
        call("final_answer", {"answer": "30"}, "call_2", raw='{"answer":20,"answer":30}')
    )
    assert duplicate.is_error
    extra = tools.execute(call("list_sources", {"gold": True}, "call_3"))
    assert extra.is_error


def test_empty_bool_nested_and_nonfinite_answers_are_rejected(task):
    tools = PublicToolSession(task)
    for index, answer in enumerate((True, None, [], "", [[1]], float("inf"))):
        assert tools.execute(call("final_answer", {"answer": answer}, f"call_{index}")).is_error


def test_tool_session_rejects_nonpublic_objects(task):
    with pytest.raises(TypeError):
        PublicToolSession({"public": task, "reference": {"answer": "secret"}})
