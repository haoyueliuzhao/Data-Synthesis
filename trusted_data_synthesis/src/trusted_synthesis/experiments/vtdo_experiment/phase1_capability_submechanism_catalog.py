from __future__ import annotations

from collections.abc import Sequence

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    CONFIRMED_MECHANISM_IDS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilityPrimitive,
    CapabilitySubmechanismSpec,
    DiagnosticOutcome,
    EvidenceDependency,
    EvidenceRelation,
    SubmechanismActionGraph,
    _dep,
    _linear_graph,
    _runtime,
    _spec,
    _two_source_graph,
)


def make_candidate_specs() -> tuple[CapabilitySubmechanismSpec, ...]:
    """Build six preregistered structural candidates for each confirmed parent."""
    typed, cross, candidate, stopping = CONFIRMED_MECHANISM_IDS
    specs: list[CapabilitySubmechanismSpec] = []

    def add_linear(
        parent: str,
        key: str,
        title: str,
        steps: Sequence[tuple[str, CapabilityPrimitive, str | None]],
        relations: tuple[EvidenceRelation, ...],
        trigger: str,
        resolution: str,
        diagnostics: tuple[DiagnosticOutcome, ...],
        *,
        implementation_id: str | None = None,
    ) -> None:
        specs.append(
            _spec(
                parent,
                key,
                title,
                _linear_graph(steps),
                tuple(
                    _dep(f"{key}_{index}", relation)
                    for index, relation in enumerate(relations)
                ),
                _runtime(
                    key,
                    trigger,
                    resolution,
                    (f"observe:{trigger}", f"resolve:{resolution}"),
                    implementation_id=implementation_id,
                ),
                diagnostics,
            )
        )

    _add_typed_specs(add_linear, typed)
    _add_candidate_specs(add_linear, specs, candidate)
    _add_cross_family_specs(add_linear, specs, cross)
    _add_stopping_specs(add_linear, specs, stopping)
    return tuple(specs)


def _add_typed_specs(add: object, parent: str) -> None:
    add_linear = add
    assert callable(add_linear)
    add_linear(
        parent,
        "parameter_value_correction",
        "Typed parameter value correction",
        (
            ("select_tool", "select_tool", "search_archive"),
            ("construct_arguments", "construct_arguments", "query_structured_fact"),
            ("typed_failure", "observe_failure", "query_structured_fact"),
            ("localize_value", "localize_failure", "cross_check_evidence"),
            ("patch_value", "repair_argument", "query_structured_fact"),
            ("retry", "execute_tool", "query_structured_fact"),
        ),
        ("selector_binding",),
        "typed_failure",
        "patch_value",
        ("tool", "recovery"),
        implementation_id="finance_typed_recovery_scenario.v1",
    )
    add_linear(
        parent,
        "parameter_field_correction",
        "Typed parameter field correction",
        (
            ("inspect_schema", "select_tool", "search_archive"),
            ("construct_arguments", "construct_arguments", "query_structured_fact"),
            ("unknown_field", "observe_failure", "query_structured_fact"),
            ("patch_field", "repair_argument", "query_structured_fact"),
            ("retry", "execute_tool", "query_structured_fact"),
            ("verify", "verify_evidence", "cross_check_evidence"),
        ),
        ("selector_binding", "required_support"),
        "unknown_field",
        "patch_field",
        ("tool", "verification", "recovery"),
        implementation_id="finance_typed_recovery_scenario.v1",
    )
    add_linear(
        parent,
        "missing_prerequisite_evidence",
        "Missing prerequisite Evidence recovery",
        (
            ("attempt_calculation", "calculate", "calculator"),
            ("missing_operand", "observe_failure", "calculator"),
            ("retrieve_operand", "retrieve_missing", "query_structured_fact"),
            ("retry_calculation", "calculate", "calculator"),
            ("verify", "verify_evidence", "cross_check_evidence"),
        ),
        ("prerequisite", "operation_lineage", "required_support"),
        "missing_operand",
        "retrieve_operand",
        ("tool", "verification", "recovery"),
    )
    add_linear(
        parent,
        "tool_switch",
        "Typed tool-family switch",
        (
            ("select_initial_tool", "select_tool", "search_archive"),
            ("unsupported_route", "observe_failure", "search_archive"),
            ("switch_tool", "switch_tool", "query_structured_fact"),
            ("execute_switched_tool", "execute_tool", "query_structured_fact"),
            ("verify", "verify_evidence", "cross_check_evidence"),
        ),
        ("alternative_tool_path", "required_support"),
        "unsupported_route",
        "switch_tool",
        ("tool", "verification", "recovery"),
    )
    add_linear(
        parent,
        "operation_reference_repair",
        "Operation-reference lineage repair",
        (
            ("calculate_predecessor", "calculate", "calculator"),
            ("stale_reference", "observe_failure", "calculator"),
            ("inspect_lineage", "replay_calculation", "calculator"),
            ("repair_reference", "repair_operation_ref", "calculator"),
            ("retry_operation", "calculate", "calculator"),
            ("verify", "verify_evidence", "cross_check_evidence"),
        ),
        ("operation_lineage", "prerequisite"),
        "stale_reference",
        "repair_reference",
        ("tool", "verification", "recovery"),
    )
    add_linear(
        parent,
        "selector_scope_correction",
        "Typed period and scope selector correction",
        (
            ("construct_selector", "construct_arguments", "query_structured_fact"),
            ("scope_failure", "observe_failure", "query_structured_fact"),
            ("inspect_scope", "normalize_semantics", "normalize_metric_unit_period"),
            ("patch_scope", "repair_argument", "query_structured_fact"),
            ("retry", "execute_tool", "query_structured_fact"),
        ),
        ("selector_binding", "semantic_compatibility"),
        "scope_failure",
        "patch_scope",
        ("tool", "recovery"),
        implementation_id="finance_typed_recovery_scenario.v1",
    )


