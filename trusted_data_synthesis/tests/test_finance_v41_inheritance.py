"""CPU-only resource-policy handoff contracts; never deserialize a tensor."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_finance_v38_inheritance import write_record
from test_finance_v39_inheritance import rewrite, stage

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
inheritance = importlib.import_module("finqa_v41_inheritance")


@pytest.fixture
def point(tmp_path):
    parent = tmp_path / "production/recovery_02"
    origin = tmp_path / "production/recovery_01/contexts/seed251/c_only/step1192_outer"
    directory = parent / "contexts/seed251/c_only/step1192_outer"
    root = parent.parent / "admission_relaxation_01"
    protocols = []
    for index in (38, 40):
        path = tmp_path / f"protocol{index}/record.json"
        protocol = write_record(
            path,
            dict(
                schema=f"fixture_v{index}",
                allowed_gpu_indices=list(range(8)) if index == 40 else [3, 4, 5, 7],
                gpu_uuids={str(i): f"gpu{i}" for i in range(8)},
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
        protocols.append((protocol, inheritance.entry(path)))
    tasks = [dict(index=i, task_id=f"t{i:04d}", shard=i % 4) for i in range(744)]
    task_ids = [row["task_id"] for row in tasks]
    assignments = [dict(task_ids=task_ids[i::4]) for i in range(4)]
    spec = [dict(name="p", shape=[1], numel=1)]
    plan = write_record(
        origin / "task_plan/record.json",
        dict(tasks=tasks, task_ids=task_ids, assignments=assignments, parameter_spec=spec),
    )
    task_binding = dict(actual_point="fixed", parameter_spec=spec)
    context = write_record(
        origin / "context/record.json",
        dict(
            schema="v37_actual_production_context.v1",
            seed=251,
            arm="C-only",
            step=1192,
            due_outer=True,
            run_root=str(origin),
            outer_root=str(origin),
            feedback=dict(mode="first_sampling"),
            task_plan=inheritance.entry(origin / "task_plan/record.json"),
            task_cache_root=str(origin / "task_cache"),
            task_binding=task_binding,
            math_context_id=inheritance.digest(task_binding),
            parameter_spec=spec,
        ),
    )
    bindings = {}
    for index, name in enumerate(inheritance.SHARDS):
        is_old = name == "shard02"
        owner, owner_ref = protocols[0 if is_old else 1]
        source = (origin if is_old else directory) / name
        stage(parent, source, owner, context, name, index * 100, index * 100 + 80, plan)
        gpu = 4 if is_old else 0
        for marker in ("launch", "result"):
            rewrite(source / marker / "record.json", gpu_index=gpu, gpu_uuid=f"gpu{gpu}")
        binding = inheritance.inspect_stage(
            source, owner, context, name, plan, protocol_ref=owner_ref
        )
        binding["immediate_parent_local"] = not is_old
        bindings[name] = binding
    overlay = dict(
        original_context_id=context["id"],
        parent_cache_root=context["task_cache_root"],
        local_cache_root=str(directory / "task_cache"),
        parent_task_ids=assignments[2]["task_ids"],
        local_task_ids=[task for i, task in enumerate(task_ids) if i % 4 != 2],
    )
    for task in tasks:
        cache = origin / "task_cache" if task["shard"] == 2 else directory / "task_cache"
        folder = cache / f"task{task['index']:04d}"
        folder.mkdir(parents=True)
        raw = b"fake tensor, never opened"
        (folder / "gradient.pt").write_bytes(raw)
        write_record(
            folder / "record.json",
            dict(
                schema="v35_complete_task_gradient.v1",
                complete_task=True,
                binding=task_binding,
                binding_sha256=context["math_context_id"],
                task_plan_id=plan["id"],
                task=task,
                parameter_spec=spec,
                gradient_sha256="a" * 64,
                gradient_bytes=len(raw),
            ),
        )
    item = dict(
        task_cache_overlay=overlay,
        inherited_compute_seconds=6785,
        phase_deadlines_epoch=dict(class_gradients=1791804320),
        phase_first_launch_epoch=dict(class_gradients=1791800000),
    )
    return SimpleNamespace(
        root=root,
        parent=parent,
        origin=origin,
        directory=directory,
        context=context,
        protocols=protocols,
        plan=plan,
        bindings=bindings,
        item=item,
        overlay=overlay,
    )


def test_all_eight_gpu_source_bound_to_own_protocol(point):
    p = point
    assert p.bindings["shard00"]["protocol_ref"] == p.protocols[1][1]
    assert p.bindings["shard02"]["protocol_ref"] == p.protocols[0][1]
    assert inheritance.read_ref(p.bindings["shard00"]["result"])["gpu_index"] == 0
    # UUID disagreement or an old protocol's forbidden device is not grandfathered.
    source = p.origin / "shard02"
    for marker in ("result", "launch"):
        rewrite(source / marker / "record.json", gpu_index=0, gpu_uuid="gpu0")
    with pytest.raises(ValueError, match="registered protocol"):
        inheritance.inspect_stage(
            source, p.protocols[0][0], p.context, "shard02", p.plan, protocol_ref=p.protocols[0][1]
        )


@pytest.mark.parametrize("marker", ["failure", "missing_exit", "nonzero_exit"])
def test_failed_partial_or_nonzero_stage_cannot_retry(point, marker):
    source = point.directory / "shard00"
    if marker == "failure":
        write_record(source / "failure/record.json", dict(error="test"))
    elif marker == "missing_exit":
        (source / "exit/record.json").unlink()
    else:
        rewrite(source / "exit/record.json", returncode=1)
    with pytest.raises(ValueError):
        inheritance.inspect_stage(
            source,
            point.protocols[1][0],
            point.context,
            "shard00",
            point.plan,
            protocol_ref=point.protocols[1][1],
        )


def test_completed_overlay_seals_exact_186_plus_558_without_tensor_reads(point, monkeypatch):
    original = Path.read_bytes

    def bounded(path):
        assert path.suffix != ".pt", "metadata handoff must not read a tensor"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", bounded)
    value = inheritance.inspect_cache_view(point.context, point.bindings, point.item)
    assert value["source_layout"] == "completed_V40_overlay"
    assert [len(row["task_ids"]) for row in value["cache_sources"]] == [186, 558]
    assert [row["task_id"] for row in value["task_records"]] == point.plan["task_ids"]
    assert value["read_only"] is True and value["writes_allowed"] is False
    assert value["cache_sources"][0]["stages"] == ["shard02"]
    assert value["cache_sources"][1]["stages"] == ["shard00", "shard01", "shard03"]


def test_partial_class_and_task_shadow_rejected(point):
    with pytest.raises(ValueError, match="four exited"):
        inheritance.inspect_cache_view(
            point.context, {"shard02": point.bindings["shard02"]}, point.item
        )
    shadow = point.directory / "task_cache/task0002"
    shadow.mkdir()
    with pytest.raises(ValueError, match="shadow"):
        inheritance.inspect_cache_view(point.context, point.bindings, point.item)


def test_overlay_cannot_change_original_point(point):
    record = point.directory / "task_cache/task0000/record.json"
    rewrite(record, binding_sha256="changed")
    with pytest.raises(ValueError, match="actual point"):
        inheritance.inspect_cache_view(point.context, point.bindings, point.item)


def test_inherited_time_plus_new_union_and_original_class_window(point):
    window_path = point.directory / "class_recovery_window/record.json"
    start = 1791805000
    write_record(
        window_path,
        dict(
            seed=251,
            arm="C-only",
            step=1192,
            context_id=point.context["id"],
            window_seconds=14400,
            started_epoch=start,
            deadline_epoch=start + 14400,
            allowed_stages=["shard00", "shard01", "shard03"],
        ),
    )
    timing = inheritance._phase_timing(
        point.context,
        point.bindings,
        dict(compute_seconds=6800),
        point.item,
        class_window=inheritance.entry(window_path),
    )
    assert timing["inherited_compute_seconds"] == 6785 + 3 * 80
    assert timing["phase_deadlines_epoch"]["class_gradients"] == start + 14400
    assert timing["phase_first_launch_epoch"]["class_gradients"] == start
    assert timing["phase_budgets_reset"] is False


def test_recovered_replay_counts_only_new186_but_requires_complete447(point):
    p = point
    context = dict(p.context, seed=389, arm="Full", step=298)
    source = p.directory / "replay_R3"
    owner, owner_ref = p.protocols[1]
    stage(p.parent, source, owner, context, "replay_R3", 1000, 2000, p.plan)
    rewrite(
        source / "result/record.json",
        response_count=447,
        replayed_responses=186,
        restored_completed_responses=261,
        inherited_response_count=261,
        actual_new_response_calls=186,
    )
    value = inheritance.inspect_stage(
        source, owner, context, "replay_R3", p.plan, protocol_ref=owner_ref
    )
    assert inheritance.read_ref(value["result"])["replayed_responses"] == 186
    rewrite(source / "result/record.json", replayed_responses=447)
    with pytest.raises(ValueError, match="prefix recovery dose"):
        inheritance.inspect_stage(
            source, owner, context, "replay_R3", p.plan, protocol_ref=owner_ref
        )


def _sample(tmp_path, context_id, count):
    directory = tmp_path / context_id / "virtual_point"
    write_record(
        directory / "result/record.json",
        dict(context_id=context_id, stage="virtual_point", new_feedback_episodes=count),
    )
    return dict(
        protocol_scope="parent",
        directory=str(directory),
        result=inheritance.entry(directory / "result/record.json"),
    )


def test_unique_sampled_uncommitted_cohort_deducted_once(tmp_path):
    first = _sample(tmp_path, "committed", 700)
    pending = _sample(tmp_path, "uncommitted", 700)
    progress = dict(
        pending_sealed_feedback_episodes=0,
        future_first_sampling_outers=11,
        future_first_sampling_feedback_episodes=7700,
    )
    result = inheritance.scientific_budget(
        progress,
        [first, pending, pending],
        [dict(stage_bindings=dict(virtual_point=pending))],
        [1] * 4,
    )
    assert result["already_generated_first_sampling_feedback_episodes"] == 1400
    assert result["already_generated_uncommitted_feedback_episodes"] == 700
    assert result["remaining_new_feedback_episodes"] == 7000
    assert result["original_reused_feedback_episodes"] == 2100
    assert result["remaining_endpoint_answers"] == 5735


def test_duplicate_scientific_result_with_different_source_rejected(tmp_path):
    first = _sample(tmp_path / "a", "same", 700)
    second = _sample(tmp_path / "b", "same", 700)
    with pytest.raises(ValueError, match="two accepted"):
        inheritance._deduplicate([first, second])


def test_stage_path_not_assumed_to_live_under_original_context(point):
    p = point
    cache_view = inheritance.inspect_cache_view(p.context, p.bindings, p.item)
    target = p.root / p.directory.relative_to(p.parent)
    row = dict(
        new_context_directory=str(target),
        original_context=inheritance.entry(p.origin / "context/record.json"),
        original_context_id=p.context["id"],
        origin_context_directory=str(p.origin),
        stage_bindings=p.bindings,
        task_cache_view=cache_view,
    )
    for name in inheritance.STAGES:
        row["stage_bindings"].setdefault(
            name, dict(protocol_scope="current", directory=str(target / name))
        )
    write_record(
        p.root / "inheritance/record.json",
        dict(schema=inheritance.SCHEMA, new_root=str(p.root), context_inheritances=[row]),
    )
    inherited_ref = inheritance.entry(p.root / "inheritance/record.json")
    write_record(
        target / "context/record.json",
        dict(
            schema=inheritance.ALIAS_SCHEMA,
            inheritance=inherited_ref,
            **{
                key: row[key]
                for key in (
                    "new_context_directory",
                    "original_context",
                    "original_context_id",
                    "origin_context_directory",
                )
            },
        ),
    )
    plan = dict(output_root=str(p.root), inheritance=inherited_ref)
    assert inheritance.resolve_origin_context(target, plan) == p.origin
    assert inheritance.stage_directory(target, plan, "shard02") == p.origin / "shard02"
    assert inheritance.stage_directory(target, plan, "shard00") == p.directory / "shard00"
    assert inheritance.stage_directory(target, plan, "virtual_point") == target / "virtual_point"
    assert inheritance.task_cache_view_binding(target, plan) == cache_view


def test_no_actual_handoff_means_no_migration(tmp_path):
    parent = tmp_path / "production/recovery_02"
    root = parent.parent / "admission_relaxation_01"
    write_record(
        parent / "protocol/record.json",
        dict(schema="v40_explicit_durable_replay_recovery_protocol.v1"),
    )
    path = tmp_path / "handoff/record.json"
    write_record(path, dict(status="DRAINING_NATURALLY"))
    with pytest.raises(ValueError, match="successful authorized"):
        inheritance.inspect_parent_migration(root, parent, path)
    assert not root.exists()


def test_legacy_training_checkpoint_does_not_require_scheduler_json_id(point):
    p = point
    checkpoint = p.root / "training/step1193_step"
    checkpoint.mkdir(parents=True)
    (checkpoint / "state.pt").write_bytes(b"legacy Tensor, never read")
    # Original training snapshots are not scheduler self-ID JSON records.
    (checkpoint / "record.json").write_text(
        json.dumps(
            dict(
                seed=251,
                arm="C-only",
                step=1193,
                phase="step",
                state_sha256="a" * 64,
                actual_state_digest="b" * 64,
            )
        )
    )
    source = p.directory / "train"
    owner, owner_ref = p.protocols[1]
    stage(p.parent, source, owner, p.context, "train", 1000, 1100, p.plan)
    rewrite(source / "result/record.json", next_checkpoint=str(checkpoint), committed_step=1193)
    inspected = inheritance.inspect_stage(
        source, owner, p.context, "train", p.plan, protocol_ref=owner_ref
    )
    assert inspected["actual_training_commits"]["next_checkpoint"]["step"] == 1193


def test_quiescent_preflight_refuses_active_worker(point, monkeypatch):
    protocol, _ = point.protocols[1]
    protocol = write_record(
        point.parent / "protocol/record.json",
        dict(protocol, schema="v40_explicit_durable_replay_recovery_protocol.v1"),
    )
    monkeypatch.setattr(inheritance, "PARENT_PROTOCOL_ID", protocol["id"])
    with pytest.raises(ValueError, match="quiescent V40"):
        inheritance.preflight_quiescent(
            point.parent,
            dict(
                protocol_id=protocol["id"],
                pilot_accepted=True,
                active_children=[dict(stage="shard00")],
            ),
        )
