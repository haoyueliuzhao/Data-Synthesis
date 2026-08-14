from __future__ import annotations

from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_confirmation import (  # noqa: E501
    EXPECTED_ROLLOUT_COUNT,
    FinanceSubmechanismConfirmationContract,
    FinanceSubmechanismConfirmationReport,
    SubmechanismConfirmationGate,
    _make_confirmation_gates,
    _population_disjointness,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    DIAGNOSTIC_RESPONSES,
    SubmechanismGeometryThresholds,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    RuntimeResolutionStage,
)


def test_confirmation_contract_rejects_development_runtime_stage() -> None:
    contract = FinanceSubmechanismConfirmationContract.model_construct(
        stage=RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
    )

    with pytest.raises(ValueError, match="another Runtime stage"):
        contract.validate_contract()


def test_confirmation_report_never_authorizes_pro_without_primary_geometry() -> None:
    gates = (
        SubmechanismConfirmationGate(
            gate_id="runtime",
            category="runtime",
            observed=1,
            requirement="=1",
            passed=True,
        ),
        SubmechanismConfirmationGate(
            gate_id="geometry",
            category="primary_geometry",
            observed=1,
            requirement="=1",
            passed=True,
        ),
    )
    report = FinanceSubmechanismConfirmationReport.model_construct(
        recorded_rollout_count=EXPECTED_ROLLOUT_COUNT,
        requested_rollout_count=EXPECTED_ROLLOUT_COUNT,
        gates=gates,
        runtime_measurement_ready=True,
        primary_information_geometry_confirmed=True,
        pro_sparse_anchor_authorized=False,
        diagnostic_spectra={item: SimpleNamespace() for item in DIAGNOSTIC_RESPONSES},
        next_permitted_stage="submechanism_confirmation_failed",
    )

    with pytest.raises(ValueError, match="Pro transition"):
        report.validate_report()


def test_confirmation_gates_require_the_five_replica_denominator() -> None:
    contract = SimpleNamespace(thresholds=SubmechanismGeometryThresholds())
    terminal = SimpleNamespace(
        api_transport_resolved=True,
        bounded_json_resolution_success=True,
        observation_replay_success=True,
        authority_integrity_success=True,
        runtime_pathology=False,
    )
    spectrum = SimpleNamespace(
        task_count=20,
        rollout_count=60,
        distinct_normalized_demand_count=20,
        nonzero_weight_task_count=20,
        boundary_task_fraction=1.0,
        residual_numerical_rank=7,
        residual_effective_rank=7.0,
        residual_condition_number=1.0,
        general_factor_fraction=0.0,
        informative_axis_count=7,
        maximum_parent_information_share=0.25,
    )

    gates = _make_confirmation_gates(
        contract,
        tuple(terminal for _ in range(60)),
        spectrum,
        complete_task_count=20,
    )

    failed = {item.gate_id for item in gates if not item.passed}
    assert failed == {
        "complete_rollout_denominator",
        "primary_geometry_rollout_denominator",
    }


def test_confirmation_population_detects_evidence_version_overlap() -> None:
    def population(
        task_id: str,
        evidence_id: str,
        evidence_version_id: str,
    ) -> SimpleNamespace:
        evidence = SimpleNamespace(
            evidence_id=evidence_id,
            evidence_version_id=evidence_version_id,
        )
        task = SimpleNamespace(
            artifact=SimpleNamespace(
                task=SimpleNamespace(task_id=task_id),
                public_corpus=SimpleNamespace(evidence=(evidence,)),
            ),
            source_semantic_signature=f"semantic:{task_id}",
        )
        return SimpleNamespace(tasks=(task,))

    observed = _population_disjointness(
        population("task:development", "evidence:development", "version:shared"),
        population("task:confirmation", "evidence:confirmation", "version:shared"),
    )

    assert observed == {
        "evidence": True,
        "evidence_version": False,
        "task": True,
        "semantic_signature": True,
    }
