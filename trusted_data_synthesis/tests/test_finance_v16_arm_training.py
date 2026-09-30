"""CPU/mock execution contracts, not real Qwen/CUDA/700-cohort acceptance."""

import fcntl
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import v16_arm_training as arms
from trusted_synthesis.finance_research.v9_training_launcher import sha


def save(path, *, seed=11, arm="shared", step=298, phase="step", outer=(), evidence=None):
    path.mkdir(parents=True)
    raw = json.dumps(dict(seed=seed, arm=arm, step=step, outer=list(outer))).encode()
    (path / "state.pt").write_bytes(raw)
    record = dict(
        seed=seed,
        arm=arm,
        step=step,
        phase=phase,
        outer_done=list(outer),
        pool_id="mock-pool",
        state_sha256=sha(path / "state.pt"),
        actual_state_digest="mock:" + sha(path / "state.pt"),
        evidence=evidence,
    )
    (path / "record.json").write_text(json.dumps(record))
    return path


def fixture(tmp_path, monkeypatch, *, fail_after_first_outer=False, shared=True):
    output = tmp_path / "launch"
    output.mkdir()
    execution = dict(N=744, shared_step=298, outer_steps=[298, 596, 894, 1192], final_step=1490)
    pool = SimpleNamespace(cache_id="mock-pool", execution_plan=execution)
    plan = dict(
        id="mock-launch",
        material_identity=dict(execution_plan=execution),
        feedback_config={"registered": True},
        feedback_seeds=[11, 29],
        device_policy=dict(allowed_gpu_indices=[5], minimum_free_mib=24576),
    )
    assets = dict(
        snapshot="public-snapshot",
        role_plan={"id": "roles"},
        assets=dict(base_binding={"id": "original-base"}),
    )
    events = []
    monkeypatch.setattr(arms, "checked_launch", lambda _: (plan, pool, assets))
    monkeypatch.setattr(arms, "gpu_inventory", lambda: [dict(index=5, uuid="GPU-mock", free=60000)])
    monkeypatch.setattr(arms.torch.cuda, "is_initialized", lambda: False)

    def components(assets, seed):
        events.append(("load", seed))
        return object(), "tokenizer", object(), "scope", {"fresh_shell_only": True}

    monkeypatch.setattr(arms, "_load_components", components)

    def collector(**kwargs):
        assert kwargs["seeds"] == (11, 29)
        assert kwargs["config"] == {"registered": True}
        events.append(("collector", str(kwargs["root"])))
        return SimpleNamespace(denominator=700)

    monkeypatch.setattr(arms, "LocalFeedbackCollector", collector)

    class Driver:
        failed = False

        def __init__(self, model, optimizer, pool, *, root, seed, arm, **kwargs):
            assert arm != "shared"
            assert kwargs["device"] == "cuda:0"
            if arm in ("C-only", "Full"):
                assert kwargs["feedback_collector"].denominator == 700
            else:
                assert kwargs["feedback_collector"] is None
            self.root, self.seed, self.arm = Path(root), seed, arm
            self.step_index, self.outer_done = 0, []
            self.outer_steps, self.final_step = execution["outer_steps"], 1490
            events.append(("driver", arm))

        def restore(self, path, *, branch=False):
            record = json.loads((Path(path) / "record.json").read_bytes())
            self.step_index, self.outer_done = record["step"], list(record["outer_done"])
            events.append(("restore", self.arm, branch, record["phase"]))
            if branch:
                assert record["arm"] == "shared" and self.step_index == 298
                assert not self.outer_done
                self.save("branch")

        def save(self, phase):
            save(
                self.root / f"step{self.step_index:04d}_{phase}",
                seed=self.seed,
                arm=self.arm,
                step=self.step_index,
                phase=phase,
                outer=self.outer_done,
            )

        def run_until(self, stop):
            assert self.step_index >= 298 and stop == 1490
            while self.step_index < stop:
                if (
                    self.arm in ("C-only", "Full")
                    and self.step_index in self.outer_steps
                    and self.step_index not in self.outer_done
                ):
                    self.outer_done.append(self.step_index)
                    events.append(("outer", self.arm, self.step_index))
                    self.save("outer")
                    if fail_after_first_outer and not Driver.failed:
                        Driver.failed = True
                        raise RuntimeError("mock stop after committed outer")
                self.step_index += 1
                events.append(("step", self.arm, self.step_index))
            self.save("step")
            return dict(arm=self.arm, committed_step=self.step_index, outer_done=self.outer_done)

    monkeypatch.setattr(arms, "ConditionalTrainingDriver", Driver)
    if shared:
        proof = arms.bound(
            dict(
                schema="v15_completed_prefix_migration.v1",
                full_pool_id="mock-pool",
                optimizer_steps_performed=0,
                prefix_retrained=False,
                first_outer_not_executed=True,
            )
        )
        save(output / "seed11/shared/step0298_step", evidence=proof)
    return output, plan, pool, events


