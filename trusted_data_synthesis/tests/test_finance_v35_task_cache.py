"""CPU/frozen-source controls, not production CUDA numerical evidence."""

import copy
import importlib
import importlib.util
import json
import multiprocessing
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
cache_module = importlib.import_module("finqa_v35_task_cache")
memory = importlib.import_module("finqa_v34_tail_memory")
FROZEN_SOURCE = Path(__file__).parents[2] / (
    ".codex-worktrees/finqa-v18-researcher-continuation-20260930/"
    "trusted_data_synthesis/src/trusted_synthesis/finance_research/v8_training_driver.py"
)
spec = importlib.util.spec_from_file_location(
    "trusted_synthesis.finance_research._v35_cpu_frozen_reference", FROZEN_SOURCE
)
v8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v8)
RT = SimpleNamespace(torch=torch, v8=v8)


class TinyModel(torch.nn.Module):
    def __init__(self, dtype=torch.float32):
        super().__init__()
        self.embedding = torch.nn.Embedding(9, 5).requires_grad_(False)
        self.output = torch.nn.Linear(5, 9, bias=True)
        self.register_buffer("registered_buffer", torch.tensor([7.0]))
        self.to(dtype=dtype)

    def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
        hidden = self.embedding(input_ids)[:, logits_to_keep, :]
        logits = hidden.transpose(1, 2).transpose(1, 2) @ self.output.weight.T
        return SimpleNamespace(logits=logits + self.output.bias)


def tiny_pool():
    task_ids = [f"task{index}/unsafe:path" for index in range(8)]
    packages, rows = [], {}
    # Global packages are interleaved. Filtering must preserve the original
    # per-task/state/package/row order, including two packages for one state.
    for round_index in range(3):
        for index, task_id in enumerate(task_ids):
            if round_index >= 1 + index % 3:
                continue
            package_id = f"p{index}_{round_index}"
            state_id = "second" if index % 2 and round_index > 0 else "first"
            row_count = 1 + (index + round_index) % 2
            row = dict(
                input_ids=[1, 2, 3, 4] + [5] * (index % 3),
                target_positions=[2, 3],
                target_ids=[(index + round_index) % 8, 4],
            )
            rows[package_id] = [copy.deepcopy(row) for _ in range(row_count)]
            rows[package_id].insert(0, dict(input_ids=[1, 2], target_positions=[], target_ids=[]))
            packages.append(
                dict(
                    task_id=task_id,
                    state_id=state_id,
                    package_id=package_id,
                    whole_package_target_tokens=2 * row_count,
                )
            )
    return v8.VerifiedPool(
        task_ids, packages, rows, binding_id="v35_cpu_mock_only", chi={}, production=False
    )


def tiny_model_optimizer(dtype=torch.float32):
    # Frozen class_gradients imports this dependency before its RNG snapshot.
    # First-import initialization changes Python RNG, so production and fixtures
    # both load dependencies before constructing/restoring the registered state.
    importlib.import_module(
        "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer"
    )
    torch.set_num_threads(1)
    torch.manual_seed(31415)
    model = TinyModel(dtype)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad])
    for index, parameter in enumerate(model.parameters()):
        if parameter.requires_grad:
            parameter.grad = torch.full_like(parameter, (index + 1) * 0.125)
    optimizer.step()
    assert optimizer.state
    # Retain deliberately nonzero .grad buffers and nonempty Adam state.
    return model, optimizer


def parameter_spec(model):
    return [
        dict(name=name, shape=list(value.shape), dtype=str(value.dtype))
        for name, value in model.named_parameters()
        if value.requires_grad
    ]


def state_identity(model, optimizer):
    return v8._tree_digest(
        dict(
            model=model.state_dict(),
            optimizer=optimizer.state_dict(),
            grads={name: value.grad for name, value in model.named_parameters()},
            modes={name: module.training for name, module in model.named_modules()},
            rng=v8._rng(),
        )
    )


def monitor():
    return SimpleNamespace(
        check_stop=lambda *args, **kwargs: None, snapshot=lambda *args, **kwargs: None
    )


