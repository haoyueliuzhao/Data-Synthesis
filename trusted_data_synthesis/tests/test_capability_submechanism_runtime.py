from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_STOPPING_SHAPE_DECISION_V4_VERSION,
    FINANCE_SUBMECHANISM_ORACLE_KEY,
    FinanceCapabilitySubmechanismRuntime,
    FinanceStoppingDependencyOption,
    FinanceStoppingMeasurementContext,
    FinanceStoppingObservedEvidenceState,
    FinanceStoppingObservedRecord,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    FinanceStoppingTemporalIdentity,
    evidence_roles_from_items,
    make_finance_submechanism_scenario,
    make_submechanism_manifest,
    public_submechanism_contract,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import _replay_observations
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    compile_finance_agent_case,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    _all_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    FinanceSubmechanismFlashContract,
    FinanceSubmechanismFlashReport,
    _host_event_sequence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    BOUNDARY_BASE_TIER,
    PUBLIC_SUBMECHANISM_METADATA_KEY,
    CapabilitySubmechanismPopulation,
    CapabilitySubmechanismTask,
    _public_mechanism_nondisclosed,
)
from trusted_synthesis.runtime.agent.iterative import (
    _make_failure_artifact,
)
from trusted_synthesis.runtime.tools import AgentToolCall, make_agent_tool_observation


def _omega() -> Any:
    case = compile_finance_agent_case(build_finance_counterfactual_case(2))
    compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    sample = ProofCarryingSampleCompiler(
        case.registry,
        compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
        source_grounding_verifier=case.source_grounding_verifier,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    return sample.joint_compilation.omega


def _scenario(context: Any, kind: str, *, candidate: bool = False) -> Any:
    items = tuple(context.public_corpus.evidence)
    roles = evidence_roles_from_items(items)
    values: dict[str, Any] = {
        "submechanism_id": f"finance.test.{kind}",
        "parent_mechanism_id": "finance.test.parent",
        "intervention_kind": kind,
        "expected_host_events": (
            "observe:typed_host_state",
            "resolve:typed_host_state",
        ),
        "evidence_roles": roles,
        "public_resolution_hint": "Use the observed typed Host state.",
    }
    if candidate:
        values.update(
            {
                "untrusted_candidate": {"value": "wrong", "unit": "USD"},
                "canonical_candidate": {"value": "correct", "unit": "USD"},
                "repair_target_field": "value",
            }
        )
    return make_finance_submechanism_scenario(**values)


def _runtime(context: Any, scenario: Any) -> FinanceCapabilitySubmechanismRuntime:
    manifest = make_submechanism_manifest(
        corpus=context.public_corpus,
        scenario=scenario,
        environment_id=f"submechanism-test:{scenario.scenario_id}",
        maximum_tool_calls=30,
        maximum_failed_tool_calls=10,
        maximum_total_observation_bytes=1_000_000,
    )
    return FinanceCapabilitySubmechanismRuntime(
        context.public_corpus,
        manifest,
        scenario=scenario,
    )


def _call(
    runtime: FinanceCapabilitySubmechanismRuntime,
    index: int,
    tool_id: str,
    arguments: dict[str, Any],
) -> Any:
    return runtime.execute(AgentToolCall(call_index=index, tool_id=tool_id, arguments=arguments))


def _select_all(runtime: FinanceCapabilitySubmechanismRuntime, scenario: Any) -> int:
    index = 0
    for role in scenario.evidence_roles:
        index += 1
        result = _call(
            runtime,
            index,
            "query_structured_fact",
            {
                "subject_alias": role.subject_alias,
                "metric_alias": role.metric_alias,
                "period_label": role.period_label,
                "public_filters": {},
            },
        )
        assert result.status == "succeeded"
    return index


def _calculate(runtime: FinanceCapabilitySubmechanismRuntime, index: int) -> tuple[int, str]:
    index += 1
    result = _call(
        runtime,
        index,
        "calculator",
        {
            "operator": "lookup",
            "operands": [{"evidence_id": runtime.selected_evidence_ids[0]}],
            "parameters": {},
        },
    )
    assert result.status == "succeeded"
    return index, str(result.result["result"]["operation_ref"])


def _verify(
    runtime: FinanceCapabilitySubmechanismRuntime,
    index: int,
    operation_ref: str,
) -> tuple[int, Any]:
    index += 1
    result = _call(
        runtime,
        index,
        "cross_check_evidence",
        {
            "evidence_ids": list(runtime.selected_evidence_ids),
            "claim_or_result": {"operation_ref": operation_ref},
        },
    )
    return index, result


def test_candidate_scenario_requires_exactly_one_mismatched_field() -> None:
    context = _omega()
    roles = evidence_roles_from_items(tuple(context.public_corpus.evidence))
    with pytest.raises(ValidationError, match="exactly one local error"):
        make_finance_submechanism_scenario(
            submechanism_id="finance.test.bad_candidate",
            parent_mechanism_id="finance.test.parent",
            intervention_kind="local_calculation_error",
            expected_host_events=("candidate:observed", "candidate:resolved"),
            evidence_roles=roles,
            public_resolution_hint="Repair exactly one field.",
            untrusted_candidate={"value": "wrong", "unit": "wrong"},
            canonical_candidate={"value": "correct", "unit": "USD"},
            repair_target_field="value",
        )


def test_runtime_snapshot_and_public_contract_are_scenario_specific() -> None:
    context = _omega()
    first = _scenario(context, "uncertain_source_coverage")
    second = _scenario(context, "post_complete_cost")
    first_manifest = make_submechanism_manifest(
        corpus=context.public_corpus,
        scenario=first,
        environment_id="submechanism-test:first",
        maximum_tool_calls=30,
        maximum_failed_tool_calls=10,
        maximum_total_observation_bytes=1_000_000,
    )
    second_manifest = make_submechanism_manifest(
        corpus=context.public_corpus,
        scenario=second,
        environment_id="submechanism-test:second",
        maximum_tool_calls=30,
        maximum_failed_tool_calls=10,
        maximum_total_observation_bytes=1_000_000,
    )

    assert first_manifest.snapshot_hash != second_manifest.snapshot_hash
    assert all("submechanism_resolution" in spec.output_contract for spec in first_manifest.tools)
    public = public_submechanism_contract(first)
    assert "canonical_candidate" not in public
    assert "evidence_roles" not in public
    assert "submechanism_id" not in public
    assert "parent_mechanism_id" not in public
    assert "intervention_kind" not in public
    assert "trigger_tool" not in public
    assert "resolution_tools" not in public
    assert "public_resolution_hint" not in public
    assert public["oracle_mechanism_identity_disclosed"] is False
    assert all("evidence:" not in str(value) for value in public.values())


def test_candidate_public_contract_exposes_shape_without_gold_value() -> None:
    context = _omega()
    scenario = _scenario(context, "local_calculation_error", candidate=True)
    public = public_submechanism_contract(scenario)
    submission = public["candidate_submission_contract"]

    assert submission == {
        "selector": ["claim_or_result", "candidate_payload"],
        "required_fields": ["unit", "value"],
        "localized_field": "value",
        "preserve_fields": ["unit"],
        "additional_fields_allowed": False,
        "canonical_value_disclosed": False,
        "value_source": "derive_independently_from_public_evidence_and_tool_observations",
    }
    assert "correct" not in str(public)

    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)
    index, mismatch = _verify(runtime, index, operation_ref)
    assert mismatch.result["candidate_repair"]["submission_contract"] == submission

    repaired = _call(
        runtime,
        index + 1,
        "cross_check_evidence",
        {
            "evidence_ids": list(runtime.selected_evidence_ids),
            "claim_or_result": {
                "operation_ref": operation_ref,
                "candidate_payload": scenario.canonical_candidate,
            },
        },
    )
    assert repaired.status == "succeeded"
    assert repaired.result["verified"] is True
    assert repaired.result["candidate_repair"]["repair_verified"] is True
    assert runtime.event_log == scenario.expected_host_events


