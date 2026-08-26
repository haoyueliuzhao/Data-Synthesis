from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.measurement.support import (
    BaselineActionSetResolution,
    MeasurementSupportEvent,
)

SupportStatusV2 = Literal["available", "not_required", "unavailable"]


class BaselineResolutionContractError(RuntimeError):
    """Raised when a baseline resolver violates the typed Instrument contract."""


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class MeasurementSupportDecisionV2(FrozenModel):
    decision_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    status: SupportStatusV2
    public_state_id: str = Field(min_length=1)
    progress_vector_id: str = Field(min_length=1)
    selected_action_id: str | None
    baseline_action_ids: tuple[str, ...]
    baseline_resolution_id: str | None
    baseline_classifier_invoked: bool
    ordinary_detour_observed: bool
    reason_code: str | None
    undeclared_exception_converted_to_support_exit: Literal[False] = False
    binding_mismatch_converted_to_support_exit: Literal[False] = False
    model_action_selected_or_repaired: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: str = "prospective_measurement_support_decision.v2"

    @model_validator(mode="after")
    def validate_decision(self) -> MeasurementSupportDecisionV2:
        if self.baseline_action_ids != tuple(sorted(set(self.baseline_action_ids))):
            raise ValueError("v2 support decision baseline IDs are not canonical")
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
                raise ValueError("available v2 support decision is malformed")
        elif self.status == "not_required":
            if (
                self.baseline_classifier_invoked
                or self.baseline_action_ids
                or self.baseline_resolution_id is not None
                or not self.reason_code
                or self.ordinary_detour_observed
            ):
                raise ValueError("not-required v2 support decision is malformed")
        elif (
            not self.baseline_classifier_invoked
            or self.baseline_action_ids
            or self.baseline_resolution_id is None
            or not self.reason_code
            or self.ordinary_detour_observed
        ):
            raise ValueError("unavailable v2 support decision is malformed")
        if self.decision_id != _identity(
            self,
            "decision_id",
            "prospective_measurement_support_decision_v2:",
        ):
            raise ValueError("v2 measurement-support decision identity changed")
        return self


class MeasurementSupportContractV2(FrozenModel):
    contract_id: str = Field(min_length=1)
    policy_version: Literal["prospective_measurement_support_boundary.v2"] = (
        "prospective_measurement_support_boundary.v2"
    )
    baseline_policy_version: Literal["prospective_public_baseline_action_set.v1"] = (
        "prospective_public_baseline_action_set.v1"
    )
    expected_unavailability_requires_typed_resolution: Literal[True] = True
    undeclared_exception_is_instrument_failure: Literal[True] = True
    resolution_binding_mismatch_is_contract_failure: Literal[True] = True
    unavailable_is_measurement_support_exit: Literal[True] = True
    unavailable_is_instrument_failure: Literal[False] = False
    model_action_selected_or_repaired: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: str = "prospective_measurement_support_contract.v2"

    @model_validator(mode="after")
    def validate_contract(self) -> MeasurementSupportContractV2:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "prospective_measurement_support_contract_v2:",
        ):
            raise ValueError("v2 measurement-support Contract identity changed")
        return self


def _decision(
    *,
    event: MeasurementSupportEvent,
    status: SupportStatusV2,
    baseline_action_ids: tuple[str, ...] = (),
    baseline_resolution_id: str | None = None,
    baseline_classifier_invoked: bool,
    ordinary_detour_observed: bool = False,
    reason_code: str | None,
) -> MeasurementSupportDecisionV2:
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
    provisional = MeasurementSupportDecisionV2.model_construct(decision_id="pending", **values)
    return MeasurementSupportDecisionV2(
        decision_id=_identity(
            provisional,
            "decision_id",
            "prospective_measurement_support_decision_v2:",
        ),
        **values,
    )


def classify_measurement_support_v2(
    event: MeasurementSupportEvent,
    *,
    baseline_resolver: Callable[[], BaselineActionSetResolution],
) -> MeasurementSupportDecisionV2:
    """Classify expected support boundaries without swallowing Instrument defects."""

    if not event.successor_public_state_available:
        resolution = baseline_resolver()
        if not isinstance(resolution, BaselineActionSetResolution):
            raise TypeError("baseline resolver returned an untyped value")
        if (
            resolution.public_state_id != event.public_state_id_before
            or resolution.progress_vector_id != event.progress_vector_id_before
            or resolution.status != "unavailable"
        ):
            raise BaselineResolutionContractError(
                "unavailable successor lacks an exactly bound typed resolution"
            )
        return _decision(
            event=event,
            status="unavailable",
            baseline_resolution_id=resolution.resolution_id,
            baseline_classifier_invoked=True,
            reason_code=resolution.reason_code,
        )
    not_required_reason = {
        "terminal_verification": "terminal_verification",
        "final_commit": "final_commit",
        "non_public_commit": "non_public_commit",
    }.get(event.event_kind)
    if not_required_reason is not None:
        return _decision(
            event=event,
            status="not_required",
            baseline_classifier_invoked=False,
            reason_code=not_required_reason,
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

    resolution = baseline_resolver()
    if not isinstance(resolution, BaselineActionSetResolution):
        raise TypeError("baseline resolver returned an untyped value")
    if (
        resolution.public_state_id != event.public_state_id_before
        or resolution.progress_vector_id != event.progress_vector_id_before
    ):
        raise BaselineResolutionContractError("baseline resolution crossed its state binding")
    if resolution.status == "unavailable":
        return _decision(
            event=event,
            status="unavailable",
            baseline_resolution_id=resolution.resolution_id,
            baseline_classifier_invoked=True,
            reason_code=resolution.reason_code,
        )
    if event.selected_action_id is None:
        raise BaselineResolutionContractError("baseline boundary omitted the selected action")
    return _decision(
        event=event,
        status="available",
        baseline_action_ids=resolution.baseline_action_ids,
        baseline_resolution_id=resolution.resolution_id,
        baseline_classifier_invoked=True,
        ordinary_detour_observed=event.selected_action_id not in resolution.baseline_action_ids,
        reason_code=None,
    )


def make_measurement_support_contract_v2() -> MeasurementSupportContractV2:
    provisional = MeasurementSupportContractV2.model_construct(contract_id="pending")
    return MeasurementSupportContractV2(
        contract_id=_identity(
            provisional,
            "contract_id",
            "prospective_measurement_support_contract_v2:",
        )
    )
