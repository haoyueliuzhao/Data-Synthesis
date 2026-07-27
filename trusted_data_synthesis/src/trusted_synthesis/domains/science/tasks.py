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
from trusted_synthesis.domains.science.patterns import (
    SCIENCE_DESCRIPTIVE_SYNTHESIS_PATTERN,
    SCIENCE_PROTOCOL_COMPARISON_PATTERN,
    SCIENCE_PROTOCOL_COMPATIBILITY_PATTERN,
    SCIENCE_TASK_PATTERNS,
)


class ScienceTaskPlugin:
    plugin_id = "science_tasks.v3"
    task_family_ids = tuple(pattern.task_type for pattern in SCIENCE_TASK_PATTERNS)

    def __init__(self) -> None:
        self._patterns = {pattern.task_type: pattern for pattern in SCIENCE_TASK_PATTERNS}
        self._compiler = TaskPatternCompiler(
            science_operation_registry(),
            ScienceTaskPatternRuntime(),
        )

    @staticmethod
    def operation_registry() -> OperationRegistry:
        return science_operation_registry()

    @property
    def pattern_manifest(self) -> tuple[TaskPatternSpec, ...]:
        return tuple(self._patterns[key] for key in sorted(self._patterns))

    def check_protocol_compatibility(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        left: EvidenceItem,
        right: EvidenceItem,
    ) -> TaskPackage:
        return self._compile(
            SCIENCE_PROTOCOL_COMPATIBILITY_PATTERN,
            proof_graph,
            bundle,
            (left, right),
        )

    def compare_experiments(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        left: EvidenceItem,
        right: EvidenceItem,
    ) -> TaskPackage:
        return self._compile(
            SCIENCE_PROTOCOL_COMPARISON_PATTERN,
            proof_graph,
            bundle,
            (left, right),
        )

    def synthesize_experiments(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        experiments: tuple[EvidenceItem, ...],
    ) -> TaskPackage:
        return self._compile(
            SCIENCE_DESCRIPTIVE_SYNTHESIS_PATTERN,
            proof_graph,
            bundle,
            experiments,
        )

    def _compile(
        self,
        pattern: TaskPatternSpec,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        experiments: tuple[EvidenceItem, ...],
    ) -> TaskPackage:
        binding = make_evidence_binding(
            pattern_id=pattern.pattern_id,
            pattern_version=pattern.pattern_version,
            pattern_hash=pattern.pattern_hash,
            role_bindings={"experiments": tuple(item.evidence_id for item in experiments)},
            source_graph_id=proof_graph.graph_id,
            domain_snapshot_id=proof_graph.source_build_id,
        )
        return self._compiler.compile(
            pattern,
            binding,
            bundle,
            proof_graph,
        ).task
