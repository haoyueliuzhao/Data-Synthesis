"""V50 metadata-only retirement inheritance and fail-closed ownership tests."""

import copy
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v50_inheritance")


def authority():
    return dict(
        user_consent="改为GPU0单卡完成全部（推荐）",
        time_limits_removed=True,
        automatic_recovery_authorized=True,
        unknown_feedback_retry_allowed=False,
        total_worker_limit_removed=False,
        max_gpu_workers=1,
        independent_total_worker_limit=1,
        max_workers_per_gpu=1,
        effective_device_capacity=1,
        allowed_gpu_indices=[0],
        steady_gpu_indices=[0],
        steady_max_gpu_workers=1,
        temporary_gpu0_full251_train_only=False,
        single_gpu0_authorized=True,
        final_device_authorization=subject.entry(subject.FINAL_DEVICE_AUTHORIZATION_RECORD),
        resource_retirement_authorized=True,
        host_ram_runtime_hard_gates_unchanged=True,
        fixed_gpu_reservation_authorized=True,
    )


@pytest.fixture(scope="module")
def real_frontier(tmp_path_factory):
    root = tmp_path_factory.mktemp("v50_metadata") / "fresh_root"
    parent = Path(subject.checked(subject.DEFAULT_HANDOFF_RECORD)["parent_root"])
    original = Path.read_bytes

    def metadata_only(path):
        assert path.suffix != ".pt", "metadata inheritance cannot load actual Tensor bytes"
        return original(path)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subject, "ROOT", root)
        patch.setattr(Path, "read_bytes", metadata_only)
        value = subject.inspect_parent_handoff(root, parent, authorization_body=authority())
    assert not root.exists(), "preview must not create the new episode"
    return SimpleNamespace(root=root, parent=parent, value=value)


def test_actual_retirement_frontier_uses_current_committed_state(real_frontier):
    value = real_frontier.value
    assert value["schema"] == subject.SCHEMA
    assert value["remaining_optimizer_updates"] == 1050
    assert value["remaining_outer_updates"] == 3
    assert value["Full251_actual_training_restart_step"] == 1334
    assert value["Full251_training_first_if_incomplete"] is True
    assert value["Full251_initial_training_complete"] is False
    assert value["GPU1_returned"] is True
    latest = {(row["seed"], row["arm"]): row for row in value["latest_checkpoints"]}
    assert latest[(251, "Full")]["step"] == 1334
    assert value["Full251_actual_training_checkpoint"] == latest[(251, "Full")]["reference"]
    assert value["GPU5_returned"] is True
    assert all(item["seed"] != 251 for item in value["context_inheritances"])
    assert value["superseded_interrupted_training_contexts"]


def test_actual_saved_prefixes_not_live_observed_counts(real_frontier):
    rows = {(row["seed"], row["arm"]): row for row in real_frontier.value["context_inheritances"]}
    for coordinate, cursor, total in (((389, "C-only"), 240, 419), ((389, "Full"), 210, 540)):
        item = rows[coordinate]
        replay = item["replay_resume"]
        assert replay["inherited_response_count"] == cursor
        assert replay["total_response_count"] == total
        assert replay["remaining_response_count"] == total - cursor
        assert replay["parent_saved_prefix_replayed_again"] is False
        assert all(
            item["stage_bindings"][key]["protocol_scope"] == "parent"
            for key in (*subject.SHARDS, "virtual_point")
        )
    assert Path(rows[(389, "Full")]["replay_resume"]["checkpoint"]["path"]).is_relative_to(
        real_frontier.parent
    )
    assert not Path(rows[(389, "C-only")]["replay_resume"]["checkpoint"]["path"]).is_relative_to(
        real_frontier.parent
    )


