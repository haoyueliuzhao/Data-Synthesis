"""CPU/mock-only V25 protocol, seed statistics and private-read barrier tests."""

import copy
import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
evaluation = importlib.import_module("finqa_v25_evaluation")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def bound(value):
    return {**value, "id": digest(value)}


def file_binding(path):
    return dict(path=str(path), sha256="fixture")


class Identity:
    def __init__(self, **values):
        self.values = values

    def model_dump(self, **kwargs):
        return self.values

    @classmethod
    def model_validate(cls, value):
        return cls(**value)


def make_reports(block):
    seeds = evaluation.OLD_SEEDS if block == "A" else evaluation.NEW_SEEDS
    tasks = [f"finqa/q{i}" for i in range(1147)]
    reports = {}
    for j, seed in enumerate(seeds):
        for arm in evaluation.ARMS:
            correct = {"Static": 500, "C-only": 530, "Full": (550, 490, 540)[j]}[arm]
            rows = [
                dict(
                    task_key=key,
                    native={
                        "native": dict(
                            execution_accuracy=int(i < correct),
                            program_accuracy=int(i < correct - 1),
                        )
                    },
                )
                for i, key in enumerate(tasks)
            ]
            reports[evaluation.coordinate(seed, arm)] = dict(
                seed=seed,
                arm=arm,
                denominator=1147,
                results=rows,
                metrics=evaluation.native_metrics(rows),
            )
    return reports, tasks


def test_registered_coordinates_and_statistics():
    assert evaluation.coordinate(11, "c_only") == "seed11/c_only"
    assert evaluation.coordinate(137, "full") == "seed137/full"
    for seed, arm in ((99, "full"), (True, "full"), (137, "Manual+")):
        with pytest.raises(ValueError):
            evaluation.coordinate(seed, arm)
    a, b = (evaluation.statistics_contract(block) for block in ("A", "B"))
    assert (
        a["execution_interval"] is None
        and a["original_six_model_preregistered_confirmation"] is False
    )
    assert a["primary"] is None and a["key_secondary"] is None
    assert a["extension_comparisons"] == ["C-only-Static", "Full-C-only"]
    assert a["reused_Full_minus_Static_reference_only"] is True
    assert b["primary"] == "Full-Static native execution accuracy"
    assert b["execution_interval"]["df"] == 2
    assert b["execution_interval"]["critical_value"] == 4.3026527299
    assert not b["statistical_power_claimed"] and not b["eighty_percent_power_claimed"]
    assert b["no_p_values"] and not b["multiplicity_adjusted"]
    assert not a["old_source_cluster_interval_reused"] and not b["source_cluster_bootstrap"]


def test_seed_t_interval_uses_sample_sd_and_three_seed_unit():
    result = evaluation.seed_effect_summary([0.02, -0.01, 0.05], confidence_interval=True)
    assert result["mean_difference"] == pytest.approx(0.02)
    assert result["sample_sd"] == pytest.approx(0.03)
    assert result["signs"] == dict(positive=2, zero=0, negative=1)
    width = 4.3026527299 * 0.03 / math.sqrt(3)
    assert result["seed_t95"]["lower"] == pytest.approx(0.02 - width)
    assert result["seed_t95"]["upper"] == pytest.approx(0.02 + width)
    assert result["seed_t95"]["not_power_or_stability_confirmation"]
    with pytest.raises(ValueError):
        evaluation.seed_effect_summary([0.1] * 6, confidence_interval=True)
    with pytest.raises(ValueError):
        evaluation.seed_effect_summary([0, np.nan, 1])


def test_old_block_is_posthoc_descriptive_and_no_interval():
    reports, tasks = make_reports("A")
    summary = evaluation.paired_summary(reports, tasks, "A")
    assert set(summary) == {"Full-Static", "Full-C-only", "C-only-Static"}
    for metrics in summary.values():
        for report in metrics.values():
            assert report["descriptive_only"] and "seed_t95" not in report
    assert summary["Full-Static"]["execution_accuracy"]["mean_difference"] == pytest.approx(
        80 / (3 * 1147)
    )
    assert (
        summary["Full-C-only"]["execution_accuracy"]["paired_by_seed"]["29"]["mean_difference"]
        == -40 / 1147
    )


