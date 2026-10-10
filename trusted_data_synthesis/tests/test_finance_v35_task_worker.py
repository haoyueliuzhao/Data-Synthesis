"""CPU/mock execution-shell checks, not CUDA numerical acceptance."""

import ast
import copy
import hashlib
import importlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v35_task_worker")
tail = importlib.import_module("finqa_v34_tail_worker")
immutable = importlib.import_module("trusted_synthesis.core.immutable_artifacts")


def digest(value):
    if isinstance(value, torch.Tensor):
        raw = value.detach().cpu().contiguous()
        value = dict(
            shape=list(raw.shape),
            dtype=str(raw.dtype),
            bytes=raw.reshape(-1).view(torch.uint8).numpy().tobytes().hex(),
        )
    if isinstance(value, dict):
        value = {str(k): digest(v) for k, v in value.items()}
    elif isinstance(value, (tuple, list)):
        value = [digest(v) for v in value]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Monitor:
    def __init__(self, fail_at=None):
        self.labels, self.fail_at = [], fail_at

    def clear_unused(self, label):
        self.labels.append(label)
        if label == self.fail_at:
            raise ValueError("mock resource gate failed")

    def check_stop(self, label, **context):
        self.labels.append(label)


class Cache:
    def __init__(self, tasks):
        self.tasks, self.values, self.receipts = list(tasks), {}, {}

    def has(self, task):
        return task in self.values

    def read(self, task):
        return self.values[task]

    def commit(self, task, values, receipt):
        assert task not in self.values
        self.values[task], self.receipts[task] = copy.deepcopy(values), receipt

    def coverage(self):
        return dict(
            missing_task_ids=[t for t in self.tasks if t not in self.values],
            complete_task_count=len(self.values),
        )

    def assemble(self, device):
        assert device == "cuda:0"
        if any(t not in self.values for t in self.tasks):
            raise ValueError("incomplete task cache")
        return {t: self.values[t] for t in self.tasks}


@pytest.fixture
def shard(tmp_path):
    model = torch.nn.Linear(2, 1, bias=False)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    model.weight.grad = torch.ones_like(model.weight)
    optimizer.step()  # Fixture builds nonempty Adam; production never steps.
    optimizer.zero_grad(set_to_none=False)
    model.weight.grad.fill_(3)
    runtime = SimpleNamespace(
        torch=SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda: None)),
        v8=SimpleNamespace(_tree_digest=digest),
    )

    def identity(rt, model, optimizer):
        return dict(
            parameters=digest(dict(model.named_parameters())),
            optimizer=digest(optimizer.state_dict()),
            buffers=digest(dict(model.named_buffers())),
            rng=digest(torch.get_rng_state()),
            modes=[m.training for m in model.modules()],
        )

    inherited = SimpleNamespace(state_identity=identity)
    cache, calls = Cache(["b", "a"]), []
    plan = dict(id="protocol")
    task_plan = dict(assignments=[dict(shard=0, task_ids=["b", "a"])])

    def class_pass(rt, received_model, pool, *, device, monitor):
        assert received_model is model and device == "cuda:0"
        calls.append(pool[0])
        values = {"s": {"weight": torch.ones_like(model.weight)}}
        return {pool[0]: SimpleNamespace(values_cpu=values)}, dict(rows_completed=2)

    return SimpleNamespace(
        directory=tmp_path,
        plan=plan,
        task_plan=task_plan,
        stage="shard00",
        pool=object(),
        cache=cache,
        model=model,
        optimizer=optimizer,
        rt=runtime,
        inherited=inherited,
        memory=SimpleNamespace(class_gradients_with_cpu_saves=class_pass),
        monitor=Monitor(),
        stop=SimpleNamespace(requested=False),
        cache_module=SimpleNamespace(TaskPoolView=lambda _pool, tasks: tasks),
        calls=calls,
    )


def run_shard(f):
    return worker.execute_shard(**{k: v for k, v in vars(f).items() if k != "calls"})


