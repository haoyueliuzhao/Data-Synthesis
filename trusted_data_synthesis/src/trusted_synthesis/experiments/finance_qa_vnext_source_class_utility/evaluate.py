"""Masked complete-trace assessment, dev selection, and untouched confirmation."""

from collections import Counter
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

from .plan import (
    CONDITIONS,
    GROUPS,
    OUTPUT,
    SEEDS,
    history_guard,
    read_json,
    record,
    require,
    select_candidate,
    sha,
    utility,
)
from .stage import masked_registrations, variant_order
from .student_audit import audit_session
from .student_review import qualify, review_template


def review_map(root, phase):
    path = (
        "preparation/private/dev_review_identity_map.json"
        if phase == "dev"
        else "selection/private/confirm_review_identity_map.json"
    )
    return read_json(root / OUTPUT / path)


def assess(root, phase):
    require(phase in {"dev", "confirm"}, "assess.registered_phase")
    output = root / OUTPUT
    require(not (output / "assessment" / phase).exists(), "assess.once")
    with execution_guard(online=False) as counts:
        mode = "train" if phase == "dev" else "confirm"
        execution = read_json(output / "execution" / mode / "report.json")
        require(execution["status"] == "COMPLETED", "assess.all_workers_completed")
        manifest(output / "execution" / mode)
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        mapping = review_map(root, phase)
        variants = (
            variant_order()
            if phase == "dev"
            else read_json(output / "selection/confirmation_authorization.json")["variants"]
        )
        require(len(mapping) == (108 if phase == "dev" else 144), "assess.full_registered_panel")
        for variant in variants:
            manifest(output / "generation" / phase / variant)
        private = read_json(output / "preparation/private/evaluation_targets.json")
        store = DurableStore(output / "assessment" / phase)
        audits, templates = [], {}
        for rid, registration in sorted(mapping.items()):
            variant, key = registration["variant"], registration["task_key"]
            directory = output / "generation" / phase / variant / "sessions" / key
            public = read_json(output / f"preparation/public/{key}.json")
            identity = read_json(output / "generation" / phase / variant / "identity.json")
            audit = audit_session(directory, public, identity)
            require(
                identity["variant"] == variant and identity["phase"] == phase,
                "assess.exact_model_and_phase",
            )
            store.json(f"audits/{rid}.json", audit)
            actual = read_json(directory / "result.json")
            all_raw = {
                str(item["response_index"]): item["content"]
                for item in actual["attempts"]
                if item["generation_invoked"]
            }
            packet = {
                "review_id": rid,
                "task_key": key,
                "group": registration["group"],
                "public_document": public,
                "raw_messages": audit["raw_messages"],
                "all_generated_public_messages": all_raw,
                "actual_events": actual["events"],
                "calculations": audit["calculations"],
                "raw_final": audit["raw_final"],
                "first_final_index": audit["first_final_index"],
                "terminal": audit["terminal"],
                "source_and_tool_history_audited": True,
                "arm_seed_model_training_logs_omitted": True,
                "public_self_description_may_reveal_behavior": True,
                "not_independent_or_guaranteed_blind": True,
            }
            store.json(f"public_review_packets/{rid}.json", packet)
            template = review_template(audit, public, private[key])
            template["condition_inferred_from_self_description"] = False
            templates[rid] = template
            audits.append(
                {
                    "review_id": rid,
                    **registration,
                    "audit_id": audit["id"],
                    "terminal": audit["terminal"],
                    "model_requests": audit["model_requests"],
                    "tool_calls": audit["tool_calls"],
                }
            )
        store.json("review_template.json", templates)
        report = record(
            "student_assessment_report",
            phase=phase,
            rows=audits,
            registered_sessions=len(mapping),
            all_generation_completed_before_review=True,
            condition_seed_and_training_logs_masked_in_packets=True,
            Teacher_requests=0,
            new_Student_generation=0,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase=phase + "_assessment"))
        seal_directory(store, kind="source_class_assessment_manifest", report_id=report["id"])
    return report


def summarize(rows, variants, per_group):
    result = {}
    for variant in variants:
        own = [r for r in rows if r["variant"] == variant]
        groups = {}
        for group in GROUPS:
            members = [r for r in own if r["group"] == group]
            require(len(members) == per_group, "utility.original_denominator")
            groups[group] = {
                "registered": len(members),
                "complete_trace_PASS": sum(
                    r["qualification"]["complete_verifiable_trajectory"] for r in members
                ),
                "answer_counts": dict(
                    Counter(r["qualification"]["task_answer_status"] for r in members)
                ),
            }
        result[variant] = {
            "registered": len(own),
            "groups": groups,
            "utility": str(
                utility({g: (v["complete_trace_PASS"], v["registered"]) for g, v in groups.items()})
            ),
            "complete_trace_PASS": sum(
                r["qualification"]["complete_verifiable_trajectory"] for r in own
            ),
            "answer_counts": dict(Counter(r["qualification"]["task_answer_status"] for r in own)),
            "delivery_counts": dict(Counter(r["qualification"]["delivery_status"] for r in own)),
            "trace_counts": dict(Counter(r["qualification"]["trace_status"] for r in own)),
            "source_binding_review_counts": dict(
                Counter(r["semantic_review"]["variable_correspondence"]["status"] for r in own)
            ),
            "actual_calculation_session_count": sum(r["actual_calculations"] > 0 for r in own),
            "actual_successful_calculations": sum(r["actual_calculations"] for r in own),
        }
    return result