def _add_candidate_specs(add: object, specs: list[CapabilitySubmechanismSpec], parent: str) -> None:
    add_linear = add
    assert callable(add_linear)
    add_linear(
        parent,
        "period_scope_error",
        "Candidate period-scope verification",
        (
            ("retrieve_support", "retrieve", "query_structured_fact"),
            ("replay", "replay_calculation", "calculator"),
            ("verify_candidate", "verify_candidate", "cross_check_evidence"),
            ("repair_period", "repair_candidate", "cross_check_evidence"),
            ("verify_repair", "verify_evidence", "cross_check_evidence"),
        ),
        ("required_support", "operation_lineage", "semantic_compatibility"),
        "verify_candidate",
        "repair_period",
        ("verification", "recovery"),
        implementation_id="finance_capability_mechanism_scenario.v3:period_scope",
    )
    add_linear(
        parent,
        "unit_error",
        "Candidate unit verification and conversion repair",
        (
            ("normalize_units", "normalize_semantics", "normalize_metric_unit_period"),
            ("replay", "replay_calculation", "calculator"),
            ("verify_candidate", "verify_candidate", "cross_check_evidence"),
            ("repair_unit", "repair_candidate", "cross_check_evidence"),
            ("verify_repair", "verify_evidence", "cross_check_evidence"),
        ),
        ("semantic_compatibility", "operation_lineage"),
        "verify_candidate",
        "repair_unit",
        ("verification", "recovery"),
    )
    specs.append(
        _branched_spec(
            parent,
            "source_definition_error",
            "Candidate SourceDefinition compatibility repair",
            resolution_primitive="compare_definition",
            post_resolution_primitive="repair_candidate",
            dependencies=(
                _dep("source_definition", "semantic_compatibility"),
                _dep("authority", "provenance"),
            ),
            diagnostics=("verification", "recovery"),
        )
    )
    add_linear(
        parent,
        "local_calculation_error",
        "Candidate local calculation replay and repair",
        (
            ("replay_inputs", "replay_calculation", "calculator"),
            ("verify_candidate", "verify_candidate", "cross_check_evidence"),
            ("repair_value", "repair_candidate", "calculator"),
            ("regression_replay", "replay_calculation", "calculator"),
            ("verify_repair", "verify_evidence", "cross_check_evidence"),
        ),
        ("operation_lineage", "required_support"),
        "verify_candidate",
        "repair_value",
        ("verification", "recovery"),
    )
    add_linear(
        parent,
        "insufficient_evidence",
        "Candidate support-completeness repair",
        (
            ("verify_support", "verify_candidate", "cross_check_evidence"),
            ("missing_support", "observe_failure", "cross_check_evidence"),
            ("retrieve_support", "retrieve_missing", "query_structured_fact"),
            ("repair_candidate", "repair_candidate", "cross_check_evidence"),
            ("verify_repair", "verify_evidence", "cross_check_evidence"),
        ),
        ("required_support", "completeness"),
        "missing_support",
        "retrieve_support",
        ("tool", "verification", "recovery"),
    )
    add_linear(
        parent,
        "entity_scope_error",
        "Candidate entity-scope verification",
        (
            ("retrieve_scope", "retrieve", "query_structured_fact"),
            ("assess_scope", "assess_completeness", "cross_check_evidence"),
            ("verify_candidate", "verify_candidate", "cross_check_evidence"),
            ("repair_scope", "repair_candidate", "cross_check_evidence"),
            ("verify_repair", "verify_evidence", "cross_check_evidence"),
        ),
        ("completeness", "required_support"),
        "verify_candidate",
        "repair_scope",
        ("verification", "recovery", "stopping"),
    )


