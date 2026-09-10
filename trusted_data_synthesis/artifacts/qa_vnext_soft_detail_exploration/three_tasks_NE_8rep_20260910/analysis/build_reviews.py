"""Post-collection author review of all 48 masked packets / 116 public responses.

This helper records the executing assistant's reviewed decisions, not an
independent expert assessment or a preregistered automatic semantic classifier.
It never reads the private review-id-to-condition map. Source roles below were
identified from the unchanged public sources and the actual public statements,
not by searching for equal-valued source facts. No old score or new policy changes.
"""

import ast
import copy
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    OUTPUT,
    read_json,
    require,
    sha,
)

MENTIONS = {
    1: [1],
    3: [1],
    4: [1],
    6: [1],
    7: [1],
    8: [0],
    12: [0],
    14: [0],
    22: [2],
    25: [0, 1],
    29: [2],
    31: [1],
    37: [0, 1],
    39: [1],
    41: [1],
    47: [1],
}
OPENING_VARIANTS = {3, 16, 23, 27, 28, 36, 48}
SYNTAX_REPAIRS = {20: [(0, 1)], 29: [(0, 1)], 44: [(1, 2)]}
PROTOCOL_REPAIRS = {22: [(0, 1)], 35: [(0, 1)], 44: [(0, 1)]}
EXTRA_LEGAL_DELIVERIES = {
    5: [1, 2, 3, 4],
    15: [1],
    18: [1],
    28: [1, 2],
    41: [1],
    45: [1, 2],
    46: [1, 2, 3],
}
ENDPOINTS = {
    "X1": ("source:t4c1n0", "source:t1c1n0"),
    "X2": ("source:q11n3", "source:q11n4"),
    "X3C": ("source:t8c1n0", "source:t8c2n0"),
}
ROLES = {
    "X1": {
        "source:t4c1n0": (
            (
                "Entergy Mississippi 2003 company-defined net revenue "
                "(comparative annual gross-margin measure)"
            ),
            "2003",
        ),
        "source:t1c1n0": (
            (
                "Entergy Mississippi 2002 company-defined net revenue "
                "(comparative annual gross-margin measure)"
            ),
            "2002",
        ),
    },
    "X2": {
        "source:q11n3": ("PPG product warranty reserve, later year-end balance", "2006-12-31"),
        "source:q11n4": (
            "PPG product warranty reserve, prior year-end / 2006 rollforward opening balance",
            "2005-12-31 / beginning of 2006",
        ),
        "source:q12n3": (
            "PPG pretax warranty charges accruing to the product warranty reserve",
            "2006",
        ),
        "source:q13n0": ("PPG cash warranty outlays reducing the product warranty reserve", "2006"),
        "source:q14n0": (
            "PPG warranty obligations assumed in business acquisitions, increasing the reserve",
            "2006",
        ),
    },
    "X3C": {
        "source:t8c1n0": (
            "Garmin ending reconciled unrecognized tax benefit balance in the fiscal-2008 column",
            "fiscal year end 2008-12-27",
        ),
        "source:t8c2n0": (
            "Garmin ending reconciled unrecognized tax benefit balance in the fiscal-2007 column",
            "fiscal year end 2007-12-29",
        ),
        "source:t1c1n0": (
            (
                "Garmin opening balance for the fiscal year ended 2008-12-27; "
                "explicitly linked by the model to the preceding fiscal-year-end "
                "balance"
            ),
            "opening of fiscal 2008 / prior fiscal 2007 close",
        ),
    },
}


def quote(raw, index):
    return {"response_index": index, "quote": raw[index]}


