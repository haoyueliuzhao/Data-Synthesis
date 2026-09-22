"""Bounded CPU integration of B ledgers, final artifacts and dependency scheduling."""

import importlib
import sys
from pathlib import Path

import pytest
import torch
from safetensors.torch import load_file

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
b = importlib.import_module("fixed_kernel_B_common_20260922")
runner = importlib.import_module("run_fixed_kernel_B_confirmation_20260922")
training = importlib.import_module("fixed_kernel_B_training_worker_20260922")
p = b.p


@pytest.fixture
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "RAW", tmp_path)
    return tmp_path


def test_prework_reservations_enforce_caps_and_reject_same_attempt_reexecution(raw):
    plan = p.record("B_confirm_protocol", physical_budget=dict(optimizer_cap=2))
    p.write_once(raw / "protocol.json", plan)
    b.reserve("optimizer", "B_prefix_11", 1, 1)
    with pytest.raises(ValueError, match="no_unmetered_same_attempt_retry"):
        b.reserve("optimizer", "B_prefix_11", 1, 1)
    assert p.read_json(raw / "budget/state.json")["counts"]["optimizer"] == 1
    b.reserve("optimizer", "B_prefix_11", 2, 1)
    with pytest.raises(ValueError, match="physical_budget_exhausted:optimizer"):
        b.reserve("optimizer", "B_prefix_11", 2, 2)
    assert p.read_json(raw / "budget/state.json")["counts"]["optimizer"] == 2
    assert not (raw / "budget/intents/optimizer/B_prefix_11/2/2.json").exists()


def test_generation_and_feedback_retry_allowances_are_independently_bounded(raw):
    plan = p.record(
        "B_confirm_protocol",
        physical_budget=dict(
            generate_call_cap=5,
            incomplete_generate_call_cap=1,
            feedback_response_cap=10,
            extra_replayed_responses_per_seed=1,
        ),
    )
    p.write_once(raw / "protocol.json", plan)
    b.reserve("generate_call", "feedback_B_delayed_c_11_00", 1, 0)
    with pytest.raises(ValueError, match="incomplete_generation_budget_exhausted"):
        b.reserve("generate_call", "feedback_B_delayed_c_11_00", 1, 1)
    completed = p.record(
        "anchored_generated_trajectory",
        point_id="synthetic_point",
        job=dict(index=0),
        actual_generate_calls=1,
    )
    b.generation_committed("synthetic_point", 0, completed)
    b.generation_committed("synthetic_point", 0, completed)
    b.reserve("generate_call", "feedback_B_delayed_c_11_00", 1, 1)
    state = p.read_json(raw / "budget/state.json")
    assert state["counts"]["generate_call"] == 2
    assert sum(row["calls"] for row in state["committed_generation"].values()) == 1
    b.set_replay_required("B_delayed_c_11", 2)
    for response in range(3):
        b.reserve("feedback_response", "B_delayed_c_11", 1, response)
    with pytest.raises(ValueError, match="feedback_replay_budget_exhausted"):
        b.reserve("feedback_response", "B_delayed_c_11", 1, 3)
    with pytest.raises(ValueError, match="fixed_sealed_feedback_replay_inventory"):
        b.set_replay_required("B_delayed_c_11", 3)