def test_complete_tasks_committed_once_preserving_existing_grad_and_adam(shard):
    before = worker.state_identity(shard.rt, shard.model, shard.optimizer, shard.inherited)
    result = run_shard(shard)
    assert shard.calls == ["b", "a"]
    assert list(shard.cache.values) == ["b", "a"]
    assert result["task_count"] == result["class_task_calls"] == 2
    assert result["new_completed_rows"] == 4
    assert before == worker.state_identity(shard.rt, shard.model, shard.optimizer, shard.inherited)
    assert all(r["state_unchanged"] for r in shard.cache.receipts.values())
    assert all(
        r["pre_state_identity"] == r["post_state_identity"] for r in shard.cache.receipts.values()
    )
    assert not torch.cuda.is_initialized()


def test_completed_task_is_read_without_kernel_reexecution(shard):
    shard.cache.values["b"] = {"s": {"weight": torch.ones(1, 2)}}
    result = run_shard(shard)
    assert shard.calls == ["a"]
    assert result["reused_task_ids"] == ["b"]
    assert result["class_task_calls"] == 1


@pytest.mark.parametrize("mutation", ["parameter", "existing_grad", "adam", "rng", "mode"])
def test_mutating_class_kernel_cannot_commit_a_task(shard, mutation):
    original = shard.memory.class_gradients_with_cpu_saves

    def mutate(*args, **kwargs):
        values = original(*args, **kwargs)
        if mutation == "parameter":
            with torch.no_grad():
                shard.model.weight.add_(1)
        elif mutation == "existing_grad":
            shard.model.weight.grad.add_(1)
        elif mutation == "adam":
            shard.optimizer.state[shard.model.weight]["exp_avg"].add_(1)
        elif mutation == "rng":
            torch.rand(1)
        else:
            shard.model.eval()
        return values

    shard.memory.class_gradients_with_cpu_saves = mutate
    with pytest.raises(ValueError, match="task changed"):
        run_shard(shard)
    assert not shard.cache.values


def test_interrupted_task_not_committed_prior_whole_task_retained(shard):
    original = shard.memory.class_gradients_with_cpu_saves

    def fail(*args, **kwargs):
        if shard.calls:
            raise RuntimeError("simulated current-task interruption")
        return original(*args, **kwargs)

    shard.memory.class_gradients_with_cpu_saves = fail
    with pytest.raises(RuntimeError, match="interruption"):
        run_shard(shard)
    assert list(shard.cache.values) == ["b"]


@pytest.fixture
def coordinator(tmp_path):
    model = torch.nn.Linear(2, 1, bias=False)
    gradient = {"weight": torch.tensor([[1.25, -2.5]])}
    prepared = dict(G={"weight": torch.ones(1, 2)}, theta_bar={"weight": torch.ones(1, 2) * 2})
    result = dict(
        a={"weight": torch.ones(1, 2) * 3},
        C={"b": {"s": 0.0}},
        distribution={"pi_next": {"b": {"s": 1.0}}},
    )
    actual = dict(
        gJ=copy.deepcopy(gradient),
        G=copy.deepcopy(prepared["G"]),
        theta_bar=copy.deepcopy(prepared["theta_bar"]),
        point_id="point",
        pullback=copy.deepcopy(result["a"]),
        C=copy.deepcopy(result["C"]),
        q_next=copy.deepcopy(result["distribution"]["pi_next"]),
        mu={"b": 1.0},
        pre_state={"pi": {"b": {"s": 1.0}}, "prior": {"b": {"s": 1.0}}},
    )
    cache, calls = Cache(["b", "a"]), []
    cache.values = {"a": {"s": {}}, "b": {"s": {}}}

    def prepare(parameters, optimizer, gradients, pi, mu):
        assert list(gradients) == ["b", "a"]
        assert mu is actual["mu"] and pi is actual["pre_state"]["pi"]
        calls.append("prepare")
        return prepared

    def update(received, gradients, gJ, pi, prior, mu, **kwargs):
        assert received is prepared and list(gradients) == ["b", "a"]
        assert gJ is not actual["gJ"] and torch.equal(gJ["weight"], gradient["weight"])
        assert kwargs["contribution_only"] and kwargs["control_tasks"] == ["b"]
        calls.append("update")
        return result

    runtime = SimpleNamespace(
        torch=SimpleNamespace(save=torch.save, cuda=SimpleNamespace(synchronize=lambda: None)),
        v8=SimpleNamespace(
            _tree_digest=digest,
            parameter_digest=digest,
            prepare_virtual_point=prepare,
            update_distribution=update,
            PARAMETERS={},
        ),
    )
    return SimpleNamespace(
        directory=tmp_path,
        plan=dict(id="protocol", saved_gJ_digest=digest(gradient)),
        actual=actual,
        gradient=gradient,
        feedback_report={"reused_completed_responses": 573},
        cache=cache,
        model=model,
        optimizer=object(),
        rt=runtime,
        inherited=SimpleNamespace(state_identity=lambda *_: {"unchanged": True}),
        guard=SimpleNamespace(recompute_point_id=lambda *_a, **_k: "point"),
        monitor=Monitor(),
        stop=SimpleNamespace(requested=False),
        immutable=immutable,
        tail=tail,
        calls=calls,
        prepared=prepared,
        computed=result,
    )


