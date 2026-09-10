"""Offline common-target reduction, execution-linked review and unchanged-panel side analysis."""

from collections import Counter

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_directory,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate

from .plan import (
    ASSESSMENT_KIND,
    CLOSEOUT_KIND,
    EXECUTION_KIND,
    GENERATION_KIND,
    OUTPUT,
    PARENT,
    SCORE_KIND,
    SEEDS,
    TRAINED,
    VARIANTS,
    configuration,
    read_json,
    record,
    reference,
    require,
)

ROUTES = {
    "balance_difference",
    "period_movements",
    "actual_dual_check",
    "other_verifiable",
    "unresolved",
}
EXPECTED_FACTS = {
    "balance_difference": {"source:t8c1n0", "source:t4c1n0"},
    "period_movements": {"source:t5c1n0", "source:t6c1n0", "source:t7c1n0"},
}
# These annotations concern already published results, not the six new L1 outputs.
OLD_CHANGED_CASES = {
    "11/R2": (["formula"], "P uses the requested interest/income ratio; Q inverts it."),
    "11/R4": (
        ["source", "formula"],
        "P uses operating cash flow as free cash flow; Q uses the reported FCF relation.",
    ),
    "29/R6": (
        ["source", "publication"],
        "P explicitly cites statutory capital for surplus in Final; "
        "Q's source binding is coherent.",
    ),
    "47/T2": (["interface"], "Q's expression-syntax failures continue without Final; P delivers."),
    "47/T3": (
        ["source"],
        "Q explicitly binds amounts to date/year locations, including 31/2004; P uses balances.",
    ),
    "47/T6": (
        ["formula", "publication"],
        "Both compute positive 191 with problematic pre-call direction; "
        "P publishes decline, Q does not.",
    ),
    "47/R2": (["formula"], "P inverts the requested ratio; Q uses the requested direction."),
}


def compare_scores(scores):
    require(set(scores) == set(VARIANTS), "diagnostic.seven_scores")
    pairs = []
    for seed in SEEDS:
        p, q = scores[f"P_{seed}"], scores[f"Q_{seed}"]
        pairs.append(
            {
                "seed": seed,
                "Q_minus_P_common_objectives": {
                    arm: q["common_objectives"][arm] - p["common_objectives"][arm]
                    for arm in ("P", "Q")
                },
                "delta_C": q["C"] - p["C"],
                "split_delta_C": {
                    kind: q["splits"][kind]["C_kind_normalized"]
                    - p["splits"][kind]["C_kind_normalized"]
                    for kind in ("calculate", "Final")
                },
                "split_delta_C_original_package_contributions": {
                    kind: q["splits"][kind]["C_original_package_contribution"]
                    - p["splits"][kind]["C_original_package_contribution"]
                    for kind in ("calculate", "Final")
                },
            }
        )
    return record(
        "common_target_comparison",
        models=scores,
        pairs=pairs,
        negative_delta_C_count=sum(p["delta_C"] < 0 for p in pairs),
        estimand="fixed original target text relative fitting, not behavioral-class probability",
        no_exponentiation_or_normalized_route_probability=True,
        no_independent_36_task_or_three_seed_population_inference=True,
    )


def route_template(audit):
    return {
        "audit_id": audit["id"],
        "author": "",
        "offline_post_generation": True,
        "observed_executed_structure": "unresolved",
        "components": [],
        "final_consumed_call_id": None,
        "final_evidence": [],
        "explanation": "",
        "semantic_review_not_automatic_route_proof": True,
    }