def test_real_common_checkpoint_and_final_point_are_exact_CPU_only(raw, monkeypatch):
    def forbid_CUDA(*args, **kwargs):
        raise AssertionError("CPU artifact serialization must not initialize CUDA")

    monkeypatch.setattr(torch.cuda, "_lazy_init", forbid_CUDA)
    capture = b.s.capture_rng
    monkeypatch.setattr(b.s, "capture_rng", lambda step: capture(step, cuda=False))
    names = {
        "block.lora_A": torch.nn.Parameter(torch.tensor([[0.25, -0.5]], dtype=torch.float32)),
        "block.lora_B": torch.nn.Parameter(torch.tensor([[0.125], [0.75]], dtype=torch.float32)),
    }
    optimizer = torch.optim.AdamW(list(names.values()), lr=1e-3)
    for _ in range(400):
        optimizer.zero_grad()
        sum(value.square().sum() for value in names.values()).backward()
        optimizer.step()
    plan = dict(id="synthetic_B_plan", materials=dict(assets=dict(base_binding=dict(id="base"))))
    model = dict(key="B_static_11", seed=11, pool="B", condition="static")
    directory = raw / "jobs" / model["key"]
    path = directory / "updates/0400.pt"
    update = p.record("optimizer_update", pool="B", arm="static", optimizer_step_calls=1)
    b.save_training(path, names, optimizer, 400, update, plan["id"], model["key"])
    saved = b.load_training(path, plan["id"], [model["key"]], step=400)
    assert saved["kind"] == "B_shared_training_state"
    cursor, restored = training._recover_updates(b, directory, plan["id"], model["key"], 399, 400)
    assert cursor == 400 and restored["snapshot"] == saved["snapshot"]
    assert p.read_json(directory / "updates/0400.json") == update
    with pytest.raises(ValueError, match="checkpoint_plan_and_lineage"):
        b.load_training(path, "other_plan", [model["key"]], step=400)
    with pytest.raises(ValueError, match="checkpoint_plan_and_lineage"):
        b.load_training(path, plan["id"], ["B_delayed_c_11"], step=400)
    report = p.record(
        "B_training_job_report",
        plan_id=plan["id"],
        job_key=model["key"],
        complete=True,
        completed_updates=400,
        checkpoint_path=str(path),
        checkpoint_sha256=p.sha(path),
        snapshot_id=saved["snapshot"]["id"],
    )
    b.write(directory / "report.json", report)
    branch = p.record("B_shared_prefix_branch_binding", plan_id=plan["id"], job_key=model["key"])
    b.write(directory / "branch_binding.json", branch)
    point_path = runner.final_point(plan, model, "synthetic_confirm_manifest")
    point = p.read_json(point_path)
    adapter = load_file(str(point_path.parent / "adapter.safetensors"), device="cpu")
    assert set(adapter) == set(names)
    for name, parameter in names.items():
        assert torch.equal(adapter[name], parameter.detach())
        assert torch.equal(adapter[name], saved["state"]["theta/" + name])
    assert point["parameter_digest"] == b.old.gate.tensor_digest(adapter)
    assert point["origin_id"] == update["id"] and point["training_report_id"] == report["id"]
    assert runner.final_point(plan, model, "synthetic_confirm_manifest") == point_path
    with pytest.raises(ValueError, match="fixed_final_point"):
        runner.final_point(plan, model, "changed_confirm_manifest")


def test_shared_prefix_unlocks_static_and_outer_but_not_delayed_tail_or_confirmation(raw):
    jobs = []
    for seed in (11, 29, 47):
        for condition in ("prefix", "static", "delayed_c"):
            jobs.append(
                dict(
                    key=f"B_{condition}_{seed}",
                    seed=seed,
                    pool="B",
                    condition=condition,
                    prefix_key=f"B_prefix_{seed}",
                    start=0 if condition == "prefix" else 200,
                    stop=200 if condition == "prefix" else 400,
                )
            )
    plan = dict(id="synthetic_DAG", seeds=[11, 29, 47], training_jobs=jobs)

    def ready():
        return {(row["key"], row["work_kind"]) for row in runner.graph(plan, {})}

    assert ready() == {(f"B_prefix_{seed}", "train") for seed in plan["seeds"]}
    p.write_once(raw / "jobs/B_prefix_11/report.json", {"complete": True})
    assert ready() == {
        ("B_prefix_29", "train"),
        ("B_prefix_47", "train"),
        ("B_static_11", "train"),
        ("prepare_B_delayed_c_11", "outer_prepare"),
    }
    p.write_once(raw / "outer/B_delayed_c_11/report.json", {"complete": True})
    assert ready() == {
        ("B_prefix_29", "train"),
        ("B_prefix_47", "train"),
        ("B_static_11", "train"),
        ("B_delayed_c_11", "train"),
    }
    assert all(kind != "generate" and kind != "score" for _, kind in ready())
    assert runner.phase(dict(work_kind="train")) == "SFT"
    assert runner.phase(dict(work_kind="outer_prepare")) == "population"
