from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import TaskPatternCompiler
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.domains.legal.operations import legal_operation_registry
from trusted_synthesis.domains.legal.pattern_runtime import LegalTaskPatternRuntime
from trusted_synthesis.domains.legal.patterns import LEGAL_RULE_APPLICATION_PATTERN


class LegalTaskPlugin:
    plugin_id = "legal_tasks.v2"
    task_family_ids = ("legal_rule_application",)

    def __init__(self) -> None:
        self._pattern = LEGAL_RULE_APPLICATION_PATTERN
        self._compiler = TaskPatternCompiler(
            legal_operation_registry(),
            LegalTaskPatternRuntime(),
        )

    @staticmethod
    def operation_registry() -> OperationRegistry:
        return legal_operation_registry()

    @property
    def pattern_manifest(self) -> tuple[TaskPatternSpec, ...]:
        return (self._pattern,)

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
        binding = make_evidence_binding(
            pattern_id=self._pattern.pattern_id,
            pattern_version=self._pattern.pattern_version,
            pattern_hash=self._pattern.pattern_hash,
            role_bindings={"rules": tuple(item.evidence_id for item in rules)},
            source_graph_id=proof_graph.graph_id,
            domain_snapshot_id=proof_graph.source_build_id,
            node_parameters={
                "apply": {
                    "satisfied_conditions": satisfied_conditions,
                    "present_exceptions": present_exceptions,
                },
                "result": {"authority_priority": authority_priority},
            },
        )
        return self._compiler.compile(
            self._pattern,
            binding,
            bundle,
            proof_graph,
        ).task