def test_new_block_reports_main_and_key_secondary_seed_intervals_only():
    reports, tasks = make_reports("B")
    summary = evaluation.paired_summary(reports, tasks, "B")
    primary = summary["Full-Static"]["execution_accuracy"]
    assert primary["n"] == 3 and primary["signs"] == dict(positive=2, zero=0, negative=1)
    assert primary["sample_sd"] == pytest.approx(np.std(np.array([50, -10, 40]) / 1147, ddof=1))
    assert "seed_t95" in summary["Full-C-only"]["execution_accuracy"]
    assert "seed_t95" not in summary["C-only-Static"]["execution_accuracy"]
    assert all("seed_t95" not in report["program_accuracy"] for report in summary.values())


@pytest.mark.parametrize("mutation", ["missing", "coordinate", "order", "unknown", "aggregate"])
def test_statistics_reject_selective_or_corrupt_results(mutation):
    reports, tasks = make_reports("B")
    report = reports["seed137/static"]
    if mutation == "missing":
        del reports["seed389/full"]
    elif mutation == "coordinate":
        report["seed"] = 251
    elif mutation == "order":
        report["results"].reverse()
    elif mutation == "unknown":
        report["results"][0]["native"]["native"]["execution_accuracy"] = None
        report["metrics"] = evaluation.native_metrics(report["results"])
    else:
        report["metrics"]["execution_accuracy"]["correct"] = 999
    with pytest.raises(ValueError):
        evaluation.paired_summary(reports, tasks, "B")


def test_combined_six_is_equal_weight_description_with_blocks_first():
    blocks = []
    for block in ("A", "B"):
        reports, tasks = make_reports(block)
        blocks.append(
            dict(
                block=block,
                statistics=evaluation.statistics_contract(block),
                comparisons=evaluation.paired_summary(reports, tasks, block),
            )
        )
    result = evaluation.combine_summaries(*blocks)
    assert result["report_order"][-1] == "combined_six_seed_descriptive"
    assert result["original_three_seed_block"] == blocks[0]["comparisons"]
    assert result["new_three_seed_block"] == blocks[1]["comparisons"]
    for report in result["combined_six_seed_descriptive"].values():
        for metrics in report.values():
            assert metrics["n"] == 6 and metrics["confidence_intervals"] is None
            assert metrics["descriptive_only"] and "seed_t95" not in metrics
    with pytest.raises(ValueError):
        evaluation.combine_summaries(*blocks[::-1])


@pytest.mark.parametrize("block,count", [("A", 3), ("B", 9)])
def test_private_read_and_old_score_reuse_wait_for_whole_block(tmp_path, monkeypatch, block, count):
    calls, reads = [], []
    seeds = evaluation.OLD_SEEDS if block == "A" else evaluation.NEW_SEEDS
    arms = ("C-only",) if block == "A" else evaluation.ARMS
    jobs = {evaluation.coordinate(s, a): dict(seed=s, arm=a) for s in seeds for a in arms}
    plan = dict(id="registered", block=block, jobs=jobs)
    final = SimpleNamespace(
        file_binding=file_binding,
        bound=bound,
        _publish=lambda *args: reads.append("publish"),
        _read_snapshot_rows=lambda *args: reads.append("private"),
    )

    def seal(root, plan, job, runtime):
        key = evaluation.coordinate(job["seed"], job["arm"])
        calls.append(key)
        if len(calls) == count:
            raise ValueError("unsealed last model")
        return dict(id=key), []

    monkeypatch.setattr(evaluation, "load_runtime", lambda: final)
    monkeypatch.setattr(evaluation, "checked_plan", lambda *args: plan)
    monkeypatch.setattr(evaluation, "bound_job", lambda root, plan, key, final: jobs[key])
    monkeypatch.setattr(evaluation, "seal_model", seal)
    monkeypatch.setattr(evaluation, "reused_reports", lambda *args: reads.append("old scores"))
    with pytest.raises(ValueError, match="unsealed last model"):
        evaluation.score(tmp_path)
    assert len(calls) == count and reads == []


