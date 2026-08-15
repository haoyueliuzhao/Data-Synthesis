from __future__ import annotations

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    SubmechanismBehaviorObservation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability import (  # noqa: E501
    FinanceStoppingShapeStabilityContract,
    FinanceStoppingShapeStabilityReport,
    FrozenStoppingDifficultyPolicy,
    StoppingShapeResult,
    StoppingShapeTaskResponse,
    _make_shape_result,
    _shape_information_bootstrap,
    stopping_difficulty_policy_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (  # noqa: E501
    STRUCTURAL_STRATA,
    ParentSensitivityRow,
    PopulationSensitivityRow,
    SourceSensitivityDiagnostic,
    StoppingShapeThresholds,
    TaskSensitivityRow,
    source_sensitivity_diagnostic_id,
)

SHAPE_IDS = (
    "partial_required_evidence",
    "authority_coverage_gap",
    "single_dimension_conflict",
    "contextual_resolution_choice",
    "verified_extra_call_error_risk",
    "verified_extra_call_cost",
)


def _behavior(
    task_id: str,
    replicate: int,
    success: int,
) -> SubmechanismBehaviorObservation:
    return SubmechanismBehaviorObservation.model_construct(
        task_artifact_id=task_id,
        replicate=replicate,
        capability_contract_success=bool(success),
    )


def _shape_contract(
    *,
    shape_id: str,
) -> FinanceStoppingShapeStabilityContract:
    task_ids = tuple(f"task:{index}" for index in range(4))
    return FinanceStoppingShapeStabilityContract.model_construct(
        thresholds=StoppingShapeThresholds(bootstrap_replicates=500),
        task_stratum_ids={
            task_id: STRUCTURAL_STRATA[index][0]
            for index, task_id in enumerate(task_ids)
        },
        task_shape_roles={task_id: "boundary_candidate" for task_id in task_ids},
        task_shape_ids={task_id: shape_id for task_id in task_ids},
    )


def _shape_result(
    shape_id: str,
    *,
    admitted: bool,
) -> StoppingShapeResult:
    responses = tuple(
        StoppingShapeTaskResponse(
            task_artifact_id=f"{shape_id}:task:{index}",
            stratum_id=STRUCTURAL_STRATA[index][0],
            realizations=(1, 0, 1, 0, 1, 0, 1, 0),
            probability=0.5,
            fisher_information=0.25,
        )
        for index in range(4)
    )
    gates = {"scientific_gate": admitted}
    return StoppingShapeResult(
        shape_id=shape_id,
        shape_role="boundary_candidate",
        task_responses=responses,
        mean_success_rate=0.5,
        minimum_task_probability=0.5,
        maximum_task_probability=0.5,
        between_task_probability_range=0.0,
        boundary_task_count=4,
        nonzero_information_task_count=4,
        total_fisher_information=1.0,
        effective_task_count=4.0,
        maximum_single_task_information_share=0.25,
        bootstrap_information_interval95=(0.5, 1.0),
        bootstrap_information_lcb=0.5,
        gate_results=gates,
        admitted=admitted,
        failure_codes=() if admitted else ("scientific_gate",),
    )


def _difficulty_policy() -> FrozenStoppingDifficultyPolicy:
    values = {
        "source_contract_id": "contract:test",
        "shape_task_quotas": {shape_id: 4 for shape_id in SHAPE_IDS},
        "structural_strata": STRUCTURAL_STRATA,
        "thresholds": StoppingShapeThresholds(),
    }
    provisional = FrozenStoppingDifficultyPolicy.model_construct(
        policy_id="pending",
        **values,
    )
    return FrozenStoppingDifficultyPolicy(
        policy_id=stopping_difficulty_policy_id(provisional),
        **values,
    )


def test_hierarchical_shape_bootstrap_is_deterministic() -> None:
    thresholds = StoppingShapeThresholds(bootstrap_replicates=500)
    responses = tuple(
        StoppingShapeTaskResponse(
            task_artifact_id=f"task:{index}",
            stratum_id=STRUCTURAL_STRATA[index][0],
            realizations=(1, 0, 1, 0, 1, 0, 1, 0),
            probability=0.5,
            fisher_information=0.25,
        )
        for index in range(4)
    )

    first = _shape_information_bootstrap(
        responses,
        thresholds,
        shape_id="shape:test",
    )
    second = _shape_information_bootstrap(
        responses,
        thresholds,
        shape_id="shape:test",
    )

    assert first == second
    assert first[0] > 0.0


def test_shape_gate_rejects_single_task_information_dominance() -> None:
    contract = _shape_contract(shape_id="shape:test")
    patterns = (
        (1, 0, 1, 0, 1, 0, 1, 0),
        (1, 1, 1, 1, 1, 1, 1, 1),
        (1, 1, 1, 1, 1, 1, 1, 1),
        (1, 1, 1, 1, 1, 1, 1, 1),
    )
    behaviors = tuple(
        _behavior(f"task:{task_index}", replicate, success)
        for task_index, pattern in enumerate(patterns)
        for replicate, success in enumerate(pattern)
    )

    result = _make_shape_result(contract, "shape:test", behaviors)

    assert not result.admitted
    assert result.effective_task_count == 1.0
    assert "maximum_single_task_information_share" in result.failure_codes
    assert "minimum_nonzero_tasks" in result.failure_codes


def test_source_sensitivity_conclusions_are_fail_closed() -> None:
    parent_rows = tuple(
        ParentSensitivityRow(
            parent_mechanism_id=f"parent:{index}",
            information_share=0.25,
            leave_one_parent_maximum_angle_degrees=50.0 if index == 0 else 10.0,
        )
        for index in range(4)
    )
    task_row = TaskSensitivityRow(
        task_artifact_id="task:dominant",
        submechanism_id="submechanism:test",
        probability=0.5,
        fisher_weight=0.25,
        leave_one_task_maximum_angle_degrees=55.0,
    )
    population_rows = tuple(
        PopulationSensitivityRow(
            population_id=f"population:{index}",
            parent_rows=parent_rows,
            dominant_task_rows=(task_row,),
            maximum_non_stopping_parent_rotation_degrees=50.0,
            maximum_single_task_rotation_degrees=55.0,
        )
        for index in range(3)
    )
    values = {
        "source_contract_id": "contract:test",
        "population_rows": population_rows,
        "stopping_only_explanation_rejected": True,
        "single_task_dominance_observed": True,
    }
    provisional = SourceSensitivityDiagnostic.model_construct(
        diagnostic_id="pending",
        **values,
    )
    valid = SourceSensitivityDiagnostic(
        diagnostic_id=source_sensitivity_diagnostic_id(provisional),
        **values,
    )
    corrupted = valid.model_dump(mode="json")
    corrupted["stopping_only_explanation_rejected"] = False

    with pytest.raises(ValidationError, match="Stopping-only sensitivity conclusion"):
        SourceSensitivityDiagnostic.model_validate(corrupted)


def test_report_forbids_policy_freeze_when_any_shape_fails() -> None:
    shape_results = tuple(
        _shape_result(shape_id, admitted=index != 0)
        for index, shape_id in enumerate(SHAPE_IDS)
    )
    values = {
        "report_id": "pending",
        "contract_id": "contract:test",
        "recorded_rollout_count": 192,
        "execution_integrity_rate": 1.0,
        "terminal_resolution_rate": 1.0,
        "api_transport_resolution_rate": 1.0,
        "bounded_json_resolution_rate": 1.0,
        "observation_replay_rate": 1.0,
        "authority_integrity_rate": 1.0,
        "runtime_pathology_rate": 0.0,
        "l0_l2_failure_count": 0,
        "behavior_success_rate": 0.5,
        "primary_valid_success_rate": 0.5,
        "capability_contract_success_rate": 0.5,
        "runtime_measurement_ready": True,
        "shape_results": shape_results,
        "all_shapes_admitted": False,
        "difficulty_policy": _difficulty_policy(),
        "difficulty_policy_frozen": True,
        "api_call_count": 192,
        "total_model_tokens": 1_000,
        "estimated_cost_usd": 1.0,
        "discovered_models": ("DeepSeek-V4-Flash",),
        "failure_codes": ("shape:test",),
        "fresh_cross_population_preparation_authorized": False,
        "next_permitted_stage": "stopping_shape_support_redesign_only",
    }

    with pytest.raises(ValidationError, match="difficulty policy decision"):
        FinanceStoppingShapeStabilityReport.model_validate(values)