def test_public_decision_contract_does_not_disclose_partial_probe_sequence() -> None:
    context = _omega()
    scenario = _scenario(context, "insufficient_evidence")
    public = public_submechanism_contract(scenario)

    assert "partial_support_probe_contract" not in public
    assert public["contract_type"] == "typed_host_state_decision"
    assert (
        public["host_feedback_contract"][
            "otherwise_select_the_next_action_from_public_tool_schemas"
        ]
        is True
    )


def test_public_mechanism_non_disclosure_fails_closed() -> None:
    scenario = SimpleNamespace(
        intervention_kind="post_complete_cost",
        public_resolution_hint="Stop immediately after verified completion.",
    )

    def task(public_payload: dict[str, Any]) -> Any:
        public = SimpleNamespace(model_dump=lambda **_: public_payload)
        return SimpleNamespace(
            artifact=SimpleNamespace(task=SimpleNamespace(public=public)),
            submechanism_id="finance.stopping.post_complete_cost",
            parent_mechanism_id="stopping_control",
            scenario=scenario,
        )

    assert _public_mechanism_nondisclosed(
        task(
            {
                "instruction": "Use the typed Host state to decide the next action.",
                "metadata": {
                    "capability_decision_contract": {
                        "contract_type": "typed_host_state_decision",
                        "oracle_mechanism_identity_disclosed": False,
                    }
                },
            }
        )
    )
    assert not _public_mechanism_nondisclosed(
        task(
            {
                "instruction": "Exercise finance.stopping.post_complete_cost.",
                "metadata": {"intervention_kind": "post_complete_cost"},
            }
        )
    )


