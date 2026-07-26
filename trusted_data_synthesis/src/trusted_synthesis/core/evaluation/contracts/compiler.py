from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from trusted_synthesis.core.evaluation.contracts.registry import (
    ClauseVerifierRegistry,
    default_clause_verifier_registry,
)
from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseScope,
    ClauseSeverity,
    ClauseTarget,
    GateAggregation,
    QualityClause,
    QualityContract,
    QualityGateSpec,
    make_quality_clause,
    make_quality_contract,
)
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import DomainQualityClauseProviderProtocol
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.hashing import canonical_hash

QUALITY_CONTRACT_COMPILER_VERSION = "quality_contract_compiler.v1"


@dataclass(frozen=True)
class QualityClauseCompilationContext:
    task: TaskPackage
    bundle: EvidenceBundle
    proof_graph: ProofGraph
    base_clause_ids: dict[str, str]
    evidence_clause_ids: dict[str, tuple[str, ...]]
    program_clause_ids: dict[str, str]


class QualityContractCompiler:
    """Compile a task-local, executable quality contract from structural artifacts."""

    def __init__(
        self,
        operation_registry: OperationRegistry,
        *,
        verifier_registry: ClauseVerifierRegistry | None = None,
        domain_provider: DomainQualityClauseProviderProtocol | None = None,
    ) -> None:
        self._operation_registry = operation_registry
        self._verifier_registry = verifier_registry or default_clause_verifier_registry()
        self._domain_provider = domain_provider

    @property
    def verifier_registry(self) -> ClauseVerifierRegistry:
        return self._verifier_registry

    def compile(
        self,
        task: TaskPackage,
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
    ) -> QualityContract:
        _validate_compile_inputs(task, bundle, proof_graph)
        clauses: list[QualityClause] = []
        gate_members: dict[str, list[str]] = {}
        gate_scopes: dict[str, ClauseScope] = {}
        base_clause_ids: dict[str, str] = {}

        def add(clause: QualityClause, gate_id: str) -> QualityClause:
            verifier = self._verifier_registry.get(clause.verifier_id)
            if verifier is None or verifier.verifier_version != clause.verifier_version:
                raise ValueError(
                    "quality clause verifier is not frozen in the compiler registry: "
                    f"{clause.verifier_id}@{clause.verifier_version}"
                )
            clauses.append(clause)
            gate_members.setdefault(gate_id, []).append(clause.clause_id)
            gate_scopes.setdefault(gate_id, clause.scope)
            if gate_scopes[gate_id] != clause.scope:
                raise ValueError(f"quality gate mixes scopes: {gate_id}")
            return clause

        identity = add(
            _candidate_check_clause(task, "task_identity", "task", task.task_id),
            "workflow_contract",
        )
        base_clause_ids["task_identity"] = identity.clause_id
        for check_id in (
            "candidate_workflow_kind",
            "required_actions_present",
            "step_statuses_succeeded",
            "action_sequence_valid",
        ):
            clause = add(
                _candidate_check_clause(
                    task,
                    check_id,
                    "trajectory",
                    task.task_id,
                    dependencies=(identity.clause_id,),
                ),
                "workflow_contract",
            )
            base_clause_ids[check_id] = clause.clause_id

        for field, expected in (
            ("planning_track", task.public.planning_track.value),
            ("retrieval_track", task.public.retrieval_track.value),
        ):
            clause = add(
                make_quality_clause(
                    task_id=task.task_id,
                    clause_kind=f"{field}_compliance",
                    scope=ClauseScope.UNIVERSAL,
                    severity=ClauseSeverity.FATAL,
                    target=ClauseTarget(target_type="task_public", target_ref=task.task_id),
                    verifier_id="task_track.v1",
                    verifier_version="1.0.0",
                    expected_ref=str(expected),
                    parameters={"field": field, "expected": expected},
                    dependencies=(identity.clause_id,),
                    failure_family="workflow_contract",
                    diagnostic_dimensions=("workflow",),
                ),
                "workflow_contract",
            )
            base_clause_ids[f"{field}_compliance"] = clause.clause_id

        for check_id in ("public_only_generation", "allowed_tool_compliance"):
            clause = add(
                _candidate_check_clause(
                    task,
                    check_id,
                    "public_boundary",
                    task.task_id,
                    dependencies=(identity.clause_id,),
                ),
                "public_boundary_and_tools",
            )
            base_clause_ids[check_id] = clause.clause_id

        evidence_root_ids: list[str] = []
        evidence_clause_ids: dict[str, tuple[str, ...]] = {}
        for evidence_id in task.oracle.gold_evidence_ids:
            present = add(
                make_quality_clause(
                    task_id=task.task_id,
                    clause_kind="gold_evidence_exists",
                    scope=ClauseScope.UNIVERSAL,
                    severity=ClauseSeverity.FATAL,
                    target=ClauseTarget(target_type="evidence", target_ref=evidence_id),
                    verifier_id="evidence_present.v1",
                    verifier_version="1.0.0",
                    expected_ref=evidence_id,
                    dependencies=(identity.clause_id,),
                    failure_family="evidence_integrity",
                    diagnostic_dimensions=("evidence",),
                ),
                "evidence_retrieval_and_selection",
            )
            selected = add(
                make_quality_clause(
                    task_id=task.task_id,
                    clause_kind="gold_evidence_selected",
                    scope=ClauseScope.UNIVERSAL,
                    severity=ClauseSeverity.FATAL,
                    target=ClauseTarget(target_type="evidence", target_ref=evidence_id),
                    verifier_id="evidence_selected.v1",
                    verifier_version="1.0.0",
                    expected_ref=evidence_id,
                    dependencies=(present.clause_id,),
                    failure_family="evidence_selection",
                    diagnostic_dimensions=("evidence", "retrieval"),
                ),
                "evidence_retrieval_and_selection",
            )
            proof = add(
                make_quality_clause(
                    task_id=task.task_id,
                    clause_kind="proof_evidence_node_present",
                    scope=ClauseScope.UNIVERSAL,
                    severity=ClauseSeverity.FATAL,
                    target=ClauseTarget(target_type="proof_node", target_ref=evidence_id),
                    verifier_id="proof_evidence_node.v1",
                    verifier_version="1.0.0",
                    expected_ref=evidence_id,
                    dependencies=(present.clause_id,),
                    failure_family="proof_graph",
                    diagnostic_dimensions=("evidence", "proof"),
                ),
                "proof_and_operation",
            )
            evidence_root_ids.append(selected.clause_id)
            evidence_clause_ids[evidence_id] = (
                present.clause_id,
                selected.clause_id,
                proof.clause_id,
            )

        for check_id in (
            "retrieved_evidence_known",
            "retrieved_evidence_validity",
            "selected_evidence_was_retrieved",
            "evidence_recall",
            "evidence_precision",
        ):
            clause = add(
                _candidate_check_clause(
                    task,
                    check_id,
                    "evidence_set",
                    task.task_id,
                    dependencies=(identity.clause_id,),
                ),
                "evidence_retrieval_and_selection",
            )
            base_clause_ids[check_id] = clause.clause_id

        for check_id in ("selected_evidence_validity", "source_grounding"):
            clause = add(
                _candidate_check_clause(
                    task,
                    check_id,
                    "domain_evidence",
                    task.task_id,
                    scope=ClauseScope.DOMAIN,
                    dependencies=tuple(evidence_root_ids),
                ),
                "domain_evidence_semantics",
            )
            base_clause_ids[check_id] = clause.clause_id

        proof_binding = add(
            _candidate_check_clause(
                task,
                "proof_graph_binding",
                "proof_graph",
                proof_graph.graph_id,
                dependencies=(identity.clause_id,),
            ),
            "proof_and_operation",
        )
        base_clause_ids["proof_graph_binding"] = proof_binding.clause_id
        prior_program_clauses: list[str] = []
        program_clause_ids: dict[str, str] = {}
        for node in task.oracle.task_program.nodes:
            operation = self._operation_registry.validate_node_contract(node)
            evidence_dependencies = tuple(
                evidence_clause_ids[ref.ref_id][1]
                for ref in node.input_refs
                if ref.ref_id in evidence_clause_ids
            )
            operation_dependencies = tuple(
                program_clause_ids[item] for item in node.dependencies
            )
            clause = add(
                make_quality_clause(
                    task_id=task.task_id,
                    clause_kind="program_node_execution",
                    scope=ClauseScope.UNIVERSAL,
                    severity=ClauseSeverity.FATAL,
                    target=ClauseTarget(target_type="program_node", target_ref=node.node_id),
                    verifier_id="program_node_trace.v1",
                    verifier_version="1.0.0",
                    expected_ref=canonical_hash(
                        _operation_contract_identity(operation),
                        prefix="operation_contract:",
                    ),
                    parameters={
                        "operator_id": node.operator_id,
                        "operation_verifier_id": node.verifier_id,
                    },
                    dependencies=(
                        proof_binding.clause_id,
                        *evidence_dependencies,
                        *operation_dependencies,
                    ),
                    failure_family="operation_trace",
                    diagnostic_dimensions=("reasoning", "operation"),
                ),
                "proof_and_operation",
            )
            program_clause_ids[node.node_id] = clause.clause_id
            prior_program_clauses.append(clause.clause_id)

        for check_id in (
            "program_node_alignment",
            "all_calculations_correct",
            "verification_step_binding",
            "operation_correctness",
        ):
            clause = add(
                _candidate_check_clause(
                    task,
                    check_id,
                    "task_program",
                    task.oracle.task_program.program_id,
                    dependencies=(proof_binding.clause_id,),
                ),
                "proof_and_operation",
            )
            base_clause_ids[check_id] = clause.clause_id

        answer_dependencies = tuple(prior_program_clauses)
        for check_id in (
            "answer_schema_validity",
            "answer_correctness",
            "citation_binding",
            "unsupported_claim_detection",
        ):
            clause = add(
                _candidate_check_clause(
                    task,
                    check_id,
                    "answer",
                    task.task_id,
                    dependencies=answer_dependencies,
                ),
                "answer_and_citation",
            )
            base_clause_ids[check_id] = clause.clause_id

        result_clause = add(
            make_quality_clause(
                task_id=task.task_id,
                clause_kind="answer_result_present",
                scope=ClauseScope.UNIVERSAL,
                severity=ClauseSeverity.FATAL,
                target=ClauseTarget(
                    target_type="answer_field", target_ref="result", json_path="result"
                ),
                verifier_id="answer_field.v1",
                verifier_version="1.0.0",
                expected_ref="result",
                dependencies=(base_clause_ids["answer_schema_validity"],),
                failure_family="answer_schema",
                diagnostic_dimensions=("answer",),
            ),
            "answer_and_citation",
        )
        for field in _required_answer_fields(task.public.answer_schema):
            add(
                make_quality_clause(
                    task_id=task.task_id,
                    clause_kind="required_answer_field_present",
                    scope=ClauseScope.UNIVERSAL,
                    severity=ClauseSeverity.FATAL,
                    target=ClauseTarget(
                        target_type="answer_field",
                        target_ref=field,
                        json_path=f"result.{field}",
                    ),
                    verifier_id="answer_field.v1",
                    verifier_version="1.0.0",
                    expected_ref=field,
                    dependencies=(result_clause.clause_id,),
                    failure_family="answer_schema",
                    diagnostic_dimensions=("answer",),
                ),
                "answer_and_citation",
            )
        for evidence_id in task.oracle.gold_evidence_ids:
            add(
                make_quality_clause(
                    task_id=task.task_id,
                    clause_kind="citation_evidence_binding",
                    scope=ClauseScope.UNIVERSAL,
                    severity=ClauseSeverity.FATAL,
                    target=ClauseTarget(target_type="citation", target_ref=evidence_id),
                    verifier_id="citation_evidence.v1",
                    verifier_version="1.0.0",
                    expected_ref=evidence_id,
                    dependencies=(evidence_clause_ids[evidence_id][1],),
                    failure_family="citation_binding",
                    diagnostic_dimensions=("answer", "citation"),
                ),
                "answer_and_citation",
            )

        claim_clause = add(
            _candidate_check_clause(
                task,
                "domain_claim_verification",
                "domain_claims",
                task.task_id,
                scope=ClauseScope.DOMAIN,
                dependencies=(base_clause_ids["answer_schema_validity"],),
            ),
            "domain_claims",
        )
        base_clause_ids["domain_claim_verification"] = claim_clause.clause_id

        context = QualityClauseCompilationContext(
            task=task,
            bundle=bundle,
            proof_graph=proof_graph,
            base_clause_ids=base_clause_ids,
            evidence_clause_ids=evidence_clause_ids,
            program_clause_ids=program_clause_ids,
        )
        if self._domain_provider is not None:
            _add_provider_clauses(
                self._domain_provider.compile_evidence_clauses(context),
                "domain_evidence_semantics",
                add,
            )
            _add_provider_clauses(
                self._domain_provider.compile_selection_clauses(context),
                "domain_evidence_semantics",
                add,
            )
            _add_provider_clauses(
                self._domain_provider.compile_program_clauses(context),
                "domain_program_semantics",
                add,
            )
            _add_provider_clauses(
                self._domain_provider.compile_claim_clauses(context),
                "domain_claims",
                add,
            )

        gates = tuple(
            QualityGateSpec(
                gate_id=gate_id,
                scope=gate_scopes[gate_id],
                clause_ids=tuple(gate_members[gate_id]),
                aggregation=GateAggregation.ALL,
            )
            for gate_id in gate_members
        )
        provider_id = self._domain_provider.provider_id if self._domain_provider else None
        provider_version = (
            self._domain_provider.provider_version if self._domain_provider else None
        )
        return make_quality_contract(
            task_id=task.task_id,
            compiler_version=QUALITY_CONTRACT_COMPILER_VERSION,
            clauses=tuple(clauses),
            gates=gates,
            verifier_manifest_hash=self._verifier_registry.manifest_hash,
            domain_provider_id=provider_id,
            domain_provider_version=provider_version,
        )


