from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from trusted_synthesis.core.operations.program import (
    ProgramExecution,
    ProgramExecutionError,
    ProgramVerification,
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.capability_observation import CapabilityFamily
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    PublicOperationPayload,
    PublicSemanticConstraint,
    build_selected_program,
    resolve_public_operator,
    resolve_required_record_handles,
    resolve_rule_record,
)
from trusted_synthesis.core.task.semantic_table_trace_hardening import (
    ActionAcceptanceReport,
    HardenedPublicObservation,
    HardenedPublicPrompt,
    HardenedStepRecord,
    StateBoundMechanismQualification,
    StateBoundQualifiedValidity,
    StepRuntimeResult,
    classify_action_acceptance,
    execution_parent_hash,
    make_hardened_observation,
    make_hardened_prompt,
    make_identity_model,
    resolve_runtime_operation,
    topological_components,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    CausalRuntimeEvent,
    CausalTargetComponent,
    canonical_public_answer,
    make_runtime_event,
    make_task_validity_report,
    project_public_answer,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as v171_runtime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import AgentToolResult


@dataclass
class StepRuntimeState:
    runtime_input: v171_runtime.RuntimeInput
    package_id: str
    replica_index: int
    ordered_components: tuple[CausalTargetComponent, ...]
    current_index: int = 0
    observations: dict[str, HardenedPublicObservation] = field(default_factory=dict)
    steps: list[HardenedStepRecord] = field(default_factory=list)
    events: list[CausalRuntimeEvent] = field(default_factory=list)
    event_ids_by_component: dict[str, list[str]] = field(default_factory=dict)
    component_checks: dict[str, bool] = field(default_factory=dict)
    acceptances: dict[str, ActionAcceptanceReport] = field(default_factory=dict)
    selected_source_handles: list[str] = field(default_factory=list)
    selected_operations: dict[str, PublicOperationPayload] = field(default_factory=dict)
    recovery_lineage_checks: dict[str, bool] = field(default_factory=dict)
    normalization_ref_by_output: dict[str, str] = field(default_factory=dict)
    record_by_normalization_ref: dict[str, str] = field(default_factory=dict)
    reconciliation_operands: list[dict[str, str]] = field(default_factory=list)
    reconciliation_input_handles: list[str] = field(default_factory=list)
    reconciliation_consumed_symbols: set[str] = field(default_factory=set)
    readiness_checks: dict[str, bool] = field(default_factory=dict)
    selected_records: list[str] = field(default_factory=list)
    selected_scope: list[str] = field(default_factory=list)
    selected_projection: tuple[str, ...] = ()
    selected_operator: str = ""
    operation_lineage_complete: bool = True
    program_execution: ProgramExecution | None = None
    verification: ProgramVerification | None = None
    interactive_output: dict[str, Any] | None = None
    execution_error: str | None = None
    stopped: bool = False
    task_program_executor_invocation_count: int = 0
    task_program_oracle_verifier_invocation_count: int = 0
    local_tool_invocation_count: int = 0
    postcompletion_call_count: int = 0
    finance_runtime: Any | None = None
    pending_prompt: HardenedPublicPrompt | None = None
    pending_source_by_display: dict[str, str] | None = None


def initialize(
    runtime_input: v171_runtime.RuntimeInput,
    *,
    package_id: str,
    replica_index: int,
) -> StepRuntimeState:
    ordered = topological_components(runtime_input.components)
    task = runtime_input.public_task.semantic_task
    required = list(resolve_required_record_handles(task))
    state = StepRuntimeState(
        runtime_input=runtime_input,
        package_id=package_id,
        replica_index=replica_index,
        ordered_components=ordered,
        event_ids_by_component={item.component_key: [] for item in ordered},
        selected_records=list(required),
        selected_scope=list(required),
        selected_projection=tuple(task.answer_fields),
        selected_operator=resolve_public_operator(task, task.terminal_operation_handle),
    )
    if runtime_input.capability_family == CapabilityFamily.STATE_DEPENDENT_STOPPING:
        _run_program(state, list(required), state.selected_operator)
    elif runtime_input.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        state.finance_runtime = v171_runtime._new_finance_runtime(runtime_input.finance_core)
    return state


def render_next_prompt(state: StepRuntimeState) -> HardenedPublicPrompt:
    if state.current_index >= len(state.ordered_components):
        raise ValueError("step Runtime has no later Prompt")
    if state.pending_prompt is not None:
        return state.pending_prompt
    component = state.ordered_components[state.current_index]
    predecessor = tuple(state.observations[key] for key in component.dependency_component_keys)
    prompt, mapping = make_hardened_prompt(
        package_id=state.package_id,
        task=state.runtime_input.public_task,
        component=component,
        replica_index=state.replica_index,
        predecessor_observations=predecessor,
    )
    state.pending_prompt = prompt
    state.pending_source_by_display = mapping
    return prompt


def _append_event(
    state: StepRuntimeState,
    *,
    component_key: str | None,
    event_type: str,
    tool_id: str | None,
    status: Literal["succeeded", "failed", "typed", "computed"],
    error_code: str | None,
    inputs: Any,
    outputs: Any,
    public_effects: Mapping[str, Any],
) -> CausalRuntimeEvent:
    event = make_runtime_event(
        event_index=len(state.events) + 1,
        component_key=component_key,
        event_type=event_type,
        tool_id=tool_id,
        status=status,
        error_code=error_code,
        inputs=inputs,
        outputs=outputs,
        public_effects=public_effects,
    )
    state.events.append(event)
    if component_key is not None:
        state.event_ids_by_component[component_key].append(event.event_id)
    return event


def _event_status(result: AgentToolResult) -> tuple[Literal["succeeded", "failed"], str | None]:
    if result.status == "succeeded":
        return "succeeded", None
    return "failed", result.error_code or "untyped_local_failure"


def _execute_context_step(
    state: StepRuntimeState,
    component: CausalTargetComponent,
    operation: PublicOperationPayload,
) -> None:
    task = state.runtime_input.public_task.semantic_task
    required = resolve_required_record_handles(task)
    arguments = operation.arguments
    key = component.component_key
    if key == "context.operator":
        state.selected_operator = str(arguments["operator_id"])
        expected = resolve_public_operator(task, str(arguments["operation_handle"]))
        passed = state.selected_operator == expected
    elif key == "context.records":
        state.selected_records = [str(item) for item in arguments["record_handles"]]
        passed = tuple(state.selected_records) == tuple(required)
    elif key == "context.projection":
        state.selected_projection = tuple(str(item) for item in arguments["answer_fields"])
        passed = state.selected_projection == tuple(task.answer_fields)
    elif key == "context.scope":
        state.selected_scope = [str(item) for item in arguments["record_handles"]]
        passed = tuple(state.selected_scope) == tuple(required)
    else:
        raise ValueError(f"unknown Context component:{key}")
    state.component_checks[key] = passed
    _append_event(
        state,
        component_key=key,
        event_type=f"{key}.applied",
        tool_id=operation.tool_id,
        status="computed",
        error_code=None,
        inputs=arguments,
        outputs={"semantic_condition_passed": passed},
        public_effects={
            "decision_kind": operation.decision_kind,
            "selected_operation_hash": canonical_hash(
                operation.model_dump(mode="json"),
                prefix="selected_runtime_operation:",
            ),
        },
    )


def _execute_reconciliation_step(
    state: StepRuntimeState,
    component: CausalTargetComponent,
    operation: PublicOperationPayload,
) -> None:
    task = state.runtime_input.public_task.semantic_task
    core = state.runtime_input.finance_core
    key = component.component_key
    operations = {item.operation_handle: item for item in task.operations}
    if key.startswith("reconciliation.mapping"):
        arguments = operation.arguments
        target = operations[str(component.public_state.facts["operation_handle"])]
        rule = next(
            item
            for item in task.resolution_rules
            if item.rule_handle == str(component.public_state.facts["rule_handle"])
        )
        expected_record = resolve_rule_record(task, rule).record_handle
        record_handle = str(arguments["record_handle"])
        query_rule = v171_runtime._rule_for_record(task, record_handle)
        query_arguments = v171_runtime._query_arguments_from_constraints(query_rule.equals)
        runtime = state.finance_runtime
        if runtime is None:
            raise ValueError("Reconciliation step lost its initialized Finance Runtime")
        state.local_tool_invocation_count += 1
        query = v171_runtime._call(runtime, 1, query_rule.source_tool_id, query_arguments)
        query_status, query_error = _event_status(query)
        _append_event(
            state,
            component_key=key,
            event_type="reconciliation.record_acquired",
            tool_id=query_rule.source_tool_id,
            status=query_status,
            error_code=query_error,
            inputs=query_arguments,
            outputs=query.result,
            public_effects={"record_handle": record_handle},
        )
        _, _, handle_to_id = v171_runtime._record_maps(core)
        normalize_arguments = {
            "evidence_ids": [handle_to_id[record_handle]],
            "target_definition": target.normalization_target,
        }
        state.local_tool_invocation_count += 1
        normalized = v171_runtime._call(
            runtime,
            2,
            "normalize_metric_unit_period",
            normalize_arguments,
        )
        status, error = _event_status(normalized)
        operation_ref = normalized.result.get("normalized_operation_ref")
        output_handle = str(arguments["output_handle"])
        if normalized.status == "succeeded" and isinstance(operation_ref, str):
            state.normalization_ref_by_output[output_handle] = operation_ref
            state.record_by_normalization_ref[operation_ref] = record_handle
        passed = bool(
            normalized.status == "succeeded"
            and record_handle == expected_record
            and output_handle == target.output_handle
            and str(arguments["rule_handle"]) == rule.rule_handle
        )
        state.component_checks[key] = passed
        _append_event(
            state,
            component_key=key,
            event_type="normalization_reference_emitted",
            tool_id="normalize_metric_unit_period",
            status=status,
            error_code=error,
            inputs=normalize_arguments,
            outputs=normalized.result,
            public_effects={
                "output_handle": output_handle,
                "record_handle": record_handle,
                "reference_emitted": isinstance(operation_ref, str),
            },
        )
        return
    if not key.startswith("reconciliation.consume"):
        raise ValueError(f"unknown Reconciliation component:{key}")
    arguments = operation.arguments
    terminal = operations[str(component.public_state.facts["operation_handle"])]
    symbol = str(component.public_state.facts["input_symbol"])
    expected_by_symbol = {
        item.output_symbol: item.output_handle
        for item in task.operations
        if item.node_kind == "normalization"
    }
    expected_output = expected_by_symbol[symbol]
    output_handle = str(arguments["output_handle"])
    operation_ref = state.normalization_ref_by_output.get(output_handle)
    consumed = operation_ref is not None
    if operation_ref is not None:
        state.reconciliation_operands.append(
            {"operation_ref": operation_ref, "selector": "normalized_inputs.target"}
        )
        state.reconciliation_input_handles.append(state.record_by_normalization_ref[operation_ref])
        state.reconciliation_consumed_symbols.add(symbol)
    state.component_checks[key] = bool(
        consumed
        and output_handle == expected_output
        and str(arguments["input_symbol"]) == symbol
        and str(arguments["operation_handle"]) == terminal.operation_handle
    )
    _append_event(
        state,
        component_key=key,
        event_type="normalization_reference_consumed",
        tool_id="calculator",
        status="computed",
        error_code=None,
        inputs=arguments,
        outputs={"reference_consumed": consumed},
        public_effects={"input_symbol": symbol, "output_handle": output_handle},
    )


def _execute_recovery_step(
    state: StepRuntimeState,
    component: CausalTargetComponent,
    operation: PublicOperationPayload,
) -> None:
    task = state.runtime_input.public_task.semantic_task
    core = state.runtime_input.finance_core
    key = component.component_key
    rules = {item.rule_handle: item for item in task.resolution_rules}
    current_rule = rules[str(component.public_state.facts["rule_handle"])]
    selected_rule = str(operation.arguments["rule_handle"])
    runtime = v171_runtime._new_finance_runtime(core)
    coarse = v171_runtime._coarse_query_arguments(current_rule)
    state.local_tool_invocation_count += 1
    failed = v171_runtime._call(runtime, 1, current_rule.source_tool_id, coarse)
    failed_status, failed_error = _event_status(failed)
    failure_receipt = canonical_hash(
        {
            "rule_handle": current_rule.rule_handle,
            "failed_selector": coarse,
            "status": failed.status,
            "error_code": failed.error_code,
        },
        prefix="state_bound_recovery_failure_receipt:",
    )
    failure_event = _append_event(
        state,
        component_key=key,
        event_type="typed_failure_observed",
        tool_id=current_rule.source_tool_id,
        status=failed_status,
        error_code=failed_error,
        inputs=coarse,
        outputs=failed.result,
        public_effects={
            "error_code": failed.error_code,
            "rule_handle": current_rule.rule_handle,
            "failure_receipt_id": failure_receipt,
        },
    )
    if selected_rule != current_rule.rule_handle:
        state.component_checks[key] = False
        state.recovery_lineage_checks[key] = False
        _append_event(
            state,
            component_key=key,
            event_type="recovery_target_rule_mismatch",
            tool_id=operation.tool_id,
            status="typed",
            error_code=None,
            inputs=operation.arguments,
            outputs={"retry_invoked": False},
            public_effects={
                "rejection_code": "typed_current_state_target_mismatch",
                "current_rule_handle": current_rule.rule_handle,
                "selected_rule_handle": selected_rule,
                "failure_receipt_id": failure_receipt,
            },
        )
        return
    selector = tuple(
        PublicSemanticConstraint.model_validate(item)
        for item in cast(Sequence[Any], operation.arguments["selector"])
    )
    revised = v171_runtime._query_arguments_from_constraints(selector)
    state.local_tool_invocation_count += 1
    retry = v171_runtime._call(
        runtime,
        2,
        current_rule.source_tool_id,
        revised,
    )
    retry_status, retry_error = _event_status(retry)
    retry_event = _append_event(
        state,
        component_key=key,
        event_type=(
            "recovery_succeeded" if retry.status == "succeeded" else "recovery_retry_failed"
        ),
        tool_id=current_rule.source_tool_id,
        status=retry_status,
        error_code=retry_error,
        inputs=revised,
        outputs=retry.result,
        public_effects={
            "selector_changed": revised != coarse,
            "rule_handle": current_rule.rule_handle,
            "failure_receipt_id": failure_receipt,
        },
    )
    _, id_to_handle, _ = v171_runtime._record_maps(core)
    expected_handle = resolve_rule_record(task, current_rule).record_handle
    returned = tuple(id_to_handle[item] for item in retry.evidence_ids if item in id_to_handle)
    if len(returned) == 1:
        required = list(resolve_required_record_handles(task))
        state.selected_records[required.index(expected_handle)] = returned[0]
    exact_selector = selector == current_rule.equals
    lineage = bool(
        failed.status == "failed"
        and failed.error_code == "typed_selector_requires_refinement"
        and selected_rule == current_rule.rule_handle
        and retry.status == "succeeded"
        and failure_event.event_index < retry_event.event_index
        and retry_event.public_effects.get("failure_receipt_id") == failure_receipt
        and retry_event.public_effects.get("rule_handle") == current_rule.rule_handle
    )
    state.recovery_lineage_checks[key] = lineage
    state.component_checks[key] = bool(
        lineage and exact_selector and returned == (expected_handle,)
    )


def _execute_stopping_step(
    state: StepRuntimeState,
    component: CausalTargetComponent,
    operation: PublicOperationPayload,
) -> None:
    key = component.component_key
    receipt = {
        "all_required_operations_complete": state.program_execution is not None,
        "no_unresolved_failure": state.execution_error is None,
        "oracle_verification_passed": bool(state.verification and state.verification.passed),
    }
    if key.startswith("stopping.readiness"):
        assertion = str(operation.arguments["assertion"])
        expected = "true" if receipt[assertion] else "false"
        passed = str(operation.arguments["verdict"]) == expected
        state.readiness_checks[key] = passed
        state.component_checks[key] = passed
        _append_event(
            state,
            component_key=key,
            event_type="dynamic_readiness_assessed",
            tool_id="cross_check_evidence",
            status="computed",
            error_code=None,
            inputs={"assertion": assertion, "receipt": receipt},
            outputs={"verdict": operation.arguments["verdict"]},
            public_effects={"readiness_matches_runtime": passed},
        )
        return
    if key != "stopping.final_decision":
        raise ValueError(f"unknown Stopping component:{key}")
    command = str(operation.arguments["command"])
    stop_ready = all(receipt.values()) and all(state.readiness_checks.values())
    state.stopped = command == "stop" and stop_ready
    state.component_checks[key] = state.stopped
    _append_event(
        state,
        component_key=key,
        event_type="stopping_terminal_decision",
        tool_id="cross_check_evidence",
        status="computed",
        error_code=None,
        inputs={"command": command, "receipt": receipt},
        outputs={"stopped": state.stopped},
        public_effects={"stop_ready": stop_ready},
    )
    if command != "stop" and state.program_execution is not None:
        task = state.runtime_input.finance_core.operational_record.task_package.task
        original = task.oracle.task_program
        evidence = {
            item.evidence_id: item
            for item in state.runtime_input.finance_core.operational_record.evidence_bundle.evidence
        }
        status: Literal["succeeded", "failed"] = "succeeded"
        error: str | None = None
        try:
            TaskProgramExecutor(default_registry()).execute(original, evidence)
            state.task_program_executor_invocation_count += 1
        except ProgramExecutionError:
            status = "failed"
            error = "ProgramExecutionError"
        state.postcompletion_call_count += 1
        _append_event(
            state,
            component_key=key,
            event_type="postcompletion_call_recorded",
            tool_id="calculator",
            status=status,
            error_code=error,
            inputs={"command": command},
            outputs={"postcompletion_violation": True},
            public_effects={"later_program_invocation": True},
        )


def step(state: StepRuntimeState, selected_action_id: str) -> HardenedPublicObservation:
    prompt = render_next_prompt(state)
    component = state.ordered_components[state.current_index]
    selected = tuple(item for item in prompt.candidates if item.action_id == selected_action_id)
    if len(selected) != 1:
        raise ValueError("step Runtime action is absent from the current Prompt")
    mapping = state.pending_source_by_display
    if mapping is None:
        raise ValueError("step Runtime lost its display/source binding")
    displayed = selected[0].choice_handle
    source_handle = mapping[displayed]
    operation = resolve_runtime_operation(prompt.state, displayed)
    source_operation = v171_runtime.choice_operation(component.public_state, source_handle)
    if operation.model_dump(mode="json") != source_operation.model_dump(mode="json"):
        raise ValueError("step Runtime display handle resolves to a crossed source Operation")
    acceptance = classify_action_acceptance(
        package_id=state.package_id,
        task=state.runtime_input.public_task,
        component=component,
        source_choice_handle=source_handle,
    )
    event_start = len(state.events)
    if not acceptance.accepted:
        state.component_checks[component.component_key] = False
        if state.runtime_input.capability_family == CapabilityFamily.FAILURE_RECOVERY:
            state.recovery_lineage_checks[component.component_key] = False
        _append_event(
            state,
            component_key=component.component_key,
            event_type="action_state_precondition_rejected",
            tool_id=operation.tool_id,
            status="typed",
            error_code=None,
            inputs=operation.model_dump(mode="json"),
            outputs={"action_committed": False},
            public_effects={
                "rejection_code": acceptance.rejection_code,
                "selected_operation_hash": acceptance.selected_operation_hash,
            },
        )
    elif state.runtime_input.capability_family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        _execute_context_step(state, component, operation)
    elif state.runtime_input.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        _execute_reconciliation_step(state, component, operation)
    elif state.runtime_input.capability_family == CapabilityFamily.FAILURE_RECOVERY:
        _execute_recovery_step(state, component, operation)
    else:
        _execute_stopping_step(state, component, operation)
    current_events = tuple(state.events[event_start:])
    predecessor = tuple(state.observations[key] for key in component.dependency_component_keys)
    observation = make_hardened_observation(
        prompt=prompt,
        selected_choice_handle=displayed,
        predecessor_receipt_ids=tuple(item.receipt_id for item in predecessor),
        acceptance=acceptance,
        events=current_events,
    )
    values = {
        "package_id": state.package_id,
        "replica_index": state.replica_index,
        "step_index": state.current_index,
        "component_key": component.component_key,
        "dependency_component_keys": component.dependency_component_keys,
        "source_choice_handle": source_handle,
        "displayed_choice_handle": displayed,
        "selected_action_id": selected_action_id,
        "prompt": prompt,
        "acceptance": acceptance,
        "observation": observation,
    }
    record = cast(
        HardenedStepRecord,
        make_identity_model(
            HardenedStepRecord,
            values,
            field="step_id",
            prefix="hardened_step_record:",
        ),
    )
    state.steps.append(record)
    state.observations[component.component_key] = observation
    state.acceptances[component.component_key] = acceptance
    state.selected_source_handles.append(source_handle)
    state.selected_operations[component.component_key] = operation
    state.current_index += 1
    state.pending_prompt = None
    state.pending_source_by_display = None
    return observation


def _run_program(
    state: StepRuntimeState,
    input_handles: Sequence[str],
    operator_id: str,
) -> None:
    core = state.runtime_input.finance_core
    record = core.operational_record
    original = record.task_package.task.oracle.task_program
    registry = default_registry()
    by_handle, _, handle_to_id = v171_runtime._record_maps(core)
    evidence = {item.evidence_id: item for item in by_handle.values()}
    try:
        if len(input_handles) != 2:
            raise ValueError("selected Program does not have two public operands")
        program = build_selected_program(
            original,
            operator_id=operator_id,
            evidence_ids=cast(tuple[str, str], tuple(handle_to_id[item] for item in input_handles)),
            registry=registry,
        )
        state.program_execution = TaskProgramExecutor(registry).execute(program, evidence)
        state.task_program_executor_invocation_count += 1
        state.verification = TaskProgramOracleVerifier(registry).verify(
            original,
            evidence,
            state.program_execution.node_outputs,
        )
        state.task_program_oracle_verifier_invocation_count = 1
        state.execution_error = None
    except (KeyError, ProgramExecutionError, ValueError) as exc:
        state.execution_error = getattr(exc, "error_code", type(exc).__name__)
        state.program_execution = None
        state.verification = None


def _finalize_context(state: StepRuntimeState) -> list[str]:
    task = state.runtime_input.public_task.semantic_task
    core = state.runtime_input.finance_core
    runtime = v171_runtime._new_finance_runtime(core)
    acquired: list[str] = []
    for index, handle in enumerate(state.selected_scope, start=1):
        rule = v171_runtime._rule_for_record(task, handle)
        arguments = v171_runtime._query_arguments_from_constraints(rule.equals)
        state.local_tool_invocation_count += 1
        result = v171_runtime._call(runtime, index, rule.source_tool_id, arguments)
        status, error = _event_status(result)
        _append_event(
            state,
            component_key=None,
            event_type="context.scope_query",
            tool_id=rule.source_tool_id,
            status=status,
            error_code=error,
            inputs=arguments,
            outputs=result.result,
            public_effects={"record_handle": handle},
        )
        if result.status == "succeeded":
            acquired.append(handle)
    state.operation_lineage_complete = all(item in acquired for item in state.selected_records)
    if state.operation_lineage_complete:
        _run_program(state, state.selected_records, state.selected_operator)
    else:
        state.execution_error = "selected_program_operand_outside_executed_scope"
    state.stopped = bool(state.verification and state.verification.passed)
    return list(state.selected_records)


def _finalize_reconciliation(state: StepRuntimeState) -> list[str]:
    task = state.runtime_input.public_task.semantic_task
    core = state.runtime_input.finance_core
    terminal = next(
        item for item in task.operations if item.operation_handle == task.terminal_operation_handle
    )
    normalizations = tuple(item for item in task.operations if item.node_kind == "normalization")
    runtime = state.finance_runtime
    if runtime is None:
        raise ValueError("Reconciliation finalization lost its Finance Runtime")
    _, _, handle_to_id = v171_runtime._record_maps(core)
    for normalization in normalizations:
        if normalization.output_handle in state.normalization_ref_by_output:
            continue
        rule = next(
            item
            for item in task.resolution_rules
            if item.variable_symbol == normalization.input_symbols[0]
            and item.source_tool_id == "query_structured_fact"
        )
        record_handle = resolve_rule_record(task, rule).record_handle
        query_arguments = v171_runtime._query_arguments_from_constraints(rule.equals)
        state.local_tool_invocation_count += 1
        query = v171_runtime._call(runtime, 1, rule.source_tool_id, query_arguments)
        query_status, query_error = _event_status(query)
        _append_event(
            state,
            component_key=None,
            event_type="reconciliation.support_record_acquired",
            tool_id=rule.source_tool_id,
            status=query_status,
            error_code=query_error,
            inputs=query_arguments,
            outputs=query.result,
            public_effects={"record_handle": record_handle},
        )
        normalize_arguments = {
            "evidence_ids": [handle_to_id[record_handle]],
            "target_definition": normalization.normalization_target,
        }
        state.local_tool_invocation_count += 1
        normalized = v171_runtime._call(
            runtime,
            2,
            "normalize_metric_unit_period",
            normalize_arguments,
        )
        status, error = _event_status(normalized)
        operation_ref = normalized.result.get("normalized_operation_ref")
        if normalized.status == "succeeded" and isinstance(operation_ref, str):
            state.normalization_ref_by_output[normalization.output_handle] = operation_ref
            state.record_by_normalization_ref[operation_ref] = record_handle
        _append_event(
            state,
            component_key=None,
            event_type="reconciliation.support_reference_emitted",
            tool_id="normalize_metric_unit_period",
            status=status,
            error_code=error,
            inputs=normalize_arguments,
            outputs=normalized.result,
            public_effects={
                "output_handle": normalization.output_handle,
                "record_handle": record_handle,
                "reference_emitted": isinstance(operation_ref, str),
            },
        )
    output_by_symbol = {item.output_symbol: item.output_handle for item in normalizations}
    for symbol in terminal.input_symbols:
        if symbol in state.reconciliation_consumed_symbols:
            continue
        output_handle = output_by_symbol[symbol]
        operation_ref = state.normalization_ref_by_output.get(output_handle)
        consumed = operation_ref is not None
        if operation_ref is not None:
            state.reconciliation_operands.append(
                {"operation_ref": operation_ref, "selector": "normalized_inputs.target"}
            )
            state.reconciliation_input_handles.append(
                state.record_by_normalization_ref[operation_ref]
            )
            state.reconciliation_consumed_symbols.add(symbol)
        _append_event(
            state,
            component_key=None,
            event_type="reconciliation.support_reference_consumed",
            tool_id="calculator",
            status="computed",
            error_code=None,
            inputs={
                "input_symbol": symbol,
                "operation_handle": terminal.operation_handle,
                "output_handle": output_handle,
            },
            outputs={"reference_consumed": consumed},
            public_effects={"input_symbol": symbol, "output_handle": output_handle},
        )
    state.operation_lineage_complete = len(state.reconciliation_operands) == len(
        terminal.input_symbols
    )
    if state.operation_lineage_complete:
        arguments: dict[str, Any] = {
            "operator": resolve_public_operator(task, terminal.operation_handle),
            "operands": state.reconciliation_operands,
            "parameters": {},
        }
        state.local_tool_invocation_count += 1
        result = v171_runtime._call(runtime, 1, "calculator", arguments)
        status, error = _event_status(result)
        state.interactive_output = v171_runtime._raw_output_from_tool_result(result)
        state.operation_lineage_complete = bool(
            result.status == "succeeded" and state.interactive_output is not None
        )
        _append_event(
            state,
            component_key=None,
            event_type="reconciliation.terminal_calculator",
            tool_id="calculator",
            status=status,
            error_code=error,
            inputs=arguments,
            outputs=result.result,
            public_effects={
                "all_normalized_references_consumed": len(state.reconciliation_operands) == 2
            },
        )
    _run_program(
        state,
        state.reconciliation_input_handles,
        resolve_public_operator(task, task.terminal_operation_handle),
    )
    if state.program_execution is not None:
        state.operation_lineage_complete = bool(
            state.operation_lineage_complete
            and state.interactive_output == state.program_execution.final_output
        )
    state.stopped = bool(state.verification and state.verification.passed)
    return list(state.reconciliation_input_handles)


def _finalize_recovery(state: StepRuntimeState) -> list[str]:
    task = state.runtime_input.public_task.semantic_task
    _run_program(
        state,
        state.selected_records,
        resolve_public_operator(task, task.terminal_operation_handle),
    )
    state.operation_lineage_complete = all(state.recovery_lineage_checks.values())
    state.stopped = bool(state.verification and state.verification.passed)
    return list(state.selected_records)


def finalize(state: StepRuntimeState) -> StepRuntimeResult:
    if state.current_index != len(state.ordered_components) or state.pending_prompt is not None:
        raise ValueError("step Runtime cannot finalize before all current actions commit")
    family = state.runtime_input.capability_family
    task_wrapper = state.runtime_input.public_task
    task = task_wrapper.semantic_task
    core = state.runtime_input.finance_core
    record = core.operational_record
    if family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        selected_input_handles = _finalize_context(state)
    elif family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        selected_input_handles = _finalize_reconciliation(state)
    elif family == CapabilityFamily.FAILURE_RECOVERY:
        selected_input_handles = _finalize_recovery(state)
    else:
        selected_input_handles = list(resolve_required_record_handles(task))
    raw_output = (
        state.interactive_output
        if family == CapabilityFamily.SEMANTIC_RECONCILIATION
        else dict(state.program_execution.final_output)
        if state.program_execution is not None
        else None
    )
    _, id_to_handle, handle_to_id = v171_runtime._record_maps(core)
    projected: dict[str, Any] | None = None
    if raw_output is not None:
        projected = project_public_answer(
            raw_output,
            selected_fields=state.selected_projection,
            evidence_id_to_record_handle=id_to_handle,
            contract=task_wrapper.answer_contract,
        )
    answer_projection_complete = bool(
        projected is not None
        and set(projected) == set(state.selected_projection)
        and not any(
            isinstance(value, str) and value.startswith("evidence:") for value in projected.values()
        )
    )
    answer_schema_valid = bool(
        projected is not None
        and set(projected) == set(task_wrapper.answer_contract.required_fields)
    )
    answer_semantics = False
    if answer_schema_valid and projected is not None:
        try:
            answer_semantics = canonical_public_answer(
                projected,
                task_wrapper.answer_contract,
            ) == canonical_public_answer(
                record.projected_expected_output,
                task_wrapper.answer_contract,
            )
        except ValueError:
            answer_semantics = False
    reference_identity = bool(
        projected is not None
        and all(
            not (isinstance(value, str) and value.startswith("evidence:"))
            for value in projected.values()
        )
        and (
            "higher_ref" not in projected
            or projected["higher_ref"]
            in set(task_wrapper.answer_contract.public_label_by_record_handle.values())
        )
    )
    citations = tuple(sorted(set(selected_input_handles)))
    cited_evidence = {handle_to_id[item] for item in selected_input_handles if item in handle_to_id}
    citation_complete = cited_evidence == set(record.target_program_evidence_ids)
    local_program_valid = bool(
        state.verification is not None
        and state.verification.passed
        and (family != CapabilityFamily.SEMANTIC_RECONCILIATION or state.operation_lineage_complete)
    )
    terminal_complete = bool(
        state.verification is not None and state.verification.passed and state.stopped
    )
    _append_event(
        state,
        component_key=None,
        event_type="public_answer_projection_evaluated",
        tool_id="cross_check_evidence",
        status="computed",
        error_code=None,
        inputs=raw_output or {"execution_error": state.execution_error},
        outputs=projected or {},
        public_effects={
            "answer_schema_valid": answer_schema_valid,
            "public_answer_semantically_valid": answer_semantics,
        },
    )
    trace_hash = canonical_hash(
        tuple(item.event_id for item in state.events),
        prefix="causal_public_runtime_trace:",
    )
    task_report = make_task_validity_report(
        package_id=state.package_id,
        trace_hash=trace_hash,
        task_program_id=(
            record.task_package.task.oracle.task_program.program_id
            if state.program_execution is not None
            else None
        ),
        checks={
            "local_program_contract_valid": local_program_valid,
            "operation_lineage_complete": state.operation_lineage_complete,
            "answer_projection_complete": answer_projection_complete,
            "answer_schema_valid": answer_schema_valid,
            "public_answer_semantically_valid": answer_semantics,
            "reference_identity_valid": reference_identity,
            "citation_complete": citation_complete,
            "terminal_verification_complete": terminal_complete,
            "postcompletion_control_passed": state.postcompletion_call_count == 0,
        },
    )
    event_ids = tuple(item.event_id for item in state.events)
    parent_hash = execution_parent_hash(
        package_id=state.package_id,
        selected_source_choice_handles=state.selected_source_handles,
        event_ids=event_ids,
        task_report_id=task_report.report_id,
    )
    first_event = {
        key: min(
            (item.event_index for item in state.events if item.component_key == key),
            default=10**9,
        )
        for key in state.event_ids_by_component
    }
    dependency_order = all(
        first_event[dependency] < first_event[item.component_key]
        for item in state.ordered_components
        for dependency in item.dependency_component_keys
    )
    all_preconditions = all(item.accepted for item in state.acceptances.values())
    recovery_lineage = (
        all(state.recovery_lineage_checks.values())
        if family == CapabilityFamily.FAILURE_RECOVERY
        else True
    )
    task_closed = terminal_complete
    semantic_qualified = all(
        (
            all(
                state.component_checks.get(item.component_key, False)
                for item in state.ordered_components
            ),
            all_preconditions,
            recovery_lineage,
            dependency_order,
            task_closed,
        )
    )
    reference_path_match = all(
        selected == component.reference_choice_handle
        for selected, component in zip(
            state.selected_source_handles,
            state.ordered_components,
            strict=True,
        )
    )
    mechanism_values = {
        "package_id": state.package_id,
        "execution_parent_hash": parent_hash,
        "capability_family": family,
        "reference_path_match": reference_path_match,
        "component_semantic_checks": {
            item.component_key: state.component_checks.get(item.component_key, False)
            for item in state.ordered_components
        },
        "component_event_ids": {
            item.component_key: tuple(state.event_ids_by_component[item.component_key])
            for item in state.ordered_components
        },
        "action_acceptance_report_ids": {
            item.component_key: state.acceptances[item.component_key].report_id
            for item in state.ordered_components
        },
        "all_state_preconditions_passed": all_preconditions,
        "recovery_rule_receipt_lineage_passed": recovery_lineage,
        "dependency_order_passed": dependency_order,
        "task_closed": task_closed,
        "mechanism_semantically_qualified": semantic_qualified,
    }
    mechanism = cast(
        StateBoundMechanismQualification,
        make_identity_model(
            StateBoundMechanismQualification,
            mechanism_values,
            field="report_id",
            prefix="state_bound_semantic_mechanism_report:",
        ),
    )
    acceptance_ids = tuple(
        state.acceptances[item.component_key].report_id for item in state.ordered_components
    )
    qualified_values = {
        "package_id": state.package_id,
        "task_report_id": task_report.report_id,
        "mechanism_report_id": mechanism.report_id,
        "action_acceptance_report_ids": acceptance_ids,
        "base_valid": task_report.base_valid,
        "mechanism_semantically_qualified": mechanism.mechanism_semantically_qualified,
        "all_state_preconditions_passed": all_preconditions,
        "qualified_valid": bool(
            task_report.base_valid and semantic_qualified and all_preconditions
        ),
    }
    qualified = cast(
        StateBoundQualifiedValidity,
        make_identity_model(
            StateBoundQualifiedValidity,
            qualified_values,
            field="report_id",
            prefix="state_bound_qualified_validity_report:",
        ),
    )
    reference_path = canonical_hash(
        tuple(item.reference_choice_handle for item in state.ordered_components),
        prefix="hardened_reference_path:",
    )
    values = {
        "package_id": state.package_id,
        "source_package_id": state.runtime_input.package_id,
        "replica_index": state.replica_index,
        "steps": tuple(state.steps),
        "events": tuple(state.events),
        "selected_source_choice_handles": tuple(state.selected_source_handles),
        "reference_path_hash": reference_path,
        "execution_parent_hash": parent_hash,
        "task_validity": task_report,
        "mechanism_qualification": mechanism,
        "qualified_validity": qualified,
        "projected_public_answer": projected,
        "public_citations": citations,
        "task_program_executor_invocation_count": state.task_program_executor_invocation_count,
        "task_program_oracle_verifier_invocation_count": (
            state.task_program_oracle_verifier_invocation_count
        ),
        "local_tool_invocation_count": state.local_tool_invocation_count,
        "postcompletion_call_count": state.postcompletion_call_count,
    }
    return cast(
        StepRuntimeResult,
        make_identity_model(
            StepRuntimeResult,
            values,
            field="result_id",
            prefix="step_runtime_result:",
        ),
    )
