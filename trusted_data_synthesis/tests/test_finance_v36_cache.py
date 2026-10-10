"""Tiny CPU tensors across the real 741+3 overlay topology; no GPU evidence."""

import importlib
import json
import pickle
import sys
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
overlay = importlib.import_module("finqa_v36_cache")
original = importlib.import_module("finqa_v35_task_cache")


def tree_digest(value):
    if isinstance(value, torch.Tensor):
        value = dict(
            shape=list(value.shape),
            dtype=str(value.dtype),
            bytes=value.detach()
            .cpu()
            .contiguous()
            .reshape(-1)
            .view(torch.uint8)
            .numpy()
            .tobytes()
            .hex(),
        )
    elif isinstance(value, dict):
        value = {str(key): tree_digest(item) for key, item in value.items()}
    elif isinstance(value, (tuple, list)):
        value = [tree_digest(item) for item in value]
    return overlay.digest(value)


class DeviceGradients(Mapping):
    def __init__(self, values, device):
        self.values_cpu, self.device = values, device

    def __len__(self):
        return len(self.values_cpu)

    def __iter__(self):
        return iter(self.values_cpu)

    def __getitem__(self, state):
        return {name: tensor.to(self.device) for name, tensor in self.values_cpu[state].items()}


RT = SimpleNamespace(
    torch=torch, v8=SimpleNamespace(_tree_digest=tree_digest, _DeviceGradients=DeviceGradients)
)


