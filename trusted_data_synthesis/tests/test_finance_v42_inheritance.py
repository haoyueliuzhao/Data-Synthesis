"""CPU-only explicit-recovery authorization, time and immutable task contracts."""

import importlib
import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from test_finance_v38_inheritance import write_record
from test_finance_v42_task_overlay import data, overlay  # noqa: F401

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v42_inheritance")


def at(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def timing_binding(root, stage, start, end, deadline):
    directory = root / stage
    write_record(directory / "launch/record.json", dict(at=at(start), deadline_epoch=deadline))
    write_record(
        directory / "exit/record.json", dict(at=at(end), elapsed_worker_wall_seconds=end - start)
    )
    return dict(
        protocol_scope="parent",
        immediate_parent_local=True,
        launch=subject.entry(directory / "launch/record.json"),
        exit=subject.entry(directory / "exit/record.json"),
    )


def test_failed_stage_time_keeps_snapshot_polling_and_original_deadline(tmp_path):
    context = dict(feedback=dict(mode="first_sampling"))
    complete = dict(shard00=timing_binding(tmp_path, "shard00", 100, 200, 1200))
    failed = dict(distribution=timing_binding(tmp_path, "distribution", 300, 500, 500))
    snapshot = dict(at=at(300), compute_seconds=134.2)
    value = subject.recovery_timing(context, complete, failed, snapshot)
    assert value["worker_interval_union_seconds"] == 300
    assert value["inherited_compute_seconds"] == 335
    assert value["unaccounted_interrupted_seconds_added"] == 200
    assert value["phase_deadlines_epoch"]["distribution"] == 500
    assert value["phase_budgets_reset"] is False


def test_interrupted_parallel_time_uses_union_not_worker_sum(tmp_path):
    context = dict(feedback=dict(mode="first_sampling"))
    interrupted = {
        "shard01": timing_binding(tmp_path, "shard01", 300, 500, 1200),
        "shard02": timing_binding(tmp_path, "shard02", 350, 550, 1200),
    }
    value = subject.recovery_timing(context, {}, interrupted, dict(at=at(400), compute_seconds=150))
    assert value["unaccounted_interrupted_seconds_added"] == 150
    assert value["inherited_compute_seconds"] == 300


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_consent", ""),
        ("global_resource_wait_budget_seconds", 86400),
        ("global_resource_wait_budget_seconds", 172800),
        ("distribution_window_seconds", 14400),
        ("unknown_request_reexecution_authorized", False),
    ],
)
def test_authorization_cannot_silently_enlarge_or_omit_exception(tmp_path, field, value):
    body = dict(
        user_consent="批准",
        global_resource_wait_budget_seconds=129600,
        distribution_window_seconds=7200,
        unknown_request_reexecution_authorized=True,
    )
    body[field] = value
    with pytest.raises(ValueError, match="explicit bounded"):
        subject._validate_parent_restart(tmp_path / "new", tmp_path / "old", {}, None, body)


def test_preview_authorization_cannot_initialize_a_scientific_episode():
    assert "authorization_body" in inspect.signature(subject.inspect_parent_recovery).parameters
    assert (
        "authorization_body" not in inspect.signature(subject.initialize_parent_recovery).parameters
    )


def test_partial_inventory_binds_same_shard_91_and_never_reads_tensor(overlay, monkeypatch):  # noqa: F811
    f = overlay
    plan_path = f.parent_root.parent / "task_plan/record.json"
    write_record(plan_path, {key: value for key, value in f.data.plan.items() if key != "id"})
    context = dict(
        f.context,
        task_plan=subject.entry(plan_path),
        math_context_id=subject.digest(f.data.binding),
    )
    original = Path.read_bytes

    def bounded(path):
        assert path.suffix != ".pt", "registration must not deserialize/read tensor payloads"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", bounded)
    value = subject.inspect_partial_task_overlay(context, f.directory, 12345)
    assert value["parent_task_ids"] == f.parent_ids
    assert value["local_task_ids"] == f.local_ids
    assert value["parent_tasks"] == 277 and value["new_tasks"] == 467
    assert value["class_deadline_epoch"] == 12345
    assert value["allowed_new_stages"] == ["shard01", "shard02", "shard03"]
    assert value["partial_task_rows_restorable"] is False


def test_partial_inventory_does_not_accept_any_different_277_subset(overlay):  # noqa: F811
    f = overlay
    plan_path = f.parent_root.parent / "task_plan/record.json"
    write_record(plan_path, {key: value for key, value in f.data.plan.items() if key != "id"})
    context = dict(
        f.context,
        task_plan=subject.entry(plan_path),
        math_context_id=subject.digest(f.data.binding),
    )
    source = f.parent_root / f.parent_ids[-1]
    source.rename(f.parent_root / f.local_ids[-1])
    with pytest.raises(ValueError, match="exactly 186 shard00 plus 91"):
        subject.inspect_partial_task_overlay(context, f.directory, 12345)


def test_feedback_budget_deducts_completed_uncommitted_and_partial_cohort(tmp_path):
    bindings = []
    for index in range(6):
        directory = tmp_path / str(index) / "virtual_point"
        write_record(
            directory / "result/record.json",
            dict(
                context_id=f"c{index}",
                stage="virtual_point",
                new_feedback_episodes=700,
            ),
        )
        bindings.append(
            dict(
                directory=str(directory),
                protocol_scope="parent",
                result=subject.entry(directory / "result/record.json"),
            )
        )
    unfinished = [dict(stage_bindings=dict(virtual_point=bindings[-1]))]
    unfinished += [dict(stage_bindings=dict(virtual_point=dict(protocol_scope="current")))] * 2
    progress = dict(
        pending_sealed_feedback_episodes=0,
        future_first_sampling_outers=7,
        future_first_sampling_feedback_episodes=4900,
    )
    budget = subject.scientific_budget(progress, bindings, unfinished, [{}] * 5)
    assert budget["already_generated_first_sampling_feedback_episodes"] == 4200
    assert budget["already_generated_uncommitted_feedback_episodes"] == 700
    assert budget["pending_sealed_feedback_episodes"] == 700
    assert budget["known_sealed_uncommitted_feedback_episodes"] == 700
    assert budget["known_sealed_uncommitted_coordinates"] == [
        dict(seed=251, arm="Full", step=894, episodes=700)
    ]
    assert budget["future_first_sampling_outers"] == 5
    assert budget["future_first_sampling_feedback_episodes"] == 3500
    nominal = budget["legacy_snapshot_not_sampling_authority"]
    assert nominal["future_first_sampling_outers"] == 7
    assert nominal["future_first_sampling_feedback_episodes"] == 4900
    assert nominal["pending_sealed_feedback_episodes"] == 0
    assert nominal["sampling_authority"] is False
    assert progress["future_first_sampling_feedback_episodes"] == 4900
    assert budget["completed_partial_feedback_episodes"] == 450
    assert budget["remaining_partial_feedback_episodes"] == 250
    assert budget["first_sampling_unstarted_feedback_episodes"] == 3500
    assert budget["remaining_new_feedback_episodes"] == 3750
    assert budget["remaining_endpoint_answers"] == 4588


def test_unregistered_failed_stage_cannot_acquire_recovery_authority(tmp_path):
    with pytest.raises(ValueError, match="unregistered failed-stage"):
        subject.inspect_interrupted_stage(
            tmp_path, {}, dict(seed=389, arm="Full", step=894), "replay_R3", protocol_ref={}
        )
