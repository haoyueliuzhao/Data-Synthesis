from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import BaseModel

from trusted_synthesis.core.feedback import (
    FeedbackExposure,
    FeedbackRoute,
    aggregate_pattern_clause_failures,
    allocate_refinement_budget,
    make_feedback_signal,
    route_failure,
)
from trusted_synthesis.core.refinement import (
    CellFeedbackStatistics,
    RefinedSynthesisMaterializer,
    aggregate_cell_feedback,
    build_observed_policy,
    build_synthesis_cell,
    calibrate_clause_feedback,
    update_synthesis_policy,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_legal_contract_case,
    build_science_contract_case,
)
from trusted_synthesis.experiments.training_utility_mvp.schema import (
    CohortEvaluationResult,
    CohortTrainingResult,
    TrainingUtilityMVPConfig,
)
from trusted_synthesis.experiments.training_utility_v09 import (
    V09Cohort,
    V09CohortDatasetManifest,
    V09OnlineGate,
    V09RefinementConfig,
    V09RefinementManifest,
    V09TrainingDataManifest,
    build_v09_offline_pilot,
    build_v09_training_utility_report,
    compile_v09_refinement,
    write_v09_initial_artifacts,
)
from trusted_synthesis.experiments.training_utility_v09.builder import (
    _score_only_cell_utilities,
    _write_refinement_json,
)
from trusted_synthesis.experiments.training_utility_v09.data import (
    _active_domain_quotas,
    _bounded_weighted_allocation,
    _cohort_manifest,
    _domain_quotas,
    _materialized_records,
    _record_evidence_version_ids,
    _subject_disjoint_finance_case_split,
    _task_signature,
)
from trusted_synthesis.experiments.training_utility_v09.finance_archive_materialization import (
    _CapacityEntry,
    _conflict_free_counts_by_key,
    _materialization_dry_run,
)
from trusted_synthesis.experiments.training_utility_v09.materialization import (
    V09FixtureBindingProvider,
)


def test_refinement_json_writer_serializes_model_collections(tmp_path: Path) -> None:
    class SerializationProbe(BaseModel):
        value: int

    output = tmp_path / "model_tuple.json"
    _write_refinement_json(output, (SerializationProbe(value=7),))

    assert json.loads(output.read_text(encoding="utf-8")) == [{"value": 7}]


def _evaluation_result(cohort: str, score: float) -> CohortEvaluationResult:
    return CohortEvaluationResult(
        cohort=cohort,
        evaluation_dataset_hash="evaluation:test",
        sample_count=1,
        valid_json_rate=score,
        response_contract_rate=score,
        action_plan_contract_rate=score,
        answer_decision_contract_rate=score,
        host_execution_success_rate=score,
        execution_replay_valid_rate=score,
        evidence_recall=score,
        evidence_precision=score,
        execution_coverage=score,
        operation_grounding_score=score,
        tool_necessity_score=score,
        operation_exact_rate=score,
        answer_exact_rate=score,
        citation_exact_rate=score,
        verification_exact_rate=score,
        end_to_end_rate=score,
        mean_latency_ms=0,
        generated_token_count=0,
        failure_counts={},
        domain_metrics={},
        prediction_artifact="predictions.jsonl",
        status="completed",
        result_hash=f"evaluation:{cohort}",
    )