def _candidate_check_clause(
    task: TaskPackage,
    check_id: str,
    target_type: str,
    target_ref: str,
    *,
    scope: ClauseScope = ClauseScope.UNIVERSAL,
    dependencies: tuple[str, ...] = (),
) -> QualityClause:
    return make_quality_clause(
        task_id=task.task_id,
        clause_kind=check_id,
        scope=scope,
        severity=ClauseSeverity.FATAL,
        target=ClauseTarget(target_type=target_type, target_ref=target_ref),
        verifier_id="candidate_check.v1",
        verifier_version="1.0.0",
        expected_ref="passed",
        parameters={"check_id": check_id},
        dependencies=dependencies,
        failure_family=check_id,
        diagnostic_dimensions=_diagnostic_dimensions(check_id),
    )


def _diagnostic_dimensions(check_id: str) -> tuple[str, ...]:
    if "evidence" in check_id or check_id == "source_grounding":
        return ("evidence",)
    if "answer" in check_id or "citation" in check_id or "claim" in check_id:
        return ("answer",)
    if "tool" in check_id:
        return ("tool_use",)
    if "operation" in check_id or "calculation" in check_id or "program" in check_id:
        return ("reasoning", "verification")
    return ("workflow",)


def _required_answer_fields(answer_schema: dict) -> tuple[str, ...]:
    fields = answer_schema.get("required_fields") or ()
    return tuple(dict.fromkeys(str(item) for item in fields if str(item)))


