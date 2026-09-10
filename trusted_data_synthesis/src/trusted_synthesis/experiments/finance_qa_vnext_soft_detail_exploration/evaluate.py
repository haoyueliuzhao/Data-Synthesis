"""Offline quantity/format qualification and masked finite public-evidence review."""

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
    audit_session,
    verify_quotes,
)

from .costs import cost_summary
from .exploration import R_evidence_chain, verify_extra_evidence
from .plan import (
    ARMS,
    LABELS,
    OUTPUT,
    SYSTEMS_NEW,
    TASKS,
    history_guard,
    public_quantity_context,
    read_json,
    record,
    require,
)
from .quantity import interpret_final, interpret_unit, score_quantity


def costs(online):
    result = cost_summary(online)
    estimates = []
    for row in result["rows"]:
        turns = online / "sessions" / row["label"] / "turns"
        values, windows = [], Counter()
        for path in sorted(turns.glob("*_reservation.json")):
            reservation = read_json(path)
            outcome_path = turns / f"{reservation['index']:03d}_outcome.json"
            outcome = read_json(outcome_path) if outcome_path.exists() else {}
            usage = outcome.get("usage") or {}
            time = datetime.fromisoformat(reservation["started_utc"])
            require(time.utcoffset().total_seconds() == 0, "cost.reservation_UTC")
            peak = 1 <= time.hour < 4 or 6 <= time.hour < 10
            windows["peak" if peak else "offpeak"] += 1
            counts = [
                usage.get(k)
                for k in (
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                    "completion_tokens",
                )
            ]
            amount = None
            if all(type(n) is int for n in counts):
                hit, miss, completion = map(Decimal, counts)
                amount = hit * Decimal("0.05") + miss * Decimal("1.5") + completion * Decimal("4.5")
                amount = amount * (2 if peak else 1) / Decimal(1000000)
            values.append(amount)
        estimate = sum(values, Decimal(0)) if all(v is not None for v in values) else None
        row["registered_rate_estimate_cny"] = str(estimate) if estimate is not None else None
        row["attempts_by_registered_rate_window"] = dict(windows)
        estimates.append(estimate)
    total = sum(estimates, Decimal(0)) if all(v is not None for v in estimates) else None
    result["registered_rate_estimate_cny"] = str(total) if total is not None else None
    result["registered_pricing_policy"] = {
        "scope": (
            "inherited conditional Flash CNY price assumptions, not a current quote or invoice"
        ),
        "per_million_offpeak": {"cache_hit": "0.05", "cache_miss": "1.5", "completion": "4.5"},
        "peak_multiplier": "2",
        "peak_UTC_hours": [[1, 4], [6, 10]],
        "window_assigned_from": "actual reservation started_utc",
        "current_price_reverified": False,
        "reasoning_already_in_completion": True,
    }
    return result


