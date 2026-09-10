"""Correct two ancillary old-panel labels from existing evidence before assessment.

This does not change any scorer, Student input, runtime, qualification rule or
old grade. The frozen source remains unchanged. This wrapper is disclosed and
bound alongside the ancillary metadata correction, not hidden as the frozen CLI.
"""

from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_pq_response_diagnostic import analysis
from trusted_synthesis.experiments.finance_qa_vnext_pq_response_diagnostic.plan import (
    OUTPUT,
    PARENT,
    read_json,
    record,
    reference,
    require,
)


def main():
    root = Path.cwd().resolve()
    old_reviews = read_json(root / PARENT / "closeout/reviews.json")["reviews"]
    require(
        "541/2859*100" in old_reviews["P_11/R2"]["formula_applicability"]["explanation"],
        "side_correction.actual_TDR_share_evidence",
    )
    require(
        "expense" in old_reviews["P_29/R6"]["variable_correspondence"]["explanation"]
        and "statutory capital" in old_reviews["P_29/R6"]["variable_correspondence"]["explanation"],
        "side_correction.actual_amortization_provenance_evidence",
    )
    replacements = {
        "11/R2": (
            ["formula"],
            "P uses commercial loans / total TDR, 541/2859*100; Q inverts that share.",
        ),
        "29/R6": (
            ["source", "publication"],
            "Both average amortization expenses, but P's Final cites statutory-capital "
            "facts as the expense sources; Q has coherent expense-source binding.",
        ),
    }
    store = DurableStore(root / OUTPUT / "side_annotation_correction")
    correction = record(
        "offline_old_panel_label_correction",
        original={key: analysis.OLD_CHANGED_CASES[key] for key in replacements},
        corrected=replacements,
        reason=(
            "The prefilled side descriptions incorrectly named R2 as interest/income "
            "and R6 as surplus. Existing raw reviews show TDR commercial share and "
            "three-year amortization expense. Only these ancillary names are corrected."
        ),
        old_review_reference=reference(root, PARENT + "/closeout/reviews.json"),
        wrapper_reference=reference(root, OUTPUT + "/assess_with_side_labels.py"),
        inference_source_configuration_and_inputs_unchanged=True,
        old_scores_unchanged=True,
        scoring_generation_and_qualification_functions_unchanged=True,
        correction_based_only_on_preexisting_reviews_not_new_L1_or_NLL_results=True,
        no_new_Student_calls=True,
    )
    store.json("correction.json", correction)
    analysis.OLD_CHANGED_CASES.update(replacements)
    result = analysis.assess(root)
    store.json("assessment_binding.json", {"assessment_id": result["id"]})
    seal_directory(
        store, kind="pq_response_side_label_correction_manifest", correction_id=correction["id"]
    )
    print(result["id"], flush=True)


if __name__ == "__main__":
    main()