def task_values(model, pool, task_id):
    view = cache_module.TaskPoolView(pool, [task_id])
    result, receipt = memory.class_gradients_with_cpu_saves(
        RT,
        model,
        view,
        device="cpu",
        monitor=monitor(),
        cpu_test=True,
    )
    assert list(result) == [task_id]
    assert receipt["saved_tensors"]["packed_live_count"] == 0
    return result[task_id].values_cpu


def assert_equal_gradients(expected, actual):
    assert list(expected) == list(actual)
    for task in expected:
        assert list(expected[task]) == list(actual[task])
        for state in expected[task]:
            assert list(expected[task][state]) == list(actual[task][state])
            for name in expected[task][state]:
                left, right = expected[task][state][name], actual[task][state][name]
                assert left.dtype == right.dtype
                assert torch.equal(
                    left.reshape(-1).view(torch.uint8), right.reshape(-1).view(torch.uint8)
                )


BINDING = dict(
    point_id="original_actual_point",
    prestate_sha256="actual_prestate",
    material_id="frozen_material",
    storage_source_sha256="frozen_v34_storage",
    numerical_source_sha256="frozen_v18_numerics",
    implementation_id="cpu_fixture",
)


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
@pytest.mark.parametrize("shards", [1, 2, 4])
def test_complete_tasks_frozen_cpu_bitwise_and_all_live_state_unchanged(tmp_path, dtype, shards):
    model, optimizer = tiny_model_optimizer(dtype)
    pool = tiny_pool()
    spec = parameter_spec(model)
    plan = cache_module.make_task_plan(pool, spec, shards=shards)
    assert Path(v8.class_gradients.__code__.co_filename).resolve() == FROZEN_SOURCE.resolve()
    before = state_identity(model, optimizer)
    expected = v8.class_gradients(model, pool, device="cpu")
    cache = cache_module.TaskCache(tmp_path / "cache", BINDING, plan, spec, RT)
    # Reverse shard order and task completion order independently of final order.
    for assignment in reversed(plan["assignments"]):
        for task_id in reversed(assignment["task_ids"]):
            cache.commit(task_id, task_values(model, pool, task_id))
    actual = cache.assemble()
    assert_equal_gradients(expected, actual)
    assert state_identity(model, optimizer) == before
    assert plan["all_singleton_control_tasks_included"]
    assert not plan["local_mu_or_pi_recomputed"]
    assert plan["global_registration"]["mu"] == pool._manifest.registration.mu
    assert cache.coverage()["complete_task_count"] == len(pool.task_ids)
    assert cache.validate_complete()["complete_task_count"] == len(pool.task_ids)
    assert len(cache.completed_records()) == len(pool.task_ids)
    assert all((tmp_path / "cache" / f"task{i:04d}").is_dir() for i in range(8))
    assert not torch.cuda.is_initialized()


def test_task_view_preserves_original_global_registration_and_whole_packages():
    pool = tiny_pool()
    selected = [pool.task_ids[7], pool.task_ids[1], pool.task_ids[3]]
    view = cache_module.TaskPoolView(pool, selected)
    assert list(view.task_ids) == [task for task in pool.task_ids if task in selected]
    assert view._manifest is pool._manifest
    assert view._manifest.registration.mu == {task: "1/8" for task in pool.task_ids}
    assert view.packages == tuple(p for p in pool.packages if p["task_id"] in selected)
    for p in view.packages:
        assert view.row_arrays(p["package_id"]) == pool.row_arrays(p["package_id"])
    with pytest.raises(ValueError, match="outside"):
        view.row_arrays("p0_0")
    with pytest.raises(ValueError, match="unknown"):
        cache_module.TaskPoolView(pool, ["invented"])
    with pytest.raises(ValueError, match="duplicate"):
        cache_module.TaskPoolView(pool, [pool.task_ids[0]] * 2)


