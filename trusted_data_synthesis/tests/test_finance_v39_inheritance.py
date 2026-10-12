"""CPU-only V39 handoff metadata tests; no Tensor deserialization or GPU use."""

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
inheritance = importlib.import_module("finqa_v39_inheritance")
fixtures = importlib.import_module("test_finance_v38_inheritance")
payload, resources, write_record = fixtures.payload, fixtures.resources, fixtures.write_record


def stamp(seconds):
    return datetime.fromtimestamp(1791800000 + seconds, timezone.utc).isoformat()


def rewrite(path, **changes):
    return write_record(path, json.loads(path.read_text()) | changes)


def write_checkpoint(path, seed, arm, step):
    path.mkdir(parents=True, exist_ok=True)
    (path / "state.pt").write_bytes(b"fake scientific Tensor: never read")
    write_record(
        path / "record.json",
        dict(
            seed=seed,
            arm=arm,
            step=step,
            phase="step",
            state_sha256="a" * 64,
            actual_state_digest="b" * 64,
        ),
    )
    return dict(
        path=str(path),
        record=inheritance.file_ref(path / "record.json"),
        state=dict(path=str(path / "state.pt"), sha256="a" * 64),
        seed=seed,
        arm=arm,
        step=step,
        phase="step",
        actual_state_digest="b" * 64,
    )


def stage(parent, directory, protocol, context, name, start, end, task_plan):
    common = dict(protocol_id=protocol["id"], context_id=context["id"], stage=name)
    write_record(
        directory / "launch/record.json",
        common
        | dict(
            at=stamp(start),
            pid=99999999,
            birth="missing",
            gpu_index=4,
            gpu_uuid="gpu4",
            deadline_epoch=1791800000
            + start
            + protocol["stage_limits_seconds"][inheritance.phase_name(context, name)],
        ),
    )
    write_record(
        directory / "exit/record.json",
        common
        | dict(
            at=stamp(end),
            returncode=0,
            stop_requested=False,
            elapsed_worker_wall_seconds=end - start,
        ),
    )
    result = common | dict(
        status="COMPLETE",
        model_released=True,
        gpu_index=4,
        gpu_uuid="gpu4",
        resources=resources(name),
        API_calls=0,
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
        replayed_responses=0,
        model_optimizer_rng_buffers_unchanged=True,
    )
    if name in inheritance.SHARDS:
        tasks = task_plan["assignments"][inheritance.SHARDS.index(name)]["task_ids"]
        result.update(
            task_ids=tasks, task_count=len(tasks), class_task_calls=len(tasks), reused_task_ids=[]
        )
    else:
        result.update(
            denominator=700, response_count=400, payload=payload(directory, context["id"], name)
        )
    if name == "virtual_point":
        result.update(
            feedback_mode="first_sampling",
            new_feedback_episodes=700,
            new_sampling_calls=850,
            scoring_calls=700,
        )
    if name == "replay_R3":
        result.update(complete_replay=True, current_point_only=True, replayed_responses=400)
    write_record(directory / "result/record.json", result)


