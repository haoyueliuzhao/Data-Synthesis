from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.operations.program import (
    ProgramExecution,
    ProgramVerification,
)
from trusted_synthesis.core.task.capability_observation import (
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.program import TaskProgram
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    PUBLIC_ACTION_ID_LENGTH,
    PublicOperationPayload,
    PublicSemanticConstraint,
    PublicSemanticTask,
    canonical_bytes,
    resolve_public_operator,
    resolve_required_record_handles,
    resolve_rule_record,
    scan_model_visible_leakage,
)
from trusted_synthesis.hashing import canonical_hash

VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION = (
    "validity_separated_public_semantic_capability_depth.v1"
)
PUBLIC_CHOICE_COMMAND: Final = "execute_public_choice"
PUBLIC_CHOICE_HANDLE_PATTERN: Final = r"^public_choice:[0-9a-f]{64}$"
NUMERIC_ANSWER_FIELDS: Final = frozenset(
    {
        "difference",
        "difference_percentage_points",
        "left_growth_pct",
        "right_growth_pct",
        "value",
    }
)

ComponentDecisionContract = dict[CapabilityFamily, dict[str, str]]
COMPONENT_DECISION_CONTRACT: Final[ComponentDecisionContract] = {
    CapabilityFamily.CONTEXT_CONDITIONED_ACTION: {
        "context.operator": "select_operator",
        "context.records": "select_records",
        "context.projection": "select_projection",
        "context.scope": "select_scope",
    },
    CapabilityFamily.SEMANTIC_RECONCILIATION: {
        "reconciliation.mapping.1": "reconcile_record",
        "reconciliation.mapping.2": "reconcile_record",
        "reconciliation.consume.1": "consume_normalized_output",
        "reconciliation.consume.2": "consume_normalized_output",
    },
    CapabilityFamily.FAILURE_RECOVERY: {
        "recovery.revision.1": "revise_selector",
        "recovery.revision.2": "revise_selector",
        "recovery.revision.3": "revise_selector",
        "recovery.revision.4": "revise_selector",
    },
    CapabilityFamily.STATE_DEPENDENT_STOPPING: {
        "stopping.readiness.all_required_operations_complete": ("assess_dynamic_readiness"),
        "stopping.readiness.no_unresolved_failure": "assess_dynamic_readiness",
        "stopping.readiness.oracle_verification_passed": ("assess_dynamic_readiness"),
        "stopping.final_decision": "stop_or_continue",
    },
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: _identity(provisional, field, prefix)}, **values)


class PublicAnswerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    required_fields: tuple[str, ...] = Field(min_length=1)
    allowed_fields: tuple[str, ...] = Field(min_length=1)
    numeric_fields: tuple[str, ...]
    public_label_by_record_handle: dict[str, str]
    citation_kind: Literal["public_finance_record_handle"] = "public_finance_record_handle"
    exact_decimal_semantics: Literal[True] = True
    additional_result_fields_allowed: Literal[False] = False
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> PublicAnswerContract:
        if self.required_fields != tuple(dict.fromkeys(self.required_fields)):
            raise ValueError("public Answer Contract repeats a required field")
        if self.allowed_fields != tuple(dict.fromkeys(self.allowed_fields)):
            raise ValueError("public Answer Contract repeats an allowed field")
        if not set(self.required_fields) <= set(self.allowed_fields):
            raise ValueError("public Answer Contract required fields are not allowed")
        if not set(self.numeric_fields) <= set(self.required_fields):
            raise ValueError("public Answer Contract numeric fields are not required")
        if any(
            re.fullmatch(r"public_finance_record:[0-9a-f]{64}", handle) is None
            for handle in self.public_label_by_record_handle
        ):
            raise ValueError("public Answer Contract contains a malformed record handle")
        if scan_model_visible_leakage(self.model_dump(mode="json")):
            raise ValueError("public Answer Contract exposes a Host-only identity")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "public_answer_projection_contract:",
        ):
            raise ValueError("public Answer Contract identity is invalid")
        return self


