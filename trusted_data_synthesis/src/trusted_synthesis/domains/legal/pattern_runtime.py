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
    runtime_id = "legal_task_pattern_runtime.v3"
    runtime_version = "3.0.0"
    domain = "legal"
    renderer_ids: tuple[str, ...] = (
        "legal.condition_application.v1",
        "legal.exception_application.v1",
        "legal.rule_application.v1",
    )

    def __init__(self) -> None:
        self._policy = LegalSemanticPolicy()

    def validate_binding(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
    ) -> PatternBindingValidationReport:
        role_id = "rules" if pattern.task_type == "legal_rule_application" else "rule"
        rules = evidence_by_role[role_id]
        first = rules[0]
        comparisons = tuple(self._policy.compare(first, item) for item in rules[1:])
        authorities = {
            item.payload.authority for item in rules if isinstance(item.payload, RuleStatement)
        }
        apply_node = "apply" if pattern.task_type == "legal_rule_application" else "result"
        apply_parameters = binding.node_parameters.get(apply_node, {})
        checks = {
            "all_evidence_valid": all(
                self._policy.validate_evidence(item).passed for item in rules
            ),
            "same_legal_question_and_scope": all(item.comparable for item in comparisons),
            "conditions_explicit": "satisfied_conditions" in apply_parameters,
            "exceptions_explicit": "present_exceptions" in apply_parameters,
        }
        if pattern.task_type == "legal_rule_application":
            authority_priority = tuple(
                str(item)
                for item in binding.node_parameters.get("result", {}).get("authority_priority", ())
            )
            checks["authority_priority_complete"] = authorities.issubset(set(authority_priority))
        if pattern.task_type == "legal_exception_application":
            checks["registered_exception_present"] = bool(
                apply_parameters.get("present_exceptions")
            )
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
        del bundle, proof_graph
        role_id = "rules" if pattern.task_type == "legal_rule_application" else "rule"
        rules = evidence_by_role[role_id]
        apply_node = "apply" if pattern.task_type == "legal_rule_application" else "result"
        apply_parameters = binding.node_parameters.get(apply_node, {})
        conditions = tuple(apply_parameters.get("satisfied_conditions") or ())
        exceptions = tuple(apply_parameters.get("present_exceptions") or ())
        facts = (
            f"Stated conditions: {conditions or ('none',)}. "
            f"Present exceptions: {exceptions or ('none',)}."
        )
        if pattern.task_type == "legal_condition_application":
            instruction = (
                "Apply the effective rule to the stated facts and identify any unsatisfied "
                f"condition before stating whether the rule applies. {facts}"
            )
        elif pattern.task_type == "legal_exception_application":
            instruction = (
                "Apply the effective rule after checking the stated facts and every registered "
                f"exception. State whether an exception prevents the legal effect. {facts}"
            )
        elif pattern.task_type == "legal_rule_application":
            authority_priority = tuple(
                binding.node_parameters.get("result", {}).get("authority_priority") or ()
            )
            instruction = (
                "Apply the effective rules to the stated conditions, check every registered "
                "exception, and resolve any conflict by authority before stating the legal effect. "
                f"{facts} Authority priority: {authority_priority}."
            )
        else:
            raise ValueError(f"unsupported legal task pattern: {pattern.task_type}")
        return TaskPatternMaterialization(
            instruction=instruction,
            retrieval_scope={
                "subject_ids": sorted({item.subject.subject_id for item in rules}),
                "predicates": sorted({item.predicate for item in rules}),
                "temporal_labels": sorted(
                    {item.temporal_context.label for item in rules if item.temporal_context.label}
                ),
                "source_authorities": sorted({item.source.authority.value for item in rules}),
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
            metadata={
                "domain_plugin_id": "legal_tasks.v3",
                "agent_contract_guidance": _legal_agent_contract_guidance(
                    pattern.task_type
                ),
            },
        )


def _legal_agent_contract_guidance(task_type: str) -> dict[str, object]:
    guidance: dict[str, object] = {
        "legal_apply_rule": {
            "exact_result_fields": (
                "applicable",
                "authority",
                "legal_effect",
                "missing_conditions",
                "triggered_exceptions",
            ),
            "field_rules": {
                "missing_conditions": (
                    "sorted rule.conditions absent from satisfied_conditions"
                ),
                "triggered_exceptions": (
                    "sorted intersection of rule.exceptions and present_exceptions"
                ),
                "applicable": (
                    "true only when both lists are empty"
                ),
                "authority": "copy the rule authority exactly",
                "legal_effect": "copy the rule legal_effect exactly",
            },
        },
        "general_rules": (
            "Do not replace missing_conditions with a prose explanation.",
            "Do not infer unstated facts, conditions, exceptions, or legal effects.",
            "Preserve every exact string and list element from the rule evidence.",
        ),
    }
    if task_type == "legal_rule_application":
        guidance["legal_resolve_authority"] = {
            "exact_result_fields": (
                "applicable",
                "selected_ref",
                "authority",
                "legal_effect",
            ),
            "field_rules": {
                "eligible_inputs": "only prior legal_apply_rule results with applicable=true",
                "selected_ref": (
                    "the prior operation result reference selected by authority_priority"
                ),
                "no_eligible_rule": (
                    "return applicable=false and null selected_ref, authority, legal_effect"
                ),
            },
        }
    return guidance