@pytest.fixture
def migration(tmp_path, monkeypatch):
    parent, root = tmp_path / "production/recovery_01", tmp_path / "production/gpu6_resume_01"
    protocol = write_record(
        parent / "protocol/record.json",
        dict(
            schema="v38_same_point_admission_recovery_protocol.v1",
            gpu_uuids={"4": "gpu4"},
            resource_wait_budget_seconds=86400,
            outer_compute_budget_seconds=86400,
            evaluation_root=str(tmp_path / "evaluation"),
            stage_limits_seconds=dict(
                class_gradients=43200,
                virtual_first_sampling=43200,
                virtual_existing=7200,
                replay_R3=57600,
                distribution=7200,
                train=28800,
            ),
        ),
    )
    write_record(parent / "implementation/record.json", dict(schema="fixture_source_seal"))
    write_record(parent / "launch_01/record.json", dict(pid=99999998, birth="gone"))
    directory = parent / "contexts/seed389/full/step0298_outer"
    task_plan = write_record(
        directory / "task_plan/record.json",
        dict(
            assignments=[dict(task_ids=[f"task{i}"]) for i in range(4)],
            task_ids=[f"task{i}" for i in range(4)],
        ),
    )
    for i in range(4):
        cache = directory / f"task_cache/task{i:04d}"
        write_record(cache / "record.json", dict(task_id=f"task{i}"))
        (cache / "gradient.pt").write_bytes(b"fake gradient: only stat")
    arms = []
    for seed in inheritance.SEEDS:
        for arm, key in inheritance.ARM_KEYS.items():
            ref = write_checkpoint(
                tmp_path / f"training/seed{seed}/{key}/step0298_step", seed, arm, 298
            )
            arms.append(
                dict(seed=seed, arm=arm, checkpoint=ref, step=298, due_outer=arm != "Static")
            )
    ref = next(row["checkpoint"] for row in arms if row["seed"] == 389 and row["arm"] == "Full")
    context = write_record(
        directory / "context/record.json",
        dict(
            schema="v37_actual_production_context.v1",
            run_root=str(directory),
            outer_root=str(directory),
            seed=389,
            arm="Full",
            step=298,
            due_outer=True,
            checkpoint=ref,
            feedback=dict(mode="first_sampling", denominator=700),
            sources={},
            execution_binding={},
            task_cache_root=str(directory / "task_cache"),
            task_plan=inheritance.entry(directory / "task_plan/record.json"),
        ),
    )
    for i, name in enumerate(inheritance.SHARDS):
        stage(parent, directory / name, protocol, context, name, i * 10, i * 10 + 80, task_plan)
    stage(
        parent, directory / "virtual_point", protocol, context, "virtual_point", 150, 200, task_plan
    )
    stop = dict(
        phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME",
        error_type="DurablePause",
        error="explicit safe stop requested",
        stop_error=None,
        actual_progress_audit_error=None,
        automatic_retry=False,
        completed_task_response_and_step_artifacts_preserved=True,
    )
    write_record(parent / "failure/record.json", stop | dict(protocol_id=protocol["id"]))
    queue = dict(
        protocol_id=protocol["id"],
        active_children=[],
        pilot_accepted=True,
        accepted_new_optimizer_updates=0,
        accepted_new_outer_updates=0,
        global_external_resource_wait_seconds=200,
        completed_evaluation_coordinates=[],
        completed_training_coordinates=[],
        **stop,
    )
    (parent / "queue").mkdir()
    (parent / "queue/status.json").write_text(json.dumps(queue))
    (directory / "queue").mkdir()
    (directory / "queue/status.json").write_text(
        json.dumps(
            dict(
                protocol_id=protocol["id"],
                context_id=context["id"],
                compute_seconds=145.5,
                active_children=[],
            )
        )
    )
    write_record(
        parent / "actual_final_progress/record.json",
        dict(
            schema="v37_actual_B_CPU_state_snapshot.v1",
            endpoint_scores_or_answers_read=False,
            original_state_or_feedback_modified=False,
            arms=arms,
            remaining_physical_updates=5810,
            remaining_outers=15,
            completed_physical_updates=5812,
            completed_outers=9,
            pending_sealed_feedback_episodes=2100,
            future_first_sampling_outers=12,
            future_first_sampling_feedback_episodes=8400,
        ),
    )
    handoff = parent / "handoff/record.json"
    write_record(
        handoff,
        dict(
            status="COMPLETE",
            parent_root=str(parent),
            parent_protocol_id=protocol["id"],
            controller_exited=True,
            children_exited=True,
            global_resource_wait_seconds=240.1,
            parent_pause=inheritance.file_ref(parent / "failure/record.json"),
            parent_final_queue=queue,
            actual_progress=inheritance.entry(parent / "actual_final_progress/record.json"),
        ),
    )
    # Opening checkpoint Tensors is a contract failure, even for these tiny mocks.
    original = Path.read_bytes

    def guarded(path):
        assert path.suffix != ".pt", "Tensor read during metadata-only migration"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    return SimpleNamespace(
        root=root,
        parent=parent,
        directory=directory,
        protocol=protocol,
        context=context,
        handoff=handoff,
        task_plan=task_plan,
    )


def test_register_alias_preserves_original_ids_and_parent_bytes(migration):
    m = migration
    before = (m.directory / "context/record.json").read_bytes()
    value = inheritance.initialize_parent_migration(m.root, m.parent, m.handoff)
    plan = dict(
        output_root=str(m.root),
        inheritance=inheritance.entry(m.root / "inheritance/record.json"),
        id="new-protocol",
    )
    item = value["context_inheritances"][0]
    target = Path(item["new_context_directory"])
    assert inheritance.resolve_origin_context(target, plan) == m.directory
    assert inheritance.stage_directory(target, plan, "shard00") == m.directory / "shard00"
    assert inheritance.stage_directory(target, plan, "replay_R3") == target / "replay_R3"
    assert item["original_context_id"] == m.context["id"]
    assert item["inherited_compute_seconds"] == 160  # union 110 + 50, not 4 * 80 + 50
    assert value["inherited_resource_wait_seconds"] == 241
    assert value["parent_pause"] == inheritance.entry(m.parent / "failure/record.json")
    assert value["remaining_scientific_budget"]["remaining_new_feedback_episodes"] == 7700
    assert (
        value["remaining_scientific_budget"]["already_generated_uncommitted_feedback_episodes"]
        == 700
    )
    assert before == (m.directory / "context/record.json").read_bytes()
    seen = []
    inheritance.require_upstream(
        target,
        m.context,
        plan,
        "replay_R3",
        SimpleNamespace(
            check_result=lambda owner, stage, result, tasks: seen.append((owner["id"], stage))
        ),
    )
    assert seen == [(m.protocol["id"], "virtual_point")]
    with pytest.raises(ValueError, match="must not be rerun"):
        inheritance.require_upstream(target, m.context, plan, "virtual_point", SimpleNamespace())
    with pytest.raises(ValueError, match="already registered"):
        inheritance.initialize_parent_migration(m.root, m.parent, m.handoff)


