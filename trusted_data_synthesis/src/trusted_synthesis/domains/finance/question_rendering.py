from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.task.materialization import time_label
from trusted_synthesis.core.task.realization import (
    QuestionRendererProfile,
    RendererRegistry,
    render_protected_template,
)


def finance_renderer_profiles() -> tuple[QuestionRendererProfile, ...]:
    return (
        _profile(
            "fact_retrieval",
            "finance.fact_retrieval.v1",
            "direct_lookup",
            "canonical",
            "What is <slot_subject>'s <slot_metric><slot_time_phrase>? "
            "Report the result and identify the source.",
            ("subject", "metric"),
            ("what is", "identify the source"),
            optional_slots=("time_phrase",),
            source_requirement="explicit",
        ),
        _profile(
            "fact_retrieval",
            "finance.fact_retrieval.concise_en.v1",
            "direct_lookup",
            "concise",
            "What value is reported for <slot_metric> of <slot_subject> in <slot_period>? "
            "Cite the source.",
            ("metric", "subject", "period"),
            ("what value", "cite the source"),
            source_requirement="explicit",
        ),
        _profile(
            "fact_retrieval",
            "finance.fact_retrieval.analyst_en.v1",
            "direct_lookup",
            "analyst",
            "For <slot_period>, what is the reported <slot_metric> for <slot_subject>? "
            "Name the supporting source.",
            ("period", "metric", "subject"),
            ("what is", "supporting source"),
            source_requirement="explicit",
        ),
        _profile(
            "fact_retrieval",
            "finance.fact_retrieval.evidence_en.v1",
            "direct_lookup",
            "evidence_explicit",
            "Using the listed evidence, what is <slot_subject>'s <slot_metric> for "
            "<slot_period>? Identify the source.",
            ("subject", "metric", "period"),
            ("what is", "identify the source"),
            source_requirement="explicit",
        ),
        _profile(
            "comparison",
            "finance.comparison.v1",
            "which_is_higher",
            "canonical",
            "Compare <slot_metric> for <slot_left_subject><slot_left_time_phrase> with "
            "<slot_right_subject><slot_right_time_phrase>. Which is higher, and by how much?",
            ("metric", "left_subject", "right_subject"),
            ("compare", "which is higher", "by how much"),
            optional_slots=("left_time_phrase", "right_time_phrase"),
        ),
        _profile(
            "comparison",
            "finance.comparison.concise_en.v1",
            "which_is_higher",
            "concise",
            "At <slot_comparison_period>, which is higher: <slot_left_subject>'s or "
            "<slot_right_subject>'s <slot_metric>, and by how much?",
            ("comparison_period", "left_subject", "right_subject", "metric"),
            ("which is higher", "by how much"),
        ),
        _profile(
            "comparison",
            "finance.comparison.analyst_en.v1",
            "metric_difference",
            "analyst",
            "Compare <slot_left_subject> and <slot_right_subject> on <slot_metric> for "
            "<slot_comparison_period>. Which entity has the higher value, and what is the "
            "difference?",
            ("left_subject", "right_subject", "metric", "comparison_period"),
            ("compare", "higher value", "difference"),
        ),
        _profile(
            "comparison",
            "finance.comparison.evidence_en.v1",
            "which_is_higher",
            "evidence_explicit",
            "Using the listed observations for <slot_comparison_period>, compare "
            "<slot_left_subject> with <slot_right_subject> on <slot_metric>. Which is higher, "
            "and by how much?",
            ("comparison_period", "left_subject", "right_subject", "metric"),
            ("compare", "which is higher", "by how much"),
            source_requirement="explicit",
        ),
        _profile(
            "temporal_growth",
            "finance.temporal_growth.v1",
            "relative_change",
            "canonical",
            "How much did <slot_subject>'s <slot_metric> change <slot_time_range>? "
            "Report the percentage change.",
            ("subject", "metric", "time_range"),
            ("change", "percentage change"),
        ),
        _profile(
            "temporal_growth",
            "finance.temporal_growth.concise_en.v1",
            "relative_change",
            "concise",
            "What is the percentage change in <slot_subject>'s <slot_metric> <slot_time_range>?",
            ("subject", "metric", "time_range"),
            ("percentage change",),
        ),
        _profile(
            "temporal_growth",
            "finance.temporal_growth.analyst_en.v1",
            "relative_change",
            "analyst",
            "Across <slot_time_range>, by what percentage did <slot_subject>'s "
            "<slot_metric> change?",
            ("time_range", "subject", "metric"),
            ("percentage", "change"),
        ),
        _profile(
            "temporal_growth",
            "finance.temporal_growth.evidence_en.v1",
            "relative_change",
            "evidence_explicit",
            "Using the two listed observations, what percentage change did "
            "<slot_subject>'s <slot_metric> record <slot_time_range>?",
            ("subject", "metric", "time_range"),
            ("percentage change",),
            source_requirement="explicit",
        ),
        _profile(
            "registered_cross_metric_comparison",
            "finance.registered_cross_metric_comparison.v1",
            "which_metric_is_higher",
            "canonical",
            "Compare <slot_left_metric> with <slot_right_metric> for <slot_subject>"
            "<slot_time_phrase>. Which metric is higher, and by how much?",
            ("left_metric", "right_metric", "subject"),
            ("compare", "which metric is higher", "by how much"),
            optional_slots=("time_phrase",),
        ),
        _profile(
            "registered_cross_metric_comparison",
            "finance.registered_cross_metric_comparison.concise_en.v1",
            "which_metric_is_higher",
            "concise",
            "For <slot_period>, which is higher for <slot_subject>: <slot_left_metric> or "
            "<slot_right_metric>, and by how much?",
            ("period", "subject", "left_metric", "right_metric"),
            ("which is higher", "by how much"),
        ),
        _profile(
            "registered_cross_metric_comparison",
            "finance.registered_cross_metric_comparison.analyst_en.v1",
            "metric_difference",
            "analyst",
            "Compare <slot_subject>'s <slot_left_metric> and <slot_right_metric> for "
            "<slot_period>. Which metric has the higher value, and what is the difference?",
            ("subject", "left_metric", "right_metric", "period"),
            ("compare", "higher value", "difference"),
        ),
        _profile(
            "registered_cross_metric_comparison",
            "finance.registered_cross_metric_comparison.evidence_en.v1",
            "which_metric_is_higher",
            "evidence_explicit",
            "Using the two listed observations for <slot_period>, compare "
            "<slot_subject>'s <slot_left_metric> with <slot_right_metric>. Which metric is "
            "higher, and by how much?",
            ("period", "subject", "left_metric", "right_metric"),
            ("compare", "which metric is higher", "by how much"),
            source_requirement="explicit",
        ),
        _profile(
            "temporal_average",
            "finance.temporal_average.v1",
            "period_average",
            "canonical",
            "What was the mean <slot_metric> for <slot_subject> <slot_time_window>? "
            "Use every listed observation and identify the sources.",
            ("metric", "subject", "time_window"),
            ("mean", "every listed observation", "identify the sources"),
            source_requirement="explicit",
        ),
        _profile(
            "temporal_average",
            "finance.temporal_average.concise_en.v1",
            "period_average",
            "concise",
            "What is the arithmetic mean of <slot_subject>'s <slot_metric> "
            "<slot_time_window> using every observation?",
            ("subject", "metric", "time_window"),
            ("arithmetic mean", "every observation"),
        ),
        _profile(
            "temporal_average",
            "finance.temporal_average.analyst_en.v1",
            "analyst_average",
            "analyst",
            "Across <slot_time_window>, what average <slot_metric> did <slot_subject> "
            "report when every listed observation is included?",
            ("time_window", "metric", "subject"),
            ("average", "every listed observation"),
        ),
        _profile(
            "temporal_average",
            "finance.temporal_average.evidence_en.v1",
            "period_average",
            "evidence_explicit",
            "Using every listed observation <slot_time_window>, what is the mean "
            "<slot_metric> for <slot_subject>? Identify the sources.",
            ("time_window", "metric", "subject"),
            ("every listed observation", "mean", "identify the sources"),
            source_requirement="explicit",
        ),
        _profile(
            "temporal_absolute_change",
            "finance.temporal_absolute_change.v1",
            "absolute_change",
            "canonical",
            "Calculate the signed absolute change in <slot_subject>'s <slot_metric> "
            "<slot_time_range>.",
            ("subject", "metric", "time_range"),
            ("signed absolute change",),
            response_form="directive",
        ),
        _profile(
            "temporal_absolute_change",
            "finance.temporal_absolute_change.concise_en.v1",
            "absolute_change",
            "concise",
            "What is the signed absolute change in <slot_subject>'s <slot_metric> "
            "<slot_time_range>?",
            ("subject", "metric", "time_range"),
            ("signed absolute change",),
        ),
        _profile(
            "temporal_absolute_change",
            "finance.temporal_absolute_change.analyst_en.v1",
            "absolute_change",
            "analyst",
            "Across <slot_time_range>, by how much did <slot_subject>'s <slot_metric> "
            "change in signed absolute terms?",
            ("time_range", "subject", "metric"),
            ("signed absolute", "change"),
        ),
        _profile(
            "temporal_absolute_change",
            "finance.temporal_absolute_change.evidence_en.v1",
            "absolute_change",
            "evidence_explicit",
            "Using the listed period endpoints, what is the signed absolute change in "
            "<slot_subject>'s <slot_metric> <slot_time_range>?",
            ("subject", "metric", "time_range"),
            ("signed absolute change",),
            source_requirement="explicit",
        ),
        _profile(
            "registered_ratio",
            "finance.registered_ratio.v1",
            "registered_ratio",
            "canonical",
            "Calculate <slot_subject>'s <slot_numerator_metric>-to-"
            "<slot_denominator_metric> ratio<slot_time_phrase> using the registered financial "
            "ratio definition.",
            ("subject", "numerator_metric", "denominator_metric"),
            ("ratio", "registered financial ratio definition"),
            optional_slots=("time_phrase",),
            response_form="directive",
        ),
        _profile(
            "registered_ratio",
            "finance.registered_ratio.concise_en.v1",
            "registered_ratio",
            "concise",
            "What is <slot_subject>'s <slot_numerator_metric>-to-"
            "<slot_denominator_metric> ratio for <slot_period> under the registered "
            "definition?",
            ("subject", "numerator_metric", "denominator_metric", "period"),
            ("ratio", "registered definition"),
        ),
        _profile(
            "registered_ratio",
            "finance.registered_ratio.analyst_en.v1",
            "registered_ratio",
            "analyst",
            "For <slot_period>, what registered financial ratio results from dividing "
            "<slot_subject>'s <slot_numerator_metric> by <slot_denominator_metric>?",
            ("period", "subject", "numerator_metric", "denominator_metric"),
            ("registered financial ratio", "dividing"),
        ),
        _profile(
            "registered_ratio",
            "finance.registered_ratio.evidence_en.v1",
            "registered_ratio",
            "evidence_explicit",
            "Using the listed observations for <slot_period>, what is <slot_subject>'s "
            "registered <slot_numerator_metric>-to-<slot_denominator_metric> ratio?",
            ("period", "subject", "numerator_metric", "denominator_metric"),
            ("registered", "ratio"),
            source_requirement="explicit",
        ),
        _profile(
            "derived_growth_comparison",
            "finance.derived_growth_comparison.v1",
            "growth_comparison",
            "canonical",
            "Compare the percentage growth in <slot_metric> for <slot_left_subject> and "
            "<slot_right_subject> <slot_time_range>. Which <slot_comparison_noun> recorded "
            "the faster growth rate, and by how many percentage points?",
            (
                "metric",
                "left_subject",
                "right_subject",
                "time_range",
                "comparison_noun",
            ),
            ("compare", "percentage growth", "percentage points"),
        ),
        _profile(
            "derived_growth_comparison",
            "finance.derived_growth_comparison.concise_en.v1",
            "growth_comparison",
            "concise",
            "Over <slot_time_range>, which <slot_comparison_noun> had faster percentage "
            "growth in <slot_metric>, <slot_left_subject> or <slot_right_subject>, and by how "
            "many percentage points?",
            (
                "time_range",
                "comparison_noun",
                "metric",
                "left_subject",
                "right_subject",
            ),
            ("percentage growth", "percentage points"),
        ),
        _profile(
            "derived_growth_comparison",
            "finance.derived_growth_comparison.analyst_en.v1",
            "growth_comparison",
            "analyst",
            "Compare <slot_left_subject> with <slot_right_subject> on <slot_metric> growth "
            "<slot_time_range>. Which <slot_comparison_noun> grew faster, and what is the "
            "percentage-point gap?",
            (
                "left_subject",
                "right_subject",
                "metric",
                "time_range",
                "comparison_noun",
            ),
            ("compare", "grew faster", "percentage-point"),
        ),
        _profile(
            "derived_growth_comparison",
            "finance.derived_growth_comparison.evidence_en.v1",
            "growth_comparison",
            "evidence_explicit",
            "Using both entities' period endpoints, compare the percentage growth in "
            "<slot_metric> for <slot_left_subject> and <slot_right_subject> "
            "<slot_time_range>. Which <slot_comparison_noun> was faster, and by how many "
            "percentage points?",
            (
                "metric",
                "left_subject",
                "right_subject",
                "time_range",
                "comparison_noun",
            ),
            ("compare", "percentage growth", "percentage points"),
            source_requirement="explicit",
        ),
    )