def test_insufficient_evidence_emits_executable_typed_continuation() -> None:
    context = _omega()
    scenario = _scenario(context, "insufficient_evidence")
    runtime = _runtime(context, scenario)
    first = scenario.evidence_roles[0]

    selected = _call(
        runtime,
        1,
        "query_structured_fact",
        {
            "subject_alias": first.subject_alias,
            "metric_alias": first.metric_alias,
            "period_label": first.period_label,
            "public_filters": {},
        },
    )

    assert selected.status == "succeeded"
    runtime.manifest.tools_by_id["query_structured_fact"].validate_output(selected.result)
    state = selected.result["completion_state"]
    assert state["complete"] is False
    assert "host_event" not in state
    assert selected.host_events == (scenario.expected_host_events[0],)
    completed = selected
    remaining = {
        (
            role.subject_alias,
            role.metric_alias,
            role.period_label,
        )
        for role in scenario.evidence_roles
        if role.evidence_id not in runtime.selected_evidence_ids
    }
    index = 2
    while remaining:
        required = state["required_prerequisite_action"]
        arguments = required["arguments"]
        role_key = (
            arguments["subject_alias"],
            arguments["metric_alias"],
            arguments["period_label"],
        )
        assert required["action"] == "retrieve_missing_evidence_role"
        assert required["tool_id"] == "query_structured_fact"
        assert arguments["public_filters"] == {}
        assert role_key in remaining
        completed = _call(runtime, index, required["tool_id"], required["arguments"])
        remaining = {
            (
                role.subject_alias,
                role.metric_alias,
                role.period_label,
            )
            for role in scenario.evidence_roles
            if role.evidence_id not in runtime.selected_evidence_ids
        }
        if remaining:
            state = completed.result["completion_state"]
        index += 1

    assert completed.status == "succeeded"
    assert completed.result["submechanism_resolution"] == {"resolved": True}
    assert completed.host_events == (scenario.expected_host_events[1],)
    assert runtime.event_log == scenario.expected_host_events


def test_incomplete_continue_requires_agent_to_select_the_next_typed_action() -> None:
    context = _omega()
    scenario = _scenario(context, "incomplete_continue")
    runtime = _runtime(context, scenario)
    first = scenario.evidence_roles[0]

    selected = _call(
        runtime,
        1,
        "query_structured_fact",
        {
            "subject_alias": first.subject_alias,
            "metric_alias": first.metric_alias,
            "period_label": first.period_label,
            "public_filters": {},
        },
    )

    state = selected.result["completion_state"]
    assert state["complete"] is False
    assert state["required_prerequisite_action"] is None
    missing = state["missing_roles"][0]
    completed = _call(
        runtime,
        2,
        "query_structured_fact",
        {
            "subject_alias": missing["subject_alias"],
            "metric_alias": missing["metric_alias"],
            "period_label": missing["period_label"],
            "public_filters": {},
        },
    )
    assert completed.status == "succeeded"
    assert completed.result["submechanism_resolution"] == {"resolved": True}
    assert completed.host_events == (scenario.expected_host_events[1],)


def test_evidence_conflict_emits_executable_normalization_action() -> None:
    context = _omega()
    scenario = _scenario(context, "evidence_conflict")
    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)

    index, conflict = _verify(runtime, index, operation_ref)

    assert conflict.status == "failed"
    retry = conflict.result["retry_contract"]
    required = retry["required_prerequisite_action"]
    assert required["action"] == "normalize_selected_evidence"
    assert required["tool_id"] == "normalize_metric_unit_period"
    assert required["arguments"]["evidence_ids"] == list(runtime.selected_evidence_ids)
    assert set(required["arguments"]["target_definition"]) == {
        "definition_id",
        "time_basis",
        "frequency",
    }

    normalized = _call(runtime, index + 1, required["tool_id"], required["arguments"])
    assert normalized.status == "succeeded"
    _, verified = _verify(runtime, index + 1, operation_ref)
    assert verified.status == "succeeded"
    assert verified.result["verified"] is True
    assert runtime.event_log == scenario.expected_host_events


def test_unresolved_conflict_requires_agent_tool_selection() -> None:
    context = _omega()
    scenario = _scenario(context, "unresolved_conflict_cannot_stop")
    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)

    index, conflict = _verify(runtime, index, operation_ref)

    retry = conflict.result["retry_contract"]
    assert retry["required_prerequisite_action"] is None
    assert "required_next_tools" not in retry
    assert "Do not repeat verification" in retry["decision_rule"]
    normalized = _call(
        runtime,
        index + 1,
        "normalize_metric_unit_period",
        {
            "evidence_ids": list(runtime.selected_evidence_ids),
            "target_definition": {
                "definition_id": context.public_corpus.evidence[0].definition.definition_id,
                "time_basis": context.public_corpus.evidence[0].temporal_context.basis,
                "frequency": context.public_corpus.evidence[0].temporal_context.frequency,
            },
        },
    )
    assert normalized.status == "succeeded"
    _, verified = _verify(runtime, index + 1, operation_ref)
    assert verified.status == "succeeded"
    assert verified.result["verified"] is True


