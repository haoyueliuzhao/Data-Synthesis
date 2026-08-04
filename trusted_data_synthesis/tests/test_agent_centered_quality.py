from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.evaluation.critic import (
    AcceptabilityLabel,
    AnnotationSource,
    QualityAnnotation,
    QualityAwareSelector,
    QualityCriticPrediction,
    QualitySelectionPolicy,
    evaluate_annotation_alignment,
)
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.experiments.agent_validation import (
    AgentValidationConfig,
    audit_agent_validation_capacity,
    run_agent_validation,
)
from trusted_synthesis.experiments.agent_validation.runner import (
    _compile_runtime,
    _run_model_critic,
    _stratified_critic_examples,
)
from trusted_synthesis.experiments.agent_validation.tracks import (
    materialize_track_variant,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.candidate import (
    PlanGivenContractCandidate,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_pattern_validation_cases,
)
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.runtime.agent import (
    AgentModelConfig,
    FailedActionPlan,
    LLMAgentSolver,
    LLMClientError,
    ModelCallTelemetry,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.client import _estimate_cost
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime


class ScriptedJsonClient:
    def __init__(
        self,
        payloads: list[dict[str, Any]],
        *,
        repair_attempts: int = 0,
        interaction_protocol: str = "full_response",
    ) -> None:
        self._payloads = list(payloads)
        self._config = AgentModelConfig(
            provider="scripted",
            endpoint="https://models.example.test/v1/chat/completions",
            models_endpoint="https://models.example.test/v1/models",
            model="deepseek-v4-pro",
            api_key_env="TEST_ONLY_KEY",
            auto_discover_models=False,
            require_requested_model=True,
            contract_repair_attempts=repair_attempts,
            interaction_protocol=interaction_protocol,
        )
        self.call_count = 0
        self.prompts: list[str] = []

    @property
    def config(self) -> AgentModelConfig:
        return self._config

    def complete_json(self, prompt: str):
        assert '"oracle_contract":' not in prompt
        self.prompts.append(prompt)
        self.call_count += 1
        payload = self._payloads.pop(0)
        return payload, ModelCallTelemetry(
            provider="scripted",
            endpoint_host="models.example.test",
            model_requested="deepseek-v4-pro",
            model_selected="deepseek-v4-pro",
            response_model="deepseek-v4-pro",
            request_hash=f"request-{self.call_count}",
            response_hash=f"response-{self.call_count}",
            http_status=200,
            http_success=True,
            json_contract_success=True,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )


class ThreadSafeScriptedJsonClient(ScriptedJsonClient):
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        super().__init__(payloads)
        self._lock = threading.Lock()

    def complete_json(self, prompt: str):
        with self._lock:
            return super().complete_json(prompt)


class PromptRoutingJsonClient(ScriptedJsonClient):
    def __init__(self, payload_by_task_id: dict[str, dict[str, Any]]) -> None:
        super().__init__([])
        self._payload_by_task_id = payload_by_task_id
        self._lock = threading.Lock()

    def complete_json(self, prompt: str):
        with self._lock:
            task_id = next(
                (key for key in self._payload_by_task_id if f'"task_id": "{key}"' in prompt),
                None,
            )
            if task_id is None:
                raise AssertionError("unexpected API call or unknown task prompt")
            self._payloads.append(copy.deepcopy(self._payload_by_task_id[task_id]))
            return super().complete_json(prompt)


def test_llm_agent_plan_given_is_independently_verified() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    client = ScriptedJsonClient([_response_from_trajectory(deterministic)])

    result = LLMAgentSolver(client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    compiled, runtime = _compile_runtime(case, task)
    assessment = runtime.evaluate(
        compiled.quality_contract,
        task,
        case.corpus,
        case.proof_graph,
        result.trajectory,
    )

    assert assessment.decision.value == "accepted"
    assert result.audit.selected_model == "deepseek-v4-pro"
    assert result.audit.contract_repair_count == 0
    verification = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
    ).verify(task, case.corpus, case.proof_graph, result.trajectory)
    assert verification.execution_coverage == 1
    assert verification.operation_grounding_score == 1
    assert verification.tool_necessity_score == 1
    assert "program_skeleton is a plan, not an execution result" in client.prompts[0]


def test_host_instrumented_agent_executes_actions_and_owns_trace_metadata() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    action_payload = _action_plan_from_trajectory(deterministic)
    answer_payload = _answer_decision_from_trajectory(deterministic)
    client = ScriptedJsonClient(
        [action_payload, answer_payload],
        interaction_protocol="host_instrumented",
    )

    result = LLMAgentSolver(client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    compiled, runtime = _compile_runtime(case, task)
    assessment = runtime.evaluate(
        compiled.quality_contract,
        task,
        case.corpus,
        case.proof_graph,
        result.trajectory,
    )

    assert assessment.decision.value == "accepted"
    assert result.audit.interaction_protocol == "host_instrumented"
    assert result.audit.action_prompt_manifest_hash
    assert result.audit.final_answer_prompt_manifest_hash
    assert result.audit.host_replay_available is True
    assert result.audit.execution_replay_valid is True
    assert result.audit.action_contract_repair_count == 0
    assert result.audit.answer_contract_repair_count == 0
    assert result.audit.action_failure_history == ()
    assert result.trajectory.program_execution["source"] == "host_instrumented_execution"
    assert client.call_count == 2
    action_prompt_payload = json.loads(client.prompts[0].split("PAYLOAD:\n", 1)[1])
    valid_evidence_inputs = action_prompt_payload["evidence_identifier_contract"][
        "valid_evidence_inputs"
    ]
    assert all(set(item) == {"source", "evidence_id"} for item in valid_evidence_inputs)
    assert all(
        {
            "input_role_contract",
            "parameter_contract",
            "downstream_selector_contract",
        }
        <= set(operation)
        for operation in action_prompt_payload["operation_catalog"]
    )
    assert "domain_contract_guidance" in action_prompt_payload
    assert set(
        action_prompt_payload["action_input_contract"]["typed_examples"]["lookup"]["inputs"][0]
    ) == {"source", "evidence_id"}
    assert "host_owned_fields" in client.prompts[0]
    assert '"evidence_identifier_contract"' in client.prompts[0]
    assert '"exact_evidence_ids"' in client.prompts[0]
    assert "Never invent evidence_1-style aliases" in client.prompts[0]
    assert "payload.value is invalid on an evidence input" in client.prompts[0]
    assert "a lookup result stores its scalar at payload.value" in client.prompts[0]
    assert all(
        evidence_id in client.prompts[0] for evidence_id in action_payload["selected_evidence_ids"]
    )
    assert "host_execution" in client.prompts[1]
    assert "answer_result_seed_complete" in client.prompts[1]
    assert "operation_results_by_public_node" in client.prompts[1]
    assert '"citation_field": "cited_evidence_ids"' in client.prompts[1]
    assert '"citation_fields"' not in client.prompts[1]
    assert "execution:host_agent_execution:" not in client.prompts[1]
    assert all("execution_id" not in item for item in action_payload["executions"])
    assert "source_locator" not in answer_payload
    host_steps = tuple(
        step for step in result.trajectory.steps if "execution_id" in step.observation
    )
    assert host_steps
    assert all(
        str(step.observation["execution_id"]).startswith("host_agent_execution:")
        and step.observation["execution_id"] != step.program_node_id
        for step in host_steps
    )


def test_generation_constraints_are_model_visible_and_change_prompt_lineage() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    action_payload = _action_plan_from_trajectory(deterministic)
    answer_payload = _answer_decision_from_trajectory(deterministic)
    compact_client = ScriptedJsonClient(
        [copy.deepcopy(action_payload), copy.deepcopy(answer_payload)],
        interaction_protocol="host_instrumented",
    )
    broad_client = ScriptedJsonClient(
        [copy.deepcopy(action_payload), copy.deepcopy(answer_payload)],
        interaction_protocol="host_instrumented",
    )

    compact = LLMAgentSolver(compact_client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
        generation_constraints={
            "acquisition_requirement": "bounded",
            "lineage_requirement": "direct",
        },
    )
    broad = LLMAgentSolver(broad_client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
        generation_constraints={
            "acquisition_requirement": "expanded",
            "lineage_requirement": "full",
        },
    )

    assert compact.audit.generation_constraints_hash
    assert broad.audit.generation_constraints_hash
    assert compact.audit.generation_constraints_hash != broad.audit.generation_constraints_hash
    assert compact.audit.action_prompt_manifest_hash != broad.audit.action_prompt_manifest_hash
    assert compact.audit.prompt_manifest_hash != broad.audit.prompt_manifest_hash
    assert '"trajectory_generation_constraints"' in compact_client.prompts[0]
    assert '"acquisition_requirement": "bounded"' in compact_client.prompts[0]
    assert '"acquisition_requirement": "expanded"' in broad_client.prompts[0]


def test_host_instrumented_multistep_uses_direct_grounding_and_transitive_lineage() -> None:
    case = next(
        item
        for item in build_pattern_validation_cases(per_domain=3)
        if len(item.task.oracle.task_program.nodes) > 1
        and any(
            ref.kind.value == "operation"
            for ref in item.task.oracle.task_program.nodes[-1].input_refs
        )
    )
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    client = ScriptedJsonClient(
        [
            _action_plan_from_trajectory(deterministic),
            _answer_decision_from_trajectory(deterministic),
        ],
        interaction_protocol="host_instrumented",
    )

    result = LLMAgentSolver(client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    report = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
    ).verify(task, case.corpus, case.proof_graph, result.trajectory)

    assert report.operation_grounding_score == 1
    output_node_id = task.oracle.task_program.output_node_id
    output_step = next(
        step
        for step in result.trajectory.steps
        if step.program_node_id == output_node_id
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    )
    output_node = next(
        node for node in task.oracle.task_program.nodes if node.node_id == output_node_id
    )
    expected_direct = {ref.ref_id for ref in output_node.input_refs if ref.kind.value == "evidence"}
    assert set(output_step.evidence_ids) == expected_direct
    expected_lineage = set(task.oracle.gold_evidence_ids)
    assert set(result.trajectory.program_execution["operation_lineage"][output_node_id]) == (
        expected_lineage
    )

    # Historical host traces carried exact transitive lineage on each derived step.
    legacy_steps = tuple(
        step.model_copy(update={"evidence_ids": tuple(sorted(expected_lineage))})
        if step.step_index == output_step.step_index
        else step
        for step in result.trajectory.steps
    )
    legacy = result.trajectory.model_copy(update={"steps": legacy_steps})
    legacy_report = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
    ).verify(task, case.corpus, case.proof_graph, legacy)
    assert legacy_report.operation_grounding_score == 1

    distractor_id = next(
        item.evidence_id
        for item in case.corpus.evidence
        if item.evidence_id not in expected_lineage
    )
    invalid_steps = tuple(
        step.model_copy(update={"evidence_ids": (*tuple(sorted(expected_lineage)), distractor_id)})
        if step.step_index == output_step.step_index
        else step
        for step in result.trajectory.steps
    )
    invalid = result.trajectory.model_copy(update={"steps": invalid_steps})
    invalid_report = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
    ).verify(task, case.corpus, case.proof_graph, invalid)
    assert invalid_report.operation_grounding_score < 1


def test_host_instrumented_agent_rejects_unretrieved_evidence() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    action_plan = _action_plan_from_trajectory(deterministic)
    action_plan["selected_evidence_ids"][0] = "evidence:unknown:item@v1"
    action_plan["executions"][0]["inputs"][0]["evidence_id"] = "evidence:unknown:item@v1"

    with pytest.raises(LLMClientError, match="host action contract") as captured:
        LLMAgentSolver(
            ScriptedJsonClient(
                [action_plan],
                interaction_protocol="host_instrumented",
            ),
            case.registry,
        ).solve(task.public, InMemoryEvidenceToolRuntime(case.corpus))

    assert isinstance(captured.value.failure_artifact, FailedActionPlan)
    assert captured.value.failure_artifact.failure_category == "interface_security"
    assert captured.value.failure_artifact.error_code == "unknown_evidence_id"
    assert captured.value.interaction_progress is not None
    assert captured.value.interaction_progress.action_plan_contract_succeeded is True
    assert captured.value.interaction_progress.host_execution_evaluable is False
    assert captured.value.telemetry[0].json_contract_success is True


def test_semi_open_action_failure_preserves_search_telemetry() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.SEMI_OPEN,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    resolved_task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        resolved_task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    action_plan = _action_plan_from_trajectory(deterministic)
    action_plan["selected_evidence_ids"][0] = "evidence:unknown:item@v1"
    action_plan["executions"][0]["inputs"][0]["evidence_id"] = "evidence:unknown:item@v1"
    client = ScriptedJsonClient(
        [_search_response(task.public.retrieval_scope), action_plan],
        interaction_protocol="host_instrumented",
    )

    with pytest.raises(LLMClientError, match="host action contract") as captured:
        LLMAgentSolver(client, case.registry).solve(
            task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )

    assert len(captured.value.telemetry) == 2
    assert captured.value.telemetry[0].json_contract_success is True
    assert captured.value.telemetry[1].error_type == "AgentActionInterfaceError"


def test_host_instrumented_semantic_action_failure_is_structured_feedback() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    action_plan = _action_plan_from_trajectory(deterministic)
    observed_operator = action_plan["executions"][0]["operator_id"]
    replacement = next(
        str(item["operator_id"])
        for item in case.registry.manifest()
        if item["operator_id"] != observed_operator
    )
    action_plan["executions"][0]["operator_id"] = replacement

    with pytest.raises(LLMClientError, match="host action contract") as captured:
        LLMAgentSolver(
            ScriptedJsonClient(
                [action_plan],
                interaction_protocol="host_instrumented",
            ),
            case.registry,
        ).solve(task.public, InMemoryEvidenceToolRuntime(case.corpus))

    failure = captured.value.failure_artifact
    assert isinstance(failure, FailedActionPlan)
    assert failure.failure_category == "semantic_action"
    assert failure.error_code == "public_operator_mismatch"
    assert failure.failed_step_index == 1
    assert failure.action_plan.executions[0].operator_id == replacement
    assert captured.value.telemetry[0].error_type == "AgentSemanticActionError"
    assert captured.value.telemetry[0].json_contract_success is True
    assert captured.value.interaction_progress is not None
    assert captured.value.interaction_progress.action_plan_contract_succeeded is True
    assert captured.value.interaction_progress.host_execution_evaluable is False


def test_host_instrumented_selector_failure_returns_coordinate_guidance() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_HIDDEN,
    )
    plan_given_task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        plan_given_task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    action_plan = _action_plan_from_trajectory(deterministic)
    action_plan["executions"][0]["inputs"][0]["selector"] = "payload.value"

    with pytest.raises(LLMClientError, match="host action contract") as captured:
        LLMAgentSolver(
            ScriptedJsonClient(
                [action_plan],
                interaction_protocol="host_instrumented",
            ),
            case.registry,
        ).solve(task.public, InMemoryEvidenceToolRuntime(case.corpus))

    failure = captured.value.failure_artifact
    assert isinstance(failure, FailedActionPlan)
    assert failure.error_code == "invalid_input_selector"
    assert "never use 'payload.value'" in failure.error_message


