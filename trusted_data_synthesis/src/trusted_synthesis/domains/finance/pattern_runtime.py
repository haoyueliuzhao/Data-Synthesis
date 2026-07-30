from __future__ import annotations

from decimal import Decimal

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.binding import EvidenceBinding
from trusted_synthesis.core.task.materialization import (
    oracle_selection_contract,
    resolved_retrieval_scope,
    scalar_answer_schema,
    temporal_sort_key,
    time_label,
)
from trusted_synthesis.core.task.pattern import (
    PatternBindingValidationReport,
    TaskPatternMaterialization,
    TaskPatternSpec,
)
from trusted_synthesis.domains.finance.patterns import REGISTERED_FINANCIAL_RATIO_PAIRS
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy


class FinanceTaskPatternRuntime:
    runtime_id = "finance_task_pattern_runtime.v1"
    runtime_version = "1.1.0"
    domain = "finance"
    renderer_ids: tuple[str, ...] = (
        "finance.fact_retrieval.v1",
        "finance.comparison.v1",
        "finance.temporal_growth.v1",
        "finance.temporal_average.v1",
        "finance.temporal_absolute_change.v1",
        "finance.registered_ratio.v1",
        "finance.derived_growth_comparison.v1",
    )

    def __init__(self) -> None:
        self._policy = FinanceSemanticPolicy()

    def validate_binding(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
    ) -> PatternBindingValidationReport:
        del binding
        all_evidence = tuple(
            item for role in pattern.evidence_roles for item in evidence_by_role[role.role_id]
        )
        checks: dict[str, bool] = {
            "all_evidence_valid": all(
                self._policy.validate_evidence(item).passed for item in all_evidence
            )
        }
        issues: list[str] = []
        if not checks["all_evidence_valid"]:
            issues.append("invalid_finance_evidence")
        if pattern.task_type == "comparison":
            decision = self._policy.compare(
                evidence_by_role["left"][0],
                evidence_by_role["right"][0],
            )
            checks["finance_metric_comparable"] = decision.comparable
            issues.extend(decision.reasons)
        elif pattern.task_type == "temporal_growth":
            earlier = evidence_by_role["earlier"][0]
            later = evidence_by_role["later"][0]
            decision = self._policy.validate_growth_pair(earlier, later)
            earlier_time = temporal_sort_key(earlier)
            later_time = temporal_sort_key(later)
            checks["same_financial_series"] = decision.comparable
            checks["same_subject"] = earlier.subject.subject_id == later.subject.subject_id
            checks["strict_temporal_order"] = bool(
                earlier_time is not None and later_time is not None and earlier_time < later_time
            )
            issues.extend(decision.reasons)
        elif pattern.task_type == "temporal_absolute_change":
            earlier = evidence_by_role["earlier"][0]
            later = evidence_by_role["later"][0]
            decision = self._policy.compare(earlier, later)
            earlier_time = temporal_sort_key(earlier)
            later_time = temporal_sort_key(later)
            checks["same_financial_series"] = decision.comparable
            checks["same_subject"] = earlier.subject.subject_id == later.subject.subject_id
            checks["strict_temporal_order"] = bool(
                earlier_time is not None and later_time is not None and earlier_time < later_time
            )
            issues.extend(decision.reasons)
        elif pattern.task_type == "registered_ratio":
            numerator = evidence_by_role["numerator"][0]
            denominator = evidence_by_role["denominator"][0]
            pair = (numerator.predicate, denominator.predicate)
            checks["registered_financial_ratio_pair"] = pair in REGISTERED_FINANCIAL_RATIO_PAIRS
            checks["same_subject_period_scope"] = (
                numerator.subject.subject_id == denominator.subject.subject_id
                and _period_identity(numerator) == _period_identity(denominator)
                and _scope_identity(numerator) == _scope_identity(denominator)
            )
            checks["same_payload_context"] = _payload_context(numerator) == _payload_context(
                denominator
            )
            checks["same_source"] = numerator.source.source_id == denominator.source.source_id
            checks["same_time_basis"] = (
                bool(numerator.temporal_context.basis)
                and numerator.temporal_context.basis == denominator.temporal_context.basis
            )
            checks["same_frequency"] = (
                bool(numerator.temporal_context.frequency)
                and numerator.temporal_context.frequency == denominator.temporal_context.frequency
            )
            checks["source_definitions_compatible"] = _ratio_definitions_compatible(
                numerator,
                denominator,
            )
            checks["denominator_non_zero"] = (
                isinstance(denominator.payload, ScalarObservation)
                and Decimal(str(denominator.payload.value)) != 0
            )
        elif pattern.task_type == "derived_growth_comparison":
            left_earlier = evidence_by_role["left_earlier"][0]
            left_later = evidence_by_role["left_later"][0]
            right_earlier = evidence_by_role["right_earlier"][0]
            right_later = evidence_by_role["right_later"][0]
            left_decision = self._policy.validate_growth_pair(left_earlier, left_later)
            right_decision = self._policy.validate_growth_pair(
                right_earlier,
                right_later,
            )
            cross_decision = self._policy.compare(left_earlier, right_earlier)
            left_times = (
                temporal_sort_key(left_earlier),
                temporal_sort_key(left_later),
            )
            right_times = (
                temporal_sort_key(right_earlier),
                temporal_sort_key(right_later),
            )
            checks["left_growth_eligible"] = left_decision.comparable
            checks["right_growth_eligible"] = right_decision.comparable
            checks["same_financial_metric"] = cross_decision.comparable
            checks["distinct_subjects"] = (
                left_earlier.subject.subject_id != right_earlier.subject.subject_id
            )
            checks["aligned_growth_windows"] = (
                all(value is not None for value in (*left_times, *right_times))
                and left_times[0] < left_times[1]
                and right_times[0] < right_times[1]
                and left_times == right_times
            )
            issues.extend(left_decision.reasons)
            issues.extend(right_decision.reasons)
            issues.extend(cross_decision.reasons)
        elif pattern.task_type == "temporal_average":
            series = evidence_by_role["series"]
            first = series[0]
            comparisons = tuple(self._policy.compare(first, item) for item in series[1:])
            times = tuple(temporal_sort_key(item) for item in series)
            checks["same_financial_series"] = all(item.comparable for item in comparisons)
            checks["same_subject"] = len({item.subject.subject_id for item in series}) == 1
            checks["strictly_ordered_unique_periods"] = bool(
                all(item is not None for item in times)
                and len(set(times)) == len(times)
                and tuple(sorted(times)) == times
            )
            checks["same_source"] = len({item.source.source_id for item in series}) == 1
            checks["same_exact_scope"] = len({_scope_identity(item) for item in series}) == 1
            checks["contiguous_periods"] = _periods_are_contiguous(series)
            issues.extend(reason for item in comparisons for reason in item.reasons)
        for check_id, passed in checks.items():
            if not passed:
                issues.append(check_id)
        unique_issues = tuple(dict.fromkeys(issues))
        return PatternBindingValidationReport(
            passed=not unique_issues,
            checks=checks,
            issues=unique_issues,
            semantic_alignment_cost=max(len(checks) - 1, 0) * 0.5,
        )

    def materialize(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
    ) -> TaskPatternMaterialization:
        del binding, bundle, proof_graph
        evidence = tuple(
            item for role in pattern.evidence_roles for item in evidence_by_role[role.role_id]
        )
        if pattern.task_type == "fact_retrieval":
            item = evidence_by_role["fact"][0]
            instruction = (
                f"What is {item.subject.name}'s {item.predicate}{_finance_time_phrase(item)}? "
                "Report the result and identify the source."
            )
            answer_schema = {
                "payload_kind": item.evidence_kind.value,
                "allowed_payload_fields": sorted(
                    item.payload.model_dump(mode="json", exclude_none=False)
                ),
            }
        elif pattern.task_type == "comparison":
            left = evidence_by_role["left"][0]
            right = evidence_by_role["right"][0]
            instruction = (
                f"Compare {left.predicate} for {left.subject.name}{_finance_time_phrase(left)} "
                f"with {right.subject.name}{_finance_time_phrase(right)}. "
                "Which is higher, and by how much?"
            )
            answer_schema = scalar_answer_schema(left, "comparison")
        elif pattern.task_type == "temporal_growth":
            earlier = evidence_by_role["earlier"][0]
            later = evidence_by_role["later"][0]
            instruction = (
                f"How much did {earlier.subject.name}'s {earlier.predicate} change from "
                f"{time_label(earlier)} to {time_label(later)}? Report the percentage change."
            )
            answer_schema = {}
        elif pattern.task_type == "temporal_absolute_change":
            earlier = evidence_by_role["earlier"][0]
            later = evidence_by_role["later"][0]
            instruction = (
                f"Calculate the signed absolute change in {earlier.subject.name}'s "
                f"{earlier.predicate} from {time_label(earlier)} to {time_label(later)}."
            )
            answer_schema = scalar_answer_schema(earlier, "absolute_change")
        elif pattern.task_type == "registered_ratio":
            numerator = evidence_by_role["numerator"][0]
            denominator = evidence_by_role["denominator"][0]
            instruction = (
                f"Calculate {numerator.subject.name}'s {numerator.predicate}-to-"
                f"{denominator.predicate} ratio{_finance_time_phrase(numerator)} using the "
                "registered financial ratio definition."
            )
            answer_schema = {}
        elif pattern.task_type == "derived_growth_comparison":
            left_earlier = evidence_by_role["left_earlier"][0]
            left_later = evidence_by_role["left_later"][0]
            right_earlier = evidence_by_role["right_earlier"][0]
            instruction = (
                f"Compare the percentage growth in {left_earlier.predicate} for "
                f"{left_earlier.subject.name} and {right_earlier.subject.name} from "
                f"{time_label(left_earlier)} to {time_label(left_later)}. "
                "Which company grew faster, and by how many percentage points?"
            )
            answer_schema = {
                "comparison_entities": [
                    {
                        "side": "left",
                        "entity_id": left_earlier.subject.subject_id,
                        "entity_name": left_earlier.subject.name,
                    },
                    {
                        "side": "right",
                        "entity_id": right_earlier.subject.subject_id,
                        "entity_name": right_earlier.subject.name,
                    },
                ],
                "growth_unit": "percent",
                "difference_unit": "percentage_points",
            }
        elif pattern.task_type == "temporal_average":
            series = evidence_by_role["series"]
            first = series[0]
            instruction = (
                f"What was the mean {first.predicate} for {first.subject.name} across "
                f"{time_label(series[0])} through {time_label(series[-1])}? "
                "Use every listed observation and identify the sources."
            )
            answer_schema = scalar_answer_schema(first, "aggregate")
        else:
            raise ValueError(f"unsupported finance task pattern: {pattern.task_type}")
        selection_contract = oracle_selection_contract(evidence)
        if pattern.task_type == "derived_growth_comparison":
            left = evidence_by_role["left_earlier"][0]
            right = evidence_by_role["right_earlier"][0]
            selection_contract = {
                **selection_contract,
                "answer_projection": {
                    "projection_type": "labeled_numeric_comparison",
                    "left_operation_ref": "left_growth",
                    "right_operation_ref": "right_growth",
                    "left_entity_id": left.subject.subject_id,
                    "left_entity_name": left.subject.name,
                    "right_entity_id": right.subject.subject_id,
                    "right_entity_name": right.subject.name,
                    "left_value_field": "left_growth_pct",
                    "right_value_field": "right_growth_pct",
                    "difference_field": "difference_percentage_points",
                },
            }
        return TaskPatternMaterialization(
            instruction=instruction,
            retrieval_scope=resolved_retrieval_scope(evidence),
            answer_schema=answer_schema,
            oracle_selection_contract=selection_contract,
            metadata={"domain_plugin_id": "finance_tasks.v2"},
        )


