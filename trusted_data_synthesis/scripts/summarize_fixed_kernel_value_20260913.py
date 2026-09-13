"""Count already-closed records; never replay, tokenize, train, or send requests."""

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / p.OUTPUT
    generation = p.read_json(output / "generation_report.json")
    finalization = p.read_json(output / "budget_finalization.json")
    gate = p.read_json(output / "material_gate.json")
    index = p.read_json(output / "materialization_index.json")
    start = p.read_json(output / "execution_started.json")
    registry = p.read_json(output / "registry.json")
    rows = p.read_json(output / "session_results.json")
    journal = p.read_json(output / "material_request_journal.json")
    p.require(
        generation["generation_closed"] and generation["no_inflight_requests"], "summary.closed"
    )
    p.require(finalization["purpose_closed"], "summary.closed_budget")
    registrations = {row["session_id"]: row for row in registry["sessions"]}

    def read_result(row):
        return (
            row,
            p.read_json(output / row["session"]["path"]) if row["session"] else None,
            p.read_json(output / row["qualification"]["path"]) if row["qualification"] else None,
        )

    fields = (
        "financial_valid",
        "full_class_valid",
        "authentic_origin_verified",
        "token_materialization_eligible",
    )
    counts, methods, fatal_reasons = Counter(), Counter(), Counter()
    groups = defaultdict(Counter)
    with ThreadPoolExecutor(max_workers=24) as pool:
        for row, session, qualification in pool.map(read_result, rows):
            registered = registrations[row["session_id"]]
            group = (registered["pool"], registered["family"], registered["role"])
            groups[group]["registered"] += 1
            groups[group][row["status"]] += 1
            if session is not None:
                counts["session_records"] += 1
                counts["public_turns_retained"] += len(session["turns"])
                counts["first_final_records"] += session["first_final_index"] is not None
                fatal = session.get("fatal_error")
                if fatal:
                    fatal_reasons[(fatal.get("type"), fatal.get("message"))] += 1
            if qualification is not None:
                counts["qualification_records"] += 1
                for field in fields:
                    counts[field] += bool(qualification[field])
                    groups[group][field] += bool(qualification[field])
                if qualification["financial_valid"]:
                    methods[qualification["actual_method"] or "UNCLASSIFIED"] += 1

    sent = [row for row in journal if row["state"] != "not_sent"]
    known = [row for row in sent if row["state"] == "settled"]
    request_groups = Counter(
        (row["state"], row["outcome"], row["response_model"]) for row in journal
    )
    before = p.read_json(output / "legacy_wallet_before.json")
    after = p.read_json(output / "legacy_wallet_after.json")
    protected_before = p.read_json(output / "protected_sources_before.json")
    protected_after = p.read_json(output / "protected_sources_after.json")
    result = p.record(
        "closed_collection_summary",
        analysis_script_sha256=p.sha(Path(__file__)),
        generation_report_id=generation["id"],
        budget_finalization_id=finalization["id"],
        material_gate_id=gate["id"],
        source_commit_at_launch=start["source_commit_at_launch"],
        started_utc=start["started_utc"],
        generation_closed_utc=generation["finished_utc"],
        registered_sessions=len(rows),
        terminal_counts=dict(Counter(row["status"] for row in rows)),
        actual_HTTP_requests=len(sent),
        actual_HTTP_sessions=len({row["session_id"] for row in sent}),
        unsent_cancelled_requests=len(journal) - len(sent),
        known_prompt_tokens=sum(row["prompt_tokens"] for row in known),
        known_completion_tokens=sum(row["completion_tokens"] for row in known),
        known_total_tokens=sum(row["reported_total_tokens"] for row in known),
        new_unknown_request_count=sum(row["state"] == "usage_unknown" for row in sent),
        request_outcomes=[
            dict(state=a, outcome=b, response_model=c, count=n)
            for (a, b, c), n in sorted(request_groups.items(), key=str)
        ],
        observed_saved_assessment_counts=dict(counts),
        observed_financial_valid_actual_methods=dict(methods),
        observed_group_counts=[
            dict(pool=a, family=b, role=c, counts=dict(value))
            for (a, b, c), value in sorted(groups.items())
        ],
        fatal_reason_counts=[
            dict(error_type=a, reason=b, count=n)
            for (a, b), n in sorted(fatal_reasons.items(), key=str)
        ],
        diagnostic_observed_prefix_is_not_representative_population_yield=True,
        recorded_legacy_snapshot_unchanged=before == after,
        recorded_five_protected_source_snapshots_unchanged=protected_before == protected_after,
        original_source_or_wallet_content_reverified_by_this_summary=False,
        tokenizer_loads=index["tokenizer_loads"],
        consumable_train=index["counts"]["consumable_train"],
        consumable_sealed=index["counts"]["consumable_sealed"],
        common_intervention_task_count=gate["common_intervention_task_count"],
        global_mass_movement=gate["global_mass_movement"],
        training_gate=gate["training_gate"],
        Student_training_runs=0,
        Student_evaluation_sessions=0,
        additional_Provider_calls=0,
        semantic_replays=0,
        token_materialization_calls=0,
        original_records_modified=False,
    )
    p.write_once(output / "closed_collection_summary.json", result)
    print(
        p.encode(
            {
                "summary_id": result["id"],
                "known_total_tokens": result["known_total_tokens"],
                "counts": result["observed_saved_assessment_counts"],
                "methods": result["observed_financial_valid_actual_methods"],
            }
        ).decode()
    )


if __name__ == "__main__":
    main()
