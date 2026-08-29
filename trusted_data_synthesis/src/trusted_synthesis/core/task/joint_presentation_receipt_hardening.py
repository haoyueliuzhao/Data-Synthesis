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

SEMANTIC_TABLE_TRACE_VERSION: Final = "joint_presentation_receipt_hardening.v1"
SEMANTIC_TABLE_PRESENTATION_SALT: Final = (
    "finance-v26.174-joint-neutral-presentation-and-receipt-v1"
)
DISPLAY_CHOICE_PATTERN: Final = r"^public_choice:[0-9a-f]{64}$"
VALUE_HANDLE_PATTERN: Final = r"^public_value:[0-9a-f]{64}$"
T = TypeVar("T")

THREE_CHOICE_RANK_SCHEDULES: Final = {
    "candidate": ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)),
    "action": ((2, 1, 0), (1, 2, 0), (1, 0, 2), (0, 2, 1), (2, 0, 1), (0, 1, 2)),
    "legend": ((2, 1, 0), (2, 0, 1), (1, 0, 2), (0, 1, 2), (1, 2, 0), (0, 2, 1)),
    "display": ((2, 0, 1), (0, 2, 1), (1, 0, 2), (2, 1, 0), (1, 2, 0), (0, 1, 2)),
    "value0": ((2, 0, 1), (0, 2, 1), (1, 0, 2), (2, 1, 0), (1, 2, 0), (0, 1, 2)),
    "value1": ((0, 2, 1), (2, 0, 1), (1, 0, 2), (1, 2, 0), (2, 1, 0), (0, 1, 2)),
    "value2": ((0, 2, 1), (2, 0, 1), (0, 1, 2), (2, 1, 0), (1, 2, 0), (1, 0, 2)),
    "value3": ((1, 2, 0), (2, 0, 1), (0, 2, 1), (2, 1, 0), (1, 0, 2), (0, 1, 2)),
}