def test_contextual_entity_scope_requires_matching_query_then_cross_check() -> None:
    context = _omega()
    roles = evidence_roles_from_items(tuple(context.public_corpus.evidence))
    decision = FinanceStoppingShapeDecisionContract(
        contract_kind="matched_contextual_resolution_choice",
        observed_conflict_signal=(
            "The requested relation is not warranted by the current evidence state."
        ),
        oracle_conflict_dimension="entity_scope_alignment",
        available_resolution_actions=(
            FinanceStoppingResolutionAction(
                tool_id="normalize_metric_unit_period",
                applicable_when="establish a shared measurement basis",
            ),
            FinanceStoppingResolutionAction(
                tool_id="open_document",
                applicable_when="inspect unresolved document authority",
            ),
            FinanceStoppingResolutionAction(
                tool_id="query_structured_fact",
                applicable_when="retrieve an observation for the required entity scope",
            ),
        ),
        resolution_step_count=2,
    )
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.contextual.entity_scope",
        parent_mechanism_id="finance.test.parent",
        intervention_kind="unresolved_conflict_cannot_stop",
        expected_host_events=("observe:context", "resolve:context"),
        evidence_roles=roles,
        public_resolution_hint="Choose from the public Evidence state.",
        stopping_shape_decision_contract=decision,
    )
    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)
    index, conflict = _verify(runtime, index, operation_ref)
    assert conflict.status == "failed"

    wrong = _call(
        runtime,
        index + 1,
        "normalize_metric_unit_period",
        {
            "evidence_ids": list(runtime.selected_evidence_ids),
            "target_definition": {
                "definition_id": context.public_corpus.evidence[0].definition.definition_id,
                "time_basis": context.public_corpus.evidence[0].temporal_context.basis,
                "frequency": context.public_corpus.evidence[0].temporal_context.frequency,
            },
        },
    )
    assert wrong.status == "failed"
    assert wrong.error_code == "submechanism_resolution_action_required"

    role = roles[0]
    resolved = _call(
        runtime,
        index + 2,
        "query_structured_fact",
        {
            "subject_alias": role.subject_alias,
            "metric_alias": role.metric_alias,
            "period_label": role.period_label,
            "public_filters": {},
        },
    )
    assert resolved.status == "succeeded"
    _, verified = _verify(runtime, index + 2, operation_ref)
    assert verified.status == "succeeded"
    assert verified.result["verified"] is True
    assert runtime.event_log == scenario.expected_host_events


def _observed_record_from_role(
    context: Any,
    role: Any,
    *,
    subject_alias: str | None = None,
    period_label: str | None = None,
) -> FinanceStoppingObservedRecord:
    item = next(
        value for value in context.public_corpus.evidence if value.evidence_id == role.evidence_id
    )
    temporal = item.temporal_context
    return FinanceStoppingObservedRecord(
        subject_alias=subject_alias or role.subject_alias,
        metric_alias=role.metric_alias,
        temporal_identity=FinanceStoppingTemporalIdentity(
            label=period_label or role.period_label,
            valid_from=temporal.valid_from.isoformat() if temporal.valid_from else None,
            valid_to=temporal.valid_to.isoformat() if temporal.valid_to else None,
            observed_at=temporal.observed_at.isoformat() if temporal.observed_at else None,
        ),
        source_id=item.source.source_id,
        definition_id=item.definition.definition_id,
        measurement_context=FinanceStoppingMeasurementContext(
            unit=getattr(item.payload, "unit", None),
            currency=getattr(item.payload, "currency", None),
        ),
    )


def _state_actions() -> tuple[FinanceStoppingResolutionAction, ...]:
    return (
        FinanceStoppingResolutionAction(
            tool_id="normalize_metric_unit_period",
            applicable_when="establish a shared reporting or measurement basis",
        ),
        FinanceStoppingResolutionAction(
            tool_id="open_document",
            applicable_when="inspect document authority when provenance is uncertain",
        ),
        FinanceStoppingResolutionAction(
            tool_id="query_structured_fact",
            applicable_when="retrieve a requested subject or period observation",
        ),
    )


