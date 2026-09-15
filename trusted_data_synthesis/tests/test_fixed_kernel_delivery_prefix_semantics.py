"""Four bounded synthetic controls, no production prefix or model calls."""

import copy
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/fixed_kernel_delivery_prefix_semantics_20260915.py"
SPEC = importlib.util.spec_from_file_location("delivery_prefix_semantics", SCRIPT)
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)
p = s.p


def fixture(boundary):
    public = {
        "question": "Percentage change from earlier to later; round to two places.",
        "quantity_contract": {
            "unit": "percent",
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
        "source_policy": "public only",
        "tool_contract": {},
        "sources": [],
    }
    for name, value in (("earlier", 100), ("later", 120)):
        public["sources"].append(
            {
                "source_id": name,
                "record": {"val": value},
                "unit": "USD",
                "native_pointer": "/" + name,
                "raw_sha256": "a" * 64,
                "original_url": "https://example.invalid/public",
            }
        )
    messages = [
        {"role": "system", "content": s.training.SYSTEM},
        {"role": "user", "content": p.encode(public).decode()},
    ]
    previous, symbolic = {}, {}
    calculation = {
        "tool": "calculate",
        "arguments": {
            "expression": "(b-a)/a",
            "variables": {"a": {"result_id": "tool:1"}, "b": {"result_id": "tool:2"}},
            "unit": "percent",
        },
    }
    choices = [
        {"tool": "read_source", "arguments": {"source_id": "earlier"}},
        {"tool": "read_source", "arguments": {"source_id": "later"}},
    ]
    if boundary == "final":
        choices.append(calculation)
    for choice in choices:
        call, expression, _ = s._execute(choice, public, previous, symbolic)
        assert call["status"] == "ok"
        messages.extend(
            [
                {"role": "assistant", "content": p.encode(choice).decode()},
                {"role": "user", "content": p.encode({"tool_observation": call}).decode()},
            ]
        )
        previous[call["call_id"]], symbolic[call["call_id"]] = call, expression
    reference = (
        calculation
        if boundary == "calculate"
        else {"final": {"value": "20.00", "unit": "percent", "result_id": "tool:3"}}
    )
    return p.record(
        "delivery_public_training_prefix",
        boundary=boundary,
        input_messages=messages,
        task_id="synthetic_task",
        source_package_id="synthetic_package",
        reference_response=p.encode(reference).decode(),
        diagnostic_scope="synthetic_control",
    )


def prediction(prefix, response):
    return p.record(
        "delivery_prefix_prediction",
        prefix_record_id=prefix["id"],
        prefix_record_sha256=p.sha(p.encode(prefix)),
        boundary=prefix["boundary"],
        raw_response=response if isinstance(response, str) else p.encode(response).decode(),
        model_identity_id="synthetic_control",
    )


def test_algebraic_alternative_and_unit_conversion_pass_without_exact_text_match():
    prefix = fixture("calculate")
    alternative = {
        "tool": "calculate",
        "arguments": {
            "expression": "new/old-1",
            "variables": {"old": {"result_id": "tool:1"}, "new": {"result_id": "tool:2"}},
            "unit": "ratio",
        },
    }
    result = s.grade_prefix(prefix, prediction(prefix, alternative))
    assert result["status"] == "CALCULATION_SEMANTIC_PASS"
    assert result["source_expression_equivalent_to_public_reference"]
    assert result["requested_quantity_matches_public_reference"]
    assert not result["exact_text_match_is_semantic_criterion"]


def test_numeric_coincidence_and_nonexistent_reference_are_not_supported_success():
    prefix = fixture("calculate")
    coincident = {
        "tool": "calculate",
        "arguments": {
            "expression": "b/a-1+(b-1.2*a)/a",
            "variables": {"a": {"result_id": "tool:1"}, "b": {"result_id": "tool:2"}},
            "unit": "percent",
        },
    }
    result = s.grade_prefix(prefix, prediction(prefix, coincident))
    assert result["tool_executable"] and result["referenced_results_supported"]
    assert result["numeric_quantity_matches_public_reference"]
    assert result["source_expression_equivalent_to_public_reference"] is False
    assert result["semantic_calculation_success"] is False
    wrong = copy.deepcopy(coincident)
    wrong["arguments"]["variables"]["a"]["result_id"] = "tool:999"
    failed = s.grade_prefix(prefix, prediction(prefix, wrong))
    assert failed["strict_json_object"] and not failed["tool_executable"]
    assert "unknown_numeric_result_reference" in failed["execution_or_final_error"]


def test_Final_semantics_accept_numeric_spelling_but_reject_units_or_unsupported_value():
    prefix = fixture("final")
    final = {"final": {"value": "20", "unit": "percent", "result_id": "tool:3"}}
    result = s.grade_prefix(prefix, prediction(prefix, final))
    assert result["status"] == "IMMEDIATE_FINAL_SEMANTIC_PASS"
    assert result["semantic_immediate_final_success"]
    wrong = {"final": {"value": "0.2", "unit": "ratio", "result_id": "tool:3"}}
    result = s.grade_prefix(prefix, prediction(prefix, wrong))
    assert result["immediate_final"] and result["final_unit_matches_request"] is False
    assert not result["semantic_immediate_final_success"]
    wrong = {"final": {"value": "21", "unit": "percent", "result_id": "tool:3"}}
    result = s.grade_prefix(prefix, prediction(prefix, wrong))
    assert result["final_value_matches_supported_result"] is False
    assert not result["semantic_immediate_final_success"]


def test_continued_checking_is_not_immediate_Final_but_never_means_never_Final():
    prefix = fixture("final")
    read = {"tool": "read_source", "arguments": {"source_id": "earlier", "unit": "USD"}}
    result = s.grade_prefix(prefix, prediction(prefix, read))
    assert result["status"] == "CONTINUED_TOOL_NOT_IMMEDIATE_FINAL"
    assert result["tool_executable"] and not result["immediate_final"]
    assert not result["never_final_inferred"] and not result["autonomous_task_success_claimed"]
    assert result["financial_qualification_score"] is None
    invalid = s.grade_prefix(prefix, prediction(prefix, '```json\n{"final":{}}\n```'))
    assert invalid["status"] == "INVALID_JSON_OBJECT"
    assert not invalid["immediate_final"]