def assess(root):
    output = root / OUTPUT
    with execution_guard(online=False) as counts:
        manifest(output / "online")
        summary = read_json(output / "online/summary.json")
        require(
            summary["registered"] == 48 and summary["all_workers_terminated"],
            "assess.only_after_all_48",
        )
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        private = read_json(output / "preparation/private/evaluation_targets.json")
        registrations = read_json(output / "preparation/registrations.json")
        store = DurableStore(output / "assessment")
        audits, templates = [], {}
        for registration in sorted(registrations, key=lambda r: r["review_id"]):
            label, key, arm, review_id = (
                registration[k] for k in ("label", "task_key", "arm", "review_id")
            )
            directory = output / "online/sessions" / label
            public = read_json(output / f"preparation/public/{key}.json")
            result_path = directory / "result.json"
            if result_path.exists():
                audit = audit_session(
                    directory, public, private[key], expected_system=SYSTEMS_NEW[arm]
                )
            else:
                outcome = next(r for r in summary["rows"] if r["label"] == label)
                audit = {
                    "terminal": outcome["terminal"],
                    "raw_final": None,
                    "calculations": [],
                    "calculation_requests": [],
                    "first_final_index": None,
                    "pre_execution_formula_observed": False,
                    "usages": [],
                }
            interpreted = interpret_final(audit["raw_final"], public_quantity_context())
            assessment = record(
                "masked_session_assessment",
                label=label,
                task_key=key,
                arm=arm,
                review_id=review_id,
                **{
                    k: v
                    for k, v in audit.items()
                    if k not in {"id", "schema_version", "label", "task_key", "arm", "review_id"}
                },
                automatic_quantity=score_quantity(
                    interpreted, private[key]["reference_exact_value"], public_quantity_context()
                ),
            )
            store.json("sessions/" + label + ".json", assessment)
            raw_messages = {
                str(int(path.name[:3])): path.read_text()
                for path in sorted((directory / "turns").glob("*_assistant.raw"))
            }
            result = read_json(result_path) if result_path.exists() else None
            store.json(
                "public_review_packets/" + review_id + ".json",
                {
                    "review_id": review_id,
                    "task_key": key,
                    "public_document": public,
                    "shared_public_quantity_context": public_quantity_context(),
                    "raw_messages": raw_messages,
                    "raw_final": audit["raw_final"],
                    "actual_events": result["events"] if result is not None else [],
                    "calculations": audit["calculations"],
                    "first_final_index": audit["first_final_index"],
                    "terminal": audit["terminal"],
                    "condition_label_model_costs_and_SYSTEM_omitted": True,
                    "model_self_description_may_reveal_condition": True,
                    "not_independent_or_guaranteed_blinded": True,
                },
            )
            templates[review_id] = {
                "published_value": interpreted.get("published_value"),
                "published_unit": interpreted.get("published_unit"),
                "answer_override_evidence": [],
                "secondary_answer_values": [],
                "answer_calculation_id": None,
                "answer_calculation_unit": None,
                **{
                    field: {
                        "status": "UNDETERMINED",
                        "evidence": [],
                        "explanation": (
                            "Await review of the actual common source and public history."
                        ),
                    }
                    for field in (*REVIEW_FIELDS, "final_answer_consistency")
                },
                "planning_observations": {"text": "", "evidence": []},
                "R_mention": {"status": "UNDETERMINED", "evidence": [], "explanation": ""},
                "R_Final_link": {"status": "UNDETERMINED", "evidence": [], "explanation": ""},
                "call_semantics": {},
                "mapping": {
                    "occurrences": {},
                    "event_annotations": [],
                    "revisions": [],
                    "cross_checks": [],
                },
                "condition_inferred_from_self_description": False,
            }
            audits.append(assessment)
        store.json("review_template.json", templates)
        report = record(
            "NE_assessment_report",
            rows=audits,
            costs=costs(output / "online"),
            all_generation_finished_before_review=True,
            masked_packet_ids_used_for_review=True,
            provider_calls=0,
            Student=False,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase="NE_offline_assessment"))
        seal_directory(store, kind="soft_detail_assessment_manifest", report_id=report["id"])
    return report


