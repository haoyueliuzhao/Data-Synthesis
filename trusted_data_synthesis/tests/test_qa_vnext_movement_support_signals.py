"""Synthetic structural diagnostics; no real sessions, files or models opened."""

import copy

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_movement_support import signals as s
from trusted_synthesis.experiments.finance_qa_vnext_movement_support.protocol import encode, record


def fixture():
    natives, sources = {}, []
    for i, fact in enumerate(("previous", "current", "component", "other")):
        row = {"val": str(10 + i), "end": "2020-12-31"}
        natives[fact] = {"raw_sha256": fact + "-sha", "pointer": "/" + fact, "record": row}
        sources.append({"source_id": fact, **natives[fact], "native_pointer": "/" + fact})
    bundle = {
        "id": "bundle:synthetic",
        "task_id": "task:synthetic",
        "public": {"sources": sources},
        "private": {
            "answer_exact": "999-private-answer-not-output",
            "basis_witnesses": [
                {
                    "basis": "endpoint",
                    "input_bindings": {"previous": "previous", "current": "current"},
                },
                {
                    "id": "witness:synthetic",
                    "basis": "movement",
                    "input_bindings": {"previous": "previous", "component": "component"},
                    "operator_dag": {
                        "output_step": "rate",
                        "operators": [
                            {"step_id": "amount", "operator": "sum"},
                            {"step_id": "rate", "operator": "ratio_percent"},
                        ],
                    },
                },
            ],
        },
    }
    return bundle, natives


def index():
    return s.build_support_index(*fixture())


def read(identifier, fact, *, status="ok"):
    return {
        "call_id": identifier,
        "tool": "read_source",
        "status": status,
        "result": {"source_locator": {"source_id": fact, "native_pointer": "/" + fact}},
    }


def calculate(identifier, expression, variables, *, declared=None):
    resolved = {
        name: {"result_id": value, "exact_value": "17"} for name, value in variables.items()
    }
    refs = sorted({value for value in variables.values() if value is not None})
    return {
        "call_id": identifier,
        "tool": "calculate",
        "status": "ok",
        "result": {
            "expression": expression,
            "resolved_variables": resolved,
            "used_result_ids": refs if declared is None else declared,
        },
    }


def session(tools, final_result="tool:3", *, no_final=False):
    events = [
        {"response_index": i, "tool_call": tool, "final": False, "protocol_error": None}
        for i, tool in enumerate(tools)
    ]
    if not no_final:
        events.append(
            {"response_index": len(tools), "tool_call": None, "final": True, "protocol_error": None}
        )
    return {
        "id": "session:synthetic",
        "identity": {"task_id": "task:synthetic"},
        "events": events,
        "first_final_index": None if no_final else len(tools),
        "raw_final": None
        if no_final
        else {"result_id": final_result, "value": "17", "unit": "USD"},
        "requested_basis": "movement",
    }


def trace(second="component", **kwargs):
    return session(
        [
            read("tool:1", "previous"),
            read("tool:2", second),
            calculate("tool:3", "100*b/a", {"a": "tool:1", "b": "tool:2"}),
        ],
        **kwargs,
    )


def test_source_index_roles_do_not_include_values_or_private_answers():
    result = index()
    assert result["fact_roles"]["previous"]["shared_endpoint_movement_input"]
    assert result["fact_roles"]["component"]["movement_exclusive_input"]
    assert result["fact_roles"]["current"]["endpoint_current"]
    assert not result["fact_roles"]["other"]["endpoint_input"]
    assert "999-private-answer" not in encode(result).decode()
    assert result["financial_qualification"] is False


def test_index_omits_unrelated_native_facts_but_keeps_visible_non_witness_facts():
    bundle, native = fixture()
    native["foreign_unpublished_fact"] = {
        "raw_sha256": "unused",
        "pointer": "/foreign",
        "record": {"val": "987654"},
    }
    result = s.build_support_index(bundle, native)
    assert "foreign_unpublished_fact" not in result["fact_roles"]
    assert "other" in result["fact_roles"]
    assert not any(result["fact_roles"]["other"].values())


def test_component_signal_with_percentage_constant_is_not_called_actual_movement():
    result = s.public_trace_signals(trace(), index())
    assert result["structural_shape"] == "MOVEMENT_EXCLUSIVE_INPUT_REFERENCED"
    assert result["closure_literal_variable_count"] == 0
    assert result["closure_numeric_expression_constant_count"] == 1
    assert result["closure_referenced_fact_ids"] == ["component", "previous"]
    assert result["actual_method_inferred"] is False
    assert result["financial_qualification_performed"] is False


def test_endpoint_signal_ignores_requested_guidance():
    original = trace("current")
    first = s.public_trace_signals(original, index())
    original["requested_basis"] = "endpoint"
    assert s.public_trace_signals(original, index()) == first
    assert first["structural_shape"] == "ONLY_ENDPOINT_INPUTS_REFERENCED"


