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
        "template_id": "single_fact_flow_en_02",
        "task_family": "single_fact",
        "period_type": "period_flow",
        "language": "en",
        "template_text": "For {period}, what {metric} did {entity} report?",
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
        "template_id": "single_fact_instant_en_02",
        "task_family": "single_fact",
        "period_type": "point_in_time",
        "language": "en",
        "template_text": "As of {period}, what {metric} did {entity} report?",
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
        "template_id": "single_fact_observation_en_02",
        "task_family": "single_fact",
        "period_type": "observation",
        "language": "en",
        "template_text": "For {period}, what {metric} value was recorded for {entity}?",
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
        "template_id": "difference_en_02",
        "task_family": "calculation",
        "language": "en",
        "template_text": "Calculate the change in {entity}'s {metric} between {previous_period} and {period}.",
        "required_slots": ["entity", "metric", "previous_period", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "difference_instant_en_01",
        "task_family": "calculation",
        "period_type": "point_in_time",
        "language": "en",
        "template_text": "Between the ends of {previous_period} and {period}, by how much did {entity}'s {metric} change?",
        "required_slots": ["entity", "metric", "previous_period", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "difference_instant_en_02",
        "task_family": "calculation",
        "period_type": "point_in_time",
        "language": "en",
        "template_text": "Calculate the change in {entity}'s {metric} from the end of {previous_period} to the end of {period}.",
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
        "template_id": "yoy_growth_en_02",
        "task_family": "calculation",
        "language": "en",
        "template_text": "How did {entity}'s {metric} change year over year in {period}?",
        "required_slots": ["entity", "metric", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "yoy_growth_instant_en_01",
        "task_family": "calculation",
        "period_type": "point_in_time",
        "language": "en",
        "template_text": "What was the year-over-year change in {entity}'s {metric} as of the end of {period}?",
        "required_slots": ["entity", "metric", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "yoy_growth_instant_en_02",
        "task_family": "calculation",
        "period_type": "point_in_time",
        "language": "en",
        "template_text": "At the end of {period}, how much had {entity}'s {metric} changed from the prior fiscal-year end, in percentage terms?",
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
        "template_id": "ratio_en_02",
        "task_family": "calculation",
        "language": "en",
        "template_text": "Calculate {entity}'s {ratio} for {period}.",
        "required_slots": ["entity", "ratio", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "ratio_instant_en_01",
        "task_family": "calculation",
        "period_type": "point_in_time",
        "language": "en",
        "template_text": "As of the end of {period}, what was {entity}'s {ratio}?",
        "required_slots": ["entity", "ratio", "period"],
        "answer_type": "numeric",
        "difficulty_base": "medium",
    },
    {
        "template_id": "ratio_instant_en_02",
        "task_family": "calculation",
        "period_type": "point_in_time",
        "language": "en",
        "template_text": "Calculate {entity}'s {ratio} at the end of {period}.",
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
        "template_text": "Which {period_unit} from {start_period} through {end_period} had {entity}'s {extreme} {metric}, and what was the value?",
        "required_slots": [
            "start_period",
            "end_period",
            "period_unit",
            "entity",
            "metric",
            "extreme",
        ],
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
        "template_text": "Across the {observation_count} {frequency} observations from {start_period} through {end_period}, what was {entity}'s average {metric}?",
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
        "template_text": "What was the mean {metric} for {entity} over the {observation_count} {frequency} observations from {start_period} to {end_period}?",
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
        "template_text": "Which {period_unit} from {start_period} through {end_period} had {entity}'s highest {primary_metric}, and what {secondary_metric} did it report in that same {period_unit}?",
        "required_slots": [
            "entity",
            "primary_metric",
            "secondary_metric",
            "start_period",
            "end_period",
            "period_unit",
        ],
        "answer_type": "period_metric_lookup",
        "difficulty_base": "expert",
    },
    {
        "template_id": "temporal_peak_followup_en_02",
        "task_family": "graph_multi_stage",
        "language": "en",
        "template_text": "Identify {entity}'s peak-{primary_metric} {period_unit} between {start_period} and {end_period}, then give its {secondary_metric} for that period.",
        "required_slots": [
            "entity",
            "primary_metric",
            "secondary_metric",
            "start_period",
            "end_period",
            "period_unit",
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
        "template_text": "Among {scope}, which {top_k} companies led on {primary_metric} in {period}? Include each selected company's {secondary_metric} to provide a second financial comparison.",
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
        "template_text": "For {period}, identify the {top_k} leaders in {primary_metric} among {scope}, and pair each result with the company's {secondary_metric} for the same period.",
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
        "template_text": "Among {scope}, which companies met all three conditions in {period}: {growth_metric} growth above {growth_threshold}%, {ranking_metric} above {benchmark}, and {debt_metric} below {debt_threshold}%?",
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
        "template_text": "Which {period_unit} from {start_period} through {end_period} had {entity}'s highest {primary_metric}? Report the {secondary_metric} for that same period and identify the source filing.",
        "required_slots": [
            "start_period",
            "end_period",
            "period_unit",
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
        "template_text": "Within {scope}, filter companies whose {growth_metric} growth in {period} exceeded {growth_threshold}%, rank the top {top_k} by {primary_metric}, and report the first-ranked company's {secondary_metric}.",
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
    "single_fact_flow_en_02": "{entity}在{period}披露的{metric}为多少？",
    "single_fact_instant_en_01": "截至{period}，{entity}的{metric}是多少？",
    "single_fact_instant_en_02": "截至{period}，{entity}报告的{metric}为多少？",
    "single_fact_observation_en_01": "{entity}在{period}的{metric}观测值是多少？",
    "single_fact_observation_en_02": "{period}记录的{entity}{metric}数值为多少？",
    "difference_en_01": "从{previous_period}到{period}，{entity}的{metric}变化了多少？",
    "difference_en_02": "计算{entity}的{metric}在{previous_period}与{period}之间的变化额。",
    "difference_instant_en_01": "从{previous_period}期末到{period}期末，{entity}的{metric}变化了多少？",
    "difference_instant_en_02": "计算{entity}的{metric}在{previous_period}期末与{period}期末之间的变化额。",
    "yoy_growth_en_01": "{entity}的{metric}在{period}的同比增长率是多少？",
    "yoy_growth_en_02": "{period}，{entity}的{metric}较上年同期变化了多少？",
    "yoy_growth_instant_en_01": "截至{period}期末，{entity}的{metric}同比变化了多少？",
    "yoy_growth_instant_en_02": "{period}期末，{entity}的{metric}较上一财年末变化了百分之多少？",
    "qoq_growth_en_01": "{entity}的{metric}在{period}的环比增长率是多少？",
    "ratio_en_01": "{entity}在{period}的{ratio}是多少？",
    "ratio_en_02": "计算{entity}在{period}的{ratio}。",
    "ratio_instant_en_01": "截至{period}期末，{entity}的{ratio}是多少？",
    "ratio_instant_en_02": "计算{entity}在{period}期末的{ratio}。",
    "share_en_01": "在{scope}中，{entity}在{period}的{metric}占总量的比例是多少？",
    "temporal_extrema_en_01": "从{start_period}到{end_period}，{entity}的{metric}在哪个{period_unit}达到{extreme}，对应数值是多少？",
    "ranking_en_01": "在{scope}中，按{period}的{metric}从高到低列出前{top_k}个实体。",
    "scope_extrema_en_01": "在{scope}中，哪个实体在{period}的{metric}{extreme}？",
    "screening_en_01": "在{scope}中，哪些实体在{period}同时满足全部筛选条件？",
    "long_window_return_en_01": "{entity}的{metric}从{start_period}到{end_period}变化了百分之多少？",
    "pairwise_entity_comparison_en_01": "在{period}，{entity_a}和{entity_b}哪一个的{metric}更高，相差多少？",
    "pairwise_entity_comparison_en_02": "比较{entity_a}与{entity_b}在{period}的{metric}，指出较高者及差额。",
    "cross_metric_comparison_en_01": "对{entity}而言，{period}的{metric_a}和{metric_b}哪一个更高，相差多少？",
    "cross_metric_comparison_en_02": "比较{entity}在{period}的{metric_a}与{metric_b}，并给出绝对差额。",
    "multi_period_average_en_01": "在{start_period}至{end_period}的{observation_count}个{frequency}观测中，{entity}的{metric}平均值是多少？",
    "multi_period_average_en_02": "{entity}的{metric}在{start_period}至{end_period}这{observation_count}个{frequency}观测中的均值是多少？",
    "temporal_peak_followup_en_01": "从{start_period}到{end_period}，{entity}的{primary_metric}在哪个{period_unit}最高，当期报告的{secondary_metric}是多少？",
    "temporal_peak_followup_en_02": "找出{entity}在{start_period}至{end_period}的{primary_metric}峰值{period_unit}，并给出该期间的{secondary_metric}。",
    "filter_then_rank_en_01": "在{scope}中，筛选{period}的{growth_metric}增长超过{growth_threshold}%的公司，再按{ranking_metric}列出前{top_k}名。",
    "filter_then_rank_en_02": "针对{period}，从{scope}筛选{growth_metric}增幅高于{growth_threshold}%的公司，再按{ranking_metric}排名并列出前{top_k}家。",
    "rank_then_secondary_lookup_en_01": "在{scope}中，哪些公司在{period}的{primary_metric}排名前{top_k}？请同时给出各公司的{secondary_metric}，用于补充比较另一项财务维度。",
    "rank_then_secondary_lookup_en_02": "找出{scope}在{period}的{primary_metric}前{top_k}名，并将各公司的同期{secondary_metric}一并列出。",
    "multi_factor_screening_en_01": "在{scope}中，哪些公司在{period}同时满足以下三项条件：{growth_metric}增长超过{growth_threshold}%、{ranking_metric}高于{benchmark}、{debt_metric}低于{debt_threshold}%？",
    "multi_factor_screening_en_02": "使用三项条件筛选{period}的{scope}：{growth_metric}增幅大于{growth_threshold}%、{ranking_metric}高于{benchmark}、{debt_metric}低于{debt_threshold}%。",
    "derived_input_trace_en_01": "计算{derived_type}结果{derived_id}使用了哪些输入事实？",
    "provenance_trace_en_01": "请追溯事实{fact_id}的数据源、来源定义和原始对象。",
    "time_hierarchy_membership_en_01": "事实{fact_id}对应期间属于哪个{hierarchy_type}？",
    "scope_composition_en_01": "派生结果{derived_id}的{scope_label}包含哪些实体？",
    "walk_temporal_peak_followup_provenance_en_01": "从{start_period}到{end_period}，{entity}的{primary_metric}在哪个{period_unit}最高？请给出同期{secondary_metric}并注明来源申报文件。",
    "walk_scope_filter_rank_followup_en_01": "在{scope}中，筛选{period}{growth_metric}增幅超过{growth_threshold}%的公司，再按{primary_metric}取前{top_k}名，并报告第一名的{secondary_metric}。",
    "walk_derived_input_time_source_trace_en_01": "{derived_type}结果{derived_id}由哪些事实计算得到？请列出对应财政年度和来源原始文件。",
}

for _english_template in list(TEMPLATES):
    _text = _ZH_TEMPLATE_TEXTS.get(_english_template["template_id"])
    if _text:
        TEMPLATES.append(
            {
                **_english_template,
                "template_id": _english_template["template_id"].replace("_en_", "_zh_"),
                "language": "zh",
                "template_text": _text,
            }
        )
        TEMPLATES.append(
            {
                **_english_template,
                "template_id": _english_template["template_id"].replace(
                    "_en_", "_mixed_"
                ),
                "language": "mixed",
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
        prefix = {
            "point_in_time": "single_fact_instant_en_",
            "period_flow": "single_fact_flow_en_",
        }.get(period_type, "single_fact_observation_en_")
        return _select_template_variant(prefix, variant_seed or task_subtype, language)
    elif period_type == "point_in_time" and task_subtype in {
        "difference",
        "yoy_growth",
        "ratio",
    }:
        return _select_template_variant(
            f"{task_subtype}_instant_en_", variant_seed or task_subtype, language
        )
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
        prefix = f"{task_subtype}_en_"
        options = [item for item in TEMPLATES if item["template_id"].startswith(prefix)]
        if options:
            return _select_template_variant(
                prefix, variant_seed or task_subtype, language
            )
        template_id = f"{task_subtype}_en_01"
    template = next(item for item in TEMPLATES if item["template_id"] == template_id)
    return _template_in_language(template, language)


def _select_template_variant(
    prefix: str, variant_seed: str, language: str
) -> dict[str, Any]:
    options = sorted(
        (item for item in TEMPLATES if item["template_id"].startswith(prefix)),
        key=lambda item: item["template_id"],
    )
    if not options:
        raise ValueError(f"No templates registered for prefix {prefix}")
    index = sum(str(variant_seed).encode("utf-8")) % len(options)
    return _template_in_language(options[index], language)


def _template_in_language(template: dict[str, Any], language: str) -> dict[str, Any]:
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
