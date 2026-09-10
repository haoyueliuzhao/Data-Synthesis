"""Source-defined prototypes and the mention/execution/source/Final measurement chain."""

import ast
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.canonical import (
    normalize_expression,
)

from .plan import ARMS, TASKS, condition, encode, record, require, sha
from .projection import _normalize_call


def target_prototypes(panel):
    tasks = {}
    for arm in ARMS:
        tasks[arm] = {}
        for key in TASKS:
            task, public = panel.tasks[key], panel.public[key]
            routes = {}
            for route, field in (("D", "expression"), ("R", "alternative")):
                expression = task["original_private_spec"][field]
                bindings = {}

                def visit(node, address, *, task=task, bindings=bindings):
                    if isinstance(node, ast.Name):
                        sid = task["source_bindings"][node.id]
                        value = task["facts"][sid]["value"]
                        bindings[address] = {
                            "kind": "source",
                            "source_id": sid,
                            "source_exact": value,
                            "executed_exact": value,
                            "attribution": "precall_source_definition_not_model_evidence",
                            "evidence_verified": True,
                        }
                    elif isinstance(node, ast.Constant) and type(node.value) is int:
                        bindings[address] = {
                            "kind": "constant",
                            "value": str(node.value),
                            "reason": "precall dimensional constant",
                            "evidence_verified": True,
                        }
                    elif isinstance(node, ast.BinOp):
                        visit(node.left, address + ".left")
                        visit(node.right, address + ".right")
                    elif isinstance(node, ast.UnaryOp):
                        visit(node.operand, address + ".operand")
                    else:
                        raise ValueError("prototype.registered_finite_expression_domain")

                visit(ast.parse(expression, mode="eval").body, "body")
                normal = normalize_expression(expression, bindings)
                require(normal["status"] == "MAPPED", "prototype.source_defined_relation")
                signature = {
                    "fixed_condition": condition(arm)["id"],
                    "task_version": public["task_id"],
                    "source_document_id": public["id"],
                    "goal_scope": task["goal_scope"],
                    "answer_source_normal_form": normal["normal_form"],
                    "active_support": normal["active_source_ids"],
                    "substantive_revision_path": [],
                    "evidenced_independent_cross_checks": [],
                }
                routes[route] = record(
                    "precall_pure_target_class",
                    arm=arm,
                    task_key=key,
                    route=route,
                    signature=signature,
                    behavior_key=sha(encode(signature)),
                    actual_model_trajectory=False,
                )
            require(
                routes["D"]["signature"] != routes["R"]["signature"],
                "prototype.D_R_distinct_physical_support",
            )
            tasks[arm][key] = routes
    return record(
        "NE_target_class_index", tasks=tasks, cross_condition_class_identity_never_collapsed=True
    )


def matches_route(normalized, prototype):
    signature = prototype["signature"]
    return (
        normalized.get("status") == "MAPPED"
        and normalized["normal_form"] == signature["answer_source_normal_form"]
        and normalized["active_source_ids"] == signature["active_support"]
    )


def complete_class(projection, prototypes):
    if projection is None or projection["status"] != "MAPPED":
        return "UNDETERMINED"
    signature = projection["behavior_signature"]
    require(projection["behavior_key"] == sha(encode(signature)), "class.full_signature_identity")
    require(
        all(
            signature[field] == prototypes["R"]["signature"][field]
            for field in ("fixed_condition", "task_version", "source_document_id", "goal_scope")
        ),
        "class.same_registered_condition_task_and_goal",
    )
    for route in ("D", "R"):
        if encode(signature) == encode(prototypes[route]["signature"]):
            return "PURE_" + route
    routes = [
        route
        for route in ("D", "R")
        if signature["answer_source_normal_form"]
        == prototypes[route]["signature"]["answer_source_normal_form"]
        and signature["active_support"] == prototypes[route]["signature"]["active_support"]
    ]
    route = routes[0] if len(routes) == 1 else "OTHER"
    revision = bool(signature["substantive_revision_path"])
    check = bool(signature["evidenced_independent_cross_checks"])
    if revision and check:
        return route + "_WITH_SUBSTANTIVE_REVISION_AND_CROSS_CHECK"
    if check:
        return route + "_WITH_CROSS_CHECK"
    if revision:
        return route + "_WITH_SUBSTANTIVE_REVISION"
    return "OTHER_VALID_CLASS"


