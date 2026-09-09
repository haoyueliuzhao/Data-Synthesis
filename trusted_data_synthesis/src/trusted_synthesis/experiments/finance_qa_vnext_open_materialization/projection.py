"""Three separate views and attributed finite mapping, never model-target rewriting."""

import ast
from fractions import Fraction

from .canonical import normalize_expression
from .ledger import CONSTANTS, CONTEXT, DECLARATIONS, FORMAT_RECOVERIES, GOALS, SOURCES
from .plan import encode, record, require, sha


def at(tree, address):
    value = tree
    for part in address.split("."):
        value = value[int(part)] if isinstance(value, list) else getattr(value, part)
    return value


def pointer(value, path):
    for part in path:
        value = value[part]
    return value


def quote(turn):
    return {
        "response_index": turn["binding"]["response_index"],
        "quote": turn["raw"].decode(),
        "raw_response_sha256": turn["binding"]["raw_response_sha256"],
        "quote_utf8_span": [0, len(turn["raw"])],
    }


def node_exact(node, expression, call):
    if isinstance(node, ast.Name):
        result = call["output"]["result"]["resolved_variables"][node.id]
        require(result["result_id"] is None, "projection.current_ledger_no_hidden_result_reference")
        return Fraction(result["exact_value"]), "consumed_named_variable"
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Fraction(ast.get_source_segment(expression, node)), "consumed_literal"
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        value = Fraction(ast.get_source_segment(expression, node.operand))
        return (-value if isinstance(node.op, ast.USub) else value), "consumed_signed_literal"
    raise ValueError("projection.not_an_evidenced_scalar_occurrence")


def attribute_source(session, turn, address, specification, declaration_path):
    sid, role, unit = specification
    public = session["public"]
    facts = {fact["id"]: fact for fact in public["numeric_catalog"]}
    require(sid in facts, "projection.source_belongs_to_same_document")
    call = turn["event"]["tool_call"]
    expression = call["arguments"]["expression"]
    tree = ast.parse(expression, mode="eval")
    actual, execution_kind = node_exact(at(tree, address), expression, call)
    source = facts[sid]
    require(actual == Fraction(source["value"]), "projection.source_vs_actual_value_conflict")
    if declaration_path is not None:
        require(
            pointer(call["arguments"], declaration_path) == sid,
            "projection.actual_model_source_declaration",
        )
        attribution = "model_declaration"
    else:
        # This branch is allowed only by the explicit, previously authored
        # case/address ledger, supported by role/period/unit prose and parent
        # finite semantic review. It is never a search over matching values.
        require(session["row"]["label"] in DECLARATIONS, "projection.no_automatic_literal_binding")
        require(
            isinstance(turn["parsed"].get("message"), str) and turn["parsed"]["message"],
            "projection.public_role_evidence_required",
        )
        attribution = "reviewer_interpretation"
    segment = public["segments"][source["segment"]]
    contextual = {name: public["segments"][name] for name in CONTEXT[session["row"]["task_key"]]}
    item = record(
        "source_occurrence_resolution",
        response_index=turn["binding"]["response_index"],
        call_id=call["id"],
        node_address=address,
        original_scalar_syntax=ast.get_source_segment(expression, at(tree, address)),
        executed_exact=str(actual),
        execution_kind=execution_kind,
        source_id=sid,
        source_document_id=public["id"],
        source_fact=source,
        source_segment=segment,
        original_context=contextual,
        interpreted_role=role,
        task_period_scope=GOALS[session["row"]["task_key"]]["period"],
        individual_source_period_described_in=(
            "interpreted_role and original source row/column/context"
        ),
        interpreted_source_unit=unit,
        meaning_annotation_author=(
            "offline executing-agent interpretation supported by original reviewed public evidence"
        ),
        source_association_attribution=attribution,
        model_source_declaration_pointer=declaration_path,
        model_evidence=quote(turn),
        named_variable_value_was_consumed=execution_kind == "consumed_named_variable",
        model_source_annotation_present=declaration_path is not None,
        source_annotation_validated_by_tool=False,
        no_match_by_numeric_value_search=True,
        parent_semantic_review_id=session["row"]["id"],
        finite_semantic_review_not_automatic_certification=True,
    )
    return item, {
        "kind": "source",
        "source_id": sid,
        "source_exact": source["value"],
        "executed_exact": str(actual),
        "attribution": attribution,
        "evidence_verified": True,
        "evidence_record_id": item["id"],
    }


def validate_format_recovery(session):
    label = session["row"]["label"]
    errors = [turn for turn in session["turns"] if turn["event"]["protocol_error"]]
    if not errors:
        return [], True
    spec = FORMAT_RECOVERIES.get(label)
    if spec is None or len(errors) != 1:
        return [
            {"kind": "repair_semantics_unresolved", "model_evidence": [quote(t) for t in errors]}
        ], False
    before, after = session["turns"][spec["before"]], session["turns"][spec["after"]]
    require(
        before["event"]["protocol_error"] and before["event"]["tool_call"] is None,
        "projection.format_before_unexecuted",
    )
    require(
        after["event"]["tool_call"] is not None and not after["event"]["protocol_error"],
        "projection.actual_recovery_call",
    )
    require(
        spec["before_anchor"] in before["raw"].decode()
        and spec["after_anchor"] in after["raw"].decode(),
        "projection.recovery_original_anchors",
    )
    if sha(before["raw"]) != spec["before_sha256"] or sha(after["raw"]) != spec["after_sha256"]:
        return [
            {"kind": "repair_semantics_unresolved", "model_evidence": [quote(before), quote(after)]}
        ], False
    return [
        record(
            "public_format_recovery",
            change_kind="format_recovery",
            model_evidence=[quote(before), quote(after)],
            interpretation=spec["interpretation"],
            interpretation_author="offline finite review, not an added model message",
            before_execution=None,
            after_execution=after["event"]["tool_call"]["id"],
            substantive_signature_contribution=None,
        )
    ], True