def _finance_time_phrase(item: EvidenceItem) -> str:
    label = time_label(item)
    if label == "the stated period":
        return ""
    if label.startswith("as of "):
        return f" {label}"
    if label.startswith("year ended "):
        return f" for the {label}"
    return f" for {label}"


def _period_identity(
    item: EvidenceItem,
) -> tuple[str | None, str | None, str | None, str | None]:
    context = item.temporal_context
    return (
        context.label,
        context.valid_from.isoformat() if context.valid_from else None,
        context.valid_to.isoformat() if context.valid_to else None,
        context.observed_at.isoformat() if context.observed_at else None,
    )


def _scope_identity(item: EvidenceItem) -> tuple[str | None, str | None]:
    if item.scope is None:
        return None, None
    return item.scope.scope_type, item.scope.scope_id


def _payload_context(item: EvidenceItem) -> tuple[str | None, str | None]:
    if not isinstance(item.payload, ScalarObservation):
        return None, None
    return item.payload.unit, item.payload.currency


def _ratio_definitions_compatible(left: EvidenceItem, right: EvidenceItem) -> bool:
    if not left.definition.definition_id or not right.definition.definition_id:
        return False
    if left.source.source_id != right.source.source_id:
        return False
    fields = ("comparability_level", "period_type", "vintage_policy")
    for field in fields:
        left_value = left.definition.attributes.get(field) or left.domain_context.get(field)
        right_value = right.definition.attributes.get(field) or right.domain_context.get(field)
        if left_value != right_value:
            return False
    return left.domain_context.get("seasonal_adjustment") == right.domain_context.get(
        "seasonal_adjustment"
    )


