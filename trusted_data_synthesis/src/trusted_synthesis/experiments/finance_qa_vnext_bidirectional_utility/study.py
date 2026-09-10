"""Full-signature input gate, exact class-mass weights and utility selection."""

import ast
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.canonical import (
    normalize_expression,
)

from .plan import (
    CONDITIONS,
    CONTROL_LABELS,
    CONTROLS,
    OUTPUT,
    SEEDS,
    TASKS,
    TRAIN_TASKS,
    condition,
    encode,
    read_json,
    record,
    require,
    sha,
)


def target_prototypes(panel, public):
    """Private source-defined classes, not model-authored or observed trajectories."""
    result = {}
    for key in TASKS:
        task = panel.tasks[key]
        prototypes = {}
        for route, field in (("D", "expression"), ("R", "alternative")):
            expression = task["original_private_spec"][field]
            bindings = {}

            def visit(item, address, *, bound_task=task, bound_bindings=bindings):
                if isinstance(item, ast.Name):
                    sid = bound_task["source_bindings"][item.id]
                    value = bound_task["facts"][sid]["value"]
                    bound_bindings[address] = dict(
                        kind="source",
                        source_id=sid,
                        source_exact=value,
                        executed_exact=value,
                        attribution="precall_private_source_definition_not_model_evidence",
                        evidence_verified=True,
                    )
                elif isinstance(item, ast.Constant) and type(item.value) is int:
                    bound_bindings[address] = dict(
                        kind="constant",
                        value=str(item.value),
                        reason="precall dimensional constant",
                        evidence_verified=True,
                    )
                elif isinstance(item, ast.BinOp):
                    visit(item.left, address + ".left")
                    visit(item.right, address + ".right")
                elif isinstance(item, ast.UnaryOp):
                    visit(item.operand, address + ".operand")
                else:
                    raise ValueError("prototype.only_registered_training_expressions")

            visit(ast.parse(expression, mode="eval").body, "body")
            normal = normalize_expression(expression, bindings)
            require(normal["status"] == "MAPPED", "prototype.exact_finite_relation")
            signature = dict(
                fixed_condition=condition()["id"],
                task_version=public[key]["task_id"],
                source_document_id=public[key]["id"],
                goal_scope=task["goal_scope"],
                answer_source_normal_form=normal["normal_form"],
                active_support=normal["active_source_ids"],
                substantive_revision_path=[],
                evidenced_independent_cross_checks=[],
            )
            prototypes[route] = record(
                "precall_target_class",
                task_key=key,
                route=route,
                signature=signature,
                behavior_key=sha(encode(signature)),
                actual_model_trajectory=False,
                source_definition_only=True,
            )
        require(
            prototypes["D"]["signature"] != prototypes["R"]["signature"],
            "prototype.distinct_complete_classes",
        )
        result[key] = prototypes
    return record(
        "precall_target_class_index",
        tasks=result,
        ordered_selection="replicate ascending",
        minimum_independent_packages_per_target_class=4,
    )


def classify(projection, prototypes):
    if projection["status"] != "MAPPED":
        return "UNDETERMINED"
    signature = projection["behavior_signature"]
    require(projection["behavior_key"] == sha(encode(signature)), "gate.complete_signature_hash")
    for route, prototype in prototypes.items():
        if encode(signature) == encode(prototype["signature"]):
            return route
    return "OTHER_VALID_CLASS"


def fixed_selection(eligible):
    """No top-up, post-outcome class replacement, or index-dependent exception."""
    ordered = sorted(eligible, key=lambda label: int(label.rsplit("_", 1)[1]))
    require(len(ordered) == len(set(ordered)), "gate.independent_registration_identity")
    return dict(
        eligible=ordered,
        eligible_count=len(ordered),
        sufficient=len(ordered) >= 4,
        train=ordered[:3] if len(ordered) >= 4 else [],
        diagnostic=ordered[3:4] if len(ordered) >= 4 else [],
        unselected=ordered[4:] if len(ordered) >= 4 else ordered,
    )


