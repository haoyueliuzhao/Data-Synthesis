from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.graph.validation import ProofGraphValidator
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.answer_schema import complete_answer_schema
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.core.task.schema import (
    PlanningTrack,
    PublicProgramInput,
    PublicProgramNode,
    PublicProgramSkeleton,
    RetrievalTrack,
    TaskLevel,
    TaskOracleContract,
    TaskPackage,
    TaskPublicSpec,
    TaskRequirement,
    VerifierRequirement,
)
from trusted_synthesis.hashing import canonical_hash


class TaskPackageBuilder:
    """Package a domain-produced binding and program into the universal task contract."""

    def __init__(self, operation_registry: OperationRegistry | None = None) -> None:
        self._proof_validator = ProofGraphValidator()
        self._operation_registry = operation_registry or default_registry()

    def build(
        self,
        *,
        task_domain: str,
        task_type: str,
        level: TaskLevel,
        instruction: str,
        evidence: tuple[EvidenceItem, ...],
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
        program: TaskProgram,
        answer_schema: dict[str, Any],
        retrieval_scope: dict[str, Any],
        retrieval_track: RetrievalTrack = RetrievalTrack.RESOLVED,
        planning_track: PlanningTrack = PlanningTrack.PLAN_GIVEN,
        oracle_selection_contract: dict[str, Any] | None = None,
        source_grounding_requirement: VerifierRequirement = VerifierRequirement.NOT_APPLICABLE,
        allow_structured_claims: bool = False,
        metadata: dict[str, Any] | None = None,
        quality_rubric: dict[str, Any] | None = None,
        identity_context: dict[str, Any] | None = None,
    ) -> TaskPackage:
        if not evidence:
            raise ValueError("task package requires evidence")
        if not task_domain.strip():
            raise ValueError("task package requires an explicit plugin-owned domain")
        evidence_domains = {item.domain for item in evidence}
        if evidence_domains != {task_domain}:
            raise ValueError(
                "task evidence domains must exactly match task_domain; "
                "cross-domain tasks require an explicit future policy"
            )
        evidence_ids = tuple(item.evidence_id for item in evidence)
        graph_report = self._proof_validator.validate(proof_graph, bundle, evidence_ids)
        if not graph_report.passed:
            failures = tuple(check.check_id for check in graph_report.checks if not check.passed)
            raise ValueError(f"proof graph is missing or invalid: {failures}")
        public_answer_schema = complete_answer_schema(
            {
                **answer_schema,
                "allow_claims": allow_structured_claims,
                "additional_result_properties": False,
            }
        )
        task_id = canonical_hash(
            {
                "task_type": task_type,
                "bundle_id": bundle.bundle_id,
                "evidence_ids": evidence_ids,
                "program_hash": program.program_hash,
                "answer_schema": public_answer_schema,
                "identity_context": identity_context or {},
                "schema": "task_package.v6",
            },
            prefix="task:",
        )
        public = TaskPublicSpec(
            task_id=task_id,
            domain=task_domain,
            task_type=task_type,
            level=level,
            instruction=instruction,
            requirements=requirements_for_program(program, self._operation_registry),
            allowed_tools=allowed_tools_for_program(program, self._operation_registry),
            retrieval_track=retrieval_track,
            planning_track=planning_track,
            program_skeleton=(
                public_program_skeleton(program, self._operation_registry, evidence)
                if planning_track == PlanningTrack.PLAN_GIVEN
                else None
            ),
            retrieval_scope=retrieval_scope,
            answer_schema=public_answer_schema,
            metadata={
                "proof_required": True,
                "source_grounding_requirement": source_grounding_requirement.value,
                **(metadata or {}),
            },
        )
        oracle = TaskOracleContract(
            task_id=task_id,
            gold_evidence_ids=evidence_ids,
            task_program=program,
            selection_contract=oracle_selection_contract or {},
            proof_graph_id=proof_graph.graph_id,
            proof_graph_hash=proof_graph.graph_hash,
            quality_rubric=quality_rubric
            or {
                "evidence_coverage": 1.0,
                "operation_replay": True,
                "source_citation": True,
            },
        )
        return TaskPackage(task_id=task_id, public=public, oracle=oracle)


def requirements_for_program(
    program: TaskProgram, registry: OperationRegistry
) -> tuple[TaskRequirement, ...]:
    requirements = [
        TaskRequirement.RETRIEVE_EVIDENCE,
        TaskRequirement.SELECT_EVIDENCE,
        TaskRequirement.CITE_SOURCE,
    ]
    if any(registry.require(node.operator_id).action_type == "calculate" for node in program.nodes):
        requirements.extend((TaskRequirement.CALCULATE, TaskRequirement.VERIFY_RESULT))
    return tuple(requirements)


def allowed_tools_for_program(program: TaskProgram, registry: OperationRegistry) -> tuple[str, ...]:
    tools = ["evidence.search"]
    tools.extend(
        definition.tool_capability
        for node in program.nodes
        if (definition := registry.require(node.operator_id)).tool_capability is not None
    )
    return tuple(dict.fromkeys(tools))


def public_program_skeleton(
    program: TaskProgram,
    registry: OperationRegistry,
    evidence: tuple[EvidenceItem, ...],
) -> PublicProgramSkeleton:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    evidence_roles: dict[str, str] = {}
    nodes = []
    for node in program.nodes:
        inputs = []
        for ref in node.input_refs:
            role_id = ref.ref_id
            if ref.kind == InputRefKind.EVIDENCE:
                role_id = evidence_roles.setdefault(
                    ref.ref_id, f"evidence_role_{len(evidence_roles) + 1}"
                )
            semantic_constraints = {}
            if ref.kind.value == "evidence":
                semantic_constraints = _public_evidence_role_constraints(evidence_by_id[ref.ref_id])
            inputs.append(
                PublicProgramInput(
                    kind=ref.kind,
                    role_id=role_id,
                    selector=ref.selector,
                    semantic_constraints=semantic_constraints,
                )
            )
        definition = registry.require(node.operator_id)
        nodes.append(
            PublicProgramNode(
                public_node_id=node.node_id,
                operator_id=node.operator_id,
                inputs=tuple(inputs),
                parameters=node.parameters,
                output_schema=node.output_schema,
                dependencies=node.dependencies,
                tool_capability=definition.tool_capability,
            )
        )
    return PublicProgramSkeleton(nodes=tuple(nodes), output_node_id=program.output_node_id)


def _public_evidence_role_constraints(evidence: EvidenceItem) -> dict[str, Any]:
    return {
        "subject_id": evidence.subject.subject_id,
        "predicate": evidence.predicate,
        "temporal_label": evidence.temporal_context.label,
        "time_basis": evidence.temporal_context.basis,
        "frequency": evidence.temporal_context.frequency,
        "definition_id": evidence.definition.definition_id,
        "scope_type": evidence.scope.scope_type if evidence.scope is not None else None,
        "scope_id": evidence.scope.scope_id if evidence.scope is not None else None,
        "source_name": evidence.source.name,
        "source_authority": evidence.source.authority.value,
        "epistemic_status": evidence.epistemic_status.value,
    }