def test_conditional_dependency_probe_output_passes_frozen_manifest_contract() -> None:
    context = _omega()
    roles = evidence_roles_from_items(tuple(context.public_corpus.evidence))
    assert len(roles) >= 2
    unresolved = roles[1]
    decision = FinanceStoppingShapeDecisionContract(
        contract_kind="conditional_dependency_observation_required",
        dependency_rule="Probe the Archive, then select the required public option.",
        dependency_decoy_option=FinanceStoppingDependencyOption(
            option_id="option:decoy",
            subject_alias=unresolved.subject_alias,
            metric_alias=unresolved.metric_alias,
            period_label="not-the-required-period",
        ),
        resolution_step_count=2,
    )
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.partial.conditional",
        parent_mechanism_id="finance.test.parent",
        intervention_kind="incomplete_continue",
        expected_host_events=("observe:partial", "resolve:partial"),
        evidence_roles=roles,
        public_resolution_hint="Follow the public dependency observation.",
        stopping_shape_decision_contract=decision,
    )
    runtime = _runtime(context, scenario)
    first = roles[0]
    selected = _call(
        runtime,
        1,
        "query_structured_fact",
        {
            "subject_alias": first.subject_alias,
            "metric_alias": first.metric_alias,
            "period_label": first.period_label,
            "public_filters": {},
        },
    )
    probe = selected.result["completion_state"]["dependency_probe"]
    observed = _call(runtime, 2, probe["tool_id"], probe["arguments"])

    assert observed.status == "succeeded"
    assert "dependency_branch_observation" in observed.result
    runtime.manifest.tools_by_id["search_archive"].validate_output(observed.result)

    index = 3
    resolved = observed
    for required in roles[1:]:
        resolved = _call(
            runtime,
            index,
            "query_structured_fact",
            {
                "subject_alias": required.subject_alias,
                "metric_alias": required.metric_alias,
                "period_label": required.period_label,
                "public_filters": {},
            },
        )
        assert resolved.status == "succeeded"
        index += 1
    assert runtime.event_log == scenario.expected_host_events


def test_v25_40_contextual_state_requires_the_public_required_record() -> None:
    context = _omega()
    roles = evidence_roles_from_items(tuple(context.public_corpus.evidence))
    required = _observed_record_from_role(context, roles[0])
    state = FinanceStoppingObservedEvidenceState(
        observed_record=required.model_copy(update={"subject_alias": "entity:neighbor"}),
        required_record=required,
    )
    decision = FinanceStoppingShapeDecisionContract(
        schema_version=FINANCE_STOPPING_SHAPE_DECISION_V4_VERSION,
        contract_kind="matched_contextual_evidence_state_choice_two_step",
        observed_conflict_signal="Two public records differ in one identity component.",
        observed_evidence_state=state,
        oracle_conflict_dimension="entity_scope_alignment",
        available_resolution_actions=_state_actions(),
        resolution_step_count=2,
    )
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.contextual.state",
        parent_mechanism_id="finance.test.parent",
        intervention_kind="unresolved_conflict_cannot_stop",
        expected_host_events=("observe:context", "resolve:context"),
        evidence_roles=roles,
        public_resolution_hint="Choose from the public Evidence state.",
        stopping_shape_decision_contract=decision,
    )
    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)
    index, conflict = _verify(runtime, index, operation_ref)

    assert conflict.result["retry_contract"]["observed_evidence_state"] == state.model_dump(
        mode="json"
    )
    wrong_role = roles[-1]
    wrong = _call(
        runtime,
        index + 1,
        "query_structured_fact",
        {
            "subject_alias": "entity:definitely-wrong",
            "metric_alias": wrong_role.metric_alias,
            "period_label": wrong_role.period_label,
            "public_filters": {},
        },
    )
    assert wrong.status == "failed"
    assert wrong.error_code == "contextual_resolution_query_mismatch"

    resolved = _call(
        runtime,
        index + 2,
        "query_structured_fact",
        {
            "subject_alias": required.subject_alias,
            "metric_alias": required.metric_alias,
            "period_label": required.period_label,
            "public_filters": {},
        },
    )
    assert resolved.status == "succeeded"
    _, verified = _verify(runtime, index + 2, operation_ref)
    assert verified.status == "succeeded"
    assert runtime.event_log == scenario.expected_host_events


def test_v25_40_temporal_conflict_requires_query_instead_of_constant_normalization() -> None:
    context = _omega()
    roles = evidence_roles_from_items(tuple(context.public_corpus.evidence))
    required = _observed_record_from_role(context, roles[0])
    observed_temporal = required.temporal_identity.model_copy(
        update={"label": f"{required.period_label} alternate"}
    )
    state = FinanceStoppingObservedEvidenceState(
        observed_record=required.model_copy(update={"temporal_identity": observed_temporal}),
        required_record=required,
    )
    decision = FinanceStoppingShapeDecisionContract(
        schema_version=FINANCE_STOPPING_SHAPE_DECISION_V4_VERSION,
        contract_kind="single_conflict_evidence_state_choice_one_step",
        observed_conflict_signal="Two public records differ in one identity component.",
        observed_evidence_state=state,
        oracle_conflict_dimension="temporal_alignment",
        available_resolution_actions=_state_actions(),
        resolution_step_count=1,
    )
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.conflict.temporal",
        parent_mechanism_id="finance.test.parent",
        intervention_kind="evidence_conflict",
        expected_host_events=("observe:conflict", "resolve:conflict"),
        evidence_roles=roles,
        public_resolution_hint="Choose from the public Evidence state.",
        stopping_shape_decision_contract=decision,
    )
    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)
    index, _ = _verify(runtime, index, operation_ref)

    normalized = _call(
        runtime,
        index + 1,
        "normalize_metric_unit_period",
        {
            "evidence_ids": list(runtime.selected_evidence_ids),
            "target_definition": {},
        },
    )
    assert normalized.status == "failed"
    assert normalized.error_code == "submechanism_resolution_action_required"

    resolved = _call(
        runtime,
        index + 2,
        "query_structured_fact",
        {
            "subject_alias": required.subject_alias,
            "metric_alias": required.metric_alias,
            "period_label": required.period_label,
            "public_filters": {},
        },
    )
    assert resolved.status == "succeeded"
    assert runtime.event_log == scenario.expected_host_events


