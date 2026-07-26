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


class FinanceQualityClauseProvider:
    provider_id = "finance_quality_clauses.v2"
    provider_version = "2.0.0"

    def compile_evidence_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return tuple(
            _domain_check(
                context,
                clause_kind="financial_evidence_semantics",
                target_type="evidence",
                target_ref=evidence_id,
                check_id="selected_evidence_validity",
                dependency=context.base_clause_ids["selected_evidence_validity"],
                failure_family="financial_definition_period_scope_alignment",
                detail_token=evidence_id,
                mutation_specs=_finance_evidence_mutations(),
            )
            for evidence_id in context.task.oracle.gold_evidence_ids
        )

    def compile_program_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return tuple(
            _domain_check(
                context,
                clause_kind="financial_operation_eligibility",
                target_type="program_node",
                target_ref=node_id,
                check_id="operation_correctness",
                dependency=context.base_clause_ids["operation_correctness"],
                failure_family="financial_operation_eligibility",
                detail_token=f"node:{node_id}",
            )
            for node_id in context.program_clause_ids
        )

    def compile_claim_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return (
            _domain_check(
                context,
                clause_kind="bounded_financial_claim",
                target_type="answer_claims",
                target_ref=context.task.task_id,
                check_id="domain_claim_verification",
                dependency=context.base_clause_ids["domain_claim_verification"],
                failure_family="financial_claim_boundary",
            ),
        )

    def compile_selection_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return (
            _domain_check(
                context,
                clause_kind="financial_source_grounding",
                target_type="evidence_selection",
                target_ref=context.task.task_id,
                check_id="source_grounding",
                dependency=context.base_clause_ids["source_grounding"],
                failure_family="financial_source_grounding",
            ),
        )


def _domain_check(
    context: QualityClauseCompilationContext,
    *,
    clause_kind: str,
    target_type: str,
    target_ref: str,
    check_id: str,
    dependency: str,
    failure_family: str,
    detail_token: str | None = None,
    mutation_specs: tuple[ClauseMutationSpec, ...] = (),
) -> QualityClause:
    parameters = {"check_id": check_id}
    if detail_token:
        parameters["detail_token"] = detail_token
    return make_quality_clause(
        task_id=context.task.task_id,
        clause_kind=clause_kind,
        scope=ClauseScope.DOMAIN,
        severity=ClauseSeverity.FATAL,
        target=ClauseTarget(target_type=target_type, target_ref=target_ref),
        verifier_id="candidate_check.v1",
        verifier_version="1.0.0",
        expected_ref="passed",
        parameters=parameters,
        dependencies=(dependency,),
        failure_family=failure_family,
        diagnostic_dimensions=("domain_semantics",),
        mutation_specs=mutation_specs,
    )


def _finance_evidence_mutations() -> tuple[ClauseMutationSpec, ...]:
    definitions = (
        ("finance_replace_metric_definition", MutationFamily.DEFINITION),
        ("finance_replace_version", MutationFamily.PROVENANCE),
        ("finance_replace_with_forecast", MutationFamily.TEMPORAL),
        ("finance_replace_unit", MutationFamily.DEFINITION),
        ("finance_replace_currency", MutationFamily.DEFINITION),
        ("finance_replace_scope", MutationFamily.SCOPE),
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
