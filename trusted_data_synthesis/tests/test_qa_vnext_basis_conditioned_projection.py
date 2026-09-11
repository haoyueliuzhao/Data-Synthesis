"""Bounded new-version controls: one historical reference and small counterexamples.

No provider, tokenizer, model, training, old-40 reassessment or old-file write.
Synthetic fixtures are explicitly synthetic, even when using frozen public X2.
"""

import ast
import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    encode,
    record,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.projection import (
    X2_ENDING_REBUILD_RELATION,
    project_session,
    x2_cross_quantity_context,
)
from trusted_synthesis.experiments.finance_qa_vnext_dr_support.source import bind
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.projection import (
    project_session as old_project_session,
)

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "trusted_data_synthesis/artifacts/qa_vnext_dr_support/E_X2_32rep_20260911"
PREPARATION = ROOT / (
    "trusted_data_synthesis/artifacts/qa_vnext_soft_detail_exploration/"
    "three_tasks_NE_8rep_20260910/preparation"
)
REFERENCE_CONDITION = "offline_boundary_reference:new_projection:E_X2_B2_07"


def read(path):
    return json.loads(path.read_bytes())


@pytest.fixture
def historical():
    row = read(OLD / "closeout/rows/E_X2_B2_07.json")
    session = bind(ROOT, row)
    mapping = read(OLD / "closeout/reviews.original.json")["dr_review_028"]["mapping"]
    goal = read(PREPARATION / "private/evaluation_targets.json")["X2"]["goal_scope"]
    context = x2_cross_quantity_context(session["public"], goal)
    # Explicitly an offline reference, never an additional new g-labelled candidate.
    session["row"] = {**row, "offline_historical_boundary_reference": True}
    mapping["cross_checks"][0]["quantity_relation"] = {
        "relation_id": X2_ENDING_REBUILD_RELATION,
        "checked_quantity": context["checked_quantity"],
        "comparator_source_id": context["comparator_source_id"],
        "final_link": {
            "pointer": ["explanation"],
            "quote": session["result"]["final"]["explanation"],
        },
    }
    return session, mapping, goal, context


def project(case, *, condition_id=REFERENCE_CONDITION):
    session, mapping, goal, context = case
    return project_session(
        session,
        mapping,
        goal,
        condition_id=condition_id,
        cross_quantity_context=context,
    )


def refresh(session, mapping):
    """Regenerate only in-memory synthetic response bindings after a mutation."""
    for turn in session["turns"]:
        event = turn["event"]
        parsed = json.loads(turn["raw"])
        if event["tool_call"]:
            parsed["arguments"] = event["tool_call"]["arguments"]
        if event["final"]:
            parsed["final"] = session["result"]["final"]
        turn["raw"] = json.dumps(parsed, ensure_ascii=False, indent=2).encode()
        event["raw_sha256"] = turn["binding"]["raw_response_sha256"] = sha(turn["raw"])
    raws = {t["binding"]["response_index"]: t["raw"].decode() for t in session["turns"]}

    def replace_evidence(value):
        if isinstance(value, dict):
            if "response_index" in value and "quote" in value:
                value["quote"] = raws[value["response_index"]]
                value.pop("raw_response_sha256", None)
            else:
                for child in value.values():
                    replace_evidence(child)
        elif isinstance(value, list):
            for child in value:
                replace_evidence(child)

    replace_evidence(mapping)


