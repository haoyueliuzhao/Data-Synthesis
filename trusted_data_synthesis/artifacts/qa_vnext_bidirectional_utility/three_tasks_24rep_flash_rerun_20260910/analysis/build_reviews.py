"""Author's finite review after reading all 167 original public responses.

This copies exact quotes and implements the explicit per-task decisions below.
It does not call a model, change a reference/alias, repair a response, or replay
a tool. Mapping is built only for the 27 sessions expected to qualify under the
unchanged policy; all other sessions retain their original evidence and scores.
"""

import ast
import copy
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.plan import (
    LABELS,
    OUTPUT,
    read_json,
    require,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import normalize_unit

X1_UNIT_REJECTIONS = {3, 5, 7, 15}
X2_ACCEPTED_UNITS = {5, 12, 13, 16, 23}
X3_REGISTERED_PERIOD = {16, 18}
X3_PRECALL_DATE_UNRESOLVED = {8, 15, 17}
X3_FINAL_DATE_UNRESOLVED = {1, 8, 9, 13, 15, 17, 19, 21}
X1_UNEXECUTED_COMPONENT_MENTIONS = {3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 18, 19, 20, 23, 24}
SOURCES = {
    "X1": ("source:t4c1n0", "source:t1c1n0"),
    "X2": ("source:q11n3", "source:q11n4"),
    "X3": ("source:t8c1n0", "source:t8c2n0"),
}
ROLES = {
    "X1": (
        "Entergy Mississippi 2003 company-defined net revenue",
        "Entergy Mississippi 2002 company-defined net revenue",
    ),
    "X2": (
        "PPG product warranty reserve at end of 2006",
        "PPG product warranty reserve at end of 2005",
    ),
    "X3": (
        "Garmin fiscal 2008 ending reconciled unrecognized tax benefits",
        "Garmin fiscal 2007 ending reconciled unrecognized tax benefits",
    ),
}


def evidence(raw, index):
    return {"response_index": index, "quote": raw[index]}


def declaration_pointer(args, node, source_id):
    """Find the manually identified source declaration, never a matching number.

    For literals, the reviewed same-call relationship connects each operand to
    its stated source role. An unused variables entry is not claimed to have
    been numerically resolved. The downstream mapper records literal vs name.
    """
    pointers = []
    declarations, variables = args.get("sources", {}), args.get("variables", {})
    if isinstance(node, ast.Name):
        require(node.id in variables, "review.actual_named_operand")
        variable = variables[node.id]
        if isinstance(declarations, dict) and node.id in declarations:
            require(declarations[node.id] == source_id, "review.do_not_replace_declared_source")
            pointers.append(["sources", node.id])
        if isinstance(variable, dict):
            for field in ("source", "source_id"):
                if field in variable:
                    require(variable[field] == source_id, "review.no_conflicting_variable_source")
                    pointers.append(["variables", node.id, field])
    else:
        require(isinstance(node, ast.Constant), "review.reviewed_simple_literal")
        if isinstance(declarations, dict):
            pointers.extend(
                ["sources", name] for name, sid in declarations.items() if sid == source_id
            )
        for name, value in variables.items():
            if isinstance(value, dict):
                pointers.extend(
                    ["variables", name, field]
                    for field in ("source", "source_id")
                    if value.get(field) == source_id
                )
    require(bool(pointers), "review.explicit_preidentified_source_required")
    return pointers[0]


def simple_difference_occurrences(key, call, index, raw):
    args = call["arguments"]
    tree = ast.parse(args["expression"], mode="eval").body
    require(
        isinstance(tree, ast.BinOp) and isinstance(tree.op, ast.Sub),
        "review.actual_reviewed_difference_shape",
    )
    return {
        address: {
            "kind": "source",
            "source_id": sid,
            "attribution": "model_declaration",
            "declaration_pointer": declaration_pointer(args, operand, sid),
            "evidence": [evidence(raw, index)],
            "role": role,
            "period": "2003 versus 2002"
            if key == "X1"
            else "2006 versus 2005"
            if key == "X2"
            else "fiscal 2008 year-end versus fiscal 2007 year-end",
            "unit": "USD_million",
        }
        for address, operand, sid, role in zip(
            ("body.left", "body.right"),
            (tree.left, tree.right),
            SOURCES[key],
            ROLES[key],
            strict=True,
        )
    }


def main(root):
    out = root / OUTPUT
    require(
        read_json(out / "online/summary.json")["all_workers_terminated"], "review.only_after_all_72"
    )
    template = read_json(out / "assessment/review_template.json")
    private = read_json(out / "preparation/private/evaluation_targets.json")
    store = DurableStore(out / "review_parts")
    reviews, observations = {}, []
    for label in LABELS:
        _, key, rep_text = label.split("_")
        rep = int(rep_text)
        directory = out / "online/sessions" / label
        result = read_json(directory / "result.json")
        audit = read_json(out / "assessment/sessions" / (label + ".json"))
        raw = {
            int(path.name[:3]): path.read_text()
            for path in sorted((directory / "turns").glob("*_assistant.raw"))
        }
        require(len(raw) == len(result["events"]), "review.every_original_public_event")
        final_index = audit["first_final_index"]
        require(
            final_index == len(raw) - 1 and result["terminal"] == "model_final",
            "review.actual_first_Final",
        )
        review = copy.deepcopy(template[label])
        # Preserve the original lexical value and the actual Final.unit exactly.
        require(
            review["published_value"] == result["final"]["value"]
            and review["published_unit"] == result["final"]["unit"],
            "review.no_answer_or_unit_replacement",
        )
        expected_value = (
            "46.4"
            if key == "X1"
            else "6"
            if key == "X2"
            else "87.8"
            if rep in X3_REGISTERED_PERIOD
            else "143.9"
        )
        require(
            Fraction(str(review["published_value"])) == Fraction(expected_value),
            "review.original_manually_checked_publication",
        )
        answer_id = result["final"]["result_id"]
        selected = next(c for c in audit["calculations"] if c["call_id"] == answer_id)
        require(
            Fraction(selected["actual_exact_value"]) == Fraction(expected_value),
            "review.original_selected_execution",
        )
        review["answer_calculation_id"] = answer_id
        before = [evidence(raw, selected["response_index"])]
        if selected["response_index"] > 0:
            before.insert(0, evidence(raw, 0))
        final = [evidence(raw, final_index)]
        unit_rejected = (key == "X1" and rep in X1_UNIT_REJECTIONS) or (
            key == "X2" and rep not in X2_ACCEPTED_UNITS
        )
        require(
            (normalize_unit(review["published_unit"]) != private[key]["unit"]) == unit_rejected,
            "review.frozen_unit_policy_not_extended",
        )
        scope_mismatch = key == "X3" and rep not in X3_REGISTERED_PERIOD
        expected_valid = not unit_rejected and not scope_mismatch
        if key in {"X1", "X2"}:
            formula_note = (
                "The publicly chosen relation is the later balance/annual "
                "amount minus the earlier corresponding amount: "
            ) + (
                "Entergy Mississippi company-defined net revenue for 2003 versus 2002."
                if key == "X1"
                else (
                    "PPG warranty reserves for 2006 versus 2005, not the "
                    "adjacent asset-retirement obligation or pension table."
                )
            )
            correspondence_note = (
                "The actual selected calculation's two original source declarations identify "
                + " and ".join(ROLES[key])
                + (
                    ". Their actual consumed amounts agree with the original "
                    "facts. Literal expressions are not falsely described as "
                    "variable resolution."
                )
            )
        elif not scope_mismatch:
            formula_note = (
                "The model explicitly interprets the question as fiscal 2008 "
                "year-end minus fiscal 2007 year-end, matching the registered "
                "comparison."
            )
            correspondence_note = (
                "Actual selected inputs are t8c1n0=214.4 and t8c2n0=126.6, both "
                "corresponding ending balances. No equal-valued opening-balance "
                "alias was substituted by the reviewer."
            )
        else:
            formula_note = (
                "The model selects a two-fiscal-year cumulative change (start "
                "2007 through end 2008), producing 143.9, instead of the "
                "registered adjacent-year-end comparison 87.8. The original "
                "wording 'during 2007 and 2008' admits a plausible cumulative "
                "reading; applicability to the registered scope is not certified."
                " This is not an arithmetic-error judgment or a retrospective "
                "target correction."
            )
            correspondence_note = (
                "The original 70.5 and 214.4 source associations describe fiscal "
                "2007 opening and fiscal 2008 closing under the model's chosen "
                "interval, or the corresponding explicit annual-difference "
                "decomposition. This does not certify correspondence to the "
                "registered narrower interval. No source was repaired."
            )
        if label == "T_X2_16":
            formula_note += (
                " The selected second calculation is correct after an explicitly "
                "acknowledged successful but unintended literal-year subtraction "
                "2006-2005=1; the actual execution-input revision is substantive "
                "and remains a separate valid behavior class."
            )
        review["formula_applicability"] = {
            "status": "UNDETERMINED" if scope_mismatch else "PASS",
            "evidence": before,
            "explanation": formula_note,
        }
        review["variable_correspondence"] = {
            "status": "UNDETERMINED"
            if key == "X3" and rep in X3_PRECALL_DATE_UNRESOLVED
            else "PASS",
            "evidence": before,
            "explanation": correspondence_note
            + (
                (
                    " The same-call prose also describes the FY2007 opening value"
                    " using the year-end column date as if it were the opening "
                    "date; this timestamp attribution remains unresolved."
                )
                if key == "X3" and rep in X3_PRECALL_DATE_UNRESOLVED
                else ""
            ),
        }
        review["unit_handling"] = {
            "status": "PASS",
            "evidence": before,
            "explanation": (
                "The selected amounts and their source context use USD millions "
                "consistently; subtraction preserves that scale. This semantic "
                "input-unit finding is separate from the unchanged raw Final-unit"
                " alias test; no new alias is added."
            ),
        }
        review["publication_alignment"] = {
            "status": "FAIL" if scope_mismatch else "PASS",
            "evidence": final,
            "explanation": "The actual Final.value and actual referenced tool result agree. "
            + (
                (
                    "The primary 143.9 is not the registered 87.8; annual "
                    "breakdown values are distinct quantities and cannot replace "
                    "the primary answer."
                )
                if scope_mismatch
                else "The direction and financial amount match the registered target."
            )
            + (
                (
                    " However, the original Final.unit string is not recognized "
                    "by the frozen dictionary, so the unchanged answer score "
                    "remains FAIL; no definite monetary-meaning error is inferred"
                    " from that label rejection alone."
                )
                if unit_rejected
                else ""
            ),
        }
        final_unresolved = key == "X3" and rep in X3_FINAL_DATE_UNRESOLVED
        review["final_answer_consistency"] = {
            "status": "UNDETERMINED" if final_unresolved else "PASS",
            "evidence": final,
            "explanation": (
                (
                    "The cumulative amount is internally coherent, but the Final "
                    "describes the FY2007 opening balance with the FY2007 "
                    "year-end date. This possible column-date/point-date "
                    "conflation is not repaired or certified."
                )
                if final_unresolved
                else (
                    "Final is internally coherent for the explicitly chosen "
                    "interval and positive increase. This is not an independent "
                    "certification that an alternate interval answers the "
                    "registered question."
                )
            ),
        }
        if key == "X1":
            planning = (
                "All actually successful X1 calculations use the two comparative "
                "net-revenue endpoints. "
            )
            if rep in X1_UNEXECUTED_COMPONENT_MENTIONS:
                planning += (
                    "The original public prose or Final also gives the 48.3 and "
                    "-1.9 component relation, but no calculator call executes "
                    "that relation. Mentioning it is not an executed R route or "
                    "independent cross-check. "
                )
        elif key == "X2":
            planning = (
                "Final relies on warranty reserve endpoint subtraction; no "
                "original successful call executes the warranty "
                "charge/cash/acquisition movement sum. "
            )
        else:
            planning = (
                "The actually selected interval is the registered adjacent-year comparison. "
                if not scope_mismatch
                else (
                    "The actually selected interval is cumulative 2007-2008, not "
                    "the registered adjacent-year comparison. "
                )
            )
            if rep == 3:
                planning += (
                    "Two successful calls repeat the annual-difference sum; "
                    "repetition of the same relation is not an independent "
                    "movement-route check. "
                )
            if rep == 15:
                planning += (
                    "A second call actually sums annual endpoint differences as a"
                    " check of the two-year change; it does not sum underlying "
                    "tax movements, and the session remains nonqualifying under "
                    "the registered target. "
                )
            if rep == 19:
                planning += (
                    "The first successful call produced 87.8; the second changed "
                    "the beginning period and produced 143.9, which the actual "
                    "Final chose. The first result is not substituted back into "
                    "Final. "
                )
        planning += (
            "Message-only deliveries and errors remain in the original "
            "transcript, and only actual accepted successful tools count as "
            "execution."
        )
        review["planning_observations"] = {
            "text": planning,
            "evidence": [evidence(raw, i) for i in raw],
        }
        if expected_valid:
            occurrences, annotations, revisions = {}, [], []
            for event in result["events"]:
                index, call = event["response_index"], event["tool_call"]
                role = "Final" if event["final"] else "public_answer_delivery_message"
                interpretation = (
                    "Original legal public answer delivery; not an executed alternative formula."
                )
                if call:
                    require(call["name"] == "calculate", "review.no_unreviewed_tool_type")
                    if call["output"]["status"] == "ok":
                        role = "answer_calculation"
                        interpretation = formula_note
                        if label == "T_X2_16" and index == 0:
                            require(
                                call["arguments"]["expression"] == "2006 - 2005"
                                and call["output"]["result"]["exact_value"] == "1",
                                "review.actual_literal_year_miscalculation",
                            )
                            role = "superseded_calculation"
                            interpretation = (
                                "Successful but unintended literal-year "
                                "subtraction, explicitly corrected in the next "
                                "public response; not a format-only failure."
                            )
                            occurrences[call["id"]] = {
                                address: {
                                    "kind": "constant",
                                    "value": value,
                                    "reason": (
                                        "Actual unintended year numeral in the "
                                        "original executed expression, not a "
                                        "resolved reserve variable or an inferred"
                                        " source claim."
                                    ),
                                    "evidence": [evidence(raw, index)],
                                }
                                for address, value in (
                                    ("body.left", "2006"),
                                    ("body.right", "2005"),
                                )
                            }
                        else:
                            occurrences[call["id"]] = simple_difference_occurrences(
                                key, call, index, raw
                            )
                    else:
                        role = "format_failed_calculation"
                        interpretation = (
                            "Unparseable digit-leading variable names; no numeric"
                            " result was executed. Subsequent "
                            "source/value/relationship-preserving repair is "
                            "format-only."
                        )
                        require(
                            label in {"T_X1_06", "T_X2_12"} and index == 0,
                            "review.explicit_valid_format_recovery_set",
                        )
                        revisions.append(
                            {
                                "before_index": 0,
                                "after_index": 1,
                                "change_kind": "format_only",
                                "semantic_key": None,
                                "interpretation": interpretation,
                                "evidence": [evidence(raw, 0), evidence(raw, 1)],
                            }
                        )
                if event["final"]:
                    interpretation = review["publication_alignment"]["explanation"]
                annotations.append(
                    {
                        "response_index": index,
                        "role": role,
                        "interpretation": interpretation,
                        "evidence": [evidence(raw, index)],
                    }
                )
            if label == "T_X2_16":
                revisions.append(
                    {
                        "before_index": 0,
                        "after_index": 1,
                        "change_kind": "substantive",
                        "semantic_key": {
                            "change": "actual_executed_operand_domain",
                            "from": {
                                "kind": "unintended_literal_year_subtraction",
                                "operands": ["2006", "2005"],
                            },
                            "to": {
                                "kind": "warranty_reserve_difference",
                                "source_ids": list(SOURCES["X2"]),
                            },
                        },
                        "interpretation": (
                            "The previous call succeeded on year literals and "
                            "returned 1. The model explicitly replaced those "
                            "actual inputs with the intended source-grounded "
                            "reserve amounts and returned 6. This is retained as "
                            "a substantive correction, not erased as "
                            "variable-name noise."
                        ),
                        "evidence": [evidence(raw, 0), evidence(raw, 1)],
                    }
                )
            review["mapping"] = {
                "occurrences": occurrences,
                "event_annotations": annotations,
                "revisions": revisions,
                "cross_checks": [],
            }
        observations.append(
            {
                "label": label,
                "task_key": key,
                "expected_joint_valid_under_frozen_policy": expected_valid,
                "raw_Final_value": review["published_value"],
                "raw_Final_unit": review["published_unit"],
                "raw_unit_dictionary_rejection": unit_rejected,
                "registered_period_mismatch": scope_mismatch,
                "answer_calculation_id": answer_id,
                "source_association_not_inferred_by_equal_number_search": True,
                "all_original_raw_response_sha256": {str(i): sha(raw[i].encode()) for i in raw},
                "financial_scope_notes": formula_note,
                "mechanism_notes": planning,
            }
        )
        reviews[label] = review
    require(
        len(reviews) == 72
        and sum(r["expected_joint_valid_under_frozen_policy"] for r in observations) == 27,
        "review.complete_manually_checked_decisions",
    )
    store.json("reviews.json", reviews)
    store.json(
        "decisions.json",
        {
            "author": "executing assistant after full public-history review",
            "independent_expert": False,
            "condition_or_class_count_used_to_change_policy": False,
            "rows": observations,
            "source_target_unit_aliases_or_original_responses_changed": False,
        },
    )
    print(
        {
            "reviews": len(reviews),
            "expected_valid": 27,
            "raw_unit_gate_rejections": 23,
            "registered_period_mismatches": 22,
        },
        flush=True,
    )


if __name__ == "__main__":
    main(Path.cwd())