def run_coordinator(f):
    return worker.execute_coordinator(
        **{k: v for k, v in vars(f).items() if k not in {"calls", "prepared", "computed"}}
    )


def test_coordinator_global_math_once_no_class_pass(coordinator):
    result = run_coordinator(coordinator)
    assert coordinator.calls == ["prepare", "update"]
    assert result["class_gradient_passes"] == 0
    assert result["global_class_gradient_passes"] == 1
    assert result["numeric_pass"] and all(result["comparison"].values())
    assert result["reused_completed_responses"] == 573 and result["replayed_responses"] == 0
    saved = torch.load(coordinator.directory / "numeric_payload/state.pt", weights_only=False)
    assert torch.equal(saved["aggregate_G"]["weight"], coordinator.prepared["G"]["weight"])
    assert saved["C"] == coordinator.computed["C"]


def test_incomplete_cache_refuses_global_math(coordinator):
    coordinator.cache.values.pop("a")
    with pytest.raises(ValueError, match="incomplete task cache"):
        run_coordinator(coordinator)
    assert not coordinator.calls


@pytest.mark.parametrize("changed", ["point", "G", "theta_bar", "gJ_reference"])
def test_wrong_global_point_stops_before_distribution(coordinator, changed):
    if changed == "point":
        coordinator.guard.recompute_point_id = lambda *_a, **_k: "other-point"
    elif changed == "gJ_reference":
        coordinator.actual["gJ"]["weight"].add_(1)
    else:
        coordinator.prepared[changed]["weight"].add_(1)
    with pytest.raises(ValueError, match="no distribution update"):
        run_coordinator(coordinator)
    assert coordinator.calls == ["prepare"]
    point = worker.control.checked(coordinator.directory / "point_comparison/record.json")
    assert not all(point["comparison"].values())
    assert not (coordinator.directory / "numeric_comparison/record.json").exists()
    assert not (coordinator.directory / "numeric_payload/state.pt").exists()


def test_virtual_point_resource_failure_stops_before_distribution(coordinator):
    coordinator.monitor.fail_at = "virtual_point_complete"
    with pytest.raises(ValueError, match="resource gate"):
        run_coordinator(coordinator)
    assert coordinator.calls == ["prepare"]
    point = worker.control.checked(coordinator.directory / "point_comparison/record.json")
    assert all(point["comparison"].values())
    assert not (coordinator.directory / "numeric_comparison/record.json").exists()


def test_numerical_payload_is_preserved_before_final_resource_failure(coordinator):
    coordinator.monitor.fail_at = "after_distribution"
    with pytest.raises(ValueError, match="resource gate"):
        run_coordinator(coordinator)
    comparison = worker.control.checked(coordinator.directory / "numeric_comparison/record.json")
    assert comparison["numeric_pass"]
    assert (coordinator.directory / "numeric_payload/state.pt").exists()


