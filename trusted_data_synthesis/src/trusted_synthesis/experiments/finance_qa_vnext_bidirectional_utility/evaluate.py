"""New-session review, finite support measurement and exact export; no feedback loop."""

from collections import Counter
from datetime import datetime
from decimal import Decimal
from fractions import Fraction

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import (
    REVIEW_FIELDS,
    answer_score,
    audit_session,
    comparison_status,
    display_compatible,
    final_number_and_unit,
    internal_final_diagnostics,
    normalize_unit,
    reviewed_answer_score,
    trace_checks,
    verify_quotes,
)

from .costs import cost_summary
from .plan import LABELS, MODEL, OUTPUT, SYSTEM, TASKS, history_guard, read_json, record, require


def costs(online):
    report = cost_summary(online)
    all_estimates = []
    for row in report["rows"]:
        turns = online / "sessions" / row["label"] / "turns"
        reservations = [read_json(p) for p in sorted(turns.glob("*_reservation.json"))]
        amounts, peak_flags = [], []
        for reservation in reservations:
            path = turns / f"{reservation['index']:03d}_outcome.json"
            outcome = read_json(path) if path.exists() else {}
            usage = outcome.get("usage") or {}
            values = [
                usage.get(k)
                for k in (
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                    "completion_tokens",
                )
            ]
            time = datetime.fromisoformat(reservation["started_utc"])
            require(
                time.utcoffset() is not None and time.utcoffset().total_seconds() == 0,
                "cost.utc_attempt_time",
            )
            peak = 1 <= time.hour < 4 or 6 <= time.hour < 10
            peak_flags.append(peak)
            value = None
            if all(type(v) is int for v in values):
                hit, miss, completion = map(Decimal, values)
                value = (
                    (hit * Decimal("0.05") + miss * Decimal("1.5") + completion * Decimal("4.5"))
                    * (2 if peak else 1)
                    / Decimal(1_000_000)
                )
            amounts.append(value)
        estimate = sum(amounts, Decimal(0)) if all(v is not None for v in amounts) else None
        all_estimates.append(estimate)
        row["registered_rate_estimate_cny"] = str(estimate) if estimate is not None else None
        row["attempts_by_registered_rate_window"] = {
            "peak": sum(peak_flags),
            "offpeak": len(peak_flags) - sum(peak_flags),
        }
    total = sum(all_estimates, Decimal(0)) if all(v is not None for v in all_estimates) else None
    report["registered_rate_estimate_cny"] = str(total) if total is not None else None
    report["registered_pricing_policy"] = {
        "currency": "CNY",
        "unit": "per million tokens",
        "offpeak": {"cache_hit": "0.05", "cache_miss": "1.5", "completion": "4.5"},
        "peak_multiplier": "2",
        "peak_hours_UTC": [[1, 4], [6, 10]],
        "window_assigned_from": (
            "durable request reservation started_utc, not inferred from response finish"
        ),
        "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
        "observation_date": "2026-09-09",
        "observation_limit": (
            "Official indexed Chinese table matches prior frozen CNY rates; direct page fetch "
            "timed out. These are estimates under the registered table, not confirmed account "
            "invoices or exchange-rate conversions."
        ),
        "current_Flash_name_does_not_independently_verify_tariff": True,
        "rate_scope": (
            "Inherited registered Flash price assumptions, not a new price quote or invoice"
        ),
    }
    return report


