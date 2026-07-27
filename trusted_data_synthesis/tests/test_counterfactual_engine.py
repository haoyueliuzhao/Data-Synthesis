from __future__ import annotations

import pytest

from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualContext,
    CounterfactualPlanner,
    TypedCounterfactualGenerator,
    calibrate_counterfactuals,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.domains.legal import legal_counterfactual_registry
from trusted_synthesis.domains.science import science_counterfactual_registry
from trusted_synthesis.experiments.counterfactual_validation import (
    run_counterfactual_validation,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.candidate import (
    PlanGivenContractCandidate,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
    build_contract_cases,
)
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime


def test_contract_mines_typed_counterfactuals_and_rejects_each_minimal_case() -> None:
    for case in build_contract_cases():
        context, runtime, registry = _counterfactual_context(case)
        opportunities = CounterfactualPlanner(registry).plan(context)

        assert opportunities
        assert {
            "remove_selected_evidence",
            "set_step_failed",
            "inject_oracle_reference",
            "replace_tool",
            "perturb_program_output",
            "perturb_answer_result",
            "replace_citation_source",
        }.issubset({item.mutation_operator_id for item in opportunities})
        cases = TypedCounterfactualGenerator(registry).generate(context, opportunities)
        assert len(cases) == len(opportunities)
        assert all(item.minimality.passed for item in cases)
        assert all(item.minimality_score > 0.9 for item in cases)
        for item in cases:
            assessment = runtime.evaluate(
                context.contract,
                context.task,
                context.corpus,
                context.proof_graph,
                item.trajectory,
            )
            assert assessment.decision == ReleaseDecision.REJECTED
            assert item.expected_root_clause in assessment.root_failure_clause_ids


def test_cross_domain_counterfactual_calibration_meets_v07_thresholds() -> None:
    for case in build_contract_cases():
        context, runtime, registry = _counterfactual_context(case)

        report, generated = calibrate_counterfactuals(
            (context,),
            registry,
            lambda item, trajectory, current=runtime: current.evaluate(
                item.contract,
                item.task,
                item.corpus,
                item.proof_graph,
                trajectory,
            ),
        )

        assert generated
        assert report.status == "passed", report.model_dump(mode="json")
        assert report.mutation_validity_rate > 0.95
        assert report.mean_minimality_score > 0.9
        assert report.detection_f1 > 0.95
        assert report.root_cause_f1 > 0.9
        assert report.failure_closure_f1 > 0.85
        assert report.clean_false_positive_count == 0
        assert report.clause_coverage_rate == 1.0
        assert report.operator_coverage_rate == 1.0
        assert set(report.operator_metrics) == set(registry.operator_ids)
        assert all(
            metrics.mutation_validity_rate == 1.0 for metrics in report.operator_metrics.values()
        )


def test_counterfactual_planner_fails_closed_for_missing_domain_operator() -> None:
    case = build_contract_cases()[0]
    context, _, _ = _counterfactual_context(case)

    with pytest.raises(ValueError, match="unknown counterfactual operator"):
        CounterfactualPlanner(science_counterfactual_registry()).plan(context)


def test_counterfactual_generation_is_deterministic() -> None:
    case = build_contract_cases()[1]
    context, _, registry = _counterfactual_context(case)
    planner = CounterfactualPlanner(registry)
    opportunities = planner.plan(context)
    generator = TypedCounterfactualGenerator(registry)

    first = generator.generate(context, opportunities)
    second = generator.generate(context, planner.plan(context))

    assert [item.counterfactual_id for item in first] == [item.counterfactual_id for item in second]
    assert [item.mutated_hash for item in first] == [item.mutated_hash for item in second]


def test_validation_suite_calibrates_finance_legal_and_science() -> None:
    report = run_counterfactual_validation(tasks_per_domain=2)

    assert report.status == "passed", report.model_dump(mode="json")
    assert report.domain_task_counts == {"finance": 2, "legal": 2, "science": 2}
    assert set(report.domain_reports) == {"finance", "legal", "science"}
    assert report.source_sample_count == 6
    assert report.mutation_validity_rate > 0.95
    assert report.mean_minimality_score > 0.9
    assert report.detection_f1 > 0.95
    assert report.root_cause_f1 > 0.9
    assert report.failure_closure_f1 > 0.85
    assert all(
        domain_report.clause_coverage_rate == 1.0 and domain_report.operator_coverage_rate == 1.0
        for domain_report in report.domain_reports.values()
    )


def _counterfactual_context(case: ContractCase):
    compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
    ).compile(case.task, case.bundle, case.proof_graph)
    candidate = PlanGivenContractCandidate(case.registry).generate(
        case.task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    verifier = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
    )
    runtime = QualityContractRuntime(
        verifier,
        verifier_registry=compiler.verifier_registry,
    )
    registry = (
        legal_counterfactual_registry()
        if case.domain == "legal"
        else science_counterfactual_registry()
    )
    context = CounterfactualContext(
        source_sample=compiled.sample,
        task=case.task,
        contract=compiled.quality_contract,
        corpus=case.corpus,
        proof_graph=case.proof_graph,
        source_trajectory=candidate,
    )
    return context, runtime, registry
