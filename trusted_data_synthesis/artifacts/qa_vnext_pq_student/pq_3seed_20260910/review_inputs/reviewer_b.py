"""Materialize 36 manually inspected, post-generation Codex-agent reviews.

This is a finite review transcription script, not a general automatic semantic
grader. The agent read all assigned original public messages and all six complete
source pages before recording the task-specific judgments below. Exact evidence
is copied from sealed audits; no original Final, source, or executable is edited.
The frozen evaluator is used only for in-memory validation before exclusive output.
"""

import copy
import json
from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    OUTPUT,
    encode,
    read_json,
    sha,
)

VARIANTS = ("P_11", "Q_11", "P_29", "Q_29", "P_47", "Q_47")
TASKS = ("T4", "T5", "T6", "R4", "R5", "R6")
AUTHOR = (
    "Codex agent /root/trace_wiring_tests; offline post-generation review; "
    "not an independent human financial expert"
)


def quote(audit, index):
    return {"response_index": index, "quote": audit["raw_messages"][str(index)]}


def field(review, name, status, evidence, explanation):
    review[name] = {
        "status": status,
        "evidence": evidence,
        "explanation": explanation,
    }


def secondary(review, value, unit, evidence, direction=1):
    review["secondary"].append(
        {
            "value": value,
            "unit": unit,
            "direction_multiplier": direction,
            "evidence": evidence,
            "explanation": (
                "Separately printed answer quantity inside the original first Final; "
                "checked at its own display precision, never substituted for Final.value."
            ),
        }
    )