def assess(root):
    output = root / OUTPUT
    with execution_guard(online=False) as counts:
        manifest(output / "online")
        summary = read_json(output / "online/summary.json")
        require(
            summary["all_workers_terminated"] and summary["registered"] == 72,
            "assess.complete_fixed_collection",
        )
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        private = read_json(output / "preparation/private/evaluation_targets.json")
        store = DurableStore(output / "assessment")
        audits, templates = [], {}
        for row in summary["rows"]:
            label, key = row["label"], row["task_key"]
            public = read_json(output / f"preparation/public/{key}.json")
            directory = output / "online/sessions" / label
            if "result_id" in row:
                audit = audit_session(directory, public, private[key], expected_system=SYSTEM)
            else:
                audit = record(
                    "unavailable_original_session_audit",
                    terminal=row["terminal"],
                    raw_final=None,
                    calculations=[],
                    first_final_index=None,
                    pre_execution_formula_observed=False,
                    usages=[],
                )
            value, unit = final_number_and_unit(audit["raw_final"], public["question"])
            assessment = record(
                "new_support_session_assessment",
                label=label,
                task_key=key,
                **{k: v for k, v in audit.items() if k not in {"id", "schema_version", "label"}},
                automatic_answer_score=answer_score(value, unit, private[key]),
            )
            store.json("sessions/" + label + ".json", assessment)
            raw_messages = {
                str(int(p.name[:3])): p.read_text()
                for p in sorted((directory / "turns").glob("*_assistant.raw"))
            }
            store.json(
                "public_review_packets/" + label + ".json",
                {
                    "label": label,
                    "task_key": key,
                    "raw_messages": raw_messages,
                    "actual_result": read_json(directory / "result.json")
                    if (directory / "result.json").exists()
                    else None,
                    "assessment_id": assessment["id"],
                    "reviewer_is_not_blinded": True,
                },
            )
            audits.append(assessment)
            templates[label] = {
                "published_value": value,
                "published_unit": unit,
                "answer_override_evidence": [],
                "secondary_answer_values": [],
                "answer_calculation_id": None,
                **{
                    field: {
                        "status": "UNDETERMINED",
                        "evidence": [],
                        "explanation": "Await finite public-evidence review.",
                    }
                    for field in (*REVIEW_FIELDS, "final_answer_consistency")
                },
                "planning_observations": {"text": "", "evidence": []},
                "mapping": {
                    "occurrences": {},
                    "event_annotations": [],
                    "revisions": [],
                    "cross_checks": [],
                },
            }
        store.json("review_template.json", templates)
        report = record(
            "new_support_assessment_report",
            rows=audits,
            costs=costs(output / "online"),
            all_generation_finished_before_review=True,
            provider_calls=0,
            student=False,
        )
        store.json("report.json", report)
        store.json(
            "execution_guards.json", guard_report(counts, phase="new_support_offline_assessment")
        )
        seal_directory(store, kind="open_support_assessment_manifest", report_id=report["id"])
    return report


def qualify(audit, review, public, private, raw_messages):
    verify_quotes(review, raw_messages)
    final_index = audit["first_final_index"]
    require(
        all(
            e["response_index"] == final_index
            for e in review["final_answer_consistency"]["evidence"]
        ),
        "review.consistency_from_actual_Final",
    )
    inferred_value, inferred_unit = final_number_and_unit(audit["raw_final"], public["question"])
    if (
        str(inferred_value) != str(review["published_value"])
        or normalize_unit(inferred_unit) != normalize_unit(review["published_unit"])
    ) and review["published_value"] is not None:
        evidence = review["answer_override_evidence"]
        require(
            bool(evidence) and all(e["response_index"] == final_index for e in evidence),
            "review.extraction_from_Final_only",
        )
        require(
            str(review["published_value"]).replace(",", "").replace(" ", "")
            in " ".join(e["quote"] for e in evidence).replace(",", "").replace(" ", ""),
            "review.no_reference_filled_answer",
        )
    score = reviewed_answer_score(
        answer_score(review["published_value"], review["published_unit"], private), review
    )
    secondary = []
    for entry in review.get("secondary_answer_values", []):
        require(
            entry["evidence"]["response_index"] == final_index
            and str(entry["value"]) in entry["evidence"]["quote"],
            "review.original_secondary_Final_value",
        )
        secondary.append(
            display_compatible(
                score.get("reference_exact_value"),
                review["published_unit"],
                entry["value"],
                entry["unit"],
            )
            if "reference_exact_value" in score
            else None
        )
    if any(check is False for check in secondary):
        score.update(task_answer_status="FAIL", reason="secondary_answer_reference_mismatch")
    if audit["terminal"] != "model_final":
        score.update(
            task_answer_status="UNDETERMINED"
            if audit["terminal"].startswith("unknown")
            else "FAIL",
            reason="no_model_final",
        )
    return record(
        "new_support_reviewed_session",
        label=audit["label"],
        task_key=audit["task_key"],
        arm="T",
        assessment_id=audit["id"],
        terminal=audit["terminal"],
        answer=score,
        **trace_checks(audit, review, score),
        semantic_review={k: v for k, v in review.items() if k != "mapping"},
        answer_calculation_id=review["answer_calculation_id"],
        secondary_numeric_checks=secondary,
        secondary_reference_check_status=comparison_status(secondary),
        final_internal_consistency=internal_final_diagnostics(review),
        successful_calculations=len(audit["calculations"]),
        reviewer_is_independent=False,
        reviewer_is_blinded=False,
        semantic_review_is_not_automatic_source_certification=True,
        mapping_unknown_does_not_change_this_validity=True,
    )


