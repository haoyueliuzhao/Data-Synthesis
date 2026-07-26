from __future__ import annotations

from datetime import date
from decimal import Decimal

from trusted_synthesis.core.evaluation.evaluator import (
    CandidateQualityEvaluator,
    ReferenceQualityEvaluator,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence import ScalarObservation, TemporalContext
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.release import SplitPolicy, select_candidate_release
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.finance_pilot.mutations import generate_mutations
from trusted_synthesis.experiments.finance_pilot.sampler import TaskBinding
from trusted_synthesis.experiments.finance_pilot.task_factory import PilotTaskCase
from trusted_synthesis.runtime import CandidateTrajectoryGenerator, InMemoryEvidenceToolRuntime


def _case(finance_evidence: EvidenceItem) -> PilotTaskCase:
    observations = [finance_evidence]
    for year, value in ((2024, "400000"), (2025, "500000")):
        observations.append(
            finance_evidence.model_copy(
                update={
                    "evidence_id": f"evidence:finance:revenue_{year}@kg_test",
                    "assertion_id": f"assertion:finance:revenue_{year}",
                    "evidence_version_id": f"version:finance:revenue_{year}@kg_test",
                    "payload": ScalarObservation(
                        value=Decimal(value),
                        unit="million USD",
                        currency="USD",
                    ),
                    "temporal_context": TemporalContext(
                        label=f"FY{year}",
                        valid_from=date(year - 1, 10, 1),
                        valid_to=date(year, 9, 30),
                        basis="fiscal_period",
                        frequency="annual",
                    ),
                    "provenance": finance_evidence.provenance.model_copy(
                        update={"source_record_id": f"revenue_{year}"}
                    ),
                }
            )
        )
    bundle = EvidenceBundle(
        bundle_id="bundle_finance_pilot_average",
        evidence=tuple(observations),
        purpose="finance pilot average test",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = FinanceTaskPlugin(allow_structured_claims=True).temporal_average(
        graph,
        bundle,
        tuple(item.evidence_id for item in observations),
    )
    corpus = EvidenceCorpus.from_bundle(bundle)
    binding = TaskBinding(
        task_type="temporal_average",
        evidence_ids=task.oracle.gold_evidence_ids,
        stratum=("global", "financial_statement", "annual", "sec", "single_source"),
    )
    return PilotTaskCase(
        binding=binding,
        bundle=bundle,
        corpus=corpus,
        proof_graph=graph,
        task=task,
        distractor_ids=(),
    )


def test_temporal_average_reference_and_candidate_are_accepted(
    finance_evidence: EvidenceItem,
) -> None:
    case = _case(finance_evidence)
    reference = ReferenceWorkflowCompiler().compile(case.task, case.bundle)
    candidate = CandidateTrajectoryGenerator().generate(
        case.task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )

    reference_quality = ReferenceQualityEvaluator(semantic_policy=FinanceSemanticPolicy()).evaluate(
        case.task, case.bundle, case.proof_graph, reference
    )
    candidate_quality = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(),
        claim_verifier=FinanceClaimVerifier(),
    ).evaluate(case.task, case.corpus, case.proof_graph, candidate)

    assert len(case.task.oracle.task_program.nodes) == 4
    assert len(case.binding.stratum) == 5
    assert reference_quality.decision == ReleaseDecision.ACCEPTED
    assert candidate_quality.decision == ReleaseDecision.ACCEPTED
    assert candidate.final_answer["result"]["method"] == "mean"


def test_pilot_mutations_are_rejected_and_not_released(
    finance_evidence: EvidenceItem,
) -> None:
    case = _case(finance_evidence)
    candidate = CandidateTrajectoryGenerator().generate(
        case.task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(),
        claim_verifier=FinanceClaimVerifier(),
    )
    clean = evaluator.evaluate(case.task, case.corpus, case.proof_graph, candidate)
    mutations = generate_mutations(
        case,
        candidate,
        (
            "missing_evidence",
            "arithmetic_error",
            "wrong_answer",
            "citation_mismatch",
            "unsupported_claim",
            "oracle_leakage",
            "disallowed_tool",
            "failed_step",
            "extra_result_field",
            "program_node_mismatch",
            "conflicting_calculation",
            "verification_result_mismatch",
            "claim_value_mismatch",
            "multi_error",
        ),
    )
    mutated = [
        (
            mutation,
            evaluator.evaluate(
                case.task,
                case.corpus,
                case.proof_graph,
                mutation.trajectory,
            ),
        )
        for mutation in mutations
    ]
    selection = select_candidate_release(
        [
            (case.task, candidate, clean),
            *[(case.task, mutation.trajectory, assessment) for mutation, assessment in mutated],
        ],
        SplitPolicy(policy_id="pilot_test_split"),
    )

    assert clean.decision == ReleaseDecision.ACCEPTED
    assert all(assessment.decision == ReleaseDecision.REJECTED for _, assessment in mutated)
    assert all(
        set(mutation.expected_failure_gates).issubset(assessment.fatal_failures)
        for mutation, assessment in mutated
    )
    assert all(
        set(mutation.expected_failure_checks).issubset(assessment.failed_check_ids)
        for mutation, assessment in mutated
    )
    assert all(
        set(mutation.expected_detail_tokens).issubset(
            {detail for details in assessment.check_failure_details.values() for detail in details}
        )
        for mutation, assessment in mutated
        if mutation.expected_detail_tokens
    )
    assert selection.accepted_trajectory_ids == (candidate.trajectory_id,)