def review_one(key, audit, template):
    variant, task = key.split("/")
    review = copy.deepcopy(template)
    review["author"] = AUTHOR
    review["review_scope_notes"] = []
    before = [quote(audit, 0)]
    if audit["first_final_index"] is None:
        assert task == "R5" and variant in {"P_11", "Q_11"}
        assert audit["terminal"] == "response_budget_exhausted"
        assert not audit["calculations"] and not audit["calculation_requests"]
        for name in evaluate.FIELDS:
            review[name]["explanation"] = (
                "No first Final and no actual calculator invocation; retain the "
                "frozen no-Final UNDETERMINED template, not a recovered answer."
            )
        review["route_observation"] = {
            "description": (
                "All 32 admitted responses contain an undispatched top-level calculate "
                "object rather than tool=calculate. The declared three-year mean is "
                "not an executed tool result or a delivered Final."
            ),
            "evidence": [quote(audit, 0), quote(audit, 31)],
            "mechanistic_not_utility": True,
        }
        return review

    last = [quote(audit, audit["first_final_index"])]
    final = evaluate._lexical_final(audit)
    publication = review["publication"]
    publication.update(
        direction_multiplier=1,
        evidence=last,
        explanation=(
            "Original first Final.value lexical number and original explicit Final.unit "
            "are retained; positive multiplier preserves the published signed number."
        ),
    )
    if key == "Q_11/T4":
        assert "value" not in final and "unit" not in final
        publication.update(
            value="-25%",
            unit="%",
            explanation=(
                "No value/unit keys exist. Extract the complete original -25% token "
                "and its percent symbol from the actual first Final.answer only."
            ),
        )
    if key == "Q_29/R6":
        assert "value" not in final and "unit" not in final
        publication.update(
            value="77",
            unit="million USD",
            explanation=(
                "No value/unit keys exist. First Final.answer explicitly publishes "
                "77 million USD; extract that original quantity, not the tool output."
            ),
        )

    if audit["calculations"]:
        assert len(audit["calculations"]) == 1
        calculation = audit["calculations"][0]
        assert calculation["call_id"] == "tool:1" and calculation["response_index"] == 0
        calc_unit = "%" if task in {"T4", "R4"} else "million dollars"
        if task == "R6":
            calc_unit = (
                "million U.S. dollars"
                if variant in {"P_47", "Q_47"}
                else "million dollars"
                if variant == "P_29"
                else "million USD"
            )
        review["calculation"].update(
            call_id="tool:1",
            unit=calc_unit,
            direction_multiplier=1,
            evidence=before,
            explanation=(
                "Interpret the actually executed expression in the unit established "
                "by this pre/same-call assistant statement and arguments. Preserve "
                "the actual signed result; no later-Final sign repair."
            ),
        )

    # All judgments below are finite, manually inspected case decisions. They do
    # not infer model financial semantics from correctness of the reference number.
    if task == "T4":
        field(
            review,
            "formula_applicability",
            "PASS",
            before,
            "The pre-call statement gives ending minus opening, divided by opening "
            "and multiplied by 100, for the requested unrecognized-tax-benefit change.",
        )
        field(
            review,
            "variable_correspondence",
            "PASS",
            before,
            "The model explicitly assigns 224 to April 1 2007 and 168 to March 31 "
            "2008, matching the table balances, not interest or adoption adjustments.",
        )
        field(
            review,
            "unit_handling",
            "PASS",
            before,
            "Both amounts share the same disclosed thousand-dollar scale, which "
            "cancels in the ratio; the model's dollar shorthand does not introduce "
            "mixed scales. Multiplication by 100 publishes percent.",
        )
        field(
            review,
            "publication_alignment",
            "PASS",
            before + last,
            "The actual calculator result -25 is published as -25 percent, without "
            "a unit conversion or a change in sign.",
        )
        field(
            review,
            "final_answer_consistency",
            "PASS",
            last,
            "The first Final unambiguously publishes the signed percentage decline; "
            "its answer prose, where present, agrees with its numeric field.",
        )
        if "value" in final:
            secondary(review, "-25%", "%", last)
        if variant == "P_29":
            review["review_scope_notes"].append(
                "Final.sources includes source:t2c0n1, the 2008 year token, not the "
                "224 opening amount. Pre-call dates and values are nevertheless "
                "explicitly and correctly assigned; this Final citation defect does "
                "not fabricate a source-ID validity requirement for literal arithmetic."
            )
        route = "Direct reported opening/ending-balance percentage calculation."

    elif task == "T5":
        field(
            review,
            "formula_applicability",
            "PASS",
            before,
            "The model defines net change as December 31 balance minus January 1 "
            "balance and executes 70-53; no interest/subset amounts are added.",
        )
        field(
            review,
            "variable_correspondence",
            "PASS",
            before,
            "The pre-call statement explicitly assigns 53 million to January 1 "
            "and 70 million to December 31 2007, matching the actual table roles. "
            "Those literal operands, not the malformed source labels, are executed.",
        )
        field(
            review,
            "unit_handling",
            "PASS",
            before,
            "Both annual boundary balances are explicitly in dollar millions; "
            "their difference retains USD_million.",
        )
        field(
            review,
            "publication_alignment",
            "PASS",
            before + last,
            "The actual tool result 17 is published as 17 million dollars.",
        )
        field(
            review,
            "final_answer_consistency",
            "PASS",
            last,
            "The numeric field and answer prose agree on the 2007 net increase; "
            "there is no contradictory decrease or percent claim.",
        )
        secondary(review, "17", "million dollars", last)
        review["review_scope_notes"].append(
            "Both arguments.sources and Final.sources use source:t5c1 at cell "
            "granularity and source:t0c1n1, which is not a catalog numeric-span ID. "
            "The referenced cells and explicit dates/amounts identify 70 and 53 "
            "correctly; these locators are not represented as verified read_source calls."
        )
        route = "Direct reported December-minus-January balance difference."

    elif task == "T6":
        negative_magnitude = variant in {"Q_11", "P_29", "Q_29", "P_47"}
        if negative_magnitude:
            publication.update(
                direction_multiplier=-1,
                explanation=(
                    "Keep original nonnegative value 191. The actual first Final "
                    "contains decrease, so the published quantity is a 191-million "
                    "decline, interpreted as signed -191; not inferred from gold."
                ),
            )
        field(
            review,
            "formula_applicability",
            "FAIL",
            before,
            "The model frames the task as 2012 versus 2011 net revenue, but "
            "actually executes 2045-1854 (prior minus current). No pre/same-call "
            "decrease/loss/magnitude semantics establish a negative orientation "
            "for that positive result. A later Final cannot repair this formula.",
        )
        field(
            review,
            "variable_correspondence",
            "PASS",
            before,
            "The model correctly assigns 2045 million to 2011 and 1854 million "
            "to 2012 Wholesale Commodities net revenue. The problem is operand "
            "orientation, not selection of another segment or financial object.",
        )
        field(
            review,
            "unit_handling",
            "PASS",
            before,
            "The two annual net-revenue values are in the same explicitly stated "
            "dollar-million scale; this is a monetary annual-flow change.",
        )
        field(
            review,
            "publication_alignment",
            "PASS" if variant == "Q_47" else "FAIL",
            before + last,
            "Q_47 preserves the executed positive 191 in its positive Final; the "
            "sign is wrong for the task but not changed at publication."
            if variant == "Q_47"
            else "The actually executed result is +191 with no established negative "
            "orientation before/same-call; the published signed -191 or explicit "
            "decrease of 191 is therefore not the same established quantity.",
        )
        field(
            review,
            "final_answer_consistency",
            "FAIL" if variant == "Q_47" else "PASS",
            last,
            "The first Final publishes positive 191 as the net change without "
            "decrease wording or a minus sign, contrary to the current-minus-prior "
            "quantity requested. No direction is backfilled from another response."
            if variant == "Q_47"
            else "The first Final itself unambiguously expresses the signed decline, "
            "either as -191 or as nonnegative 191 paired with decrease. This does "
            "not certify the earlier calculator formula.",
        )
        if variant == "Q_11":
            secondary(review, "191", "million", last, direction=-1)
        review["review_scope_notes"].append(
            "Selected calculation retains direction_multiplier=+1. The pre-call "
            "message names both years but never calls the operation a decrease "
            "magnitude; later response-level message text is not an orientation "
            "license for the earlier call. Only quantities within Final are secondary."
        )
        route = "Reported annual net-revenue endpoints with reversed executed subtraction."

    elif task == "R4":
        if variant == "P_11":
            field(
                review,
                "formula_applicability",
                "PASS",
                before,
                "The publicly stated general percentage-change formula uses the "
                "prior year as denominator; the financial input assignment fails separately.",
            )
            field(
                review,
                "variable_correspondence",
                "FAIL",
                [quote(audit, 0), quote(audit, 3)],
                "Despite initially mentioning FCF 1415/699, actual requests bind "
                "4105/3204 from the cash-provided-by-operating-activities row and "
                "later call those CFO amounts free cash flow. They omit the "
                "company-defined adjustments, investing cash use, and dividends.",
            )
            field(
                review,
                "unit_handling",
                "PASS",
                before,
                "The stated year-over-year ratio of same-scale dollar millions "
                "times 100 has percent units; the financial metric selection is wrong.",
            )
            field(
                review,
                "publication_alignment",
                "FAIL",
                last,
                "Four malformed colon/dot expressions produced no successful "
                "calculator result. The Final claims manual 28.11 percent from "
                "CFO 4105/3204, not the declared company FCF endpoints.",
            )
            field(
                review,
                "final_answer_consistency",
                "FAIL",
                last,
                "The first-Final response explicitly calls CFO 4105/3204 free cash "
                "flow and publishes their approximate percentage, an inapplicable "
                "financial quantity for this question.",
            )
            review["review_scope_notes"].append(
                "The four calculation_requests are errors and calculations is empty; "
                "no result_id is selected or reconstructed as a real tool result."
            )
            route = (
                "Repeated invalid source-path arithmetic, followed by a manual CFO-as-FCF answer."
            )
        else:
            field(
                review,
                "formula_applicability",
                "PASS",
                before,
                "The model uses the reported company FCF endpoints in "
                "(2010-2009)/2009*100, not a substitute generic CFO-minus-capex definition.",
            )
            field(
                review,
                "variable_correspondence",
                "PASS",
                before,
                "The pre-call message explicitly binds 1415 million to 2010 FCF "
                "and 699 million to 2009 FCF; the executed expression contains "
                "exactly those literal inputs.",
            )
            field(
                review,
                "unit_handling",
                "PASS",
                before,
                "The original same-scale monetary endpoints cancel and the "
                "explicit factor 100 produces percent, as the model states.",
            )
            field(
                review,
                "publication_alignment",
                "PASS",
                before + last,
                "The actual result 71600/699 is published with the original "
                "long decimal value; 102.43% is a separate rounded answer display.",
            )
            field(
                review,
                "final_answer_consistency",
                "PASS",
                last,
                "The first Final publishes a positive percentage increase; the "
                "long value and the two-decimal percent answer are compatible "
                "at their respective display precision.",
            )
            secondary(review, "102.43%", "%", last)
            review["review_scope_notes"].append(
                "arguments.variables includes an extraneous value around 101.71. "
                "The literal expression references no variable names and consumes "
                "none of this mapping; the actual independently audited result is "
                "71600/699. This pre-call unused field is not a Final secondary answer."
            )
            route = "Direct reported company-FCF endpoint percentage calculation."

    elif task == "R5":
        assert not audit["calculations"] and not audit["calculation_requests"]
        field(
            review,
            "formula_applicability",
            "PASS",
            before,
            "The model publicly proposes the correct equal-weight three-year "
            "operating-profit mean, including 2014, 2015, and 2016.",
        )
        field(
            review,
            "variable_correspondence",
            "PASS",
            before,
            "The initial statement explicitly maps MFC profit 1344/1282/1018 to "
            "2014/2015/2016, respectively, matching the actual MFC profit row.",
        )
        field(
            review,
            "unit_handling",
            "PASS",
            before,
            "All three declared annual profits and the final mean use millions.",
        )
        field(
            review,
            "publication_alignment",
            "FAIL",
            before + last,
            "The top-level calculate object is not an admitted tool call. The "
            "published number is also inconsistent with the model's own "
            "(1344+1282+1018)/3 relationship; no real execution supports it.",
        )
        field(
            review,
            "final_answer_consistency",
            "PASS",
            last,
            "Within the original Final, answer and value agree on one explicitly "
            "million-denominated mean; they are numerically wrong, not ambiguous "
            "or mutually contradictory displays. Numeric scoring remains separate.",
        )
        secondary(review, final["answer"], "million", last)
        review["review_scope_notes"].append(
            "No actual calculator request exists: a top-level calculate key is "
            "ordinary recorded public content. Where Final.result_id says "
            "calculate:expression, it is not a real tool result reference. Final "
            "source IDs pointing to t0c* are year headers, not profit amounts; "
            "the earlier explicit year/profit assignment is recorded separately."
        )
        route = (
            "Correct public mean specification in an undispatched calculate object, "
            "then wrong Final."
        )

    elif task == "R6":
        field(
            review,
            "formula_applicability",
            "PASS",
            before,
            "The pre-call message specifies average amortization expense for "
            "2006-2008 and the actual expression averages the three annual amounts.",
        )
        conflicting_sources = variant in {"P_11", "Q_11"}
        final_source_conflict = variant in {"P_29", "P_47", "Q_47"}
        field(
            review,
            "variable_correspondence",
            "FAIL" if conflicting_sources or final_source_conflict else "PASS",
            before + last if final_source_conflict else before,
            "The actual call explicitly maps 90/77/64 to source:t1c1n0/t1c2n0/"
            "t1c3n0, which actually contain statutory capital 7001/8579/7605. "
            "These are source/value/financial-object contradictions, not mere "
            "ID syntax defects; the reviewer must not replace them with q8 IDs."
            if conflicting_sources
            else "The original call has the correct three expense literals, but the "
            "Final then claims sources t1c6n0/t1c5n0/t1c4n0 as the basis of this "
            "three-year expense answer. Those are statutory capital 4431/5321/5337, "
            "not the claimed expense inputs. This unresolved published provenance "
            "contradiction prevents a complete verified trajectory without "
            "changing the separately evaluated numeric answer."
            if final_source_conflict
            else "The pre-call expense/2006-2008 scope and literal 90/77/64 identify "
            "the three actual annual tangible-property expenses in q8. No "
            "contradictory source mapping is supplied in this calculator call; "
            "an average does not depend on operand order.",
        )
        field(
            review,
            "unit_handling",
            "PASS",
            before,
            "The original arguments explicitly put all three expense values in "
            "million US dollars and averaging retains that scale. For the literal "
            "million U.S. dollars alias, semantic clarity does not extend the "
            "frozen parser's finite alias list.",
        )
        field(
            review,
            "publication_alignment",
            "PASS",
            before + last,
            "The actual tool result 77 is published as the same million-dollar "
            "mean. This verifies numerical publication transfer, not the accuracy "
            "of contradictory source declarations where present.",
        )
        field(
            review,
            "final_answer_consistency",
            "PASS",
            last,
            "The first Final's number and any answer prose agree on the average "
            "annual amortization expense; no future forecast or other object is "
            "introduced. Provenance defects remain a separate trace judgment.",
        )
        if "value" in final and "answer" in final:
            secondary(review, "77", final["unit"], last)
        if conflicting_sources:
            review["review_scope_notes"].append(
                "Both actual-call sources and Final.sources point to statutory "
                "capital instead of q8 amortization expenses. variable_correspondence "
                "FAIL preserves that substantive contradiction while the separately "
                "published task number may still be correct."
            )
        if variant in {"P_29", "P_47", "Q_47"}:
            review["review_scope_notes"].append(
                "Final-only sources t1c6n0/t1c5n0/t1c4n0 point to statutory capital "
                "4431/5321/5337. The earlier actual call had no such source mapping "
                "and specified the amortization-expense scope plus correct three "
                "literal inputs. The Final's claimed supporting sources create an "
                "unresolved trajectory-level provenance contradiction, so the "
                "reviewed variable_correspondence is FAIL. The audit of the earlier "
                "literal calculation is not rewritten and the number is scored separately."
            )
        if variant in {"P_47", "Q_47"}:
            review["review_scope_notes"].append(
                "Keep explicit original Final.unit='million U.S. dollars'. It is "
                "not in the frozen normalize_unit alias table. Natural-language "
                "understanding is not used to overwrite it or expand the evaluator; "
                "the resulting quantity score remains UNDETERMINED."
            )
        route = "Three-year tangible-property amortization expense mean from literal inputs."
    else:
        raise AssertionError(key)

    review["route_observation"] = {
        "description": route,
        "evidence": before + last,
        "mechanistic_not_utility": True,
    }
    return review


