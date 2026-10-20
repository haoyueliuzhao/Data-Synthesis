"""Uncovered V63 CPU/mock integration; no scientific/GPU process is started."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import finqa_v63_binding as binding

binding.install_scientific_paths()

import finqa_v63_runtime as runtime
import finqa_v63_training as training
import finqa_v63_worker as worker
import pytest
import torch


def record(path, body):
    value = {**body, "id": binding.digest(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


class CudaStub:
    def __init__(self):
        self.peak = 34 * runtime.GIB
        self.calls = []

    def synchronize(self):
        self.calls.append("synchronize")

    def mem_get_info(self):
        return 60 * runtime.GIB, 80 * runtime.GIB

    def memory_allocated(self):
        return 12 * runtime.GIB

    def memory_reserved(self):
        return 15 * runtime.GIB

    def max_memory_allocated(self):
        return self.peak

    def max_memory_reserved(self):
        return 36 * runtime.GIB


def guard_stub(monkeypatch, arm):
    guard = object.__new__(runtime.ResourceGuard)
    guard.job = worker.job_spec(137, "replay_" + arm)
    guard.gpu, guard.violation = 0, None
    guard.stop = SimpleNamespace(requested=True, reason="registered stop", received_signals=[])
    guard.observations, guard.preflight_observations = [], []
    guard.deferred_observation, guard.wait_seconds = None, 0
    guard.torch = SimpleNamespace(cuda=CudaStub())
    guard._host = lambda: dict(
        rss_bytes=12 * runtime.GIB, peak_rss_bytes=13 * runtime.GIB,
        rss_limit_bytes=192 * runtime.GIB, available_bytes=200 * runtime.GIB,
        available_reserve_bytes=96 * runtime.GIB, passed=True)
    guard._record = lambda value: None
    probes = []

    def known_shared(uuids):
        probes.extend(uuids)
        return {uuid: dict(gpu_uuid=uuid, allowed=True, process_count=1,
                           known_processes=[dict(pid=123, birth="1", uids=[1000] * 4)],
                           unresolved_processes=[]) for uuid in uuids}

    monkeypatch.setattr(runtime.isolation, "probe_gpus", known_shared)
    return guard, probes


def test_resource_classes_are_private_and_C1_uses_registered_R3_phase():
    assert runtime._base is not runtime.reference_base
    assert runtime._durable is not runtime.reference_recovery
    assert runtime._base.ResourceGuard is not runtime.reference_base.ResourceGuard
    assert runtime._durable.ResourceGuard is not runtime.reference_recovery.ResourceGuard
    assert runtime._durable.original is runtime._base
    assert runtime.reference_recovery.original is runtime.reference_base
    assert runtime.reference_recovery.ROOT == binding.OLD_ROOT
    assert runtime.kind(worker.job_spec(137, "replay_C1")) == "replay"
    assert runtime.MINIMUM_FREE_GIB["replay"] == 56
    assert runtime.resource_policy()["max_gpu_workers"] == binding.MAX_WORKERS == 6
    assert runtime.resource_recovery_policy()["replay_checkpoint_formal_and_draw_accumulators_atomic"]
    assert "shard00" not in worker.STAGES  # No new class pass is a dispatchable job.


@pytest.mark.parametrize("arm", ["C1", "C05"])
def test_registered_resource_constructor_matches_new_policies_without_entering_CUDA(
        tmp_path, monkeypatch, arm):
    for owner in (binding, runtime, runtime._base, runtime._durable):
        monkeypatch.setattr(owner, "ROOT", tmp_path)
    protocol = record(tmp_path / "protocol/record.json", dict(
        resource_policy=runtime.resource_policy(),
        resource_recovery_policy=runtime.resource_recovery_policy(),
        gpu_isolation_policy=runtime.isolation.gpu_isolation_policy(),
        max_gpu_workers=6, max_workers_per_gpu=1, allowed_gpu_indices=list(range(8)),
        gpu_uuids=runtime.GPU_UUIDS))
    stub = SimpleNamespace(cuda=CudaStub())
    guard = runtime.ResourceGuard(tmp_path, worker.job_spec(137, "replay_" + arm), 0,
                                  torch_module=stub)
    try:
        assert guard.kind == "replay" and guard.protocol == protocol
        assert guard._reset is None and guard._thread is None
        assert guard.torch is stub and not stub.cuda.calls
        assert guard.directory.is_relative_to(tmp_path / "resources")
    finally:
        guard._events.close()


@pytest.mark.parametrize("arm", ["C1", "C05"])
def test_new_replay_cooperative_stop_reaches_checkpoint_but_feedback_stop_is_immediate(
        monkeypatch, arm):
    guard, probes = guard_stub(monkeypatch, arm)
    value = guard.check("diagnostic_checkpoint_boundary", boundary=True)
    assert value["passed"] and value["stop_requested"]
    assert probes == [runtime.GPU_UUIDS["0"]]
    assert value["gpu_isolation"]["known_processes"][0]["uids"] == [1000] * 4
    if arm == "C1":
        # The old class still rejects this unregistered stage at the stop gate.
        with pytest.raises(runtime.reference_base.ExplicitStop):
            runtime.reference_recovery.ResourceGuard.ensure_capacity(guard, "old-C1")
    guard.job = worker.job_spec(137, "feedback_" + arm)
    with pytest.raises(runtime.ExplicitStop):
        guard.check("before_feedback_call")
    assert probes == [runtime.GPU_UUIDS["0"]]


def test_original_failed_R3_snapshot_cannot_be_replaced_by_later_free_memory(monkeypatch):
    guard, probes = guard_stub(monkeypatch, "C1")
    with pytest.raises(runtime.R3CapacityError):
        guard.check("after_response", response_backend_observation=dict(
            phase="after_response", torch_peak_allocated_bytes=34 * runtime.GIB,
            device_free_bytes_at_response_boundary=runtime.GIB))
    assert guard.deferred_observation["free_bytes"] == runtime.GIB
    assert guard.deferred_observation["completed_response_not_yet_accumulated"]
    assert not probes and not guard.torch.cuda.calls


@pytest.fixture
def parent_environment(tmp_path, monkeypatch):
    root, old = tmp_path / "new", tmp_path / "old"
    for owner in (binding, training):
        monkeypatch.setattr(owner, "ROOT", root)
        monkeypatch.setattr(owner, "OLD_ROOT", old)
    monkeypatch.setattr(worker, "ROOT", root)
    initial = dict(seed=137, step=596, pi={"task": {"a": 0.5, "b": 0.5}},
                   outer_done=[298], mock_parameter=4, mock_Adam_step=596, rng=17)
    plan = record(old / "parents/seed137/task_plan/record.json", dict(
        task_ids=[f"task{i}" for i in range(744)]))
    parent = record(old / "parents/seed137/record.json", dict(
        schema="original-parent", protocol_id=binding.OLD_PROTOCOL_ID, seed=137,
        c1_reuse={"eligible": True}, parent_checkpoint={"path": str(old / "pre596")},
        parent_state_digest=binding.digest(initial), old_outer_checkpoint={"path": "old-outer"},
        old_outer_inputs={"path": "old-virtual"}, old_outer_inputs_digest="virtual-digest",
        parameter_spec={"mock_parameter": [1]}, pool_id="pool", task_plan=binding.entry(
            old / "parents/seed137/task_plan/record.json"),
        mu={"task": 1}, point_id="fixed-pre596", component_digests={"rng": binding.digest(17)},
        parent_pi=copy.deepcopy(initial["pi"]), old_class_context=None,
        scientific_sources={"driver": {"id": "frozen-driver"}}))
    for arm in ("Hold", "C1", "C05"):
        record(old / f"branches/seed137/{arm}/completed/record.json", dict(
            status="COMPLETE", parent_state_digest=parent["parent_state_digest"]))
    old_bytes = {str(path): path.read_bytes() for path in old.rglob("*") if path.is_file()}
    inherited = training.prepare_parent(root, 137, "new-protocol")
    assert training.checked_parent(root, 137) == inherited
    rt = SimpleNamespace(v8=SimpleNamespace(_tree_digest=binding.digest))
    return SimpleNamespace(root=root, old=old, old_parent=parent, parent=inherited,
                           initial=initial, old_bytes=old_bytes, plan=plan, rt=rt)


def test_parent_and_class_cache_are_read_only_and_keep_original_loader_identity(
        parent_environment, monkeypatch):
    e, calls = parent_environment, []
    cache = SimpleNamespace(plan={"id": e.plan["id"], "task_ids": e.plan["task_ids"]})

    def original_loader(root, parent, rt):
        calls.append((root, parent, rt))
        return cache

    monkeypatch.setattr(worker.original, "load_cache", original_loader)
    assert worker.load_cache(e.root, e.parent, e.rt) is cache
    assert calls == [(e.old, e.old_parent, e.rt)]
    assert e.parent["new_class_task_count"] == 0
    assert e.parent["all_original_class_tasks_read_only"]
    assert e.parent["new_C1_branch_is_not_old_C1_reuse"]
    assert {str(path): path.read_bytes() for path in e.old.rglob("*") if path.is_file()} == e.old_bytes


class DriverStub:
    """Executes the real orchestration loop, but every optimizer/model is mock."""

    arm = "C-only"

    def __init__(self, environment, arm):
        self.environment = environment
        self.root = training.branch_root(environment.root, 137, arm) / "training"
        self.state = None
        self.steps, self.restores, self.commits = [], [], []
        self.outer_steps = (298, 596, 894, 1192)
        self.final_step = 1490

    @property
    def pi(self):
        return self.state["pi"]

    @pi.setter
    def pi(self, value):
        self.state["pi"] = value

    @property
    def outer_done(self):
        return self.state["outer_done"]

    @property
    def step_index(self):
        return self.state["step"]

    def _payload(self):
        return copy.deepcopy(self.state)

    def restore(self, path):
        self.restores.append(str(path))
        if str(path) == self.environment.parent["parent_checkpoint"]["path"]:
            self.state = copy.deepcopy(self.environment.initial)
        else:
            self.state = json.loads((Path(path) / "state.pt").read_bytes())

    def commit(self, phase, evidence):
        directory = self.root / f"step{self.step_index:04d}_{phase}"
        directory.mkdir(parents=True, exist_ok=False)
        raw = json.dumps(self.state, sort_keys=True).encode()
        (directory / "state.pt").write_bytes(raw)
        value = dict(
            seed=137, arm="C-only", step=self.step_index, phase=phase,
            pool_id="pool", state_sha256=hashlib.sha256(raw).hexdigest(),
            actual_state_digest=binding.digest(self.state),
            checkpoint_contains_actual_model_Adam_RNG_pi=True, evidence=evidence)
        (directory / "record.json").write_text(json.dumps(value))
        self.commits.append((self.step_index, phase))

    def step(self):
        assert self.outer_steps == () and self.final_step == 894
        self.state["step"] += 1
        self.state["mock_Adam_step"] += 1
        self.state["mock_parameter"] += 1
        self.state["rng"] += 1
        self.steps.append(self.step_index)
        result = dict(optimizer_step_calls=1, clip_calls=1)
        self.commit("step", result)
        return result


class MonitorStub:
    def __init__(self, stop_before=None):
        self.stop_before = stop_before
        self.steps = []

    def check_stop(self, label, **context):
        self.steps.append(context["step"])
        if context["step"] == self.stop_before:
            raise runtime.ExplicitStop("mock registered pause")

    def clear_unused(self, label):
        pass


@pytest.mark.parametrize("arm", ["C1", "C05"])
def test_each_new_arm_executes_exact_298_mock_driver_steps_and_native_snapshots(
        parent_environment, arm):
    e = parent_environment
    driver = DriverStub(e, arm)
    q = {"task": {"a": 0.6, "b": 0.4}}
    result = training.execute_training(
        e.root, 137, arm, "new-protocol", driver, q, rt=e.rt, monitor=MonitorStub(),
        distribution_source={"id": "new-q-source"})
    assert driver.steps == list(range(597, 895))
    assert driver.restores == [e.parent["parent_checkpoint"]["path"]]
    assert driver.commits[0] == (596, "branch")
    assert driver.pi == q and driver.outer_done == [298]
    assert result["optimizer_updates"] == result["new_optimizer_updates"] == 298
    assert result["updates_in_final_worker"] == 298 and result["feedback_batch"] == 1
    assert result["temperature"] == binding.TEMPERATURES[arm]
    assert set(result["snapshots"]) == {"745", "894"}
    assert result["next_outer894_executed"] is False
    assert training.checked_branch_result(e.root, 137, arm) == result
    assert {str(path): path.read_bytes() for path in e.old.rglob("*") if path.is_file()} == e.old_bytes


def test_cold_training_continues_only_uncommitted_steps_and_rejects_new_q(parent_environment):
    e, q = parent_environment, {"task": {"a": 0.6, "b": 0.4}}
    first = DriverStub(e, "C1")
    with pytest.raises(runtime.ExplicitStop):
        training.execute_training(
            e.root, 137, "C1", "new-protocol", first, q, rt=e.rt,
            monitor=MonitorStub(stop_before=701), distribution_source={"id": "same-q-source"})
    assert first.steps == list(range(597, 701))
    changed = DriverStub(e, "C1")
    with pytest.raises(ValueError, match="cold branch restore differs"):
        training.execute_training(
            e.root, 137, "C1", "new-protocol", changed, {"task": {"a": 0.7, "b": 0.3}},
            rt=e.rt, monitor=MonitorStub(), distribution_source={"id": "same-q-source"})
    assert not changed.steps and not changed.restores
    second = DriverStub(e, "C1")
    result = training.execute_training(
        e.root, 137, "C1", "new-protocol", second, q, rt=e.rt, monitor=MonitorStub(),
        distribution_source={"id": "same-q-source"})
    assert second.steps == list(range(701, 895))
    assert first.steps + second.steps == list(range(597, 895))
    assert second.restores == [str(second.root / "step0700_step")]
    assert result["updates_in_final_worker"] == 194
    assert result["new_optimizer_updates"] == 298


def test_worker_payload_record_matches_registration_coordinate_and_rejects_cross_arm(
        parent_environment):
    e = parent_environment
    rt = SimpleNamespace(torch=torch, v8=SimpleNamespace(
        _tree_digest=lambda value: binding.digest(
            {key: tensor.tolist() for key, tensor in value.items()})))
    value = {"gJ": torch.tensor([1.0, 2.0])}
    directory = worker.stage_root(e.root, 137, "replay_C1")
    reference = worker.save_payload(directory, value, e.parent, "replay_C1", rt)
    native = binding.checked(reference["path"])
    assert native["schema"] == "v63_actual_scientific_payload.v1"
    assert (native["feedback_batch"], native["arm"], native["temperature"]) == (1, "C1", 1.0)
    assert native["actual_tensors_saved"] and native["state_bytes"] > 0
    restored = worker.read_payload(directory, e.parent, "replay_C1", rt)
    assert torch.equal(restored["gJ"], value["gJ"])
    other = worker.stage_root(e.root, 137, "replay_C05") / "payload"
    other.mkdir(parents=True)
    for name in ("record.json", "state.pt"):
        (other / name).write_bytes((directory / "payload" / name).read_bytes())
    with pytest.raises(ValueError, match="payload scientific identity changed"):
        worker.read_payload(other.parent, e.parent, "replay_C05", rt)
