from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.builder import TaskPackageBuilder
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    make_program,
)
from trusted_synthesis.core.task.schema import RetrievalTrack, TaskLevel, TaskPackage


class ScienceTaskPlugin:
    plugin_id = "science_tasks.v1"

    def __init__(self) -> None:
        self._builder = TaskPackageBuilder()

    def compare_experiments(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        left: EvidenceItem,
        right: EvidenceItem,
    ) -> TaskPackage:
        evidence = (left, right)
        alignment = OperationNode(
            node_id="align_protocol",
            operator_id="science_align_protocol",
            input_refs=tuple(
                ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=item.evidence_id)
                for item in evidence
            ),
            output_schema="structured",
            verifier_id="science_align_protocol.oracle.v1",
        )
        result = OperationNode(
            node_id="result",
            operator_id="science_compare_effect",
            input_refs=(
                ProgramInputRef(kind=InputRefKind.OPERATION, ref_id=alignment.node_id),
                ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=left.evidence_id),
                ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=right.evidence_id),
            ),
            output_schema="structured",
            verifier_id="science_compare_effect.oracle.v1",
            dependencies=(alignment.node_id,),
        )
        program = make_program((alignment, result), "result")
        return self._builder.build(
            task_domain="science",
            task_type="science_protocol_effect_comparison",
            level=TaskLevel.RESEARCH_WORKFLOW,
            instruction=(
                "Determine whether the two experimental results use comparable protocols, then "
                "compare their observed effects while preserving uncertainty in the conclusion."
            ),
            evidence=evidence,
            bundle=bundle,
            proof_graph=proof_graph,
            program=program,
            retrieval_track=RetrievalTrack.SEMI_OPEN,
            retrieval_scope={
                "aliases": sorted({left.subject.name, right.subject.name}),
                "partial_constraints": {
                    "predicate": left.predicate,
                    "definition_id": left.definition.definition_id,
                },
                "corpus_boundary": bundle.bundle_id,
            },
            answer_schema={
                "type": "science_effect_comparison",
                "required_fields": [
                    "higher_ref",
                    "difference",
                    "uncertainty_intervals_overlap",
                    "qualified_conclusion",
                ],
            },
            metadata={"domain_plugin_id": self.plugin_id},
        )