def main():
    root = Path(__file__).resolve().parents[5]
    output = root / OUTPUT
    destination = output / "review_inputs/reviewer_b.json"
    assert not destination.exists(), "Refuse to overwrite an existing review artifact"
    assert read_json(output / "preparation/evaluation_policy.json") == evaluate.policy()
    templates = read_json(output / "assessment/review_templates.json")["reviews"]
    reviews, grades, inputs = {}, {}, []
    for variant in VARIANTS:
        for task in TASKS:
            key = f"{variant}/{task}"
            audit_path = output / f"assessment/audits/{key}.json"
            packet_path = output / f"assessment/packets/{key}.json"
            audit = read_json(audit_path)
            packet = read_json(packet_path)
            assert audit == packet["audit"]
            assert templates[key]["audit_id"] == audit["id"]
            reviews[key] = review_one(key, audit, templates[key])
            grades[key] = evaluate.qualify(
                audit,
                reviews[key],
                packet["public"],
                packet["private_reference_for_offline_review_only"],
            )
            inputs.append(
                {
                    "key": key,
                    "audit_id": audit["id"],
                    "audit_sha256": sha(audit_path.read_bytes()),
                    "packet_sha256": sha(packet_path.read_bytes()),
                }
            )
    assert len(reviews) == len(grades) == 36
    rows = [
        {
            "key": key,
            "task_answer_status": grade["task_answer_status"],
            "trace_status": grade["trace_status"],
            "complete_verifiable_trajectory": grade["complete_verifiable_trajectory"],
            "terminal": grade["terminal"],
        }
        for key, grade in grades.items()
    ]
    result = {
        "author": AUTHOR,
        "scope": "36 trained-variant sessions only; B0 reviewed by parent separately",
        "policy_id": evaluate.policy()["id"],
        "reviews": reviews,
        "input_bindings": inputs,
        "prequalification": {
            "all_36_qualify_calls_succeeded_before_output": True,
            "answer_counts": dict(Counter(r["task_answer_status"] for r in rows)),
            "trace_counts": dict(Counter(r["trace_status"] for r in rows)),
            "rows": rows,
        },
        "source_code_or_frozen_artifacts_modified": False,
        "new_model_or_provider_calls": 0,
        "independent_human_expert_review": False,
    }
    with destination.open("xb") as stream:
        stream.write(encode(result))
    print(json.dumps(result["prequalification"], indent=2))
    print(str(destination))


if __name__ == "__main__":
    main()