def declared_pointer(arguments, node, sid):
    declarations, variables = arguments.get("sources", {}), arguments.get("variables", {})
    candidates = []
    if isinstance(node, ast.Name):
        value = variables[node.id]
        declared = declarations.get(node.id) if isinstance(declarations, dict) else None
        if declared is not None:
            require(declared == sid, "review.actual_named_source_not_replaced")
            candidates.append(["sources", node.id])
        if isinstance(value, dict):
            for field in ("source", "source_id"):
                if field in value:
                    require(value[field] == sid, "review.no_conflicting_named_declaration")
                    candidates.append(["variables", node.id, field])
    else:
        # The source ID was identified by its public role BEFORE examining values.
        # A literal expression does not consume a variables entry numerically.
        if isinstance(declarations, dict):
            candidates.extend(
                ["sources", name] for name, item in declarations.items() if item == sid
            )
        for name, value in variables.items():
            if isinstance(value, dict):
                candidates.extend(
                    ["variables", name, field]
                    for field in ("source", "source_id")
                    if value.get(field) == sid
                )
    require(bool(candidates), "review.preidentified_source_declaration_required")
    return candidates[0]


def occurrences(packet, number, event, raw):
    key, call, index = packet["task_key"], event["tool_call"], event["response_index"]
    args = call["arguments"]
    expression = args["expression"]
    tree = ast.parse(expression, mode="eval").body
    facts = {item["id"]: item for item in packet["public_document"]["numeric_catalog"]}
    expected = set(ENDPOINTS[key])
    if number in OPENING_VARIANTS:
        expected = {"source:t8c1n0", "source:t1c1n0"}
    if number == 14:
        expected = {"source:q11n4", "source:q12n3", "source:q14n0", "source:q13n0"}
        require(
            expression == "(beg + charges + assumed - outlays) - beg",
            "review.original_component_rollforward_expression",
        )
    result = {}

    def visit(node, address):
        if isinstance(node, ast.BinOp):
            visit(node.left, address + ".left")
            visit(node.right, address + ".right")
            return
        if isinstance(node, ast.Name):
            supplied = args["variables"][node.id]
            sid = args.get("sources", {}).get(node.id)
            if sid is None and isinstance(supplied, dict):
                sid = supplied.get("source", supplied.get("source_id"))
            require(sid in expected, "review.actual_named_source_matches_reviewed_role_set")
            actual = call["output"]["result"]["resolved_variables"][node.id]["exact_value"]
        else:
            require(
                isinstance(node, ast.Constant) and number != 14,
                "review.only_preidentified_literal_difference_case",
            )
            require(
                isinstance(tree, ast.BinOp)
                and isinstance(tree.op, ast.Sub)
                and address in {"body.left", "body.right"},
                "review.literal_source_role_chosen_by_original_expression_position",
            )
            source_pair = ENDPOINTS[key]
            if number in OPENING_VARIANTS:
                source_pair = ("source:t8c1n0", "source:t1c1n0")
            sid = source_pair[0 if address == "body.left" else 1]
            actual = ast.get_source_segment(expression, node)
        # This is a consistency check AFTER role/source selection, not a search.
        require(
            Fraction(str(actual)) == Fraction(facts[sid]["value"]),
            "review.actual_consumed_amount_agrees_with_preidentified_source",
        )
        role, period = ROLES[key][sid]
        result[address] = {
            "kind": "source",
            "source_id": sid,
            "attribution": "model_declaration",
            "declaration_pointer": declared_pointer(args, node, sid),
            "role": role,
            "period": period,
            "unit": "USD_million",
            "evidence": [quote(raw, index)],
            "literal_expression_is_not_claimed_to_resolve_unused_named_variables": not isinstance(
                node, ast.Name
            ),
        }

    visit(tree, "body")
    require(
        {entry["source_id"] for entry in result.values()} == expected,
        "review.exact_original_active_input_role_set",
    )
    require(
        call["output"]["result"]["used_result_ids"] == [], "review.no_unreviewed_result_dependency"
    )
    return result


