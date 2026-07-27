from __future__ import annotations

import json

import pytest

from trusted_synthesis.core.evaluation.contracts import (
    ClauseScope,
    ClauseSeverity,
    QualityClauseCompilationContext,
    QualityContractCompiler,
    QualityContractRuntime,
    QualityGateSpec,
    default_clause_verifier_registry,
    make_quality_clause,
)
from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseTarget,
    make_quality_contract,
)
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.task.schema import PlanningTrack
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.experiments.cross_domain_contract_suite.candidate import (
    PlanGivenContractCandidate,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_contract_cases,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.mutations import (
    generate_contract_mutations,
)
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime


class _UnknownVerifierProvider:
    provider_id = "unknown_verifier_provider.v1"
    provider_version = "1.0.0"

    def compile_evidence_clauses(self, context: QualityClauseCompilationContext) -> tuple:
        evidence_id = context.task.oracle.gold_evidence_ids[0]
        return (
            make_quality_clause(
                task_id=context.task.task_id,
                clause_kind="unavailable_domain_verifier",
                scope=ClauseScope.DOMAIN,
                severity=ClauseSeverity.FATAL,
                target=ClauseTarget(target_type="evidence", target_ref=evidence_id),
                verifier_id="not_registered.v1",
                verifier_version="1.0.0",
                dependencies=(context.evidence_clause_ids[evidence_id][1],),
                failure_family="registry_fail_closed",
            ),
        )

    def compile_program_clauses(self, context: QualityClauseCompilationContext) -> tuple:
        return ()

    def compile_claim_clauses(self, context: QualityClauseCompilationContext) -> tuple:
        return ()

    def compile_selection_clauses(self, context: QualityClauseCompilationContext) -> tuple:
        return ()


def test_contract_is_task_local_and_every_evidence_and_program_node_is_locatable() -> None:
    contracts = []
    for case in build_contract_cases():
        contract = QualityContractCompiler(
            case.registry,
            domain_provider=case.quality_clause_provider,
        ).compile(case.task, case.bundle, case.proof_graph)
        contracts.append(contract)
        evidence_targets = {
            clause.target.target_ref
            for clause in contract.clauses
            if clause.target.target_type in {"evidence", "proof_node"}
        }
        program_targets = {
            clause.target.target_ref
            for clause in contract.clauses
            if clause.target.target_type == "program_node"
        }
        assert set(case.task.oracle.gold_evidence_ids).issubset(evidence_targets)
        assert {node.node_id for node in case.task.oracle.task_program.nodes}.issubset(
            program_targets
        )
        assert contract.domain_provider_id == case.quality_clause_provider.provider_id
        assert contract.domain_provider_version == case.quality_clause_provider.provider_version
    assert len({len(item.clauses) for item in contracts}) == 2
    assert len({item.contract_hash for item in contracts}) == 2


def test_planning_tracks_compile_different_executable_contracts() -> None:
    case = build_contract_cases()[0]
    compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    given = compiler.compile(case.task, case.bundle, case.proof_graph)
    hidden_public = case.task.public.model_copy(
        update={"planning_track": PlanningTrack.PLAN_HIDDEN, "program_skeleton": None}
    )
    hidden_task = case.task.model_copy(update={"public": hidden_public})
    hidden = compiler.compile(hidden_task, case.bundle, case.proof_graph)

    assert given.contract_hash != hidden.contract_hash
    given_clause = next(
        item for item in given.clauses if item.clause_kind == "planning_track_compliance"
    )
    hidden_clause = next(
        item for item in hidden.clauses if item.clause_kind == "planning_track_compliance"
    )
    assert given_clause.expected_ref == "plan_given"
    assert hidden_clause.expected_ref == "plan_hidden"


def test_contract_runtime_matches_legacy_for_clean_and_mutated_candidates() -> None:
    for case in build_contract_cases():
        compiler = QualityContractCompiler(
            case.registry,
            domain_provider=case.quality_clause_provider,
        )
        contract = compiler.compile(case.task, case.bundle, case.proof_graph)
        verifier = CandidateWorkflowVerifier(
            case.registry,
            semantic_policy=case.semantic_policy,
        )
        runtime = QualityContractRuntime(
            verifier,
            verifier_registry=compiler.verifier_registry,
        )
        legacy = CandidateQualityEvaluator(
            semantic_policy=case.semantic_policy,
            workflow_verifier=verifier,
        )
        candidate = PlanGivenContractCandidate(case.registry).generate(
            case.task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )
        trajectories = (
            candidate,
            *(item for _, item in generate_contract_mutations(candidate, case.corpus.evidence)),
        )
        for trajectory in trajectories:
            legacy_result = legacy.evaluate(case.task, case.corpus, case.proof_graph, trajectory)
            contract_result = runtime.evaluate(
                contract, case.task, case.corpus, case.proof_graph, trajectory
            )
            assert contract_result.decision == legacy_result.decision


def test_unknown_clause_verifier_fails_closed() -> None:
    case = build_contract_cases()[0]
    compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    contract = compiler.compile(case.task, case.bundle, case.proof_graph)
    replaced = contract.clauses[-1]
    unknown = make_quality_clause(
        task_id=case.task.task_id,
        clause_kind="unknown_verifier_probe",
        scope=ClauseScope.DOMAIN,
        severity=ClauseSeverity.FATAL,
        target=ClauseTarget(target_type="probe", target_ref=case.task.task_id),
        verifier_id="not_registered.v1",
        verifier_version="1.0.0",
        dependencies=replaced.dependencies,
        failure_family="registry_fail_closed",
    )
    gates = tuple(
        QualityGateSpec(
            gate_id=gate.gate_id,
            scope=gate.scope,
            clause_ids=tuple(
                unknown.clause_id if item == replaced.clause_id else item
                for item in gate.clause_ids
            ),
            aggregation=gate.aggregation,
            threshold=gate.threshold,
        )
        for gate in contract.gates
    )
    modified = make_quality_contract(
        task_id=contract.task_id,
        compiler_version=contract.compiler_version,
        clauses=(*contract.clauses[:-1], unknown),
        gates=gates,
        verifier_manifest_hash=contract.verifier_manifest_hash,
        domain_provider_id=contract.domain_provider_id,
        domain_provider_version=contract.domain_provider_version,
    )
    verifier = CandidateWorkflowVerifier(case.registry, semantic_policy=case.semantic_policy)
    candidate = PlanGivenContractCandidate(case.registry).generate(
        case.task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    result = QualityContractRuntime(verifier).evaluate(
        modified, case.task, case.corpus, case.proof_graph, candidate
    )

    assert result.decision == ReleaseDecision.REJECTED
    failed = next(item for item in result.clause_results if item.clause_id == unknown.clause_id)
    assert not failed.executed
    assert failed.failure_code == "verifier_unavailable"
    assert unknown.clause_id in result.root_failure_clause_ids


def test_contract_compiler_rejects_a_provider_with_an_unfrozen_verifier() -> None:
    case = build_contract_cases()[0]

    with pytest.raises(ValueError, match="not frozen in the compiler registry"):
        QualityContractCompiler(
            case.registry,
            domain_provider=_UnknownVerifierProvider(),
        ).compile(case.task, case.bundle, case.proof_graph)


def test_contract_hash_tampering_is_rejected() -> None:
    case = build_contract_cases()[0]
    contract = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    ).compile(case.task, case.bundle, case.proof_graph)
    payload = contract.model_dump(mode="json")
    payload["contract_hash"] = "quality_contract_hash:tampered"

    with pytest.raises(ValueError, match="identity or hash"):
        type(contract).model_validate(payload)

    assert json.dumps(contract.model_dump(mode="json"))
    assert default_clause_verifier_registry().manifest_hash == contract.verifier_manifest_hash
