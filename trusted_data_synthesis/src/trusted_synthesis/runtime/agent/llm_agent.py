from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.schema import (
    PlanningTrack,
    RetrievalTrack,
    TaskPublicSpec,
    TaskRequirement,
)
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import JsonCompletionClient, LLMClientError
from trusted_synthesis.runtime.agent.host_execution import (
    ActionPlanExecutionError,
    assemble_host_response,
    execute_action_plan,
    make_failed_action_plan,
    model_visible_execution_result,
)
from trusted_synthesis.runtime.agent.schema import (
    AgentActionPlanContract,
    AgentAnswerDecisionContract,
    AgentExecutionTrace,
    AgentGenerationAudit,
    AgentResponseContract,
    AgentSearchResponseContract,
    AgentSolveResult,
    FailedActionPlan,
    HostInteractionProgress,
    ModelCallTelemetry,
)
from trusted_synthesis.runtime.tools import EvidenceToolRuntime

LLM_AGENT_SOLVER_VERSION = "llm_agent_solver.v7"
LLM_AGENT_PROMPT_VERSION = "agent_candidate_prompt.v7"
LLM_AGENT_LEGACY_PROMPT_VERSION = "agent_candidate_prompt.v6"
LLM_AGENT_ACTION_PROMPT_VERSION = "agent_action_prompt.v1"
LLM_AGENT_FINAL_ANSWER_PROMPT_VERSION = "agent_final_answer_prompt.v1"
LLM_AGENT_SEARCH_PROMPT_VERSION = "agent_search_prompt.v1"


class LLMAgentSolver:
    """Generate a public-only candidate and preserve model errors for independent review."""

    def __init__(
        self,
        client: JsonCompletionClient,
        operation_registry: OperationRegistry,
    ) -> None:
        self._client = client
        self._registry = operation_registry

    def solve(self, task: TaskPublicSpec, environment: EvidenceToolRuntime) -> Trajectory:
        return self.solve_with_audit(task, environment).trajectory

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory:
        return self.solve(task, runtime)

    def solve_with_audit(
        self,
        task: TaskPublicSpec,
        environment: EvidenceToolRuntime,
    ) -> AgentSolveResult:
        telemetry: list[ModelCallTelemetry] = []
        repair_count = 0
        model_search_used = task.retrieval_track != RetrievalTrack.RESOLVED
        search_prompt_manifest_hash: str | None = None
        action_prompt_manifest_hash: str | None = None
        final_answer_prompt_manifest_hash: str | None = None
        action_failure_history: tuple[FailedActionPlan, ...] = ()
        search_plan_summary: str | None = None
        executed_search_query = dict(task.retrieval_scope)
        if model_search_used:
            search_prompt, search_prompt_manifest_hash = _build_search_prompt(task)
            search_response, search_telemetry, search_repairs = _request_search_response(
                self._client,
                search_prompt,
            )
            telemetry.extend(search_telemetry)
            repair_count += search_repairs
            search_plan_summary = search_response.plan_summary
            executed_search_query = _bounded_search_query(
                task,
                search_response.search_query.model_dump(
                    mode="json",
                    exclude_defaults=True,
                ),
            )
        retrieved = environment.search(executed_search_query)
        operation_catalog = _public_operation_catalog(self._registry, task)
        if self._client.config.interaction_protocol == "host_instrumented":
            action_prompt, action_prompt_manifest_hash = _build_action_prompt(
                task,
                retrieved,
                operation_catalog,
                executed_search_query,
            )
            (
                action_plan,
                execution_trace,
                action_telemetry,
                action_repairs,
                action_failure_history,
            ) = (
                _request_host_action_plan(
                    self._client,
                    action_prompt,
                    task,
                    retrieved,
                    self._registry,
                )
            )
            telemetry.extend(action_telemetry)
            repair_count += action_repairs
            final_prompt, final_answer_prompt_manifest_hash = _build_final_answer_prompt(
                task,
                retrieved,
                action_plan,
                execution_trace,
            )
            response, final_telemetry, final_repairs = _request_host_answer(
                self._client,
                final_prompt,
                task,
                retrieved,
                action_plan,
                execution_trace,
                self._registry,
                action_contract_repair_count=action_repairs,
            )
            telemetry.extend(final_telemetry)
            repair_count += final_repairs
            answer_repairs = final_repairs
            answer_prompt_manifest_hash = canonical_hash(
                {
                    "action_prompt_manifest_hash": action_prompt_manifest_hash,
                    "final_answer_prompt_manifest_hash": final_answer_prompt_manifest_hash,
                },
                prefix="agent_host_prompt_bundle:",
            )
            execution_source = "host_instrumented_execution"
        else:
            base_prompt, answer_prompt_manifest_hash = _build_prompt(
                task,
                retrieved,
                operation_catalog,
                executed_search_query,
            )
            response, answer_telemetry, answer_repairs = _request_agent_response(
                self._client,
                base_prompt,
                task,
                retrieved,
                self._registry,
            )
            telemetry.extend(answer_telemetry)
            repair_count += answer_repairs
            execution_source = "model_reported_execution_trace"
        trajectory = _normalize_trajectory(
            task,
            retrieved,
            response,
            self._registry,
            executed_search_query=executed_search_query,
            search_plan_summary=search_plan_summary,
            execution_source=execution_source,
        )
        response_hash = canonical_hash(response, prefix="agent_response:")
        prompt_manifest_hash = canonical_hash(
            {
                "search_prompt_manifest_hash": search_prompt_manifest_hash,
                "answer_prompt_manifest_hash": answer_prompt_manifest_hash,
            },
            prefix="agent_prompt_bundle:",
        )
        executed_search_query_hash = canonical_hash(
            executed_search_query,
            prefix="agent_search_query:",
        )
        selected_model = next(
            (
                item.response_model or item.model_selected
                for item in reversed(telemetry)
                if item.http_success
            ),
            None,
        )
        audit_identity = {
            "task_id": task.task_id,
            "trajectory_id": trajectory.trajectory_id,
            "model_config_hash": self._client.config.public_manifest_hash,
            "prompt_manifest_hash": prompt_manifest_hash,
            "response_contract_hash": response_hash,
            "executed_search_query_hash": executed_search_query_hash,
            "telemetry_request_hashes": tuple(item.request_hash for item in telemetry),
        }
        audit = AgentGenerationAudit(
            audit_id=canonical_hash(audit_identity, prefix="agent_generation_audit:"),
            task_id=task.task_id,
            trajectory_id=trajectory.trajectory_id,
            retrieval_track=task.retrieval_track.value,
            planning_track=task.planning_track.value,
            model_config_hash=self._client.config.public_manifest_hash,
            prompt_manifest_hash=prompt_manifest_hash,
            search_prompt_manifest_hash=search_prompt_manifest_hash,
            answer_prompt_manifest_hash=answer_prompt_manifest_hash,
            action_prompt_manifest_hash=action_prompt_manifest_hash,
            final_answer_prompt_manifest_hash=final_answer_prompt_manifest_hash,
            interaction_protocol=self._client.config.interaction_protocol,
            executed_search_query_hash=executed_search_query_hash,
            model_search_used=model_search_used,
            response_contract_hash=response_hash,
            telemetry=tuple(telemetry),
            selected_model=selected_model,
            contract_repair_count=repair_count,
            search_contract_repair_count=search_repairs if model_search_used else 0,
            action_contract_repair_count=(
                action_repairs
                if self._client.config.interaction_protocol == "host_instrumented"
                else 0
            ),
            answer_contract_repair_count=answer_repairs,
            action_failure_history=action_failure_history,
            host_replay_available=(
                self._client.config.interaction_protocol == "host_instrumented"
            ),
            execution_replay_valid=(
                True if self._client.config.interaction_protocol == "host_instrumented" else None
            ),
        )
        return AgentSolveResult(trajectory=trajectory, audit=audit)


