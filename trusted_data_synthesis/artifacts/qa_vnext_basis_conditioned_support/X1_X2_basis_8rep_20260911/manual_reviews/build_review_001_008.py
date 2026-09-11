"""Serialize manually reviewed cases 001--008 and validate only offline evidence.

All case decisions and source-occurrence choices below were made after reading
the complete original public transcripts/events/calculations and both complete
public source documents. This script copies exact quotations and applies frozen
validators; it does not assign judgments from requested guidance, numeric search,
support quotas, or classifier output. It writes only this review's three files.
"""

import copy
import json
import re
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.core import (
    verify_preparation,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.methods import (
    classify_method,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    OUTPUT,
    encode,
    read_json,
    require,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.projection import (
    project_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.review import qualify
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.source import bind
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)


ROOT = Path(__file__).resolve().parents[5]
STUDY = ROOT / OUTPUT
OUT = Path(__file__).resolve().parent

# These are explicit manual semantic assignments, not inferred from equal values.
FACTS = {
    "source:t4c1n0": ("net revenue, Entergy Mississippi-defined gross margin", "fiscal 2003", ("p3", "p4", "t4c0", "t4c1", "t0c1")),
    "source:t1c1n0": ("net revenue, Entergy Mississippi-defined gross margin", "fiscal 2002", ("p3", "p4", "t1c0", "t1c1", "t0c1")),
    "source:t2c1n0": ("base-rate contribution to net revenue change", "2003 compared with 2002", ("p4", "q0", "t2c0", "t2c1", "t0c1")),
    "source:t3c1n0": ("other contribution to net revenue change", "2003 compared with 2002", ("p4", "t3c0", "t3c1", "t0c1")),
    "source:q11n3": ("reserve for product warranties", "December 31, 2006", ("q9", "q10", "q11")),
    "source:q11n4": ("reserve for product warranties", "December 31, 2005", ("q9", "q10", "q11")),
    "source:q12n3": ("pretax warranty charges against income", "fiscal 2006", ("q9", "q12")),
    "source:q13n0": ("cash outlays for product warranties", "fiscal 2006", ("q9", "q13")),
    "source:q14n0": ("warranty obligations assumed in business acquisitions", "fiscal 2006", ("q9", "q14")),
}

CASES = {
    1: {
        "task": "X1", "expression": "426.6 - 380.2", "actual_method": "endpoint", "literal": True,
        "operands": [("body.left", "net_revenue_2003", "source:t4c1n0"), ("body.right", "net_revenue_2002", "source:t1c1n0")],
        "formula": "The actual subtraction compares 2003 and 2002 company-defined net revenue (gross margin), exactly the public question's annual comparison; it is not net income or a stock reserve roll-forward.",
        "context_facts": ["source:t2c1n0", "source:t3c1n0"],
        "context_text_field": "explanation",
        "mention": True,
        "note": "One actual endpoint calculation. Final mentions base rates +48.3 and other -1.9, but no movement or cross-check tool calculation occurred. The unused named metadata remain direct source assertions and are checked as such.",
    },
    2: {
        "task": "X2", "expression": "charges - cash_outlays + assumed_obligations", "actual_method": "movement", "literal": False,
        "operands": [("body.left.left", "charges", "source:q12n3"), ("body.left.right", "cash_outlays", "source:q13n0"), ("body.right", "assumed_obligations", "source:q14n0")],
        "formula": "The actual 2006 warranty-reserve change is pretax warranty charges minus cash outlays plus obligations assumed in acquisitions. The amounts, signs and fiscal 2006 roles are supported by q9 and q12--q14.",
        "context_facts": ["source:q11n4", "source:q11n3"],
        "context_text_field": "answer",
        "ambiguous_citations": ["source:q11n2", "source:q11n3"],
        "mention": True,
        "note": "Main tool inputs are the correct 2006 components. Final.sources includes q11n2 (the year 2005) and q11n3 (10); the unstructured list does not establish whether these are period/context citations or intended direct balance sources. Preserve UNRESOLVED claim role, not a fabricated 4->2005 failure and not automatic PASS. Actual movement feature remains known; complete financial/delivery qualification is UNDETERMINED.",
    },
    3: {
        "task": "X2", "expression": "reserve_2006 - reserve_2005", "actual_method": "endpoint", "literal": False,
        "operands": [("body.left", "reserve_2006", "source:q11n3"), ("body.right", "reserve_2005", "source:q11n4")],
        "formula": "The actual subtraction is the December 31, 2006 product-warranty reserve minus the December 31, 2005 product-warranty reserve, exactly the public comparison.",
        "context_facts": [], "mention": False,
        "note": "One actual endpoint calculation with correct q11n3/q11n4 amounts, periods and explicit Final tool:1 link. No executed or stated movement alternative and no revisions.",
    },
    4: {
        "task": "X2", "expression": "4 + 7 - 5", "actual_method": "movement", "literal": True,
        "operands": [("body.left.left", "pretax_warranty_charges_2006", "source:q12n3"), ("body.left.right", "warranty_obligations_assumed_2006", "source:q14n0"), ("body.right", "cash_outlays_2006", "source:q13n0")],
        "formula": "The executed literal calculation is the 2006 charges plus acquired warranty obligations minus cash outlays, giving the net change. The same message distinguishes the beginning reserve from the 2006 pretax-charge operand; metadata explicitly names the latter and q12n3.",
        "context_facts": ["source:q11n4"], "context_index": 0,
        "general_citations": ["source:q11n3", "source:q11n4"],
        "mention": True,
        "note": "Literal 4+7-5 executes the requested net change. The four-million opening balance mentioned in prose is context, not a fourth executed operand; the consumed first literal is tied to fiscal-2006 charges by explicit same-response semantics/source metadata. No ending-balance rebuild or extra verification was executed.",
    },
    5: {
        "task": "X1", "expression": "rev2003 - rev2002", "actual_method": "endpoint", "literal": False,
        "operands": [("body.left", "rev2003", "source:t4c1n0"), ("body.right", "rev2002", "source:t1c1n0")],
        "formula": "The executed annual net-revenue comparison is 2003 minus 2002, using the disclosed company-defined gross-margin endpoints in the same USD-million scale.",
        "context_facts": ["source:t2c1n0", "source:t3c1n0"], "context_text_field": "calculation",
        "mention": True,
        "note": "The Final additionally writes base-rates +48.3 and other -1.9 = +46.4 as a consistency statement. That statement is retained but no second tool result exists; it does not change the actual endpoint main support into movement or create an executed cross-check.",
    },
    6: {
        "task": "X2", "expression": "10 - 4", "actual_method": "endpoint", "literal": True,
        "operands": [("body.left", "reserve_2006", "source:q11n3"), ("body.right", "reserve_2005", "source:q11n4")],
        "formula": "The actual literal subtraction takes the 2006 warranty reserve less the 2005 reserve, with the two original amounts and years expressly stated before execution.",
        "context_facts": [], "mention": False, "final_index": 2,
        "note": "Response 1 is a legal independent public JSON message with answer/value/result_id but no final key; the event has protocol_error=null and no tool. Response 2 supplies the terminal Final. This is not a protocol error or a substantive financial revision, and response 1 remains a positive original public-message target.",
    },
    7: {
        "task": "X2", "expression": "charges_2006 + acquisitions_2006 - cash_outlays_2006", "actual_method": "movement", "literal": False,
        "operands": [("body.left.left", "charges_2006", "source:q12n3"), ("body.left.right", "acquisitions_2006", "source:q14n0"), ("body.right", "cash_outlays_2006", "source:q13n0")],
        "formula": "The executed 2006 reserve movement adds fiscal-2006 charges and assumed acquisition obligations and subtracts fiscal-2006 cash outlays. The opening reserve mentioned in context is not an executed additional operand.",
        "context_facts": ["source:q11n4", "source:q11n3"], "context_text_field": "answer",
        "ambiguous_citations": ["source:q11n0", "source:q11n1", "source:q11n2"],
        "mention": True,
        "note": "The primary variables and source IDs are correct, and the Final's numerical/period narrative is correct. Its sources list instead cites q11n0/n1/n2 (31/2006/2005) for the reserve paragraph. Calendar/context reference versus intended balance provenance is not uniquely established. Keep UNRESOLVED role without inventing a direct false amount binding or silently forgiving it because the primary answer is correct.",
    },
    8: {
        "task": "X2", "expression": "charges_2006 - cash_outlays_2006 + assumed_obligations_2006", "actual_method": "movement", "literal": False,
        "operands": [("body.left.left", "charges_2006", "source:q12n3"), ("body.left.right", "cash_outlays_2006", "source:q13n0"), ("body.right", "assumed_obligations_2006", "source:q14n0")],
        "formula": "The actual requested reserve movement is fiscal-2006 charges minus cash outlays plus assumed warranty obligations from acquisitions. Its actual tool:1 result is the Final's principal support.",
        "context_facts": ["source:q11n4", "source:q11n3"], "context_text_field": "answer",
        "general_citations": ["source:q11n3", "source:q11n4"],
        "mention": True,
        "note": "The model says the endpoint balances are a consistency check, but there is only one actual tool calculation and it is the movement calculation. Preserve the actual prose and endpoint-context citations; do not add an endpoint execution, an ending-balance rebuild, or a second independent measurement.",
    },
}


def make_review(number, packet, template):
    case = CASES[number]
    review = copy.deepcopy(template)
    raw = {int(index): value for index, value in packet["raw_messages"].items()}
    parsed = {index: json.loads(value) for index, value in raw.items()}
    final_index = case.get("final_index", 1)
    final = packet["raw_final"]
    public = packet["public_document"]
    catalog = {fact["id"]: fact for fact in public["numeric_catalog"]}
    require(packet["first_final_index"] == final_index and final["result_id"] == "tool:1", "review.manual_actual_Final")
    require(len(packet["calculations"]) == 1 and packet["calculations"][0]["original_expression"] == case["expression"], "review.manual_actual_single_calculation")
    require(all(event["protocol_error"] is None for event in packet["events"]), "review.manual_no_protocol_error")

    def quote(index, text):
        require(text and text in raw[index], "review.exact_original_quote_before_serialization")
        return {"response_index": index, "quote": text}

    def sources(source_ids):
        segments = []
        for source_id in source_ids:
            for segment_id in FACTS[source_id][2]:
                if segment_id not in segments:
                    segments.append(segment_id)
        return [{"segment_id": sid, "quote": public["segments"][sid]["text"]} for sid in segments]

    message = quote(0, parsed[0]["message"])
    publication = quote(final_index, final["answer"])
    link = quote(final_index, '"result_id"' + (': ' if ': "tool:1"' in raw[final_index] else ':') + '"tool:1"')
    monetary_source_ids = [item[2] for item in case["operands"]]
    correspondence = (
        "The actual expression consumes numeric literals; resolved_variables is empty. The unused named value/source/unit objects and arguments.sources are preserved declarations, not consumed variable bindings. Same-response financial language and explicit source pointers establish each literal's intended role without equal-value search."
        if case["literal"] else
        "Each actual named operand is resolved from its own original value/source/unit object. The cited source role and comparison period match the actual operand; no same-valued source from a different year is substituted."
    )
    for field, explanation in (
        ("formula_applicability", case["formula"]),
        ("variable_correspondence", correspondence),
        ("unit_handling", "Every amount is in source-stated millions of dollars and the same-response metadata says USD_million. The shared public USD contract supplies currency consistently; there is no scaling or currency conversion."),
    ):
        review[field] = {"status": "PASS", "evidence": [message], "explanation": explanation}
    review["publication_alignment"] = {
        "status": "PASS", "evidence": [publication, link],
        "explanation": "The actual terminal Final explicitly links tool:1 and publishes its executed net change in USD_million with the correct public object, period and increase direction. Citation-role uncertainty, where present, is separately retained in current_source_claim_certification.",
    }
    review["final_answer_consistency"] = {
        "status": "PASS", "evidence": [publication],
        "explanation": "The actual Final numeric value, USD-million unit, narrative amount, comparison years and direction agree. No sibling field, previous message or private reference was used to replace the extracted Final quantity.",
    }
    review["answer_calculation_id"] = "tool:1"
    review["answer_calculation_unit"] = "USD_million"
    review["planning_observations"] = {"text": case["note"], "evidence": [message, publication]}
    review["call_semantics"] = {
        "tool:1": {field: copy.deepcopy(review[field]) for field in ("formula_applicability", "variable_correspondence", "unit_handling")}
    }
    if case["actual_method"] == "movement":
        mention_evidence = [message]
        review["R_Final_link"] = {
            "status": "CONFIRMED", "evidence": [publication, link],
            "explanation": "The actual movement calculation is tool:1 and the terminal Final explicitly references it; this observation does not certify the separate overall qualification or complete class.",
        }
    else:
        mention_evidence = [quote(final_index, final[case["context_text_field"]])] if case["mention"] else []
        review["R_Final_link"] = {
            "status": "NOT_OBSERVED", "evidence": [link],
            "explanation": "Final links the only actual endpoint calculation. Any component consistency text is retained as prose, not an executed movement result or a second actual support chain.",
        }
    review["R_mention"] = {
        "status": "CONFIRMED" if case["mention"] else "NOT_OBSERVED",
        "evidence": mention_evidence,
        "explanation": "Actual public component relationship is present." if case["mention"] else "Complete public history contains no period-component relationship proposal.",
    }
    anchors = ("p0", "p3", "p4", "t1c0", "t1c1", "t4c0", "t4c1", "t0c1") if case["task"] == "X1" else ("q9", "q10", "q11", "q12", "q13", "q14")
    review["target_binding"] = {
        "parameters": {key: "PASS" for key in ("local_relation", "public_scope_match", "registered_scope_match", "final_chain_completes_public_target")},
        "evidence": [message, publication, link],
        "source_evidence": [{"segment_id": sid, "quote": public["segments"][sid]["text"]} for sid in anchors],
        "explanation": case["formula"] + " The public question and these original source passages establish the object and comparison; private reference equality is not the source of scope.",
    }

    claims, occurrences = [], {}
    for address, variable, source_id in case["operands"]:
        block = re.search(r'"' + re.escape(variable) + r'"\s*:\s*\{[^{}]*\}', raw[0])
        require(block is not None, "review.original_variable_declaration_quote")
        declaration = quote(0, block.group(0))
        role, period, _ = FACTS[source_id]
        claims.append({
            "location": f"response 0 arguments.variables.{variable}, matching arguments.sources when present, and the accompanying financial message",
            "parameters": {"role": "DIRECT_SOURCE_VALUE", "current": True, "source_value_equal": True, "consumed": not case["literal"]},
            "evidence": [declaration, message], "source_evidence": sources([source_id]),
            "source_id": source_id, "source_exact": catalog[source_id]["value"],
            "explanation": f"The explicit nested declaration supplies the correct original {role}, {period}, in USD millions. " + ("Its variable name is not consumed by the literal AST; nonconsumption does not erase this current assertion, which was independently checked." if case["literal"] else "This named operand was actually resolved by the tool."),
        })
        occurrences[address] = {
            "kind": "source", "source_id": source_id, "scale": "1",
            "role": role, "period": period, "unit": "USD_million",
            "attribution": "model_declaration", "declaration_pointer": ["variables", variable, "source"],
            "evidence": [message, declaration],
            "reason": "Original same-response financial semantics plus the exact model source declaration bind this particular AST occurrence; no numeric-source search or rewritten execution.",
        }

    # Final narratives repeat directly disclosed amounts as contextual facts.
    # They are distinct from the reported net change, which is derived below.
    final_fact_ids = list(dict.fromkeys(monetary_source_ids + case["context_facts"]))
    final_text = final.get(case.get("context_text_field", "answer"), final["answer"])
    context_index = case.get("context_index", final_index)
    fact_evidence = [publication]
    if context_index == 0:
        fact_evidence.append(message)
    if final_text != final["answer"]:
        fact_evidence.append(quote(final_index, final_text))
    claims.append({
        "location": "Public financial amount/period statements in the pre-calculation message and Final explanation/answer (separate from the derived change)",
        "parameters": {"role": "DIRECT_SOURCE_VALUE", "current": True, "source_value_equal": True, "consumed": False},
        "evidence": [message, *fact_evidence], "source_evidence": sources(final_fact_ids),
        "explanation": "The directly stated input and contextual amounts agree with the original named source roles and years. In X1 the other item is the signed -1.9 contribution; no second positive catalog ID is invented. In X2 opening/closing balances are distinguished from fiscal-2006 movements. This does not resolve a separate ambiguous citation list or certify a second executed calculation.",
    })
    claims.append({
        "location": "Actual Final.value/answer and Final.result_id",
        "parameters": {"role": "DERIVED_FROM_SOURCES", "current": True, "derivation_supported": True, "consumed": False},
        "evidence": [publication, link], "source_evidence": sources(monetary_source_ids),
        "explanation": "The published net change is the actual successful tool:1 arithmetic result from the declared sources, not a claim that the derived answer itself appears at a single source numeric ID.",
    })
    ordinary = set(monetary_source_ids)
    cited = final["sources"]
    for source_id in cited:
        if source_id not in ordinary:
            continue
        claims.append({
            "location": f"Final.sources reference {source_id}",
            "parameters": {"role": "DERIVED_FROM_SOURCES", "current": True, "derivation_supported": True, "consumed": False},
            "evidence": [quote(final_index, source_id), publication, link],
            "source_evidence": sources([source_id]),
            "explanation": "This source is already tied to a main-calculation operand by explicit earlier metadata and financial prose; the actual Final result_id links that executed derivation. It is not interpreted as the source's literal value equaling the final net change.",
        })
    for source_id in case.get("general_citations", []):
        require(source_id in cited, "review.observed_general_citation")
        claims.append({
            "location": f"Final.sources contextual reference {source_id}",
            "parameters": {"role": "GENERAL_REFERENCE", "current": True, "reference_relevant": True, "consumed": False},
            "evidence": [quote(final_index, source_id), publication],
            "source_evidence": sources([source_id]),
            "explanation": "The q11 warranty-reserve endpoint context is relevant to the requested comparison and agrees with the model's balance narrative. The explicitly executed main calculation remains the movement relation; no extra endpoint execution is inferred from the citation.",
        })
    if case.get("ambiguous_citations"):
        require(all(sid in cited for sid in case["ambiguous_citations"]), "review.observed_ambiguous_citations")
        claims.append({
            "location": "Actual Final.sources unstructured q11 citation subset: " + ", ".join(case["ambiguous_citations"]),
            "parameters": {"role": "UNRESOLVED", "current": True, "consumed": False},
            "evidence": [quote(final_index, sid) for sid in case["ambiguous_citations"]] + [publication],
            "source_evidence": [{"segment_id": "q11", "quote": public["segments"]["q11"]["text"]}],
            "explanation": case["note"] + " The public contract does not supply a positional value-to-ID interpretation for this Final list. No later actual withdrawal or clarification exists, so it stays current and unresolved.",
        })
    if number == 6:
        claims.append({
            "location": "Response 1 independent public message answer/value/result_id/sources",
            "parameters": {"role": "DERIVED_FROM_SOURCES", "current": True, "derivation_supported": True, "consumed": False},
            "evidence": [quote(1, raw[1])], "source_evidence": sources(monetary_source_ids),
            "explanation": "This legal non-Final public message reports the same actual tool:1 endpoint result and correct source IDs. It remains part of the original history and is not relabeled as a failed response or withdrawn claim merely because Final packaging follows.",
        })
    review["source_claims"] = claims
    review["claim_inventory"] = {
        "complete": True, "reviewed_response_indices": sorted(raw),
        "explanation": "The executing-assistant reviewer read every original public response, event and actual calculation and the complete public source context. Inventory includes each nested value/source/unit declaration (including unused literal-call metadata), matching arguments.sources, stated financial facts, derived reported change and every Final citation. Date/source-role ambiguities are separately retained; no correct Final is used to cancel earlier assertions, and no actual withdrawal was found.",
    }
    annotations = []
    for index in sorted(raw):
        if index == 0:
            role = "main_answer_calculation"
            interpretation = case["formula"] + " " + correspondence
            evidence = [message]
        elif index == final_index:
            role = "terminal_publication"
            interpretation = case["note"]
            evidence = [publication, link]
        else:
            role = "independent_public_message"
            interpretation = case["note"]
            evidence = [quote(index, raw[index])]
        annotations.append({"response_index": index, "role": role, "interpretation": interpretation, "evidence": evidence})
    review["mapping"] = {"occurrences": {"tool:1": occurrences}, "event_annotations": annotations, "revisions": [], "cross_checks": []}
    review["offline_review_scope"] = "Executing assistant team; not an independent or guaranteed blinded reviewer. Only original evidence and frozen validators; no Provider, Student, GPU, tokenizer, selection, or training."
    return review


def main():
    output_paths = [OUT / ("review_001_008" + suffix) for suffix in (".json", ".validation.json", ".notes.md")]
    require(all(not path.exists() for path in output_paths), "review.own_outputs_write_once")
    verify_preparation(ROOT)
    templates = read_json(STUDY / "assessment/review_template.json")
    audits = {row["review_id"]: row for row in read_json(STUDY / "assessment/report.json")["rows"]}
    prototypes = read_json(STUDY / "preparation/private/target_class_prototypes.json")
    ledgers = read_json(STUDY / "preparation/target_ledgers.json")
    cross = read_json(STUDY / "preparation/private/x2_cross_quantity_context.json")
    reviews, validations, read_sources = {}, [], {}
    with execution_guard(online=False) as counts:
        for number, case in CASES.items():
            review_id = f"basis_review_{number:03d}"
            packet_path = STUDY / f"assessment/packets/{review_id}.json"
            packet = read_json(packet_path)
            key = case["task"]
            original_public = read_json(STUDY / f"preparation/public/{key}.json")
            require(packet["public_document"] == original_public, "review.same_complete_public_source")
            read_sources[key] = original_public["id"]
            review = make_review(number, packet, templates[review_id])
            raw = {int(index): value for index, value in packet["raw_messages"].items()}
            audit = audits[review_id]
            qualified = qualify(audit, review, raw, packet["public_document"])
            session = bind(ROOT, qualified)
            goal = ledgers[key]["registered_goal_scope"]
            projection = project_session(session, review["mapping"], goal, condition_id=audit["condition_id"], cross_quantity_context=cross if key == "X2" else None) if qualified["formula_driven_trace_verified"] else None
            method = classify_method(session, review["mapping"], goal, prototypes[key], audit["condition_id"], projection=projection)
            expected_status = "UNDETERMINED" if case.get("ambiguous_citations") else "PASS"
            require(qualified["trace_status"] == expected_status, "review.frozen_validator_vs_manual_financial_judgment")
            require(method["method_stratum"] == case["actual_method"], "review.actual_source_method_matches_reviewed_expression")
            require(projection is None or projection["status"] == "MAPPED", "review.complete_valid_projection")
            reviews[review_id] = review
            validations.append({
                "review_id": review_id, "packet_sha256": sha(packet_path.read_bytes()),
                "task_key": key, "trace_status": qualified["trace_status"],
                "financial_delivery_valid": qualified["formula_driven_trace_verified"],
                "quantity": qualified["answer"]["V_quantity"],
                "source_claim_status": qualified["current_source_claim_certification"]["status"],
                "actual_method": method["method_stratum"], "full_mapping_status": method["full_mapping_status"],
                "projection_reason": projection["reason"] if projection else "No complete projection admitted: original qualification unresolved.",
                "qualification_id": qualified["id"], "method_id": method["id"],
                "fine_class_id": method["fine_class_id"], "note": case["note"],
            })
        guards = guard_report(counts, phase="manual_review_001_008_offline_only")
    verify_preparation(ROOT)
    validation = {"reviewer_scope": "executing assistant team; not independent or guaranteed blinded", "public_sources_read_in_full": read_sources, "rows": validations, "execution_guards": guards, "selection_performed": False, "tokenizer_called": False}
    lines = ["# Offline review of basis_review_001--008", "", "Executing assistant team review, not independent or guaranteed blinded. Complete original public responses/events/calculations were read; both complete public sources were read, and every packet source was checked identical to its original public document. Frozen source/tests/online/assessment/preparation files were not edited. No tokenization, selection, Provider, Student, GPU or training was performed.", "", "The construction script serializes explicit manual case decisions and exact quotations, then checks frozen qualify/bind/project_session/classify_method only. It does not choose judgments from guidance labels or quotas.", ""]
    for row in validations:
        lines.extend([f"- {row['review_id']}: {row['trace_status']}; actual method {row['actual_method']}; full mapping {row['full_mapping_status']}. {row['note']}", ""])
    for path, data in zip(output_paths, (encode(reviews), encode(validation), "\n".join(lines).encode()), strict=True):
        with path.open("xb") as handle:
            handle.write(data)
    print(json.dumps(validations, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
