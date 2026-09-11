"""New-condition full projection with one finite X2 cross-quantity relation.

The source-symbolic quotient and substantive revision path are inherited from
the frozen soft-detail implementation. Original calls, declarations, source
roles/periods/units and exact public quotations stay in the evidence ledger;
variable names and formatting are not new class distinctions. A method stratum
is a separate downstream feature of Final's actual answer normal form.

The only added financial relation connects the unchanged PPG 2006 warranty
reserve target to an actually rebuilt ending reserve. Its explanatory identity
is offline mathematics, never an extra executed movement or residual result.
"""

import ast
import re

from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.canonical import (
    normalize_expression,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.projection import (
    _normalize_call,
    _number,
    _pointer,
    _public_evidence,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.quantity import (
    interpret_unit,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.source import (
    _event_target,
    content_identity,
)

from .plan import encode, record, require, sha

X2_ENDING_REBUILD_RELATION = "X2_2006_product_warranty_ending_rebuild.v1"
_X2_DOCUMENT_ID = "public_document:7f3f17a11b917d081d5dbbdcedfe6c557a023624217e8bfc297c581f22609d40"
_X2_GOAL = {
    "period": "2006 minus 2005",
    "quantity": "net_change_product_warranty_reserve",
    "unit": "USD_million",
}
_X2_ROLES = {
    "e": ("source:q11n3", "reserve for product warranties", "December 31, 2006"),
    "b": ("source:q11n4", "reserve for product warranties", "December 31, 2005"),
    "c": ("source:q12n3", "pretax warranty charges against income", "fiscal 2006"),
    "a": (
        "source:q14n0",
        "warranty obligations assumed in business acquisitions",
        "fiscal 2006",
    ),
    "o": ("source:q13n0", "cash outlays for product warranties", "fiscal 2006"),
}


def x2_cross_quantity_context(public, goal_scope):
    """Build the precall offline relation registry from the frozen public X2.

    This does not read a private answer, execute a tool, or rewrite a source
    occurrence. X1 has its own net-revenue comparison and is outside this
    reserve-balance extension. The context must be frozen before collection.
    """
    content_identity(public, "cross_quantity.public_content_identity")
    require(
        public["id"] == _X2_DOCUMENT_ID
        and public["task_id"] == "PPG/2006/page_42.pdf-4"
        and goal_scope == _X2_GOAL,
        "cross_quantity.only_frozen_X2_original_target",
    )
    facts = {item["id"]: item for item in public["numeric_catalog"]}
    roles = {
        name: {
            "source_id": sid,
            "role": role,
            "period": period,
            "unit": "USD_million",
            "source_exact": facts[sid]["value"],
            "source_fact": facts[sid],
            "public_segment": public["segments"][facts[sid]["segment"]],
        }
        for name, (sid, role, period) in _X2_ROLES.items()
    }

    def normal(expression):
        bindings = {}

        def visit(node, address):
            if isinstance(node, ast.Name):
                role = roles[node.id]
                bindings[address] = {
                    "kind": "source",
                    "source_id": role["source_id"],
                    "source_exact": role["source_exact"],
                    "executed_exact": role["source_exact"],
                    "attribution": "precall_public_relation_not_model_execution",
                    "evidence_verified": True,
                }
            elif isinstance(node, ast.BinOp):
                visit(node.left, address + ".left")
                visit(node.right, address + ".right")
            else:
                raise ValueError("cross_quantity.registered_linear_relation_only")

        visit(ast.parse(expression, mode="eval").body, "body")
        result = normalize_expression(expression, bindings)
        require(result["status"] == "MAPPED", "cross_quantity.registered_normal_form")
        return result

    return record(
        "basis_cross_quantity_context",
        relation_id=X2_ENDING_REBUILD_RELATION,
        task_key="X2",
        task_version=public["task_id"],
        source_document_id=public["id"],
        goal_scope=goal_scope,
        roles=roles,
        checked_quantity={
            "quantity": "ending_product_warranty_reserve",
            "period": "December 31, 2006",
            "unit": "USD_million",
        },
        comparator_source_id=roles["e"]["source_id"],
        normalizations={
            "endpoint": normal("e-b"),
            "movement": normal("c+a-o"),
            "ending_rebuild": normal("b+c+a-o"),
        },
        public_financial_relation={
            "relation": "ending = beginning + charges + acquired obligations - cash outlays",
            "source_segments": {
                sid: public["segments"][sid] for sid in ("q9", "q10", "q11", "q12", "q13", "q14")
            },
            "interpretation_author": "offline public financial relation review",
            "publicly_disclosed_component_roles_not_equal_value_search": True,
        },
        offline_explanatory_identity={
            "definitions": {"D": "e-b", "R": "c+a-o", "B": "b+c+a-o"},
            "identity": "D-R=e-B",
            "is_model_execution": False,
            "creates_no_executed_R_or_residual": True,
            "does_not_substitute_one_source_occurrence_for_another": True,
        },
        statistical_independence_claimed=False,
        scope="Only the unchanged X2 2006 ending warranty reserve reconstruction.",
    )


def _matches(normal, expected):
    return (
        normal.get("status") == "MAPPED"
        and normal["normal_form"] == expected["normal_form"]
        and normal["active_source_ids"] == expected["active_source_ids"]
    )


def _ending_predictions(message):
    """Recognize only explicit local ending-reserve predictions, not Final values."""
    if not isinstance(message, str):
        return []
    number = r"([-+]?\d+(?:\.\d+)?)"
    patterns = (
        r"(?:ending|closing)\s+(?:warranty\s+)?(?:reserve|balance)"
        r"\s*(?:of|is|was|=|:)?\s*\$?\s*" + number,
        r"=\s*\$?\s*" + number + r"\s*(?:M|million)?\s+"
        r"(?:ending|closing)\s+(?:warranty\s+)?(?:reserve|balance)",
    )
    return [_number(match) for pattern in patterns for match in re.findall(pattern, message, re.I)]


def _cross_quantity_check(
    session,
    check,
    context,
    goal_scope,
    turns,
    calls,
    normalizations,
    ledger,
    answer_id,
    check_dependencies,
    final_index,
    revisions,
):
    require(isinstance(context, dict), "cross_quantity.frozen_context_required")
    require(
        context == x2_cross_quantity_context(session["public"], goal_scope),
        "cross_quantity.exact_frozen_context",
    )
    require(session["row"]["task_key"] == "X2", "cross_quantity.X2_only")
    relation = check["quantity_relation"]
    require(isinstance(relation, dict), "cross_quantity.review_required")
    require(
        relation.get("relation_id") == X2_ENDING_REBUILD_RELATION,
        "cross_quantity.registered_relation_only",
    )
    require(
        relation.get("checked_quantity") == context["checked_quantity"],
        "cross_quantity.same_object_period_unit",
    )
    comparator = relation.get("comparator_source_id")
    require(
        comparator == context["comparator_source_id"],
        "cross_quantity.actual_disclosed_comparator",
    )
    cid = check["call_id"]
    normal = normalizations[cid]
    require(
        _matches(normal, context["normalizations"]["ending_rebuild"]),
        "cross_quantity.actual_rebuilt_ending_relation",
    )
    answer = normalizations[answer_id]
    require(
        any(
            _matches(answer, context["normalizations"][method])
            for method in ("endpoint", "movement")
        ),
        "cross_quantity.relation_to_original_target",
    )
    # The check may consume prior component results but never the answer result
    # (checked by the main mapper) or a mechanically cancelled endpoint.
    roles_by_source = {item["source_id"]: item for item in context["roles"].values()}
    expected_check_sources = set(normal["active_source_ids"])
    relevant = [
        item
        for item in ledger
        if item["call_id"] in check_dependencies and item["kind"] == "source"
    ]
    require(
        {item["source_id"] for item in relevant} == expected_check_sources,
        "cross_quantity.no_cancelled_same_source_recalculation",
    )
    for item in relevant:
        role = roles_by_source[item["source_id"]]
        require(
            item["interpreted_role"] == role["role"]
            and item["interpreted_period"] == role["period"]
            and item["interpreted_source_unit"] == role["unit"]
            and _number(item["normalization_scale"]) == 1,
            "cross_quantity.source_role_period_unit",
        )
        arguments = calls[item["call_id"]]["call"]["arguments"]
        variable = arguments.get("variables", {}).get(item["original_scalar_syntax"])
        declared_units = [arguments["unit"]] if "unit" in arguments else []
        if isinstance(variable, dict) and "unit" in variable:
            declared_units.append(variable["unit"])
        for unit in declared_units:
            interpreted = interpret_unit(
                unit,
                {
                    "public_target_currencies": ["USD"],
                    "relevant_source_currencies": ["USD"],
                },
            )
            require(
                interpreted.get("status") == "MAPPED"
                and interpreted.get("dimension") == "money"
                and interpreted.get("currency") == "USD"
                and interpreted.get("scale") == "1000000",
                "cross_quantity.actual_declared_unit",
            )
    actual = _number(calls[cid]["call"]["output"]["result"]["exact_value"])
    require(
        actual == _number(context["roles"]["e"]["source_exact"]),
        "cross_quantity.executed_result_matches_disclosed_comparator",
    )
    evidence = _public_evidence(check.get("evidence"), turns, final_index, calls[cid]["index"])
    require(
        any(item["response_index"] == final_index for item in evidence),
        "cross_quantity.actual_Final_evidence_required",
    )
    link = relation.get("final_link")
    require(isinstance(link, dict), "cross_quantity.Final_link_review_required")
    final_value = _pointer(session["result"]["final"], link.get("pointer"))
    quote = link.get("quote")
    require(
        isinstance(final_value, str) and isinstance(quote, str) and quote and quote in final_value,
        "cross_quantity.quote_inside_actual_Final",
    )
    # Finite evidence-recognition domain only. This is not the primary Final
    # quantity extractor; unfamiliar wording remains UNDETERMINED.
    require(
        re.search(
            r"corroborat|cross[- ]?check|reconcil|confirm|agree|consistent|verif|match|check",
            quote,
            re.I,
        )
        and re.search(r"ending|closing|year[- ]?end|end.of", quote, re.I)
        and re.search(r"reserve|warrant", quote, re.I)
        and re.search(r"(?<![\d.])" + re.escape(str(actual)) + r"(?![\d.])", quote),
        "cross_quantity.explicit_Final_corroboration",
    )
    require(
        not re.search(
            r"\b(?:not|never|without|unverified|unconfirmed|inconsistent|"
            r"mismatch\w*|disagree\w*|failed?|incorrect|wrong)\b",
            quote,
            re.I,
        ),
        "cross_quantity.negated_or_conflicting_Final_link",
    )
    parsed = _event_target(
        turns[calls[cid]["index"]]["event"],
        turns[calls[cid]["index"]]["raw"],
        session["result"]["final"],
    )
    wrong_predictions = [
        value for value in _ending_predictions(parsed.get("message")) if value != actual
    ]
    if wrong_predictions:
        require(
            any(
                item["change_kind"] == "substantive"
                and item["before_index"] == calls[cid]["index"]
                and item["after_index"] == final_index
                for item in revisions
            ),
            "cross_quantity.actual_prediction_revision_must_be_retained",
        )
    shared = sorted(set(answer["active_source_ids"]) & set(normal["active_source_ids"]))
    key = {
        "goal_scope": goal_scope,
        "relation_id": context["relation_id"],
        "checked_quantity": context["checked_quantity"],
        "comparator_source_id": comparator,
        "source_normal_form": normal["normal_form"],
        "active_support": normal["active_source_ids"],
    }
    observed = {
        "kind": "executed_cross_quantity_check_review",
        "call_id": cid,
        "actual_expression": calls[cid]["call"]["arguments"]["expression"],
        "actual_result_exact": str(actual),
        "actual_result_dependencies": calls[cid]["call"]["output"]["result"]["used_result_ids"],
        "check_ancestor_call_ids": sorted(check_dependencies),
        "disclosed_comparator": context["roles"]["e"],
        "shared_active_source_ids_with_answer": shared,
        "statistical_independence_claimed": False,
        "check_has_no_answer_result_dependency": True,
        "evidence": evidence,
        "actual_Final_link": link,
        "interpretation": check["interpretation"],
        "offline_relation_context_id": context["id"],
        "offline_explanatory_identity": context["offline_explanatory_identity"],
        "creates_no_executed_R_or_residual": True,
        "signature_component": key,
    }
    return key, observed


def project_session(session, mapping, goal_scope, *, condition_id, cross_quantity_context=None):
    """Map reviewed occurrences/events; missing support changes no validity finding.

    Evidence consists of exact nonempty quotes and response indices.  Source
    quotes must precede or accompany consumption.  Each event annotation needs
    its own event's quote.  Nonunit source scales require scale_reason (or reason).
    Unconnected successful calculations must be explicit cross_checks, annotated
    auxiliary_calculation, or superseded_calculation with a substantive revision.
    A cross_check without quantity_relation retains the same-target contract.
    A quantity_relation must satisfy the frozen X2 ending-rebuild extension.
    condition_id denotes this new synthesis condition, never an old N/E class.
    Historical boundary controls must explicitly mark their row as an offline
    reference; they are never new candidate sessions.
    """
    row, public = session["row"], session["public"]
    require(row["formula_driven_trace_verified"], "projection.original_validity_required")
    turns = {turn["binding"]["response_index"]: turn for turn in session["turns"]}
    raw_view = [
        {
            "response_index": index,
            "raw_response": turn["raw"].decode(),
            "binding": turn["binding"],
            "event": turn["event"],
        }
        for index, turn in turns.items()
    ]
    calls = {
        turn["event"]["tool_call"]["id"]: {"index": index, "call": turn["event"]["tool_call"]}
        for index, turn in turns.items()
        if turn["event"]["tool_call"] is not None
    }
    execution = {
        "calls": list(calls.values()),
        "dependency_edges": [],
        "Final_original": session["result"]["final"],
        "Final_calculation_link": row["answer_calculation_id"],
        "Final_link_attribution": (
            "existing finite source-validity review, not a numeric-only inferred model claim"
        ),
        "failed_calls_and_unexecuted_errors_retained_in_raw_view": True,
    }
    ledger, normalizations, adaptations, reads, annotations, revisions = [], {}, [], [], [], []
    cross_quantity_observations = []
    base = {
        "population": row["arm"],
        "task_key": row["task_key"],
        "task_version": public["task_id"],
        "source_document_id": public["id"],
        "session_label": row["label"],
        "source_closeout_id": row["id"],
        "raw_public_sequence": raw_view,
        "actual_execution_and_support": execution,
    }

    def result(status, reason=None, signature=None):
        return record(
            "basis_conditioned_support_projection",
            **base,
            status=status,
            reason=reason,
            behavior_signature=signature,
            behavior_key=sha(encode(signature)) if signature is not None else None,
            model_public_relations={
                "event_annotations": annotations,
                "revisions": revisions,
                "reviewer_interpretations_are_not_added_model_claims": True,
            },
            source_mapping_ledger=ledger,
            normalizations=normalizations,
            offline_normalization_adaptations=adaptations,
            source_read_events=reads,
            cross_quantity_checks=cross_quantity_observations,
            requested_condition_id=condition_id,
            actual_main_support=normalizations.get(row["answer_calculation_id"]),
            method_stratum_is_not_a_new_equivalence_relation=True,
            original_validity_preserved=True,
            no_financial_identity_expansion=True,
            no_source_selected_by_equal_value_search=True,
        )

    try:
        require(
            isinstance(mapping, dict) and isinstance(goal_scope, dict) and goal_scope,
            "projection.review_and_goal_required",
        )
        require(
            row["arm"] in {"endpoint", "movement"}
            or row.get("offline_historical_boundary_reference") is True,
            "projection.new_condition_or_explicit_offline_reference",
        )
        require(
            isinstance(condition_id, str) and condition_id and condition_id not in {"N", "E"},
            "projection.explicit_new_condition_identity",
        )
        require(len(turns) == len(session["turns"]), "projection.unique_event_indices")
        require(
            len(calls) == sum(turn["event"]["tool_call"] is not None for turn in turns.values()),
            "projection.unique_actual_call_ids",
        )
        require(list(turns) == sorted(turns), "projection.chronological_history")
        for index, turn in turns.items():
            require(index == turn["event"]["response_index"], "projection.event_index_identity")
            require(
                sha(turn["raw"])
                == turn["binding"]["raw_response_sha256"]
                == turn["event"]["raw_sha256"],
                "projection.raw_evidence_identity",
            )
            _event_target(turn["event"], turn["raw"], session["result"]["final"])
        annotations_by_index = {}
        for item in mapping.get("event_annotations", []):
            index = item.get("response_index")
            require(
                index in turns and index not in annotations_by_index,
                "projection.unique_reviewed_event",
            )
            require(
                isinstance(item.get("role"), str)
                and item["role"] not in {"", "unresolved", "unreviewed"},
                "projection.resolved_event_role",
            )
            require(
                isinstance(item.get("interpretation"), str) and item["interpretation"],
                "projection.event_interpretation_required",
            )
            reviewed = {
                **item,
                "evidence": _public_evidence(item.get("evidence"), turns, index, index),
            }
            annotations.append(reviewed)
            annotations_by_index[index] = reviewed
        require(set(annotations_by_index) == set(turns), "projection.every_public_event_reviewed")
        revision_path, repaired_indices, substantive_before = [], set(), set()
        for item in mapping.get("revisions", []):
            before, after = item.get("before_index"), item.get("after_index")
            require(
                type(before) is int
                and type(after) is int
                and before in turns
                and after in turns
                and before < after,
                "projection.ordered_real_revision",
            )
            evidence = _public_evidence(item.get("evidence"), turns, after, before)
            require(
                any(quote["response_index"] == after for quote in evidence),
                "projection.revision_after_evidence",
            )
            require(
                isinstance(item.get("interpretation"), str) and item["interpretation"],
                "projection.revision_interpretation_required",
            )
            kind, semantic = item.get("change_kind"), item.get("semantic_key")
            if kind == "format_only":
                event = turns[before]["event"]
                failed = (
                    event["tool_call"] is not None
                    and event["tool_call"]["output"]["status"] != "ok"
                )
                require(
                    (event["protocol_error"] is not None or failed) and semantic is None,
                    "projection.format_recovery_not_successful_method_rewrite",
                )
            elif kind == "substantive":
                require(
                    isinstance(semantic, (dict, list)) and semantic,
                    "projection.substantive_semantic_key_required",
                )
                revision_path.append(
                    (before, after, {"change_kind": kind, "semantic_key": semantic})
                )
                substantive_before.add(before)
            else:
                raise ValueError("projection.unresolved_revision_semantics")
            repaired_indices.add(before)
            revisions.append({**item, "evidence": evidence})
        for index, turn in turns.items():
            event = turn["event"]
            failed = (
                event["tool_call"] is not None and event["tool_call"]["output"]["status"] != "ok"
            )
            if event["protocol_error"] is not None or failed:
                require(index in repaired_indices, "projection.error_recovery_semantics_unreviewed")
        occurrence_maps = mapping.get("occurrences")
        require(isinstance(occurrence_maps, dict), "projection.occurrence_maps_required")
        successful_calculations = {
            cid
            for cid, item in calls.items()
            if item["call"]["name"] == "calculate" and item["call"]["output"]["status"] == "ok"
        }
        require(
            set(occurrence_maps) == successful_calculations,
            "projection.every_successful_calculation_ledger",
        )
        previous, prior_calls = {}, {}
        for cid, item in calls.items():
            call, index = item["call"], item["index"]
            if call["output"]["status"] != "ok":
                prior_calls[cid] = item
                continue
            if call["name"] == "calculate":
                normalized, call_ledger, adaptation = _normalize_call(
                    call, index, occurrence_maps[cid], public, turns, previous, prior_calls
                )
                ledger.extend(call_ledger)
                adaptations.append(adaptation)
                normalizations[cid] = normalized
                previous[cid] = normalized
                for ref in call["output"]["result"]["used_result_ids"]:
                    execution["dependency_edges"].append(
                        {
                            "producer_call_id": ref,
                            "consumer_call_id": cid,
                            "kind": "actual_result_id",
                        }
                    )
                require(
                    normalized["status"] == "MAPPED",
                    "projection.unsupported_calculation:" + str(normalized["reason"]),
                )
            elif call["name"] == "read_source":
                output = call["output"]["result"]
                source_id = output.get("numeric_source_id")
                read = {
                    "call_id": cid,
                    "response_index": index,
                    "original_call": call,
                    "reading_alone_is_not_answer_support": True,
                }
                if source_id is not None:
                    facts = {fact["id"]: fact for fact in public["numeric_catalog"]}
                    require(
                        call["arguments"]["locators"] == [source_id] and source_id in facts,
                        "projection.scalar_read_same_public_source",
                    )
                    fact = facts[source_id]
                    require(
                        _number(output["exact_value"]) == _number(fact["value"]),
                        "projection.scalar_read_exact_source",
                    )
                    require(
                        output["records"]
                        == [
                            {"numeric_record": fact, "segment": public["segments"][fact["segment"]]}
                        ],
                        "projection.actual_read_payload",
                    )
                    normalized = normalize_expression(
                        "read_source_value",
                        {
                            "body": {
                                "kind": "source",
                                "source_id": source_id,
                                "source_exact": fact["value"],
                                "executed_exact": output["exact_value"],
                                "attribution": "model_declaration",
                                "evidence_verified": True,
                            }
                        },
                    )
                    previous[cid] = normalized
                    read.update(numeric_source_id=source_id, normalized_numeric_read=normalized)
                reads.append(read)
            elif call["name"] != "notebook":
                raise ValueError("projection.unsupported_successful_tool")
            prior_calls[cid] = item
        answer_id = row["answer_calculation_id"]
        require(
            answer_id in successful_calculations and answer_id in normalizations,
            "projection.actual_mapped_answer_calculation",
        )
        finals = [index for index, turn in turns.items() if turn["event"]["final"]]
        require(
            len(finals) == 1 and finals[0] == max(turns) and calls[answer_id]["index"] < finals[0],
            "projection.original_terminal_Final",
        )
        answer = normalizations[answer_id]

        def ancestors_of(start):
            visited = set()

            def visit(cid):
                if cid in visited:
                    return
                visited.add(cid)
                call = calls[cid]["call"]
                if call["name"] == "calculate":
                    for ref in call["output"]["result"]["used_result_ids"]:
                        visit(ref)

            visit(start)
            return visited

        ancestors = ancestors_of(answer_id)
        checks, quantity_checks, check_ids, check_ancestors = {}, {}, set(), set()
        for check in mapping.get("cross_checks", []):
            cid = check.get("call_id")
            require(
                cid in successful_calculations and cid != answer_id and cid not in check_ids,
                "projection.actual_distinct_cross_check",
            )
            require(cid not in ancestors, "projection.cross_check_not_answer_intermediate")
            check_dependencies = ancestors_of(cid)
            require(
                answer_id not in check_dependencies,
                "projection.cross_check_not_derived_from_answer",
            )
            evidence = _public_evidence(check.get("evidence"), turns, finals[0])
            require(
                any(item["response_index"] >= calls[cid]["index"] for item in evidence),
                "projection.check_episode_link_evidence",
            )
            require(
                isinstance(check.get("interpretation"), str) and check["interpretation"],
                "projection.check_interpretation_required",
            )
            normalized = normalizations[cid]
            if "quantity_relation" in check:
                key, observed = _cross_quantity_check(
                    session,
                    check,
                    cross_quantity_context,
                    goal_scope,
                    turns,
                    calls,
                    normalizations,
                    ledger,
                    answer_id,
                    check_dependencies,
                    finals[0],
                    revisions,
                )
                quantity_checks[sha(encode(key))] = key
                cross_quantity_observations.append(observed)
                annotations.append(observed)
                check_ids.add(cid)
                check_ancestors.update(check_dependencies)
                continue
            require(
                _number(calls[cid]["call"]["output"]["result"]["exact_value"])
                == _number(calls[answer_id]["call"]["output"]["result"]["exact_value"]),
                "projection.check_same_answer_quantity_only",
            )
            require(
                normalized["active_source_ids"] != answer["active_source_ids"],
                "projection.check_distinct_active_source_support",
            )
            key = {
                "goal_scope": goal_scope,
                "source_normal_form": normalized["normal_form"],
                "active_support": normalized["active_source_ids"],
            }
            checks[sha(encode(key))] = key
            check_ids.add(cid)
            check_ancestors.update(check_dependencies)
            annotations.append(
                {
                    "kind": "executed_same_target_cross_check_review",
                    "statistical_independence_claimed": False,
                    "shared_active_source_ids_with_answer": sorted(
                        set(normalized["active_source_ids"]) & set(answer["active_source_ids"])
                    ),
                    "call_id": cid,
                    "evidence": evidence,
                    "interpretation": check["interpretation"],
                    "signature_component": key,
                }
            )
        for cid in successful_calculations - ancestors - check_ancestors:
            index = calls[cid]["index"]
            role = annotations_by_index[index]["role"]
            # A reviewed auxiliary label must not erase the known executed
            # ending-reserve check when both its call and Final state the link.
            if row["task_key"] == "X2" and goal_scope == _X2_GOAL:
                context = x2_cross_quantity_context(public, goal_scope)
                parsed = _event_target(
                    turns[index]["event"], turns[index]["raw"], session["result"]["final"]
                )
                final = session["result"]["final"]
                final_text = final.get("explanation", "") if isinstance(final, dict) else ""
                check_words = r"cross[- ]?check|corroborat|reconcil|verif"
                public_link = (
                    isinstance(parsed.get("message"), str)
                    and isinstance(final_text, str)
                    and re.search(check_words, parsed["message"], re.I)
                    and re.search(check_words, final_text, re.I)
                    and re.search(r"ending|closing", final_text, re.I)
                )
                require(
                    not (
                        _matches(normalizations[cid], context["normalizations"]["ending_rebuild"])
                        and public_link
                    ),
                    "cross_quantity.actual_check_must_be_retained",
                )
            require(
                role == "auxiliary_calculation"
                or (role == "superseded_calculation" and index in substantive_before),
                "projection.unclassified_nonanswer_calculation",
            )
        signature = {
            "fixed_condition": condition_id,
            "task_version": public["task_id"],
            "source_document_id": public["id"],
            "goal_scope": goal_scope,
            "answer_source_normal_form": answer["normal_form"],
            "active_support": answer["active_source_ids"],
            "substantive_revision_path": [
                item[2] for item in sorted(revision_path, key=lambda item: (item[0], item[1]))
            ],
            "evidenced_independent_cross_checks": [checks[key] for key in sorted(checks)],
            "evidenced_cross_quantity_checks": [
                quantity_checks[key] for key in sorted(quantity_checks)
            ],
        }
        return result("MAPPED", signature=signature)
    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
        SyntaxError,
        RecursionError,
        ZeroDivisionError,
    ) as error:
        return result("UNDETERMINED", reason=str(error))