def verify_extra_evidence(review, raw_messages, audit):
    final_index = audit["first_final_index"]

    def verify(items, *, latest=None, must_include=None):
        require(isinstance(items, list), "review.extra_evidence_list")
        for item in items:
            index, quote = item["response_index"], item["quote"]
            require(
                type(index) is int
                and index in raw_messages
                and isinstance(quote, str)
                and quote
                and quote in raw_messages[index]
                and (latest is None or index <= latest),
                "review.extra_actual_chronological_quote",
            )
        if must_include is not None:
            require(
                any(e["response_index"] == must_include for e in items),
                "review.extra_this_event_quote",
            )

    mention = review["R_mention"]
    require(
        mention["status"] in {"CONFIRMED", "NOT_OBSERVED", "UNDETERMINED"},
        "review.R_mention_status",
    )
    verify(mention["evidence"])
    if mention["status"] == "CONFIRMED":
        require(bool(mention["evidence"]), "review.R_mention_needs_actual_public_relation")
    calls = {call["call_id"]: call for call in audit["calculations"]}
    for cid, semantics in review.get("call_semantics", {}).items():
        require(cid in calls, "review.only_actual_successful_calculation")
        index = calls[cid]["response_index"]
        for field in ("formula_applicability", "variable_correspondence", "unit_handling"):
            item = semantics[field]
            require(
                item["status"] in {"PASS", "FAIL", "UNDETERMINED"},
                "review.per_call_semantics_status",
            )
            verify(item["evidence"], latest=index)
            if item["status"] in {"PASS", "FAIL"}:
                require(bool(item["evidence"]), "review.per_call_semantic_claim_evidence")
    link = review["R_Final_link"]
    require(
        link["status"] in {"CONFIRMED", "NOT_OBSERVED", "UNDETERMINED"},
        "review.R_Final_link_status",
    )
    verify(link["evidence"])
    if link["status"] == "CONFIRMED":
        require(final_index is not None, "review.R_Final_link_requires_actual_Final")
        verify(link["evidence"], must_include=final_index)
    return True


def normalize_executions(session, mapping):
    """Map observed successful calls independently of final-answer qualification."""
    turns = {t["binding"]["response_index"]: t for t in session["turns"]}
    previous, prior_calls, normals, ledgers, adaptations, unresolved = {}, {}, {}, [], [], []
    facts = {f["id"]: f for f in session["public"]["numeric_catalog"]}
    for index, turn in turns.items():
        call = turn["event"]["tool_call"]
        if call is None:
            continue
        cid = call["id"]
        if call["output"]["status"] == "ok" and call["name"] == "read_source":
            output = call["output"]["result"]
            sid = output.get("numeric_source_id")
            if sid is not None:
                require(
                    sid in facts
                    and call["arguments"]["locators"] == [sid]
                    and Fraction(output["exact_value"]) == Fraction(facts[sid]["value"]),
                    "execution.read_source_exact_actual_operand",
                )
                previous[cid] = normalize_expression(
                    "read_value",
                    {
                        "body": {
                            "kind": "source",
                            "source_id": sid,
                            "source_exact": facts[sid]["value"],
                            "executed_exact": output["exact_value"],
                            "attribution": "actual_numeric_read",
                            "evidence_verified": True,
                        }
                    },
                )
        if call["output"]["status"] == "ok" and call["name"] == "calculate":
            try:
                normal, ledger, adaptation = _normalize_call(
                    call,
                    index,
                    mapping.get("occurrences", {}).get(cid),
                    session["public"],
                    turns,
                    previous,
                    prior_calls,
                )
                normals[cid] = normal
                ledgers.extend(ledger)
                adaptations.append(adaptation)
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
                normals[cid] = {"status": "UNDETERMINED", "reason": str(error)}
            previous[cid] = normals[cid]
            if normals[cid]["status"] != "MAPPED":
                unresolved.append(cid)
        prior_calls[cid] = {"index": index, "call": call}
    return {
        "normalizations": normals,
        "source_mapping_ledger": ledgers,
        "normalization_adaptations": adaptations,
        "unresolved_calculation_ids": unresolved,
        "original_source_values_or_expressions_not_repaired": True,
        "mapping_does_not_by_itself_certify_financial_applicability": True,
    }


