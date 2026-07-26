from __future__ import annotations

from trusted_synthesis.core.evaluation.contracts.compiler import (
    QualityClauseCompilationContext,
)
from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseMutationSpec,
    ClauseScope,
    ClauseSeverity,
    ClauseTarget,
    QualityClause,
    make_quality_clause,
)
from trusted_synthesis.core.evaluation.mutations import MutationFamily


class LegalQualityClauseProvider:
    provider_id = "legal_quality_clauses.v2"
    provider_version = "2.0.0"

    def compile_evidence_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return tuple(
            _clause(
                context,
                "legal_authority_time_scope",
                "evidence",
                evidence_id,
                "selected_evidence_validity",
                context.base_clause_ids["selected_evidence_validity"],
                "legal_authority_effective_date_and_scope",
                mutation_specs=_legal_evidence_mutations(),
            )
            for evidence_id in context.task.oracle.gold_evidence_ids
        )

    def compile_program_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return tuple(
            _clause(
                context,
                "legal_rule_application",
                "program_node",
                node_id,
                "operation_correctness",
                context.base_clause_ids["operation_correctness"],
                "legal_condition_exception_authority_resolution",
            )
            for node_id in context.program_clause_ids
        )

    def compile_claim_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return (
            _clause(
                context,
                "bounded_legal_claim",
                "answer_claims",
                context.task.task_id,
                "domain_claim_verification",
                context.base_clause_ids["domain_claim_verification"],
                "legal_claim_boundary",
            ),
        )

    def compile_selection_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return ()


def _clause(
    context: QualityClauseCompilationContext,
    clause_kind: str,
    target_type: str,
    target_ref: str,
    check_id: str,
    dependency: str,
    failure_family: str,
    mutation_specs: tuple[ClauseMutationSpec, ...] = (),
) -> QualityClause:
    return make_quality_clause(
        task_id=context.task.task_id,
        clause_kind=clause_kind,
        scope=ClauseScope.DOMAIN,
        severity=ClauseSeverity.FATAL,
        target=ClauseTarget(target_type=target_type, target_ref=target_ref),
        verifier_id="candidate_check.v1",
        verifier_version="1.0.0",
        expected_ref="passed",
        parameters={"check_id": check_id},
        dependencies=(dependency,),
        failure_family=failure_family,
        diagnostic_dimensions=("domain_semantics",),
        mutation_specs=mutation_specs,
    )


def _legal_evidence_mutations() -> tuple[ClauseMutationSpec, ...]:
    definitions = (
        ("legal_replace_effective_date", MutationFamily.TEMPORAL),
        ("legal_replace_jurisdiction", MutationFamily.SCOPE),
        ("legal_replace_definition", MutationFamily.DEFINITION),
    )
    return tuple(
        ClauseMutationSpec(
            operator_id=operator_id,
            operator_version="1.0.0",
            mutation_family=family,
            root_clause_kind="gold_evidence_selected",
        )
        for operator_id, family in definitions
    )
