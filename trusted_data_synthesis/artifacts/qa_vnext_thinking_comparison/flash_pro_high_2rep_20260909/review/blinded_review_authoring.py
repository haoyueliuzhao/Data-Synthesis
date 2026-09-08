"""Post-generation manual judgments, authored before condition-label decoding.

This is an artifact-authoring utility, not frozen online/evaluation code. It only
reads the allowlisted R packets/template and task-only reference targets. It never
opens review_ids, condition-labelled sessions, reports, usage, or cost records.
Full original public messages are mechanically copied as evidence; the explanations
and statuses below are the executing agent's finite semantic judgments, not an
independent reviewer and not an automatic semantic certificate. Output is a patch.
"""

import copy
import json
import sys
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.evaluate import (
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

# Each tuple is a manually reviewed statement of formula, data association,
# unit treatment, and observed public behavior, after reading its complete packet.
JUDGMENTS = {
    "R001": (
        "2015 agricultural revenue divided by 2015 total operating revenue, times 100, is the requested share.",
        "The pre-call message names agricultural and total 2015 revenues and places 3581/21813 in that order. Table rows t1/t9, column 1 agree. This is a finite prose/literal review; source IDs appear only in Final and no named source variable was consumed.",
        "Both table amounts use the same millions scale, which cancels, and the public expression multiplies by 100. No cross-period or percentage-scale conversion is needed.",
        "One complete literal expression was executed, then Final; no actual result reuse, source lookup, notebook, or revision is present.",
    ),
    "R002": (
        "GE-held cash divided by total cash and equivalents in 2017, times 100, is applicable.",
        "Before execution, cash_ge_millions binds 997 to p2n0 and cash_equiv_billions binds 7.0 to p1n2; the source prose gives those roles and year.",
        "The denominator is explicitly converted from billions to millions by 1000; the final multiplication produces percentage points.",
        "One named-variable calculation with explicit source bindings, followed by Final referencing tool:1; no intermediate-result reuse or revision.",
    ),
    "R003": (
        "Accrued interest and penalties divided by ending gross unrecognized tax benefits, times 100, is an applicable percentage relation.",
        "The model explicitly selected 15.3 million from q2 and the rounded 139.5 million from q0. Both are authentic same-period financial items. It did not select the finer table ending balance 139549 thousand. Thus this passes item/source correspondence only, not equivalence to the registered exact reference or full-precision data selection. Unused declarations do not create machine bindings.",
        "Both actually substituted amounts are in millions, so the scale cancels. The discrepancy is rounded-denominator precision, not a million/thousand error.",
        "One calculation on 15.3/139.5, then Final. The tool faithfully executes that lower-precision source choice; no corrective iteration occurs. Its long value is retained and is not replaced by a target-derived value.",
    ),
    "R004": (
        "After-tax cost is compensation cost less the positive magnitude of the tax benefit; change is (2010 minus 2009)/2009 times 100.",
        "The pre-call explanation names cost, tax benefit and years; ordered literal fractions 181/10, 63/10, 73/5 and 26/5 represent 18.1, 6.3, 14.6 and 5.2 in the respective table positions. Subtracting positive benefit magnitudes agrees with the signed negative benefit lines. No actual named-source binding is claimed.",
        "The cost and benefit terms share a monetary scale; the 2009-based ratio cancels it and multiplies by 100. Rational spellings are exact conversions of the source decimals.",
        "One full rational-literal expression, then Final. The representation has extra arithmetic nodes, not additional autonomous planning stages or result reuse.",
    ),
    "R005": (
        "The relation 997/7000 times 100 is applicable, but is visible only in the same response as Final, with no actual calculate call.",
        "The Final response explicitly identifies 2017 cash of 7.0 billion at p1n2 and GE-held 997 million at p2n0. These agree with the original prose; this is final-only source evidence.",
        "The public Final explanation explicitly converts 7.0 billion to 7000 million and reports a percentage.",
        "Direct Final with a self-reported calculation. There is no executed calculation to verify or pre-execution tool trajectory to certify.",
    ),
    "R006": (
        "Interest/penalties divided by the ending balance, times 100, is applicable.",
        "Pre-call named variables select q2n2 = 15.3 and t6c1n0 = 139549. The period and roles agree with the source table/prose; both named inputs were actually consumed.",
        "The model explicitly interprets 139549 as thousands and converts it to millions by dividing by 1000. This inference is supported by the adjacent rounded 139.5 million disclosure, not an explicit thousand header in the extracted table.",
        "One named-variable formula, then Final linked to tool:1; no source-tool retrieval or corrective iteration.",
    ),
    "R007": (
        "Subtract tax-benefit magnitudes from compensation costs, then divide the increase by the 2009 after-tax cost and multiply by 100.",
        "The pre-call annotations explicitly pair 2010 with 18.1 and -6.3 and 2009 with 14.6 and -5.2. Literal subtraction of positive benefit magnitudes is appropriate. Annotation values such as '18.1 - 6.3' are unused metadata, not executed named variables.",
        "Same-scale monetary differences and the percent multiplier are correct. Final restates subtraction as adding the signed negative benefits without changing the relationship.",
        "One literal calculation; Final rewrites the same signed arithmetic in prose. This is not an actual second calculation or revision after a failed method.",
    ),
    "R008": (
        "The sum of coal revenues over 2014-2016 divided by the sum of total operating revenues over those years is the aggregate share, not an average of yearly percentages.",
        "The pre-call message identifies coal/total and period; the literal groups and source mapping agree with rows t4/t9, columns 1-3. The source map is visible metadata, not a consumed variable binding.",
        "All six inputs share the table's millions scale, which cancels; the expression multiplies by 100.",
        "One complete sum-over-sum expression, then Final. The two sums occur inside one actual calculator call, not a multi-call plan.",
    ),
    "R009": (
        "GE-held cash as a share of the 2017 total cash and equivalents is applicable.",
        "The consumed variables explicitly associate 997 with p2n0 and 7.0 with p1n2, matching the public prose roles and year.",
        "The denominator is converted from billions to millions by 1000 before the percentage is taken.",
        "One named-variable calculation; Final publishes the same result without an explicit tool result_id. No false result reference is introduced.",
    ),
    "R010": (
        "The 2017 shares times 2017 average exercise price minus the corresponding 2016 product is the requested exercise-value increase; it is not an option fair-value valuation.",
        "The executed variables pair 11 million shares with 33.32 for 2017 and 13 with 26.93 for 2016, with the exact t3c2/t3c3 and q0n2/q0n3 source spans.",
        "Million shares times USD per share yields million USD; taking the later-minus-earlier product gives a positive increase.",
        "One source-bound expression with two products and one subtraction, then Final. No intermediate tool result or independent option-pricing model is used.",
    ),
    "R011": (
        "The Final-only public formula multiplies annual option shares by the same year's exercise price and takes 2017 minus 2016, appropriate for this task.",
        "The Final prose pairs 11 with 33.32 and 13 with 26.93, and lists the corresponding source spans. This is final-only evidence, not a preceding tool request.",
        "The Final states million-dollar totals and a positive 16.43 million increase; the share-count/price scales agree.",
        "Direct Final with arithmetic in public prose, but no calculate call. A correct answer does not establish an executed formula trajectory.",
    ),
    "R012": (
        "The aggregate three-year coal share is the ratio of the two three-year sums times 100.",
        "All six consumed variables explicitly bind coal and total revenues to the corresponding 2016, 2015 and 2014 table cells.",
        "All six variables declare millions and the ratio multiplies by 100; no unweighted average or mixed-year denominator.",
        "One complete expression with six bound inputs, followed by Final with tool:1. No multi-call result reuse or revision.",
    ),
    "R013": (
        "The Final-only expression (11*33.32)-(13*26.93) is the appropriate later-minus-earlier exercise-value difference.",
        "The public Final explanation explicitly pairs option counts and average exercise prices for 2017 and 2016 and cites the matching source spans.",
        "The Final prose states million-dollar annual totals and increase, consistent with million shares times USD/share.",
        "Direct Final, with calculation text and no actual tool execution. Its self-reported intermediate values are not calculator outputs.",
    ),
    "R014": (
        "The submitted expression computes 2015 agricultural revenue over total operating revenue times 100, which is applicable.",
        "Before the real calculation, the model explicitly names 3581 million agricultural and 21813 million total 2015 revenues and provides their source spans as metadata.",
        "Both amounts are explicitly in millions and the expression multiplies the ratio by 100.",
        "A valid calculation completed, but no Final was received; the second public raw entry is empty and the packet terminal is unknown_transport_or_condition. The tool result is not promoted into a model answer.",
    ),
    "R015": (
        "GE-held 997 million divided by 2017 total cash 7000 million, times 100, is applicable.",
        "The pre-call message explicitly identifies both financial roles, the 2017 date and the amounts 997 and 7.0 billion. Final source spans agree; the literal expression has no machine source binding.",
        "The pre-call explanation converts 7.0 billion to 7000 million and uses a percentage multiplier.",
        "One literal expression then Final. Since Final has no value, the actual quoted answer 14.24% supplies the published number under the registered fallback rule.",
    ),
    "R016": (
        "After-tax cost adds the signed negative tax benefit to compensation cost; the percent change uses the 2009 after-tax denominator.",
        "Four consumed exact-fraction variables bind cost2010, tax2010, cost2009 and tax2009 to the correct table spans and retain benefit signs.",
        "The same-scale monetary terms cancel in the growth ratio and the executed formula multiplies by 100. The Final ratio is expressed as a percentage, consistent with its value.",
        "One complete source-bound expression then Final linked to tool:1. Prose mentions intermediate costs but no separate tool calls occur.",
    ),
    "R017": (
        "The actual calculation correctly uses summed coal revenue divided by summed total operating revenue for 2014-2016, times 100.",
        "The pre-call message labels both aggregate roles and the six literal inputs; accompanying year/source annotations match the table. Those annotations were not consumed as named variables.",
        "The executed inputs are same-scale monetary values and the expression correctly converts the ratio to percent. This PASS concerns pre-execution handling only; Final later introduces a separate factor-100 publication error.",
        "One correct full calculation followed by inconsistent Final: value is a fraction near 0.149, yet unit is percent and answer/prose are near 14.91%. The value-first policy is retained; no repair, feedback or additional call.",
    ),
    "R018": (
        "The submitted two annual share-price products, subtracted in 2017-minus-2016 order, form the requested exercise-value difference.",
        "Although there is no message field, the pre-call unused variable annotations explicitly pair the four values with their year, role and source span. The executed expression uses literals, so this is finite semantic review rather than machine source binding.",
        "Pre-call annotations give million shares and USD per share; the literal products therefore use million USD and the final positive difference agrees.",
        "One literal calculation with informative unused annotations, then Final linked to tool:1. No separate calculation of intermediate totals was called.",
    ),
    "R019": (
        "Accrued interest/penalties over ending unrecognized tax benefits times 100 is applicable.",
        "The pre-call prose identifies 15.3 million and the table balance 139549 thousand; 15300 is the openly scaled numerator in the actual expression. Numeric-looking variable keys are unused annotations, not consumed bindings.",
        "Both substituted values are in thousands: the model scales 15.3 million to 15300 and retains 139549. The extracted table lacks an explicit thousand header; the rounded prose balance supports that scale inference.",
        "One full literal calculation and Final referencing tool:1. Visible unit conversion is part of that one call, not a separate result reuse.",
    ),
    "R020": (
        "The named expression computes the interest/penalties percentage of the ending balance.",
        "The model's source:t6c1 declaration omits the n0 numeric-span suffix, so the automatic numeric-source link is unestablished for the denominator. However the pre-call prose explicitly identifies 139549 as the FIN 48 ending balance and source t6c1 is the correct cell; a finite source-text/role review supports correspondence without silently repairing the machine binding.",
        "The actual denominator divides thousands by 1000 to align with the 15.3 million numerator, then multiplies by 100. The table scale is inferred using the adjacent rounded balance disclosure.",
        "One named calculation with one unresolved machine source identifier but explicit public financial correspondence; Final agrees. No retry or host binding repair occurred.",
    ),
    "R021": (
        "The bare 3581/21813*100 expression is numerically the applicable agricultural/total revenue share for this task. This limited formula check does not establish a public operand-to-source explanation.",
        "NOT_ESTABLISHED: the pre-call response has only a literal expression and an empty variables object, with no role, year or source declaration. Correct source IDs first appear in Final. Do not backdate them or infer a declared binding solely from matching numbers.",
        "NOT_ESTABLISHED: multiplying a bare ratio by 100 is visible, but the model does not identify the monetary units or roles of either operand before execution. Final's percent label is not pre-execution unit evidence.",
        "One bare literal expression, then a correct Final with source IDs. Actual arithmetic is verified, but pre-execution data/unit correspondence is not established from its public request; this is not a numeric task failure.",
    ),
    "R022": (
        "The pre-call message explicitly describes the 2015 agricultural/total operating revenue percentage and the actual expression implements it.",
        "Unused annotations map agricultural_products_2015=3581 and total_operating_revenues_2015=21813 to the correct source spans; the pre-call message gives the same roles. Literal execution is not a machine-bound named-variable trace.",
        "Both pre-call annotations declare millions and the literal ratio multiplies by 100.",
        "One annotated literal expression, then Final with 16.4% display and a more precise value. No result reuse or revision.",
    ),
    "R023": (
        "The Final-only public after-tax calculation correctly adds signed negative tax benefits and uses 2009 as the percent-change baseline.",
        "The Final response explicitly pairs 18.1/-6.3 with 2010 and 14.6/-5.2 with 2009 and gives their source spans. No preceding calculate request exists.",
        "Same-scale after-tax cost differences and the percentage multiplier are correct in the Final-only prose.",
        "Direct Final. Its result_id points to the public document, not an actual calculator result. The numeric answer is separately assessable, but the claimed result reference does not certify an executed calculation.",
    ),
    "R024": (
        "Coal revenue summed across 2014-2016 divided by total operating revenue summed over those years, times 100, is applicable.",
        "The six consumed variables explicitly associate coal and total revenues, years and the corresponding t4/t9 table numeric spans.",
        "The referenced table puts all six amounts on the same millions scale, which cancels; the public expression multiplies by 100. Unit strings are not required to infer this from the explicit source/role declarations.",
        "One source-bound aggregate expression and Final. No read_source, notebook, intermediate-result reuse or method revision is observed.",
    ),
}

SECONDARY = {
    "R001": ["16.42"], "R002": ["14.2"], "R003": ["10.97"],
    "R004": ["25.5"], "R005": ["14.24"], "R006": ["10.96"],
    "R007": ["25.5"], "R008": ["14.9"], "R009": ["14.24"],
    "R010": ["16.43"], "R011": ["16.43"], "R012": ["14.9"],
    "R013": ["16.43"], "R014": [], "R015": ["14.24"],
    "R016": ["25.5"], "R017": ["14.91284", "14.91"], "R018": ["16.43"],
    "R019": ["10.96"], "R020": ["10.96"], "R021": ["16.4"],
    "R022": ["16.4"], "R023": ["25.5"], "R024": ["14.9"],
}


def main():
    reviews = json.loads((ROOT / "assessment/review_template.json").read_text())
    private = json.loads((ROOT / "preparation/private/evaluation_targets.json").read_text())
    assert set(reviews) == set(JUDGMENTS) == set(SECONDARY)
    summary = []
    for rid in sorted(reviews):
        review = reviews[rid]
        packet = json.loads((ROOT / f"assessment/blinded/{rid}.json").read_text())
        assert packet["review_id"] == rid and packet["no_model_label_or_usage"] is True
        raw = {int(k): v for k, v in packet["raw_messages"].items()}
        fi = packet["first_final_index"]
        pre = {"response_index": 0, "quote": raw[0]}
        final = {"response_index": fi, "quote": raw[fi]} if fi is not None else None
        formula, variables, units, observation = JUDGMENTS[rid]
        for field, explanation in zip(REVIEW_FIELDS[:3], (formula, variables, units), strict=True):
            review[field] = {
                "status": "NOT_ESTABLISHED" if explanation.startswith("NOT_ESTABLISHED:") else "PASS",
                "explanation": explanation,
                "evidence": [copy.deepcopy(pre)],
            }
        # Actual calculation presence is read from the public packet, not guessed.
        review["answer_calculation_id"] = "tool:1" if packet["calculations"] else None
        alignment = "PASS"
        explanation = "Final's primary published number agrees with the actually executed tool:1 result at its display precision; direction and unit agree. An omitted result_id is not invented. This does not by itself establish correctness against the task reference."
        if not packet["calculations"]:
            alignment = "NOT_ESTABLISHED"
            explanation = "No actual calculate call exists; final-only arithmetic is not an execution/publication alignment certificate."
        if rid == "R023":
            alignment = "FAIL"
            explanation = "The Final result_id names a public_document, not an actual tool result; there was no calculate call. This is an invalid execution reference, separately reported from the correct numeric answer."
        if rid == "R014":
            alignment = "NOT_ESTABLISHED"
            explanation = "A calculation exists but no Final was published. Do not fill the answer from the correct tool result."
        if rid == "R017":
            alignment = "FAIL"
            explanation = "The actual tool result is approximately 14.912841 percent, but primary value 0.14912841106142192 with unit percent is 100 times smaller. A correct answer string cannot replace the value field."
        review["publication_alignment"] = {
            "status": alignment, "explanation": explanation,
            "evidence": [copy.deepcopy(final or pre)],
        }
        review["final_answer_consistency"] = {
            "status": "PASS",
            "explanation": "The actual Final's answer quantities, direction, period and units are internally consistent at each stated display precision. This internal check does not change the separate reference-based numeric score or certify a nonexistent tool result.",
            "evidence": [copy.deepcopy(final)] if final else [],
        }
        if rid == "R014":
            review["final_answer_consistency"].update(
                status="UNDETERMINED", explanation="No actual Final exists; publication consistency is unknown."
            )
        if rid == "R017":
            review["final_answer_consistency"].update(
                status="FAIL", explanation="The answer 14.91284% and prose 14.91% contradict primary value 0.14912841106142192 labelled percent. Preserve value priority and the factor-100 publication failure."
            )
        if rid == "R003":
            review["final_answer_consistency"]["explanation"] = (
                "Answer 10.97% and value 10.96774193548387 are internally consistent with the actual rounded-denominator calculation, with no sign or unit contradiction. They are not equivalent to the finer registered reference 15.3/139.549*100 at the frozen publication precisions; the independent numeric/secondary checks retain that failure."
            )
        if rid in {"R001", "R011", "R015"}:
            assert review["published_value"] is None
            review["published_value"] = {
                "R001": "16.41681566038601", "R011": "16.43", "R015": "14.24"
            }[rid]
            review["answer_override_evidence"] = [copy.deepcopy(final)]
        review["secondary_answer_values"] = [
            {"value": value, "unit": review["published_unit"], "evidence": copy.deepcopy(final)}
            for value in SECONDARY[rid]
        ]
        review["planning_observations"] = {
            "text": observation, "evidence": [copy.deepcopy(pre)] + ([copy.deepcopy(final)] if fi not in (None, 0) else [])
        }
        verify_quotes(review, raw)
        assert all(e["response_index"] == fi for e in review["final_answer_consistency"]["evidence"])
        public = json.loads((ROOT / f"preparation/public/{packet['task_key']}.json").read_text())
        iv, iu = final_number_and_unit(packet["raw_final"], public["question"])
        if iv is not None:
            assert str(iv) == str(review["published_value"]), "Never replace a present value"
        assert normalize_unit(iu) == normalize_unit(review["published_unit"])
        for item in review["answer_override_evidence"]:
            assert item["response_index"] == fi and str(review["published_value"]) in item["quote"]
        score = reviewed_answer_score(answer_score(review["published_value"], review["published_unit"], private[packet["task_key"]]), review)
        checks = []
        for secondary in review["secondary_answer_values"]:
            assert secondary["value"] in secondary["evidence"]["quote"]
            checks.append(display_compatible(score["reference_exact_value"], review["published_unit"], secondary["value"], secondary["unit"]))
        if any(c is False for c in checks):
            score["task_answer_status"] = "FAIL"
        if packet["terminal"] != "model_final":
            score["task_answer_status"] = "UNDETERMINED" if packet["terminal"].startswith("unknown") else "FAIL"
        trace = trace_checks(packet, review, score)
        expected = "FAIL" if rid in {"R003", "R017"} else "UNDETERMINED" if rid == "R014" else "PASS"
        assert score["task_answer_status"] == expected, rid
        expected_trace = rid not in {"R003", "R005", "R011", "R013", "R014", "R017", "R021", "R023"}
        assert trace["formula_driven_trace_verified"] == expected_trace, rid
        summary.append({"review_id": rid, "task_key": packet["task_key"], "answer": score["task_answer_status"], "trace": trace["formula_driven_trace_verified"], "secondary_checks": checks})
    print(json.dumps({"masked_only_validation": summary}, ensure_ascii=False), file=sys.stderr)
    target = ROOT / "review/masked_reviews.json"
    assert not target.exists(), "Never overwrite a review input, especially after label decoding"
    print("*** Begin Patch\n*** Add File: " + str(target))
    for line in json.dumps(reviews, ensure_ascii=False, sort_keys=True, indent=2).splitlines():
        print("+" + line)
    print("*** End Patch")


if __name__ == "__main__":
    main()
