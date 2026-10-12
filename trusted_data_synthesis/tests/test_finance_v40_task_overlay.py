"""Actual CPU task tensors: immutable186 parent plus authorized558 local, no GPU."""

import hashlib
import importlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.finance_research import v8_training_driver as v8

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v40_task_overlay")
contexts = importlib.import_module("finqa_v37_task_cache")
original = importlib.import_module("finqa_v35_task_cache")
CONTROL = SimpleNamespace(require=contexts.require, checked=contexts.checked, entry=contexts.entry)


def values(index):
    return {"z0": {"weight": torch.tensor([index + 0.25], dtype=torch.float32)}}


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    root = tmp_path_factory.mktemp("overlay-parent186")
    tasks = [f"task{index:04d}" for index in range(744)]
    packages = [
        dict(task_id=task, state_id="z0", package_id=f"p{index}", whole_package_target_tokens=1)
        for index, task in enumerate(tasks)
    ]
    pool = v8.VerifiedPool(
        tasks,
        packages,
        {
            p["package_id"]: [dict(input_ids=[1, 2], target_positions=[1], target_ids=[2])]
            for p in packages
        },
        binding_id="V40_CPU_OVERLAY_ONLY",
        chi={},
        production=False,
    )
    spec = [dict(name="weight", shape=[1], dtype="torch.float32")]
    plan = original.make_task_plan(pool, spec, shards=4)
    binding = dict(
        schema="v37_actual_outer_task_gradient_binding.v1",
        cross_parameter_point_reuse=False,
        task_plan_id=plan["id"],
        parameter_spec=spec,
        seed=251,
        arm="C-only",
        step=1192,
        pre_state_digest="CPU_ORIGINAL_SAME_POINT",
    )
    rt = SimpleNamespace(torch=torch, v8=v8)
    cache = contexts.ProductionTaskCache(
        root / "task_cache", binding, plan, spec, rt, original_cache_module=original
    )
    for task in plan["assignments"][2]["task_ids"]:
        cache.commit(task, values(cache.task(task)["index"]), receipt={"stage": "shard02"})
    return SimpleNamespace(root=root, plan=plan, binding=binding, spec=spec, rt=rt)


@pytest.fixture
def overlay(data, tmp_path):
    parent_root = tmp_path / "parent/task_cache"
    shutil.copytree(data.root / "task_cache", parent_root)
    context = dict(
        id="ORIGINAL_C251_1192_CONTEXT",
        seed=251,
        arm="C-only",
        step=1192,
        task_cache_root=str(parent_root),
        task_binding=data.binding,
        parameter_spec=data.spec,
    )
    directory = tmp_path / "recovery_02/contexts/seed251/c_only/step1192_outer"
    parent_ids = data.plan["assignments"][2]["task_ids"]
    local_ids = [task for task in data.plan["task_ids"] if task not in set(parent_ids)]
    records = []
    for task in parent_ids:
        path = parent_root / task
        record = contexts.checked(path / "record.json")
        records.append(
            dict(
                task_id=task,
                record=contexts.entry(path / "record.json"),
                gradient=dict(
                    path=str(path / "gradient.pt"),
                    sha256=record["gradient_sha256"],
                    bytes=record["gradient_bytes"],
                ),
                record_file_identity=subject._identity(path / "record.json"),
                gradient_file_identity=subject._identity(path / "gradient.pt"),
            )
        )
    binding = dict(
        seed=251,
        arm="C-only",
        step=1192,
        original_context_id=context["id"],
        parent_cache_root=str(parent_root),
        local_cache_root=str(directory / "task_cache"),
        task_plan_id=data.plan["id"],
        binding_sha256=contexts.digest(data.binding),
        parent_task_ids=parent_ids,
        local_task_ids=local_ids,
        allowed_new_stages=list(subject.NEW_STAGES),
        parent_records=records,
    )
    bundle = SimpleNamespace(context=contexts, original_cache=original, rt=data.rt)

    def build(stage):
        parent = contexts.ProductionTaskCache(
            parent_root,
            data.binding,
            data.plan,
            data.spec,
            data.rt,
            original_cache_module=original,
        )
        return subject.build_overlay(
            parent, context, directory, stage, binding, bundle, control=CONTROL
        )

    return SimpleNamespace(
        context=context,
        directory=directory,
        binding=binding,
        build=build,
        data=data,
        parent_root=parent_root,
        parent_ids=parent_ids,
        local_ids=local_ids,
    )


def hashes(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.glob("task*/*")
    }


def test_parent186_plus_local558_assemble_in_original_order_with_strict_real_tensor_reads(overlay):
    f = overlay
    before = hashes(f.parent_root)
    committed = []
    for stage in subject.NEW_STAGES:
        cache = f.build(stage)
        for task in f.data.plan["assignments"][int(stage[-2:])]["task_ids"]:
            assert not cache.has(task)
            cache.commit(task, values(cache.task(task)["index"]), receipt={"stage": stage})
            committed.append(task)
    assert len(committed) == len(set(committed)) == 558
    assert not (set(committed) & set(f.parent_ids))
    coordinator = f.build("virtual_point")
    merged = coordinator.assemble("cpu")
    assert list(merged) == f.data.plan["task_ids"]
    assert all(
        torch.equal(merged[task]["z0"]["weight"], values(index)["z0"]["weight"])
        for index, task in enumerate(f.data.plan["task_ids"])
    )
    summary = coordinator.verification_summary()
    assert summary["strict_payload_file_reads"] == summary["verified_task_count"] == 744
    assert summary["parent_tasks_strictly_verified"] == 186
    assert summary["local_tasks_strictly_verified"] == 558
    assert summary["parent_gradient_payload_bytes_copied"] == 0
    assert summary["parent_artifacts_written"] is False
    assert hashes(f.parent_root) == before
    # Reusing a value in this live process does not reread or waive another worker's checks.
    coordinator.read(f.parent_ids[0])
    assert coordinator.verification_summary()["strict_payload_file_reads"] == 744
    with pytest.raises(ValueError, match="only the dispatched"):
        coordinator.commit(f.local_ids[0], values(0))


