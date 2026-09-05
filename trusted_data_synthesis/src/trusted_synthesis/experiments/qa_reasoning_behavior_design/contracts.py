"""Design-only public behavior rules; no runtime Mapper or trajectory projection."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from .models import STAGE, DesignChangeRequest

SCOPE_DIMENSIONS = (
    "task_definition",
    "evidence_universe",
    "oracle_program",
    "answer_schema",
    "unit_contract",
    "rounding_tolerance",
    "citation_contract",
    "validity_obligations",
)
EQUIVALENT_DIMENSIONS = ("schedule_order", "runtime_identity", "wording", "numeric_surface")
RETAINED_DIMENSIONS = (
    "evidence_support",
    "decision_basis",
    "derivation_dependencies",
    "observation_update",
)
FUTURE_VALIDATIONS = (
    "bind identical Task and frozen evidence, Oracle, answer, citation, and validity scope",
    "bind the behavior contract before candidate execution and outcome inspection",
    "reconstruct each candidate from its own actual State, Envelope, execution, Observation, "
    "Update",
    "check visible evidence and verified-Claim access at every actual pre-action boundary",
    "recompute QA validity and all required public decision obligations without a "
    "reference-route oracle",
    "establish actual action and update semantics, including meaningful causal dependencies",
    "qualify each actual trajectory independently before any future quotient projection",
)


def build_contract() -> dict[str, Any]:
    """Return a content-addressed design specification, not executable authority."""
    payload: dict[str, Any] = {
        "schema_version": "qa_reasoning_public_behavior_contract_design.v1",
        "stage": STAGE,
        "execution_status": "design_unexecuted",
        "scientific_object": "public evidence-grounded decisions and their causal updates",
        "private_reasoning_is_not_the_object": True,
        "same_task_scope": {
            "fixed_dimensions": SCOPE_DIMENSIONS,
            "task_definition": (
                "exact Task, question, entity, periods, metric definitions and objective"
            ),
            "evidence_universe": (
                "exact authorized source universe and fixed role, visibility and authority "
                "constraints"
            ),
            "oracle_program": "exact answer-correctness Oracle Program and its binding",
            "answer_contract": "fixed answer schema, units, numeric tolerance and rounding",
            "citation_contract": "fixed source-grounding and citation requirements",
            "validity_obligations": (
                "fixed QA and trajectory validation semantics and required public obligations"
            ),
            "actual_support_selection_is_behavior_not_task_identity": True,
            "no_new_evidence_or_relaxed_role_binding_to_manufacture_classes": True,
            "unavailable_variation_axis_status": "empty_or_not_witnessed",
        },
        "oracle_and_obligation_boundary": {
            "is_answer_correctness_oracle_only": True,
            "prescribes_unique_reasoning_path": False,
            "historical_five_step_execute_only_graph": (
                "verified local candidate subdomain, not universal route grammar"
            ),
            "required_obligations": "must still be discharged under unchanged validation semantics",
            "alternative_derivation": (
                "requires its own typed execution and evidence-to-obligation discharge mapping"
            ),
            "oracle_program_node_identity": (
                "source lineage, not mandatory candidate decision identity"
            ),
            "missing_alternative_validator": (
                "candidate family remains unimplemented; never waive validation"
            ),
        },
        "public_behavior_fields": {
            "evidence_support": (
                "source content binding, locator, role, period, definition, unit and authority",
                "actually selected visible support subset and its decision-use edges",
            ),
            "decision_basis": (
                "typed supports, requires, rules_out or insufficient relation",
                "actual source Evidence or verified Claim and the supported proposition",
            ),
            "derivation_dependencies": (
                "registered operation semantics and typed ordered operand roles",
                "actual producer-to-consumer Claim dependency edges and obligation discharge",
                "semantic Claim payload with exact values, units and grounding",
            ),
            "observation_update": (
                "actual supporting Observation and accept, reject or revise disposition",
                "old and replacement Claim semantics, revision dependency and uncertainty change",
                "invalidation of affected downstream Claims and actual enabled actions",
            ),
            "termination": "public terminal disposition and final answer/citation semantics",
            "termination_change_request_boundary": (
                "retained in any future projection; changing terminal policy is outside the "
                "current change-request domain and cannot waive the frozen answer contract"
            ),
        },
        "equivalence_design": {
            "domain": (
                "future independently Qualified own-execution trajectories for one fixed Task "
                "and contract"
            ),
            "equivalent_dimensions": EQUIVALENT_DIMENSIONS,
            "retained_dimensions": RETAINED_DIMENSIONS,
            "relation": (
                "equality of a future canonical typed public causal behavior representation"
            ),
            "canonicalization_requirement": (
                "deterministic identity up to semantic-label-preserving graph isomorphism"
            ),
            "source_alias_rule": (
                "only preregistered source-content, locator, role and authority preserving "
                "mappings; equal numeric values alone cannot merge distinct evidential grounds"
            ),
            "alpha_renaming": (
                "runtime IDs map bijectively to actual producers and all their references"
            ),
            "schedule_swap": (
                "only independent commuting actions with no conflicting Claim or State effects"
            ),
            "wording": (
                "only nonauthoritative surface text; changing a typed proposition or basis is "
                "retained"
            ),
            "decimal_surface": (
                "finite exact Decimal equality, no rounding or approximate tolerance relation"
            ),
            "ordered_operands": (
                "preserve roles; sort only explicitly registered unordered/commutative domains"
            ),
            "updates": (
                "retain meaningful revisions and rejection causality; timestamps and callback "
                "order alone vanish"
            ),
            "unregistered_algebraic_rewrite": (
                "outside this design domain until a rule is preregistered"
            ),
            "synthetic_padding_or_method_labels": (
                "not sufficient to establish a semantic difference"
            ),
            "graph_or_program_hash_difference_alone": (
                "not sufficient to establish a semantic difference"
            ),
            "answer_equality_alone": "not sufficient for behavior equivalence",
            "distinctness": (
                "same fixed scope, two own-qualified executions, and a replay-supported "
                "retained-field difference"
            ),
            "scope_mismatch": "not comparable as same-task classes",
            "failed_or_unreplayed_candidate": "outside quotient domain, never a new class",
            "transitivity": (
                "exact canonical equality required; pairwise numeric closeness is prohibited"
            ),
            "formal_mapper_implemented": False,
            "state_assignment_implemented": False,
        },
        "allowed_behavior_design": {
            "evidence_support": (
                "different sufficient support within unchanged visible universe and "
                "role/citation constraints"
            ),
            "decision_basis": (
                "different valid typed evidential basis for the same required obligation"
            ),
            "derivation_dependencies": (
                "different grounded typed route discharging all unchanged required obligations"
            ),
            "observation_update": (
                "observation-grounded rejection or revision with correct State and dependency "
                "propagation"
            ),
            "correction_boundary": (
                "tentative or invalidated Claims may not masquerade as verified inputs"
            ),
            "all_separation_cases_are_conditional": True,
            "new_valid_route_is_not_assumed_to_exist": True,
            "second_quotient_class_is_not_a_design_pass_requirement": True,
        },
        "responsibility_matrix": {
            "model_if_later_authorized": (
                "choose visible supporting evidence, typed basis, strategy, operands and next "
                "action before execution",
                "propose an observation-grounded Claim update and uncertainty/subgoal change",
                "own only semantic fields supplied by its corresponding phase-correct proposal",
                "action choices precede execution; Update proposals follow Observation and precede "
                "the next State commit",
            ),
            "host": (
                "derive legal candidates from frozen public rules and current State without "
                "answer-directed route filtering",
                "resolve source references and execute exactly the chosen registered "
                "tool/arithmetic action",
                "persist commitments and receipts, fsync artifacts and preserve actual callback "
                "ordering",
                "validate proposed updates, apply exact State changes and independently "
                "recompute the Oracle",
                "reject malformed or unsupported choices instead of silently substituting a "
                "successful route",
            ),
            "required_future_provenance": (
                "field_origin: frozen_contract, host_derived, model_proposed, or "
                "deterministic_fixture",
                "bind raw proposal, admitted action, host transformation and actual execution "
                "without imputed ownership",
            ),
            "host_fixed_trajectory_is_model_owned": False,
            "model_reachability_or_contribution_established": False,
        },
        "historical_control": {
            "scope": "two historical Tasks, two legal schedules per Task",
            "accepted_result": "one quotient class per Task in that frozen candidate family",
            "independent_commuting_pair": ("revenue_branch", "operating_income_branch"),
            "current_audit_topic": "closed_as_scoped",
            "historical_replay_requested": False,
            "new_empirical_confirmation_claimed": False,
        },
        "required_future_validations": FUTURE_VALIDATIONS,
        "qualification_contract": {
            "formula": "QA_valid AND trajectory_valid",
            "qa_valid": ("source_valid", "answer_valid", "citation_valid"),
            "trajectory_valid": (
                "preaction_valid",
                "grounding_valid",
                "reasoning_action_valid",
                "observation_update_valid",
                "critical_coverage_valid",
            ),
            "correct_answer_cannot_override_invalid_trajectory": True,
        },
        "claim_boundary": {
            "design_conformance_only": True,
            "actual_trajectory_rows": 0,
            "semantic_class_witnesses": 0,
            "provider_calls": 0,
            "training_or_distribution_claims": False,
            "future_runtime_or_candidate_stage_authorized": False,
            "old_mainline": "remains_paused",
        },
    }
    return {
        **payload,
        "contract_id": strict_canonical_hash(
            payload, prefix="qa_reasoning_behavior_design_contract:"
        ),
    }


def _decision(
    classification: str, reasons: list[str], changed: tuple[str, ...] = ()
) -> dict[str, Any]:
    return {
        "classification": classification,
        "execution_status": "design_unexecuted",
        "decision_basis": tuple(reasons),
        "changed_dimensions": changed,
        "required_future_validations": FUTURE_VALIDATIONS,
        "input_relations_are_unverified_design_premises": True,
        "equivalence_or_separation_empirically_established": False,
        "actual_trajectory_rows": 0,
        "semantic_class_witnesses": 0,
        "quotient_state_id": None,
    }


def classify_change(
    request: DesignChangeRequest | Mapping[str, Any],
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify a hypothetical change, never qualify or project an execution."""
    try:
        if contract is not None and canonical_json_bytes(contract) != canonical_json_bytes(
            build_contract()
        ):
            return _decision("reject_design_request", ["contract differs from frozen design rules"])
    except (TypeError, ValueError):
        return _decision("reject_design_request", ["contract is not canonical design data"])
    try:
        # Revalidation prevents model_construct or model_copy from bypassing strict fields.
        values = (
            request.model_dump(mode="python")
            if isinstance(request, DesignChangeRequest)
            else request
        )
        typed = DesignChangeRequest.model_validate_json(canonical_json_bytes(values))
    except (ValidationError, TypeError, ValueError):
        return _decision(
            "reject_design_request",
            [
                "request violates strict design-only schema; runtime proofs and qualification "
                "flags are not inputs"
            ],
        )
    changed = typed.changed_dimensions
    dimensions = set(changed)
    failures: list[str] = []
    for dimension in SCOPE_DIMENSIONS:
        if dimension in dimensions:
            failures.append(f"fixed same-task scope changed: {dimension}")
    for dimension in ("unregistered_equivalence", "unsupported_update", "external_evidence"):
        if dimension in dimensions:
            failures.append(f"unregistered or unsupported design change: {dimension}")
    relation_checks = (
        ("schedule_order", typed.schedule_relation, "independent_commuting_swap"),
        ("evidence_support", typed.evidence_relation, "different_admissible_visible_support"),
        ("decision_basis", typed.basis_relation, "different_typed_grounded_basis"),
        (
            "derivation_dependencies",
            typed.derivation_relation,
            "different_typed_obligation_discharge",
        ),
        ("observation_update", typed.update_relation, "observation_grounded_rejection_or_revision"),
    )
    for dimension, relation, admitted in relation_checks:
        if dimension in dimensions and relation != admitted:
            failures.append(f"{dimension} lacks its required design premise: {admitted}")
        elif dimension not in dimensions and relation != "unchanged":
            failures.append(f"undeclared substantive change: {dimension}")
    if "numeric_surface" in dimensions:
        try:
            before, after = Decimal(typed.numeric_before), Decimal(typed.numeric_after)
            if not before.is_finite() or not after.is_finite() or before != after:
                failures.append("numeric surfaces do not express the same finite exact Decimal")
        except (TypeError, InvalidOperation):
            failures.append("numeric surface normalization requires two exact Decimal strings")
    elif typed.numeric_before is not None or typed.numeric_after is not None:
        failures.append("undeclared numeric-surface change")
    if failures:
        return _decision("reject_design_request", failures, changed)
    retained = tuple(dimension for dimension in RETAINED_DIMENSIONS if dimension in dimensions)
    if retained:
        reasons = [
            f"retain replay-supported semantic difference in {dimension}" for dimension in retained
        ]
        reasons.append(
            "presence of an equivalent surface or schedule change cannot erase a retained "
            "semantic change"
        )
        reasons.append(
            "different labels alone are insufficient; future own-execution validity and actual "
            "retained-field change are mandatory"
        )
        return _decision("retain_difference_subject_to_future_validity", reasons, changed)
    return _decision(
        "equivalent_by_design",
        [f"registered identity-preserving design rule: {dimension}" for dimension in changed]
        + [
            "conditional on unchanged retained semantics and future qualification of both "
            "actual executions"
        ],
        changed,
    )


