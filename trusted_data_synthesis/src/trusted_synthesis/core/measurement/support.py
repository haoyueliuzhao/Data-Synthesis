from __future__ import annotations

from collections.abc import Callable
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

MEASUREMENT_SUPPORT_POLICY_VERSION: Final = "prospective_measurement_support_boundary.v1"
BASELINE_ACTION_SET_POLICY_VERSION: Final = "prospective_public_baseline_action_set.v1"

SupportStatus = Literal["available", "not_required", "unavailable"]
SupportEventKind = Literal[
    "public_observation",
    "terminal_verification",
    "final_commit",
    "non_public_commit",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class BaselineActionSetResolution(FrozenModel):
    resolution_id: str = Field(min_length=1)
    status: Literal["available", "unavailable"]
    public_state_id: str = Field(min_length=1)
    progress_vector_id: str = Field(min_length=1)
    baseline_action_ids: tuple[str, ...]
    reason_code: str | None
    policy_version: Literal["prospective_public_baseline_action_set.v1"] = (
        BASELINE_ACTION_SET_POLICY_VERSION
    )
    current_public_state_only: Literal[True] = True
    candidate_authority_preserved: Literal[True] = True
    model_action_selected_or_repaired: Literal[False] = False
    exposed_to_model_prompt: Literal[False] = False

    @model_validator(mode="after")
    def validate_resolution(self) -> BaselineActionSetResolution:
        if self.baseline_action_ids != tuple(sorted(set(self.baseline_action_ids))):
            raise ValueError("baseline action IDs must be canonical and unique")
        if self.status == "available":
            if not self.baseline_action_ids or self.reason_code is not None:
                raise ValueError("available baseline resolution is malformed")
        elif self.baseline_action_ids or not self.reason_code:
            raise ValueError("unavailable baseline resolution is malformed")
        if self.resolution_id != _identity(
            self,
            "resolution_id",
            "prospective_baseline_action_set_resolution:",
        ):
            raise ValueError("baseline action-set resolution identity changed")
        return self


class MeasurementSupportEvent(FrozenModel):
    event_id: str = Field(min_length=1)
    event_kind: SupportEventKind
    public_state_id_before: str = Field(min_length=1)
    public_state_id_after: str = Field(min_length=1)
    progress_vector_id_before: str = Field(min_length=1)
    progress_vector_id_after: str = Field(min_length=1)
    selected_action_id: str | None
    observation_status: Literal["succeeded", "failed"] | None
    progress_vector_changed: bool
    successor_public_state_available: bool
    policy_version: Literal["prospective_measurement_support_boundary.v1"] = (
        MEASUREMENT_SUPPORT_POLICY_VERSION
    )

    @model_validator(mode="after")
    def validate_event(self) -> MeasurementSupportEvent:
        if self.event_kind == "public_observation":
            if self.selected_action_id is None or self.observation_status is None:
                raise ValueError("public Observation support event is incomplete")
        elif self.observation_status is not None:
            raise ValueError("non-Observation support event carries an Observation status")
        if not self.successor_public_state_available and (
            self.event_kind != "public_observation" or self.progress_vector_changed
        ):
            raise ValueError("unavailable successor event is malformed")
        if self.progress_vector_changed != (
            self.progress_vector_id_before != self.progress_vector_id_after
        ):
            raise ValueError("support event progress-vector binding changed")
        if self.event_id != _identity(
            self,
            "event_id",
            "prospective_measurement_support_event:",
        ):
            raise ValueError("measurement-support event identity changed")
        return self


class MeasurementSupportDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    status: SupportStatus
    public_state_id: str = Field(min_length=1)
    progress_vector_id: str = Field(min_length=1)
    selected_action_id: str | None
    baseline_action_ids: tuple[str, ...]
    baseline_resolution_id: str | None
    baseline_classifier_invoked: bool
    ordinary_detour_observed: bool
    reason_code: str | None
    policy_version: Literal["prospective_measurement_support_boundary.v1"] = (
        MEASUREMENT_SUPPORT_POLICY_VERSION
    )
    model_action_selected_or_repaired: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_decision(self) -> MeasurementSupportDecision:
        if self.baseline_action_ids != tuple(sorted(set(self.baseline_action_ids))):
            raise ValueError("support decision baseline IDs are not canonical")
        if self.status == "available":
            if (
                not self.baseline_classifier_invoked
                or not self.baseline_action_ids
                or self.baseline_resolution_id is None
                or self.reason_code is not None
                or self.selected_action_id is None
                or self.ordinary_detour_observed
                != (self.selected_action_id not in self.baseline_action_ids)
            ):
                raise ValueError("available support decision is malformed")
        elif self.status == "not_required":
            if (
                self.baseline_classifier_invoked
                or self.baseline_action_ids
                or self.baseline_resolution_id is not None
                or not self.reason_code
                or self.ordinary_detour_observed
            ):
                raise ValueError("not-required support decision is malformed")
        elif self.baseline_action_ids or not self.reason_code or self.ordinary_detour_observed:
            raise ValueError("unavailable support decision is malformed")
        elif self.baseline_classifier_invoked:
            if self.baseline_resolution_id is None:
                raise ValueError("baseline-unavailable decision omits its resolution")
        elif self.baseline_resolution_id is not None or self.reason_code not in {
            "public_replan_state_unavailable_after_failed_observation",
            "public_replan_state_unavailable_after_succeeded_observation",
        }:
            raise ValueError("successor-unavailable decision is malformed")
        if self.decision_id != _identity(
            self,
            "decision_id",
            "prospective_measurement_support_decision:",
        ):
            raise ValueError("measurement-support decision identity changed")
        return self


class MeasurementSupportContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    policy_version: Literal["prospective_measurement_support_boundary.v1"] = (
        MEASUREMENT_SUPPORT_POLICY_VERSION
    )
    baseline_policy_version: Literal["prospective_public_baseline_action_set.v1"] = (
        BASELINE_ACTION_SET_POLICY_VERSION
    )
    maximum_ordinary_detours: Literal[1] = 1
    failed_observation_requires_baseline: Literal[False] = False
    progress_observation_requires_baseline: Literal[False] = False
    successful_no_progress_requires_baseline: Literal[True] = True
    baseline_uses_current_public_state_only: Literal[True] = True
    baseline_is_not_model_visible: Literal[True] = True
    baseline_may_not_select_replace_or_repair_model_action: Literal[True] = True
    unavailable_is_measurement_support_exit: Literal[True] = True
    unselectable_public_successor_is_typed_support_exit: Literal[True] = True
    unavailable_is_model_invalid: Literal[False] = False
    unavailable_is_instrument_failure: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["prospective_measurement_support_contract.v1"] = (
        "prospective_measurement_support_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> MeasurementSupportContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "prospective_measurement_support_contract:",
        ):
            raise ValueError("measurement-support contract identity changed")
        return self


def make_baseline_resolution(
    *,
    status: Literal["available", "unavailable"],
    public_state_id: str,
    progress_vector_id: str,
    baseline_action_ids: tuple[str, ...] = (),
    reason_code: str | None = None,
) -> BaselineActionSetResolution:
    values = {
        "status": status,
        "public_state_id": public_state_id,
        "progress_vector_id": progress_vector_id,
        "baseline_action_ids": tuple(sorted(set(baseline_action_ids))),
        "reason_code": reason_code,
    }
    provisional = BaselineActionSetResolution.model_construct(
        resolution_id="pending",
        **values,
    )
    return BaselineActionSetResolution(
        resolution_id=_identity(
            provisional,
            "resolution_id",
            "prospective_baseline_action_set_resolution:",
        ),
        **values,
    )


def make_measurement_support_event(
    *,
    event_kind: SupportEventKind,
    public_state_id_before: str,
    public_state_id_after: str,
    progress_vector_id_before: str,
    progress_vector_id_after: str,
    selected_action_id: str | None,
    observation_status: Literal["succeeded", "failed"] | None,
    successor_public_state_available: bool = True,
) -> MeasurementSupportEvent:
    values = {
        "event_kind": event_kind,
        "public_state_id_before": public_state_id_before,
        "public_state_id_after": public_state_id_after,
        "progress_vector_id_before": progress_vector_id_before,
        "progress_vector_id_after": progress_vector_id_after,
        "selected_action_id": selected_action_id,
        "observation_status": observation_status,
        "progress_vector_changed": progress_vector_id_before != progress_vector_id_after,
        "successor_public_state_available": successor_public_state_available,
    }
    provisional = MeasurementSupportEvent.model_construct(event_id="pending", **values)
    return MeasurementSupportEvent(
        event_id=_identity(
            provisional,
            "event_id",
            "prospective_measurement_support_event:",
        ),
        **values,
    )


def _decision(
    *,
    event: MeasurementSupportEvent,
    status: SupportStatus,
    baseline_action_ids: tuple[str, ...] = (),
    baseline_resolution_id: str | None = None,
    baseline_classifier_invoked: bool,
    ordinary_detour_observed: bool = False,
    reason_code: str | None,
) -> MeasurementSupportDecision:
    values = {
        "event_id": event.event_id,
        "status": status,
        "public_state_id": event.public_state_id_before,
        "progress_vector_id": event.progress_vector_id_before,
        "selected_action_id": event.selected_action_id,
        "baseline_action_ids": tuple(sorted(set(baseline_action_ids))),
        "baseline_resolution_id": baseline_resolution_id,
        "baseline_classifier_invoked": baseline_classifier_invoked,
        "ordinary_detour_observed": ordinary_detour_observed,
        "reason_code": reason_code,
    }
    provisional = MeasurementSupportDecision.model_construct(decision_id="pending", **values)
    return MeasurementSupportDecision(
        decision_id=_identity(
            provisional,
            "decision_id",
            "prospective_measurement_support_decision:",
        ),
        **values,
    )


def classify_measurement_support(
    event: MeasurementSupportEvent,
    *,
    baseline_resolver: Callable[[], BaselineActionSetResolution],
) -> MeasurementSupportDecision:
    """Classify support after public behavior; resolve a baseline only when needed."""

    if not event.successor_public_state_available:
        return _decision(
            event=event,
            status="unavailable",
            baseline_classifier_invoked=False,
            reason_code=(
                f"public_replan_state_unavailable_after_{event.observation_status}_observation"
            ),
        )
    if event.event_kind == "terminal_verification":
        return _decision(
            event=event,
            status="not_required",
            baseline_classifier_invoked=False,
            reason_code="terminal_verification",
        )
    if event.event_kind == "final_commit":
        return _decision(
            event=event,
            status="not_required",
            baseline_classifier_invoked=False,
            reason_code="final_commit",
        )
    if event.event_kind == "non_public_commit":
        return _decision(
            event=event,
            status="not_required",
            baseline_classifier_invoked=False,
            reason_code="non_public_commit",
        )
    if event.observation_status == "failed":
        return _decision(
            event=event,
            status="not_required",
            baseline_classifier_invoked=False,
            reason_code="failed_observation",
        )
    if event.progress_vector_changed:
        return _decision(
            event=event,
            status="not_required",
            baseline_classifier_invoked=False,
            reason_code="public_progress",
        )
    try:
        resolution = baseline_resolver()
    except Exception:  # The public boundary must terminate as typed support evidence.
        resolution = make_baseline_resolution(
            status="unavailable",
            public_state_id=event.public_state_id_before,
            progress_vector_id=event.progress_vector_id_before,
            reason_code="baseline_classifier_exception",
        )
    if (
        resolution.public_state_id != event.public_state_id_before
        or resolution.progress_vector_id != event.progress_vector_id_before
    ):
        resolution = make_baseline_resolution(
            status="unavailable",
            public_state_id=event.public_state_id_before,
            progress_vector_id=event.progress_vector_id_before,
            reason_code="baseline_resolution_binding_mismatch",
        )
    if resolution.status == "unavailable":
        return _decision(
            event=event,
            status="unavailable",
            baseline_resolution_id=resolution.resolution_id,
            baseline_classifier_invoked=True,
            reason_code=resolution.reason_code,
        )
    selected = event.selected_action_id
    if selected is None:
        return _decision(
            event=event,
            status="unavailable",
            baseline_resolution_id=resolution.resolution_id,
            baseline_classifier_invoked=True,
            reason_code="selected_action_missing_at_baseline_boundary",
        )
    return _decision(
        event=event,
        status="available",
        baseline_action_ids=resolution.baseline_action_ids,
        baseline_resolution_id=resolution.resolution_id,
        baseline_classifier_invoked=True,
        ordinary_detour_observed=selected not in resolution.baseline_action_ids,
        reason_code=None,
    )


def make_measurement_support_contract() -> MeasurementSupportContract:
    provisional = MeasurementSupportContract.model_construct(contract_id="pending")
    return MeasurementSupportContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "prospective_measurement_support_contract:",
        )
    )
