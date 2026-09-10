"""Evidence-attributed offline mapping of arbitrary finite open public histories.

No source is selected by searching for an equal number.  Optional reviewed source
scales are applied only in a separate normalization AST; the original expression
and actual consumed values remain untouched in the execution view.
"""

import ast
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.canonical import (
    normalize_expression,
)

from .plan import condition, encode, record, require, sha


def _pointer(value, path):
    require(isinstance(path, list) and path, "projection.declaration_pointer_required")
    for part in path:
        value = value[part]
    return value


def _number(value):
    require(
        isinstance(value, (str, int, float)) and not isinstance(value, bool),
        "projection.exact_scalar",
    )
    text = str(value)
    require(len(text) <= 4096, "projection.scalar_size")
    # Real worker values are bounded rational strings, never arbitrary programs.
    return Fraction(text)


def _public_evidence(items, turns, latest, required_index=None):
    require(isinstance(items, list) and items, "projection.public_evidence_required")
    result = []
    for item in items:
        require(isinstance(item, dict), "projection.evidence_object")
        index, text = item.get("response_index"), item.get("quote")
        require(
            type(index) is int and index in turns and index <= latest,
            "projection.evidence_not_future",
        )
        require(
            isinstance(text, str) and text and text in turns[index]["raw"].decode(),
            "projection.exact_public_quote",
        )
        result.append(
            {**item, "raw_response_sha256": turns[index]["binding"]["raw_response_sha256"]}
        )
    if required_index is not None:
        require(
            any(item["response_index"] == required_index for item in result),
            "projection.evidence_for_this_event",
        )
    return result


def _scalar(node, expression, call):
    if isinstance(node, ast.Name):
        resolved = call["output"]["result"]["resolved_variables"]
        require(node.id in resolved, "projection.variable_actually_consumed")
        return (
            _number(resolved[node.id]["exact_value"]),
            resolved[node.id].get("result_id"),
            "named_variable",
        )
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return _number(ast.get_source_segment(expression, node)), None, "numeric_literal"
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) in (int, float)
    ):
        value = _number(ast.get_source_segment(expression, node.operand))
        return (-value if isinstance(node.op, ast.USub) else value), None, "signed_numeric_literal"
    raise ValueError("projection.not_a_consumed_scalar_occurrence")