def test_v25_41_contextual_query_is_causal_before_evidence_selection() -> None:
    context = _omega()
    roles = evidence_roles_from_items(tuple(context.public_corpus.evidence))
    required = _observed_record_from_role(context, roles[0])
    state = FinanceStoppingObservedEvidenceState(
        observed_record=required.model_copy(update={"subject_alias": "entity:neighbor"}),
        required_record=required,
    )
    decision = FinanceStoppingShapeDecisionContract(
        contract_kind="matched_contextual_evidence_state_choice_two_step",
        observed_conflict_signal="Two public records differ in one identity component.",
        observed_evidence_state=state,
        oracle_conflict_dimension="entity_scope_alignment",
        state_activation_phase="before_required_evidence_selection",
        available_resolution_actions=_state_actions(),
        resolution_step_count=2,
    )
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.contextual.causal",
        parent_mechanism_id="finance.test.parent",
        intervention_kind="unresolved_conflict_cannot_stop",
        expected_host_events=("observe:context", "resolve:context"),
        evidence_roles=roles,
        public_resolution_hint="Choose from the active public Evidence state.",
        stopping_shape_decision_contract=decision,
    )
    runtime = _runtime(context, scenario)

    assert runtime.event_log == (scenario.expected_host_events[0],)
    assert runtime.selected_evidence_ids == ()
    public_decision = public_submechanism_contract(scenario)["stopping_shape_decision_contract"]
    assert public_decision["state_activation_phase"] == "before_required_evidence_selection"

    wrong = _call(
        runtime,
        1,
        "normalize_metric_unit_period",
        {"evidence_ids": [], "target_definition": {}},
    )
    assert wrong.status == "failed"
    assert wrong.error_code == "submechanism_resolution_action_required"
    assert wrong.host_events == (scenario.expected_host_events[0],)
    assert "host_event_sequence" not in wrong.result
    assert "submechanism_activation" not in wrong.result

    required_item = runtime.evidence_item(roles[0].evidence_id)
    assert required_item.subject.name != required.subject_alias
    resolved = _call(
        runtime,
        2,
        "query_structured_fact",
        {
            "subject_alias": required_item.subject.name,
            "metric_alias": required.metric_alias,
            "period_label": required.period_label,
            "public_filters": {},
        },
    )
    assert resolved.status == "succeeded"

    index = 2
    for role in roles:
        if role.evidence_id in runtime.selected_evidence_ids:
            continue
        index += 1
        selected = _call(
            runtime,
            index,
            "query_structured_fact",
            {
                "subject_alias": role.subject_alias,
                "metric_alias": role.metric_alias,
                "period_label": role.period_label,
                "public_filters": {},
            },
        )
        assert selected.status == "succeeded"
    index, operation_ref = _calculate(runtime, index)
    _, verified = _verify(runtime, index, operation_ref)

    assert verified.status == "succeeded"
    assert verified.result["verified"] is True
    assert runtime.event_log == scenario.expected_host_events


def test_v25_41_temporal_query_resolves_before_required_selection() -> None:
    context = _omega()
    roles = evidence_roles_from_items(tuple(context.public_corpus.evidence))
    required = _observed_record_from_role(context, roles[0])
    state = FinanceStoppingObservedEvidenceState(
        observed_record=required.model_copy(
            update={
                "temporal_identity": required.temporal_identity.model_copy(
                    update={"label": f"{required.period_label} alternate"}
                )
            }
        ),
        required_record=required,
    )
    decision = FinanceStoppingShapeDecisionContract(
        contract_kind="single_conflict_evidence_state_choice_one_step",
        observed_conflict_signal="Two public records differ in one identity component.",
        observed_evidence_state=state,
        oracle_conflict_dimension="temporal_alignment",
        state_activation_phase="before_required_evidence_selection",
        available_resolution_actions=_state_actions(),
        resolution_step_count=1,
    )
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.conflict.temporal.causal",
        parent_mechanism_id="finance.test.parent",
        intervention_kind="evidence_conflict",
        expected_host_events=("observe:conflict", "resolve:conflict"),
        evidence_roles=roles,
        public_resolution_hint="Resolve the active temporal Evidence state.",
        stopping_shape_decision_contract=decision,
    )
    runtime = _runtime(context, scenario)

    required_item = runtime.evidence_item(roles[0].evidence_id)
    resolved_call = AgentToolCall(
        call_index=1,
        tool_id="query_structured_fact",
        arguments={
            "subject_alias": required_item.subject.name,
            "metric_alias": required.metric_alias,
            "period_label": required.period_label,
            "public_filters": {},
        },
    )
    resolved = runtime.execute(resolved_call)
    runtime.manifest.tools_by_id[resolved_call.tool_id].validate_output(resolved.result)
    assert resolved.host_events == scenario.expected_host_events
    assert "host_event_sequence" not in resolved.result
    assert "submechanism_activation" not in resolved.result
    resolved_observation = make_agent_tool_observation(
        environment_manifest_id=runtime.manifest.manifest_id,
        call=resolved_call,
        result=resolved,
        observation_time_hash="observation-time:v25-42-causal",
    )

    assert resolved.status == "succeeded"
    assert (
        _host_event_sequence(
            (resolved_observation,),
            scenario.expected_host_events,
        )
        == scenario.expected_host_events
    )
    assert runtime.event_log == scenario.expected_host_events