def test_real_B2_07_new_projection_keeps_execution_revision_and_old_unknown(historical):
    paths = [
        OLD / "closeout/behavior/E_X2_B2_07.json",
        OLD / "closeout/rows/E_X2_B2_07.json",
        OLD / "online/sessions/E_X2_B2_07/result.json",
    ]
    before = {str(path): sha(path.read_bytes()) for path in paths}
    session, mapping, goal, context = historical
    old_mapping = deepcopy(mapping)
    old_mapping["cross_checks"][0].pop("quantity_relation")
    old = old_project_session(session, old_mapping, goal)
    assert old["status"] == "UNDETERMINED"
    assert old["reason"] == "projection.check_same_answer_quantity_only"
    mapped = project(historical)
    assert mapped["status"] == "MAPPED", mapped["reason"]
    assert mapped["actual_execution_and_support"]["Final_calculation_link"] == "tool:1"
    assert set(mapped["normalizations"]) == {"tool:1", "tool:2"}
    assert mapped["actual_main_support"] == mapped["normalizations"]["tool:1"]
    check = mapped["cross_quantity_checks"][0]
    assert check["actual_result_exact"] == "10"
    assert check["actual_expression"] == "b + c + d - e"
    assert check["actual_result_dependencies"] == []
    assert check["shared_active_source_ids_with_answer"] == ["source:q11n4"]
    assert check["statistical_independence_claimed"] is False
    assert check["creates_no_executed_R_or_residual"] is True
    assert check["offline_explanatory_identity"]["identity"] == "D-R=e-B"
    assert check["offline_explanatory_identity"]["is_model_execution"] is False
    signature = mapped["behavior_signature"]
    assert len(signature["substantive_revision_path"]) == 1
    assert signature["substantive_revision_path"][0]["semantic_key"]["before_USD_million"] == "6"
    assert len(signature["evidenced_cross_quantity_checks"]) == 1
    assert signature["evidenced_independent_cross_checks"] == []
    assert len(mapped["source_mapping_ledger"]) == 6
    assert all(
        item["interpreted_role"]
        and item["interpreted_period"]
        and item["interpreted_source_unit"] == "USD_million"
        and item["original_declaration_pointer"]
        and item["original_source_segment"]
        for item in mapped["source_mapping_ledger"]
    )
    assert before == {str(path): sha(path.read_bytes()) for path in paths}
    assert read(paths[0])["status"] == "UNDETERMINED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("period", "December 31, 2004"),
        ("unit", "EUR_million"),
        ("quantity", "ending_asset_retirement_obligation"),
    ],
)
def test_different_quantity_period_or_unit_is_not_cross_quantity_evidence(historical, field, value):
    historical[1]["cross_checks"][0]["quantity_relation"]["checked_quantity"] = {
        **historical[3]["checked_quantity"],
        field: value,
    }
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.same_object_period_unit"


@pytest.mark.parametrize(
    "field,value",
    [
        ("period", "fiscal 2004"),
        ("unit", "EUR_million"),
        ("role", "asset retirement obligation"),
    ],
)
def test_wrong_source_semantics_cannot_be_hidden_by_equal_check_result(historical, field, value):
    historical[1]["occurrences"]["tool:2"]["body.left.left.right"][field] = value
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.source_role_period_unit"


def test_actual_unit_declaration_cannot_be_relabelled_by_offline_ledger(historical):
    session, mapping, _, _ = historical
    session["turns"][1]["event"]["tool_call"]["arguments"]["variables"]["c"]["unit"] = "EUR_million"
    refresh(session, mapping)
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.actual_declared_unit"


def test_equal_value_wrong_disclosed_object_is_not_a_comparator(historical):
    # q21n3 is also 10, but is an asset-retirement obligation, not this reserve.
    historical[1]["cross_checks"][0]["quantity_relation"]["comparator_source_id"] = "source:q21n3"
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.actual_disclosed_comparator"


@pytest.mark.parametrize("missing_index", [1, 2])
def test_actual_check_call_and_actual_Final_evidence_both_required(historical, missing_index):
    check = historical[1]["cross_checks"][0]
    check["evidence"] = [
        item for item in check["evidence"] if item["response_index"] != missing_index
    ]
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] in {
        "projection.evidence_for_this_event",
        "cross_quantity.actual_Final_evidence_required",
    }


def test_prose_only_check_has_no_executed_result(historical):
    historical[1]["cross_checks"][0]["call_id"] = "unexecuted:ending_rebuild"
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "projection.actual_distinct_cross_check"


def test_actual_Final_link_cannot_be_borrowed_from_sibling_fields(historical):
    historical[1]["cross_checks"][0]["quantity_relation"]["final_link"]["pointer"] = [
        "outside_final",
        "explanation",
    ]
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"


def test_correct_answer_alone_does_not_supply_Final_check_connection(historical):
    session, mapping, _, _ = historical
    session["result"]["final"]["explanation"] = "The reserve increased by 6 million."
    mapping["cross_checks"][0]["quantity_relation"]["final_link"]["quote"] = session["result"][
        "final"
    ]["explanation"]
    refresh(session, mapping)
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.explicit_Final_corroboration"


def test_negated_Final_check_is_not_affirmative_corroboration(historical):
    session, mapping, _, _ = historical
    explanation = (
        "The ending warranty reserve is 10 million, but this is not corroborated by the check."
    )
    session["result"]["final"]["explanation"] = explanation
    mapping["cross_checks"][0]["quantity_relation"]["final_link"]["quote"] = explanation
    refresh(session, mapping)
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.negated_or_conflicting_Final_link"


def test_deleted_substantive_prediction_correction_cannot_manufacture_a_pure_class(historical):
    historical[1]["revisions"] = []
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.actual_prediction_revision_must_be_retained"


