"""One read-only verification and accounting pass after both reviews are sealed.

No tokenization, qualification, source normalization, model load, or generation.
The result is a new closeout artifact; every prior phase remains immutable.
"""

import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.evaluate import verify
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.plan import (
    GROUPS,
    OUTPUT,
    SEEDS,
    read_json,
    record,
    require,
)


def phase_accounting(output, phase, reviewed):
    counts, terminals, events, tool_names, finishes = (Counter() for _ in range(5))
    for row in reviewed["rows"]:
        result = read_json(
            output
            / "generation"
            / phase
            / row["variant"]
            / "sessions"
            / row["task_key"]
            / "result.json"
        )
        counts["sessions"] += 1
        terminals[result["terminal"]] += 1
        counts["model_requests"] += result["model_requests"]
        counts["decoder_requests"] += result["decoder_requests"]
        counts["tool_calls"] += result["tool_calls"]
        counts["admitted_responses"] += result["admitted_public_responses"]
        for attempt in result["attempts"]:
            counts["decoder_attempt_records"] += 1
            finishes[str(attempt["finish_reason"])] += 1
            if attempt["generation_invoked"]:
                counts["actual_model_generation_invocations"] += 1
                counts["generation_prompt_tokens"] += attempt["prompt_token_count"]
                counts["generated_tokens_including_actual_EOS"] += attempt["generated_token_count"]
                counts["public_content_tokens"] += len(attempt["public_content_token_ids"])
            else:
                counts["decoder_attempt_without_model_invocation"] += 1
        for event in result["events"]:
            call = event["tool_call"]
            if event["final"]:
                events["first_Final"] += 1
                require(call is None, "closeout.Final_has_no_sibling_dispatch")
            elif event["protocol_error"] is not None:
                events["protocol_error"] += 1
            elif call is not None:
                name = call["name"]
                tool_names[name if isinstance(name, str) else "NON_STRING_TOOL_NAME"] += 1
                events["tool_success" if call["output"]["status"] == "ok" else "tool_error"] += 1
                if name == "calculate" and call["output"]["status"] == "ok":
                    counts["successful_calculations"] += 1
                    counts["arithmetic_operations"] += call["output"]["result"]["operation_count"]
            else:
                events["legal_message_only"] += 1
    require(sum(events.values()) == counts["admitted_responses"], "closeout.event_partition")
    require(sum(tool_names.values()) == counts["tool_calls"], "closeout.tool_partition")
    require(
        counts["actual_model_generation_invocations"] == counts["model_requests"],
        "closeout.model_invocation_partition",
    )
    counts["unadmitted_generated_responses"] = (
        counts["actual_model_generation_invocations"] - counts["admitted_responses"]
    )
    return {
        "counts": dict(counts),
        "terminals": dict(terminals),
        "event_partition": dict(events),
        "tool_names": dict(tool_names),
        "decoder_finish_reasons": dict(finishes),
    }


def summarize_arms(reviewed):
    arms = sorted({row["variant"].rsplit("_", 1)[0] for row in reviewed["rows"]})
    result = {}
    for arm in arms:
        variants = [reviewed["by_variant"][f"{arm}_{seed}"] for seed in SEEDS]
        rows = [row for row in reviewed["rows"] if row["variant"].rsplit("_", 1)[0] == arm]
        complete = sum(row["qualification"]["complete_verifiable_trajectory"] for row in rows)
        result[arm] = {
            "sessions": len(rows),
            "unique_registered_task_count": reviewed["task_count"],
            "complete_trace_PASS": complete,
            "mean_three_seed_utility": str(sum(Fraction(v["utility"]) for v in variants) / 3),
            "answer_statuses": dict(
                Counter(row["qualification"]["task_answer_status"] for row in rows)
            ),
            "trace_statuses": dict(Counter(row["qualification"]["trace_status"] for row in rows)),
            "Final_delivery": dict(
                Counter(row["qualification"]["delivery_status"] for row in rows)
            ),
            "source_correspondence": dict(
                Counter(row["semantic_review"]["variable_correspondence"]["status"] for row in rows)
            ),
            "actual_successful_calculation_sessions": sum(
                row["actual_calculations"] > 0 for row in rows
            ),
            "group_complete_trace_PASS": {
                group: sum(v["groups"][group]["complete_trace_PASS"] for v in variants)
                for group in GROUPS
            },
            "group_registered_sessions": {
                group: sum(v["groups"][group]["registered"] for v in variants) for group in GROUPS
            },
        }
    return result


def main():
    root = Path(__file__).resolve().parents[5]
    output = root / OUTPUT
    require(output == Path(__file__).resolve().parents[1], "closeout.exact_output_root")
    require(not (output / "closeout").exists(), "closeout.once")
    development = read_json(output / "reviewed/dev/report.json")
    confirmation = read_json(output / "reviewed/confirm/report.json")
    # This calls the pre-training-frozen verification function exactly once.
    verified = verify(root)
    accounting = {
        "dev": phase_accounting(output, "dev", development),
        "confirm": phase_accounting(output, "confirm", confirmation),
    }
    require(
        sum(v["counts"]["model_requests"] for v in accounting.values())
        == verified["actual_generation_requests"],
        "closeout.request_totals",
    )
    require(
        sum(v["counts"]["tool_calls"] for v in accounting.values())
        == verified["actual_tool_calls"],
        "closeout.tool_totals",
    )
    report = record(
        "source_class_closed_study",
        verification_id=verified["id"],
        development_report_id=development["id"],
        confirmation_report_id=confirmation["id"],
        actual_accounting=accounting,
        development_by_arm=summarize_arms(development),
        confirmation_by_arm=summarize_arms(confirmation),
        development_selection=verified["development_selection"],
        confirmation_contrast=verified["confirmation_contrast"],
        confirmation_mean_gain_positive=(
            Fraction(verified["confirmation_contrast"]["paired_mean_gain"]) > 0
        ),
        no_runner_up_or_extra_generation_after_confirmation=True,
        no_requalification_in_closeout=True,
        no_model_loads_tokenization_or_new_teacher_requests=True,
        empirical_scope=(
            "fixed support and original material kernel, 12 dev and 24 confirm tasks; "
            "three repeated seeds are not independent tasks"
        ),
        fully_blind_or_independent_reviewer=False,
        theoretical_Contribution_established=False,
    )
    store = DurableStore(output / "closeout")
    store.json("verification.json", verified)
    store.json("report.json", report)
    seal_directory(store, kind="source_class_closeout_manifest", report_id=report["id"])
    print(
        json.dumps(
            {
                "id": report["id"],
                "verification_id": verified["id"],
                "actual_Student_sessions": verified["actual_Student_sessions"],
                "confirmation_contrast": verified["confirmation_contrast"],
            }
        )
    )


if __name__ == "__main__":
    main()
