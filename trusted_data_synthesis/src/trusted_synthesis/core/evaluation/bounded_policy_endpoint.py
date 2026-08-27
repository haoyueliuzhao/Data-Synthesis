from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from decimal import Decimal, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash

BoundedPolicyTerminalClass = Literal[
    "completed_model_endpoint",
    "model_result_failure",
    "model_typed_rejection",
    "policy_horizon_exhausted",
    "measurement_support_exit",
    "instrument_failure",
    "privacy_failure",
    "provider_transport_failure",
]
PolicyHorizonStatus = Literal["within_horizon", "exhausted"]
PolicyHorizonReason = Literal[
    "ordinary_detour_limit",
    "primary_request_limit",
    "provider_call_limit",
    "transport_invocation_limit",
    "rollout_token_limit",
]
CellNullReason = Literal[
    "global_integrity_gate_failed",
    "cell_endpoint_gate_failed",
    "no_qualified_rows",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class BoundedPolicyEndpointGenerationPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    measurement_support_contract_id: str = Field(min_length=1)
    maximum_primary_requests: Literal[21] = 21
    maximum_provider_calls: Literal[23] = 23
    maximum_transport_invocations: Literal[24] = 24
    maximum_rollout_tokens: Literal[1120000] = 1_120_000
    maximum_ordinary_detours: Literal[1] = 1
    declared_horizon_reasons: tuple[PolicyHorizonReason, ...] = (
        "ordinary_detour_limit",
        "primary_request_limit",
        "provider_call_limit",
        "rollout_token_limit",
        "transport_invocation_limit",
    )
    horizon_is_generation_policy_endpoint: Literal[True] = True
    horizon_is_measurement_support_exit: Literal[False] = False
    horizon_is_model_semantic_error: Literal[False] = False
    horizon_task_completion: Literal[False] = False
    horizon_base_validity: Literal[False] = False
    horizon_qualified_validity: Literal[False] = False
    horizon_state_mapping_eligible: Literal[False] = False
    unrestricted_natural_agent_distribution_claimed: Literal[False] = False
    schema_version: str = "bounded_policy_endpoint_generation.v1"

    @model_validator(mode="after")
    def validate_policy(self) -> BoundedPolicyEndpointGenerationPolicy:
        if self.declared_horizon_reasons != tuple(
            sorted(set(self.declared_horizon_reasons))
        ) or self.policy_id != _identity(
            self,
            "policy_id",
            "bounded_policy_endpoint_generation_policy:",
        ):
            raise ValueError("bounded-policy endpoint generation policy changed")
        return self


class BoundedPolicyEndpointProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    terminal_class: BoundedPolicyTerminalClass
    policy_horizon_status: PolicyHorizonStatus
    policy_horizon_reason: PolicyHorizonReason | None = None
    raw_instrument_integrity: bool
    measurement_support_available: bool
    resource_accounting_integrity: bool
    provider_identity_integrity: bool
    thinking_usage_integrity: bool
    privacy_compliant: bool
    transport_resolved: bool
    model_terminal_observed: bool
    policy_terminal_observed: bool
    bounded_policy_endpoint_observed: bool
    task_completion: bool | None
    base_validity: bool | None
    mechanism_qualification: bool | None
    qualified_validity: bool | None
    state_mapping_eligible: bool
    task_verifier_invocation_count: int = Field(ge=0, le=1)
    support_exit: bool
    instrument_failure: bool
    resource_failure: bool
    model_outcome: bool
    bounded_policy_outcome: bool
    validity_evaluable: bool
    schema_version: str = "bounded_policy_endpoint_projection.v1"

    @model_validator(mode="after")
    def validate_projection(self) -> BoundedPolicyEndpointProjection:
        horizon = self.policy_horizon_status == "exhausted"
        integrity = all(
            (
                self.raw_instrument_integrity,
                self.resource_accounting_integrity,
                self.provider_identity_integrity,
                self.thinking_usage_integrity,
                self.privacy_compliant,
                self.transport_resolved,
            )
        )
        endpoint = self.model_terminal_observed or self.policy_terminal_observed
        evaluable = bool(integrity and self.measurement_support_available and endpoint)
        if (
            horizon != (self.policy_horizon_reason is not None)
            or self.policy_terminal_observed != horizon
            or (self.model_terminal_observed and self.policy_terminal_observed)
            or self.bounded_policy_endpoint_observed != endpoint
            or self.validity_evaluable != evaluable
            or self.support_exit != (not self.measurement_support_available)
            or self.instrument_failure != (not self.raw_instrument_integrity)
            or self.resource_failure != (not self.resource_accounting_integrity)
            or self.model_outcome != self.model_terminal_observed
            or self.bounded_policy_outcome != endpoint
        ):
            raise ValueError("bounded-policy endpoint decomposition changed")
        if horizon and (
            self.terminal_class != "policy_horizon_exhausted"
            or not integrity
            or not self.measurement_support_available
            or self.task_completion is not False
            or self.base_validity is not False
            or self.qualified_validity is not False
            or self.state_mapping_eligible
            or self.task_verifier_invocation_count
        ):
            raise ValueError("policy Horizon is not a complete bounded-policy failure endpoint")
        if not evaluable and any(
            value is not None
            for value in (
                self.task_completion,
                self.base_validity,
                self.mechanism_qualification,
                self.qualified_validity,
            )
        ):
            raise ValueError("ineligible bounded-policy endpoint has imputed validity")
        if evaluable and self.qualified_validity != bool(
            self.base_validity is True and self.mechanism_qualification is True
        ):
            raise ValueError("bounded-policy Qualified validity changed")
        if self.state_mapping_eligible != (self.qualified_validity is True):
            raise ValueError("bounded-policy State Mapping eligibility changed")
        if self.projection_id != _identity(
            self,
            "projection_id",
            "bounded_policy_endpoint_projection:",
        ):
            raise ValueError("bounded-policy endpoint projection identity changed")
        return self


def make_bounded_policy_endpoint_projection(
    *,
    trajectory_id: str,
    generation_policy_id: str,
    terminal_class: BoundedPolicyTerminalClass,
    policy_horizon_reason: PolicyHorizonReason | None,
    raw_instrument_integrity: bool,
    measurement_support_available: bool,
    resource_accounting_integrity: bool,
    provider_identity_integrity: bool,
    thinking_usage_integrity: bool,
    privacy_compliant: bool,
    transport_resolved: bool,
    model_terminal_observed: bool,
    task_completion: bool | None,
    base_validity: bool | None,
    mechanism_qualification: bool | None,
    qualified_validity: bool | None,
    task_verifier_invocation_count: int,
) -> BoundedPolicyEndpointProjection:
    horizon = policy_horizon_reason is not None
    policy_terminal = horizon
    endpoint = model_terminal_observed or policy_terminal
    integrity = all(
        (
            raw_instrument_integrity,
            resource_accounting_integrity,
            provider_identity_integrity,
            thinking_usage_integrity,
            privacy_compliant,
            transport_resolved,
        )
    )
    evaluable = bool(integrity and measurement_support_available and endpoint)
    values = {
        "trajectory_id": trajectory_id,
        "generation_policy_id": generation_policy_id,
        "terminal_class": terminal_class,
        "policy_horizon_status": "exhausted" if horizon else "within_horizon",
        "policy_horizon_reason": policy_horizon_reason,
        "raw_instrument_integrity": raw_instrument_integrity,
        "measurement_support_available": measurement_support_available,
        "resource_accounting_integrity": resource_accounting_integrity,
        "provider_identity_integrity": provider_identity_integrity,
        "thinking_usage_integrity": thinking_usage_integrity,
        "privacy_compliant": privacy_compliant,
        "transport_resolved": transport_resolved,
        "model_terminal_observed": model_terminal_observed,
        "policy_terminal_observed": policy_terminal,
        "bounded_policy_endpoint_observed": endpoint,
        "task_completion": task_completion,
        "base_validity": base_validity,
        "mechanism_qualification": mechanism_qualification,
        "qualified_validity": qualified_validity,
        "state_mapping_eligible": qualified_validity is True,
        "task_verifier_invocation_count": task_verifier_invocation_count,
        "support_exit": not measurement_support_available,
        "instrument_failure": not raw_instrument_integrity,
        "resource_failure": not resource_accounting_integrity,
        "model_outcome": model_terminal_observed,
        "bounded_policy_outcome": endpoint,
        "validity_evaluable": evaluable,
    }
    provisional = BoundedPolicyEndpointProjection.model_construct(
        projection_id="pending",
        **values,
    )
    return BoundedPolicyEndpointProjection(
        projection_id=_identity(
            provisional,
            "projection_id",
            "bounded_policy_endpoint_projection:",
        ),
        **values,
    )


class BoundedPolicyGlobalIntegrityGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    exact_job_denominator: int = Field(gt=0)
    complete_raw_count: int = Field(ge=0)
    bounded_policy_endpoint_count: int = Field(ge=0)
    raw_instrument_failure_count: int = Field(ge=0)
    resource_accounting_failure_count: int = Field(ge=0)
    privacy_failure_count: int = Field(ge=0)
    provider_identity_thinking_usage_failure_count: int = Field(ge=0)
    unresolved_transport_failure_count: int = Field(ge=0)
    unsupported_measurement_exit_count: int = Field(ge=0)
    passed: bool
    failure_ids: tuple[str, ...]
    cell_selection_after_outcome_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_gate(self) -> BoundedPolicyGlobalIntegrityGate:
        checks = {
            "complete_raw_denominator": self.complete_raw_count == self.exact_job_denominator,
            "complete_policy_endpoint_denominator": (
                self.bounded_policy_endpoint_count == self.exact_job_denominator
            ),
            "raw_instrument_failure_zero": self.raw_instrument_failure_count == 0,
            "resource_accounting_failure_zero": self.resource_accounting_failure_count == 0,
            "privacy_failure_zero": self.privacy_failure_count == 0,
            "provider_identity_thinking_usage_failure_zero": (
                self.provider_identity_thinking_usage_failure_count == 0
            ),
            "unresolved_transport_failure_zero": self.unresolved_transport_failure_count == 0,
            "unsupported_measurement_exit_zero": self.unsupported_measurement_exit_count == 0,
        }
        expected_failures = tuple(sorted(name for name, passed in checks.items() if not passed))
        if (
            self.passed != all(checks.values())
            or self.failure_ids != expected_failures
            or self.gate_id
            != _identity(
                self,
                "gate_id",
                "bounded_policy_global_integrity_gate:",
            )
        ):
            raise ValueError("bounded-policy Global Integrity Gate changed")
        return self


def make_bounded_policy_global_integrity_gate(
    *,
    exact_job_denominator: int,
    complete_raw_count: int,
    bounded_policy_endpoint_count: int,
    raw_instrument_failure_count: int = 0,
    resource_accounting_failure_count: int = 0,
    privacy_failure_count: int = 0,
    provider_identity_thinking_usage_failure_count: int = 0,
    unresolved_transport_failure_count: int = 0,
    unsupported_measurement_exit_count: int = 0,
) -> BoundedPolicyGlobalIntegrityGate:
    checks = {
        "complete_raw_denominator": complete_raw_count == exact_job_denominator,
        "complete_policy_endpoint_denominator": (
            bounded_policy_endpoint_count == exact_job_denominator
        ),
        "raw_instrument_failure_zero": raw_instrument_failure_count == 0,
        "resource_accounting_failure_zero": resource_accounting_failure_count == 0,
        "privacy_failure_zero": privacy_failure_count == 0,
        "provider_identity_thinking_usage_failure_zero": (
            provider_identity_thinking_usage_failure_count == 0
        ),
        "unresolved_transport_failure_zero": unresolved_transport_failure_count == 0,
        "unsupported_measurement_exit_zero": unsupported_measurement_exit_count == 0,
    }
    values = {
        "exact_job_denominator": exact_job_denominator,
        "complete_raw_count": complete_raw_count,
        "bounded_policy_endpoint_count": bounded_policy_endpoint_count,
        "raw_instrument_failure_count": raw_instrument_failure_count,
        "resource_accounting_failure_count": resource_accounting_failure_count,
        "privacy_failure_count": privacy_failure_count,
        "provider_identity_thinking_usage_failure_count": (
            provider_identity_thinking_usage_failure_count
        ),
        "unresolved_transport_failure_count": unresolved_transport_failure_count,
        "unsupported_measurement_exit_count": unsupported_measurement_exit_count,
        "passed": all(checks.values()),
        "failure_ids": tuple(sorted(name for name, passed in checks.items() if not passed)),
    }
    provisional = BoundedPolicyGlobalIntegrityGate.model_construct(gate_id="pending", **values)
    return BoundedPolicyGlobalIntegrityGate(
        gate_id=_identity(
            provisional,
            "gate_id",
            "bounded_policy_global_integrity_gate:",
        ),
        **values,
    )


class WilsonInterval(FrozenModel):
    confidence_level: Literal["0.95"] = "0.95"
    lower: str
    upper: str
    method: Literal["wilson_score"] = "wilson_score"
    simultaneous_multinomial_coverage_claimed: Literal[False] = False


def wilson_interval(successes: int, total: int) -> WilsonInterval:
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("Wilson interval denominator changed")
    with localcontext() as context:
        context.prec = 50
        n = Decimal(total)
        p = Decimal(successes) / n
        z = Decimal("1.959963984540054")
        z2 = z * z
        denominator = Decimal(1) + z2 / n
        center = (p + z2 / (Decimal(2) * n)) / denominator
        margin = z * ((p * (Decimal(1) - p) / n + z2 / (Decimal(4) * n * n)).sqrt()) / denominator
        lower = max(Decimal(0), center - margin)
        upper = min(Decimal(1), center + margin)
    return WilsonInterval(lower=format(lower, "f"), upper=format(upper, "f"))


class StateFrequency(FrozenModel):
    structural_state_id: str = Field(min_length=1)
    count: int = Field(gt=0)
    empirical_frequency: str
    marginal_wilson_interval: WilsonInterval


class BoundedPolicyCellFrequencyReport(FrozenModel):
    report_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    global_gate_id: str = Field(min_length=1)
    global_integrity_gate_passed: bool
    expected_n_total: int = Field(gt=0)
    n_total: int = Field(ge=0)
    n_policy_endpoints: int = Field(ge=0)
    n_qualified: int = Field(ge=0)
    q_hat: str | None
    q_wilson_interval: WilsonInterval | None
    state_frequencies: tuple[StateFrequency, ...]
    pi_instantiated: bool
    pi_null_reason: CellNullReason | None
    empirical_non_degenerate: bool | None
    stable_population_probability_claimed: Literal[False] = False
    task_is_primary_statistical_unit: Literal[True] = True
    rollouts_are_secondary_repeated_measures: Literal[True] = True

    @model_validator(mode="after")
    def validate_report(self) -> BoundedPolicyCellFrequencyReport:
        global_failed = not self.global_integrity_gate_passed
        cell_complete = bool(
            self.n_total == self.expected_n_total
            and self.n_policy_endpoints == self.expected_n_total
        )
        if global_failed:
            if (
                self.q_wilson_interval is not None
                or self.state_frequencies
                or self.pi_instantiated
                or self.pi_null_reason != "global_integrity_gate_failed"
            ):
                raise ValueError("failed Global Gate leaked a Cell estimand")
        elif not cell_complete:
            if (
                self.q_wilson_interval is not None
                or self.state_frequencies
                or self.pi_instantiated
                or self.pi_null_reason != "cell_endpoint_gate_failed"
            ):
                raise ValueError("failed Cell Gate leaked a Cell estimand")
        elif self.n_qualified == 0:
            if (
                self.q_hat != "0"
                or self.q_wilson_interval is None
                or self.state_frequencies
                or self.pi_instantiated
                or self.pi_null_reason != "no_qualified_rows"
                or self.empirical_non_degenerate is not None
            ):
                raise ValueError("zero-Qualified Cell was imputed as a State distribution")
        else:
            counts = sum(item.count for item in self.state_frequencies)
            if (
                self.q_wilson_interval is None
                or not self.pi_instantiated
                or self.pi_null_reason is not None
                or counts != self.n_qualified
                or self.empirical_non_degenerate
                != (self.n_qualified >= 2 and len(self.state_frequencies) >= 2)
            ):
                raise ValueError("bounded-policy Cell frequency changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "bounded_policy_cell_frequency_report:",
        ):
            raise ValueError("bounded-policy Cell report identity changed")
        return self


def summarize_bounded_policy_cell(
    *,
    task_condition_cell_id: str,
    generation_policy_id: str,
    global_gate: BoundedPolicyGlobalIntegrityGate,
    expected_n_total: int,
    observed_n_total: int,
    endpoint_count: int,
    qualified_state_ids: Sequence[str],
) -> BoundedPolicyCellFrequencyReport:
    n_total = observed_n_total
    n_qualified = len(qualified_state_ids)
    q_hat: str | None = None
    q_interval: WilsonInterval | None = None
    state_rows: tuple[StateFrequency, ...] = ()
    pi_instantiated = False
    null_reason: CellNullReason | None = None
    nondegenerate: bool | None = None
    if not global_gate.passed:
        null_reason = "global_integrity_gate_failed"
    elif endpoint_count != expected_n_total:
        null_reason = "cell_endpoint_gate_failed"
    else:
        q_hat = format(Decimal(n_qualified) / Decimal(expected_n_total), "f")
        q_interval = wilson_interval(n_qualified, expected_n_total)
        if n_qualified == 0:
            q_hat = "0"
            null_reason = "no_qualified_rows"
        else:
            counts = Counter(qualified_state_ids)
            state_rows = tuple(
                StateFrequency(
                    structural_state_id=state_id,
                    count=count,
                    empirical_frequency=format(
                        Decimal(count) / Decimal(n_qualified),
                        "f",
                    ),
                    marginal_wilson_interval=wilson_interval(count, n_qualified),
                )
                for state_id, count in sorted(counts.items())
            )
            pi_instantiated = True
            nondegenerate = n_qualified >= 2 and len(state_rows) >= 2
    values = {
        "task_condition_cell_id": task_condition_cell_id,
        "generation_policy_id": generation_policy_id,
        "global_gate_id": global_gate.gate_id,
        "global_integrity_gate_passed": global_gate.passed,
        "expected_n_total": expected_n_total,
        "n_total": n_total,
        "n_policy_endpoints": endpoint_count,
        "n_qualified": n_qualified,
        "q_hat": q_hat,
        "q_wilson_interval": q_interval,
        "state_frequencies": state_rows,
        "pi_instantiated": pi_instantiated,
        "pi_null_reason": null_reason,
        "empirical_non_degenerate": nondegenerate,
    }
    provisional = BoundedPolicyCellFrequencyReport.model_construct(report_id="pending", **values)
    return BoundedPolicyCellFrequencyReport(
        report_id=_identity(
            provisional,
            "report_id",
            "bounded_policy_cell_frequency_report:",
        ),
        **values,
    )
