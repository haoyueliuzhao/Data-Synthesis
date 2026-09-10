"""Finite within-task measurement for this new, fixed T-condition population.

Only immutable validity rows and already produced projections enter this module.
It never projects a response, executes arithmetic, assigns training weights, or
reads empirical files. Missing mappings retain their original valid mass. Source
provenance and the exact full 72-row cohort are asserted by the stage caller;
synthetic subsets are accepted here for bounded local controls.
"""

from collections import Counter
from fractions import Fraction
from itertools import combinations

from .plan import TASKS, condition, encode, record, require, sha

SIGNATURE_FIELDS = {
    "fixed_condition",
    "task_version",
    "source_document_id",
    "goal_scope",
    "answer_source_normal_form",
    "active_support",
    "substantive_revision_path",
    "evidenced_independent_cross_checks",
}
REPLICATES = 24


def _signature(projection):
    signature = projection.get("behavior_signature")
    require(isinstance(signature, dict), "measurement.mapped_signature_required")
    require(set(signature) == SIGNATURE_FIELDS, "measurement.complete_signature_required")
    require(
        signature["fixed_condition"] == condition()["id"],
        "measurement.only_new_fixed_condition",
    )
    for field in ("task_version", "source_document_id"):
        require(
            isinstance(projection.get(field), str)
            and projection[field]
            and signature[field] == projection[field],
            "measurement.signature_identity",
        )
    require(isinstance(signature["goal_scope"], dict), "measurement.goal_scope_required")
    require(
        isinstance(signature["answer_source_normal_form"], dict),
        "measurement.symbolic_relation_required",
    )
    for field in ("substantive_revision_path", "evidenced_independent_cross_checks"):
        require(isinstance(signature[field], list), "measurement.revision_and_check_lists")
    support = signature["active_support"]
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
    """Compare full finite signatures, never just a number or a digest.

    Unsupported or absent mappings are UNDETERMINED, not additional classes. A
    different task version/document is outside the comparison domain; measure()
    rejects such mixed versions within one registered task before making pairs.
    """
    if left is None or right is None:
        return "UNDETERMINED"
    if any(
        left.get(field) != right.get(field)
        for field in ("task_key", "task_version", "source_document_id")
    ):
        return "NOT_COMPARABLE"
    if left.get("status") != "MAPPED" or right.get("status") != "MAPPED":
        return "UNDETERMINED"
    first, second = _signature(left), _signature(right)
    return "EQUIVALENT" if encode(first) == encode(second) else "DISTINCT"


def _mass(numerator, denominator):
    return str(Fraction(numerator, denominator)) if denominator else None


