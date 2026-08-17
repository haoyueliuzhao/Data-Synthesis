from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bridge_statistical_audit import (
    AnswerProjectionAudit,
    MetricInterval,
    _classify_answer_only_mismatch,
    _earliest_failure_stage,
    _effective_count,
    _entropy_bits,
    _evidence_relation,
    _jensen_shannon_bits,
    _model_owned_trace,
    _normalized_levenshtein,
)


def test_evidence_relation_distinguishes_exact_superset_and_incomplete_sets() -> None:
    gold = ("gold:1", "gold:2")

    assert _evidence_relation((), gold) == "empty"
    assert _evidence_relation(gold, gold) == "exact_gold"
    assert _evidence_relation((*gold, "extra:1"), gold) == "strict_superset"
    assert _evidence_relation(("gold:1",), gold) == "strict_subset"
    assert _evidence_relation(("gold:1", "extra:1"), gold) == "partial_overlap"
    assert _evidence_relation(("extra:1",), gold) == "disjoint"


def test_failure_stage_is_an_ordered_contract_gate_not_the_last_failed_check() -> None:
    assert (
        _earliest_failure_stage(
            terminal_category="model_invalid_trajectory",
            failed_check_ids=("answer_correct", "operation_lineage_covers_gold"),
        )
        == "operation_execution"
    )
    assert (
        _earliest_failure_stage(
            terminal_category="model_invalid_trajectory",
            failed_check_ids=(),
        )
        == "model_contract"
    )
    assert (
        _earliest_failure_stage(
            terminal_category="model_valid_trajectory",
            failed_check_ids=(),
        )
        is None
    )


def test_trace_canonicalization_removes_task_values_but_keeps_operation_semantics() -> None:
    def raw(subject: str, metric: str, period: str, value: float, operator: str):
        return {
            "trajectory": {
                "steps": [
                    {
                        "action": "plan",
                        "tool_name": None,
                        "status": "succeeded",
                        "tool_input": None,
                        "evidence_ids": [],
                        "input_refs": [],
                    },
                    {
                        "action": "select_evidence",
                        "tool_name": "query_structured_fact",
                        "status": "succeeded",
                        "tool_input": {
                            "subject_alias": subject,
                            "metric_alias": metric,
                            "period_label": period,
                        },
                        "evidence_ids": ["gold:1"],
                        "input_refs": ["search:1"],
                    },
                    {
                        "action": "calculate",
                        "tool_name": "calculator",
                        "status": "succeeded",
                        "tool_input": {
                            "operator": operator,
                            "operands": [value, 2.0],
                        },
                        "evidence_ids": ["gold:1"],
                        "input_refs": ["fact:1"],
                    },
                ]
            }
        }

    first = _model_owned_trace(
        raw("Company A", "Revenue", "2024", 100.0, "ratio"), frozenset({"gold:1"})
    )
    second = _model_owned_trace(
        raw("Company B", "Profit", "2023", 999.0, "ratio"), frozenset({"gold:1"})
    )
    changed_operator = _model_owned_trace(
        raw("Company B", "Profit", "2023", 999.0, "mean"), frozenset({"gold:1"})
    )

    assert first == second
    assert first[0] != changed_operator[0]
    assert first[1] != changed_operator[1]


def test_trace_distribution_metrics_have_expected_extremes() -> None:
    assert _jensen_shannon_bits(Counter({"a": 6}), Counter({"a": 6})) == 0.0
    assert _jensen_shannon_bits(Counter({"a": 6}), Counter({"b": 6})) == 1.0
    assert _normalized_levenshtein(("a", "b"), ("a", "b")) == 0.0
    assert _normalized_levenshtein(("a", "b"), ("a", "c")) == 0.5


def test_statistical_interval_keeps_the_frozen_confidence_level() -> None:
    MetricInterval(
        metric_id="trace_change",
        point_estimate=0.5,
        lower_bound=0.25,
        upper_bound=0.75,
    )
    with pytest.raises(ValidationError, match="confidence_level"):
        MetricInterval(
            metric_id="trace_change",
            point_estimate=0.5,
            lower_bound=0.25,
            upper_bound=0.75,
            confidence_level=0.9,
        )


