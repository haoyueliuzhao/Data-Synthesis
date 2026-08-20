from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.runtime.agent.public_operation import (
    model_visible_public_operation_progress,
    public_stop_readiness_payload,
)
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

COMPACT_BUDGET_PROMPT_VERSION = "compact_budget_prompt.v1"

PLAN_HEADER = "Return only one compact JSON object with exactly these keys: plan_summary"
DECISION_HEADER = "Return only one compact JSON object. Choose one next public action."
FINAL_HEADER = "Return only one JSON object with exactly rationale_summary, answer"

_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "expected_arguments",
        "expected_operator_id",
        "gold_evidence_ids",
        "mechanism_private_state",
        "oracle",
        "oracle_program",
        "private",
        "required_argument_patch",
        "required_next_tools",
        "required_prerequisite_action",
        "source_program_node_id",
        "suggested_argument_patch",
        "target_evidence_ids",
    }
)
_OMITTED_OBSERVATION_KEYS = frozenset(
    {
        "content_hash",
        "environment_manifest_id",
        "observation_id",
        "observation_time_hash",
        "provenance_hash",
        "provenance_hashes",
        "query_hash",
        "snapshot_hash",
        "source_locator_hash",
    }
)


def _compact_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"compact Prompt requires public mapping {field}")
    return value


def _without_telemetry(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_telemetry(item)
            for key, item in value.items()
            if str(key) not in _OMITTED_OBSERVATION_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_without_telemetry(item) for item in value]
    return value


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {str(key) for key in value} | set().union(
            *(_walk_keys(item) for item in value.values()),
            set(),
        )
    if isinstance(value, (list, tuple)):
        return set().union(*(_walk_keys(item) for item in value), set())
    return set()


def require_action_neutral_public_projection(value: Any) -> None:
    observed = _walk_keys(value)
    forbidden = tuple(sorted(observed & _FORBIDDEN_PUBLIC_KEYS))
    if forbidden:
        raise ValueError(
            "compact public Prompt projection contains private/action-bearing keys: "
            + ", ".join(forbidden)
        )
    if isinstance(value, Mapping) and value.get("action_binding_fields_exposed") is True:
        raise ValueError("compact public Prompt projection exposes action bindings")


def _compact_resolution_rules(variable: Mapping[str, Any]) -> dict[str, Any]:
    rules = variable.get("resolution_rules")
    if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)) or not rules:
        raise ValueError("public Operation variable lacks resolution rules")
    selector_sets: list[tuple[tuple[str, Any], ...]] = []
    source_tools: list[str] = []
    for raw_rule in rules:
        rule = _mapping(raw_rule, field="resolution_rule")
        predicates = rule.get("equals")
        if not isinstance(predicates, Sequence) or isinstance(predicates, (str, bytes)):
            raise ValueError("public Operation resolution rule lacks equality predicates")
        compact_predicates = []
        for raw_predicate in predicates:
            predicate = _mapping(raw_predicate, field="resolution_predicate")
            selector = predicate.get("selector")
            if not isinstance(selector, Sequence) or isinstance(selector, (str, bytes)):
                raise ValueError("public Operation selector is malformed")
            compact_predicates.append(
                (".".join(str(item) for item in selector), predicate.get("value"))
            )
        selector_sets.append(tuple(sorted(compact_predicates)))
        source_tools.append(str(rule["source_tool_id"]))
    if len(set(selector_sets)) != 1:
        raise ValueError("public acquisition tools resolve a variable with different semantics")
    values = dict(selector_sets[0])
    public_record = {
        "subject_id": values.get("subject.subject_id"),
        "subject_name": values.get("subject.name"),
        "subject_type": values.get("subject.type"),
        "metric": values.get("metric.predicate"),
        "definition_id": values.get("metric.definition_id"),
        "period": values.get("period"),
        "source_id": values.get("source.source_id"),
        "source_authority": values.get("source.authority"),
        "payload_kind": values.get("payload.kind"),
        "unit": values.get("payload.unit"),
        "currency": values.get("payload.currency"),
        "frequency": values.get("frequency"),
        "time_basis": values.get("time_basis"),
    }
    return {
        "symbol": str(variable["symbol"]),
        "semantic_role": str(variable["semantic_role"]),
        "public_record": public_record,
        "acquisition_tools": sorted(set(source_tools)),
    }


