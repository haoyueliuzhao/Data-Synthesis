from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

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
from trusted_synthesis.runtime.agent.schema import (
    AgentGenerationAudit,
    AgentResponseContract,
    AgentSearchResponseContract,
    AgentSolveResult,
    ModelCallTelemetry,
)
from trusted_synthesis.runtime.tools import EvidenceToolRuntime

LLM_AGENT_SOLVER_VERSION = "llm_agent_solver.v1"
LLM_AGENT_PROMPT_VERSION = "agent_candidate_prompt.v2"
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
        self._operation_catalog = _public_operation_catalog(operation_registry)

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
        base_prompt, answer_prompt_manifest_hash = _build_prompt(
            task,
            retrieved,
            self._operation_catalog,
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
        trajectory = _normalize_trajectory(
            task,
            retrieved,
            response,
            self._registry,
            executed_search_query=executed_search_query,
            search_plan_summary=search_plan_summary,
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
            executed_search_query_hash=executed_search_query_hash,
            model_search_used=model_search_used,
            response_contract_hash=response_hash,
            telemetry=tuple(telemetry),
            selected_model=selected_model,
            contract_repair_count=repair_count,
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
            validation_error = str(exc)
            telemetry.append(
                _invalid_contract_telemetry(call_telemetry, "AgentSearchContractError")
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
            validation_error = str(exc)
            telemetry.append(
                _invalid_contract_telemetry(
                    call_telemetry,
                    "AgentContractValidationError",
                )
            )
    if response is None:
        raise LLMClientError("model failed the agent response contract", tuple(telemetry))
    return response, tuple(telemetry), max(len(telemetry) - 1, 0)


def _invalid_contract_telemetry(
    telemetry: ModelCallTelemetry,
    error_type: str,
) -> ModelCallTelemetry:
    return telemetry.model_copy(
        update={
            "json_contract_success": False,
            "error_type": error_type,
        }
    )


def _validate_agent_response_contract(
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    response: AgentResponseContract,
    registry: OperationRegistry,
) -> None:
    retrieved_ids = {item.evidence_id for item in retrieved}
    unknown_selected = set(response.selected_evidence_ids) - retrieved_ids
    if unknown_selected:
        raise ValueError(f"selected evidence was not retrieved: {sorted(unknown_selected)}")
    for operation in response.operations:
        definition = registry.require(operation.operator_id)
        registry.validate_output(definition, operation.result)
        for ref in operation.input_refs:
            if not ref.startswith("evidence:"):
                continue
            evidence_id = _evidence_id_from_ref(ref)
            if evidence_id not in retrieved_ids:
                raise ValueError(
                    "operation evidence ref does not resolve to retrieved evidence: "
                    f"{ref}; use evidence:<full evidence_id>, for example "
                    "evidence:evidence:domain:item@version"
                )
    if TaskRequirement.VERIFY_RESULT in task.requirements and response.verification_result is None:
        raise ValueError("verification_result is required by the public task")
    if task.planning_track != PlanningTrack.PLAN_GIVEN:
        return
    if task.program_skeleton is None:
        raise ValueError("plan_given task is missing its public program skeleton")
    expected = task.program_skeleton.nodes
    if len(response.operations) != len(expected):
        raise ValueError("agent operation count does not match the public program skeleton")
    for operation, node in zip(response.operations, expected, strict=True):
        if operation.node_id != node.public_node_id:
            raise ValueError("agent node IDs must preserve the public plan")
        if operation.operator_id != node.operator_id:
            raise ValueError("agent operators must preserve the public plan")
        if operation.parameters != node.parameters:
            raise ValueError("agent parameters must preserve the public plan")


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
        f"{instructions}\n\n"
        f"PAYLOAD:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
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


def _build_prompt(
    task: TaskPublicSpec,
    evidence: tuple[EvidenceItem, ...],
    operation_catalog: tuple[dict[str, Any], ...],
    executed_search_query: dict[str, Any],
) -> tuple[str, str]:
    response_schema = AgentResponseContract.model_json_schema()
    manifest = {
        "prompt_version": LLM_AGENT_PROMPT_VERSION,
        "response_schema_hash": canonical_hash(
            response_schema, prefix="agent_response_schema:"
        ),
        "operation_catalog_hash": canonical_hash(
            operation_catalog, prefix="agent_operation_catalog:"
        ),
    }
    payload = {
        "task_public_spec": task.model_dump(mode="json", exclude_none=True),
        "executed_search_query": executed_search_query,
        "retrieved_evidence": [
            item.model_dump(mode="json", exclude_none=True) for item in evidence
        ],
        "operation_catalog": operation_catalog,
        "response_json_schema": response_schema,
    }
    instructions = (
        "You are an evidence-grounded agent candidate. Use only the public task and "
        "retrieved evidence below. Never infer hidden gold IDs or an oracle answer. "
        "Select only evidence needed for the answer. Return exactly one JSON object "
        "that validates against response_json_schema. Every operation result and the "
        "final answer must be your own computed decision; no later component will "
        "repair it. Input refs must use evidence:<full evidence_id> or "
        "operation:<earlier node_id>, with an optional #selector suffix. For "
        "plan_given, preserve public node IDs, operators, input ordering, parameters, "
        "and dependencies. Evidence input refs have a kind prefix in addition to the "
        "full evidence ID: if an ID is evidence:finance:item@v1, write the input ref "
        "as evidence:evidence:finance:item@v1. For plan_hidden, construct a valid "
        "topological operation plan from the catalog. Copy citation evidence_id, source_id, and "
        "source_locator exactly from selected evidence. Include verification_result "
        "when verify_result is required. Do not include commentary outside JSON."
    )
    prompt = (
        f"{instructions}\n\n"
        f"PAYLOAD:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
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
            "Repair only JSON shape and graph ordering. Preserve your factual and "
            "reasoning decisions; do not substitute a hidden or externally supplied answer."
        ),
    }
    return (
        f"{base_prompt}\n\n"
        f"CONTRACT_REPAIR:\n{json.dumps(repair, ensure_ascii=False, sort_keys=True)}"
    )


def _public_operation_catalog(
    registry: OperationRegistry,
) -> tuple[dict[str, Any], ...]:
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
        for item in registry.manifest()
    )


def _normalize_trajectory(
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    response: AgentResponseContract,
    registry: OperationRegistry,
    *,
    executed_search_query: dict[str, Any],
    search_plan_summary: str | None,
) -> Trajectory:
    selected_ids = tuple(dict.fromkeys(response.selected_evidence_ids))
    retrieved_ids = tuple(item.evidence_id for item in retrieved)
    steps = [
        TrajectoryStep(
            step_index=1,
            action=ActionType.PLAN,
            observation={
                "retrieval_track": task.retrieval_track.value,
                "planning_track": task.planning_track.value,
                "search_plan_summary": search_plan_summary,
                "model_plan_summary": response.plan_summary,
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
    for operation in response.operations:
        definition = registry.require(operation.operator_id)
        direct_evidence_ids = tuple(
            _evidence_id_from_ref(ref)
            for ref in operation.input_refs
            if ref.startswith("evidence:")
        )
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType(definition.action_type),
                tool_name=definition.tool_capability,
                tool_input={"parameters": operation.parameters},
                observation={"result": operation.result},
                evidence_ids=direct_evidence_ids,
                program_node_id=operation.node_id,
                operator_id=operation.operator_id,
                input_refs=operation.input_refs,
                output_ref=f"operation:{operation.node_id}",
                rationale_summary=operation.rationale_summary,
                status=StepStatus.SUCCEEDED,
            )
        )
    if TaskRequirement.VERIFY_RESULT in task.requirements:
        output_node_id = response.operations[-1].node_id
        output_ref = f"operation:{output_node_id}"
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType.VERIFY,
                observation={
                    "verified_output_ref": output_ref,
                    "verified_result": response.verification_result or {},
                },
                evidence_ids=selected_ids,
                program_node_id=output_node_id,
                input_refs=(output_ref,),
                rationale_summary="Verify the model-reported final operation result.",
                status=StepStatus.SUCCEEDED,
            )
        )
    steps.append(
        TrajectoryStep(
            step_index=len(steps) + 1,
            action=ActionType.ANSWER,
            observation=response.final_answer,
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
            "source": "model_reported",
            "operation_outputs": {
                item.node_id: item.result for item in response.operations
            },
        },
        final_answer=response.final_answer,
        generator_version=LLM_AGENT_SOLVER_VERSION,
    )


def _evidence_id_from_ref(ref: str) -> str:
    return ref.removeprefix("evidence:").split("#", 1)[0]