def _normalize_call(call, index, specifications, public, turns, previous, prior_calls):
    require(isinstance(specifications, dict), "projection.calculation_occurrence_ledger_required")
    expression = call["arguments"]["expression"]
    result = call["output"]["result"]
    require(result["expression"] == expression, "projection.actual_expression_identity")
    tree = ast.parse(expression, mode="eval")
    facts = {item["id"]: item for item in public["numeric_catalog"]}
    require(len(facts) == len(public["numeric_catalog"]), "projection.unique_public_sources")
    aliases, consumed, ledger, actual_refs = {}, set(), [], set()

    def alias(binding):
        name = f"offline_occurrence_{len(aliases)}"
        aliases[name] = binding
        return ast.Name(id=name, ctx=ast.Load())

    def occurrence(node, address):
        require(address in specifications, "projection.missing_occurrence:" + address)
        specification = specifications[address]
        require(isinstance(specification, dict), "projection.occurrence_object")
        consumed.add(address)
        actual, real_reference, execution_kind = _scalar(node, expression, call)
        evidence = _public_evidence(specification.get("evidence"), turns, index)
        kind = specification.get("kind")
        item = {
            "call_id": call["id"],
            "response_index": index,
            "node_address": address,
            "original_scalar_syntax": ast.get_source_segment(expression, node),
            "actual_consumed_exact": str(actual),
            "actual_result_reference": real_reference,
            "execution_kind": execution_kind,
            "model_evidence": evidence,
            "annotation_author": "offline executing-agent review; not an added model statement",
        }
        if kind == "source":
            require(real_reference is None, "projection.real_reference_cannot_be_relabelled_source")
            sid = specification.get("source_id")
            require(sid in facts, "projection.source_from_same_public_document")
            fact = facts[sid]
            source_exact = _number(fact["value"])
            scale = _number(specification.get("scale", "1"))
            require(scale != 0, "projection.nonzero_reviewed_source_scale")
            require(actual == source_exact * scale, "projection.source_scale_vs_actual_consumption")
            for field in ("role", "period", "unit"):
                require(
                    isinstance(specification.get(field), str) and specification[field],
                    "projection.source_semantic_evidence:" + field,
                )
            attribution = specification.get("attribution")
            require(
                attribution in {"model_declaration", "reviewer_interpretation"},
                "projection.source_attribution",
            )
            declaration = specification.get("declaration_pointer")
            if attribution == "model_declaration":
                require(
                    _pointer(call["arguments"], declaration) == sid,
                    "projection.original_model_source_declaration",
                )
            else:
                require(declaration is None, "projection.reviewer_mapping_not_model_declaration")
            scale_reason = specification.get("scale_reason", specification.get("reason"))
            if scale != 1:
                require(
                    isinstance(scale_reason, str) and scale_reason,
                    "projection.scale_reason_required",
                )
            source_alias = alias(
                {
                    "kind": "source",
                    "source_id": sid,
                    "source_exact": str(source_exact),
                    "executed_exact": str(source_exact),
                    "attribution": attribution,
                    "evidence_verified": True,
                    "normalization_only_original_execution_not_rewritten": True,
                }
            )
            replacement = source_alias
            if scale != 1:
                scale_alias = alias(
                    {
                        "kind": "constant",
                        "value": str(scale),
                        "reason": scale_reason,
                        "evidence_verified": True,
                    }
                )
                replacement = ast.BinOp(left=scale_alias, op=ast.Mult(), right=source_alias)
            item.update(
                kind="source",
                source_id=sid,
                source_document_id=public["id"],
                original_source_fact=fact,
                original_source_segment=public["segments"][fact["segment"]],
                source_exact=str(source_exact),
                normalization_scale=str(scale),
                scale_reason=scale_reason,
                interpreted_role=specification["role"],
                interpreted_period=specification["period"],
                interpreted_source_unit=specification["unit"],
                source_association_attribution=attribution,
                original_declaration_pointer=declaration,
                source_inferred_by_numeric_search=False,
            )
        elif kind == "constant":
            require(
                real_reference is None, "projection.real_reference_cannot_be_relabelled_constant"
            )
            require(
                actual == _number(specification.get("value")), "projection.actual_constant_value"
            )
            reason = specification.get("reason")
            require(isinstance(reason, str) and reason, "projection.constant_reason_required")
            replacement = alias(
                {
                    "kind": "constant",
                    "value": str(actual),
                    "reason": reason,
                    "evidence_verified": True,
                }
            )
            item.update(kind="constant", reason=reason)
        elif kind == "result":
            ref = specification.get("result_id")
            require(
                isinstance(node, ast.Name) and real_reference is not None and ref == real_reference,
                "projection.actual_result_reference_required",
            )
            require(
                ref in prior_calls and ref in previous, "projection.prior_mapped_numeric_result"
            )
            prior = prior_calls[ref]
            require(
                prior["index"] < index and prior["call"]["output"]["status"] == "ok",
                "projection.prior_successful_result",
            )
            require(
                actual == _number(prior["call"]["output"]["result"]["exact_value"]),
                "projection.consumed_reference_exact_value",
            )
            require(previous[ref]["status"] == "MAPPED", "projection.reference_semantics_unmapped")
            actual_refs.add(ref)
            replacement = alias(
                {
                    "kind": "result",
                    "result_id": ref,
                    "executed_exact": str(actual),
                    "evidence_verified": True,
                }
            )
            item.update(
                kind="result", producer_call_id=ref, reference_is_actual_execution_fact=True
            )
        else:
            raise ValueError("projection.unsupported_occurrence_kind")
        ledger.append(item)
        return replacement

    def adapt(node, address):
        scalar = isinstance(node, ast.Name) or (
            isinstance(node, ast.Constant) and type(node.value) in (int, float)
        )
        signed = (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, (ast.UAdd, ast.USub))
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) in (int, float)
        )
        if scalar or (signed and address in specifications):
            return occurrence(node, address)
        if isinstance(node, ast.BinOp):
            return ast.BinOp(
                left=adapt(node.left, address + ".left"),
                op=node.op,
                right=adapt(node.right, address + ".right"),
            )
        if isinstance(node, ast.UnaryOp):
            return ast.UnaryOp(op=node.op, operand=adapt(node.operand, address + ".operand"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            return ast.Call(
                func=node.func,
                args=[
                    adapt(child, address + f".args.{position}")
                    for position, child in enumerate(node.args)
                ],
                keywords=[],
            )
        if isinstance(node, (ast.List, ast.Tuple)):
            return type(node)(
                elts=[
                    adapt(child, address + f".elts.{position}")
                    for position, child in enumerate(node.elts)
                ],
                ctx=ast.Load(),
            )
        raise ValueError("projection.unsupported_expression_node:" + type(node).__name__)

    transformed = ast.fix_missing_locations(ast.Expression(body=adapt(tree.body, "body")))
    require(consumed == set(specifications), "projection.unconsumed_occurrence_ledger")
    require(
        actual_refs == set(result["used_result_ids"]), "projection.every_real_dependency_accounted"
    )
    normalized_expression = ast.unparse(transformed)
    normalization_tree = ast.parse(normalized_expression, mode="eval")
    bindings = {}

    def bind_aliases(node, address):
        if isinstance(node, ast.Name):
            require(node.id in aliases, "projection.normalization_alias")
            bindings[address] = aliases[node.id]
        elif isinstance(node, ast.BinOp):
            bind_aliases(node.left, address + ".left")
            bind_aliases(node.right, address + ".right")
        elif isinstance(node, ast.UnaryOp):
            bind_aliases(node.operand, address + ".operand")
        elif isinstance(node, ast.Call):
            for position, child in enumerate(node.args):
                bind_aliases(child, address + f".args.{position}")
        elif isinstance(node, (ast.List, ast.Tuple)):
            for position, child in enumerate(node.elts):
                bind_aliases(child, address + f".elts.{position}")
        else:
            raise ValueError("projection.unexpected_normalization_node")

    bind_aliases(normalization_tree.body, "body")
    normalized = normalize_expression(normalized_expression, bindings, previous)
    return (
        normalized,
        ledger,
        {
            "call_id": call["id"],
            "original_expression": expression,
            "derived_expression_for_normalization_only": normalized_expression,
            "derived_bindings": bindings,
            "derived_expression_is_not_model_formula_or_execution": True,
        },
    )


def project_session(session, mapping, goal_scope):
    """Map reviewed occurrences/events; missing support changes no validity finding.

    Evidence consists of exact nonempty quotes and response indices.  Source
    quotes must precede or accompany consumption.  Each event annotation needs
    its own event's quote.  Nonunit source scales require scale_reason (or reason).
    Unconnected successful calculations must be explicit cross_checks, annotated
    auxiliary_calculation, or superseded_calculation with a substantive revision.
    A cross_check currently supports a second executed estimate of the same
    answer quantity, not an unannotated zero-residual or Boolean check.
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
            "open_support_projection",
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
            original_validity_preserved=True,
            no_financial_identity_expansion=True,
            no_source_selected_by_equal_value_search=True,
        )

    try:
        require(
            isinstance(mapping, dict) and isinstance(goal_scope, dict) and goal_scope,
            "projection.review_and_goal_required",
        )
        require(row["arm"] == "T", "projection.fixed_T_population")
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
        checks, check_ids, check_ancestors = {}, set(), set()
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
                    "kind": "independent_cross_check_review",
                    "call_id": cid,
                    "evidence": evidence,
                    "interpretation": check["interpretation"],
                    "signature_component": key,
                }
            )
        for cid in successful_calculations - ancestors - check_ancestors:
            index = calls[cid]["index"]
            role = annotations_by_index[index]["role"]
            require(
                role == "auxiliary_calculation"
                or (role == "superseded_calculation" and index in substantive_before),
                "projection.unclassified_nonanswer_calculation",
            )
        signature = {
            "fixed_condition": condition()["id"],
            "task_version": public["task_id"],
            "source_document_id": public["id"],
            "goal_scope": goal_scope,
            "answer_source_normal_form": answer["normal_form"],
            "active_support": answer["active_source_ids"],
            "substantive_revision_path": [
                item[2] for item in sorted(revision_path, key=lambda item: (item[0], item[1]))
            ],
            "evidenced_independent_cross_checks": [checks[key] for key in sorted(checks)],
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