def _compact_operation_node(node: Mapping[str, Any]) -> dict[str, Any]:
    output = {
        "node_id": node["node_id"],
        "kind": node["node_kind"],
        "semantic_role": node["semantic_role"],
        "dependencies": node.get("dependency_node_ids") or (),
        "inputs": node.get("inputs") or (),
        "output_symbol": node["output_symbol"],
        "tool_id": node["tool_id"],
        "operator_choice_mode": node["operator_choice_mode"],
        "allowed_operator_ids": node.get("allowed_operator_ids") or (),
        "operator_selection_rule": node.get("operator_selection_rule"),
        "operator_output_schemas": node.get("operator_output_schemas") or {},
        "required_output_schema": node.get("required_output_schema"),
        "normalization_target": node.get("normalization_target"),
        "parameters": node.get("parameters") or {},
        "terminal": bool(node.get("terminal")),
    }
    return {key: value for key, value in output.items() if value not in (None, (), [], {})}


def compact_public_task_context(
    task: TaskPublicSpec,
    environment: AgentToolEnvironmentManifest,
    *,
    mechanism_public_state: Mapping[str, Any],
) -> dict[str, Any]:
    guidance = _mapping(task.metadata.get("agent_contract_guidance"), field="guidance")
    operation = _mapping(
        guidance.get("public_operation_execution_contract"),
        field="public_operation_execution_contract",
    )
    stop = _mapping(
        guidance.get("public_stop_readiness_contract"),
        field="public_stop_readiness_contract",
    )
    repair = _mapping(
        guidance.get("public_action_neutral_repair_contract"),
        field="public_action_neutral_repair_contract",
    )
    verification = _mapping(
        guidance.get("public_terminal_verification_target"),
        field="public_terminal_verification_target",
    )
    answer_constraints = _mapping(
        guidance.get("answer_observation_constraints"),
        field="answer_observation_constraints",
    )
    variables = operation.get("variables")
    nodes = operation.get("nodes")
    if not isinstance(variables, Sequence) or isinstance(variables, (str, bytes)):
        raise ValueError("public Operation Contract lacks variables")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise ValueError("public Operation Contract lacks nodes")
    retrieval = _mapping(task.retrieval_scope, field="retrieval_scope")
    partial = _mapping(
        retrieval.get("partial_constraints") or {},
        field="retrieval_scope.partial_constraints",
    )
    compact_retrieval = {
        "aliases": retrieval.get("aliases") or (),
        "period_labels": partial.get("period_labels") or (),
    }

    tools = tuple(
        {
            "tool_id": item.tool_id,
            "semantic_role": item.semantic_role,
            "required_input_fields": item.required_input_fields,
        }
        for item in sorted(environment.tools, key=lambda value: value.tool_id)
    )
    context = {
        "prompt_protocol": COMPACT_BUDGET_PROMPT_VERSION,
        "task": {
            "instruction": task.instruction,
            "answer_schema": task.answer_schema,
            "retrieval": compact_retrieval,
            "mechanism_requirement_fields": tuple(sorted(mechanism_public_state)),
        },
        "public_operation": {
            "acquisition_path_policy": operation["acquisition_path_policy"],
            "completion_rule": operation["completion_rule"],
            "variables": tuple(
                _compact_resolution_rules(_mapping(item, field="operation_variable"))
                for item in variables
            ),
            "nodes": tuple(
                _compact_operation_node(_mapping(item, field="operation_node")) for item in nodes
            ),
            "terminal_node_id": operation["terminal_node_id"],
            "exact_tool_sequence_required": operation["exact_tool_sequence_required"],
            "correct_choice_exposed_for_model_choice": operation[
                "correct_choice_exposed_for_model_choice"
            ],
        },
        "repair": {
            "exposed_context_fields": repair["exposed_context_fields"],
            "forbidden_action_binding_fields": repair["forbidden_action_binding_fields"],
            "repair_semantics_source": repair["repair_semantics_source"],
            "model_retains_repair_decision": repair["model_retains_repair_decision"],
        },
        "stop": {
            "required_node_ids": stop["required_node_ids"],
            "terminal_node_id": stop["terminal_node_id"],
            "readiness_formula": stop["readiness_formula"],
            "verification_after_terminal_required": stop["verification_after_terminal_required"],
            "maximum_postcompletion_tool_calls": stop["maximum_postcompletion_tool_calls"],
        },
        "terminal_verification": {
            "tool_id": verification["verification_tool_id"],
            "evidence_argument_field": verification["evidence_argument_field"],
            "claim_argument_field": verification["claim_argument_field"],
            "required_claim_fields": verification["required_claim_fields"],
            "terminal_reference_field": verification["terminal_reference_field"],
            "additional_claim_fields_policy": verification["additional_claim_fields_policy"],
        },
        "answer_observation": dict(answer_constraints),
        "tools": tools,
        "action_binding_fields_exposed": False,
    }
    require_action_neutral_public_projection(context)
    return context