def _operation_contract_identity(operation) -> dict[str, object]:
    return {
        "operator_id": operation.operator_id,
        "verifier_id": operation.verifier_id,
        "input_schema": operation.input_schema,
        "output_schema": operation.output_schema,
        "compatibility_policy": operation.compatibility_policy,
        "invariant_checks": operation.invariant_checks,
        "verifier_version": operation.verifier_version,
        "semantic_version": operation.semantic_version,
        "implementation_hash": operation.implementation_hash,
    }


def _validate_compile_inputs(
    task: TaskPackage,
    bundle: EvidenceBundle,
    proof_graph: ProofGraph,
) -> None:
    if proof_graph.graph_id != task.oracle.proof_graph_id:
        raise ValueError("proof graph ID does not match task oracle")
    if proof_graph.graph_hash != task.oracle.proof_graph_hash:
        raise ValueError("proof graph hash does not match task oracle")
    bundle_ids = {item.evidence_id for item in bundle.evidence}
    missing = set(task.oracle.gold_evidence_ids) - bundle_ids
    if missing:
        raise ValueError(f"quality contract bundle is missing gold evidence: {sorted(missing)}")
    graph_missing = [
        item for item in task.oracle.gold_evidence_ids if not proof_graph.contains_evidence(item)
    ]
    if graph_missing:
        raise ValueError(f"quality contract graph is missing gold evidence: {graph_missing}")


def _add_provider_clauses(
    clauses: Iterable[QualityClause],
    gate_id: str,
    add: Callable[[QualityClause, str], QualityClause],
) -> None:
    for clause in clauses:
        if clause.scope != ClauseScope.DOMAIN:
            raise ValueError("domain quality provider emitted a universal clause")
        add(clause, gate_id)