class ValiditySeparatedPublicTask(FrozenModel):
    task_id: str = Field(min_length=1)
    semantic_task: PublicSemanticTask
    answer_contract: PublicAnswerContract
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_task(self) -> ValiditySeparatedPublicTask:
        record_handles = {item.record_handle for item in self.semantic_task.records}
        if self.answer_contract.required_fields != self.semantic_task.answer_fields:
            raise ValueError("public Answer Contract crosses the semantic Task schema")
        if not set(self.answer_contract.public_label_by_record_handle) <= record_handles:
            raise ValueError("public Answer Contract labels an absent Finance record")
        if scan_model_visible_leakage(self.model_dump(mode="json")):
            raise ValueError("validity-separated public Task exposes Host-only content")
        if self.task_id != _identity(
            self,
            "task_id",
            "validity_separated_public_finance_task:",
        ):
            raise ValueError("validity-separated public Task identity is invalid")
        return self


class PublicChoiceLegendEntry(FrozenModel):
    choice_handle: str = Field(pattern=PUBLIC_CHOICE_HANDLE_PATTERN)
    operation: PublicOperationPayload
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_entry(self) -> PublicChoiceLegendEntry:
        expected = canonical_hash(
            self.operation.model_dump(mode="json"),
            prefix="public_choice:",
        )
        if self.choice_handle != expected:
            raise ValueError("public Choice handle is not operation-derived")
        return self


class CausalPublicDecisionState(FrozenModel):
    state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    decision_kind: str = Field(min_length=1)
    facts: dict[str, Any] = Field(min_length=1)
    history: tuple[dict[str, Any], ...] = ()
    choice_legend: tuple[PublicChoiceLegendEntry, ...] = Field(
        min_length=2,
        max_length=3,
    )
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> CausalPublicDecisionState:
        handles = tuple(item.choice_handle for item in self.choice_legend)
        if len(handles) != len(set(handles)):
            raise ValueError("causal public State repeats a Choice handle")
        if any(item.operation.decision_kind != self.decision_kind for item in self.choice_legend):
            raise ValueError("causal public State crosses a Decision kind")
        if scan_model_visible_leakage(self.model_dump(mode="json")):
            raise ValueError("causal public State exposes Host-only content")
        return self


class CausalTargetComponent(FrozenModel):
    component_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    public_state: CausalPublicDecisionState
    reference_choice_handle: str = Field(pattern=PUBLIC_CHOICE_HANDLE_PATTERN)
    dependency_component_keys: tuple[str, ...] = ()
    target_capability_component: Literal[True] = True
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_component(self) -> CausalTargetComponent:
        contract = COMPONENT_DECISION_CONTRACT[self.capability_family]
        expected_decision = contract.get(self.component_key)
        if expected_decision is None:
            raise ValueError("Component key is outside its capability-family contract")
        if self.public_state.decision_kind != expected_decision:
            raise ValueError("Component Decision kind crosses its capability family")
        handles = {item.choice_handle for item in self.public_state.choice_legend}
        if self.reference_choice_handle not in handles:
            raise ValueError("Component reference is not a visible semantic Choice")
        if len(self.dependency_component_keys) != len(set(self.dependency_component_keys)):
            raise ValueError("Component dependency list repeats a predecessor")
        if self.component_key in self.dependency_component_keys:
            raise ValueError("Component depends on itself")
        if self.component_id != _identity(
            self,
            "component_id",
            "causal_public_target_component:",
        ):
            raise ValueError("causal target Component identity is invalid")
        return self


class PresentedChoiceCandidate(FrozenModel):
    action_id: str = Field(
        min_length=PUBLIC_ACTION_ID_LENGTH,
        max_length=PUBLIC_ACTION_ID_LENGTH,
        pattern=rf"^[0-9a-f]{{{PUBLIC_ACTION_ID_LENGTH}}}$",
    )
    presentation_index: int = Field(ge=0, le=2)
    command: Literal["execute_public_choice"] = PUBLIC_CHOICE_COMMAND
    choice_handle: str = Field(pattern=PUBLIC_CHOICE_HANDLE_PATTERN)
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION


