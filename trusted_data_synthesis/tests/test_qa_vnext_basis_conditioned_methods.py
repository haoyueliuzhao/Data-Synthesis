"""Static actual-method and full-class controls for the NEW basis study only."""

import json
from copy import deepcopy

import pytest
from test_qa_vnext_basis_conditioned_projection import (
    PREPARATION,
    REFERENCE_CONDITION,
    read,
    refresh,
    synthetic,
)
from test_qa_vnext_basis_conditioned_projection import (
    historical as historical,
)
from test_qa_vnext_basis_conditioned_projection import (
    project as project_reference,
)

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.methods import (
    classify_method,
    method_prototypes,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    condition,
    encode,
    record,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.projection import (
    project_session,
)


def prototypes(task):
    frozen = read(PREPARATION / "private/target_class_prototypes.json")["tasks"]["E"][task]
    fields = (
        "task_version",
        "source_document_id",
        "goal_scope",
        "answer_source_normal_form",
        "active_support",
    )
    return {
        route: {"signature": {field: frozen[route]["signature"][field] for field in fields}}
        for route in ("D", "R")
    }


def single(task="X2", method="endpoint", requested="movement"):
    if task == "X1":
        expression, bindings = (
            ("e-b", {"e": "source:t4c1n0", "b": "source:t1c1n0"})
            if method == "endpoint"
            else ("c+a", {"c": "source:t2c1n0", "a": "source:t3c1n0"})
        )
    else:
        expression, bindings = (
            ("e-b", {"e": "source:q11n3", "b": "source:q11n4"})
            if method == "endpoint"
            else ("c+a-o", {"c": "source:q12n3", "a": "source:q14n0", "o": "source:q13n0"})
        )
    case = synthetic(
        task,
        [(expression, bindings, "Execute the actual main comparison relation.")],
        answer_id="tool:1",
    )
    session, mapping, _, _ = case
    row = session["row"]
    session["row"] = record(
        "synthetic_basis_method_row",
        **{
            key: value
            for key, value in row.items()
            if key not in {"id", "schema_version", "arm", "label"}
        },
        arm=requested,
        label=f"synthetic_{task}_{requested}_{method}",
        condition_id=condition(requested)["id"],
    )
    session["result"]["final"]["explanation"] = "The main result is the executed comparison."
    refresh(session, mapping)
    return case


def projected(case):
    session, mapping, goal, context = case
    cond = (
        REFERENCE_CONDITION
        if session["row"].get("offline_historical_boundary_reference")
        else condition(session["row"]["arm"])["id"]
    )
    return project_session(
        session,
        mapping,
        goal,
        condition_id=cond,
        cross_quantity_context=context,
    )


def classify(case, *, projection=None, prototype=None, condition_id=None):
    session, mapping, goal, _ = case
    cond = condition_id or (
        REFERENCE_CONDITION
        if session["row"].get("offline_historical_boundary_reference")
        else condition(session["row"]["arm"])["id"]
    )
    return classify_method(
        session,
        mapping,
        goal,
        prototype or prototypes(session["row"]["task_key"]),
        cond,
        projection=projection,
    )


def reissue_projection(projection, **updates):
    return record(
        "basis_conditioned_support_projection",
        **{**{k: v for k, v in projection.items() if k not in {"id", "schema_version"}}, **updates},
    )


@pytest.mark.parametrize("task", ["X1", "X2"])
@pytest.mark.parametrize("method,requested", [("endpoint", "movement"), ("movement", "endpoint")])
def test_actual_method_is_not_the_requested_guidance(task, method, requested):
    case = single(task, method, requested)
    full = projected(case)
    assert full["status"] == "MAPPED", full["reason"]
    result = classify(case, projection=full)
    assert result["requested_basis"] == requested
    assert result["method_stratum"] == method
    assert result["raw_admissible"] is True
    assert result["full_mapping_status"] == "MAPPED"
    assert result["fine_class_id"].startswith("basis_complete_behavior_class:")
    assert result["requested_guidance_used_to_assign_method"] is False


def test_no_projection_is_not_implicitly_completed_or_admitted():
    case = single()
    result = classify(case)
    assert result["method_stratum"] == "endpoint"
    assert result["full_mapping_status"] == "NOT_MEASURED"
    assert result["fine_class_id"] is None
    assert result["raw_admissible"] is False
    assert result["projector_called_implicitly"] is False


@pytest.mark.parametrize("validity", [False, None])
def test_financial_failure_or_unknown_does_not_erase_known_method(validity):
    case = single()
    case[0]["row"]["formula_driven_trace_verified"] = validity
    case[0]["result"]["final"]["value"] = "999"  # Not a source or method lookup key.
    refresh(case[0], case[1])
    result = classify(case)
    assert result["method_stratum"] == "endpoint"
    assert result["original_financial_delivery_validity"] is validity
    assert result["joint_valid_package"] is False
    assert result["raw_admissible"] is False
    assert result["numeric_answer_equality_used_to_assign_method"] is False


def test_historical_endpoint_plus_actual_balance_check_is_not_a_movement_main(historical):
    full = project_reference(historical)
    result = classify(historical, projection=full)
    assert result["method_stratum"] == "endpoint"
    assert result["main_support_call_ids"] == ["tool:1"]
    assert result["per_call_method"] == {"tool:1": "endpoint", "tool:2": "UNDETERMINED"}
    assert result["full_mapping_status"] == "MAPPED"
    assert len(result["fine_class"]["behavior_signature"]["evidenced_cross_quantity_checks"]) == 1
    assert len(result["fine_class"]["behavior_signature"]["substantive_revision_path"]) == 1
    # A historical boundary reference is not a new package.
    assert result["raw_admissible"] is False


def test_valid_but_full_mapping_unknown_keeps_known_method_without_admission(historical):
    historical[1]["cross_checks"][0].pop("quantity_relation")
    full = projected(historical)
    assert full["status"] == "UNDETERMINED"
    result = classify(historical, projection=full)
    assert result["method_stratum"] == "endpoint"
    assert result["original_financial_delivery_validity"] is True
    assert result["full_mapping_status"] == "UNDETERMINED"
    assert result["fine_class_id"] is None
    assert result["raw_admissible"] is False


def mixed():
    case = synthetic(
        "X2",
        [
            ("e-b", {"e": "source:q11n3", "b": "source:q11n4"}, "Main endpoint basis."),
            (
                "c+a-o",
                {"c": "source:q12n3", "a": "source:q14n0", "o": "source:q13n0"},
                "A second primary component basis.",
            ),
        ],
        answer_id="tool:1",
    )
    session, mapping, _, _ = case
    session["result"]["final"]["main_result_ids"] = ["tool:1", "tool:2"]
    session["result"]["final"]["explanation"] = "Both executed results are primary answer bases."
    # Existing single-main projector cannot encode this additional main status;
    # the method classifier must prevent its resulting partial signature admission.
    mapping["event_annotations"][1]["role"] = "auxiliary_calculation"
    refresh(session, mapping)
    final_index = len(session["turns"]) - 1
    mapping["main_support"] = {
        "status": "CONFIRMED",
        "call_ids": ["tool:1", "tool:2"],
        "evidence": [
            {
                "response_index": final_index,
                "quote": session["turns"][-1]["raw"].decode(),
            }
        ],
        "interpretation": "The synthetic Final explicitly identifies two primary results.",
        "links": [
            {"call_id": "tool:1", "pointer": ["main_result_ids", 0]},
            {"call_id": "tool:2", "pointer": ["main_result_ids", 1]},
        ],
    }
    return case


def test_two_actual_main_bases_are_MIXED_and_single_main_signature_not_admitted():
    case = mixed()
    full = projected(case)
    assert full["status"] == "MAPPED", full["reason"]
    result = classify(case, projection=full)
    assert result["method_stratum"] == "MIXED"
    assert result["main_support_call_ids"] == ["tool:1", "tool:2"]
    assert result["full_mapping_status"] == "UNDETERMINED"
    assert result["full_mapping_reason"] == (
        "class.multiple_or_unresolved_main_chains_outside_full_signature"
    )
    assert result["fine_class_id"] is None
    assert result["raw_admissible"] is False


def test_multiple_unreviewed_Final_result_links_are_not_forced_into_one_method():
    case = mixed()
    case[1].pop("main_support")
    result = classify(case)
    assert result["method_stratum"] == "UNDETERMINED"
    assert result["reason"] == "method.additional_Final_result_links_need_review"


def test_unresolved_review_does_not_choose_a_main_method():
    case = mixed()
    case[1]["main_support"]["status"] = "UNDETERMINED"
    result = classify(case)
    assert result["method_stratum"] == "UNDETERMINED"
    assert result["per_call_method"] == {"tool:1": "endpoint", "tool:2": "movement"}


@pytest.mark.parametrize("wrong", ["period", "object"])
def test_equal_number_from_wrong_period_or_object_does_not_determine_method(wrong):
    case = single(method="movement") if wrong == "period" else single(method="endpoint")
    session, mapping, _, _ = case
    call = session["turns"][0]["event"]["tool_call"]
    variable, incorrect_sid = ("c", "source:q12n5") if wrong == "period" else ("e", "source:q21n3")
    original_sid = call["arguments"]["variables"][variable]["source"]
    call["arguments"]["variables"][variable]["source"] = incorrect_sid
    for entry in mapping["occurrences"]["tool:1"].values():
        if entry["source_id"] == original_sid:
            entry["source_id"] = incorrect_sid
    refresh(session, mapping)
    assert call["output"]["result"]["exact_value"] == "6"
    result = classify(case)
    assert result["method_stratum"] == "UNDETERMINED"
    assert result["raw_admissible"] is False


def test_literal_correct_answer_without_sources_is_not_a_method():
    case = single()
    session, mapping, _, _ = case
    call = session["turns"][0]["event"]["tool_call"]
    call["arguments"] = {"expression": "6"}
    call["output"]["result"].update(expression="6", resolved_variables={})
    mapping["occurrences"]["tool:1"] = {
        "body": {
            "kind": "constant",
            "value": "6",
            "reason": "Actually executed literal, no source.",
            "evidence": [{"response_index": 0, "quote": session["turns"][0]["raw"].decode()}],
        },
    }
    refresh(session, mapping)
    result = classify(case)
    assert result["method_stratum"] == "UNDETERMINED"


def test_component_execution_with_only_no_Final_has_no_main_method():
    case = single(method="movement")
    case[0]["turns"] = case[0]["turns"][:-1]
    case[0]["result"]["final"] = None
    result = classify(case)
    assert result["method_stratum"] == "UNDETERMINED"
    assert result["reason"] == "method.no_actual_Final"
    assert result["per_call_method"]["tool:1"] == "movement"


def test_actual_component_result_chain_is_movement():
    case = synthetic(
        "X2",
        [
            ("c+a", {"c": "source:q12n3", "a": "source:q14n0"}, "Sum warranty inflows."),
            ("inflows-o", {"inflows": "tool:1", "o": "source:q13n0"}, "Main net movement."),
        ],
        answer_id="tool:2",
    )
    result = classify(case, projection=projected(case))
    assert result["method_stratum"] == "movement"
    assert result["main_support_call_ids"] == ["tool:2"]
    result_entries = [
        item
        for item in result["observed_execution_mapping"]["source_mapping_ledger"]
        if item["kind"] == "result"
    ]
    assert result_entries[0]["producer_call_id"] == "tool:1"


def test_balance_reconstruction_cannot_be_claimed_as_movement_principal():
    case = synthetic(
        "X2",
        [
            (
                "b+c+a-o",
                {
                    "b": "source:q11n4",
                    "c": "source:q12n3",
                    "a": "source:q14n0",
                    "o": "source:q13n0",
                },
                "Rebuild the ending warranty reserve.",
            ),
        ],
        answer_id="tool:1",
    )
    result = classify(case)
    assert result["method_stratum"] == "UNDETERMINED"


def test_cross_check_role_cannot_also_be_a_primary_method(historical):
    session, mapping, _, _ = historical
    mapping["main_support"] = {
        "status": "CONFIRMED",
        "call_ids": ["tool:1", "tool:2"],
        "evidence": [{"response_index": 2, "quote": session["turns"][-1]["raw"].decode()}],
        "interpretation": "Deliberately conflicting synthetic primary/check annotation.",
        "links": [
            {"call_id": "tool:1", "pointer": ["result_id"]},
            {
                "call_id": "tool:2",
                "pointer": ["explanation"],
                "quote": session["result"]["final"]["explanation"],
                "attribution": "reviewer_interpretation",
            },
        ],
    }
    result = classify(historical)
    assert result["method_stratum"] == "UNDETERMINED"
    assert result["reason"] == "method.check_not_a_principal_basis"


@pytest.mark.parametrize(
    "field",
    [
        "requested_condition_id",
        "task_key",
        "source_document_id",
        "source_closeout_id",
    ],
)
def test_wrong_projection_condition_task_or_interaction_cannot_supply_class_id(field):
    case = single()
    full = projected(case)
    full = reissue_projection(full, **{field: "deliberately_wrong"})
    result = classify(case, projection=full)
    assert result["method_stratum"] == "endpoint"
    assert result["full_mapping_status"] == "UNDETERMINED"
    assert result["fine_class_id"] is None
    assert result["raw_admissible"] is False


def test_correct_projection_cannot_be_attached_to_different_actual_response_bytes():
    case = single()
    full = projected(case)
    changed = deepcopy(full["raw_public_sequence"])
    changed[0]["raw_response"] = '{"message":"different packet"}'
    full = reissue_projection(full, raw_public_sequence=changed)
    result = classify(case, projection=full)
    assert result["method_stratum"] == "endpoint"
    assert result["full_mapping_reason"] == "class.projection_same_complete_public_interaction"
    assert result["fine_class_id"] is None


@pytest.mark.parametrize(
    "field",
    [
        "fixed_condition",
        "task_version",
        "source_document_id",
        "goal_scope",
    ],
)
def test_full_signature_itself_is_bound_to_new_condition_task_and_goal(field):
    case = single()
    full = projected(case)
    signature = deepcopy(full["behavior_signature"])
    signature[field] = "deliberately_wrong"
    full = reissue_projection(
        full, behavior_signature=signature, behavior_key=sha(encode(signature))
    )
    result = classify(case, projection=full)
    assert result["method_stratum"] == "endpoint"
    assert result["full_mapping_status"] == "UNDETERMINED"
    assert result["fine_class_id"] is None


@pytest.mark.parametrize("field", ["substantive_revision_path", "evidenced_cross_quantity_checks"])
def test_erased_revision_or_actual_check_cannot_manufacture_a_simpler_class(historical, field):
    full = projected(historical)
    signature = deepcopy(full["behavior_signature"])
    signature[field] = []
    full = reissue_projection(
        full, behavior_signature=signature, behavior_key=sha(encode(signature))
    )
    result = classify(historical, projection=full)
    assert result["method_stratum"] == "endpoint"
    assert result["full_mapping_status"] == "UNDETERMINED"
    assert result["fine_class_id"] is None


def test_wrong_task_prototype_is_not_matched_by_equal_final_value():
    case = single(task="X2")
    result = classify(case, prototype=prototypes("X1"))
    assert result["method_stratum"] == "UNDETERMINED"
    assert result["reason"] == "method.prototype_task_source_goal_binding"


def test_legacy_class_metadata_is_never_reused_for_new_fine_identity():
    case = single()
    old = read(PREPARATION / "private/target_class_prototypes.json")["tasks"]["E"]["X2"]
    registry = method_prototypes(case[0]["public"], case[2], old, task_key="X2")
    serialized = encode(registry).decode()
    assert "fixed_exploration_condition:" not in serialized
    assert "precall_pure_target_class:" not in serialized
    full = projected(case)
    first = classify(case, projection=full)
    second = classify(case, prototype=old, projection=full)
    assert first["fine_class_id"] == second["fine_class_id"]


def test_same_method_across_two_new_requested_conditions_has_distinct_full_ids():
    first_case = single(requested="endpoint")
    second_case = single(requested="movement")
    first = classify(first_case, projection=projected(first_case))
    second = classify(second_case, projection=projected(second_case))
    assert first["method_stratum"] == second["method_stratum"] == "endpoint"
    assert first["fine_class_id"] != second["fine_class_id"]


def test_original_text_and_session_identity_do_not_split_the_same_full_class():
    first_case = single()
    second_case = single()
    session, mapping, _, _ = second_case
    session["row"] = record(
        "synthetic_basis_method_row",
        **{
            key: value
            for key, value in session["row"].items()
            if key not in {"id", "schema_version", "label"}
        },
        label="another_independent_synthetic_packet",
    )
    parsed = json.loads(session["turns"][0]["raw"])
    parsed["message"] = "Use the disclosed comparison endpoints for the requested difference."
    session["turns"][0]["raw"] = encode(parsed)
    refresh(session, mapping)
    first = classify(first_case, projection=projected(first_case))
    second = classify(second_case, projection=projected(second_case))
    assert first["session_label"] != second["session_label"]
    assert first["fine_class_id"] == second["fine_class_id"]


def test_same_method_with_real_substantive_revision_keeps_a_distinct_full_class():
    case = single()
    before = classify(case, projection=projected(case))
    session, mapping, _, _ = case
    parsed = json.loads(session["turns"][0]["raw"])
    parsed["message"] = "I predict a change of seven million; execute the endpoint calculation."
    session["turns"][0]["raw"] = encode(parsed)
    session["result"]["final"]["explanation"] = (
        "The earlier prediction of seven was incorrect; the executed change is six million."
    )
    refresh(session, mapping)
    mapping["revisions"] = [
        {
            "before_index": 0,
            "after_index": 1,
            "change_kind": "substantive",
            "semantic_key": {
                "quantity": "net_change_product_warranty_reserve",
                "from": "7",
                "to": "6",
            },
            "interpretation": "A synthetic real public prediction was substantively corrected.",
            "evidence": [
                {"response_index": index, "quote": turn["raw"].decode()}
                for index, turn in enumerate(session["turns"])
            ],
        }
    ]
    after = classify(case, projection=projected(case))
    assert before["method_stratum"] == after["method_stratum"] == "endpoint"
    assert before["fine_class_id"] != after["fine_class_id"]
    assert len(after["fine_class"]["behavior_signature"]["substantive_revision_path"]) == 1


def test_reviewed_text_main_link_stays_inside_actual_Final_and_keeps_attribution():
    case = single()
    session, mapping, _, _ = case
    session["result"]["final"].pop("result_id")
    session["result"]["final"]["explanation"] = (
        "The answer is based on the actual tool:1 calculation."
    )
    refresh(session, mapping)
    assert classify(case)["method_stratum"] == "UNDETERMINED"
    mapping["main_support"] = {
        "status": "CONFIRMED",
        "call_ids": ["tool:1"],
        "interpretation": "The actual Final identifies the selected calculation in public text.",
        "evidence": [{"response_index": 1, "quote": session["turns"][-1]["raw"].decode()}],
        "links": [
            {
                "call_id": "tool:1",
                "pointer": ["explanation"],
                "quote": session["result"]["final"]["explanation"],
                "attribution": "reviewer_interpretation",
            }
        ],
    }
    result = classify(case)
    assert result["method_stratum"] == "endpoint"
    assert (
        result["actual_Final_main_support"]["links"][0]["attribution"] == "reviewer_interpretation"
    )
    mapping["main_support"]["links"][0]["pointer"] = ["outside_actual_Final"]
    assert classify(case)["method_stratum"] == "UNDETERMINED"