def publish(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {**body, "id": overlay.digest(body)}
    with path.open("x") as stream:
        json.dump(value, stream)
    return value


def read_ref(reference):
    assert overlay.entry(reference["path"]) == reference
    return overlay.checked(reference["path"])


def values(index):
    return {"state": {"weight": torch.tensor([float(index), -float(index)], dtype=torch.float32)}}


@pytest.fixture
def fixture(tmp_path):
    torch.set_num_threads(1)
    old = tmp_path / "replay_performance_04"
    parent, root = old / "recovery_01", old / "recovery_02"
    ids = [overlay.ALLOWED_NEW.get(index, f"CPU_task_{index}") for index in range(744)]
    spec = [dict(name="weight", shape=[2], dtype="torch.float32")]
    tasks = [
        dict(
            index=index,
            task_id=task,
            state_ids=["state"],
            packages=[],
            row_count={739: 8, 741: 9, 743: 9}.get(index, 1),
            shard=1 if index in overlay.ALLOWED_NEW else index % 4,
        )
        for index, task in enumerate(ids)
    ]
    plan = publish(
        old / "task_plan/record.json",
        dict(
            schema="v35_complete_task_plan.v1",
            task_ids=ids,
            tasks=tasks,
            parameter_spec=spec,
            assignments=[
                dict(shard=i, task_ids=[t["task_id"] for t in tasks if t["shard"] == i])
                for i in range(4)
            ],
        ),
    )
    binding = dict(
        implementation_id="original_frozen_math",
        point_id="unchanged_actual_point",
        task_plan_id=plan["id"],
        storage_source="unchanged_V34_CPU_saves",
    )
    protocol = publish(
        old / "protocol/record.json",
        dict(task_binding=binding, task_plan=overlay.entry(old / "task_plan/record.json")),
    )
    parent_protocol = publish(
        parent / "protocol/record.json",
        dict(
            source_protocol=overlay.entry(old / "protocol/record.json"),
            task_binding=binding,
            task_plan=protocol["task_plan"],
        ),
    )
    cache = original.TaskCache(parent / "task_cache", binding, plan, spec, RT)
    references, complete = [], []
    for task in tasks:
        if task["index"] in overlay.ALLOWED_NEW:
            continue
        cache.commit(task["task_id"], values(task["index"]))
        complete.append(task["task_id"])
        references.append(
            dict(
                task_id=task["task_id"],
                **overlay.entry(cache.directory(task["task_id"]) / "record.json"),
            )
        )
    publish(
        parent / "failure/record.json",
        dict(
            protocol_id=parent_protocol["id"],
            original_B_resume_authorized=False,
            original_V35_failure_reclassified=False,
            task_cache_coverage=dict(
                task_plan_id=plan["id"],
                binding_sha256=overlay.digest(binding),
                complete_task_count=741,
                total_task_count=744,
                complete_task_ids=complete,
                missing_task_ids=list(overlay.ALLOWED_NEW.values()),
                task_records=references,
            ),
        ),
    )
    publish(
        parent / "closeout_01/record.json",
        dict(
            status="STOPPED_FAILURE_NO_RETRY",
            durable_complete_tasks=741,
            global_coordinator_launched=False,
            original_B_resume_authorized=False,
        ),
    )
    for stage, source, bound_protocol in (
        ("shard00", old, protocol),
        ("shard02", parent, parent_protocol),
        ("shard03", parent, parent_protocol),
    ):
        publish(
            source / stage / "result/record.json",
            dict(
                status="COMPLETE",
                stage=stage,
                model_released=True,
                protocol_id=bound_protocol["id"],
            ),
        )
        publish(
            source / stage / "exit/record.json",
            dict(stage=stage, protocol_id=bound_protocol["id"], returncode=0),
        )
        publish(
            source / stage / "launch/record.json",
            dict(stage=stage, protocol_id=bound_protocol["id"]),
        )

    def check_result(p, stage, result, original_plan):
        assert (
            result["status"] == "COMPLETE"
            and result["stage"] == stage
            and result["protocol_id"] == p["id"]
        )
        assert original_plan == plan

    base = SimpleNamespace(
        checked=overlay.checked,
        entry=overlay.entry,
        publish=publish,
        read_ref=read_ref,
        now=lambda: "CPU_FIXTURE_ONLY",
        check_result=check_result,
        checked_protocol=lambda path: overlay.checked(Path(path) / "protocol/record.json"),
    )
    receipt = overlay.prepare_index(old, parent, root, base)
    adapter = overlay.overlay_adapter(root, original, base)
    active = adapter.TaskCache(root / "task_cache", binding, plan, spec, RT)
    return SimpleNamespace(
        old=old,
        parent=parent,
        root=root,
        plan=plan,
        binding=binding,
        spec=spec,
        base=base,
        receipt=receipt,
        adapter=adapter,
        cache=active,
    )


def test_index_only_original_source_paths_no_tensor_copy_and_exact_successful_stage_refs(fixture):
    f = fixture
    assert f.receipt["complete_task_count"] == 741 and f.receipt["missing_task_count"] == 3
    assert f.receipt["copied_gradient_bytes"] == 0 and not (f.root / "task_cache").exists()
    assert f.receipt["task_binding"] == f.binding and f.receipt["task_plan"] == overlay.entry(
        f.old / "task_plan/record.json"
    )
    assert f.receipt["inherited_completed_stages"]["shard00"]["result"] == overlay.entry(
        f.old / "shard00/result/record.json"
    )
    assert f.receipt["inherited_completed_stages"]["shard02"]["result"] == overlay.entry(
        f.parent / "shard02/result/record.json"
    )
    assert f.receipt["inherited_completed_stages"]["shard03"]["result"] == overlay.entry(
        f.parent / "shard03/result/record.json"
    )
    assert f.adapter.TaskPoolView is original.TaskPoolView
    assert f.adapter.make_task_plan is original.make_task_plan
    assert overlay.inspect_overlay(f.root, complete=False)["complete_task_count"] == 741
    with pytest.raises(ValueError, match="all 744"):
        overlay.inspect_overlay(f.root, complete=True)
    with pytest.raises(ValueError, match="missing complete"):
        f.cache.assemble()
    assert f.cache.verification_summary()["strict_payload_file_reads"] == 0


def test_true_tensor_validation_once_live_process_then_full744_original_order(fixture):
    f = fixture
    first = f.plan["task_ids"][0]
    assert f.cache.has(first)
    assert torch.equal(f.cache.read(first)["state"]["weight"], values(0)["state"]["weight"])
    assert f.cache.verification_summary()["strict_payload_file_reads"] == 1
    shared = f.adapter.TaskCache(
        f.root / "task_cache", f.binding, f.plan, f.spec, RT, verified_state=f.cache.verified_state
    )
    assert shared.has(first) and shared.verification_summary()["strict_payload_file_reads"] == 1
    for index, task_id in reversed(list(overlay.ALLOWED_NEW.items())):
        f.cache.commit(task_id, values(index))
    assembled = f.cache.assemble(device="cpu")
    assert list(assembled) == f.plan["task_ids"]
    for index, task_id in enumerate(f.plan["task_ids"]):
        assert torch.equal(assembled[task_id]["state"]["weight"], values(index)["state"]["weight"])
    report = f.cache.verification_summary()
    assert report["strict_payload_file_reads"] == 744
    assert (
        report["parent_tasks_strictly_verified"] == 741
        and report["local_tasks_strictly_verified"] == 3
    )
    assert f.cache.validate_complete()["verification"]["strict_payload_file_reads"] == 744
    assert overlay.inspect_overlay(f.root, complete=True)["complete_task_count"] == 744
    fresh = f.adapter.TaskCache(f.root / "task_cache", f.binding, f.plan, f.spec, RT)
    assert fresh.verification_summary()["strict_payload_file_reads"] == 0
    assert fresh.has(first) and fresh.verification_summary()["strict_payload_file_reads"] == 1
    assert not torch.cuda.is_initialized()


def test_parent_is_read_only_unknown_task_binding_and_nonfinite_local_rejected(fixture):
    f = fixture
    task = f.plan["task_ids"][0]
    before = (f.parent / "task_cache/task0000/gradient.pt").read_bytes()
    with pytest.raises(ValueError, match="read-only parent"):
        f.cache.commit(task, values(0))
    with pytest.raises(ValueError, match="outside frozen plan"):
        f.cache.commit("unknown", values(1))
    with pytest.raises(ValueError, match="binding changed"):
        f.adapter.TaskCache(
            f.root / "task_cache", {**f.binding, "point_id": "wrong"}, f.plan, f.spec, RT
        )
    invalid = values(739)
    invalid["state"]["weight"][0] = float("nan")
    with pytest.raises(ValueError, match="invalid/nonfinite"):
        f.cache.commit(overlay.ALLOWED_NEW[739], invalid)
    assert (f.parent / "task_cache/task0000/gradient.pt").read_bytes() == before


def test_parent_tensor_corruption_refused_not_satisfied_by_metadata_index(fixture):
    f = fixture
    path = f.parent / "task_cache/task0000/gradient.pt"
    raw = path.read_bytes()
    path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(ValueError, match="identity changed"):
        f.cache.has(f.plan["task_ids"][0])
    assert f.cache.verification_summary()["strict_payload_file_reads"] == 0


def test_cached_cpu_tensor_mutation_and_cross_process_waiver_refused(fixture, monkeypatch):
    f = fixture
    task = f.plan["task_ids"][0]
    f.cache.read(task)["state"]["weight"].add_(1)
    with pytest.raises(ValueError, match="CPU tensor changed"):
        f.cache.has(task)
    with pytest.raises(TypeError, match="another process"):
        pickle.dumps(f.cache.verified_state)
    monkeypatch.setattr(overlay.os, "getpid", lambda: f.cache.verified_state.pid + 1)
    with pytest.raises(ValueError, match="another process"):
        f.adapter.TaskCache(
            f.root / "task_cache",
            f.binding,
            f.plan,
            f.spec,
            RT,
            verified_state=f.cache.verified_state,
        )


def test_local_parent_shadow_and_overlay_receipt_tampering_rejected(fixture):
    f = fixture
    (f.root / "task_cache/task0000").mkdir(parents=True)
    with pytest.raises(ValueError, match="shadow"):
        f.cache.has(f.plan["task_ids"][0])
    with pytest.raises(ValueError, match="unauthorized"):
        f.adapter.TaskCache(f.root / "task_cache", f.binding, f.plan, f.spec, RT)
    path = f.root / "cache_index/record.json"
    value = json.loads(path.read_bytes())
    value["parent_cache_root"] = str(f.old / "task_cache")
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="record changed"):
        overlay.inspect_overlay(f.root, complete=False)
