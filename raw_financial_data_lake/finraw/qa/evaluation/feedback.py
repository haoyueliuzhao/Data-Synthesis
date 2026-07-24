from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


FEEDBACK_CONTRACT_VERSION = "qa_generation_feedback.v1"

FEEDBACK_DIMENSIONS = (
    "template_id",
    "pattern_id",
    "operation_macro",
    "metric_pair",
    "generation_pipeline",
    "language",
)

# Subjective defects are routed back to their owning generation component. They
# remain dataset-selection signals unless a separate deterministic check fails.
ISSUE_COMPONENT_TARGETS: dict[str, dict[str, Any]] = {
    "output_instruction_slightly_formulaic": {
        "target_component": "output_contract_verbalizer",
        "recommended_action": "expand_answer_type_specific_output_contract_variants",
        "action_type": "generator_fix",
    },
    "unnatural_output_instruction": {
        "target_component": "answer_type_instruction",
        "recommended_action": "revise_answer_type_specific_instruction",
        "action_type": "generator_fix",
    },
    "mechanical_template_language": {
        "target_component": "surface_variant_template",
        "recommended_action": "expand_or_replace_surface_variant",
        "action_type": "generator_fix",
    },
    "time_scope_awkward": {
        "target_component": "period_verbalizer",
        "recommended_action": "revise_period_surface_realization",
        "action_type": "generator_fix",
    },
    "scope_definition_unclear": {
        "target_component": "scope_description_builder",
        "recommended_action": "make_scope_membership_and_boundary_explicit",
        "action_type": "generator_fix",
    },
    "metric_pair_weakly_meaningful": {
        "target_component": "metric_pair_ontology_pattern_gate",
        "recommended_action": "downgrade_or_block_metric_pair",
        "action_type": "semantic_gate_fix",
    },
    "weak_followup_logic": {
        "target_component": "static_pattern_walk_macro",
        "recommended_action": "revise_followup_role_or_operation_macro",
        "action_type": "pattern_fix",
    },
    "overly_trivial": {
        "target_component": "sampling_quota",
        "recommended_action": "reduce_sampling_quota_for_low_information_slice",
        "action_type": "sampling_adjustment",
    },
    "low_standalone_value": {
        "target_component": "pattern_value_dataset_selection",
        "recommended_action": "lower_pattern_value_or_release_priority",
        "action_type": "dataset_selection",
    },
    "insufficient_context": {
        "target_component": "required_slot_contract",
        "recommended_action": "add_missing_entity_metric_period_or_scope_slot",
        "action_type": "contract_fix",
    },
    "gratuitous_complexity": {
        "target_component": "operation_plan_pattern_value",
        "recommended_action": "simplify_operation_plan_or_reduce_pattern_value",
        "action_type": "pattern_fix",
    },
    "redundant_constraints": {
        "target_component": "required_slot_output_contract",
        "recommended_action": "remove_redundant_surface_constraints",
        "action_type": "contract_fix",
    },
    "overly_verbose": {
        "target_component": "surface_verbalizer",
        "recommended_action": "tighten_surface_variant_length_policy",
        "action_type": "generator_fix",
    },
}


