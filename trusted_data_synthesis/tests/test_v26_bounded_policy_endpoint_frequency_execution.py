from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    make_bounded_policy_global_integrity_gate,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_execution as execution,
)
from trusted_synthesis.runtime.agent import prospective_bounded_policy_endpoint_runner as adapter


@pytest.mark.parametrize(
    ("terminal_disposition", "terminal_failure_type", "expected"),
    (
        (
            "measurement_support_exit",
            "ordinary_detour_allowance_exhausted",
            "ordinary_detour_limit",
        ),
        (
            "model_result_failure",
            "semantic_action_primary_request_limit_exhausted",
            "primary_request_limit",
        ),
        (
            "typed_budget_no_call",
            "stage_one_request_count_exhausted",
            "provider_call_limit",
        ),
        (
            "typed_budget_no_call",
            "request_bound_exceeds_remaining_budget",
            "rollout_token_limit",
        ),
        (
            "typed_budget_no_call",
            "required_reserve_not_available",
            "rollout_token_limit",
        ),
        (
            "typed_budget_no_call",
            "transport_invocation_count_exhausted",
            "transport_invocation_limit",
        ),
        ("completed_model_endpoint", None, None),
    ),
)
def test_v26_164_independent_horizon_decoder_covers_raw_runner_terminals(
    terminal_disposition: str,
    terminal_failure_type: str | None,
    expected: str | None,
) -> None:
    raw = cast(
        Any,
        SimpleNamespace(
            terminal_disposition=terminal_disposition,
            terminal_failure_type=terminal_failure_type,
        ),
    )
    assert execution._expected_horizon_reason(raw) == expected  # noqa: SLF001


def test_v26_164_rejects_undeclared_typed_budget_terminal() -> None:
    raw = cast(
        Any,
        SimpleNamespace(
            terminal_disposition="typed_budget_no_call",
            terminal_failure_type="unknown_budget_boundary",
        ),
    )
    with pytest.raises(ValueError, match="undeclared typed-budget terminal"):
        execution._expected_horizon_reason(raw)  # noqa: SLF001


def test_v26_164_guard_exposes_frozen_adapter_coverage_boundary() -> None:
    raw = cast(
        Any,
        SimpleNamespace(
            terminal_disposition="model_result_failure",
            terminal_failure_type="semantic_action_primary_request_limit_exhausted",
        ),
    )
    assert execution._expected_horizon_reason(raw) == "primary_request_limit"  # noqa: SLF001
    assert adapter._policy_horizon_reason(raw) is None  # noqa: SLF001

    raw = cast(
        Any,
        SimpleNamespace(
            terminal_disposition="typed_budget_no_call",
            terminal_failure_type="stage_one_request_count_exhausted",
        ),
    )
    assert execution._expected_horizon_reason(raw) == "provider_call_limit"  # noqa: SLF001
    with pytest.raises(ValueError, match="lacks a declared bounded-policy Horizon"):
        adapter._policy_horizon_reason(raw)  # noqa: SLF001


def test_v26_164_failed_global_gate_blocks_assignment_before_mapper() -> None:
    gate = make_bounded_policy_global_integrity_gate(
        exact_job_denominator=360,
        complete_raw_count=360,
        bounded_policy_endpoint_count=359,
    )
    assert gate.passed is False
    with pytest.raises(ValueError, match="passing Global Integrity Gate"):
        execution._make_frequency_assignment(  # noqa: SLF001
            job=SimpleNamespace(job_id="job"),
            cell=SimpleNamespace(
                cell_id="cell",
                task_package_id="task",
                experimental_condition_id="condition",
            ),
            mapping_assignment=SimpleNamespace(
                structural_state_id="state",
                empirical_route_signature_id="route",
            ),
            gate=gate,
        )