def test_capacity_dry_run_uses_full_corpus_disjointness() -> None:
    entries = (
        _CapacityEntry(
            pattern_id="pattern_a",
            binding_hash="binding_1",
            cell_id="cell_a",
            evidence_version_ids=frozenset(("version_a", "version_shared")),
        ),
        _CapacityEntry(
            pattern_id="pattern_a",
            binding_hash="binding_2",
            cell_id="cell_a",
            evidence_version_ids=frozenset(("version_shared", "version_b")),
        ),
        _CapacityEntry(
            pattern_id="pattern_a",
            binding_hash="binding_3",
            cell_id="cell_a",
            evidence_version_ids=frozenset(("version_c",)),
        ),
    )

    conflict_free = _conflict_free_counts_by_key(entries, key=lambda item: item.pattern_id)
    counts, collisions = _materialization_dry_run(entries, {"pattern_a": 3})

    assert conflict_free == {"pattern_a": 2}
    assert counts == {"pattern_a": 2}
    assert collisions == 1


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
        domain="finance",
        pattern_id="finance.compare",
        failure_family="operation_trace",
    )
    signal = make_feedback_signal(
        task_id="task_1",
        domain="finance",
        pattern_id="finance.compare",
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
        task_quality_scores={"task_1": 0.75},
        quality_score_policy_hash="quality_policy:test",
        quality_score_source="test_quality_vector",
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
    assert c3.domain_weights == {"finance": 1.0, "legal": 0.0, "science": 0.0}
    assert manifest.primary_training_domain == "finance"
    assert manifest.cross_domain_validation_domains == ("legal", "science")
    assert manifest.research_question_ids == ("RQ1", "RQ2", "RQ3")
    assert manifest.engineering_regression_cohort_ids == ("D1", "D2", "D3", "D4", "D5")
    assert manifest.validation_domain_exposure_counts == {"finance": 1}
    assert manifest.refinement_domain_exposure_counts == {"finance": 1}
    assert manifest.validation_task_ids == manifest.refinement_task_ids == ("task_1",)
    assert not c3.feedback_refined
    assert c4.feedback_refined
    assert {item.lambda_value for item in manifest.allocations} == {0.0, 0.5, 1.0}
    assert {item.ablation_id for item in manifest.ccgr_updates} == {
        "static_verified",
        "score_only_feedback",
        "raw_failure_reweighting",
        "no_defect_suppression",
        "no_coverage_regularization",
        "random_same_shift",
        "full_ccgr",
    }
    assert manifest.status == "ready_for_online_gate"


def test_v09_domain_quota_and_weighted_allocation_are_exact() -> None:
    assert _domain_quotas(
        600,
        {"finance": 1.0, "legal": 0.0, "science": 0.0},
    ) == {"finance": 600, "legal": 0, "science": 0}
    assert _active_domain_quotas({"finance": 600, "legal": 0, "science": 0}) == {"finance": 600}

    allocation = _bounded_weighted_allocation(
        7,
        capacities={"a": 2, "b": 10},
        weights={"a": 0.8, "b": 0.2},
    )

    assert sum(allocation.values()) == 7
    assert allocation["a"] == 2
    assert allocation["b"] == 5


def test_historical_v4_manifest_remains_loadable_with_six_ablations() -> None:
    exposure = FeedbackExposure(
        task_id="task_v4",
        domain="finance",
        pattern_id="finance.lookup",
        failure_family="answer_schema",
    )
    signal = make_feedback_signal(
        task_id="task_v4",
        domain="finance",
        pattern_id="finance.lookup",
        clause_id="clause_v4",
        clause_kind="answer_schema_exact",
        failure_family="answer_schema",
        severity="fatal",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        source_kind="quality_contract",
        failure_code="wrong_answer",
        weight=1.0,
    )
    current = compile_v09_refinement(
        V09RefinementConfig(cohort_example_budget=12),
        exposures=(exposure,),
        signals=(signal,),
        feedback_source="v4_compatibility_test",
        round0_real_agent_feedback=False,
        clause_calibration={"answer_schema_exact": 1.0},
        task_quality_scores={"task_v4": 1.0},
        quality_score_policy_hash="quality_policy:v4_test",
        quality_score_source="v4_compatibility_test",
    )
    payload = current.model_dump(mode="json")
    payload["version"] = "training_utility_v09.v4"
    payload["ccgr_updates"] = [
        item for item in payload["ccgr_updates"] if item["ablation_id"] != "score_only_feedback"
    ]
    for contract in payload["cohort_contracts"]:
        contract["domain_weights"] = {"finance": 0.8, "legal": 0.1, "science": 0.1}

    restored = V09RefinementManifest.model_validate(payload)

    assert restored.version == "training_utility_v09.v4"
    assert len(restored.ccgr_updates) == 6


def test_score_only_feedback_uses_only_scalar_cell_quality() -> None:
    statistics = tuple(
        CellFeedbackStatistics(
            cell_id=cell_id,
            exposure_count=4,
            root_feedback_count=1,
            interface_failure_count=0,
            synthesis_defect_count=0,
            capability_gap_count=1,
            uncalibrated_feedback_count=0,
            interface_weight_sum=0,
            synthesis_defect_weight_sum=0,
            capability_gap_weight_sum=cell_rate * 4,
            pattern_exposure_count=8,
            pattern_synthesis_defect_rate=pattern_defect_rate,
            pattern_capability_gap_rate=pattern_gap_rate,
            cell_synthesis_defect_rate=0,
            cell_capability_gap_rate=cell_rate,
            shrinkage_weight=0.5,
            synthesis_defect_risk=pattern_defect_rate,
            capability_gap_demand=pattern_gap_rate,
            target_share=0.5,
            observed_share=0.5,
            coverage_gap=0,
        )
        for cell_id, cell_rate, pattern_defect_rate, pattern_gap_rate in (
            ("cell_a", 0.25, 0.125, 0.375),
            ("cell_b", 0.5, 0.375, 0.125),
        )
    )

    utilities = _score_only_cell_utilities(
        statistics,
        task_quality_scores={"task_a": 0.25, "task_b": 0.75, "task_c": 0.5},
        task_cell_ids={"task_a": "cell_a", "task_b": "cell_a", "task_c": "cell_b"},
        gamma=0.5,
    )

    assert utilities == {"cell_a": -0.5, "cell_b": -0.5}


def test_cross_domain_feedback_does_not_change_finance_refinement_policy() -> None:
    finance_exposure = FeedbackExposure(
        task_id="finance_task",
        domain="finance",
        pattern_id="finance.lookup",
        failure_family="answer_schema",
    )
    legal_exposure = FeedbackExposure(
        task_id="legal_task",
        domain="legal",
        pattern_id="legal.rule_application",
        failure_family="answer_schema",
    )
    finance_signal = make_feedback_signal(
        task_id="finance_task",
        domain="finance",
        pattern_id="finance.lookup",
        clause_id="finance_clause",
        clause_kind="answer_schema_exact",
        failure_family="answer_schema",
        severity="fatal",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        source_kind="quality_contract",
        failure_code="wrong_answer",
        weight=1.0,
    )

    def compile_with_legal_route(route: FeedbackRoute):
        legal_signal = make_feedback_signal(
            task_id="legal_task",
            domain="legal",
            pattern_id="legal.rule_application",
            clause_id="legal_clause",
            clause_kind="answer_schema_exact",
            failure_family="answer_schema",
            severity="fatal",
            route=route,
            source_kind="quality_contract",
            failure_code="wrong_answer",
            weight=3.0,
        )
        return compile_v09_refinement(
            V09RefinementConfig(cohort_example_budget=12),
            exposures=(finance_exposure, legal_exposure),
            signals=(finance_signal, legal_signal),
            feedback_source=f"legal_route:{route.value}",
            round0_real_agent_feedback=False,
            clause_calibration={"answer_schema_exact": 1.0},
            task_quality_scores={"finance_task": 0.5},
            quality_score_policy_hash="quality_policy:invariance",
            quality_score_source="invariance_test",
        )

    capability = compile_with_legal_route(FeedbackRoute.AGENT_CAPABILITY_GAP)
    defect = compile_with_legal_route(FeedbackRoute.UPSTREAM_DATA_DEFECT)
    capability_full = next(
        item for item in capability.ccgr_updates if item.ablation_id == "full_ccgr"
    )
    defect_full = next(item for item in defect.ccgr_updates if item.ablation_id == "full_ccgr")

    assert capability_full.update_id == defect_full.update_id
    assert capability_full.next_policy == defect_full.next_policy
    assert capability.feedback_route_counts != defect.feedback_route_counts
    assert (
        capability.refinement_domain_signal_counts
        == defect.refinement_domain_signal_counts
        == {"finance": 1}
    )


def test_online_gate_fails_when_any_validation_domain_has_no_accepted_sample() -> None:
    exposure = FeedbackExposure(
        task_id="finance_gate_task",
        domain="finance",
        pattern_id="finance.lookup",
        failure_family="answer_schema",
    )
    signal = make_feedback_signal(
        task_id="finance_gate_task",
        domain="finance",
        pattern_id="finance.lookup",
        clause_id="finance_gate_clause",
        clause_kind="answer_schema_exact",
        failure_family="answer_schema",
        severity="fatal",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        source_kind="quality_contract",
        failure_code="wrong_answer",
        weight=1.0,
    )
    incomplete_gate = V09OnlineGate(
        attempted_rate=1.0,
        action_plan_contract_rate=1.0,
        host_execution_evaluable_rate=1.0,
        answer_decision_contract_rate=1.0,
        contract_acceptance_rate=1.0,
        accepted_domains=("finance", "legal"),
        accepted_patterns=("finance.lookup",),
        status="passed",
    )

    with pytest.raises(ValueError, match="all three validation domains"):
        compile_v09_refinement(
            V09RefinementConfig(cohort_example_budget=12),
            exposures=(exposure,),
            signals=(signal,),
            feedback_source="incomplete_online_gate",
            round0_real_agent_feedback=True,
            online_gate=incomplete_gate,
            clause_calibration={"answer_schema_exact": 1.0},
            task_quality_scores={"finance_gate_task": 0.5},
            quality_score_policy_hash="quality_policy:gate",
            quality_score_source="gate_test",
        )


def test_v09_task_migration_signature_ignores_legacy_subject_suffix() -> None:
    common = {
        "domain": "legal",
        "task_type": "rule_application",
        "instruction": "Apply the controlling rule.",
        "level": "hard",
        "requirements": ["cite evidence"],
    }
    legacy = {
        **common,
        "retrieval_scope": {
            "subject_ids": ["filing_case"],
            "corpus_boundary": "legal_contract_fixture_0125",
        },
        "prompt_contract_version": "1",
    }
    current = {
        **common,
        "retrieval_scope": {
            "subject_ids": ["filing_case_0125"],
            "corpus_boundary": "legal_contract_fixture_0125",
        },
        "prompt_contract_version": "3",
    }

    assert _task_signature(legacy) == _task_signature(current)
    assert _task_signature(legacy) != _task_signature(
        {**current, "instruction": "Apply a different rule."}
    )
    assert _task_signature(legacy) != _task_signature(
        {
            **current,
            "retrieval_scope": {
                "subject_ids": ["filing_case_0125"],
                "corpus_boundary": "different_legal_fixture_0125",
            },
        }
    )


@pytest.mark.parametrize(
    ("case_factory", "source_index", "start_index"),
    (
        (build_finance_counterfactual_case, 1, 100_001),
        (build_legal_contract_case, 1, 200_001),
        (build_legal_contract_case, 2, 210_002),
        (build_science_contract_case, 1, 300_001),
    ),
)
def test_route_b_materializes_new_cross_domain_proof_carrying_samples(
    case_factory,
    source_index: int,
    start_index: int,
) -> None:
    source = case_factory(1)
    cell = build_synthesis_cell(
        source.task.public,
        source.corpus,
        source.task.oracle.gold_evidence_ids,
    )
    task_cells = {source.task.task_id: cell}
    policy = build_observed_policy(task_cells)
    statistics = aggregate_cell_feedback(policy, (), (), task_cells)
    update = update_synthesis_policy(
        policy,
        statistics,
        (),
        eta=0,
        beta=1,
        gamma=0,
        total_budget=2,
        calibration_manifest_hash="calibration:route_b_test",
        require_calibrated_feedback=False,
    )
    provider = V09FixtureBindingProvider(
        namespace=f"route_b_{source.domain}",
        start_index=start_index,
    )

    artifacts, report = RefinedSynthesisMaterializer(provider).materialize(
        update,
        seed=17,
        forbidden_task_ids={source.task.task_id},
        forbidden_evidence_version_ids={
            item.evidence_version_id for item in source.corpus.evidence
        },
    )

    assert report.status == "passed"
    assert report.requested_sample_count == 2
    assert report.successfully_materialized_count == 2
    assert report.binding_feasibility_rate == 1
    assert report.contract_pass_rate == 1
    assert report.new_task_identity_rate == 1
    assert report.new_binding_identity_rate == 1
    assert report.new_evidence_identity_rate == 1
    assert len({item.compiled.task.task_id for item in artifacts}) == 2
    assert all(
        item.compiled.reference_assessment.decision.value == "accepted" for item in artifacts
    )
    assert all(item.compiled.quality_contract.clauses for item in artifacts)


def test_route_b_exports_fresh_agent_sft_records_with_compilation_lineage() -> None:
    source = build_finance_counterfactual_case(1)
    cell = build_synthesis_cell(
        source.task.public,
        source.corpus,
        source.task.oracle.gold_evidence_ids,
    )
    task_cells = {source.task.task_id: cell}
    policy = build_observed_policy(task_cells)
    exposure = FeedbackExposure(
        task_id=source.task.task_id,
        domain=source.domain,
        pattern_id=cell.pattern_id,
        failure_family="evidence_selection",
    )
    signal = make_feedback_signal(
        task_id=source.task.task_id,
        domain=source.domain,
        pattern_id=cell.pattern_id,
        clause_id="finance:selected_evidence_exact",
        clause_kind="selected_evidence_exact",
        failure_family="evidence_selection",
        severity="fatal",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        source_kind="quality_contract",
        failure_code="wrong_evidence_selected",
        weight=1.0,
    )
    feedback = calibrate_clause_feedback(
        (signal,),
        task_cells,
        {"selected_evidence_exact": 1.0},
    )
    statistics = aggregate_cell_feedback(
        policy,
        (exposure,),
        feedback,
        task_cells,
    )
    update = update_synthesis_policy(
        policy,
        statistics,
        feedback,
        eta=0,
        beta=1,
        gamma=0,
        total_budget=2,
        calibration_manifest_hash="calibration:route_b_export",
    )
    artifacts, report = RefinedSynthesisMaterializer(
        V09FixtureBindingProvider(namespace="route_b_export", start_index=400_001)
    ).materialize(
        update,
        seed=19,
        forbidden_task_ids={source.task.task_id},
        forbidden_evidence_version_ids={
            item.evidence_version_id for item in source.corpus.evidence
        },
    )

    records = _materialized_records(
        artifacts,
        V09Cohort.VERIFIED_STATIC,
        update=update,
        source_cells_by_task={source.task.task_id: cell},
        source_example_ids={source.task.task_id: "critic_example:accepted"},
        accepted_example_ids={source.task.task_id: "critic_example:accepted"},
        materialization_report=report,
        source_kind="route_b_test",
        clause_feedback=feedback,
        feedback_source="quality_run:test",
    )

    assert len(records) == 2
    assert {item.task_id for item in records}.isdisjoint({source.task.task_id})
    assert all(item.metadata["new_identity_compilation"] for item in records)
    assert all(item.metadata["quality_contract_applied"] for item in records)
    assert all(item.metadata["materialization_report_id"] == report.report_id for item in records)
    assert all(
        item.metadata["contributing_clause_feedback_ids"] == (feedback[0].feedback_id,)
        for item in records
    )
    assert all(
        item.metadata["contributing_failure_families"] == ("evidence_selection",)
        for item in records
    )
    assert all(
        item.metadata["feedback_lineage_mode"] == "cell_policy_contribution" for item in records
    )
    assert all(item.metadata["cell_capability_gap_demand"] > 0 for item in records)
    assert all(item.metadata["feedback_source"] == "quality_run:test" for item in records)
    assert _record_evidence_version_ids(records).isdisjoint(
        {item.evidence_version_id for item in source.corpus.evidence}
    )
    cohort_manifest = _cohort_manifest(
        V09Cohort.VERIFIED_STATIC,
        records,
        selection_policy_id=update.update_id,
        eligible_source_records=records,
        accepted_real_link_count=len(records),
        real_feedback_link_count=len(records),
        materialization_report=report,
    )
    assert cohort_manifest.materialization_mode == "new_compilation"
    assert cohort_manifest.domain_counts == {"finance": 2, "legal": 0, "science": 0}
    assert cohort_manifest.compiler_contract_hash == report.compiler_contract_hash
    assert report.seed_effective
    assert report.candidate_pool_id == "v09_fixture_superpool"
    assert report.sampling_partition_id == "A"
    assert cohort_manifest.real_feedback_link_count == len(records)

    fallback_records = _materialized_records(
        artifacts,
        V09Cohort.FEEDBACK_REFINED,
        update=update,
        source_cells_by_task={source.task.task_id: cell},
        source_example_ids={source.task.task_id: "critic_example:evaluated"},
        accepted_example_ids={},
        materialization_report=report,
        source_kind="route_b_evaluated_feedback_test",
    )
    assert all(not item.metadata["source_candidate_accepted"] for item in fallback_records)
    assert all("accepted_real_example_id" not in item.metadata for item in fallback_records)
    fallback_manifest = _cohort_manifest(
        V09Cohort.FEEDBACK_REFINED,
        fallback_records,
        selection_policy_id=update.update_id,
        eligible_source_records=fallback_records,
        accepted_real_link_count=0,
        real_feedback_link_count=len(fallback_records),
        materialization_report=report,
    )
    assert fallback_manifest.accepted_real_link_count == 0
    assert fallback_manifest.real_feedback_link_count == len(fallback_records)

    external_signal = make_feedback_signal(
        task_id="offline_policy_task",
        domain=source.domain,
        pattern_id=cell.pattern_id,
        clause_id="finance:offline_policy_clause",
        clause_kind="selected_evidence_exact",
        failure_family="evidence_selection",
        severity="fatal",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        source_kind="quality_contract",
        failure_code="wrong_evidence_selected",
        weight=1.0,
    )
    external_feedback = calibrate_clause_feedback(
        (external_signal,),
        {"offline_policy_task": cell},
        {"selected_evidence_exact": 1.0},
    )
    external_records = _materialized_records(
        artifacts,
        V09Cohort.FEEDBACK_REFINED,
        update=update,
        source_cells_by_task={source.task.task_id: cell},
        source_example_ids={source.task.task_id: "critic_example:evaluated"},
        accepted_example_ids={},
        materialization_report=report,
        source_kind="route_b_external_policy_test",
        clause_feedback=external_feedback,
    )
    assert all(
        item.metadata["feedback_lineage_mode"] == "external_policy_cell_context"
        for item in external_records
    )
    assert all(
        item.metadata["policy_clause_feedback_ids"] == (external_feedback[0].feedback_id,)
        for item in external_records
    )
    assert all(item.metadata["contributing_clause_feedback_ids"] == () for item in external_records)


def test_finance_reference_split_preserves_prefix_and_subject_holdout() -> None:
    cases = tuple(build_finance_counterfactual_case(index) for index in range(1, 13))
    first = cases[0]
    first_scope = first.task.public.retrieval_scope
    scope_payload = (
        dict(first_scope) if isinstance(first_scope, dict) else first_scope.model_dump(mode="json")
    )
    cases = (
        replace(
            first,
            task=first.task.model_copy(
                update={
                    "public": first.task.public.model_copy(
                        update={"retrieval_scope": scope_payload}
                    )
                }
            ),
        ),
        *cases[1:],
    )

    selected = _subject_disjoint_finance_case_split(
        cases,
        training_count=4,
        evaluation_count=3,
        fixed_training_prefix_count=2,
        seed=17,
    )

    assert selected[:2] == cases[:2]
    assert len(selected) == 7
    training_subjects = {
        evidence.subject.subject_id for case in selected[:4] for evidence in case.corpus.evidence
    }
    evaluation_subjects = {
        evidence.subject.subject_id for case in selected[4:] for evidence in case.corpus.evidence
    }
    assert training_subjects.isdisjoint(evaluation_subjects)


def test_route_b_replenishes_reused_evidence_and_binding_identity() -> None:
    source = build_finance_counterfactual_case(1)
    cell = build_synthesis_cell(
        source.task.public,
        source.corpus,
        source.task.oracle.gold_evidence_ids,
    )
    task_cells = {source.task.task_id: cell}
    policy = build_observed_policy(task_cells)
    update = update_synthesis_policy(
        policy,
        aggregate_cell_feedback(policy, (), (), task_cells),
        (),
        eta=0,
        beta=1,
        gamma=0,
        total_budget=1,
        calibration_manifest_hash="calibration:route_b_collision",
        require_calibrated_feedback=False,
    )

    provider = V09FixtureBindingProvider(
        namespace="route_b_collision",
        start_index=1,
    )
    baseline, baseline_report = RefinedSynthesisMaterializer(provider).materialize(
        update,
        seed=23,
    )
    assert baseline_report.status == "passed"
    selected_evidence = {
        item.evidence_version_id
        for artifact in baseline
        for item in artifact.candidate.corpus.evidence
    }
    artifacts, report = RefinedSynthesisMaterializer(provider).materialize(
        update,
        seed=23,
        forbidden_evidence_version_ids=selected_evidence,
    )

    assert len(artifacts) == 1
    assert report.status == "passed"
    assert report.successfully_materialized_count == 1
    assert report.provider_candidate_count == 2
    assert report.new_evidence_identity_rate == 0.5
    assert report.candidate_rejection_counts == {"binding_identity_collision": 1}
    assert report.failure_counts == {}


def test_route_b_replenishes_forbidden_subject_identity() -> None:
    source = build_finance_counterfactual_case(1)
    cell = build_synthesis_cell(
        source.task.public,
        source.corpus,
        source.task.oracle.gold_evidence_ids,
    )
    task_cells = {source.task.task_id: cell}
    policy = build_observed_policy(task_cells)
    update = update_synthesis_policy(
        policy,
        aggregate_cell_feedback(policy, (), (), task_cells),
        (),
        eta=0,
        beta=1,
        gamma=0,
        total_budget=1,
        calibration_manifest_hash="calibration:route_b_subject_collision",
        require_calibrated_feedback=False,
    )
    provider = V09FixtureBindingProvider(
        namespace="route_b_subject_collision",
        start_index=1,
    )
    baseline, baseline_report = RefinedSynthesisMaterializer(provider).materialize(
        update,
        seed=29,
    )
    assert baseline_report.status == "passed"
    forbidden_subjects = {
        evidence.subject.subject_id
        for artifact in baseline
        for evidence in artifact.candidate.bundle.evidence
    }

    artifacts, report = RefinedSynthesisMaterializer(provider).materialize(
        update,
        seed=29,
        forbidden_subject_ids=forbidden_subjects,
    )

    assert len(artifacts) == 1
    assert report.status == "passed"
    assert report.provider_candidate_count == 2
    assert report.candidate_rejection_counts == {"subject_identity_collision": 1}
    assert report.forbidden_subject_count == len(forbidden_subjects)
    assert report.forbidden_subject_manifest_hash.startswith(
        "refined_synthesis_forbidden_subject_manifest:"
    )
    assert {
        evidence.subject.subject_id
        for artifact in artifacts
        for evidence in artifact.candidate.bundle.evidence
    }.isdisjoint(forbidden_subjects)


def test_v09_training_report_preserves_offline_causal_boundary() -> None:
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=1,
    )
    cohort_manifests = tuple(
        V09CohortDatasetManifest.model_construct(
            cohort=cohort,
            dataset_hash=f"dataset:{cohort.value}",
        )
        for cohort in V09Cohort
    )
    manifest = V09TrainingDataManifest.model_construct(
        manifest_id="manifest:test",
        causal_status="offline_pilot_only",
        round0_real_agent_feedback=False,
        cohorts=cohort_manifests,
        evaluation_dataset_hash="evaluation:test",
        cohort_example_budget=600,
        supervised_token_budget=1_200_000,
    )
    training_results = tuple(
        CohortTrainingResult(
            cohort=cohort.value,
            config_hash=config.config_hash,
            dataset_hash=f"dataset:{cohort.value}",
            base_model="Qwen/Qwen2.5-7B-Instruct",
            adapter_dir=f"/tmp/{cohort.value}",
            trainable_parameter_count=1,
            total_parameter_count=2,
            final_train_loss=1,
            train_runtime_seconds=1,
            peak_gpu_memory_bytes=1,
            completed_steps=1,
            dependency_versions={},
            status="completed",
            result_hash=f"training:{cohort.value}",
        )
        for cohort in V09Cohort
    )
    base = _evaluation_result("base", 0.1)
    evaluations = tuple(
        _evaluation_result(cohort.value, 0.4 + index * 0.1)
        for index, cohort in enumerate(V09Cohort)
    )

    report = build_v09_training_utility_report(
        config,
        manifest,
        base,
        training_results,
        evaluations,
    )

    assert report.status == "completed"
    assert report.causal_claim_status == "not_identified"
    assert report.c4_minus_c3["end_to_end_rate"] == pytest.approx(0.1)
    assert any("do not identify" in item for item in report.limitations)


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
    full = next(item for item in manifest.ccgr_updates if item.ablation_id == "full_ccgr")
    score_only = next(
        item for item in manifest.ccgr_updates if item.ablation_id == "score_only_feedback"
    )
    random_control = next(
        item for item in manifest.ccgr_updates if item.ablation_id == "random_same_shift"
    )
    assert full.status == "passed"
    assert score_only.utility_mode == "score_only_control"
    assert score_only.activated_binding_constraints == {}
    assert abs(full.total_variation_distance - random_control.total_variation_distance) < 1e-10
    assert full.fixed_group_weights == {"finance": 1.0}
    assert score_only.fixed_group_weights == {"finance": 1.0}
    assert set(manifest.validation_domain_exposure_counts) == {
        "finance",
        "legal",
        "science",
    }
    assert manifest.validation_exposure_count == sum(
        manifest.validation_domain_exposure_counts.values()
    )
    assert manifest.refinement_domain_exposure_counts == {
        "finance": manifest.validation_domain_exposure_counts["finance"]
    }
    assert set(manifest.refinement_domain_signal_counts) == {"finance"}
    assert all(
        item.domain_weights == {"finance": 1.0, "legal": 0.0, "science": 0.0}
        for item in manifest.cohort_contracts
    )
    finance_provider = V09FixtureBindingProvider(
        namespace="finance_only_zero_quota",
        start_index=500_001,
        enabled_domains=("finance",),
    )
    legal_pattern_id = str(
        build_legal_contract_case(1).task.public.metadata["task_pattern"]["pattern_id"]
    )
    with pytest.raises(ValueError, match="absent from the Provider catalog"):
        finance_provider.domain_for_pattern(legal_pattern_id)
    artifacts, materialization_report = RefinedSynthesisMaterializer(finance_provider).materialize(
        full,
        seed=23,
    )
    assert materialization_report.status == "passed"
    assert materialization_report.successfully_materialized_count == 24
    assert {item.compiled.task.public.domain for item in artifacts} == {"finance"}
    assert any(item.route == FeedbackRoute.AGENT_CAPABILITY_GAP for item in signals)
    assert (tmp_path / "feedback_exposures.jsonl").is_file()
    assert (tmp_path / "feedback_signals.jsonl").is_file()
    assert (tmp_path / "synthesis_cells.jsonl").is_file()
    assert (tmp_path / "clause_feedback.jsonl").is_file()
    assert (tmp_path / "ccgr_policy_updates.json").is_file()
    stored = json.loads((tmp_path / "v09_initial_build_report.json").read_text(encoding="utf-8"))
    assert stored["report_id"] == report.report_id
    markdown = (tmp_path / "v09_initial_build_report.md").read_text(encoding="utf-8")
    assert "Real-agent Round-0 feedback: **not executed**" in markdown


