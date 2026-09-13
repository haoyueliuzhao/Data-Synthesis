"""New bounded executed-history quotient, preserving the old assessment.

Errors and unused arithmetic are observable events, not evidence of cognitive
intent.  No failed prefix is removed, no implicit revision edge is invented,
and no error response becomes a positive target merely by receiving a class.
The caller must first replay the complete session in its registered runtime.
"""

import copy

from ..finance_qa_vnext_catalog_bridge.assessment import assess_replayed_session
from . import protocol as p

RESOLVABLE_REASONS = {
    "failed_tool_requires_complete_class_review",
    "format_recovery_complete_class_review",
    "non_support_calculation_intent_unresolved",
}
ERROR_DOMAIN = {
    "tool.unit_dimension_conflict",
    "tool.adjacent_single_row_amount",
    "tool.multiple_or_missing_numeric_bodies",
    "tool.table_cell_coordinates",
    "tool.table_cell_out_of_range",
    "tool.incomplete_or_nonnumeric_amount",
    "tool.unknown_public_source",
    "tool.json_record_has_no_cells",
    "tool.unknown_unit",
    "tool.read_arguments",
    "tool.calculate_arguments",
    "tool.revision_requires_prior_calculation",
}


def _fields(row):
    return {key: value for key, value in row.items() if key not in {"id", "schema_version"}}


def assess_new_semantics(session, prepared_fixture, original_assessment=None):
    """Pure offline assessment after full replay; authentication is separate.

    Return the same financial/method/mapping keys expected by material consumers,
    together with both the untouched original assessment and new source result.
    ``enriched_native_bindings`` is never supplied to the online model runtime.
    """
    bundle = prepared_fixture["bundle"]
    boundary = prepared_fixture["source_boundary"]
    p.checked(boundary, "fixture_source_boundary")
    p.require(
        boundary["task_id"] == session["identity"]["task_id"]
        and boundary["bundle_id"] == bundle["id"]
        and boundary["original_native_bindings_sha256"]
        == p.sha(p.encode(prepared_fixture["native_bindings"]))
        and boundary["enriched_native_bindings_sha256"]
        == p.sha(p.encode(prepared_fixture["enriched_native_bindings"])),
        "semantics.frozen_private_source_boundary",
    )
    original = assess_replayed_session(session, bundle, prepared_fixture["native_bindings"])
    if original_assessment is not None:
        p.require(original == original_assessment, "semantics.original_regression_unchanged")
    source_result = assess_replayed_session(
        session, bundle, prepared_fixture["enriched_native_bindings"]
    )
    outcome = _fields(source_result)
    outcome.update(
        original_semantic_assessment=original,
        source_extended_assessment=source_result,
        source_boundary_id=boundary["id"],
        original_results_not_rewritten=True,
        mapping_version="executed_history_with_explicit_rejections_and_side_calculations.v1",
        training_eligible=False,
    )
    signature = source_result.get("full_signature")
    if not signature or not source_result["financial_valid"]:
        return p.record("new_semantic_assessment", **outcome)
    pending = set(source_result.get("full_mapping_pending_reasons", [])) - RESOLVABLE_REASONS
    semantic_events = copy.deepcopy(signature["events"])
    by_result = {row["result_id"]: row for row in semantic_events}
    rejected, protocol_rejections = [], []
    support = set(source_result["support_result_ids"])
    for event, turn in zip(session["events"], session["turns"], strict=True):
        p.require(
            event["response_index"] == turn["response_index"]
            and p.sha(turn["raw_response"]) == turn["raw_response_sha256"],
            "semantics.original_response_join",
        )
        if event["protocol_error"]:
            # The runtime has already rejected this exact response; encoding the
            # rejection does not parse/execute the fragment or invent an action.
            protocol_rejections.append(
                {
                    "response_index": event["response_index"],
                    "kind": "runtime_protocol_rejected_response",
                    "runtime_error": event["protocol_error"],
                    "raw_response_sha256": turn["raw_response_sha256"],
                    "tool_executed": False,
                    "later_response_exists": event["response_index"] < session["first_final_index"],
                    "implicit_repair_or_revision_edge": False,
                }
            )
        tool = event["tool_call"]
        if not tool:
            continue
        row = by_result.get(tool["call_id"])
        if tool["status"] != "ok":
            error = tool.get("error")
            if error not in ERROR_DOMAIN:
                pending.add("unknown_failed_tool_execution_semantics:" + str(error))
            p.require(tool["call_id"] not in support, "semantics.failed_event_not_final_support")
            rejection = {
                "result_id": tool["call_id"],
                "response_index": event["response_index"],
                "kind": "deterministic_tool_rejection",
                "tool": tool["tool"],
                "status": tool["status"],
                "error": error,
                "attempted_arguments": tool["arguments"],
                "raw_response_sha256": turn["raw_response_sha256"],
                "numeric_result_created": False,
                "in_final_dependency_closure": False,
                "implicit_repair_or_revision_edge": False,
            }
            rejected.append(rejection)
            if row is not None:
                row.clear()
                row.update(rejection)
        elif row is not None and row.get("role") == "non_support_calculation_intent_unresolved":
            p.require(
                row.get("canonical_program") is not None and tool["call_id"] not in support,
                "semantics.source_resolved_side_calculation",
            )
            row.update(
                role="executed_side_calculation_not_in_final_dependency_closure",
                inferred_cognitive_intent=None,
                implicit_revision=False,
                in_final_dependency_closure=False,
            )
    new_signature = p.record(
        "executed_complete_signature",
        **{
            **_fields(signature),
            "events": semantic_events,
            "original_expression_spelling_omitted": not bool(rejected),
        },
        rejected_tool_events=rejected,
        protocol_rejections=protocol_rejections,
        every_original_response_accounted_for=True,
        all_failed_prefixes_retained=True,
        rejected_attempts_keep_literal_arguments_without_inferred_numeric_meaning=True,
        side_calculation_rule="canonical_source_bound_program_and_observed_Final_non_dependency_only",
        original_finite_signature_id=signature["id"],
        mapping_version=outcome["mapping_version"],
    )
    outcome.update(
        full_mapping_status="PENDING_REVIEW" if pending else "MAPPED",
        full_class=None if pending else new_signature["id"],
        full_signature=new_signature,
        full_mapping_pending_reasons=sorted(pending),
        original_history_rewritten=False,
        failure_responses_are_positive_training_targets=False,
    )
    return p.record("new_semantic_assessment", **outcome)