def test_actual_retirement_preserves_feedback_dose_and_six_endpoint_seals(real_frontier):
    value = real_frontier.value
    budget = value["remaining_scientific_budget"]
    assert len(value["completed_evaluations"]) == 6
    assert budget["pending_sealed_feedback_episodes"] == 1400
    assert budget["future_first_sampling_feedback_episodes"] == 700
    assert budget["remaining_new_feedback_episodes"] == 700
    assert budget["remaining_endpoint_answers"] == 3441
    assert budget["reserved_partial_feedback_episodes"] == 0
    assert value["original_accounting_reset"] is False
    assert value["inherited_resource_wait_seconds"] >= 105003
    assert all(
        row["inherited_compute_seconds"] >= row["earlier_inherited_compute_seconds"]
        for row in value["context_inheritances"]
    )
    assert value["max_gpu_workers"] == value["independent_total_worker_limit"] == 1
    assert value["allowed_gpu_indices"] == [0]
    assert value["steady_gpu_indices"] == [0]
    assert value["steady_max_gpu_workers"] == 1
    assert value["total_worker_limit_removed"] is False


def test_actual_manual_retirement_is_explicit_not_automatic_reclassification(real_frontier):
    audit = real_frontier.value["safe_recovery_audit"]
    assert audit["allowed"] is True
    assert audit["reason"] == "explicit_user_resource_retirement_at_actual_durable_boundaries"
    assert audit["unknown_failure_retry"] is False
    assert audit["old_manual_stop_reclassified"] is False
    assert len(audit["interrupted_stages"]) == 3
    assert {row["recovery_kind"] for row in audit["interrupted_stages"]} == {
        "pre_cuda_wait_no_model_or_response",
        "ordered_actual_response_boundary",
        "actual_committed_training_state",
    }
    assert real_frontier.value["explicit_manual_retirement_not_automatic_failure_retry"] is True
    assert real_frontier.value["initial_known_failure_exception_applied"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_gpu_workers", 4),
        ("independent_total_worker_limit", None),
        ("total_worker_limit_removed", True),
        ("allowed_gpu_indices", [0, 1, 5]),
        ("steady_gpu_indices", [0, 5]),
        ("steady_max_gpu_workers", 2),
        ("max_workers_per_gpu", 2),
        ("effective_device_capacity", 8),
        ("temporary_gpu0_full251_train_only", True),
        ("unknown_feedback_retry_allowed", True),
        ("resource_retirement_authorized", False),
        ("host_ram_runtime_hard_gates_unchanged", False),
    ],
)
def test_resource_retirement_authority_cannot_silently_expand_scope(key, value):
    body = authority()
    body[key] = value
    with pytest.raises(ValueError, match="retirement authority required"):
        subject._authorization(subject.ROOT, body=body)


def test_superseded_gpu5_choice_cannot_authorize_new_gpu0_episode():
    body = authority()
    body["final_device_authorization"] = subject.entry(
        subject.DEFAULT_HANDOFF_RECORD.parent.parent / "authorization/record.json"
    )
    with pytest.raises(ValueError, match="latest user-confirmed"):
        subject._authorization(subject.ROOT, body=body)


def test_latest_gpu0_authority_is_separate_from_unchanged_historical_stop():
    final = subject.checked(subject.FINAL_DEVICE_AUTHORIZATION_RECORD)
    old = subject.read_ref(final["original_stop_authorization"])
    assert final["allowed_gpu_indices"] == [0]
    assert old["steady_gpu_indices"] == [5]
    assert old["gpu0_endpoint_generation_allowed"] is False
    assert final["supersedes_gpu0_retire_after_Full251"] is True
    assert final["historical_stop_records_rewritten"] is False
    assert subject._authorization(subject.ROOT, body=authority())["preview_only"] is True


@pytest.mark.parametrize(
    "receipts,expected",
    [
        ([15], True),
        ([15, 15], True),
        ([dict(signal_number=15), dict(signal_number=15)], True),
        ([], False),
        ([9], False),
        ([15, 2], False),
        ([dict(signal_number=15), dict(signal_number=9)], False),
    ],
)
def test_sigterm_receipts_allow_multiple_own_cooperative_relays_not_other_signals(
    receipts, expected
):
    assert subject._sigterm_receipts(receipts) is expected


