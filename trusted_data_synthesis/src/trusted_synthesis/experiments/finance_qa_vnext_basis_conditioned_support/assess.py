"""Assess all 32 new sessions, freeze actual-method selection, check only its 16 packages."""

from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    public_quantity_context,
)
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
from .costs import costs
from .plan import (
    GENERATION_CONDITIONS,
    LABELS,
    METHODS,
    OUTPUT,
    SYSTEMS,
    TASKS,
    fixed_selection,
    read_json,
    record,
    reference,
    require,
    sha,
)
from .projection import project_session
from .review import qualify, template
from .source import bind, candidates


def raw_messages(directory):
    """Preserve exact original UTF-8 newlines for quote validation, not text I/O normalization."""
    return {
        int(path.name[:3]): path.read_bytes().decode("utf-8")
        for path in sorted((Path(directory) / "turns").glob("*_assistant.raw"))
    }


def scope_status(consumed):
    if any(
        failure["phase"] in {"original_source_validation", "tokenizer_loading"}
        for failure in consumed["failures"]
    ):
        return "STOPPED_SOURCE_OR_ASSET_NOT_CERTIFIED"
    return "PASS_AS_SCOPED"


def assess(root):
    root = Path(root)
    history_guard(root)
    verify_preparation(root)
    output = root / OUTPUT
    manifest(output / "online")
    collected = read_json(output / "online/report.json")
    require(
        collected["registered"] == 32 and collected["all_workers_terminated"],
        "assess.all_32_finished_before_any_review",
    )
    registered = read_json(output / "preparation/registrations.json")
    require([r["label"] for r in registered] == list(LABELS), "assess.fixed_registration_order")
    outcomes = {r["label"]: r for r in collected["rows"]}
    require(set(outcomes) == set(LABELS), "assess.exact_new_population")
    private = read_json(output / "preparation/private/evaluation_targets.json")
    rows, templates = [], {}
    store = Store(output / "assessment")
    with execution_guard(online=False) as counts:
        for registration in sorted(registered, key=lambda r: r["review_id"]):
            label, key, g, review_id = (
                registration[k] for k in ("label", "task_key", "arm", "review_id")
            )
            public = read_json(output / f"preparation/public/{key}.json")
            directory = output / "online/sessions" / label
            result_path = directory / "result.json"
            if result_path.exists():
                audit = audit_session(directory, public, private[key], expected_system=SYSTEMS[g])
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
                private[key]["reference_exact_value"],
                public_quantity_context(),
            )
            row = record(
                "basis_support_assessment",
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
                arm=g,
                task_key=key,
                review_id=review_id,
                batch="new_basis_conditioned_32",
                replicate=registration["replicate"],
                condition_id=registration["condition_id"],
                automatic_quantity=quantity,
                historical_target_package=False,
            )
            raw = raw_messages(directory)
            result = read_json(result_path) if result_path.exists() else None
            packet = {
                "review_id": review_id,
                "public_document": public,
                "public_quantity_context": public_quantity_context(),
                "raw_messages": raw,
                "raw_final": audit["raw_final"],
                "events": result["events"] if result else [],
                "calculations": audit["calculations"],
                "first_final_index": audit["first_final_index"],
                "terminal": audit["terminal"],
                "requested_g_model_costs_SYSTEM_and_replicate_omitted": True,
                "self_description_may_reveal_guidance": True,
                "review_scope": "executing assistant team; not independent or guaranteed blinded",
            }
            store.json(f"packets/{review_id}.json", packet)
            store.json(f"sessions/{label}.json", row)
            templates[review_id] = template(row, raw)
            rows.append(row)
        report = record(
            "basis_support_assessment_report",
            rows=rows,
            new_registered=32,
            historical_candidates=0,
            all_generation_completed_before_review=True,
            new_costs=costs(output / "online"),
            model_requests_after_collection=0,
            tokenizer_calls=0,
            Student_calls=0,
        )
        store.json("report.json", report)
        store.json("review_template.json", templates)
        store.json(
            "execution_guards.json", guard_report(counts, phase="basis_assessment_no_models")
        )
    store.seal(report_id=report["id"])
    return report


