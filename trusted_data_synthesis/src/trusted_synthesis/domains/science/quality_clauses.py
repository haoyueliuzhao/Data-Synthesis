from __future__ import annotations

from trusted_synthesis.core.evaluation.contracts.compiler import (
    QualityClauseCompilationContext,
)
from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseScope,
    ClauseSeverity,
    ClauseTarget,
    QualityClause,
    make_quality_clause,
)


class ScienceQualityClauseProvider:
    provider_id = "science_quality_clauses.v1"
    provider_version = "1.0.0"

    def compile_evidence_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return tuple(
            _clause(
                context,
                "scientific_protocol_and_uncertainty",
                "evidence",
                evidence_id,
                "selected_evidence_validity",
                context.evidence_clause_ids[evidence_id][1],
                "scientific_protocol_population_metric_uncertainty",
            )
            for evidence_id in context.task.oracle.gold_evidence_ids
        )

    def compile_program_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return tuple(
            _clause(
                context,
                "scientific_comparison_operation",
                "program_node",
                node_id,
                "operation_correctness",
                clause_id,
                "scientific_comparability_and_uncertainty_preservation",
            )
            for node_id, clause_id in context.program_clause_ids.items()
        )

    def compile_claim_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]:
        return (
            _clause(
                context,
                "qualified_scientific_claim",
                "answer_claims",
                context.task.task_id,
                "domain_claim_verification",
                context.base_clause_ids["domain_claim_verification"],
                "scientific_claim_calibration",
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
    )
