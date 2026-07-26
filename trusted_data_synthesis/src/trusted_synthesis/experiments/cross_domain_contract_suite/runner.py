from __future__ import annotations

from dataclasses import dataclass

from trusted_synthesis.core.evaluation.evaluator import (
    CandidateQualityEvaluator,
    ReferenceQualityEvaluator,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.plugins import DomainPluginSet
from trusted_synthesis.core.release.schema import CrossDomainContractSuiteResult
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier
from trusted_synthesis.experiments.cross_domain_contract_suite.candidate import (
    PlanGivenContractCandidate,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_contract_cases,
    fixture_manifest_hash,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.mutations import (
    generate_contract_mutations,
)
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime

SUITE_ID = "cross_domain_candidate_contract_suite.v1"
SUITE_VERSION = "1.0.0"


@dataclass(frozen=True)
class CrossDomainContractArtifacts:
    result: CrossDomainContractSuiteResult
    plugin_sets: tuple[DomainPluginSet, ...]


def run_cross_domain_contract_suite() -> CrossDomainContractArtifacts:
    cases = build_contract_cases()
    reference_passed = 0
    candidate_passed = 0
    mutation_rejected = 0
    mutation_count = 0
    failures = []
    for case in cases:
        reference = ReferenceWorkflowCompiler(case.registry).compile(case.task, case.bundle)
        reference_assessment = ReferenceQualityEvaluator(
            semantic_policy=case.semantic_policy,
            workflow_verifier=ReferenceWorkflowVerifier(case.registry),
        ).evaluate(case.task, case.bundle, case.proof_graph, reference)
        if reference_assessment.decision == ReleaseDecision.ACCEPTED:
            reference_passed += 1
        else:
            failures.append(f"{case.domain}:reference")
        shuffled_corpus = case.corpus.model_copy(
            update={"evidence": tuple(reversed(case.corpus.evidence))}
        )
        candidate = PlanGivenContractCandidate(case.registry).generate(
            case.task.public,
            InMemoryEvidenceToolRuntime(shuffled_corpus),
        )
        candidate_evaluator = CandidateQualityEvaluator(
            semantic_policy=case.semantic_policy,
            workflow_verifier=CandidateWorkflowVerifier(
                case.registry,
                semantic_policy=case.semantic_policy,
            ),
        )
        candidate_assessment = candidate_evaluator.evaluate(
            case.task,
            case.corpus,
            case.proof_graph,
            candidate,
        )
        if candidate_assessment.decision == ReleaseDecision.ACCEPTED:
            candidate_passed += 1
        else:
            failures.append(f"{case.domain}:clean_candidate")
        for mutation_type, mutation in generate_contract_mutations(candidate, case.corpus.evidence):
            mutation_count += 1
            assessment = candidate_evaluator.evaluate(
                case.task,
                case.corpus,
                case.proof_graph,
                mutation,
            )
            if assessment.decision == ReleaseDecision.REJECTED:
                mutation_rejected += 1
            else:
                failures.append(f"{case.domain}:mutation:{mutation_type}")
    task_count = len(cases)
    result = CrossDomainContractSuiteResult(
        suite_id=SUITE_ID,
        suite_version=SUITE_VERSION,
        fixture_manifest_hash=fixture_manifest_hash(cases),
        domains=tuple(case.domain for case in cases),
        task_count=task_count,
        clean_candidate_count=task_count,
        mutation_count=mutation_count,
        reference_pass_rate=reference_passed / task_count,
        clean_candidate_pass_rate=candidate_passed / task_count,
        mutation_rejection_rate=(mutation_rejected / mutation_count if mutation_count else 1),
        status="passed" if not failures else "failed",
        failure_details=tuple(failures),
    )
    return CrossDomainContractArtifacts(
        result=result,
        plugin_sets=tuple(case.plugin_set for case in cases),
    )