def test_bare_numeric_variables_do_not_get_source_provenance():
    raw = session([calculate("tool:3", "100*b/a", {"a": None, "b": None})])
    result = s.public_trace_signals(raw, index())
    assert result["structural_shape"] == "NO_REFERENCED_SOURCE_IN_SYNTACTIC_CLOSURE"
    assert result["closure_literal_variable_count"] == 2
    assert result["closure_numeric_expression_constant_count"] == 1


def test_pure_constant_expression_is_observed_without_reclassifying_financial_validity():
    result = s.public_trace_signals(session([calculate("tool:3", "1700/100", {})]), index())
    assert result["closure_literal_variable_count"] == 0
    assert result["closure_numeric_expression_constant_count"] == 2
    assert result["structural_shape"] == "NO_REFERENCED_SOURCE_IN_SYNTACTIC_CLOSURE"


def test_exploration_not_referenced_by_first_final_does_not_change_closure_shape():
    raw = trace("current")
    raw["events"].insert(0, {"response_index": -1, "tool_call": read("extra", "component")})
    result = s.public_trace_signals(raw, index())
    assert result["all_tool_count"] == 4 and result["closure_tool_count"] == 3
    assert result["structural_shape"] == "ONLY_ENDPOINT_INPUTS_REFERENCED"


def test_unused_resolved_input_is_visible_but_not_syntactic_support():
    raw = session(
        [
            read("tool:1", "previous"),
            read("tool:2", "component"),
            calculate("tool:3", "a", {"a": "tool:1", "unused": "tool:2"}),
        ]
    )
    result = s.public_trace_signals(raw, index())
    assert result["closure_referenced_fact_ids"] == ["previous"]
    assert result["structural_shape"] == "ONLY_ENDPOINT_INPUTS_REFERENCED"
    assert result["all_public_tool_diagnostics"][-1]["calculation"][
        "unused_resolved_variable_names"
    ] == ["unused"]


def test_cancelled_component_stays_syntactically_referenced_not_algebraically_effective():
    raw = session(
        [
            read("tool:1", "previous"),
            read("tool:2", "component"),
            calculate("tool:3", "a+b-b", {"a": "tool:1", "b": "tool:2"}),
        ]
    )
    result = s.public_trace_signals(raw, index())
    assert result["structural_shape"] == "MOVEMENT_EXCLUSIVE_INPUT_REFERENCED"
    assert not result["units_values_periods_or_algebraic_sufficiency_verified"]


def test_current_and_component_joint_reference_is_not_actual_hybrid():
    result = s.public_trace_signals(
        session(
            [
                read("tool:1", "current"),
                read("tool:2", "component"),
                calculate("tool:3", "a+b", {"a": "tool:1", "b": "tool:2"}),
            ]
        ),
        index(),
    )
    assert result["structural_shape"] == "MOVEMENT_EXCLUSIVE_AND_CURRENT_REFERENCED"
    assert "actual_method" not in result


@pytest.mark.parametrize(
    "with_index,second,expected",
    [(False, "component", "INDEX_NOT_PROVIDED"), (True, "missing", "UNBOUND_SOURCE")],
)
def test_unknown_source_binding_is_not_endpoint_or_movement(with_index, second, expected):
    result = s.public_trace_signals(trace(second), index() if with_index else None)
    assert result["structural_shape"] == "UNRESOLVED_SOURCE_BINDING"
    assert result["closure_source_status_counts"][expected] >= 1


def test_other_unique_fact_is_separate_from_endpoint():
    result = s.public_trace_signals(trace("other"), index())
    assert result["structural_shape"] == "OTHER_SOURCE_INPUTS_REFERENCED"


def test_ambiguous_locator_not_resolved_by_value():
    value = index()
    locator = next(k for k in value["locator_facts"] if "component" in k)
    value["locator_facts"][locator].append("other")
    value = record(
        "structural_support_index",
        **{k: v for k, v in value.items() if k not in ("id", "schema_version")},
    )
    result = s.public_trace_signals(trace(), value)
    assert result["closure_source_status_counts"]["AMBIGUOUS_SOURCE"] == 1
    assert result["structural_shape"] == "UNRESOLVED_SOURCE_BINDING"


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_ref", "missing_result_reference"),
        ("missing_var", "expression_variable_missing_resolution"),
        ("declared", "declared_vs_resolved_reference_mismatch"),
        ("duplicate_declared", "duplicate_used_result_id"),
        ("malformed_vars", "resolved_variables_missing_or_malformed"),
        ("syntax", "expression_not_structurally_parsed"),
        ("failed_source", "failed_result_in_first_final_closure"),
        ("successful_without_result", "successful_tool_result_missing"),
        ("unknown_tool", "unknown_successful_numeric_tool"),
    ],
)
def test_broken_closure_preserved_as_unresolved(mutation, code):
    raw = trace()
    calc = raw["events"][2]["tool_call"]["result"]
    if mutation == "missing_ref":
        calc["resolved_variables"]["b"]["result_id"] = "missing"
        calc["used_result_ids"] = ["missing", "tool:1"]
    elif mutation == "missing_var":
        calc["expression"] = "a+c"
    elif mutation == "declared":
        calc["used_result_ids"] = []
    elif mutation == "duplicate_declared":
        calc["used_result_ids"].append("tool:1")
    elif mutation == "malformed_vars":
        calc["resolved_variables"] = None
    elif mutation == "syntax":
        calc["expression"] = "("
    elif mutation == "failed_source":
        raw["events"][0]["tool_call"]["status"] = "error"
    elif mutation == "successful_without_result":
        raw["events"][0]["tool_call"]["result"] = None
    else:
        raw["events"][0]["tool_call"]["tool"] = "other_tool"
    result = s.public_trace_signals(raw, index())
    assert result["structural_shape"] == "UNRESOLVED_STRUCTURE"
    assert code in result["closure_issues"]