def _request_search_response(
    client: JsonCompletionClient,
    base_prompt: str,
) -> tuple[AgentSearchResponseContract, tuple[ModelCallTelemetry, ...], int]:
    telemetry: list[ModelCallTelemetry] = []
    previous_payload: dict[str, Any] | None = None
    validation_error = ""
    response: AgentSearchResponseContract | None = None
    for attempt in range(client.config.contract_repair_attempts + 1):
        prompt = (
            base_prompt
            if attempt == 0
            else _repair_prompt(base_prompt, previous_payload, validation_error)
        )
        payload, call_telemetry = client.complete_json(prompt)
        previous_payload = payload
        try:
            response = AgentSearchResponseContract.model_validate(payload)
            telemetry.append(call_telemetry)
            break
        except ValidationError as exc:
            contract_errors = _contract_errors(exc)
            validation_error = "; ".join(contract_errors)
            telemetry.append(
                _invalid_contract_telemetry(
                    call_telemetry,
                    "AgentSearchContractError",
                    contract_errors=contract_errors,
                    payload=payload,
                )
            )
    if response is None:
        raise LLMClientError("model failed the agent search contract", tuple(telemetry))
    return response, tuple(telemetry), max(len(telemetry) - 1, 0)


def _request_agent_response(
    client: JsonCompletionClient,
    base_prompt: str,
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    registry: OperationRegistry,
) -> tuple[AgentResponseContract, tuple[ModelCallTelemetry, ...], int]:
    telemetry: list[ModelCallTelemetry] = []
    previous_payload: dict[str, Any] | None = None
    validation_error = ""
    response: AgentResponseContract | None = None
    for attempt in range(client.config.contract_repair_attempts + 1):
        prompt = (
            base_prompt
            if attempt == 0
            else _repair_prompt(base_prompt, previous_payload, validation_error)
        )
        payload, call_telemetry = client.complete_json(prompt)
        previous_payload = payload
        try:
            candidate = AgentResponseContract.model_validate(payload)
            _validate_agent_response_contract(task, retrieved, candidate, registry)
            response = candidate
            telemetry.append(call_telemetry)
            break
        except (ValidationError, ValueError) as exc:
            contract_errors = _contract_errors(exc)
            validation_error = "; ".join(contract_errors)
            telemetry.append(
                _invalid_contract_telemetry(
                    call_telemetry,
                    "AgentContractValidationError",
                    contract_errors=contract_errors,
                    payload=payload,
                )
            )
    if response is None:
        raise LLMClientError("model failed the agent response contract", tuple(telemetry))
    return response, tuple(telemetry), max(len(telemetry) - 1, 0)


