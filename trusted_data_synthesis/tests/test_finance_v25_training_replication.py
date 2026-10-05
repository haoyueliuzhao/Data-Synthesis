"""CPU-only replication checks; frozen runtime controls run in an isolated process.

Isolation matters: the main repository conftest imports its own package tree,
which production correctly refuses to mix with the frozen scientific runtime.
"""

import importlib
import json
import random
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
replication = importlib.import_module("finqa_v25_training_replication")


@pytest.mark.parametrize("seed", [11, 29, 47, 0, 138, True])
def test_only_new_registered_seeds_before_runtime(seed):
    with pytest.raises(ValueError, match="fresh registered"):
        replication.coordinate(seed)


@pytest.mark.parametrize("arm", ["Manual+", "manual_plus", "shared", "other"])
def test_no_extra_arm(arm):
    with pytest.raises(ValueError, match="only registered"):
        replication.arm_name(arm)


def test_exact_new_coordinates_and_remaining_global_disk_budget():
    assert replication.coordinate(137, "c_only") == "seed137/arms/c_only"
    assert replication.arm_name("Full") == "Full"
    assert replication.disk_required(0) == 400 * replication.GIB
    assert replication.disk_required(100 * replication.GIB) == 300 * replication.GIB
    assert replication.disk_required(390 * replication.GIB) == 32 * replication.GIB
    assert replication.disk_required(420 * replication.GIB) == 32 * replication.GIB


def test_disk_gate_blocks_before_any_worker_allocation(tmp_path, monkeypatch):
    monkeypatch.setattr(replication.shutil, "disk_usage", lambda _: SimpleNamespace(free=1))
    with pytest.raises(ValueError, match="remaining registered"):
        replication.disk_gate(tmp_path / "new")


