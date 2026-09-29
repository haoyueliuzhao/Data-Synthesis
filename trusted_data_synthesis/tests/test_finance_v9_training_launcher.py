"""Launcher CPU mocks, not Qwen/CUDA/feedback acceptance or training outcomes."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.finance_research import v9_training_launcher as launch


def pool():
    return SimpleNamespace(
        production_verified=True,
        conditional_scope_verified=True,
        task_ids=("x", "y"),
        chi={"x": {"z0": 0, "z1": 1}, "y": {"z0": 0}},
        _manifest=SimpleNamespace(
            registration=SimpleNamespace(pi0={"x": {"z0": ".5", "z1": ".5"}, "y": {"z0": "1"}})
        ),
        capability_profile=dict(D_pi=1, multi_state_tasks=1, chi_flexible_tasks=1, M_flex="1/2"),
        execution_plan=dict(N=2, shared_step=2, outer_steps=[2, 4, 6, 8], final_step=10),
        cache_id="mock-verified-pool",
        support_manifest={"id": "mock-frozen-entire-conditional-support"},
    )


def commit(path, step, phase, arm, *, seed=11):
    payload = dict(step=step, phase=phase, arm=arm, seed=seed)
    raw = json.dumps(payload).encode()
    path.mkdir(parents=True)
    (path / "state.pt").write_bytes(raw)
    (path / "record.json").write_text(
        json.dumps(
            payload
            | dict(state_sha256=launch.sha(path / "state.pt"), actual_state_digest="mock-state")
        )
    )
    return path


class Student(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = torch.nn.Module()
        self.proj.lora_A = torch.nn.Parameter(torch.ones(2, 2))
        self.proj.lora_B = torch.nn.Parameter(torch.zeros(2, 2))


def fixture(tmp_path, monkeypatch, *, fail_after_first_outer=False):
    output = tmp_path / "launch"
    output.mkdir()
    material = pool()
    assets = dict(
        snapshot="mock-public",
        role_plan={"id": "mock-roles"},
        assets=dict(base_binding={"id": "mock-original-base"}),
    )
    plan = dict(
        id="mock-launch",
        feedback_config={},
        feedback_seeds=[11, 29],
        device_policy=dict(allowed_gpu_indices=[5], minimum_free_mib=24576),
    )
    events = []
    monkeypatch.setattr(launch, "checked_launch", lambda out: (plan, material, assets))
    monkeypatch.setattr(
        launch,
        "gpu_inventory",
        lambda: [dict(index=5, uuid="GPU-mock", free=40000, used=40000, processes=[999999])],
    )
    monkeypatch.setattr(launch.torch.cuda, "is_initialized", lambda: False)
    monkeypatch.setattr(launch, "load_tokenizer", lambda value: "mock-tokenizer")
    monkeypatch.setattr(launch, "validate_student_adapters", lambda model, scope: {"mock": True})
    monkeypatch.setattr(launch, "adapter_digest", lambda model: "mock-fresh-parameter-digest")

    def load_student(binding, seed, **kwargs):
        events.append(("load", seed, kwargs))
        assert kwargs == {"trainable": True}  # No prior adapter loading path.
        return Student(), {"id": "mock-scope"}

    monkeypatch.setattr(launch, "load_student", load_student)

    def collector(**kwargs):
        events.append(("collector", str(kwargs["root"]), kwargs["seeds"]))
        return SimpleNamespace(root=kwargs["root"], denominator=700)

    monkeypatch.setattr(launch, "LocalFeedbackCollector", collector)

    class Driver:
        failed = False

        def __init__(self, model, optimizer, material, *, root, seed, arm, **kwargs):
            self.root, self.seed, self.arm = Path(root), seed, arm
            self.step_index, self.outer_done = 0, []
            self.shared_step, self.final_step, self.outer_steps = 2, 10, [2, 4, 6, 8]
            if arm in ("C-only", "Full"):
                assert kwargs["feedback_collector"].denominator == 700
            self.kwargs = kwargs
            events.append(("driver", arm))

        def restore(self, path, *, branch=False):
            record = json.loads((Path(path) / "record.json").read_text())
            self.step_index = record["step"]
            self.outer_done = list(record.get("outer_done", []))
            events.append(("restore", self.arm, branch, record["phase"]))
            if branch:
                assert record["arm"] == "shared" and record["step"] == self.shared_step
                self.save("branch")

        def save(self, phase):
            path = commit(
                self.root / f"step{self.step_index:04d}_{phase}",
                self.step_index,
                phase,
                self.arm,
                seed=self.seed,
            )
            record = json.loads((path / "record.json").read_text())
            record["outer_done"] = self.outer_done
            (path / "record.json").write_text(json.dumps(record))

        def run_until(self, stop):
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
                        raise RuntimeError("mock failure after durable outer; no model call")
                self.step_index += 1
                events.append(("step", self.arm, self.step_index))
                self.save("step")
            return dict(arm=self.arm, committed_step=self.step_index, outer_done=self.outer_done)

    monkeypatch.setattr(launch, "ConditionalTrainingDriver", Driver)
    return output, material, events


def test_real_loader_call_fresh_shell_shared_then_all_five_arms(tmp_path, monkeypatch):
    output, _, events = fixture(tmp_path, monkeypatch)
    result = launch.run_seed(output, 11, 5)
    assert result["all_five_actual_training_histories_complete"]
    assert set(result["arms"]) == set(launch.ARMS)
    assert [e[1] for e in events if e[0] == "driver"] == ["shared", *launch.ARMS]
    assert len([e for e in events if e[0] == "load"]) == 1
    branches = [e for e in events if e[0] == "restore"]
    assert len(branches) == 5 and all(e[2] for e in branches)
    assert [(e[1], e[2]) for e in events if e[0] == "outer"] == [
        (arm, step) for arm in ("C-only", "Full") for step in (2, 4, 6, 8)
    ]
    roots = [e[1] for e in events if e[0] == "collector"]
    assert len(set(roots)) == 2  # Never assume cross-arm feedback sharing.
    assert not result["automatic_evaluation"] and not result["Base_rerun"]
    assert not result["original1000_protocol_admitted"]


def test_resume_restores_actual_commits_not_fresh_training_or_repeated_outer(tmp_path, monkeypatch):
    output, _, events = fixture(tmp_path, monkeypatch, fail_after_first_outer=True)
    with pytest.raises(RuntimeError, match="durable outer"):
        launch.run_seed(output, 11, 5)
    previous_loads = len([e for e in events if e[0] == "load"])
    with pytest.raises(ValueError, match="explicit resume"):
        launch.run_seed(output, 11, 5)
    assert len([e for e in events if e[0] == "load"]) == previous_loads
    result = launch.run_seed(output, 11, 5, resume=True)
    assert result["all_five_actual_training_histories_complete"]
    assert events.count(("outer", "C-only", 2)) == 1
    assert ("restore", "C-only", False, "outer") in events
    assert len([e for e in events if e[:2] == ("step", "shared")]) == 2


def test_partial_700_blocks_before_device_query_or_loading(tmp_path, monkeypatch):
    output, _, events = fixture(tmp_path, monkeypatch)
    intent = output / "seed11/arms/c_only/feedback/point/intent/record.json"
    intent.parent.mkdir(parents=True)
    intent.write_text("{}")
    monkeypatch.setattr(launch, "gpu_inventory", lambda: pytest.fail("must not query/hold device"))
    with pytest.raises(ValueError, match="partial fixed700"):
        launch.run_seed(output, 11, 5, resume=True)
    assert not events


def test_material_block_is_before_any_gpu_or_student(tmp_path, monkeypatch):
    output, _, events = fixture(tmp_path, monkeypatch)

    def blocked(out):
        raise ValueError("whole frozen material unavailable")

    monkeypatch.setattr(launch, "checked_launch", blocked)
    monkeypatch.setattr(
        launch, "gpu_inventory", lambda: pytest.fail("material must gate GPU query")
    )
    with pytest.raises(ValueError, match="whole frozen"):
        launch.run_seed(output, 11, 5)
    assert not events


def test_busy_device_with_margin_is_allowed_but_shortage_never_waits(tmp_path, monkeypatch):
    output, _, events = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        launch,
        "gpu_inventory",
        lambda: [dict(index=5, uuid="GPU-mock", free=20000, processes=[999999])],
    )
    with pytest.raises(ValueError, match="insufficient GPU margin"):
        launch.run_seed(output, 11, 5)
    assert not events and not (output / "seed11").exists()


@pytest.mark.parametrize("failure", ["unverified", "singleton", "chi_constant"])
def test_no_nominal_degenerate_five_arm_admission(failure):
    value = pool()
    if failure == "unverified":
        value.conditional_scope_verified = False
    elif failure == "singleton":
        value._manifest.registration.pi0["x"] = {"z0": "1"}
    else:
        value.chi["x"]["z1"] = 0
    with pytest.raises(ValueError):
        launch.material_identity(value)


def test_scale_decision_uses_actual_profile_before_any_student(tmp_path, monkeypatch):
    binding = tmp_path / "binding.json"
    binding.write_text("{}")
    monkeypatch.setattr(launch, "load_training_pool", lambda path: pool())
    decision = launch.scale_decision(
        binding,
        tmp_path / "scale",
        decision="proceed_exploratory",
        rationale="Actual frozen flexible support is small; exploratory interpretation only.",
        scope_confirmed=True,
    )
    assert decision["material_identity"]["N"] == 2
    assert not decision["statistical_power_claimed"] and not decision["student_results_used"]
    assert not decision["task_or_package_selection_performed"]
    with pytest.raises(ValueError, match="immutable"):
        launch.scale_decision(
            binding,
            tmp_path / "scale",
            decision="stop",
            rationale="not a post-result overwrite",
            scope_confirmed=True,
        )


def test_fresh_lora_guard_refuses_pretrained_B_or_nonempty_Adam(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "validate_student_adapters", lambda *a: {})
    monkeypatch.setattr(launch, "adapter_digest", lambda *a: "mock")
    model = Student()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    assert launch.fresh_student_evidence(model, optimizer, {}, 11)["actual_B_zero"]
    with torch.no_grad():
        model.proj.lora_B.add_(1)
    with pytest.raises(ValueError, match="fresh LoRA B"):
        launch.fresh_student_evidence(model, optimizer, {}, 11)


def test_explicit_stop_can_record_nonempty_but_degenerate_support(tmp_path, monkeypatch):
    material = pool()
    material.chi["x"]["z1"] = 0
    material.capability_profile["chi_flexible_tasks"] = 0
    binding = tmp_path / "binding.json"
    binding.write_text("{}")
    monkeypatch.setattr(launch, "load_training_pool", lambda path: material)
    value = launch.scale_decision(
        binding,
        tmp_path / "stop",
        decision="stop",
        rationale="Manual arms degenerate.",
        scope_confirmed=True,
    )
    assert value["decision"] == "stop"
    with pytest.raises(ValueError, match="nontrivial pi"):
        launch.material_identity(material)
