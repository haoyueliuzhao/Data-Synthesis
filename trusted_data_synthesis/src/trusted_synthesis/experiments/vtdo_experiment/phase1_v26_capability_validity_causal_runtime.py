from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import (
    ProgramExecution,
    ProgramExecutionError,
    ProgramVerification,
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    OPERATOR_CATALOG,
    PublicOperationPayload,
    PublicResolutionRule,
    PublicSemanticConstraint,
    PublicSemanticTask,
    build_selected_program,
    public_record_from_evidence,
    resolve_public_operator,
    resolve_required_record_handles,
    resolve_rule_record,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    COMPONENT_DECISION_CONTRACT,
    CausalPublicDecisionState,
    CausalPublicPrompt,
    CausalRuntimeEvent,
    CausalSemanticExecutionResult,
    CausalTargetComponent,
    PresentedChoiceCandidate,
    PublicAnswerContract,
    ValiditySeparatedPublicTask,
    candidate_legality_findings,
    canonical_public_answer,
    choice_entry,
    choice_operation,
    make_identity_model,
    make_mechanism_qualification_report,
    make_prompt,
    make_qualified_validity_report,
    make_runtime_event,
    make_task_validity_report,
    project_public_answer,
    public_only_select_action,
)
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import AgentToolCall, AgentToolResult

PRESENTATION_SALT = "finance-v26.171-validity-causal-deleaked-presentation-v1"


@dataclass(frozen=True)
class ComponentSpec:
    component_key: str
    decision_kind: str
    facts: dict[str, Any]
    operations: tuple[PublicOperationPayload, ...]
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeInput:
    package_id: str
    capability_family: CapabilityFamily
    public_task: ValiditySeparatedPublicTask
    components: tuple[CausalTargetComponent, ...]
    finance_core: v168_models.LowNuisanceFinanceCore


def _operation(
    decision_kind: str,
    tool_id: str,
    arguments: dict[str, Any],
) -> PublicOperationPayload:
    return PublicOperationPayload(
        decision_kind=decision_kind,
        tool_id=tool_id,
        arguments=arguments,
    )


def _record_maps(
    core: v168_models.LowNuisanceFinanceCore,
) -> tuple[dict[str, EvidenceItem], dict[str, str], dict[str, str]]:
    evidence = core.operational_record.evidence_bundle.evidence
    by_handle = {public_record_from_evidence(item).record_handle: item for item in evidence}
    id_to_handle = {item.evidence_id: handle for handle, item in by_handle.items()}
    handle_to_id = {handle: item.evidence_id for handle, item in by_handle.items()}
    return by_handle, id_to_handle, handle_to_id


def build_public_task(
    core: v168_models.LowNuisanceFinanceCore,
    semantic_task: PublicSemanticTask,
) -> ValiditySeparatedPublicTask:
    _, id_to_handle, _ = _record_maps(core)
    labels = {
        id_to_handle[evidence_id]: label
        for evidence_id, label in core.operational_record.answer_projection.items()
        if evidence_id in id_to_handle
    }
    values = {
        "required_fields": semantic_task.answer_fields,
        "allowed_fields": semantic_task.answer_fields,
        "numeric_fields": tuple(
            field
            for field in semantic_task.answer_fields
            if field not in {"higher_ref", "selected_ref"}
        ),
        "public_label_by_record_handle": dict(sorted(labels.items())),
    }
    answer_contract = cast(
        PublicAnswerContract,
        make_identity_model(
            PublicAnswerContract,
            values,
            field="contract_id",
            prefix="public_answer_projection_contract:",
        ),
    )
    task_values = {
        "semantic_task": semantic_task,
        "answer_contract": answer_contract,
    }
    return cast(
        ValiditySeparatedPublicTask,
        make_identity_model(
            ValiditySeparatedPublicTask,
            task_values,
            field="task_id",
            prefix="validity_separated_public_finance_task:",
        ),
    )


def _constraint_values(rule: PublicResolutionRule) -> dict[tuple[str, ...], Any]:
    return {item.selector: item.value for item in rule.equals}


def _query_arguments_from_constraints(
    constraints: Sequence[PublicSemanticConstraint],
) -> dict[str, Any]:
    values = {item.selector: item.value for item in constraints}
    arguments: dict[str, Any] = {}
    direct = {
        ("subject", "name"): "subject_alias",
        ("metric", "predicate"): "metric_alias",
        ("period",): "period_label",
    }
    for selector, name in direct.items():
        if selector in values:
            arguments[name] = values[selector]
    filters: dict[str, Any] = {}
    filter_fields = {
        ("source", "source_id"): "source_id",
        ("source", "authority"): "source_authority",
        ("payload", "unit"): "unit",
        ("payload", "currency"): "currency",
        ("metric", "definition_id"): "definition_id",
        ("time_basis",): "time_basis",
        ("frequency",): "frequency",
        ("subject", "type"): "subject_type",
    }
    for selector, name in filter_fields.items():
        if selector in values:
            filters[name] = values[selector]
    if filters:
        arguments["public_filters"] = filters
    return arguments


def _coarse_query_arguments(rule: PublicResolutionRule) -> dict[str, Any]:
    values = _constraint_values(rule)
    arguments = {
        "subject_alias": values[("subject", "name")],
        "metric_alias": values[("metric", "predicate")],
        "period_label": values[("period",)],
        "public_filters": {"source_id": values[("source", "source_id")]},
    }
    return arguments


