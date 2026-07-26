from __future__ import annotations

from trusted_synthesis.core.evidence.payloads import RuleStatement
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.binding import EvidenceBinding
from trusted_synthesis.core.task.materialization import oracle_selection_contract
from trusted_synthesis.core.task.pattern import (
    PatternBindingValidationReport,
    TaskPatternMaterialization,
    TaskPatternSpec,
)
from trusted_synthesis.domains.legal.policy import LegalSemanticPolicy


class LegalTaskPatternRuntime:
    runtime_id = "legal_task_pattern_runtime.v1"
    runtime_version = "1.0.0"
    domain = "legal"
    renderer_ids: tuple[str, ...] = ("legal.rule_application.v1",)

    def __init__(self) -> None:
        self._policy = LegalSemanticPolicy()

    def validate_binding(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
    ) -> PatternBindingValidationReport:
        del pattern
        rules = evidence_by_role["rules"]
        first = rules[0]
        comparisons = tuple(self._policy.compare(first, item) for item in rules[1:])
        authorities = {
            item.payload.authority
            for item in rules
            if isinstance(item.payload, RuleStatement)
        }
        authority_priority = tuple(
            str(item) for item in binding.node_parameters.get("result", {}).get(
                "authority_priority", ()
            )
        )
        apply_parameters = binding.node_parameters.get("apply", {})
        checks = {
            "all_evidence_valid": all(
                self._policy.validate_evidence(item).passed for item in rules
            ),
            "same_legal_question_and_scope": all(item.comparable for item in comparisons),
            "conditions_explicit": "satisfied_conditions" in apply_parameters,
            "exceptions_explicit": "present_exceptions" in apply_parameters,
            "authority_priority_complete": authorities.issubset(set(authority_priority)),
        }
        issues = [check_id for check_id, passed in checks.items() if not passed]
        issues.extend(reason for item in comparisons for reason in item.reasons)
        unique_issues = tuple(dict.fromkeys(issues))
        return PatternBindingValidationReport(
            passed=not unique_issues,
            checks=checks,
            issues=unique_issues,
            semantic_alignment_cost=2.5,
        )

    def materialize(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
    ) -> TaskPatternMaterialization:
        del pattern, binding, bundle, proof_graph
        rules = evidence_by_role["rules"]
        return TaskPatternMaterialization(
            instruction=(
                "Apply the effective rules to the stated conditions, check every registered "
                "exception, and resolve any conflict by authority before stating the legal effect."
            ),
            retrieval_scope={
                "subject_ids": sorted({item.subject.subject_id for item in rules}),
                "predicates": sorted({item.predicate for item in rules}),
                "temporal_labels": sorted(
                    {
                        item.temporal_context.label
                        for item in rules
                        if item.temporal_context.label
                    }
                ),
                "source_authorities": sorted(
                    {item.source.authority.value for item in rules}
                ),
                "semantic_constraints": {
                    "definition_ids": sorted(
                        {
                            item.definition.definition_id
                            for item in rules
                            if item.definition.definition_id
                        }
                    ),
                    "scope_ids": sorted(
                        {
                            item.scope.scope_id
                            for item in rules
                            if item.scope is not None and item.scope.scope_id
                        }
                    ),
                },
            },
            oracle_selection_contract=oracle_selection_contract(rules),
            metadata={"domain_plugin_id": "legal_tasks.v2"},
        )