def test_plan_bindings_cost_complete_rows_denominators_and_stable_ties():
    model, _ = tiny_model_optimizer()
    pool = tiny_pool()
    plan = cache_module.make_task_plan(pool, parameter_spec(model))
    assert cache_module.validate_plan(plan, pool) is plan
    assert plan == cache_module.make_task_plan(pool, parameter_spec(model))
    assert [task["task_id"] for task in plan["tasks"]] == list(pool.task_ids)
    assert plan["row_count"] == sum(len(pool.row_arrays(p["package_id"])) for p in pool.packages)
    assert plan["input_tokens"] == sum(
        len(row["input_ids"]) for p in pool.packages for row in pool.row_arrays(p["package_id"])
    )
    assert sorted(
        task for assignment in plan["assignments"] for task in assignment["task_ids"]
    ) == sorted(pool.task_ids)
    for assignment in plan["assignments"]:
        assert assignment["task_indices"] == sorted(assignment["task_indices"])
    changed = tiny_pool()
    changed._rows["p0_0"][1]["input_ids"][0] = 8
    with pytest.raises(ValueError, match="frozen actual pool"):
        cache_module.validate_plan(plan, changed)
    changed._packages[0]["whole_package_target_tokens"] += 1
    with pytest.raises(ValueError, match="denominator"):
        cache_module.make_task_plan(changed, parameter_spec(model))
    with pytest.raises(ValueError, match="planning source"):
        cache_module.make_task_plan(
            cache_module.TaskPoolView(pool, [pool.task_ids[0]]), parameter_spec(model)
        )


def test_cache_reuse_skips_compute_and_missing_task_never_zero_filled(tmp_path):
    model, _ = tiny_model_optimizer()
    pool = tiny_pool()
    spec = parameter_spec(model)
    plan = cache_module.make_task_plan(pool, spec)
    cache = cache_module.TaskCache(tmp_path, BINDING, plan, spec, RT)
    task = pool.task_ids[0]
    calls = []

    def compute():
        calls.append(task)
        return task_values(model, pool, task)

    first, reused = cache.get_or_compute(task, compute)
    assert not reused and calls == [task]
    second, reused = cache.get_or_compute(
        task, lambda: pytest.fail("must not recompute a complete task")
    )
    assert reused and v8._tree_digest(first) == v8._tree_digest(second)
    assert cache.coverage()["missing_task_ids"] == list(pool.task_ids[1:])
    with pytest.raises(ValueError, match="missing complete"):
        cache.assemble()
    with pytest.raises(ValueError, match="missing complete"):
        cache.validate_complete()
    with pytest.raises(FileExistsError, match="immutable"):
        cache.commit(task, first)


@pytest.mark.parametrize(
    "alteration", ["NaN", "missing_state", "state_order", "parameter_order", "dtype", "shape"]
)
def test_cache_refuses_invalid_or_incomplete_values(tmp_path, alteration):
    model, _ = tiny_model_optimizer()
    pool = tiny_pool()
    spec = parameter_spec(model)
    plan = cache_module.make_task_plan(pool, spec)
    cache = cache_module.TaskCache(tmp_path, BINDING, plan, spec, RT)
    task = pool.task_ids[1]
    values = task_values(model, pool, task)
    state = next(iter(values))
    name = next(iter(values[state]))
    if alteration == "NaN":
        values[state][name].reshape(-1)[0] = float("nan")
    elif alteration == "missing_state":
        values.pop(state)
    elif alteration == "state_order":
        values = dict(reversed(list(values.items())))
    elif alteration == "parameter_order":
        values[state] = dict(reversed(list(values[state].items())))
    elif alteration == "dtype":
        values[state][name] = values[state][name].double()
    elif alteration == "shape":
        values[state][name] = values[state][name].reshape(-1)
    with pytest.raises(ValueError):
        cache.commit(task, values)
    assert not cache.directory(task).exists()


@pytest.mark.parametrize(
    "key",
    [
        "point_id",
        "prestate_sha256",
        "storage_source_sha256",
        "numerical_source_sha256",
        "material_id",
    ],
)
def test_cache_rejects_wrong_source_binding_even_if_plan_same(tmp_path, key):
    model, _ = tiny_model_optimizer()
    pool = tiny_pool()
    spec = parameter_spec(model)
    plan = cache_module.make_task_plan(pool, spec)
    cache = cache_module.TaskCache(tmp_path, BINDING, plan, spec, RT)
    task = pool.task_ids[0]
    cache.commit(task, task_values(model, pool, task))
    changed = {**BINDING, key: "different"}
    wrong = cache_module.TaskCache(tmp_path, changed, plan, spec, RT)
    with pytest.raises(ValueError, match="binding/point/source"):
        wrong.has(task)
    with pytest.raises(ValueError, match="binding/point/source"):
        cache_module.inspect_completed(tmp_path, changed, plan)


