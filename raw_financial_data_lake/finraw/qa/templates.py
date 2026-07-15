from __future__ import annotations

from typing import Any


TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "single_fact_flow_en_01",
        "task_family": "single_fact",
        "period_type": "period_flow",
        "language": "en",
        "template_text": "What was {entity}'s {metric} for {period}?",
        "required_slots": ["entity", "metric", "period"],
        "answer_type": "numeric",
        "difficulty_base": "easy",
    },
    {
        "template_id": "single_fact_instant_en_01",
        "task_family": "single_fact",
        "period_type": "point_in_time",
        "language": "en",
        "template_text": "What was {entity}'s {metric} as of {period}?",
        "required_slots": ["entity", "metric", "period"],
        "answer_type": "numeric",
        "difficulty_base": "easy",
    },
    {
        "template_id": "single_fact_observation_en_01",
        "task_family": "single_fact",
        "period_type": "observation",
        "language": "en",
        "template_text": "What was the {metric} for {entity} on {period}?",
        "required_slots": ["entity", "metric", "period"],
        "answer_type": "numeric",
        "difficulty_base": "easy",
    },
    {
        "template_id": "difference_en_01",
        "task_family": "calculation",
        "language": "en",
        "template_text": "By how much did {entity}'s {metric} change from {previous_period} to {period}?",
        "required_slots": ["entity", "metric", "previous_period", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "yoy_growth_en_01",
        "task_family": "calculation",
        "language": "en",
        "template_text": "What was the year-over-year growth rate of {entity}'s {metric} in {period}?",
        "required_slots": ["entity", "metric", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "qoq_growth_en_01",
        "task_family": "calculation",
        "language": "en",
        "template_text": "What was the quarter-over-quarter growth rate of {entity}'s {metric} in {period}?",
        "required_slots": ["entity", "metric", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "ratio_en_01",
        "task_family": "calculation",
        "language": "en",
        "template_text": "What was {entity}'s {ratio} in {period}?",
        "required_slots": ["entity", "ratio", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "share_en_01",
        "task_family": "calculation",
        "language": "en",
        "template_text": "Within {scope}, what share of total {metric} did {entity} account for in {period}?",
        "required_slots": ["scope", "entity", "metric", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "temporal_extrema_en_01",
        "task_family": "temporal_investigation",
        "language": "en",
        "template_text": "Between {start_period} and {end_period}, when did {entity}'s {metric} reach its {extreme}, and what was the value?",
        "required_slots": ["start_period", "end_period", "entity", "metric", "extreme"],
        "answer_type": "period_and_value",
        "difficulty_base": "hard",
    },
    {
        "template_id": "ranking_en_01",
        "task_family": "scope_comparison",
        "language": "en",
        "template_text": "Within {scope}, rank the top {top_k} entities by {metric} in {period}.",
        "required_slots": ["scope", "top_k", "metric", "period"],
        "answer_type": "ranked_list",
        "difficulty_base": "hard",
    },
    {
        "template_id": "scope_extrema_en_01",
        "task_family": "scope_comparison",
        "language": "en",
        "template_text": "Within {scope}, which entity had the {extreme} {metric} in {period}?",
        "required_slots": ["scope", "extreme", "metric", "period"],
        "answer_type": "entity_and_value",
        "difficulty_base": "hard",
    },
    {
        "template_id": "screening_en_01",
        "task_family": "scope_screening",
        "language": "en",
        "template_text": "Within {scope}, which entities met all configured screening conditions in {period}?",
        "required_slots": ["scope", "period"],
        "answer_type": "entity_set",
        "difficulty_base": "expert",
    },
    {
        "template_id": "long_window_return_en_01",
        "task_family": "temporal_investigation",
        "language": "en",
        "template_text": "What was the percentage change in {entity}'s {metric} from {start_period} to {end_period}?",
        "required_slots": ["entity", "metric", "start_period", "end_period"],
        "answer_type": "numeric",
        "difficulty_base": "hard",
    },
    {
        "template_id": "pairwise_entity_comparison_en_01",
        "task_family": "graph_comparison",
        "language": "en",
        "template_text": "In {period}, which had the higher {metric}, {entity_a} or {entity_b}, and by how much?",
        "required_slots": ["period", "metric", "entity_a", "entity_b"],
        "answer_type": "comparison",
        "difficulty_base": "medium",
    },
    {
        "template_id": "pairwise_entity_comparison_en_02",
        "task_family": "graph_comparison",
        "language": "en",
        "template_text": "Compare {entity_a} and {entity_b} on {metric} in {period}. Identify the higher value and the difference.",
        "required_slots": ["period", "metric", "entity_a", "entity_b"],
        "answer_type": "comparison",
        "difficulty_base": "medium",
    },
    {
        "template_id": "cross_metric_comparison_en_01",
        "task_family": "graph_comparison",
        "language": "en",
        "template_text": "For {entity} in {period}, which was higher, {metric_a} or {metric_b}, and by how much?",
        "required_slots": ["entity", "period", "metric_a", "metric_b"],
        "answer_type": "comparison",
        "difficulty_base": "medium",
    },
    {
        "template_id": "cross_metric_comparison_en_02",
        "task_family": "graph_comparison",
        "language": "en",
        "template_text": "Compare {entity}'s {metric_a} with its {metric_b} for {period}, including the absolute difference.",
        "required_slots": ["entity", "period", "metric_a", "metric_b"],
        "answer_type": "comparison",
        "difficulty_base": "medium",
    },
    {
        "template_id": "multi_period_average_en_01",
        "task_family": "graph_temporal_aggregation",
        "language": "en",
        "template_text": "What was the average {metric} for {entity} from {start_period} through {end_period}?",
        "required_slots": ["entity", "metric", "start_period", "end_period"],
        "answer_type": "numeric",
        "difficulty_base": "hard",
    },
    {
        "template_id": "multi_period_average_en_02",
        "task_family": "graph_temporal_aggregation",
        "language": "en",
        "template_text": "Across {start_period} to {end_period}, what arithmetic mean did {entity} report for {metric}?",
        "required_slots": ["entity", "metric", "start_period", "end_period"],
        "answer_type": "numeric",
        "difficulty_base": "hard",
    },
]


def template_for(
    task_subtype: str,
    period_type: str | None = None,
    variant_seed: str | None = None,
) -> dict[str, Any]:
    if task_subtype == "single_fact":
        template_id = {
            "point_in_time": "single_fact_instant_en_01",
            "period_flow": "single_fact_flow_en_01",
        }.get(period_type, "single_fact_observation_en_01")
    elif task_subtype in {
        "multi_year_argmax",
        "multi_year_argmin",
        "rolling_max",
        "rolling_min",
        "macro_time_series_argmax",
        "macro_time_series_argmin",
        "time_series_argmax",
        "time_series_argmin",
    }:
        template_id = "temporal_extrema_en_01"
    elif task_subtype == "multi_condition_screening":
        template_id = "screening_en_01"
    elif task_subtype in {"ranking", "industry_ranking"}:
        template_id = "ranking_en_01"
    elif task_subtype in {"argmax", "argmin", "industry_argmax", "industry_argmin"}:
        template_id = "scope_extrema_en_01"
    elif task_subtype in {
        "pairwise_entity_comparison",
        "cross_metric_comparison",
        "multi_period_average",
    }:
        prefix = {
            "pairwise_entity_comparison": "pairwise_entity_comparison_en_",
            "cross_metric_comparison": "cross_metric_comparison_en_",
            "multi_period_average": "multi_period_average_en_",
        }[task_subtype]
        options = sorted(
            (
                item
                for item in TEMPLATES
                if item["template_id"].startswith(prefix)
            ),
            key=lambda item: item["template_id"],
        )
        seed = variant_seed or task_subtype
        index = sum(seed.encode("utf-8")) % len(options)
        return options[index]
    else:
        template_id = f"{task_subtype}_en_01"
    return next(item for item in TEMPLATES if item["template_id"] == template_id)