def _new_finance_runtime(
    core: v168_models.LowNuisanceFinanceCore,
) -> FinanceExecutableSupportRuntime:
    scenario = (
        FinanceTypedRecoveryScenario.model_validate(core.operational_record.recovery_scenario)
        if core.operational_record.recovery_scenario is not None
        else None
    )
    return FinanceExecutableSupportRuntime(
        core.operational_record.public_corpus,
        core.environment,
        recovery_scenario=scenario,
    )


def _call(
    runtime: FinanceExecutableSupportRuntime,
    call_index: int,
    tool_id: str,
    arguments: dict[str, Any],
) -> AgentToolResult:
    try:
        return runtime.execute(
            AgentToolCall(
                call_index=call_index,
                tool_id=tool_id,
                arguments=arguments,
            )
        )
    except (KeyError, TypeError, ValueError) as exc:
        return AgentToolResult(
            status="failed",
            result={},
            error_code="local_contract_exception",
            error_message=type(exc).__name__,
        )


def _actual_failure_receipt(
    core: v168_models.LowNuisanceFinanceCore,
    rule: PublicResolutionRule,
) -> dict[str, Any]:
    runtime = _new_finance_runtime(core)
    arguments = _coarse_query_arguments(rule)
    result = _call(runtime, 1, rule.source_tool_id, arguments)
    if result.status != "failed" or not result.error_code:
        raise ValueError("Recovery failure probe did not produce a typed failed Observation")
    public = {
        "attempt_hash": canonical_hash(arguments, prefix="public_failed_selector:"),
        "error_code": result.error_code,
        "status": result.status,
    }
    return {
        **public,
        "receipt_hash": canonical_hash(public, prefix="actual_failure_receipt:"),
    }


def source_execution_receipt(
    core: v168_models.LowNuisanceFinanceCore,
) -> tuple[ProgramExecution, ProgramVerification, dict[str, bool]]:
    record = core.operational_record
    program = record.task_package.task.oracle.task_program
    evidence = {item.evidence_id: item for item in record.evidence_bundle.evidence}
    execution = TaskProgramExecutor(default_registry()).execute(program, evidence)
    verification = TaskProgramOracleVerifier(default_registry()).verify(
        program,
        evidence,
        execution.node_outputs,
    )
    receipt = {
        "all_required_operations_complete": execution.final_output is not None,
        "no_unresolved_failure": True,
        "oracle_verification_passed": verification.passed,
    }
    return execution, verification, receipt


def _context_specs(task: PublicSemanticTask) -> tuple[ComponentSpec, ...]:
    terminal = next(
        item for item in task.operations if item.operation_handle == task.terminal_operation_handle
    )
    left, right = resolve_required_record_handles(task)
    expected_operator = resolve_public_operator(task, terminal.operation_handle)
    operator_choices = tuple(
        item for item in terminal.allowed_operator_ids if item in OPERATOR_CATALOG
    )
    if expected_operator not in operator_choices or len(operator_choices) < 2:
        raise ValueError("Context operator choice does not contain two legal operators")
    ordered_operators = (expected_operator,) + tuple(
        item for item in operator_choices if item != expected_operator
    )
    fields = list(task.answer_fields)
    rows: tuple[tuple[str, str, dict[str, Any], tuple[PublicOperationPayload, ...]], ...] = (
        (
            "context.operator",
            "select_operator",
            {"operation_handle": terminal.operation_handle},
            tuple(
                _operation(
                    "select_operator",
                    terminal.tool_id,
                    {
                        "operation_handle": terminal.operation_handle,
                        "operator_id": operator_id,
                    },
                )
                for operator_id in ordered_operators
            ),
        ),
        (
            "context.records",
            "select_records",
            {"operation_handle": terminal.operation_handle},
            (
                _operation(
                    "select_records",
                    terminal.tool_id,
                    {"record_handles": [left, right]},
                ),
                _operation(
                    "select_records",
                    terminal.tool_id,
                    {"record_handles": [right, left]},
                ),
                _operation(
                    "select_records",
                    terminal.tool_id,
                    {"record_handles": [left, left]},
                ),
            ),
        ),
        (
            "context.projection",
            "select_projection",
            {"terminal_operation_handle": terminal.operation_handle},
            (
                _operation(
                    "select_projection",
                    "cross_check_evidence",
                    {"answer_fields": fields},
                ),
                _operation(
                    "select_projection",
                    "cross_check_evidence",
                    {"answer_fields": [fields[0]]},
                ),
                _operation(
                    "select_projection",
                    "cross_check_evidence",
                    {"answer_fields": [fields[-1]]},
                ),
            ),
        ),
        (
            "context.scope",
            "select_scope",
            {"aliases": list(task.aliases), "periods": list(task.periods)},
            (
                _operation(
                    "select_scope",
                    "query_structured_fact",
                    {"record_handles": [left, right]},
                ),
                _operation(
                    "select_scope",
                    "query_structured_fact",
                    {"record_handles": [left, left]},
                ),
                _operation(
                    "select_scope",
                    "query_structured_fact",
                    {"record_handles": [right, right]},
                ),
            ),
        ),
    )
    return tuple(
        ComponentSpec(key, decision, facts, operations, tuple(item[0] for item in rows[:index]))
        for index, (key, decision, facts, operations) in enumerate(rows)
    )


