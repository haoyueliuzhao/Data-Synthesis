from __future__ import annotations

import pytest

from trusted_synthesis.core.measurement.support import (
    make_baseline_resolution,
    make_measurement_support_event,
)
from trusted_synthesis.core.measurement.support_v2 import (
    BaselineResolutionContractError,
    classify_measurement_support_v2,
)


def _event():
    return make_measurement_support_event(
        event_kind="public_observation",
        public_state_id_before="state-before",
        public_state_id_after="state-unavailable",
        progress_vector_id_before="progress-before",
        progress_vector_id_after="progress-before",
        selected_action_id="action-1",
        observation_status="succeeded",
        successor_public_state_available=False,
    )


def test_unavailable_successor_requires_an_exact_typed_support_resolution() -> None:
    decision = classify_measurement_support_v2(
        _event(),
        baseline_resolver=lambda: make_baseline_resolution(
            status="unavailable",
            public_state_id="state-before",
            progress_vector_id="progress-before",
            reason_code="public_successor_not_constructible",
        ),
    )
    assert decision.status == "unavailable"
    assert decision.reason_code == "public_successor_not_constructible"

    with pytest.raises(BaselineResolutionContractError, match="exactly bound"):
        classify_measurement_support_v2(
            _event(),
            baseline_resolver=lambda: make_baseline_resolution(
                status="available",
                public_state_id="state-before",
                progress_vector_id="progress-before",
                baseline_action_ids=("action-1",),
            ),
        )