def test_actual_balance_check_cannot_be_erased_by_an_auxiliary_annotation(historical):
    historical[1]["cross_checks"] = []
    historical[1]["event_annotations"][1]["role"] = "auxiliary_calculation"
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.actual_check_must_be_retained"


def test_wrong_period_source_with_the_same_number_is_not_a_valid_reconstruction(historical):
    session, mapping, _, _ = historical
    call = session["turns"][1]["event"]["tool_call"]
    # The 2004 charge is also four, but is not the 2006 charge occurrence.
    call["arguments"]["variables"]["c"]["source"] = "source:q12n5"
    call["arguments"]["sources"]["c"] = "source:q12n5"
    occurrence = mapping["occurrences"]["tool:2"]["body.left.left.right"]
    occurrence["source_id"] = "source:q12n5"
    occurrence["period"] = "fiscal 2004"
    refresh(session, mapping)
    mapped = project(historical)
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.actual_rebuilt_ending_relation"


def test_frozen_context_cannot_be_rewritten_after_equal_number_observed(historical):
    context = deepcopy(historical[3])
    context["roles"]["e"]["source_id"] = "source:q21n3"
    mapped = project((*historical[:3], context))
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.exact_frozen_context"


def test_only_original_X2_target_can_register_the_balance_relation(historical):
    with pytest.raises(ValueError, match="only_frozen_X2_original_target"):
        x2_cross_quantity_context(
            historical[0]["public"],
            {**historical[2], "period": "2005 minus 2004"},
        )
    x1 = read(PREPARATION / "public/X1.json")
    with pytest.raises(ValueError, match="only_frozen_X2_original_target"):
        x2_cross_quantity_context(x1, historical[2])


def test_variable_names_and_raw_formatting_do_not_split_full_class(historical):
    before = project(historical)
    session, mapping, _, _ = historical
    call = session["turns"][0]["event"]["tool_call"]
    call["arguments"]["expression"] = "later - earlier"
    call["output"]["result"]["expression"] = "later - earlier"
    for old, new in (("a", "later"), ("b", "earlier")):
        call["arguments"]["variables"][new] = call["arguments"]["variables"].pop(old)
        call["arguments"]["sources"][new] = call["arguments"]["sources"].pop(old)
        call["output"]["result"]["resolved_variables"][new] = call["output"]["result"][
            "resolved_variables"
        ].pop(old)
    for occurrence in mapping["occurrences"]["tool:1"].values():
        occurrence["declaration_pointer"][1] = {
            "a": "later",
            "b": "earlier",
        }[occurrence["declaration_pointer"][1]]
    refresh(session, mapping)
    after = project(historical)
    assert after["status"] == "MAPPED", after["reason"]
    assert after["behavior_key"] == before["behavior_key"]
    assert after["raw_public_sequence"] != before["raw_public_sequence"]


def test_same_actual_behavior_has_new_condition_specific_full_ids(historical):
    session, mapping, goal, context = historical
    first = project(historical, condition_id="new_condition:endpoint")
    second = project(historical, condition_id="new_condition:movement")
    assert first["status"] == second["status"] == "MAPPED"
    assert first["actual_main_support"] == second["actual_main_support"]
    assert first["behavior_key"] != second["behavior_key"]


