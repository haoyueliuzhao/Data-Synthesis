from __future__ import annotations

from copy import deepcopy
from typing import Any

from finraw.qa.evaluation.aggregation import _decision
from finraw.qa.evaluation.dataset_metrics import compute_dataset_role_values


def test_train_complex_is_training_but_dev_and_test_are_holdouts() -> None:
    train_complex = _bundle(
        "qa_complex",
        split="train_complex",
        benchmark_task="T3",
        market="greater_china",
        language="zh",
        pipeline="typed_edge_walk",
    )
    dev = deepcopy(train_complex)
    dev["qa_id"] = "qa_dev"
    dev["sample"]["split"] = "dev"
    test = deepcopy(train_complex)
    test["qa_id"] = "qa_test"
    test["sample"]["split"] = "test_complex"

    values = compute_dataset_role_values(
        [train_complex, dev, test],
        contract={"target_release_count": 100},
    )

    assert values["qa_complex"]["training_release_eligible"] is True
    assert values["qa_complex"]["release_role"] == "sft_complex_training"
    assert values["qa_complex"]["dataset_role_value_score"] > 0
    assert values["qa_dev"]["training_release_eligible"] is False
    assert values["qa_dev"]["dataset_role_value_score"] == 0
    assert values["qa_test"]["training_release_eligible"] is False
    assert values["qa_test"]["dataset_role_value_score"] == 0


def test_distribution_noise_is_not_rewarded_for_being_rare() -> None:
    aligned = _bundle(
        "qa_aligned",
        split="train",
        benchmark_task="T3",
        market="greater_china",
        language="en",
        pipeline="typed_edge_walk",
    )
    noise = _bundle(
        "qa_noise",
        split="train",
        benchmark_task="unknown",
        market="unknown",
        language="unknown",
        pipeline="unknown",
    )

    values = compute_dataset_role_values(
        [aligned, noise],
        contract={"target_release_count": 100},
    )

    assert values["qa_aligned"]["dataset_role_value_score"] > 70
    assert values["qa_noise"]["dataset_role_value_score"] <= 15
    assert not values["qa_noise"]["coverage_contributions"]


def test_role_signature_reuses_protected_template_and_semantic_fingerprints() -> None:
    apple = _bundle(
        "qa_apple",
        question="What was Apple revenue in 2023?",
        canonical_question="What was Apple revenue in 2023?",
        protected_question="What was {entity} {metric} in {period}?",
        template_id="single_fact_en_01",
    )
    microsoft = _bundle(
        "qa_microsoft",
        question="What was Microsoft revenue in 2024?",
        canonical_question="What was Microsoft revenue in 2024?",
        protected_question="What was {entity} {metric} in {period}?",
        template_id="single_fact_en_01",
    )

    values = compute_dataset_role_values(
        [apple, microsoft],
        contract={"target_release_count": 100},
    )
    left = values["qa_apple"]["signatures"]
    right = values["qa_microsoft"]["signatures"]

    assert left["protected_or_template_signature"] == right[
        "protected_or_template_signature"
    ]
    assert left["slot_normalized_signature"] == right[
        "slot_normalized_signature"
    ]
    assert left["operation_program_signature"] == right[
        "operation_program_signature"
    ]
    assert left["surface_signature"] == right["surface_signature"]


def test_gap_manifest_contributes_only_to_matching_release_gap() -> None:
    matched = _bundle(
        "qa_matched",
        benchmark_task="T3",
        market="greater_china",
        pipeline="typed_edge_walk",
    )
    unmatched = _bundle(
        "qa_unmatched",
        benchmark_task="T2",
        market="global",
        pipeline="fact_qa",
    )
    values = compute_dataset_role_values(
        [matched, unmatched],
        contract={
            "target_release_count": 100,
            "gap_manifest": [
                {
                    "gap_id": "walk_t3_gc",
                    "benchmark_task": "T3",
                    "market_subset": "greater_china",
                    "generation_pipeline": "typed_edge_walk",
                    "target_count": 50,
                }
            ],
        },
    )

    assert "gap_manifest:walk_t3_gc" in values["qa_matched"][
        "coverage_contributions"
    ]
    assert "gap_manifest" in values["qa_matched"]["components"]
    assert "gap_manifest" not in values["qa_unmatched"]["components"]


def test_holdout_cannot_be_accepted_for_training_coverage() -> None:
    policy = {
        "decision_thresholds": {
            "accepted": 80,
            "coverage_acceptance": 70,
            "manual_review": 60,
        }
    }
    training_decision, _ = _decision(
        75,
        [],
        False,
        False,
        100,
        True,
        policy,
        replacement_mode="human",
    )
    holdout_decision, _ = _decision(
        75,
        [],
        False,
        False,
        100,
        False,
        policy,
        replacement_mode="human",
    )

    assert training_decision == "accepted_for_coverage"
    assert holdout_decision == "manual_review"


def _bundle(
    qa_id: str,
    *,
    split: str = "train",
    benchmark_task: str = "T2",
    market: str = "global",
    language: str = "en",
    pipeline: str = "fact_qa",
    question: str = "What was Apple revenue in 2023?",
    canonical_question: str | None = None,
    protected_question: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    source_metadata = {}
    if protected_question:
        source_metadata["question_generation"] = {
            "protected_question": protected_question
        }
    return {
        "qa_id": qa_id,
        "deterministic_gate_status": "passed",
        "distribution_label": {
            "benchmark_task": benchmark_task,
            "market_subset": market,
            "language": language,
            "topic": "equity_fundamentals",
            "metric_families": ["revenue"],
            "source_classes": ["official_filing"],
            "time_basis": "fiscal_period",
            "frequency": "annual",
            "time_span_months": 0,
            "answer_type": "numeric",
            "operation_families": ["lookup"],
            "primary_operation_family": "lookup",
            "generation_pipeline": pipeline,
            "structural_features": {},
        },
        "sample": {
            "qa_id": qa_id,
            "split": split,
            "language": language,
            "question": question,
            "canonical_question": canonical_question or question,
            "source_metadata": source_metadata,
            "template_id": template_id,
            "answer_type": "numeric",
        },
        "candidate": {
            "pattern_id": "single_fact",
            "task_subtype": "single_fact",
            "entity_ids": ["AAPL_US"],
            "metric_ids": ["revenue"],
            "canonical_semantics": {
                "entity_names": ["Apple"],
                "metric_names": ["revenue"],
                "period_label": "2023",
            },
        },
    }