def _add_cross_family_specs(
    add: object, specs: list[CapabilitySubmechanismSpec], parent: str
) -> None:
    add_linear = add
    assert callable(add_linear)
    add_linear(
        parent,
        "retrieval_failure",
        "Cross-family retrieval failure recovery",
        (
            ("initial_query", "retrieve", "query_structured_fact"),
            ("empty_result", "observe_failure", "query_structured_fact"),
            ("localize_query", "localize_failure", "cross_check_evidence"),
            ("reformulate", "repair_argument", "search_archive"),
            ("retry_query", "retrieve", "search_archive"),
        ),
        ("selector_binding", "alternative_tool_path"),
        "empty_result",
        "reformulate",
        ("tool", "recovery"),
        implementation_id="finance_typed_recovery_scenario.v1",
    )
    add_linear(
        parent,
        "argument_failure",
        "Cross-family argument failure recovery",
        (
            ("construct_arguments", "construct_arguments", "query_structured_fact"),
            ("typed_failure", "observe_failure", "query_structured_fact"),
            ("attribute_field", "localize_failure", "cross_check_evidence"),
            ("patch_argument", "repair_argument", "query_structured_fact"),
            ("retry", "execute_tool", "query_structured_fact"),
        ),
        ("selector_binding",),
        "typed_failure",
        "patch_argument",
        ("tool", "recovery"),
    )
    add_linear(
        parent,
        "calculation_prerequisite_failure",
        "Cross-family calculation prerequisite recovery",
        (
            ("attempt_calculation", "calculate", "calculator"),
            ("missing_prerequisite", "observe_failure", "calculator"),
            ("retrieve_prerequisite", "retrieve_missing", "query_structured_fact"),
            ("repair_reference", "repair_operation_ref", "calculator"),
            ("retry_calculation", "calculate", "calculator"),
        ),
        ("prerequisite", "operation_lineage"),
        "missing_prerequisite",
        "retrieve_prerequisite",
        ("tool", "recovery"),
    )
    add_linear(
        parent,
        "verification_rejection",
        "Cross-family verification rejection recovery",
        (
            ("calculate", "calculate", "calculator"),
            ("verification_rejection", "verify_evidence", "cross_check_evidence"),
            ("trace_lineage", "replay_calculation", "calculator"),
            ("repair_reference", "repair_operation_ref", "calculator"),
            ("reverify", "verify_evidence", "cross_check_evidence"),
        ),
        ("operation_lineage", "required_support"),
        "verification_rejection",
        "repair_reference",
        ("verification", "recovery"),
    )
    specs.append(
        _branched_spec(
            parent,
            "evidence_conflict",
            "Cross-family Evidence conflict recovery",
            resolution_primitive="resolve_conflict",
            post_resolution_primitive="verify_evidence",
            dependencies=(
                _dep("conflicting_values", "conflict"),
                _dep("authority", "provenance"),
            ),
            diagnostics=("verification", "recovery"),
        )
    )
    add_linear(
        parent,
        "empty_result_tool_fallback",
        "Cross-family empty-result tool fallback",
        (
            ("initial_query", "execute_tool", "query_structured_fact"),
            ("empty_result", "observe_failure", "query_structured_fact"),
            ("attribute_route", "localize_failure", "cross_check_evidence"),
            ("switch_route", "switch_tool", "search_archive"),
            ("retrieve", "retrieve", "search_archive"),
            ("verify", "verify_evidence", "cross_check_evidence"),
        ),
        ("alternative_tool_path", "required_support"),
        "empty_result",
        "switch_route",
        ("tool", "verification", "recovery"),
    )