def finance_renderer_registry() -> RendererRegistry:
    return RendererRegistry(finance_renderer_profiles())


def canonical_finance_instruction(
    task_type: str,
    evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
) -> str:
    registry = finance_renderer_registry()
    profile = registry.require(f"finance.{task_type}.v1")
    slots = finance_question_slots(task_type, evidence_by_role)
    declared = (*profile.required_slots, *profile.optional_slots)
    return render_protected_template(
        profile.protected_template,
        {slot: slots[slot] for slot in declared},
    )


def finance_question_slots(
    task_type: str,
    evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
) -> dict[str, str]:
    if task_type == "fact_retrieval":
        item = evidence_by_role["fact"][0]
        return {
            "subject": item.subject.name,
            "metric": item.predicate,
            "period": time_label(item),
            "time_phrase": _finance_time_phrase(item),
        }
    if task_type == "comparison":
        left = evidence_by_role["left"][0]
        right = evidence_by_role["right"][0]
        return {
            "metric": left.predicate,
            "left_subject": left.subject.name,
            "right_subject": right.subject.name,
            "left_time_phrase": _finance_time_phrase(left),
            "right_time_phrase": _finance_time_phrase(right),
            "comparison_period": _comparison_period(left, right),
        }
    if task_type == "registered_cross_metric_comparison":
        left = evidence_by_role["left_metric"][0]
        right = evidence_by_role["right_metric"][0]
        return {
            "subject": left.subject.name,
            "left_metric": left.predicate,
            "right_metric": right.predicate,
            "period": time_label(left),
            "time_phrase": _finance_time_phrase(left),
        }
    if task_type in {"temporal_growth", "temporal_absolute_change"}:
        earlier = evidence_by_role["earlier"][0]
        later = evidence_by_role["later"][0]
        return {
            "subject": earlier.subject.name,
            "metric": earlier.predicate,
            "time_range": _time_range_phrase(earlier, later),
        }
    if task_type == "temporal_average":
        series = evidence_by_role["series"]
        first = series[0]
        return {
            "subject": first.subject.name,
            "metric": first.predicate,
            "time_window": _time_window_phrase(series[0], series[-1]),
        }
    if task_type == "registered_ratio":
        numerator = evidence_by_role["numerator"][0]
        denominator = evidence_by_role["denominator"][0]
        return {
            "subject": numerator.subject.name,
            "numerator_metric": numerator.predicate,
            "denominator_metric": denominator.predicate,
            "period": time_label(numerator),
            "time_phrase": _finance_time_phrase(numerator),
        }
    if task_type == "derived_growth_comparison":
        left_earlier = evidence_by_role["left_earlier"][0]
        left_later = evidence_by_role["left_later"][0]
        right_earlier = evidence_by_role["right_earlier"][0]
        return {
            "metric": left_earlier.predicate,
            "left_subject": left_earlier.subject.name,
            "right_subject": right_earlier.subject.name,
            "time_range": _time_range_phrase(left_earlier, left_later),
            "comparison_noun": _comparison_subject_noun(left_earlier, right_earlier),
        }
    raise ValueError(f"unsupported finance question slots: {task_type}")


