from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evaluation.contracts.observation import build_observation_index
from trusted_synthesis.core.evaluation.contracts.registry import (
    ClauseVerificationContext,
    ClauseVerifierRegistry,
    default_clause_verifier_registry,
)
from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseResult,
    ClauseSeverity,
    ContractQualityAssessment,
    DecisionParityReport,
    GateAggregation,
    QualityContract,
    QualityGateResult,
)
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash

QUALITY_CONTRACT_RUNTIME_VERSION = "quality_contract_runtime.v1"


class QualityContractRuntime:
    """Execute every compiled clause and reject missing verifiers or blocked clauses."""

    def __init__(
        self,
        workflow_verifier: CandidateWorkflowVerifier,
        *,
        verifier_registry: ClauseVerifierRegistry | None = None,
    ) -> None:
        self._workflow_verifier = workflow_verifier
        self._verifier_registry = verifier_registry or default_clause_verifier_registry()

    def evaluate(
        self,
        contract: QualityContract,
        task: TaskPackage,
        corpus: EvidenceCorpus,
        proof_graph: ProofGraph,
        trajectory: Trajectory,
    ) -> ContractQualityAssessment:
        QualityContract.model_validate(contract.model_dump(mode="json", exclude_none=True))
        if contract.task_id != task.task_id:
            raise ValueError("quality contract does not belong to the task")
        if contract.verifier_manifest_hash != self._verifier_registry.manifest_hash:
            raise ValueError("quality contract verifier manifest is not available in this runtime")
        report = self._workflow_verifier.verify(task, corpus, proof_graph, trajectory)
        observations = build_observation_index(report, trajectory)
        context = ClauseVerificationContext(
            task=task,
            corpus=corpus,
            proof_graph=proof_graph,
            trajectory=trajectory,
            report=report,
            observations=observations,
        )
        results: list[ClauseResult] = []
        by_id: dict[str, ClauseResult] = {}
        for clause in contract.clauses:
            blocked = tuple(
                dependency
                for dependency in clause.dependencies
                if dependency not in by_id or not by_id[dependency].passed
            )
            if blocked:
                result = ClauseResult(
                    clause_id=clause.clause_id,
                    executed=False,
                    passed=False,
                    failure_code="dependency_failed",
                    location_type=clause.target.target_type,
                    location_ref=clause.target.target_ref,
                    details=blocked,
                )
            else:
                verifier = self._verifier_registry.get(clause.verifier_id)
                if verifier is None or verifier.verifier_version != clause.verifier_version:
                    result = ClauseResult(
                        clause_id=clause.clause_id,
                        executed=False,
                        passed=False,
                        failure_code="verifier_unavailable",
                        location_type=clause.target.target_type,
                        location_ref=clause.target.target_ref,
                        details=(f"{clause.verifier_id}@{clause.verifier_version}",),
                    )
                else:
                    try:
                        outcome = verifier.verify(clause, context)
                        result = ClauseResult(
                            clause_id=clause.clause_id,
                            executed=True,
                            passed=outcome.passed,
                            observed_digest=_digest(outcome.observed),
                            expected_digest=_digest(outcome.expected),
                            failure_code=outcome.failure_code,
                            location_type=clause.target.target_type,
                            location_ref=clause.target.target_ref,
                            details=outcome.details,
                        )
                    except Exception as exc:  # fail closed at the contract boundary
                        result = ClauseResult(
                            clause_id=clause.clause_id,
                            executed=False,
                            passed=False,
                            failure_code="verifier_execution_error",
                            location_type=clause.target.target_type,
                            location_ref=clause.target.target_ref,
                            details=(type(exc).__name__, str(exc)),
                        )
            results.append(result)
            by_id[result.clause_id] = result

        gates = tuple(_aggregate_gate(gate, by_id) for gate in contract.gates)
        failed_ids = tuple(item.clause_id for item in results if not item.passed)
        unexecuted_ids = tuple(item.clause_id for item in results if not item.executed)
        root_ids = tuple(
            clause.clause_id
            for clause in contract.clauses
            if not by_id[clause.clause_id].passed
            and not any(not by_id[item].passed for item in clause.dependencies)
        )
        clauses_by_id = {item.clause_id: item for item in contract.clauses}
        fatal_gate_ids = tuple(
            gate.gate_id
            for gate in gates
            if not gate.passed
            and any(
                clauses_by_id[item].severity == ClauseSeverity.FATAL
                for item in gate.failed_clause_ids
            )
        )
        quarantine_failures = any(
            not result.passed
            and clauses_by_id[result.clause_id].severity == ClauseSeverity.QUARANTINE
            for result in results
        )
        decision = (
            ReleaseDecision.REJECTED
            if fatal_gate_ids
            else ReleaseDecision.QUARANTINED
            if quarantine_failures
            else ReleaseDecision.ACCEPTED
        )
        identity = {
            "task_id": task.task_id,
            "trajectory_id": trajectory.trajectory_id,
            "contract_hash": contract.contract_hash,
            "runtime_version": QUALITY_CONTRACT_RUNTIME_VERSION,
        }
        return ContractQualityAssessment(
            assessment_id=canonical_hash(identity, prefix="contract_assessment:"),
            task_id=task.task_id,
            trajectory_id=trajectory.trajectory_id,
            quality_contract_id=contract.contract_id,
            quality_contract_hash=contract.contract_hash,
            clause_results=tuple(results),
            gate_results=gates,
            decision=decision,
            failed_clause_ids=failed_ids,
            unexecuted_clause_ids=unexecuted_ids,
            root_failure_clause_ids=root_ids,
            fatal_failure_gate_ids=fatal_gate_ids,
            runtime_version=QUALITY_CONTRACT_RUNTIME_VERSION,
        )


def compare_decisions(
    legacy: QualityAssessment,
    contract: ContractQualityAssessment,
) -> DecisionParityReport:
    if (legacy.task_id, legacy.trajectory_id) != (contract.task_id, contract.trajectory_id):
        raise ValueError("cannot compare assessments for different task trajectories")
    identity = {
        "legacy_assessment_id": legacy.assessment_id,
        "contract_assessment_id": contract.assessment_id,
    }
    return DecisionParityReport(
        parity_id=canonical_hash(identity, prefix="decision_parity:"),
        task_id=legacy.task_id,
        trajectory_id=legacy.trajectory_id,
        legacy_assessment_id=legacy.assessment_id,
        contract_assessment_id=contract.assessment_id,
        legacy_decision=legacy.decision,
        contract_decision=contract.decision,
        decisions_match=legacy.decision == contract.decision,
    )


def _aggregate_gate(gate, results: dict[str, ClauseResult]) -> QualityGateResult:
    items = tuple(results[item] for item in gate.clause_ids)
    passed_count = sum(item.passed for item in items)
    if gate.aggregation == GateAggregation.ALL:
        passed = passed_count == len(items)
    elif gate.aggregation == GateAggregation.ANY:
        passed = passed_count > 0
    else:
        assert gate.threshold is not None
        passed = passed_count / len(items) >= gate.threshold
    return QualityGateResult(
        gate_id=gate.gate_id,
        scope=gate.scope,
        passed=passed,
        passed_clause_count=passed_count,
        clause_count=len(items),
        failed_clause_ids=tuple(item.clause_id for item in items if not item.passed),
    )


def _digest(value: Any) -> str | None:
    return None if value is None else canonical_hash(value, prefix="observation:")
