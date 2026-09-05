from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_multitrajectory_independent_audit import models
from trusted_synthesis.experiments.qa_reasoning_multitrajectory_independent_audit.audit import (
    IndependentAuditError,
    build_audit,
    files_at,
    freeze_candidate,
    helper_boundary,
    validate_manifest,
    write_formal,
)
from trusted_synthesis.experiments.qa_reasoning_multitrajectory_independent_audit.quotient import (
    audit_quotient,
    enumerate_schedules,
)
from trusted_synthesis.experiments.qa_reasoning_multitrajectory_independent_audit.semantics import (
    audit_trajectories,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/03bff3aa-a4fe-44d3-9903-a07aea4efd20/pasted-text.txt"
)


def git(value: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", value),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def build(target: Path) -> dict[str, Any]:
    return build_audit(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=git("HEAD"),
        source_tree=git("HEAD^{tree}"),
        output_directory=target,
    )


@pytest.fixture(scope="module")
def products(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return build(tmp_path_factory.mktemp("qa_current_independent") / "formal")


def test_only_current_candidate_rebuilt_with_exact_source(products: dict[str, Any]) -> None:
    rebuild = products["detached_rebuild_audit"]
    assert rebuild["actual_byte_matches"] == rebuild["rebuilt_files"] == 156
    assert rebuild["rebuilt_bytes"] == 602070
    assert rebuild["manifest_members_revalidated"] == 155
    assert rebuild["prior_independent_audit_builders_executed"] == 0
    sources = products["source_authority_audit"]
    assert sources["candidate_members"] == 13
    assert sources["audit_implementation"]["member_count"] == 6
    assert not sources["transitive_import_or_runtime_closure_claimed"]


def test_actual_callback_observes_predeclared_rules_and_own_receipts(
    products: dict[str, Any],
) -> None:
    probe = products["dynamic_durability_audit"]
    assert probe["callback_count"] == probe["own_envelope_receipt_pairs"] == 20
    assert probe["own_envelope_receipt_exclusive_creates"] == 40
    assert len({r["receipt_relative_path"] for r in probe["callbacks"]}) == 20
    for row in probe["callbacks"]:
        assert row["envelope_open_event"] < row["envelope_file_fsync_event"]
        assert row["envelope_file_fsync_event"] < row["envelope_directory_fsync_event"]
        assert row["envelope_directory_fsync_event"] < row["receipt_open_event"]
        assert row["receipt_open_event"] < row["receipt_file_fsync_event"]
        assert row["receipt_file_fsync_event"] < row["receipt_directory_fsync_event"]
        assert row["receipt_directory_fsync_event"] < row["callback_event"]
        assert len(row["receipt_sha256"]) == 64 and row["receipt_byte_count"] > 0
        assert all(
            r["directory_fsync_event"] < row["envelope_open_event"] for r in row["preregistration"]
        )


def test_five_node_dag_has_exactly_two_legal_complete_orders(products: dict[str, Any]) -> None:
    orders = enumerate_schedules()
    assert set(orders) == {("D0", "D1", "D2", "D3", "D4"), ("D0", "D2", "D1", "D3", "D4")}
    assert products["quotient_audit"]["permutations_enumerated"] == 120


def test_four_own_chains_and_programs_independently_recomputed(products: dict[str, Any]) -> None:
    audit = products["trajectory_reconstruction_audit"]
    assert audit["runtime_objects_reconstructed"] == 124
    assert audit["action_results_recomputed"] == 20
    assert audit["program_nodes_replayed"] == 32
    assert audit["qa_valid"] == audit["trajectory_valid"] == audit["qualified"] == 4
    assert all(result["replay_audit"]["independent_replay"] for result in products["results"])


def test_quotient_comparison_is_per_task_and_accepts_the_local_negative(
    products: dict[str, Any],
) -> None:
    audit = products["quotient_audit"]
    assert audit["saved_projection_byte_matches"] == 4
    assert audit["saved_partition_byte_match"]
    assert [row["distinct_quotient_classes"] for row in audit["per_task_rows"]] == [1, 1]
    assert audit["tasks_with_multiple_classes"] == 0
    assert audit["distinct_cross_task_classes"] == 2
    assert products["gate_evaluation"]["passed"] == 9
    assert products["gate_evaluation"]["failed"] == 0
    assert not products["gate_evaluation"]["multiple_quotient_classes_required_for_passing"]


def test_depths_keep_their_separate_meanings(products: dict[str, Any]) -> None:
    for result in products["results"]:
        depth = json.loads(canonical_json_bytes(result["depth"]))
        assert (
            depth["semantic_operation_depth"],
            depth["reasoning_depth"],
            depth["evidence_integration_depth"],
            depth["correction_depth"],
            depth["critical_decision_coverage"],
        ) == (3, 4, 4, 0, 1.0)


def test_ten_independent_current_boundary_controls_reject(products: dict[str, Any]) -> None:
    runtime = products["runtime_negative_audit"]
    quotient = products["quotient_audit"]
    assert runtime["attempted"] == runtime["rejected"] == 6
    assert runtime["single_object_rehashed_controls"] == 4
    assert not runtime["joint_full_chain_rehash_claimed"]
    assert quotient["negative_controls_rejected"] == 4
    assert quotient["negative_controls_accepted"] == runtime["accepted"] == 0


def test_saved_outcome_reports_are_not_semantic_oracles(products: dict[str, Any]) -> None:
    _, files = freeze_candidate(ROOT)
    for name in (
        "report.json",
        "gate_evaluation.json",
        "negative_audit.json",
        "independent_replays.jsonl",
    ):
        files[name] = b'{"untrusted_outcome": "deliberately_unusable"}'
    selection = json.loads(files["selection_audit.json"])
    files["selection_audit.json"] = canonical_json_bytes(
        {
            "selected_row_ids": selection["selected_row_ids"],
            "all_other_selection_fields": "deliberately_unusable",
        }
    )
    audit, results = audit_trajectories(repo_root=ROOT, candidate_files=files)
    quotient, _, _ = audit_quotient(candidate_files=files, results=results)
    assert audit["qualified"] == 4 and quotient["tasks_with_multiple_classes"] == 0
    assert helper_boundary()["passed"]


def test_complete_independent_second_build_matches_actual_bytes(
    products: dict[str, Any],
    tmp_path: Path,
) -> None:
    rebuilt = build(tmp_path / "rebuilt")
    actual = files_at(products["output_directory"])
    assert actual == files_at(rebuilt["output_directory"])
    validate_manifest(
        actual, products["manifest"]["manifest_id"], products["manifest"]["artifact_root"]
    )


def test_changed_review_invalid_source_and_output_replacement_fail_before_formal_write(
    products: dict[str, Any],
    tmp_path: Path,
) -> None:
    review = tmp_path / "changed.txt"
    review.write_bytes(REVIEW.read_bytes() + b"\n")
    target = tmp_path / "not_created"
    with pytest.raises(IndependentAuditError) as error:
        build_audit(
            repo_root=ROOT,
            external_audit_path=review,
            source_commit="0" * 40,
            source_tree="1" * 40,
            output_directory=target,
        )
    assert error.value.stage == "authorization.review" and not target.exists()
    with pytest.raises(IndependentAuditError):
        build_audit(
            repo_root=ROOT,
            external_audit_path=REVIEW,
            source_commit="0" * 40,
            source_tree="1" * 40,
            output_directory=target,
        )
    assert not target.exists()
    with pytest.raises(IndependentAuditError) as error:
        write_formal(products["output_directory"], {}, products["report"])
    assert error.value.stage == "output.no_replace"


def test_manifest_rejects_equal_length_member_mutation(products: dict[str, Any]) -> None:
    files = files_at(products["output_directory"])
    files["operator_directive.txt"] = b"x" * len(files["operator_directive.txt"])
    with pytest.raises(IndependentAuditError) as error:
        validate_manifest(
            files, products["manifest"]["manifest_id"], products["manifest"]["artifact_root"]
        )
    assert error.value.stage == "freeze.manifest_members"


def test_no_successor_expansion_or_mainline_execution(products: dict[str, Any]) -> None:
    scope = products["scope_audit"]
    assert scope["Provider_calls"] == scope["credential_lookups"] == scope["GPU_jobs"] == 0
    assert scope["new_task_cases"] == scope["new_schedule_variants"] == 0
    assert scope["mainline_executions"] == scope["historical_formal_writes"] == 0
    assert products["transition"]["next_stage_authorized"] is False
    assert products["transition"]["prospective_next_stage"] == models.NEXT_CANDIDATE
    assert not products["decision"]["global_semantic_uniqueness_claimed"]