def _profile(
    task_type: str,
    profile_id: str,
    intent: str,
    style: str,
    template: str,
    required_slots: tuple[str, ...],
    required_cues: tuple[str, ...],
    *,
    optional_slots: tuple[str, ...] = (),
    source_requirement: str = "optional",
    response_form: str = "question",
) -> QuestionRendererProfile:
    return QuestionRendererProfile(
        profile_id=profile_id,
        task_type=task_type,
        intent=intent,
        language="en",
        style=style,
        protected_template=template,
        required_slots=required_slots,
        optional_slots=optional_slots,
        required_operator_cues=required_cues,
        source_requirement=source_requirement,
        response_form=response_form,
    )


def _time_range_phrase(earlier: EvidenceItem, later: EvidenceItem) -> str:
    left = time_label(earlier)
    right = time_label(later)
    if left.startswith("as of ") and right.startswith("as of "):
        return f"between {left.removeprefix('as of ')} and {right.removeprefix('as of ')}"
    if left.startswith("year ended ") and right.startswith("year ended "):
        left_date = left.removeprefix("year ended ")
        right_date = right.removeprefix("year ended ")
        return f"between the years ended {left_date} and {right_date}"
    return f"from {left} to {right}"


def _time_window_phrase(first: EvidenceItem, last: EvidenceItem) -> str:
    left = time_label(first)
    right = time_label(last)
    if left.startswith("as of ") and right.startswith("as of "):
        left_date = left.removeprefix("as of ")
        right_date = right.removeprefix("as of ")
        return f"across all observations between {left_date} and {right_date}"
    if left.startswith("year ended ") and right.startswith("year ended "):
        left_date = left.removeprefix("year ended ")
        right_date = right.removeprefix("year ended ")
        return f"over the years ended {left_date} through {right_date}"
    return f"across {left} through {right}"


def _comparison_subject_noun(left: EvidenceItem, right: EvidenceItem) -> str:
    subject_types = {left.subject.subject_type.casefold(), right.subject.subject_type.casefold()}
    if subject_types <= {"company", "corporation", "issuer"}:
        return "company"
    if subject_types <= {"country", "economy", "sovereign"}:
        return "country"
    if subject_types == {"index"}:
        return "index"
    if subject_types == {"fund"}:
        return "fund"
    return "entity"


def _finance_time_phrase(item: EvidenceItem) -> str:
    label = time_label(item)
    if label == "the stated period":
        return ""
    if label.startswith("as of "):
        return f" {label}"
    if label.startswith("year ended "):
        return f" for the {label}"
    return f" for {label}"


def _comparison_period(left: EvidenceItem, right: EvidenceItem) -> str:
    left_label = time_label(left)
    right_label = time_label(right)
    if left_label == right_label:
        return left_label
    return f"{left_label} versus {right_label}"
