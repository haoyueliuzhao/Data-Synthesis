from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.builder import TaskPackageBuilder
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    make_program,
)
from trusted_synthesis.core.task.schema import RetrievalTrack, TaskLevel, TaskPackage
from trusted_synthesis.domains.legal.operations import legal_operation_registry


class LegalTaskPlugin:
    plugin_id = "legal_tasks.v1"
    task_family_ids = ("legal_rule_application",)

    def __init__(self) -> None:
        self._builder = TaskPackageBuilder(legal_operation_registry())

    @staticmethod
    def operation_registry() -> OperationRegistry:
        return legal_operation_registry()

    def rule_application(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        rules: tuple[EvidenceItem, ...],
        *,
        satisfied_conditions: tuple[str, ...],
        present_exceptions: tuple[str, ...],
        authority_priority: tuple[str, ...],
    ) -> TaskPackage:
        if len(rules) < 2:
            raise ValueError("authority resolution requires at least two rules")
        apply_nodes = tuple(
            OperationNode(
                node_id=f"apply_{index}",
                operator_id="legal_apply_rule",
                input_refs=(ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=rule.evidence_id),),
                parameters={
                    "satisfied_conditions": satisfied_conditions,
                    "present_exceptions": present_exceptions,
                },
                output_schema="structured",
                verifier_id="legal_apply_rule.oracle.v1",
            )
            for index, rule in enumerate(rules, start=1)
        )
        result = OperationNode(
            node_id="result",
            operator_id="legal_resolve_authority",
            input_refs=tuple(
                ProgramInputRef(kind=InputRefKind.OPERATION, ref_id=node.node_id)
                for node in apply_nodes
            ),
            parameters={"authority_priority": authority_priority},
            output_schema="structured",
            verifier_id="legal_resolve_authority.oracle.v1",
            dependencies=tuple(node.node_id for node in apply_nodes),
        )
        program = make_program((*apply_nodes, result), "result")
        return self._builder.build(
            task_domain="legal",
            task_type="legal_rule_application",
            level=TaskLevel.RESEARCH_WORKFLOW,
            instruction=(
                "Apply the effective rules to the stated conditions, check every registered "
                "exception, and resolve any conflict by authority before stating the legal effect."
            ),
            evidence=rules,
            bundle=bundle,
            proof_graph=proof_graph,
            program=program,
            retrieval_track=RetrievalTrack.RESOLVED,
            retrieval_scope=_retrieval_scope(rules),
            oracle_selection_contract=_oracle_selection_contract(rules),
            answer_schema={
                "type": "legal_rule_decision",
                "required_fields": [
                    "applicable",
                    "selected_ref",
                    "authority",
                    "legal_effect",
                ],
            },
            metadata={"domain_plugin_id": self.plugin_id},
        )


def _retrieval_scope(evidence: tuple[EvidenceItem, ...]) -> dict[str, object]:
    return {
        "subject_ids": sorted({item.subject.subject_id for item in evidence}),
        "predicates": sorted({item.predicate for item in evidence}),
        "temporal_labels": sorted(
            {item.temporal_context.label for item in evidence if item.temporal_context.label}
        ),
        "source_authorities": sorted({item.source.authority.value for item in evidence}),
        "semantic_constraints": {
            "definition_ids": sorted(
                {
                    item.definition.definition_id
                    for item in evidence
                    if item.definition.definition_id
                }
            ),
            "scope_ids": sorted(
                {
                    item.scope.scope_id
                    for item in evidence
                    if item.scope is not None and item.scope.scope_id
                }
            ),
        },
    }


def _oracle_selection_contract(evidence: tuple[EvidenceItem, ...]) -> dict[str, object]:
    return {
        "evidence_version_ids": sorted({item.evidence_version_id for item in evidence}),
        "source_ids": sorted({item.source.source_id for item in evidence}),
        "required_build_ids": {
            key: sorted(
                {
                    value
                    for item in evidence
                    if (value := item.provenance.build_ids.get(key)) is not None
                }
            )
            for key in sorted({key for item in evidence for key in item.provenance.build_ids})
        },
    }
