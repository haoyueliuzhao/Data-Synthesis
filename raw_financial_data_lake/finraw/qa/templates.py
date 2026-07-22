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
        "template_text": "Across {observation_count} comparable {frequency} observations from {start_period} through {end_period}, what was the average {metric} for {entity}?",
        "required_slots": [
            "entity",
            "metric",
            "start_period",
            "end_period",
            "observation_count",
            "frequency",
        ],
        "answer_type": "numeric",
        "difficulty_base": "hard",
    },
    {
        "template_id": "multi_period_average_en_02",
        "task_family": "graph_temporal_aggregation",
        "language": "en",
        "template_text": "Using the {observation_count} comparable {frequency} observations from {start_period} to {end_period}, what arithmetic mean did {entity} report for {metric}?",
        "required_slots": [
            "entity",
            "metric",
            "start_period",
            "end_period",
            "observation_count",
            "frequency",
        ],
        "answer_type": "numeric",
        "difficulty_base": "hard",
    },
    {
        "template_id": "temporal_peak_followup_en_01",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "Between {start_period} and {end_period}, when did {entity}'s {primary_metric} peak, and what was its {secondary_metric} in that same period?",
        "required_slots": [
            "entity",
            "primary_metric",
            "secondary_metric",
            "start_period",
            "end_period",
        ],
        "answer_type": "period_metric_lookup",
        "difficulty_base": "expert",
    },
    {
        "template_id": "temporal_peak_followup_en_02",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "Identify {entity}'s highest {primary_metric} from {start_period} through {end_period}, then report {secondary_metric} for the selected period.",
        "required_slots": [
            "entity",
            "primary_metric",
            "secondary_metric",
            "start_period",
            "end_period",
        ],
        "answer_type": "period_metric_lookup",
        "difficulty_base": "expert",
    },
    {
        "template_id": "filter_then_rank_en_01",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "Within {scope}, filter companies whose {growth_metric} growth exceeded {growth_threshold}% in {period}, then rank the top {top_k} by {ranking_metric}.",
        "required_slots": [
            "scope",
            "growth_metric",
            "growth_threshold",
            "period",
            "top_k",
            "ranking_metric",
        ],
        "answer_type": "ranked_table",
        "difficulty_base": "research",
    },
    {
        "template_id": "filter_then_rank_en_02",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "For {period}, screen {scope} for {growth_metric} growth above {growth_threshold}%, and list the {top_k} qualifying companies with the highest {ranking_metric}.",
        "required_slots": [
            "scope",
            "growth_metric",
            "growth_threshold",
            "period",
            "top_k",
            "ranking_metric",
        ],
        "answer_type": "ranked_table",
        "difficulty_base": "research",
    },
    {
        "template_id": "rank_then_secondary_lookup_en_01",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "Within {scope}, identify the top {top_k} companies by {primary_metric} in {period}, then report {secondary_metric} for each selected company.",
        "required_slots": [
            "scope",
            "top_k",
            "primary_metric",
            "secondary_metric",
            "period",
        ],
        "answer_type": "multi_metric_ranked_table",
        "difficulty_base": "expert",
    },
    {
        "template_id": "rank_then_secondary_lookup_en_02",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "Rank the top {top_k} companies in {scope} by {primary_metric} for {period} and add each company's {secondary_metric} for that period.",
        "required_slots": [
            "scope",
            "top_k",
            "primary_metric",
            "secondary_metric",
            "period",
        ],
        "answer_type": "multi_metric_ranked_table",
        "difficulty_base": "expert",
    },
    {
        "template_id": "multi_factor_screening_en_01",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "Within {scope} in {period}, which companies had {growth_metric} growth above {growth_threshold}%, {ranking_metric} above {benchmark}, and a {debt_metric} below {debt_threshold}%?",
        "required_slots": [
            "scope",
            "period",
            "growth_metric",
            "growth_threshold",
            "ranking_metric",
            "benchmark",
            "debt_metric",
            "debt_threshold",
        ],
        "answer_type": "screening_table",
        "difficulty_base": "research",
    },
    {
        "template_id": "multi_factor_screening_en_02",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "Screen {scope} for {period} using all three conditions: {growth_metric} growth greater than {growth_threshold}%, {ranking_metric} above {benchmark}, and {debt_metric} under {debt_threshold}%.",
        "required_slots": [
            "scope",
            "period",
            "growth_metric",
            "growth_threshold",
            "ranking_metric",
            "benchmark",
            "debt_metric",
            "debt_threshold",
        ],
        "answer_type": "screening_table",
        "difficulty_base": "research",
    },
    {
        "template_id": "derived_input_trace_en_01",
        "task_family": "graph_composition",
        "language": "en",
        "template_text": "Which input facts were used to calculate the {derived_type} result {derived_id}?",
        "required_slots": ["derived_type", "derived_id"],
        "answer_type": "structured_fact_list",
        "difficulty_base": "medium",
    },
    {
        "template_id": "provenance_trace_en_01",
        "task_family": "graph_provenance",
        "language": "en",
        "template_text": "Trace fact {fact_id} to its data source, source definition, and raw object.",
        "required_slots": ["fact_id"],
        "answer_type": "evidence_trace",
        "difficulty_base": "easy",
    },
    {
        "template_id": "time_hierarchy_membership_en_01",
        "task_family": "graph_time_hierarchy",
        "language": "en",
        "template_text": "Which {hierarchy_type} does the period for fact {fact_id} belong to?",
        "required_slots": ["hierarchy_type", "fact_id"],
        "answer_type": "time_hierarchy_membership",
        "difficulty_base": "easy",
    },
    {
        "template_id": "scope_composition_en_01",
        "task_family": "graph_scope",
        "language": "en",
        "template_text": "Which entities make up {scope_label} for derived result {derived_id}?",
        "required_slots": ["scope_label", "derived_id"],
        "answer_type": "entity_scope_membership",
        "difficulty_base": "medium",
    },
    {
        "template_id": "walk_temporal_peak_followup_provenance_en_01",
        "task_family": "walk_temporal_followup",
        "language": "en",
        "template_text": "Between {start_period} and {end_period}, identify the highest {primary_metric} for {entity}, then report {secondary_metric} for that period and list its source raw object.",
        "required_slots": [
            "start_period",
            "end_period",
            "entity",
            "primary_metric",
            "secondary_metric",
        ],
        "answer_type": "period_metric_provenance",
        "difficulty_base": "research",
    },
    {
        "template_id": "walk_scope_filter_rank_followup_en_01",
        "task_family": "walk_scope_analysis",
        "language": "en",
        "template_text": "Within {scope} in {period}, filter companies whose {growth_metric} growth exceeded {growth_threshold}%, then rank the top {top_k} by {primary_metric}, and report {secondary_metric} for the first-ranked company.",
        "required_slots": [
            "scope",
            "period",
            "growth_metric",
            "growth_threshold",
            "top_k",
            "primary_metric",
            "secondary_metric",
        ],
        "answer_type": "filtered_rank_followup",
        "difficulty_base": "research",
    },
    {
        "template_id": "walk_derived_input_time_source_trace_en_01",
        "task_family": "walk_derived_trace",
        "language": "en",
        "template_text": "Which input facts, fiscal years, and source raw objects support the {derived_type} result {derived_id}?",
        "required_slots": ["derived_type", "derived_id"],
        "answer_type": "derived_fact_input_trace",
        "difficulty_base": "hard",
    },
]


