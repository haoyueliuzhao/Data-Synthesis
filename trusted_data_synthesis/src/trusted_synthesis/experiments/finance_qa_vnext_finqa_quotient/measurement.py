"""Separate condition-local finite laws and trajectory-level materialization indices."""

from collections import Counter
from fractions import Fraction

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require

from .projection import compare
from .rules import rule


def operational_inventory(graph):
    return dict(
        Counter(
            node["kind"] + ":" + node.get("operation", "") + ":" + node.get("disposition", "")
            for node in graph["nodes"].values()
            if node["kind"] != "source"
        )
    )


def measure(population, projections):
    laws, states, assignments, pairs = {}, [], [], []
    for view in ("V0", "V1"):
        registered = [r for r in population["rows"] if r["view_condition"] == view]
        successful = [r for r in registered if r["complete_valid"]]
        require(
            len(registered) == 4 and all(r["task_key"] == "J2" for r in successful),
            "distribution.original_task_population",
        )
        classes, unknown = [], []
        for row in successful:
            projection = projections[row["label"]]
            if projection["status"] != "MAPPED":
                unknown.append(row["label"])
                assignments.append(
                    {
                        "label": row["label"],
                        "view_condition": view,
                        "status": "UNDETERMINED",
                        "state_id": None,
                    }
                )
                continue
            found = None
            for group in classes:
                reference = projections[group["representative"]]
                comparison = compare(reference["graph"], projection["graph"])
                pair = record(
                    "finqa_condition_local_comparison",
                    view_condition=view,
                    left=group["representative"],
                    right=row["label"],
                    rule_id=rule()["id"],
                    operational_inventory_without_judgments={
                        "left": operational_inventory(reference["graph"]),
                        "right": operational_inventory(projection["graph"]),
                    },
                    **comparison,
                )
                pairs.append(pair)
                if comparison["relation"] == "EQUIVALENT":
                    found = group
                    group["equivalence_witness_ids"].append(pair["id"])
                    break
                require(comparison["relation"] == "DIFFERENT", "distribution.common_graph_domain")
            if found is None:
                found = {
                    "representative": row["label"],
                    "members": [],
                    "equivalence_witness_ids": [],
                }
                classes.append(found)
            found["members"].append(row["label"])
        m = len(successful)
        distribution = []
        for group in classes:
            state = record(
                "finqa_finite_behavior_state",
                version=rule()["version"],
                view_condition=view,
                task_key="J2",
                rule_id=rule()["id"],
                representative_projection_id=projections[group["representative"]]["id"],
                identity_scope="condition-local finite representative, not universal class ID",
                **group,
            )
            states.append(state)
            distribution.append(
                {
                    "state_id": state["id"],
                    "count": len(group["members"]),
                    "mass": str(Fraction(len(group["members"]), m)),
                }
            )
            for label in group["members"]:
                assignments.append(
                    {
                        "label": label,
                        "view_condition": view,
                        "status": "MAPPED",
                        "state_id": state["id"],
                    }
                )
        laws[view] = {
            "original_registered": 4,
            "original_task_weights": {"E1": "1/2", "J2": "1/2"},
            "original_valid": m,
            "original_failed": 4 - m,
            "J2": {
                "registered": 2,
                "valid_denominator": m,
                "mapped_count": m - len(unknown),
                "unresolved_count": len(unknown),
                "unresolved_labels": unknown,
                "unresolved_valid_mass": str(Fraction(len(unknown), m)) if m else None,
                "full_pi": distribution if m and not unknown else None,
                "known_state_mass": distribution,
                "law_conditioning": f"{view},E,P,R,J2,Y=1",
            },
            "E1": {
                "registered": 2,
                "valid_denominator": 0,
                "full_pi": None,
                "reason": "zero_success_sample_not_proof_of_empty_solution_space",
            },
            "fixed_two_task_training_dataset": False,
        }
    return record(
        "finqa_finite_quotient_measurement",
        by_view=laws,
        states=states,
        assignments=assignments,
        within_condition_pairs=pairs,
        pooled_success_law=None,
        cross_view_behavior_class_pool_created=False,
        finite_development_only=True,
        novelty=None,
        contribution=None,
        training_utility=None,
    )


def mechanism_comparisons(projections):
    mapped = [p for p in projections.values() if p["status"] == "MAPPED"]
    if not mapped:
        return {"status": "UNDETERMINED", "pairs": []}
    reference = mapped[0]
    pairs = [
        {
            "left": reference["label"],
            "right": p["label"],
            **compare(reference["support_graph"], p["support_graph"]),
        }
        for p in mapped[1:]
    ]
    return {
        "status": "DESCRIPTIVE_SUPPORT_ONLY",
        "pairs": pairs,
        "full_behavior_relation": False,
        "cross_view_sampling_pool": False,
        "all_mapped_support_graphs_same": all(p["relation"] == "EQUIVALENT" for p in pairs),
        "unmapped_labels": [p["label"] for p in projections.values() if p["status"] != "MAPPED"],
    }


def package_index(session, candidates, token_rows, assignment):
    by_id = {r["row_id"]: r for r in token_rows}
    require(set(by_id) == {r["id"] for r in candidates}, "package.every_candidate_encoded")
    require(
        len(candidates) == sum(t["event"]["admitted"] for t in session["turns"]),
        "package.all_admitted_rows",
    )
    return record(
        "finqa_original_trajectory_package",
        label=session["row"]["label"],
        task_key="J2",
        view_condition=session["row"]["view_condition"],
        registration_id=session["row"]["registration"]["id"],
        validity_id=session["audit"]["id"],
        behavior_assignment=assignment,
        original_interactions=[t["binding"]["id"] for t in session["turns"]],
        candidate_ids=[r["id"] for r in candidates],
        token_representation_ids=[r["id"] for r in token_rows],
        original_submission_count=len(session["turns"]),
        admitted_unit_count=len(candidates),
        unadmitted_submissions=[
            t["event"]["submission_count"] for t in session["turns"] if not t["event"]["admitted"]
        ],
        whole_package_token_fit=all(r["consumable_token_representation"] for r in token_rows),
        sequence_length_min=min(r["sequence_length"] for r in token_rows),
        sequence_length_max=max(r["sequence_length"] for r in token_rows),
        target_token_count=sum(r["target_token_count"] for r in token_rows),
        sampler_path=[
            "generation_condition",
            "task",
            "behavior_state",
            "whole_trajectory",
            "units",
        ],
        unit_loss_reduction="not instantiated; must be declared with future training objective",
        assigned_training_weight=None,
        uniform_row_sampling_authorized=False,
        student_forward=False,
        class_weight_update=False,
    )
