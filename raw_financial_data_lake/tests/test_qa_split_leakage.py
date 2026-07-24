from __future__ import annotations

from finraw.qa.split_leakage import (
    audit_split_leakage,
    entity_is_holdout,
    leakage_policy,
    strict_holdout_clusters,
)


def _row(
    cluster: str,
    *,
    split: str = "train",
    entities: list[str] | None = None,
    metrics: list[str] | None = None,
    year: int = 2023,
    pattern: str = "pattern_shared",
    documents: list[str] | None = None,
    protected_question: str = "What was <slot_entity>'s <slot_metric>?",
) -> dict:
    return {
        "qa_group_id": f"group_{cluster}",
        "semantic_cluster_id": cluster,
        "split": split,
        "task_subtype": "single_fact",
        "entity_ids": entities or ["ENTITY_A"],
        "metric_ids": metrics or ["revenue"],
        "time_scope": {"year": year, "basis": "fiscal_year"},
        "canonical_semantics": {"frequency": "annual"},
        "source_document_ids": documents or [],
        "proposal_semantic_id": pattern,
        "source_metadata": {
            "question_generation": {"protected_question": protected_question}
        },
    }


def test_temporal_holdout_uses_complete_entity_metric_series_component():
    policy = leakage_policy({})
    rows = [
        _row("cluster_old", entities=["SERIES_ENTITY_1"], year=2023),
        _row("cluster_cutoff", entities=["SERIES_ENTITY_1"], year=2025),
        _row("cluster_unrelated", entities=["SERIES_ENTITY_2"], year=2023),
    ]

    result = strict_holdout_clusters(rows, cutoff_year=2025, policy=policy)

    assert result["temporal_holdout_clusters"] == {
        "cluster_old",
        "cluster_cutoff",
    }
    assert "cluster_unrelated" not in result["temporal_holdout_clusters"]


def test_entity_holdout_closes_over_shared_entity_components():
    policy = leakage_policy({})
    heldout = next(
        candidate
        for index in range(10_000)
        if entity_is_holdout(candidate := f"ENTITY_{index}")
    )
    rows = [
        _row("cluster_seed", entities=[heldout, "ENTITY_BRIDGE"]),
        _row("cluster_connected", entities=["ENTITY_BRIDGE"]),
        _row("cluster_unrelated", entities=["ENTITY_OTHER"]),
    ]

    result = strict_holdout_clusters(rows, cutoff_year=3000, policy=policy)

    assert result["entity_holdout_clusters"] == {
        "cluster_seed",
        "cluster_connected",
    }


def test_split_leakage_audit_reports_each_requested_overlap_dimension():
    policy = leakage_policy({})
    rows = [
        _row("cluster_shared", split="train", documents=["doc_1"]),
        _row(
            "cluster_entity",
            split="test_entity_holdout",
            entities=["ENTITY_A"],
            metrics=["net_income"],
        ),
        _row("cluster_temporal", split="test_temporal_holdout"),
        _row("cluster_complex", split="test_complex"),
        _row("cluster_shared", split="test_standard", documents=["doc_1"]),
    ]

    report = audit_split_leakage(rows, policy)
    checks = report["checks"]

    assert checks["semantic_cluster"]["overlap_count"] == 1
    assert checks["entity_holdout_entity"]["overlap_count"] == 1
    assert checks["temporal_holdout_entity_metric_period"]["overlap_count"] == 1
    assert checks["temporal_holdout_entity_metric_series"]["overlap_count"] == 1
    assert checks["complex_holdout_pattern"]["overlap_count"] == 1
    assert checks["source_document"]["overlap_count"] == 1
    assert checks["canonical_question_skeleton"]["overlap_count"] == 1
    assert "complex_holdout_pattern" not in report["violations"]
    assert "canonical_question_skeleton" not in report["violations"]
    assert report["passed"] is False


def test_pattern_and_question_skeleton_overlap_can_be_hard_gated():
    policy = leakage_policy(
        {
            "split_leakage": {
                "enforce_complex_pattern_disjoint": True,
                "enforce_question_skeleton_disjoint": True,
            }
        }
    )
    rows = [
        _row("cluster_train", split="train"),
        _row("cluster_complex", split="test_complex"),
    ]

    report = audit_split_leakage(rows, policy)

    assert "complex_holdout_pattern" in report["violations"]
    assert "canonical_question_skeleton" in report["violations"]
