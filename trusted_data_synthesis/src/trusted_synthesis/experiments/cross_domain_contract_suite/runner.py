from __future__ import annotations

from dataclasses import dataclass

from trusted_synthesis.core.evaluation.contracts import (
    DecisionParityReport,
    QualityContract,
    QualityContractCompiler,
    QualityContractRuntime,
    compare_decisions,
)
from trusted_synthesis.core.evaluation.evaluator import (
    CandidateQualityEvaluator,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.plugins import DomainPluginSet
from trusted_synthesis.core.release.schema import CrossDomainContractSuiteResult
from trusted_synthesis.core.synthesis import (
    ProofCarryingSample,
    ProofCarryingSampleCompiler,
    ProofCertificate,
)
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
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
SUITE_VERSION = "1.1.0"


@dataclass(frozen=True)
class CrossDomainContractArtifacts:
    result: CrossDomainContractSuiteResult
    plugin_sets: tuple[DomainPluginSet, ...]
    proof_samples: tuple[ProofCarryingSample, ...]
    quality_contracts: tuple[QualityContract, ...]
    proof_certificates: tuple[ProofCertificate, ...]
    parity_reports: tuple[DecisionParityReport, ...]


def run_cross_domain_contract_suite() -> CrossDomainContractArtifacts:
    cases = build_contract_cases()
    reference_passed = 0
    candidate_passed = 0
    mutation_rejected = 0
    mutation_count = 0
    contract_evaluation_count = 0
    parity_count = 0
    proof_samples = []
    quality_contracts = []
    proof_certificates = []
    parity_reports = []
    failures = []
    for case in cases:
        contract_compiler = QualityContractCompiler(
            case.registry,
            domain_provider=case.quality_clause_provider,
        )
        compiled = ProofCarryingSampleCompiler(
            case.registry,
            contract_compiler,
            case.plugin_set,
            semantic_policy=case.semantic_policy,
        ).compile(case.task, case.bundle, case.proof_graph)
        reference_assessment = compiled.reference_assessment
        proof_samples.append(compiled.sample)
        quality_contracts.append(compiled.quality_contract)
        proof_certificates.append(compiled.sample.certificate)
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
        workflow_verifier = CandidateWorkflowVerifier(
            case.registry,
            semantic_policy=case.semantic_policy,
        )
        candidate_evaluator = CandidateQualityEvaluator(
            semantic_policy=case.semantic_policy,
            workflow_verifier=workflow_verifier,
        )
        contract_runtime = QualityContractRuntime(
            workflow_verifier,
            verifier_registry=contract_compiler.verifier_registry,
        )
        candidate_assessment = candidate_evaluator.evaluate(
            case.task,
            case.corpus,
            case.proof_graph,
            candidate,
        )
        contract_assessment = contract_runtime.evaluate(
            compiled.quality_contract,
            case.task,
            case.corpus,
            case.proof_graph,
            candidate,
        )
        contract_evaluation_count += 1
        parity = compare_decisions(candidate_assessment, contract_assessment)
        parity_reports.append(parity)
        parity_count += int(parity.decisions_match)
        if not parity.decisions_match:
            failures.append(f"{case.domain}:clean_candidate:contract_parity")
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
            contract_assessment = contract_runtime.evaluate(
                compiled.quality_contract,
                case.task,
                case.corpus,
                case.proof_graph,
                mutation,
            )
            contract_evaluation_count += 1
            parity = compare_decisions(assessment, contract_assessment)
            parity_reports.append(parity)
            parity_count += int(parity.decisions_match)
            if not parity.decisions_match:
                failures.append(f"{case.domain}:mutation:{mutation_type}:contract_parity")
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
        quality_contract_count=len(quality_contracts),
        proof_certificate_count=len(proof_certificates),
        contract_evaluation_count=contract_evaluation_count,
        contract_decision_parity_rate=(
            parity_count / contract_evaluation_count if contract_evaluation_count else 0
        ),
        quality_contract_hashes=tuple(item.contract_hash for item in quality_contracts),
        proof_certificate_hashes=tuple(item.certificate_hash for item in proof_certificates),
        quality_contract_compiler_versions=tuple(
            sorted({item.compiler_version for item in quality_contracts})
        ),
        proof_compiler_versions=tuple(
            sorted({item.compiler_version for item in proof_certificates})
        ),
        clause_verifier_manifest_hashes=tuple(
            sorted({item.verifier_manifest_hash for item in quality_contracts})
        ),
        status="passed" if not failures else "failed",
        failure_details=tuple(failures),
    )
    return CrossDomainContractArtifacts(
        result=result,
        plugin_sets=tuple(case.plugin_set for case in cases),
        proof_samples=tuple(proof_samples),
        quality_contracts=tuple(quality_contracts),
        proof_certificates=tuple(proof_certificates),
        parity_reports=tuple(parity_reports),
    )
