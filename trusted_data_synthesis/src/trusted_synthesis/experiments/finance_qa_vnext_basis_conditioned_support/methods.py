"""Actual Final support features and NEW condition-bound complete class IDs.

The method stratum is not an equivalence relation. Only the actual main
calculation's source-symbolic normal form is compared with frozen financial
method prototypes. Requested guidance, final numeric equality, component
mentions, and auxiliary checks do not supply a principal method.

This module never runs the full projector implicitly. A supplied MAPPED
projection is separately checked against the interaction and complete semantic
signature before a new fine-class ID can be exposed for raw admission.
"""

from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.exploration import (
    normalize_executions,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.projection import (
    _pointer,
    _public_evidence,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.source import (
    _event_target,
    content_identity,
)

from .plan import condition, encode, record, require, sha

_TASK_VERSIONS = {
    "X1": "ETR/2004/page_239.pdf-2",
    "X2": "PPG/2006/page_42.pdf-4",
}
_ROUTES = {"D": "endpoint", "R": "movement"}
_ERRORS = (
    ValueError,
    KeyError,
    TypeError,
    IndexError,
    AttributeError,
    SyntaxError,
    RecursionError,
    ZeroDivisionError,
)


def method_prototypes(public, goal_scope, prototypes, *, task_key):
    """Strip legacy class/condition metadata; retain frozen source relations only."""
    require(task_key in _TASK_VERSIONS, "method.registered_task")
    require(public["task_id"] == _TASK_VERSIONS[task_key], "method.fixed_task_version")
    content_identity(public, "method.public_content_identity")
    require(
        isinstance(prototypes, dict) and set(prototypes) == set(_ROUTES),
        "method.two_financial_prototypes",
    )
    routes = {}
    for route, method in _ROUTES.items():
        signature = prototypes[route]["signature"]
        require(
            signature["task_version"] == public["task_id"]
            and signature["source_document_id"] == public["id"]
            and signature["goal_scope"] == goal_scope,
            "method.prototype_task_source_goal_binding",
        )
        active = signature["active_support"]
        require(
            isinstance(active, list) and active and len(set(active)) == len(active),
            "method.prototype_nonempty_unique_sources",
        )
        source_ids = {item["id"] for item in public["numeric_catalog"]}
        require(set(active) <= source_ids, "method.prototype_public_sources")
        routes[method] = {
            "source_normal_form": signature["answer_source_normal_form"],
            "active_support": active,
        }
    require(routes["endpoint"] != routes["movement"], "method.distinct_financial_methods")
    return record(
        "basis_actual_method_prototypes",
        task_key=task_key,
        task_version=public["task_id"],
        source_document_id=public["id"],
        goal_scope=goal_scope,
        methods=routes,
        old_condition_class_or_sample_identity_reused=False,
        method_is_not_an_equivalence_relation=True,
    )


def _bound_history(session):
    turns = {turn["binding"]["response_index"]: turn for turn in session["turns"]}
    require(len(turns) == len(session["turns"]), "method.unique_response_indices")
    require(list(turns) == sorted(turns), "method.chronological_history")
    result = session.get("result")
    actual_final = result.get("final") if isinstance(result, dict) else None
    calls, finals = {}, []
    for index, turn in turns.items():
        event = turn["event"]
        require(
            event["response_index"] == index
            and sha(turn["raw"]) == turn["binding"]["raw_response_sha256"] == event["raw_sha256"],
            "method.actual_public_response_binding",
        )
        _event_target(event, turn["raw"], actual_final)
        if event["final"]:
            finals.append(index)
        call = event["tool_call"]
        if call:
            require(call["id"] not in calls, "method.unique_actual_call_ids")
            calls[call["id"]] = {"index": index, "call": call}
    require(
        not finals or (len(finals) == 1 and finals[0] == max(turns)),
        "method.original_first_terminal_Final",
    )
    return turns, calls, finals[0] if finals else None


def _main_support(session, mapping, turns, calls, final_index):
    require(final_index is not None, "method.no_actual_Final")
    final = session["result"]["final"]
    selected = session["row"].get("answer_calculation_id")
    review = mapping.get("main_support")
    if review is None:
        require(isinstance(final, dict), "method.reviewed_Final_main_link_required")
        actual_id = final.get("result_id")
        require(
            isinstance(actual_id, str) and actual_id and actual_id == selected,
            "method.unique_actual_Final_result_link",
        )
        # Unreviewed additional result references do not become co-primary
        # evidence and cannot be silently discarded in favor of result_id.
        require(
            not any(final.get(key) for key in ("result_ids", "main_result_ids", "main_support")),
            "method.additional_Final_result_links_need_review",
        )
        ids = [actual_id]
        evidence = _public_evidence(
            [{"response_index": final_index, "quote": turns[final_index]["raw"].decode()}],
            turns,
            final_index,
            final_index,
        )
        links = [
            {
                "call_id": actual_id,
                "pointer": ["result_id"],
                "attribution": "actual_model_structured_Final_reference",
            }
        ]
        interpretation = "The original Final result_id uniquely selects this actual calculation."
    else:
        require(isinstance(review, dict), "method.main_support_review_object")
        require(review.get("status") == "CONFIRMED", "method.main_support_not_uniquely_established")
        ids = review.get("call_ids")
        require(
            isinstance(ids, list)
            and ids
            and all(isinstance(cid, str) for cid in ids)
            and len(set(ids)) == len(ids),
            "method.unique_reviewed_main_call_ids",
        )
        require(selected is None or selected in ids, "method.main_review_vs_selected_answer")
        evidence = _public_evidence(review.get("evidence"), turns, final_index, final_index)
        interpretation = review.get("interpretation")
        require(
            isinstance(interpretation, str) and interpretation,
            "method.main_review_interpretation",
        )
        links = review.get("links")
        require(
            isinstance(links, list)
            and len(links) == len(ids)
            and {item.get("call_id") for item in links} == set(ids),
            "method.every_main_chain_has_Final_link",
        )
        for link in links:
            target = _pointer(final, link.get("pointer"))
            if target == link["call_id"]:
                continue
            quote = link.get("quote")
            require(
                isinstance(target, str)
                and isinstance(quote, str)
                and quote
                and quote in target
                and link.get("attribution") == "reviewer_interpretation",
                "method.reviewed_text_inside_actual_Final",
            )
    checks = {item["call_id"] for item in mapping.get("cross_checks", [])}
    require(not (checks & set(ids)), "method.check_not_a_principal_basis")
    for cid in ids:
        require(
            cid in calls
            and calls[cid]["index"] < final_index
            and calls[cid]["call"]["name"] == "calculate"
            and calls[cid]["call"]["output"]["status"] == "ok",
            "method.actual_successful_pre_Final_main_calculation",
        )
    return ids, {
        "evidence": evidence,
        "links": links,
        "interpretation": interpretation,
        "reviewer_interpretations_are_not_added_model_declarations": True,
    }


def _route(normal, methods):
    if not isinstance(normal, dict) or normal.get("status") != "MAPPED":
        return "UNDETERMINED"
    matches = [
        method
        for method, target in methods.items()
        if normal["normal_form"] == target["source_normal_form"]
        and normal["active_source_ids"] == target["active_support"]
    ]
    return matches[0] if len(matches) == 1 else "UNDETERMINED"


def _fine_class(session, mapping, goal_scope, condition_id, projection, observed, main_ids):
    if projection is None:
        return "NOT_MEASURED", None, None
    try:
        content_identity(projection, "class.projection_content_identity")
        row, public = session["row"], session["public"]
        require(
            projection["session_label"] == row["label"]
            and projection["source_closeout_id"] == row["id"]
            and projection["population"] == row["arm"]
            and projection["task_key"] == row["task_key"]
            and projection["task_version"] == public["task_id"]
            and projection["source_document_id"] == public["id"]
            and projection["requested_condition_id"] == condition_id,
            "class.projection_interaction_condition_task_binding",
        )
        require(
            isinstance(condition_id, str)
            and condition_id
            and (
                row.get("offline_historical_boundary_reference") is True
                or condition_id == condition(row["arm"])["id"]
            ),
            "class.new_condition_not_old_or_other_guidance",
        )
        require(
            row.get("condition_id", condition_id) == condition_id,
            "class.registered_condition_binding",
        )
        raw_view = [
            {
                "response_index": turn["binding"]["response_index"],
                "raw_response": turn["raw"].decode(),
                "binding": turn["binding"],
                "event": turn["event"],
            }
            for turn in session["turns"]
        ]
        require(
            projection["raw_public_sequence"] == raw_view,
            "class.projection_same_complete_public_interaction",
        )
        if projection["status"] != "MAPPED":
            require(projection["status"] == "UNDETERMINED", "class.known_mapping_status")
            return "UNDETERMINED", None, projection.get("reason")
        require(
            len(main_ids) == 1 and main_ids[0] == row.get("answer_calculation_id"),
            "class.multiple_or_unresolved_main_chains_outside_full_signature",
        )
        signature = projection["behavior_signature"]
        require(
            projection["behavior_key"] == sha(encode(signature))
            and signature["fixed_condition"] == condition_id
            and signature["task_version"] == public["task_id"]
            and signature["source_document_id"] == public["id"]
            and signature["goal_scope"] == goal_scope,
            "class.complete_signature_condition_task_goal_binding",
        )
        answer = observed["normalizations"].get(main_ids[0], {})
        require(
            answer.get("status") == "MAPPED"
            and signature["answer_source_normal_form"] == answer["normal_form"]
            and signature["active_support"] == answer["active_source_ids"]
            and projection["actual_execution_and_support"]["Final_original"]
            == session["result"]["final"]
            and projection["actual_execution_and_support"]["Final_calculation_link"] == main_ids[0],
            "class.actual_Final_main_source_normal_form",
        )
        revisions = [
            {"change_kind": item["change_kind"], "semantic_key": item["semantic_key"]}
            for item in sorted(
                mapping.get("revisions", []),
                key=lambda item: (item["before_index"], item["after_index"]),
            )
            if item["change_kind"] == "substantive"
        ]
        require(
            signature["substantive_revision_path"] == revisions,
            "class.substantive_revisions_must_not_be_dropped",
        )
        annotations = projection["model_public_relations"]["event_annotations"]
        observed_checks = [
            item
            for item in annotations
            if item.get("kind")
            in {
                "executed_same_target_cross_check_review",
                "executed_cross_quantity_check_review",
            }
        ]
        require(
            {item["call_id"] for item in observed_checks}
            == {item["call_id"] for item in mapping.get("cross_checks", [])},
            "class.actual_checks_must_not_be_dropped",
        )
        for kind, field in (
            ("executed_same_target_cross_check_review", "evidenced_independent_cross_checks"),
            ("executed_cross_quantity_check_review", "evidenced_cross_quantity_checks"),
        ):
            components = {
                sha(encode(item["signature_component"])): item["signature_component"]
                for item in observed_checks
                if item["kind"] == kind
            }
            require(
                signature[field] == [components[key] for key in sorted(components)],
                "class.complete_check_signature_retained",
            )
        fine = record(
            "basis_complete_behavior_class",
            condition_id=condition_id,
            requested_basis=row["arm"],
            task_key=row["task_key"],
            task_version=public["task_id"],
            source_document_id=public["id"],
            goal_scope=goal_scope,
            behavior_signature=signature,
            behavior_key=projection["behavior_key"],
            class_definition="full source-symbolic support, substantive revision path, and checks",
            method_stratum_is_not_the_class_definition=True,
            old_class_identity_reused=False,
        )
        return "MAPPED", fine, None
    except _ERRORS as error:
        return "UNDETERMINED", None, str(error)


def classify_method(session, mapping, goal_scope, prototypes, condition_id, *, projection=None):
    """Describe the actual main method and independently certify a new full class.

    prototypes is the single-task D/R dict from the frozen financial normal-form
    registry. mapping.main_support is optional; CONFIRMED multiple principal
    calls require one exact actual-Final link each. Text links retain explicit
    reviewer attribution. The fallback uses only the actual Final.result_id and
    its existing reviewed answer_calculation_id, never an equal numeric answer.

    A supplied projection is not recomputed. Failure/unknown financial validity
    or full mapping does not erase a known actual method feature, but admission
    requires joint validity, a bound MAPPED complete class, and a unique method.
    """
    row = session["row"]
    method, reason, main_ids, link_review = "UNDETERMINED", None, [], None
    observed = {"normalizations": {}, "source_mapping_ledger": [], "unresolved_calculation_ids": []}
    per_call, registry = {}, None
    try:
        require(isinstance(mapping, dict), "method.explicit_mapping_required")
        registry = method_prototypes(
            session["public"],
            goal_scope,
            prototypes,
            task_key=row["task_key"],
        )
        turns, calls, final_index = _bound_history(session)
        observed = normalize_executions(session, mapping)
        per_call = {
            cid: _route(normal, registry["methods"])
            for cid, normal in observed["normalizations"].items()
        }
        main_ids, link_review = _main_support(session, mapping, turns, calls, final_index)
        selected = {per_call.get(cid, "UNDETERMINED") for cid in main_ids}
        if "UNDETERMINED" in selected:
            reason = "method.main_source_relation_outside_registered_method_domain"
        elif len(selected) == 1:
            method = next(iter(selected))
        else:
            method = "MIXED"
            reason = "method.multiple_actual_primary_financial_bases"
    except _ERRORS as error:
        reason = str(error)
    full_status, fine, full_reason = _fine_class(
        session,
        mapping,
        goal_scope,
        condition_id,
        projection,
        observed,
        main_ids,
    )
    joint_valid = row.get("formula_driven_trace_verified") is True
    raw_admissible = (
        joint_valid
        and full_status == "MAPPED"
        and fine is not None
        and method in {"endpoint", "movement"}
        and row.get("offline_historical_boundary_reference") is not True
    )
    return record(
        "basis_actual_method_classification",
        session_label=row["label"],
        task_key=row["task_key"],
        requested_basis=row["arm"],
        condition_id=condition_id,
        method_stratum=method,
        reason=reason,
        main_support_call_ids=main_ids,
        actual_Final_main_support=link_review,
        per_call_method=per_call,
        observed_execution_mapping=observed,
        method_prototype_id=registry["id"] if registry else None,
        original_financial_delivery_validity=row.get("formula_driven_trace_verified"),
        joint_valid_package=joint_valid,
        full_mapping_status=full_status,
        full_mapping_reason=full_reason,
        fine_class_id=fine["id"] if fine else None,
        fine_class=fine,
        raw_admissible=raw_admissible,
        method_classification_is_not_financial_validity_or_full_class_certification=True,
        requested_guidance_used_to_assign_method=False,
        numeric_answer_equality_used_to_assign_method=False,
        cross_checks_used_as_main_bases=False,
        method_is_not_an_equivalence_relation=True,
        projector_called_implicitly=False,
    )