def test_cyclic_and_nonprior_references_do_not_recurse_forever():
    raw = session(
        [calculate("tool:1", "a", {"a": "tool:2"}), calculate("tool:2", "a", {"a": "tool:1"})],
        "tool:2",
    )
    result = s.public_trace_signals(raw, index())
    assert "cyclic_result_reference" in result["closure_issues"]
    assert "nonprior_result_reference" in result["closure_issues"]


def test_no_final_preserves_all_executions_without_claiming_support():
    result = s.public_trace_signals(trace(no_final=True), index())
    assert result["first_final_status"] == "NO_FINAL"
    assert result["closure_tool_count"] == 0 and result["all_tool_count"] == 3


def test_missing_final_reference_is_explicit():
    raw = trace()
    raw["raw_final"] = {"value": 1}
    result = s.public_trace_signals(raw, index())
    assert result["first_final_status"] == "FINAL_WITHOUT_RESULT_REFERENCE"
    assert "final_missing_result_reference" in result["closure_issues"]


def test_duplicate_ids_not_silently_overwritten():
    raw = trace()
    raw["events"][1]["tool_call"]["call_id"] = "tool:1"
    result = s.public_trace_signals(raw, index())
    assert "duplicate_tool_call_id" in result["trace_issues"]


def test_tool_after_first_final_is_unresolved():
    raw = trace()
    raw["first_final_index"] = 1
    result = s.public_trace_signals(raw, index())
    assert "tool_not_before_first_final" in result["closure_issues"]


def test_source_index_content_and_task_join_are_checked():
    value = index()
    value["task_id"] = "changed"
    with pytest.raises(ValueError, match="content_identity"):
        s.public_trace_signals(trace(), value)
    raw = trace()
    raw["identity"]["task_id"] = "changed"
    with pytest.raises(ValueError, match="task_index_join"):
        s.public_trace_signals(raw, index())


def test_existing_public_protocol_errors_are_counted_without_relabeling_later_support():
    raw = trace()
    raw["events"].insert(0, {"response_index": -1, "tool_call": None, "protocol_error": "parse"})
    result = s.public_trace_signals(raw, index())
    assert result["all_protocol_error_count"] == 1
    assert result["structural_shape"] == "MOVEMENT_EXCLUSIVE_INPUT_REFERENCED"


def test_sum_function_name_is_not_a_missing_variable():
    raw = trace()
    raw["events"][2]["tool_call"]["result"]["expression"] = "sum([a,b])"
    result = s.public_trace_signals(raw, index())
    assert result["closure_issues"] == []


def test_private_transport_and_requested_fields_are_never_consumed():
    class Guard(dict):
        def get(self, key, *args):
            if key in {"transport", "reasoning_content", "requested_basis", "turns"}:
                raise AssertionError("private or requested-label access")
            return super().get(key, *args)

    raw = Guard(trace())
    raw.update(transport=object(), reasoning_content=object(), turns=object())
    result = s.public_trace_signals(raw, index())
    assert result["transport_private_reasoning_or_Student_data_read"] is False


def test_inputs_are_not_mutated_and_outputs_own_data():
    raw, source_index = trace(), index()
    before = copy.deepcopy((raw, source_index))
    result = s.public_trace_signals(raw, source_index)
    assert (raw, source_index) == before
    saved = copy.deepcopy(result)
    raw["events"][2]["tool_call"]["result"]["expression"] = "changed"
    assert result == saved


@pytest.mark.parametrize(
    "name,operator,expected",
    [
        ("amount", "ratio_percent", True),
        ("change", "ratio_percent", False),
        ("amount", "sum", False),
    ],
)
def test_growth_hazard_checks_actual_output_operator_and_literal_step(name, operator, expected):
    bundle, _ = fixture()
    dag = bundle["private"]["basis_witnesses"][1]["operator_dag"]
    dag["operators"][0]["step_id"] = name
    dag["operators"][1]["operator"] = operator
    result = s.growth_delta_hazard(bundle)
    assert result["percentage_output_used_as_currency_delta"] is expected
    assert result["actual_session_requalified"] is False
    assert result["hazard_alone_proves_observed_failure"] is False


def test_no_movement_witness_has_no_growth_hazard():
    bundle, _ = fixture()
    bundle["private"]["basis_witnesses"].pop()
    assert s.growth_delta_hazard(bundle)["percentage_output_used_as_currency_delta"] is False