def finalize(root, phase, reviews_path):
    require(phase in {"dev", "confirm"}, "finalize.registered_phase")
    output = root / OUTPUT
    require(
        reviews_path is not None and not (output / "reviewed" / phase).exists(),
        "finalize.one_review_set_per_phase",
    )
    with execution_guard(online=False) as counts:
        manifest(output / "assessment" / phase)
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        mapping = review_map(root, phase)
        reviews = read_json(reviews_path)
        require(set(reviews) == set(mapping), "finalize.complete_masked_reviews")
        private = read_json(output / "preparation/private/evaluation_targets.json")
        store = DurableStore(output / "reviewed" / phase)
        store.write("reviews.original.json", reviews_path.read_bytes())
        rows = []
        for rid, registration in sorted(mapping.items()):
            key, review = registration["task_key"], reviews[rid]
            public = read_json(output / f"preparation/public/{key}.json")
            audit = read_json(output / "assessment" / phase / f"audits/{rid}.json")
            qualification = qualify(audit, review, public, private[key])
            row = record(
                "reviewed_utility_session",
                review_id=rid,
                **registration,
                qualification=qualification,
                semantic_review={
                    k: review[k]
                    for k in (
                        "formula_applicability",
                        "variable_correspondence",
                        "unit_handling",
                        "publication_alignment",
                        "final_answer_consistency",
                    )
                },
                actual_calculations=len(audit["calculations"]),
                model_requests=audit["model_requests"],
                tool_calls=audit["tool_calls"],
            )
            rows.append(row)
            store.json(f"sessions/{rid}.json", row)
        variants = (
            variant_order()
            if phase == "dev"
            else read_json(output / "selection/confirmation_authorization.json")["variants"]
        )
        by_variant = summarize(rows, variants, 4 if phase == "dev" else 8)
        report = record(
            "complete_trace_utility_report",
            phase=phase,
            rows=rows,
            by_variant=by_variant,
            registered_sessions=len(rows),
            primary_metric="equal-three-group full-trace PASS mean",
            unknowns_kept_in_original_denominators=True,
            task_count=12 if phase == "dev" else 24,
            paired_seed_count=3,
            repeated_seeds_not_independent_tasks=True,
            reviewer_independent_or_completely_blind=False,
            Teacher_requests=0,
            additional_Student_generation=0,
            auxiliary_NLL=0,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase=phase + "_finalize"))
        seal_directory(store, kind="source_class_review_manifest", report_id=report["id"])
    if phase == "dev":
        seal_selection(root, report)
    return report


def seal_selection(root, development):
    output = root / OUTPUT
    require(not (output / "selection").exists(), "selection.once_before_confirmation")
    require(not (output / "generation/confirm").exists(), "selection.no_confirmation_peek")
    utilities = {
        arm: {seed: development["by_variant"][f"{arm}_{seed}"]["utility"] for seed in SEEDS}
        for arm in CONDITIONS
    }
    decision = select_candidate(utilities)
    store = DurableStore(output / "selection")
    store.json("decision.json", decision)
    selected = decision["selected_condition"]
    if decision["confirmation_required"]:
        variants = [f"{arm}_{seed}" for seed in SEEDS for arm in ("pi0", selected)]
        identities = {
            variant: read_json(output / f"training/{variant}/report.json")["id"]
            for variant in variants
        }
        authorization = record(
            "sealed_confirmation_authorization",
            selected_condition=selected,
            development_report_id=development["id"],
            decision_id=decision["id"],
            variants=variants,
            training_report_ids=identities,
            Student_sessions=144,
            no_other_candidate_after_confirmation=True,
            panel_unchanged=True,
        )
        store.json("confirmation_authorization.json", authorization)
        registrations = read_json(output / "preparation/evaluation_registrations.json")["confirm"]
        store.json(
            "private/confirm_review_identity_map.json",
            masked_registrations("confirm", variants, registrations),
        )
    report = record(
        "source_class_selection_seal",
        development_report_id=development["id"],
        decision=decision,
        confirmation_authorized=decision["confirmation_required"],
        no_move_means_no_duplicate_confirmation=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind="source_class_selection_manifest", report_id=report["id"])
    return report


