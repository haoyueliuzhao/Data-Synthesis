"""Manual, condition-label-masked review decisions; emits an artifact patch only.

Authored after reading all 24 complete blinded public packets and the six original
source entries, but before opening the A/T mapping or labelled outcome/cost reports.
This is an executing-agent review, not independent human certification. A bounded
peer-agent check advised on the five missing-target-scalar cases, also label-masked.
No calculations, missing answers, source declarations or model messages are added
to an online trajectory. The frozen evaluator is imported, never modified here.
"""

import copy
import json
import sys
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import (
    REVIEW_FIELDS,
    answer_score,
    display_compatible,
    final_number_and_unit,
    normalize_unit,
    reviewed_answer_score,
    trace_checks,
    verify_quotes,
)

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = {"R011", "R013", "R016", "R021", "R024"}
NO_OVERALL_RELATION = {"R008", "R011", "R013", "R016", "R021"}
VERIFIED_TRACES = {
    "R001", "R002", "R003", "R004", "R005", "R007", "R009", "R012",
    "R014", "R018", "R022", "R023",
}
EXTRACTED = {
    "R002": "58,665", "R003": "18", "R005": "14.46", "R006": "69.0",
    "R008": "18", "R010": "892.3", "R014": "892.3", "R015": "58665",
    "R017": "58665", "R019": "14.46", "R020": "892.3", "R023": "58665",
}
SECONDARY = {
    "R001": ["18"], "R002": ["58,665"], "R003": ["18"],
    "R004": ["69.0"], "R005": ["14.4643"], "R006": ["69.0"],
    "R007": ["14.46"], "R008": [], "R009": ["892.3"],
    "R010": ["892.3"], "R011": [], "R012": ["69.0"],
    "R013": [], "R014": ["892.3"], "R015": ["58,665"],
    "R016": [], "R017": ["58665"], "R018": ["14.464285714285714", "14.46"],
    "R019": ["14.46"], "R020": ["892.3"], "R021": [],
    "R022": ["69.0025", "69.0"], "R023": ["58,665"], "R024": [],
}

