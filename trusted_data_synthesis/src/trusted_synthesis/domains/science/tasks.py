from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import TaskPatternCompiler
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.domains.science.operations import science_operation_registry
from trusted_synthesis.domains.science.pattern_runtime import ScienceTaskPatternRuntime
from trusted_synthesis.domains.science.patterns import SCIENCE_PROTOCOL_COMPARISON_PATTERN


class ScienceTaskPlugin:
    plugin_id = "science_tasks.v2"
    task_family_ids = ("science_protocol_effect_comparison",)

    def __init__(self) -> None:
        self._pattern = SCIENCE_PROTOCOL_COMPARISON_PATTERN
        self._compiler = TaskPatternCompiler(
            science_operation_registry(),
            ScienceTaskPatternRuntime(),
        )

    @staticmethod
    def operation_registry() -> OperationRegistry:
        return science_operation_registry()

    @property
    def pattern_manifest(self) -> tuple[TaskPatternSpec, ...]:
        return (self._pattern,)

    def compare_experiments(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        left: EvidenceItem,
        right: EvidenceItem,
    ) -> TaskPackage:
        binding = make_evidence_binding(
            pattern_id=self._pattern.pattern_id,
            pattern_version=self._pattern.pattern_version,
            pattern_hash=self._pattern.pattern_hash,
            role_bindings={"experiments": (left.evidence_id, right.evidence_id)},
            source_graph_id=proof_graph.graph_id,
            domain_snapshot_id=proof_graph.source_build_id,
        )
        return self._compiler.compile(
            self._pattern,
            binding,
            bundle,
            proof_graph,
        ).task
