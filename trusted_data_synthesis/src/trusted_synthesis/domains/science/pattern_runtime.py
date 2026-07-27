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
    runtime_id = "science_task_pattern_runtime.v3"
    runtime_version = "3.0.0"
    domain = "science"
    renderer_ids: tuple[str, ...] = (
        "science.protocol_compatibility.v1",
        "science.protocol_effect_comparison.v1",
        "science.descriptive_effect_synthesis.v1",
    )

    def __init__(self) -> None:
        self._policy = ScienceSemanticPolicy()

    def validate_binding(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
    ) -> PatternBindingValidationReport:
        del binding
        experiments = evidence_by_role["experiments"]
        checks = {
            "all_evidence_valid": all(
                self._policy.validate_evidence(item).passed for item in experiments
            ),
        }
        issues: list[str] = []
        if pattern.task_type == "science_protocol_compatibility":
            first = experiments[0]
            checks["same_metric_definition"] = all(
                item.predicate == first.predicate
                and item.definition.definition_id == first.definition.definition_id
                and item.scope == first.scope
                for item in experiments[1:]
            )
        else:
            comparisons = tuple(
                self._policy.compare(experiments[0], item) for item in experiments[1:]
            )
            checks["protocol_comparable"] = all(item.comparable for item in comparisons)
            issues.extend(reason for item in comparisons for reason in item.reasons)
        issues.extend(check_id for check_id, passed in checks.items() if not passed)
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
        del binding, proof_graph
        evidence = evidence_by_role["experiments"]
        left, right = evidence[:2]
        if pattern.task_type == "science_protocol_compatibility":
            instruction = (
                "Determine whether the two experimental results use compatible metrics, "
                "datasets, methods, and protocols. Report every protocol field that differs."
            )
        elif pattern.task_type == "science_protocol_effect_comparison":
            instruction = (
                "Determine whether the two experimental results use comparable protocols, then "
                "compare their observed effects while preserving uncertainty in the conclusion."
            )
        elif pattern.task_type == "science_descriptive_effect_synthesis":
            instruction = (
                "Using all protocol-compatible studies, compute the sample-size-weighted "
                "observed effect and report the full uncertainty envelope. Treat this as a "
                "descriptive synthesis, not a causal estimate or formal meta-analysis."
            )
        else:
            raise ValueError(f"unsupported science task pattern: {pattern.task_type}")
        return TaskPatternMaterialization(
            instruction=instruction,
            retrieval_scope={
                "aliases": sorted({item.subject.name for item in evidence}),
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
            metadata={
                "domain_plugin_id": "science_tasks.v3",
                "agent_contract_guidance": _science_agent_contract_guidance(
                    pattern.task_type
                ),
            },
        )


def _science_agent_contract_guidance(task_type: str) -> dict[str, object]:
    guidance: dict[str, object] = {
        "science_align_protocol": {
            "exact_result_fields": ("comparable", "mismatches"),
            "mismatch_vocabulary": ("metric", "unit", "dataset", "method", "protocol"),
            "field_rules": {
                "mismatches": (
                    "list only differing top-level registered field names in registry order; "
                    "never emit nested paths such as protocol.seed_policy"
                ),
                "comparable": "true only when mismatches is empty",
            },
        },
        "general_rules": (
            "All numeric strings are machine decimals without units or prose.",
            "All reference fields copy exact raw evidence IDs.",
            "Registered conclusion values are enums, not natural-language summaries.",
        ),
    }
    if task_type == "science_protocol_effect_comparison":
        guidance["science_compare_effect"] = {
            "exact_result_fields": (
                "higher_ref",
                "difference",
                "uncertainty_intervals_overlap",
                "qualified_conclusion",
            ),
            "qualified_conclusion_enum": (
                "observed_difference_with_overlapping_uncertainty",
                "observed_difference_with_separated_uncertainty",
            ),
            "field_rules": {
                "higher_ref": "exact raw evidence_id with the larger observed value",
                "difference": "absolute unrounded plain decimal string",
            },
        }
    if task_type == "science_descriptive_effect_synthesis":
        guidance["science_descriptive_synthesis"] = {
            "exact_result_fields": (
                "weighted_value",
                "total_sample_size",
                "uncertainty_lower",
                "uncertainty_upper",
                "qualified_conclusion",
            ),
            "qualified_conclusion_enum": (
                "descriptive_sample_size_weighted_summary_not_meta_analysis",
            ),
        }
    return guidance
