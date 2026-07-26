import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_cost_controlled_qa_release.py"
)
SPEC = importlib.util.spec_from_file_location("cost_controlled_release", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
_release_readiness = MODULE._release_readiness


def test_release_readiness_fails_closed_on_distribution_and_review_gaps() -> None:
    result = _release_readiness(
        {
            "numeric_share": 0.55,
            "numeric_target_band": [0.35, 0.45],
            "market_percentage_point_gap": {
                "global": -6.0,
                "greater_china": 6.0,
            },
            "answer_type_target_counts": {
                "numeric": 42,
                "ranked_table": 10,
            },
            "answer_type_actual_counts": {
                "numeric": 55,
                "ranked_table": 5,
            },
        },
        {"decision_counts": {"accepted": 70, "manual_review": 30}},
        100,
    )

    assert result["status"] == "partial_not_training_ready"
    assert result["training_ready"] is False
    assert result["accepted_rate"] == 0.7
    assert result["underfilled_answer_type_counts"] == {"ranked_table": 5}
    assert set(result["reasons"]) == {
        "numeric_answer_share_outside_target_band",
        "market_distribution_limited_by_eligible_capacity",
        "accepted_rate_below_80_percent",
        "contains_manual_review_samples",
        "answer_type_quota_underfilled",
    }


def test_release_readiness_passes_complete_contract() -> None:
    result = _release_readiness(
        {
            "numeric_share": 0.42,
            "numeric_target_band": [0.35, 0.45],
            "market_percentage_point_gap": {"global": 0.0},
            "answer_type_target_counts": {"numeric": 42},
            "answer_type_actual_counts": {"numeric": 42},
        },
        {"decision_counts": {"accepted": 100}},
        100,
    )

    assert result["status"] == "ready"
    assert result["training_ready"] is True
    assert result["reasons"] == []
