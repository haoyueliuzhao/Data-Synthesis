from __future__ import annotations

import pytest

from trusted_synthesis.core.evaluation.measurement_outcome_v2 import (
    make_measurement_outcome_projection_v2,
)
from trusted_synthesis.core.measurement.support import (
    make_baseline_resolution,
    make_measurement_support_event,
)
from trusted_synthesis.core.measurement.support_v2 import (
    BaselineResolutionContractError,
    classify_measurement_support_v2,
)


def _no_progress_event():
    return make_measurement_support_event(
        event_kind="public_observation",
        public_state_id_before="state-1",
        public_state_id_after="state-2",
        progress_vector_id_before="progress-1",
        progress_vector_id_after="progress-1",
        selected_action_id="action-2",
        observation_status="succeeded",
    )


def test_v2_support_classifier_propagates_programming_errors() -> None:
    def broken_resolver():
        raise RuntimeError("programming bug")

    with pytest.raises(RuntimeError, match="programming bug"):
        classify_measurement_support_v2(
            _no_progress_event(),
            baseline_resolver=broken_resolver,
        )


def test_v2_support_classifier_requires_typed_unavailability_and_exact_binding() -> None:
    unavailable = classify_measurement_support_v2(
        _no_progress_event(),
        baseline_resolver=lambda: make_baseline_resolution(
            status="unavailable",
            public_state_id="state-1",
            progress_vector_id="progress-1",
            reason_code="baseline_not_defined_for_public_state",
        ),
    )
    assert unavailable.status == "unavailable"
    assert unavailable.undeclared_exception_converted_to_support_exit is False

    with pytest.raises(BaselineResolutionContractError, match="crossed"):
        classify_measurement_support_v2(
            _no_progress_event(),
            baseline_resolver=lambda: make_baseline_resolution(
                status="available",
                public_state_id="other-state",
                progress_vector_id="progress-1",
                baseline_action_ids=("action-1",),
            ),
        )


def test_support_exit_is_not_reexpressed_as_instrument_failure() -> None:
    projection = make_measurement_outcome_projection_v2(
        terminal_class="measurement_support_exit",
        raw_instrument_integrity=True,
        measurement_support_status="unavailable",
        resource_accounting_integrity=True,
        detour_allowance_status=False,
        privacy_compliant=True,
        provider_response_observed=True,
        public_payload_observed=True,
        model_action_observed=True,
        model_terminal_observed=False,
        completed_task_endpoint=False,
    )

    assert projection.support_exit is True
    assert projection.instrument_failure is False
    assert projection.support_exit_reexpressed_as_instrument_failure is False
    assert projection.validity_evaluable is False


def test_endpoint_observations_distinguish_typed_rejection_budget_and_completion() -> None:
    rejection = make_measurement_outcome_projection_v2(
        terminal_class="model_typed_rejection",
        raw_instrument_integrity=True,
        measurement_support_status="not_required",
        resource_accounting_integrity=True,
        detour_allowance_status=True,
        privacy_compliant=True,
        provider_response_observed=True,
        public_payload_observed=True,
        model_action_observed=True,
        model_terminal_observed=True,
        completed_task_endpoint=False,
    )
    budget = make_measurement_outcome_projection_v2(
        terminal_class="typed_budget_no_call",
        raw_instrument_integrity=True,
        measurement_support_status="not_required",
        resource_accounting_integrity=True,
        detour_allowance_status=True,
        privacy_compliant=True,
        provider_response_observed=False,
        public_payload_observed=False,
        model_action_observed=False,
        model_terminal_observed=False,
        completed_task_endpoint=False,
    )
    completed = make_measurement_outcome_projection_v2(
        terminal_class="completed_model_endpoint",
        raw_instrument_integrity=True,
        measurement_support_status="not_required",
        resource_accounting_integrity=True,
        detour_allowance_status=True,
        privacy_compliant=True,
        provider_response_observed=True,
        public_payload_observed=True,
        model_action_observed=True,
        model_terminal_observed=True,
        completed_task_endpoint=True,
    )

    assert rejection.model_outcome is True
    assert rejection.validity_evaluable is True
    assert rejection.endpoint.completed_task_endpoint is False
    assert budget.model_outcome is False
    assert budget.validity_evaluable is False
    assert completed.endpoint.completed_task_endpoint is True


def test_v2_terminal_classes_reject_support_instrument_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        make_measurement_outcome_projection_v2(
            terminal_class="measurement_support_exit",
            raw_instrument_integrity=False,
            measurement_support_status="unavailable",
            resource_accounting_integrity=True,
            detour_allowance_status=False,
            privacy_compliant=True,
            provider_response_observed=True,
            public_payload_observed=True,
            model_action_observed=True,
            model_terminal_observed=False,
            completed_task_endpoint=False,
        )


def test_v2_terminal_class_must_match_projected_facts() -> None:
    with pytest.raises(ValueError, match="terminal class disagrees"):
        make_measurement_outcome_projection_v2(
            terminal_class="completed_model_endpoint",
            raw_instrument_integrity=True,
            measurement_support_status="not_required",
            resource_accounting_integrity=True,
            detour_allowance_status=True,
            privacy_compliant=True,
            provider_response_observed=True,
            public_payload_observed=True,
            model_action_observed=True,
            model_terminal_observed=True,
            completed_task_endpoint=False,
        )

    with pytest.raises(ValueError, match="terminal class disagrees"):
        make_measurement_outcome_projection_v2(
            terminal_class="instrument_failure",
            raw_instrument_integrity=True,
            measurement_support_status="not_required",
            resource_accounting_integrity=True,
            detour_allowance_status=True,
            privacy_compliant=True,
            provider_response_observed=False,
            public_payload_observed=False,
            model_action_observed=False,
            model_terminal_observed=False,
            completed_task_endpoint=False,
        )

    with pytest.raises(ValueError, match="not mutually exclusive"):
        make_measurement_outcome_projection_v2(
            terminal_class="measurement_support_exit",
            raw_instrument_integrity=True,
            measurement_support_status="unavailable",
            resource_accounting_integrity=True,
            detour_allowance_status=True,
            privacy_compliant=True,
            provider_response_observed=True,
            public_payload_observed=True,
            model_action_observed=True,
            model_terminal_observed=True,
            completed_task_endpoint=False,
        )