def project_session(session):
    row, public = session["row"], session["public"]
    require(row["formula_driven_trace_verified"], "projection.original_validity_required")
    raw_view = [
        {"binding_id": t["binding"]["id"], "model_evidence": quote(t), "event": t["event"]}
        for t in session["turns"]
    ]
    actual_calls = [t for t in session["turns"] if t["event"]["tool_call"] is not None]
    execution_view = {
        "calls": [
            {"response_index": t["binding"]["response_index"], **t["event"]["tool_call"]}
            for t in actual_calls
        ],
        "Final_original": session["result"]["final"],
        "Final_selected_calculation_by_parent_review": row["answer_calculation_id"],
        "no_unexecuted_proposal_is_a_tool_result": True,
    }
    base = {
        "population": row["arm"],
        "task_key": row["task_key"],
        "task_version": public["task_id"],
        "source_document_id": public["id"],
        "session_label": row["label"],
        "source_closeout_id": row["id"],
        "raw_public_sequence": raw_view,
        "actual_execution_and_support": execution_view,
    }
    if row["label"] not in DECLARATIONS or row["task_key"] not in GOALS:
        return record(
            "open_behavior_projection",
            **base,
            status="UNDETERMINED",
            reason="no_frozen_occurrence_ledger",
            behavior_key=None,
        )
    selected = next(
        (t for t in actual_calls if t["event"]["tool_call"]["id"] == row["answer_calculation_id"]),
        None,
    )
    require(selected is not None, "projection.real_answer_calculation")
    require(
        all(
            row["semantic_review"][field]["status"] == "PASS"
            for field in ("formula_applicability", "variable_correspondence", "unit_handling")
        ),
        "projection.existing_semantic_review",
    )
    revisions, repairs_known = validate_format_recovery(session)
    # This empirical ledger currently covers one executed answer calculation
    # per valid session. The generic normalizer supports real result unfolding,
    # but unannotated multi-call semantic trajectories are not assumed equivalent.
    if len(actual_calls) != 1:
        return record(
            "open_behavior_projection",
            **base,
            status="UNDETERMINED",
            reason="multi_call_semantics_without_frozen_ledger",
            behavior_key=None,
            revisions=revisions,
        )
    if any(
        not t["event"]["final"]
        and not t["event"]["protocol_error"]
        and t["event"]["tool_call"] is None
        for t in session["turns"]
    ):
        return record(
            "open_behavior_projection",
            **base,
            status="UNDETERMINED",
            reason="unreviewed_public_semantic_history",
            behavior_key=None,
            revisions=revisions,
        )
    key = row["task_key"]
    call = selected["event"]["tool_call"]
    expression = call["arguments"]["expression"]
    source_ledger, bindings = [], {}
    for address, spec in SOURCES[key].items():
        item, binding = attribute_source(
            session, selected, address, spec, DECLARATIONS[row["label"]].get(address)
        )
        source_ledger.append(item)
        bindings[address] = binding
    for address, (value, reason) in CONSTANTS[key].items():
        bindings[address] = {
            "kind": "constant",
            "value": value,
            "reason": reason,
            "evidence_verified": True,
            "model_evidence": quote(selected),
        }
    normalized = normalize_expression(expression, bindings)
    mapped = normalized["status"] == "MAPPED" and repairs_known
    signature = (
        {
            "population": row["arm"],
            "task_version": public["task_id"],
            "source_document_id": public["id"],
            "goal_scope": GOALS[key],
            "active_source_support": normalized["active_source_ids"],
            "answer_connected_source_rational_form": normalized["normal_form"],
            "substantive_public_revision_path": [],
        }
        if mapped
        else None
    )
    return record(
        "open_behavior_projection",
        **base,
        status="MAPPED" if mapped else "UNDETERMINED",
        reason=None if mapped else normalized["reason"] or "repair_semantics_unresolved",
        model_proposed_relation={
            "original_public_evidence": [quote(selected)],
            "original_public_message": selected["parsed"].get("message"),
            "original_expression": expression,
            "reviewer_relation_interpretation": GOALS[key],
            "interpretation_is_not_added_model_text": True,
        },
        source_mapping_ledger=source_ledger,
        normalization=normalized,
        revisions=revisions,
        behavior_signature=signature,
        behavior_key=sha(encode(signature)) if signature is not None else None,
        source_attribution_kept_outside_nuisance_quotient=True,
        raw_DAG_not_replaced_by_normal_form=True,
        no_financial_identity_expansion=True,
    )