TWO_CHOICE_RANK_SCHEDULES: Final = {
    "candidate": ((0, 1), (0, 1), (0, 1), (1, 0), (1, 0), (1, 0)),
    "action": ((1, 0), (1, 0), (1, 0), (0, 1), (0, 1), (0, 1)),
    "legend": ((1, 0), (0, 1), (1, 0), (1, 0), (0, 1), (0, 1)),
    "display": ((0, 1), (1, 0), (1, 0), (0, 1), (0, 1), (1, 0)),
    "value0": ((1, 0), (1, 0), (1, 0), (0, 1), (0, 1), (0, 1)),
    "value1": ((1, 0), (1, 0), (0, 1), (1, 0), (0, 1), (0, 1)),
    "value2": ((1, 0), (0, 1), (1, 0), (0, 1), (1, 0), (0, 1)),
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


class ReplicaSemanticValue(FrozenModel):
    value_handle: str = Field(pattern=VALUE_HANDLE_PATTERN)
    semantic_value: Any
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION


class ExactFailureReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    rule_handle: str = Field(min_length=1)
    failed_selector_hash: str = Field(min_length=1)
    error_code: Literal["typed_selector_requires_refinement"]
    source_tool_id: str = Field(min_length=1)
    failure_event_id: str = Field(min_length=1)
    status: Literal["failed"] = "failed"
    schema_version: str = SEMANTIC_TABLE_TRACE_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> ExactFailureReceipt:
        if self.receipt_id != _identity(
            self,
            "receipt_id",
            "exact_public_failure_receipt:",
        ):
            raise ValueError("exact Failure Receipt identity is invalid")
        return self


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
    failure_receipt: ExactFailureReceipt | None = None
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
            if not values or len(handles) != len(set(handles)):
                raise ValueError(f"hardened State value aliases are not handle-unique:{field}")
            if len(values) != len(self.choice_legend):
                raise ValueError(f"hardened State value aliases do not cover every Choice:{field}")
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
        if self.decision_kind == "revise_selector":
            if self.failure_receipt is None:
                raise ValueError("Recovery State is missing its exact Failure Receipt")
            expected_selector_hash = canonical_hash(
                self.facts.get("failed_selector"),
                prefix="state_bound_failed_selector:",
            )
            if (
                self.failure_receipt.rule_handle != str(self.facts.get("rule_handle"))
                or self.failure_receipt.failed_selector_hash != expected_selector_hash
            ):
                raise ValueError("Recovery State crosses its Rule or failed selector Receipt")
        elif self.failure_receipt is not None:
            raise ValueError("non-Recovery State contains a Failure Receipt")
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
    failure_receipt_required: bool
    failure_receipt_id: str | None = None
    failure_receipt_binding_valid: bool
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
                self.failure_receipt_binding_valid,
            )
        )
        if not self.failure_receipt_required and self.failure_receipt_id is not None:
            raise ValueError("non-Recovery Action acceptance contains a Failure Receipt")
        if self.accepted and self.failure_receipt_required and self.failure_receipt_id is None:
            raise ValueError("accepted Recovery Action is missing its Failure Receipt")
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
    exact_failure_receipt_ids: dict[str, str]
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
        receipt_keys = set(self.exact_failure_receipt_ids)
        if self.capability_family == CapabilityFamily.FAILURE_RECOVERY:
            if receipt_keys != keys:
                raise ValueError("Recovery Mechanism report does not bind every exact Receipt")
        elif receipt_keys:
            raise ValueError("non-Recovery Mechanism report contains Failure Receipts")
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
    exact_failure_receipt_ids: tuple[str, ...]
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
        if len(self.exact_failure_receipt_ids) != len(set(self.exact_failure_receipt_ids)):
            raise ValueError("state-bound Qualified report repeats a Failure Receipt")
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
    failure_receipt_id: str | None = None
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
        prompt_receipt_id = (
            self.prompt.state.failure_receipt.receipt_id
            if self.prompt.state.failure_receipt is not None
            else None
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
            or self.failure_receipt_id != prompt_receipt_id
            or self.acceptance.failure_receipt_id != prompt_receipt_id
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
        expected_receipts = {
            step.component_key: step.failure_receipt_id
            for step in self.steps
            if step.failure_receipt_id is not None
        }
        expected_receipt_order = tuple(
            step.failure_receipt_id for step in self.steps if step.failure_receipt_id is not None
        )
        for step in self.steps:
            receipt = step.prompt.state.failure_receipt
            if receipt is None:
                continue
            failure_events = tuple(
                item for item in self.events if item.event_id == receipt.failure_event_id
            )
            if (
                len(failure_events) != 1
                or failure_events[0].component_key != step.component_key
                or failure_events[0].event_type != "typed_failure_observed"
                or failure_events[0].error_code != receipt.error_code
                or failure_events[0].tool_id != receipt.source_tool_id
            ):
                raise ValueError("step Runtime Result crosses its exact Failure event")
        if (
            mechanism.package_id != self.package_id
            or mechanism.execution_parent_hash != self.execution_parent_hash
            or any(
                mechanism.action_acceptance_report_ids.get(step.component_key)
                != step.acceptance.report_id
                for step in self.steps
            )
            or mechanism.component_event_ids != expected_component_events
            or mechanism.exact_failure_receipt_ids != expected_receipts
            or qualified.package_id != self.package_id
            or qualified.task_report_id != self.task_validity.report_id
            or qualified.mechanism_report_id != mechanism.report_id
            or qualified.action_acceptance_report_ids != acceptance_ids
            or qualified.exact_failure_receipt_ids != expected_receipt_order
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


def _rank_schedule(
    *,
    choice_count: int,
    channel: str,
    replica_index: int,
) -> tuple[int, ...]:
    schedules = THREE_CHOICE_RANK_SCHEDULES if choice_count == 3 else TWO_CHOICE_RANK_SCHEDULES
    try:
        return schedules[channel][replica_index]
    except KeyError as exc:
        raise ValueError(f"joint presentation channel is not registered:{channel}") from exc


def _rank_by_source(
    *,
    normalized_source_indices: tuple[int, ...],
    choice_count: int,
    channel: str,
    replica_index: int,
) -> dict[int, int]:
    schedule = _rank_schedule(
        choice_count=choice_count,
        channel=channel,
        replica_index=replica_index,
    )
    return {
        source_index: schedule[normalized_index]
        for normalized_index, source_index in enumerate(normalized_source_indices)
    }


def make_hardened_prompt(
    *,
    package_id: str,
    task: ValiditySeparatedPublicTask,
    component: CausalTargetComponent,
    replica_index: int,
    predecessor_observations: Sequence[HardenedPublicObservation],
    failure_receipt: ExactFailureReceipt | None,
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
    choice_count = len(source_entries)
    reference_index = next(
        index
        for index, item in enumerate(source_entries)
        if item.choice_handle == component.reference_choice_handle
    )
    other_indices = tuple(
        sorted(
            (index for index in range(choice_count) if index != reference_index),
            key=lambda index: canonical_bytes(operations[index].model_dump(mode="json")),
        )
    )
    normalized_source_indices = (reference_index, *other_indices)
    catalogs: dict[str, tuple[ReplicaSemanticValue, ...]] = {}
    value_handle_by_source: dict[str, dict[int, str]] = {}
    for field_index, field in enumerate(fields):
        channel = f"value{field_index}"
        rank_by_source = _rank_by_source(
            normalized_source_indices=normalized_source_indices,
            choice_count=choice_count,
            channel=channel,
            replica_index=replica_index,
        )
        pool = _opaque_pool(
            "public_value:",
            f"{package_id}|{component.component_key}|{replica_index}|{channel}|{field}",
            choice_count,
        )
        assignments = {
            source_index: pool[rank_by_source[source_index]] for source_index in range(choice_count)
        }
        value_handle_by_source[field] = assignments
        entries = tuple(
            ReplicaSemanticValue(
                value_handle=assignments[source_index],
                semantic_value=operations[source_index].arguments[field],
            )
            for source_index in range(choice_count)
        )
        catalogs[field] = tuple(sorted(entries, key=lambda item: item.value_handle))
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
    display_rank = _rank_by_source(
        normalized_source_indices=normalized_source_indices,
        choice_count=choice_count,
        channel="display",
        replica_index=replica_index,
    )
    action_rank = _rank_by_source(
        normalized_source_indices=normalized_source_indices,
        choice_count=choice_count,
        channel="action",
        replica_index=replica_index,
    )
    legend_rank = _rank_by_source(
        normalized_source_indices=normalized_source_indices,
        choice_count=choice_count,
        channel="legend",
        replica_index=replica_index,
    )
    candidate_rank = _rank_by_source(
        normalized_source_indices=normalized_source_indices,
        choice_count=choice_count,
        channel="candidate",
        replica_index=replica_index,
    )
    display_by_source = {index: display_pool[display_rank[index]] for index in range(choice_count)}
    action_by_source = {index: action_pool[action_rank[index]] for index in range(choice_count)}
    entries_by_source = tuple(
        HardenedLegendEntry(
            choice_handle=display_by_source[index],
            value_handles=tuple(value_handle_by_source[field][index] for field in fields),
        )
        for index in range(choice_count)
    )
    ordered_entries = tuple(
        entries_by_source[index]
        for index in sorted(range(choice_count), key=legend_rank.__getitem__)
    )
    state_values = {
        "decision_kind": component.public_state.decision_kind,
        "tool_id": operations[0].tool_id,
        "facts": {
            key: value
            for key, value in component.public_state.facts.items()
            if key not in {"dependency_component_keys", "actual_failure_receipt"}
        },
        "argument_fields": fields,
        "argument_value_catalogs": catalogs,
        "choice_legend": ordered_entries,
        "prior_observations": tuple(predecessor_observations),
        "failure_receipt": failure_receipt,
        "schema_version": SEMANTIC_TABLE_TRACE_VERSION,
    }
    provisional = HardenedPublicState.model_construct(state_token="0" * 24, **state_values)
    token_payload = provisional.model_dump(mode="json", exclude={"state_token"})
    state = HardenedPublicState(
        state_token=hashlib.sha256(canonical_bytes(token_payload)).hexdigest()[:24],
        **state_values,
    )
    source_order = tuple(sorted(range(choice_count), key=candidate_rank.__getitem__))
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
    visible_failure_receipt: ExactFailureReceipt | None,
    expected_failure_receipt: ExactFailureReceipt | None,
) -> ActionAcceptanceReport:
    operation = choice_operation(component.public_state, source_choice_handle)
    findings = list(candidate_legality_findings(task, component.public_state, operation))
    grounded = not any(item.endswith("_absent") for item in findings)
    executable = not findings
    facts = component.public_state.facts
    arguments = operation.arguments
    decision = operation.decision_kind
    precondition = executable
    receipt_required = decision == "revise_selector"
    receipt_binding = not receipt_required
    if decision == "revise_selector":
        rules = {item.rule_handle: item for item in task.semantic_task.resolution_rules}
        current_rule = str(facts.get("rule_handle"))
        selected_rule = str(arguments.get("rule_handle"))
        rule = rules.get(current_rule)
        expected_selector_hash = canonical_hash(
            facts.get("failed_selector"),
            prefix="state_bound_failed_selector:",
        )
        receipt_binding = bool(
            visible_failure_receipt is not None
            and expected_failure_receipt is not None
            and visible_failure_receipt == expected_failure_receipt
            and visible_failure_receipt.rule_handle == current_rule
            and visible_failure_receipt.failed_selector_hash == expected_selector_hash
            and visible_failure_receipt.error_code == "typed_selector_requires_refinement"
            and rule is not None
            and visible_failure_receipt.source_tool_id == rule.source_tool_id
        )
        precondition = bool(
            executable
            and receipt_binding
            and rule is not None
            and selected_rule == current_rule
            and str(arguments.get("source_tool_id")) == rule.source_tool_id
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
    if receipt_required and not receipt_binding:
        findings.append("exact_failure_receipt_mismatch")
    if executable and not precondition:
        findings.append("current_state_precondition_mismatch")
    rejection_code = (
        None
        if relevant
        else "typed_failure_receipt_mismatch"
        if receipt_required and not receipt_binding
        else "typed_current_state_target_mismatch"
    )
    operation_hash = canonical_hash(
        operation.model_dump(mode="json"),
        prefix="selected_runtime_operation:",
    )
    values = {
        "package_id": package_id,
        "component_key": component.component_key,
        "source_choice_handle": source_choice_handle,
        "selected_operation_hash": operation_hash,
        "failure_receipt_required": receipt_required,
        "failure_receipt_id": (
            visible_failure_receipt.receipt_id if visible_failure_receipt is not None else None
        ),
        "failure_receipt_binding_valid": receipt_binding,
        "publicly_grounded": grounded,
        "publicly_executable": executable,
        "state_precondition_valid": precondition,
        "mechanism_relevant": relevant,
        "accepted": bool(grounded and executable and precondition and relevant and receipt_binding),
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
            "failure_receipt_id": acceptance.failure_receipt_id,
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
