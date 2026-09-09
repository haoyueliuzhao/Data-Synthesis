"""Finite conditional measurement of immutable valid source trajectories.

This module does not project sessions or read empirical artifacts.  It receives
already projected records and original validity rows.  Missing mapping support
retains its share of the original valid denominator; A is never pooled with T.
"""

from collections import Counter
from fractions import Fraction

from .plan import TASKS, encode, record, require, sha

POPULATIONS = ("T", "A")
PRIMARY_PAIR_TASKS = tuple(task for task in TASKS if task != "N3")
SIGNATURE_FIELDS = {
    "population",
    "task_version",
    "source_document_id",
    "goal_scope",
    "active_source_support",
    "answer_connected_source_rational_form",
    "substantive_public_revision_path",
}


def _signature(projection):
    signature = projection.get("behavior_signature")
    require(isinstance(signature, dict), "measurement.mapped_signature_required")
    require(SIGNATURE_FIELDS.issubset(signature), "measurement.complete_signature_required")
    for field in ("population", "task_version", "source_document_id"):
        require(signature[field] == projection[field], "measurement.signature_identity")
    require(isinstance(signature["goal_scope"], dict), "measurement.goal_scope_required")
    require(
        isinstance(signature["answer_connected_source_rational_form"], dict),
        "measurement.symbolic_relation_required",
    )
    require(
        isinstance(signature["substantive_public_revision_path"], list),
        "measurement.revision_path_required",
    )
    support = signature["active_source_support"]
    require(
        isinstance(support, list)
        and all(isinstance(item, str) and item for item in support)
        and support == sorted(set(support)),
        "measurement.canonical_source_support_required",
    )
    require(
        projection.get("behavior_key") == sha(encode(signature)),
        "measurement.behavior_key_matches_complete_signature",
    )
    return signature


def compare(left, right):
    """Compare complete finite projections, not arithmetic or final numbers alone.

    Broken MAPPED records raise an integrity error.  A genuine unsupported
    projection instead returns UNDETERMINED.  Different conditions, tasks, task
    versions, or source documents are outside the comparison domain.
    """
    scope = ("population", "task_key", "task_version", "source_document_id")
    if any(left.get(field) != right.get(field) for field in scope):
        return "NOT_COMPARABLE"
    if left.get("status") != "MAPPED" or right.get("status") != "MAPPED":
        return "UNDETERMINED"
    left_signature, right_signature = _signature(left), _signature(right)
    return "EQUIVALENT" if encode(left_signature) == encode(right_signature) else "DISTINCT"


def _mass(numerator, denominator):
    return str(Fraction(numerator, denominator)) if denominator else None


