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
    CausalTargetComponent,
    PresentedChoiceCandidate,
    StaticTaskValidityReport,
    ValiditySeparatedPublicTask,
    candidate_legality_findings,
    choice_operation,
)
from trusted_synthesis.hashing import canonical_hash

SEMANTIC_TABLE_TRACE_VERSION: Final = "semantic_table_trace_hardening.v1"
SEMANTIC_TABLE_PRESENTATION_SALT: Final = (
    "finance-v26.173-replica-local-semantic-table-presentation-v1"
)
DISPLAY_CHOICE_PATTERN: Final = r"^public_choice:[0-9a-f]{64}$"
VALUE_HANDLE_PATTERN: Final = r"^public_value:[0-9a-f]{64}$"
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


class ReplicaSemanticValue(FrozenModel):
    value_handle: str = Field(pattern=VALUE_HANDLE_PATTERN)
    semantic_value: Any
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION


class HardenedLegendEntry(FrozenModel):
    choice_handle: str = Field(pattern=DISPLAY_CHOICE_PATTERN)
    value_handles: tuple[str, ...] = Field(min_length=1)
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_entry(self) -> HardenedLegendEntry:
        if any(re.fullmatch(VALUE_HANDLE_PATTERN, item) is None for item in self.value_handles):
            raise ValueError("hardened Legend contains a malformed value handle")
        return self


class HardenedPublicObservation(FrozenModel):
    receipt_id: str = Field(min_length=1)
    state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    selected_choice_handle: str = Field(pattern=DISPLAY_CHOICE_PATTERN)
    selected_operation_hash: str = Field(min_length=1)
    predecessor_receipt_ids: tuple[str, ...]
    event_ids: tuple[str, ...] = Field(min_length=1)
    status: Literal["accepted", "failed", "typed"]
    action_accepted: bool
    rejection_code: str | None = None
    public_effects: dict[str, Any] = Field(min_length=1)
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> HardenedPublicObservation:
        if len(self.event_ids) != len(set(self.event_ids)):
            raise ValueError("hardened Observation repeats a Runtime event")
        if self.action_accepted == (self.rejection_code is not None):
            raise ValueError("hardened Observation acceptance and rejection code conflict")
        if scan_model_visible_leakage(self.model_dump(mode="json", exclude={"receipt_id"})):
            raise ValueError("hardened Observation exposes Host-only content")
        if self.receipt_id != _identity(
            self,
            "receipt_id",
            "hardened_public_observation_receipt:",
        ):
            raise ValueError("hardened Observation receipt identity is invalid")
        return self


class HardenedPublicState(FrozenModel):
    state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    decision_kind: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    facts: dict[str, Any] = Field(min_length=1)
    argument_fields: tuple[str, ...] = Field(min_length=1)
    argument_value_catalogs: dict[str, tuple[ReplicaSemanticValue, ...]] = Field(min_length=1)
    choice_legend: tuple[HardenedLegendEntry, ...] = Field(min_length=2, max_length=3)
    prior_observations: tuple[HardenedPublicObservation, ...] = ()
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> HardenedPublicState:
        if len(self.argument_fields) != len(set(self.argument_fields)):
            raise ValueError("hardened State repeats an argument field")
        if set(self.argument_fields) != set(self.argument_value_catalogs):
            raise ValueError("hardened State catalogs do not match argument fields")
        allowed_by_field: dict[str, set[str]] = {}
        for field, values in self.argument_value_catalogs.items():
            handles = tuple(item.value_handle for item in values)
            encoded = tuple(canonical_bytes(item.semantic_value) for item in values)
            if not values or len(handles) != len(set(handles)) or len(encoded) != len(set(encoded)):
                raise ValueError(f"hardened State value catalog is not one-to-one:{field}")
            allowed_by_field[field] = set(handles)
        choice_handles = tuple(item.choice_handle for item in self.choice_legend)
        if len(choice_handles) != len(set(choice_handles)):
            raise ValueError("hardened State repeats a display Choice handle")
        for entry in self.choice_legend:
            if len(entry.value_handles) != len(self.argument_fields):
                raise ValueError("hardened Legend row does not cover every semantic field")
            for field, handle in zip(self.argument_fields, entry.value_handles, strict=True):
                if handle not in allowed_by_field[field]:
                    raise ValueError("hardened Legend references an absent semantic value")
        row_lengths = {
            len(canonical_bytes(item.model_dump(mode="json"))) for item in self.choice_legend
        }
        if len(row_lengths) != 1:
            raise ValueError("hardened Legend rows are not structurally equal-width")
        receipt_ids = tuple(item.receipt_id for item in self.prior_observations)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("hardened State repeats a predecessor Observation")
        visible = self.model_dump(mode="json", exclude={"state_token"})
        if scan_model_visible_leakage(visible):
            raise ValueError("hardened State exposes Host-only content")
        expected = hashlib.sha256(canonical_bytes(visible)).hexdigest()[:24]
        if self.state_token != expected:
            raise ValueError("hardened State token is not content-derived")
        return self