def compact_public_observation(observation: AgentToolObservation) -> dict[str, Any]:
    output: dict[str, Any] = {
        "call_index": observation.call.call_index,
        "tool_id": observation.call.tool_id,
        "status": observation.status,
        "result": _without_telemetry(observation.result),
    }
    if observation.error_code is not None:
        output["error_code"] = observation.error_code
        output["failed_arguments"] = _without_telemetry(observation.call.arguments)
    if observation.host_events:
        output["host_events"] = _without_telemetry(observation.host_events)
    return output


def compact_public_history(
    observations: tuple[AgentToolObservation, ...],
) -> dict[str, Any]:
    acquisitions = []
    operations = []
    failures = []
    selected_evidence_ids: set[str] = set()
    for observation in observations:
        compact = compact_public_observation(observation)
        if observation.status == "failed":
            failures.append(compact)
        elif observation.call.tool_id in {"query_structured_fact", "open_document"}:
            acquisitions.append(compact)
            selected_evidence_ids.update(observation.evidence_ids)
        elif observation.call.tool_id != "search_archive":
            operations.append(compact)
    pending_search = (
        compact_public_observation(observations[-1])
        if observations and observations[-1].call.tool_id == "search_archive"
        else None
    )
    output = {
        "selected_evidence_ids": tuple(sorted(selected_evidence_ids)),
        "acquisitions": tuple(acquisitions),
        "pending_search": pending_search,
        "operations": tuple(operations),
        "failed_actions": tuple(failures),
    }
    require_action_neutral_public_projection(output)
    return output


def compact_public_progress(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
) -> dict[str, Any]:
    progress = model_visible_public_operation_progress(task, observations)
    stop = public_stop_readiness_payload(task, observations)
    if progress is None or stop is None:
        raise ValueError("compact Prompt requires the public Operation and stop contracts")
    output = {
        "completed_node_ids": progress["completed_node_ids"],
        "completed_node_operation_refs": progress["completed_node_operation_refs"],
        "remaining_node_ids": progress["remaining_node_ids"],
        "ready_nodes": progress["ready_nodes"],
        "unresolved_symbols": progress["unresolved_symbols"],
        "terminal_node_completed": stop["terminal_node_completed"],
        "verification_after_terminal_completed": stop["verification_after_terminal_completed"],
        "postcompletion_violation": stop["postcompletion_violation"],
        "stop_ready": stop["stop_ready"],
        "final_answer_allowed": stop["final_answer_allowed"],
        "action_binding_fields_exposed": False,
    }
    require_action_neutral_public_projection(output)
    return output


def render_compact_plan_prompt(
    context: Mapping[str, Any],
    *,
    public_path_condition: str | None,
) -> str:
    payload = {
        "public_context": dict(context),
        "public_path_condition": public_path_condition,
        "instruction": (
            "Plan semantically over the public contract. Do not invent private identifiers or "
            "delegate the next action to the Host."
        ),
    }
    require_action_neutral_public_projection(payload)
    return f"{PLAN_HEADER}.\n{_compact_json(payload)}"


