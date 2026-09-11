"""All fixed collection first, then forty bounded eligibility records, no tokenizer."""

from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.evaluate import costs
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.exploration import (
    R_evidence_chain,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    public_quantity_context,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.projection import (
    project_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.derive import class_id
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.quantity import (
    interpret_final,
    score_quantity,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import audit_session

from .core import Store, history_guard, verify_preparation
from .plan import (
    LABELS,
    OLD,
    OLD_LABELS,
    OLD_UTILITY,
    OUTPUT,
    SYSTEM,
    read_json,
    record,
    reference,
    require,
    select_support,
    sha,
)
from .review import qualify, template
from .source import batch_path, bind, candidates


def assess(root):
    root = Path(root)
    history_guard(root)
    verify_preparation(root)
    output = root / OUTPUT
    manifest(output / "online")
    collected = read_json(output / "online/report.json")
    require(
        collected["registered"] == 32 and collected["all_workers_terminated"],
        "assess.all_32_finished",
    )
    public = read_json(output / "preparation/public/X2.json")
    private = read_json(output / "preparation/private/evaluation_targets.json")["X2"]
    registered = {r["label"]: r for r in read_json(output / "preparation/registrations.json")}
    outcomes = {r["label"]: r for r in collected["rows"]}
    old_audits = {
        r["label"]: r
        for r in read_json(root / OLD / "assessment/report.json")["rows"]
        if r["label"] in OLD_LABELS
    }
    require(set(old_audits) == set(OLD_LABELS), "assess.only_fixed_old_eight")
    rows, templates = [], {}
    store = Store(output / "assessment")
    with execution_guard(online=False) as counts:
        for label in (*OLD_LABELS, *LABELS):
            directory = root / batch_path(label) / "online/sessions" / label
            if label in OLD_LABELS:
                audit = old_audits[label]
                historical = read_json(
                    root / OLD_UTILITY / f"quantity_revision/sessions/{label}.json"
                )
                quantity = dict(historical["answer"])
                quantity["V_quantity"] = quantity["automatic_V_quantity"]
                review_id = "dr_old_" + label.rsplit("_", 1)[1]
            else:
                historical = None
                if (directory / "result.json").exists():
                    audit = audit_session(directory, public, private, expected_system=SYSTEM)
                else:
                    audit = {
                        "terminal": outcomes[label]["terminal"],
                        "raw_model_and_history_verified": False,
                        "raw_final": None,
                        "calculations": [],
                        "calculation_requests": [],
                        "first_final_index": None,
                        "pre_execution_formula_observed": False,
                        "usages": [],
                    }
                quantity = score_quantity(
                    interpret_final(audit["raw_final"], public_quantity_context()),
                    private["reference_exact_value"],
                    public_quantity_context(),
                )
                review_id = registered[label]["review_id"]
            row = record(
                "DR_support_assessment",
                **{
                    k: v
                    for k, v in audit.items()
                    if k
                    not in {
                        "id",
                        "schema_version",
                        "label",
                        "arm",
                        "task_key",
                        "review_id",
                        "automatic_quantity",
                    }
                },
                label=label,
                arm="E",
                task_key="X2",
                review_id=review_id,
                batch="historical_8" if historical else "new_32",
                historical_qualification_id=historical["id"] if historical else None,
                automatic_quantity=quantity,
                historical_calculation_audit_reused_without_rerun=historical is not None,
            )
            raw_messages = {
                int(p.name[:3]): p.read_text()
                for p in sorted((directory / "turns").glob("*_assistant.raw"))
            }
            result = (
                read_json(directory / "result.json")
                if (directory / "result.json").exists()
                else None
            )
            packet = {
                "review_id": review_id,
                "public_document": public,
                "public_quantity_context": public_quantity_context(),
                "raw_messages": raw_messages,
                "raw_final": audit["raw_final"],
                "events": result["events"] if result else [],
                "calculations": audit["calculations"],
                "first_final_index": audit["first_final_index"],
                "terminal": audit["terminal"],
                "review_scope": (
                    "all E/X2, executing assistant, not independent or guaranteed blinded"
                ),
            }
            store.json(f"packets/{review_id}.json", packet)
            store.json(f"sessions/{label}.json", row)
            templates[review_id] = template(row, raw_messages)
            rows.append(row)
        report = record(
            "DR_support_assessment_report",
            rows=rows,
            new_registered=32,
            old_eligibility_candidates=8,
            old_other_40_sessions_not_reassessed=True,
            new_costs=costs(output / "online"),
            model_requests_after_collection=0,
            tokenizer_calls=0,
            Student_calls=0,
        )
        store.json("report.json", report)
        store.json("review_template.json", templates)
        store.json(
            "execution_guards.json", guard_report(counts, phase="DR_support_assessment_no_models")
        )
    store.seal(report_id=report["id"])
    return report


def population_summary(rows, denominator):
    require(len(rows) == denominator, "summary.explicit_batch_denominator")
    return {
        "registered": denominator,
        "complete_valid": sum(r["formula_driven_trace_verified"] for r in rows),
        "quantity_status": dict(Counter(r["answer"]["V_quantity"] for r in rows)),
        "trace_status": dict(Counter(r["trace_status"] for r in rows)),
        "behavior_counts": dict(Counter(r["behavior"] for r in rows)),
        "R_mentioned": sum(r["R_chain"]["public_R_mention"]["status"] == "CONFIRMED" for r in rows),
        "R_execution": dict(Counter(r["R_chain"]["R_execution_status"] for r in rows)),
        "R_source_relation": dict(Counter(r["R_chain"]["R_source_relation_status"] for r in rows)),
        "R_Final_support": dict(Counter(r["R_chain"]["R_Final_support_status"] for r in rows)),
        "valid_pure_D": sum(r["behavior"] == "PURE_D" for r in rows),
        "valid_pure_R": sum(r["behavior"] == "PURE_R" for r in rows),
        "valid_pure_R_yield": f"{sum(r['behavior'] == 'PURE_R' for r in rows)}/{denominator}",
        "provider_probability_or_Student_utility_inferred": False,
    }


def finalize(root, reviews_path):
    root, reviews_path = Path(root), Path(reviews_path).resolve()
    require(
        reviews_path.is_relative_to(root / OUTPUT / "manual_reviews")
        and not reviews_path.is_symlink(),
        "finalize.only_new_manual_reviews",
    )
    history_guard(root)
    verify_preparation(root)
    output = root / OUTPUT
    manifest(output / "assessment")
    assessment = read_json(output / "assessment/report.json")
    reviews = read_json(reviews_path)
    require(
        set(reviews) == {r["review_id"] for r in assessment["rows"]},
        "finalize.every_fixed_candidate_reviewed",
    )
    prototypes = read_json(output / "preparation/private/target_class_prototypes.json")
    ledger = read_json(output / "preparation/target_ledger.json")
    public = read_json(output / "preparation/public/X2.json")
    store = Store(output / "closeout")
    store.write("reviews.original.json", reviews_path.read_bytes())
    rows, package_index, duplicate_keys = [], [], {}
    with execution_guard(online=False) as counts:
        for audit in assessment["rows"]:
            label, review_id = audit["label"], audit["review_id"]
            packet = read_json(output / f"assessment/packets/{review_id}.json")
            raw = {int(k): v for k, v in packet["raw_messages"].items()}
            review = reviews[review_id]
            qualified = qualify(audit, review, raw, public)
            session = bind(root, qualified)
            projection = (
                project_session(session, review["mapping"], ledger["registered_goal_scope"])
                if qualified["formula_driven_trace_verified"]
                else None
            )
            chain = R_evidence_chain(session, review, prototypes, projection)
            chain = record(
                "DR_R_execution_chain",
                **{
                    k: v
                    for k, v in chain.items()
                    if k not in {"id", "schema_version", "original_registered_denominator"}
                },
                registered_batch_denominator=8 if label in OLD_LABELS else 32,
            )
            row = record(
                "DR_support_row",
                **{k: v for k, v in qualified.items() if k not in {"id", "schema_version"}},
                qualification_id=qualified["id"],
                behavior=chain["complete_behavior_label"],
                class_id=class_id(projection)
                if projection and projection["status"] == "MAPPED"
                else None,
                projection_id=projection["id"] if projection else None,
                R_chain=chain,
            )
            store.json(f"sessions/{label}.json", qualified)
            store.json(f"rows/{label}.json", row)
            if projection:
                store.json(f"behavior/{label}.json", projection)
            store.json(f"R_chain/{label}.json", chain)
            if qualified["formula_driven_trace_verified"]:
                positives, excluded = candidates(session)
                targets = []
                for candidate, raw_target in positives:
                    prefix = f"raw_packages/positive/{label}/{candidate['response_index']:03d}"
                    store.json(prefix + ".candidate.json", candidate)
                    store.write(prefix + ".target.raw", raw_target)
                    targets.append(
                        {
                            "prefix": prefix,
                            "response_index": candidate["response_index"],
                            "candidate_id": candidate["id"],
                            "raw_sha256": sha(raw_target),
                        }
                    )
                package = record(
                    "DR_unweighted_original_package",
                    label=label,
                    batch=qualified["batch"],
                    class_id=row["class_id"],
                    behavior=row["behavior"],
                    qualification_id=qualified["id"],
                    source_directory=str(session["directory"].relative_to(root)),
                    source_manifest_id=session["session_manifest_id"],
                    positive_responses=targets,
                    excluded_responses=excluded,
                    token_consumability="NOT_MEASURED",
                    original_E_prefix_unchanged=True,
                    whole_original_session_retained=True,
                    training_weights_assigned=False,
                )
                store.json(f"raw_packages/packages/{label}.json", package)
                package_index.append(package)
            text_key = sha(
                b"\x00".join(session["turns"][i]["raw"] for i in range(len(session["turns"])))
            )
            if session["turns"]:
                duplicate_keys.setdefault(text_key, []).append(label)
            rows.append(row)
        require(
            set(r["label"] for r in rows) == set(OLD_LABELS) | set(LABELS),
            "finalize.exact_eight_plus_thirty_two",
        )
        selection = select_support(rows)
        store.json("support_selection.json", selection)
        store.json(
            "raw_packages/index.json",
            record(
                "DR_original_package_index",
                packages=package_index,
                token_consumability="NOT_MEASURED",
                tokenizer_calls=0,
            ),
        )
        report = record(
            "DR_bounded_support_report",
            scope_status="PASS_AS_SCOPED",
            collection_status="FIXED_32_CLOSED",
            support_status=selection["status"],
            consumable_input_status="NOT_MEASURED",
            source_selection_id=selection["id"],
            target_ledger_id=ledger["id"],
            rows=rows,
            new_batch=population_summary([r for r in rows if r["label"] in LABELS], 32),
            historical_eligibility_batch=population_summary(
                [r for r in rows if r["label"] in OLD_LABELS], 8
            ),
            original_historical_qualification_reference=reference(
                root, OLD_UTILITY + "/quantity_revision/report.json"
            ),
            duplicate_entire_public_response_sequences=[
                {"sha256": key, "labels": labels}
                for key, labels in duplicate_keys.items()
                if len(labels) > 1
            ],
            duplicate_text_not_an_additional_behavior_class=True,
            new_costs=assessment["new_costs"],
            actual_model_requests_after_collection=0,
            new_tokenizer_calls=0,
            Student_training_runs=0,
            Student_sessions=0,
            historical_scores_and_original_classes_unchanged=True,
            no_topup_or_provider_model_equivalence_claim=True,
            next_step=selection["next_step"],
        )
        store.json("report.json", report)
        store.json(
            "execution_guards.json", guard_report(counts, phase="DR_bounded_semantic_closeout")
        )
    verify_preparation(root)
    store.json("history.json", history_guard(root))
    store.seal(report_id=report["id"])
    return report
