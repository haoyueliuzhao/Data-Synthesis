from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FinanceCapabilitySubmechanismRuntime,
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
        "expected_host_events": (f"{kind}:observed", f"{kind}:resolved"),
        "evidence_roles": roles,
        "public_resolution_hint": f"Resolve the typed {kind} branch.",
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
    assert all("evidence:" not in str(value) for value in public.values())


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
    first = scenario.evidence_roles[0]
    search = _call(
        runtime,
        1,
        "search_archive",
        {
            "query": f"{first.subject_alias} {first.metric_alias}",
            "limit": 12,
        },
    )
    assert search.status == "succeeded"
    locator = search.result["matches"][0]["public_locator"]

    index = 1 + _select_all(runtime, scenario)
    index, operation_ref = _calculate(runtime, index)
    index, uncertain = _verify(runtime, index, operation_ref)
    assert uncertain.status == "succeeded"
    assert uncertain.result["verified"] is False
    assert uncertain.result["completion_state"]["host_event"] == scenario.expected_host_events[0]

    opened = _call(
        runtime,
        index + 1,
        "open_document",
        {"public_locator": locator},
    )
    assert opened.status == "succeeded"
    runtime.manifest.tools_by_id["open_document"].validate_output(opened.result)
    assert (
        opened.result["submechanism_resolution"]["host_event"] == scenario.expected_host_events[1]
    )

    _, verified = _verify(runtime, index + 1, operation_ref)
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
    assert runtime.event_log == scenario.expected_host_events

    blocked = _call(
        runtime,
        index + 1,
        "search_archive",
        {"query": "redundant action", "limit": 1},
    )
    assert blocked.status == "failed"
    assert blocked.result["completion_state"]["complete"] is True
