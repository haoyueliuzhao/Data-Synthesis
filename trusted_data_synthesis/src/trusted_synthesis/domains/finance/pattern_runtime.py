from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.binding import EvidenceBinding
from trusted_synthesis.core.task.materialization import (
    oracle_selection_contract,
    resolved_retrieval_scope,
    scalar_answer_schema,
    temporal_sort_key,
    time_label,
    time_phrase,
)
from trusted_synthesis.core.task.pattern import (
    PatternBindingValidationReport,
    TaskPatternMaterialization,
    TaskPatternSpec,
)
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy


class FinanceTaskPatternRuntime:
    runtime_id = "finance_task_pattern_runtime.v1"
    runtime_version = "1.0.0"
    domain = "finance"
    renderer_ids: tuple[str, ...] = (
        "finance.fact_retrieval.v1",
        "finance.comparison.v1",
        "finance.temporal_growth.v1",
        "finance.temporal_average.v1",
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
            item
            for role in pattern.evidence_roles
            for item in evidence_by_role[role.role_id]
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
                earlier_time is not None
                and later_time is not None
                and earlier_time < later_time
            )
            issues.extend(decision.reasons)
        elif pattern.task_type == "temporal_average":
            series = evidence_by_role["series"]
            first = series[0]
            comparisons = tuple(self._policy.compare(first, item) for item in series[1:])
            times = tuple(temporal_sort_key(item) for item in series)
            checks["same_financial_series"] = all(item.comparable for item in comparisons)
            checks["same_subject"] = len(
                {item.subject.subject_id for item in series}
            ) == 1
            checks["strictly_ordered_unique_periods"] = bool(
                all(item is not None for item in times)
                and len(set(times)) == len(times)
                and tuple(sorted(times)) == times
            )
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
            item
            for role in pattern.evidence_roles
            for item in evidence_by_role[role.role_id]
        )
        if pattern.task_type == "fact_retrieval":
            item = evidence_by_role["fact"][0]
            instruction = (
                f"What is {item.subject.name}'s {item.predicate}{time_phrase(item)}? "
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
                f"Compare {left.predicate} for {left.subject.name}{time_phrase(left)} "
                f"with {right.subject.name}{time_phrase(right)}. Which is higher, and by how much?"
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
        return TaskPatternMaterialization(
            instruction=instruction,
            retrieval_scope=resolved_retrieval_scope(evidence),
            answer_schema=answer_schema,
            oracle_selection_contract=oracle_selection_contract(evidence),
            metadata={"domain_plugin_id": "finance_tasks.v2"},
        )