def R_evidence_chain(session, review, prototypes, projection=None):
    row = session["row"]
    require(
        prototypes["R"]["arm"] == row["arm"]
        and prototypes["R"]["task_key"] == row["task_key"]
        and prototypes["R"]["signature"]["source_document_id"] == session["public"]["id"],
        "R_chain.same_registered_condition_task_and_source",
    )
    observed = normalize_executions(session, review["mapping"])
    normals = observed["normalizations"]
    registered_R_sources = set(prototypes["R"]["signature"]["active_support"])
    component_sources_by_call = {}
    for entry in observed["source_mapping_ledger"]:
        sid = entry.get("source_id")
        if sid in registered_R_sources:
            component_sources_by_call.setdefault(entry["call_id"], set()).add(sid)
    component_consumption = {
        "source_ids_by_call": {
            cid: sorted(sids) for cid, sids in component_sources_by_call.items()
        },
        "calls_consuming_all_registered_R_source_operands": [
            cid for cid, sids in component_sources_by_call.items() if sids == registered_R_sources
        ],
        "operand_consumption_alone_is_not_proof_of_the_R_relation": True,
    }
    executed = [cid for cid, normal in normals.items() if matches_route(normal, prototypes["R"])]
    unknown = observed["unresolved_calculation_ids"]
    execution_status = (
        "CONFIRMED"
        if executed
        else "UNDETERMINED"
        if unknown or row["terminal"].startswith("unknown")
        else "NOT_OBSERVED"
    )
    calls = {
        turn["event"]["tool_call"]["id"]: turn["event"]["tool_call"]
        for turn in session["turns"]
        if turn["event"]["tool_call"] is not None
    }
    source_statuses = {}
    for cid in executed:
        semantics = review.get("call_semantics", {}).get(cid, {})
        states = [
            semantics.get(field, {}).get("status", "UNDETERMINED")
            for field in ("formula_applicability", "variable_correspondence", "unit_handling")
        ]
        source_statuses[cid] = (
            "PASS"
            if all(s == "PASS" for s in states)
            else "FAIL"
            if "FAIL" in states
            else "UNDETERMINED"
        )
    source_status = (
        "PASS"
        if "PASS" in source_statuses.values()
        else "UNDETERMINED"
        if "UNDETERMINED" in source_statuses.values()
        else "FAIL"
        if source_statuses
        else "NOT_ESTABLISHED"
    )
    answer_id = row["answer_calculation_id"]
    ancestors = set()

    def visit(cid):
        if cid not in calls or cid in ancestors:
            return
        ancestors.add(cid)
        call = calls[cid]
        if call["name"] == "calculate" and call["output"]["status"] == "ok":
            for ref in call["output"]["result"]["used_result_ids"]:
                visit(ref)

    visit(answer_id)
    used = set(executed) & ancestors
    checked = set()
    if projection is not None and projection["status"] == "MAPPED":
        for check in review["mapping"].get("cross_checks", []):
            if check["call_id"] in executed:
                checked.add(check["call_id"])
    link = review["R_Final_link"]
    linked = (
        bool(used or checked)
        and link["status"] == "CONFIRMED"
        and row["selected_tool_result_numerically_matches_publication"]
        and row["explicit_final_result_reference_consistent"]
        and review["publication_alignment"]["status"] == "PASS"
    )
    final_status = (
        "CONFIRMED"
        if linked
        else "UNDETERMINED"
        if link["status"] == "UNDETERMINED"
        else "NOT_OBSERVED"
    )
    class_name = (
        complete_class(projection, prototypes)
        if row["formula_driven_trace_verified"]
        else "NOT_JOINT_VALID"
    )
    return record(
        "R_public_execution_evidence_chain",
        label=row["label"],
        arm=row["arm"],
        task_key=row["task_key"],
        original_registered_denominator=8,
        public_R_mention=review["R_mention"],
        R_execution_status=execution_status,
        actual_R_calculation_ids=executed,
        R_execution_definition=(
            "successful source-symbolic registered R relation on actually "
            "consumed operands; no equal-number source search or private-thought "
            "evidence"
        ),
        per_R_call_source_relation_status=source_statuses,
        R_source_relation_status=source_status,
        R_Final_support_status=final_status,
        R_answer_ancestor_ids=sorted(used),
        R_cross_check_ids=sorted(checked),
        R_Final_link_review=link,
        complete_behavior_label=class_name,
        full_class_not_inferred_from_intended_exploration_prompt=True,
        valid_pure_R=row["formula_driven_trace_verified"] and class_name == "PURE_R",
        observed_execution_mapping=observed,
        R_component_operand_consumption=component_consumption,
        different_physical_source_occurrences_not_silently_collapsed=True,
    )
