from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import CapabilityFamily
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    PUBLIC_ACTION_ID_LENGTH,
    PublicOperationPayload,
    canonical_bytes,
    resolve_public_operator,
    resolve_required_record_handles,
    resolve_rule_record,
    scan_model_visible_leakage,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    CausalRuntimeEvent,
    CausalSemanticExecutionResult,
    CausalTargetComponent,
    PresentedChoiceCandidate,
    ValiditySeparatedPublicTask,
    candidate_legality_findings,
    choice_operation,
)
from trusted_synthesis.hashing import canonical_hash

DYNAMIC_CAPABILITY_DEPTH_VERSION: Final = "dynamic_capability_depth.v1"
DYNAMIC_PRESENTATION_SALT: Final = "finance-v26.172-joint-legend-candidate-presentation-v1"
DISPLAY_CHOICE_PATTERN: Final = r"^public_choice:[0-9a-f]{64}$"
INDEX_PATTERN: Final = r"^[0-9]{2}$"
T = TypeVar("T")


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


class DynamicLegendEntry(FrozenModel):
    """A fixed-width row into State-level, shared semantic value catalogs."""

    choice_handle: str = Field(pattern=DISPLAY_CHOICE_PATTERN)
    value_indices: tuple[str, ...] = Field(min_length=1)
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_entry(self) -> DynamicLegendEntry:
        if any(re.fullmatch(INDEX_PATTERN, item) is None for item in self.value_indices):
            raise ValueError("dynamic Legend contains a non-fixed-width value index")
        return self


class DynamicPublicObservation(FrozenModel):
    receipt_id: str = Field(min_length=1)
    state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    selected_choice_handle: str = Field(pattern=DISPLAY_CHOICE_PATTERN)
    predecessor_receipt_ids: tuple[str, ...]
    event_ids: tuple[str, ...] = Field(min_length=1)
    status: Literal["accepted", "failed", "typed"]
    public_effects: dict[str, Any] = Field(min_length=1)
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> DynamicPublicObservation:
        if len(self.event_ids) != len(set(self.event_ids)):
            raise ValueError("dynamic Observation repeats a Runtime event")
        if scan_model_visible_leakage(self.model_dump(mode="json", exclude={"receipt_id"})):
            raise ValueError("dynamic Observation exposes Host-only content")
        if self.receipt_id != _identity(
            self,
            "receipt_id",
            "dynamic_public_observation_receipt:",
        ):
            raise ValueError("dynamic Observation receipt identity is invalid")
        return self


class DynamicPublicState(FrozenModel):
    state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    decision_kind: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    facts: dict[str, Any] = Field(min_length=1)
    argument_fields: tuple[str, ...] = Field(min_length=1)
    argument_value_catalogs: dict[str, tuple[Any, ...]] = Field(min_length=1)
    choice_legend: tuple[DynamicLegendEntry, ...] = Field(min_length=2, max_length=3)
    prior_observations: tuple[DynamicPublicObservation, ...] = ()
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> DynamicPublicState:
        if tuple(sorted(self.argument_fields)) != self.argument_fields:
            raise ValueError("dynamic State argument fields are not canonical")
        if set(self.argument_fields) != set(self.argument_value_catalogs):
            raise ValueError("dynamic State semantic catalogs do not match argument fields")
        for field, values in self.argument_value_catalogs.items():
            encoded = tuple(canonical_bytes(value) for value in values)
            if not values or len(encoded) != len(set(encoded)) or tuple(sorted(encoded)) != encoded:
                raise ValueError(f"dynamic State value catalog is not canonical:{field}")
        handles = tuple(item.choice_handle for item in self.choice_legend)
        if len(handles) != len(set(handles)):
            raise ValueError("dynamic State repeats a display Choice handle")
        for entry in self.choice_legend:
            if len(entry.value_indices) != len(self.argument_fields):
                raise ValueError("dynamic Legend row does not cover every semantic field")
            for field, index in zip(self.argument_fields, entry.value_indices, strict=True):
                if int(index) >= len(self.argument_value_catalogs[field]):
                    raise ValueError("dynamic Legend index is outside its shared catalog")
        row_lengths = {
            len(canonical_bytes(item.model_dump(mode="json"))) for item in self.choice_legend
        }
        if len(row_lengths) != 1:
            raise ValueError("dynamic Legend rows are not structurally equal-width")
        receipt_ids = tuple(item.receipt_id for item in self.prior_observations)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("dynamic State repeats a predecessor Observation")
        visible = self.model_dump(mode="json", exclude={"state_token"})
        if scan_model_visible_leakage(visible):
            raise ValueError("dynamic public State exposes Host-only content")
        expected = hashlib.sha256(canonical_bytes(visible)).hexdigest()[:24]
        if self.state_token != expected:
            raise ValueError("dynamic public State token is not content-derived")
        return self


