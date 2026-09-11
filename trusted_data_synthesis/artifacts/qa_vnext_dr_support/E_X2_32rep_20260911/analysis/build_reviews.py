"""Transcribe forty individually read cases; not an automatic scientific grader.

All raw packets were read before this transcription. The explicit case registry
below records the judgments; AST/source traversal only attaches exact evidence
and actual occurrence addresses. It does not choose a source by numeric search.
The frozen qualifier, quantity parser and full-class mapper are not changed.
"""

import ast
import copy
import json
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_dr_support.core import (
    Store,
    history_guard,
    verify_preparation,
)
from trusted_synthesis.experiments.finance_qa_vnext_dr_support.plan import (
    OUTPUT,
    read_json,
    record,
    reference,
    require,
)
from trusted_synthesis.experiments.finance_qa_vnext_dr_support.review import (
    claim_certification,
    semantic_binding,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.exploration import (
    verify_extra_evidence,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import verify_quotes


# Each entry is the executing reviewer's conclusion after reading this actual
# packet, not a pattern discovered by the transcription program.
CASES = {
    "dr_old_01": ("R_cancel_beginning", 1),
    "dr_old_02": ("D_named", 1),
    "dr_old_03": ("D_literal", 1),
    "dr_old_04": ("D_named", 1),
    "dr_old_05": ("D_prose_rollforward", 1),
    "dr_old_06": ("D_named", 1),
    "dr_old_07": ("D_message_rollforward", 2),
    "dr_old_08": ("D_named", 1),
    "dr_review_001": ("D_format_recovery", 2),
    "dr_review_002": ("D_prose_rollforward", 1),
    "dr_review_003": ("D_named", 1),
    "dr_review_004": ("D_named", 1),
    "dr_review_005": ("D_wrong_date_source_assertions", 1),
    "dr_review_006": ("D_named", 1),
    "dr_review_007": ("D_empty_second_public_response_no_Final", None),
    "dr_review_008": ("D_named", 1),
    "dr_review_009": ("D_named", 1),
    "dr_review_010": ("D_format_recovery", 2),
    "dr_review_011": ("D_literal", 1),
    "dr_review_012": ("D_plain_numeric_variables", 1),
    "dr_review_013": ("D_literal_free_Final_multiple_amounts", 1),
    "dr_review_014": ("D_named", 1),
    "dr_review_015": ("D_named_no_separate_message", 1),
    "dr_review_016": ("D_named", 1),
    "dr_review_017": ("D_named", 1),
    "dr_review_018": ("D_literal_unused_digit_initial_names", 1),
    "dr_review_019": ("D_named", 1),
    "dr_review_020": ("D_literal", 1),
    "dr_review_021": ("D_named", 1),
    "dr_review_022": ("D_named", 1),
    "dr_review_023": ("D_named", 1),
    "dr_review_024": ("D_named", 1),
    "dr_review_025": ("D_format_recovery", 2),
    "dr_review_026": ("D_extra_legal_publication_message", 2),
    "dr_review_027": ("D_named", 1),
    "dr_review_028": ("D_plus_executed_ending_balance_check", 2),
    "dr_review_029": ("D_named", 1),
    "dr_review_030": ("D_literal", 1),
    "dr_review_031": ("D_plain_numeric_variables", 1),
    "dr_review_032": ("D_Final_sources_also_actual_result", 1),
}

SOURCE_ROLES = {
    "source:q11n3": ("reserve for product warranties", "December 31, 2006", "10"),
    "source:q11n4": ("reserve for product warranties", "December 31, 2005", "4"),
    "source:q12n3": ("pretax warranty charges against income", "fiscal 2006", "4"),
    "source:q13n0": ("cash outlays for product warranties", "fiscal 2006", "5"),
    "source:q14n0": ("warranty obligations assumed in business acquisitions", "fiscal 2006", "7"),
    # These two are retained as the actual erroneous declarations in case 005.
    "source:q11n0": ("day of month, not a money amount", "date in the warranty disclosure", "31"),
    "source:q11n1": ("calendar year, not a money amount", "2006 date token", "2006"),
}

NO_ENDPOINT_FACTS_IN_FINAL = {
    "dr_old_03",
    "dr_review_007",
    "dr_review_009",
    "dr_review_011",
    "dr_review_012",
    "dr_review_014",
    "dr_review_019",
    "dr_review_022",
    "dr_review_026",
    "dr_review_027",
}


def actual_Final_span(raw):
    """Return the exact top-level final value span, never its sibling fields."""
    decoder = json.JSONDecoder()
    position = raw.index("{") + 1
    while True:
        while raw[position].isspace() or raw[position] == ",":
            position += 1
        key, end = decoder.raw_decode(raw, position)
        require(isinstance(key, str), "transcription.object_key")
        position = end
        while raw[position].isspace():
            position += 1
        require(raw[position] == ":", "transcription.object_colon")
        position += 1
        while raw[position].isspace():
            position += 1
        _, end = decoder.raw_decode(raw, position)
        if key == "final":
            return raw[position:end]
        position = end


def transcribe(packet, audit, blank):
    review_id = packet["review_id"]
    family, final_index = CASES[review_id]
    require(packet["first_final_index"] == final_index, "transcription.actual_read_case_shape")
    raw = {int(k): v for k, v in packet["raw_messages"].items()}
    public = packet["public_document"]
    facts = {f["id"]: f for f in public["numeric_catalog"]}
    parsed = {i: json.loads(value) for i, value in raw.items() if value}
    events = packet["events"]
    calls = [e for e in events if e["tool_call"]]
    successful = [e for e in calls if e["tool_call"]["output"]["status"] == "ok"]
    require(
        len(successful) == (2 if family == "D_plus_executed_ending_balance_check" else 1),
        "transcription.read_successful_calls",
    )
    answer_event = successful[0]
    answer_index = answer_event["response_index"]
    answer_id = answer_event["tool_call"]["id"] if final_index is not None else None
    require(
        answer_index == (1 if family == "D_format_recovery" else 0),
        "transcription.read_calculation_time",
    )

    def evidence(index, quote=None):
        value = raw[index] if quote is None else quote
        require(value and value in raw[index], "transcription.exact_nonempty_quote")
        return {"response_index": index, "quote": value}

    def source_evidence(*keys):
        return [
            {"segment_id": key, "quote": public["segments"][key]["text"]}
            for key in dict.fromkeys(keys)
        ]

    final_evidence = (
        [] if final_index is None else [evidence(final_index, actual_Final_span(raw[final_index]))]
    )
    reviewed = copy.deepcopy(blank)
    reviewed["answer_calculation_id"] = answer_id
    reviewed["answer_calculation_unit"] = "USD_million" if answer_id else None
    reviewed["claim_inventory"] = {
        "complete": True,
        "reviewed_response_indices": sorted(raw),
        "explanation": (
            "The executing reviewer read every original public response and actual event. "
            "All nested input/source-map statements, the surrounding financial statements, "
            "extra messages and the entire actual Final were inspected. Derived citations "
            "do not assert that every cited cell contains the derived result."
        ),
    }
    reviewed["reviewer_note"] = {
        "author": "executing assistant; not independent or guaranteed blind",
        "manually_reviewed_family": family,
        "before_transcription_all_40_packets_read": True,
        "not_an_automatic_family_classifier": True,
        "unchanged_quantity_fields_copied_from_frozen_assessment": True,
    }

    def item(status, explanation, quotes):
        return {"status": status, "explanation": explanation, "evidence": quotes}

    formula_text = (
        "The actual relationship uses the publicly requested PPG warranty reserve and "
        "December 31, 2006 versus December 31, 2005, later minus earlier. The real selected "
        "calculation and actual Final complete that net change in USD millions. This is "
        "original-task applicability, not merely correctness for a model-selected goal."
    )
    if family == "R_cancel_beginning":
        formula_text = (
            "The actual call (beg + charges + assumed - outlays) - beg derives the requested "
            "reserve change from the 2006 movements; the two occurrences of the same beginning "
            "balance cancel only in the defined symbolic normal form. All actual operands remain "
            "in the execution ledger. The Final links this result, not an executed second route."
        )
    if family == "D_literal_free_Final_multiple_amounts":
        formula_text += (
            " The actual Final string explicitly states the correct requested increase and "
            "endpoint subtraction. The frozen quantity parser nevertheless leaves multiple "
            "explicit amounts unresolved. Its unknown is retained; sibling value/unit/result_id "
            "outside final are not copied into Final or used as explicit Final linkage."
        )
    if family == "D_plus_executed_ending_balance_check":
        formula_text += (
            " The separately executed second call checks the ending BALANCE, not the requested "
            "net CHANGE. The Final explicitly uses tool:1. The independent balance check and "
            "its corrected predicted amount are retained and may make the full class unmapped."
        )
    formula_state = "UNDETERMINED" if final_index is None else "PASS"
    reviewed["formula_applicability"] = item(
        formula_state,
        formula_text
        if final_index is not None
        else (
            "The observed endpoint subtraction is locally valid and publicly in scope, but "
            "there is no actual Final dependency-chain completion. Do not turn its tool result "
            "into a delivered answer."
        ),
        [evidence(answer_index), *final_evidence],
    )
    bad_sources = family == "D_wrong_date_source_assertions"
    reviewed["variable_correspondence"] = item(
        "FAIL" if bad_sources else "PASS",
        (
            "The prose states the correct reserve amounts, but current nested source-value "
            "assertions map 10 to q11n0 (day 31) and 4 to q11n1 (year 2006); arguments.sources "
            "and Final keep the same erroneous associations. This is a false explicit source "
            "assertion, not merely a noncanonical ID format. No correction is present."
        )
        if bad_sources
        else (
            "The original named inputs/source maps or literal-occurrence context identify the "
            "correct warranty object, year and amount in q11 or the actual 2006 movement items "
            "q12-q14. Numeric equality alone was not used to select a source. Current additional "
            "claims and any explicit later correction are inventoried separately."
        ),
        [evidence(answer_index)],
    )
    reviewed["unit_handling"] = item(
        "PASS",
        "The source and original pre/same-call amounts/variable units are USD millions; no scale or currency conversion is introduced.",
        [evidence(answer_index)],
    )
    reviewed["publication_alignment"] = item(
        "PASS" if final_index is not None else "NOT_ESTABLISHED",
        (
            "The actual Final describes the requested six-million-dollar increase and the "
            "selected successful calculation has that physical quantity. In the free-text "
            "case, this semantic correspondence does not override the separate parser unknown."
        )
        if final_index is not None
        else "No actual Final was delivered; the empty second public response cannot publish the earlier tool result.",
        final_evidence,
    )
    reviewed["final_answer_consistency"] = item(
        "PASS" if final_index is not None else "NOT_ESTABLISHED",
        "The actual Final consistently describes the requested warranty reserve increase, correct years, direction and million-dollar scale."
        if final_index is not None
        else "The actual Final is absent; do not judge fabricated answer fields.",
        final_evidence,
    )
    source_keys = ["q9", "q10", "q11"]
    if family in {"R_cancel_beginning", "D_plus_executed_ending_balance_check"}:
        source_keys += ["q12", "q13", "q14"]
    reviewed["target_binding"] = {
        "parameters": {
            "local_relation": "PASS",
            "public_scope_match": "PASS",
            "registered_scope_match": "PASS" if final_index is not None else "UNDETERMINED",
            "final_chain_completes_public_target": "PASS"
            if final_index is not None
            else "UNDETERMINED",
        },
        "evidence": [evidence(answer_index), *final_evidence],
        "source_evidence": source_evidence(*source_keys),
        "explanation": reviewed["formula_applicability"]["explanation"],
    }
    reviewed["planning_observations"] = {
        "text": "Actual public explanation and arguments only; no provider private reasoning or intended E prompt is used as evidence of execution.",
        "evidence": [evidence(answer_index)],
    }

    claims = []

    def add_claim(
        role,
        location,
        explanation,
        quotes,
        sources,
        *,
        truth=True,
        current=True,
        consumed=False,
        withdrawal=None,
    ):
        params = {"role": role, "current": current, "consumed": consumed}
        field = {
            "DIRECT_SOURCE_VALUE": "source_value_equal",
            "DERIVED_FROM_SOURCES": "derivation_supported",
            "GENERAL_REFERENCE": "reference_relevant",
        }.get(role)
        if field is not None:
            params[field] = truth
        else:
            require(role == "UNRESOLVED", "transcription.registered_claim_role")
        if not current:
            params["withdrawal_supported"] = True
        claims.append(
            {
                "location": location,
                "explanation": explanation,
                "evidence": quotes,
                "source_evidence": sources,
                "parameters": params,
                **({"withdrawal_evidence": withdrawal} if withdrawal else {}),
            }
        )

    for event in calls:
        index, call = event["response_index"], event["tool_call"]
        args = call["arguments"]
        resolved = call["output"].get("result") or {}
        consumed = set(resolved.get("resolved_variables", {}))
        for name, value in args["variables"].items():
            sid = value["source"] if isinstance(value, dict) else args["sources"][name]
            if name in args.get("sources", {}):
                require(
                    args["sources"][name] == sid, "transcription.same_actual_repeated_source_map"
                )
            require(sid in SOURCE_ROLES, "transcription.only_individually_reviewed_sources")
            original_value = value["value"] if isinstance(value, dict) else value
            equality = Fraction(str(original_value)) == Fraction(facts[sid]["value"])
            require(
                equality is (not bad_sources),
                "transcription.observed_numeric_claim_matches_manual_judgment",
            )
            role, period, _ = SOURCE_ROLES[sid]
            add_claim(
                "DIRECT_SOURCE_VALUE",
                f"response[{index}].arguments.variables.{name} and matching arguments.sources entry if present",
                (
                    f"The original nested object or explicit name-to-source map asserts input {name} "
                    f"has the stated value at {sid}. The public source occurrence is {role}, {period}. "
                    + (
                        "The assertion is correct even when the variable is unconsumed or its request fails only syntactically."
                        if equality
                        else "The declared monetary input conflicts with the date-token source; correct surrounding prose does not retract this current explicit assertion."
                    )
                ),
                [evidence(index)],
                source_evidence(facts[sid]["segment"]),
                truth=not bad_sources,
                consumed=name in consumed,
            )

    # Explicit financial prose is assessed separately from metadata and citations.
    for index, body in parsed.items():
        prose = body.get("message")
        if index != final_index and any(
            key in body for key in ("answer", "value", "unit", "sources", "result_id")
        ):
            add_claim(
                "DERIVED_FROM_SOURCES",
                f"response[{index}] non-Final publication fields",
                "These are actual additional publication/provenance claims with the correct six-million change, endpoint sources and real result reference. Their presence without a final key is a legal message turn, not an actual Final and not a retraction of earlier claims.",
                [evidence(index)],
                source_evidence("q11"),
            )
        if not prose:
            continue
        if family == "D_plus_executed_ending_balance_check" and index == 1:
            add_claim(
                "DIRECT_SOURCE_VALUE",
                "response[1].message four rollforward input facts",
                "The stated beginning balance 4, charges 4, acquired obligations 7 and cash outlays 5 are correct 2005-end/2006 source facts. Only these four inputs are covered here; the wrong predicted ending value 6 is a separate derived claim below.",
                [evidence(index)],
                source_evidence("q11", "q12", "q13", "q14"),
            )
            add_claim(
                "DERIVED_FROM_SOURCES",
                "response[1].message predicted ending reserve $6M",
                "The predicted ending balance of $6M is wrong. The actual expression yields $10M. The later actual Final explicitly restates this same rollforward as $10M ending reserve, replacing the previous wrong derived value. The original error is retained, not erased merely because execution succeeded.",
                [evidence(index, "ending reserve $6M... computing: 4 + 4 + 7 − 5.")],
                source_evidence("q11", "q12", "q13", "q14"),
                truth=False,
                current=False,
                withdrawal=[
                    evidence(
                        final_index,
                        "beginning reserve $4M + pretax warranty charges $4M + assumed acquisition warranty obligations $7M − cash outlays $5M = $10M ending reserve.",
                    )
                ],
            )
        else:
            keys = (
                ("q11", "q12", "q13", "q14")
                if family == "R_cancel_beginning"
                or (family == "D_message_rollforward" and index == 1)
                else ("q11",)
            )
            if (review_id, index) != ("dr_review_025", 1):
                add_claim(
                    "DIRECT_SOURCE_VALUE",
                    f"response[{index}].message stated input facts",
                    "The individually read prose directly states correct warranty reserve or movement amounts with their correct periods. This direct factual assertion is separate from the derived relationship and from any incorrect metadata links in case 005.",
                    [evidence(index)],
                    source_evidence(*keys),
                )
            add_claim(
                "DERIVED_FROM_SOURCES",
                f"response[{index}].message financial relationship and stated amounts",
                "The individually read public explanation states the correct warranty reserve facts and/or the supported relationship using those facts. This is supported financial derivation, not a claim that every source cell equals its conclusion.",
                [evidence(index)],
                source_evidence(*keys),
            )

    if final_index is not None:
        if review_id not in NO_ENDPOINT_FACTS_IN_FINAL:
            add_claim(
                "DIRECT_SOURCE_VALUE",
                "actual Final stated endpoint facts",
                "The actual Final's answer, calculation or explanation states the correct 2005-end reserve of 4 and 2006-end reserve of 10 million dollars. These factual endpoint amounts are distinct from the derived increase of 6 and from the separately assessed source-list provenance.",
                final_evidence,
                source_evidence("q11"),
            )
        add_claim(
            "DERIVED_FROM_SOURCES",
            "actual Final stated derived answer and interpretable provenance",
            (
                "The Final calculation explicitly states the correct monetary endpoint difference. Its repeated date-token source list is assessed separately as unresolved citation semantics; it is not silently repaired into the correct numeric operand links, and it does not retract the two known false nested input assertions."
            )
            if bad_sources
            else (
                "The actual Final identifies the requested change and its supporting quantities. "
                "Endpoint citations support the derived difference, not a false direct equality "
                "to six. An additional tool:1 citation in case 032 is the actual successful "
                "result, not a required numeric-catalog ID. In old 01 the endpoint explanation "
                "corroborates the value without changing the actually executed R support."
            ),
            final_evidence,
            source_evidence("q11"),
            truth=True,
        )
        if bad_sources:
            add_claim(
                "UNRESOLVED",
                "actual Final.sources repeated q11n0/q11n1 date occurrences",
                "The unstructured Final list repeats the earlier incorrectly bound date occurrences. Unlike the explicit nested input objects, it does not uniquely say whether it is citing numeric operands or the containing warranty-note/date context. Keep that role unresolved rather than imposing a numeric-ID-only citation gate. The earlier two current direct source-value assertions are independently false and sufficient for source failure.",
                final_evidence,
                source_evidence("q11"),
                truth=None,
            )
        body = parsed[final_index]
        if any(key in body for key in ("sources", "answer", "value", "unit", "result_id")):
            add_claim(
                "DERIVED_FROM_SOURCES",
                "top-level published fields outside actual Final",
                "These additional public fields consistently describe the correct derived change and source/result provenance. They remain claims but are not used to complete a missing or ambiguous actual Final value, unit or result_id.",
                [evidence(final_index)],
                source_evidence("q11"),
            )
        if family in {"D_prose_rollforward", "D_plus_executed_ending_balance_check"}:
            add_claim(
                "DIRECT_SOURCE_VALUE",
                "actual Final.explanation stated movement inputs",
                "The Final explanation directly states correct beginning balance 4, 2006 charges 4, 2006 cash outlays 5 and assumed obligations 7. They are separate source facts, not a claim that the net change is recorded in any one of those source occurrences.",
                final_evidence,
                source_evidence("q11", "q12", "q13", "q14"),
            )
            add_claim(
                "DERIVED_FROM_SOURCES",
                "actual Final.explanation complete rollforward",
                "The Final correctly relates beginning balance, pretax charges, assumed obligations and cash outlays to the ten-million ending balance. This statement is supported, but prose alone is not an executed R; the separately executed check in case 028 returns the ending balance, not the requested net change.",
                final_evidence,
                source_evidence("q11", "q12", "q13", "q14"),
            )
    reviewed["source_claims"] = claims

    mentioned = family in {
        "R_cancel_beginning",
        "D_prose_rollforward",
        "D_message_rollforward",
        "D_plus_executed_ending_balance_check",
    }
    mention_index = (
        0
        if family == "R_cancel_beginning"
        else 1
        if family in {"D_message_rollforward", "D_plus_executed_ending_balance_check"}
        else final_index
    )
    reviewed["R_mention"] = item(
        "CONFIRMED" if mentioned else "NOT_OBSERVED",
        "Specific period-movement/rollforward relationship is publicly stated; this mention is not itself registered net-change execution."
        if mentioned
        else "No specific period-component relation is stated in the observed public responses; the fixed E instruction is not model evidence.",
        [evidence(mention_index)] if mentioned else [evidence(answer_index)],
    )
    reviewed["R_Final_link"] = item(
        "CONFIRMED" if family == "R_cancel_beginning" else "NOT_OBSERVED",
        "Actual Final explicitly cites the real R-supporting tool:1 calculation."
        if family == "R_cancel_beginning"
        else "There is no actual registered R-net-change result in the delivered Final dependency chain; a balance check or prose corroboration is not that result.",
        final_evidence,
    )

    mapping = {"occurrences": {}, "event_annotations": [], "revisions": [], "cross_checks": []}
    for event in events:
        index = event["response_index"]
        call = event["tool_call"]
        role = "final_publication" if event["final"] else "public_explanation"
        if call:
            role = "format_error" if call["output"]["status"] != "ok" else "answer_calculation"
            if family == "D_plus_executed_ending_balance_check" and index == 1:
                role = "independent_ending_balance_check"
        mapping["event_annotations"].append(
            {
                "response_index": index,
                "role": role,
                "interpretation": f"Actual {role}; all original public bytes are retained. Not a fabricated Action or model-independent reasoning trace.",
                "evidence": [evidence(index)],
            }
        )
    if family == "D_format_recovery":
        mapping["revisions"].append(
            {
                "before_index": 0,
                "after_index": 1,
                "change_kind": "format_only",
                "semantic_key": None,
                "interpretation": "Only digit-initial invalid variable identifiers are renamed. The financial object, periods, values, sources, sign and units do not change.",
                "evidence": [evidence(0), evidence(1)],
            }
        )
    if family == "D_plus_executed_ending_balance_check":
        mapping["revisions"].append(
            {
                "before_index": 1,
                "after_index": 2,
                "change_kind": "substantive",
                "semantic_key": {
                    "quantity": "predicted_ending_warranty_balance",
                    "before_USD_million": "6",
                    "after_USD_million": "10",
                },
                "interpretation": "The wrong public prediction of the ending balance is substantively corrected in the actual Final, following the executed ten-million balance result. It is not treated as a mere spelling change.",
                "evidence": [evidence(1), *final_evidence],
            }
        )
        mapping["cross_checks"].append(
            {
                "call_id": "tool:2",
                "interpretation": "An actual independent ending-balance cross-check explicitly called a Cross-check and later corroboration. It returns 10, whereas the requested net-change answer is 6. Preserve it even though the frozen same-answer-only full-class mapper cannot certify this check shape; do not relabel as an irrelevant auxiliary calculation or a pure R answer.",
                "evidence": [evidence(1), *final_evidence],
            }
        )

    for event in successful:
        index, call = event["response_index"], event["tool_call"]
        args = call["arguments"]
        original_expression = args["expression"]
        tree = ast.parse(original_expression, mode="eval").body
        occurrences = {}

        def visit(node, address):
            if isinstance(node, ast.BinOp):
                require(
                    isinstance(node.op, (ast.Add, ast.Sub)), "transcription.read_operator_domain"
                )
                visit(node.left, address + ".left")
                visit(node.right, address + ".right")
                return
            if isinstance(node, ast.Name):
                value = args["variables"][node.id]
                sid = value["source"] if isinstance(value, dict) else args["sources"][node.id]
                pointer = (
                    ["variables", node.id, "source"]
                    if isinstance(value, dict)
                    else ["sources", node.id]
                )
                attribution = "model_declaration"
            else:
                require(
                    isinstance(node, ast.Constant) and original_expression == "10 - 4",
                    "transcription.only_read_literal_difference",
                )
                require(address in {"body.left", "body.right"}, "transcription.literal_occurrence")
                # Fixed source roles from this individual's read public argument
                # context, not a search for a catalog entry with the same number.
                sid = {"body.left": "source:q11n3", "body.right": "source:q11n4"}[address]
                pointer = None
                attribution = "reviewer_interpretation"
            role, period, _ = SOURCE_ROLES[sid]
            occurrences[address] = {
                "kind": "source",
                "source_id": sid,
                "role": role,
                "period": period,
                "unit": "USD_million"
                if sid not in {"source:q11n0", "source:q11n1"}
                else "date token; model's money association is false",
                "attribution": attribution,
                "declaration_pointer": pointer,
                "evidence": [evidence(index)],
                "reason": "Actual named declaration or explicitly reviewed literal/period context. No equal-value source search, ID repair or target identity expansion.",
            }

        visit(tree, "body")
        mapping["occurrences"][call["id"]] = occurrences
        per_call_text = (
            "A valid endpoint subtraction for the original public task, with source roles "
            "and units stated before/same call."
        )
        if family == "R_cancel_beginning":
            per_call_text = "The actual movement calculation, with the same beginning-balance occurrence cancelling, gives the requested net reserve change."
        if family == "D_plus_executed_ending_balance_check" and index == 1:
            per_call_text = "The actual rollforward expression validly computes ENDING BALANCE 10, not net CHANGE 6. Its public predicted ending value 6 is wrong and separately retained as corrected only at Final; this per-call relationship flag does not certify that earlier predicted number."
        reviewed["call_semantics"][call["id"]] = {
            "formula_applicability": item("PASS", per_call_text, [evidence(index)]),
            "variable_correspondence": item(
                "FAIL" if bad_sources else "PASS",
                reviewed["variable_correspondence"]["explanation"],
                [evidence(index)],
            ),
            "unit_handling": item(
                "PASS",
                "All executed money amounts use the stated USD-million scale; source correspondence is evaluated separately.",
                [evidence(index)],
            ),
        }
    reviewed["mapping"] = mapping
    verify_quotes(reviewed, raw)
    verify_extra_evidence(reviewed, raw, audit)
    semantic_binding(reviewed, raw, public, final_index)
    claim_certification(reviewed, raw, public)
    return reviewed


def main():
    root = Path("/data1/zhuxinrui/projects/Data-Synthesis")
    history_guard(root)
    verify_preparation(root)
    output = root / OUTPUT
    manifest(output / "assessment")
    report = read_json(output / "assessment/report.json")
    blank = read_json(output / "assessment/review_template.json")
    require(
        set(CASES) == set(blank) and len(CASES) == 40, "transcription.exact_read_case_population"
    )
    reviews = {}
    for audit in report["rows"]:
        rid = audit["review_id"]
        packet = read_json(output / f"assessment/packets/{rid}.json")
        reviews[rid] = transcribe(packet, audit, blank[rid])
    store = Store(output / "manual_reviews")
    store.json("reviews.json", reviews)
    receipt = record(
        "DR_manual_transcription",
        manually_read_cases=40,
        manually_reviewed_registry=CASES,
        all_original_packet_references=[
            reference(root, OUTPUT + f"/assessment/packets/{rid}.json") for rid in CASES
        ],
        source_claim_occurrences=sum(len(r["source_claims"]) for r in reviews.values()),
        new_model_calls=0,
        new_tokenizer_calls=0,
        historical_original_files_changed=False,
        reviewer="executing assistant; not independent or guaranteed blind",
        numeric_identity_checks_are_not_semantic_judgment_automation=True,
        formal_qualifier_and_projection_not_run_by_this_transcription=True,
        builder_reference=reference(root, Path(__file__).relative_to(root)),
    )
    store.json("report.json", receipt)
    store.seal(report_id=receipt["id"])
    print(receipt["id"], flush=True)


if __name__ == "__main__":
    main()