def test_v25_41_definition_normalization_blocks_calculation_after_selection() -> None:
    context = _omega()
    roles = evidence_roles_from_items(tuple(context.public_corpus.evidence))
    required = _observed_record_from_role(context, roles[0])
    state = FinanceStoppingObservedEvidenceState(
        observed_record=required.model_copy(update={"definition_id": "definition:observed"}),
        required_record=required,
    )
    decision = FinanceStoppingShapeDecisionContract(
        contract_kind="single_conflict_evidence_state_choice_one_step",
        observed_conflict_signal="Two public records differ in one identity component.",
        observed_evidence_state=state,
        oracle_conflict_dimension="source_definition_compatibility",
        state_activation_phase="after_required_evidence_selection_before_calculation",
        available_resolution_actions=_state_actions(),
        resolution_step_count=1,
    )
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.conflict.definition.causal",
        parent_mechanism_id="finance.test.parent",
        intervention_kind="evidence_conflict",
        expected_host_events=("observe:conflict", "resolve:conflict"),
        evidence_roles=roles,
        public_resolution_hint="Resolve the active definition Evidence state.",
        stopping_shape_decision_contract=decision,
    )
    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)

    premature = _call(
        runtime,
        index + 1,
        "calculator",
        {
            "operator": "lookup",
            "operands": [{"evidence_id": runtime.selected_evidence_ids[0]}],
            "parameters": {},
        },
    )
    assert premature.status == "failed"
    assert premature.error_code == "submechanism_resolution_action_required"

    normalized = _call(
        runtime,
        index + 2,
        "normalize_metric_unit_period",
        {
            "evidence_ids": list(runtime.selected_evidence_ids),
            "target_definition": {
                "definition_id": required.definition_id,
                "time_basis": context.public_corpus.evidence[0].temporal_context.basis,
                "frequency": context.public_corpus.evidence[0].temporal_context.frequency,
            },
        },
    )
    assert normalized.status == "succeeded"
    assert runtime.event_log == scenario.expected_host_events

    index, operation_ref = _calculate(runtime, index + 2)
    _, verified = _verify(runtime, index, operation_ref)
    assert verified.status == "succeeded"
    assert verified.result["verified"] is True


def test_submechanism_replay_and_failed_artifact_preserve_host_observations() -> None:
    context = _omega()
    scenario = _scenario(context, "argument_failure")
    runtime = _runtime(context, scenario)
    call = AgentToolCall(
        call_index=1,
        tool_id="query_structured_fact",
        arguments={
            "subject_alias": scenario.evidence_roles[0].subject_alias,
            "metric_alias": scenario.evidence_roles[0].metric_alias,
            "period_label": scenario.evidence_roles[0].period_label,
            "public_filters": {},
        },
    )
    result = runtime.execute(call)
    observation = make_agent_tool_observation(
        environment_manifest_id=runtime.manifest.manifest_id,
        call=call,
        result=result,
        observation_time_hash="observation-time:test",
    )

    assert (
        _replay_observations(
            context.public_corpus,
            runtime.manifest,
            (observation,),
            submechanism_scenario=scenario,
        )
        == ()
    )

    artifact = _make_failure_artifact(
        task=context.task,
        mode="autonomous_agent",
        environment_manifest_id=runtime.manifest.manifest_id,
        protocol_profile_hash="protocol:test",
        plan=None,
        decisions=(),
        observations=(observation,),
        telemetry=(),
        failure_message="bounded model failure",
    )
    record = SimpleNamespace(observations=(), failure_artifact=artifact)
    assert _all_observations(record) == (observation,)


