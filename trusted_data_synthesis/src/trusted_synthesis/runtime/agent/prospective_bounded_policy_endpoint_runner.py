from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyEndpointGenerationPolicy,
    BoundedPolicyEndpointProjection,
    BoundedPolicyTerminalClass,
    PolicyHorizonReason,
    make_bounded_policy_endpoint_projection,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


class BoundedPolicyEndpointRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    raw_execution_content_hash: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    projection: BoundedPolicyEndpointProjection
    historical_raw_reclassified: Literal[False] = False
    schema_version: str = "bounded_policy_endpoint_record.v1"

    @model_validator(mode="after")
    def validate_record(self) -> BoundedPolicyEndpointRecord:
        if (
            self.projection.trajectory_id != self.raw_execution_id
            or self.projection.generation_policy_id != self.generation_policy_id
            or self.record_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"record_id"}),
                prefix="bounded_policy_endpoint_record:",
            )
        ):
            raise ValueError("bounded-policy endpoint Raw binding changed")
        return self


def _policy_horizon_reason(raw: Any) -> PolicyHorizonReason | None:
    failure = str(raw.terminal_failure_type or "")
    if (
        raw.terminal_disposition == "measurement_support_exit"
        and failure == "ordinary_detour_allowance_exhausted"
    ):
        return "ordinary_detour_limit"
    if raw.terminal_disposition != "typed_budget_no_call":
        return None
    for marker, reason in (
        ("primary_request", "primary_request_limit"),
        ("provider_call", "provider_call_limit"),
        ("transport", "transport_invocation_limit"),
        ("rollout", "rollout_token_limit"),
        ("token", "rollout_token_limit"),
    ):
        if marker in failure:
            return cast(PolicyHorizonReason, reason)
    raise ValueError("typed budget no-call lacks a declared bounded-policy Horizon reason")


def _terminal_class(
    raw: Any,
    horizon_reason: PolicyHorizonReason | None,
) -> BoundedPolicyTerminalClass:
    if horizon_reason is not None:
        return "policy_horizon_exhausted"
    return cast(
        BoundedPolicyTerminalClass,
        {
            "completed_model_endpoint": "completed_model_endpoint",
            "model_result_failure": "model_result_failure",
            "typed_semantic_rejection": "model_typed_rejection",
            "measurement_support_exit": "measurement_support_exit",
            "instrument_failure": "instrument_failure",
            "privacy_rejection": "privacy_failure",
            "provider_transport_failure": "provider_transport_failure",
        }[raw.terminal_disposition],
    )


def make_bounded_policy_endpoint_record(
    *,
    raw: Any,
    policy: BoundedPolicyEndpointGenerationPolicy,
    provider_identity_integrity: bool,
    thinking_usage_integrity: bool,
    privacy_artifact_integrity: bool,
    transport_resolved: bool,
    task_completion: bool | None,
    base_validity: bool | None,
    mechanism_qualification: bool | None,
    qualified_validity: bool | None,
    task_verifier_invocation_count: int,
) -> BoundedPolicyEndpointRecord:
    horizon_reason = _policy_horizon_reason(raw)
    terminal_class = _terminal_class(raw, horizon_reason)
    horizon = horizon_reason is not None
    model_terminal = raw.terminal_disposition in {
        "completed_model_endpoint",
        "model_result_failure",
        "typed_semantic_rejection",
    }
    measurement_support_available = bool(
        horizon
        or (
            raw.measurement_support_available
            and raw.terminal_disposition != "measurement_support_exit"
        )
    )
    resource_integrity = bool(
        raw.cumulative_provider_tokens <= policy.maximum_rollout_tokens
        and raw.stage_one_provider_call_count <= policy.maximum_provider_calls
        and raw.transport_inclusive_invocation_count <= policy.maximum_transport_invocations
    )
    if horizon:
        task_completion = False
        base_validity = False
        mechanism_qualification = False
        qualified_validity = False
        task_verifier_invocation_count = 0
    elif not model_terminal:
        task_completion = None
        base_validity = None
        mechanism_qualification = None
        qualified_validity = None
        task_verifier_invocation_count = 0
    projection = make_bounded_policy_endpoint_projection(
        trajectory_id=raw.artifact_id,
        generation_policy_id=policy.policy_id,
        terminal_class=terminal_class,
        policy_horizon_reason=horizon_reason,
        raw_instrument_integrity=raw.instrument_integrity,
        measurement_support_available=measurement_support_available,
        resource_accounting_integrity=resource_integrity,
        provider_identity_integrity=provider_identity_integrity,
        thinking_usage_integrity=thinking_usage_integrity,
        privacy_compliant=bool(raw.privacy_compliant and privacy_artifact_integrity),
        transport_resolved=transport_resolved,
        model_terminal_observed=model_terminal,
        task_completion=task_completion,
        base_validity=base_validity,
        mechanism_qualification=mechanism_qualification,
        qualified_validity=qualified_validity,
        task_verifier_invocation_count=task_verifier_invocation_count,
    )
    values = {
        "raw_execution_id": raw.artifact_id,
        "raw_execution_content_hash": strict_canonical_hash(
            raw,
            prefix="bounded_policy_parent_raw_execution:",
        ),
        "generation_policy_id": policy.policy_id,
        "projection": projection,
    }
    provisional = BoundedPolicyEndpointRecord.model_construct(record_id="pending", **values)
    return BoundedPolicyEndpointRecord(
        record_id=strict_canonical_hash(
            provisional.model_dump(mode="python", exclude={"record_id"}),
            prefix="bounded_policy_endpoint_record:",
        ),
        **values,
    )