def test_host_instrumented_answer_failure_preserves_completed_host_stage() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    action_plan = _action_plan_from_trajectory(deterministic)

    with pytest.raises(LLMClientError, match="host answer contract") as captured:
        LLMAgentSolver(
            ScriptedJsonClient(
                [
                    action_plan,
                    {
                        "schema_version": "agent_answer_decision.v1",
                        "result": {},
                        "cited_evidence_ids": [],
                    },
                ],
                interaction_protocol="host_instrumented",
            ),
            case.registry,
        ).solve(task.public, InMemoryEvidenceToolRuntime(case.corpus))

    progress = captured.value.interaction_progress
    assert progress is not None
    assert progress.action_plan_contract_succeeded is True
    assert progress.host_execution_evaluable is True
    assert progress.answer_decision_attempted is True
    assert progress.answer_decision_contract_succeeded is False


def test_public_skeleton_copy_is_rejected_as_execution() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    payload = _response_from_trajectory(deterministic)
    first = payload["execution_trace"]["steps"][0]
    first["execution_id"] = first["planned_node_id"]

    with pytest.raises(LLMClientError, match="response contract"):
        LLMAgentSolver(ScriptedJsonClient([payload]), case.registry).solve(
            task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )


def test_plan_hidden_candidate_node_ids_are_semantically_normalized() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    visible_task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    hidden_task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_HIDDEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        visible_task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    payload = _response_from_trajectory(deterministic, rename_nodes=True)

    trajectory = LLMAgentSolver(
        ScriptedJsonClient([payload]),
        case.registry,
    ).solve(hidden_task.public, InMemoryEvidenceToolRuntime(case.corpus))
    compiled, runtime = _compile_runtime(case, hidden_task)
    assessment = runtime.evaluate(
        compiled.quality_contract,
        hidden_task,
        case.corpus,
        case.proof_graph,
        trajectory,
    )

    assert assessment.decision.value == "accepted", assessment.model_dump(mode="json")
    assert all(
        step.program_node_id is None or step.program_node_id.startswith("candidate_")
        for step in trajectory.steps
        if step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    )