def verify(root):
    """Read-only closeout evidence; no extra model loads, scoring or tokenization."""
    output = root / OUTPUT
    history = history_guard(root)
    verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
    phases = [
        "quantity_revision",
        "materialization",
        "preparation",
        "execution/train",
        "assessment/dev",
        "reviewed/dev",
        "selection",
    ]
    decision = read_json(output / "selection/decision.json")
    confirmation_required = decision["confirmation_required"]
    if confirmation_required:
        phases.extend(["execution/confirm", "assessment/confirm", "reviewed/confirm"])
    manifests = {phase: manifest(output / phase)["id"] for phase in phases}
    training, pairs, generated_sessions, requests, calls = {}, {}, 0, 0, 0
    config = read_json(output / "preparation/training_configuration.json")
    for variant in variant_order():
        manifests["training/" + variant] = manifest(output / "training" / variant)["id"]
        report = read_json(output / f"training/{variant}/report.json")
        identity = read_json(output / f"training/{variant}/identity.json")
        require(
            report["optimizer_updates"] == report["full_passes"] == 10
            and report["actual_supervised_tokens"] == config["supervised_tokens_per_run"]
            and report["actual_sequence_tokens"] == config["sequence_tokens_per_run"],
            "verify.exact_training_budget",
        )
        adapter = output / f"training/{variant}/adapter.safetensors"
        require(
            sha(adapter.read_bytes()) == report["final_adapter"]["sha256"],
            "verify.final_adapter_bytes",
        )
        require(
            read_json(output / f"worker_guards/train_{variant}.json")["all_zero"],
            "verify.training_network_private_guards",
        )
        training[variant] = identity
    for seed in SEEDS:
        identities = [training[f"{arm}_{seed}"] for arm in CONDITIONS]
        equal = {}
        for field in (
            "initial_adapter_parameter_sha256",
            "initial_CPU_rng_sha256",
            "initial_CUDA_rng_sha256",
            "orders",
            "physical_row_reference_sha256",
        ):
            equal[field] = all(item[field] == identities[0][field] for item in identities)
        require(
            all(equal.values()) and all(i["optimizer_initial_state_empty"] for i in identities),
            "verify.paired_initialization_orders_and_empty_optimizer",
        )
        pairs[str(seed)] = equal
    dev = read_json(output / "reviewed/dev/report.json")
    confirm = read_json(output / "reviewed/confirm/report.json") if confirmation_required else None
    for phase, report in (("dev", dev), ("confirm", confirm)):
        if report is None:
            continue
        for variant in report["by_variant"]:
            manifests[f"generation/{phase}/{variant}"] = manifest(
                output / "generation" / phase / variant
            )["id"]
            generated = read_json(output / f"generation/{phase}/{variant}/report.json")
            generated_sessions += generated["sessions"]
            requests += sum(r["model_requests"] for r in generated["rows"])
            calls += sum(r["tool_calls"] for r in generated["rows"])
            if phase == "confirm":
                require(
                    read_json(output / f"worker_guards/confirm_{variant}.json")["all_zero"],
                    "verify.confirmation_network_private_guards",
                )
    require(
        generated_sessions == (252 if confirmation_required else 108),
        "verify.no_unregistered_Student_sessions",
    )
    contrast = None
    if confirm:
        selected = decision["selected_condition"]
        gains = {
            str(seed): str(
                Fraction(confirm["by_variant"][f"{selected}_{seed}"]["utility"])
                - Fraction(confirm["by_variant"][f"pi0_{seed}"]["utility"])
            )
            for seed in SEEDS
        }
        groups = {}
        for group in GROUPS:
            per_seed = {}
            for seed in SEEDS:
                first = confirm["by_variant"][f"{selected}_{seed}"]["groups"][group]
                base = confirm["by_variant"][f"pi0_{seed}"]["groups"][group]
                per_seed[str(seed)] = str(
                    Fraction(first["complete_trace_PASS"], first["registered"])
                    - Fraction(base["complete_trace_PASS"], base["registered"])
                )
            groups[group] = per_seed
        contrast = {
            "selected_condition": selected,
            "paired_seed_gains": gains,
            "paired_mean_gain": str(sum(map(Fraction, gains.values())) / 3),
            "task_group_paired_seed_gains": groups,
            "positive_mean_is_not_stable_or_lossless_improvement": True,
        }
    return record(
        "source_class_completion_verification",
        status="COMPLETED_AS_BOUNDED",
        historical_integrity=history,
        phase_manifest_ids=manifests,
        paired_training_checks=pairs,
        actual_training_runs=9,
        supervised_tokens_all_runs=9 * config["supervised_tokens_per_run"],
        sequence_tokens_all_runs=9 * config["sequence_tokens_per_run"],
        actual_Student_sessions=generated_sessions,
        actual_generation_requests=requests,
        actual_tool_calls=calls,
        actual_Teacher_requests=0,
        development_selection=decision,
        confirmation_contrast=contrast,
        confirmation_status="COMPLETED" if confirmation_required else "NOT_RUN_BASELINE_SELECTED",
        same_task_greedy_auxiliary_NLL_and_B0=0,
        theoretical_Contribution_established=False,
        scope="fixed support, full original material kernel, tasks and budget; local evidence only",
    )
