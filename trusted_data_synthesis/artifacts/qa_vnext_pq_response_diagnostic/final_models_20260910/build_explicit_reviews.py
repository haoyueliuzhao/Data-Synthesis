"""Materialize the root agent's six explicit post-generation L1 reviews.

This is a case-bound transcription of the six fully read public trajectories,
not an automatic semantic evaluator, not blinded and not independent expert review.
It never invokes a model or changes any original trace, tool, target or grade.
"""

import json
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_pq_response_diagnostic.plan import (
    OUTPUT,
    TRAINED,
    read_json,
    record,
    reference,
    require,
)

AUTHOR = "Codex root explicit offline semantic review; non-blind, not independent financial expert"
BAD_SOURCE_VARIANTS = {"P_11", "Q_11", "P_29", "Q_29", "Q_47"}
BAD_SOURCES = {
    "balance_end_2006": "source:t4c1n0",
    "balance_begin_2006": "source:t5c1n0",
}
CORRECT_SOURCES = {
    "balance_end_2006": "source:t8c1n0",
    "balance_end_2005": "source:t4c1n0",
}


def main():
    root = Path.cwd().resolve()
    output = root / OUTPUT
    templates = read_json(output / "assessment/review_templates.json")
    for variant in TRAINED:
        audit = read_json(output / "assessment/audits" / f"{variant}.json")
        raw0, raw1 = audit["raw_messages"]["0"], audit["raw_messages"]["1"]
        first, terminal = json.loads(raw0), json.loads(raw1)
        final = json.loads(raw1, parse_int=str, parse_float=str)["final"]
        require(
            audit["model_requests"] == 2
            and audit["tool_calls"] == 1
            and audit["first_final_index"] == 1
            and len(audit["calculations"]) == 1
            and audit["calculations"][0]["call_id"] == "tool:1"
            and audit["calculations"][0]["actual_exact_value"] == "18"
            and first["arguments"]["expression"] == "134 - 116",
            "manual_review.exact_observed_session_not_general_rule",
        )
        sources = first["arguments"]["sources"]
        bad = variant in BAD_SOURCE_VARIANTS
        require(
            sources == (BAD_SOURCES if bad else CORRECT_SOURCES),
            "manual_review.exact_observed_source_declarations",
        )
        pre = {"response_index": 0, "quote": first["message"]}
        call = {"response_index": 0, "quote": raw0}
        ending = {"response_index": 1, "quote": raw1}
        review = templates["reviews"][variant]
        review["author"] = AUTHOR
        review["calculation"] = {
            "call_id": "tool:1",
            "unit": "USD_million",
            "direction_multiplier": 1,
            "evidence": [pre, call],
            "explanation": (
                "Actual literal 134-116 is positive 18. The pre-call prose identifies the "
                "2006 closing and opening/same-as-2005-closing balances in the original "
                "restructuring table. Its p1 says millions and dollar markers establish "
                "the money scale. No explicit unit is present in this calculate request; "
                "this is finite offline interpretation from the already public same-scale "
                "table, not later-Final backfill. Contradictory source IDs are separately FAIL."
            ),
        }
        review["formula_applicability"] = {
            "status": "PASS",
            "evidence": [pre, call],
            "explanation": (
                "The public relation is 2006 closing less 2006 opening, equivalently 2005 "
                "closing. Actual literal operands 134 and 116 have that ordered relation; "
                "the expression was executed successfully. Formula applicability does not "
                "certify the separately reviewed explicit provenance declarations."
            ),
        }
        review["variable_correspondence"] = {
            "status": "FAIL" if bad else "PASS",
            "evidence": [call],
            "explanation": (
                "FAIL: the model explicitly assigns end-2006=134 to source:t4c1n0, whose "
                "actual value is 116 and role is end-2005; it assigns begin-2006=116 to "
                "source:t5c1n0, whose actual value is 155 and role is expensed-in-2006. "
                "This is an actual value/financial-role contradiction, not omitted n0 or "
                "a harmless source-label style. Correct prose/literal arithmetic does not "
                "authorize silently rebinding the model to t8c1n0/t4c1n0. No later repair occurs."
            )
            if bad
            else (
                "PASS: explicit source:t8c1n0 is 134, balance at December 31 2006; "
                "source:t4c1n0 is 116, balance at December 31 2005. Pre-call roles, literal "
                "operands and Final source declarations agree with those actual public facts."
            ),
        }
        review["unit_handling"] = {
            "status": "PASS",
            "evidence": [pre, call],
            "explanation": (
                "The two selected balance roles and literal amounts are in the same original "
                "dollar-million table; subtraction has no scaling or percent conversion. "
                "The model did not explicitly write a pre-call unit. Apply the unchanged "
                "finite source-unit interpretation policy, not a new required-field gate. "
                "Source-identity contradictions remain a separate variable-correspondence FAIL."
            ),
        }
        if variant == "P_11":
            require(final == "18", "manual_review.original_scalar_Final")
            review["publication"] = {
                "value": "18",
                "unit": None,
                "direction_multiplier": 1,
                "evidence": [ending],
                "explanation": (
                    "Actual first Final is only the scalar string 18. The sibling message "
                    "says million dollars, but it is outside Final and cannot fill missing "
                    "Final scale under the frozen Final-only policy. Preserve unresolved "
                    "quantity, not a determinate financial error and not an inferred PASS."
                ),
            }
            review["publication_alignment"] = {
                "status": "UNDETERMINED",
                "evidence": [ending],
                "explanation": (
                    "The bare Final number equals the calculator's 18, but its Final-only "
                    "unit/scale is unresolved, so transfer of the same physical quantity "
                    "is not established by numeric equality alone."
                ),
            }
            review["final_answer_consistency"] = {
                "status": "UNDETERMINED",
                "evidence": [ending],
                "explanation": (
                    "Final itself contains only 18 without a unit or quantity description. "
                    "Do not substitute sibling response.message for the actual Final."
                ),
            }
            review["secondary"] = []
        else:
            require(
                isinstance(final, dict)
                and final["value"] == "18"
                and final["unit"] == "million dollars"
                and final["result_id"] == "tool:1",
                "manual_review.original_structured_Final",
            )
            require(terminal["final"]["sources"] == sources, "manual_review_same_Final_sources")
            review["publication"] = {
                "value": final["value"],
                "unit": final["unit"],
                "direction_multiplier": 1,
                "evidence": [ending],
                "explanation": (
                    "Retain exact original Final.value lexical 18 and explicit Final.unit "
                    "million dollars. Positive signed net change/increase is stated in Final. "
                    "Source contradictions do not replace the separately scored number."
                ),
            }
            review["publication_alignment"] = {
                "status": "PASS",
                "evidence": [ending],
                "explanation": (
                    "Actual successful tool:1 produces 18 in the established million-dollar "
                    "scale. Final explicitly consumes tool:1 and publishes that same 18 "
                    "million-dollar quantity. This is transfer alignment, not source validity."
                ),
            }
            review["final_answer_consistency"] = {
                "status": "PASS",
                "evidence": [ending],
                "explanation": (
                    "Actual Final.value, unit and answer prose agree on the positive 18 "
                    "million-dollar change during 2006. The duplicated answer quantity has "
                    "the same display precision. Conflicting source IDs are explicitly "
                    "assessed in variable_correspondence, not silently repaired here."
                ),
            }
            review["secondary"] = [
                {
                    "value": "18",
                    "unit": "million dollars",
                    "direction_multiplier": 1,
                    "evidence": [{"response_index": 1, "quote": final["answer"]}],
                    "explanation": (
                        "The actual Final.answer repeats 18 million dollars; "
                        "same secondary quantity."
                    ),
                }
            ]
        description = (
            "Actual executed formula structure is balance difference 134-116. No period "
            "movement sum and no second-route calculation occurs. "
            + (
                "Its explicit source bindings are contradictory, so this is not an admitted "
                "valid source-grounded D trajectory."
                if bad
                else "The actual t8c1n0/t4c1n0 bindings and Final tool:1 consumption are coherent."
            )
        )
        review["route_observation"] = {
            "description": description,
            "evidence": [call],
            "mechanistic_not_utility": True,
        }
        route = templates["routes"][variant]
        route.update(
            author=AUTHOR,
            observed_executed_structure="balance_difference",
            explanation=description,
            final_consumed_call_id=None if variant == "P_11" else "tool:1",
            final_evidence=[] if variant == "P_11" else [ending],
            components=[
                {
                    "structure": "balance_difference",
                    "call_id": "tool:1",
                    "actual_expression": "134 - 116",
                    "source_fact_ids": ["source:t8c1n0", "source:t4c1n0"],
                    "source_fact_ids_role": (
                        "Reference facts defining the observed 134/116 "
                        "balance-difference structure; "
                        "NOT replacement of the model's actual declarations below."
                    ),
                    "model_declared_sources": sources,
                    "model_declared_source_fact_ids": sorted(set(sources.values())),
                    "model_source_binding_status": "FAIL" if bad else "PASS",
                    "public_relation_and_binding_explanation": (
                        review["formula_applicability"]["explanation"]
                        + " "
                        + review["variable_correspondence"]["explanation"]
                    ),
                    "evidence": [pre, call],
                }
            ],
        )
    store = DurableStore(output / "manual_review")
    store.json("reviews.json", templates)
    provenance = record(
        "explicit_six_L1_review_provenance",
        author=AUTHOR,
        audit_ids={v: templates["reviews"][v]["audit_id"] for v in TRAINED},
        builder_reference=reference(root, OUTPUT + "/build_explicit_reviews.py"),
        all_six_complete_raw_assistant_trajectories_read=True,
        original_public_L1_and_source_facts_read=True,
        actual_source_conflicts_not_repaired=True,
        route_structure_reference_facts_are_not_claimed_model_bindings=True,
        original_Final_only_and_numeric_policy_unchanged=True,
        new_model_or_teacher_calls=0,
    )
    store.json("provenance.json", provenance)
    seal_directory(
        store, kind="pq_response_explicit_review_manifest", provenance_id=provenance["id"]
    )
    print(provenance["id"], flush=True)


if __name__ == "__main__":
    main()