def test_independent_arms_only_tail_and_original_seed_closure(tmp_path, monkeypatch):
    output, _, _, events = fixture(tmp_path, monkeypatch)
    shared_raw = (output / "seed11/shared/step0298_step/state.pt").read_bytes()
    for arm in ("C-only", "Full", "Static", "Manual+", "Manual-"):
        result = arms.run_arm(output, 11, arm, 5)
        assert result["result"]["committed_step"] == 1490
        assert not result["prefix_retrained"] and not result["cross_arm_feedback_shared"]
    assert events.index(("outer", "C-only", 298)) < events.index(("step", "C-only", 299))
    assert all(event[1] != "shared" for event in events if event[0] == "driver")
    assert all(event[2] > 298 for event in events if event[0] == "step")
    assert len({event[1] for event in events if event[0] == "collector"}) == 2
    assert (output / "seed11/shared/step0298_step/state.pt").read_bytes() == shared_raw
    result = arms.aggregate_seed(output, 11)
    assert result["schema"] == "v9_conditional_five_arm_seed_result.v1"
    assert set(result["arms"]) == set(arms.ARMS)
    assert result["all_five_actual_training_histories_complete"]
    assert not result["same_point_savings_assumed"] and not result["automatic_evaluation"]
    assert arms.aggregate_seed(output, 11) == result  # Idempotent immutable CPU closure.


def test_resume_uses_committed_outer_and_never_repeats_prefix_or_700(tmp_path, monkeypatch):
    output, _, _, events = fixture(tmp_path, monkeypatch, fail_after_first_outer=True)
    with pytest.raises(RuntimeError, match="committed outer"):
        arms.run_arm(output, 11, "Full", 5)
    with pytest.raises(ValueError, match="explicit resume"):
        arms.run_arm(output, 11, "Full", 5)
    arms.run_arm(output, 11, "Full", 5, resume=True)
    assert events.count(("outer", "Full", 298)) == 1
    assert ("restore", "Full", False, "outer") in events
    with pytest.raises(ValueError, match="completed arm"):
        arms.run_arm(output, 11, "Full", 5, resume=True)


def test_absent_or_unmigrated_shared_blocks_before_gpu(tmp_path, monkeypatch):
    output, _, _, events = fixture(tmp_path, monkeypatch, shared=False)
    monkeypatch.setattr(arms, "gpu_inventory", lambda: pytest.fail("no GPU before real migration"))
    with pytest.raises(ValueError, match="shared step298"):
        arms.run_arm(output, 11, "Static", 5)
    save(output / "seed11/shared/step0298_step", evidence={})
    with pytest.raises(ValueError, match="zero-update"):
        arms.run_arm(output, 11, "Static", 5)
    assert not events