def main(root):
    out = root / OUTPUT
    require(
        read_json(out / "online/summary.json")["all_workers_terminated"],
        "review.only_after_fixed_collection_finished",
    )
    templates = read_json(out / "assessment/review_template.json")
    packets = [
        read_json(out / f"assessment/public_review_packets/review_{i:03d}.json")
        for i in range(1, 49)
    ]
    reviews, decisions = {}, []
    total_public = 0
    for number, packet in enumerate(packets, 1):
        rid, key = packet["review_id"], packet["task_key"]
        require(rid == f"review_{number:03d}", "review.masked_original_order")
        require("arm" not in packet and "SYSTEM" not in packet, "review.no_condition_metadata")
        raw = {int(i): value for i, value in packet["raw_messages"].items()}
        events = packet["actual_events"]
        total_public += len(raw)
        require(
            set(raw) == {e["response_index"] for e in events}, "review.every_received_public_event"
        )
        final_index = packet["first_final_index"]
        require(
            final_index == len(raw) - 1 and events[final_index]["final"],
            "review.actual_first_Final_boundary",
        )
        review = copy.deepcopy(templates[rid])
        final = packet["raw_final"]
        require(
            str(review["published_value"]) == str(final["value"])
            and review["published_unit"] == final["unit"] == "USD_million",
            "review.actual_Final_fields_not_replaced",
        )
        expected_value = {"X1": "46.4", "X2": "6", "X3C": "87.8"}[key]
        require(
            Fraction(str(final["value"])) == Fraction(expected_value),
            "review.original_read_numeric_field",
        )
        successes = [
            event
            for event in events
            if event["tool_call"] is not None and event["tool_call"]["output"]["status"] == "ok"
        ]
        require(
            len(successes) == 1 and successes[0]["tool_call"]["name"] == "calculate",
            "review.one_actual_successful_calculation_in_each_observed_session",
        )
        selected = successes[0]
        selected_index, selected_call = selected["response_index"], selected["tool_call"]
        require(
            selected_call["id"] == final["result_id"],
            "review.actual_Final_result_id_not_inferred_by_numeric_equality",
        )
        require(
            Fraction(selected_call["output"]["result"]["exact_value"]) == Fraction(expected_value),
            "review.original_actual_result_matches_publication",
        )
        review["answer_calculation_id"] = selected_call["id"]
        review["answer_calculation_unit"] = "USD_million"
        before, final_evidence = [quote(raw, selected_index)], [quote(raw, final_index)]
        if key == "X1":
            formula = (
                "The actually chosen relation is the comparative 2003 company-defined net "
                "revenue minus the 2002 amount. These are the annual net-revenue/gross-margin "
                "measures described in the source, not balance-sheet stocks."
            )
            correspondence = (
                "The original selected inputs identify t4c1n0 (2003) and t1c1n0 (2002) "
                "with the correct financial quantity, year and amount. Literal expressions "
                "retain literal consumption, even when unused variable metadata is supplied."
            )
        elif key == "X2" and number != 14:
            formula = (
                "The actually chosen relation is PPG's 2006 year-end product-warranty reserve "
                "minus its 2005 year-end reserve, not the adjacent pension or asset-retirement "
                "obligation figures."
            )
            correspondence = (
                "The original input declarations identify q11n3 and q11n4 for the respective "
                "2006 and 2005 warranty reserves. The source context disambiguates the same-valued "
                "numbers elsewhere; no equal-number source search is used."
            )
        elif number == 14:
            formula = (
                "The public pre-call explanation and actual expression use the 2006 warranty "
                "rollforward: prior reserve plus warranty charges plus acquired obligations "
                "minus cash outlays, then subtract that same prior reserve. This computes "
                "the requested net change through the actual movement items."
            )
            correspondence = (
                "The actually resolved operands are beg=q11n4, charges=q12n3, assumed=q14n0, "
                "outlays=q13n0, all with their correct 2006 roles (beg is the 2005 closing "
                "reserve). The two beg occurrences refer to the SAME physical source and can "
                "cancel symbolically. Beg=4 is NOT identified with charges=4 just because their "
                "numeric values coincide. All five scalar occurrences remain in the ledger."
            )
        else:
            formula = (
                "The actual relation answers the explicitly clarified interval between fiscal "
                "year ends 2007-12-29 and 2008-12-27, not the cumulative change over both fiscal "
                "years. The selected comparison is grounded in the original reconciliation."
            )
            correspondence = (
                "The actual source declarations use the two ending-balance cells t8c1n0 and "
                "t8c2n0. An unconsumed mention of an equivalent opening balance does not "
                "change those actual source IDs."
                if number not in OPENING_VARIANTS
                else "The model explicitly identifies fiscal-2008 opening balance t1c1n0 with "
                "the preceding fiscal-2007 close, as supported by the reconciliation and its "
                "prior-year ending column. The actual calculation uses t8c1n0 minus t1c1n0. "
                "The reviewer does NOT replace t1c1n0 with equal-valued t8c2n0: this financially "
                "valid physical-source variant remains a different complete class."
            )
        if number == 36:
            correspondence += (
                " The pre-call 'December 27, 2008-beginning/December 29, 2007-ending' phrasing "
                "is read as fiscal-column shorthand, disambiguated by the explicit prior-close "
                "phrase, variable name and Final. This is the reviewer's contextual reading, "
                "not certification of a literal opening point on 2008-12-27."
            )
        if number == 42:
            correspondence += (
                " The first sentence's beginning/ending terminology is read as bridge-comparison "
                "shorthand because the same response explicitly identifies the annual 2003 and "
                "2002 net-revenue amounts. This is a disclosed reviewer interpretation, not a "
                "reclassification of net revenue as a stock balance."
            )
        unit_explanation = (
            "The chosen source amounts, the public currency contract and the selected "
            "calculation all use USD millions; the stated subtraction/rollforward preserves "
            "that scale. This input-unit finding does not override the frozen Final parser."
        )
        publication = (
            "The actual first Final explicitly references the sole real successful calculation; "
            "its numeric value and USD-million field match that original result and its "
            "source-grounded quantity. No answer is taken from earlier flat message objects."
        )
        consistency = (
            "The actual Final's increase, financial quantity and requested comparison period "
            "are coherent with its published amount and the original source. Additional "
            "unexecuted explanations are not counted as tool-backed cross-checks."
        )
        if number == 14:
            publication += (
                " Its supplementary sources list names the reserve endpoints, but result_id "
                "tool:1 actually binds the movement calculation. The reviewer does not "
                "reclassify that execution as D or invent an executed endpoint cross-check."
            )
        if number == 27:
            publication += (
                " The supplementary Final.sources strings use noncanonical heading/segment-like "
                "locators without numeric-span indices. They are NOT certified as valid numeric "
                "catalog IDs. Financial support is established by the actual result_id and "
                "the correct pre-call numeric source declarations; no unregistered hard "
                "Final.sources-format gate is added."
            )
            review["supplementary_Final_citation_diagnostic"] = {
                "status": "NONCANONICAL_LOCATOR_FORMAT",
                "original_sources": final["sources"],
                "not_certified_numeric_catalog_ids": True,
                "actual_calculation_source_binding_unchanged": True,
                "new_hard_financial_validity_gate_added": False,
            }
        if number == 18:
            publication += (
                " The actual Final.answer uses $M shorthand consistently with its explicit "
                "Final.value and Final.unit. The frozen parser nevertheless partially matches "
                "'$46.4' inside '$46.4M' as base dollars and records a conflicting-unit FAIL. "
                "That implementation limitation is retained, not overridden, and is not a "
                "definite financial or arithmetic error by the model."
            )
            consistency += (
                " Here M denotes millions in the explicit USD_million context. The semantic "
                "PASS is distinct from the immutable parser's false-conflict exclusion."
            )
            review["quantity_policy_limitation"] = {
                "kind": "partial_match_of_unsupported_shorthand_M",
                "frozen_score_retained_without_regrading": True,
                "actual_primary_value_and_unit_are_explicit": True,
                "not_claimed_model_financial_or_arithmetic_error": True,
                "no_postcall_parser_patch_or_alias_added": True,
            }
        for field, explanation in (
            ("formula_applicability", formula),
            ("variable_correspondence", correspondence),
            ("unit_handling", unit_explanation),
        ):
            review[field] = {"status": "PASS", "evidence": before, "explanation": explanation}
        review["publication_alignment"] = {
            "status": "PASS",
            "evidence": final_evidence,
            "explanation": publication,
        }
        review["final_answer_consistency"] = {
            "status": "PASS",
            "evidence": final_evidence,
            "explanation": consistency,
        }
        review["R_mention"] = {
            "status": "CONFIRMED" if number in MENTIONS else "NOT_OBSERVED",
            "evidence": [quote(raw, i) for i in MENTIONS.get(number, [])],
            "explanation": (
                "The original public text explicitly gives the registered period's signed "
                "movement/component relation, sometimes inside a full opening-to-ending "
                "reconciliation. This is a public mention only unless actually executed."
                if number in MENTIONS
                else "The complete public history was reviewed and does not explicitly give the "
                "registered movement relation. Citing possible source IDs alone is not a "
                "relation mention, and a host instruction is not a model utterance."
            ),
        }
        review["R_Final_link"] = {
            "status": "CONFIRMED" if number == 14 else "NOT_OBSERVED",
            "evidence": final_evidence if number == 14 else [],
            "explanation": (
                "The actual first Final selects tool:1, the actually executed component "
                "rollforward net change. No other successful calculation exists."
                if number == 14
                else "The actual first Final selects the endpoint calculation; no registered R "
                "result was actually produced for it to select or independently check."
            ),
        }
        review["call_semantics"] = {
            selected_call["id"]: {
                field: copy.deepcopy(review[field])
                for field in ("formula_applicability", "variable_correspondence", "unit_handling")
            }
        }
        mapping = {"occurrences": {}, "event_annotations": [], "revisions": [], "cross_checks": []}
        mapping["occurrences"][selected_call["id"]] = occurrences(packet, number, selected, raw)
        for event in events:
            index, call = event["response_index"], event["tool_call"]
            if event["protocol_error"] is not None:
                role = "protocol_failed_public_response"
                explanation = "Original malformed public JSON/protocol response; no tool execution."
            elif call is not None and call["output"]["status"] == "error":
                role = "format_failed_calculation"
                explanation = (
                    "Digit-leading variable identifier caused syntax failure; no number executed."
                )
            elif call is not None:
                role = "answer_calculation"
                explanation = formula
            elif event["final"]:
                role = "Final"
                explanation = publication
            else:
                role = "public_answer_delivery_message"
                explanation = (
                    "Original legal message or flat answer object without a final key; "
                    "not an earlier terminal Final and not an additional calculation."
                )
            mapping["event_annotations"].append(
                {
                    "response_index": index,
                    "role": role,
                    "interpretation": explanation,
                    "evidence": [quote(raw, index)],
                }
            )
        for repairs, reason in (
            (
                SYNTAX_REPAIRS,
                (
                    "Renamed illegal digit-leading identifiers; sources, values, "
                    "units and subtraction relation are unchanged."
                ),
            ),
            (
                PROTOCOL_REPAIRS,
                (
                    "Removed malformed extra public protocol text / JSON "
                    "packaging; the financial source inputs and chosen "
                    "subtraction relation are unchanged."
                ),
            ),
        ):
            for before_index, after_index in repairs.get(number, []):
                mapping["revisions"].append(
                    {
                        "before_index": before_index,
                        "after_index": after_index,
                        "change_kind": "format_only",
                        "semantic_key": None,
                        "interpretation": reason,
                        "evidence": [quote(raw, before_index), quote(raw, after_index)],
                    }
                )
        failed_indices = {
            event["response_index"]
            for event in events
            if event["protocol_error"] is not None
            or (
                event["tool_call"] is not None and event["tool_call"]["output"]["status"] == "error"
            )
        }
        require(
            failed_indices == {item["before_index"] for item in mapping["revisions"]},
            "review.every_actual_error_has_original_format_recovery",
        )
        actual_messages = [
            e["response_index"]
            for e in events
            if not e["final"] and e["tool_call"] is None and e["protocol_error"] is None
        ]
        require(
            actual_messages == EXTRA_LEGAL_DELIVERIES.get(number, []),
            "review.all_legal_nontemporal_Final_deliveries_recorded",
        )
        review["mapping"] = mapping
        planning = (
            "One actual successful calculation is present. "
            + (
                "It is the source-grounded warranty movement rollforward and its net change. "
                if number == 14
                else (
                    "It is an endpoint difference; any component relation in "
                    "public prose was not executed. "
                )
            )
            + (
                "All original malformed responses, syntax failures and legal message-only "
                "deliveries remain in their actual positions. No successful calculation was "
                "superseded and "
                "no independent second method was executed. N/E metadata was not "
                "used to assign a class."
            )
        )
        if number == 44:
            planning += (
                " The provider placed protocol-planning text and a separator in the public "
                "content field, causing the first JSON parse error. It is preserved as public "
                "malformed content, not taken from the omitted private reasoning_content field."
            )
            review["malformed_public_meta_protocol_content"] = {
                "response_index": 0,
                "source_field": "public assistant content",
                "dedicated_API_reasoning_content_not_read_or_used": True,
                "not_positive_supervision": True,
            }
        review["planning_observations"] = {
            "text": planning,
            "evidence": [quote(raw, i) for i in raw],
        }
        review["condition_inferred_from_self_description"] = False
        reviews[rid] = review
        decisions.append(
            {
                "review_id": rid,
                "task_key": key,
                "actual_first_Final_index": final_index,
                "actual_successful_call_id": selected_call["id"],
                "actual_expression": selected_call["arguments"]["expression"],
                "expected_registered_R_execution": number == 14,
                "public_R_mention_reviewed": number in MENTIONS,
                "uses_distinct_X3_opening_source": number in OPENING_VARIANTS,
                "expected_joint_valid_under_frozen_implementation": number != 18,
                "known_quantity_parser_limitation": number == 18,
                "supplementary_Final_locator_format_issue": number == 27,
                "input_wording_contextual_interpretation_disclosed": number in {36, 42},
                "condition_metadata_inspected_for_decision": False,
                "all_original_public_response_sha256": {str(i): sha(raw[i].encode()) for i in raw},
            }
        )
    require(len(reviews) == 48 and total_public == 116, "review.full_fixed_masked_batch_read")
    require(set(reviews) == set(templates), "review.exact_template_id_set")
    store = DurableStore(out / "review_parts")
    store.json("reviews.json", reviews)
    store.json(
        "decisions.json",
        {
            "author": "executing assistant after full masked-public-history review",
            "independent_expert": False,
            "guaranteed_fully_blinded": False,
            "private_condition_mapping_read_during_authoring": False,
            "new_generation_or_old_rescoring": False,
            "frozen_code_or_rules_changed_after_generation": False,
            "rows": decisions,
        },
    )
    print(
        {
            "masked_reviews": len(reviews),
            "original_public_responses_read": total_public,
            "expected_R_executions": 1,
            "known_parser_limit_exclusions": 1,
            "source_opening_variants_preserved": len(OPENING_VARIANTS),
            "expected_valid_under_frozen_implementation": 47,
        },
        flush=True,
    )


if __name__ == "__main__":
    main(Path.cwd())