def population_summary(rows):
    """Keep every registered/valid unknown in its declared denominator."""
    valid = [r for r in rows if r["formula_driven_trace_verified"]]
    mapped = [r for r in valid if r["full_mapping_status"] == "MAPPED"]
    method_counts = Counter(r["method_stratum"] for r in rows)
    valid_method_counts = Counter(r["method_stratum"] for r in valid)
    eligible = Counter(r["method_stratum"] for r in mapped if r["method_stratum"] in METHODS)
    return {
        "registered": len(rows),
        "complete_valid": len(valid),
        "quantity_status": dict(Counter(r["answer"]["V_quantity"] for r in rows)),
        "trace_status": dict(Counter(r["trace_status"] for r in rows)),
        "actual_method_all_rows": dict(method_counts),
        "actual_method_complete_valid": dict(valid_method_counts),
        "complete_valid_full_mapped": len(mapped),
        "complete_valid_full_unmapped": len(valid) - len(mapped),
        "eligible_unique_method": dict(eligible),
        "valid_full_mapped_unique_method_yields": {
            method: f"{eligible[method]}/{len(rows)}" for method in METHODS
        },
        "mapped_mass_among_all_valid_denominator": len(valid),
        "unmapped_valid_mass": f"{len(valid) - len(mapped)}/{len(valid)}" if valid else None,
        "unmapped_valid_mass_dropped_or_renormalized": False,
        "fine_class_counts": dict(Counter(r["class_id"] for r in mapped)),
        "guidance_compliance": dict(Counter(r["guidance_compliance"] for r in rows)),
        "provider_probability_or_Student_utility_inferred": False,
    }