@pytest.mark.parametrize("change", ["failure", "partial", "exit", "protocol", "live"])
def test_incomplete_failed_foreign_or_live_stage_rejects(migration, monkeypatch, change):
    m = migration
    directory = m.directory / "shard02"
    if change == "failure":
        write_record(directory / "failure/record.json", dict(error="no retry"))
    elif change == "partial":
        (directory / "result/record.json").unlink()
    elif change == "exit":
        rewrite(directory / "exit/record.json", returncode=1)
    elif change == "protocol":
        rewrite(directory / "result/record.json", protocol_id="foreign")
    else:
        monkeypatch.setattr(
            inheritance.old, "_birth", lambda pid: "missing" if pid == 99999999 else None
        )
    with pytest.raises(ValueError):
        inheritance.inspect_parent_migration(m.root, m.parent, m.handoff)
    assert not m.root.exists()


def test_partial_class_phase_cannot_reuse_parent_cache_for_writes(migration):
    m = migration
    # Remove a complete fake stage and downstream phase, leaving three shards.
    for name in ("shard03", "virtual_point"):
        for file in sorted((m.directory / name).rglob("*"), reverse=True):
            if file.is_file():
                file.unlink()
            else:
                file.rmdir()
    with pytest.raises(ValueError, match="partial class phase"):
        inheritance.inspect_parent_migration(m.root, m.parent, m.handoff)


@pytest.mark.parametrize(
    "field,value",
    [("controller_exited", False), ("status", "RUNNING"), ("global_resource_wait_seconds", 10)],
)
def test_handoff_must_include_actual_exit_and_all_wait(migration, field, value):
    m = migration
    rewrite(m.handoff, **{field: value})
    with pytest.raises(ValueError):
        inheritance.inspect_parent_migration(m.root, m.parent, m.handoff)


def test_original_phase_absolute_deadline_and_larger_compute_snapshot_preserved(migration):
    m = migration
    path = m.directory / "queue/status.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | dict(compute_seconds=190.1)))
    value = inheritance.inspect_parent_migration(m.root, m.parent, m.handoff)
    item = value["context_inheritances"][0]
    assert item["inherited_compute_seconds"] == 191
    assert item["phase_deadlines_epoch"]["class_gradients"] == 1791800000 + 43200
    assert item["phase_deadlines_epoch"]["virtual_first_sampling"] == 1791800150 + 43200
    assert "replay_R3" not in item["phase_deadlines_epoch"]


def test_snapshot_counters_cannot_increase_remaining_budget(migration):
    m = migration
    rewrite(m.parent / "actual_final_progress/record.json", remaining_physical_updates=5811)
    rewrite(
        m.handoff, actual_progress=inheritance.entry(m.parent / "actual_final_progress/record.json")
    )
    with pytest.raises(ValueError, match="dose changed"):
        inheritance.inspect_parent_migration(m.root, m.parent, m.handoff)


def test_new_native_context_does_not_resolve_parent(migration):
    m = migration
    inheritance.initialize_parent_migration(m.root, m.parent, m.handoff)
    plan = dict(
        output_root=str(m.root), inheritance=inheritance.entry(m.root / "inheritance/record.json")
    )
    new = m.root / "contexts/seed251/full/step0894_outer"
    write_record(
        new / "context/record.json",
        dict(schema="v37_actual_production_context.v1", run_root=str(new), outer_root=str(new)),
    )
    assert inheritance.resolve_origin_context(new, plan) == new
    assert inheritance.stage_directory(new, plan, "train") == new / "train"


def test_wait_interval_union_rejects_invalid_values():
    assert inheritance.union_seconds([(1, 10), (2, 8), (10, 12), (20, 25)]) == 16
    with pytest.raises(ValueError):
        inheritance.union_seconds([(2, float("nan"))])


def test_scientific_failure_cannot_be_reclassified_as_authorized_pause(migration):
    m = migration
    rewrite(m.parent / "failure/record.json", error="GPU resource gate failed")
    rewrite(m.handoff, parent_pause=inheritance.entry(m.parent / "failure/record.json"))
    with pytest.raises(ValueError, match="clean DurablePause"):
        inheritance.inspect_parent_migration(m.root, m.parent, m.handoff)


def test_stale_context_child_is_checked_against_successful_exit(migration):
    m = migration
    launch = inheritance.checked(m.directory / "virtual_point/launch/record.json")
    child = {key: launch[key] for key in ("stage", "pid", "birth", "gpu_index", "gpu_uuid")}
    path = m.directory / "queue/status.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | dict(active_children=[child])))
    assert inheritance.inspect_parent_migration(m.root, m.parent, m.handoff)["context_inheritances"]
    child["birth"] = "foreign"
    path.write_text(json.dumps(json.loads(path.read_text()) | dict(active_children=[child])))
    with pytest.raises(ValueError, match="stale snapshot child"):
        inheritance.inspect_parent_migration(m.root, m.parent, m.handoff)