@pytest.mark.parametrize("domain", ("finance", "legal"))
def test_plan_hidden_accepts_only_verified_transparent_lookup_adapters(
    domain: str,
) -> None:
    if domain == "finance":
        case = build_finance_counterfactual_cases(count=2)[1]
    else:
        case = next(
            item for item in build_pattern_validation_cases(per_domain=1) if item.domain == "legal"
        )
    visible_task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    hidden_task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_HIDDEN,
    )
    if domain == "finance":
        deterministic = FinanceNumericCandidateGenerator().generate(
            visible_task.public,
            InMemoryEvidenceToolRuntime(case.bundle),
        )
    else:
        deterministic = PlanGivenContractCandidate(case.registry).generate(
            visible_task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )
    selected_step = next(
        step
        for step in deterministic.steps
        if step.action == ActionType.SELECT_EVIDENCE and step.program_node_id is None
    )
    semantic_steps = [
        step
        for step in deterministic.steps
        if step.program_node_id is not None
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    ]
    assert len(semantic_steps) == 1
    semantic_step = semantic_steps[0]
    direct_inputs = [_action_input_from_ref(ref, {}) for ref in semantic_step.input_refs]
    assert all(item["source"] == "evidence" for item in direct_inputs)
    lookup_executions = [
        {
            "operator_id": "lookup",
            "inputs": [item],
            "parameters": {},
            "rationale_summary": "Project one selected Evidence payload.",
        }
        for item in direct_inputs
    ]
    semantic_execution = {
        "operator_id": semantic_step.operator_id,
        "inputs": [
            {
                "source": "step",
                "step_index": index,
                "selector": "payload",
            }
            for index in range(1, len(lookup_executions) + 1)
        ],
        "parameters": semantic_step.tool_input.get("parameters", {}),
        "rationale_summary": "Execute the semantic operation over projected payloads.",
    }
    action_payload = {
        "schema_version": "agent_action_plan.v1",
        "plan_summary": "Project selected evidence, then execute the semantic operation.",
        "selected_evidence_ids": list(selected_step.evidence_ids),
        "executions": [*lookup_executions, semantic_execution],
        "output_step_index": len(lookup_executions) + 1,
    }
    client = ScriptedJsonClient(
        [action_payload, _answer_decision_from_trajectory(deterministic)],
        interaction_protocol="host_instrumented",
    )

    result = LLMAgentSolver(client, case.registry).solve_with_audit(
        hidden_task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    report = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
    ).verify(hidden_task, case.corpus, case.proof_graph, result.trajectory)

    assert report.passed, report.model_dump(mode="json")
    assert len(report.program_node_mapping) == len(lookup_executions) + 1
    assert {
        alias for alias in report.program_node_mapping.values() if alias.startswith("projection:")
    } == {
        f"projection:{semantic_step.program_node_id}:{index}"
        for index in range(len(lookup_executions))
    }
    operation_steps = [
        step
        for step in result.trajectory.steps
        if step.program_node_id is not None
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    ]
    assert len(operation_steps) == len(lookup_executions) + 1
    if domain == "finance":
        output = operation_steps[-1].observation["result"]
        assert output["higher_ref"] in set(hidden_task.oracle.gold_evidence_ids)
        assert not str(output["higher_ref"]).startswith(("step_", "operation:"))

    lookup_step = next(step for step in operation_steps if step.operator_id == "lookup")
    tampered_steps = tuple(
        step.model_copy(
            update={
                "observation": {
                    **step.observation,
                    "result": {
                        **step.observation["result"],
                        "selected_ref": "evidence:tampered:item@v1",
                    },
                }
            }
        )
        if step.step_index == lookup_step.step_index
        else step
        for step in result.trajectory.steps
    )
    tampered = result.trajectory.model_copy(update={"steps": tampered_steps})
    tampered_report = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
    ).verify(hidden_task, case.corpus, case.proof_graph, tampered)
    assert not tampered_report.passed
    assert "program_node_alignment" in {
        check.check_id for check in tampered_report.checks if not check.passed
    }


