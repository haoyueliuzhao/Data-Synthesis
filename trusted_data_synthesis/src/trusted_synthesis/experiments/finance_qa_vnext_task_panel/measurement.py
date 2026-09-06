"""Pure stratified measurement of one preregistered eight-task, sixteen-session panel.

Qualifications remain the authority for outcomes and actual observed depth.  Finite
comparisons remain the authority for equivalence; a projection hash is only an
artifact reference.  Missing outcomes, unsupported projections and nonconsumable
representations are different dimensions, none of which changes the design marginal.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

from ..finance_qa_vnext_model_execution.models import identity, record, require
from ..finance_qa_vnext_model_execution.qualification import compare_qualified_sessions

GROUPS = ("F", "C", "G", "A", "D", "R", "B", "S")
STATUSES = ("success", "known_failure", "unknown", "not_started")
PARENT_FIELDS = (
    "task_group",
    "task_type",
    "task_id",
    "context_id",
    "protocol_id",
    "registry_hash",
    "model_configuration_id",
)


def _fraction(numerator: int, denominator: int) -> dict[str, int] | None:
    """Keep the stated empirical denominator rather than silently reducing it."""
    return {"numerator": numerator, "denominator": denominator} if denominator else None


def _decidable(item: dict[str, Any]) -> bool:
    return item.get("evidence_complete") is True and (
        item["status"] == "success"
        and item.get("end_to_end_success") is True
        or item["status"] == "known_failure"
        and item.get("end_to_end_success") is False
    )


def _mapped(item: dict[str, Any]) -> bool:
    return item.get("qualified") is True and item.get("projection_status") == "supported"


def finite_comparisons(qualifications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """At most one same-task pair per group; never compare unsupported projections."""
    pairs = []
    require(
        len({item["id"] for item in qualifications}) == len(qualifications),
        "panel_measurement.duplicate_qualification",
    )
    require(
        all(item["task_group"] in GROUPS for item in qualifications),
        "panel_measurement.foreign_task_group",
    )
    for group in GROUPS:
        values = [item for item in qualifications if item["task_group"] == group]
        require(len(values) <= 2, "panel_measurement.same_task_pair_budget")
        eligible = [item for item in values if _mapped(item)]
        if len(eligible) != 2:
            continue
        left, right = eligible
        require(
            all(left.get(key) == right.get(key) for key in PARENT_FIELDS),
            "panel_measurement.same_task_pair_context",
        )
        pairs.append(
            record(
                "finite_pair",
                task_group=group,
                left_qualification_id=left["id"],
                right_qualification_id=right["id"],
                comparison=compare_qualified_sessions(left, right),
            )
        )
    return pairs


def _population(
    qualifications: list[dict[str, Any]],
    registrations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    require(
        len(registrations) == len(qualifications) == 16, "panel_measurement.registered_denominator"
    )
    by_registration = {item["id"]: item for item in registrations}
    require(len(by_registration) == 16, "panel_measurement.duplicate_registration")
    require(
        len({item["session_id"] for item in registrations}) == 16,
        "panel_measurement.duplicate_registered_session",
    )
    require(
        Counter(item["task_group"] for item in registrations)
        == Counter({group: 2 for group in GROUPS}),
        "panel_measurement.task_denominator",
    )
    require(
        len({item["task_id"] for item in registrations}) == 8,
        "panel_measurement.fixed_task_denominator",
    )
    require(
        len({item["task_type"] for item in registrations}) == 8,
        "panel_measurement.fixed_task_type_denominator",
    )
    for item in registrations:
        identity(item, "session_registration")
    by_qualification = {}
    registration_ids = []
    for item in qualifications:
        identity(item, "qualification")
        registration = by_registration.get(item["registration_id"])
        require(registration is not None, "panel_measurement.foreign_registration")
        require(
            item["registered_session_id"] == registration["session_id"]
            and all(item[key] == registration[key] for key in PARENT_FIELDS),
            "panel_measurement.qualification_parent",
        )
        require(item["status"] in STATUSES, "panel_measurement.outcome_status")
        require(
            item.get("projection_status") in {"supported", "undetermined"},
            "panel_measurement.projection_status",
        )
        if item["status"] == "success":
            require(
                _decidable(item)
                and item.get("qualified") is True
                and item.get("model_origin_verified") is True,
                "panel_measurement.success_evidence",
            )
        elif item["status"] == "known_failure":
            require(
                _decidable(item) and item.get("qualified") is False,
                "panel_measurement.failure_evidence",
            )
        else:
            require(
                item.get("end_to_end_success") is None and item.get("qualified") is None,
                "panel_measurement.undecidable_not_failure",
            )
        if _mapped(item):
            audit = item.get("domain_audit")
            require(
                isinstance(audit, dict)
                and audit.get("projection_supported") is True
                and isinstance(audit.get("finite_projection"), dict)
                and audit.get("id") == item.get("domain_audit_id"),
                "panel_measurement.projection_parent",
            )
        by_qualification[item["id"]] = item
        registration_ids.append(item["registration_id"])
    require(
        len(by_qualification) == 16 and set(registration_ids) == set(by_registration),
        "panel_measurement.qualification_inventory",
    )
    for group in GROUPS:
        values = [item for item in registrations if item["task_group"] == group]
        require(
            all(values[0][key] == values[1][key] for key in PARENT_FIELDS),
            "panel_measurement.registered_task_binding",
        )
    return by_qualification


def _pair_index(
    pairs: list[dict[str, Any]],
    qualifications: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    require(len(pairs) <= 8, "panel_measurement.same_task_pair_budget")
    indexed = {}
    for pair in pairs:
        identity(pair, "finite_pair")
        left = qualifications.get(pair["left_qualification_id"])
        right = qualifications.get(pair["right_qualification_id"])
        require(
            left is not None and right is not None and left["id"] != right["id"],
            "panel_measurement.pair_population",
        )
        require(_mapped(left) and _mapped(right), "panel_measurement.pair_projection_support")
        require(
            all(left[key] == right[key] for key in PARENT_FIELDS)
            and pair["task_group"] == left["task_group"],
            "panel_measurement.pair_same_task",
        )
        comparison = pair["comparison"]
        require(
            comparison["left_audit_id"] == left["domain_audit_id"]
            and comparison["right_audit_id"] == right["domain_audit_id"],
            "panel_measurement.pair_audit_parents",
        )
        require(
            comparison["relation"] in {"equivalent", "not_equivalent", "undetermined"},
            "panel_measurement.pair_relation",
        )
        require(
            comparison.get("equivalent")
            == {
                "equivalent": True,
                "not_equivalent": False,
                "undetermined": None,
            }[comparison["relation"]],
            "panel_measurement.pair_relation_consistency",
        )
        require(pair["task_group"] not in indexed, "panel_measurement.duplicate_task_pair")
        indexed[pair["task_group"]] = pair
    return indexed


def _observed_classes(
    values: list[dict[str, Any]],
    pair: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | None, str]:
    successes = [item for item in values if item.get("qualified") is True]
    if not successes:
        return None, "no_qualified_observations"
    if not all(_mapped(item) for item in successes):
        return None, "qualified_observations_include_undetermined_projection"
    groups = [successes]
    if len(successes) == 2:
        if pair is None:
            return None, "supported_pair_comparison_missing"
        relation = pair["comparison"]["relation"]
        if relation == "undetermined":
            return None, "supported_pair_comparison_undetermined"
        if relation == "not_equivalent":
            groups = [[item] for item in successes]
    rows = []
    for ordinal, members in enumerate(groups, start=1):
        representative = members[0]
        rows.append(
            {
                "finite_observed_group": ordinal,
                "representative_projection_id": strict_canonical_hash(
                    representative["domain_audit"]["finite_projection"],
                    prefix="qa_vnext_task_panel_observed_projection:",
                ),
                "representative_domain_audit_id": representative["domain_audit_id"],
                "qualification_ids": [item["id"] for item in members],
                "observed_count": len(members),
                "qualified_observation_denominator": len(successes),
                "conditional_frequency": _fraction(len(members), len(successes)),
            }
        )
    return rows, "all_qualified_observations_mapped_in_this_finite_sample"


def summarize(
    qualifications: list[dict[str, Any]],
    registrations: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    packages: dict[str, Any],
    representation_tokens: dict[str, Any],
    pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure only this registration inventory; no runtime, model or tokenizer calls.

    ``packages.rows`` retains all sixteen registrations, while ``tokens.records``
    contains the positive candidates (including non-fit diagnostics).  No observed
    success threshold or minimum class count is a collection-completion gate.
    """
    qualified_by_id = _population(qualifications, registrations)
    indexed_pairs = _pair_index(pairs, qualified_by_id)
    indexed_packages = {item["qualification_id"]: item for item in packages["rows"]}
    require(
        len(packages["rows"]) == len(indexed_packages) == 16
        and set(indexed_packages) == set(qualified_by_id),
        "panel_measurement.package_inventory",
    )
    tokens = representation_tokens["records"]
    require(
        len({item["row_id"] for item in tokens}) == len(tokens),
        "panel_measurement.duplicate_token_candidate",
    )
    for token in tokens:
        qualification = qualified_by_id.get(token["qualification_id"])
        require(
            qualification is not None
            and qualification["qualified"] is True
            and token["session_id"] == qualification["session_id"],
            "panel_measurement.token_positive_parent",
        )
        require(
            token["tokenrepresentation_status"] in {"fit", "not_fit"}
            and token["consumable_token_representation"]
            is (token["tokenrepresentation_status"] == "fit"),
            "panel_measurement.token_consumability",
        )
    session_rows = []
    for registration in registrations:
        qualification = next(
            item for item in qualifications if item["registration_id"] == registration["id"]
        )
        package = indexed_packages[qualification["id"]]
        require(
            package["session_id"] == qualification["session_id"]
            and package["registration_id"] == registration["id"]
            and package["registered_session_id"] == registration["session_id"]
            and all(
                package[key] == registration[key] for key in ("task_group", "task_type", "task_id")
            ),
            "panel_measurement.package_parent",
        )
        require(
            package["positive_eligible"] is (qualification["qualified"] is True),
            "panel_measurement.package_qualification",
        )
        if package["complete"]:
            require(
                package["positive_eligible"]
                and package["expected_units"] > 0
                and package["expected_units"]
                == package["consumable_units"]
                == len(package["units"])
                and all(unit["consumable"] is True for unit in package["units"]),
                "panel_measurement.complete_package_units",
            )
        local_tokens = [item for item in tokens if item["qualification_id"] == qualification["id"]]
        session_rows.append(
            {
                "label": registration["label"],
                "registration_id": registration["id"],
                "registered_session_id": registration["session_id"],
                "session_id": qualification["session_id"],
                "qualification_id": qualification["id"],
                "task_group": registration["task_group"],
                "task_type": registration["task_type"],
                "task_id": registration["task_id"],
                "status": qualification["status"],
                "reason": qualification.get("reason"),
                "execution_started": qualification.get("execution_started"),
                "evidence_complete": qualification["evidence_complete"],
                "outcome_decidable": _decidable(qualification),
                "end_to_end_success": qualification["end_to_end_success"],
                "qualified": qualification["qualified"],
                "projection_status": qualification["projection_status"],
                "depth_scope": qualification.get("depth_scope"),
                "depth_metrics": qualification.get("depth_metrics"),
                "expected_package_units": package["expected_units"],
                "consumable_package_units": package["consumable_units"],
                "complete_representation_package": package["complete"],
                "representation_candidate_rows": len(local_tokens),
                "representation_fit_rows": sum(
                    item["consumable_token_representation"] for item in local_tokens
                ),
                "representation_not_fit_rows": sum(
                    not item["consumable_token_representation"] for item in local_tokens
                ),
            }
        )
    complete = all(item["outcome_decidable"] for item in session_rows)
    successes = sum(item["end_to_end_success"] is True for item in session_rows)
    total_packages = sum(item["complete_representation_package"] for item in session_rows)
    total_fit_rows = sum(item["representation_fit_rows"] for item in session_rows)
    total_complete_rows = sum(
        item["expected_package_units"]
        for item in session_rows
        if item["complete_representation_package"]
    )
    task_rows = []
    for group in GROUPS:
        values = [item for item in qualifications if item["task_group"] == group]
        sessions = [item for item in session_rows if item["task_group"] == group]
        statuses = Counter(item["status"] for item in values)
        task_successes = statuses["success"]
        decidable = all(item["outcome_decidable"] for item in sessions)
        classes, mapping_reason = _observed_classes(values, indexed_pairs.get(group))
        complete_packages = sum(item["complete_representation_package"] for item in sessions)
        fit_rows = sum(item["representation_fit_rows"] for item in sessions)
        complete_rows = sum(
            item["expected_package_units"]
            for item in sessions
            if item["complete_representation_package"]
        )
        pair = indexed_pairs.get(group)
        task_rows.append(
            {
                "task_group": group,
                "task_type": values[0]["task_type"],
                "task_id": values[0]["task_id"],
                "design_task_marginal": _fraction(1, 8),
                "registered_attempts": 2,
                "registered_denominator": 2,
                **{status: statuses[status] for status in STATUSES},
                "model_successes": task_successes,
                "success_numerator": task_successes,
                "known_failures": statuses["known_failure"],
                "qualified_mapped": sum(_mapped(item) for item in values),
                "qualified_projection_undetermined": sum(
                    item["qualified"] is True and not _mapped(item) for item in values
                ),
                "complete_repr_packages": complete_packages,
                "complete_success_proportion": task_successes / 2 if decidable else None,
                "complete_success_fraction": _fraction(task_successes, 2) if decidable else None,
                "complete_decidable_population": decidable,
                "success_pool_task_share": _fraction(task_successes, successes),
                "success_pool_population_decidable": complete,
                "complete_package_pool_task_share": _fraction(complete_packages, total_packages),
                "representation_candidate_rows": sum(
                    item["representation_candidate_rows"] for item in sessions
                ),
                "representation_fit_rows": fit_rows,
                "representation_not_fit_rows": sum(
                    item["representation_not_fit_rows"] for item in sessions
                ),
                "fit_row_pool_task_share": _fraction(fit_rows, total_fit_rows),
                "complete_package_rows": complete_rows,
                "complete_package_row_pool_task_share": _fraction(
                    complete_rows, total_complete_rows
                ),
                "finite_comparison_id": pair["id"] if pair else None,
                "finite_comparison_relation": pair["comparison"]["relation"] if pair else None,
                "finite_comparison_status": "performed"
                if pair
                else (
                    "not_performed_unsupported_projection"
                    if task_successes == 2 and not all(_mapped(item) for item in values)
                    else "not_performed_fewer_than_two_qualified"
                    if task_successes < 2
                    else "not_performed_missing_supported_pair"
                ),
                "empirical_conditional_class_frequencies": classes,
                "conditional_frequency_status": mapping_reason,
                "finite_observed_class_count": len(classes) if classes is not None else None,
                "all_qualified_observations_mapped": classes is not None,
                "session_qualification_ids": [item["id"] for item in values],
                "training_task_full_support_witness": complete_packages > 0,
            }
        )
    selected_coverage = [item for item in coverage if item["selected_for_model_population"]]
    require(
        len(coverage) == len({item["task_type"] for item in coverage}) == 11
        and len(selected_coverage) == 8
        and {item["task_type"] for item in selected_coverage}
        == {item["task_type"] for item in task_rows},
        "panel_measurement.coverage_inventory",
    )
    measured_coverage = []
    for source in coverage:
        selected = source["selected_for_model_population"]
        require(
            type(selected) is bool and source["source_available"] is selected,
            "panel_measurement.coverage_source_boundary",
        )
        task = next((item for item in task_rows if item["task_type"] == source["task_type"]), None)
        require(
            (task is not None) is selected
            and source["registered_model_sessions"] == (2 if selected else 0)
            and source["population_status"]
            == ("selected_model_task" if selected else "source_uninstantiated"),
            "panel_measurement.coverage_selection_binding",
        )
        require(
            source["task_id"] == (task["task_id"] if task else None)
            and source["task_group"] == (task["task_group"] if task else None),
            "panel_measurement.coverage_task_parent",
        )
        measured_coverage.append(
            {
                "source_coverage_id": source["id"],
                "source_coverage": source,
                "task_group": task["task_group"] if task else None,
                "task_type": source["task_type"],
                "task_id": task["task_id"] if task else None,
                "population_status": source["population_status"],
                "model_measurement_performed": selected,
                "registered_attempts": 2 if task else 0,
                "model_successes": task["model_successes"] if task else 0,
                "qualified_mapped": task["qualified_mapped"] if task else 0,
                "complete_repr_packages": task["complete_repr_packages"] if task else 0,
                "complete_success_proportion": task["complete_success_proportion"]
                if task
                else None,
                "in_fixed_panel_statistical_denominator": selected,
            }
        )
    full_support = all(item["training_task_full_support_witness"] for item in task_rows)
    return record(
        "task_panel_measurement",
        task_rows=task_rows,
        session_rows=session_rows,
        coverage_rows=measured_coverage,
        registered_task_type_coverage_count=11,
        source_available_selected_task_count=8,
        source_uninstantiated_task_type_count=3,
        fixed_task_denominator=8,
        registered_session_denominator=16,
        design_task_marginal_kind="uniform_fixed_design_not_demand_estimate",
        complete_decidable_population=complete,
        success_numerator=successes,
        complete_success_proportion=successes / 16 if complete else None,
        complete_success_fraction=_fraction(successes, 16) if complete else None,
        equal_task_weight_mean=successes / 16 if complete else None,
        known_failures=sum(item["status"] == "known_failure" for item in session_rows),
        unknown=sum(item["status"] == "unknown" for item in session_rows),
        not_started=sum(item["status"] == "not_started" for item in session_rows),
        qualified_mapped=sum(item["qualified_mapped"] for item in task_rows),
        complete_repr_packages=total_packages,
        representation_candidate_rows=len(tokens),
        representation_fit_rows=total_fit_rows,
        representation_not_fit_rows=len(tokens) - total_fit_rows,
        complete_package_rows=total_complete_rows,
        finite_comparison_count=len(pairs),
        maximum_finite_comparisons=8,
        selected_tasks_with_success_witness=sum(item["model_successes"] > 0 for item in task_rows),
        all_selected_tasks_have_success_witness=all(
            item["model_successes"] > 0 for item in task_rows
        ),
        full_support_training_support_available=full_support,
        full_support_training_materialized=False,
        full_support_training_materialization_status=(
            "support_available_not_materialized"
            if full_support
            else "support_missing_not_materializable"
        ),
        full_support_absent_task_groups=[
            item["task_group"]
            for item in task_rows
            if not item["training_task_full_support_witness"]
        ],
        collection_requires_all_sessions_successful=False,
        collection_requires_all_projections_mapped=False,
        collection_requires_multiple_observed_classes=False,
        missing_training_support_invalidates_collection=False,
        missing_outcomes_counted_as_failures=False,
        design_marginal_renormalized=False,
        historical_model_sessions_pooled=0,
        replacement_sessions=0,
        finite_frequencies_are_optimal_training_weights=False,
        observed_groups_enumerate_all_possible_classes=False,
        projection_hash_is_equivalence_authority=False,
        quotient_assignments=[],
        final_training_weights=None,
        stable_population_probabilities_claimed=False,
        causal_depth_effect_claimed=False,
        model_critical_reasoning_depth_claimed=False,
        entire_finance_model_coverage_claimed=False,
        provider_calls_by_measurement=0,
        runtime_executions_by_measurement=0,
    )