class CausalPublicPrompt(FrozenModel):
    prompt_hash: str = Field(min_length=64, max_length=64)
    rendered_bytes: int = Field(ge=1)
    task: ValiditySeparatedPublicTask
    state: CausalPublicDecisionState
    candidates: tuple[PresentedChoiceCandidate, ...] = Field(
        min_length=2,
        max_length=3,
    )
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_prompt(self) -> CausalPublicPrompt:
        if tuple(item.presentation_index for item in self.candidates) != tuple(
            range(len(self.candidates))
        ):
            raise ValueError("causal public Prompt positions are not contiguous")
        if len({item.action_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("causal public Prompt repeats an action ID")
        if {item.choice_handle for item in self.candidates} != {
            item.choice_handle for item in self.state.choice_legend
        }:
            raise ValueError("causal public Prompt changes its semantic Choice set")
        candidate_lengths = {
            len(canonical_bytes(item.model_dump(mode="json"))) for item in self.candidates
        }
        if len(candidate_lengths) != 1:
            raise ValueError("fixed-width public Candidate encodings differ")
        legend = {item.choice_handle: item.operation for item in self.state.choice_legend}
        argument_counts = {len(legend[item.choice_handle].arguments) for item in self.candidates}
        if len(argument_counts) != 1:
            raise ValueError("public Candidate semantic argument counts differ")
        visible = self.model_dump(mode="json")
        if _find_key(visible, "padding"):
            raise ValueError("causal public Prompt serializes visible padding")
        payload = self.model_dump(
            mode="json",
            exclude={"prompt_hash", "rendered_bytes", "schema_version"},
        )
        rendered = canonical_bytes(payload)
        if self.prompt_hash != hashlib.sha256(rendered).hexdigest():
            raise ValueError("causal public Prompt hash is invalid")
        if self.rendered_bytes != len(rendered):
            raise ValueError("causal public Prompt byte count is invalid")
        return self


class CausalRuntimeEvent(FrozenModel):
    event_id: str = Field(min_length=1)
    event_index: int = Field(ge=1)
    component_key: str | None = None
    event_type: str = Field(min_length=1)
    tool_id: str | None = None
    status: Literal["succeeded", "failed", "typed", "computed"]
    error_code: str | None = None
    input_hash: str = Field(min_length=1)
    output_hash: str = Field(min_length=1)
    public_effects: dict[str, Any]
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_event(self) -> CausalRuntimeEvent:
        if self.status == "failed" and not self.error_code:
            raise ValueError("failed causal Runtime event lacks an error code")
        if self.status != "failed" and self.error_code is not None:
            raise ValueError("nonfailed causal Runtime event carries an error code")
        if self.event_id != _identity(
            self,
            "event_id",
            "causal_public_runtime_event:",
        ):
            raise ValueError("causal Runtime event identity is invalid")
        return self


class StaticTaskValidityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    trace_hash: str = Field(min_length=1)
    task_program_id: str | None = None
    local_program_contract_valid: bool
    operation_lineage_complete: bool
    answer_projection_complete: bool
    answer_schema_valid: bool
    public_answer_semantically_valid: bool
    reference_identity_valid: bool
    citation_complete: bool
    terminal_verification_complete: bool
    postcompletion_control_passed: bool
    base_valid: bool
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> StaticTaskValidityReport:
        expected = all(
            (
                self.local_program_contract_valid,
                self.operation_lineage_complete,
                self.answer_projection_complete,
                self.answer_schema_valid,
                self.public_answer_semantically_valid,
                self.reference_identity_valid,
                self.citation_complete,
                self.terminal_verification_complete,
                self.postcompletion_control_passed,
            )
        )
        if self.base_valid != expected:
            raise ValueError("Base validity is not the exact task-check conjunction")
        payload = self.model_dump(mode="json")
        if any("reference_choice" in str(key) for key in payload):
            raise ValueError("Base validity contains Host reference-choice metadata")
        if self.report_id != _identity(
            self,
            "report_id",
            "static_public_task_validity_report:",
        ):
            raise ValueError("static task-validity report identity is invalid")
        return self


class StaticMechanismQualificationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    trace_hash: str = Field(min_length=1)
    capability_family: CapabilityFamily
    component_checks: dict[str, bool] = Field(min_length=1)
    component_event_ids: dict[str, tuple[str, ...]] = Field(min_length=1)
    causal_effect_count: int = Field(ge=0)
    dependency_order_passed: bool
    mechanism_qualified: bool
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> StaticMechanismQualificationReport:
        if set(self.component_checks) != set(self.component_event_ids):
            raise ValueError("mechanism report Component and event parents differ")
        expected = (
            all(self.component_checks.values())
            and self.dependency_order_passed
            and self.causal_effect_count >= len(self.component_checks)
        )
        if self.mechanism_qualified != expected:
            raise ValueError("mechanism qualification is not trace-derived")
        if self.report_id != _identity(
            self,
            "report_id",
            "static_mechanism_qualification_report:",
        ):
            raise ValueError("static mechanism report identity is invalid")
        return self


class StaticQualifiedValidityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    task_report_id: str = Field(min_length=1)
    mechanism_report_id: str = Field(min_length=1)
    base_valid: bool
    mechanism_qualified: bool
    qualified_valid: bool
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> StaticQualifiedValidityReport:
        if self.qualified_valid != (self.base_valid and self.mechanism_qualified):
            raise ValueError("Qualified validity is not Base and Mechanism")
        if self.report_id != _identity(
            self,
            "report_id",
            "static_qualified_validity_report:",
        ):
            raise ValueError("static Qualified report identity is invalid")
        return self


class CausalSemanticExecutionResult(FrozenModel):
    result_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    selected_program: TaskProgram | None
    program_execution: ProgramExecution | None
    oracle_verification: ProgramVerification | None
    raw_program_output: dict[str, Any] | None
    projected_public_answer: dict[str, Any] | None
    public_citations: tuple[str, ...]
    events: tuple[CausalRuntimeEvent, ...] = Field(min_length=1)
    task_validity: StaticTaskValidityReport
    mechanism_qualification: StaticMechanismQualificationReport
    qualified_validity: StaticQualifiedValidityReport
    chosen_choice_handles: tuple[str, ...] = Field(min_length=1)
    task_program_executor_invocation_count: int = Field(ge=0)
    task_program_oracle_verifier_invocation_count: int = Field(ge=0, le=1)
    local_tool_invocation_count: int = Field(ge=0)
    postcompletion_call_count: int = Field(ge=0)
    result_assigned_by_host: Literal[False] = False
    schema_version: str = VALIDITY_SEPARATED_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> CausalSemanticExecutionResult:
        trace_hash = canonical_hash(
            tuple(item.event_id for item in self.events),
            prefix="causal_public_runtime_trace:",
        )
        if (
            self.task_validity.package_id != self.package_id
            or self.mechanism_qualification.package_id != self.package_id
            or self.qualified_validity.package_id != self.package_id
            or self.task_validity.trace_hash != trace_hash
            or self.mechanism_qualification.trace_hash != trace_hash
            or self.qualified_validity.task_report_id != self.task_validity.report_id
            or self.qualified_validity.mechanism_report_id != self.mechanism_qualification.report_id
            or self.qualified_validity.base_valid != self.task_validity.base_valid
            or self.qualified_validity.mechanism_qualified
            != self.mechanism_qualification.mechanism_qualified
        ):
            raise ValueError("causal execution validity parent binding is inconsistent")
        if self.task_program_oracle_verifier_invocation_count != int(
            self.oracle_verification is not None
        ):
            raise ValueError("causal execution Verifier accounting is inconsistent")
        if self.result_id != _identity(
            self,
            "result_id",
            "causal_semantic_execution_result:",
        ):
            raise ValueError("causal semantic execution Result identity is invalid")
        return self


def _find_key(value: Any, target: str) -> bool:
    if isinstance(value, Mapping):
        return any(str(key) == target or _find_key(item, target) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_find_key(item, target) for item in value)
    return False


def choice_entry(operation: PublicOperationPayload) -> PublicChoiceLegendEntry:
    return PublicChoiceLegendEntry(
        choice_handle=canonical_hash(
            operation.model_dump(mode="json"),
            prefix="public_choice:",
        ),
        operation=operation,
    )


def choice_operation(
    state: CausalPublicDecisionState,
    choice_handle: str,
) -> PublicOperationPayload:
    matches = tuple(
        item.operation for item in state.choice_legend if item.choice_handle == choice_handle
    )
    if len(matches) != 1:
        raise ValueError("public Choice handle is absent or ambiguous")
    return matches[0]


def _desired_operation(prompt: CausalPublicPrompt) -> dict[str, Any]:
    task = prompt.task.semantic_task
    facts = prompt.state.facts
    operations = {item.operation_handle: item for item in task.operations}
    rules = {item.rule_handle: item for item in task.resolution_rules}
    outputs = {item.output_symbol: item.output_handle for item in task.operations}
    decision = prompt.state.decision_kind
    if decision == "select_operator":
        operation = operations[str(facts["operation_handle"])]
        return {
            "operation_handle": operation.operation_handle,
            "operator_id": resolve_public_operator(task, operation.operation_handle),
        }
    if decision in {"select_records", "select_scope"}:
        return {"record_handles": list(resolve_required_record_handles(task))}
    if decision == "select_projection":
        return {"answer_fields": list(task.answer_fields)}
    if decision == "reconcile_record":
        rule = rules[str(facts["rule_handle"])]
        operation = operations[str(facts["operation_handle"])]
        return {
            "operation_handle": operation.operation_handle,
            "output_handle": operation.output_handle,
            "record_handle": resolve_rule_record(task, rule).record_handle,
            "rule_handle": rule.rule_handle,
        }
    if decision == "consume_normalized_output":
        operation = operations[str(facts["operation_handle"])]
        input_symbol = str(facts["input_symbol"])
        return {
            "input_symbol": input_symbol,
            "operation_handle": operation.operation_handle,
            "output_handle": outputs[input_symbol],
        }
    if decision == "revise_selector":
        rule = rules[str(facts["rule_handle"])]
        return {
            "rule_handle": rule.rule_handle,
            "selector": [item.model_dump(mode="json") for item in rule.equals],
            "source_tool_id": rule.source_tool_id,
        }
    if decision == "assess_dynamic_readiness":
        assertion = str(facts["assertion"])
        receipt = cast(Mapping[str, Any], facts["execution_receipt"])
        value = receipt[assertion]
        return {
            "assertion": assertion,
            "verdict": "true" if value is True else "false" if value is False else "unknown",
        }
    if decision == "stop_or_continue":
        receipt = cast(Mapping[str, Any], facts["execution_receipt"])
        return {
            "command": (
                "stop" if all(value is True for value in receipt.values()) else "repeat_program"
            )
        }
    raise ValueError(f"unknown causal public Decision kind:{decision}")


def public_only_select_action(prompt: CausalPublicPrompt) -> str:
    desired = _desired_operation(prompt)
    operation_by_handle = {
        item.choice_handle: item.operation for item in prompt.state.choice_legend
    }
    matches = tuple(
        candidate.action_id
        for candidate in prompt.candidates
        if operation_by_handle[candidate.choice_handle].arguments == desired
    )
    if len(matches) != 1:
        raise ValueError("public-only Selector did not identify one semantic Choice")
    return matches[0]


def candidate_legality_findings(
    task: ValiditySeparatedPublicTask,
    state: CausalPublicDecisionState,
    operation: PublicOperationPayload,
) -> tuple[str, ...]:
    semantic = task.semantic_task
    findings: list[str] = []
    if operation.tool_id not in semantic.allowed_tools:
        findings.append("tool_not_allowed")
    if operation.decision_kind != state.decision_kind:
        findings.append("decision_kind_mismatch")
    arguments = operation.arguments
    operation_by_handle = {item.operation_handle: item for item in semantic.operations}
    rule_handles = {item.rule_handle for item in semantic.resolution_rules}
    record_handles = {item.record_handle for item in semantic.records}
    output_handles = {item.output_handle for item in semantic.operations}
    decision = state.decision_kind
    if decision == "select_operator":
        handle = str(arguments.get("operation_handle"))
        operator = str(arguments.get("operator_id"))
        if handle not in operation_by_handle:
            findings.append("operation_handle_absent")
        elif operator not in operation_by_handle[handle].allowed_operator_ids:
            findings.append("operator_not_allowed_for_operation")
    elif decision in {"select_records", "select_scope"}:
        handles = arguments.get("record_handles")
        if not isinstance(handles, list) or len(handles) != 2:
            findings.append("record_handle_shape_invalid")
        elif not set(str(item) for item in handles) <= record_handles:
            findings.append("record_handle_absent")
    elif decision == "select_projection":
        fields = arguments.get("answer_fields")
        if not isinstance(fields, list) or not fields:
            findings.append("answer_field_shape_invalid")
        elif not set(str(item) for item in fields) <= set(semantic.answer_fields):
            findings.append("answer_field_absent")
    elif decision == "reconcile_record":
        if str(arguments.get("operation_handle")) not in operation_by_handle:
            findings.append("operation_handle_absent")
        if str(arguments.get("rule_handle")) not in rule_handles:
            findings.append("rule_handle_absent")
        if str(arguments.get("record_handle")) not in record_handles:
            findings.append("record_handle_absent")
        if str(arguments.get("output_handle")) not in output_handles:
            findings.append("output_handle_absent")
    elif decision == "consume_normalized_output":
        if str(arguments.get("operation_handle")) not in operation_by_handle:
            findings.append("operation_handle_absent")
        if str(arguments.get("output_handle")) not in output_handles:
            findings.append("output_handle_absent")
        if not str(arguments.get("input_symbol") or ""):
            findings.append("input_symbol_absent")
    elif decision == "revise_selector":
        if str(arguments.get("rule_handle")) not in rule_handles:
            findings.append("rule_handle_absent")
        try:
            selector = tuple(
                PublicSemanticConstraint.model_validate(item)
                for item in cast(Sequence[Any], arguments.get("selector") or ())
            )
        except (TypeError, ValueError):
            selector = ()
        if not selector:
            findings.append("selector_absent")
    elif decision == "assess_dynamic_readiness":
        if str(arguments.get("verdict")) not in semantic.verdict_catalog:
            findings.append("verdict_not_allowed")
    elif decision == "stop_or_continue":
        if str(arguments.get("command")) not in semantic.control_commands:
            findings.append("control_command_not_allowed")
    return tuple(sorted(set(findings)))


def _canonical_decimal(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError("numeric answer field is not a finite Decimal")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("numeric answer field is not Decimal-compatible") from exc
    if not number.is_finite():
        raise ValueError("numeric answer field is nonfinite")
    normalized = number.normalize()
    if normalized == 0:
        normalized = Decimal(0)
    return format(normalized, "f")


def canonical_public_answer(
    answer: Mapping[str, Any],
    contract: PublicAnswerContract,
) -> dict[str, Any]:
    if set(answer) != set(contract.required_fields):
        raise ValueError("public answer does not have the exact required field set")
    output: dict[str, Any] = {}
    for field in contract.required_fields:
        value = answer[field]
        output[field] = _canonical_decimal(value) if field in contract.numeric_fields else value
    return output


def project_public_answer(
    raw_output: Mapping[str, Any],
    *,
    selected_fields: Sequence[str],
    evidence_id_to_record_handle: Mapping[str, str],
    contract: PublicAnswerContract,
) -> dict[str, Any]:
    output = {field: raw_output[field] for field in selected_fields if field in raw_output}
    for field in ("higher_ref", "selected_ref"):
        value = output.get(field)
        if value is None:
            continue
        handle = evidence_id_to_record_handle.get(str(value))
        if handle is not None and handle in contract.public_label_by_record_handle:
            output[field] = contract.public_label_by_record_handle[handle]
    return output


def make_task_validity_report(
    *,
    package_id: str,
    trace_hash: str,
    task_program_id: str | None,
    checks: Mapping[str, bool],
) -> StaticTaskValidityReport:
    names = (
        "local_program_contract_valid",
        "operation_lineage_complete",
        "answer_projection_complete",
        "answer_schema_valid",
        "public_answer_semantically_valid",
        "reference_identity_valid",
        "citation_complete",
        "terminal_verification_complete",
        "postcompletion_control_passed",
    )
    values: dict[str, Any] = {name: bool(checks.get(name)) for name in names}
    values.update(
        {
            "package_id": package_id,
            "trace_hash": trace_hash,
            "task_program_id": task_program_id,
            "base_valid": all(values.values()),
        }
    )
    return cast(
        StaticTaskValidityReport,
        make_identity_model(
            StaticTaskValidityReport,
            values,
            field="report_id",
            prefix="static_public_task_validity_report:",
        ),
    )


def make_mechanism_qualification_report(
    *,
    package_id: str,
    trace_hash: str,
    capability_family: CapabilityFamily,
    component_checks: Mapping[str, bool],
    component_event_ids: Mapping[str, Sequence[str]],
    causal_effect_count: int,
    dependency_order_passed: bool,
) -> StaticMechanismQualificationReport:
    event_ids = {key: tuple(values) for key, values in sorted(component_event_ids.items())}
    checks = dict(sorted(component_checks.items()))
    qualified = (
        all(checks.values()) and dependency_order_passed and causal_effect_count >= len(checks)
    )
    values = {
        "package_id": package_id,
        "trace_hash": trace_hash,
        "capability_family": capability_family,
        "component_checks": checks,
        "component_event_ids": event_ids,
        "causal_effect_count": causal_effect_count,
        "dependency_order_passed": dependency_order_passed,
        "mechanism_qualified": qualified,
    }
    return cast(
        StaticMechanismQualificationReport,
        make_identity_model(
            StaticMechanismQualificationReport,
            values,
            field="report_id",
            prefix="static_mechanism_qualification_report:",
        ),
    )


def make_qualified_validity_report(
    *,
    package_id: str,
    task: StaticTaskValidityReport,
    mechanism: StaticMechanismQualificationReport,
) -> StaticQualifiedValidityReport:
    values = {
        "package_id": package_id,
        "task_report_id": task.report_id,
        "mechanism_report_id": mechanism.report_id,
        "base_valid": task.base_valid,
        "mechanism_qualified": mechanism.mechanism_qualified,
        "qualified_valid": task.base_valid and mechanism.mechanism_qualified,
    }
    return cast(
        StaticQualifiedValidityReport,
        make_identity_model(
            StaticQualifiedValidityReport,
            values,
            field="report_id",
            prefix="static_qualified_validity_report:",
        ),
    )


def make_runtime_event(
    *,
    event_index: int,
    component_key: str | None,
    event_type: str,
    tool_id: str | None,
    status: Literal["succeeded", "failed", "typed", "computed"],
    error_code: str | None,
    inputs: Any,
    outputs: Any,
    public_effects: Mapping[str, Any],
) -> CausalRuntimeEvent:
    values = {
        "event_index": event_index,
        "component_key": component_key,
        "event_type": event_type,
        "tool_id": tool_id,
        "status": status,
        "error_code": error_code,
        "input_hash": canonical_hash(inputs, prefix="causal_runtime_event_input:"),
        "output_hash": canonical_hash(outputs, prefix="causal_runtime_event_output:"),
        "public_effects": dict(public_effects),
    }
    return cast(
        CausalRuntimeEvent,
        make_identity_model(
            CausalRuntimeEvent,
            values,
            field="event_id",
            prefix="causal_public_runtime_event:",
        ),
    )


def make_prompt(
    *,
    task: ValiditySeparatedPublicTask,
    state: CausalPublicDecisionState,
    candidates: Sequence[PresentedChoiceCandidate],
) -> CausalPublicPrompt:
    payload = {
        "task": task.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in candidates],
    }
    rendered = canonical_bytes(payload)
    return CausalPublicPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        task=task,
        state=state,
        candidates=tuple(candidates),
    )


def public_prompt_shortcut_findings(prompt: CausalPublicPrompt) -> tuple[str, ...]:
    findings: list[str] = []
    payload = prompt.model_dump(mode="json")
    if _find_key(payload, "padding"):
        findings.append("visible_padding")
    lengths = [len(canonical_bytes(item.model_dump(mode="json"))) for item in prompt.candidates]
    if len(set(lengths)) != 1:
        findings.append("candidate_byte_length_varies")
    field_counts = [len(item.model_dump(mode="json")) for item in prompt.candidates]
    if len(set(field_counts)) != 1:
        findings.append("candidate_field_count_varies")
    argument_counts = [
        len(choice_operation(prompt.state, item.choice_handle).arguments)
        for item in prompt.candidates
    ]
    if len(set(argument_counts)) != 1:
        findings.append("semantic_argument_count_varies")
    return tuple(sorted(findings))


def semantic_task_hash(task: ValiditySeparatedPublicTask) -> str:
    return task.task_id


def json_round_trip(value: BaseModel) -> BaseModel:
    return type(value).model_validate_json(
        json.dumps(value.model_dump(mode="json"), sort_keys=True)
    )