_ZH_TEMPLATE_TEXTS = {
    "single_fact_flow_en_01": "{entity}在{period}报告的{metric}是多少？",
    "single_fact_instant_en_01": "截至{period}，{entity}的{metric}是多少？",
    "single_fact_observation_en_01": "{entity}在{period}的{metric}观测值是多少？",
    "difference_en_01": "从{previous_period}到{period}，{entity}的{metric}变化了多少？",
    "yoy_growth_en_01": "{entity}的{metric}在{period}的同比增长率是多少？",
    "qoq_growth_en_01": "{entity}的{metric}在{period}的环比增长率是多少？",
    "ratio_en_01": "{entity}在{period}的{ratio}是多少？",
    "share_en_01": "在{scope}中，{entity}在{period}的{metric}占总量的比例是多少？",
    "temporal_extrema_en_01": "在{start_period}至{end_period}期间，{entity}的{metric}何时达到{extreme}，对应数值是多少？",
    "ranking_en_01": "在{scope}中，按{period}的{metric}从高到低列出前{top_k}个实体。",
    "scope_extrema_en_01": "在{scope}中，哪个实体在{period}的{metric}{extreme}？",
    "screening_en_01": "在{scope}中，哪些实体在{period}同时满足全部筛选条件？",
    "long_window_return_en_01": "{entity}的{metric}从{start_period}到{end_period}变化了百分之多少？",
    "pairwise_entity_comparison_en_01": "在{period}，{entity_a}和{entity_b}哪一个的{metric}更高，相差多少？",
    "pairwise_entity_comparison_en_02": "比较{entity_a}与{entity_b}在{period}的{metric}，指出较高者及差额。",
    "cross_metric_comparison_en_01": "对{entity}而言，{period}的{metric_a}和{metric_b}哪一个更高，相差多少？",
    "cross_metric_comparison_en_02": "比较{entity}在{period}的{metric_a}与{metric_b}，并给出绝对差额。",
    "multi_period_average_en_01": "基于{start_period}至{end_period}的{observation_count}个可比{frequency}观测，{entity}的{metric}平均值是多少？",
    "multi_period_average_en_02": "使用{start_period}至{end_period}的{observation_count}个可比{frequency}观测，计算{entity}的{metric}算术平均值。",
    "temporal_peak_followup_en_01": "在{start_period}至{end_period}期间，找出{entity}的{primary_metric}最高时期，并报告同一期的{secondary_metric}。",
    "temporal_peak_followup_en_02": "找出{entity}在{start_period}至{end_period}间{primary_metric}最高的期间，并报告该期的{secondary_metric}。",
    "filter_then_rank_en_01": "在{scope}中，筛选{period}的{growth_metric}增长超过{growth_threshold}%的公司，再按{ranking_metric}列出前{top_k}名。",
    "filter_then_rank_en_02": "针对{period}，从{scope}筛选{growth_metric}增幅高于{growth_threshold}%的公司，再按{ranking_metric}排名并列出前{top_k}家。",
    "rank_then_secondary_lookup_en_01": "在{scope}中，按{period}的{primary_metric}排名取前{top_k}家公司，再报告每家公司的{secondary_metric}。",
    "rank_then_secondary_lookup_en_02": "按{period}的{primary_metric}对{scope}中的公司排名取前{top_k}名，然后报告其同期{secondary_metric}。",
    "multi_factor_screening_en_01": "在{scope}中，哪些公司在{period}同时满足：{growth_metric}增长超过{growth_threshold}%、{ranking_metric}高于{benchmark}、且{debt_metric}低于{debt_threshold}%？",
    "multi_factor_screening_en_02": "使用三项条件筛选{period}的{scope}：{growth_metric}增幅大于{growth_threshold}%、{ranking_metric}高于{benchmark}、{debt_metric}低于{debt_threshold}%。",
    "derived_input_trace_en_01": "计算{derived_type}结果{derived_id}使用了哪些输入事实？",
    "provenance_trace_en_01": "请追溯事实{fact_id}的数据源、来源定义和原始对象。",
    "time_hierarchy_membership_en_01": "事实{fact_id}对应期间属于哪个{hierarchy_type}？",
    "scope_composition_en_01": "派生结果{derived_id}的{scope_label}包含哪些实体？",
    "walk_temporal_peak_followup_provenance_en_01": "在{start_period}至{end_period}期间，找出{entity}的{primary_metric}最高值，再报告同一期的{secondary_metric}及其来源原始文件。",
    "walk_scope_filter_rank_followup_en_01": "在{scope}中，筛选{period}的{growth_metric}增幅超过{growth_threshold}%的公司，再按{primary_metric}排名取前{top_k}名，并报告第一名的{secondary_metric}。",
    "walk_derived_input_time_source_trace_en_01": "{derived_type}结果{derived_id}由哪些事实计算得到？请列出对应财政年度和来源原始文件。",
}