def synthetic(task, specs, *, answer_id, check_ids=()):
    """Construct actual synthetic event/response joins, not provider histories."""
    public = read(PREPARATION / f"public/{task}.json")
    private = read(PREPARATION / "private/evaluation_targets.json")[task]
    goal = private["goal_scope"]
    facts = {item["id"]: item for item in public["numeric_catalog"]}
    context = x2_cross_quantity_context(public, goal) if task == "X2" else None
    semantics = (
        {value["source_id"]: value for value in context["roles"].values()} if context else {}
    )
    calls, turns = {}, []
    mapping = {"occurrences": {}, "event_annotations": [], "revisions": [], "cross_checks": []}
    for index, (expression, bindings, message) in enumerate(specs):
        cid = f"tool:{index + 1}"
        variables, resolved, occurrences, dependencies = {}, {}, {}, []
        for name, sid in bindings.items():
            if sid.startswith("tool:"):
                value = calls[sid]["output"]["result"]["exact_value"]
                variables[name] = {"result_id": sid}
                resolved[name] = {"exact_value": value, "result_id": sid}
                dependencies.append(sid)
            else:
                value = facts[sid]["value"]
                variables[name] = {"value": value, "source": sid, "unit": "USD_million"}
                resolved[name] = {"exact_value": value, "result_id": None}

        def visit(node, address, *, bindings=bindings, resolved=resolved, occurrences=occurrences):
            if isinstance(node, ast.Name):
                sid = bindings[node.id]
                if sid.startswith("tool:"):
                    occurrences[address] = {"kind": "result", "result_id": sid}
                else:
                    role = semantics.get(
                        sid,
                        {
                            "role": "company-defined net revenue comparison",
                            "period": "2003 versus 2002",
                            "unit": "USD_million",
                        },
                    )
                    occurrences[address] = {
                        "kind": "source",
                        "source_id": sid,
                        "attribution": "model_declaration",
                        "declaration_pointer": ["variables", node.id, "source"],
                        **{field: role[field] for field in ("role", "period", "unit")},
                    }
                return Fraction(resolved[node.id]["exact_value"])
            if isinstance(node, ast.BinOp):
                left, right = (
                    visit(node.left, address + ".left"),
                    visit(node.right, address + ".right"),
                )
                return left + right if isinstance(node.op, ast.Add) else left - right
            raise AssertionError("synthetic finite additive fixture")

        value = str(visit(ast.parse(expression, mode="eval").body, "body"))
        arguments = {"expression": expression, "variables": variables}
        call = {
            "id": cid,
            "name": "calculate",
            "arguments": arguments,
            "output": {
                "call_id": cid,
                "tool": "calculate",
                "status": "ok",
                "result": {
                    "expression": expression,
                    "exact_value": value,
                    "value": value,
                    "resolved_variables": resolved,
                    "used_result_ids": sorted(set(dependencies)),
                },
            },
        }
        calls[cid] = call
        parsed = {"message": message, "tool": "calculate", "arguments": arguments}
        raw = encode(parsed)
        event = {
            "response_index": index,
            "raw_sha256": sha(raw),
            "tool_call": call,
            "final": False,
            "protocol_error": None,
        }
        turns.append(
            {
                "raw": raw,
                "event": event,
                "binding": {"response_index": index, "raw_response_sha256": sha(raw)},
            }
        )
        mapping["occurrences"][cid] = occurrences
    final = {
        "value": calls[answer_id]["output"]["result"]["exact_value"],
        "unit": "USD_million",
        "result_id": answer_id,
        "explanation": (
            "The actual net change is corroborated by the component check: "
            "the ending warranty reserve is 10 million."
        ),
    }
    raw = encode({"final": final})
    turns.append(
        {
            "raw": raw,
            "event": {
                "response_index": len(specs),
                "raw_sha256": sha(raw),
                "tool_call": None,
                "final": True,
                "protocol_error": None,
            },
            "binding": {"response_index": len(specs), "raw_response_sha256": sha(raw)},
        }
    )
    for index, turn in enumerate(turns):
        evidence = [{"response_index": index, "quote": turn["raw"].decode()}]
        mapping["event_annotations"].append(
            {
                "response_index": index,
                "role": "Final" if turn["event"]["final"] else "calculation",
                "interpretation": "Explicit synthetic fixture event.",
                "evidence": evidence,
            }
        )
        if turn["event"]["tool_call"]:
            cid = turn["event"]["tool_call"]["id"]
            for occurrence in mapping["occurrences"][cid].values():
                occurrence["evidence"] = evidence
    for cid in check_ids:
        index = int(cid.split(":")[1]) - 1
        mapping["cross_checks"].append(
            {
                "call_id": cid,
                "interpretation": "Executed synthetic check.",
                "evidence": [
                    {"response_index": index, "quote": turns[index]["raw"].decode()},
                    {"response_index": len(specs), "quote": turns[-1]["raw"].decode()},
                ],
            }
        )
    row = record(
        "synthetic_basis_projection_row",
        arm="movement",
        task_key=task,
        label="synthetic",
        formula_driven_trace_verified=True,
        answer_calculation_id=answer_id,
    )
    return (
        {"row": row, "public": public, "result": {"final": final}, "turns": turns},
        mapping,
        goal,
        context,
    )


def add_quantity_relation(case, cid):
    session, mapping, _, context = case
    check = next(item for item in mapping["cross_checks"] if item["call_id"] == cid)
    check["quantity_relation"] = {
        "relation_id": X2_ENDING_REBUILD_RELATION,
        "checked_quantity": context["checked_quantity"],
        "comparator_source_id": context["comparator_source_id"],
        "final_link": {
            "pointer": ["explanation"],
            "quote": session["result"]["final"]["explanation"],
        },
    }


