"""CPU checkpoints and mocks only; no Qwen/CUDA/API or real benchmark outcomes."""

import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.finance_research import v9_final_evaluation as evaluation
from trusted_synthesis.finance_research.providers import parameter_digest
from trusted_synthesis.finance_research.v8_training_driver import _tree_digest
from trusted_synthesis.finance_research.v9_conditional_training import (
    build_task_schedule,
    execution_plan,
)
from trusted_synthesis.finance_research.v9_training_launcher import ARMS, SEEDS


def checkpoint(tmp_path, *, saved_seed=11, saved_arm="Full", saved_step=10, phase="step"):
    tasks = ["train/x", "train/y"]
    execution = execution_plan(len(tasks))
    plan = dict(
        id="mock-training", material_identity=dict(pool_id="pool", execution_plan=execution)
    )
    state = dict(
        schema="v8_committed_training_state.v1",
        seed=saved_seed,
        arm=saved_arm,
        pool_id="pool",
        execution_plan=execution,
        schedule=build_task_schedule(tasks, 11),
        step=saved_step,
        outer_done=[2, 4, 6, 8],
        parameters={"adapter.lora_A": torch.ones(2, 2), "adapter.lora_B": torch.full((2, 2), 3.0)},
        buffers={},
        frozen_base_digest="base-bytes",
        adapter_binding={"fixture": True},
        optimizer={"state": {}},
        rng={"fixture": True},
        pi={},
        prior={},
        model_training=True,
    )
    root = tmp_path / "training"
    path = root / "seed11/arms/full/training/step0010_step"
    path.mkdir(parents=True)
    stream = io.BytesIO()
    torch.save(state, stream)
    (path / "state.pt").write_bytes(stream.getvalue())
    summary = dict(
        step=saved_step,
        phase=phase,
        arm=saved_arm,
        seed=saved_seed,
        pool_id="pool",
        state_sha256=evaluation.sha(path / "state.pt"),
        actual_state_digest=_tree_digest(state),
        schedule_sha256=state["schedule"]["schedule_sha256"],
    )
    (path / "record.json").write_text(json.dumps(summary))
    final = dict(
        path=str(path),
        **{k: summary[k] for k in ("step", "phase", "arm", "state_sha256", "actual_state_digest")},
    )
    result = evaluation.bound(
        dict(
            schema="v9_conditional_five_arm_seed_result.v1",
            protocol_id=plan["id"],
            pool_id="pool",
            seed=11,
            all_five_actual_training_histories_complete=True,
            arms={arm: {"final_checkpoint": final} for arm in ARMS},
        )
    )
    (root / "seed11/result").mkdir()
    (root / "seed11/result/record.json").write_text(json.dumps(result))
    return root, plan, tasks, state


def test_actual_final_checkpoint_parameter_digest_and_coordinate_binding(tmp_path):
    root, plan, tasks, state = checkpoint(tmp_path)
    proof, saved = evaluation.checked_final_checkpoint(root, plan, tasks, 11, "Full")
    assert proof["step"] == 10 and proof["phase"] == "step"
    assert proof["parameter_digest"] == parameter_digest(state["parameters"])
    assert _tree_digest(saved) == _tree_digest(state)
    (Path(proof["checkpoint"]["path"])).write_bytes(b"changed checkpoint")
    with pytest.raises(ValueError, match="checkpoint bytes"):
        evaluation.checked_final_checkpoint(root, plan, tasks, 11, "Full")


@pytest.mark.parametrize(
    "change", [{"saved_seed": 29}, {"saved_arm": "Static"}, {"saved_step": 8}, {"phase": "outer"}]
)
def test_wrong_seed_arm_step_or_phase_never_evaluated(tmp_path, change):
    root, plan, tasks, _ = checkpoint(tmp_path, **change)
    with pytest.raises(ValueError, match="wrong seed/arm/final"):
        evaluation.checked_final_checkpoint(root, plan, tasks, 11, "Full")


class TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.base = torch.nn.Parameter(torch.ones(2, 2, dtype=torch.bfloat16), requires_grad=False)
        self.adapter = torch.nn.Module()
        self.adapter.lora_A = torch.nn.Parameter(torch.zeros(2, 2))
        self.adapter.lora_B = torch.nn.Parameter(torch.zeros(2, 2))
        self.register_buffer("position", torch.arange(2))
        self.config = SimpleNamespace(use_cache=False)
        self.checkpointing_disabled = False

    def gradient_checkpointing_disable(self):
        self.checkpointing_disabled = True


