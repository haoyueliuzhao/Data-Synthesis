"""One versioned offline quantity-impact pass, with existing semantic evidence."""

from collections import Counter
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.evaluate import (
    qualify as existing_qualification,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import condition
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.projection import (
    project_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.source import (
    bind_session,
    positive_candidate,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)

from .plan import (
    NE_SOURCE,
    OUTPUT,
    PACKAGE,
    X3_KEYS,
    encode,
    history_guard,
    public_quantity_context,
    read_json,
    record,
    reference,
    require,
    sha,
)
from .quantity import VERSION, interpret_final, score_quantity


def class_id(projection):
    """Exactly the old full-signature class identity, not a new class definition."""
    return "NE_complete_behavior_class:" + sha(
        encode(
            {
                "fixed_condition": condition(projection["population"])["id"],
                "task_key": projection["task_key"],
                "full_behavior_signature": projection["behavior_signature"],
            }
        )
    )


def fixed_selection(rows):
    eligible = {"X1": {"D": []}, "X2": {"D": []}, "X3C": {"D": [], "A": []}}
    for row in rows:
        if row["arm"] != "N" or not row["formula_driven_trace_verified"]:
            continue
        key, projection = row["task_key"], row.get("projection")
        if not projection or projection["status"] != "MAPPED":
            continue
        route = None
        if key == "X3C":
            route = next(
                (r for r, digest in X3_KEYS.items() if projection["behavior_key"] == digest), None
            )
        elif key in {"X1", "X2"}:
            route = "D" if row["historical_behavior_label"] == "PURE_D" else None
        if route is not None:
            eligible[key][route].append(row["label"])
    selected, heldout = [], []
    for key, groups in eligible.items():
        for route, labels in groups.items():
            labels.sort(key=lambda s: int(s.rsplit("_", 1)[1]))
            minimum = 4 if key == "X3C" else 3
            if len(labels) < minimum:
                return record(
                    "support_selection",
                    status="INPUT_INADEQUATE",
                    eligible=eligible,
                    train=[],
                    heldout=[],
                    reason="insufficient_versioned_valid_original_support",
                )
            selected.extend(
                {"label": label, "task_key": key, "route": route} for label in labels[:3]
            )
            if key == "X3C":
                heldout.append({"label": labels[3], "task_key": key, "route": route})
    require(len(selected) == 12 and len(heldout) == 2, "selection.exact_twelve_plus_two")
    return record(
        "support_selection",
        status="RAW_SUPPORT_ESTABLISHED",
        eligible=eligible,
        train=selected,
        heldout=heldout,
        selection="original replicate ascending; first three",
        holdouts_not_tokenized_trained_evaluated_or_used_for_distribution_choice=True,
        A_is_existing_OTHER_VALID_CLASS_not_R=True,
        no_E_examples=True,
        no_replacement_after_token_failure=True,
    )


def derive(root):
    root = Path(root)
    target = root / OUTPUT / "quantity_revision"
    require(not target.exists(), "derive.one_new_versioned_pass_no_overwrite")
    with execution_guard(online=False) as counts:
        history_guard(root)
        source = root / NE_SOURCE
        audits = read_json(source / "assessment/report.json")["rows"]
        reviews = read_json(source / "closeout/posthoc_reviews.original.json")
        private = read_json(source / "preparation/private/evaluation_targets.json")
        measurement = read_json(source / "closeout/measurement.json")
        prototypes = read_json(source / "preparation/private/target_class_prototypes.json")
        require(len(audits) == 48, "derive.exact_original_48")
        store = DurableStore(target)
        references = [
            reference(root, NE_SOURCE + "/" + relative)
            for relative in (
                "assessment/report.json",
                "closeout/posthoc_reviews.original.json",
                "preparation/private/evaluation_targets.json",
                "closeout/measurement.json",
            )
        ]
        rows, impacts = [], []
        for audit in audits:
            label, key = audit["label"], audit["task_key"]
            original = read_json(source / f"closeout/sessions/{label}.json")
            old_projection_path = source / f"closeout/behavior/{label}.json"
            review = reviews[audit["review_id"]]
            actual = {
                int(k): v
                for k, v in read_json(
                    source / f"assessment/public_review_packets/{audit['review_id']}.json"
                )["raw_messages"].items()
            }
            interpreted = interpret_final(audit["raw_final"], public_quantity_context())
            updated = {
                **audit,
                "automatic_quantity": score_quantity(
                    interpreted, private[key]["reference_exact_value"], public_quantity_context()
                ),
            }
            # The actual events, source mappings, period, direction and five
            # semantic decisions are reused, not reauthored or tools replayed.
            qualified = existing_qualification(updated, review, actual)
            row = record(
                "derived_NE_qualification",
                **{k: v for k, v in qualified.items() if k not in {"id", "schema_version"}},
                original_qualification_id=original["id"],
                quantity_interpretation_version=VERSION,
                new_version_only_old_score_retained=True,
                existing_semantic_evidence_reused_without_revision=True,
            )
            unchanged = (
                "semantic_review",
                "answer_calculation_id",
                "reviewed_formula_data_units_precede_selected_execution",
                "explicit_final_result_reference_consistent",
            )
            require(
                all(row[k] == original[k] for k in unchanged),
                "derive.no_unrelated_qualification_changes",
            )
            projection = read_json(old_projection_path) if old_projection_path.exists() else None
            newly_valid = bool(
                row["formula_driven_trace_verified"]
                and not original["formula_driven_trace_verified"]
            )
            if newly_valid:
                session = bind_session(root, row)
                projection = project_session(session, review["mapping"], private[key]["goal_scope"])
                store.json(f"newly_eligible/behavior/{label}.json", projection)
                for turn in session["turns"]:
                    candidate = positive_candidate(session, turn)
                    if candidate is not None:
                        index = candidate["response_index"]
                        prefix = f"newly_eligible/positive/{label}/{index:03d}"
                        store.json(prefix + ".candidate.json", candidate)
                        store.write(prefix + ".target.raw", turn["raw"])
            cid = class_id(projection) if projection and projection["status"] == "MAPPED" else None
            if projection and old_projection_path.exists():
                require(
                    cid == measurement["session_class_ids"][label], "derive.exact_existing_class_ID"
                )
            behavior = None
            if projection and projection["status"] == "MAPPED":
                own = prototypes["tasks"][audit["arm"]][key]
                behavior = next(
                    (
                        "PURE_" + r
                        for r, p in own.items()
                        if projection["behavior_signature"] == p["signature"]
                    ),
                    "OTHER_VALID_CLASS",
                )
            summary = record(
                "derived_support_row",
                **{k: v for k, v in row.items() if k not in {"id", "schema_version"}},
                qualification_id=row["id"],
                projection=projection,
                class_id=cid,
                historical_behavior_label=behavior,
                newly_eligible=newly_valid,
            )
            store.json(f"sessions/{label}.json", row)
            rows.append(summary)
            impacts.append(
                {
                    "label": label,
                    "old_qualification_id": original["id"],
                    "derived_qualification_id": row["id"],
                    "old_quantity": original["answer"]["V_quantity"],
                    "new_quantity": row["answer"]["V_quantity"],
                    "old_full_trace": original["formula_driven_trace_verified"],
                    "new_full_trace": row["formula_driven_trace_verified"],
                    "old_reason": original["answer"].get("reason"),
                    "new_reason": row["answer"].get("reason"),
                    "existing_semantic_decisions_identical": True,
                }
            )
        selection = fixed_selection(rows)
        store.json("support_selection.json", selection)
        report = record(
            "quantity_revision_report",
            version=VERSION,
            registered=48,
            rows=rows,
            impacts=impacts,
            counts=dict(Counter(r["answer"]["V_quantity"] for r in rows)),
            full_trace_valid=sum(r["formula_driven_trace_verified"] for r in rows),
            affected_labels=[
                r["label"]
                for r in impacts
                if (r["old_quantity"], r["old_full_trace"])
                != (r["new_quantity"], r["new_full_trace"])
            ],
            original_references=references,
            implementation_references=[
                reference(root, PACKAGE + "/" + name)
                for name in ("quantity.py", "derive.py", "plan.py")
            ],
            original_assessment_closeout_unchanged=True,
            old_FAIL_is_not_a_valid_financial_error_claim=True,
            known_development_sample_repair_not_blind_validation=True,
            full_PASS_count_not_a_success_criterion=True,
            historical_tool_reexecution=0,
            Teacher_requests=0,
            Student_calls=0,
            unaffected_existing_source_period_direction_evidence_reused=True,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase="quantity_v1_1_derivation"))
        seal_directory(store, kind="quantity_revision_manifest", report_id=report["id"])
    return report