def build_generation_feedback(
    bundles: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    *,
    items: list[dict[str, Any]] | None = None,
    minimum_issue_count: int = 1,
    maximum_hotspots: int = 100,
) -> dict[str, Any]:
    """Attribute judge issues to the generation components that produced them."""
    minimum_issue_count = max(int(minimum_issue_count), 1)
    maximum_hotspots = max(int(maximum_hotspots), 1)
    bundle_by_qa = {str(row.get("qa_id") or ""): row for row in bundles}
    item_by_qa = {str(row.get("qa_id") or ""): row for row in items or []}
    components_by_qa = {
        qa_id: _component_dimensions(bundle)
        for qa_id, bundle in bundle_by_qa.items()
    }
    exact_denominators = Counter(
        _dimension_key(components) for components in components_by_qa.values()
    )
    dimension_denominators: dict[str, Counter[str]] = {
        dimension: Counter(
            components[dimension] for components in components_by_qa.values()
        )
        for dimension in FEEDBACK_DIMENSIONS
    }

    issue_roles: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    confirmed: dict[str, set[str]] = defaultdict(set)
    for row in calls:
        if row.get("status") != "succeeded":
            continue
        qa_id = str(row.get("qa_id") or "")
        if qa_id not in bundle_by_qa:
            continue
        role = str(row.get("judge_role") or "unknown")
        for issue in set(str(value) for value in row.get("issue_codes") or []):
            issue_roles[qa_id][issue].add(role)
            if role == "adversarial_reviewer" and row.get("resolutions"):
                confirmed[qa_id].add(issue)

    exact_groups: dict[tuple[str, ...], dict[str, Any]] = {}
    dimension_groups: dict[str, dict[tuple[str, str], dict[str, Any]]] = {
        dimension: {} for dimension in FEEDBACK_DIMENSIONS
    }
    issue_summary: dict[str, dict[str, Any]] = {}
    for qa_id, issues in issue_roles.items():
        components = components_by_qa[qa_id]
        component_key = _dimension_key(components)
        for issue, roles in issues.items():
            strength = _strength(roles, issue in confirmed.get(qa_id, set()))
            summary = issue_summary.setdefault(
                issue,
                _issue_summary_seed(issue, len(bundles)),
            )
            _increment_strength(summary, strength)
            summary["affected_qa_ids"].append(qa_id)

            exact_key = (issue, *component_key)
            exact = exact_groups.setdefault(
                exact_key,
                _hotspot_seed(issue, components, exact_denominators[component_key]),
            )
            _increment_strength(exact, strength)
            decision = str(item_by_qa.get(qa_id, {}).get("decision") or "unknown")
            exact["decision_counts"][decision] += 1

            for dimension in FEEDBACK_DIMENSIONS:
                value = components[dimension]
                group_key = (issue, value)
                row = dimension_groups[dimension].setdefault(
                    group_key,
                    _dimension_hotspot_seed(
                        issue,
                        dimension,
                        value,
                        dimension_denominators[dimension][value],
                    ),
                )
                _increment_strength(row, strength)

    normalized_summary = {
        issue: _finalize_issue_summary(row, len(bundles))
        for issue, row in sorted(issue_summary.items())
    }
    exact_rows = [
        _finalize_hotspot(row)
        for row in exact_groups.values()
        if int(row["flagged_by_any_judge"]) >= minimum_issue_count
    ]
    exact_rows.sort(key=_hotspot_sort_key)
    exact_rows = exact_rows[:maximum_hotspots]
    dimension_rows = {
        dimension: sorted(
            (
                _finalize_hotspot(row)
                for row in groups.values()
                if int(row["flagged_by_any_judge"]) >= minimum_issue_count
            ),
            key=_hotspot_sort_key,
        )[:maximum_hotspots]
        for dimension, groups in dimension_groups.items()
    }
    recommendations = sorted(
        (
            {
                "issue_code": issue,
                "target_component": row["target_component"],
                "recommended_action": row["recommended_action"],
                "action_type": row["action_type"],
                "priority": _priority(row),
                "flagged_by_any_judge": row["flagged_by_any_judge"],
                "flagged_by_two_or_more": row["flagged_by_two_or_more"],
                "confirmed_by_adjudicator": row["confirmed_by_adjudicator"],
                "correctness_gate": False,
            }
            for issue, row in normalized_summary.items()
        ),
        key=lambda row: (
            {"critical": 0, "high": 1, "medium": 2}[row["priority"]],
            -int(row["flagged_by_any_judge"]),
            row["issue_code"],
        ),
    )
    return {
        "contract_version": FEEDBACK_CONTRACT_VERSION,
        "population": {
            "sample_count": len(bundles),
            "sample_with_issue_count": len(issue_roles),
            "sample_with_issue_rate": _rate(len(issue_roles), len(bundles)),
            "successful_judge_call_count": sum(
                row.get("status") == "succeeded" for row in calls
            ),
        },
        "cube_dimensions": list(FEEDBACK_DIMENSIONS),
        "minimum_issue_count": minimum_issue_count,
        "issue_target_map": ISSUE_COMPONENT_TARGETS,
        "issue_summary": normalized_summary,
        "component_hotspots": exact_rows,
        "dimension_hotspots": dimension_rows,
        "recommended_actions": recommendations,
        "policy_note": (
            "Issue attribution guides generator, semantic-gate, sampling, and "
            "dataset-selection changes. It does not replace deterministic "
            "correctness gates. Rates use all evaluated samples in the same "
            "component slice as the denominator."
        ),
    }