def test_frozen_numerical_cpu_acceptance(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--cpu-acceptance", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = json.loads(completed.stdout.splitlines()[-1])
    assert receipt == dict(
        seeds=[137, 251, 389],
        real_cpu_prefix_updates=12,
        real_cpu_outer_updates=6,
        synthetic_feedback_episodes=12,
        unchanged_numerical_methods=True,
        zero_update_migration=True,
        exact_cpu_resume=True,
        static_prior_unchanged=True,
        c_only_and_full_require_separate_due_outer=True,
        all_steps_have_complete_state=True,
        GPU_calls=0,
        API_calls=0,
    )


def cpu_acceptance(root):
    """Real tiny CPU Adam/dropout/commit/restore; never a production artifact."""
    rt = replication.load_runtime()
    torch = rt.torch
    torch.set_num_threads(1)
    # Reuse the frozen CPU episode/receipt fixtures, never a production cohort.
    sys.path.insert(0, str(replication.FROZEN / "trusted_data_synthesis/tests"))
    feedback_fixtures = importlib.import_module("test_finance_research_feedback")
    provider_fixtures = importlib.import_module("test_finance_research_providers")
    providers = importlib.import_module("trusted_synthesis.finance_research.providers")
    adapted = replication.adapters()
    assert adapted.PrefixDriver.step is rt.prefix.PrefixDriver.step
    assert adapted.PrefixDriver.commit is rt.prefix.PrefixDriver.commit
    assert adapted.PrefixDriver.restore is rt.prefix.PrefixDriver.restore
    for method in ("step", "outer_update", "_outer_update", "commit", "restore", "run_until"):
        assert getattr(adapted.TrainingDriver, method) is getattr(rt.v8.TrainingDriver, method)
    assert rt.prefix.SEEDS == (11, 29, 47)
    with pytest.raises(ValueError, match="paired seeds"):
        rt.conditional.build_task_schedule(["t"], 137)

    class TinyDropoutModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(
                torch.arange(20, dtype=torch.float32).reshape(4, 5) / 10
            )
            self.dropout = torch.nn.Dropout(0.2)

        def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
            return SimpleNamespace(logits=self.dropout(self.weight[input_ids])[:, logits_to_keep])

    class TinyWithMockGeneration(TinyDropoutModel, provider_fixtures.Model):
        def __init__(self):
            TinyDropoutModel.__init__(self)
            self.generation_config = SimpleNamespace(eos_token_id=2)
            self.calls = 0

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

    def full_pool():
        tasks, packages, rows, chi = [f"t{i}" for i in range(9)], [], {}, {}
        for task in tasks:
            chi[task] = {"first": 0, "rest": 1}
            for index in range(3):
                package = task + f"/p{index}"
                rows[package] = [
                    dict(
                        input_ids=[0, 1, 2, 3],
                        target_positions=[1, 3],
                        target_ids=[1, 3],
                        turn_index=0,
                    )
                ]
                packages.append(
                    dict(
                        package_id=package,
                        task_id=task,
                        state_id="first" if index == 0 else "rest",
                        whole_package_target_tokens=2,
                        fused=False,
                    )
                )
        pool = rt.conditional.tiny_cpu_pool(tasks, packages, rows, chi=chi)
        pool.conditional_scope_verified = True
        pool.support_manifest = dict(material_complete=True, exploratory_training_admitted=True)
        pool.material_order_id = "same-cpu-package-and-row-order"
        pool.tokenizer_binding = ("CPU-codec", "CPU-template")
        pool.prefix_binding_ref = dict(path="CPU-fixture", sha256="CPU-only", id="fresh-prefix")
        pool.execution_plan = rt.conditional.execution_plan(len(tasks))
        return pool

    production_tasks = [f"production{i}" for i in range(744)]
    hashes = []
    for seed in replication.SEEDS:
        schedule = replication.build_task_schedule(production_tasks, seed)
        assert schedule["updates"] == 1490
        assert sum(len(row["task_ids"]) == 4 for row in schedule["batches"]) == 10
        rng = random.Random(seed)
        first = list(production_tasks)
        rng.shuffle(first)
        assert [t for batch in schedule["batches"][:149] for t in batch["task_ids"]] == first
        hashes.append(schedule["schedule_sha256"])
    assert len(set(hashes)) == 3

    for seed in replication.SEEDS:
        full = full_pool()
        prefix = replication.StateFreePool(full, full.prefix_binding_ref)
        assert not any(hasattr(prefix, key) for key in ("pi", "chi", "prior", "_manifest"))
        assert all("state_id" not in package for package in prefix.packages)
        examples = rt.prefix.direct_batch_examples(prefix, ["t0", "t1", "t2", "t3"])
        assert all(Fraction(row["target_token_coefficient"]) == Fraction(1, 24) for row in examples)
        torch.manual_seed(seed)
        model = TinyDropoutModel()
        opt = optimizer(model)
        assert not opt.state
        driver = adapted.PrefixDriver(
            model, opt, prefix, root=root / str(seed) / "prefix", seed=seed, cpu_control=True
        )
        actual = driver.run_until()
        assert actual["consumption"]["updates"] == 4
        assert len(list(driver.root.glob("step*_step/state.pt"))) == 4
        assert (driver.root / "first_step_acceptance/record.json").exists()
        prefix_path = driver.root / "step0004_step"
        saved, _ = rt.prefix._state(prefix_path)
        assert all(k not in saved for k in ("pi", "prior", "chi", "outer_done"))
        proof = adapted.migrate(
            prefix_path, prefix, full, root / str(seed) / "shared", cpu_control=True
        )
        assert proof["optimizer_steps_performed"] == 0
        migrated = Path(proof["migrated_checkpoint"]["path"])
        state, _ = rt.prefix._state(migrated)
        assert state["outer_done"] == []
        assert state["pi"] == state["prior"] == full._manifest.registration.pi0
        assert rt.v8._tree_digest({k: saved[k] for k in rt.prefix.COMMON_COMPUTATION_FIELDS}) == (
            rt.v8._tree_digest({k: state[k] for k in rt.prefix.COMMON_COMPUTATION_FIELDS})
        )
        for arm in replication.ARMS:
            branch_model = TinyWithMockGeneration()
            branch = adapted.TrainingDriver(
                branch_model,
                optimizer(branch_model),
                full,
                root=root / str(seed) / arm,
                seed=seed,
                arm=arm,
            )
            branch.restore(migrated, branch=True)
            assert branch.step_index == 4 and not branch.outer_done
            assert rt.v8._tree_digest(branch.optimizer.state_dict()) == rt.v8._tree_digest(
                saved["optimizer"]
            )
            assert rt.v8._tree_digest(rt.v8._rng()) == rt.v8._tree_digest(saved["rng"])
            if arm in ("C-only", "Full"):
                with pytest.raises(ValueError, match="real sealed outer"):
                    branch.step()
                real_steps = branch.optimizer.state[branch.model.weight]["step"].item()

                def collect(prepared, point_id, branch=branch):
                    with rt.v8.installed_point(branch.model, prepared["theta_bar"]) as theta:
                        tokenizer = provider_fixtures.Tokenizer()
                        identity = providers.local_model_identity(
                            branch.model,
                            tokenizer,
                            model_id="CPU-only-new-seed-replication",
                            point_id=point_id,
                            parameter_tensors=theta,
                        )
                        local = providers.LocalTorchProvider(
                            branch.model, tokenizer, identity, parameter_tensors=theta
                        )
                        episodes = [feedback_fixtures.episode(local, seed=i) for i in (1, 2)]
                        return feedback_fixtures.seal(episodes, identity), [0, 0]

                evidence = branch.outer_update(cpu_control_feedback=collect)
                assert evidence["distribution"]["status"] == "UNINFORMATIVE_FEEDBACK"
                assert branch.pi == branch.prior and branch.outer_done == [4]
                assert branch.optimizer.state[branch.model.weight]["step"].item() == real_steps
                assert (branch.root / "step0004_outer/outer_inputs.pt").exists()
                branch.step()
                assert branch.step_index == 5
                continue
            branch.run_until(7)
            snapshot = rt.launcher.latest_checkpoint(branch.root)
            branch.run_until(9)
            uninterrupted = rt.v8._tree_digest(branch._payload())
            resumed_model = TinyDropoutModel()
            resumed = adapted.TrainingDriver(
                resumed_model,
                optimizer(resumed_model),
                full,
                root=root / str(seed) / "resumed",
                seed=seed,
                arm="Static",
            )
            resumed.restore(snapshot)
            resumed.run_until(9)
            assert rt.v8._tree_digest(resumed._payload()) == uninterrupted
            assert resumed.pi == resumed.prior
            assert len(list(branch.root.glob("step*_step/state.pt"))) == 5
        # Genuine incomplete materials cannot pass the original migration gate.
        full.support_manifest["material_complete"] = False
        with pytest.raises(ValueError, match="all real mappings"):
            adapted.migrate(
                prefix_path, prefix, full, root / str(seed) / "blocked", cpu_control=True
            )
    print(
        json.dumps(
            dict(
                seeds=[137, 251, 389],
                real_cpu_prefix_updates=12,
                real_cpu_outer_updates=6,
                synthetic_feedback_episodes=12,
                unchanged_numerical_methods=True,
                zero_update_migration=True,
                exact_cpu_resume=True,
                static_prior_unchanged=True,
                c_only_and_full_require_separate_due_outer=True,
                all_steps_have_complete_state=True,
                GPU_calls=0,
                API_calls=0,
            )
        )
    )


if __name__ == "__main__":
    assert sys.argv[1] == "--cpu-acceptance"
    cpu_acceptance(Path(sys.argv[2]))