def validate_route(audit, review, grade, private):
    require(
        review["audit_id"] == audit["id"]
        and review["offline_post_generation"] is True
        and bool(review["author"].strip())
        and bool(review["explanation"].strip()),
        "route.explicit_offline_review",
    )
    require(review["semantic_review_not_automatic_route_proof"] is True, "route.disclosed_review")
    route = review["observed_executed_structure"]
    require(route in ROUTES, "route.open_unresolved_category")
    calculations = {c["call_id"]: c for c in audit["calculations"]}
    raw = {int(k): v for k, v in audit["raw_messages"].items()}

    def evidence(items, cutoff, final=False):
        require(bool(items), "route.actual_public_evidence_required")
        for e in items:
            require(
                type(e["response_index"]) is int
                and e["response_index"] in raw
                and isinstance(e["quote"], str)
                and bool(e["quote"])
                and e["quote"] in raw[e["response_index"]]
                and (e["response_index"] == cutoff if final else e["response_index"] <= cutoff),
                "route.actual_scoped_public_quote",
            )

    components = review["components"]
    for component in components:
        call_id = component["call_id"]
        require(call_id in calculations, "route.actual_successful_calculation_required")
        calc = calculations[call_id]
        require(
            component["actual_expression"] == calc["original_expression"], "route.actual_expression"
        )
        require(
            bool(component["public_relation_and_binding_explanation"].strip()),
            "route.source_role_reasoning",
        )
        evidence(component["evidence"], calc["response_index"])
        facts = component["source_fact_ids"]
        require(
            bool(facts) and len(set(facts)) == len(facts) and set(facts) <= set(private["facts"]),
            "route.original_public_source_facts",
        )
        if component["structure"] in EXPECTED_FACTS:
            require(
                set(facts) == EXPECTED_FACTS[component["structure"]],
                "route.sufficient_route_sources",
            )
        else:
            require(component["structure"] == "other_verifiable", "route.component_structure")
    call_ids = [c["call_id"] for c in components]
    require(len(set(call_ids)) == len(call_ids), "route.no_double_counted_execution")
    structures = {c["structure"] for c in components}
    if route == "actual_dual_check":
        require(
            len(components) >= 2 and set(EXPECTED_FACTS) <= structures,
            "route.two_actual_executed_relations_not_mention",
        )
    elif route != "unresolved":
        require(bool(components) and structures == {route}, "route.matches_executed_components")
    final_id = review["final_consumed_call_id"]
    if final_id is not None:
        require(
            audit["first_final_index"] is not None and final_id in call_ids,
            "route.actual_Final_consumption",
        )
        evidence(review["final_evidence"], audit["first_final_index"], final=True)
        require(
            final_id == grade["original_calculation_quantity"]["call_id"],
            "route.qualified_Final_lineage",
        )
    valid = bool(
        route != "unresolved" and final_id is not None and grade["complete_verifiable_trajectory"]
    )
    return record(
        "reviewed_original_L1_route",
        audit_id=audit["id"],
        observed_executed_structure=route,
        valid_complete_trajectory_route=valid,
        components=components,
        final_consumed_call_id=final_id,
        explanation=review["explanation"],
        original_class_identity_reused_as_runtime_identity=False,
        number_18_or_alternative_mention_alone_is_not_route_admission=True,
        semantic_review_not_blind_or_independent_expert=True,
    )


