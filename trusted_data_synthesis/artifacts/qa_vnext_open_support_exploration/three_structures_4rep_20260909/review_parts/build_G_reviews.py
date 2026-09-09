"""Explicit post-generation finite review of only the eight new G sessions.

All semantic decisions, published values, and source pointers below were chosen
after reading these eight complete original public histories and their frozen
source context.  This helper copies exact evidence; it neither infers sources by
number matching nor changes any frozen code, original response, or target.
"""

import copy
import json
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.evaluate import qualify
from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.projection import project_session
from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.source import bind_session

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent.parent

DECISIONS = {
    "T_G1_01": {
        "published_value": "14.46", "published_unit": "percent", "override": True,
        "expression": "8.1/56*100", "pointers": ["8.1", "56.0"],
        "secondary": [], "publication_status": "PASS",
        "publication_note": "Final.answer explicitly publishes 14.46%; this is within the frozen primary 0.005 percentage-point cap of the actual 405/28 result. The actual Final cites tool:1.",
        "special": "The same-call prose states the part/whole ratio, and the actual expression supplies the explicit multiplication by 100. Both source IDs are model declarations for consumed literals, not consumed named variables.",
    },
    "T_G1_02": {
        "published_value": "14.4642857142857", "published_unit": "percent", "override": True,
        "expression": "leased / total * 100", "pointers": ["leased", "total"],
        "secondary": ["14.5"], "publication_status": "PASS",
        "publication_note": "The actual string Final begins with 14.4642857142857%, retained as the primary answer. Its separately marked approximately 14.5% is a secondary display and is checked at its own display precision, not substituted for the primary.",
        "special": "Named variables leased and total were actually resolved and consumed. Their source IDs are explicitly declared in both the variables objects and the sources dictionary. No result_id inside the string Final is invented.",
    },
    "T_G1_03": {
        "published_value": "14.464285714285714", "published_unit": "percent", "override": False,
        "expression": "leased_total / total_facilities * 100", "pointers": ["leased_total", "total_facilities"],
        "secondary": ["14.46"], "publication_status": "PASS",
        "publication_note": "The original Final.value 14.464285714285714 is primary. Final.answer 14.46% is separately checked against the same exact reference at its own displayed precision. The actual Final cites tool:1.",
        "special": "Both named variables, their million-square-feet units, and their source IDs appear in the original calculate request and are actually consumed. The sibling final-turn message is retained but not used to replace Final.value.",
    },
    "T_G1_04": {
        "published_value": "14.5", "published_unit": "percent (%)", "override": False,
        "expression": "8.1/56.0*100", "pointers": ["leased", "total"],
        "secondary": [], "publication_status": "FAIL",
        "publication_note": "The original Final.value is 14.5, not the more precise tool result or the explanatory 14.464...%. Its error from 405/28 exceeds the frozen 0.005 primary cap. The raw unit string percent (%) is also outside the unchanged automatic unit-alias dictionary; it is preserved rather than normalized by a new rule.",
        "special": "The expression consumes only numeric literals. The variables dictionary contains source-ID strings but resolved_variables is empty, so those entries are not portrayed as numerical consumption. The sources dictionary and same-call formula explicitly associate leased and total with the two source IDs. Final prose 14.464...% is an ellipsis continuation, not an exact replacement primary or a newly completed decimal; it remains visible in the original Final evidence.",
    },
    "T_G2_01": {
        "published_value": "11.6893203883495", "published_unit": "percent", "override": False,
        "expression": "301/2575*100", "pointers": ["301", "2575"],
        "secondary": ["11.69"], "publication_status": "PASS",
        "publication_note": "The original Final.value 11.6893203883495 is primary; Final.answer approximately 11.69% is a compatible secondary display. The actual Final cites tool:1. The ellipsis in the sibling message is not promoted to an exact answer.",
        "special": "The model explicitly names 2018 payments and total future payments in USD millions, and maps the consumed literals through its original sources dictionary.",
    },
    "T_G2_02": {
        "published_value": "11.6893203883495", "published_unit": "percent", "override": True,
        "expression": "(due2018 / total) * 100", "pointers": ["due2018", "total"],
        "secondary": ["11.7", "1204/103", "11.69"], "publication_status": "PASS",
        "publication_note": "Final.answer starts with 11.6893203883495%, retained as primary. Its about 11.7%, and the actual Final.calculation results 1204/103% and approximately 11.69%, are all recorded as secondary answer displays and checked against the same reference under the frozen secondary rule. None replaces the primary.",
        "special": "The two named variables due2018 and total are actually consumed with exact values 301 and 2575. Their original variable objects and sources dictionary explicitly declare source IDs and dollar-million units.",
    },
    "T_G2_03": {
        "published_value": "11.69", "published_unit": "percent", "override": True,
        "expression": "301/2575*100", "pointers": ["301", "2575"],
        "secondary": [], "publication_status": "PASS",
        "publication_note": "Final.answer explicitly publishes approximately 11.69%; Final.calculation repeats the same result. The primary is within the frozen 0.005 cap of 1204/103 and the actual Final cites tool:1.",
        "special": "The original same-call message names the 2018 and total table rows and says to convert to percentage; arguments.sources supplies the exact source IDs for both consumed literals.",
    },
    "T_G2_04": {
        "published_value": "11.7", "published_unit": "percent", "override": True,
        "expression": "301/2575*100", "pointers": ["301", "2575"],
        "secondary": [], "publication_status": "FAIL",
        "publication_note": "The actual string Final publishes only 11.7% as its answer. The error from 1204/103 exceeds the frozen 0.005 primary cap. The exact tool result is not inserted into Final. The top-level sibling result_id is not represented as a result_id field inside the original string Final.",
        "special": "The input pair and conversion to percentage are explicit in the calculate message and sources dictionary. The Final's 301 and 2575 are operands, not alternate answer publications; they are not incorrectly included as secondary answers.",
    },
}