class DynamicPublicPrompt(FrozenModel):
    prompt_hash: str = Field(min_length=64, max_length=64)
    rendered_bytes: int = Field(ge=1)
    task: ValiditySeparatedPublicTask
    state: DynamicPublicState
    candidates: tuple[PresentedChoiceCandidate, ...] = Field(min_length=2, max_length=3)
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_prompt(self) -> DynamicPublicPrompt:
        if tuple(item.presentation_index for item in self.candidates) != tuple(
            range(len(self.candidates))
        ):
            raise ValueError("dynamic Prompt Candidate positions are not contiguous")
        if len({item.action_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("dynamic Prompt repeats an action ID")
        if {item.choice_handle for item in self.candidates} != {
            item.choice_handle for item in self.state.choice_legend
        }:
            raise ValueError("dynamic Prompt Candidate and Legend Choice sets differ")
        candidate_lengths = {
            len(canonical_bytes(item.model_dump(mode="json"))) for item in self.candidates
        }
        if len(candidate_lengths) != 1:
            raise ValueError("dynamic Prompt Candidate rows are not equal-width")
        payload = self.model_dump(
            mode="json",
            exclude={"prompt_hash", "rendered_bytes", "schema_version"},
        )
        rendered = canonical_bytes(payload)
        if self.prompt_hash != hashlib.sha256(rendered).hexdigest():
            raise ValueError("dynamic Prompt hash is invalid")
        if self.rendered_bytes != len(rendered):
            raise ValueError("dynamic Prompt byte count is invalid")
        if scan_model_visible_leakage(payload):
            raise ValueError("dynamic Prompt exposes Host-only content")
        return self


class DynamicStepRecord(FrozenModel):
    step_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    step_index: int = Field(ge=0, le=3)
    component_key: str = Field(min_length=1)
    dependency_component_keys: tuple[str, ...]
    source_choice_handle: str = Field(min_length=1)
    displayed_choice_handle: str = Field(pattern=DISPLAY_CHOICE_PATTERN)
    selected_action_id: str = Field(min_length=PUBLIC_ACTION_ID_LENGTH)
    prompt: DynamicPublicPrompt
    observation: DynamicPublicObservation
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_step(self) -> DynamicStepRecord:
        selected = tuple(
            item for item in self.prompt.candidates if item.action_id == self.selected_action_id
        )
        if len(selected) != 1 or selected[0].choice_handle != self.displayed_choice_handle:
            raise ValueError("dynamic Step selected action is not in its current Prompt")
        if self.observation.state_token != self.prompt.state.state_token:
            raise ValueError("dynamic Step Observation crosses a current State")
        if self.observation.selected_choice_handle != self.displayed_choice_handle:
            raise ValueError("dynamic Step Observation crosses the selected Choice")
        if self.step_id != _identity(self, "step_id", "dynamic_depth_step_record:"):
            raise ValueError("dynamic Step identity is invalid")
        return self


class DynamicReplicaTrace(FrozenModel):
    trace_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    steps: tuple[DynamicStepRecord, ...] = Field(min_length=1, max_length=4)
    terminal_result_id: str = Field(min_length=1)
    precommitted_choice_vector_allowed: Literal[False] = False
    future_prompt_access_allowed: Literal[False] = False
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_trace(self) -> DynamicReplicaTrace:
        if tuple(item.step_index for item in self.steps) != tuple(range(len(self.steps))):
            raise ValueError("dynamic Trace steps are not contiguous")
        if any(
            item.package_id != self.package_id or item.replica_index != self.replica_index
            for item in self.steps
        ):
            raise ValueError("dynamic Trace crosses a Package or Replica")
        receipt_by_key: dict[str, str] = {}
        for step in self.steps:
            expected = tuple(receipt_by_key[key] for key in step.dependency_component_keys)
            if step.observation.predecessor_receipt_ids != expected:
                raise ValueError("dynamic Trace does not bind exact predecessor receipts")
            if tuple(item.receipt_id for item in step.prompt.state.prior_observations) != expected:
                raise ValueError("dynamic next Prompt was not rebuilt from reached Observations")
            receipt_by_key[step.component_key] = step.observation.receipt_id
        if self.trace_id != _identity(self, "trace_id", "dynamic_depth_replica_trace:"):
            raise ValueError("dynamic Trace identity is invalid")
        return self


class CandidateLegalityProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    source_choice_handle: str = Field(min_length=1)
    reference_path_choice: bool
    publicly_grounded: bool
    publicly_executable: bool
    state_precondition_valid: bool
    mechanism_relevant: bool
    task_semantically_valid: bool
    findings: tuple[str, ...]
    execution_result_id: str = Field(min_length=1)
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_projection(self) -> CandidateLegalityProjection:
        if self.mechanism_relevant and not self.state_precondition_valid:
            raise ValueError("mechanism-relevant Candidate violates its current State")
        if self.state_precondition_valid and not self.publicly_executable:
            raise ValueError("State-valid Candidate is not publicly executable")
        if self.publicly_executable and not self.publicly_grounded:
            raise ValueError("publicly executable Candidate is ungrounded")
        if self.projection_id != _identity(
            self,
            "projection_id",
            "dynamic_candidate_legality_projection:",
        ):
            raise ValueError("Candidate legality projection identity is invalid")
        return self


class SemanticMechanismQualification(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    execution_result_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    reference_path_match: bool
    component_semantic_checks: dict[str, bool] = Field(min_length=1)
    component_event_ids: dict[str, tuple[str, ...]] = Field(min_length=1)
    dependency_order_passed: bool
    task_closed: bool
    mechanism_semantically_qualified: bool
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> SemanticMechanismQualification:
        if set(self.component_semantic_checks) != set(self.component_event_ids):
            raise ValueError("semantic mechanism Component and event parents differ")
        expected = (
            all(self.component_semantic_checks.values())
            and self.dependency_order_passed
            and self.task_closed
        )
        if self.mechanism_semantically_qualified != expected:
            raise ValueError("semantic mechanism qualification is not event-derived")
        if self.report_id != _identity(
            self,
            "report_id",
            "semantic_mechanism_qualification_report:",
        ):
            raise ValueError("semantic mechanism report identity is invalid")
        return self


class BaselineTraceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_result_id: str = Field(min_length=1)
    replay_result_id: str = Field(min_length=1)
    chosen_choice_handles: tuple[str, ...] = Field(min_length=1)
    event_ids: tuple[str, ...] = Field(min_length=1)
    event_order_hash: str = Field(min_length=1)
    task_report_id: str = Field(min_length=1)
    mechanism_report_id: str = Field(min_length=1)
    qualified_report_id: str = Field(min_length=1)
    canonical_result_sha256: str = Field(min_length=64, max_length=64)
    source_replay_bytes_match: Literal[True] = True
    schema_version: str = DYNAMIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> BaselineTraceBinding:
        expected_order = canonical_hash(self.event_ids, prefix="baseline_event_order:")
        if self.event_order_hash != expected_order:
            raise ValueError("baseline trace event order hash is stale")
        if self.source_result_id != self.replay_result_id:
            raise ValueError("baseline trace replay Result identity differs")
        if self.binding_id != _identity(
            self,
            "binding_id",
            "dynamic_baseline_trace_binding:",
        ):
            raise ValueError("baseline trace binding identity is invalid")
        return self


def _rotate(values: tuple[T, ...], shift: int) -> tuple[T, ...]:
    offset = shift % len(values)
    return values[offset:] + values[:offset]


def topological_components(
    components: Sequence[CausalTargetComponent],
) -> tuple[CausalTargetComponent, ...]:
    by_key = {item.component_key: item for item in components}
    if len(by_key) != len(components):
        raise ValueError("dynamic component graph repeats a Component key")
    if any(
        dependency not in by_key
        for item in components
        for dependency in item.dependency_component_keys
    ):
        raise ValueError("dynamic component graph contains an absent dependency")
    remaining = set(by_key)
    ordered: list[CausalTargetComponent] = []
    emitted: set[str] = set()
    while remaining:
        ready = sorted(
            key for key in remaining if set(by_key[key].dependency_component_keys) <= emitted
        )
        if not ready:
            raise ValueError("dynamic component graph is cyclic")
        for key in ready:
            ordered.append(by_key[key])
            emitted.add(key)
            remaining.remove(key)
    return tuple(ordered)


def _value_catalog(
    operations: Sequence[PublicOperationPayload],
) -> tuple[tuple[str, ...], dict[str, tuple[Any, ...]], tuple[tuple[str, ...], ...]]:
    fields = tuple(sorted(operations[0].arguments))
    if any(tuple(sorted(item.arguments)) != fields for item in operations):
        raise ValueError("dynamic semantic table crosses an argument schema")
    catalogs: dict[str, tuple[Any, ...]] = {}
    encoded_rows: list[tuple[str, ...]] = []
    for field in fields:
        unique = {
            canonical_bytes(item.arguments[field]): item.arguments[field] for item in operations
        }
        catalogs[field] = tuple(unique[key] for key in sorted(unique))
    for operation in operations:
        indices: list[str] = []
        for field in fields:
            target = canonical_bytes(operation.arguments[field])
            index = next(
                offset
                for offset, value in enumerate(catalogs[field])
                if canonical_bytes(value) == target
            )
            indices.append(f"{index:02d}")
        encoded_rows.append(tuple(indices))
    return fields, catalogs, tuple(encoded_rows)


def _display_handles(
    *,
    package_id: str,
    component_key: str,
    replica_index: int,
    choice_count: int,
) -> tuple[str, ...]:
    pool = tuple(
        sorted(
            "public_choice:"
            + hashlib.sha256(
                f"{DYNAMIC_PRESENTATION_SALT}|{package_id}|{component_key}|"
                f"{replica_index}|handle-rank|{rank}".encode()
            ).hexdigest()
            for rank in range(choice_count)
        )
    )
    shift = replica_index % choice_count
    return tuple(pool[(index + shift) % choice_count] for index in range(choice_count))


def _position_shift(replica_index: int, choice_count: int, *, candidate: bool) -> int:
    if choice_count == 3:
        return ((2 if candidate else 1) * replica_index) % choice_count
    if candidate:
        return (0, 0, 0, 1, 1, 1)[replica_index]
    return replica_index % choice_count


def _action_id(
    package_id: str,
    component_key: str,
    replica_index: int,
    choice_handle: str,
) -> str:
    payload = (
        f"{DYNAMIC_PRESENTATION_SALT}|{package_id}|{component_key}|{replica_index}|{choice_handle}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:PUBLIC_ACTION_ID_LENGTH]


def make_dynamic_prompt(
    *,
    package_id: str,
    task: ValiditySeparatedPublicTask,
    component: CausalTargetComponent,
    replica_index: int,
    predecessor_observations: Sequence[DynamicPublicObservation],
) -> tuple[DynamicPublicPrompt, dict[str, str]]:
    source_entries = tuple(component.public_state.choice_legend)
    operations = tuple(item.operation for item in source_entries)
    if len({item.decision_kind for item in operations}) != 1:
        raise ValueError("dynamic Prompt crosses Decision kinds")
    if len({item.tool_id for item in operations}) != 1:
        raise ValueError("dynamic Prompt crosses Tool schemas")
    fields, catalogs, rows = _value_catalog(operations)
    handles = _display_handles(
        package_id=package_id,
        component_key=component.component_key,
        replica_index=replica_index,
        choice_count=len(operations),
    )
    source_by_display = {
        handles[index]: source_entries[index].choice_handle for index in range(len(handles))
    }
    entries = tuple(
        DynamicLegendEntry(choice_handle=handles[index], value_indices=rows[index])
        for index in range(len(handles))
    )
    ordered_entries = _rotate(
        entries,
        _position_shift(replica_index, len(entries), candidate=False),
    )
    state_values = {
        "decision_kind": component.public_state.decision_kind,
        "tool_id": operations[0].tool_id,
        "facts": {
            key: value
            for key, value in component.public_state.facts.items()
            if key != "dependency_component_keys"
        },
        "argument_fields": fields,
        "argument_value_catalogs": catalogs,
        "choice_legend": ordered_entries,
        "prior_observations": tuple(predecessor_observations),
        "schema_version": DYNAMIC_CAPABILITY_DEPTH_VERSION,
    }
    state_token_payload = {
        **state_values,
        "choice_legend": [item.model_dump(mode="json") for item in ordered_entries],
        "prior_observations": [item.model_dump(mode="json") for item in predecessor_observations],
    }
    state_token = hashlib.sha256(canonical_bytes(state_token_payload)).hexdigest()[:24]
    state = DynamicPublicState(state_token=state_token, **state_values)
    candidate_source = _rotate(
        entries,
        _position_shift(replica_index, len(entries), candidate=True),
    )
    candidates = tuple(
        PresentedChoiceCandidate(
            action_id=_action_id(
                package_id,
                component.component_key,
                replica_index,
                entry.choice_handle,
            ),
            presentation_index=index,
            choice_handle=entry.choice_handle,
        )
        for index, entry in enumerate(candidate_source)
    )
    payload = {
        "task": task.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in candidates],
    }
    rendered = canonical_bytes(payload)
    prompt = DynamicPublicPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        task=task,
        state=state,
        candidates=candidates,
    )
    return prompt, source_by_display


def resolve_dynamic_operation(
    state: DynamicPublicState,
    choice_handle: str,
) -> PublicOperationPayload:
    entry = next(
        (item for item in state.choice_legend if item.choice_handle == choice_handle),
        None,
    )
    if entry is None:
        raise ValueError("dynamic Choice is absent from current State")
    arguments = {
        field: state.argument_value_catalogs[field][int(index)]
        for field, index in zip(state.argument_fields, entry.value_indices, strict=True)
    }
    return PublicOperationPayload(
        decision_kind=state.decision_kind,
        tool_id=state.tool_id,
        arguments=arguments,
    )


def _desired_operation(prompt: DynamicPublicPrompt) -> dict[str, Any]:
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
        symbol = str(facts["input_symbol"])
        return {
            "input_symbol": symbol,
            "operation_handle": operation.operation_handle,
            "output_handle": outputs[symbol],
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
            "command": "stop"
            if all(value is True for value in receipt.values())
            else "repeat_program"
        }
    raise ValueError(f"unknown dynamic Decision kind:{decision}")


def public_only_select_dynamic_action(prompt: DynamicPublicPrompt) -> str:
    desired = _desired_operation(prompt)
    matches = tuple(
        item.action_id
        for item in prompt.candidates
        if resolve_dynamic_operation(prompt.state, item.choice_handle).arguments == desired
    )
    if len(matches) != 1:
        raise ValueError("public-only dynamic Selector did not identify one Choice")
    return matches[0]


def make_observation(
    *,
    prompt: DynamicPublicPrompt,
    selected_choice_handle: str,
    predecessor_receipt_ids: Sequence[str],
    events: Sequence[CausalRuntimeEvent],
) -> DynamicPublicObservation:
    if not events:
        raise ValueError("dynamic Observation has no actual Runtime event")
    operation = resolve_dynamic_operation(prompt.state, selected_choice_handle)
    status: Literal["accepted", "failed", "typed"] = (
        "failed"
        if any(item.status == "failed" for item in events)
        else "typed"
        if any(item.status == "typed" for item in events)
        else "accepted"
    )
    values = {
        "state_token": prompt.state.state_token,
        "selected_choice_handle": selected_choice_handle,
        "predecessor_receipt_ids": tuple(predecessor_receipt_ids),
        "event_ids": tuple(item.event_id for item in events),
        "status": status,
        "public_effects": {
            "selected_operation": operation.model_dump(mode="json"),
            "runtime_effects": [item.public_effects for item in events],
        },
    }
    return cast(
        DynamicPublicObservation,
        make_identity_model(
            DynamicPublicObservation,
            values,
            field="receipt_id",
            prefix="dynamic_public_observation_receipt:",
        ),
    )


def classify_candidate(
    *,
    task: ValiditySeparatedPublicTask,
    component: CausalTargetComponent,
    source_choice_handle: str,
    result: CausalSemanticExecutionResult,
) -> tuple[bool, bool, bool, bool, tuple[str, ...]]:
    operation = choice_operation(component.public_state, source_choice_handle)
    findings = candidate_legality_findings(task, component.public_state, operation)
    grounded = not any(item.endswith("_absent") for item in findings)
    executable = not findings
    facts = component.public_state.facts
    arguments = operation.arguments
    decision = operation.decision_kind
    precondition = executable
    if decision == "revise_selector":
        precondition = bool(
            executable
            and str(arguments.get("rule_handle")) == str(facts.get("rule_handle"))
            and arguments.get("selector") != facts.get("failed_selector")
        )
    elif decision == "reconcile_record":
        precondition = bool(
            executable
            and str(arguments.get("rule_handle")) == str(facts.get("rule_handle"))
            and str(arguments.get("operation_handle")) == str(facts.get("operation_handle"))
        )
    elif decision == "consume_normalized_output":
        precondition = bool(
            executable
            and str(arguments.get("input_symbol")) == str(facts.get("input_symbol"))
            and str(arguments.get("operation_handle")) == str(facts.get("operation_handle"))
        )
    elif decision == "assess_dynamic_readiness":
        precondition = bool(
            executable and str(arguments.get("assertion")) == str(facts.get("assertion"))
        )
    relevant = precondition
    task_valid = result.task_validity.base_valid
    labels = list(findings)
    if executable and not precondition:
        labels.append("current_state_precondition_mismatch")
    if precondition and not task_valid:
        labels.append("task_semantics_failed")
    return grounded, executable, precondition, relevant, tuple(sorted(set(labels)))


def semantic_mechanism_qualification(
    *,
    package_id: str,
    family: CapabilityFamily,
    components: Sequence[CausalTargetComponent],
    selected_by_component: Mapping[str, str],
    result: CausalSemanticExecutionResult,
) -> SemanticMechanismQualification:
    ordered = topological_components(components)
    events_by_key = {
        item.component_key: tuple(
            event for event in result.events if event.component_key == item.component_key
        )
        for item in ordered
    }
    checks: dict[str, bool] = {}
    for component in ordered:
        events = events_by_key[component.component_key]
        if family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
            checks[component.component_key] = bool(
                events
                and any(item.event_type.endswith(".applied") for item in events)
                and result.task_validity.local_program_contract_valid
            )
        elif family == CapabilityFamily.SEMANTIC_RECONCILIATION:
            if component.component_key.startswith("reconciliation.mapping"):
                checks[component.component_key] = any(
                    item.event_type == "normalization_reference_emitted"
                    and item.status == "succeeded"
                    and item.public_effects.get("reference_emitted") is True
                    for item in events
                )
            else:
                checks[component.component_key] = any(
                    item.event_type == "normalization_reference_consumed"
                    and item.public_effects.get("output_handle") is not None
                    and item.output_hash
                    for item in events
                )
        elif family == CapabilityFamily.FAILURE_RECOVERY:
            typed_failure = any(
                item.event_type == "typed_failure_observed"
                and item.status == "failed"
                and item.error_code == "typed_selector_requires_refinement"
                for item in events
            )
            changed_success = any(
                item.event_type == "recovery_succeeded"
                and item.status == "succeeded"
                and item.public_effects.get("selector_changed") is True
                for item in events
            )
            checks[component.component_key] = typed_failure and changed_success
        else:
            if component.component_key.startswith("stopping.readiness"):
                checks[component.component_key] = any(
                    item.event_type == "dynamic_readiness_assessed"
                    and item.public_effects.get("readiness_matches_runtime") is True
                    for item in events
                )
            else:
                checks[component.component_key] = (
                    any(
                        item.event_type == "stopping_terminal_decision"
                        and item.public_effects.get("stop_ready") is True
                        for item in events
                    )
                    and result.postcompletion_call_count == 0
                )
    first_index = {
        key: min((item.event_index for item in events), default=10**9)
        for key, events in events_by_key.items()
    }
    dependency_order = all(
        first_index[dependency] < first_index[item.component_key]
        for item in ordered
        for dependency in item.dependency_component_keys
    )
    task_closed = result.task_validity.terminal_verification_complete
    reference_path_match = all(
        selected_by_component.get(item.component_key, item.reference_choice_handle)
        == item.reference_choice_handle
        for item in components
    )
    values = {
        "package_id": package_id,
        "execution_result_id": result.result_id,
        "capability_family": family,
        "reference_path_match": reference_path_match,
        "component_semantic_checks": dict(sorted(checks.items())),
        "component_event_ids": {
            key: tuple(item.event_id for item in events_by_key[key])
            for key in sorted(events_by_key)
        },
        "dependency_order_passed": dependency_order,
        "task_closed": task_closed,
        "mechanism_semantically_qualified": (
            all(checks.values()) and dependency_order and task_closed
        ),
    }
    return cast(
        SemanticMechanismQualification,
        make_identity_model(
            SemanticMechanismQualification,
            values,
            field="report_id",
            prefix="semantic_mechanism_qualification_report:",
        ),
    )


def make_baseline_trace_binding(
    *,
    source: CausalSemanticExecutionResult,
    replay: CausalSemanticExecutionResult,
) -> BaselineTraceBinding:
    source_bytes = canonical_bytes(source.model_dump(mode="json"))
    replay_bytes = canonical_bytes(replay.model_dump(mode="json"))
    if source_bytes != replay_bytes:
        raise ValueError("baseline Runtime replay differs from the frozen source Result")
    event_ids = tuple(item.event_id for item in replay.events)
    values = {
        "package_id": replay.package_id,
        "source_result_id": source.result_id,
        "replay_result_id": replay.result_id,
        "chosen_choice_handles": replay.chosen_choice_handles,
        "event_ids": event_ids,
        "event_order_hash": canonical_hash(event_ids, prefix="baseline_event_order:"),
        "task_report_id": replay.task_validity.report_id,
        "mechanism_report_id": replay.mechanism_qualification.report_id,
        "qualified_report_id": replay.qualified_validity.report_id,
        "canonical_result_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_replay_bytes_match": True,
    }
    return cast(
        BaselineTraceBinding,
        make_identity_model(
            BaselineTraceBinding,
            values,
            field="binding_id",
            prefix="dynamic_baseline_trace_binding:",
        ),
    )
