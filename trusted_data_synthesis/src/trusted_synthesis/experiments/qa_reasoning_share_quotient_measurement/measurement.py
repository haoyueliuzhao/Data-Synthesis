"""Finite relation consistency, qualified-only Assignment and empirical denominators."""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .comparison import canonical_graph, compare_projections
from .models import EQUIVALENT, UNDETERMINED, condition_binding, record, require


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    require(
        type(numerator) is int and type(denominator) is int and 0 <= numerator <= denominator,
        "measurement.fraction_domain",
    )
    return {
        "numerator": numerator,
        "denominator": denominator,
        "exact": f"{numerator}/{denominator}",
        "value": numerator / denominator if denominator else None,
    }


def build_partition(
    inputs: Mapping[str, Any],
    rules: Mapping[str, Any],
    projections: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    sessions = inputs["sessions"]
    condition = condition_binding(inputs, rules)
    by_session = {session["declaration"]["id"]: session for session in sessions}
    by_projection = {projection["session_id"]: projection for projection in projections}
    require(
        len(by_session) == len(by_projection) == len(sessions) == len(projections) == 6
        and set(by_session) == set(by_projection),
        "partition.exact_six_outcomes",
    )
    candidates: list[str] = []
    excluded: list[str] = []
    for session in sessions:
        sid = session["declaration"]["id"]
        projection, audit = by_projection[sid], session["qualification"]
        require(
            projection["condition"] == condition
            and projection["qualification_id"] == audit["id"]
            and projection["session_manifest_id"] == session["records"]["manifest"]["id"],
            "partition.projection_authority",
        )
        qualified = audit["qualified"] is True and audit["Y"] == 1
        require(
            (projection["status"] == "not_qualified") == (not qualified),
            "partition.failed_session_assignment",
        )
        (candidates if qualified else excluded).append(sid)
    require(
        len(candidates) == rules["denominators"]["success_conditioned"],
        "partition.qualified_denominator",
    )
    expected_pairs = list(itertools.combinations(candidates, 2))
    actual_pairs = [(pair["left_session_id"], pair["right_session_id"]) for pair in pairs]
    require(actual_pairs == expected_pairs and len(actual_pairs) == 10, "partition.exact_ten_pairs")
    relation: dict[tuple[str, str], str] = {}
    symmetric = True
    for pair in pairs:
        left, right = pair["left_session_id"], pair["right_session_id"]
        expected = compare_projections(by_projection[left], by_projection[right], rules)
        require(pair == expected, "partition.pair_witness_not_reproducible")
        relation[left, right] = relation[right, left] = pair["relation"]
        symmetric = (
            symmetric
            and compare_projections(by_projection[right], by_projection[left], rules)["relation"]
            == pair["relation"]
        )
    reflexive = True
    for sid in candidates:
        relation[sid, sid] = compare_projections(by_projection[sid], by_projection[sid], rules)[
            "relation"
        ]
        reflexive = reflexive and relation[sid, sid] == EQUIVALENT
    determined = all(by_projection[sid]["status"] == "mapped" for sid in candidates) and all(
        pair["relation"] != UNDETERMINED for pair in pairs
    )
    transitive = (
        all(
            not (relation[a, b] == relation[b, c] == EQUIVALENT) or relation[a, c] == EQUIVALENT
            for a, b, c in itertools.product(candidates, repeat=3)
        )
        if determined
        else None
    )
    if determined:
        require(
            reflexive and symmetric and transitive is True, "partition.inconsistent_equivalence"
        )
    complete = determined and reflexive and symmetric and transitive is True
    classes: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    if complete:
        assigned: set[str] = set()
        for representative in candidates:
            if representative in assigned:
                continue
            members = [sid for sid in candidates if relation[representative, sid] == EQUIVALENT]
            require(not assigned.intersection(members), "partition.overlapping_classes")
            canonical = canonical_graph(
                by_projection[representative]["graph"], rules["canonical_permutation_limit"]
            )["graph"]
            state = record("quotient_state", condition=condition, graph=canonical)
            classes.append(
                {
                    "state_id": state["id"],
                    "members": members,
                    "representative_session_id": representative,
                    "state": state,
                }
            )
            for sid in members:
                projection = by_projection[sid]
                assignments.append(
                    record(
                        "assignment",
                        session_id=sid,
                        projection_id=projection["id"],
                        qualification_id=projection["qualification_id"],
                        session_manifest_id=projection["session_manifest_id"],
                        condition=condition,
                        state_id=state["id"],
                    )
                )
            assigned.update(members)
        require(assigned == set(candidates), "partition.assignment_totality")
    return record(
        "partition",
        condition=condition,
        measurement_contract_id=rules["id"],
        complete=complete,
        relation_checks={
            "complete_pairs": True,
            "reflexive": reflexive,
            "symmetric": symmetric,
            "transitive": transitive,
        },
        classes=classes,
        assignments=assignments,
        unmapped_session_ids=[] if complete else candidates,
        excluded_session_ids=excluded,
        class_count=len(classes) if complete else None,
        old_quotient_state_ids_reused=False,
        complete_partition_requires_no_uninterpreted_qualified_candidate=True,
    )


def measure_empirical(
    inputs: Mapping[str, Any], rules: Mapping[str, Any], partition: Mapping[str, Any]
) -> dict[str, Any]:
    sessions = inputs["sessions"]
    condition = condition_binding(inputs, rules)
    require(partition["condition"] == condition, "measurement.generation_condition")
    by_session = {session["declaration"]["id"]: session for session in sessions}
    require(
        len(by_session) == len(sessions) == rules["denominators"]["end_to_end"] == 6,
        "measurement.fixed_population",
    )
    qualified = [
        sid
        for sid, session in by_session.items()
        if session["qualification"]["qualified"] is True and session["qualification"]["Y"] == 1
    ]
    failed = [sid for sid, session in by_session.items() if session["qualification"]["Y"] == 0]
    require(
        len(qualified) + len(failed) == len(sessions)
        and set(failed) == set(partition["excluded_session_ids"]),
        "measurement.outcome_denominator",
    )
    require(
        len(qualified) == rules["denominators"]["success_conditioned"],
        "measurement.qualified_denominator",
    )
    assigned = [assignment["session_id"] for assignment in partition["assignments"]]
    unmapped = partition["unmapped_session_ids"]
    require(
        len(assigned) == len(set(assigned))
        and len(unmapped) == len(set(unmapped))
        and not set(assigned).intersection(unmapped)
        and set(assigned) | set(unmapped) == set(qualified),
        "measurement.assignment_conservation",
    )
    class_ids = [row["state_id"] for row in partition["classes"]]
    require(len(class_ids) == len(set(class_ids)), "measurement.duplicate_class")
    counts = Counter(assignment["state_id"] for assignment in partition["assignments"])
    require(set(counts) == set(class_ids), "measurement.state_assignment_membership")
    for row in partition["classes"]:
        actual = [
            assignment["session_id"]
            for assignment in partition["assignments"]
            if assignment["state_id"] == row["state_id"]
        ]
        require(sorted(row["members"]) == sorted(actual), "measurement.class_member_counts")
    for assignment in partition["assignments"]:
        session = by_session[assignment["session_id"]]
        require(
            assignment["condition"] == condition
            and assignment["qualification_id"] == session["qualification"]["id"]
            and assignment["session_manifest_id"] == session["records"]["manifest"]["id"],
            "measurement.assignment_authority",
        )
    complete = partition["complete"] is True
    require(
        complete == (not unmapped) and (complete or not assigned),
        "measurement.partial_mapping_policy",
    )
    require(
        partition["class_count"] == (len(class_ids) if complete else None),
        "measurement.class_count",
    )
    frequencies = [
        {
            "state_id": state_id,
            "count": counts[state_id],
            "joint": fraction(counts[state_id], len(sessions)),
            "conditional": fraction(counts[state_id], len(qualified)),
        }
        for state_id in class_ids
    ]
    return record(
        "empirical_measurement",
        condition=condition,
        registered_denominator=len(sessions),
        qualified_denominator=len(qualified),
        qualified_count=len(qualified),
        mapped_count=len(assigned),
        unmapped_count=len(unmapped),
        failed_count=len(failed),
        complete=complete,
        q=fraction(len(qualified), len(sessions)),
        state_frequencies=frequencies,
        joint_total=fraction(len(assigned), len(sessions)),
        conditional_total=fraction(len(assigned), len(qualified)),
        unmapped_conditional=fraction(len(unmapped), len(qualified)),
        failure_frequency=fraction(len(failed), len(sessions)),
        conditional_distribution=frequencies if complete else None,
        old_quotient_mapping=False,
        population_probability_claimed=False,
        training_target_distribution=False,
        new_provider_calls=0,
        historical_provider_attempts=sum(
            session["qualification"]["provider_attempts"] for session in sessions
        ),
        mock_sessions_in_denominator=0,
        failed_sessions_are_valid_quotient_states=False,
        measurement_scope="empirical push-forward of the exact frozen six-session cohort",
    )