def finalize(root, reviews_path):
    from .consumption import check_selected
    from .methods import classify_method

    root, reviews_path = Path(root), Path(reviews_path).resolve()
    output = root / OUTPUT
    require(
        reviews_path.is_relative_to(output / "manual_reviews") and not reviews_path.is_symlink(),
        "finalize.only_new_manual_reviews",
    )
    history_guard(root)
    verify_preparation(root)
    manifest(output / "assessment")
    assessment = read_json(output / "assessment/report.json")
    reviews = read_json(reviews_path)
    require(
        len(assessment["rows"]) == 32
        and {r["label"] for r in assessment["rows"]} == set(LABELS)
        and set(reviews) == {r["review_id"] for r in assessment["rows"]},
        "finalize.every_new_candidate_reviewed_once",
    )
    prototypes = read_json(output / "preparation/private/target_class_prototypes.json")
    ledgers = read_json(output / "preparation/target_ledgers.json")
    cross_context = read_json(output / "preparation/private/x2_cross_quantity_context.json")
    store = Store(output / "qualification")
    store.write("reviews.original.json", reviews_path.read_bytes())
    rows, packages, duplicate_keys, original_candidates = [], [], {}, {}
    with execution_guard(online=False) as counts:
        for audit in assessment["rows"]:
            label, review_id, key = audit["label"], audit["review_id"], audit["task_key"]
            packet = read_json(output / f"assessment/packets/{review_id}.json")
            raw = {int(k): v for k, v in packet["raw_messages"].items()}
            public = read_json(output / f"preparation/public/{key}.json")
            review = reviews[review_id]
            qualified = qualify(audit, review, raw, public)
            session = bind(root, qualified)
            goal = ledgers[key]["registered_goal_scope"]
            projection = (
                project_session(
                    session,
                    review["mapping"],
                    goal,
                    condition_id=audit["condition_id"],
                    cross_quantity_context=cross_context if key == "X2" else None,
                )
                if qualified["formula_driven_trace_verified"]
                else None
            )
            method = classify_method(
                session,
                review["mapping"],
                goal,
                prototypes[key],
                audit["condition_id"],
                projection=projection,
            )
            actual = method["method_stratum"]
            mapped = method["full_mapping_status"] == "MAPPED"
            require(
                method["raw_admissible"]
                == bool(
                    qualified["formula_driven_trace_verified"] and mapped and actual in METHODS
                ),
                "finalize.method_and_full_class_admission_agree",
            )
            require(
                not mapped
                or (
                    qualified["formula_driven_trace_verified"]
                    and projection is not None
                    and projection["status"] == "MAPPED"
                    and method["fine_class_id"]
                ),
                "finalize.full_class_requires_actual_qualified_projection",
            )
            row = record(
                "basis_support_row",
                **{k: v for k, v in qualified.items() if k not in {"id", "schema_version"}},
                qualification_id=qualified["id"],
                method_stratum=actual,
                method_record_id=method["id"],
                guidance_compliance=(
                    "COMPLIANT"
                    if actual == audit["arm"]
                    else "NONCOMPLIANT"
                    if actual in METHODS
                    else "UNDETERMINED"
                ),
                full_mapping_status=method["full_mapping_status"],
                class_id=method["fine_class_id"] if mapped else None,
                projection_id=projection["id"] if projection else None,
            )
            store.json(f"sessions/{label}.json", qualified)
            store.json(f"rows/{label}.json", row)
            store.json(f"methods/{label}.json", method)
            if projection:
                store.json(f"behavior/{label}.json", projection)
            if qualified["formula_driven_trace_verified"]:
                positives, excluded = candidates(session)
                original_candidates[label] = positives
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
                    "basis_unweighted_original_package",
                    label=label,
                    task_key=key,
                    requested_basis=audit["arm"],
                    condition_id=audit["condition_id"],
                    actual_method=actual,
                    full_mapping_status=row["full_mapping_status"],
                    class_id=row["class_id"],
                    qualification_id=qualified["id"],
                    source_directory=str(session["directory"].relative_to(root)),
                    source_manifest_id=session["session_manifest_id"],
                    positive_responses=targets,
                    excluded_responses=excluded,
                    token_consumability="NOT_MEASURED",
                    original_requested_guidance_prefix_unchanged=True,
                    whole_original_session_retained=True,
                    training_weights_assigned=False,
                )
                store.json(f"raw_packages/packages/{label}.json", package)
                packages.append(package)
            if session["turns"]:
                text_key = sha(b"\x00".join(turn["raw"] for turn in session["turns"]))
                duplicate_keys.setdefault(text_key, []).append(label)
            rows.append(row)
        require({r["label"] for r in rows} == set(LABELS), "finalize.only_new_32")
        qualification_report = record(
            "basis_qualification_report", rows=rows, total=population_summary(rows)
        )
        store.json("report.json", qualification_report)
        store.json(
            "raw_packages/index.json", record("basis_original_package_index", packages=packages)
        )
        store.json(
            "execution_guards.json", guard_report(counts, phase="basis_qualification_zero_models")
        )
        qualification_manifest = store.seal(report_id=qualification_report["id"])

        # All identities and first-four choices are sealed BEFORE loading any tokenizer.
        selection = fixed_selection(rows)
        choice_store = Store(output / "selection")
        choice_store.json("support_selection.json", selection)
        choice_store.json(
            "qualification_reference.json",
            {
                "manifest_id": qualification_manifest["id"],
                "report": reference(root, OUTPUT + "/qualification/report.json"),
            },
        )
        choice_manifest = choice_store.seal(selection_id=selection["id"])
        require(
            manifest(output / "selection") == choice_manifest, "selection.sealed_before_tokenizer"
        )

        consumed = check_selected(
            root,
            selection,
            original_candidates,
            expected_policy=read_json(output / "preparation/representation_policy.json"),
        )
        consumption_store = Store(output / "consumption")
        consumption_store.json("report.json", consumed)
        consumption_store.json(
            "selection_reference.json",
            {
                "selection_id": selection["id"],
                "selection_manifest_id": choice_manifest["id"],
            },
        )
        consumption_store.json(
            "execution_guards.json", guard_report(counts, phase="basis_representation_zero_Student")
        )
        consumption_store.seal(report_id=consumed["id"])

        closeout = Store(output / "closeout")
        report = record(
            "basis_bounded_support_report",
            scope_status=scope_status(consumed),
            collection_status="FIXED_32_CLOSED",
            raw_support_status=selection["status"],
            consumable_input_status=consumed["status"],
            source_selection_id=selection["id"],
            selection_manifest_id=choice_manifest["id"],
            consumption_report_id=consumed["id"],
            target_ledger_ids={key: ledgers[key]["id"] for key in TASKS},
            rows=rows,
            total=population_summary(rows),
            task_requested_guidance_cells={
                key: {
                    g: population_summary(
                        [r for r in rows if r["task_key"] == key and r["arm"] == g]
                    )
                    for g in GENERATION_CONDITIONS
                }
                for key in TASKS
            },
            actual_method_fine_class_mix={
                key: {
                    method: dict(
                        Counter(
                            (r["arm"] + ":" + r["class_id"])
                            for r in rows
                            if r["task_key"] == key
                            and r["method_stratum"] == method
                            and r["formula_driven_trace_verified"]
                            and r["full_mapping_status"] == "MAPPED"
                        )
                    )
                    for method in METHODS
                }
                for key in TASKS
            },
            duplicate_entire_public_response_sequences=[
                {"sha256": key, "labels": labels}
                for key, labels in duplicate_keys.items()
                if len(labels) > 1
            ],
            duplicate_text_not_an_additional_method=True,
            new_costs=assessment["new_costs"],
            actual_model_requests_after_collection=0,
            new_tokenizer_load_attempts=consumed["tokenizer_load_attempts"],
            selected_positive_response_checks=consumed["candidate_encoding_attempts"],
            Student_training_runs=0,
            Student_sessions=0,
            NLL=0,
            training_allowed=False,
            full_27_package_training_population_or_weight_views_created=False,
            requested_g_and_actual_m_are_separate=True,
            no_fine_class_coarsening_or_historical_relabeling=True,
            known_history_and_final_multi_amount_parser_unchanged=True,
            fixed_conditioned_kernel_not_a_prompt_isolated_method_effect=True,
            no_topup_or_provider_weight_equivalence_claim=True,
            next_step=(
                "close_support_stage; any future utility study needs a separate "
                "acceptance and freeze"
            ),
        )
        closeout.json("report.json", report)
        closeout.json("execution_guards.json", guard_report(counts, phase="basis_support_complete"))
    verify_preparation(root)
    closeout.json("history.json", history_guard(root))
    closeout.seal(report_id=report["id"])
    return report