@pytest.mark.parametrize(
    "mutation",
    [
        "controller_failure",
        "not_empty",
        "auto_after_stop",
        "wrong_birth",
        "unknown_gpu1_error",
        "gpu1_cuda",
        "wrong_gpu5_checkpoint",
        "unknown_gpu0_error",
        "unrequested_worker",
        "v49_successor_still_allowed",
    ],
)
def test_initial_retirement_rejects_unknown_or_non_durable_state(monkeypatch, mutation):
    receipt = subject.checked(subject.DEFAULT_HANDOFF_RECORD)
    parent = Path(receipt["parent_root"])
    original_checked, original_read = subject.checked, subject.read_ref

    def mutate(path, value):
        value = copy.deepcopy(value)
        path = str(path)
        if mutation == "controller_failure" and path == str(parent / "failure/record.json"):
            value["error_type"], value["error"] = "ValueError", "numerical mismatch"
        elif mutation == "not_empty" and path == str(parent / "queue/status.json"):
            value["active_children"] = [dict(pid=1)]
        elif mutation == "auto_after_stop" and path == receipt["supervisor_closeout"]["path"]:
            value["automatic_recovery_after_manual_stop"] = True
        elif (
            mutation == "wrong_birth"
            and path == receipt["supervisor_actual_controller_exit"]["path"]
        ):
            value["birth"] = "wrong-process"
        elif (
            mutation == "unknown_gpu1_error"
            and "/c_only/" in path
            and path.endswith("replay_R3/failure/record.json")
        ):
            value["error_type"] = "RuntimeError"
        elif (
            mutation == "gpu1_cuda"
            and "/c_only/" in path
            and path.endswith("pre_cuda_wait/status.json")
        ):
            value["cuda_initialized"] = True
        elif (
            mutation == "wrong_gpu5_checkpoint"
            and "/full/" in path
            and "/seed389/" in path
            and path.endswith("replay_R3/failure/record.json")
        ):
            value["durable_replay_checkpoint"]["cursor"] += 1
        elif (
            mutation == "unknown_gpu0_error"
            and "/seed251/" in path
            and path.endswith("train/failure/record.json")
        ):
            value["error_type"] = "OutOfMemoryError"
        elif mutation == "unrequested_worker" and path == str(subject.DEFAULT_HANDOFF_RECORD):
            value["authorized_worker_launches"] = value["authorized_worker_launches"][:2]
        elif mutation == "v49_successor_still_allowed" and path.endswith(
            "handoff/release_authority/record.json"
        ):
            value["successor_launch_allowed"] = True
        return value

    monkeypatch.setattr(subject, "checked", lambda path: mutate(path, original_checked(path)))
    monkeypatch.setattr(subject, "read_ref", lambda ref: mutate(ref["path"], original_read(ref)))
    protocol = subject.checked(parent / "protocol/record.json")
    with pytest.raises((ValueError, FileNotFoundError)):
        subject._read_retirement_handoff(parent, protocol, subject.DEFAULT_HANDOFF_RECORD)


def test_future_automatic_recovery_keeps_manual_stop_terminal(tmp_path, monkeypatch):
    root = tmp_path / "v50"
    monkeypatch.setattr(subject, "ROOT", root)
    protocol = dict(
        schema=subject.PROTOCOL_SCHEMA,
        output_root=str(root),
        supervision_root=str(root),
        id="p",
    )
    records = {
        root / "protocol/record.json": protocol,
        root / "queue/status.json": dict(
            active_children=[], protocol_id="p", phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME"
        ),
        root / "failure/record.json": dict(
            protocol_id="p",
            phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME",
            stop_error=None,
            actual_progress_audit_error=None,
            error="explicit safe stop requested",
            error_type="DurablePause",
        ),
        root / "launch_01/record.json": dict(pid=1, birth="1"),
        root / "actual_final_progress/record.json": dict(
            endpoint_scores_or_answers_read=False, original_state_or_feedback_modified=False
        ),
    }
    monkeypatch.setattr(subject, "checked", lambda path: records[Path(path)])
    monkeypatch.setattr(subject, "entry", lambda path: dict(path=str(path)))
    monkeypatch.setattr(subject, "file_ref", lambda path: dict(path=str(path)))
    monkeypatch.setattr(subject, "read_ref", lambda ref: records[Path(ref["path"])])
    monkeypatch.setattr(subject.old, "_stopped", lambda launch: None)
    value = subject.validate_safe_recovery(root)
    assert value["allowed"] is False
    assert value["reason"] == "manual_stop_is_terminal"