def test_agent_contract_repair_feeds_a_new_request() -> None:
    case = build_pattern_validation_cases(per_domain=1)[1]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.SEMI_OPEN,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    client = ScriptedJsonClient(
        [
            _search_response(task.public.retrieval_scope),
            {"schema_version": "agent_response.v1"},
            _response_from_trajectory(deterministic),
        ],
        repair_attempts=1,
    )

    result = LLMAgentSolver(client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )

    assert client.call_count == 3
    assert result.audit.contract_repair_count == 1
    assert result.audit.telemetry[0].json_contract_success is True
    assert result.audit.telemetry[1].json_contract_success is False
    assert result.audit.telemetry[2].json_contract_success is True


def test_agent_contract_repair_rejects_unresolvable_evidence_ref() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    valid = _response_from_trajectory(deterministic)
    invalid = {
        **valid,
        "execution_trace": {
            **valid["execution_trace"],
            "steps": [
                {
                    **execution,
                    "input_refs": [
                        (
                            ref.removeprefix("evidence:")
                            if ref.startswith("evidence:evidence:")
                            else ref
                        )
                        for ref in execution["input_refs"]
                    ],
                }
                for execution in valid["execution_trace"]["steps"]
            ],
        },
    }
    client = ScriptedJsonClient([invalid, valid], repair_attempts=1)

    result = LLMAgentSolver(client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )

    assert client.call_count == 2
    assert result.audit.contract_repair_count == 1
    assert result.audit.telemetry[0].json_contract_success is False
    assert result.audit.telemetry[0].error_type == "AgentContractValidationError"
    assert result.audit.telemetry[1].json_contract_success is True


def test_failed_agent_contract_preserves_redacted_diagnostics() -> None:
    case = next(
        item for item in build_pattern_validation_cases(per_domain=1) if item.domain == "legal"
    )
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    payload = _response_from_trajectory(deterministic)
    payload["final_answer"] = {"payload": {"applicable": True}}

    with pytest.raises(LLMClientError) as captured:
        LLMAgentSolver(ScriptedJsonClient([payload]), case.registry).solve(
            task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )

    telemetry = captured.value.telemetry[0]
    assert telemetry.json_contract_success is False
    assert telemetry.contract_errors
    assert telemetry.error_message == telemetry.contract_errors[0]
    final_shape = telemetry.response_shape["properties"]["final_answer"]
    assert final_shape["keys"] == ["payload"]
    assert "applicable" not in str(telemetry.contract_errors)


def test_legal_prompt_exposes_exact_plugin_owned_contract() -> None:
    case = next(
        item for item in build_pattern_validation_cases(per_domain=1) if item.domain == "legal"
    )
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    client = ScriptedJsonClient([_response_from_trajectory(deterministic)])

    LLMAgentSolver(client, case.registry).solve(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )

    prompt = client.prompts[0]
    assert '"domain_contract_guidance"' in prompt
    assert '"missing_conditions"' in prompt
    assert '"required_top_level_fields"' in prompt
    assert '"required_tool_name": "rule_engine"' in prompt


def test_agent_contract_rejects_non_output_verification_payload() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    payload = _response_from_trajectory(deterministic)
    payload["verification_result"] = {"status": "verified"}

    with pytest.raises(LLMClientError) as captured:
        LLMAgentSolver(ScriptedJsonClient([payload]), case.registry).solve(
            task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )

    assert any(
        "verification_result must exactly equal" in error
        for error in captured.value.telemetry[0].contract_errors
    )


