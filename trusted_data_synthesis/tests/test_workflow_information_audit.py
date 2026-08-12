from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    RuntimeInformationThreshold,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_workflow_information_audit import (
    WORKFLOW_RUNTIME_ARMS,
    WorkflowInformationThresholds,
    WorkflowRuntimeDesignAudit,
    _InformationRow,
    _make_information_cell,
    _sha256,
    _verify_audit_contract_inputs,
)


def _one_hot(axis: str) -> tuple[float, ...]:
    return tuple(float(item == axis) for item in CAPABILITY_AXES)


def _design(
    runtime: CapabilityRuntimeArm,
    families: tuple[str, ...],
) -> WorkflowRuntimeDesignAudit:
    return WorkflowRuntimeDesignAudit(
        runtime_arm=runtime,
        selected_families=families,
        selected_tiers={
            family: DifficultyTier.FRONTIER for family in families
        },
        selected_binding_count=len(families) * 3,
        distinct_normalized_demand_count=len(families),
        model_visible_primary_families=families,
        host_controlled_primary_families=(),
        family_primary_axis_alignment={family: True for family in families},
        primary_aligned_family_count=len(families),
        minimum_primary_aligned_family_count=3,
        passed=True,
    )


def _rows(
    family_axes: tuple[tuple[str, str], ...],
    *,
    active_family: str | None = None,
) -> list[_InformationRow]:
    rows = []
    for family, axis in family_axes:
        for group in range(3):
            active = active_family is None or family == active_family
            realizations = (1, 1, 0, 0, 0) if active else (0, 0, 0, 0, 0)
            rows.append(
                _InformationRow(
                    task_artifact_id=f"task:{family}:{group}",
                    family=family,
                    group_id=f"group:{family}:{group}",
                    probability=sum(realizations) / len(realizations),
                    general_difficulty=5.0,
                    demand=_one_hot(axis),
                    realizations=realizations,
                )
            )
    return rows


def _test_thresholds() -> WorkflowInformationThresholds:
    return WorkflowInformationThresholds(
        by_runtime={
            CapabilityRuntimeArm.SCRIPTED_TOOL: RuntimeInformationThreshold(
                minimum_rank=3,
                minimum_effective_rank=2.0,
                maximum_condition_number=100.0,
                minimum_boundary_task_fraction=0.25,
                maximum_general_factor_fraction=0.85,
                minimum_informative_axis_count=3,
            ),
            CapabilityRuntimeArm.AUTONOMOUS_AGENT: RuntimeInformationThreshold(
                minimum_rank=4,
                minimum_effective_rank=3.0,
                maximum_condition_number=100.0,
                minimum_boundary_task_fraction=0.25,
                maximum_general_factor_fraction=0.85,
                minimum_informative_axis_count=4,
            ),
        },
        bootstrap_replicates=100,
    )


def test_balanced_multi_axis_workflow_information_passes() -> None:
    family_axes = (
        ("finance.multi_hop_retrieval_join", "retrieval"),
        ("finance.calculation_chain", "calculation"),
        ("finance.definition_reconciliation", "reconciliation"),
        ("finance.verification_sensitive_selection", "verification"),
        ("finance.recovery_guided_search", "recovery"),
    )
    families = tuple(family for family, _ in family_axes)

    cell = _make_information_cell(
        model=ExplorerArm.PRO,
        runtime=CapabilityRuntimeArm.SCRIPTED_TOOL,
        rows=_rows(family_axes),
        design=_design(CapabilityRuntimeArm.SCRIPTED_TOOL, families),
        thresholds=_test_thresholds(),
        seed=7,
    )

    assert cell.passed is True
    assert cell.residual_numerical_rank == 4
    assert cell.residual_effective_rank >= 3.9
    assert cell.informative_axis_count >= 5
    assert cell.maximum_family_information_share <= 0.21


def test_low_rank_family_dominated_workflow_information_fails_closed() -> None:
    family_axes = (
        ("finance.calculation_chain", "calculation"),
        ("finance.definition_reconciliation", "reconciliation"),
        ("finance.verification_sensitive_selection", "verification"),
        ("finance.recovery_guided_search", "recovery"),
    )
    families = tuple(family for family, _ in family_axes)

    cell = _make_information_cell(
        model=ExplorerArm.FLASH,
        runtime=CapabilityRuntimeArm.SCRIPTED_TOOL,
        rows=_rows(
            family_axes,
            active_family="finance.verification_sensitive_selection",
        ),
        design=_design(CapabilityRuntimeArm.SCRIPTED_TOOL, families),
        thresholds=_test_thresholds(),
        seed=11,
    )
    failed = {item.gate_id for item in cell.gates if not item.passed}

    assert cell.passed is False
    assert "residual_numerical_rank" in failed
    assert "family_information_dominance" in failed
    assert cell.maximum_family_information_share == pytest.approx(1.0)


def test_workflow_information_thresholds_reject_direct_runtime() -> None:
    thresholds = _test_thresholds()
    invalid = {
        **thresholds.by_runtime,
        CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL: (
            thresholds.by_runtime[CapabilityRuntimeArm.SCRIPTED_TOOL]
        ),
    }

    with pytest.raises(ValidationError, match="workflow Runtime"):
        WorkflowInformationThresholds(by_runtime=invalid)

    assert WORKFLOW_RUNTIME_ARMS == (
        CapabilityRuntimeArm.SCRIPTED_TOOL,
        CapabilityRuntimeArm.AUTONOMOUS_AGENT,
    )
    assert set(CAPABILITY_SENSITIVE_FAMILIES) >= {
        "finance.calculation_chain",
        "finance.verification_sensitive_selection",
    }


def test_workflow_information_frozen_input_hash_fails_on_mutation(tmp_path) -> None:
    paths = [tmp_path / name for name in ("contract.json", "report.json", "outcomes.jsonl")]
    for index, path in enumerate(paths):
        path.write_text(f"frozen:{index}\n", encoding="utf-8")
    contract = SimpleNamespace(
        localization_contract_path=str(paths[0]),
        localization_contract_sha256=_sha256(paths[0]),
        localization_report_path=str(paths[1]),
        localization_report_sha256=_sha256(paths[1]),
        localization_outcomes_path=str(paths[2]),
        localization_outcomes_sha256=_sha256(paths[2]),
    )

    _verify_audit_contract_inputs(contract)
    paths[2].write_text("mutated\n", encoding="utf-8")

    with pytest.raises(ValueError, match="frozen workflow information input changed"):
        _verify_audit_contract_inputs(contract)