def finalize(root, review_path):
    from .materialize import export
    from .measurement import measure
    from .projection import project_session
    from .source import bind_session

    output = root / OUTPUT
    with execution_guard(online=False) as counts:
        manifest(output / "assessment")
        history_guard(root)
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        reviews = read_json(review_path)
        require(set(reviews) == set(LABELS), "finalize.all_72_reviews")
        assessment = read_json(output / "assessment/report.json")
        private = read_json(output / "preparation/private/evaluation_targets.json")
        store = DurableStore(output / "closeout")
        store.write("posthoc_reviews.original.json", review_path.read_bytes())
        rows, sessions, projections = [], {}, []
        for audit in assessment["rows"]:
            label, key = audit["label"], audit["task_key"]
            directory = output / "online/sessions" / label
            raw_messages = {
                int(p.name[:3]): p.read_text()
                for p in (directory / "turns").glob("*_assistant.raw")
            }
            public = read_json(output / f"preparation/public/{key}.json")
            row = qualify(audit, reviews[label], public, private[key], raw_messages)
            rows.append(row)
            store.json("sessions/" + label + ".json", row)
            if row["formula_driven_trace_verified"]:
                session = bind_session(root, row)
                sessions[label] = session
                projection = project_session(
                    session, reviews[label]["mapping"], private[key]["goal_scope"]
                )
                projections.append(projection)
                store.json("behavior/" + label + ".json", projection)
        require(
            len(rows) == 72 and all(sum(r["task_key"] == key for r in rows) == 24 for key in TASKS),
            "finalize.original_new_denominators",
        )
        measurement = measure(projections, rows)
        store.json("measurement.json", measurement)
        materialization = export(
            root, store.root / "materialization", sessions, rows, projections, measurement
        )
        from .study import support_gate

        gate = support_gate(root, projections, materialization)
        store.json("input_gate.json", gate)
        costs_report = assessment["costs"]
        expense_by_label = {r["label"]: r for r in costs_report["rows"]}
        by_task = {}
        for key in TASKS:
            subset = [r for r in rows if r["task_key"] == key]
            n_valid = sum(r["formula_driven_trace_verified"] for r in subset)
            amounts = [expense_by_label[r["label"]]["registered_rate_estimate_cny"] for r in subset]
            total = (
                sum(map(Decimal, amounts), Decimal(0))
                if all(a is not None for a in amounts)
                else None
            )
            by_task[key] = {
                "registered": 24,
                "answer_counts": dict(Counter(r["answer"]["task_answer_status"] for r in subset)),
                "valid_count": n_valid,
                "valid_yield": str(Fraction(n_valid, 24)),
                "registered_rate_estimated_cny": str(total) if total is not None else None,
                "all_registered_cost_per_valid_package_cny": str(total / n_valid)
                if total is not None and n_valid
                else None,
            }
        valid_count = len(sessions)
        total_cost = costs_report["registered_rate_estimate_cny"]
        report = record(
            "new_support_exploration_report",
            registered=72,
            requested_model=MODEL,
            instruction="unchanged T",
            rows=rows,
            answer_counts=dict(Counter(r["answer"]["task_answer_status"] for r in rows)),
            valid_count=valid_count,
            input_gate=gate,
            completion_status=gate["status"],
            downstream_started=False,
            valid_yield=str(Fraction(valid_count, 72)),
            by_task=by_task,
            costs=costs_report,
            all_registered_cost_per_valid_package_cny=str(Decimal(total_cost) / valid_count)
            if total_cost is not None and valid_count
            else None,
            measurement_id=measurement["id"],
            materialization_index_id=materialization["id"],
            local_two_support_witness_tasks=measurement["local_two_support_witness_tasks"],
            class_probability_degrees_of_freedom=measurement[
                "class_probability_degrees_of_freedom"
            ],
            old_trajectories_in_new_frequency_denominator=False,
            prior_batch_and_other_experiment_artifacts_unchanged=True,
            old_N3_unchanged=True,
            new_six_task_population_not_old_panel_renormalization=True,
            no_forced_reconstruction=True,
            no_adaptive_prompt_or_budget=True,
            provider_calls_after_generation=0,
            student=False,
            gpu=False,
            training=False,
            vtdo=False,
            no_contribution_inferred_from_rarity_length_or_novelty=True,
            observation_scope=(
                "72 new fixed Teacher input sessions; finite support reachability and original "
                "representation, not population class cardinality or Student utility"
            ),
        )
        store.json("report.json", report)
        store.json("history_after.json", history_guard(root))
        store.json(
            "execution_guards.json",
            guard_report(counts, phase="new_support_measurement_and_original_export"),
        )
        seal_directory(store, kind="open_support_closeout_manifest", report_id=report["id"])
    return report