def support_gate(root, projections, materialization):
    prototypes = read_json(root / OUTPUT / "preparation/private/target_class_prototypes.json")
    packages = {p["session_label"]: p for p in materialization["packages"]}
    classes = {key: {route: [] for route in ("D", "R")} for key in TASKS}
    observations = []
    for projection in projections:
        label, key = projection["session_label"], projection["task_key"]
        route = classify(projection, prototypes["tasks"][key])
        consumable = packages[label]["whole_package_token_consumable"]
        if route in {"D", "R"} and consumable:
            classes[key][route].append(label)
        observations.append(
            dict(
                session_label=label,
                task_key=key,
                target_class=route,
                original_full_trace_valid=True,
                consumable=consumable,
                behavior_key=projection["behavior_key"],
                behavior_projection_id=projection["id"],
            )
        )
    selection = {
        key: {route: fixed_selection(labels) for route, labels in routes.items()}
        for key, routes in classes.items()
    }
    missing = [
        f"{key}/{route}"
        for key, routes in selection.items()
        for route, row in routes.items()
        if not row["sufficient"]
    ]
    established = not missing
    train = (
        [
            label
            for routes in selection.values()
            for row in routes.values()
            for label in row["train"]
        ]
        if established
        else []
    )
    diagnostic = (
        [
            label
            for routes in selection.values()
            for row in routes.values()
            for label in row["diagnostic"]
        ]
        if established
        else []
    )
    duplicate_groups = {}
    for package in packages.values():
        label = package["session_label"]
        full = read_json(root / OUTPUT / f"closeout/materialization/packages/{label}.json")
        target_digests = [
            sha(
                (root / OUTPUT / "closeout/materialization" / (prefix + ".target.raw")).read_bytes()
            )
            for prefix in full["positive_row_paths"]
        ]
        duplicate_groups.setdefault(sha(encode(target_digests)), []).append(label)
    duplicates = [labels for labels in duplicate_groups.values() if len(labels) > 1]
    diagnostic_duplicates = {
        label: sorted(
            other for group in duplicates if label in group for other in group if other in train
        )
        for label in diagnostic
    }
    return record(
        "fixed_input_gate",
        status="INPUT_ESTABLISHED" if established else "INPUT_INADEQUATE",
        target_class_index_id=prototypes["id"],
        minimum_per_class=4,
        by_task=selection,
        missing_target_classes=missing,
        observations=observations,
        selected_new_training_labels=train,
        selected_same_task_diagnostic_labels=diagnostic,
        accepted_old_control_labels=list(CONTROL_LABELS),
        would_train_packages=len(train) + 9 if established else 0,
        exact_positive_target_text_duplicate_groups=duplicates,
        diagnostic_target_text_matches_selected_training=diagnostic_duplicates,
        duplication_is_not_new_behavior_or_unseen_text_generalization=True,
        mapping_unknown_preserves_original_validity=True,
        other_valid_classes_are_not_failures=True,
        insufficient_class_action=(
            "close input result; no more sampling, no task replacement, no training or Student "
            "evaluation"
        ),
        selected_fraction_is_not_natural_class_mass=True,
        old_L1_greedy_sessions_added=0,
    )


def package_weights(condition_name):
    require(condition_name in CONDITIONS, "weights.registered_condition")
    weights = {}
    for key in TRAIN_TASKS:
        if key in CONTROLS:
            for i in range(3):
                weights[(key, "control", i)] = Fraction(1, 18)
            continue
        r_mass = Fraction(1, 3)
        if condition_name == key + "+":
            r_mass += Fraction(1, 6)
        elif condition_name == key + "-":
            r_mass -= Fraction(1, 6)
        for route, mass in (("D", 1 - r_mass), ("R", r_mass)):
            for i in range(3):
                weights[(key, route, i)] = Fraction(1, 6) * mass / 3
    require(len(weights) == 27 and sum(weights.values()) == 1, "weights.total_mass")
    for key in TRAIN_TASKS:
        require(
            sum(w for (task, _, _), w in weights.items() if task == key) == Fraction(1, 6),
            "weights.fixed_task_marginal",
        )
    return weights


def utility(group_counts):
    require(
        set(group_counts) == {"dual_sufficient", "detail_related", "other_finance"},
        "utility.three_groups",
    )
    value = Fraction(0)
    for passed, registered in group_counts.values():
        require(
            type(passed) is int
            and type(registered) is int
            and 0 <= passed <= registered
            and registered > 0,
            "utility.actual_full_denominator",
        )
        value += Fraction(passed, registered) / 3
    return value


def select_candidate(dev_utilities):
    require(set(dev_utilities) == set(CONDITIONS), "selection.all_seven_conditions")
    require(
        all(set(rows) == set(SEEDS) for rows in dev_utilities.values()),
        "selection.all_three_paired_seeds",
    )
    gains = {
        name: sum(
            Fraction(dev_utilities[name][s]) - Fraction(dev_utilities["P_new"][s]) for s in SEEDS
        )
        / 3
        for name in CONDITIONS
    }
    selected = "P_new"
    for name in CONDITIONS[1:]:
        if gains[name] > gains[selected]:
            selected = name
    directions = {
        key: sum(
            Fraction(dev_utilities[key + "+"][s]) - Fraction(dev_utilities[key + "-"][s])
            for s in SEEDS
        )
        / 3
        / Fraction(1, 3)
        for key in TASKS
    }
    return record(
        "development_candidate_selection",
        selected_condition=selected,
        paired_mean_gain={k: str(v) for k, v in gains.items()},
        finite_delta_directional_utility={k: str(v) for k, v in directions.items()},
        delta="1/6",
        theory_Contribution_established=False,
        tie_priority=list(CONDITIONS),
        positive_gain_required=True,
        confirmation_required=selected != "P_new",
        no_second_candidate_after_confirmation=True,
    )