def side_analysis(root):
    old_path = f"{PARENT}/closeout/report.json"
    old = read_json(root / old_path)
    old_reviews = read_json(root / PARENT / "closeout/reviews.json")["reviews"]
    by_key = {g["key"]: g for g in old["grades"]}
    changed, answer, trace = [], Counter(), Counter()
    for seed in SEEDS:
        for task in [*(f"T{i}" for i in range(1, 7)), *(f"R{i}" for i in range(1, 7))]:
            p, q = by_key[f"P_{seed}/{task}"], by_key[f"Q_{seed}/{task}"]
            a = int(q["task_answer_status"] == "PASS") - int(p["task_answer_status"] == "PASS")
            t = int(q["complete_verifiable_trajectory"]) - int(p["complete_verifiable_trajectory"])
            answer[a] += 1
            trace[t] += 1
            if a or t:
                key = f"{seed}/{task}"
                require(key in OLD_CHANGED_CASES, "side.frozen_existing_cases")
                layers, explanation = OLD_CHANGED_CASES[key]
                audit_refs = [
                    reference(root, f"{PARENT}/assessment/audits/{v}_{seed}/{task}.json")
                    for v in ("P", "Q")
                ]
                changed.append(
                    {
                        "pair": key,
                        "layers": layers,
                        "explanation": explanation,
                        "Q_minus_P_answer_PASS": a,
                        "Q_minus_P_trace_PASS": t,
                        "unchanged_P_grade": p,
                        "unchanged_Q_grade": q,
                        "original_reviews": {
                            v: old_reviews[f"{v}_{seed}/{task}"] for v in ("P", "Q")
                        },
                        "original_audit_references": audit_refs,
                    }
                )
    require(len(changed) == 7, "side.exact_seven_existing_changed_pairs")
    transfer = [g for g in old["grades"] if g["group"] == "transfer" and g["variant"] != "B0"]
    successful = [g for g in transfer if g["complete_verifiable_trajectory"]]
    return record(
        "unchanged_panel_side_analysis",
        original_report_id=old["id"],
        original_report_reference=reference(root, old_path),
        old_sessions=84,
        original_scores_recomputed=False,
        sessions_regenerated=0,
        matched_pairs=36,
        distinct_source_tasks=12,
        changed_pairs=changed,
        answer_PASS_indicator_changes={str(k): answer[k] for k in (-1, 0, 1)},
        trace_PASS_indicator_changes={str(k): trace[k] for k in (-1, 0, 1)},
        successful_transfer_existing_routes=[
            {"key": g["key"], "grade_id": g["id"], "route_observation": g["route_observation"]}
            for g in successful
        ],
        transfer_counts={
            arm: {
                "sessions": 18,
                "answer_PASS": sum(
                    g["task_answer_status"] == "PASS"
                    for g in transfer
                    if g["variant"].startswith(arm)
                ),
                "trace_PASS": sum(
                    g["complete_verifiable_trajectory"]
                    for g in transfer
                    if g["variant"].startswith(arm)
                ),
            }
            for arm in ("P", "Q")
        },
        interpretation=(
            "Existing successful transfer routes use endpoints/adjacent years. The public tasks "
            "permit those sufficient relations and do not require the extra L1 movement route. "
            "P's 18/18 transfer answers leave a local answer ceiling, "
            "but 14/18 traces are not saturated. "
            "This does not establish a ceiling as the cause of absent Q benefit."
        ),
        classifications_are_non_blind_offline_interpretation_not_new_scores=True,
    )


def assess(root):
    from .scoring import summarize
    from .stage import check_preparation

    prepared = check_preparation(root)
    output = root / OUTPUT
    verify_directory(output / "execution", kind=EXECUTION_KIND)
    view = read_json(output / "preparation/weight_view.json")
    models = read_json(output / "preparation/models.json")
    scores, generations = {}, {}
    for variant in VARIANTS:
        directory = output / "scoring" / variant
        verify_directory(directory, kind=SCORE_KIND)
        report = read_json(directory / "report.json")
        require(
            report["variant"] == variant
            and report["configuration_id"] == configuration()["id"]
            and report["weight_view_id"] == view["id"]
            and report["model_identity_id"] == models[variant]["id"]
            and read_json(directory / "identity.json") == models[variant]
            and report["rows"] == 36
            and report["target_positions"] == 4793
            and report["sequence_positions"] == 232603,
            "diagnostic.same_score_configuration_population_and_model",
        )
        recomputed = summarize(
            view, [read_json(directory / f"rows/{i:03d}.json") for i in range(36)]
        )
        require(
            all(report[k] == v for k, v in recomputed.items()), "diagnostic.persisted_NLL_reduction"
        )
        require(
            read_json(directory / "parameters_before.json")
            == read_json(directory / "parameters_after.json"),
            "diagnostic.score_parameters_unchanged",
        )
        scores[variant] = report
    public = read_json(output / "preparation/public/L1.json")
    private = read_json(output / "preparation/private/L1.json")
    store = DurableStore(output / "assessment")
    templates, routes, audits = {}, {}, {}
    for variant in TRAINED:
        directory = output / "generation" / variant
        verify_directory(directory, kind=GENERATION_KIND)
        identity = read_json(directory / "identity.json")
        gen = read_json(directory / "report.json")
        require(
            identity == models[variant]
            and gen["configuration_id"] == configuration()["id"]
            and gen["inherited_decoder_configuration_id"]
            == configuration()["parent_decoder_configuration_id"],
            "diagnostic.same_generation_configuration_and_model",
        )
        require(
            gen["parameter_sha256"] == scores[variant]["parameter_sha256"],
            "diagnostic.same_fixed_score_generate_model",
        )
        require(
            read_json(directory / "parameters_before.json")
            == read_json(directory / "parameters_after.json"),
            "diagnostic.generation_parameters_unchanged",
        )
        require(
            gen["initial_messages_sha256"] == prepared["initial_messages_sha256"],
            "diagnostic.same_unhinted_L1_input",
        )
        audit = evaluate.audit_session(directory / "sessions/L1", public, identity)
        require(audit["result_id"] == gen["result_id"], "diagnostic.actual_session_join")
        store.json(f"audits/{variant}.json", audit)
        templates[variant] = evaluate.review_template(audit, public, private)
        routes[variant] = route_template(audit)
        audits[variant] = audit["id"]
        generations[variant] = gen
    comparison = compare_scores(scores)
    store.json("score_comparison.json", comparison)
    store.json("side_analysis.json", side_analysis(root))
    store.json("review_templates.json", {"reviews": templates, "routes": routes})
    report = record(
        "response_assessment",
        preparation_id=prepared["id"],
        score_comparison_id=comparison["id"],
        audits=audits,
        generations=generations,
        policy_id=evaluate.policy()["id"],
        generation_sessions=6,
        no_scores_before_explicit_semantic_review=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind=ASSESSMENT_KIND, report_id=report["id"])
    return report