def test_agent_parameters_compare_after_json_round_trip() -> None:
    case = next(
        item for item in build_pattern_validation_cases(per_domain=1) if item.domain == "legal"
    )
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    payload = json.loads(json.dumps(_response_from_trajectory(deterministic)))

    trajectory = LLMAgentSolver(ScriptedJsonClient([payload]), case.registry).solve(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    compiled, runtime = _compile_runtime(case, task)
    assessment = runtime.evaluate(
        compiled.quality_contract,
        task,
        case.corpus,
        case.proof_graph,
        trajectory,
    )
    operation_step = next(
        step
        for step in trajectory.steps
        if step.program_node_id is not None
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    )

    assert trajectory.task_id == task.task_id
    assert task.public.program_skeleton is not None
    assert operation_step.tool_input == {
        "parameters": task.public.program_skeleton.nodes[0].parameters
    }
    assert assessment.decision.value == "accepted", assessment.model_dump(mode="json")


def test_science_synthesis_prompt_requires_unrounded_decimal_output() -> None:
    case = next(
        item
        for item in build_pattern_validation_cases(per_domain=3)
        if item.task.public.task_type == "science_descriptive_effect_synthesis"
    )
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    client = ScriptedJsonClient([_response_from_trajectory(deterministic)])

    LLMAgentSolver(client, case.registry).solve(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )

    prompt = client.prompts[0]
    assert "full normalized decimal result" in prompt
    assert "emit the full normalized quotient without rounding" in prompt


@pytest.mark.parametrize("retrieval_track", [RetrievalTrack.SEMI_OPEN, RetrievalTrack.OPEN])
def test_agent_controls_non_resolved_search_without_oracle_ids(
    retrieval_track: RetrievalTrack,
) -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=retrieval_track,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    resolved_task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        resolved_task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    client = ScriptedJsonClient(
        [
            _search_response(task.public.retrieval_scope),
            _response_from_trajectory(deterministic),
        ]
    )

    result = LLMAgentSolver(client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    search_step = next(step for step in result.trajectory.steps if step.action == ActionType.SEARCH)

    assert result.audit.model_search_used is True
    assert result.audit.search_prompt_manifest_hash is not None
    assert len(result.audit.telemetry) == 2
    assert search_step.tool_input["corpus_boundary"] == case.corpus.corpus_id
    assert "evidence_ids" not in search_step.tool_input


def test_agent_repairs_a_valid_search_contract_that_returns_no_evidence() -> None:
    case = build_pattern_validation_cases(per_domain=1)[0]
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.SEMI_OPEN,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    resolved_task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        resolved_task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    empty_search = _search_response(task.public.retrieval_scope)
    empty_search["search_query"] = {"subject_ids": ["subject:does-not-exist"]}
    client = ScriptedJsonClient(
        [
            empty_search,
            _search_response(task.public.retrieval_scope),
            _response_from_trajectory(deterministic),
        ],
        repair_attempts=1,
    )

    result = LLMAgentSolver(client, case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )

    assert client.call_count == 3
    assert result.audit.search_contract_repair_count == 1
    assert result.audit.contract_repair_count == 1
    assert result.audit.telemetry[0].error_type == "AgentSearchExecutionError"
    assert result.audit.telemetry[0].json_contract_success is True
    assert result.audit.telemetry[1].json_contract_success is True
    assert "search_empty_result" in client.prompts[1]
    assert "individually_nonmatching_fields" in client.prompts[1]


def test_agent_capacity_audit_supports_domain_specific_targets() -> None:
    config = AgentValidationConfig(
        model=ScriptedJsonClient([]).config,
        domain_task_targets={"finance": 3, "legal": 2, "science": 1},
        retrieval_tracks=(RetrievalTrack.RESOLVED,),
        planning_tracks=(PlanningTrack.PLAN_GIVEN,),
        run_model_critic=True,
        model_critic_max_examples=4,
    )

    report = audit_agent_validation_capacity(config)

    assert report.status == "ready"
    assert report.materialized_task_counts == {
        "finance": 3,
        "legal": 2,
        "science": 1,
    }
    assert report.unique_task_counts == report.materialized_task_counts
    assert report.planned_candidate_count == 6
    assert report.interaction_protocol == "full_response"
    assert report.planned_search_api_calls == 0
    assert report.planned_action_api_calls == 0
    assert report.planned_final_answer_api_calls == 0
    assert report.planned_full_response_api_calls == 6
    assert report.planned_agent_api_call_floor == 6
    assert report.planned_critic_api_call_ceiling == 4


def test_host_instrumented_capacity_counts_both_generation_phases() -> None:
    config = AgentValidationConfig(
        model=ScriptedJsonClient([], interaction_protocol="host_instrumented").config,
        domain_task_targets={"finance": 3, "legal": 2, "science": 1},
        retrieval_tracks=(RetrievalTrack.RESOLVED,),
        planning_tracks=(PlanningTrack.PLAN_GIVEN,),
    )

    report = audit_agent_validation_capacity(config)

    assert report.interaction_protocol == "host_instrumented"
    assert report.planned_search_api_calls == 0
    assert report.planned_action_api_calls == 6
    assert report.planned_final_answer_api_calls == 6
    assert report.planned_full_response_api_calls == 0
    assert report.planned_agent_api_call_floor == 12


def test_agent_validation_runner_covers_three_domains_and_both_planning_tracks(
    tmp_path: Path,
) -> None:
    cases = (
        *build_finance_counterfactual_cases(count=1),
        *build_pattern_validation_cases(per_domain=1),
    )
    payloads = []
    for case in cases:
        visible_task = materialize_track_variant(
            case.task,
            case.corpus,
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
        )
        if case.domain == "finance":
            deterministic = FinanceNumericCandidateGenerator().generate(
                visible_task.public,
                InMemoryEvidenceToolRuntime(case.bundle),
            )
            payloads.append(_response_from_trajectory(deterministic))
            payloads.append(_response_from_trajectory(deterministic, rename_nodes=True))
        else:
            deterministic = PlanGivenContractCandidate(case.registry).generate(
                visible_task.public,
                InMemoryEvidenceToolRuntime(case.corpus),
            )
            payloads.append(_response_from_trajectory(deterministic))
            payloads.append(_response_from_trajectory(deterministic, rename_nodes=True))
    client = ScriptedJsonClient(payloads)
    config = AgentValidationConfig(
        model=client.config,
        tasks_per_domain=1,
        retrieval_tracks=(RetrievalTrack.RESOLVED,),
        planning_tracks=(PlanningTrack.PLAN_GIVEN, PlanningTrack.PLAN_HIDDEN),
        generate_counterfactuals=True,
        selection_target=3,
    )

    artifacts = run_agent_validation(config, client)
    report = artifacts.report

    assert report.status == "completed", [
        (item.domain, item.planning_track.value, item.generation_status, item.error_type)
        for item in report.samples
    ]
    assert report.attempted_count == 6
    assert report.accepted_count == 6, [
        (
            item.domain,
            item.planning_track.value,
            item.contract_assessment.decision.value
            if item.contract_assessment is not None
            else None,
            tuple(
                result.failure_code
                for result in item.contract_assessment.clause_results
                if not result.passed
            )
            if item.contract_assessment is not None
            else None,
        )
        for item in report.samples
    ]
    assert report.domain_counts == {"finance": 2, "legal": 2, "science": 2}
    assert report.retrieval_planning_counts == {
        "resolved|plan_given": 3,
        "resolved|plan_hidden": 3,
    }
    assert report.quality_selection is not None
    assert report.quality_selection.status == "complete"
    assert report.training_utility_protocol.status == "planned"
    d1 = report.training_utility_protocol.cohorts[0]
    assert d1.cohort.value == "D1_random_synthetic"
    assert d1.materialization_status == "planned"
    assert d1.sample_ids == ()
    assert artifacts.critic_dataset.real_agent_count == 6
    assert artifacts.critic_dataset.counterfactual_count > 0
    critic_slice = _stratified_critic_examples(artifacts.critic_dataset.examples, 6)
    assert {item.domain for item in critic_slice} == {"finance", "legal", "science"}
    for domain in ("finance", "legal", "science"):
        assert (
            sum(
                item.domain == domain
                and item.candidate_source == "real_agent"
                and item.contract_annotation.acceptability.value == "accept"
                for item in critic_slice
            )
            == 1
        )

    buffered_slice = _stratified_critic_examples(artifacts.critic_dataset.examples, 9)
    assert len(buffered_slice) == 9
    for domain in ("finance", "legal", "science"):
        assert (
            sum(
                item.domain == domain
                and item.candidate_source == "real_agent"
                and item.contract_annotation.acceptability.value == "accept"
                for item in buffered_slice
            )
            == 2
        )
    assert any(item.candidate_source == "typed_counterfactual" for item in buffered_slice)

    assert {item.candidate_source for item in critic_slice} == {
        "real_agent",
        "typed_counterfactual",
    }
    critic_client = ScriptedJsonClient(
        [
            {
                "schema_version": "quality_critic_response.v1",
                "accept_probability": (
                    0.95
                    if item.contract_annotation.acceptability == AcceptabilityLabel.ACCEPT
                    else 0.05
                ),
                "predicted_acceptability": item.contract_annotation.acceptability.value,
                "failure_families": list(item.contract_annotation.failure_families),
                "root_locations": [
                    location.model_dump(mode="json")
                    for location in item.contract_annotation.root_locations
                ],
                "dimension_scores": {},
            }
            for item in critic_slice
        ]
    )
    critic_checkpoint_stats: dict[str, int] = {}
    reviewed, predictions, _, _, failures, attempted = _run_model_critic(
        critic_client,
        artifacts.critic_dataset.examples,
        6,
        checkpoint_dir=tmp_path / "critic_checkpoints",
        checkpoint_config_hash="critic-test-config",
        checkpoint_stats=critic_checkpoint_stats,
    )
    alignment = evaluate_annotation_alignment(reviewed)
    assert attempted == 6
    assert len(predictions) == 6
    assert failures == ()
    assert critic_checkpoint_stats == {"loaded": 0, "written": 6}
    assert alignment.model_contract_acceptability_agreement == 1.0
    assert report.alignment_report.human_annotation_count == 0
    assert report.alignment_report.human_contract_acceptability_agreement is None

    resume_stats: dict[str, int] = {}
    _, resumed_predictions, _, _, resumed_failures, resumed_attempted = _run_model_critic(
        ScriptedJsonClient([]),
        artifacts.critic_dataset.examples,
        6,
        checkpoint_dir=tmp_path / "critic_checkpoints",
        checkpoint_config_hash="critic-test-config",
        checkpoint_stats=resume_stats,
    )
    assert resumed_attempted == 6
    assert resumed_failures == ()
    assert len(resumed_predictions) == 6
    assert resume_stats == {"loaded": 6, "written": 0}

    repair_client = ScriptedJsonClient(
        [
            {"schema_version": "quality_critic_response.v1"},
            {
                "schema_version": "quality_critic_response.v1",
                "accept_probability": 0.95,
                "predicted_acceptability": "accept",
                "failure_families": [],
                "root_locations": [],
                "dimension_scores": {},
            },
        ],
        repair_attempts=1,
    )
    _, repaired_predictions, _, repaired_telemetry, failures, attempted = _run_model_critic(
        repair_client,
        (critic_slice[0],),
        1,
    )
    calls = repaired_telemetry[critic_slice[0].example_id]
    assert attempted == 1
    assert failures == ()
    assert len(repaired_predictions) == 1
    assert len(calls) == 2
    assert calls[0].json_contract_success is False
    assert calls[0].error_type == "QualityCriticContractError"
    assert calls[1].json_contract_success is True


def test_agent_runner_concurrency_checkpoints_and_zero_call_resume(tmp_path: Path) -> None:
    cases = (
        *build_finance_counterfactual_cases(count=1),
        *build_pattern_validation_cases(per_domain=1),
    )
    payload_by_task_id = {}
    for case in cases:
        task = materialize_track_variant(
            case.task,
            case.corpus,
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
        )
        if case.domain == "finance":
            deterministic = FinanceNumericCandidateGenerator().generate(
                task.public,
                InMemoryEvidenceToolRuntime(case.bundle),
            )
        else:
            deterministic = PlanGivenContractCandidate(case.registry).generate(
                task.public,
                InMemoryEvidenceToolRuntime(case.corpus),
            )
        payload_by_task_id[task.task_id] = _response_from_trajectory(deterministic)
    client = PromptRoutingJsonClient(payload_by_task_id)
    config = AgentValidationConfig(
        model=client.config,
        tasks_per_domain=1,
        retrieval_tracks=(RetrievalTrack.RESOLVED,),
        planning_tracks=(PlanningTrack.PLAN_GIVEN,),
        generate_counterfactuals=False,
        selection_target=3,
        maximum_concurrency=2,
    )
    checkpoint_dir = tmp_path / "checkpoints"

    first = run_agent_validation(config, client, checkpoint_dir=checkpoint_dir)

    assert first.report.status == "completed"
    assert client.call_count == 3
    assert first.report.maximum_concurrency == 2
    assert first.report.agent_checkpoint_loaded_count == 0
    assert first.report.agent_checkpoint_written_count == 3
    assert len(tuple((checkpoint_dir / "agent").glob("*.json"))) == 3

    resumed_client = PromptRoutingJsonClient({})
    resumed = run_agent_validation(
        config,
        resumed_client,
        checkpoint_dir=checkpoint_dir,
    )

    assert resumed_client.call_count == 0
    assert resumed.report.agent_checkpoint_loaded_count == 3
    assert resumed.report.agent_checkpoint_written_count == 0
    assert tuple(item.sample_id for item in resumed.report.samples) == tuple(
        item.sample_id for item in first.report.samples
    )
    assert resumed.critic_dataset.dataset_id == first.critic_dataset.dataset_id


def test_model_advisory_cannot_be_declared_as_human_annotation() -> None:
    with pytest.raises(ValueError, match="human annotations require"):
        QualityAnnotation(
            annotation_id="annotation:test",
            source=AnnotationSource.HUMAN,
            acceptability=AcceptabilityLabel.ACCEPT,
            model_id="deepseek-v4-pro",
        )


def test_unreviewed_candidate_receives_neutral_critic_prior() -> None:
    cases = (
        *build_finance_counterfactual_cases(count=1),
        *build_pattern_validation_cases(per_domain=1),
    )
    payloads = []
    for case in cases:
        visible_task = materialize_track_variant(
            case.task,
            case.corpus,
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
        )
        if case.domain == "finance":
            deterministic = FinanceNumericCandidateGenerator().generate(
                visible_task.public,
                InMemoryEvidenceToolRuntime(case.bundle),
            )
        else:
            deterministic = PlanGivenContractCandidate(case.registry).generate(
                visible_task.public,
                InMemoryEvidenceToolRuntime(case.corpus),
            )
        payloads.append(_response_from_trajectory(deterministic))
    artifacts = run_agent_validation(
        AgentValidationConfig(
            model=ScriptedJsonClient(payloads).config,
            tasks_per_domain=1,
            retrieval_tracks=(RetrievalTrack.RESOLVED,),
            planning_tracks=(PlanningTrack.PLAN_GIVEN,),
            generate_counterfactuals=False,
            selection_target=1,
        ),
        ScriptedJsonClient(payloads),
    )
    examples = artifacts.critic_dataset.examples
    reviewed = examples[-1]
    prediction = QualityCriticPrediction(
        prediction_id="critic:reviewed",
        example_id=reviewed.example_id,
        model_id="deepseek-v4-pro",
        model_manifest_hash="model-manifest:test",
        accept_probability=0.99,
        predicted_acceptability=AcceptabilityLabel.ACCEPT,
    )

    selected = QualityAwareSelector().select(
        examples,
        QualitySelectionPolicy(target_size=1),
        (prediction,),
    )

    assert selected.selected_example_ids == (reviewed.example_id,)


def test_model_config_rejects_inline_credentials() -> None:
    with pytest.raises(ValueError, match="api_key_env"):
        AgentModelConfig(
            provider="test",
            endpoint="https://models.example.test/v1/chat/completions",
            model="deepseek-v4-pro",
            api_key_env="DEEPSEEK_API_KEY",
            extra_headers={"Authorization": "Bearer must-not-be-stored"},
        )


def test_agent_cost_estimation_uses_cache_breakdown_or_conservative_miss() -> None:
    config = AgentModelConfig(
        provider="deepseek",
        endpoint="https://api.deepseek.com/v1/chat/completions",
        model="deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        input_cache_hit_cost_per_million=0.003625,
        input_cache_miss_cost_per_million=0.435,
        output_cost_per_million=0.87,
    )

    detailed, detailed_method = _estimate_cost(
        config,
        1_000_000,
        1_000_000,
        prompt_cache_hit_tokens=750_000,
        prompt_cache_miss_tokens=250_000,
    )
    conservative, conservative_method = _estimate_cost(
        config,
        1_000_000,
        1_000_000,
    )

    assert detailed == pytest.approx(0.75 * 0.003625 + 0.25 * 0.435 + 0.87)
    assert detailed_method == "provider_cache_breakdown"
    assert conservative == pytest.approx(0.435 + 0.87)
    assert conservative_method == "conservative_cache_miss"


def test_agent_model_config_rejects_partial_cache_pricing() -> None:
    with pytest.raises(ValueError, match="both hit and miss"):
        AgentModelConfig(
            provider="deepseek",
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-pro",
            api_key_env="DEEPSEEK_API_KEY",
            input_cache_hit_cost_per_million=0.003625,
        )


def test_agent_model_config_rejects_core_request_body_override() -> None:
    with pytest.raises(ValueError, match="core request fields"):
        AgentModelConfig(
            provider="test",
            endpoint="https://models.example.test/v1/chat/completions",
            model="test-model",
            api_key_env="TEST_ONLY_KEY",
            request_body_overrides={"messages": []},
        )


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status = 200
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test_openai_client_applies_safe_body_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ONLY_KEY", "test-secret")
    observed: dict[str, Any] = {}

    def fake_urlopen(request: urllib.request.Request, *, timeout: float):
        observed.update(json.loads(request.data or b"{}"))
        assert timeout == 60
        return _FakeHttpResponse(
            {
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"ok": true}'},
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 8,
                    "total_tokens": 108,
                },
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleJsonClient(
        AgentModelConfig(
            provider="deepseek",
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-pro",
            api_key_env="TEST_ONLY_KEY",
            auto_discover_models=False,
            maximum_model_attempts=1,
            request_body_overrides={"thinking": {"type": "disabled"}},
        )
    )

    payload, telemetry = client.complete_json("Return JSON.")

    assert payload == {"ok": True}
    assert observed["thinking"] == {"type": "disabled"}
    assert telemetry.finish_reason == "stop"
    assert telemetry.response_content_length == len('{"ok": true}')
    assert telemetry.reasoning_content_present is False


def test_openai_client_reports_reasoning_budget_exhaustion_with_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ONLY_KEY", "test-secret")

    def fake_urlopen(_request: urllib.request.Request, *, timeout: float):
        assert timeout == 60
        return _FakeHttpResponse(
            {
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "content": "",
                            "reasoning_content": "private reasoning omitted",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 4096,
                    "total_tokens": 4196,
                    "completion_tokens_details": {"reasoning_tokens": 4096},
                },
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleJsonClient(
        AgentModelConfig(
            provider="deepseek",
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-pro",
            api_key_env="TEST_ONLY_KEY",
            auto_discover_models=False,
            maximum_model_attempts=1,
            input_cost_per_million=0.435,
            output_cost_per_million=0.87,
        )
    )

    with pytest.raises(LLMClientError) as captured:
        client.complete_json("Return JSON.")

    telemetry = captured.value.telemetry[-1]
    assert telemetry.error_type == "ReasoningBudgetExhaustedError"
    assert telemetry.http_success is True
    assert telemetry.finish_reason == "length"
    assert telemetry.reasoning_content_present is True
    assert telemetry.reasoning_tokens == 4096
    assert telemetry.completion_tokens == 4096
    assert telemetry.estimated_cost == pytest.approx(
        100 / 1_000_000 * 0.435 + 4096 / 1_000_000 * 0.87
    )


def test_public_agent_imports_work_in_a_cold_python_process() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "PYTHONPATH": str(repository_root / "src")}
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from trusted_synthesis.runtime.agent import AgentModelConfig; "
                "from trusted_synthesis.core.trajectory import CandidateWorkflowVerifier; "
                "from trusted_synthesis.core.evaluation import QualityContract; "
                "assert AgentModelConfig and CandidateWorkflowVerifier and QualityContract"
            ),
        ],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def _action_plan_from_trajectory(trajectory: Trajectory) -> dict[str, Any]:
    operation_steps = [
        step
        for step in trajectory.steps
        if step.program_node_id is not None
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    ]
    node_positions = {
        step.program_node_id: index
        for index, step in enumerate(operation_steps, start=1)
        if step.program_node_id is not None
    }
    selected_step = next(
        step
        for step in trajectory.steps
        if step.action == ActionType.SELECT_EVIDENCE and step.program_node_id is None
    )
    verify_step = next(
        (step for step in trajectory.steps if step.action == ActionType.VERIFY),
        None,
    )
    output_node_id = (
        verify_step.program_node_id
        if verify_step is not None
        else operation_steps[-1].program_node_id
    )
    assert output_node_id is not None
    return {
        "schema_version": "agent_action_plan.v1",
        "plan_summary": "Select matching evidence and execute a typed operation DAG.",
        "selected_evidence_ids": list(selected_step.evidence_ids),
        "executions": [
            {
                "operator_id": step.operator_id,
                "inputs": [_action_input_from_ref(ref, node_positions) for ref in step.input_refs],
                "parameters": step.tool_input.get("parameters", {}),
                "rationale_summary": "Execute the selected typed operation.",
            }
            for step in operation_steps
        ],
        "output_step_index": node_positions[output_node_id],
    }