def test_answer_only_mismatch_classification_separates_reference_and_value_errors() -> None:
    def classify(candidate, oracle, answer_projection=None):
        return _classify_answer_only_mismatch(  # type: ignore[arg-type]
            SimpleNamespace(
                normalized_candidate_answer=candidate,
                normalized_oracle_answer=oracle,
            ),
            answer_projection=answer_projection or {},
        )

    assert classify(
        {"difference": "1", "higher_ref": "France"},
        {"difference": "1", "higher_ref": "evidence:fact"},
        {"evidence:fact": "France"},
    ) == ("reference_representation_only", ("higher_ref",))
    assert classify(
        {"difference": "1", "higher_ref": "Switzerland"},
        {"difference": "1", "higher_ref": "evidence:fact"},
        {"evidence:fact": "France"},
    ) == ("reference_identity_only", ("higher_ref",))
    assert classify(
        {"difference": "1", "higher_ref": "evidence:left"},
        {"difference": "1", "higher_ref": "evidence:right"},
    ) == ("reference_identity_only", ("higher_ref",))
    assert classify({"value": "1"}, {"value": "2"}) == (
        "numeric_or_scalar_only",
        ("value",),
    )
    assert classify(
        {"difference": "1", "higher_ref": "France"},
        {"difference": "2", "higher_ref": "evidence:fact"},
    ) == ("mixed_value_and_reference", ("difference", "higher_ref"))
    assert classify({"value": ["1"]}, {"value": ["1", "2"]}) == (
        "structural_or_other",
        ("value.<length>",),
    )


def test_answer_projection_accounting_is_derived_and_fail_closed() -> None:
    values = {
        "answer_only_failure_count": 2,
        "answer_only_failure_counts_by_mechanism": {
            "context_conditioned_action": 2,
            "semantic_reconciliation": 0,
            "recovery_and_stopping": 0,
        },
        "mismatch_class_counts": {"reference_representation_only": 2},
        "mismatch_path_counts": {"higher_ref": 2},
        "pairwise_difference_and_reference_count": 0,
        "scalar_value_count": 0,
        "reference_representation_only_count": 2,
        "reference_identity_only_count": 0,
        "numeric_or_scalar_only_count": 0,
        "mixed_value_and_reference_count": 0,
        "structural_or_other_count": 0,
    }

    observed = AnswerProjectionAudit(**values)
    assert observed.answer_only_failure_count == 2

    with pytest.raises(ValidationError, match="mismatch classes disagree"):
        AnswerProjectionAudit(
            **{
                **values,
                "mismatch_class_counts": {"reference_representation_only": 1},
            }
        )
    with pytest.raises(ValidationError, match="accounted by mechanism"):
        AnswerProjectionAudit(
            **{
                **values,
                "answer_only_failure_counts_by_mechanism": {"context_conditioned_action": 1},
            }
        )


def test_jsd_is_exactly_stable_across_counter_insertion_orders() -> None:
    left_forward = Counter({"a": 7, "b": 3, "c": 2, "d": 1})
    right_forward = Counter({"a": 1, "b": 4, "c": 5, "d": 3})
    left_reverse = Counter({"d": 1, "c": 2, "b": 3, "a": 7})
    right_reverse = Counter({"d": 3, "c": 5, "b": 4, "a": 1})

    assert _jensen_shannon_bits(left_forward, right_forward) == _jensen_shannon_bits(
        left_reverse,
        right_reverse,
    )


def test_entropy_and_effective_count_are_stable_across_counter_order() -> None:
    forward = Counter({"state_a": 2, "state_b": 2, "state_c": 1})
    reverse = Counter({"state_c": 1, "state_b": 2, "state_a": 2})

    assert _entropy_bits(forward) == _entropy_bits(reverse)
    assert _effective_count(forward) == _effective_count(reverse)