def finalize(root, reviews_path):
    from .stage import check_preparation

    check_preparation(root)
    output = root / OUTPUT
    verify_directory(output / "assessment", kind=ASSESSMENT_KIND)
    reviews = read_json(reviews_path)
    require(
        set(reviews["reviews"]) == set(reviews["routes"]) == set(TRAINED),
        "diagnostic.six_explicit_reviews",
    )
    public = read_json(output / "preparation/public/L1.json")
    private = read_json(output / "preparation/private/L1.json")
    grades, routes = {}, {}
    for variant in TRAINED:
        audit = read_json(output / "assessment/audits" / f"{variant}.json")
        grades[variant] = evaluate.qualify(audit, reviews["reviews"][variant], public, private)
        routes[variant] = validate_route(
            audit, reviews["routes"][variant], grades[variant], private
        )
    # Validate all six before creating exclusive closeout; never leave a partial graded population.
    store = DurableStore(output / "closeout")
    store.json("reviews.json", reviews)
    for variant in TRAINED:
        store.json(f"grades/{variant}.json", grades[variant])
        store.json(f"routes/{variant}.json", routes[variant])
    comparison = read_json(output / "assessment/score_comparison.json")
    report = record(
        "fixed_response_diagnostic_closeout",
        grades=grades,
        routes=routes,
        common_target_pairs=comparison["pairs"],
        negative_delta_C_count=comparison["negative_delta_C_count"],
        task_answer_status_counts=dict(Counter(g["task_answer_status"] for g in grades.values())),
        complete_trace_PASS=sum(g["complete_verifiable_trajectory"] for g in grades.values()),
        observed_route_counts=dict(
            Counter(r["observed_executed_structure"] for r in routes.values())
        ),
        valid_route_counts=dict(
            Counter(
                r["observed_executed_structure"]
                for r in routes.values()
                if r["valid_complete_trajectory_route"]
            )
        ),
        score_models=7,
        score_rows=252,
        new_L1_sessions=6,
        old_panel_sessions=84,
        teacher_calls=0,
        new_training_updates=0,
        probability_or_generalization_claim=False,
        stop_at_registered_boundary_regardless_of_Q_preference=True,
        scientific_limits=[
            "single R text",
            "three paired seeds",
            "one training task generation",
            "greedy once",
            "non-blind agent semantic review",
            "no new transfer evidence",
        ],
    )
    store.json("report.json", report)
    seal_directory(store, kind=CLOSEOUT_KIND, report_id=report["id"])
    return report