def _action_input_from_ref(
    ref: str,
    node_positions: dict[str, int],
) -> dict[str, Any]:
    base, separator, selector = ref.partition("#")
    if base.startswith("evidence:"):
        return {
            "source": "evidence",
            "evidence_id": base.removeprefix("evidence:"),
            "selector": selector if separator else None,
        }
    node_id = base.removeprefix("operation:")
    return {
        "source": "step",
        "step_index": node_positions[node_id],
        "selector": selector if separator else None,
    }


def _answer_decision_from_trajectory(trajectory: Trajectory) -> dict[str, Any]:
    final_answer = trajectory.final_answer
    return {
        "schema_version": "agent_answer_decision.v1",
        "result": final_answer["result"],
        "cited_evidence_ids": [item["evidence_id"] for item in final_answer["citations"]],
        **({"status": final_answer["status"]} if "status" in final_answer else {}),
        **({"claims": final_answer["claims"]} if "claims" in final_answer else {}),
    }


def _response_from_trajectory(
    trajectory: Trajectory,
    *,
    rename_nodes: bool = False,
) -> dict[str, Any]:
    operation_steps = [
        step
        for step in trajectory.steps
        if step.program_node_id is not None
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    ]
    execution_ids = {
        step.program_node_id: (f"candidate_{index}" if rename_nodes else f"exec_{index:03d}")
        for index, step in enumerate(operation_steps, start=1)
        if step.program_node_id is not None
    }
    result_mapping = {
        node_id: (execution_ids[node_id] if rename_nodes else node_id) for node_id in execution_ids
    }
    selected_step = next(
        (
            step
            for step in trajectory.steps
            if step.action == ActionType.SELECT_EVIDENCE and step.program_node_id is None
        ),
        None,
    )
    selected_evidence_ids = (
        selected_step.evidence_ids
        if selected_step is not None
        else tuple(
            dict.fromkeys(
                evidence_id for step in operation_steps for evidence_id in step.evidence_ids
            )
        )
    )
    verify_step = next(
        (step for step in trajectory.steps if step.action == ActionType.VERIFY),
        None,
    )
    output_node_id = (
        verify_step.program_node_id
        if verify_step is not None
        else operation_steps[-1].program_node_id
    )
    assert output_node_id is not None
    return {
        "schema_version": "agent_response.v3",
        "plan_summary": "Select matching evidence and execute a typed operation DAG.",
        "selected_evidence_ids": list(selected_evidence_ids),
        "execution_trace": {
            "trace_version": "agent_execution_trace.v1",
            "steps": [
                {
                    "execution_id": execution_ids[step.program_node_id],
                    "planned_node_id": None if rename_nodes else step.program_node_id,
                    "operator_id": step.operator_id,
                    "tool_name": step.tool_name,
                    "input_refs": [
                        _translate_execution_ref(ref, execution_ids) for ref in step.input_refs
                    ],
                    "parameters": step.tool_input.get("parameters", {}),
                    "evidence_ids": list(step.evidence_ids),
                    "observation": {
                        "result": _translate_value(
                            step.observation["result"],
                            result_mapping,
                        )
                    },
                    "status": step.status.value,
                    "rationale_summary": "Execute the selected typed operation.",
                }
                for step in operation_steps
                if step.program_node_id is not None
            ],
            "output_execution_id": execution_ids[output_node_id],
        },
        "verification_result": (
            None
            if verify_step is None
            else _translate_value(
                verify_step.observation.get("verified_result"),
                result_mapping,
            )
        ),
        "final_answer": _translate_value(trajectory.final_answer, result_mapping),
    }