def _request_host_action_plan(
    client: JsonCompletionClient,
    base_prompt: str,
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    registry: OperationRegistry,
) -> tuple[
    AgentActionPlanContract,
    AgentExecutionTrace,
    tuple[ModelCallTelemetry, ...],
    int,
    tuple[FailedActionPlan, ...],
]:
    telemetry: list[ModelCallTelemetry] = []
    previous_payload: dict[str, Any] | None = None
    validation_error = ""
    accepted_plan: AgentActionPlanContract | None = None
    execution_trace: AgentExecutionTrace | None = None
    failed_actions: list[FailedActionPlan] = []
    for attempt in range(client.config.contract_repair_attempts + 1):
        prompt = (
            base_prompt
            if attempt == 0
            else _repair_prompt(base_prompt, previous_payload, validation_error)
        )
        try:
            payload, call_telemetry = client.complete_json(prompt)
        except LLMClientError as exc:
            raise LLMClientError(
                "model call failed during the host action stage",
                (*telemetry, *exc.telemetry),
                failure_artifact=(failed_actions[-1] if failed_actions else None),
                interaction_progress=HostInteractionProgress(
                    action_plan_attempted=True,
                    action_plan_contract_succeeded=bool(failed_actions),
                    action_contract_repair_count=attempt,
                ),
            ) from exc
        previous_payload = payload
        try:
            candidate = AgentActionPlanContract.model_validate(payload)
            trace = execute_action_plan(task, retrieved, candidate, registry)
            accepted_plan = candidate
            execution_trace = trace
            telemetry.append(call_telemetry)
            break
        except ActionPlanExecutionError as exc:
            failed_action = make_failed_action_plan(
                task,
                candidate,
                exc,
                attempt_number=attempt + 1,
            )
            failed_actions.append(failed_action)
            contract_errors: tuple[str, ...] = (f"{exc.error_code}:{exc}",)
            validation_error = "; ".join(contract_errors)
            telemetry.append(
                _invalid_contract_telemetry(
                    call_telemetry,
                    (
                        "AgentSemanticActionError"
                        if exc.category == "semantic_action"
                        else "AgentActionInterfaceError"
                    ),
                    contract_errors=contract_errors,
                    payload=payload,
                )
            )
        except ValidationError as exc:
            contract_errors = _contract_errors(exc)
            validation_error = "; ".join(contract_errors)
            telemetry.append(
                _invalid_contract_telemetry(
                    call_telemetry,
                    "AgentActionContractError",
                    contract_errors=contract_errors,
                    payload=payload,
                )
            )
    if accepted_plan is None or execution_trace is None:
        raise LLMClientError(
            "model failed the host action contract",
            tuple(telemetry),
            failure_artifact=(failed_actions[-1] if failed_actions else None),
            interaction_progress=HostInteractionProgress(
                action_plan_attempted=True,
                action_plan_contract_succeeded=bool(failed_actions),
                action_contract_repair_count=max(len(telemetry) - 1, 0),
            ),
        )
    return (
        accepted_plan,
        execution_trace,
        tuple(telemetry),
        max(len(telemetry) - 1, 0),
        tuple(failed_actions),
    )


def _request_host_answer(
    client: JsonCompletionClient,
    base_prompt: str,
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    action_plan: AgentActionPlanContract,
    execution_trace: AgentExecutionTrace,
    registry: OperationRegistry,
    *,
    action_contract_repair_count: int,
) -> tuple[AgentResponseContract, tuple[ModelCallTelemetry, ...], int]:
    telemetry: list[ModelCallTelemetry] = []
    previous_payload: dict[str, Any] | None = None
    validation_error = ""
    response: AgentResponseContract | None = None
    for attempt in range(client.config.contract_repair_attempts + 1):
        prompt = (
            base_prompt
            if attempt == 0
            else _repair_prompt(base_prompt, previous_payload, validation_error)
        )
        try:
            payload, call_telemetry = client.complete_json(prompt)
        except LLMClientError as exc:
            raise LLMClientError(
                "model call failed during the host answer stage",
                (*telemetry, *exc.telemetry),
                interaction_progress=HostInteractionProgress(
                    action_plan_attempted=True,
                    action_plan_contract_succeeded=True,
                    host_execution_evaluable=True,
                    answer_decision_attempted=True,
                    action_contract_repair_count=action_contract_repair_count,
                    answer_contract_repair_count=attempt,
                ),
            ) from exc
        previous_payload = payload
        try:
            answer = AgentAnswerDecisionContract.model_validate(payload)
            candidate = assemble_host_response(
                task,
                retrieved,
                action_plan,
                execution_trace,
                answer,
            )
            _validate_agent_response_contract(task, retrieved, candidate, registry)
            response = candidate
            telemetry.append(call_telemetry)
            break
        except (ValidationError, ValueError) as exc:
            contract_errors = _contract_errors(exc)
            validation_error = "; ".join(contract_errors)
            telemetry.append(
                _invalid_contract_telemetry(
                    call_telemetry,
                    "AgentAnswerContractError",
                    contract_errors=contract_errors,
                    payload=payload,
                )
            )
    if response is None:
        raise LLMClientError(
            "model failed the host answer contract",
            tuple(telemetry),
            interaction_progress=HostInteractionProgress(
                action_plan_attempted=True,
                action_plan_contract_succeeded=True,
                host_execution_evaluable=True,
                answer_decision_attempted=True,
                action_contract_repair_count=action_contract_repair_count,
                answer_contract_repair_count=max(len(telemetry) - 1, 0),
            ),
        )
    return response, tuple(telemetry), max(len(telemetry) - 1, 0)


def _invalid_contract_telemetry(
    telemetry: ModelCallTelemetry,
    error_type: str,
    *,
    contract_errors: tuple[str, ...] = (),
    payload: dict[str, Any] | None = None,
) -> ModelCallTelemetry:
    return telemetry.model_copy(
        update={
            "json_contract_success": False,
            "error_type": error_type,
            "error_message": contract_errors[0] if contract_errors else None,
            "contract_errors": contract_errors,
            "response_shape": _response_shape(payload),
        }
    )


def _contract_errors(exc: ValidationError | ValueError) -> tuple[str, ...]:
    if isinstance(exc, ValidationError):
        return tuple(
            ":".join(
                (
                    ".".join(str(item) for item in error.get("loc") or ("root",)),
                    str(error.get("type") or "validation_error"),
                    str(error.get("msg") or "invalid value"),
                )
            )
            for error in exc.errors(include_input=False, include_url=False)
        )
    message = " ".join(str(exc).split())
    return (message[:1000] or type(exc).__name__,)