# Manual case-specific financial/source/unit judgments and observed behavior.
# Evidence below is copied mechanically from the full original public responses;
# copying authentic text does not make these semantic judgments automatic.
CASES = {
    "R001": (
        "Closing 2006 restructuring liability minus closing 2005/opening 2006 liability is a valid pre-registered alternative to summing the 2006 roll-forward movements.",
        "The pre-call explanation identifies 134 at Dec 31, 2006 and 116 at Dec 31, 2005; actually consumed variables bind t8c1n0 and t4c1n0 correctly. This is not the unrelated OCR opening row.",
        "The public pre-call message explicitly states both balances in million dollars, giving a positive 18 million change.",
        "One source-bound balance-difference calculation, then Final referencing tool:1. A shorter valid route was autonomously chosen; no multi-step plan is required.",
    ),
    "R002": (
        "Sum the two trading-asset categories for 2008 and subtract the same two-category sum for 2007; this matches the requested increase.",
        "The pre-call message identifies the two asset categories and annual pairing. Literal amounts and the source metadata match t1c2/t2c2 for 2008 and t1c3/t2c3 for 2007; no liabilities or 2009 values were substituted. Metadata attached to literal arithmetic is not a consumed named-variable binding.",
        "The pre-call explanation explicitly states million dollars. Both annual sums use the same scale and the later-minus-earlier difference is positive.",
        "One complete literal expression, then Final. The missing value field is extracted from the actual Final answer '$58,665 million', not filled from the reference.",
    ),
    "R003": (
        "Closing 2006 minus its opening balance is a valid source-grounded net-change relation, equivalent to the registered roll-forward sum.",
        "Consumed closing_2006=134 and opening_2006=116 bind the correct t8c1n0 and t4c1n0; the model explicitly explains Dec 31, 2005 as the opening balance for 2006.",
        "Both variables declare $ millions, and the resulting positive difference retains that unit.",
        "One named-variable subtraction, then Final with tool:1. Final answer=18 is used because value is absent; no host-created computation.",
    ),
    "R004": (
        "2004 money-pool operating cash use divided by same-year receivables, times 100, is the applicable percentage relation.",
        "Before execution the model explicitly names q0n0=42.5 million cash use and t2c0n0=61592 thousand year-end receivables. The positive use magnitude and first data column are correct. Unused variables/source metadata do not create automatic bindings for the literal expression.",
        "The pre-call message and expression convert 61592 thousand to 61.592 million before division and percentage scaling.",
        "One full literal expression followed by Final. The precise value and 69.0% display agree at their respective frozen precisions.",
    ),
    "R005": (
        "Global leased floor area divided by global total area, times 100, is applicable. The successful calculation at response 1 implements that relation.",
        "The corrected request consumes leased_sqft=8.1 from t2c3n0 and total_sqft=56.0 from t3c3n0. Both global roles and correct source spans are visible before that actual execution.",
        "Both corrected input variables declare million square feet; the common scale cancels and the expression multiplies by 100.",
        "Response 0 contains the unquoted fraction 81/10 in a JSON value position and produced no actual calculation. Response 1 represents it as 8.1 and executes the same intended formula once. This is a visible JSON/interface-format repair, not a new financial method. Final is free text; take its first explicit answer 14.46% and separately check its more precise 14.4643% display.",
    ),
    "R006": (
        "The Final itself publicly states the appropriate same-year money-pool cash-use percentage calculation, but no actual calculator request exists.",
        "The actual Final text explicitly identifies 2004 cash use 42.5 million and Dec 31, 2004 receivables 61592 thousand; the same response also lists their source spans. This is final-only source evidence.",
        "The Final explicitly converts the receivable to 61.592 million and reports 69.0%, with the correct percentage scale.",
        "Direct Final with a correct public calculation in prose, not a tool-executed trace. Top-level value outside the final field is not adopted as an alternative schema; extract 69.0 from the actual Final string itself.",
    ),
    "R007": (
        "The pre-call explanation identifies leased/total global square footage times 100, and the literal expression implements it.",
        "The message pairs 8.1 leased with 56.0 total and source metadata explicitly identifies numerator t2c3n0 and denominator t3c3n0. Literal arithmetic remains distinct from machine-bound source variables.",
        "The pre-call roles and referenced table identify the same million-square-feet scale; the ratio cancels it and multiplies by 100.",
        "One annotated literal calculation then Final with tool:1, a precise value and a compatible 14.46% display. The coarse original annotation 14% is not substituted as a target.",
    ),
    "R008": (
        "NOT_ESTABLISHED: the only public content is '18 million'; no formula or financial relationship is stated, and none is inferred from a correct number.",
        "NOT_ESTABLISHED: no input, year-to-source association or provenance is published. Do not reconstruct a supposed 134-116 plan on the model's behalf.",
        "NOT_ESTABLISHED: the output's million scale can be interpreted in the monetary task context, but no input units or actual unit handling are visible. This is separate from the numeric answer's published-unit check.",
        "Bare direct Final containing only a number and million unit. This case lacks both a public derivation and actual calculation, unlike other no-tool answers that do contain a derivation.",
    ),
    "R009": (
        "The arithmetic average of the three company-defined cash-flow values is applicable; not the operating-CFO or annual-percentage-change row.",
        "The pre-call message explicitly maps 957.4 to 2006, 769.1 to 2005 and 950.4 to 2004 and names the company's defined cash-flow row, with matching t3 source IDs in metadata.",
        "The referenced table's three same-scale cash-flow values are in million dollars; dividing the three-value sum by the count preserves that scale. Final does not claim a percentage.",
        "One complete literal average then Final linked to tool:1. Final additionally describes the source's non-GAAP definition, without inventing a separately executed capex calculation.",
    ),
    "R010": (
        "The Final-only expression averages the three cash-flow values for the requested 2004-2006 interval.",
        "Final includes the three correct cash-flow source spans and the expression 957.4+769.1+950.4, with a message identifying the requested range. This permits finite final-only correspondence review, not pre-execution certification.",
        "Final explicitly states $ million and a monetary average, consistent with the source table.",
        "Direct Final with a formula and correct answer, but zero actual calculation. Extract the actual answer field because value is absent.",
    ),
    "R011": (
        "NOT_ESTABLISHED for the registered combined two-year quantity: the model proposes and then publishes separate annual cash-plus-securities totals, not a cross-year aggregate. The annual relation is reasonable and its arithmetic is correct; this is not a false-formula finding.",
        "Response 1 correctly pairs 2010 cash/securities 25.0/9.7 and 2009 cash/securities 24.0/10.2, as disclosed in q16. These are correct public input associations for annual subtotals.",
        "The published component amounts are explicitly dollar billions and their annual sums use that same scale.",
        "The first response is incomplete JSON with text inside the expression and produces no actual calculation. Final then gives 2010=34.7 and 2009=34.2. There is no published combined 68.9; do not choose one annual subtotal, treat it as the same semantic quantity, or host-add the pair.",
    ),
    "R012": (
        "Money-pool use divided by same-year receivables, with the thousand/million conversion and percent multiplier, is applicable.",
        "The pre-call message explicitly names the 42.5 million use and 61592 thousand receivable for 2004, with correct source-span metadata.",
        "The actual expression converts the denominator by 1000, then multiplies by 100; Final 69.0 is a percentage-point display, not a raw fraction.",
        "One literal calculation and Final with tool:1. The actual Final value 69.0 is kept at its lexical precision; its difference from the exact tool result is within the unchanged 0.005 cap.",
    ),
    "R013": (
        "NOT_ESTABLISHED for the registered combined two-year total: both actual expressions compute legitimate annual cash-plus-securities subtotals only. Neither an executed nor published cross-year aggregate appears.",
        "Response 0 publicly identifies 2010 cash 25.0 and securities 9.7 with correct source IDs; response 1 identifies 2009 cash 24.0 and securities 10.2. All annual/category pairings are correct.",
        "Pre-call public statements use dollar billions for each annual calculation, and Final retains USD billions.",
        "Two actual independent additions yield 34.7 and 34.2; no earlier-result reference is consumed. Final publishes both annual results but no combined target scalar. The individual tool outputs are real and correct, yet neither is selected as the registered answer calculation.",
    ),
    "R014": (
        "Average of the three company-defined cash-flow row values is the required quantity; the pre-call explanation also identifies its CFO-less-property-additions meaning.",
        "The pre-call text and metadata correctly pair the three values with 2006/2005/2004 and the t3 row. It does not rely on the erroneous hand-written source annotation intermediate.",
        "The source row uses million dollars throughout; the three-year arithmetic average retains that unit, as Final explicitly states.",
        "One literal average followed by Final referencing tool:1. Extract 892.3 from its actual answer field because no value field is present.",
    ),
    "R015": (
        "The Final response publicly shows the two asset-category sums and the 2008-minus-2007 difference; that is an applicable complete relation.",
        "The same Final response explicitly pairs 384102/121417 with 2008 and 381415/65439 with 2007, lists the correct spans and does not subtract liabilities or use 2009.",
        "Final explicitly labels the positive increase in million dollars, with same-scale annual sums.",
        "Direct Final with correct public arithmetic, but no actual calculate call. The answer remains separately eligible for numeric PASS.",
    ),
    "R016": (
        "NOT_ESTABLISHED for the registered combined two-year total: cash2010+sec2010 and cash2009+sec2009 are valid annual subtotal relations, but no relation combining the years is delivered.",
        "The two actual calls consume correctly source-bound year/category variables: q16n3/q16n5 for 2010 and q16n4/q16n6 for 2009. This is not a wrong-source or wrong-year finding.",
        "All four consumed inputs are declared billion and the accompanying prose explicitly identifies dollars; both annual results preserve the billion scale.",
        "Two source-bound independent additions produce correct annual subtotals; Final repeats those two quantities and no combined answer. Do not select tool:1 or tool:2 as if it computed the missing cross-year total, and do not sum them offline into a model answer.",
    ),
    "R017": (
        "The Final response correctly defines total trading assets as the two asset categories and subtracts the 2007 total from 2008.",
        "Public Final prose labels the balances as averages and correctly maps each year to its two values and source spans.",
        "Final explicitly requests the result in million dollars and reports a positive later-minus-earlier increase.",
        "Direct Final with correct complete public derivation but no actual tool execution; no inference of a hidden calculator call.",
    ),
    "R018": (
        "Global leased square footage divided by global total square footage, times 100, is applicable and actually executed.",
        "The pre-call message explicitly associates 8.1 with leased and 56.0 with total table amounts. Final IDs agree, but are not backdated as machine bindings; the literal request had no source declarations.",
        "Both quantities are explicitly identified as million square feet before execution; their common scale cancels and the ratio is converted to percent.",
        "One literal expression then Final. The long value, equally precise answer string and 14.46% prose display are compatible; no host precision repair.",
    ),
    "R019": (
        "The Final-only public relation correctly computes the global leased-area percentage.",
        "The same Final response identifies 8.1 million leased and 56.0 million total and lists the corresponding total-column source spans.",
        "The Final prose explicitly aligns million square feet and percentage scaling, with a compatible 14.46% answer.",
        "Direct Final with a correct public formula, but result_id points to a public_document rather than any actual tool result. Numeric correctness and invalid execution-reference metadata are separate findings.",
    ),
    "R020": (
        "The Final response correctly describes averaging the three company-defined cash-flow amounts, not the operating-CFO row.",
        "The public message pairs 950.4 with 2004, 769.1 with 2005 and 957.4 with 2006 and cites the correct source spans. Reversing addition order is immaterial.",
        "The Final and its explanation explicitly use million dollars; taking the three-year average preserves that unit.",
        "Direct Final containing correct public arithmetic. Its result_id points to a task identifier, not an executed calculator result; no tool execution is manufactured from that field.",
    ),
    "R021": (
        "NOT_ESTABLISHED for the registered combined quantity: the direct Final correctly explains cash plus securities separately for 2010 and 2009, without giving a cross-year total.",
        "Final explicitly associates 25.0+9.7 with 2010 and 24.0+10.2 with 2009 and names the correct q16 numeric spans. These annual associations are supported.",
        "Each amount and annual result is explicitly in dollar billions; no scale error is observed.",
        "Direct Final with correct annual derivations but no actual calculation or combined target scalar. The original question can naturally invite per-year reporting; that is a scope-interpretation limitation, not permission to change the pre-registered target after seeing responses.",
    ),
    "R022": (
        "The submitted expression correctly computes the positive money-pool use percentage of receivables for 2004.",
        "The pre-call message explicitly names the same-year cash-use and year-end receivable amounts and their financial roles. Later Final source IDs agree, without creating automatic bindings for the literal expression.",
        "The pre-call explanation explicitly converts 61592 thousand to 61.592 million and multiplies the ratio by 100. The Final's 69.0025% and 69.0% displays are consistent percentage representations.",
        "One correct literal expression then Final linked to tool:1. Both additional answer displays are checked separately at their own precision.",
    ),
    "R023": (
        "The actual successful expression computes the correct two-category annual totals and their 2008-minus-2007 difference.",
        "At response 1, the model explicitly identifies each annual pair and source spans. Both categories are assets; no liabilities or 2009 quantities enter the formula.",
        "The successful pre-call message and Final explicitly use million dollars with a positive increase, consistent with the source's annual average balances.",
        "Response 0 placed unevaluated sums such as 384102+121417 in JSON value positions and produced no actual calculation. Response 1 moves the same intended arithmetic into expression and executes once. This is JSON/interface repair, not a financially different method or tool-result reuse.",
    ),
    "R024": (
        "The earlier public response correctly states the pre-registered alternative 134 minus 116 for the 2006 restructuring-liability net change.",
        "Response 0 identifies the two closing dates and correct t8c1n0/t4c1n0 source spans. That public financial correspondence is real even though the response is not Final and has no tool call.",
        "Response 0 explicitly labels the net change in million dollars and uses compatible monetary balances. This evidence is about the public method, not a unit published in the later Final.",
        "Response 0 contains a correct public answer and derivation without a final field or tool request. Response 1 then says only 'Task complete.' in Final. Frozen scoring extracts from actual Final only: do not move the earlier 18 into it. There is no actual calculation.",
    ),
}


