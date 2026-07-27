from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evaluation.counterfactual.closure import (
    failure_closure,
    resolve_root_clause,
)
from trusted_synthesis.core.evaluation.counterfactual.context import CounterfactualContext
from trusted_synthesis.core.evaluation.counterfactual.registry import (
    CounterfactualOperatorRegistry,
)
from trusted_synthesis.core.evaluation.counterfactual.schema import (
    CounterfactualOpportunity,
)
from trusted_synthesis.hashing import canonical_hash

COUNTERFACTUAL_PLANNER_VERSION = "counterfactual_planner.v1"


class CounterfactualPlanner:
    """Mine executable mutation opportunities directly from contract clauses."""

    def __init__(self, registry: CounterfactualOperatorRegistry) -> None:
        self._registry = registry

    def plan(
        self,
        context: CounterfactualContext,
    ) -> tuple[CounterfactualOpportunity, ...]:
        context.validate()
        opportunities = []
        for clause in context.contract.clauses:
            for spec in clause.mutation_specs:
                operator = self._registry.require(
                    spec.operator_id,
                    spec.operator_version,
                )
                root_clause_id = resolve_root_clause(
                    context.contract,
                    clause.clause_id,
                    spec.root_clause_kind,
                )
                expected_failures = failure_closure(
                    context.contract,
                    (root_clause_id,),
                )
                for draft in operator.plan(context, clause, spec):
                    parameters = dict(spec.parameters)
                    overlap = set(parameters) & set(draft.parameters)
                    if overlap:
                        raise ValueError(
                            f"counterfactual draft overwrote contract parameters: {sorted(overlap)}"
                        )
                    parameters.update(draft.parameters)
                    identity: dict[str, Any] = {
                        "source_sample_id": context.source_sample.sample_id,
                        "source_certificate_hash": (
                            context.source_sample.certificate.certificate_hash
                        ),
                        "source_trajectory_id": context.source_trajectory.trajectory_id,
                        "quality_contract_hash": context.contract.contract_hash,
                        "source_clause_id": clause.clause_id,
                        "source_clause_kind": clause.clause_kind,
                        "mutation_family": spec.mutation_family.value,
                        "mutation_operator_id": spec.operator_id,
                        "mutation_operator_version": spec.operator_version,
                        "target_object_type": clause.target.target_type,
                        "target_object_id": clause.target.target_ref,
                        "parameters": parameters,
                        "allowed_json_path_prefixes": draft.allowed_json_path_prefixes,
                        "expected_root_clause_id": root_clause_id,
                        "expected_failed_clause_ids": expected_failures,
                        "planner_version": COUNTERFACTUAL_PLANNER_VERSION,
                    }
                    opportunities.append(
                        CounterfactualOpportunity(
                            opportunity_id=canonical_hash(
                                identity,
                                prefix="counterfactual_opportunity:",
                            ),
                            source_sample_id=context.source_sample.sample_id,
                            source_certificate_hash=(
                                context.source_sample.certificate.certificate_hash
                            ),
                            source_trajectory_id=context.source_trajectory.trajectory_id,
                            quality_contract_hash=context.contract.contract_hash,
                            source_clause_id=clause.clause_id,
                            source_clause_kind=clause.clause_kind,
                            mutation_family=spec.mutation_family,
                            mutation_operator_id=spec.operator_id,
                            mutation_operator_version=spec.operator_version,
                            target_object_type=clause.target.target_type,
                            target_object_id=clause.target.target_ref,
                            parameters=parameters,
                            allowed_json_path_prefixes=(draft.allowed_json_path_prefixes),
                            expected_root_clause_id=root_clause_id,
                            expected_failed_clause_ids=expected_failures,
                            planner_version=COUNTERFACTUAL_PLANNER_VERSION,
                        )
                    )
        return tuple(
            sorted(
                opportunities,
                key=lambda item: item.opportunity_id,
            )
        )
