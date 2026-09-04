from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture import models
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.preflight import (
    build_qa_reasoning_fixed_fixture_preflight,
    validate_written_artifacts,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import (
    DurableArtifactWriter,
    FixedFixtureRuntimeError,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/aaa0cf77-e2a9-4f0f-9a41-bbb8978664f3/pasted-text.txt"
)


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("qa_reasoning_fixed_fixture") / "formal"
    commit = _git("rev-parse", "HEAD^{commit}")
    tree = _git("rev-parse", f"{commit}^{{tree}}")
    build_qa_reasoning_fixed_fixture_preflight(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=commit,
        source_tree=tree,
        output_directory=output,
    )
    return output


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes())


def _jsonl(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(json.loads(line) for line in path.read_text().splitlines())


def test_external_authority_and_selection_are_exact(built: Path) -> None:
    assert hashlib.sha256(REVIEW.read_bytes()).hexdigest() == models.EXTERNAL_REVIEW_SHA256
    selection = _json(built / "selection_contract.json")
    rows = _jsonl(built / "selected_fixture_rows.jsonl")
    assert selection["selected_row_ids"] == list(models.SELECTED_ROW_IDS)
    assert tuple(row["row_id"] for row in rows) == models.SELECTED_ROW_IDS
    assert rows[0]["numeric_relationship"] == "mixed_sign"
    assert rows[1]["near_equal_growth"] is True


def test_two_complete_reasoning_trajectories_are_qualified(built: Path) -> None:
    audit = _json(built / "execution_audit.json")
    rows = audit["rows"]
    assert isinstance(rows, list)
    assert audit["fixture_count"] == 2
    assert audit["program_node_count"] == audit["program_nodes_replayed"] == 16
    assert audit["qa_valid_count"] == 2
    assert audit["trajectory_valid_count"] == 2
    assert audit["qualified_count"] == 2
    assert all(row["state_count"] == 6 for row in rows)
    assert all(row["reasoning_action_count"] == 5 for row in rows)
    assert all(row["observation_count"] == row["update_count"] == 5 for row in rows)


def test_durable_preaction_receipts_precede_every_dispatch(built: Path) -> None:
    audit = _json(built / "durable_preaction_commit_audit.json")
    receipts = audit["receipts"]
    assert isinstance(receipts, list)
    assert audit["envelope_count"] == 10
    assert audit["no_replace_count"] == 10
    assert audit["dispatch_after_durable_receipt_count"] == 10
    for receipt in receipts:
        events = (
            receipt["envelope_file_fsync_event"],
            receipt["envelope_directory_fsync_event"],
            receipt["receipt_file_fsync_event"],
            receipt["receipt_directory_fsync_event"],
            receipt["dispatch_event"],
        )
        assert tuple(sorted(events)) == events
        envelope = built / receipt["envelope_relative_path"]
        payload = envelope.read_bytes()
        assert len(payload) == receipt["envelope_byte_count"]
        assert hashlib.sha256(payload).hexdigest() == receipt["envelope_sha256"]


def test_validity_and_five_metrics_are_independently_reported(built: Path) -> None:
    rows = _jsonl(built / "reasoning_depth_metrics.jsonl")
    assert len(rows) == 2
    for row in rows:
        assert row["semantic_operation_depth"] == 3
        assert row["reasoning_depth"] == 4
        assert row["evidence_integration_depth"] == 4
        assert row["correction_depth"] == 0
        assert row["critical_decision_coverage"] == 1.0
        assert row["token_count_used_as_depth"] is False
        assert row["text_length_used_as_depth"] is False


def test_interventions_attacks_and_scope_fail_closed(built: Path) -> None:
    interventions = _json(built / "intervention_audit.json")
    attacks = _json(built / "negative_control_audit.json")
    scope = _json(built / "scope_boundary_audit.json")
    gate = _json(built / "gate_evaluation.json")
    assert interventions["registered_intervention_count"] == 10
    assert interventions["rejected_count"] == 10
    assert attacks["attempted_count"] == attacks["rejected_count"] == 9
    assert attacks["accepted_count"] == attacks["attack_dispatch_callback_calls"] == 0
    assert attacks["no_replace_original_bytes_retained"] is True
    assert scope["provider_calls"] == scope["credential_lookups"] == scope["gpu_jobs"] == 0
    assert scope["archive_expansion_rows"] == scope["new_task_registrations"] == 0
    assert scope["same_task_multitrajectory_rows"] == scope["qa_release_objects"] == 0
    assert gate["passed_count"] == 10
    assert gate["failed_count"] == 0
    gates = gate["gates"]
    assert isinstance(gates, dict)
    assert all(gates.values())


def test_complete_second_build_is_byte_identical(built: Path, tmp_path: Path) -> None:
    output = tmp_path / "formal"
    commit = _git("rev-parse", "HEAD^{commit}")
    tree = _git("rev-parse", f"{commit}^{{tree}}")
    build_qa_reasoning_fixed_fixture_preflight(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=commit,
        source_tree=tree,
        output_directory=output,
    )
    left = {
        path.relative_to(built): path.read_bytes() for path in built.rglob("*") if path.is_file()
    }
    right = {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    assert left == right
    validate_written_artifacts(output)


def test_existing_output_and_existing_file_are_not_replaced(built: Path, tmp_path: Path) -> None:
    writer = DurableArtifactWriter(built)
    with pytest.raises(FixedFixtureRuntimeError) as directory_error:
        writer.create_root()
    assert directory_error.value.stage == "runtime.output_directory_no_replace"

    fresh = DurableArtifactWriter(tmp_path / "writer")
    fresh.create_root()
    original = canonical_json_bytes({"value": "original"})
    fresh.write_bytes("object.json", original)
    with pytest.raises(FixedFixtureRuntimeError) as file_error:
        fresh.write_bytes("object.json", canonical_json_bytes({"value": "replacement"}))
    assert file_error.value.stage == "runtime.no_replace"
    assert fresh.read_bytes("object.json") == original