def _contract_invariants(contract: Mapping[str, Any]) -> dict[str, bool]:
    """Check separate normative boundaries, not observed runtime behavior."""
    expected = build_contract()

    def same(section: str, *fields: str) -> bool:
        actual_section = contract.get(section)
        if not isinstance(actual_section, Mapping):
            return False
        try:
            return all(
                canonical_json_bytes(actual_section.get(field))
                == canonical_json_bytes(expected[section][field])
                for field in fields
            )
        except (TypeError, ValueError):
            return False

    return {
        "task_behavior_disjoint": (
            same(
                "same_task_scope",
                "fixed_dimensions",
                "actual_support_selection_is_behavior_not_task_identity",
                "no_new_evidence_or_relaxed_role_binding_to_manufacture_classes",
            )
            and same("equivalence_design", "retained_dimensions")
            and set(SCOPE_DIMENSIONS).isdisjoint(RETAINED_DIMENSIONS)
        ),
        "oracle_not_unique_route": same(
            "oracle_and_obligation_boundary",
            "is_answer_correctness_oracle_only",
            "prescribes_unique_reasoning_path",
            "historical_five_step_execute_only_graph",
            "required_obligations",
            "alternative_derivation",
            "missing_alternative_validator",
        ),
        "commutation_conditional": same(
            "equivalence_design",
            "schedule_swap",
            "alpha_renaming",
            "source_alias_rule",
            "wording",
            "decimal_surface",
            "ordered_operands",
            "transitivity",
        ),
        "conditional_semantic_separation": (
            same(
                "equivalence_design",
                "retained_dimensions",
                "distinctness",
                "failed_or_unreplayed_candidate",
                "synthetic_padding_or_method_labels",
            )
            and same(
                "allowed_behavior_design",
                "all_separation_cases_are_conditional",
                "new_valid_route_is_not_assumed_to_exist",
                "second_quotient_class_is_not_a_design_pass_requirement",
            )
        ),
        "evidence_and_update_boundaries": same(
            "allowed_behavior_design",
            "evidence_support",
            "observation_update",
            "correction_boundary",
        ),
        "noncompensatory_validity": same(
            "qualification_contract",
            "formula",
            "qa_valid",
            "trajectory_valid",
            "correct_answer_cannot_override_invalid_trajectory",
        ),
        "role_responsibility_explicit": same(
            "responsibility_matrix",
            "model_if_later_authorized",
            "host",
            "required_future_provenance",
            "host_fixed_trajectory_is_model_owned",
            "model_reachability_or_contribution_established",
        ),
        "design_not_measured": (
            contract.get("execution_status") == "design_unexecuted"
            and same(
                "equivalence_design", "formal_mapper_implemented", "state_assignment_implemented"
            )
            and same(
                "claim_boundary",
                "design_conformance_only",
                "actual_trajectory_rows",
                "semantic_class_witnesses",
                "provider_calls",
                "training_or_distribution_claims",
                "future_runtime_or_candidate_stage_authorized",
            )
        ),
        "closed_historical_audit": same(
            "historical_control",
            "current_audit_topic",
            "historical_replay_requested",
            "new_empirical_confirmation_claimed",
        ),
    }