def _reconciliation_specs(task: PublicSemanticTask) -> tuple[ComponentSpec, ...]:
    normalizations = tuple(item for item in task.operations if item.node_kind == "normalization")
    terminal = next(
        item for item in task.operations if item.operation_handle == task.terminal_operation_handle
    )
    if len(normalizations) != 2 or len(terminal.input_symbols) != 2:
        raise ValueError("Reconciliation Task is not the exact two-normalization core")
    rows: list[tuple[str, str, dict[str, Any], tuple[PublicOperationPayload, ...]]] = []
    for index, operation in enumerate(normalizations):
        rule = next(
            item
            for item in task.resolution_rules
            if item.variable_symbol == operation.input_symbols[0]
            and item.source_tool_id == "query_structured_fact"
        )
        correct = resolve_rule_record(task, rule)
        other = next(item for item in task.records if item.record_handle != correct.record_handle)
        other_output = next(
            item.output_handle
            for item in normalizations
            if item.output_handle != operation.output_handle
        )
        base = {
            "operation_handle": operation.operation_handle,
            "output_handle": operation.output_handle,
            "record_handle": correct.record_handle,
            "rule_handle": rule.rule_handle,
        }
        rows.append(
            (
                f"reconciliation.mapping.{index + 1}",
                "reconcile_record",
                {"operation_handle": operation.operation_handle, "rule_handle": rule.rule_handle},
                (
                    _operation("reconcile_record", operation.tool_id, base),
                    _operation(
                        "reconcile_record",
                        operation.tool_id,
                        {**base, "record_handle": other.record_handle},
                    ),
                    _operation(
                        "reconcile_record",
                        operation.tool_id,
                        {**base, "output_handle": other_output},
                    ),
                ),
            )
        )
    output_by_symbol = {item.output_symbol: item.output_handle for item in normalizations}
    for index, symbol in enumerate(terminal.input_symbols):
        expected_output_handle = output_by_symbol[symbol]
        alternate_output_handle = next(
            item for item in output_by_symbol.values() if item != expected_output_handle
        )
        base = {
            "input_symbol": symbol,
            "operation_handle": terminal.operation_handle,
        }
        rows.append(
            (
                f"reconciliation.consume.{index + 1}",
                "consume_normalized_output",
                {"input_symbol": symbol, "operation_handle": terminal.operation_handle},
                (
                    _operation(
                        "consume_normalized_output",
                        terminal.tool_id,
                        {**base, "output_handle": expected_output_handle},
                    ),
                    _operation(
                        "consume_normalized_output",
                        terminal.tool_id,
                        {**base, "output_handle": alternate_output_handle},
                    ),
                ),
            )
        )
    return tuple(
        ComponentSpec(key, decision, facts, operations, tuple(item[0] for item in rows[:index]))
        for index, (key, decision, facts, operations) in enumerate(rows)
    )


def _recovery_specs(
    core: v168_models.LowNuisanceFinanceCore,
    task: PublicSemanticTask,
) -> tuple[ComponentSpec, ...]:
    rules = tuple(
        item for item in task.resolution_rules if item.source_tool_id == "query_structured_fact"
    )
    if len(rules) != 2:
        raise ValueError("Recovery Task does not expose two query Rules")
    rows: list[ComponentSpec] = []
    for index in range(4):
        rule = rules[index % 2]
        other = rules[(index + 1) % 2]
        missing = (index + 1) % len(rule.equals)
        correct_selector = [item.model_dump(mode="json") for item in rule.equals]
        other_selector = [item.model_dump(mode="json") for item in other.equals]
        partial_selector = [
            item.model_dump(mode="json")
            for offset, item in enumerate(rule.equals)
            if offset != missing
        ]
        facts = {
            "actual_failure_receipt": _actual_failure_receipt(core, rule),
            "failed_selector": _coarse_query_arguments(rule),
            "rule_handle": rule.rule_handle,
        }
        operations = (
            _operation(
                "revise_selector",
                rule.source_tool_id,
                {
                    "rule_handle": rule.rule_handle,
                    "selector": correct_selector,
                    "source_tool_id": rule.source_tool_id,
                },
            ),
            _operation(
                "revise_selector",
                other.source_tool_id,
                {
                    "rule_handle": other.rule_handle,
                    "selector": other_selector,
                    "source_tool_id": other.source_tool_id,
                },
            ),
            _operation(
                "revise_selector",
                rule.source_tool_id,
                {
                    "rule_handle": rule.rule_handle,
                    "selector": partial_selector,
                    "source_tool_id": rule.source_tool_id,
                },
            ),
        )
        rows.append(
            ComponentSpec(
                component_key=f"recovery.revision.{index + 1}",
                decision_kind="revise_selector",
                facts=facts,
                operations=operations,
                dependencies=tuple(item.component_key for item in rows),
            )
        )
    return tuple(rows)