def main():
    reviews = json.loads((ROOT / "assessment/review_template.json").read_text())
    private = json.loads((ROOT / "preparation/private/evaluation_targets.json").read_text())
    assert set(reviews) == set(CASES) == set(SECONDARY)
    summary = []
    for rid in sorted(reviews):
        review = reviews[rid]
        packet = json.loads((ROOT / f"assessment/blinded/{rid}.json").read_text())
        assert packet["review_id"] == rid and packet["no_condition_label_or_usage"] is True
        raw = {int(k): v for k, v in packet["raw_messages"].items()}
        fi = packet["first_final_index"]
        assert fi is not None and packet["terminal"] == "model_final"

        def evidence(indices):
            return [{"response_index": index, "quote": raw[index]} for index in indices]

        basis = [1] if rid in {"R005", "R011", "R023"} else [0, 1] if rid in {"R013", "R016"} else [0]
        formula, variables, units, observation = CASES[rid]
        for field, explanation in zip(REVIEW_FIELDS[:3], (formula, variables, units), strict=True):
            review[field] = {
                "status": "NOT_ESTABLISHED" if explanation.startswith("NOT_ESTABLISHED") else "PASS",
                "explanation": explanation,
                "evidence": evidence(basis),
            }
        assert (review["formula_applicability"]["status"] != "PASS") == (rid in NO_OVERALL_RELATION)
        review["answer_calculation_id"] = "tool:1" if rid in VERIFIED_TRACES else None
        alignment = "PASS" if rid in VERIFIED_TRACES else "NOT_ESTABLISHED"
        explanation = (
            "The actual Final's primary answer matches the actually executed tool:1 result at the frozen publication precision, with the correct unit and direction. No missing explicit result_id is invented."
            if alignment == "PASS"
            else "No actual tool execution and Final publication of the registered target quantity can be selected as one complete answer chain. Correct public prose or component calculations are described separately, not promoted."
        )
        if rid in {"R019", "R020"}:
            alignment = "FAIL"
            explanation = "The Final result_id names a public document or task, not an actual calculator result; no calculate call exists. This invalid execution reference does not reverse the separate correct numeric answer."
        review["publication_alignment"] = {
            "status": alignment, "explanation": explanation, "evidence": evidence([fi]),
        }
        review["final_answer_consistency"] = {
            "status": "NOT_ESTABLISHED" if rid in UNKNOWN else "PASS",
            "explanation": (
                "Final gives correctly labelled annual subtotals only, not an unambiguous combined two-year target scalar. The fields do not contradict each other and no wrong combined value is asserted. Retain UNDETERMINED under the frozen missing-number rule; do not add the subtotals or compare different annual quantities as same-target secondary fields."
                if rid in UNKNOWN - {"R024"}
                else "The actual Final is only 'Task complete.' and has no answer quantity. The correct 18 in the previous non-Final public message is not eligible for the frozen Final-only extraction rule. No incorrect numeric claim is manufactured; interpretation of a final answer remains unestablished."
                if rid == "R024"
                else "The actual Final's answer quantity, sign, time scope and unit are coherent at the stated display precisions. Valid arithmetic without an actual tool call can still be a correct answer; execution-reference validity is checked separately."
            ),
            "evidence": evidence([fi]),
        }
        if rid in EXTRACTED:
            assert review["published_value"] is None
            review["published_value"] = EXTRACTED[rid]
            review["answer_override_evidence"] = evidence([fi])
        if rid == "R008":
            assert review["published_unit"] is None
            review["published_unit"] = "USD_million"
            review["final_answer_consistency"]["explanation"] += (
                " The actual free-text Final explicitly says '18 million'; in this monetary-liability source context this is a million-dollar answer. This is semantic extraction of its stated quantity/unit, not filling an absent number or inventing a formula from the reference."
            )
        if rid in UNKNOWN:
            assert review["published_value"] is None and not review["answer_override_evidence"]
        review["secondary_answer_values"] = [
            {"value": value, "unit": review["published_unit"], "evidence": evidence([fi])[0]}
            for value in SECONDARY[rid]
        ]
        review["planning_observations"] = {
            "text": observation,
            "evidence": evidence(sorted(raw)),
        }
        verify_quotes(review, raw)
        assert all(e["response_index"] == fi for e in review["final_answer_consistency"]["evidence"])
        public = json.loads((ROOT / f"preparation/public/{packet['task_key']}.json").read_text())
        iv, iu = final_number_and_unit(packet["raw_final"], public["question"])
        if iv is not None:
            assert str(iv) == str(review["published_value"]), "Never replace an existing Final value"
        if rid != "R008":
            assert normalize_unit(iu) == normalize_unit(review["published_unit"])
        for item in review["answer_override_evidence"]:
            assert item["response_index"] == fi
            assert str(review["published_value"]).replace(",", "") in item["quote"].replace(",", "")
        score = reviewed_answer_score(
            answer_score(review["published_value"], review["published_unit"], private[packet["task_key"]]), review
        )
        checks = []
        for secondary in review["secondary_answer_values"]:
            assert secondary["value"] in secondary["evidence"]["quote"]
            assert secondary["evidence"]["response_index"] == fi
            checks.append(display_compatible(
                score["reference_exact_value"], review["published_unit"], secondary["value"], secondary["unit"]
            ))
        if any(c is False for c in checks):
            score["task_answer_status"] = "FAIL"
        trace = trace_checks(packet, review, score)
        assert score["task_answer_status"] == ("UNDETERMINED" if rid in UNKNOWN else "PASS"), rid
        assert trace["formula_driven_trace_verified"] == (rid in VERIFIED_TRACES), rid
        summary.append({
            "review_id": rid, "task_key": packet["task_key"],
            "answer_status": score["task_answer_status"],
            "formula_driven_verified": trace["formula_driven_trace_verified"],
            "secondary_checks": checks,
        })
    print(json.dumps({"masked_validation": summary}, ensure_ascii=False), file=sys.stderr)
    target = ROOT / "review/masked_reviews.json"
    assert not target.exists(), "Never overwrite reviews after condition decoding"
    print("*** Begin Patch\n*** Add File: " + str(target))
    for line in json.dumps(reviews, ensure_ascii=False, sort_keys=True, indent=2).splitlines():
        print("+" + line)
    print("*** End Patch")


if __name__ == "__main__":
    main()