def test_actual_cpu_final_parameters_and_buffers_installed_then_frozen(monkeypatch):
    model = TinyModel()
    state = dict(
        adapter_binding={"fixture": True},
        frozen_base_digest=parameter_digest({"base": model.base}),
        parameters={"adapter.lora_A": torch.ones(2, 2), "adapter.lora_B": torch.full((2, 2), 4.0)},
        buffers={"position": torch.tensor([3, 4])},
    )
    monkeypatch.setattr(evaluation, "validate_student_adapters", lambda *a: {"fixture": True})
    parameters = evaluation.install_checkpoint_state(model, state, {})
    assert parameter_digest(parameters) == parameter_digest(state["parameters"])
    assert model.position.tolist() == [3, 4]
    assert not model.training and not any(p.requires_grad for p in model.parameters())
    assert model.config.use_cache and model.checkpointing_disabled
    other = TinyModel()
    other.base.data.add_(1)
    with pytest.raises(ValueError, match="Base tensor bytes"):
        evaluation.install_checkpoint_state(other, state, {})


def matrix():
    tasks = [f"finqa/dev{i}" for i in range(883)]
    groups = {t: dict(group=f"report{i // 10}", level="report") for i, t in enumerate(tasks)}
    reports = {}
    for seed in SEEDS:
        for arm in ARMS:
            rows = []
            for i, key in enumerate(tasks):
                answer = int(i % 2 == 1 or (i == 0 and arm == "Full"))
                rows.append(
                    dict(
                        task_key=key,
                        native=dict(
                            native=dict(execution_accuracy=answer, program_accuracy=answer)
                        ),
                    )
                )
            reports[evaluation.coordinate(seed, arm)] = dict(
                seed=seed,
                arm=arm,
                denominator=883,
                results=rows,
                metrics=evaluation.native_metrics(rows),
            )
    base = {
        k: dict(denominator=883, unknown=0, complete_dataset_mean=33 / 883)
        for k in ("execution_accuracy", "program_accuracy")
    }
    return tasks, groups, reports, base


def test_paired_mean_preserves883_repeated_questions_and_source_clusters():
    tasks, groups, reports, base = matrix()
    result = evaluation.paired_summary(reports, tasks, groups, base)
    effect = result["comparisons"]["execution_accuracy"]["Full-Static"]
    assert effect["mean_difference"] == pytest.approx(1 / 883)
    assert effect["repeated_task_count"] == result["distinct_question_count"] == 883
    assert effect["training_seed_count"] == 3
    assert all(v["wins"] == 1 for v in effect["paired_by_seed"].values())
    assert sum(v["task_count"] for v in effect["source_cluster_summaries"].values()) == 883
    assert effect["source_cluster_count"] == 89
    assert effect["confidence_interval"] is None and effect["p_value"] is None
    assert not result["question_independence_assumed"]
    assert result["statistics_contract"]["Static_minus_Base"].startswith("ordinary learning")


def test_unknown_is_preserved_not_zero_or_complete_case_statistics():
    tasks, groups, reports, base = matrix()
    report = reports[evaluation.coordinate(47, "Full")]
    report["results"][0]["native"]["native"]["execution_accuracy"] = None
    report["metrics"] = evaluation.native_metrics(report["results"])
    assert report["metrics"]["execution_accuracy"]["unknown"] == 1
    assert report["metrics"]["execution_accuracy"]["complete_dataset_mean"] is None
    with pytest.raises(ValueError, match="unknown or incomplete"):
        evaluation.paired_summary(reports, tasks, groups, base)


def test_missing_model_or_question_prevents_aggregate():
    tasks, groups, reports, base = matrix()
    partial = copy.deepcopy(reports)
    partial.pop(evaluation.coordinate(47, "Full"))
    with pytest.raises(ValueError, match="all fifteen"):
        evaluation.paired_summary(partial, tasks, groups, base)
    reports[evaluation.coordinate(11, "Static")]["results"].pop()
    with pytest.raises(ValueError, match="denominator changed"):
        evaluation.paired_summary(reports, tasks, groups, base)
    with pytest.raises(ValueError, match="complete883"):
        evaluation.native_metrics([])


def test_incomplete_generation_stops_before_private_reference_read(tmp_path, monkeypatch):
    plan = dict(jobs={evaluation.coordinate(11, "Full"): dict(seed=11, arm="Full")})
    monkeypatch.setattr(evaluation, "checked_plan", lambda path: plan)

    def incomplete(*args):
        raise ValueError("all883 must be sealed")

    monkeypatch.setattr(evaluation, "seal_model", incomplete)
    monkeypatch.setattr(
        evaluation,
        "_read_snapshot_rows",
        lambda *a: pytest.fail("private references opened before full seal"),
    )
    with pytest.raises(ValueError, match="all883"):
        evaluation.score_model(tmp_path, 11, "Full")