def _stopping_specs(
    task: PublicSemanticTask,
    depth: ObservationDepth,
    receipt: dict[str, bool],
) -> tuple[ComponentSpec, ...]:
    depth_index = OBSERVATION_DEPTH_ORDER.index(depth)
    readiness: list[ComponentSpec] = []
    for assertion in tuple(receipt)[:depth_index]:
        readiness.append(
            ComponentSpec(
                component_key=f"stopping.readiness.{assertion}",
                decision_kind="assess_dynamic_readiness",
                facts={"assertion": assertion, "execution_receipt": receipt},
                operations=tuple(
                    _operation(
                        "assess_dynamic_readiness",
                        "cross_check_evidence",
                        {"assertion": assertion, "verdict": verdict},
                    )
                    for verdict in task.verdict_catalog
                ),
                dependencies=tuple(item.component_key for item in readiness),
            )
        )
    final = ComponentSpec(
        component_key="stopping.final_decision",
        decision_kind="stop_or_continue",
        facts={
            "execution_receipt": receipt,
            "required_readiness_component_keys": [item.component_key for item in readiness],
        },
        operations=tuple(
            _operation(
                "stop_or_continue",
                "cross_check_evidence",
                {"command": command},
            )
            for command in task.control_commands
        ),
        dependencies=tuple(item.component_key for item in readiness),
    )
    return (final, *readiness)


def component_specs(
    *,
    core: v168_models.LowNuisanceFinanceCore,
    family: CapabilityFamily,
    depth: ObservationDepth,
    task: PublicSemanticTask,
) -> tuple[ComponentSpec, ...]:
    depth_count = OBSERVATION_DEPTH_ORDER.index(depth) + 1
    if family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        return _context_specs(task)[:depth_count]
    if family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        return _reconciliation_specs(task)[:depth_count]
    if family == CapabilityFamily.FAILURE_RECOVERY:
        return _recovery_specs(core, task)[:depth_count]
    _, _, receipt = source_execution_receipt(core)
    return _stopping_specs(task, depth, receipt)


def _action_id(
    package_id: str,
    component_key: str,
    replica_index: int,
    choice_handle: str,
) -> str:
    payload = f"{PRESENTATION_SALT}|{package_id}|{component_key}|{replica_index}|{choice_handle}"
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def prompt_for_component(
    *,
    package_id: str,
    task: ValiditySeparatedPublicTask,
    component: CausalTargetComponent,
    replica_index: int,
) -> CausalPublicPrompt:
    choices = component.public_state.choice_legend
    base = int(
        hashlib.sha256(
            f"{PRESENTATION_SALT}|{package_id}|{component.component_key}".encode()
        ).hexdigest()[:8],
        16,
    ) % len(choices)
    shift = (base + replica_index) % len(choices)
    ordered = choices[shift:] + choices[:shift]
    candidates = tuple(
        PresentedChoiceCandidate(
            action_id=_action_id(
                package_id,
                component.component_key,
                replica_index,
                item.choice_handle,
            ),
            presentation_index=index,
            choice_handle=item.choice_handle,
        )
        for index, item in enumerate(ordered)
    )
    return make_prompt(task=task, state=component.public_state, candidates=candidates)


def build_component(
    *,
    package_id: str,
    family: CapabilityFamily,
    depth: ObservationDepth,
    task: ValiditySeparatedPublicTask,
    spec: ComponentSpec,
) -> CausalTargetComponent:
    legend = tuple(choice_entry(item) for item in spec.operations)
    state = CausalPublicDecisionState(
        state_token=hashlib.sha256(
            f"{package_id}|{spec.component_key}|causal-public-state".encode()
        ).hexdigest()[:24],
        decision_kind=spec.decision_kind,
        facts={
            **spec.facts,
            "dependency_component_keys": list(spec.dependencies),
        },
        choice_legend=legend,
    )
    for entry in legend:
        findings = candidate_legality_findings(task, state, entry.operation)
        if findings:
            raise ValueError(f"v26.171 Candidate violates public Runtime legality:{findings}")
    provisional_values = {
        "component_key": spec.component_key,
        "capability_family": family,
        "depth": depth,
        "public_state": state,
        "reference_choice_handle": legend[0].choice_handle,
        "dependency_component_keys": spec.dependencies,
    }
    provisional = cast(
        CausalTargetComponent,
        make_identity_model(
            CausalTargetComponent,
            provisional_values,
            field="component_id",
            prefix="causal_public_target_component:",
        ),
    )
    probe = prompt_for_component(
        package_id=package_id,
        task=task,
        component=provisional,
        replica_index=0,
    )
    selected_action = public_only_select_action(probe)
    reference = next(
        item.choice_handle for item in probe.candidates if item.action_id == selected_action
    )
    values = {**provisional_values, "reference_choice_handle": reference}
    return cast(
        CausalTargetComponent,
        make_identity_model(
            CausalTargetComponent,
            values,
            field="component_id",
            prefix="causal_public_target_component:",
        ),
    )


def _rule_for_record(
    task: PublicSemanticTask,
    record_handle: str,
) -> PublicResolutionRule:
    matches = tuple(
        rule
        for rule in task.resolution_rules
        if rule.source_tool_id == "query_structured_fact"
        and resolve_rule_record(task, rule).record_handle == record_handle
    )
    if not matches:
        raise ValueError("no public query Rule resolves the selected Finance record")
    return matches[0]


def _event_status(result: AgentToolResult) -> tuple[str, str | None]:
    if result.status == "succeeded":
        return "succeeded", None
    return "failed", result.error_code or "untyped_local_failure"


def _raw_output_from_tool_result(result: AgentToolResult) -> dict[str, Any] | None:
    parent = result.result.get("result") if isinstance(result.result, Mapping) else None
    output = parent.get("output") if isinstance(parent, Mapping) else None
    return dict(output) if isinstance(output, Mapping) else None


