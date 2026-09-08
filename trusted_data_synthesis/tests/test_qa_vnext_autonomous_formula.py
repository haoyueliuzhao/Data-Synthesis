"""New responsibility split only; no historical sessions, qualification or token tests."""

import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_autonomous_formula.evaluate import (
    REVIEW_FIELDS,
    answer_score,
    audit_session,
    cost_summary,
    reviewed_answer_score,
    trace_checks,
    verify_quotes,
)
from trusted_synthesis.experiments.finance_qa_vnext_autonomous_formula.online.calculator import (
    CalculationError,
    calculate,
)
from trusted_synthesis.experiments.finance_qa_vnext_autonomous_formula.online.common import (
    encode,
    strict_json,
)
from trusted_synthesis.experiments.finance_qa_vnext_autonomous_formula.plan import WORKER_PYTHON
from trusted_synthesis.experiments.finance_qa_vnext_autonomous_formula.stage import assert_public

WORKER = (
    Path(__file__).resolve().parents[1]
    / "src/trusted_synthesis/experiments/finance_qa_vnext_autonomous_formula/online/worker.py"
)


def test_financially_wrong_but_numeric_legal_executes_without_source_certification():
    result = calculate(
        {
            "expression": "q*p",
            "variables": {"q": "13", "p": "33.32"},
            "sources": {"p": "invented_or_wrong_year_source"},
        },
        {},
    )
    assert result["exact_value"] == "10829/25"
    assert result["model_supplied_sources"] == {"p": "invented_or_wrong_year_source"}
    assert not result["source_declarations_validated"] and not result["financial_meaning_certified"]


def test_complete_expression_and_result_reuse_without_accept():
    result = calculate({"expression": "(x+y)/z", "variables": {"x": "6", "y": "-2", "z": "5"}}, {})
    previous = {"tool:1": {"tool": "calculate", "status": "ok", "result": result}}
    next_result = calculate(
        {"expression": "v*100", "variables": {"v": {"result_id": "tool:1"}}}, previous
    )
    assert next_result["exact_value"] == "80" and next_result["used_result_ids"] == ["tool:1"]
    assert calculate({"expression": "2+3"}, {})["exact_value"] == "5"


@pytest.mark.parametrize(
    "expression,error",
    [
        ("x+1", "undefined_variable"),
        ("1/0", "division_by_zero"),
        ("1+", "syntax"),
        ("__import__('os')", "unsupported"),
        ("(1).__class__", "unsupported"),
        ("2**100000", "power_exponent_limit"),
        ("1e999999", "exponent_limit"),
    ],
)
def test_actual_tool_errors_only(expression, error):
    with pytest.raises(CalculationError, match=error):
        calculate({"expression": expression}, {})


def test_arithmetic_preserves_exact_decimal_and_supported_aggregates():
    result = calculate({"expression": "sum([0.1, 0.2, -0.3])+avg(2,4)+abs(-2)"}, {})
    assert result["exact_value"] == "5"


