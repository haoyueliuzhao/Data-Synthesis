from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_independent_audit as audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_independent_audit_models as models,
)


@pytest.fixture(scope="module")
def products(tmp_path_factory: pytest.TempPathFactory) -> models.BuildProducts:
    package_root = Path(__file__).resolve().parents[1]
    output = tmp_path_factory.mktemp("v26_182_independent") / "artifacts"
    return audit.build(package_root=package_root, output_dir=output)


def test_exact_a934_source_and_all_v181_formal_artifacts_replay(
    products: models.BuildProducts,
) -> None:
    freeze = products.freeze

    assert freeze.audited_commit == audit.AUDITED_COMMIT
    assert freeze.source_file_match_count == freeze.source_file_count == 347
    assert freeze.entry_source_file_match_count == freeze.entry_source_file_count == 4
    assert freeze.formal_artifact_match_count == freeze.formal_artifact_count == 15
    assert freeze.current_worktree_artifact_match_count == 15
    assert freeze.report_detail_binding_match_count == 14
    assert len(freeze.auditor_source_files) == 3


def test_independent_controls_freeze_five_failed_online_gates(
    products: models.BuildProducts,
) -> None:
    assert products.report.independent_control_count == 10
    assert products.report.admitted_attack_count == 8
    assert products.report.semantic_state_loss_control_count == 2
    assert products.completed_invalid.property_failure_count == 2
    assert products.diagnostic_empirical.admitted_attack_count == 2
    assert products.failure_locus.admitted_attack_count == 2
    assert products.artifact_bytes.admitted_attack_count == 1
    assert products.parent_revalidation.admitted_attack_count == 3
    assert products.decision.passed_gate_count == 3
    assert products.decision.failed_gate_count == 5
    assert not products.decision.online_execution_authorized
    assert products.decision.online_execution_admission == ("BLOCKED_FAILED_INDEPENDENT_AUDIT")


def test_mixed_completion_and_diagnostic_controls_are_exact(
    products: models.BuildProducts,
) -> None:
    mixed = products.completed_invalid.observations
    assert {
        (
            item.evidence["source_base_valid"],
            item.evidence["source_mechanism_qualified"],
        )
        for item in mixed
    } == {(True, False), (False, True)}
    assert all(
        (
            item.evidence["projected_base_valid"],
            item.evidence["projected_mechanism_qualified"],
        )
        == (False, False)
        for item in mixed
    )
    diagnostic = products.diagnostic_empirical.observations
    assert {item.evidence["terminal_kind"] for item in diagnostic} == {
        "policy_horizon_exhausted",
        "measurement_support_exit",
    }
    assert all(item.evidence["denominator_count"] == 192 for item in diagnostic)
    assert all(item.evidence["terminal_count_in_denominator"] == 1 for item in diagnostic)


def test_forged_loci_byte_replacement_and_model_construct_parents_are_admitted(
    products: models.BuildProducts,
) -> None:
    assert all(
        item.evidence["terminal_kind"] == "completed_qualified"
        and item.evidence["final_qualified_valid"] is True
        and item.production_entry_admitted
        for item in products.failure_locus.observations
    )
    byte_control = products.artifact_bytes.observations[0]
    assert byte_control.evidence["bytes_changed"] is True
    assert byte_control.evidence["raw_descriptor_binds_sha256"] is False
    assert byte_control.evidence["result_descriptor_binds_sha256"] is False
    assert byte_control.production_entry_admitted
    assert all(
        item.evidence["direct_parent_revalidation_rejected"] is True
        and item.evidence["production_estimator_admitted"] is True
        for item in products.parent_revalidation.observations
    )


def test_report_detail_bytes_and_content_identities_are_replayable(
    products: models.BuildProducts,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    output_root = next(
        path
        for path in tmp_path_factory.getbasetemp().glob("v26_182_independent*/artifacts")
        if path.is_dir()
    )
    assert {path.name for path in output_root.iterdir()} == {
        *audit.DETAIL_FILENAMES,
        "report.json",
    }
    report = models.IndependentAuditReport.model_validate(
        json.loads((output_root / "report.json").read_bytes())
    )
    for binding in report.detail_files:
        path = output_root / Path(binding.relative_path).name
        payload = path.read_bytes()
        assert len(payload) == binding.byte_count
        assert audit._sha256(payload) == binding.sha256


def test_independent_identity_and_immutable_writer_fail_closed(
    products: models.BuildProducts,
    tmp_path: Path,
) -> None:
    changed = products.report.model_dump(mode="python")
    changed["online_execution_authorized"] = True
    with pytest.raises(ValidationError):
        models.IndependentAuditReport.model_validate(changed)

    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        audit._write_immutable_directory(existing, {"report.json": b"{}\n"})
    assert sentinel.read_text(encoding="utf-8") == "keep"