def qualify(audit, review, raw_messages):
    verify_quotes(review, raw_messages)
    verify_extra_evidence(review, raw_messages, audit)
    require(
        not review["answer_override_evidence"] and not review["secondary_answer_values"],
        "quantity.no_posthoc_extraction_override_or_unregistered_secondary_score",
    )
    context = public_quantity_context()
    interpreted = audit["automatic_quantity"]["interpretation"]
    require(
        review["published_value"] == interpreted.get("published_value")
        and review["published_unit"] == interpreted.get("published_unit"),
        "quantity.actual_Final_extraction_not_replaced",
    )
    require(
        all(
            e["response_index"] == audit["first_final_index"]
            for e in review["final_answer_consistency"]["evidence"]
        ),
        "review.Final_consistency_evidence_from_actual_Final",
    )
    score = dict(audit["automatic_quantity"])
    final_status = review["final_answer_consistency"]["status"]
    score["automatic_V_quantity"] = score["V_quantity"]
    if final_status == "FAIL":
        score.update(
            V_quantity="FAIL",
            task_answer_status="FAIL",
            reason="contradictory_or_inapplicable_actual_Final",
        )
    elif final_status != "PASS" and score["V_quantity"] == "PASS":
        score.update(
            V_quantity="UNDETERMINED",
            task_answer_status="UNDETERMINED",
            reason="actual_Final_scope_or_internal_consistency_unresolved",
        )
    selected = next(
        (c for c in audit["calculations"] if c["call_id"] == review["answer_calculation_id"]), None
    )
    temporal = bool(selected) and all(
        any(e["response_index"] <= selected["response_index"] for e in review[field]["evidence"])
        for field in REVIEW_FIELDS[:3]
    )
    actual_final = audit["raw_final"]
    explicit = actual_final.get("result_id") if isinstance(actual_final, dict) else None
    reference_consistent = explicit is None or bool(selected and explicit == selected["call_id"])
    selected_unit = interpret_unit(review["answer_calculation_unit"], context)
    numeric = None
    if selected and interpreted["status"] == "MAPPED" and selected_unit["status"] == "MAPPED":
        unit = interpreted["unit_interpretation"]
        same_kind = (
            unit["dimension"] == selected_unit["dimension"]
            and unit["currency"] == selected_unit["currency"]
        )
        tolerance = Fraction(score.get("rounding_tolerance", "0"))
        selected_value = (
            Fraction(selected["actual_exact_value"])
            * Fraction(selected_unit["scale"])
            / Fraction(context["target_scale"])
        )
        published_value = Fraction(interpreted["physical_value"]) / Fraction(
            context["target_scale"]
        )
        numeric = same_kind and abs(selected_value - published_value) <= tolerance
    semantic = [review[field]["status"] for field in REVIEW_FIELDS]
    complete = (
        audit["terminal"] == "model_final"
        and selected
        and temporal
        and numeric is True
        and reference_consistent
        and all(s == "PASS" for s in semantic)
        and score["V_quantity"] == "PASS"
    )
    definite_failure = (
        score["V_quantity"] == "FAIL"
        or "FAIL" in semantic
        or not reference_consistent
        or numeric is False
        or (audit["terminal"] == "model_final" and not audit["calculations"])
    )
    trace_status = "PASS" if complete else "FAIL" if definite_failure else "UNDETERMINED"
    return record(
        "reviewed_NE_session",
        label=audit["label"],
        arm=audit["arm"],
        task_key=audit["task_key"],
        review_id=audit["review_id"],
        assessment_id=audit["id"],
        terminal=audit["terminal"],
        answer=score,
        trace_status=trace_status,
        formula_driven_trace_verified=bool(complete),
        reviewed_formula_data_units_precede_selected_execution=temporal,
        selected_tool_result_numerically_matches_publication=numeric is True,
        explicit_final_result_reference_consistent=reference_consistent,
        actual_tool_publication_consistency_separate_from_reference_correctness=True,
        answer_calculation_id=review["answer_calculation_id"],
        reviewed_calculation_unit=selected_unit,
        semantic_review={k: v for k, v in review.items() if k != "mapping"},
        reviewer_is_independent=False,
        reviewer_is_fully_blinded=False,
        condition_metadata_hidden_in_packets=True,
        missing_behavior_mapping_does_not_change_this_original_qualification=True,
    )


