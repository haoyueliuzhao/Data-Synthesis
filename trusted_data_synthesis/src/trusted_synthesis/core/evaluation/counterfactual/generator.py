from __future__ import annotations

from trusted_synthesis.core.evaluation.counterfactual.context import CounterfactualContext
from trusted_synthesis.core.evaluation.counterfactual.minimality import (
    validate_minimality,
)
from trusted_synthesis.core.evaluation.counterfactual.registry import (
    CounterfactualOperatorRegistry,
)
from trusted_synthesis.core.evaluation.counterfactual.schema import (
    CounterfactualCase,
    CounterfactualOpportunity,
)
from trusted_synthesis.hashing import canonical_hash

COUNTERFACTUAL_GENERATOR_VERSION = "typed_counterfactual_generator.v1"


class TypedCounterfactualGenerator:
    def __init__(
        self,
        registry: CounterfactualOperatorRegistry,
        *,
        minimality_threshold: float = 0.9,
    ) -> None:
        self._registry = registry
        self._minimality_threshold = minimality_threshold

    def generate(
        self,
        context: CounterfactualContext,
        opportunities: tuple[CounterfactualOpportunity, ...],
    ) -> tuple[CounterfactualCase, ...]:
        return tuple(self.generate_one(context, opportunity) for opportunity in opportunities)

    def generate_one(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> CounterfactualCase:
        context.validate()
        if opportunity.source_sample_id != context.source_sample.sample_id:
            raise ValueError("counterfactual opportunity belongs to another sample")
        if opportunity.quality_contract_hash != context.contract.contract_hash:
            raise ValueError("counterfactual opportunity belongs to another contract")
        operator = self._registry.require(
            opportunity.mutation_operator_id,
            opportunity.mutation_operator_version,
        )
        raw_mutated = operator.apply(context, opportunity)
        identity = {
            "source_trajectory_id": context.source_trajectory.trajectory_id,
            "opportunity_id": opportunity.opportunity_id,
            "steps": [
                item.model_dump(mode="json", exclude_none=True) for item in raw_mutated.steps
            ],
            "final_answer": raw_mutated.final_answer,
            "version": COUNTERFACTUAL_GENERATOR_VERSION,
        }
        mutated = raw_mutated.model_copy(
            update={
                "trajectory_id": canonical_hash(
                    identity,
                    prefix="typed_counterfactual_trajectory:",
                ),
                "generator_version": (
                    f"{COUNTERFACTUAL_GENERATOR_VERSION}:{opportunity.mutation_operator_id}"
                ),
            }
        )
        minimality = validate_minimality(
            context.source_trajectory,
            mutated,
            opportunity.allowed_json_path_prefixes,
            threshold=self._minimality_threshold,
        )
        case_identity = {
            "opportunity_id": opportunity.opportunity_id,
            "source_sample_id": opportunity.source_sample_id,
            "source_certificate_hash": opportunity.source_certificate_hash,
            "source_trajectory_id": opportunity.source_trajectory_id,
            "quality_contract_hash": opportunity.quality_contract_hash,
            "source_clause_id": opportunity.source_clause_id,
            "source_clause_kind": opportunity.source_clause_kind,
            "mutation_family": opportunity.mutation_family.value,
            "mutation_operator_id": opportunity.mutation_operator_id,
            "mutation_operator_version": opportunity.mutation_operator_version,
            "target_object_type": opportunity.target_object_type,
            "target_object_id": opportunity.target_object_id,
            "original_hash": context.source_trajectory.trajectory_hash,
            "mutated_hash": mutated.trajectory_hash,
            "expected_failed_clauses": opportunity.expected_failed_clause_ids,
            "expected_root_clause": opportunity.expected_root_clause_id,
            "minimality": minimality.model_dump(mode="json"),
            "generated_by": operator.provider_id,
            "version": COUNTERFACTUAL_GENERATOR_VERSION,
        }
        return CounterfactualCase(
            counterfactual_id=canonical_hash(
                case_identity,
                prefix="counterfactual_case:",
            ),
            opportunity_id=opportunity.opportunity_id,
            source_sample_id=opportunity.source_sample_id,
            source_certificate_hash=opportunity.source_certificate_hash,
            source_trajectory_id=opportunity.source_trajectory_id,
            quality_contract_hash=opportunity.quality_contract_hash,
            source_clause_id=opportunity.source_clause_id,
            source_clause_kind=opportunity.source_clause_kind,
            mutation_family=opportunity.mutation_family,
            mutation_operator_id=opportunity.mutation_operator_id,
            mutation_operator_version=opportunity.mutation_operator_version,
            target_object_type=opportunity.target_object_type,
            target_object_id=opportunity.target_object_id,
            original_hash=context.source_trajectory.trajectory_hash,
            mutated_hash=mutated.trajectory_hash,
            expected_failed_clauses=opportunity.expected_failed_clause_ids,
            expected_root_clause=opportunity.expected_root_clause_id,
            minimality=minimality,
            trajectory=mutated,
            generated_by=operator.provider_id,
            version=COUNTERFACTUAL_GENERATOR_VERSION,
        )