def measure(projections, source_rows):
    """Keep m/24 validity yield separate from n/m conditional class mass.

    The stage supplies all 72 new registrations, including terminated/unknown rows
    without a usable result. This function permits smaller synthetic input sets but
    never increases the 24-replicate task budget. It does not infer validity from
    mapping status, final numbers, or local two-support witnesses.
    """
    require(isinstance(source_rows, list), "measurement.original_rows_list")
    require(isinstance(projections, list), "measurement.projections_list")
    rows = {}
    for row in source_rows:
        require(isinstance(row, dict), "measurement.original_row_object")
        label = row.get("label")
        require(
            isinstance(label, str) and label and label not in rows,
            "measurement.unique_source_labels",
        )
        require(row.get("arm") == "T", "measurement.only_new_T_population")
        require(row.get("task_key") in TASKS, "measurement.registered_task")
        require(
            type(row.get("formula_driven_trace_verified")) is bool,
            "measurement.original_boolean_validity",
        )
        if "condition_id" in row:
            require(
                row["condition_id"] == condition()["id"], "measurement.only_new_fixed_condition"
            )
        rows[label] = row
    for task in TASKS:
        require(
            sum(row["task_key"] == task for row in source_rows) <= REPLICATES,
            "measurement.no_extra_replicates",
        )

    indexed, task_identity = {}, {}
    for projection in projections:
        require(isinstance(projection, dict), "measurement.projection_object")
        label = projection.get("session_label")
        require(label in rows and label not in indexed, "measurement.unique_registered_projection")
        source = rows[label]
        require(source["formula_driven_trace_verified"], "measurement.original_validity_required")
        require(projection.get("task_key") == source["task_key"], "measurement.task_not_reassigned")
        require(projection.get("population", "T") == "T", "measurement.only_new_T_population")
        require(
            projection.get("status") in {"MAPPED", "UNDETERMINED"},
            "measurement.projection_status",
        )
        if "id" in source:
            require(
                projection.get("source_closeout_id") == source["id"],
                "measurement.original_source_row_id",
            )
        identity = tuple(projection.get(field) for field in ("task_version", "source_document_id"))
        require(
            all(isinstance(value, str) and value for value in identity),
            "measurement.original_task_identity_required",
        )
        task = source["task_key"]
        if task in task_identity:
            require(
                task_identity[task] == identity, "measurement.one_version_and_document_per_task"
            )
        task_identity[task] = identity
        if projection["status"] == "MAPPED":
            _signature(projection)
        else:
            require(
                projection.get("behavior_key") is None
                and projection.get("behavior_signature") is None,
                "measurement.unknown_is_not_a_class",
            )
        indexed[label] = projection

    tasks, all_pairs, session_class_ids, unavailable = {}, [], {}, []
    for task in TASKS:
        task_rows = sorted(
            (row for row in source_rows if row["task_key"] == task),
            key=lambda row: row["label"],
        )
        valid_rows = [row for row in task_rows if row["formula_driven_trace_verified"]]
        valid_labels = [row["label"] for row in valid_rows]
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
                        "reason": projection.get("reason") if projection else "missing_projection",
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
        classes = []
        for key, group in sorted(groups.items()):
            class_id = "new_open_support_class:" + sha(
                encode(
                    {
                        "fixed_condition": condition()["id"],
                        "task_key": task,
                        "behavior_key": key,
                    }
                )
            )
            for label in group["session_labels"]:
                session_class_ids[label] = class_id
            classes.append(
                {
                    "class_id": class_id,
                    "population": "T",
                    "task_key": task,
                    "behavior_key": key,
                    **group,
                    "count": len(group["session_labels"]),
                    "mass": _mass(len(group["session_labels"]), denominator),
                }
            )
        pairs = []
        for left_label, right_label in combinations(valid_labels, 2):
            left, right = indexed.get(left_label), indexed.get(right_label)
            status = compare(left, right)
            require(
                status in {"EQUIVALENT", "DISTINCT", "UNDETERMINED"},
                "measurement.within_task_pair_scope",
            )
            pairs.append(
                record(
                    "new_valid_within_task_pair",
                    population="T",
                    fixed_condition=condition()["id"],
                    task_key=task,
                    session_labels=[left_label, right_label],
                    projection_ids=[item.get("id") if item else None for item in (left, right)],
                    behavior_keys=[
                        item.get("behavior_key") if item else None for item in (left, right)
                    ],
                    status=status,
                    full_signature_including_revisions_and_cross_checks_compared=True,
                    old_sessions_or_other_conditions_in_pair=False,
                )
            )
        require(len(pairs) == denominator * (denominator - 1) // 2, "measurement.all_valid_pairs")
        all_pairs.extend(pairs)
        witnesses = [pair for pair in pairs if pair["status"] == "DISTINCT"]
        if denominator < 2:
            unavailable.append(
                {
                    "task_key": task,
                    "valid_count": denominator,
                    "reason": "fewer_than_two_valid_trajectories",
                }
            )
        masses = {item["class_id"]: item["mass"] for item in classes}
        complete = denominator > 0 and not unresolved
        known_lower_bound = max(len(classes) - 1, 0)
        require(
            sum(item["count"] for item in classes) + len(unresolved) == denominator,
            "measurement.valid_denominator_conserved",
        )
        tasks[task] = record(
            "new_task_conditional_measurement",
            population="T",
            fixed_condition=condition()["id"],
            task_key=task,
            original_task_marginal="1/6",
            planned_registered_count=REPLICATES,
            registered_count=len(task_rows),
            complete_registered_task=len(task_rows) == REPLICATES,
            original_registered_session_labels=[row["label"] for row in task_rows],
            original_invalid_count=len(task_rows) - denominator,
            valid_denominator=denominator,
            valid_session_labels=valid_labels,
            original_full_trajectory_yield={
                "numerator": denominator,
                "denominator": REPLICATES,
                "fraction": _mass(denominator, REPLICATES),
            },
            mapped_count=denominator - len(unresolved),
            known_class_count=len(classes),
            known_classes=classes,
            known_class_masses=masses,
            unresolved_count=len(unresolved),
            unresolved_mass=_mass(len(unresolved), denominator),
            unresolved_records=unresolved,
            conditional_distribution=masses if complete else None,
            distribution_state="COMPLETE"
            if complete
            else "PARTIALLY_MAPPED"
            if denominator
            else "NO_VALID_SUPPORT",
            valid_pair_count=len(pairs),
            valid_pair_ids=[pair["id"] for pair in pairs],
            valid_pair_status_counts=dict(
                sorted(Counter(pair["status"] for pair in pairs).items())
            ),
            local_two_support_witness=bool(witnesses),
            local_two_support_witness_pair_ids=[pair["id"] for pair in witnesses],
            local_witness_does_not_establish_complete_distribution=True,
            observed_class_probability_degrees_of_freedom=known_lower_bound
            if complete or not denominator
            else None,
            known_class_probability_degrees_of_freedom_lower_bound=known_lower_bound,
            no_valid_support_does_not_establish_no_behavior=denominator == 0,
            reweighted_over_mapped_subset=False,
            invalid_source_rows_preserved_not_regraded=True,
            mapping_undetermined_does_not_change_original_validity=True,
        )

    valid_count = sum(task["valid_denominator"] for task in tasks.values())
    unresolved_count = sum(task["unresolved_count"] for task in tasks.values())
    lower_bound = sum(
        task["known_class_probability_degrees_of_freedom_lower_bound"] for task in tasks.values()
    )
    population = record(
        "new_fixed_T_population_measurement",
        population="T",
        fixed_condition=condition()["id"],
        registered_count=len(source_rows),
        planned_registered_count=len(TASKS) * REPLICATES,
        original_valid_count=valid_count,
        original_full_trajectory_yield={
            "numerator": valid_count,
            "denominator": len(TASKS) * REPLICATES,
            "fraction": _mass(valid_count, len(TASKS) * REPLICATES),
        },
        mapped_count=valid_count - unresolved_count,
        unresolved_count=unresolved_count,
        tasks=tasks,
        pooled_with_other_population=False,
    )
    return record(
        "new_open_support_measurement",
        fixed_condition=condition()["id"],
        primary_population="T",
        original_task_marginal={task: "1/6" for task in TASKS},
        populations={"T": population},
        primary_pairs=all_pairs,
        primary_pair_status_counts=dict(
            sorted(Counter(pair["status"] for pair in all_pairs).items())
        ),
        expected_primary_pair_tasks=list(TASKS),
        unavailable_primary_pairs=unavailable,
        maximum_planned_valid_pairs=len(TASKS) * 6,
        local_two_support_witness_tasks=[
            task for task in TASKS if tasks[task]["local_two_support_witness"]
        ],
        local_two_support_witness_does_not_require_all_valid_mapped=True,
        class_probability_degrees_of_freedom=lower_bound if not unresolved_count else None,
        known_class_probability_degrees_of_freedom_lower_bound=lower_bound,
        complete_supported_task_degrees_of_freedom=sum(
            task["observed_class_probability_degrees_of_freedom"]
            for task in tasks.values()
            if task["distribution_state"] == "COMPLETE"
        ),
        degrees_of_freedom_scope=(
            "Observed supported taskwise class simplexes only; zero-valid tasks add no "
            "observed dimension and do not establish impossible behavior; any valid unresolved "
            "mapping makes the total incomplete."
        ),
        session_class_ids=session_class_ids,
        condition_pooling=False,
        old_trajectories_in_frequency_denominator=False,
        denominator_policy=(
            "m/4 original validity yield; n/m class mass with all originally valid new sessions, "
            "including unmapped and missing projections"
        ),
        original_invalid_records_retained=len(source_rows) - valid_count,
        source_row_count=len(source_rows),
        source_projection_count=len(projections),
        complete_registered_population=all(
            task["complete_registered_task"] for task in tasks.values()
        ),
        full_cohort_source_identity_requires_stage_caller=True,
        six_task_training_distribution_implemented=False,
        training_weights_assigned=False,
        provider_calls=0,
        no_valid_support_is_not_a_claim_of_no_possible_behavior=True,
    )