for _english_template in list(TEMPLATES):
    _text = _ZH_TEMPLATE_TEXTS.get(_english_template["template_id"])
    if _text:
        TEMPLATES.append(
            {
                **_english_template,
                "template_id": _english_template["template_id"].replace(
                    "_en_", "_zh_"
                ),
                "language": "zh",
                "template_text": _text,
            }
        )


def template_for(
    task_subtype: str,
    period_type: str | None = None,
    variant_seed: str | None = None,
    *,
    language: str = "en",
) -> dict[str, Any]:
    if task_subtype == "single_fact":
        template_id = {
            "point_in_time": "single_fact_instant_en_01",
            "period_flow": "single_fact_flow_en_01",
        }.get(period_type, "single_fact_observation_en_01")
    elif task_subtype in {
        "derived_input_trace",
        "provenance_trace",
        "time_hierarchy_membership",
        "scope_composition",
        "walk_derived_input_time_source_trace",
    }:
        template_id = {
            "derived_input_trace": "derived_input_trace_en_01",
            "provenance_trace": "provenance_trace_en_01",
            "time_hierarchy_membership": "time_hierarchy_membership_en_01",
            "scope_composition": "scope_composition_en_01",
            "walk_derived_input_time_source_trace": "walk_derived_input_time_source_trace_en_01",
        }[task_subtype]
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
        "temporal_peak_followup",
        "filter_then_rank",
        "rank_then_secondary_lookup",
        "multi_factor_screening",
        "walk_temporal_peak_followup_provenance",
        "walk_scope_filter_rank_followup",
    }:
        prefix = {
            "pairwise_entity_comparison": "pairwise_entity_comparison_en_",
            "cross_metric_comparison": "cross_metric_comparison_en_",
            "multi_period_average": "multi_period_average_en_",
            "temporal_peak_followup": "temporal_peak_followup_en_",
            "filter_then_rank": "filter_then_rank_en_",
            "rank_then_secondary_lookup": "rank_then_secondary_lookup_en_",
            "multi_factor_screening": "multi_factor_screening_en_",
            "walk_temporal_peak_followup_provenance": "walk_temporal_peak_followup_provenance_en_",
            "walk_scope_filter_rank_followup": "walk_scope_filter_rank_followup_en_",
        }[task_subtype]
        options = sorted(
            (item for item in TEMPLATES if item["template_id"].startswith(prefix)),
            key=lambda item: item["template_id"],
        )
        seed = variant_seed or task_subtype
        index = sum(seed.encode("utf-8")) % len(options)
        return _template_in_language(options[index], language)
    else:
        template_id = f"{task_subtype}_en_01"
    template = next(item for item in TEMPLATES if item["template_id"] == template_id)
    return _template_in_language(template, language)


def _template_in_language(
    template: dict[str, Any], language: str
) -> dict[str, Any]:
    normalized = str(language or "en").casefold()
    if normalized == "en":
        return template
    localized_id = str(template["template_id"]).replace("_en_", f"_{normalized}_")
    try:
        return next(item for item in TEMPLATES if item["template_id"] == localized_id)
    except StopIteration as exc:
        raise ValueError(
            f"No {normalized} template for {template['template_id']}"
        ) from exc