@pytest.mark.parametrize("block,count", [("A", 3), ("B", 9)])
def test_block_barrier_exact_registered_models(tmp_path, monkeypatch, block, count):
    seeds = evaluation.OLD_SEEDS if block == "A" else evaluation.NEW_SEEDS
    arms = ("C-only",) if block == "A" else evaluation.ARMS
    jobs = {evaluation.coordinate(s, a): dict(seed=s, arm=a) for s in seeds for a in arms}
    plan = dict(id="fixed", block=block, jobs=jobs)
    publications = []
    final = SimpleNamespace(
        file_binding=file_binding, bound=bound, _publish=lambda *args: publications.append(args)
    )
    monkeypatch.setattr(evaluation, "bound_job", lambda root, plan, key, final: jobs[key])
    monkeypatch.setattr(
        evaluation, "seal_model", lambda root, plan, job, final: (dict(id="seal"), [])
    )
    barrier, episodes, actual_jobs = evaluation.seal_all(tmp_path, plan, final)
    assert set(barrier["models"]) == set(episodes) == set(actual_jobs) == set(jobs)
    assert barrier["total_episodes"] == count * 1147
    assert not barrier["private_references_read"]
    assert publications[0][0] == tmp_path / "all_generation_seal"


def test_registration_a_resume_completes_and_checks_every_public_run(tmp_path, monkeypatch):
    (tmp_path / "registration").mkdir()
    (tmp_path / "registration/record.json").write_text("fixture")
    jobs = {
        evaluation.coordinate(s, "C-only"): dict(seed=s, arm="C-only") for s in evaluation.OLD_SEEDS
    }
    plan = dict(block="A", jobs=jobs)
    calls = []
    monkeypatch.setattr(evaluation, "load_runtime", lambda: SimpleNamespace())
    monkeypatch.setattr(evaluation, "checked_plan", lambda *args: plan)
    monkeypatch.setattr(evaluation, "prepare_job", lambda root, plan, job, final: calls.append(job))
    assert evaluation.register_a(tmp_path) == plan and calls == list(jobs.values())


def test_new_a_registration_reuses_six_but_only_prepares_three(tmp_path, monkeypatch):
    calls, states = [], []
    dev = dict(
        training_protocol={"path": "old-training"},
        training_root="old-training",
        training_task_ids=["train"],
        material_identity={},
        device_policy={},
        jobs={
            evaluation.coordinate(s, "C-only"): dict(
                seed=s, arm="C-only", step=1490, model_identity={"backend": "local_torch"}
            )
            for s in evaluation.OLD_SEEDS
        },
    )
    fields = dict(tasks=["test"], config={}, source_groups={}, snapshot_id="snapshot", block="A")
    old = {
        **fields,
        "jobs": {
            evaluation.coordinate(s, a): {}
            for s in evaluation.OLD_SEEDS
            for a in ("Static", "Full")
        },
    }
    final = SimpleNamespace(
        read_registered_state=lambda plan, job: states.append(job),
        bound=bound,
        file_binding=file_binding,
        _publish=lambda *args: calls.append(("registration", args)),
    )
    monkeypatch.setattr(evaluation, "load_runtime", lambda: final)
    monkeypatch.setattr(evaluation, "base_registration", lambda *args: (dev, fields))
    monkeypatch.setattr(evaluation.original, "checked_plan", lambda *args: old)
    monkeypatch.setattr(evaluation, "prepare_job", lambda *args: calls.append(("prepare", args)))
    plan = evaluation.register_a(tmp_path / "new-a")
    assert plan["total_models"] == 3 and plan["total_episodes"] == 3441
    assert plan["reused_models"] == 6 and len(plan["reused_score_reports"]) == 6
    assert not plan["existing_score_results_parsed_at_registration"]
    assert plan["existing_score_files_hashed_at_registration"]
    assert len(states) == 3 and [c[0] for c in calls] == ["registration"] + ["prepare"] * 3


