from __future__ import annotations

import hashlib
from typing import Any

import pytest

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.operations.program import TaskProgramOracleVerifier
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.domains.finance.agent_tools import (
    finance_archive_agent_tool_specs,
    make_finance_archive_agent_tool_manifest,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
    FinanceCompletionRole,
    _matches_subject,
    finance_runtime_snapshot_hash,
    make_candidate_verification_scenario,
    make_finance_typed_recovery_scenario,
    make_state_dependent_stopping_scenario,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FinanceIterativeAgentVerifier,
    _apply_reference_projection,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    compile_finance_agent_case,
)
from trusted_synthesis.runtime.agent import (
    IterativeAgentSolver,
    PublicAgentStateCondition,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolCall


class _ScriptedClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = iter(payloads)
        self._config = AgentModelConfig(
            provider="fixture",
            endpoint="https://fixture.invalid/v1/chat/completions",
            model="fixture-model",
            api_key_env="FIXTURE_API_KEY",
            contract_repair_attempts=0,
        )
        self.prompts: list[str] = []

    @property
    def config(self) -> AgentModelConfig:
        return self._config

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        self.prompts.append(prompt)
        payload = next(self._payloads)
        return payload, ModelCallTelemetry(
            provider="fixture",
            endpoint_host="fixture.invalid",
            model_requested="fixture-model",
            model_selected="fixture-model",
            response_model="fixture-model",
            request_hash=hashlib.sha256(prompt.encode()).hexdigest(),
            response_hash=hashlib.sha256(repr(payload).encode()).hexdigest(),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            prompt_tokens=6,
            completion_tokens=4,
            total_tokens=10,
        )


def _omega():
    case = compile_finance_agent_case(build_finance_counterfactual_case(2))
    contract_compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        contract_compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
        source_grounding_verifier=case.source_grounding_verifier,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    return compiled.joint_compilation.omega


def _manifest(context):
    corpus = context.public_corpus
    return make_finance_archive_agent_tool_manifest(
        environment_id="finance_agent_test",
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        archive_snapshot_id="finance_agent_test_snapshot",
        archive_snapshot_hash=corpus.corpus_hash,
        maximum_tool_calls=12,
        maximum_failed_tool_calls=2,
    )


def _tool_decision(tool_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_type": "tool_call",
        "rationale_summary": f"Use {tool_id} on public Archive data.",
        "tool_id": tool_id,
        "arguments": arguments,
        "answer": None,
        "cited_evidence_ids": [],
    }


def _model_payloads(context, manifest):
    runtime = FinanceArchiveInteractiveToolRuntime(context.public_corpus, manifest)
    task = context.task
    evidence_by_id = context.public_corpus.by_id()
    payloads: list[dict[str, Any]] = [
        {
            "plan_summary": "Search, select, calculate, verify, and answer.",
            "subgoal_labels": ["search", "select", "calculate", "verify"],
            "stop_conditions": ["all cited facts and the computed result are verified"],
        }
    ]
    call_index = 1

    def execute(tool_id: str, arguments: dict[str, Any]):
        nonlocal call_index
        payloads.append(_tool_decision(tool_id, arguments))
        result = runtime.execute(
            AgentToolCall(
                call_index=call_index,
                tool_id=tool_id,
                arguments=arguments,
            )
        )
        call_index += 1
        assert result.status == "succeeded", result
        return result

    execute(
        "search_archive",
        {
            "query": task.public.instruction,
            "limit": 12,
        },
    )
    for evidence_id in task.oracle.gold_evidence_ids:
        item = evidence_by_id[evidence_id]
        execute(
            "query_structured_fact",
            {
                "subject_alias": item.subject.name,
                "metric_alias": item.predicate,
                "period_label": item.temporal_context.label,
                "public_filters": {"source_id": item.source.source_id},
            },
        )

    operation_refs: dict[str, str] = {}
    for node in task.oracle.task_program.nodes:
        operands: list[Any] = []
        for ref in node.input_refs:
            if ref.kind == InputRefKind.EVIDENCE:
                operands.append({"evidence_id": ref.ref_id})
            else:
                operand: dict[str, Any] = {
                    "operation_ref": operation_refs[ref.ref_id],
                }
                if ref.selector:
                    operand["selector"] = ref.selector
                operands.append(operand)
        result = execute(
            "calculator",
            {
                "operator": node.operator_id,
                "operands": operands,
                "parameters": node.parameters,
            },
        )
        operation_refs[node.node_id] = result.result["result"]["operation_ref"]

    final_operation_ref = operation_refs[task.oracle.task_program.output_node_id]
    execute(
        "cross_check_evidence",
        {
            "evidence_ids": list(task.oracle.gold_evidence_ids),
            "claim_or_result": {"operation_ref": final_operation_ref},
        },
    )
    expected = TaskProgramOracleVerifier(default_registry()).derive_expected(
        task.oracle.task_program,
        evidence_by_id,
    )
    answer = CandidateAnswerNormalizer().normalize_oracle(
        task,
        expected.final_output,
        tuple(evidence_by_id[item] for item in task.oracle.gold_evidence_ids),
        node_outputs=expected.node_outputs,
    )
    payloads.append(
        {
            "decision_type": "final_answer",
            "rationale_summary": "The selected facts and replayed calculation support the answer.",
            "tool_id": None,
            "arguments": None,
            "answer": answer,
            "cited_evidence_ids": list(task.oracle.gold_evidence_ids),
        }
    )
    return payloads, tuple(item["tool_id"] for item in payloads[1:-1]), answer


def test_finance_archive_runtime_requires_discovery_and_selected_lineage() -> None:
    context = _omega()
    runtime = FinanceArchiveInteractiveToolRuntime(context.public_corpus, _manifest(context))
    first = context.public_corpus.evidence[0]
    blocked = runtime.execute(
        AgentToolCall(
            call_index=1,
            tool_id="open_document",
            arguments={"public_locator": "archive://source/not-discovered"},
        )
    )
    assert blocked.status == "failed"
    assert blocked.error_code == "locator_not_discovered"

    search = runtime.execute(
        AgentToolCall(
            call_index=2,
            tool_id="search_archive",
            arguments={"query": f"{first.subject.name} {first.predicate}", "limit": 12},
        )
    )
    assert search.status == "succeeded"
    assert search.result["matches"]
    locator = search.result["matches"][0]["public_locator"]
    opened = runtime.execute(
        AgentToolCall(
            call_index=3,
            tool_id="open_document",
            arguments={"public_locator": locator},
        )
    )
    assert opened.status == "succeeded"
    evidence_id = opened.evidence_ids[0]
    calculated = runtime.execute(
        AgentToolCall(
            call_index=4,
            tool_id="calculator",
            arguments={
                "operator": "lookup",
                "operands": [{"evidence_id": evidence_id}],
                "parameters": {},
            },
        )
    )
    assert calculated.status == "succeeded"
    assert calculated.evidence_ids == (evidence_id,)


def test_structured_fact_query_fails_closed_when_no_fact_matches() -> None:
    context = _omega()
    runtime = FinanceArchiveInteractiveToolRuntime(context.public_corpus, _manifest(context))

    result = runtime.execute(
        AgentToolCall(
            call_index=1,
            tool_id="query_structured_fact",
            arguments={
                "subject_alias": "not-a-real-subject",
                "metric_alias": "not-a-real-metric",
                "period_label": "not-a-real-period",
                "public_filters": {},
            },
        )
    )

    assert result.status == "failed"
    assert result.error_code == "structured_query_no_match"
    assert result.evidence_ids == ()


def test_typed_recovery_requires_a_changed_public_selector() -> None:
    context = _omega()
    item = context.public_corpus.evidence[0]
    scenario = make_finance_typed_recovery_scenario(
        scope_identity="test:typed-recovery",
        mismatch_fields=("subject",),
    )
    manifest = make_finance_archive_agent_tool_manifest(
        environment_id="finance_agent_recovery_test",
        corpus_id=context.public_corpus.corpus_id,
        corpus_hash=context.public_corpus.corpus_hash,
        archive_snapshot_id="finance_agent_recovery_snapshot",
        archive_snapshot_hash=finance_runtime_snapshot_hash(
            context.public_corpus.corpus_hash,
            scenario,
        ),
        maximum_tool_calls=12,
        maximum_failed_tool_calls=2,
    )
    runtime = FinanceArchiveInteractiveToolRuntime(
        context.public_corpus,
        manifest,
        recovery_scenario=scenario,
    )
    first_arguments = {
        "subject_alias": item.subject.name,
        "metric_alias": item.predicate,
        "period_label": item.temporal_context.label,
        "public_filters": {"source_id": item.source.source_id},
    }
    first = runtime.execute(
        AgentToolCall(
            call_index=1,
            tool_id="query_structured_fact",
            arguments=first_arguments,
        )
    )
    repeated = runtime.execute(
        AgentToolCall(
            call_index=2,
            tool_id="query_structured_fact",
            arguments=first_arguments,
        )
    )
    corrected = runtime.execute(
        AgentToolCall(
            call_index=3,
            tool_id="query_structured_fact",
            arguments={
                **first_arguments,
                "subject_alias": item.subject.subject_id,
            },
        )
    )

    assert first.status == "failed"
    assert first.error_code == "typed_selector_requires_refinement"
    retry_contract = first.result["retry_contract"]
    assert retry_contract["policy"] == "argument_patch_required"
    assert retry_contract["maximum_identical_replays"] == 0
    assert retry_contract["suggested_argument_patch"]
    assert repeated.status == "failed"
    assert repeated.error_code == "typed_selector_not_revised"
    assert repeated.result["retry_contract"]["policy"] == "selector_revision_required"
    assert corrected.status == "succeeded"
    assert item.evidence_id in corrected.evidence_ids


def _scenario_manifest(context, scenario):
    corpus = context.public_corpus
    return make_finance_archive_agent_tool_manifest(
        environment_id=f"finance_agent_scenario_test:{scenario.scenario_id}",
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        archive_snapshot_id="finance_agent_scenario_snapshot",
        archive_snapshot_hash=finance_runtime_snapshot_hash(
            corpus.corpus_hash,
            None,
            scenario,
        ),
        maximum_tool_calls=12,
        maximum_failed_tool_calls=2,
    )


def _select_fact(runtime, item, call_index: int):
    return runtime.execute(
        AgentToolCall(
            call_index=call_index,
            tool_id="query_structured_fact",
            arguments={
                "subject_alias": item.subject.name,
                "metric_alias": item.predicate,
                "period_label": item.temporal_context.label,
                "public_filters": {"source_id": item.source.source_id},
            },
        )
    )


def test_candidate_verification_scenario_requires_localized_repair() -> None:
    context = _omega()
    item = context.public_corpus.evidence[0]
    expected_payload = {
        "kind": "scalar_observation",
        "value": str(item.payload.value),
        "unit": item.payload.unit,
        "currency": item.payload.currency,
    }
    candidate_payload = {
        **expected_payload,
        "value": str(item.payload.value + 1),
    }
    candidate = {
        "selected_ref": item.evidence_id,
        "payload": candidate_payload,
    }
    scenario = make_candidate_verification_scenario(
        candidate_payload=candidate,
        canonical_candidate_payload={
            "selected_ref": item.evidence_id,
            "payload": expected_payload,
        },
        repair_target_field="payload",
    )
    runtime = FinanceArchiveInteractiveToolRuntime(
        context.public_corpus,
        _scenario_manifest(context, scenario),
        capability_scenario=scenario,
    )
    selected = _select_fact(runtime, item, 1)
    assert selected.status == "succeeded"
    calculated = runtime.execute(
        AgentToolCall(
            call_index=2,
            tool_id="calculator",
            arguments={
                "operator": "lookup",
                "operands": [{"evidence_id": item.evidence_id}],
                "parameters": {},
            },
        )
    )
    assert calculated.status == "succeeded"
    operation_ref = calculated.result["result"]["operation_ref"]
    mismatch = runtime.execute(
        AgentToolCall(
            call_index=3,
            tool_id="cross_check_evidence",
            arguments={
                "evidence_ids": [item.evidence_id],
                "claim_or_result": {"operation_ref": operation_ref},
            },
        )
    )
    assert mismatch.status == "succeeded"
    assert not mismatch.result["verified"]
    assert mismatch.result["candidate_repair"]["localized"]
    assert not mismatch.result["candidate_repair"]["repair_verified"]
    assert mismatch.result["conflicts"][0]["type"] == "candidate_field_mismatch"

    repaired = runtime.execute(
        AgentToolCall(
            call_index=4,
            tool_id="cross_check_evidence",
            arguments={
                "evidence_ids": [item.evidence_id],
                "claim_or_result": {
                    "operation_ref": operation_ref,
                    "candidate_payload": {
                        "selected_ref": item.evidence_id,
                        "payload": expected_payload,
                    },
                },
            },
        )
    )
    assert repaired.status == "succeeded"
    assert repaired.result["verified"], repaired.result["conflicts"]
    assert repaired.result["candidate_repair"]["repair_verified"]


def test_stopping_scenario_exposes_state_and_penalizes_redundant_action() -> None:
    context = _omega()
    first = context.public_corpus.evidence[0]
    first_key = (
        first.subject.subject_id,
        first.predicate,
        first.temporal_context.label,
        first.source.source_id,
    )
    second = next(
        item
        for item in context.public_corpus.evidence[1:]
        if (
            item.subject.subject_id,
            item.predicate,
            item.temporal_context.label,
            item.source.source_id,
        )
        != first_key
    )
    roles = tuple(
        FinanceCompletionRole(
            role_id=f"role_{index}",
            subject_alias=item.subject.name,
            metric_alias=item.predicate,
            period_label=str(item.temporal_context.label),
            public_filters={"source_id": item.source.source_id},
        )
        for index, item in enumerate((first, second), start=1)
    )
    scenario = make_state_dependent_stopping_scenario(required_roles=roles)
    runtime = FinanceArchiveInteractiveToolRuntime(
        context.public_corpus,
        _scenario_manifest(context, scenario),
        capability_scenario=scenario,
    )
    assert _select_fact(runtime, first, 1).status == "succeeded"
    blocked = _select_fact(runtime, second, 2)
    assert blocked.status == "failed"
    assert blocked.error_code == "incomplete_completion_probe_required"
    assert not blocked.result["completion_state"]["complete"]

    incomplete = runtime.execute(
        AgentToolCall(
            call_index=3,
            tool_id="cross_check_evidence",
            arguments={
                "evidence_ids": [first.evidence_id],
                "claim_or_result": {"phase": "partial_state"},
            },
        )
    )
    assert incomplete.status == "succeeded"
    assert not incomplete.result["completion_state"]["complete"]
    assert incomplete.result["completion_state"]["missing_role_ids"] == ["role_2"]

    assert _select_fact(runtime, second, 4).status == "succeeded"
    calculated = runtime.execute(
        AgentToolCall(
            call_index=5,
            tool_id="calculator",
            arguments={
                "operator": "lookup",
                "operands": [{"evidence_id": first.evidence_id}],
                "parameters": {},
            },
        )
    )
    completed = runtime.execute(
        AgentToolCall(
            call_index=6,
            tool_id="cross_check_evidence",
            arguments={
                "evidence_ids": [first.evidence_id, second.evidence_id],
                "claim_or_result": {
                    "operation_ref": calculated.result["result"]["operation_ref"]
                },
            },
        )
    )
    assert completed.status == "succeeded"
    assert completed.result["verified"]
    assert completed.result["completion_state"]["complete"]

    redundant = _select_fact(runtime, first, 7)
    assert redundant.status == "failed"
    assert redundant.error_code == "redundant_action_after_verified_completion"
    assert redundant.result["completion_state"]["redundant_action_cost_applied"]


def test_comparison_reference_projection_maps_internal_id_to_public_label() -> None:
    projection = {"evidence:alpha": "Alpha Plc", "evidence:beta": "Beta Plc"}

    assert _apply_reference_projection(
        {"higher_ref": "evidence:alpha", "difference": "12"},
        projection,
    ) == {"higher_ref": "Alpha Plc", "difference": "12"}
    assert _apply_reference_projection(
        {"higher_ref": "Alpha Plc", "difference": "12"},
        projection,
    ) == {"higher_ref": "Alpha Plc", "difference": "12"}


def test_frozen_short_subject_identifier_matches_public_subject_suffix() -> None:
    context = _omega()
    source = context.public_corpus.evidence[0]
    item = source.model_copy(
        update={"subject": source.subject.model_copy(update={"subject_id": "PUBLIC_TICKER_US"})}
    )

    assert _matches_subject(item, "PUBLIC_TICKER")
    assert _matches_subject(item, "PUBLIC_TICKER_US")
    assert _matches_subject(item, item.subject.name)


def test_finance_iterative_agent_verifier_accepts_replayable_oracle_correct_run() -> None:
    context = _omega()
    manifest = _manifest(context)
    payloads, tool_sequence, _ = _model_payloads(context, manifest)
    client = _ScriptedClient(payloads)
    condition = PublicAgentStateCondition(
        action_sequence=tuple(
            manifest.tools_by_id[tool_id].trajectory_action for tool_id in tool_sequence
        ),
        tool_sequence=tool_sequence,
        minimum_successful_tool_calls=len(tool_sequence),
        minimum_verification_calls=1,
        query_policy="single_query_allowed",
        recovery_policy="recover_if_tool_fails",
        stop_policy="stop only after a successful cross-check",
    )
    result = IterativeAgentSolver(
        client,
        mode="autonomous_agent",
        maximum_total_tokens=1000,
    ).solve_with_audit(
        context.task.public,
        FinanceArchiveInteractiveToolRuntime(context.public_corpus, manifest),
        public_state_condition=condition,
    )
    report = FinanceIterativeAgentVerifier().verify(
        context,
        context.public_corpus,
        manifest,
        result,
    )

    assert report.valid
    assert report.citation_recall == 1
    assert report.citation_precision == 1
    assert report.evidence_provenance_completeness == 1
    assert result.audit.public_state_condition_hash == condition.condition_hash
    assert all("target_state_id" not in prompt for prompt in client.prompts)
    assert any("agent_contract_guidance" in prompt for prompt in client.prompts)
    assert all("gold_evidence_ids" not in prompt for prompt in client.prompts)


def test_finance_iterative_agent_verifier_rejects_wrong_answer() -> None:
    context = _omega()
    manifest = _manifest(context)
    payloads, _, answer = _model_payloads(context, manifest)
    field = next(iter(answer))
    payloads[-1]["answer"] = {**answer, field: "999"}
    result = IterativeAgentSolver(
        _ScriptedClient(payloads),
        mode="autonomous_agent",
        maximum_total_tokens=1000,
    ).solve_with_audit(
        context.task.public,
        FinanceArchiveInteractiveToolRuntime(context.public_corpus, manifest),
    )
    report = FinanceIterativeAgentVerifier().verify(
        context,
        context.public_corpus,
        manifest,
        result,
    )

    assert not report.valid
    assert not next(item for item in report.checks if item.check_id == "answer_correct").passed


def test_public_agent_state_condition_rejects_hidden_state_identity() -> None:
    with pytest.raises(ValueError):
        PublicAgentStateCondition.model_validate(
            {
                "action_sequence": ["search"],
                "tool_sequence": ["search_archive"],
                "minimum_successful_tool_calls": 1,
                "minimum_verification_calls": 0,
                "query_policy": "single_query_allowed",
                "recovery_policy": "recovery_not_required",
                "stop_policy": "after evidence",
                "target_state_id": "state:hidden",
            }
        )


def test_cross_check_tool_contract_accepts_typed_mechanism_reports() -> None:
    spec = next(
        item
        for item in finance_archive_agent_tool_specs()
        if item.tool_id == "cross_check_evidence"
    )
    base = {
        "verified": True,
        "support": [],
        "conflicts": [],
        "verification_hash": "verification:fixture",
    }

    spec.validate_output(
        {
            **base,
            "candidate_repair": {
                "localized": True,
                "repair_verified": True,
                "target_field": "difference",
            },
        }
    )
    spec.validate_output(
        {
            **base,
            "completion_state": {
                "complete": True,
                "missing_role_ids": [],
                "redundant_action_cost_applied": False,
            },
        }
    )
