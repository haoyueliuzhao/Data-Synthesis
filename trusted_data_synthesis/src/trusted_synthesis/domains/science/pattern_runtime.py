from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.binding import EvidenceBinding
from trusted_synthesis.core.task.materialization import oracle_selection_contract
from trusted_synthesis.core.task.pattern import (
    PatternBindingValidationReport,
    TaskPatternMaterialization,
    TaskPatternSpec,
)
from trusted_synthesis.domains.science.policy import ScienceSemanticPolicy


class ScienceTaskPatternRuntime:
    runtime_id = "science_task_pattern_runtime.v1"
    runtime_version = "1.0.0"
    domain = "science"
    renderer_ids: tuple[str, ...] = ("science.protocol_effect_comparison.v1",)

    def __init__(self) -> None:
        self._policy = ScienceSemanticPolicy()

    def validate_binding(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
    ) -> PatternBindingValidationReport:
        del pattern, binding
        experiments = evidence_by_role["experiments"]
        comparison = self._policy.compare(experiments[0], experiments[1])
        checks = {
            "all_evidence_valid": all(
                self._policy.validate_evidence(item).passed for item in experiments
            ),
            "protocol_comparable": comparison.comparable,
        }
        issues = [check_id for check_id, passed in checks.items() if not passed]
        issues.extend(comparison.reasons)
        unique_issues = tuple(dict.fromkeys(issues))
        return PatternBindingValidationReport(
            passed=not unique_issues,
            checks=checks,
            issues=unique_issues,
            semantic_alignment_cost=2.0,
        )

    def materialize(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
    ) -> TaskPatternMaterialization:
        del pattern, binding, proof_graph
        left, right = evidence_by_role["experiments"]
        evidence = (left, right)
        return TaskPatternMaterialization(
            instruction=(
                "Determine whether the two experimental results use comparable protocols, then "
                "compare their observed effects while preserving uncertainty in the conclusion."
            ),
            retrieval_scope={
                "aliases": sorted({left.subject.name, right.subject.name}),
                "partial_constraints": {
                    "predicate": left.predicate,
                    "definition_id": left.definition.definition_id,
                },
                "corpus_boundary": bundle.bundle_id,
                "semantic_constraints": {
                    "scope_ids": sorted(
                        {
                            item.scope.scope_id
                            for item in evidence
                            if item.scope is not None and item.scope.scope_id
                        }
                    ),
                    "temporal_labels": sorted(
                        {
                            item.temporal_context.label
                            for item in evidence
                            if item.temporal_context.label
                        }
                    ),
                    "source_authorities": sorted(
                        {item.source.authority.value for item in evidence}
                    ),
                },
            },
            oracle_selection_contract=oracle_selection_contract(evidence),
            metadata={"domain_plugin_id": "science_tasks.v2"},
        )
