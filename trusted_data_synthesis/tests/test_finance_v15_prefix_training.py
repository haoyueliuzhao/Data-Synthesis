"""State-free prefix CPU acceptance; no real Qwen/GPU/API or temporary states."""

import copy
import json
from collections import Counter
from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_consumer
from trusted_synthesis.finance_research import v15_prefix_training as prefix
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.v8_training_driver import _restore_rng, _rng, _tree_digest
from trusted_synthesis.finance_research.v9_conditional_training import (
    ConditionalTrainingDriver,
    build_task_schedule,
)
from trusted_synthesis.finance_research.v15_prefix_material import (
    PrefixPool,
    material_order_identity,
)


class TinyDropoutModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.arange(20, dtype=torch.float32).reshape(4, 5) / 10)
        self.dropout = torch.nn.Dropout(0.2)

    def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
        return SimpleNamespace(logits=self.dropout(self.weight[input_ids])[:, logits_to_keep])


@pytest.fixture(autouse=True)
def cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def material():
    tasks, packages, encodings = [f"t{i}" for i in range(9)], [], {}
    for task in tasks:
        for package_index in range(2 if task == "t0" else 3):
            sid = task + f"/p{package_index}"
            rows = []
            for index, positions in enumerate(([], [1, 3], [2] if package_index % 2 else [1, 2])):
                ids = [0, 1, 2, 3]
                row = dict(
                    turn_index=index,
                    input_ids=ids,
                    target_positions=positions,
                    target_ids=[ids[p] for p in positions],
                )
                rows.append(row | dict(row_sha256=digest(row)))
            encodings[sid] = dict(rows=rows)
            packages.append(
                dict(
                    package_id=sid,
                    task_id=task,
                    fused=False,
                    whole_package_target_tokens=sum(len(r["target_ids"]) for r in rows),
                )
            )
    order = material_order_identity(tasks, packages, encodings)
    return PrefixPool(
        task_ids=tasks,
        packages=packages,
        encodings=encodings,
        binding_ref=dict(id="synthetic-prefix", path="CPU-only-binding", sha256="synthetic"),
        token_binding=("cpu-tokenizer", "cpu-template"),
        material_order_id=order,
        production=False,
    )


def optimizer(model):
    return torch.optim.AdamW(
        model.parameters(),
        lr=1e-4,
        betas=(0.9, 0.999),
        eps=1e-8,
        weight_decay=0,
        foreach=False,
        fused=False,
    )


def warmed():
    model = TinyDropoutModel()
    opt = optimizer(model)
    # Actual nonempty Adam moments, not a claimed production prefix update.
    (model.weight.square().sum()).backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
    opt.step()
    opt.zero_grad(set_to_none=True)
    return model, opt


def driver(path, pool=None):
    model, opt = warmed()
    return prefix.PrefixDriver(model, opt, pool or material(), root=path, seed=11, cpu_control=True)


def partition_examples(pool, tasks, mode):
    examples = prefix.direct_batch_examples(pool, tasks)
    states = {}
    for task in pool.task_ids:
        members = [p for p in pool.packages if p["task_id"] == task]
        for i, p in enumerate(members):
            states[p["package_id"]] = (
                "one"
                if mode == "one"
                else f"p{i}"
                if mode == "per_package"
                else "first"
                if i == 0
                else "remainder"
            )
    counts = Counter((p["task_id"], states[p["package_id"]]) for p in pool.packages)
    n_x = Counter(p["task_id"] for p in pool.packages)
    for example in examples:
        task, sid = example["task_id"], example["package_id"]
        n_xz = counts[task, states[sid]]
        prior = Fraction(n_xz, n_x[task])
        coefficient = prior / (len(tasks) * n_xz * example["whole_package_target_tokens"])
        example["target_token_coefficient"] = str(coefficient)
        example["coefficient_float"] = float(coefficient)
    return examples