def _response_shape(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}

    def shape(value: Any, depth: int) -> dict[str, Any]:
        if depth >= 4:
            return {"type": type(value).__name__}
        if isinstance(value, dict):
            keys = sorted(str(key) for key in value)[:50]
            return {
                "type": "object",
                "keys": keys,
                "properties": {key: shape(value[key], depth + 1) for key in keys},
            }
        if isinstance(value, (list, tuple)):
            return {
                "type": "array",
                "length": len(value),
                "item_shapes": [shape(item, depth + 1) for item in value[:3]],
            }
        return {"type": type(value).__name__}

    return shape(payload, 0)


def _validate_agent_response_contract(
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    response: AgentResponseContract,
    registry: OperationRegistry,
) -> None:
    retrieved_by_id = {item.evidence_id: item for item in retrieved}
    retrieved_ids = set(retrieved_by_id)
    if len(response.selected_evidence_ids) != len(set(response.selected_evidence_ids)):
        raise ValueError("selected_evidence_ids must be unique")
    unknown_selected = set(response.selected_evidence_ids) - retrieved_ids
    if unknown_selected:
        raise ValueError(f"selected evidence was not retrieved: {sorted(unknown_selected)}")
    final_answer = response.final_answer.model_dump(mode="json", exclude_none=True)
    answer_schema_passed, answer_schema_failures = CandidateAnswerNormalizer().validate_schema(
        task,
        final_answer,
    )
    if not answer_schema_passed:
        raise ValueError(
            "final_answer violates the task answer schema: "
            + "; ".join(answer_schema_failures)
        )
    citations = response.final_answer.citations
    citation_ids = tuple(item.evidence_id for item in citations)
    if len(citation_ids) != len(set(citation_ids)):
        raise ValueError("final_answer citations must be unique")
    if set(citation_ids) != set(response.selected_evidence_ids):
        raise ValueError("final_answer citations must exactly cover selected_evidence_ids")
    for citation in citations:
        evidence = retrieved_by_id[citation.evidence_id]
        expected_locator = evidence.source_locator.model_dump(mode="json", exclude_none=True)
        if citation.source_id != evidence.source.source_id:
            raise ValueError("citation source_id does not match retrieved evidence")
        if citation.source_locator != expected_locator:
            raise ValueError("citation source_locator does not match retrieved evidence")
    executions = response.execution_trace.steps
    for execution in executions:
        definition = registry.require(execution.operator_id)
        registry.validate_output(definition, execution.observation["result"])
        if execution.tool_name != definition.tool_capability:
            raise ValueError(
                f"execution tool_name must equal registered tool_capability for "
                f"{execution.operator_id}: {definition.tool_capability!r}"
            )
        unknown_lineage = set(execution.evidence_ids) - retrieved_ids
        if unknown_lineage:
            raise ValueError(
                "execution lineage contains evidence that was not retrieved: "
                f"{sorted(unknown_lineage)}"
            )
        for ref in execution.input_refs:
            if ref.startswith("execution:"):
                continue
            evidence_id = _evidence_id_from_ref(ref)
            if evidence_id not in retrieved_ids:
                raise ValueError(
                    "execution evidence ref does not resolve to retrieved evidence: "
                    f"{ref}; use evidence:<full evidence_id>, for example "
                    "evidence:evidence:domain:item@version"
                )
    if TaskRequirement.VERIFY_RESULT in task.requirements and response.verification_result is None:
        raise ValueError("verification_result is required by the public task")
    output_execution = next(
        item
        for item in executions
        if item.execution_id == response.execution_trace.output_execution_id
    )
    if (
        TaskRequirement.VERIFY_RESULT in task.requirements
        and response.verification_result != output_execution.observation["result"]
    ):
        raise ValueError(
            "verification_result must exactly equal the output execution observation.result"
        )
    if task.planning_track != PlanningTrack.PLAN_GIVEN:
        if any(item.planned_node_id is not None for item in executions):
            raise ValueError("plan-hidden executions cannot claim hidden planned node IDs")
        return
    if task.program_skeleton is None:
        raise ValueError("plan_given task is missing its public program skeleton")
    expected = task.program_skeleton.nodes
    if len(executions) != len(expected):
        raise ValueError("agent execution count does not cover the public program skeleton")
    for execution, node in zip(executions, expected, strict=True):
        if execution.planned_node_id != node.public_node_id:
            raise ValueError("each concrete execution must bind to its public plan node")
        if execution.execution_id == node.public_node_id:
            raise ValueError("execution IDs must be distinct from public plan node IDs")
        if execution.operator_id != node.operator_id:
            raise ValueError("agent executions must preserve public plan operators")
        if canonical_hash(
            execution.parameters,
            prefix="agent_execution_parameters:",
        ) != canonical_hash(node.parameters, prefix="agent_execution_parameters:"):
            raise ValueError(
                "agent executions must preserve public plan parameters: "
                f"node={node.public_node_id}, "
                f"expected={json.dumps(node.parameters, ensure_ascii=False, sort_keys=True)}, "
                f"observed={json.dumps(execution.parameters, ensure_ascii=False, sort_keys=True)}"
            )
    if output_execution.planned_node_id != task.program_skeleton.output_node_id:
        raise ValueError("execution trace output must bind to the public output node")