def _component_dimensions(bundle: dict[str, Any]) -> dict[str, str]:
    sample = bundle.get("sample") or {}
    candidate = bundle.get("candidate") or {}
    plan = bundle.get("operation_plan") or {}
    label = bundle.get("distribution_label") or {}
    canonical = candidate.get("canonical_semantics") or {}
    source_metadata = sample.get("source_metadata") or {}
    question_generation = source_metadata.get("question_generation") or {}
    query_graph = canonical.get("query_graph_ir") or {}

    template_id = _first_text(
        sample.get("template_id"),
        sample.get("surface_form_id"),
        question_generation.get("template_id"),
        question_generation.get("surface_form_id"),
        sample.get("generation_method"),
    )
    pattern_id = _first_text(
        sample.get("graph_pattern_id"),
        candidate.get("catalog_pattern_id"),
        candidate.get("pattern_id"),
        plan.get("pattern_id"),
        candidate.get("task_subtype"),
    )
    operators = [
        str(row.get("operator") or "")
        for row in (plan.get("operator_dag") or {}).get("operators", [])
        if row.get("operator")
    ]
    operation_macro = _first_text(
        canonical.get("operation_macro_id"),
        query_graph.get("operation_macro_id"),
        " > ".join(operators) if operators else None,
        label.get("primary_operation_family"),
    )
    metric_ids = sorted(
        {
            str(value)
            for value in candidate.get("metric_ids")
            or label.get("metric_families")
            or []
            if str(value)
        }
    )
    metric_pair = " + ".join(metric_ids) if metric_ids else "unknown"
    return {
        "template_id": template_id,
        "pattern_id": pattern_id,
        "operation_macro": operation_macro,
        "metric_pair": metric_pair,
        "generation_pipeline": _first_text(
            label.get("generation_pipeline"), bundle.get("generation_pipeline")
        ),
        "language": _first_text(sample.get("language"), label.get("language")),
    }


def _issue_target(issue: str) -> dict[str, Any]:
    return ISSUE_COMPONENT_TARGETS.get(
        issue,
        {
            "target_component": "unmapped_issue_taxonomy",
            "recommended_action": "classify_issue_before_automated_remediation",
            "action_type": "taxonomy_review",
        },
    )


def _issue_summary_seed(issue: str, sample_count: int) -> dict[str, Any]:
    return {
        **_issue_target(issue),
        "population_count": sample_count,
        "flagged_by_any_judge": 0,
        "flagged_by_two_or_more": 0,
        "confirmed_by_adjudicator": 0,
        "affected_qa_ids": [],
    }


def _hotspot_seed(
    issue: str, components: dict[str, str], population_count: int
) -> dict[str, Any]:
    return {
        "issue_code": issue,
        **_issue_target(issue),
        **components,
        "population_count": population_count,
        "flagged_by_any_judge": 0,
        "flagged_by_two_or_more": 0,
        "confirmed_by_adjudicator": 0,
        "decision_counts": Counter(),
    }


def _dimension_hotspot_seed(
    issue: str, dimension: str, value: str, population_count: int
) -> dict[str, Any]:
    return {
        "issue_code": issue,
        **_issue_target(issue),
        "dimension": dimension,
        "dimension_value": value,
        "population_count": population_count,
        "flagged_by_any_judge": 0,
        "flagged_by_two_or_more": 0,
        "confirmed_by_adjudicator": 0,
    }


def _increment_strength(row: dict[str, Any], strength: dict[str, int]) -> None:
    for key, value in strength.items():
        row[key] = int(row.get(key) or 0) + value


def _strength(roles: set[str], is_confirmed: bool) -> dict[str, int]:
    return {
        "flagged_by_any_judge": 1,
        "flagged_by_two_or_more": int(len(roles) >= 2),
        "confirmed_by_adjudicator": int(is_confirmed),
    }


def _finalize_issue_summary(row: dict[str, Any], sample_count: int) -> dict[str, Any]:
    out = dict(row)
    out["affected_qa_ids"] = sorted(set(out["affected_qa_ids"]))
    out["affected_sample_rate"] = _rate(
        int(out["flagged_by_any_judge"]), sample_count
    )
    out["correctness_gate"] = False
    return out


def _finalize_hotspot(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if isinstance(out.get("decision_counts"), Counter):
        out["decision_counts"] = dict(sorted(out["decision_counts"].items()))
    out["affected_rate_within_component"] = _rate(
        int(out["flagged_by_any_judge"]), int(out["population_count"])
    )
    out["correctness_gate"] = False
    return out


def _dimension_key(components: dict[str, str]) -> tuple[str, ...]:
    return tuple(components[dimension] for dimension in FEEDBACK_DIMENSIONS)


def _hotspot_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(row["confirmed_by_adjudicator"]),
        -int(row["flagged_by_two_or_more"]),
        -int(row["flagged_by_any_judge"]),
        -float(row.get("affected_rate_within_component") or 0),
        str(row["issue_code"]),
        str(row.get("dimension_value") or row.get("template_id") or ""),
    )


def _priority(row: dict[str, Any]) -> str:
    if int(row["confirmed_by_adjudicator"]) > 0:
        return "critical"
    if int(row["flagged_by_two_or_more"]) > 0:
        return "high"
    return "medium"


def _first_text(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return "unknown"


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