@pytest.mark.parametrize("batch_index", [0, 1])
def test_nonempty_adam_dropout_rng_matches_three_legal_prior_partitions(batch_index):
    pool = material()
    tasks = build_task_schedule(pool.task_ids, 11)["batches"][batch_index]["task_ids"]
    assert len(tasks) == (5 if batch_index == 0 else 4)
    original, old_opt = warmed()
    torch.manual_seed(909)
    rng = _rng()
    results = []
    for mode in ("direct", "one", "per_package", "unequal"):
        model = copy.deepcopy(original)
        opt = optimizer(model)
        opt.load_state_dict(copy.deepcopy(old_opt.state_dict()))
        assert opt.state and next(iter(opt.state.values()))["step"].item() == 1
        _restore_rng(rng)
        examples = (
            prefix.direct_batch_examples(pool, tasks)
            if mode == "direct"
            else partition_examples(pool, tasks, mode)
        )
        assert all("state_id" not in example for example in examples)
        gradients = {}

        def event(row, gradients=gradients, model=model):
            if row["event"] in ("package_backward_completed", "before_optimizer_step"):
                gradients[row["event"]] = {
                    n: p.grad.detach().clone() for n, p in model.named_parameters()
                }

        report = trajectory_consumer.execute_update(
            model,
            opt,
            examples,
            {"tasks": tasks},
            pool="CPU_control",
            arm="prior_oracle",
            device="cpu",
            trajectory_cache=pool,
            event_sink=event,
        )
        results.append(
            _tree_digest(
                dict(
                    weighted_loss=report["weighted_loss"],
                    gradient_norm=report["preclip_gradient_norm"],
                    gradients_before_and_after_clip=gradients,
                    parameters=dict(model.named_parameters()),
                    Adam=opt.state_dict(),
                    RNG=_rng(),
                )
            )
        )
    assert len(set(results)) == 1


def test_formal_first_step_restore_is_not_an_extra_update_and_resume_is_exact(tmp_path):
    run = driver(tmp_path / "uninterrupted")
    torch.manual_seed(919)
    first = run.step()
    assert run.step_index == 1 and run.consumption["updates"] == 1
    assert next(iter(run.optimizer.state.values()))["step"].item() == 2
    acceptance = prefix.read_bound(run.root / "first_step_acceptance/record.json")
    assert acceptance["same_actual_state"] and acceptance["additional_optimizer_steps"] == 0
    assert not acceptance["repeat_first_update"] and not acceptance["separate_validation_update"]
    assert first["loss_rule"] == prefix.LOSS_RULE and not first["state_or_pi_used"]
    assert first["optimizer_step_calls"] == first["clip_calls"] == first["zero_grad_calls"] == 1
    second = run.step()
    assert second["actual_batch_size"] == 4
    saved = run.root / "step0002_step"
    run.run_until()
    final = _tree_digest(run._payload())
    resumed = driver(tmp_path / "resumed", run.pool)
    resumed.restore(saved)
    resumed.run_until()
    assert _tree_digest(resumed._payload()) == final
    assert run.stop_step == 4 and run.consumption["packages"] == 2 * len(run.pool.packages)
    assert run.consumption["supervised_tokens"] == 2 * sum(
        p["whole_package_target_tokens"] for p in run.pool.packages
    )
    assert not hasattr(run, "outer_update") and not hasattr(run, "pi") and not hasattr(run, "prior")
    with pytest.raises(ValueError, match="hard stop"):
        run.step()
    with pytest.raises(ValueError, match="common prefix"):
        run.run_until(5)


@pytest.mark.parametrize("kind", ["resource", "numerical"])
def test_failed_uncommitted_step_is_distinct_from_committed_update(tmp_path, monkeypatch, kind):
    run = driver(tmp_path / kind)
    before = _tree_digest(
        dict(parameters=dict(run.model.named_parameters()), optimizer=run.optimizer.state_dict())
    )
    if kind == "resource":

        def fail(*args, **kwargs):
            raise torch.cuda.OutOfMemoryError("synthetic CPU control out of memory")

        monkeypatch.setattr(trajectory_consumer, "execute_update", fail)
    else:
        with torch.no_grad():
            run.model.weight.fill_(float("nan"))
    with pytest.raises((RuntimeError, ValueError)):
        run.step()
    assert run.committed_step == run.step_index == 0 and run.tainted
    failure = prefix.read_bound(run.root / "failures/attempt001/record.json")
    assert failure["failure_kind"] == kind + "_failure"
    assert (
        not failure["optimizer_step_started"] and not failure["failed_update_counted_as_committed"]
    )
    assert run.consumption["updates"] == 0
    if kind == "resource":
        assert before == _tree_digest(
            dict(
                parameters=dict(run.model.named_parameters()), optimizer=run.optimizer.state_dict()
            )
        )
    with pytest.raises(ValueError, match="explicit committed-state restore"):
        run.step()


