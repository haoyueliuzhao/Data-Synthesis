from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.graph.validation import ProofGraphValidator
from trusted_synthesis.core.task.program import TaskProgram
from trusted_synthesis.core.task.schema import (
    RetrievalTrack,
    TaskLevel,
    TaskOracleContract,
    TaskPackage,
    TaskPublicSpec,
    TaskRequirement,
)
from trusted_synthesis.hashing import canonical_hash


class TaskPackageBuilder:
    """Package a domain-produced binding and program into the universal task contract."""

    def __init__(self) -> None:
        self._proof_validator = ProofGraphValidator()

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
        allow_structured_claims: bool = False,
        metadata: dict[str, Any] | None = None,
        quality_rubric: dict[str, Any] | None = None,
    ) -> TaskPackage:
        if not evidence:
            raise ValueError("task package requires evidence")
        if not task_domain.strip():
            raise ValueError("task package requires an explicit plugin-owned domain")
        evidence_ids = tuple(item.evidence_id for item in evidence)
        graph_report = self._proof_validator.validate(proof_graph, bundle, evidence_ids)
        if not graph_report.passed:
            failures = tuple(check.check_id for check in graph_report.checks if not check.passed)
            raise ValueError(f"proof graph is missing or invalid: {failures}")
        task_id = canonical_hash(
            {
                "task_type": task_type,
                "bundle_id": bundle.bundle_id,
                "evidence_ids": evidence_ids,
                "program_hash": program.program_hash,
                "schema": "task_package.v3",
            },
            prefix="task:",
        )
        public = TaskPublicSpec(
            task_id=task_id,
            domain=task_domain,
            task_type=task_type,
            level=level,
            instruction=instruction,
            requirements=requirements_for_program(program),
            allowed_tools=allowed_tools_for_program(program),
            retrieval_track=retrieval_track,
            retrieval_scope=retrieval_scope,
            answer_schema={
                **answer_schema,
                "allow_claims": allow_structured_claims,
                "additional_result_properties": False,
            },
            metadata={"bundle_id": bundle.bundle_id, "proof_required": True, **(metadata or {})},
        )
        oracle = TaskOracleContract(
            task_id=task_id,
            gold_evidence_ids=evidence_ids,
            task_program=program,
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


def requirements_for_program(program: TaskProgram) -> tuple[TaskRequirement, ...]:
    requirements = [
        TaskRequirement.RETRIEVE_EVIDENCE,
        TaskRequirement.SELECT_EVIDENCE,
        TaskRequirement.CITE_SOURCE,
    ]
    if any(node.operator_id != "lookup" for node in program.nodes):
        requirements.extend((TaskRequirement.CALCULATE, TaskRequirement.VERIFY_RESULT))
    return tuple(requirements)


def allowed_tools_for_program(program: TaskProgram) -> tuple[str, ...]:
    tools = ["evidence.search"]
    if any(node.operator_id != "lookup" for node in program.nodes):
        tools.append("calculator")
    return tuple(tools)