def run_design_controls(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check rule decisions on hypothetical requests; construct zero trajectories."""

    def proposal(dimensions: tuple[str, ...], **values: Any) -> dict[str, Any]:
        return {"execution_status": "design_unexecuted", "changed_dimensions": dimensions, **values}

    cases = (
        (
            "independent_swap",
            "equivalent_by_design",
            proposal(("schedule_order",), schedule_relation="independent_commuting_swap"),
        ),
        ("alpha_renaming", "equivalent_by_design", proposal(("runtime_identity",))),
        ("wording_only", "equivalent_by_design", proposal(("wording",))),
        (
            "exact_decimal_surface",
            "equivalent_by_design",
            proposal(("numeric_surface",), numeric_before="1.000", numeric_after="1e0"),
        ),
        (
            "visible_support_selection",
            "retain_difference_subject_to_future_validity",
            proposal(
                ("evidence_support",), evidence_relation="different_admissible_visible_support"
            ),
        ),
        (
            "typed_basis_change",
            "retain_difference_subject_to_future_validity",
            proposal(("decision_basis",), basis_relation="different_typed_grounded_basis"),
        ),
        (
            "typed_dependency_route",
            "retain_difference_subject_to_future_validity",
            proposal(
                ("derivation_dependencies",),
                derivation_relation="different_typed_obligation_discharge",
            ),
        ),
        (
            "grounded_revision",
            "retain_difference_subject_to_future_validity",
            proposal(
                ("observation_update",),
                update_relation="observation_grounded_rejection_or_revision",
            ),
        ),
        (
            "wording_cannot_mask_route",
            "retain_difference_subject_to_future_validity",
            proposal(
                ("wording", "derivation_dependencies"),
                derivation_relation="different_typed_obligation_discharge",
            ),
        ),
        ("oracle_scope_change", "reject_design_request", proposal(("oracle_program",))),
        ("task_scope_change", "reject_design_request", proposal(("task_definition",))),
        (
            "external_support",
            "reject_design_request",
            proposal(("evidence_support",), evidence_relation="outside_frozen_visible_universe"),
        ),
        (
            "dependency_crossing_swap",
            "reject_design_request",
            proposal(("schedule_order",), schedule_relation="dependency_crossing"),
        ),
        (
            "approximate_numeric_equality",
            "reject_design_request",
            proposal(("numeric_surface",), numeric_before="1.000", numeric_after="1.001"),
        ),
        (
            "unregistered_equivalence",
            "reject_design_request",
            proposal(("unregistered_equivalence",)),
        ),
        (
            "unsupported_update",
            "reject_design_request",
            proposal(("observation_update",), update_relation="unsupported_rewrite"),
        ),
        (
            "caller_qualification_not_authority",
            "reject_design_request",
            proposal(("wording",), qualified=True),
        ),
        (
            "undeclared_route_change",
            "reject_design_request",
            proposal(("wording",), derivation_relation="different_typed_obligation_discharge"),
        ),
    )
    rows = tuple(
        {
            "control_id": name,
            "request": request,
            "expected_classification": expected,
            "actual": (actual := classify_change(request, contract)),
            "passed": actual["classification"] == expected,
        }
        for name, expected, request in cases
    )
    invariants = _contract_invariants(contract)
    return {
        "execution_status": "design_unexecuted",
        "passed": all(row["passed"] for row in rows) and all(invariants.values()),
        "contract_invariants": invariants,
        "equivalence_controls": tuple(
            row for row in rows if row["expected_classification"] == "equivalent_by_design"
        ),
        "conditional_separation_controls": tuple(
            row
            for row in rows
            if row["expected_classification"] == "retain_difference_subject_to_future_validity"
        ),
        "rejected_controls": tuple(
            row for row in rows if row["expected_classification"] == "reject_design_request"
        ),
        "control_count": len(rows),
        "actual_trajectory_rows": 0,
        "semantic_class_witnesses": 0,
        "actual_quotient_partition_computed": False,
    }
