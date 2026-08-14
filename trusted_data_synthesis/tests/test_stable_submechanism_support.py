from __future__ import annotations

from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (  # noqa: E501
    CAPABILITY_AXES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_support import (
    FinanceStableSupportReport,
    StableSupportGate,
    _population_disjointness,
    _stable_rows,
)


def _gate(gate_id: str, category: str = "stable_geometry") -> StableSupportGate:
    return StableSupportGate(
        gate_id=gate_id,
        category=category,  # type: ignore[arg-type]
        observed=1.0,
        requirement=">=1",
        passed=True,
    )


def _population(
    *,
    evidence_id: str,
    evidence_version_id: str,
    task_id: str,
    semantic_signature: str,
    materializer_hash: str,
) -> SimpleNamespace:
    evidence = SimpleNamespace(
        evidence_id=evidence_id,
        evidence_version_id=evidence_version_id,
    )
    artifact = SimpleNamespace(
        task=SimpleNamespace(task_id=task_id),
        public_corpus=SimpleNamespace(evidence=(evidence,)),
    )
    task = SimpleNamespace(
        artifact=artifact,
        source_semantic_signature=semantic_signature,
        materializer_hash=materializer_hash,
    )
    return SimpleNamespace(tasks=(task,))


def test_stable_support_development_cannot_authorize_pro() -> None:
    report = FinanceStableSupportReport.model_construct(
        report_id="pending",
        stage="development",
        requested_rollout_count=480,
        recorded_rollout_count=480,
        gates=(_gate("runtime", "runtime"), _gate("geometry")),
        runtime_measurement_ready=True,
        capability_support_admitted=True,
        fresh_confirmation_authorized=True,
        pro_sparse_anchor_authorized=True,
        next_permitted_stage="pro_sparse_anchor_preparation",
        alignment_summary=None,
    )

    with pytest.raises(ValueError, match="Pro authorization is inconsistent"):
        report.validate_report()


def test_stable_rows_use_capability_contract_success_as_primary_response() -> None:
    task_id = "task:one"
    contract = SimpleNamespace(
        bindings=(SimpleNamespace(task_artifact_id=task_id, general_difficulty=0.5),),
        replicas=2,
        task_submechanism_ids={task_id: "submechanism:one"},
        task_parent_mechanism_ids={task_id: "parent:one"},
        task_instance_ids={task_id: "instance:one"},
        task_raw_capability_demands={
            task_id: {axis: 1.0 for axis in CAPABILITY_AXES}
        },
    )
    behaviors = tuple(
        SimpleNamespace(
            task_artifact_id=task_id,
            replicate=replicate,
            runtime_eligible=True,
            primary_valid_success=True,
            capability_contract_success=False,
        )
        for replicate in range(2)
    )

    rows, complete = _stable_rows(contract, behaviors)

    assert complete == {task_id}
    assert rows[0].realizations == (0, 0)


@pytest.mark.parametrize(
    ("field", "expected_overlap"),
    [
        ("evidence_id", "evidence"),
        ("evidence_version_id", "evidence_version"),
        ("task_id", "task"),
        ("semantic_signature", "semantic_signature"),
        ("materializer_hash", "submechanism_signature_instance"),
    ],
)
def test_population_disjointness_detects_each_frozen_identity(
    field: str,
    expected_overlap: str,
) -> None:
    values = {
        "evidence_id": "evidence:left",
        "evidence_version_id": "version:left",
        "task_id": "task:left",
        "semantic_signature": "semantic:left",
        "materializer_hash": "materializer:left",
    }
    right_values = {key: value.replace("left", "right") for key, value in values.items()}
    right_values[field] = values[field]

    result = _population_disjointness(_population(**values), _population(**right_values))

    assert result[expected_overlap] is False
    assert all(value for key, value in result.items() if key != expected_overlap)
