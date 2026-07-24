from __future__ import annotations

from itertools import product

from finraw.qa.evaluation.dataset_metrics import (
    compute_dataset_role_values,
    resolve_dataset_role_contract,
    select_dataset_role_contract,
)
from finraw.qa.evaluation.release import _select_with_distribution_quotas


def test_single_market_pool_selects_the_matching_regional_contract() -> None:
    global_contract = select_dataset_role_contract({}, [_bundle("q1", "global", "en")])
    china_contract = select_dataset_role_contract(
        {}, [_bundle("q2", "greater_china", "zh")]
    )
    combined_contract = select_dataset_role_contract(
        {},
        [_bundle("q1", "global", "en"), _bundle("q2", "greater_china", "zh")],
    )

    assert global_contract["contract_id"] == "finsearchcomp_t2_t3_global_release.v1"
    assert global_contract["target_distributions"][0]["shares"] == {
        "T2": 119 / 203,
        "T3": 84 / 203,
    }
    assert china_contract["contract_id"].endswith("greater_china_release.v1")
    assert combined_contract["contract_id"] == "finsearchcomp_t2_t3_release.v1"


def test_bilingual_contract_key_and_mixed_sample_share_one_cell() -> None:
    contract = resolve_dataset_role_contract(
        {
            "contract_id": "language_alias_test",
            "target_release_count": 10,
            "target_distributions": [
                {
                    "name": "language",
                    "fields": ["language"],
                    "weight": 1,
                    "shares": {"bilingual": 1.0},
                }
            ],
        }
    )
    assert contract["target_distributions"][0]["shares"] == {"mixed": 1.0}
    values = compute_dataset_role_values(
        [_bundle("mixed_qa", "global", "mixed")], contract
    )
    assert values["mixed_qa"]["components"]["gap_language"] == 90.0


def test_release_selector_fills_hard_margins_instead_of_global_top_n() -> None:
    contract = _release_contract()
    rows = []
    index = 0
    for task, language, pipeline in product(
        ("T2", "T3"), ("en", "zh"), ("fact_qa", "typed_edge_walk")
    ):
        for _ in range(5):
            index += 1
            rows.append(
                _eligible(
                    f"qa_{index:03d}",
                    task,
                    language,
                    pipeline,
                    score=100 - index if pipeline == "fact_qa" else 20 - index,
                )
            )
    rows.sort(key=lambda row: (-row["selection_score"], row["qa_id"]))

    result = _select_with_distribution_quotas(
        rows,
        contract,
        20,
        {
            "enforce_distribution_quotas": True,
            "minimum_candidate_multiplier": {"typed_edge_walk": 1.3},
        },
    )

    assert result["quota_satisfied"] is True
    assert result["supply_preflight_passed"] is True
    assert result["selected_counts"] == {
        "benchmark_task": {"T2": 10, "T3": 10},
        "generation_pipeline": {"fact_qa": 10, "typed_edge_walk": 10},
        "language": {"en": 10, "zh": 10},
    }


def test_release_selector_reports_partial_when_walk_supply_is_too_small() -> None:
    contract = _release_contract()
    rows = [
        _eligible(f"fact_{index}", "T2" if index % 2 else "T3", "en", "fact_qa", 100 - index)
        for index in range(30)
    ] + [
        _eligible(f"walk_{index}", "T2", "zh", "typed_edge_walk", 10 - index)
        for index in range(5)
    ]
    rows.sort(key=lambda row: (-row["selection_score"], row["qa_id"]))

    result = _select_with_distribution_quotas(
        rows,
        contract,
        20,
        {
            "enforce_distribution_quotas": True,
            "minimum_candidate_multiplier": {"typed_edge_walk": 1.3},
        },
    )

    assert result["quota_satisfied"] is False
    assert result["supply_preflight_passed"] is False
    assert result["supply_preflight"]["typed_edge_walk"] == {
        "target_count": 10,
        "eligible_count": 5,
        "minimum_candidate_multiplier": 1.3,
        "observed_candidate_multiplier": 0.5,
        "passed": False,
    }
    assert result["unmet_counts"]


def _bundle(qa_id: str, market: str, language: str) -> dict:
    return {
        "qa_id": qa_id,
        "deterministic_gate_status": "passed",
        "distribution_label": {
            "benchmark_task": "T2",
            "market_subset": market,
            "language": language,
            "topic": "equity_fundamentals",
            "metric_families": ["revenue"],
            "source_classes": ["official_filing"],
            "frequency": "annual",
            "time_span_months": 0,
            "answer_type": "numeric",
            "primary_operation_family": "lookup",
            "generation_pipeline": "fact_qa",
        },
        "sample": {
            "qa_id": qa_id,
            "split": "train",
            "language": language,
            "question": "What was revenue?",
            "answer_type": "numeric",
        },
        "candidate": {
            "pattern_id": "single_fact",
            "task_subtype": "single_fact",
            "metric_ids": ["revenue"],
            "canonical_semantics": {},
        },
    }


def _release_contract() -> dict:
    return resolve_dataset_role_contract(
        {
            "contract_id": "release_test",
            "target_distributions": [
                {
                    "name": "benchmark_task",
                    "fields": ["benchmark_task"],
                    "weight": 1,
                    "shares": {"T2": 0.5, "T3": 0.5},
                },
                {
                    "name": "language",
                    "fields": ["language"],
                    "weight": 1,
                    "shares": {"en": 0.5, "zh": 0.5},
                },
                {
                    "name": "generation_pipeline",
                    "fields": ["generation_pipeline"],
                    "weight": 1,
                    "shares": {"fact_qa": 0.5, "typed_edge_walk": 0.5},
                },
            ],
            "release_hard_distributions": [
                "benchmark_task",
                "language",
                "generation_pipeline",
            ],
        }
    )


def _eligible(
    qa_id: str,
    task: str,
    language: str,
    pipeline: str,
    score: float,
) -> dict:
    return {
        "qa_id": qa_id,
        "selection_score": score,
        "distribution_features": {
            "benchmark_task": task,
            "language": language,
            "generation_pipeline": pipeline,
        },
    }