def _build_search_prompt(task: TaskPublicSpec) -> tuple[str, str]:
    response_schema = AgentSearchResponseContract.model_json_schema()
    manifest = {
        "prompt_version": LLM_AGENT_SEARCH_PROMPT_VERSION,
        "response_schema_hash": canonical_hash(
            response_schema,
            prefix="agent_search_response_schema:",
        ),
    }
    payload = {
        "task_public_spec": task.model_dump(mode="json", exclude_none=True),
        "search_interface": {
            "allowed_fields": (
                "subject_ids",
                "predicates",
                "temporal_labels",
                "aliases",
                "source_authorities",
                "semantic_constraints",
                "partial_constraints",
            ),
            "forbidden_fields": ("evidence_ids", "gold_ids", "oracle_contract"),
        },
        "response_json_schema": response_schema,
    }
    instructions = (
        "Plan one bounded evidence search from the public task. Return only a JSON object "
        "matching response_json_schema. Never invent or request evidence IDs, gold IDs, "
        "or oracle fields. Use aliases for natural-language entity names and use only "
        "constraints supported by search_interface. The host preserves the immutable "
        "corpus boundary. Do not answer the task in this phase."
    )
    prompt = (
        f"{instructions}\n\nPAYLOAD:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )
    return prompt, canonical_hash(manifest, prefix="agent_search_prompt_manifest:")


def _bounded_search_query(
    task: TaskPublicSpec,
    model_query: dict[str, Any],
) -> dict[str, Any]:
    query = {key: value for key, value in model_query.items() if value not in (None, [], {}, ())}
    if query.get("semantic_constraints"):
        query["apply_semantic_filters"] = True
    corpus_boundary = task.retrieval_scope.get("corpus_boundary")
    if corpus_boundary is not None:
        query["corpus_boundary"] = corpus_boundary
    return query


def _build_action_prompt(
    task: TaskPublicSpec,
    evidence: tuple[EvidenceItem, ...],
    operation_catalog: tuple[dict[str, Any], ...],
    executed_search_query: dict[str, Any],
) -> tuple[str, str]:
    response_schema = AgentActionPlanContract.model_json_schema()
    task_execution_contract = _task_execution_contract(task, operation_catalog)
    manifest = {
        "prompt_version": LLM_AGENT_ACTION_PROMPT_VERSION,
        "response_schema_hash": canonical_hash(
            response_schema,
            prefix="agent_action_plan_schema:",
        ),
        "operation_catalog_hash": canonical_hash(
            operation_catalog,
            prefix="agent_operation_catalog:",
        ),
        "task_execution_contract_hash": canonical_hash(
            task_execution_contract,
            prefix="agent_task_execution_contract:",
        ),
    }
    payload = {
        "task_public_spec": task.model_dump(mode="json", exclude_none=True),
        "executed_search_query": executed_search_query,
        "retrieved_evidence": [
            item.model_dump(mode="json", exclude_none=True) for item in evidence
        ],
        "operation_catalog": operation_catalog,
        "task_execution_contract": task_execution_contract,
        "action_input_contract": {
            "evidence": {
                "source": "evidence",
                "evidence_id": "copy one exact retrieved evidence_id",
                "step_index": None,
                "selector": "optional payload path",
            },
            "step": {
                "source": "step",
                "evidence_id": None,
                "step_index": "one-based index of an earlier execution decision",
                "selector": "optional operation-result path",
            },
            "host_owned_fields": (
                "execution_id",
                "tool_name",
                "observation",
                "status",
                "source_locator",
                "evidence_lineage",
            ),
        },
        "response_json_schema": response_schema,
    }
    instructions = (
        "Choose the evidence and operations needed to solve the public task. Return only "
        "one JSON object matching response_json_schema. You decide selected evidence, "
        "operator IDs, semantic inputs, parameters, and the output step. The host executes "
        "those decisions and records immutable IDs, tool observations, source locators, and "
        "lineage; never emit those host-owned fields. Evidence inputs copy an exact retrieved "
        "evidence_id. Step inputs use the one-based index of an earlier decision. For "
        "plan_given tasks, preserve the public node order, operator, input kind, selector, "
        "dependency, and exact parameters. For plan_hidden tasks, use only registered "
        "operators allowed by the public tool policy. selected_evidence_ids must be unique "
        "and exactly equal the evidence used by all decisions. The output step must be the "
        "last execution. Do not answer the task in this phase and include no text outside JSON."
    )
    prompt = (
        f"{instructions}\n\nPAYLOAD:\n"
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )
    return prompt, canonical_hash(manifest, prefix="agent_action_prompt_manifest:")


def _build_final_answer_prompt(
    task: TaskPublicSpec,
    evidence: tuple[EvidenceItem, ...],
    action_plan: AgentActionPlanContract,
    execution_trace: AgentExecutionTrace,
) -> tuple[str, str]:
    response_schema = AgentAnswerDecisionContract.model_json_schema()
    final_answer_contract = _final_answer_contract(task)
    output_execution = next(
        item
        for item in execution_trace.steps
        if item.execution_id == execution_trace.output_execution_id
    )
    selected = set(action_plan.selected_evidence_ids)
    selected_evidence = tuple(item for item in evidence if item.evidence_id in selected)
    manifest = {
        "prompt_version": LLM_AGENT_FINAL_ANSWER_PROMPT_VERSION,
        "response_schema_hash": canonical_hash(
            response_schema,
            prefix="agent_answer_decision_schema:",
        ),
        "final_answer_contract_hash": canonical_hash(
            final_answer_contract,
            prefix="agent_final_answer_contract:",
        ),
        "action_plan_hash": canonical_hash(action_plan, prefix="agent_action_plan:"),
    }
    payload = {
        "task_public_spec": task.model_dump(mode="json", exclude_none=True),
        "selected_evidence": [
            item.model_dump(mode="json", exclude_none=True) for item in selected_evidence
        ],
        "host_execution": {
            "steps": [
                {
                    "step_index": index,
                    "operator_id": item.operator_id,
                    "parameters": item.parameters,
                    "result": model_visible_execution_result(
                        execution_trace,
                        item.observation["result"],
                    ),
                    "evidence_ids": item.evidence_ids,
                }
                for index, item in enumerate(execution_trace.steps, start=1)
            ],
            "output_step_index": action_plan.output_step_index,
            "output_result": model_visible_execution_result(
                execution_trace,
                output_execution.observation["result"],
            ),
        },
        "final_answer_contract": final_answer_contract,
        "domain_contract_guidance": task.metadata.get("agent_contract_guidance") or {},
        "citation_contract": {
            "required_evidence_ids": action_plan.selected_evidence_ids,
            "rule": (
                "cited_evidence_ids must contain every required raw evidence ID exactly once; "
                "the host attaches source IDs and locators"
            ),
        },
        "response_json_schema": response_schema,
    }
    instructions = (
        "Answer the public task from the host-executed results and selected evidence. Return "
        "only one JSON object matching response_json_schema. Keep exact machine values and "
        "exact result field names required by final_answer_contract; do not append units or "
        "explanations inside numeric machine fields. Copy all required evidence IDs into "
        "cited_evidence_ids exactly once. Do not emit source locators, execution IDs, tool "
        "observations, verification wrappers, or any commentary outside JSON. The host owns "
        "those records and will independently bind them."
    )
    prompt = (
        f"{instructions}\n\nPAYLOAD:\n"
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )
    return prompt, canonical_hash(manifest, prefix="agent_final_answer_prompt_manifest:")


def _build_prompt(
    task: TaskPublicSpec,
    evidence: tuple[EvidenceItem, ...],
    operation_catalog: tuple[dict[str, Any], ...],
    executed_search_query: dict[str, Any],
) -> tuple[str, str]:
    response_schema = AgentResponseContract.model_json_schema()
    task_execution_contract = _task_execution_contract(task, operation_catalog)
    final_answer_contract = _final_answer_contract(task)
    domain_contract_guidance = task.metadata.get("agent_contract_guidance") or {}
    manifest = {
        "prompt_version": LLM_AGENT_LEGACY_PROMPT_VERSION,
        "response_schema_hash": canonical_hash(response_schema, prefix="agent_response_schema:"),
        "operation_catalog_hash": canonical_hash(
            operation_catalog, prefix="agent_operation_catalog:"
        ),
        "task_execution_contract_hash": canonical_hash(
            task_execution_contract,
            prefix="agent_task_execution_contract:",
        ),
        "final_answer_contract_hash": canonical_hash(
            final_answer_contract,
            prefix="agent_final_answer_contract:",
        ),
        "domain_contract_guidance_hash": canonical_hash(
            domain_contract_guidance,
            prefix="agent_domain_contract_guidance:",
        ),
    }
    payload = {
        "task_public_spec": task.model_dump(mode="json", exclude_none=True),
        "executed_search_query": executed_search_query,
        "retrieved_evidence": [
            item.model_dump(mode="json", exclude_none=True) for item in evidence
        ],
        "evidence_identifier_contract": {
            "exact_evidence_ids": [item.evidence_id for item in evidence],
            "raw_id_fields": (
                "selected_evidence_ids",
                "execution_trace.steps[].evidence_ids",
                "final_answer.citations[].evidence_id",
                "operation result reference fields such as selected_ref and higher_ref",
            ),
            "input_ref_examples": {
                item.evidence_id: f"evidence:{item.evidence_id}" for item in evidence
            },
            "rule": (
                "Only input_refs add the evidence: reference prefix. Every raw ID field "
                "copies exact_evidence_ids without adding a prefix."
            ),
        },
        "operation_catalog": operation_catalog,
        "task_execution_contract": task_execution_contract,
        "final_answer_contract": final_answer_contract,
        "domain_contract_guidance": domain_contract_guidance,
        "execution_contract": {
            "program_skeleton": (
                "a non-executed specification; never copy its node records as results"
            ),
            "execution_trace": (
                "concrete tool calls with bound evidence, observations, and outputs"
            ),
            "input_ref_kinds": (
                "evidence:<full evidence_id>",
                "execution:<earlier execution_id>",
            ),
            "verification_result": (
                "when required, an exact copy of output execution observation.result"
            ),
        },
        "response_json_schema": response_schema,
    }
    instructions = (
        "You are an evidence-grounded agent candidate. Use only the public task and "
        "retrieved evidence below. Never infer hidden gold IDs or an oracle answer. "
        "Return exactly one JSON object matching response_json_schema. A public "
        "program_skeleton is a plan, not an execution result: do not copy its inputs, "
        "dependencies, or output schema into execution_trace. Execute each operation "
        "against concrete retrieved evidence or an earlier execution result. Give every "
        "execution a fresh execution_id, set tool_name exactly to the operation catalog's "
        "tool_capability (including null), and provide concrete "
        "input_refs, direct evidence_ids, status, and a structured observation.result. "
        "Evidence refs use evidence:<full evidence_id>; when the full ID is "
        "evidence:finance:item@v1, write evidence:evidence:finance:item@v1. "
        "This double prefix applies only inside input_refs. In selected_evidence_ids, "
        "execution evidence_ids, citations, selected_ref, and higher_ref, copy the raw "
        "retrieved evidence_id exactly once. "
        "Execution "
        "refs use execution:<earlier execution_id> with an optional #selector. For "
        "plan_given, bind planned_node_id to the corresponding public node while keeping "
        "execution_id distinct; preserve operator order and parameters. For plan_hidden, "
        "planned_node_id must be null and the trace must be topologically valid. Set "
        "output_execution_id to the execution producing the answer. Follow every exact "
        "result field and enum in task_execution_contract; do not rename semantic fields. "
        "Select only evidence used by the execution and copy citation fields exactly. The "
        "final_answer top level must contain result and citations, never raw payload fields. "
        "When verification_result is required, copy output observation.result exactly, not "
        "a status or notes wrapper. Include no commentary outside JSON."
    )
    prompt = (
        f"{instructions}\n\nPAYLOAD:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )
    return prompt, canonical_hash(manifest, prefix="agent_prompt_manifest:")


def _repair_prompt(
    base_prompt: str,
    previous_payload: dict[str, Any] | None,
    validation_error: str,
) -> str:
    repair = {
        "previous_response": previous_payload,
        "contract_error": validation_error,
        "repair_rule": (
            "Repair JSON shape, exact typed result fields, citations, tool binding, and graph "
            "ordering. Recompute only from the same retrieved evidence and public operators "
            "when required by the contract error. Never substitute a hidden or externally "
            "supplied answer."
        ),
    }
    return (
        f"{base_prompt}\n\n"
        f"CONTRACT_REPAIR:\n{json.dumps(repair, ensure_ascii=False, sort_keys=True)}"
    )


def _public_operation_catalog(
    registry: OperationRegistry,
    task: TaskPublicSpec,
) -> tuple[dict[str, Any], ...]:
    manifest = registry.manifest()
    if task.program_skeleton is not None:
        allowed_operator_ids = {
            node.operator_id for node in task.program_skeleton.nodes
        }
    else:
        allowed_tools = set(task.allowed_tools)
        allowed_operator_ids = {
            str(item["operator_id"])
            for item in manifest
            if item["action_type"] == "select_evidence"
            or item["tool_capability"] in allowed_tools
        }
    return tuple(
        {
            "operator_id": item["operator_id"],
            "input_schema": item["input_schema"],
            "output_schema": item["output_schema"],
            "output_model_schema": item["output_model_schema"],
            "tool_capability": item["tool_capability"],
            "action_type": item["action_type"],
            "invariant_checks": item["invariant_checks"],
        }
        for item in manifest
        if item["operator_id"] in allowed_operator_ids
    )


def _task_execution_contract(
    task: TaskPublicSpec,
    operation_catalog: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    by_operator = {str(item["operator_id"]): item for item in operation_catalog}
    node_contracts = []
    if task.program_skeleton is not None:
        for node in task.program_skeleton.nodes:
            operation = by_operator[node.operator_id]
            node_contracts.append(
                {
                    "public_node_id": node.public_node_id,
                    "operator_id": node.operator_id,
                    "required_tool_name": operation["tool_capability"],
                    "exact_parameters": node.parameters,
                    "observation_result_json_schema": operation["output_model_schema"],
                    "exact_result_field_rules": _operation_field_rules(node.operator_id),
                }
            )
    return {
        "planning_track": task.planning_track.value,
        "node_contracts": node_contracts,
        "allowed_operator_ids": [item["operator_id"] for item in operation_catalog],
        "output_public_node_id": (
            task.program_skeleton.output_node_id
            if task.program_skeleton is not None
            else None
        ),
        "verification_required": TaskRequirement.VERIFY_RESULT in task.requirements,
        "verification_rule": (
            "verification_result == output execution observation.result"
            if TaskRequirement.VERIFY_RESULT in task.requirements
            else "verification_result may be null"
        ),
        "machine_output_rule": (
            "Operation results are machine values. Do not append units, percent signs, "
            "explanations, display labels, or nested field names unless the exact output "
            "schema and field rules require them."
        ),
    }


def _operation_field_rules(operator_id: str) -> tuple[str, ...]:
    registered = {
        "lookup": (
            "selected_ref is the exact raw evidence_id of the selected input",
            "payload is an exact copy of that evidence payload",
        ),
        "compare": (
            "higher_ref is the exact raw input evidence_id with the greater value, or null",
            "difference is an unsigned plain decimal string with no unit text",
        ),
        "difference": (
            "value is a plain decimal string with no unit text",
        ),
        "ratio": (
            "value is a plain decimal string with no unit or percent suffix",
        ),
        "growth": (
            "value is the unrounded percentage number as a plain decimal string",
            "never append a percent sign or descriptive text",
        ),
        "aggregate": (
            "method is the exact registered method parameter",
            "value is the unrounded aggregate as a plain decimal string",
        ),
    }
    return registered.get(
        operator_id,
        (
            "Use only exact machine values allowed by the output JSON schema",
            "Do not replace registered enum strings with prose",
        ),
    )


def _final_answer_contract(task: TaskPublicSpec) -> dict[str, Any]:
    answer_type = str(task.answer_schema.get("type") or "")
    registered_fields = {
        "payload_with_source": ("payload", "source_id"),
        "comparison": ("higher_ref", "difference"),
        "percentage": ("value",),
        "aggregate": ("method", "value"),
    }
    required_result_fields = tuple(
        registered_fields.get(
            answer_type,
            tuple(task.answer_schema.get("required_fields") or ()),
        )
    )
    optional_result_fields = tuple(task.answer_schema.get("optional_fields") or ())
    allowed_top_level = ["result", "citations"]
    if task.answer_schema.get("allow_status") is True:
        allowed_top_level.append("status")
    if task.answer_schema.get("allow_claims") is True:
        allowed_top_level.append("claims")
    return {
        "answer_type": answer_type,
        "required_top_level_fields": ["result", "citations"],
        "allowed_top_level_fields": allowed_top_level,
        "required_result_fields": required_result_fields,
        "allowed_result_fields": tuple(
            dict.fromkeys((*required_result_fields, *optional_result_fields))
        ),
        "allowed_payload_fields": tuple(task.answer_schema.get("allowed_payload_fields") or ()),
        "additional_result_properties": False,
        "citation_fields": ("evidence_id", "source_id", "source_locator"),
        "citation_coverage": "exactly one citation per selected evidence ID",
        "envelope_example": {
            "result": {field: f"<{field}>" for field in required_result_fields},
            "citations": [
                {
                    "evidence_id": "<retrieved evidence_id>",
                    "source_id": "<exact source_id>",
                    "source_locator": {"<exact locator field>": "<exact locator value>"},
                }
            ],
        },
    }


def _normalize_trajectory(
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    response: AgentResponseContract,
    registry: OperationRegistry,
    *,
    executed_search_query: dict[str, Any],
    search_plan_summary: str | None,
    execution_source: str = "model_reported_execution_trace",
) -> Trajectory:
    selected_ids = tuple(dict.fromkeys(response.selected_evidence_ids))
    final_answer = response.final_answer.model_dump(mode="json", exclude_none=True)
    retrieved_ids = tuple(item.evidence_id for item in retrieved)
    executions = response.execution_trace.steps
    execution_node_ids = {
        item.execution_id: item.planned_node_id or item.execution_id for item in executions
    }
    canonical_execution_results = {
        item.execution_id: _canonicalize_execution_refs(
            item.observation["result"], execution_node_ids
        )
        for item in executions
    }
    final_answer["result"] = _canonicalize_execution_refs(
        final_answer["result"], execution_node_ids
    )
    canonical_verification_result = _canonicalize_execution_refs(
        response.verification_result, execution_node_ids
    )
    canonical_node_parameters = (
        {item.public_node_id: item.parameters for item in task.program_skeleton.nodes}
        if task.program_skeleton is not None
        else {}
    )
    steps = [
        TrajectoryStep(
            step_index=1,
            action=ActionType.PLAN,
            observation={
                "retrieval_track": task.retrieval_track.value,
                "planning_track": task.planning_track.value,
                "search_plan_summary": search_plan_summary,
                "model_plan_summary": response.plan_summary,
                "execution_trace_version": response.execution_trace.trace_version,
            },
            rationale_summary=response.plan_summary,
            status=StepStatus.SUCCEEDED,
        ),
        TrajectoryStep(
            step_index=2,
            action=ActionType.SEARCH,
            tool_name="evidence.search",
            tool_input=executed_search_query,
            observation={"matched_count": len(retrieved)},
            evidence_ids=retrieved_ids,
            rationale_summary="Search the public evidence environment within the declared scope.",
            status=StepStatus.SUCCEEDED,
        ),
        TrajectoryStep(
            step_index=3,
            action=ActionType.SELECT_EVIDENCE,
            observation={"selected_count": len(selected_ids)},
            evidence_ids=selected_ids,
            rationale_summary="Select evidence judged relevant to the requested answer.",
            status=StepStatus.SUCCEEDED,
        ),
    ]
    for execution in executions:
        definition = registry.require(execution.operator_id)
        node_id = execution_node_ids[execution.execution_id]
        input_refs = tuple(
            _execution_ref_to_program_ref(ref, execution_node_ids) for ref in execution.input_refs
        )
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType(definition.action_type),
                tool_name=execution.tool_name,
                # Execution identity belongs to the trace envelope and observation.
                # Keep tool_input identical to deterministic candidate workflows so
                # replay uses the frozen plan's canonical Python representation.
                tool_input={
                    "parameters": canonical_node_parameters.get(node_id, execution.parameters)
                },
                observation={
                    **execution.observation,
                    "result": canonical_execution_results[execution.execution_id],
                    "execution_id": execution.execution_id,
                },
                evidence_ids=execution.evidence_ids,
                program_node_id=node_id,
                operator_id=execution.operator_id,
                input_refs=input_refs,
                output_ref=f"operation:{node_id}",
                rationale_summary=execution.rationale_summary,
                status=StepStatus(execution.status),
            )
        )
    output_execution_id = response.execution_trace.output_execution_id
    output_node_id = execution_node_ids[output_execution_id]
    output_ref = f"operation:{output_node_id}"
    if TaskRequirement.VERIFY_RESULT in task.requirements:
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType.VERIFY,
                observation={
                    "verified_output_ref": output_ref,
                    "verified_result": canonical_verification_result or {},
                },
                evidence_ids=selected_ids,
                program_node_id=output_node_id,
                input_refs=(output_ref,),
                rationale_summary="Verify the model-reported final execution result.",
                status=StepStatus.SUCCEEDED,
            )
        )
    steps.append(
        TrajectoryStep(
            step_index=len(steps) + 1,
            action=ActionType.ANSWER,
            observation=final_answer,
            evidence_ids=selected_ids,
            rationale_summary="Return the model's structured answer and citations.",
            status=StepStatus.SUCCEEDED,
        )
    )
    identity = {
        "task_id": task.task_id,
        "retrieved_evidence_ids": retrieved_ids,
        "response_contract": response.model_dump(mode="json"),
        "generator_version": LLM_AGENT_SOLVER_VERSION,
    }
    return Trajectory(
        trajectory_id=canonical_hash(identity, prefix="llm_candidate_trajectory:"),
        task_id=task.task_id,
        workflow_kind=WorkflowKind.CANDIDATE,
        steps=tuple(steps),
        program_execution={
            "source": execution_source,
            "trace_version": response.execution_trace.trace_version,
            "operation_outputs": {
                execution_node_ids[item.execution_id]: canonical_execution_results[
                    item.execution_id
                ]
                for item in executions
            },
        },
        final_answer=final_answer,
        generator_version=LLM_AGENT_SOLVER_VERSION,
    )


def _evidence_id_from_ref(ref: str) -> str:
    return ref.removeprefix("evidence:").split("#", 1)[0]


def _execution_ref_to_program_ref(
    ref: str,
    execution_node_ids: dict[str, str],
) -> str:
    if not ref.startswith("execution:"):
        return ref
    execution_id, separator, selector = ref.removeprefix("execution:").partition("#")
    node_id = execution_node_ids[execution_id]
    suffix = f"#{selector}" if separator else ""
    return f"operation:{node_id}{suffix}"


def _canonicalize_execution_refs(value: Any, execution_node_ids: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize_execution_refs(item, execution_node_ids)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_canonicalize_execution_refs(item, execution_node_ids) for item in value]
    if isinstance(value, tuple):
        return tuple(_canonicalize_execution_refs(item, execution_node_ids) for item in value)
    if isinstance(value, str) and value.startswith("execution:"):
        execution_id, separator, selector = value.removeprefix("execution:").partition("#")
        node_id = execution_node_ids[execution_id]
        suffix = f"#{selector}" if separator else ""
        return f"{node_id}{suffix}"
    return value