def test_real_loader_path_uses_bound_installed_point_not_an_old_adapter(monkeypatch):
    events = []
    identity = SimpleNamespace(model_dump=lambda **kw: {"bound": "point"})
    plan = dict(assets={"base_binding": {"id": "base"}}, config={"seed": 20260928})
    job = dict(model_identity={"model_id": "base", "point_id": "final:fixed", "bound": "point"})
    # Keep the expected identity exact while making the mock point inspectable.
    identity.model_dump = lambda **kw: job["model_identity"]
    model, parameters = object(), {"adapter.lora_A": object()}
    monkeypatch.setattr(evaluation.base, "load_tokenizer", lambda a: "tokens")

    def load(binding, seed, **kwargs):
        events.append(("load", seed, kwargs))
        return model, {"scope": "original"}

    monkeypatch.setattr(evaluation, "load_student", load)

    def install(actual, state, scope):
        assert actual is model and state == {"actual": "final"} and scope == {"scope": "original"}
        events.append(("install",))
        return parameters

    monkeypatch.setattr(evaluation, "install_checkpoint_state", install)
    monkeypatch.setattr(evaluation, "local_model_identity", lambda *a, **kw: identity)
    monkeypatch.setattr(
        evaluation,
        "LocalTorchProvider",
        lambda m, t, i, **kw: dict(parameters=kw["parameter_tensors"], identity=i),
    )
    provider = evaluation.load_final_provider(plan, job, {"actual": "final"})
    assert events == [("load", 20260928, {"trainable": True}), ("install",)]
    assert provider["parameters"] is parameters


def test_runner_reuses_complete_generation_without_gpu_or_resampling(tmp_path, monkeypatch):
    job = dict(seed=11, arm="Full")
    plan = dict(jobs={evaluation.coordinate(11, "Full"): job})
    monkeypatch.setattr(evaluation, "checked_plan", lambda path: plan)
    monkeypatch.setattr(evaluation, "inspect_model", lambda *a: dict(sealed=True, completed=883))
    monkeypatch.setattr(
        evaluation, "gpu_inventory", lambda: pytest.fail("sealed model must not load")
    )
    marker = {"sealed_score_only": True}
    monkeypatch.setattr(evaluation, "score_model", lambda *a: marker)
    assert evaluation.run_model(tmp_path, 11, "Full", 5, resume=True) == marker


def test_unsealed_runner_loads_bound_point_then_generates_before_score(tmp_path, monkeypatch):
    job = dict(seed=11, arm="Full", state_sha256="mock-final")
    plan = dict(
        id="mock-eval",
        jobs={evaluation.coordinate(11, "Full"): job},
        device_policy=dict(allowed_gpu_indices=[5], minimum_free_mib=24576),
    )
    events = []
    monkeypatch.setattr(evaluation, "checked_plan", lambda path: plan)
    monkeypatch.setattr(evaluation, "inspect_model", lambda *a: dict(sealed=False, completed=0))
    monkeypatch.setattr(evaluation, "read_registered_state", lambda *a: {"fixed": "final"})
    monkeypatch.setattr(
        evaluation,
        "gpu_inventory",
        lambda: [dict(index=5, uuid="GPU-test-only", free=40000, processes=[123456])],
    )
    monkeypatch.setattr(evaluation.torch.cuda, "is_initialized", lambda: False)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    provider = object()

    def load(plan, actual_job, state):
        assert actual_job == job and state == {"fixed": "final"}
        events.append("load")
        return provider

    async def generate(path, actual_provider):
        assert actual_provider is provider and path.name == "generation"
        events.append("generate")

    def score(*args):
        assert events == ["load", "generate"]
        events.append("score")
        return {"complete_mock": True}

    monkeypatch.setattr(evaluation, "load_final_provider", load)
    monkeypatch.setattr(evaluation, "execute_run", generate)
    monkeypatch.setattr(evaluation, "score_model", score)
    assert evaluation.run_model(tmp_path, 11, "Full", 5) == {"complete_mock": True}
    assert events == ["load", "generate", "score"]
    with pytest.raises(ValueError, match="explicit resume"):
        evaluation.run_model(tmp_path, 11, "Full", 5)