class HardenedPublicPrompt(FrozenModel):
    prompt_hash: str = Field(min_length=64, max_length=64)
    rendered_bytes: int = Field(ge=1)
    task: ValiditySeparatedPublicTask
    state: HardenedPublicState
    candidates: tuple[PresentedChoiceCandidate, ...] = Field(min_length=2, max_length=3)
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_prompt(self) -> HardenedPublicPrompt:
        if tuple(item.presentation_index for item in self.candidates) != tuple(
            range(len(self.candidates))
        ):
            raise ValueError("hardened Prompt Candidate positions are not contiguous")
        if len({item.action_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("hardened Prompt repeats an action ID")
        if {item.choice_handle for item in self.candidates} != {
            item.choice_handle for item in self.state.choice_legend
        }:
            raise ValueError("hardened Prompt Candidate and Legend sets differ")
        candidate_lengths = {
            len(canonical_bytes(item.model_dump(mode="json"))) for item in self.candidates
        }
        if len(candidate_lengths) != 1:
            raise ValueError("hardened Prompt Candidate rows are not equal-width")
        payload = self.model_dump(
            mode="json",
            exclude={"prompt_hash", "rendered_bytes", "schema_version"},
        )
        rendered = canonical_bytes(payload)
        if self.prompt_hash != hashlib.sha256(rendered).hexdigest():
            raise ValueError("hardened Prompt hash is invalid")
        if self.rendered_bytes != len(rendered):
            raise ValueError("hardened Prompt byte count is invalid")
        if scan_model_visible_leakage(payload):
            raise ValueError("hardened Prompt exposes Host-only content")
        return self


class EncodedPublicOperation(FrozenModel):
    decision_kind: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    argument_value_handles: dict[str, str] = Field(min_length=1)
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_operation(self) -> EncodedPublicOperation:
        if any(
            re.fullmatch(VALUE_HANDLE_PATTERN, value) is None
            for value in self.argument_value_handles.values()
        ):
            raise ValueError("encoded Operation contains a malformed value handle")
        return self


class ActionAcceptanceReport(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    source_choice_handle: str = Field(min_length=1)
    selected_operation_hash: str = Field(min_length=1)
    publicly_grounded: bool
    publicly_executable: bool
    state_precondition_valid: bool
    mechanism_relevant: bool
    accepted: bool
    rejection_code: str | None = None
    findings: tuple[str, ...]
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ActionAcceptanceReport:
        expected = all(
            (
                self.publicly_grounded,
                self.publicly_executable,
                self.state_precondition_valid,
                self.mechanism_relevant,
            )
        )
        if self.accepted != expected:
            raise ValueError("Action acceptance is not the exact legality conjunction")
        if self.accepted == (self.rejection_code is not None):
            raise ValueError("Action acceptance rejection code is inconsistent")
        if self.report_id != _identity(
            self,
            "report_id",
            "state_bound_action_acceptance_report:",
        ):
            raise ValueError("Action acceptance identity is invalid")
        return self


class StateBoundMechanismQualification(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    execution_parent_hash: str = Field(min_length=1)
    capability_family: CapabilityFamily
    reference_path_match: bool
    component_semantic_checks: dict[str, bool] = Field(min_length=1)
    component_event_ids: dict[str, tuple[str, ...]] = Field(min_length=1)
    action_acceptance_report_ids: dict[str, str] = Field(min_length=1)
    all_state_preconditions_passed: bool
    recovery_rule_receipt_lineage_passed: bool
    dependency_order_passed: bool
    task_closed: bool
    mechanism_semantically_qualified: bool
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> StateBoundMechanismQualification:
        keys = set(self.component_semantic_checks)
        if keys != set(self.component_event_ids) or keys != set(self.action_acceptance_report_ids):
            raise ValueError("state-bound Mechanism report has inconsistent Component parents")
        expected = all(
            (
                all(self.component_semantic_checks.values()),
                self.all_state_preconditions_passed,
                self.recovery_rule_receipt_lineage_passed,
                self.dependency_order_passed,
                self.task_closed,
            )
        )
        if self.mechanism_semantically_qualified != expected:
            raise ValueError("state-bound Mechanism qualification is not parent-derived")
        if self.report_id != _identity(
            self,
            "report_id",
            "state_bound_semantic_mechanism_report:",
        ):
            raise ValueError("state-bound Mechanism report identity is invalid")
        return self


class StateBoundQualifiedValidity(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    task_report_id: str = Field(min_length=1)
    mechanism_report_id: str = Field(min_length=1)
    action_acceptance_report_ids: tuple[str, ...] = Field(min_length=1)
    base_valid: bool
    mechanism_semantically_qualified: bool
    all_state_preconditions_passed: bool
    qualified_valid: bool
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> StateBoundQualifiedValidity:
        expected = (
            self.base_valid
            and self.mechanism_semantically_qualified
            and self.all_state_preconditions_passed
        )
        if self.qualified_valid != expected:
            raise ValueError("state-bound Qualified validity is not the exact conjunction")
        if len(self.action_acceptance_report_ids) != len(set(self.action_acceptance_report_ids)):
            raise ValueError("state-bound Qualified report repeats Action acceptance")
        if self.report_id != _identity(
            self,
            "report_id",
            "state_bound_qualified_validity_report:",
        ):
            raise ValueError("state-bound Qualified report identity is invalid")
        return self


class HardenedStepRecord(FrozenModel):
    step_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    step_index: int = Field(ge=0, le=3)
    component_key: str = Field(min_length=1)
    dependency_component_keys: tuple[str, ...]
    source_choice_handle: str = Field(min_length=1)
    displayed_choice_handle: str = Field(pattern=DISPLAY_CHOICE_PATTERN)
    selected_action_id: str = Field(min_length=PUBLIC_ACTION_ID_LENGTH)
    prompt: HardenedPublicPrompt
    acceptance: ActionAcceptanceReport
    observation: HardenedPublicObservation
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_step(self) -> HardenedStepRecord:
        selected = tuple(
            item for item in self.prompt.candidates if item.action_id == self.selected_action_id
        )
        if len(selected) != 1 or selected[0].choice_handle != self.displayed_choice_handle:
            raise ValueError("hardened Step selected action is not in its current Prompt")
        operation = resolve_runtime_operation(self.prompt.state, self.displayed_choice_handle)
        operation_hash = canonical_hash(
            operation.model_dump(mode="json"),
            prefix="selected_runtime_operation:",
        )
        if (
            self.acceptance.package_id != self.package_id
            or self.acceptance.component_key != self.component_key
            or self.acceptance.source_choice_handle != self.source_choice_handle
            or self.acceptance.selected_operation_hash != operation_hash
            or self.observation.selected_operation_hash != operation_hash
            or self.observation.state_token != self.prompt.state.state_token
            or self.observation.selected_choice_handle != self.displayed_choice_handle
            or self.observation.action_accepted != self.acceptance.accepted
            or self.observation.rejection_code != self.acceptance.rejection_code
        ):
            raise ValueError("hardened Step semantic parents are inconsistent")
        if self.step_id != _identity(self, "step_id", "hardened_step_record:"):
            raise ValueError("hardened Step identity is invalid")
        return self


class StepRuntimeResult(FrozenModel):
    result_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    steps: tuple[HardenedStepRecord, ...] = Field(min_length=1, max_length=4)
    events: tuple[CausalRuntimeEvent, ...] = Field(min_length=1)
    selected_source_choice_handles: tuple[str, ...] = Field(min_length=1, max_length=4)
    reference_path_hash: str = Field(min_length=1)
    execution_parent_hash: str = Field(min_length=1)
    task_validity: StaticTaskValidityReport
    mechanism_qualification: StateBoundMechanismQualification
    qualified_validity: StateBoundQualifiedValidity
    projected_public_answer: dict[str, Any] | None
    public_citations: tuple[str, ...]
    task_program_executor_invocation_count: int = Field(ge=0)
    task_program_oracle_verifier_invocation_count: int = Field(ge=0, le=1)
    local_tool_invocation_count: int = Field(ge=0)
    postcompletion_call_count: int = Field(ge=0)
    complete_baseline_loaded: Literal[False] = False
    precommitted_choice_vector_allowed: Literal[False] = False
    future_prompt_access_allowed: Literal[False] = False
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> StepRuntimeResult:
        if tuple(item.step_index for item in self.steps) != tuple(range(len(self.steps))):
            raise ValueError("step Runtime result has noncontiguous Steps")
        if any(
            item.package_id != self.package_id or item.replica_index != self.replica_index
            for item in self.steps
        ):
            raise ValueError("step Runtime Result crosses a Package or Replica")
        receipt_by_key: dict[str, str] = {}
        for step in self.steps:
            expected = tuple(receipt_by_key[key] for key in step.dependency_component_keys)
            if step.observation.predecessor_receipt_ids != expected:
                raise ValueError("step Runtime Observation crosses predecessor receipts")
            if tuple(item.receipt_id for item in step.prompt.state.prior_observations) != expected:
                raise ValueError("step Runtime Prompt was not rendered from reached receipts")
            receipt_by_key[step.component_key] = step.observation.receipt_id
        event_ids = tuple(item.event_id for item in self.events)
        observed = tuple(event for step in self.steps for event in step.observation.event_ids)
        if any(item not in event_ids for item in observed):
            raise ValueError("step Runtime Observation references an absent event")
        expected_trace_hash = canonical_hash(
            event_ids,
            prefix="causal_public_runtime_trace:",
        )
        if self.task_validity.trace_hash != expected_trace_hash:
            raise ValueError("step Runtime task report crosses its exact event trace")
        expected_parent = execution_parent_hash(
            package_id=self.package_id,
            selected_source_choice_handles=self.selected_source_choice_handles,
            event_ids=event_ids,
            task_report_id=self.task_validity.report_id,
        )
        if self.execution_parent_hash != expected_parent:
            raise ValueError("step Runtime execution parent hash is invalid")
        acceptance_ids = tuple(item.acceptance.report_id for item in self.steps)
        mechanism = self.mechanism_qualification
        qualified = self.qualified_validity
        expected_component_events = {
            step.component_key: tuple(
                item.event_id for item in self.events if item.component_key == step.component_key
            )
            for step in self.steps
        }
        if (
            mechanism.package_id != self.package_id
            or mechanism.execution_parent_hash != self.execution_parent_hash
            or any(
                mechanism.action_acceptance_report_ids.get(step.component_key)
                != step.acceptance.report_id
                for step in self.steps
            )
            or mechanism.component_event_ids != expected_component_events
            or qualified.package_id != self.package_id
            or qualified.task_report_id != self.task_validity.report_id
            or qualified.mechanism_report_id != mechanism.report_id
            or qualified.action_acceptance_report_ids != acceptance_ids
            or qualified.base_valid != self.task_validity.base_valid
            or qualified.mechanism_semantically_qualified
            != mechanism.mechanism_semantically_qualified
        ):
            raise ValueError("step Runtime validity parents are inconsistent")
        if self.result_id != _identity(self, "result_id", "step_runtime_result:"):
            raise ValueError("step Runtime Result identity is invalid")
        return self


def _rotate(values: tuple[T, ...], shift: int) -> tuple[T, ...]:
    offset = shift % len(values)
    return values[offset:] + values[:offset]


def topological_components(
    components: Sequence[CausalTargetComponent],
) -> tuple[CausalTargetComponent, ...]:
    by_key = {item.component_key: item for item in components}
    if len(by_key) != len(components):
        raise ValueError("step Runtime Component graph repeats a key")
    if any(
        dependency not in by_key
        for item in components
        for dependency in item.dependency_component_keys
    ):
        raise ValueError("step Runtime Component graph has an absent dependency")
    remaining = set(by_key)
    emitted: set[str] = set()
    ordered: list[CausalTargetComponent] = []
    while remaining:
        ready = sorted(
            key for key in remaining if set(by_key[key].dependency_component_keys) <= emitted
        )
        if not ready:
            raise ValueError("step Runtime Component graph is cyclic")
        for key in ready:
            ordered.append(by_key[key])
            emitted.add(key)
            remaining.remove(key)
    return tuple(ordered)


def _opaque_pool(prefix: str, context: str, count: int) -> tuple[str, ...]:
    return tuple(
        sorted(
            prefix
            + hashlib.sha256(
                f"{SEMANTIC_TABLE_PRESENTATION_SALT}|{context}|pool|{index}".encode()
            ).hexdigest()
            for index in range(count)
        )
    )


def _candidate_position_shift(replica_index: int, choice_count: int) -> int:
    if choice_count == 3:
        return (2 * replica_index) % choice_count
    return (0, 0, 0, 1, 1, 1)[replica_index]


def make_hardened_prompt(
    *,
    package_id: str,
    task: ValiditySeparatedPublicTask,
    component: CausalTargetComponent,
    replica_index: int,
    predecessor_observations: Sequence[HardenedPublicObservation],
) -> tuple[HardenedPublicPrompt, dict[str, str]]:
    source_entries = tuple(component.public_state.choice_legend)
    operations = tuple(item.operation for item in source_entries)
    if len({item.decision_kind for item in operations}) != 1:
        raise ValueError("hardened Prompt crosses Decision kinds")
    if len({item.tool_id for item in operations}) != 1:
        raise ValueError("hardened Prompt crosses Tool schemas")
    canonical_fields = tuple(sorted(operations[0].arguments))
    if any(tuple(sorted(item.arguments)) != canonical_fields for item in operations):
        raise ValueError("hardened Prompt crosses an argument schema")
    unique_count_by_field = {
        field: len({canonical_bytes(item.arguments[field]) for item in operations})
        for field in canonical_fields
    }
    fields = tuple(
        sorted(
            canonical_fields,
            key=lambda field: (
                -unique_count_by_field[field],
                hashlib.sha256(
                    f"{SEMANTIC_TABLE_PRESENTATION_SALT}|{package_id}|"
                    f"{component.component_key}|field|{field}".encode()
                ).hexdigest(),
            ),
        )
    )
    catalogs: dict[str, tuple[ReplicaSemanticValue, ...]] = {}
    handle_by_value: dict[str, dict[bytes, str]] = {}
    reference_operation = choice_operation(
        component.public_state,
        component.reference_choice_handle,
    )
    for field in fields:
        unique = {
            canonical_bytes(item.arguments[field]): item.arguments[field] for item in operations
        }
        semantic_values = tuple(unique[key] for key in sorted(unique))
        pool = _opaque_pool(
            "public_value:",
            f"{package_id}|{component.component_key}|{replica_index}|{field}",
            len(semantic_values),
        )
        reference_key = canonical_bytes(reference_operation.arguments[field])
        reference_rank = (replica_index + fields.index(field)) % len(pool)
        remaining_ranks = tuple(index for index in range(len(pool)) if index != reference_rank)
        remaining_values = tuple(
            value for value in semantic_values if canonical_bytes(value) != reference_key
        )
        assignments = {reference_key: pool[reference_rank]}
        assignments.update(
            {
                canonical_bytes(value): pool[rank]
                for value, rank in zip(remaining_values, remaining_ranks, strict=True)
            }
        )
        handle_by_value[field] = assignments
        entries = tuple(
            ReplicaSemanticValue(
                value_handle=assignments[canonical_bytes(value)], semantic_value=value
            )
            for value in semantic_values
        )
        catalogs[field] = tuple(sorted(entries, key=lambda item: item.value_handle))
    choice_count = len(source_entries)
    display_pool = _opaque_pool(
        "public_choice:",
        f"{package_id}|{component.component_key}|{replica_index}|display",
        choice_count,
    )
    action_pool = tuple(
        item.removeprefix("public_action:")[:PUBLIC_ACTION_ID_LENGTH]
        for item in _opaque_pool(
            "public_action:",
            f"{package_id}|{component.component_key}|{replica_index}|action",
            choice_count,
        )
    )
    display_by_source = {
        index: display_pool[(index + replica_index) % choice_count] for index in range(choice_count)
    }
    action_shift = (2 * replica_index) % choice_count if choice_count == 3 else replica_index
    action_by_source = {
        index: action_pool[(index + action_shift) % choice_count] for index in range(choice_count)
    }
    entries_by_source = tuple(
        HardenedLegendEntry(
            choice_handle=display_by_source[index],
            value_handles=tuple(
                handle_by_value[field][canonical_bytes(operation.arguments[field])]
                for field in fields
            ),
        )
        for index, operation in enumerate(operations)
    )
    ordered_entries = _rotate(entries_by_source, replica_index)
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
        "schema_version": SEMANTIC_TABLE_TRACE_VERSION,
    }
    token_payload = {
        key: (
            [item.model_dump(mode="json") for item in value]
            if key in {"choice_legend", "prior_observations"}
            else {
                field: [item.model_dump(mode="json") for item in entries]
                for field, entries in value.items()
            }
            if key == "argument_value_catalogs"
            else value
        )
        for key, value in state_values.items()
    }
    state = HardenedPublicState(
        state_token=hashlib.sha256(canonical_bytes(token_payload)).hexdigest()[:24],
        **state_values,
    )
    source_order = _rotate(
        tuple(range(choice_count)),
        _candidate_position_shift(replica_index, choice_count),
    )
    candidates = tuple(
        PresentedChoiceCandidate(
            action_id=action_by_source[source_index],
            presentation_index=index,
            choice_handle=display_by_source[source_index],
        )
        for index, source_index in enumerate(source_order)
    )
    payload = {
        "task": task.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in candidates],
    }
    rendered = canonical_bytes(payload)
    prompt = HardenedPublicPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        task=task,
        state=state,
        candidates=candidates,
    )
    source_by_display = {
        display_by_source[index]: source_entries[index].choice_handle
        for index in range(choice_count)
    }
    return prompt, source_by_display


def resolve_encoded_operation(
    state: HardenedPublicState,
    choice_handle: str,
) -> EncodedPublicOperation:
    entry = next(
        (item for item in state.choice_legend if item.choice_handle == choice_handle), None
    )
    if entry is None:
        raise ValueError("hardened Choice is absent from current State")
    return EncodedPublicOperation(
        decision_kind=state.decision_kind,
        tool_id=state.tool_id,
        argument_value_handles=dict(zip(state.argument_fields, entry.value_handles, strict=True)),
    )


def resolve_runtime_operation(
    state: HardenedPublicState,
    choice_handle: str,
) -> PublicOperationPayload:
    encoded = resolve_encoded_operation(state, choice_handle)
    by_handle = {
        field: {item.value_handle: item.semantic_value for item in values}
        for field, values in state.argument_value_catalogs.items()
    }
    arguments = {
        field: by_handle[field][handle] for field, handle in encoded.argument_value_handles.items()
    }
    return PublicOperationPayload(
        decision_kind=state.decision_kind,
        tool_id=state.tool_id,
        arguments=arguments,
    )


def _desired_operation(prompt: HardenedPublicPrompt) -> dict[str, Any]:
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
    raise ValueError(f"unknown hardened Decision kind:{decision}")


def public_only_select_hardened_action(prompt: HardenedPublicPrompt) -> str:
    desired = _desired_operation(prompt)
    matches = tuple(
        item.action_id
        for item in prompt.candidates
        if resolve_runtime_operation(prompt.state, item.choice_handle).arguments == desired
    )
    if len(matches) != 1:
        raise ValueError("public-only hardened Selector did not identify one Choice")
    return matches[0]


def classify_action_acceptance(
    *,
    package_id: str,
    task: ValiditySeparatedPublicTask,
    component: CausalTargetComponent,
    source_choice_handle: str,
) -> ActionAcceptanceReport:
    operation = choice_operation(component.public_state, source_choice_handle)
    findings = list(candidate_legality_findings(task, component.public_state, operation))
    grounded = not any(item.endswith("_absent") for item in findings)
    executable = not findings
    facts = component.public_state.facts
    arguments = operation.arguments
    decision = operation.decision_kind
    precondition = executable
    if decision == "revise_selector":
        rules = {item.rule_handle: item for item in task.semantic_task.resolution_rules}
        current_rule = str(facts.get("rule_handle"))
        selected_rule = str(arguments.get("rule_handle"))
        rule = rules.get(current_rule)
        receipt = cast(Mapping[str, Any], facts.get("actual_failure_receipt") or {})
        precondition = bool(
            executable
            and rule is not None
            and selected_rule == current_rule
            and str(arguments.get("source_tool_id")) == rule.source_tool_id
            and str(receipt.get("rule_handle", current_rule)) == current_rule
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
    if executable and not precondition:
        findings.append("current_state_precondition_mismatch")
    rejection_code = None if relevant else "typed_current_state_target_mismatch"
    operation_hash = canonical_hash(
        operation.model_dump(mode="json"),
        prefix="selected_runtime_operation:",
    )
    values = {
        "package_id": package_id,
        "component_key": component.component_key,
        "source_choice_handle": source_choice_handle,
        "selected_operation_hash": operation_hash,
        "publicly_grounded": grounded,
        "publicly_executable": executable,
        "state_precondition_valid": precondition,
        "mechanism_relevant": relevant,
        "accepted": bool(grounded and executable and precondition and relevant),
        "rejection_code": rejection_code,
        "findings": tuple(sorted(set(findings))),
    }
    return cast(
        ActionAcceptanceReport,
        make_identity_model(
            ActionAcceptanceReport,
            values,
            field="report_id",
            prefix="state_bound_action_acceptance_report:",
        ),
    )


def make_hardened_observation(
    *,
    prompt: HardenedPublicPrompt,
    selected_choice_handle: str,
    predecessor_receipt_ids: Sequence[str],
    acceptance: ActionAcceptanceReport,
    events: Sequence[CausalRuntimeEvent],
) -> HardenedPublicObservation:
    if not events:
        raise ValueError("hardened Observation has no actual Runtime event")
    operation = resolve_runtime_operation(prompt.state, selected_choice_handle)
    status: Literal["accepted", "failed", "typed"] = (
        "typed"
        if not acceptance.accepted or any(item.status == "typed" for item in events)
        else "failed"
        if any(item.status == "failed" for item in events)
        else "accepted"
    )
    values = {
        "state_token": prompt.state.state_token,
        "selected_choice_handle": selected_choice_handle,
        "selected_operation_hash": acceptance.selected_operation_hash,
        "predecessor_receipt_ids": tuple(predecessor_receipt_ids),
        "event_ids": tuple(item.event_id for item in events),
        "status": status,
        "action_accepted": acceptance.accepted,
        "rejection_code": acceptance.rejection_code,
        "public_effects": {
            "selected_operation": operation.model_dump(mode="json"),
            "runtime_effects": [item.public_effects for item in events],
        },
    }
    return cast(
        HardenedPublicObservation,
        make_identity_model(
            HardenedPublicObservation,
            values,
            field="receipt_id",
            prefix="hardened_public_observation_receipt:",
        ),
    )


def execution_parent_hash(
    *,
    package_id: str,
    selected_source_choice_handles: Sequence[str],
    event_ids: Sequence[str],
    task_report_id: str,
) -> str:
    return canonical_hash(
        {
            "package_id": package_id,
            "selected_source_choice_handles": list(selected_source_choice_handles),
            "event_ids": list(event_ids),
            "task_report_id": task_report_id,
        },
        prefix="step_runtime_execution_parent:",
    )