def execute_runtime(
    runtime_input: RuntimeInput,
    selected_by_component: Mapping[str, str] | None = None,
) -> CausalSemanticExecutionResult:
    selected_by_component = selected_by_component or {}
    package_id = runtime_input.package_id
    family = runtime_input.capability_family
    public_task = runtime_input.public_task
    task = public_task.semantic_task
    core = runtime_input.finance_core
    record = core.operational_record
    original_program = record.task_package.task.oracle.task_program
    registry = default_registry()
    by_handle, id_to_handle, handle_to_id = _record_maps(core)
    evidence_by_id = {item.evidence_id: item for item in by_handle.values()}
    required_records = resolve_required_record_handles(task)
    selected_records = list(required_records)
    selected_scope = list(required_records)
    selected_operator = resolve_public_operator(task, task.terminal_operation_handle)
    selected_projection = tuple(task.answer_fields)
    chosen: dict[str, str] = {}
    selected_operations: dict[str, PublicOperationPayload] = {}
    for component in runtime_input.components:
        handle = selected_by_component.get(
            component.component_key,
            component.reference_choice_handle,
        )
        selected_operations[component.component_key] = choice_operation(
            component.public_state,
            handle,
        )
        chosen[component.component_key] = handle

    events: list[CausalRuntimeEvent] = []
    event_ids_by_component: dict[str, list[str]] = {
        item.component_key: [] for item in runtime_input.components
    }
    component_checks: dict[str, bool] = {}
    local_tool_calls = 0
    postcompletion_calls = 0

    def append_event(
        *,
        component_key: str | None,
        event_type: str,
        tool_id: str | None,
        status: str,
        error_code: str | None,
        inputs: Any,
        outputs: Any,
        public_effects: Mapping[str, Any],
    ) -> CausalRuntimeEvent:
        event = make_runtime_event(
            event_index=len(events) + 1,
            component_key=component_key,
            event_type=event_type,
            tool_id=tool_id,
            status=cast(Any, status),
            error_code=error_code,
            inputs=inputs,
            outputs=outputs,
            public_effects=public_effects,
        )
        events.append(event)
        if component_key is not None:
            event_ids_by_component[component_key].append(event.event_id)
        return event

    interactive_output: dict[str, Any] | None = None
    operation_lineage_complete = True
    selected_program_input_handles = list(selected_records)

    if family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        for component in runtime_input.components:
            operation = selected_operations[component.component_key]
            arguments = operation.arguments
            if component.component_key == "context.operator":
                selected_operator = str(arguments["operator_id"])
                expected = resolve_public_operator(task, str(arguments["operation_handle"]))
                component_checks[component.component_key] = selected_operator == expected
            elif component.component_key == "context.records":
                selected_records = [str(item) for item in arguments["record_handles"]]
                component_checks[component.component_key] = tuple(selected_records) == tuple(
                    required_records
                )
            elif component.component_key == "context.projection":
                selected_projection = tuple(str(item) for item in arguments["answer_fields"])
                component_checks[component.component_key] = selected_projection == tuple(
                    task.answer_fields
                )
            elif component.component_key == "context.scope":
                selected_scope = [str(item) for item in arguments["record_handles"]]
                component_checks[component.component_key] = tuple(selected_scope) == tuple(
                    required_records
                )
            append_event(
                component_key=component.component_key,
                event_type=f"{component.component_key}.applied",
                tool_id=operation.tool_id,
                status="computed",
                error_code=None,
                inputs=arguments,
                outputs={"semantic_condition_passed": component_checks[component.component_key]},
                public_effects={"decision_kind": operation.decision_kind},
            )
        runtime = _new_finance_runtime(core)
        acquired: list[str] = []
        for handle in selected_scope:
            rule = _rule_for_record(task, handle)
            arguments = _query_arguments_from_constraints(rule.equals)
            local_tool_calls += 1
            result = _call(runtime, local_tool_calls, rule.source_tool_id, arguments)
            status, error = _event_status(result)
            append_event(
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
        operation_lineage_complete = all(item in acquired for item in selected_records)
        selected_program_input_handles = selected_records

    elif family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        runtime = _new_finance_runtime(core)
        normalizations = tuple(
            item for item in task.operations if item.node_kind == "normalization"
        )
        terminal = next(
            item
            for item in task.operations
            if item.operation_handle == task.terminal_operation_handle
        )
        operation_ref_by_output: dict[str, str] = {}
        handle_by_operation_ref: dict[str, str] = {}
        output_by_symbol = {item.output_symbol: item.output_handle for item in normalizations}
        for index, normalization in enumerate(normalizations, start=1):
            key = f"reconciliation.mapping.{index}"
            rule = next(
                item
                for item in task.resolution_rules
                if item.variable_symbol == normalization.input_symbols[0]
                and item.source_tool_id == "query_structured_fact"
            )
            expected_handle = resolve_rule_record(task, rule).record_handle
            selected = selected_operations.get(key)
            arguments = (
                selected.arguments
                if selected is not None
                else {
                    "operation_handle": normalization.operation_handle,
                    "output_handle": normalization.output_handle,
                    "record_handle": expected_handle,
                    "rule_handle": rule.rule_handle,
                }
            )
            record_handle = str(arguments["record_handle"])
            target_output = str(arguments["output_handle"])
            query_rule = _rule_for_record(task, record_handle)
            query_arguments = _query_arguments_from_constraints(query_rule.equals)
            local_tool_calls += 1
            query_result = _call(
                runtime,
                local_tool_calls,
                query_rule.source_tool_id,
                query_arguments,
            )
            query_status, query_error = _event_status(query_result)
            append_event(
                component_key=None,
                event_type="reconciliation.record_acquired",
                tool_id=query_rule.source_tool_id,
                status=query_status,
                error_code=query_error,
                inputs=query_arguments,
                outputs=query_result.result,
                public_effects={"record_handle": record_handle},
            )
            normalization_arguments: dict[str, Any] = {
                "evidence_ids": [handle_to_id[record_handle]],
                "target_definition": normalization.normalization_target,
            }
            local_tool_calls += 1
            result = _call(
                runtime,
                local_tool_calls,
                "normalize_metric_unit_period",
                normalization_arguments,
            )
            status, error = _event_status(result)
            operation_ref = result.result.get("normalized_operation_ref")
            if result.status == "succeeded" and isinstance(operation_ref, str):
                operation_ref_by_output[target_output] = operation_ref
                handle_by_operation_ref[operation_ref] = record_handle
            if selected is not None:
                component_checks[key] = bool(
                    result.status == "succeeded"
                    and record_handle == expected_handle
                    and target_output == normalization.output_handle
                    and str(arguments["rule_handle"]) == rule.rule_handle
                )
            append_event(
                component_key=key if selected is not None else None,
                event_type="normalization_reference_emitted",
                tool_id="normalize_metric_unit_period",
                status=status,
                error_code=error,
                inputs=normalization_arguments,
                outputs=result.result,
                public_effects={
                    "output_handle": target_output,
                    "record_handle": record_handle,
                    "reference_emitted": isinstance(operation_ref, str),
                },
            )
        operands: list[dict[str, str]] = []
        selected_program_input_handles = []
        for index, symbol in enumerate(terminal.input_symbols, start=1):
            key = f"reconciliation.consume.{index}"
            expected_output = output_by_symbol[symbol]
            selected = selected_operations.get(key)
            output_handle = (
                str(selected.arguments["output_handle"])
                if selected is not None
                else expected_output
            )
            operation_ref = operation_ref_by_output.get(output_handle)
            consumed = operation_ref is not None
            if operation_ref is not None:
                operands.append(
                    {
                        "operation_ref": operation_ref,
                        "selector": "normalized_inputs.target",
                    }
                )
                selected_program_input_handles.append(handle_by_operation_ref[operation_ref])
            if selected is not None:
                component_checks[key] = bool(consumed and output_handle == expected_output)
            append_event(
                component_key=key if selected is not None else None,
                event_type="normalization_reference_consumed",
                tool_id="calculator",
                status="computed",
                error_code=None,
                inputs=(
                    selected.arguments
                    if selected is not None
                    else {
                        "input_symbol": symbol,
                        "operation_handle": terminal.operation_handle,
                        "output_handle": expected_output,
                    }
                ),
                outputs={"reference_consumed": consumed},
                public_effects={
                    "input_symbol": symbol,
                    "output_handle": output_handle,
                },
            )
        operation_lineage_complete = len(operands) == len(terminal.input_symbols)
        if operation_lineage_complete:
            calculator_arguments: dict[str, Any] = {
                "operator": resolve_public_operator(task, terminal.operation_handle),
                "operands": operands,
                "parameters": {},
            }
            local_tool_calls += 1
            result = _call(runtime, local_tool_calls, "calculator", calculator_arguments)
            status, error = _event_status(result)
            interactive_output = _raw_output_from_tool_result(result)
            operation_lineage_complete = result.status == "succeeded" and (
                interactive_output is not None
            )
            append_event(
                component_key=None,
                event_type="reconciliation.terminal_calculator",
                tool_id="calculator",
                status=status,
                error_code=error,
                inputs=calculator_arguments,
                outputs=result.result,
                public_effects={"all_normalized_references_consumed": len(operands) == 2},
            )

    elif family == CapabilityFamily.FAILURE_RECOVERY:
        rules = {item.rule_handle: item for item in task.resolution_rules}
        recovery_lineage_checks: list[bool] = []
        for component in runtime_input.components:
            runtime = _new_finance_runtime(core)
            operation = selected_operations[component.component_key]
            target_rule = rules[str(component.public_state.facts["rule_handle"])]
            coarse = _coarse_query_arguments(target_rule)
            local_tool_calls += 1
            failed = _call(
                runtime,
                1,
                target_rule.source_tool_id,
                coarse,
            )
            failed_status, failed_error = _event_status(failed)
            failure_event = append_event(
                component_key=component.component_key,
                event_type="typed_failure_observed",
                tool_id=target_rule.source_tool_id,
                status=failed_status,
                error_code=failed_error,
                inputs=coarse,
                outputs=failed.result,
                public_effects={"error_code": failed.error_code},
            )
            selector = tuple(
                PublicSemanticConstraint.model_validate(item)
                for item in cast(Sequence[Any], operation.arguments["selector"])
            )
            revised_arguments = _query_arguments_from_constraints(selector)
            local_tool_calls += 1
            retry = _call(
                runtime,
                2,
                str(operation.arguments["source_tool_id"]),
                revised_arguments,
            )
            retry_status, retry_error = _event_status(retry)
            retry_event = append_event(
                component_key=component.component_key,
                event_type=(
                    "recovery_succeeded" if retry.status == "succeeded" else "recovery_retry_failed"
                ),
                tool_id=str(operation.arguments["source_tool_id"]),
                status=retry_status,
                error_code=retry_error,
                inputs=revised_arguments,
                outputs=retry.result,
                public_effects={"selector_changed": revised_arguments != coarse},
            )
            expected_handle = resolve_rule_record(task, target_rule).record_handle
            returned_handles = tuple(
                id_to_handle[item] for item in retry.evidence_ids if item in id_to_handle
            )
            if len(returned_handles) == 1:
                position = required_records.index(expected_handle)
                selected_records[position] = returned_handles[0]
            exact_selector = tuple(selector) == target_rule.equals
            recovery_lineage_checks.append(
                failed.status == "failed"
                and failed.error_code == "typed_selector_requires_refinement"
                and retry.status == "succeeded"
                and failure_event.event_index < retry_event.event_index
            )
            component_checks[component.component_key] = bool(
                failed.status == "failed"
                and failed.error_code == "typed_selector_requires_refinement"
                and retry.status == "succeeded"
                and str(operation.arguments["rule_handle"]) == target_rule.rule_handle
                and exact_selector
                and returned_handles == (expected_handle,)
                and failure_event.event_index < retry_event.event_index
            )
        selected_program_input_handles = selected_records
        operation_lineage_complete = all(recovery_lineage_checks)

    selected_program = None
    program_execution: ProgramExecution | None = None
    verification: ProgramVerification | None = None
    executor_calls = 0
    verifier_calls = 0
    execution_error: str | None = None
    if family != CapabilityFamily.SEMANTIC_RECONCILIATION:
        selected_program_input_handles = selected_records
    try:
        if len(selected_program_input_handles) != 2:
            raise ValueError("selected Program does not have two public operands")
        if family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION and not operation_lineage_complete:
            raise ValueError("selected Program operand is outside the executed public Scope")
        selected_program = build_selected_program(
            original_program,
            operator_id=selected_operator,
            evidence_ids=cast(
                tuple[str, str],
                tuple(handle_to_id[item] for item in selected_program_input_handles),
            ),
            registry=registry,
        )
        program_execution = TaskProgramExecutor(registry).execute(
            selected_program,
            evidence_by_id,
        )
        executor_calls += 1
        verification = TaskProgramOracleVerifier(registry).verify(
            original_program,
            evidence_by_id,
            program_execution.node_outputs,
        )
        verifier_calls = 1
    except (KeyError, ProgramExecutionError, ValueError) as exc:
        execution_error = getattr(exc, "error_code", type(exc).__name__)

    if family == CapabilityFamily.STATE_DEPENDENT_STOPPING:
        receipt = {
            "all_required_operations_complete": program_execution is not None,
            "no_unresolved_failure": execution_error is None,
            "oracle_verification_passed": bool(verification and verification.passed),
        }
        readiness_checks: dict[str, bool] = {}
        readiness_components = tuple(
            item
            for item in runtime_input.components
            if item.component_key.startswith("stopping.readiness.")
        )
        for component in readiness_components:
            operation = selected_operations[component.component_key]
            assertion = str(operation.arguments["assertion"])
            expected_verdict = "true" if receipt[assertion] else "false"
            passed = str(operation.arguments["verdict"]) == expected_verdict
            readiness_checks[component.component_key] = passed
            component_checks[component.component_key] = passed
            append_event(
                component_key=component.component_key,
                event_type="dynamic_readiness_assessed",
                tool_id="cross_check_evidence",
                status="computed",
                error_code=None,
                inputs={"assertion": assertion, "receipt": receipt},
                outputs={"verdict": operation.arguments["verdict"]},
                public_effects={"readiness_matches_runtime": passed},
            )
        final_component = next(
            item
            for item in runtime_input.components
            if item.component_key == "stopping.final_decision"
        )
        final_operation = selected_operations[final_component.component_key]
        command = str(final_operation.arguments["command"])
        stop_ready = all(receipt.values()) and all(readiness_checks.values())
        stopped = command == "stop" and stop_ready
        component_checks[final_component.component_key] = stopped
        append_event(
            component_key=final_component.component_key,
            event_type="stopping_terminal_decision",
            tool_id="cross_check_evidence",
            status="computed",
            error_code=None,
            inputs={"command": command, "receipt": receipt},
            outputs={"stopped": stopped},
            public_effects={"stop_ready": stop_ready},
        )
        if command != "stop" and program_execution is not None and selected_program is not None:
            postcompletion_status: Literal["succeeded", "failed"] = "succeeded"
            postcompletion_error: str | None = None
            try:
                TaskProgramExecutor(registry).execute(selected_program, evidence_by_id)
                executor_calls += 1
            except ProgramExecutionError:
                postcompletion_status = "failed"
                postcompletion_error = "ProgramExecutionError"
            postcompletion_calls += 1
            append_event(
                component_key=final_component.component_key,
                event_type="postcompletion_call_recorded",
                tool_id="calculator",
                status=postcompletion_status,
                error_code=postcompletion_error,
                inputs={"command": command},
                outputs={"postcompletion_violation": True},
                public_effects={"later_program_invocation": True},
            )
    else:
        stopped = bool(verification and verification.passed)

    raw_output = (
        interactive_output
        if family == CapabilityFamily.SEMANTIC_RECONCILIATION
        else (dict(program_execution.final_output) if program_execution is not None else None)
    )
    if family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        operation_lineage_complete = bool(
            operation_lineage_complete
            and raw_output is not None
            and program_execution is not None
            and raw_output == program_execution.final_output
        )

    projected: dict[str, Any] | None = None
    if raw_output is not None:
        projected = project_public_answer(
            raw_output,
            selected_fields=selected_projection,
            evidence_id_to_record_handle=id_to_handle,
            contract=public_task.answer_contract,
        )
    answer_projection_complete = bool(
        projected is not None
        and set(projected) == set(selected_projection)
        and not any(
            isinstance(value, str) and value.startswith("evidence:") for value in projected.values()
        )
    )
    answer_schema_valid = bool(
        projected is not None and set(projected) == set(public_task.answer_contract.required_fields)
    )
    public_answer_semantically_valid = False
    if answer_schema_valid and projected is not None:
        try:
            observed_answer = canonical_public_answer(projected, public_task.answer_contract)
            expected_answer = canonical_public_answer(
                record.projected_expected_output,
                public_task.answer_contract,
            )
            public_answer_semantically_valid = observed_answer == expected_answer
        except ValueError:
            public_answer_semantically_valid = False
    reference_identity_valid = bool(
        projected is not None
        and all(
            not (isinstance(value, str) and value.startswith("evidence:"))
            for value in projected.values()
        )
        and (
            "higher_ref" not in projected
            or projected["higher_ref"]
            in set(public_task.answer_contract.public_label_by_record_handle.values())
        )
    )
    public_citations = tuple(sorted(set(selected_program_input_handles)))
    selected_evidence_ids = {
        handle_to_id[item] for item in selected_program_input_handles if item in handle_to_id
    }
    citation_complete = selected_evidence_ids == set(record.target_program_evidence_ids)
    local_program_contract_valid = bool(
        verification is not None
        and verification.passed
        and (family != CapabilityFamily.SEMANTIC_RECONCILIATION or operation_lineage_complete)
    )
    terminal_verification_complete = bool(
        verification is not None and verification.passed and stopped
    )
    postcompletion_control_passed = postcompletion_calls == 0
    append_event(
        component_key=None,
        event_type="public_answer_projection_evaluated",
        tool_id="cross_check_evidence",
        status="computed",
        error_code=None,
        inputs=raw_output or {"execution_error": execution_error},
        outputs=projected or {},
        public_effects={
            "answer_schema_valid": answer_schema_valid,
            "public_answer_semantically_valid": public_answer_semantically_valid,
        },
    )

    trace_hash = canonical_hash(
        tuple(item.event_id for item in events),
        prefix="causal_public_runtime_trace:",
    )
    task_checks = {
        "local_program_contract_valid": local_program_contract_valid,
        "operation_lineage_complete": operation_lineage_complete,
        "answer_projection_complete": answer_projection_complete,
        "answer_schema_valid": answer_schema_valid,
        "public_answer_semantically_valid": public_answer_semantically_valid,
        "reference_identity_valid": reference_identity_valid,
        "citation_complete": citation_complete,
        "terminal_verification_complete": terminal_verification_complete,
        "postcompletion_control_passed": postcompletion_control_passed,
    }
    task_report = make_task_validity_report(
        package_id=package_id,
        trace_hash=trace_hash,
        task_program_id=selected_program.program_id if selected_program is not None else None,
        checks=task_checks,
    )
    first_event_index = {
        key: min(
            (event.event_index for event in events if event.component_key == key),
            default=10**9,
        )
        for key in event_ids_by_component
    }
    dependency_order_passed = all(
        first_event_index[dependency] < first_event_index[component.component_key]
        for component in runtime_input.components
        for dependency in component.dependency_component_keys
    )
    causal_effect_count = sum(bool(value) for value in event_ids_by_component.values())
    mechanism_report = make_mechanism_qualification_report(
        package_id=package_id,
        trace_hash=trace_hash,
        capability_family=family,
        component_checks=component_checks,
        component_event_ids=event_ids_by_component,
        causal_effect_count=causal_effect_count,
        dependency_order_passed=dependency_order_passed,
    )
    qualified_report = make_qualified_validity_report(
        package_id=package_id,
        task=task_report,
        mechanism=mechanism_report,
    )
    values = {
        "package_id": package_id,
        "selected_program": selected_program,
        "program_execution": program_execution,
        "oracle_verification": verification,
        "raw_program_output": raw_output,
        "projected_public_answer": projected,
        "public_citations": public_citations,
        "events": tuple(events),
        "task_validity": task_report,
        "mechanism_qualification": mechanism_report,
        "qualified_validity": qualified_report,
        "chosen_choice_handles": tuple(
            chosen[item.component_key] for item in runtime_input.components
        ),
        "task_program_executor_invocation_count": executor_calls,
        "task_program_oracle_verifier_invocation_count": verifier_calls,
        "local_tool_invocation_count": local_tool_calls,
        "postcompletion_call_count": postcompletion_calls,
    }
    return cast(
        CausalSemanticExecutionResult,
        make_identity_model(
            CausalSemanticExecutionResult,
            values,
            field="result_id",
            prefix="causal_semantic_execution_result:",
        ),
    )


def component_contract_projection() -> dict[CapabilityFamily, tuple[str, ...]]:
    return {
        family: tuple(sorted(set(values.values())))
        for family, values in COMPONENT_DECISION_CONTRACT.items()
    }
