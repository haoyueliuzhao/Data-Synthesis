"""Separate prospective task scopes, not retrospective rescoring or trajectory classes."""

from .plan import record, require


def clarification(sessions):
    originals = [s for s in sessions.values() if s["row"]["task_key"] == "N3"]
    require(len(originals) == 4, "N3.four_original_registrations")
    public = originals[0]["public"]
    return record(
        "N3_task_scope_clarification",
        original_task_id=public["task_id"],
        original_question=public["question"],
        original_source_document_id=public["id"],
        original_temporal_source_segment=public["segments"]["q16"],
        original_frozen_target={"value": "68.9", "unit": "USD_billion"},
        original_rows=[s["row"] for s in originals],
        original_final_and_actual_calls=[
            {
                "session_label": s["row"]["label"],
                "Final": s["result"]["final"],
                "actual_calls": [
                    t["event"]["tool_call"] for t in s["turns"] if t["event"]["tool_call"]
                ],
                "no_host_added_execution": True,
            }
            for s in originals
        ],
        original_outcomes_preserved=True,
        interpretation=(
            "Two separately dated asset snapshots support annual totals; the original wording "
            "does not uniquely establish an across-year sum. The arithmetic sum is not a "
            "deduplicated cumulative asset stock."
        ),
        proposed_new_versions=[
            {
                "proposed_version": "N3_per_year_totals_v2_draft",
                "question": (
                    "Report separately, in billions of dollars, the total fair value of assets "
                    "segregated for the benefit of securities and futures brokerage customers "
                    "as of December 31, 2010 and as of December 31, 2009."
                ),
                "evaluation_scope": "two named annual snapshot totals, one for each specified year",
                "prospectively_validated": False,
            },
            {
                "proposed_version": "N3_snapshot_arithmetic_sum_v2_draft",
                "question": (
                    "What is the arithmetic sum, in billions of dollars, of the total fair "
                    "values of assets segregated for the benefit of securities and futures "
                    "brokerage customers at the two year-end snapshots, December 31, 2010 and "
                    "December 31, 2009? Report a single arithmetic sum of the snapshots, not a "
                    "cumulative or deduplicated asset amount across the two years."
                ),
                "evaluation_scope": (
                    "one explicitly requested arithmetic sum of two dated snapshots"
                ),
                "prospectively_validated": False,
            },
        ],
        new_questions_contain_no_amounts_formulas_or_input_pairing=True,
        selected_future_version=None,
        different_task_targets_not_two_behavior_classes=True,
        old_responses_regraded_under_new_target=False,
        new_provider_calls=0,
        no_need_to_complete_N3_before_current_materialization=True,
    )