def test_uncertain_source_requires_public_provenance_resolution() -> None:
    context = _omega()
    scenario = _scenario(context, "uncertain_source_coverage")
    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)
    index, uncertain = _verify(runtime, index, operation_ref)
    assert uncertain.status == "succeeded"
    assert uncertain.result["verified"] is False
    assert uncertain.result["completion_state"]["complete"] is False
    assert "host_event" not in uncertain.result["completion_state"]
    assert uncertain.host_events == (scenario.expected_host_events[0],)

    first = scenario.evidence_roles[0]
    search = _call(
        runtime,
        index + 1,
        "search_archive",
        {
            "query": f"{first.subject_alias} {first.metric_alias}",
            "limit": 12,
        },
    )
    assert search.status == "succeeded"
    locator = search.result["matches"][0]["public_locator"]

    opened = _call(
        runtime,
        index + 2,
        "open_document",
        {"public_locator": locator},
    )
    assert opened.status == "succeeded"
    runtime.manifest.tools_by_id["open_document"].validate_output(opened.result)
    assert opened.result["submechanism_resolution"] == {"resolved": True}
    assert opened.host_events == (scenario.expected_host_events[1],)

    _, verified = _verify(runtime, index + 2, operation_ref)
    assert verified.status == "succeeded"
    assert verified.result["verified"] is True
    assert runtime.event_log == scenario.expected_host_events


@pytest.mark.parametrize("kind", ["post_complete_error_risk", "post_complete_cost"])
def test_completion_observation_exposes_ordered_host_events(kind: str) -> None:
    context = _omega()
    scenario = _scenario(context, kind)
    runtime = _runtime(context, scenario)
    index = _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)
    index, verified = _verify(runtime, index, operation_ref)

    assert verified.status == "succeeded"
    assert verified.result["verified"] is True
    assert "host_event_sequence" not in verified.result["completion_state"]
    assert "host_event" not in verified.result["completion_state"]
    assert verified.host_events == scenario.expected_host_events
    assessment = verified.result["completion_state"]["additional_action_assessment"]
    assert "additional_action_required" not in assessment
    assert "redundant_action_policy" not in verified.result["completion_state"]
    assert kind not in str(verified.result["completion_state"])
    assert runtime.event_log == scenario.expected_host_events

    blocked = _call(
        runtime,
        index + 1,
        "search_archive",
        {"query": "redundant action", "limit": 1},
    )
    assert blocked.status == "failed"
    assert blocked.result["completion_state"]["complete"] is True


def test_v25_27_task_contract_rejects_non_easy_artifact() -> None:
    task = CapabilitySubmechanismTask.model_construct(
        base_tier=BOUNDARY_BASE_TIER,
        artifact=SimpleNamespace(tier=DifficultyTier.FRONTIER),
    )

    with pytest.raises(ValueError, match="frozen Easy base tier"):
        task.validate_task()


def test_v25_27_task_contract_rejects_missing_answer_projection_contract() -> None:
    context = _omega()
    scenario = _scenario(context, "post_complete_cost")
    projection = {"evidence:left": "Left", "evidence:right": "Right"}
    artifact = SimpleNamespace(
        tier=BOUNDARY_BASE_TIER,
        answer_projection=projection,
        projected_expected_output={"higher_ref": "Right", "difference": "2"},
        task=SimpleNamespace(
            public=SimpleNamespace(
                metadata={PUBLIC_SUBMECHANISM_METADATA_KEY: public_submechanism_contract(scenario)},
                instruction="Return the public labels.",
            ),
            oracle=SimpleNamespace(
                selection_contract={
                    FINANCE_SUBMECHANISM_ORACLE_KEY: scenario.model_dump(mode="json"),
                    "answer_projection": projection,
                }
            ),
        ),
    )
    task = CapabilitySubmechanismTask.model_construct(
        base_tier=BOUNDARY_BASE_TIER,
        artifact=artifact,
        scenario=scenario,
        submechanism_id=scenario.submechanism_id,
        parent_mechanism_id=scenario.parent_mechanism_id,
    )

    with pytest.raises(ValueError, match="projected public answer contract"):
        task.validate_task()


def test_v25_27_population_contract_rejects_non_easy_identity() -> None:
    population = CapabilitySubmechanismPopulation.model_construct(
        base_tier=DifficultyTier.FRONTIER,
        tasks=(),
    )

    with pytest.raises(ValueError, match="freeze the Easy base tier"):
        population.validate_population()


def test_v25_28_flash_contract_and_report_reject_non_easy_identity() -> None:
    contract = FinanceSubmechanismFlashContract.model_construct(
        source_base_tier=DifficultyTier.FRONTIER,
        tasks=(),
    )
    report = FinanceSubmechanismFlashReport.model_construct(
        source_base_tier=DifficultyTier.FRONTIER,
    )

    with pytest.raises(ValueError, match="requires the frozen Easy base tier"):
        contract.validate_contract()
    with pytest.raises(ValueError, match="does not identify the Easy base tier"):
        report.validate_report()
