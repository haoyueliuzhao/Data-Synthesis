from __future__ import annotations

from collections import defaultdict
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseSeverity,
    ContractQualityAssessment,
    QualityContract,
)

from .schema import (
    FeedbackExposure,
    FeedbackRoute,
    FeedbackSignal,
    make_feedback_signal,
)


class FeedbackRoutingPolicy(BaseModel):
    """Domain-neutral routing vocabulary. Domain plugins may supply another policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    upstream_family_tokens: tuple[str, ...] = (
        "source_grounding",
        "evidence_integrity",
        "evidence_version",
        "definition_conflict",
        "binding_unsatisfied",
        "binding_infeasible",
    )
    interface_error_codes: tuple[str, ...] = (
        "invalid_json",
        "schema_validation_failed",
        "unknown_evidence_id",
        "unknown_evidence_input",
        "unregistered_operator",
        "disallowed_tool",
        "oracle_injection",
        "provider_timeout",
    )
    severity_weights: dict[str, float] = {
        "fatal": 1.0,
        "quarantine": 0.5,
        "diagnostic": 0.25,
    }


def route_failure(
    *,
    failure_family: str,
    failure_code: str | None,
    action_category: str | None = None,
    policy: FeedbackRoutingPolicy | None = None,
) -> FeedbackRoute:
    active = policy or FeedbackRoutingPolicy()
    if action_category in {"interface_security", "infrastructure"}:
        return FeedbackRoute.INTERFACE_FAILURE
    if action_category == "upstream_data":
        return FeedbackRoute.UPSTREAM_DATA_DEFECT
    if failure_code in set(active.interface_error_codes):
        return FeedbackRoute.INTERFACE_FAILURE
    normalized = failure_family.casefold()
    if any(token.casefold() in normalized for token in active.upstream_family_tokens):
        return FeedbackRoute.UPSTREAM_DATA_DEFECT
    return FeedbackRoute.AGENT_CAPABILITY_GAP


def contract_feedback(
    *,
    domain: str,
    pattern_id: str,
    contract: QualityContract,
    assessment: ContractQualityAssessment,
    policy: FeedbackRoutingPolicy | None = None,
) -> tuple[tuple[FeedbackExposure, ...], tuple[FeedbackSignal, ...]]:
    """Compile sample-level exposures and root-only failures from one assessment."""

    if contract.contract_id != assessment.quality_contract_id:
        raise ValueError("assessment does not belong to the supplied quality contract")
    active = policy or FeedbackRoutingPolicy()
    clauses_by_id = {item.clause_id: item for item in contract.clauses}
    results_by_id = {item.clause_id: item for item in assessment.clause_results}
    families = defaultdict(list)
    for clause in contract.clauses:
        families[clause.failure_family].append(clause)
    exposures = tuple(
        FeedbackExposure(
            task_id=assessment.task_id,
            domain=domain,
            pattern_id=pattern_id,
            failure_family=family,
        )
        for family in sorted(families)
    )
    signals = []
    for clause_id in assessment.root_failure_clause_ids:
        try:
            clause = clauses_by_id[clause_id]
            result = results_by_id[clause_id]
        except KeyError as exc:
            raise ValueError(f"root failure references an unknown clause: {clause_id}") from exc
        severity = cast(
            Literal["fatal", "quarantine", "diagnostic"],
            clause.severity.value,
        )
        signals.append(
            make_feedback_signal(
                task_id=assessment.task_id,
                domain=domain,
                pattern_id=pattern_id,
                clause_id=clause.clause_id,
                clause_kind=clause.clause_kind,
                failure_family=clause.failure_family,
                severity=severity,
                failure_code=result.failure_code,
                route=route_failure(
                    failure_family=clause.failure_family,
                    failure_code=result.failure_code,
                    policy=active,
                ),
                source_kind="quality_contract",
                weight=active.severity_weights[severity],
            )
        )
    return exposures, tuple(signals)


def failed_action_feedback(
    *,
    task_id: str,
    domain: str,
    pattern_id: str,
    failure_category: str,
    error_code: str,
    failed_step_index: int | None,
    policy: FeedbackRoutingPolicy | None = None,
) -> FeedbackSignal:
    active = policy or FeedbackRoutingPolicy()
    route = route_failure(
        failure_family="action_execution",
        failure_code=error_code,
        action_category=failure_category,
        policy=active,
    )
    return make_feedback_signal(
        task_id=task_id,
        domain=domain,
        pattern_id=pattern_id,
        clause_id=f"host_action:{error_code}:{failed_step_index or 0}",
        clause_kind="host_action_execution",
        failure_family="action_execution",
        severity="fatal",
        failure_code=error_code,
        route=route,
        source_kind="failed_action_plan",
        weight=active.severity_weights[ClauseSeverity.FATAL.value],
    )
