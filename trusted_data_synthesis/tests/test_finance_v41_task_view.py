"""Real CPU tensors only: complete single and 186+558 inherited cache views."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.finance_research import v8_training_driver as v8

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v41_task_view")
contexts = importlib.import_module("finqa_v37_task_cache")
original = importlib.import_module("finqa_v35_task_cache")
CONTROL = SimpleNamespace(
    require=contexts.require,
    checked=contexts.checked,
    entry=contexts.entry,
    read_ref=contexts.read_ref,
)


def values(index):
    return {"z0": {"weight": torch.tensor([index + 0.25], dtype=torch.float32)}}


def fixture(tmp_path, *, count=8, split=True):
    tasks = [f"task{index:04d}" for index in range(count)]
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
        binding_id="V41_CPU_VIEW_ONLY",
        chi={},
        production=False,
    )
    spec = [dict(name="weight", shape=[1], dtype="torch.float32")]
    plan = original.make_task_plan(pool, spec, shards=4)
    plan_path = tmp_path / "task_plan/record.json"
    contexts.publish(plan_path, {key: value for key, value in plan.items() if key != "id"})
    source_binding = dict(
        schema="v37_actual_outer_task_gradient_binding.v1",
        cross_parameter_point_reuse=False,
        task_plan_id=plan["id"],
        parameter_spec=spec,
        seed=251,
        arm="C-only",
        step=1192,
        pre_state_digest="CPU_SAME_ACTUAL_POINT",
    )
    rt = SimpleNamespace(torch=torch, v8=v8)
    roots = [tmp_path / "parent/task_cache"]
    selected = [tasks]
    if split:
        roots.append(tmp_path / "completed_supplement/task_cache")
        parent_ids = plan["assignments"][2]["task_ids"]
        selected = [parent_ids, [task for task in tasks if task not in set(parent_ids)]]

    def cache(root):
        return contexts.ProductionTaskCache(
            root, source_binding, plan, spec, rt, original_cache_module=original
        )

    records = {}
    for root, task_ids in zip(roots, selected, strict=True):
        writer = cache(root)
        for task in task_ids:
            writer.commit(task, values(writer.task(task)["index"]))
            directory = writer.directory(task)
            record = contexts.checked(directory / "record.json")
            records[task] = dict(
                task_id=task,
                cache_root=str(root),
                record=contexts.entry(directory / "record.json"),
                gradient=dict(
                    path=str(directory / "gradient.pt"),
                    sha256=record["gradient_sha256"],
                    bytes=record["gradient_bytes"],
                ),
                record_file_identity=subject._identity(directory / "record.json"),
                gradient_file_identity=subject._identity(directory / "gradient.pt"),
            )
    context = dict(
        id="SAME_CONTEXT",
        task_cache_root=str(roots[0]),
        task_binding=source_binding,
        parameter_spec=spec,
        task_plan=contexts.entry(plan_path),
    )
    binding = dict(
        schema=subject.SCHEMA,
        read_only=True,
        writes_allowed=False,
        original_context_id=context["id"],
        task_plan=context["task_plan"],
        task_plan_id=plan["id"],
        binding_sha256=contexts.digest(source_binding),
        task_ids=tasks,
        cache_sources=[
            dict(cache_root=str(root), task_ids=ids)
            for root, ids in zip(roots, selected, strict=True)
        ],
        task_records=[records[task] for task in tasks],
    )
    directory = tmp_path / "new_context"
    bundle = SimpleNamespace(context=contexts, original_cache=original, rt=rt)

    def build(stage="virtual_point"):
        return subject.build_view(
            cache(roots[0]), context, directory, stage, binding, bundle, control=CONTROL
        )

    return SimpleNamespace(**locals())


@pytest.mark.parametrize("split", [False, True])
def test_real_cpu_tensor_order_and_each_new_process_reader_is_strict(tmp_path, split):
    f = fixture(tmp_path, count=744 if split else 8, split=split)
    before = {str(path): path.read_bytes() for root in f.roots for path in root.glob("task*/*")}
    view = f.build()
    assert view.verification_summary()["strict_payload_file_reads"] == 0
    merged = view.assemble("cpu")
    assert list(merged) == f.tasks
    assert all(
        torch.equal(merged[task]["z0"]["weight"], values(index)["z0"]["weight"])
        for index, task in enumerate(f.tasks)
    )
    report = view.verification_summary()
    assert report["strict_payload_file_reads"] == report["verified_task_count"] == len(f.tasks)
    assert report["inherited_gradient_payload_bytes_copied"] == 0
    assert report["inherited_artifacts_written"] is False
    assert report["cross_process_verification_waiver"] is False
    if split:
        assert list(report["source_verified_task_counts"].values()) == [186, 558]
    view.read(f.tasks[0])
    assert view.verification_summary()["strict_payload_file_reads"] == len(f.tasks)
    assert f.build().verification_summary()["strict_payload_file_reads"] == 0
    assert before == {
        str(path): path.read_bytes() for root in f.roots for path in root.glob("task*/*")
    }
    assert not f.directory.exists()


@pytest.mark.parametrize("stage", ["shard00", "shard02", "generate", "unknown"])
def test_no_inherited_class_stage_or_unregistered_consumer(tmp_path, stage):
    with pytest.raises(ValueError, match="only complete inherited"):
        fixture(tmp_path).build(stage)


@pytest.mark.parametrize("method", ["commit", "get_or_compute"])
def test_complete_view_never_computes_or_writes(tmp_path, method):
    f = fixture(tmp_path)
    with pytest.raises(ValueError, match="read-only"):
        getattr(f.build(), method)(f.tasks[0], lambda: pytest.fail("compute is forbidden"))


@pytest.mark.parametrize(
    "corruption",
    [
        "duplicate_owner",
        "missing_owner",
        "record_order",
        "source_order",
        "point",
        "plan",
        "local_shadow",
        "source_shadow",
        "missing_payload",
    ],
)
def test_view_rejects_incomplete_shadowed_reordered_or_cross_point_metadata(tmp_path, corruption):
    f = fixture(tmp_path)
    if corruption == "duplicate_owner":
        f.binding["cache_sources"][1]["task_ids"].append(f.selected[0][0])
    elif corruption == "missing_owner":
        f.binding["cache_sources"].pop()
    elif corruption == "record_order":
        f.binding["task_records"].reverse()
    elif corruption == "source_order":
        f.binding["cache_sources"][1]["task_ids"].reverse()
    elif corruption == "point":
        f.context["task_binding"] = dict(f.source_binding, step=894)
    elif corruption == "plan":
        f.binding["task_plan_id"] = "another-plan"
    elif corruption == "local_shadow":
        (f.directory / "task_cache").mkdir(parents=True)
    elif corruption == "source_shadow":
        (f.roots[0] / "shadow").mkdir()
    else:
        (f.roots[0] / f.selected[0][0] / "gradient.pt").unlink()
    with pytest.raises(ValueError):
        f.build()


@pytest.mark.parametrize(
    "kind", ["file_after_registration", "file_after_read", "tensor_after_read", "symlink"]
)
def test_registered_file_and_actual_cpu_tensor_mutations_fail_closed(tmp_path, kind):
    f = fixture(tmp_path)
    view = f.build()
    task = f.tasks[0]
    payload = view.directory(task) / "gradient.pt"
    if kind == "file_after_registration":
        payload.write_bytes(payload.read_bytes() + b"x")
    elif kind == "file_after_read":
        view.read(task)
        payload.write_bytes(payload.read_bytes())
    elif kind == "tensor_after_read":
        view.read(task)["z0"]["weight"].add_(1)
    else:
        saved = payload.with_name("saved_payload.pt")
        payload.rename(saved)
        payload.symlink_to(saved)
    with pytest.raises(ValueError):
        view.read(task)


def test_different_source_reader_cannot_waive_tensor_verification(tmp_path):
    f = fixture(tmp_path)
    view = f.build()
    readers = list(view.readers.values())
    readers[0].verification_summary = lambda: dict(
        process_id=-1, verified_task_ids=[], strict_payload_file_reads=0
    )
    with pytest.raises(ValueError, match="another process"):
        view.verification_summary()


def test_metadata_registration_does_not_equal_tensor_validation(tmp_path):
    f = fixture(tmp_path)
    view = f.build()
    task = f.tasks[0]
    payload = view.directory(task) / "gradient.pt"
    # Simulate a maliciously self-consistent metadata list; the unchanged strict
    # payload reader must still compare the actual bytes to the saved digest.
    content = bytearray(payload.read_bytes())
    content[-1] ^= 1
    payload.write_bytes(content)
    view.records[task]["gradient_file_identity"] = subject._identity(payload)
    with pytest.raises(ValueError, match="digest|hash|checksum"):
        view.read(task)
