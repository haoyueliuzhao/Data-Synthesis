from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.executable_support import (
    AlternativeValidPath,
    AlternativeValidPathCatalog,
    EvidenceSupportLattice,
    TypedAnswerProjectionContract,
    alternative_valid_path_catalog_id,
    alternative_valid_path_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_support_audit import (
    CONDITIONAL_METRIC_DEFINITIONS,
    V26ExecutableSupportAuditReport,
    build_v26_executable_support_audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_NO_API = (
    PACKAGE_ROOT / "artifacts" / "vtdo_experiment" / "finance_v26_42_no_api_joint_scaffold_20260817"
)
SOURCE_STATISTICAL = (
    PACKAGE_ROOT
    / "artifacts"
    / "vtdo_experiment"
    / "finance_v26_53_failure_cascade_trace_audit_20260818"
    / "report.json"
)


@pytest.fixture(scope="module")
def built_audits(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("v26_executable_support")
    first = root / "first"
    second = root / "second"
    for output in (first, second):
        build_v26_executable_support_audit(
            run_id="finance_v26_54_test",
            source_no_api_dir=SOURCE_NO_API,
            source_statistical_audit_path=SOURCE_STATISTICAL,
            output_dir=output,
        )
    return first, second


def _load_rows(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, list)
    return value


def test_v26_executable_support_replays_current_blockers(
    built_audits: tuple[Path, Path],
) -> None:
    first, _ = built_audits
    report = V26ExecutableSupportAuditReport.model_validate_json(
        (first / "report.json").read_text(encoding="utf-8")
    )

    assert report.task_count == 24
    assert report.public_witness_pass_count == 18
    assert report.typed_answer_projection_bound_count == 0
    assert report.evidence_lattice_bound_count == 0
    assert report.mechanism_necessity_pass_count == 0
    assert report.alternative_path_catalog_pass_count == 0
    assert report.capability_measurement_eligible_count == 0
    assert report.vtdo_multistate_eligible_count == 0
    assert report.target_mechanism_task_counts == {
        "context_conditioned_action": 8,
        "semantic_reconciliation": 8,
        "failure_recovery": 4,
        "state_dependent_stopping": 4,
    }
    assert report.context_wrong_action_irreparable_pass_count == 0
    assert report.reconciliation_normalized_ref_consumed_pass_count == 0
    assert report.status == "blocked"
    assert report.next_permitted_stage == "capability_task_or_scaffold_redesign_only"
    assert report.conditional_metric_definitions == CONDITIONAL_METRIC_DEFINITIONS
    assert report.model_api_calls == report.gpu_jobs == 0
    assert report.production_contribution == 0


def test_public_witness_failures_are_typed_task_contract_defects(
    built_audits: tuple[Path, Path],
) -> None:
    first, _ = built_audits
    witnesses = _load_rows(first / "public_executable_witnesses.json")
    failed = [item for item in witnesses if not item["full_validity_passed"]]

    assert len(failed) == 6
    assert all(
        "required_normalization_tool_not_allowed" in item["failure_reasons"] for item in failed
    )
    assert all(
        set(step["tool_id"] for step in item["steps"]) <= set(item["allowed_tools"])
        for item in witnesses
    )
    passed = [item for item in witnesses if item["full_validity_passed"]]
    assert len(passed) == 18
    assert all(item["hidden_from_model"] for item in passed)
    assert all(not item["model_owned_path"] for item in passed)


def test_compiler_witness_does_not_count_as_vtdo_path(
    built_audits: tuple[Path, Path],
) -> None:
    first, _ = built_audits
    catalogs = _load_rows(first / "alternative_valid_path_catalogs.json")

    assert all(item["status"] == "blocked" for item in catalogs)
    assert all(item["paths"] == [] for item in catalogs)
    assert all(item["compiler_witness_count"] in {0, 1} for item in catalogs)
    assert all(
        "compiler_witness_is_not_model_owned" in item["failure_reasons"] for item in catalogs
    )


def test_new_detail_artifacts_replay_byte_identically(
    built_audits: tuple[Path, Path],
) -> None:
    first, second = built_audits
    names = (
        "typed_answer_projection_contracts.json",
        "public_executable_witnesses.json",
        "public_witness_observations.json",
        "evidence_support_lattices.json",
        "mechanism_necessity_artifacts.json",
        "alternative_valid_path_catalogs.json",
        "task_support_compilations.json",
        "report.json",
    )

    for name in names:
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_answer_projection_rejects_parallel_source_specs(
    built_audits: tuple[Path, Path],
) -> None:
    first, _ = built_audits
    payload = _load_rows(first / "typed_answer_projection_contracts.json")[0]
    payload["view_bindings"][0]["source_spec_hash"] = "parallel-source"

    with pytest.raises(ValidationError, match="different sources"):
        TypedAnswerProjectionContract.model_validate(payload)


def test_exact_evidence_equality_requires_uniqueness_proof(
    built_audits: tuple[Path, Path],
) -> None:
    first, _ = built_audits
    payload = _load_rows(first / "evidence_support_lattices.json")[0]
    payload["exact_equality_required"] = True

    with pytest.raises(ValidationError, match="uniqueness proof"):
        EvidenceSupportLattice.model_validate(payload)


def _path(index: int, *, state: str | None = None) -> AlternativeValidPath:
    values = {
        "witness_id": f"witness:{index}",
        "trajectory_hash": f"trajectory:{index}",
        "model_owned_decision_signature": f"decision:{index}",
        "behavior_signature": f"behavior:{index}",
        "quotient_state_id": state or f"state:{index}",
        "scaffold_surface_signature": "same-surface",
    }
    provisional = AlternativeValidPath.model_construct(path_id="pending", **values)
    return AlternativeValidPath(
        path_id=alternative_valid_path_id(provisional),
        **values,
    )


def test_vtdo_catalog_requires_three_distinct_quotient_states() -> None:
    paths = tuple(_path(index) for index in range(3))
    values = {
        "task_id": "task:test",
        "paths": paths,
        "compiler_witness_count": 1,
        "scaffold_surface_only_path_count": 0,
        "status": "passed",
        "failure_reasons": (),
    }
    provisional = AlternativeValidPathCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    catalog = AlternativeValidPathCatalog(
        catalog_id=alternative_valid_path_catalog_id(provisional),
        **values,
    )
    assert catalog.status == "passed"

    collision_paths = (_path(0, state="one-state"), _path(1, state="one-state"), _path(2))
    collision_values = {**values, "paths": collision_paths}
    collision_provisional = AlternativeValidPathCatalog.model_construct(
        catalog_id="pending",
        **collision_values,
    )
    collision_values["catalog_id"] = alternative_valid_path_catalog_id(collision_provisional)
    with pytest.raises(ValidationError, match="status is inconsistent"):
        AlternativeValidPathCatalog.model_validate(collision_values)


def test_historical_oracle_reference_is_not_a_public_witness() -> None:
    rows = _load_rows(SOURCE_NO_API / "joint" / "compiled_proof_artifacts.json")
    for item in rows:
        reference_tools = {
            step["tool_name"]
            for step in item["reference_trajectory"]["steps"]
            if step["tool_name"] is not None
        }
        allowed_tools = set(item["task"]["public"]["allowed_tools"])
        assert reference_tools == {
            "oracle_evidence.read",
            "operation_program.execute",
            "operation_oracle.verify",
        }
        assert reference_tools.isdisjoint(allowed_tools)