@pytest.mark.parametrize(
    "corruption", ["file_bytes", "record_id", "partial_directory", "semantic_payload", "extra_file"]
)
def test_cache_rejects_corruption_or_partial_publication(tmp_path, monkeypatch, corruption):
    model, _ = tiny_model_optimizer()
    pool = tiny_pool()
    spec = parameter_spec(model)
    plan = cache_module.make_task_plan(pool, spec)
    cache = cache_module.TaskCache(tmp_path, BINDING, plan, spec, RT)
    task = pool.task_ids[0]
    if corruption == "partial_directory":
        cache.directory(task).mkdir()
    else:
        cache.commit(task, task_values(model, pool, task))
        if corruption == "file_bytes":
            path = cache.directory(task) / "gradient.pt"
            path.write_bytes(path.read_bytes() + b"corruption")
        elif corruption == "record_id":
            path = cache.directory(task) / "record.json"
            record = json.loads(path.read_bytes())
            record["receipt"] = "unauthorized change"
            path.write_bytes(cache_module.json_bytes(record))
        elif corruption == "extra_file":
            (cache.directory(task) / "temporary.pt").write_bytes(b"partial")
        elif corruption == "semantic_payload":
            original = torch.load

            def altered(*args, **kwargs):
                payload = original(*args, **kwargs)
                next(iter(next(iter(payload["values_cpu"].values())).values())).add_(1)
                return payload

            monkeypatch.setattr(torch, "load", altered)
    with pytest.raises(ValueError):
        cache.read(task)
    if corruption != "semantic_payload":
        with pytest.raises(ValueError):
            cache_module.inspect_completed(tmp_path, BINDING, plan)


def test_staging_siblings_never_count_as_completed(tmp_path):
    model, _ = tiny_model_optimizer()
    pool = tiny_pool()
    spec = parameter_spec(model)
    plan = cache_module.make_task_plan(pool, spec)
    (tmp_path / ".task0000.staging-unfinished").mkdir()
    (tmp_path / ".task0000.write-lock").mkdir()
    assert cache_module.inspect_completed(tmp_path, BINDING, plan) == []


def _child_compute(root, plan, shard):
    model, optimizer = tiny_model_optimizer()
    before = state_identity(model, optimizer)
    pool = tiny_pool()
    cache_module.validate_plan(plan, pool)
    cache = cache_module.TaskCache(root, BINDING, plan, parameter_spec(model), RT)
    for task_id in reversed(plan["assignments"][shard]["task_ids"]):
        cache.commit(
            task_id, task_values(model, pool, task_id), receipt={"cpu_process_shard": shard}
        )
    assert state_identity(model, optimizer) == before
    assert not torch.cuda.is_initialized()


def test_four_real_cpu_processes_publish_disjoint_tasks_then_global_order_assemble(tmp_path):
    model, optimizer = tiny_model_optimizer()
    pool = tiny_pool()
    spec = parameter_spec(model)
    plan = cache_module.make_task_plan(pool, spec, shards=4)
    assert all(assignment["task_ids"] for assignment in plan["assignments"])
    before = state_identity(model, optimizer)
    reference = v8.class_gradients(model, pool, device="cpu")
    context = multiprocessing.get_context("spawn")
    children = [
        context.Process(target=_child_compute, args=(str(tmp_path), plan, shard))
        for shard in (3, 0, 2, 1)
    ]
    try:
        for child in children:
            child.start()
        for child in children:
            child.join(timeout=60)
            assert child.exitcode == 0
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
                child.join(timeout=10)
    cache = cache_module.TaskCache(tmp_path, BINDING, plan, spec, RT)
    assert_equal_gradients(reference, cache.assemble())
    records = cache_module.inspect_completed(tmp_path, BINDING, plan)
    assert [record["task_id"] for record in records] == list(pool.task_ids)
    assert {record["record"]["receipt"]["cpu_process_shard"] for record in records} == {0, 1, 2, 3}
    assert state_identity(model, optimizer) == before