def test_route_b_seed_changes_enumeration_and_superpool_partitions_are_disjoint() -> None:
    source = build_finance_counterfactual_case(1)
    cell = build_synthesis_cell(
        source.task.public,
        source.corpus,
        source.task.oracle.gold_evidence_ids,
    )
    task_cells = {source.task.task_id: cell}
    policy = build_observed_policy(task_cells)
    update = update_synthesis_policy(
        policy,
        aggregate_cell_feedback(policy, (), (), task_cells),
        (),
        eta=0,
        beta=1,
        gamma=0,
        total_budget=3,
        calibration_manifest_hash="calibration:seeded_superpool",
        require_calibrated_feedback=False,
    )
    common = {
        "start_index": 800_001,
        "candidate_pool_id": "seed_test_superpool",
        "candidate_pool_size": 100_000,
        "pool_split_seed": 31,
    }
    provider_a = V09FixtureBindingProvider(
        namespace="seed_test_a",
        sampling_partition_id="A",
        **common,
    )
    provider_b = V09FixtureBindingProvider(
        namespace="seed_test_b",
        sampling_partition_id="B",
        **common,
    )
    seed_11, report_11 = RefinedSynthesisMaterializer(provider_a).materialize(
        update,
        seed=11,
    )
    seed_12, report_12 = RefinedSynthesisMaterializer(provider_a).materialize(
        update,
        seed=12,
    )
    partition_b, report_b = RefinedSynthesisMaterializer(provider_b).materialize(
        update,
        seed=11,
    )

    evidence_11 = {
        item.evidence_version_id
        for artifact in seed_11
        for item in artifact.candidate.corpus.evidence
    }
    evidence_12 = {
        item.evidence_version_id
        for artifact in seed_12
        for item in artifact.candidate.corpus.evidence
    }
    evidence_b = {
        item.evidence_version_id
        for artifact in partition_b
        for item in artifact.candidate.corpus.evidence
    }
    assert report_11.status == report_12.status == report_b.status == "passed"
    assert report_11.candidate_pool_contract_hash == report_b.candidate_pool_contract_hash
    assert report_11.sampling_contract_hash != report_b.sampling_contract_hash
    assert evidence_11 != evidence_12
    assert evidence_11.isdisjoint(evidence_b)