def _periods_are_contiguous(series: tuple[EvidenceItem, ...]) -> bool:
    return all(
        _periods_are_adjacent(left, right) for left, right in zip(series, series[1:], strict=False)
    )


def _periods_are_adjacent(left: EvidenceItem, right: EvidenceItem) -> bool:
    left_point = temporal_sort_key(left)
    right_point = temporal_sort_key(right)
    if left_point is None or right_point is None or left_point >= right_point:
        return False
    left_class = _period_class(left)
    if left_class != _period_class(right):
        return False
    if left_class == "fiscal_quarter":
        left_index = _fiscal_quarter_index(left)
        right_index = _fiscal_quarter_index(right)
        return left_index is not None and right_index == left_index + 1
    if left_class in {"annual", "yearly"}:
        left_year = _period_year(left, left_point.year)
        right_year = _period_year(right, right_point.year)
        return right_year == left_year + 1
    left_month = left_point.year * 12 + left_point.month
    right_month = right_point.year * 12 + right_point.month
    if left_class == "quarterly":
        return right_month == left_month + 3
    if left_class == "monthly":
        return right_month == left_month + 1
    days = (right_point - left_point).days
    if left_class == "weekly":
        return 5 <= days <= 10
    if left_class == "daily":
        return 1 <= days <= 10
    return False


def _period_class(item: EvidenceItem) -> str:
    fiscal_quarter = str(item.domain_context.get("fiscal_quarter") or "").upper()
    if "YTD" in fiscal_quarter:
        return "unsupported_ytd"
    if fiscal_quarter == "FY":
        return "annual"
    if fiscal_quarter in {"Q1", "Q2", "Q3", "Q4"}:
        return "fiscal_quarter"
    return str(item.temporal_context.frequency or "unknown").casefold()


def _fiscal_quarter_index(item: EvidenceItem) -> int | None:
    fiscal_year = item.domain_context.get("fiscal_year")
    quarter = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3}.get(
        str(item.domain_context.get("fiscal_quarter") or "").upper()
    )
    if fiscal_year is None or quarter is None:
        return None
    return int(fiscal_year) * 4 + quarter


def _period_year(item: EvidenceItem, fallback: int) -> int:
    value = item.domain_context.get("fiscal_year") or item.domain_context.get("calendar_year")
    return int(value) if value is not None else fallback
