from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_fixed_fixture_independent_audit import models
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture_independent_audit.audit import (
    IndependentAuditError,
    build_independent_audit,
    validate_written_artifacts,
    write_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/b8f8d6e2-a8aa-41bf-8a5a-b291b0f8536b/pasted-text.txt"
)


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def products() -> dict[str, Any]:
    commit = _git("rev-parse", "HEAD^{commit}")
    tree = _git("rev-parse", f"{commit}^{{tree}}")
    return build_independent_audit(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=commit,
        source_tree=tree,
    )


def test_exact_external_authority_and_candidate_freeze(products: dict[str, Any]) -> None:
    assert len(products["external_review_bytes"]) == models.EXTERNAL_REVIEW_BYTE_COUNT
    assert hashlib.sha256(products["external_review_bytes"]).hexdigest() == (
        models.EXTERNAL_REVIEW_SHA256
    )
    assert products["operator_directive_bytes"] == models.OPERATOR_DIRECTIVE.encode()
    freeze = products["candidate_freeze"]
    assert (freeze["file_count"], freeze["total_bytes"]) == (88, 217_567)
    assert (freeze["manifest_member_count"], freeze["manifest_member_bytes"]) == (
        87,
        201_416,
    )
    assert freeze["manifest_id"] == models.CANDIDATE_MANIFEST_ID
    assert freeze["artifact_root"] == models.CANDIDATE_ROOT_ID
    assert freeze["candidate_historical_next_stage_authorized"] is False


def test_detached_rebuild_and_dynamic_durability_are_observed(
    products: dict[str, Any],
) -> None:
    detached = products["detached_rebuild"]
    assert detached["saved_file_count"] == detached["rebuilt_file_count"] == 88
    assert detached["saved_bytes"] == detached["rebuilt_bytes"] == 217_567
    assert detached["path_matches"] == detached["sha256_matches"] == 88
    assert detached["actual_byte_matches"] == 88
    assert detached["manifest_member_matches"] == 87
    dynamic = products["dynamic_runtime"]
    assert dynamic["callback_count"] == 10
    assert dynamic["open_create_exclusive_count"] == 20
    assert dynamic["envelope_file_fsync_count"] == 10
    assert dynamic["envelope_directory_fsync_count"] == 10
    assert dynamic["receipt_file_fsync_count"] == 10
    assert dynamic["receipt_directory_fsync_count"] == 10
    assert dynamic["disk_reread_verified_count"] == 10
    assert dynamic["callback_after_receipt_directory_fsync_count"] == 10
    assert dynamic["callback_before_admission_count"] == 0


def test_selection_and_all_runtime_parents_are_independently_reconstructed(
    products: dict[str, Any],
) -> None:
    selection = products["selection"]
    assert tuple(selection["selected_row_ids"]) == models.SELECTED_ROW_IDS
    assert tuple(selection["selected_case_ids"]) == (
        "branch_hii_2014_q2_2014_q4",
        "branch_hii_2014_q1_2014_q3",
    )
    assert selection["future_reasoning_outcome_fields_read"] == ()
    parent = products["parent"]
    assert parent["runtime_object_count"] == parent["runtime_actual_byte_matches"] == 62
    assert parent["state_count"] == 12
    assert parent["envelope_count"] == parent["receipt_count"] == 10
    assert parent["action_execution_count"] == parent["observation_count"] == 10
    assert parent["update_count"] == 10
    assert parent["candidate_reconstruction_helper_calls"] == 0


def test_actions_program_validity_and_depth_are_recomputed(products: dict[str, Any]) -> None:
    audit = products["semantic"]
    assert audit["fixture_count"] == 2
    assert audit["d0_d3_action_recomputations"] == 8
    assert audit["program_count"] == 2
    assert audit["program_node_count"] == audit["program_nodes_replayed"] == 16
    assert audit["qa_valid_count"] == 2
    assert audit["trajectory_valid_count"] == 2
    assert audit["qualified_count"] == 2
    assert audit["semantic_depth_distribution"] == {"3": 2}
    assert audit["reasoning_depth_distribution"] == {"4": 2}
    assert audit["evidence_integration_depth_distribution"] == {"4": 2}
    assert audit["correction_depth_distribution"] == {"0": 2}
    assert audit["critical_decision_coverage_distribution"] == {"1.0": 2}
    assert audit["candidate_execution_audit_used_as_oracle"] is False


def test_interventions_and_attacks_reject_without_callback(products: dict[str, Any]) -> None:
    intervention = products["intervention"]
    assert tuple(row["name"] for row in intervention["rows"]) == (models.INTERVENTION_NAMES * 2)
    assert (intervention["attempted_count"], intervention["rejected_count"]) == (10, 10)
    assert intervention["accepted_count"] == 0
    negative = products["negative"]
    assert tuple(row["name"] for row in negative["rows"]) == models.ATTACK_NAMES
    assert (negative["attempted_count"], negative["rejected_count"]) == (9, 9)
    assert negative["accepted_count"] == negative["attack_callback_calls"] == 0
    assert negative["no_replace_original_bytes_retained"] is True


def test_helper_scope_gate_decision_and_transition(products: dict[str, Any]) -> None:
    source = products["audit_source_binding"]
    assert source["member_count"] == 5
    assert source["all_current_bytes_equal_committed_bytes"] is True
    assert source["helper_boundary_passed"] is True
    assert source["candidate_helper_imports"] == 0
    assert source["candidate_semantic_helper_calls"] == 0
    scope = products["scope"]
    assert scope["provider_calls"] == scope["credential_lookups"] == 0
    assert scope["third_fixture_rows"] == scope["same_task_multitrajectory_rows"] == 0
    assert scope["qa_release_objects"] == scope["vtdo_rows"] == 0
    assert scope["old_mainline_paused"] is True
    gate = products["gate"]
    assert tuple(gate["gates"]) == models.GATE_NAMES
    assert gate["passed_count"] == 9 and gate["failed_count"] == 0
    assert all(gate["gates"].values())
    assert products["decision"]["decision"] == models.DECISION
    assert products["transition"]["next_stage_authorized"] is False
    assert products["transition"]["prospective_next_stage"] == (models.PROSPECTIVE_NEXT_STAGE)


def test_writer_is_reproducible_and_manifest_is_self_excluding(
    products: dict[str, Any], tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_artifacts(products, left)
    commit = _git("rev-parse", "HEAD^{commit}")
    rebuilt = build_independent_audit(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=commit,
        source_tree=_git("rev-parse", f"{commit}^{{tree}}"),
    )
    write_artifacts(rebuilt, right)
    assert _files(left) == _files(right)
    summary = validate_written_artifacts(left)
    files = _files(left)
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert summary["file_count"] == len(files) == 24
    assert summary["manifest_member_count"] == len(files) - 1
    assert summary["manifest_member_matches"] == len(files) - 1
    assert files["external_review.txt"] == REVIEW.read_bytes()
    assert files["operator_directive.txt"] == models.OPERATOR_DIRECTIVE.encode()


def test_changed_external_review_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(REVIEW.read_bytes() + b"\n")
    with pytest.raises(IndependentAuditError, match="external audit bytes differ"):
        build_independent_audit(
            repo_root=ROOT,
            external_audit_path=changed,
            source_commit=_git("rev-parse", "HEAD^{commit}"),
            source_tree=_git("rev-parse", "HEAD^{tree}"),
        )