def full_control(pool):
    packages, counts = [], {}
    for task in pool.task_ids:
        row = [p for p in pool.packages if p["task_id"] == task]
        counts[task] = Counter()
        for i, p in enumerate(row):
            state = "first" if i == 0 else "rest"
            packages.append({**p, "state_id": state})
            counts[task][state] += 1
    prior = {
        t: {z: str(Fraction(n, sum(c.values()))) for z, n in c.items()} for t, c in counts.items()
    }
    registration = SimpleNamespace(
        pi0=prior,
        state_support={t: tuple(c) for t, c in counts.items()},
        mu={t: "1/9" for t in counts},
        dataset="finqa",
    )
    return SimpleNamespace(
        task_ids=pool.task_ids,
        packages=tuple(packages),
        row_arrays=pool.row_arrays,
        cache_id="synthetic-complete-full-material",
        production_verified=False,
        conditional_scope_verified=True,
        support_manifest=dict(material_complete=True, exploratory_training_admitted=True),
        material_order_id=pool.material_order_id,
        tokenizer_binding=pool.tokenizer_binding,
        prefix_binding_ref=pool.prefix_binding_ref,
        execution_plan=pool.execution_plan,
        _manifest=SimpleNamespace(registration=registration),
        chi={t: {"first": 0, "rest": 1} for t in counts},
        registered_singleton_tasks=(),
    )


def test_complete_mapping_migration_preserves_actual_state_and_first_outer_boundary(tmp_path):
    run = driver(tmp_path / "prefix")
    torch.manual_seed(929)
    run.run_until()
    checkpoint = prefix.latest_checkpoint(run.root)
    saved, _ = prefix._state(checkpoint)
    assert all(k not in saved for k in ("pi", "prior", "chi", "outer_done"))
    full = full_control(run.pool)
    full.support_manifest["material_complete"] = False
    with pytest.raises(ValueError, match="all real mappings"):
        prefix.migrate_prefix_checkpoint(
            checkpoint, run.pool, full, tmp_path / "blocked", cpu_control=True
        )
    full.support_manifest["material_complete"] = True
    proof = prefix.migrate_prefix_checkpoint(
        checkpoint, run.pool, full, tmp_path / "full_shared", cpu_control=True
    )
    migrated = proof["migrated_checkpoint"]["path"]
    state, _ = prefix._state(migrated)
    assert (
        state["outer_done"] == []
        and state["pi"] == state["prior"] == full._manifest.registration.pi0
    )
    assert proof["optimizer_steps_performed"] == 0 and not proof["original_prefix_contained_pi"]
    assert _tree_digest({k: saved[k] for k in prefix.COMMON_COMPUTATION_FIELDS}) == _tree_digest(
        {k: state[k] for k in prefix.COMMON_COMPUTATION_FIELDS}
    )
    for arm in ("Static", "Manual+", "Manual-", "C-only", "Full"):
        model = TinyDropoutModel()
        real = ConditionalTrainingDriver(
            model, optimizer(model), full, root=tmp_path / arm, seed=11, arm=arm
        )
        real.restore(migrated, branch=True)
        assert real.step_index == 4 and real.outer_done == []
        assert _tree_digest(dict(model.named_parameters())) == _tree_digest(saved["parameters"])
        assert _tree_digest(real.optimizer.state_dict()) == _tree_digest(saved["optimizer"])
        assert _tree_digest(_rng()) == _tree_digest(saved["rng"])
        if arm in ("C-only", "Full"):
            with pytest.raises(ValueError, match="real sealed outer"):
                real.step()
    full.material_order_id = "different-order"
    with pytest.raises(ValueError, match="state labels may change"):
        prefix.migrate_prefix_checkpoint(
            checkpoint, run.pool, full, tmp_path / "wrong", cpu_control=True
        )


def test_fake_state_pool_and_out_of_scope_launch_rejected_before_GPU(tmp_path, monkeypatch):
    pool = material()
    pool.pi = {"fake": 1}
    model, opt = warmed()
    with pytest.raises(ValueError, match="genuinely state-free"):
        prefix.PrefixDriver(model, opt, pool, root=tmp_path / "fake", seed=11, cpu_control=True)

    def rejected(_):
        raise ValueError("prefix material has not passed source binding")

    monkeypatch.setattr(prefix, "checked_launch", rejected)
    monkeypatch.setattr(
        prefix, "gpu_inventory", lambda: (_ for _ in ()).throw(AssertionError("GPU queried"))
    )
    with pytest.raises(ValueError, match="source binding"):
        prefix.run_seed(tmp_path, 11, 0)


def test_driver_initial_checkpoint_contains_no_state_or_distribution(tmp_path):
    run = driver(tmp_path / "state-free")
    run.step()
    payload, record = prefix._state(run.root / "step0001_step")
    assert payload["schema"] == prefix.STATE_SCHEMA
    assert payload["distribution_fields_present"] is False
    assert not any(k in payload for k in ("pi", "prior", "chi", "outer_done"))
    assert record["contains_state_or_pi"] is False
    assert (
        json.loads((run.root / "step0001_step/record.json").read_bytes())["evidence"][
            "actual_batch_size"
        ]
        == 5
    )
