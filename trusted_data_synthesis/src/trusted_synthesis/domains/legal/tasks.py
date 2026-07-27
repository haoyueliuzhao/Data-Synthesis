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
from trusted_synthesis.domains.legal.patterns import (
    LEGAL_CONDITION_APPLICATION_PATTERN,
    LEGAL_EXCEPTION_APPLICATION_PATTERN,
    LEGAL_RULE_APPLICATION_PATTERN,
    LEGAL_TASK_PATTERNS,
)


class LegalTaskPlugin:
    plugin_id = "legal_tasks.v3"
    task_family_ids = tuple(pattern.task_type for pattern in LEGAL_TASK_PATTERNS)

    def __init__(self) -> None:
        self._patterns = {pattern.task_type: pattern for pattern in LEGAL_TASK_PATTERNS}
        self._compiler = TaskPatternCompiler(
            legal_operation_registry(),
            LegalTaskPatternRuntime(),
        )

    @staticmethod
    def operation_registry() -> OperationRegistry:
        return legal_operation_registry()

    @property
    def pattern_manifest(self) -> tuple[TaskPatternSpec, ...]:
        return tuple(self._patterns[key] for key in sorted(self._patterns))

    def condition_application(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        rule: EvidenceItem,
        *,
        satisfied_conditions: tuple[str, ...],
    ) -> TaskPackage:
        return self._single_rule_application(
            LEGAL_CONDITION_APPLICATION_PATTERN,
            proof_graph,
            bundle,
            rule,
            satisfied_conditions=satisfied_conditions,
            present_exceptions=(),
        )

    def exception_application(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        rule: EvidenceItem,
        *,
        satisfied_conditions: tuple[str, ...],
        present_exceptions: tuple[str, ...],
    ) -> TaskPackage:
        return self._single_rule_application(
            LEGAL_EXCEPTION_APPLICATION_PATTERN,
            proof_graph,
            bundle,
            rule,
            satisfied_conditions=satisfied_conditions,
            present_exceptions=present_exceptions,
        )

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
        pattern = LEGAL_RULE_APPLICATION_PATTERN
        binding = make_evidence_binding(
            pattern_id=pattern.pattern_id,
            pattern_version=pattern.pattern_version,
            pattern_hash=pattern.pattern_hash,
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
            pattern,
            binding,
            bundle,
            proof_graph,
        ).task

    def _single_rule_application(
        self,
        pattern: TaskPatternSpec,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        rule: EvidenceItem,
        *,
        satisfied_conditions: tuple[str, ...],
        present_exceptions: tuple[str, ...],
    ) -> TaskPackage:
        binding = make_evidence_binding(
            pattern_id=pattern.pattern_id,
            pattern_version=pattern.pattern_version,
            pattern_hash=pattern.pattern_hash,
            role_bindings={"rule": (rule.evidence_id,)},
            source_graph_id=proof_graph.graph_id,
            domain_snapshot_id=proof_graph.source_build_id,
            node_parameters={
                "result": {
                    "satisfied_conditions": satisfied_conditions,
                    "present_exceptions": present_exceptions,
                }
            },
        )
        return self._compiler.compile(pattern, binding, bundle, proof_graph).task