def _translate_execution_ref(value: str, execution_ids: dict[str, str]) -> str:
    if not value.startswith("operation:"):
        return value
    node_id, separator, selector = value.removeprefix("operation:").partition("#")
    suffix = f"#{selector}" if separator else ""
    return f"execution:{execution_ids[node_id]}{suffix}"


def _translate_ref(value: str, mapping: dict[str, str]) -> str:
    if not value.startswith("operation:"):
        return value
    node_id, separator, selector = value.removeprefix("operation:").partition("#")
    suffix = f"#{selector}" if separator else ""
    return f"operation:{mapping.get(node_id, node_id)}{suffix}"


def _translate_value(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _translate_value(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_translate_value(item, mapping) for item in value]
    if isinstance(value, tuple):
        return [_translate_value(item, mapping) for item in value]
    if isinstance(value, str):
        return _translate_ref(value, mapping)
    return value


def _search_response(scope: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "subject_ids",
        "predicates",
        "temporal_labels",
        "aliases",
        "source_authorities",
        "semantic_constraints",
        "partial_constraints",
    }
    return {
        "schema_version": "agent_search.v1",
        "plan_summary": "Search the bounded corpus using public semantic constraints.",
        "search_query": {key: value for key, value in scope.items() if key in allowed},
    }


def test_plan_given_result_execution_refs_are_canonicalized_before_replay() -> None:
    case = next(
        item
        for item in build_pattern_validation_cases(per_domain=3)
        if item.task.public.metadata["task_pattern"]["pattern_id"] == "legal.rule_application"
    )
    task = materialize_track_variant(
        case.task,
        case.corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    deterministic = PlanGivenContractCandidate(case.registry).generate(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    payload = _response_from_trajectory(deterministic)
    execution_ids = {
        step["planned_node_id"]: step["execution_id"]
        for step in payload["execution_trace"]["steps"]
    }

    def to_execution_refs(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: to_execution_refs(item) for key, item in value.items()}
        if isinstance(value, list):
            return [to_execution_refs(item) for item in value]
        if isinstance(value, str) and value in execution_ids:
            return f"execution:{execution_ids[value]}"
        return value

    for step in payload["execution_trace"]["steps"]:
        step["observation"]["result"] = to_execution_refs(step["observation"]["result"])
    payload["verification_result"] = to_execution_refs(payload["verification_result"])
    payload["final_answer"]["result"] = to_execution_refs(payload["final_answer"]["result"])

    result = LLMAgentSolver(ScriptedJsonClient([payload]), case.registry).solve_with_audit(
        task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    compiled, runtime = _compile_runtime(case, task)
    assessment = runtime.evaluate(
        compiled.quality_contract, task, case.corpus, case.proof_graph, result.trajectory
    )

    assert assessment.decision.value == "accepted"
    assert result.trajectory.final_answer["result"]["selected_ref"] == "apply_2"