def _compact_decision_context(
    context: Mapping[str, Any],
    progress: Mapping[str, Any],
) -> dict[str, Any]:
    unresolved = set(progress["unresolved_symbols"])
    remaining = set(progress["remaining_node_ids"])
    task_context = {
        "instruction": context["task"]["instruction"],
        "answer_schema": context["task"]["answer_schema"],
        "mechanism_requirement_fields": context["task"]["mechanism_requirement_fields"],
    }
    if unresolved:
        task_context["retrieval"] = context["task"]["retrieval"]
    operation = dict(context["public_operation"])
    variables = tuple(item for item in operation["variables"] if item["symbol"] in unresolved)
    nodes = tuple(item for item in operation["nodes"] if item["node_id"] in remaining)
    operation["variables"] = variables
    operation["nodes"] = nodes
    tools = tuple(context["tools"])
    if unresolved:
        allowed_tools = {"search_archive", "query_structured_fact", "open_document"}
    elif progress["terminal_node_completed"]:
        allowed_tools = {"cross_check_evidence"}
    else:
        allowed_tools = {
            str(item["tool_id"])
            for item in nodes
            if isinstance(item, Mapping) and item.get("tool_id")
        }
    compact = {
        "prompt_protocol": context["prompt_protocol"],
        "task": task_context,
        "public_operation": operation,
        "repair": context["repair"],
        "stop": context["stop"],
        "terminal_verification": context["terminal_verification"],
        "tools": tuple(item for item in tools if item["tool_id"] in allowed_tools),
        "action_binding_fields_exposed": False,
    }
    require_action_neutral_public_projection(compact)
    return compact


def _compact_history_for_progress(
    observations: tuple[AgentToolObservation, ...],
    progress: Mapping[str, Any],
) -> dict[str, Any]:
    history = compact_public_history(observations)
    ready_nodes = tuple(progress["ready_nodes"])
    only_dependency_bound_frontier = bool(ready_nodes) and all(
        item.get("dependency_node_ids") for item in ready_nodes
    )
    if progress["terminal_node_completed"] or only_dependency_bound_frontier:
        history = {**history, "acquisitions": ()}
    return history


def render_compact_decision_prompt(
    context: Mapping[str, Any],
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    *,
    public_path_condition: str | None,
) -> str:
    progress = compact_public_progress(task, observations)
    payload = {
        "public_context": _compact_decision_context(context, progress),
        "public_path_condition": public_path_condition,
        "progress": progress,
        "history": _compact_history_for_progress(observations, progress),
        "response_contract": {
            "action": "call_tool_or_emit_final",
            "call_tool_fields": ("tool_id", "arguments", "rationale_summary"),
            "emit_final_only_when": "final_answer_allowed",
        },
    }
    require_action_neutral_public_projection(payload)
    return f"{DECISION_HEADER}\n{_compact_json(payload)}"


def render_compact_final_prompt(
    context: Mapping[str, Any],
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    *,
    public_path_condition: str | None,
) -> str:
    progress = compact_public_progress(task, observations)
    if not progress["final_answer_allowed"]:
        raise ValueError("compact final Prompt requires exact public Stop Readiness")
    payload = {
        "final_context": {
            "instruction": context["task"]["instruction"],
            "answer_schema": context["task"]["answer_schema"],
            "answer_observation": context["answer_observation"],
            "terminal_verification": context["terminal_verification"],
        },
        "public_path_condition": public_path_condition,
        "progress": progress,
        "history": _compact_history_for_progress(observations, progress),
        "response_contract": {
            "answer_must_match": context["task"]["answer_schema"],
            "reasoning_content_persistence": "forbidden",
            "rationale_summary_required": True,
        },
    }
    require_action_neutral_public_projection(payload)
    return f"{FINAL_HEADER}.\n{_compact_json(payload)}"


def render_compact_witness_prompts(
    context: Mapping[str, Any],
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    *,
    public_path_condition: str | None,
) -> tuple[str, ...]:
    prompts = [
        render_compact_plan_prompt(
            context,
            public_path_condition=public_path_condition,
        )
    ]
    prompts.extend(
        render_compact_decision_prompt(
            context,
            task,
            observations[:index],
            public_path_condition=public_path_condition,
        )
        for index in range(len(observations))
    )
    prompts.append(
        render_compact_final_prompt(
            context,
            task,
            observations,
            public_path_condition=public_path_condition,
        )
    )
    return tuple(prompts)
