from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_outcome_authority_independent_audit as audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_outcome_authority_independent_audit_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
EXTERNAL_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/5775d6da-6ef0-47e6-8bd3-c5e7ef08047e/pasted-text.txt"
)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, models.IndependentAuditReport]:
    output = tmp_path_factory.mktemp("v26-196") / "formal"
    report = audit.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=EXTERNAL_AUDIT,
        output_dir=output,
    )
    return output, report


def test_exact_external_authorization_and_v195_freeze(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    authorization = _load(output / "external_independent_audit_authorization.json")
    freeze = _load(output / "v26_195_source_and_artifact_freeze_audit.json")
    assert authorization["audit_sha256"] == audit.EXPECTED_EXTERNAL_AUDIT_SHA256
    assert authorization["audit_byte_count"] == audit.EXPECTED_EXTERNAL_AUDIT_BYTES
    assert freeze["source_commit"] == audit.AUDITED_SOURCE_COMMIT
    assert freeze["source_tree"] == audit.AUDITED_SOURCE_TREE
    assert freeze["artifact_commit"] == audit.AUDITED_ARTIFACT_COMMIT
    assert freeze["artifact_tree"] == audit.AUDITED_ARTIFACT_TREE
    assert freeze["formal_file_count"] == 403
    assert freeze["formal_byte_count"] == 2_300_542
    assert report.v195_formal_rebuild_passed is True


def test_detached_source_rebuild_matches_all_403_files(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, _ = built
    rebuild = _load(output / "v26_195_formal_rebuild_audit.json")
    assert rebuild["detached_source_commit_match"] is True
    assert rebuild["detached_source_tree_match"] is True
    assert rebuild["rebuilt_file_count"] == rebuild["exact_byte_match_count"] == 403
    assert rebuild["exact_sha256_match_count"] == 403
    assert rebuild["canonical_json_count"] == 402
    assert rebuild["provider_calls"] == 0


def test_all_16_reachable_terminals_expose_the_same_first_production_seam(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    totality = _load(output / "production_terminal_totality_audit.json")
    controls = totality["controls"]
    assert len(controls) == 16
    assert {item["target_terminal_kind"] for item in controls} == set(audit.REACHABLE_TERMINALS)
    assert totality["actual_old_raw_result_control_count"] == 16
    assert totality["production_terminal_to_fresh_outcome_success_count"] == 0
    assert totality["failed_control_count"] == 16
    assert totality["gate_passed"] is False
    assert all(item["observed_terminal_value"] == "fixture_complete" for item in controls)
    assert all(item["actual_raw_written"] and item["actual_result_written"] for item in controls)
    assert all(item["raw_before_result"] for item in controls)
    assert all(not item["fresh_typed_writer_reached"] for item in controls)
    assert all(not item["fresh_trace_reconstructed"] for item in controls)
    assert all(not item["fresh_outcome_reconstructed"] for item in controls)
    assert totality["python_escape_count"] == 0
    assert totality["pydantic_escape_count"] == 0
    assert totality["value_error_escape_count"] == 0
    assert report.production_terminal_totality_passed is False


def test_two_not_applicable_terminals_remain_outside_empirical_denominator(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    exclusion = _load(output / "not_applicable_terminal_exclusion_audit.json")
    assert set(exclusion["terminal_kinds"]) == {
        "policy_horizon_exhausted",
        "measurement_support_exit",
    }
    assert exclusion["empirical_admission_attempt_count"] == 2
    assert exclusion["empirical_admission_rejection_count"] == 2
    assert exclusion["empirical_denominator_entry_count"] == 0
    assert report.not_applicable_empirical_entry_count == 0


def test_external_parent_controls_reject_but_legal_online_ingress_is_absent(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    parent = _load(output / "online_authorization_parent_audit.json")
    assert parent["missing_parent_rejected"] is True
    assert parent["forged_parent_rejected"] is True
    assert parent["self_declared_parent_rejected"] is True
    assert parent["legal_parent_valid_for_independent_audit"] is True
    assert parent["legal_parent_accepted_by_online_precredential_guard"] is False
    assert parent["online_precredential_guard_exists"] is False
    assert parent["six_contract_identity_change_count"] == 0
    assert parent["credential_lookup_count"] == 0
    assert parent["client_construction_count"] == 0
    assert report.external_online_authorization_ingress_passed is False


def test_failed_audit_blocks_online_and_authorizes_only_first_seam_repair(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    decision = _load(output / "independent_audit_decision.json")
    transition = _load(output / "prospective_transition.json")
    static = _load(output / "static_audit.json")
    assert report.decision == (
        "fresh_outcome_authority_independent_audit_failed_at_terminal_to_persistence_integration"
    )
    assert report.online_development_execution_authorized is False
    assert decision["first_failed_gate"] == "production_terminal_to_fresh_outcome_totality"
    assert transition["next_stage"] == models.REPAIR_STAGE
    assert transition["online_execution_authorized"] is False
    assert transition["source_task_or_manifest_change_authorized"] is False
    assert transition["six_outcome_contract_semantic_change_authorized"] is False
    assert transition["qa_change_authorized"] is False
    assert static["passed_count"] == 12
    assert static["failed_count"] == 2


def test_immutable_output_does_not_replace_existing_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_immutable_artifact_directory(output, {"report.json": b"{}\n"})
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_second_complete_build_is_byte_identical(
    built: tuple[Path, models.IndependentAuditReport],
    tmp_path: Path,
) -> None:
    first, _ = built
    second = tmp_path / "second"
    audit.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=EXTERNAL_AUDIT,
        output_dir=second,
    )
    expected = {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    observed = {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert observed == expected