def _add_stopping_specs(
    add: object, specs: list[CapabilitySubmechanismSpec], parent: str
) -> None:
    add_linear = add
    assert callable(add_linear)
    add_linear(
        parent,
        "incomplete_continue",
        "Incomplete Evidence state must continue",
        (
            ("retrieve_partial", "retrieve", "query_structured_fact"),
            ("check_incomplete", "assess_completeness", "cross_check_evidence"),
            ("continue", "continue_work", None),
            ("retrieve_missing", "retrieve_missing", "query_structured_fact"),
            ("check_complete", "assess_completeness", "cross_check_evidence"),
        ),
        ("completeness", "required_support"),
        "check_incomplete",
        "retrieve_missing",
        ("tool", "verification", "stopping"),
        implementation_id="finance_capability_mechanism_scenario.v3:incomplete_transition",
    )
    add_linear(
        parent,
        "complete_stop",
        "Complete Evidence state must stop",
        (
            ("retrieve_complete", "retrieve", "query_structured_fact"),
            ("check_complete", "assess_completeness", "cross_check_evidence"),
            ("verify", "verify_evidence", "cross_check_evidence"),
        ),
        ("completeness", "required_support"),
        "check_complete",
        "verify",
        ("verification", "stopping"),
    )
    add_linear(
        parent,
        "post_complete_error_risk",
        "Post-completion error-risk stopping",
        (
            ("retrieve_complete", "retrieve", "query_structured_fact"),
            ("check_complete", "assess_completeness", "cross_check_evidence"),
            ("assess_extra_action_risk", "assess_risk", "cross_check_evidence"),
        ),
        ("completeness", "required_support"),
        "check_complete",
        "assess_extra_action_risk",
        ("verification", "stopping"),
    )
    add_linear(
        parent,
        "post_complete_cost",
        "Post-completion marginal-cost stopping",
        (
            ("retrieve_complete", "retrieve", "query_structured_fact"),
            ("check_complete", "assess_completeness", "cross_check_evidence"),
            ("assess_marginal_cost", "assess_cost", None),
        ),
        ("completeness",),
        "check_complete",
        "assess_marginal_cost",
        ("stopping",),
        implementation_id="finance_capability_mechanism_scenario.v3:redundancy_cost",
    )
    specs.append(
        _branched_spec(
            parent,
            "unresolved_conflict_cannot_stop",
            "Unresolved Evidence conflict prevents stopping",
            resolution_primitive="resolve_conflict",
            post_resolution_primitive="assess_completeness",
            dependencies=(
                _dep("conflict", "conflict"),
                _dep("completion", "completeness"),
            ),
            diagnostics=("verification", "recovery", "stopping"),
        )
    )
    add_linear(
        parent,
        "uncertain_source_coverage",
        "Source-coverage uncertainty prevents stopping",
        (
            ("retrieve_primary", "retrieve", "query_structured_fact"),
            ("check_coverage", "assess_completeness", "cross_check_evidence"),
            ("retrieve_provenance", "retrieve_missing", "search_archive"),
            ("verify_authority", "verify_evidence", "cross_check_evidence"),
            ("recheck", "assess_completeness", "cross_check_evidence"),
        ),
        ("provenance", "completeness", "required_support"),
        "check_coverage",
        "retrieve_provenance",
        ("tool", "verification", "stopping"),
    )


def _branched_spec(
    parent: str,
    key: str,
    title: str,
    *,
    resolution_primitive: CapabilityPrimitive,
    post_resolution_primitive: CapabilityPrimitive,
    dependencies: tuple[EvidenceDependency, ...],
    diagnostics: tuple[DiagnosticOutcome, ...],
) -> CapabilitySubmechanismSpec:
    graph: SubmechanismActionGraph = _two_source_graph(
        resolution_primitive=resolution_primitive,
        post_resolution_primitive=post_resolution_primitive,
    )
    return _spec(
        parent,
        key,
        title,
        graph,
        dependencies,
        _runtime(
            key,
            "resolve_two_sources",
            "post_resolution_check",
            (f"observe:{key}", f"resolve:{key}"),
        ),
        diagnostics,
    )