def run_isolated(tmp_path, script):
    public = tmp_path / "public.json"
    public.write_bytes(
        encode(
            {
                "task_id": "control",
                "question": "A constructed control.",
                "numeric_catalog": [
                    {"id": "source:x", "segment": "p0", "value": "13", "token": "13"}
                ],
                "segments": {"p0": {"text": "13 units", "locator": ["pre_text", 0]}},
            }
        )
    )
    private = tmp_path / "hidden.json"
    private.write_text('{"program":"never-visible","exe_ans":9999}')
    commands = tmp_path / "script.json"
    commands.write_bytes(encode(script))
    output = tmp_path / "session"
    result = subprocess.run(
        [
            WORKER_PYTHON,
            "-I",
            "-S",
            "-B",
            str(WORKER),
            "--public",
            str(public),
            "--output",
            str(output),
            "--forbidden",
            str(private),
            "--script",
            str(commands),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    assert result.returncode == 0, result.stderr
    return output, json.loads((output / "result.json").read_text())


def test_os_isolation_wrong_final_stops_and_history_is_literal(tmp_path):
    script = [
        {
            "message": "Use the stated product as a tentative relation.",
            "tool": "calculate",
            "arguments": {"expression": "q*p", "variables": {"q": "13", "p": "33.32"}},
        },
        {"final": {"answer": "Deliberately wrong financial answer", "value": "433.16"}},
        {"tool": "calculate", "arguments": {"expression": "9999"}},
    ]
    output, result = run_isolated(tmp_path, script)
    isolation = json.loads((output / "isolation.json").read_text())
    assert isolation["landlock_abi"] >= 3 and all(
        p["read_denied"] for p in isolation["private_read_probes"]
    )
    assert (
        isolation["repository_modules_loaded"] == []
        and isolation["isolated_mode"]
        and isolation["no_site"]
    )
    assert (
        result["terminal"] == "model_final"
        and result["model_requests"] == 2
        and result["tool_calls"] == 1
    )
    assert result["provider_attempts"] == 0 and not result["online_answer_feedback"]
    first = json.loads((output / "turns/000_http_request.body").read_text())["messages"]
    second = json.loads((output / "turns/001_http_request.body").read_text())["messages"]
    assert second[: len(first)] == first
    assert (
        second[len(first)]["content"].encode() == (output / "turns/000_assistant.raw").read_bytes()
    )
    assert "never-visible" not in json.dumps(second) and "target_not_established" not in json.dumps(
        second
    )


def test_execution_error_can_be_corrected_and_final_needs_no_formula_gate(tmp_path):
    script = [
        {"tool": "calculate", "arguments": {"expression": "x+1"}},
        {"tool": "calculate", "arguments": {"expression": "x+1", "variables": {"x": "2"}}},
        {"final": "3"},
    ]
    _, result = run_isolated(tmp_path, script)
    assert result["events"][0]["tool_call"]["output"]["status"] == "error"
    assert result["events"][1]["tool_call"]["output"]["result"]["exact_value"] == "3"
    assert result["model_requests"] == 3 and result["tool_calls"] == 2


def test_direct_final_or_empty_final_ends_without_forced_compute(tmp_path):
    output, result = run_isolated(
        tmp_path, [{"final": None, "tool": "calculate", "arguments": {"expression": "1/0"}}]
    )
    assert (
        result["terminal"] == "model_final"
        and result["tool_calls"] == 0
        and result["model_requests"] == 1
    )
    assert not (output / "turns/000_tool.json").exists()


def test_hidden_reference_keys_cannot_be_public_document():
    with pytest.raises(ValueError, match="hidden_field"):
        assert_public({"source": {"program": "hidden"}})


def test_model_json_decimal_values_and_explicit_metadata_are_not_rounded_or_corrected():
    args = strict_json(
        '{"expression":"x + 0.000000000000000002",'
        '"variables":{"x":{"value":0.123456789123456789,"source":"wrong","unit":"made up"}}}'
    )
    assert args["variables"]["x"]["value"] == "0.123456789123456789"
    assert calculate(args, {})["exact_value"] == "123456789123456791/1000000000000000000"


def control_private(value="13"):
    return {
        "facts": {"source:x": {"value": value}},
        "target": "source:x",
        "relations": {},
        "unit": "percent",
    }


def review_for(value, index, calculation="tool:1"):
    return {
        "published_value": value,
        "published_unit": "percent",
        "answer_override_evidence": [],
        "answer_calculation_id": calculation,
        **{
            field: {"status": "PASS", "evidence": [{"response_index": index, "quote": "x"}]}
            for field in (*REVIEW_FIELDS, "final_answer_consistency")
        },
        "planning_observations": {"text": "", "evidence": []},
    }


def test_posthoc_independent_execution_and_no_same_number_source_inference(tmp_path):
    output, result = run_isolated(
        tmp_path,
        [
            {"tool": "calculate", "arguments": {"expression": "x", "variables": {"x": "13"}}},
            {"final": {"value": "13", "unit": "percent", "result_id": "tool:1"}},
        ],
    )
    public = json.loads((tmp_path / "public.json").read_text())
    with pytest.raises(ValueError, match="actual_model_origin"):
        audit_session(output, public, control_private())
    audit = audit_session(output, public, control_private(), model_required=False)
    calculation = audit["calculations"][0]
    assert calculation["independent_execution_verified"]
    assert calculation["variable_bindings"][0]["kind"] == "unlinked_numeric_constant"
    assert calculation["source_symbolic_target_match"] is False
    assert answer_score("13", "percent", control_private())["task_answer_status"] == "PASS"
    assert result["provider_attempts"] == 0 and audit["no_final_retry"]


def test_explicit_source_transformation_requires_review_not_host_repair(tmp_path):
    output, _ = run_isolated(
        tmp_path,
        [
            {
                "tool": "calculate",
                "arguments": {
                    "expression": "x",
                    "variables": {"x": {"value": "13000", "source": "source:x"}},
                },
            },
            {"final": {"value": "13000", "unit": "percent"}},
        ],
    )
    audit = audit_session(
        output,
        json.loads((tmp_path / "public.json").read_text()),
        control_private(),
        model_required=False,
    )
    calc = audit["calculations"][0]
    assert calc["actual_exact_value"] == "13000" and calc["independent_execution_verified"]
    assert not calc["variable_bindings"][0]["numeric_alignment"] and calc["binding_issues"]
    # Declared source identity alone can match algebra; it never certifies the supplied value.
    assert calc["source_symbolic_target_match"] is True
    assert answer_score("13000", "percent", control_private())["task_answer_status"] == "FAIL"


def test_final_only_formula_and_direct_numeric_answer_do_not_become_pre_execution_proof():
    private = control_private()
    score = answer_score("13", "percent", private)
    audit = {
        "raw_final": {"value": "13", "result_id": "tool:1"},
        "calculations": [{"call_id": "tool:1", "response_index": 0, "actual_exact_value": "13"}],
    }
    assert score["task_answer_status"] == "PASS"
    assert not trace_checks(audit, review_for("13", 1), score)["formula_driven_trace_verified"]
    assert trace_checks(audit, review_for("13", 0), score)["formula_driven_trace_verified"]
    audit["raw_final"]["result_id"] = "tool:wrong"
    assert not trace_checks(audit, review_for("13", 0), score)["formula_driven_trace_verified"]
    audit["calculations"] = []
    assert not trace_checks(audit, review_for("13", 0), score)["formula_driven_trace_verified"]
    assert score["numeric_correct"] is True


def test_published_rounding_units_and_exact_rational_are_scored_separately():
    private = control_private("1200/47")
    assert answer_score("25.53", "%", private)["task_answer_status"] == "PASS"
    assert answer_score("25.5319", "percentage", private)["task_answer_status"] == "PASS"
    assert answer_score("25.54", "percent", private)["numeric_correct"] is False
    assert answer_score("1200/47", "percent", private)["numeric_correct"] is True
    assert answer_score("25.53", "USD million", private)["unit_correct"] is False
    assert answer_score(None, "percent", private)["task_answer_status"] == "UNDETERMINED"


def test_review_quotes_must_come_from_literal_model_content():
    review = review_for("13", 0)
    verify_quotes(review, {0: '{"message":"x"}'})
    with pytest.raises(ValueError, match="actual_model_quote"):
        verify_quotes(review, {0: '{"message":"a different raw message"}'})


def test_cost_missing_provider_usage_is_not_zero_or_removed(tmp_path):
    online = tmp_path / "online"
    turns = online / "sessions/control/turns"
    turns.mkdir(parents=True)
    (online / "launch.json").write_bytes(
        encode({"registrations": [{"label": "control", "task_key": "control"}]})
    )
    (turns / "000_reservation.json").write_bytes(
        encode({"request_bytes": 100, "reserved_token_allowance": 107520})
    )
    cost = cost_summary(online)["aggregate"]
    assert cost["reserved_attempts"] == 1 and cost["recorded_outcomes"] == 0
    assert cost["provider_usage"]["total_tokens"]["complete_sum"] is None
    assert cost["provider_usage"]["total_tokens"]["missing_attempts"] == 1


def test_contradictory_final_prose_does_not_erase_numeric_score_but_fails_task_answer():
    score = answer_score("13", "percent", control_private())
    review = review_for("13", 0)
    review["final_answer_consistency"]["status"] = "FAIL"
    checked = reviewed_answer_score(score, review)
    assert checked["numeric_correct"] is True and checked["task_answer_status"] == "FAIL"
