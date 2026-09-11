"""Serialize eight explicitly reviewed new histories, not a general-purpose grading rule.

The executing assistant fully read packets 025–032 and their source context
before authoring these decisions. This emits an apply_patch for a new review
file, never changes original responses, frozen policy, tools, or extraction.
It neither calls a provider nor loads a tokenizer/Student. Financial judgments
below are manual; loops only copy exact evidence and repeated schema fields.
"""

import json
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    OUTPUT, read_json,
)

BASE = Path(OUTPUT)
ROLES = {
    "source:t4c1n0": ("2003 company-defined net revenue", "fiscal 2003", ["p3", "p4", "t0c1", "t4c0", "t4c1"]),
    "source:t1c1n0": ("2002 company-defined net revenue", "fiscal 2002", ["p3", "p4", "t0c1", "t1c0", "t1c1"]),
    "source:t2c1n0": ("base-rate contribution to annual net-revenue comparison", "2003 versus 2002", ["p3", "p4", "t0c1", "t2c0", "t2c1"]),
    "source:t3c1n0": ("other contribution to annual net-revenue comparison", "2003 versus 2002", ["p3", "p4", "t0c1", "t3c0", "t3c1"]),
    "source:q11n3": ("reserve for product warranties", "December 31, 2006", ["q11"]),
    "source:q11n4": ("reserve for product warranties", "December 31, 2005", ["q11"]),
}
EP1 = {"end_2003": "source:t4c1n0", "end_2002": "source:t1c1n0"}
MV1 = {"base_rates": "source:t2c1n0", "other": "source:t3c1n0"}
DECISIONS = {
    25: {
        "task": "X1", "route": "endpoint", "expression": "end_2003 - end_2002", "index": 0,
        "declared": EP1, "nodes": {"body.left": "end_2003", "body.right": "end_2002"},
        "note": "One actual named-variable endpoint calculation. The final response duplicates fields outside and inside final; the actual final independently contains the same supported value/unit/result_id, so no sibling-field stitching is needed.",
    },
    26: {
        "task": "X1", "route": "movement", "expression": "48.3 + (-1.9)", "index": 0,
        "declared": MV1, "nodes": {"body.left": "base_rates", "body.right": "other"},
        "note": "The actual literal expression consumes +48.3 and signed -1.9. Response 1 and response 2 repeat identical legally recorded answer-only objects without final, then response 3 supplies actual final. These are two real positive public-message targets, not tool calls, protocol failures, independent checks, or substantive revisions. No virtual early Final is inserted.",
    },
    27: {
        "task": "X1", "route": "movement", "expression": "48.3 + (-1.9)", "index": 0,
        "declared": MV1, "nodes": {"body.left": "base_rates", "body.right": "other"},
        "note": "One actual literal component sum. The signed -1.9 is directly the whole unary scalar occurrence, not a newly invented positive source ID. Final states the same decrease magnitude and links tool:1.",
    },
    28: {
        "task": "X1", "route": "movement", "expression": "48.3 + -1.9", "index": 0,
        "declared": MV1, "nodes": {"body.left": "base_rates", "body.right": "other"},
        "note": "One actual literal component sum with a signed right operand. The extra type=json_object metadata does not alter the admitted calculation or actual final. Decrease magnitude in Final is consistent with signed other=-1.9.",
    },
    29: {
        "task": "X1", "route": "endpoint", "expression": "426.6 - 380.2", "index": 0,
        "declared": {"net_revenue_2003": "source:t4c1n0", "net_revenue_2002": "source:t1c1n0"},
        "nodes": {"body.left": "net_revenue_2003", "body.right": "net_revenue_2002"},
        "note": "One actual endpoint subtraction. Final additionally mentions consistency with the +48.3/-1.9 components, but no second tool or component expression was executed. This remains endpoint with a public component mention, not an executed cross-check or a movement main answer.",
    },
    30: {
        "task": "X1", "route": "movement", "expression": "48.3 + (-1.9)", "index": 0,
        "declared": MV1, "nodes": {"body.left": "base_rates", "body.right": "other"},
        "note": "One component sum and actual Final tool:1. The unstructured final sources list additionally cites both correctly identified annual endpoints as comparison context. All are real relevant amounts in the same public bridge; it does not assert that the derived 46.4 is any one cited source literal or establish a second executed basis/check.",
    },
    31: {
        "task": "X2", "route": "endpoint", "expression": "10 - 4", "index": 0,
        "declared": {"2006_reserve": "source:q11n3", "2005_reserve": "source:q11n4"},
        "nodes": {"body.left": "2006_reserve", "body.right": "2005_reserve"},
        "note": "The literal expression 10-4 is the only executed calculation. Digit-leading metadata keys 2006_reserve/2005_reserve are not expression variables and are not consumed; they therefore produce no syntax error. Their direct source-value statements and public prose correctly identify the two reserve balances, not dates or years.",
    },
    32: {
        "task": "X1", "route": "endpoint", "expression": "426.6 - 380.2", "index": 2,
        "declared": {"a": "source:t4c1n0", "b": "source:t1c1n0"},
        "nodes": {"body.left": "a", "body.right": "b"},
        "note": "Responses 0 and 1 contain readable, financially identical endpoint requests followed by DSML closing tags; both fail JSON framing before any calculation. Response 2 removes the trailing framing and actually executes the same literal 426.6-380.2. Renaming unused declaration keys is not a change of financial basis. Preserve both interface errors, all current source claims and two evidenced format-only recoveries; only response 2 and actual Final are positive targets.",
    },
}