def test_true_numerical_disagreement_is_saved_not_replaced_by_reference(coordinator):
    coordinator.computed["a"]["weight"].add_(1)
    with pytest.raises(ValueError, match="numerical comparison failed"):
        run_coordinator(coordinator)
    comparison = worker.control.checked(coordinator.directory / "numeric_comparison/record.json")
    assert not comparison["comparison"]["pullback_bitwise_equal"]
    saved = torch.load(coordinator.directory / "numeric_payload/state.pt", weights_only=False)
    assert not torch.equal(saved["pullback"]["weight"], coordinator.actual["pullback"]["weight"])


def gpu_event():
    return dict(passed=True, label="class_row_end", allocated_pass=True, free_pass=True)


@pytest.mark.parametrize("stage,limit", [("shard00", 160), ("coordinator", 192)])
def test_exact_host_limits_and_combined_events(stage, limit):
    published = []
    events = worker.ResourceEvents(
        published.append,
        stage=stage,
        deadline_epoch=time.time() + 60,
        stop=SimpleNamespace(requested=False),
        read_host=lambda: dict(
            rss_bytes=limit * worker.GIB,
            peak_rss_bytes=limit * worker.GIB,
            available_bytes=96 * worker.GIB,
        ),
    )
    events(gpu_event())
    assert published[0]["passed"]
    assert events.report()["rss_limit_bytes"] == limit * worker.GIB
    assert events.report()["all_passed"]


@pytest.mark.parametrize("rss,available", [(161, 100), (159, 95)])
def test_host_failure_is_published_before_throwing(rss, available):
    published = []
    events = worker.ResourceEvents(
        published.append,
        stage="shard03",
        deadline_epoch=time.time() + 60,
        stop=SimpleNamespace(requested=False),
        read_host=lambda: dict(
            rss_bytes=rss * worker.GIB,
            peak_rss_bytes=rss * worker.GIB,
            available_bytes=available * worker.GIB,
        ),
    )
    with pytest.raises(ValueError, match="host RAM"):
        events(gpu_event())
    assert len(published) == 1 and not published[0]["passed"]


def test_shared_deadline_is_not_reset_at_phase_boundary():
    published = []
    events = worker.ResourceEvents(
        published.append,
        stage="coordinator",
        deadline_epoch=time.time() - 1,
        stop=SimpleNamespace(requested=False),
        read_host=lambda: dict(
            rss_bytes=worker.GIB, peak_rss_bytes=worker.GIB, available_bytes=96 * worker.GIB
        ),
    )
    assert events.stopped()
    with pytest.raises(ValueError, match="shared global deadline"):
        events(gpu_event())
    assert not published[0]["deadline_pass"]


def test_frozen_parameter_version_and_existing_grad_are_in_state_identity(shard):
    shard.model.register_parameter("base", torch.nn.Parameter(torch.ones(2), requires_grad=False))
    before = worker.state_identity(shard.rt, shard.model, shard.optimizer, shard.inherited)
    with torch.no_grad():
        shard.model.base.add_(1)
    after = worker.state_identity(shard.rt, shard.model, shard.optimizer, shard.inherited)
    assert before["frozen_parameter_storage_versions"] != after["frozen_parameter_storage_versions"]


def test_production_ast_has_no_optimizer_step_replay_or_old_tail_execution():
    tree = ast.parse(Path(worker.__file__).read_text())
    calls = [
        n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]
    assert "step" not in calls
    assert "execute_tail" not in calls and "run" not in calls
    assert calls.count("reset_peak_memory_stats") == 1
    coord = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "execute_coordinator"
    )
    coord_calls = [
        n.func.attr
        for n in ast.walk(coord)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]
    assert "class_gradients_with_cpu_saves" not in coord_calls
    assert (
        coord_calls.count("prepare_virtual_point") == coord_calls.count("update_distribution") == 1
    )