def measure(projections, source_rows):
    """Measure supplied projections without changing any original outcome.

    All six tasks remain in each condition.  Class mass uses the count of source
    rows with formula_driven_trace_verified=True, including unmapped or missing
    projections.  Complete conditional distributions are null unless the valid
    denominator is positive and every valid row maps.  No training weights are
    assigned.  Synthetic subsets are allowed for controls; collection identity
    and original full-cohort cardinalities are verified by the stage caller.
    """
    require(isinstance(projections, list), "measurement.projections_list")
    require(isinstance(source_rows, list), "measurement.original_rows_list")
    rows = {}
    for row in source_rows:
        require(isinstance(row, dict), "measurement.original_row_object")
        label = row.get("label")
        require(
            isinstance(label, str) and label and label not in rows,
            "measurement.unique_source_labels",
        )
        require(row.get("arm") in POPULATIONS, "measurement.registered_population")
        require(row.get("task_key") in TASKS, "measurement.registered_task")
        require(
            type(row.get("formula_driven_trace_verified")) is bool,
            "measurement.original_boolean_validity",
        )
        rows[label] = row
    indexed = {}
    for projection in projections:
        require(isinstance(projection, dict), "measurement.projection_object")
        label = projection.get("session_label")
        require(label in rows and label not in indexed, "measurement.unique_registered_projection")
        source = rows[label]
        require(source["formula_driven_trace_verified"], "measurement.original_validity_required")
        require(
            projection.get("population") == source["arm"], "measurement.population_not_reassigned"
        )
        require(projection.get("task_key") == source["task_key"], "measurement.task_not_reassigned")
        require(
            projection.get("status") in {"MAPPED", "UNDETERMINED"}, "measurement.projection_status"
        )
        if "id" in source:
            require(
                projection.get("source_closeout_id") == source["id"],
                "measurement.original_source_row_id",
            )
        if projection["status"] == "MAPPED":
            _signature(projection)
        indexed[label] = projection

    populations, session_class_ids = {}, {}
    for population in POPULATIONS:
        task_records = {}
        population_rows = [row for row in source_rows if row["arm"] == population]
        for task in TASKS:
            task_rows = sorted(
                [row for row in population_rows if row["task_key"] == task],
                key=lambda row: row["label"],
            )
            valid_rows = [row for row in task_rows if row["formula_driven_trace_verified"]]
            denominator = len(valid_rows)
            groups, unresolved = {}, []
            for row in valid_rows:
                label = row["label"]
                session_class_ids[label] = None
                projection = indexed.get(label)
                if projection is None or projection["status"] == "UNDETERMINED":
                    unresolved.append(
                        {
                            "session_label": label,
                            "projection_id": projection.get("id") if projection else None,
                            "reason": projection.get("reason")
                            if projection
                            else "missing_projection",
                        }
                    )
                    continue
                key = projection["behavior_key"]
                if key not in groups:
                    groups[key] = {
                        "behavior_signature": projection["behavior_signature"],
                        "session_labels": [],
                        "projection_ids": [],
                    }
                require(
                    encode(groups[key]["behavior_signature"])
                    == encode(projection["behavior_signature"]),
                    "measurement.no_hash_only_equivalence",
                )
                groups[key]["session_labels"].append(label)
                groups[key]["projection_ids"].append(projection.get("id"))
            known_classes = []
            for key, group in sorted(groups.items()):
                class_id = "open_behavior_class:" + sha(
                    encode({"population": population, "task_key": task, "behavior_key": key})
                )
                for label in group["session_labels"]:
                    session_class_ids[label] = class_id
                known_classes.append(
                    {
                        "class_id": class_id,
                        "population": population,
                        "task_key": task,
                        "behavior_key": key,
                        **group,
                        "count": len(group["session_labels"]),
                        "mass": _mass(len(group["session_labels"]), denominator),
                    }
                )
            masses = {item["class_id"]: item["mass"] for item in known_classes}
            complete = denominator > 0 and not unresolved
            require(
                sum(item["count"] for item in known_classes) + len(unresolved) == denominator,
                "measurement.valid_denominator_conserved",
            )
            task_records[task] = record(
                "task_conditional_measurement",
                population=population,
                task_key=task,
                original_task_marginal="1/6",
                registered_count=len(task_rows),
                original_registered_session_labels=[row["label"] for row in task_rows],
                valid_denominator=denominator,
                valid_session_labels=[row["label"] for row in valid_rows],
                mapped_count=denominator - len(unresolved),
                known_classes=known_classes,
                known_class_masses=masses,
                unresolved_count=len(unresolved),
                unresolved_mass=_mass(len(unresolved), denominator),
                unresolved_records=unresolved,
                conditional_distribution=masses if complete else None,
                distribution_state=(
                    "COMPLETE"
                    if complete
                    else "PARTIALLY_MAPPED"
                    if denominator
                    else "NO_VALID_SUPPORT"
                ),
                no_valid_support_does_not_establish_no_behavior=denominator == 0,
                reweighted_over_mapped_subset=False,
                invalid_source_rows_preserved_not_regraded=True,
            )
        valid_count = sum(task["valid_denominator"] for task in task_records.values())
        populations[population] = record(
            "population_measurement",
            population=population,
            role="primary" if population == "T" else "separate_descriptive_only",
            registered_count=len(population_rows),
            original_valid_count=valid_count,
            original_full_trajectory_yield={
                "numerator": valid_count,
                "denominator": len(population_rows),
                "fraction": _mass(valid_count, len(population_rows)),
            },
            mapped_count=sum(task["mapped_count"] for task in task_records.values()),
            unresolved_count=sum(task["unresolved_count"] for task in task_records.values()),
            tasks=task_records,
            pooled_with_other_population=False,
        )

    pairs, unavailable = [], []
    for task in PRIMARY_PAIR_TASKS:
        valid_labels = populations["T"]["tasks"][task]["valid_session_labels"]
        if len(valid_labels) != 2:
            unavailable.append(
                {
                    "task_key": task,
                    "reason": "valid_pair_cardinality_not_two",
                    "valid_count": len(valid_labels),
                }
            )
            continue
        left, right = (indexed.get(label) for label in valid_labels)
        status = compare(left, right) if left is not None and right is not None else "UNDETERMINED"
        pairs.append(
            record(
                "primary_within_task_pair",
                population="T",
                task_key=task,
                session_labels=valid_labels,
                projection_ids=[item.get("id") if item else None for item in (left, right)],
                status=status,
                behavior_keys=[
                    item.get("behavior_key") if item else None for item in (left, right)
                ],
                substantive_public_revisions_included=True,
                no_cross_population_pair=True,
            )
        )
    return record(
        "open_finite_behavior_measurement",
        primary_population="T",
        original_task_marginal={task: "1/6" for task in TASKS},
        populations=populations,
        primary_pairs=pairs,
        primary_pair_status_counts=dict(sorted(Counter(pair["status"] for pair in pairs).items())),
        expected_primary_pair_tasks=list(PRIMARY_PAIR_TASKS),
        unavailable_primary_pairs=unavailable,
        session_class_ids=session_class_ids,
        condition_pooling=False,
        denominator_policy="all originally valid rows, including unmapped or missing projections",
        original_invalid_records_retained=len(source_rows) - len(session_class_ids),
        source_row_count=len(source_rows),
        source_projection_count=len(projections),
        six_task_training_distribution_implemented=False,
        training_weights_assigned=False,
        provider_calls=0,
        N3_regraded=False,
        no_valid_support_is_not_a_claim_of_no_possible_behavior=True,
    )