def build(number, decision):
    review_id = f"basis_review_{number:03d}"
    packet = read_json(BASE / f"assessment/packets/{review_id}.json")
    raw = {int(k): v for k, v in packet["raw_messages"].items()}
    public, fi, ci = packet["public_document"], packet["first_final_index"], decision["index"]
    audit = next(r for r in read_json(BASE / "assessment/report.json")["rows"] if r["review_id"] == review_id)
    assert audit["task_key"] == decision["task"]
    calls = [event["tool_call"] for event in packet["events"] if event["tool_call"]]
    assert len(calls) == 1 and calls[0]["id"] == "tool:1"
    call = calls[0]
    assert call["arguments"]["expression"] == decision["expression"]
    assert packet["raw_final"]["result_id"] == "tool:1"
    assert all(call["arguments"]["variables"][name]["source"] == sid for name, sid in decision["declared"].items())

    def evidence(*indices):
        return [{"response_index": index, "quote": raw[index]} for index in indices]

    def source_evidence(segments):
        return [{"segment_id": sid, "quote": public["segments"][sid]["text"]} for sid in dict.fromkeys(segments)]

    source_segments = ["q11"] if decision["task"] == "X2" else ["p3", "p4", "t0c1", "t1c0", "t1c1", "t2c0", "t2c1", "t3c0", "t3c1", "t4c0", "t4c1"]
    target_reason = (
        "The original public question asks the change in the product-warranty reserve. Public q11 explicitly binds 10 to December 31, 2006 and 4 to December 31, 2005. The actual calculation subtracts the earlier balance from the later one and Final completes this USD-million change."
        if decision["task"] == "X2" else
        "Public p3/p4 define the company net-revenue gross-margin measure and the 2003-to-2002 comparison. The selected actual calculation uses the disclosed annual endpoints or the base-rate/other variance bridge for that same company, interval and change. The source t0c1 establishes millions; this is not net income or a stock reserve. Actual Final completes this public target without using a private answer to choose its scope."
    )
    formula = {"status": "PASS", "evidence": evidence(ci, fi), "explanation": target_reason}
    correspondence = {
        "status": "PASS", "evidence": evidence(ci),
        "explanation": "Each actual scalar is tied to a named financial item in the contemporaneous public explanation and the explicit nested source declaration, checked against the row/period context. No same-number source search is used. " + decision["note"],
    }
    units = {
        "status": "PASS", "evidence": evidence(ci),
        "explanation": "The public source, pre-execution explanation or declared input units and actual operands consistently use USD millions. Signed decreases remain signed source scalars; no unit/scale transformation or annualization is inserted.",
    }
    review = {
        "published_value": audit["automatic_quantity"]["interpretation"].get("published_value"),
        "published_unit": audit["automatic_quantity"]["interpretation"].get("published_unit"),
        "answer_override_evidence": [], "secondary_answer_values": [],
        "answer_calculation_id": "tool:1", "answer_calculation_unit": "USD_million",
        "formula_applicability": formula, "variable_correspondence": correspondence,
        "unit_handling": units,
        "publication_alignment": {
            "status": "PASS", "evidence": evidence(fi),
            "explanation": "Actual Final itself contains value, USD_million and result_id=tool:1; the same successful prior actual result supports the claimed increase. Top-level sibling fields, earlier message-only publications and offline arithmetic are not used to fabricate a Final.",
        },
        "final_answer_consistency": {
            "status": "PASS", "evidence": evidence(fi),
            "explanation": "Actual Final's principal value, unit, sign, comparison and internal financial explanation are mutually consistent. Additional cited source amounts or decrease magnitudes are not competing answers; no unsupported multi-amount extraction override is made. " + decision["note"],
        },
        "planning_observations": {
            "text": decision["note"], "evidence": evidence(*range(fi + 1)),
        },
        "R_mention": {
            "status": "CONFIRMED" if decision["route"] == "movement" or number == 29 else "NOT_OBSERVED",
            "evidence": evidence(fi if number == 29 else ci) if decision["route"] == "movement" or number == 29 else [],
            "explanation": "Components are publicly mentioned; this field never certifies execution or method." if decision["route"] == "movement" or number == 29 else "No public component-method statement was observed in these complete messages.",
        },
        "R_Final_link": {
            "status": "CONFIRMED" if decision["route"] == "movement" else "NOT_OBSERVED",
            "evidence": evidence(fi) if decision["route"] == "movement" else [],
            "explanation": "The actual Final tool:1 refers to the actually executed component calculation." if decision["route"] == "movement" else "The sole actual Final support is endpoint; a component mention, if any, is not an executed principal or check.",
        },
        "call_semantics": {"tool:1": {
            "formula_applicability": {**formula, "evidence": evidence(ci)},
            "variable_correspondence": correspondence, "unit_handling": units,
        }},
        "mapping": {"occurrences": {"tool:1": {}}, "event_annotations": [], "revisions": [], "cross_checks": []},
        "claim_inventory": {
            "complete": True, "reviewed_response_indices": sorted(raw),
            "explanation": "All original public responses, including unknown top-level metadata, malformed framing, repeated message-only answers and actual Final, were read. Nested input source-value assertions and repeated arguments.sources/prose declarations are recorded by financial item; publication provenance and any additional source context are separately interpreted. No current assertion is erased merely because its variables were not consumed. " + decision["note"],
        },
        "source_claims": [],
        "target_binding": {
            "parameters": {key: "PASS" for key in ("local_relation", "public_scope_match", "registered_scope_match", "final_chain_completes_public_target")},
            "evidence": evidence(fi), "source_evidence": source_evidence(source_segments),
            "explanation": target_reason,
        },
        "review_author": "executing assistant, main partition 025–032; not independent or blinded",
    }
    for address, name in decision["nodes"].items():
        sid = decision["declared"][name]
        role, period, _ = ROLES[sid]
        review["mapping"]["occurrences"]["tool:1"][address] = {
            "kind": "source", "source_id": sid, "attribution": "model_declaration",
            "declaration_pointer": ["variables", name, "source"],
            "role": role, "period": period, "unit": "USD_million", "evidence": evidence(ci),
        }
    for index, event in enumerate(packet["events"]):
        if event["protocol_error"]:
            role = "failed_interface_message"
        elif event["tool_call"]:
            role = "answer_calculation"
        elif event["final"]:
            role = "Final"
        else:
            role = "public_message"
        review["mapping"]["event_annotations"].append({
            "response_index": index, "role": role,
            "interpretation": decision["note"], "evidence": evidence(index),
        })
        if event["protocol_error"]:
            assert number == 32 and index in (0, 1)
            review["mapping"]["revisions"].append({
                "before_index": index, "after_index": 2, "change_kind": "format_only",
                "semantic_key": None, "interpretation": decision["note"],
                "evidence": evidence(index, 2),
            })
        # Reading the first JSON fragment of failed framing is for claim inventory
        # only; it is never substituted for the recorded failed request/event.
        parsed, _ = json.JSONDecoder().raw_decode(raw[index])
        variables = parsed.get("arguments", {}).get("variables", {})
        for name, declaration in variables.items():
            sid = declaration["source"]
            assert sid in ROLES and sid in decision["declared"].values()
            role, period, segments = ROLES[sid]
            review["source_claims"].append({
                "location": f"response[{index}].arguments.variables.{name}; corresponding arguments.sources and contemporaneous item explanation",
                "parameters": {"role": "DIRECT_SOURCE_VALUE", "current": True, "source_value_equal": True, "consumed": bool(index == ci and name in call["output"]["result"]["resolved_variables"])},
                "evidence": evidence(index), "source_evidence": source_evidence(segments),
                "explanation": f"The explicit nested declaration binds this value to {sid}: {role}, {period}. The original source statement, amount and USD-million unit agree. This remains a current source-value assertion even when the literal expression consumes no named variable, or JSON framing prevents execution; current is not inferred from later correctness.",
            })
        publication = parsed.get("final", parsed)
        if isinstance(publication, dict) and "sources" in publication and "value" in publication:
            cited = publication["sources"]
            assert set(cited) <= set(ROLES)
            review["source_claims"].append({
                "location": f"response[{index}] publication explanation and sources list" + ("; actual final plus identical siblings" if number == 25 else ""),
                "parameters": {"role": "DERIVED_FROM_SOURCES", "current": True, "derivation_supported": True, "consumed": False},
                "evidence": evidence(index),
                "source_evidence": source_evidence([segment for sid in cited for segment in ROLES[sid][2]]),
                "explanation": "Surrounding text explicitly states a comparison or component-derived change and cites its input/source context, not a direct assertion that the derived answer equals each individual numeric source value. Every cited source is a correctly identified relevant amount of this same public comparison; their declared roles and the actual main calculation support the stated derivation. " + decision["note"],
            })
    return review_id, review


reviews = dict(build(number, decision) for number, decision in DECISIONS.items())
relative = BASE / "manual_reviews/review_025_032.json"
print("*** Begin Patch")
print("*** Add File: " + str(relative))
for line in json.dumps(reviews, ensure_ascii=False, indent=2).splitlines():
    print("+" + line)
print("*** End Patch")
