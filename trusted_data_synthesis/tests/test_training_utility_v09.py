from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.core.feedback import (
    FeedbackExposure,
    FeedbackRoute,
    aggregate_pattern_clause_failures,
    allocate_refinement_budget,
    make_feedback_signal,
    route_failure,
)
from trusted_synthesis.experiments.training_utility_v09 import (
    V09Cohort,
    V09RefinementConfig,
    build_v09_offline_pilot,
    compile_v09_refinement,
    write_v09_initial_artifacts,
)


def test_feedback_router_keeps_engineering_and_synthesis_ownership_separate() -> None:
    assert (
        route_failure(
            failure_family="action_execution",
            failure_code="invalid_json",
            action_category="interface_security",
        )
        == FeedbackRoute.INTERFACE_FAILURE
    )
    assert (
        route_failure(
            failure_family="source_grounding",
            failure_code="source_version_mismatch",
        )
        == FeedbackRoute.UPSTREAM_DATA_DEFECT
    )
    assert (
        route_failure(
            failure_family="evidence_selection",
            failure_code="wrong_evidence_selected",
            action_category="semantic_action",
        )
        == FeedbackRoute.AGENT_CAPABILITY_GAP
    )
    assert (
        route_failure(
            failure_family="citation_binding",
            failure_code="citation_does_not_support_claim",
        )
        == FeedbackRoute.AGENT_CAPABILITY_GAP
    )


def test_clause_allocation_is_deterministic_and_preserves_ablation_budget() -> None:
    exposures = (
        FeedbackExposure(
            task_id="task_high_1",
            domain="finance",
            pattern_id="pattern_high",
            failure_family="evidence_selection",
        ),
        FeedbackExposure(
            task_id="task_high_2",
            domain="finance",
            pattern_id="pattern_high",
            failure_family="evidence_selection",
        ),
        FeedbackExposure(
            task_id="task_low_1",
            domain="legal",
            pattern_id="pattern_low",
            failure_family="answer_schema",
        ),
        FeedbackExposure(
            task_id="task_low_2",
            domain="legal",
            pattern_id="pattern_low",
            failure_family="answer_schema",
        ),
    )
    signals = tuple(
        make_feedback_signal(
            task_id=task_id,
            domain="finance",
            pattern_id="pattern_high",
            clause_id=f"clause:{task_id}",
            clause_kind="selected_evidence_exact",
            failure_family="evidence_selection",
            severity="fatal",
            route=FeedbackRoute.AGENT_CAPABILITY_GAP,
            source_kind="quality_contract",
            failure_code="wrong_evidence_selected",
            weight=1.0,
        )
        for task_id in ("task_high_1", "task_high_2")
    )
    failures = aggregate_pattern_clause_failures(exposures, signals)

    static = allocate_refinement_budget(
        failures,
        total_budget=17,
        lambda_value=0,
        capability_signal_count=2,
    )
    focused = allocate_refinement_budget(
        failures,
        total_budget=17,
        lambda_value=1,
        capability_signal_count=2,
    )
    focused_again = allocate_refinement_budget(
        failures,
        total_budget=17,
        lambda_value=1,
        capability_signal_count=2,
    )

    assert sum(item.allocated_count for item in static.cells) == 17
    assert max(item.final_probability for item in static.cells) == 0.5
    assert focused == focused_again
    focused_by_pattern = {item.pattern_id: item for item in focused.cells}
    assert (
        focused_by_pattern["pattern_high"].allocated_count
        > focused_by_pattern["pattern_low"].allocated_count
    )


def test_v09_cohorts_freeze_the_causal_comparison_contract() -> None:
    exposure = FeedbackExposure(
        task_id="task_1",
        domain="science",
        pattern_id="science.compare",
        failure_family="operation_trace",
    )
    signal = make_feedback_signal(
        task_id="task_1",
        domain="science",
        pattern_id="science.compare",
        clause_id="clause_1",
        clause_kind="operation_trace_exact",
        failure_family="operation_trace",
        severity="fatal",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        source_kind="quality_contract",
        failure_code="wrong_operator",
        weight=1.0,
    )

    manifest = compile_v09_refinement(
        V09RefinementConfig(cohort_example_budget=24),
        exposures=(exposure,),
        signals=(signal,),
        feedback_source="test",
        round0_real_agent_feedback=False,
        clause_calibration={"operation_trace_exact": 1.0},
    )

    by_cohort = {item.cohort: item for item in manifest.cohort_contracts}
    c3 = by_cohort[V09Cohort.VERIFIED_STATIC]
    c4 = by_cohort[V09Cohort.FEEDBACK_REFINED]
    assert c3.training_format == c4.training_format == "host_instrumented_joint"
    assert c3.base_model_revision == c4.base_model_revision
    assert c3.training_seed == c4.training_seed
    assert c3.pattern_catalog_hash == c4.pattern_catalog_hash == manifest.pattern_catalog_hash
    assert c3.supervised_token_budget == c4.supervised_token_budget
    assert c3.domain_weights == c4.domain_weights
    assert not c3.feedback_refined
    assert c4.feedback_refined
    assert {item.lambda_value for item in manifest.allocations} == {0.0, 0.5, 1.0}
    assert {item.ablation_id for item in manifest.ccgr_updates} == {
        "static_verified",
        "raw_failure_reweighting",
        "no_defect_suppression",
        "no_coverage_regularization",
        "random_same_shift",
        "full_ccgr",
    }
    assert manifest.status == "ready_for_online_gate"


def test_v09_offline_pilot_builds_cross_domain_feedback_artifacts(
    tmp_path: Path,
) -> None:
    config = V09RefinementConfig(cohort_example_budget=24)

    report, manifest, exposures, signals = build_v09_offline_pilot(
        config,
        tasks_per_domain=1,
    )
    write_v09_initial_artifacts(tmp_path, report, manifest, exposures, signals)

    assert report.status == "passed"
    assert report.domain_task_counts == {"finance": 1, "legal": 1, "science": 1}
    assert report.clean_acceptance_rate == 1
    assert report.valid_case_rate == 1
    assert report.expected_root_match_rate == 1
    assert report.round0_real_agent_feedback is False
    assert manifest.status == "ready_for_online_gate"
    assert manifest.online_gate.status == "not_run"
    assert manifest.external_benchmark_status == "not_executed"
    assert manifest.calibration_coverage_rate >= 0.6
    full = next(
        item for item in manifest.ccgr_updates if item.ablation_id == "full_ccgr"
    )
    random_control = next(
        item
        for item in manifest.ccgr_updates
        if item.ablation_id == "random_same_shift"
    )
    assert full.status == "passed"
    assert abs(
        full.total_variation_distance
        - random_control.total_variation_distance
    ) < 1e-10
    assert any(item.route == FeedbackRoute.AGENT_CAPABILITY_GAP for item in signals)
    assert (tmp_path / "feedback_exposures.jsonl").is_file()
    assert (tmp_path / "feedback_signals.jsonl").is_file()
    assert (tmp_path / "synthesis_cells.jsonl").is_file()
    assert (tmp_path / "clause_feedback.jsonl").is_file()
    assert (tmp_path / "ccgr_policy_updates.json").is_file()
    stored = json.loads(
        (tmp_path / "v09_initial_build_report.json").read_text(encoding="utf-8")
    )
    assert stored["report_id"] == report.report_id
    markdown = (tmp_path / "v09_initial_build_report.md").read_text(encoding="utf-8")
    assert "Real-agent Round-0 feedback: **not executed**" in markdown