def read(path):
    return json.loads(path.read_bytes())


def build():
    template = read(OUT / "assessment/review_template.json")
    private = read(OUT / "preparation/private/evaluation_targets.json")
    reviews, validation = {}, {}
    for label, decision in DECISIONS.items():
        key = label.split("_")[1]
        packet = read(OUT / "assessment/public_review_packets" / (label + ".json"))
        audit = read(OUT / "assessment/sessions" / (label + ".json"))
        public = read(OUT / "preparation/public" / (key + ".json"))
        session_dir = OUT / "online/sessions" / label
        result = read(session_dir / "result.json")
        assert result == packet["actual_result"]
        assert len(result["events"]) == 2 and result["events"][1]["final"]
        call = result["events"][0]["tool_call"]
        assert call["id"] == "tool:1" and call["name"] == "calculate"
        assert call["arguments"]["expression"] == decision["expression"]
        assert call["output"]["status"] == "ok"
        assert call["output"] == read(session_dir / "turns/000_tool.json")
        raw = {index: (session_dir / f"turns/{index:03d}_assistant.raw").read_text() for index in (0, 1)}
        assert raw == {int(index): text for index, text in packet["raw_messages"].items()}
        before = {"response_index": 0, "quote": raw[0]}
        final = {"response_index": 1, "quote": raw[1]}
        review = copy.deepcopy(template[label])
        review["published_value"] = decision["published_value"]
        review["published_unit"] = decision["published_unit"]
        review["answer_override_evidence"] = [final] if decision["override"] else []
        review["answer_calculation_id"] = "tool:1"
        review["secondary_answer_values"] = [
            {"value": value, "unit": "percent", "evidence": final}
            for value in decision["secondary"]
        ]
        if key == "G1":
            source_ids = ["source:t2c3n0", "source:t3c3n0"]
            roles = ["Worldwide leased facility floor area", "Worldwide total facility floor area"]
            source_unit = "million square feet"
            period = "December 26 2015 source-table snapshot; reviewer attribution from original p3"
            formula_note = "The model proposes leased total floor area divided by all-facility total floor area, with multiplication by 100 in the same request. That is the requested global area share, not a count of buildings or a regional ratio."
            correspondence_note = "The original model source declarations identify the leased-total row and the all-facilities-total row in the total column. The actual consumed values are 8.1 and 56.0 (56 is an exact spelling of 56.0), matching those two table cells. The source's p3 establishes the 2015 snapshot; no model claim of separate temporal reasoning is added."
            unit_note = "Both source values share the million-square-feet scale, which cancels in the ratio. The actual same-call expression multiplies by 100 for percentage publication. This semantic input-unit judgment is separate from any raw Final-unit alias acceptance."
            final_note = "Final concerns the leased share of total facility square footage, with the correct numerator/denominator scope and positive percentage. Any coarse primary display is handled by the unchanged numerical rule, not by changing the interpreted task."
        else:
            source_ids = ["source:t3c1n0", "source:t7c1n0"]
            roles = ["Future minimum net rental payments due in 2018", "Total future minimum net rental payments"]
            source_unit = "USD_million"
            period = "December 2015 disclosure; numerator maturity 2018 and denominator all listed future maturities"
            formula_note = "The model proposes 2018-due minimum rental payments divided by total future minimum rental payments, multiplied by 100. This matches the requested maturity share. No time-bucket reconstruction or alternate-route checking was executed."
            correspondence_note = "The original model declarations identify the 2018 row (301) and total row (2575), and actual execution consumes those values. Both are in the December 2015 table; original p25 specifies net of minimum sublease rentals. The unrelated annual rent expense is not used. The net/disclosure-time elaboration is reviewer interpretation of the cited source context, not added model wording."
            unit_note = "Both actual input amounts are USD millions in the same table. Their common scale cancels, and multiplication by 100 supplies percent rather than an unconverted decimal ratio."
            final_note = "Final reports the percentage due in 2018 within the same future-payment table scope. It does not substitute annual rent expense, change the due year, or describe a gross amount from another source. Coarse primary precision is evaluated separately."
        for field, explanation in (
            ("formula_applicability", formula_note),
            ("variable_correspondence", correspondence_note),
            ("unit_handling", unit_note),
        ):
            review[field] = {"status": "PASS", "evidence": [before], "explanation": explanation}
        review["publication_alignment"] = {
            "status": decision["publication_status"], "evidence": [final],
            "explanation": decision["publication_note"],
        }
        review["final_answer_consistency"] = {"status": "PASS", "evidence": [final], "explanation": final_note}
        review["planning_observations"] = {
            "text": "One successful calculate request followed by the first terminal Final. The observed method uses the two disclosed total-column/total-row inputs. No read_source, notebook, actual result reuse, interface recovery, substantive revision, or independent cross-check is present. " + decision["special"],
            "evidence": [before, final],
        }
        occurrences = {}
        for address, sid, role, pointer_key in zip(
            ("body.left.left", "body.left.right"), source_ids, roles, decision["pointers"], strict=True
        ):
            assert call["arguments"]["sources"][pointer_key] == sid
            assert sid in private[key]["facts"]
            occurrences[address] = {
                "kind": "source", "source_id": sid,
                "attribution": "model_declaration", "declaration_pointer": ["sources", pointer_key],
                "evidence": [before], "role": role, "period": period, "unit": source_unit,
            }
        occurrences["body.right"] = {
            "kind": "constant", "value": "100", "reason": "Dimensionless ratio-to-percent conversion explicitly present in the original calculation request.", "evidence": [before],
        }
        review["mapping"] = {
            "occurrences": {"tool:1": occurrences},
            "event_annotations": [
                {"response_index": 0, "role": "answer_calculation", "interpretation": formula_note + " " + decision["special"], "evidence": [before]},
                {"response_index": 1, "role": "Final", "interpretation": decision["publication_note"], "evidence": [final]},
            ],
            "revisions": [], "cross_checks": [],
        }
        qualified = qualify(audit, review, public, private[key], raw)
        expected_valid = decision["publication_status"] == "PASS"
        assert qualified["formula_driven_trace_verified"] is expected_valid, qualified
        projection_status, projection_reason = "NOT_PROJECTED_ORIGINAL_INVALID", None
        if expected_valid:
            projection = project_session(bind_session(ROOT, qualified), review["mapping"], private[key]["goal_scope"])
            projection_status, projection_reason = projection["status"], projection["reason"]
            assert projection_status == "MAPPED", projection_reason
        validation[label] = {
            "answer_status": qualified["answer"]["task_answer_status"],
            "valid": qualified["formula_driven_trace_verified"],
            "published_value": review["published_value"],
            "published_unit": review["published_unit"],
            "secondary_reference_checks": qualified["secondary_numeric_checks"],
            "mapping_status": projection_status, "mapping_reason": projection_reason,
        }
        reviews[label] = review
    target = OUT / "review_parts/G.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(reviews, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(validation, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    build()
