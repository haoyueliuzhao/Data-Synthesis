from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_SUBMECHANISM_ORACLE_KEY,
    FinanceCapabilitySubmechanismRuntime,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
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
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    BOUNDARY_BASE_TIER,
    PUBLIC_SUBMECHANISM_METADATA_KEY,
    CapabilitySubmechanismPopulation,
    CapabilitySubmechanismTask,
    _public_mechanism_nondisclosed,
)
from trusted_synthesis.runtime.agent.iterative import (
    IterativeAgentFailureArtifact,
    iterative_agent_failure_artifact_id,
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
    assert state["host_event"] == scenario.expected_host_events[0]
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
    assert (
        completed.result["submechanism_resolution"]["host_event"]
        == (scenario.expected_host_events[1])
    )
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
    assert (
        completed.result["submechanism_resolution"]["host_event"]
        == (scenario.expected_host_events[1])
    )


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

    values = {
        "task_id": context.task.task_id,
        "mode": "autonomous_agent",
        "environment_manifest_id": runtime.manifest.manifest_id,
        "protocol_profile_hash": "protocol:test",
        "plan": None,
        "decisions": (),
        "observations": (observation,),
        "telemetry": (),
        "failure_message": "bounded model failure",
        "stop_rejections": (),
    }
    provisional = IterativeAgentFailureArtifact.model_construct(artifact_id="pending", **values)
    artifact = IterativeAgentFailureArtifact(
        artifact_id=iterative_agent_failure_artifact_id(provisional), **values
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
    assert uncertain.result["completion_state"]["host_event"] == scenario.expected_host_events[0]
    assert uncertain.result["completion_state"]["complete"] is False

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
    assert (
        opened.result["submechanism_resolution"]["host_event"] == scenario.expected_host_events[1]
    )

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
    assert verified.result["completion_state"]["host_event_sequence"] == list(
        scenario.expected_host_events
    )
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