def finalize(root, review_path):
    from .archive import export
    from .measurement import measure
    from .projection import project_session
    from .source import bind_execution_prefix, bind_session

    output = root / OUTPUT
    with execution_guard(online=False) as counts:
        manifest(output / "assessment")
        history_guard(root)
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        review_map = read_json(output / "preparation/private/review_identity_map.json")
        reviews = read_json(review_path)
        require(set(reviews) == set(review_map), "finalize.exact_48_masked_reviews")
        assessment = read_json(output / "assessment/report.json")
        private = read_json(output / "preparation/private/evaluation_targets.json")
        prototypes = read_json(output / "preparation/private/target_class_prototypes.json")
        store = DurableStore(output / "closeout")
        store.write("posthoc_reviews.original.json", review_path.read_bytes())
        rows, projections, chains, valid_sessions = [], [], [], {}
        for audit in assessment["rows"]:
            label, key, arm = audit["label"], audit["task_key"], audit["arm"]
            review_id = audit["review_id"]
            require(
                review_map[review_id]["label"] == label, "finalize.unmask_only_registered_identity"
            )
            review = reviews[review_id]
            directory = output / "online/sessions" / label
            raw_messages = {
                int(p.name[:3]): p.read_text()
                for p in (directory / "turns").glob("*_assistant.raw")
            }
            row = qualify(audit, review, raw_messages)
            store.json("sessions/" + label + ".json", row)
            rows.append(row)
            projection = None
            if row["formula_driven_trace_verified"]:
                session = bind_session(root, row)
                valid_sessions[label] = session
                projection = project_session(session, review["mapping"], private[key]["goal_scope"])
                projections.append(projection)
                store.json("behavior/" + label + ".json", projection)
            else:
                session = bind_execution_prefix(root, row)
            chain = R_evidence_chain(session, review, prototypes["tasks"][arm][key], projection)
            chains.append(chain)
            store.json("R_chain/" + label + ".json", chain)
        require(set(r["label"] for r in rows) == set(LABELS), "finalize.only_all_48_registrations")
        measurement = measure(rows, projections, chains)
        store.json("measurement.json", measurement)
        archive = export(root, store, rows, valid_sessions, measurement)
        costs_report = assessment["costs"]
        expense_rows = {r["label"]: r for r in costs_report["rows"]}
        costs_by_cell = {}
        for arm in ARMS:
            costs_by_cell[arm] = {}
            for task in TASKS:
                subset = [r for r in rows if r["arm"] == arm and r["task_key"] == task]
                amounts = [expense_rows[r["label"]]["registered_rate_estimate_cny"] for r in subset]
                total = (
                    sum(map(Decimal, amounts), Decimal(0))
                    if all(a is not None for a in amounts)
                    else None
                )
                n_valid = sum(r["formula_driven_trace_verified"] for r in subset)
                costs_by_cell[arm][task] = {
                    "all_eight_registered_rate_estimate_cny": str(total)
                    if total is not None
                    else None,
                    "valid_count": n_valid,
                    "registered_cost_per_valid_original_package_cny": str(total / n_valid)
                    if total is not None and n_valid
                    else None,
                }
        report = record(
            "bounded_NE_exploration_report",
            scope_status="PASS_AS_SCOPED",
            study_completion="FIXED_48_CLOSED",
            Student_status="NOT_RUN",
            training_input_status="NOT_INSTANTIATED",
            registered=48,
            valid_count=sum(r["formula_driven_trace_verified"] for r in rows),
            rows=rows,
            measurement_id=measurement["id"],
            archive_index_id=archive["id"],
            by_condition=measurement["populations"],
            contrasts=measurement["contrasts"],
            costs=costs_report,
            costs_by_condition_task=costs_by_cell,
            actual_training_runs=0,
            actual_Student_sessions=0,
            auxiliary_NLL=0,
            tokenizer_loaded=False,
            provider_calls_after_collection=0,
            training_selection=[],
            no_resampling_no_second_prompt_search=True,
            no_old_score_or_source_rewriting=True,
            no_Contribution_or_Student_utility_claim=True,
            original_conditional_prefixes_never_removed=True,
            reviewer_scope=(
                "same executing assistant using metadata-masked packets, not "
                "independent or guaranteed blind"
            ),
        )
        store.json("report.json", report)
        store.json("history_after.json", history_guard(root))
        store.json(
            "execution_guards.json", guard_report(counts, phase="NE_finite_closeout_no_Student")
        )
        seal_directory(store, kind="soft_detail_closeout_manifest", report_id=report["id"])
    return report