def test_new_b_registration_locks_all_future_checkpoints_without_loading_one(tmp_path, monkeypatch):
    training_root = tmp_path / "training"
    contract = dict(
        registration_id="new-training-id",
        training_protocol={"path": "new-training"},
        training_root=str(training_root.resolve()),
        training_task_ids=["train"],
        material_identity={"pool": "same"},
        device_policy={},
        assets={"base": "same"},
    )
    dev = dict(material_identity=contract["material_identity"])
    fields = dict(block="B", assets=contract["assets"])
    published = []
    final = SimpleNamespace(bound=bound, _publish=lambda *args: published.append(args))
    monkeypatch.setattr(evaluation, "load_runtime", lambda: final)
    monkeypatch.setattr(evaluation, "base_registration", lambda *args: (dev, fields))
    monkeypatch.setattr(
        evaluation,
        "training_module",
        lambda: SimpleNamespace(evaluation_contract=lambda root: contract),
    )
    plan = evaluation.register_b(tmp_path / "new-b", training_root=training_root)
    assert plan["total_models"] == 9 and plan["total_episodes"] == 10323
    assert len(plan["jobs"]) == 9 and plan["training_protocol_id"] == "new-training-id"
    assert plan["training_evaluation_contract"] == contract and len(published) == 1
    for key, job in plan["jobs"].items():
        assert job["step"] == 1490 and job["phase"] == "step"
        assert job["checkpoint_path"].endswith("training/step1490_step/state.pt")
        assert "model_identity" not in job
        assert key == evaluation.coordinate(job["seed"], job["arm"])


def test_existing_public_run_cannot_silently_change_provider(tmp_path):
    job = dict(seed=11, arm="C-only", model_identity={"point": "fixed"})
    directory = evaluation.generation_root(tmp_path, job)
    directory.mkdir(parents=True)
    (directory / "run.json").write_text("fixture")
    final = SimpleNamespace(
        read_json=lambda _: dict(
            tasks=["test"], provider={"point": "other"}, config={}, role="test"
        )
    )
    with pytest.raises(ValueError, match="differs"):
        evaluation.prepare_job(tmp_path, dict(tasks=["test"], config={}), job, final)


def test_future_endpoint_binding_is_per_job_and_precedes_prepare(tmp_path, monkeypatch):
    job = evaluation.future_job(tmp_path / "training", 137, "full")
    evidence = {k: job[k] for k in ("seed", "arm", "step", "phase")}
    evidence.update(checkpoint=dict(path=job["checkpoint_path"]), parameter_digest="weights")
    calls, cpu_state = [], {"parameters": "mock"}
    plan = dict(
        id="registered-all-nine",
        block="B",
        jobs={"seed137/full": job},
        training_root=str(tmp_path / "training"),
        training_protocol_id="training-id",
        original_dev_registration={"path": "old"},
        assets={"base_binding": {"id": "base"}},
    )
    final = SimpleNamespace(
        read_bound=lambda _: {
            "jobs": {
                "seed11/static": {
                    "model_identity": dict(
                        tokenizer_digest="codec", chat_template_digest="template"
                    )
                }
            }
        },
        ModelIdentity=Identity,
        digest=digest,
        bound=bound,
        _publish=lambda path, record: calls.append(("bind", path, record)),
    )
    monkeypatch.setattr(
        evaluation,
        "training_module",
        lambda: SimpleNamespace(
            checked_evaluation_checkpoint=lambda root, seed, arm: (evidence, cpu_state)
        ),
    )
    monkeypatch.setattr(evaluation, "prepare_job", lambda *args: calls.append(("prepare", args)))
    actual, state = evaluation.bind_b_locked(tmp_path, plan, 137, "full", final, keep_state=True)
    assert state is cpu_state and actual["arm"] == "Full"
    assert [c[0] for c in calls] == ["bind", "prepare"]
    assert calls[0][2]["registered_future_endpoint"] == job
    evidence["checkpoint"]["path"] = "/not/the/registered/checkpoint"
    with pytest.raises(ValueError, match="not the registered"):
        evaluation.bind_b_locked(tmp_path, plan, 137, "full", final)