def test_unfinished_local_population_cannot_be_zero_filled(overlay):
    cache = overlay.build("virtual_point")
    with pytest.raises(ValueError, match="all 558"):
        cache.assemble()
    assert cache.verification_summary()["strict_payload_file_reads"] == 0


@pytest.mark.parametrize("kind", ["parent", "other_shard"])
def test_new_shard_cannot_write_parent_or_another_shard(overlay, kind):
    cache = overlay.build("shard00")
    task = (
        overlay.parent_ids[0]
        if kind == "parent"
        else (overlay.data.plan["assignments"][1]["task_ids"][0])
    )
    with pytest.raises(ValueError, match="only the dispatched"):
        cache.commit(task, values(cache.task(task)["index"]))


def test_local_complete_task_cannot_be_committed_twice(overlay):
    cache = overlay.build("shard00")
    task = overlay.data.plan["assignments"][0]["task_ids"][0]
    cache.commit(task, values(cache.task(task)["index"]))
    with pytest.raises(FileExistsError, match="immutable"):
        cache.commit(task, values(cache.task(task)["index"]))


def test_completed_shard02_is_never_a_new_worker(overlay):
    with pytest.raises(ValueError, match="registered partial"):
        overlay.build("shard02")
    assert not subject.allows_new_shard(overlay.binding, "shard02")
    assert subject.allows_new_shard(overlay.binding, "shard03")


@pytest.mark.parametrize("change", ["missing", "metadata_changed", "shadow", "unknown"])
def test_parent_missing_changed_and_local_overlap_are_rejected(overlay, change):
    f = overlay
    source = f.parent_root / f.parent_ids[0]
    if change == "missing":
        (source / "gradient.pt").unlink()
    elif change == "metadata_changed":
        with (source / "record.json").open("ab") as stream:
            stream.write(b" ")
    else:
        name = f.parent_ids[0] if change == "shadow" else "task9999"
        (f.directory / "task_cache" / name).mkdir(parents=True)
    with pytest.raises(ValueError):
        f.build("shard00")


def test_actual_parent_tensor_checksum_is_checked_even_if_registration_stat_matches(overlay):
    f = overlay
    row = f.binding["parent_records"][0]
    path = Path(row["gradient"]["path"])
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 1
    path.write_bytes(raw)
    # Registration is metadata-only; simulate observing the changed file's stat.
    # Actual mathematical consumption must still use the original strict SHA reader.
    row["gradient_file_identity"] = subject._identity(path)
    cache = f.build("virtual_point")
    with pytest.raises(ValueError, match="checksum"):
        cache.read(f.parent_ids[0])


def test_authorized_original_task_order_cannot_be_rearranged(overlay):
    overlay.binding["local_task_ids"] = list(reversed(overlay.local_ids))
    with pytest.raises(ValueError, match="ownership"):
        overlay.build("shard00")


def test_class_window_binds_protocol_point_and_single_four_hour_budget(overlay):
    f = overlay
    authority = {"id": "EXPLICIT_SINGLE_4H"}
    plan = dict(id="NEW_PROTOCOL", partial_class_completion_authorization=authority)
    body = dict(
        schema="v40_single_bounded_class_completion_window.v1",
        protocol_id=plan["id"],
        context_id=f.context["id"],
        seed=251,
        arm="C-only",
        step=1192,
        first_dispatched_shard="shard00",
        started_epoch=1000,
        deadline_epoch=15400,
        window_seconds=14400,
        allowed_stages=list(subject.NEW_STAGES),
        authorization=authority,
        inherited_task_count=186,
        remaining_task_count=558,
        original_class_deadline_epoch=900,
    )
    path = f.directory / "class_recovery_window/record.json"
    path.parent.mkdir(parents=True)

    def publish(value):
        path.write_text(json.dumps(dict(value, id=contexts.digest(value))))

    publish(body)
    assert (
        subject.validate_class_window(
            f.directory, f.context, plan, "shard03", 15000, control=CONTROL
        )["deadline_epoch"]
        == 15400
    )
    with pytest.raises(ValueError, match="reset"):
        subject.validate_class_window(
            f.directory, f.context, plan, "shard01", 15401, control=CONTROL
        )
    publish(dict(body, context_id="different-point"))
    with pytest.raises(ValueError, match="authorized"):
        subject.validate_class_window(
            f.directory, f.context, plan, "shard01", 15000, control=CONTROL
        )
    publish(body)
    with pytest.raises(ValueError, match="authorized"):
        subject.validate_class_window(
            f.directory, f.context, plan, "shard02", 15000, control=CONTROL
        )