def test_partial_feedback_blocks_only_its_arm_before_device(tmp_path, monkeypatch):
    output, _, _, events = fixture(tmp_path, monkeypatch)
    partial = output / "seed11/arms/c_only/feedback/point/intent/record.json"
    partial.parent.mkdir(parents=True)
    partial.write_text("{}")
    inventory = arms.gpu_inventory
    monkeypatch.setattr(arms, "gpu_inventory", lambda: pytest.fail("no GPU on partial700"))
    with pytest.raises(ValueError, match="partial fixed700"):
        arms.run_arm(output, 11, "C-only", 5, resume=True)
    assert not events
    monkeypatch.setattr(arms, "gpu_inventory", inventory)
    assert arms.run_arm(output, 11, "Static", 5)["arm"] == "Static"


def test_source_and_free_memory_fail_before_model_load(tmp_path, monkeypatch):
    output, _, _, events = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(arms, "gpu_inventory", lambda: [dict(index=5, uuid="GPU-mock", free=20000)])
    with pytest.raises(ValueError, match="insufficient GPU margin"):
        arms.run_arm(output, 11, "Static", 5)
    assert not events and not (output / "seed11/arms").exists()

    def changed(_):
        raise ValueError("frozen launcher source changed")

    monkeypatch.setattr(arms, "checked_launch", changed)
    monkeypatch.setattr(
        arms, "gpu_inventory", lambda: pytest.fail("no GPU before source admission")
    )
    with pytest.raises(ValueError, match="source changed"):
        arms.run_arm(output, 11, "Static", 5)


def test_old_seed_worker_lock_excludes_independent_arm(tmp_path, monkeypatch):
    output, _, _, events = fixture(tmp_path, monkeypatch)
    locks = output / "locks"
    locks.mkdir()
    with (locks / "seed11.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            arms.run_arm(output, 11, "Static", 5)
    assert not events


def test_seed_closure_requires_five_real_finals_and_full_outer_history(tmp_path, monkeypatch):
    output, _, _, _ = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="all five"):
        arms.aggregate_seed(output, 11)
    for arm in arms.ARMS:
        arms.run_arm(output, 11, arm, 5)
    record_path = output / "seed11/arms/full/result/record.json"
    record = json.loads(record_path.read_bytes())
    record["result"]["outer_done"] = [596, 894, 1192]
    record = arms.bound({k: v for k, v in record.items() if k != "id"})
    record_path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="final arm result"):
        arms.aggregate_seed(output, 11)


def test_original_744_coordinates_cannot_be_shortened(tmp_path, monkeypatch):
    output, plan, _, events = fixture(tmp_path, monkeypatch)
    plan["material_identity"]["execution_plan"]["final_step"] = 447
    monkeypatch.setattr(arms, "gpu_inventory", lambda: pytest.fail("no GPU on changed schedule"))
    with pytest.raises(ValueError, match="fixed744"):
        arms.run_arm(output, 11, "Full", 5)
    assert not events


def test_restore_deserializes_nonempty_adam_on_cpu_even_with_cuda_destination(
    tmp_path, monkeypatch
):
    from test_finance_v8_training_driver import driver

    from trusted_synthesis.finance_research import v8_training_driver as training

    run = driver(tmp_path / "source")
    run.step()
    checkpoint = run.root / "step0001_step"
    resumed = driver(tmp_path / "resumed")
    # Only a destination marker: this is a tiny CPU control, not CUDA acceptance.
    resumed.device = "cuda:0"
    original_load = training.torch.load
    destinations = []

    def checked_load(*args, **kwargs):
        destinations.append(kwargs["map_location"])
        assert kwargs["map_location"] == "cpu"
        return original_load(*args, **kwargs)

    monkeypatch.setattr(training.torch, "load", checked_load)
    resumed.restore(checkpoint)
    assert destinations == ["cpu"]
    assert resumed.optimizer.state[resumed.model.weight]["step"].device.type == "cpu"
    assert resumed.optimizer.state[resumed.model.weight]["step"].item() == 1
    assert training._tree_digest(resumed.optimizer.state_dict()) == training._tree_digest(
        run.optimizer.state_dict()
    )