@pytest.mark.parametrize("mode", ["unsettled", "existing_attempt", "sealed"])
def test_generation_no_implicit_resume_and_no_early_gpu(tmp_path, monkeypatch, mode):
    touched = []
    job = dict(seed=11, arm="C-only")
    plan = dict(block="A", jobs={"seed11/c_only": job})
    monkeypatch.setattr(evaluation, "load_runtime", lambda: SimpleNamespace())
    monkeypatch.setattr(evaluation, "checked_plan", lambda *args: plan)
    monkeypatch.setattr(evaluation, "prepare_job", lambda *args: None)
    monkeypatch.setattr(evaluation, "read_state", lambda *args: touched.append("checkpoint/GPU"))
    monkeypatch.setattr(evaluation, "seal_model", lambda *args: (dict(id="generation-only"), []))
    if mode == "unsettled":

        def inspect(*args):
            raise ValueError("unsettled intent")

        monkeypatch.setattr(evaluation, "inspect_model", inspect)
        with pytest.raises(ValueError, match="unsettled"):
            evaluation.generate(tmp_path, 11, "c_only", 0, resume=True)
    elif mode == "existing_attempt":
        (evaluation.model_root(tmp_path, job) / "attempts").mkdir(parents=True)
        monkeypatch.setattr(evaluation, "inspect_model", lambda *args: dict(sealed=False))
        with pytest.raises(ValueError, match="explicit resume"):
            evaluation.generate(tmp_path, 11, "c_only", 0)
    else:
        monkeypatch.setattr(evaluation, "inspect_model", lambda *args: dict(sealed=True))
        assert evaluation.generate(tmp_path, 11, "c_only", 0) == dict(id="generation-only")
    assert touched == []


def test_fixed_generation_seed_and_api_policy(monkeypatch):
    config = SimpleNamespace(seed=20260928)
    monkeypatch.setattr(evaluation.original, "test_config", lambda _: config)
    assert evaluation.test_config(None).seed == 20260928
    config.seed = 42
    with pytest.raises(ValueError, match="RNG seed"):
        evaluation.test_config(None)


def test_no_combined_selection_by_missing_seed():
    blocks = []
    for block in ("A", "B"):
        reports, tasks = make_reports(block)
        blocks.append(
            dict(
                block=block,
                statistics=evaluation.statistics_contract(block),
                comparisons=evaluation.paired_summary(reports, tasks, block),
            )
        )
    broken = copy.deepcopy(blocks)
    del broken[1]["comparisons"]["Full-C-only"]["execution_accuracy"]["paired_by_seed"]["389"]
    with pytest.raises(ValueError, match="all three old and three new"):
        evaluation.combine_summaries(*broken)


def test_real_training_evaluation_interface_in_fresh_frozen_runtime():
    """Actual imports/contracts only: no registration, state load, GPU or private data."""
    program = """
import inspect
import json
from pathlib import Path
import finqa_v25_evaluation as evaluation
training = evaluation.training_module()
assert list(inspect.signature(training.evaluation_contract).parameters) == ['root']
parameters = list(inspect.signature(training.checked_evaluation_checkpoint).parameters)
assert parameters == ['root', 'seed', 'arm']
assert training.SEEDS == evaluation.NEW_SEEDS
assert training.ARMS == evaluation.ARMS
root = Path('/tmp/v25-interface-contract-only-no-output')
for seed in evaluation.NEW_SEEDS:
    for arm in evaluation.ARMS:
        future = evaluation.future_job(root, seed, arm)
        endpoint = root / training.coordinate(seed, arm) / 'training/step1490_step/state.pt'
        assert future['checkpoint_path'] == str(endpoint)
        assert future['phase'] == 'step' and future['step'] == 1490
final = evaluation.load_runtime()
runtime = training.load_runtime()
assert runtime.storage.runtime_binding() == final.runtime_binding()
config = evaluation.test_config(final)
assert config.seed == 20260928 and config.temperature == 0
assert config.top_p == 1 and config.top_k == 0
assert config.context_limit == 24576 and config.max_new_tokens == 2048 and config.max_steps == 32
assert config.api_model == 'deepseek-flash' and not final.torch.cuda.is_initialized()
assert 'finqa_v25_training_replication.py' in evaluation.source_binding('B')
cuda = final.torch.cuda.is_initialized()
print(json.dumps(dict(matched=True, CUDA_initialized=cuda, API_calls=0)))
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        env={
            **os.environ,
            "PYTHONPATH": str(evaluation.original.FROZEN / "trusted_data_synthesis/src")
            + os.pathsep
            + str(PROJECT / "scripts"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == dict(matched=True, CUDA_initialized=False, API_calls=0)
