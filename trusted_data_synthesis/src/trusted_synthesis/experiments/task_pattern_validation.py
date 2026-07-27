from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
    compare_decisions,
)
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.experiments.cross_domain_contract_suite.candidate import (
    PlanGivenContractCandidate,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_pattern_validation_cases,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime


class TaskPatternValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    validation_id: str
    validation_version: str = "task_pattern_validation.v1"
    requested_tasks_per_domain: int = Field(ge=1)
    task_counts: dict[str, int]
    compiled_task_count: int = Field(ge=0)
    reference_pass_rate: float = Field(ge=0, le=1)
    clean_candidate_pass_rate: float = Field(ge=0, le=1)
    contract_decision_parity_rate: float = Field(ge=0, le=1)
    pattern_binding_clause_rate: float = Field(ge=0, le=1)
    difficulty_clause_rate: float = Field(ge=0, le=1)
    unique_task_count: int = Field(ge=0)
    unique_binding_count: int = Field(ge=0)
    pattern_hashes: tuple[str, ...]
    status: str
    failures: tuple[str, ...] = ()

    @property
    def report_hash(self) -> str:
        return canonical_hash(self, prefix="task_pattern_validation_report:")


def run_task_pattern_validation(*, tasks_per_domain: int = 10) -> TaskPatternValidationReport:
    cases = build_pattern_validation_cases(per_domain=tasks_per_domain)
    failures: list[str] = []
    references_passed = 0
    candidates_passed = 0
    parity_passed = 0
    pattern_clause_count = 0
    difficulty_clause_count = 0
    task_ids: set[str] = set()
    binding_hashes: set[str] = set()
    pattern_hashes: set[str] = set()
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
        task_ids.add(case.task.task_id)
        if compiled.sample.binding_hash is not None:
            binding_hashes.add(compiled.sample.binding_hash)
        if compiled.sample.pattern_hash is not None:
            pattern_hashes.add(compiled.sample.pattern_hash)
        references_passed += int(compiled.reference_assessment.decision == ReleaseDecision.ACCEPTED)
        clause_kinds = {clause.clause_kind for clause in compiled.quality_contract.clauses}
        pattern_clause_count += int("task_pattern_binding_integrity" in clause_kinds)
        difficulty_clause_count += int("difficulty_profile_integrity" in clause_kinds)
        candidate = PlanGivenContractCandidate(case.registry).generate(
            case.task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )
        workflow_verifier = CandidateWorkflowVerifier(
            case.registry,
            semantic_policy=case.semantic_policy,
        )
        candidate_assessment = CandidateQualityEvaluator(
            semantic_policy=case.semantic_policy,
            workflow_verifier=workflow_verifier,
        ).evaluate(case.task, case.corpus, case.proof_graph, candidate)
        contract_assessment = QualityContractRuntime(
            workflow_verifier,
            verifier_registry=contract_compiler.verifier_registry,
        ).evaluate(
            compiled.quality_contract,
            case.task,
            case.corpus,
            case.proof_graph,
            candidate,
        )
        candidates_passed += int(candidate_assessment.decision == ReleaseDecision.ACCEPTED)
        parity = compare_decisions(candidate_assessment, contract_assessment)
        parity_passed += int(parity.decisions_match)
        if candidate_assessment.decision != ReleaseDecision.ACCEPTED:
            failures.append(f"{case.domain}:{case.task.task_id}:candidate")
        if not parity.decisions_match:
            failures.append(f"{case.domain}:{case.task.task_id}:contract_parity")
    total = len(cases)
    task_counts = dict(Counter(case.domain for case in cases))
    expected_total = tasks_per_domain * 2
    if total != expected_total or task_counts != {
        "legal": tasks_per_domain,
        "science": tasks_per_domain,
    }:
        failures.append("task_distribution")
    if len(task_ids) != total:
        failures.append("task_identity_collision")
    if len(binding_hashes) != total:
        failures.append("binding_identity_collision")
    return TaskPatternValidationReport(
        validation_id=canonical_hash(
            {
                "tasks_per_domain": tasks_per_domain,
                "task_ids": sorted(task_ids),
                "binding_hashes": sorted(binding_hashes),
            },
            prefix="task_pattern_validation:",
        ),
        requested_tasks_per_domain=tasks_per_domain,
        task_counts=task_counts,
        compiled_task_count=total,
        reference_pass_rate=references_passed / total,
        clean_candidate_pass_rate=candidates_passed / total,
        contract_decision_parity_rate=parity_passed / total,
        pattern_binding_clause_rate=pattern_clause_count / total,
        difficulty_clause_rate=difficulty_clause_count / total,
        unique_task_count=len(task_ids),
        unique_binding_count=len(binding_hashes),
        pattern_hashes=tuple(sorted(pattern_hashes)),
        status="passed" if not failures else "failed",
        failures=tuple(failures),
    )
