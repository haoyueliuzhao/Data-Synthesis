from __future__ import annotations

from datetime import date
from decimal import Decimal

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence import ScalarObservation, TemporalContext
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.runtime import CandidateTrajectoryGenerator, InMemoryEvidenceToolRuntime


def _setup(finance_evidence: EvidenceItem):
    bundle = EvidenceBundle(
        bundle_id="bundle_candidate",
        evidence=(finance_evidence,),
        purpose="candidate quality mutations",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    corpus = EvidenceCorpus.from_bundle(bundle)
    candidate = CandidateTrajectoryGenerator().generate(
        task.public, InMemoryEvidenceToolRuntime(corpus)
    )
    return task, corpus, graph, candidate


def test_correct_candidate_is_accepted(finance_evidence: EvidenceItem) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, candidate)

    assert assessment.decision == ReleaseDecision.ACCEPTED
    assert assessment.total_score == 100
    assert all(gate.passed for gate in assessment.hard_gates)


def test_wrong_or_missing_evidence_is_rejected(finance_evidence: EvidenceItem) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    mutated = _mutate_step_evidence(candidate, ActionType.SELECT_EVIDENCE, ())

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "evidence_retrieval_and_selection" in assessment.fatal_failures


def test_unknown_selected_evidence_and_wrong_answer_are_rejected(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    unknown_id = "evidence:finance:unknown@kg_test"
    steps = tuple(
        step.model_copy(update={"evidence_ids": (unknown_id,)})
        if step.action in {ActionType.SEARCH, ActionType.SELECT_EVIDENCE}
        else step
        for step in candidate.steps
    )
    answer = dict(candidate.final_answer)
    answer["result"] = {**answer["result"], "value": "1"}
    mutated = candidate.model_copy(update={"steps": steps, "final_answer": answer})

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "evidence_retrieval_and_selection" in assessment.fatal_failures
    assert "answer_citation_and_claims" in assessment.fatal_failures


def test_resolved_track_searches_a_corpus_with_distractors(
    finance_evidence: EvidenceItem,
) -> None:
    task, _, graph, _ = _setup(finance_evidence)
    distractor = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:distractor@kg_test",
            "assertion_id": "assertion:finance:distractor",
            "evidence_version_id": "version:finance:distractor@kg_test",
            "predicate": "total_assets",
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "distractor"}
            ),
        }
    )
    corpus = EvidenceCorpus(
        corpus_id="corpus_with_distractor",
        evidence=(finance_evidence, distractor),
        build_id="kg_test",
    )
    candidate = CandidateTrajectoryGenerator().generate(
        task.public, InMemoryEvidenceToolRuntime(corpus)
    )

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, candidate)

    assert task.public.retrieval_track.value == "resolved"
    assert assessment.decision == ReleaseDecision.ACCEPTED
    assert candidate.steps[1].evidence_ids == (finance_evidence.evidence_id,)


def test_wrong_calculation_is_rejected(finance_evidence: EvidenceItem) -> None:
    later = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:fact_revenue_2024@kg_test",
            "assertion_id": "assertion:finance:fact_revenue_2024",
            "evidence_version_id": "version:finance:fact_revenue_2024@kg_test",
            "payload": ScalarObservation(
                value=Decimal("421613.5"), unit="million USD", currency="USD"
            ),
            "temporal_context": TemporalContext(
                label="FY2024",
                valid_from=date(2023, 10, 1),
                valid_to=date(2024, 9, 30),
                basis="fiscal_period",
                frequency="annual",
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "fact_revenue_2024"}
            ),
        }
    )
    bundle = EvidenceBundle(
        bundle_id="bundle_candidate_growth",
        evidence=(finance_evidence, later),
        purpose="candidate calculation mutation",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().temporal_growth(
        graph, bundle, finance_evidence.evidence_id, later.evidence_id
    )
    corpus = EvidenceCorpus.from_bundle(bundle)
    candidate = CandidateTrajectoryGenerator().generate(
        task.public, InMemoryEvidenceToolRuntime(corpus)
    )
    mutated_steps = tuple(
        step.model_copy(update={"observation": {"result": {"value": "99"}}})
        if step.action == ActionType.CALCULATE
        else step
        for step in candidate.steps
    )
    mutated = candidate.model_copy(update={"steps": mutated_steps})

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "proof_and_operation" in assessment.fatal_failures


def test_wrong_citation_locator_and_unsupported_claim_are_rejected(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    answer = dict(candidate.final_answer)
    answer["citations"] = [
        {
            **answer["citations"][0],
            "source_locator": {"uri": "https://wrong.example/"},
        }
    ]
    answer["claims"] = [{"claim": "An unsupported causal conclusion."}]
    mutated = candidate.model_copy(update={"final_answer": answer})

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "answer_citation_and_claims" in assessment.fatal_failures


def test_oracle_leakage_and_disallowed_tool_are_rejected(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    steps = []
    for step in candidate.steps:
        if step.action == ActionType.PLAN:
            step = step.model_copy(
                update={"tool_input": {"gold_evidence_ids": task.oracle.gold_evidence_ids}}
            )
        if step.action == ActionType.SEARCH:
            step = step.model_copy(update={"tool_name": "oracle_evidence.read"})
        steps.append(step)
    mutated = candidate.model_copy(update={"steps": tuple(steps)})

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "public_boundary_and_tools" in assessment.fatal_failures


def test_missing_required_check_rejects_without_exception(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    report = CandidateWorkflowVerifier().verify(task, corpus, graph, candidate)
    incomplete = report.model_copy(
        update={
            "checks": tuple(
                check for check in report.checks if check.check_id != "citation_binding"
            )
        }
    )

    class IncompleteVerifier:
        def verify(self, *args, **kwargs):
            return incomplete

    assessment = CandidateQualityEvaluator(workflow_verifier=IncompleteVerifier()).evaluate(
        task, corpus, graph, candidate
    )

    assert assessment.decision == ReleaseDecision.REJECTED
    manifest_gate = next(
        gate for gate in assessment.hard_gates if gate.gate_id == "required_check_manifest"
    )
    assert manifest_gate.details == ("citation_binding",)


def test_claim_field_is_only_allowed_by_answer_contract(
    finance_evidence: EvidenceItem,
) -> None:
    task, _, _, candidate = _setup(finance_evidence)
    answer = {
        **candidate.final_answer,
        "claims": [
            {
                "claim_id": "claim:observed_revenue",
                "claim_type": "observed_metric",
                "predicate": "revenue",
                "evidence_ids": [finance_evidence.evidence_id],
            }
        ],
    }
    normalizer = CandidateAnswerNormalizer()

    disallowed, failures = normalizer.validate_schema(task.public, answer)
    claim_task = task.public.model_copy(
        update={"answer_schema": {**task.public.answer_schema, "allow_claims": True}}
    )
    allowed, allowed_failures = normalizer.validate_schema(claim_task, answer)

    assert not disallowed
    assert "unexpected_top_level:claims" in failures
    assert allowed
    assert allowed_failures == ()


def _mutate_step_evidence(
    candidate: Trajectory, action: ActionType, evidence_ids: tuple[str, ...]
) -> Trajectory:
    return candidate.model_copy(
        update={
            "steps": tuple(
                step.model_copy(update={"evidence_ids": evidence_ids})
                if step.action == action
                else step
                for step in candidate.steps
            )
        }
    )
