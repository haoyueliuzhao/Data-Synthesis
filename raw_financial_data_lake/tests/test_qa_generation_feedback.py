from __future__ import annotations

from finraw.qa.evaluation.contracts import ISSUE_CODES
from finraw.qa.evaluation.feedback import (
    ISSUE_COMPONENT_TARGETS,
    build_generation_feedback,
)


def test_every_registered_issue_has_a_generation_feedback_target() -> None:
    assert set(ISSUE_CODES) == set(ISSUE_COMPONENT_TARGETS)
    assert ISSUE_COMPONENT_TARGETS["overly_trivial"] == {
        "target_component": "sampling_quota",
        "recommended_action": "reduce_sampling_quota_for_low_information_slice",
        "action_type": "sampling_adjustment",
    }


def test_feedback_cube_preserves_consensus_and_adversarial_confirmation() -> None:
    bundles = [
        _bundle("qa_1", "template_rank", "en"),
        _bundle("qa_2", "template_rank", "zh"),
    ]
    calls = [
        _call("qa_1", "surface_financial_analyst", "weak_followup_logic"),
        _call("qa_1", "grounded_qa_auditor", "weak_followup_logic"),
        _call(
            "qa_1",
            "adversarial_reviewer",
            "weak_followup_logic",
            resolutions={"reasoning_necessity": {"decision": "downgrade"}},
        ),
        _call("qa_2", "surface_financial_analyst", "overly_trivial"),
    ]
    report = build_generation_feedback(bundles, calls)

    followup = report["issue_summary"]["weak_followup_logic"]
    assert followup["flagged_by_any_judge"] == 1
    assert followup["flagged_by_two_or_more"] == 1
    assert followup["confirmed_by_adjudicator"] == 1
    assert followup["target_component"] == "static_pattern_walk_macro"

    trivial = report["issue_summary"]["overly_trivial"]
    assert trivial["flagged_by_two_or_more"] == 0
    assert trivial["correctness_gate"] is False
    recommendation = next(
        row
        for row in report["recommended_actions"]
        if row["issue_code"] == "overly_trivial"
    )
    assert recommendation["action_type"] == "sampling_adjustment"
    assert recommendation["correctness_gate"] is False

    language_hotspots = report["dimension_hotspots"]["language"]
    english = next(
        row
        for row in language_hotspots
        if row["issue_code"] == "weak_followup_logic"
    )
    assert english["dimension_value"] == "en"
    assert english["population_count"] == 1
    assert english["affected_rate_within_component"] == 1.0


def _bundle(qa_id: str, template_id: str, language: str) -> dict:
    return {
        "qa_id": qa_id,
        "sample": {
            "template_id": template_id,
            "graph_pattern_id": "industry_rank_followup",
            "language": language,
            "source_metadata": {},
        },
        "candidate": {
            "pattern_id": "industry_rank_followup",
            "task_subtype": "filtered_rank_followup",
            "metric_ids": ["revenue", "net_margin"],
            "canonical_semantics": {
                "operation_macro_id": "scope_filter_rank_followup"
            },
        },
        "operation_plan": {
            "operator_dag": {
                "operators": [
                    {"operator": "filter"},
                    {"operator": "rank"},
                    {"operator": "lookup_ranked_entities"},
                ]
            }
        },
        "distribution_label": {
            "generation_pipeline": "typed_edge_walk",
            "language": language,
        },
        "generation_pipeline": "typed_edge_walk",
    }


def _call(
    qa_id: str,
    role: str,
    issue_code: str,
    *,
    resolutions: dict | None = None,
) -> dict:
    return {
        "qa_id": qa_id,
        "judge_role": role,
        "status": "succeeded",
        "issue_codes": [issue_code],
        "resolutions": resolutions or {},
    }
