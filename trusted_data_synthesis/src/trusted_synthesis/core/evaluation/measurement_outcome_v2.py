from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash

MeasurementTerminalClassV2 = Literal[
    "completed_model_endpoint",
    "model_result_failure",
    "model_typed_rejection",
    "measurement_support_exit",
    "instrument_failure",
    "privacy_failure",
    "typed_budget_no_call",
    "provider_transport_failure",
]
MeasurementSupportStatusV2 = Literal["available", "not_required", "unavailable"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class EndpointObservationV2(FrozenModel):
    provider_response_observed: bool
    public_payload_observed: bool
    model_action_observed: bool
    model_terminal_observed: bool
    completed_task_endpoint: bool

    @model_validator(mode="after")
    def validate_endpoint(self) -> EndpointObservationV2:
        if self.public_payload_observed and not self.provider_response_observed:
            raise ValueError("public payload cannot precede a Provider response")
        if self.model_action_observed and not self.public_payload_observed:
            raise ValueError("model action cannot precede a public payload")
        if self.model_terminal_observed and not self.provider_response_observed:
            raise ValueError("model terminal cannot precede a Provider response")
        if self.completed_task_endpoint and not (
            self.model_terminal_observed and self.public_payload_observed
        ):
            raise ValueError("completed task endpoint is missing model terminal evidence")
        return self


class MeasurementOutcomeProjectionV2(FrozenModel):
    projection_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    terminal_class: MeasurementTerminalClassV2
    raw_instrument_integrity: bool
    measurement_support_status: MeasurementSupportStatusV2
    resource_accounting_integrity: bool
    detour_allowance_status: bool
    privacy_compliant: bool
    endpoint: EndpointObservationV2
    validity_evaluable: bool
    support_exit: bool
    instrument_failure: bool
    model_outcome: bool
    endpoint_projection_matches_raw: Literal[True] = True
    support_exit_reexpressed_as_instrument_failure: Literal[False] = False
    schema_version: str = "prospective_measurement_outcome_projection.v2"

    @model_validator(mode="after")
    def validate_projection(self) -> MeasurementOutcomeProjectionV2:
        expected_support_exit = self.measurement_support_status == "unavailable"
        expected_instrument_failure = (
            not self.raw_instrument_integrity or not self.resource_accounting_integrity
        )
        expected_model_outcome = self.endpoint.model_terminal_observed
        expected_evaluable = bool(
            not expected_support_exit
            and not expected_instrument_failure
            and self.privacy_compliant
            and expected_model_outcome
        )
        if (
            self.support_exit != expected_support_exit
            or self.instrument_failure != expected_instrument_failure
            or self.model_outcome != expected_model_outcome
            or self.validity_evaluable != expected_evaluable
        ):
            raise ValueError("v2 Measurement outcome decomposition changed")
        if self.support_exit and self.instrument_failure:
            raise ValueError("Support Exit and Instrument Failure overlap")
        terminal_fact_count = sum(
            (
                self.support_exit,
                self.instrument_failure,
                not self.privacy_compliant,
                self.model_outcome,
            )
        )
        if terminal_fact_count > 1:
            raise ValueError("v2 terminal facts are not mutually exclusive")
        if not self.detour_allowance_status and not self.support_exit:
            raise ValueError("detour allowance exhaustion must be a Support Exit")
        if self.support_exit:
            expected_terminal_classes = {"measurement_support_exit"}
        elif self.instrument_failure:
            expected_terminal_classes = {"instrument_failure"}
        elif not self.privacy_compliant:
            expected_terminal_classes = {"privacy_failure"}
        elif self.model_outcome:
            expected_terminal_classes = (
                {"completed_model_endpoint"}
                if self.endpoint.completed_task_endpoint
                else {"model_result_failure", "model_typed_rejection"}
            )
        else:
            expected_terminal_classes = {
                "typed_budget_no_call",
                "provider_transport_failure",
            }
        if self.terminal_class not in expected_terminal_classes:
            raise ValueError("terminal class disagrees with the v2 outcome projection")
        if self.projection_id != _identity(
            self,
            "projection_id",
            "prospective_measurement_outcome_projection_v2:",
        ):
            raise ValueError("v2 Measurement outcome projection identity changed")
        return self


def make_measurement_outcome_projection_v2(
    *,
    terminal_class: MeasurementTerminalClassV2,
    raw_instrument_integrity: bool,
    measurement_support_status: MeasurementSupportStatusV2,
    resource_accounting_integrity: bool,
    detour_allowance_status: bool,
    privacy_compliant: bool,
    provider_response_observed: bool,
    public_payload_observed: bool,
    model_action_observed: bool,
    model_terminal_observed: bool,
    completed_task_endpoint: bool,
    trajectory_id: str = "fixture-trajectory",
) -> MeasurementOutcomeProjectionV2:
    endpoint = EndpointObservationV2(
        provider_response_observed=provider_response_observed,
        public_payload_observed=public_payload_observed,
        model_action_observed=model_action_observed,
        model_terminal_observed=model_terminal_observed,
        completed_task_endpoint=completed_task_endpoint,
    )
    support_exit = measurement_support_status == "unavailable"
    instrument_failure = not raw_instrument_integrity or not resource_accounting_integrity
    model_outcome = endpoint.model_terminal_observed
    values = {
        "trajectory_id": trajectory_id,
        "terminal_class": terminal_class,
        "raw_instrument_integrity": raw_instrument_integrity,
        "measurement_support_status": measurement_support_status,
        "resource_accounting_integrity": resource_accounting_integrity,
        "detour_allowance_status": detour_allowance_status,
        "privacy_compliant": privacy_compliant,
        "endpoint": endpoint,
        "validity_evaluable": bool(
            not support_exit and not instrument_failure and privacy_compliant and model_outcome
        ),
        "support_exit": support_exit,
        "instrument_failure": instrument_failure,
        "model_outcome": model_outcome,
    }
    provisional = MeasurementOutcomeProjectionV2.model_construct(
        projection_id="pending",
        **values,
    )
    return MeasurementOutcomeProjectionV2(
        projection_id=_identity(
            provisional,
            "projection_id",
            "prospective_measurement_outcome_projection_v2:",
        ),
        **values,
    )
