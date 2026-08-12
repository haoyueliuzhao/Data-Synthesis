from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    ConfidenceInterval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    FinanceMultiTierFlashReport,
    MultiTierInformationCell,
    _make_support_rules,
    _select_pro_anchor_groups,
    multitier_flash_report_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_workflow_information_audit import (
    InformationGate,
)


def test_multitier_support_excludes_host_axes_and_recovery_easy() -> None:
    rules = {
        (item.runtime_arm, item.family): item for item in _make_support_rules()
    }

    scripted_stopping = rules[
        (
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            "finance.stopping_decision_control",
        )
    ]
    assert scripted_stopping.primary_tiers == ()
    assert set(scripted_stopping.secondary_tiers) == set(DifficultyTier)

    scripted_branching = rules[
        (
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            "finance.branching_operation_plan",
        )
    ]
    assert scripted_branching.primary_tiers == ()
    assert set(scripted_branching.secondary_tiers) == set(DifficultyTier)

    for runtime in (
        CapabilityRuntimeArm.SCRIPTED_TOOL,
        CapabilityRuntimeArm.AUTONOMOUS_AGENT,
    ):
        recovery = rules[(runtime, "finance.recovery_guided_search")]
        assert recovery.primary_tiers == (
            DifficultyTier.FRONTIER,
            DifficultyTier.HARD_CONTROL,
        )
        assert recovery.secondary_tiers == (DifficultyTier.EASY_CONTROL,)


def test_sparse_pro_anchor_selection_is_preregistered_and_balanced() -> None:
    groups = tuple(
        SimpleNamespace(family=family, group_id=f"{family}:group:{index}")
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for index in range(3)
    )
    population = SimpleNamespace(groups=groups)

    first = _select_pro_anchor_groups(population, "frozen-anchor-salt")
    second = _select_pro_anchor_groups(population, "frozen-anchor-salt")

    assert first == second
    assert set(first) == set(CAPABILITY_SENSITIVE_FAMILIES)
    assert len(set(first.values())) == len(CAPABILITY_SENSITIVE_FAMILIES)


def _flash_report_values(*, information_passed: bool) -> dict[str, object]:
    interval = ConfidenceInterval(lower=0.0, point=0.0, upper=0.0)
    gates = tuple(
        InformationGate(
            gate_id=f"gate:{index}",
            observed=0.0,
            requirement=">=0",
            passed=information_passed,
        )
        for index in range(9)
    )
    cells = tuple(
        MultiTierInformationCell(
            model_arm=ExplorerArm.FLASH,
            runtime_arm=runtime,
            primary_families=("finance.calculation_chain",),
            primary_tiers_by_family={
                "finance.calculation_chain": tuple(DifficultyTier)
            },
            task_count=1,
            rollout_count=5,
            mean_success_rate=0.0,
            boundary_task_fraction=0.0,
            residual_information_eigenvalues=tuple(0.0 for _ in CAPABILITY_AXES),
            residual_numerical_rank=0,
            residual_effective_rank=0.0,
            residual_condition_number=1.0,
            general_factor_fraction=1.0,
            marginal_axis_information={axis: 0.0 for axis in CAPABILITY_AXES},
            marginal_axis_intervals={axis: interval for axis in CAPABILITY_AXES},
            informative_axis_count=0,
            family_information_share={
                family: 0.0 for family in CAPABILITY_SENSITIVE_FAMILIES
            },
            group_information_share={"group:test": 0.0},
            maximum_family_information_share=0.0,
            maximum_group_information_share=0.0,
            primary_aligned_family_count=1,
            gates=gates,
            passed=information_passed,
        )
        for runtime in (
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
        )
    )
    return {
        "contract_id": "contract:v25.12",
        "population_id": "population:v25.12",
        "requested_rollout_count": 630,
        "recorded_rollout_count": 630,
        "primary_rollout_count": 540,
        "secondary_diagnostic_rollout_count": 90,
        "information_cells": cells,
        "technical_resolution_rate": 1.0,
        "technical_status": "passed",
        "all_information_cells_ready": information_passed,
        "flash_information_ready": information_passed,
        "failure_codes": (() if information_passed else ("information:scripted_tool",)),
        "outcome_set_hash": "outcomes:v25.12",
        "api_call_count": 630,
        "total_model_tokens": 63_000,
        "estimated_cost_usd": 1.0,
        "pro_stage_authorized": information_passed,
        "next_permitted_stage": (
            "pro_sparse_anchor"
            if information_passed
            else "flash_support_or_task_redesign_only"
        ),
    }


def test_flash_information_failure_blocks_pro_stage() -> None:
    values = _flash_report_values(information_passed=False)
    provisional = FinanceMultiTierFlashReport.model_construct(
        report_id="pending",
        **values,
    )
    report = FinanceMultiTierFlashReport(
        report_id=multitier_flash_report_id(provisional),
        **values,
    )

    assert report.pro_stage_authorized is False
    assert report.next_permitted_stage == "flash_support_or_task_redesign_only"

    invalid = dict(values)
    invalid["pro_stage_authorized"] = True
    with pytest.raises(ValidationError, match="Flash stage transition is inconsistent"):
        FinanceMultiTierFlashReport(report_id="forged", **invalid)
