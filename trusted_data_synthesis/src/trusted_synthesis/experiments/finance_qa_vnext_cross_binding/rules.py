"""Prospective, role-parameterized rule contract; no new outcome-specific revisions."""

from ..finance_qa_vnext_model_execution.models import record
from ..finance_qa_vnext_panel_quotient.rules import quotient_rule as base_rule
from ..finance_qa_vnext_support_transition.rules import measurement_rule as transition_rule


def quotient_rule():
    previous = transition_rule()
    return record(
        "cross_binding_rule",
        version="source_bound_share_retention.v1",
        base_rule_id=base_rule()["id"],
        prior_semantic_rule_id=previous["id"],
        applicability="new source-bound part-whole Share instances admitted before sampling",
        evidence_roles=[
            "target_component",
            "other_component",
            "disclosed_total",
            "composition_relation",
        ],
        required_source_contract=(
            "same entity, consolidation scope, period, currency, unit and metric definition; "
            "source-supported complete disjoint components and independently disclosed total"
        ),
        actual_operations=["relation_sum", "share_ratio", "scale_percent"],
        actual_graph_policy="retain every actual node and Final, including unused sum Claims",
        base_interpretations=base_rule(),
        support_transition=previous["support_transition"],
        grounding_assertion=previous["grounding_assertion"],
        assertion_normal_form=previous["assertion_normal_form"],
        normalization=previous["normalization"],
        retained_episode_order="source order; preserve all interpretable old and new episodes",
        instantiation=(
            "substitute real bound evidence references and task contracts, never rename bank "
            "components as freight, alter events or reuse old fixed sample labels"
        ),
        support_proof="Final <- accepted percent <- accepted ratio <- actual denominator",
        support_proof_is_complete_behavior_class=False,
        comparison="same Task/Context/protocol/registry/rule only, exact complete graph proof",
        cross_task_mechanism_summary_is_state_assignment=False,
        new_outcome_specific_rule_extension_allowed=False,
        fallback=previous["fallback"],
        forbidden_inferences=previous["forbidden_inferences"],
        frozen_before_new_provider_response=True,
        independently_bound_evaluation_set_exists=False,
    )