@pytest.mark.parametrize("task", ["X1", "X2"])
def test_ordinary_same_target_executed_checks_remain_supported(task):
    if task == "X1":
        endpoints = {"e": "source:t4c1n0", "b": "source:t1c1n0"}
        movements = {"c": "source:t2c1n0", "a": "source:t3c1n0"}
        movement_expression = "c+a"
    else:
        endpoints = {"e": "source:q11n3", "b": "source:q11n4"}
        movements = {"c": "source:q12n3", "a": "source:q14n0", "o": "source:q13n0"}
        movement_expression = "c+a-o"
    case = synthetic(
        task,
        [
            (movement_expression, movements, "Executed component comparison check."),
            ("e-b", endpoints, "Main answer from disclosed comparison endpoints."),
        ],
        answer_id="tool:2",
        check_ids=["tool:1"],
    )
    mapped = project(case, condition_id="new_condition:movement")
    assert mapped["status"] == "MAPPED", mapped["reason"]
    assert len(mapped["behavior_signature"]["evidenced_independent_cross_checks"]) == 1
    assert mapped["behavior_signature"]["evidenced_cross_quantity_checks"] == []
    assert mapped["actual_main_support"]["active_source_ids"] == sorted(endpoints.values())


@pytest.mark.parametrize("mechanism", ["result_reference", "same_source_recalculation"])
def test_original_answer_inversion_is_not_an_additional_ending_check(mechanism):
    second = (
        ("answer+b", {"answer": "tool:1", "b": "source:q11n4"})
        if mechanism == "result_reference"
        else ("e-b+b", {"e": "source:q11n3", "b": "source:q11n4"})
    )
    case = synthetic(
        "X2",
        [
            ("e-b", {"e": "source:q11n3", "b": "source:q11n4"}, "Main endpoint change."),
            (*second, "Cross-check the ending reserve by mechanical inversion."),
        ],
        answer_id="tool:1",
        check_ids=["tool:2"],
    )
    add_quantity_relation(case, "tool:2")
    mapped = project(case, condition_id="new_condition:endpoint")
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == (
        "projection.cross_check_not_derived_from_answer"
        if mechanism == "result_reference"
        else "cross_quantity.actual_rebuilt_ending_relation"
    )


def test_component_result_dependencies_are_retained_without_inventing_R_execution():
    case = synthetic(
        "X2",
        [
            ("e-b", {"e": "source:q11n3", "b": "source:q11n4"}, "Main endpoint change."),
            ("c+a", {"c": "source:q12n3", "a": "source:q14n0"}, "Sum the warranty inflows."),
            (
                "b+inflows-o",
                {"b": "source:q11n4", "inflows": "tool:2", "o": "source:q13n0"},
                "Cross-check the ending warranty reserve.",
            ),
        ],
        answer_id="tool:1",
        check_ids=["tool:3"],
    )
    add_quantity_relation(case, "tool:3")
    mapped = project(case, condition_id="new_condition:endpoint")
    assert mapped["status"] == "MAPPED", mapped["reason"]
    assert mapped["cross_quantity_checks"][0]["actual_result_dependencies"] == ["tool:2"]
    assert mapped["cross_quantity_checks"][0]["check_ancestor_call_ids"] == ["tool:2", "tool:3"]
    assert mapped["actual_execution_and_support"]["dependency_edges"] == [
        {
            "producer_call_id": "tool:2",
            "consumer_call_id": "tool:3",
            "kind": "actual_result_id",
        }
    ]
    movement = case[3]["normalizations"]["movement"]["normal_form"]
    assert all(item["normal_form"] != movement for item in mapped["normalizations"].values())


def test_cancelled_original_endpoint_consumption_is_retained_as_a_scope_boundary():
    case = synthetic(
        "X2",
        [
            ("e-b", {"e": "source:q11n3", "b": "source:q11n4"}, "Main endpoint change."),
            (
                "e-b+b-e+b+c+a-o",
                {
                    "e": "source:q11n3",
                    "b": "source:q11n4",
                    "c": "source:q12n3",
                    "a": "source:q14n0",
                    "o": "source:q13n0",
                },
                "Cross-check with cancelled endpoint consumption.",
            ),
        ],
        answer_id="tool:1",
        check_ids=["tool:2"],
    )
    add_quantity_relation(case, "tool:2")
    mapped = project(case, condition_id="new_condition:endpoint")
    assert mapped["status"] == "UNDETERMINED"
    assert mapped["reason"] == "cross_quantity.no_cancelled_same_source_recalculation"
