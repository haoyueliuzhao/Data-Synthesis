"""Necessary CPU-only tests: no API, GPU, real registration, or private data."""

import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
confirmation = importlib.import_module("finqa_v23_test_confirmation")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def bound(value):
    return {**value, "id": digest(value)}


class Config:
    def __init__(self, values):
        self.__dict__.update(values)

    def model_dump(self, **kwargs):
        return self.__dict__.copy()

    @classmethod
    def model_validate(cls, value):
        return cls(value)


@pytest.fixture
def public_fixture():
    config = dict(
        api_model="deepseek-flash",
        role="development",
        temperature=0,
        top_p=1,
        top_k=0,
        max_steps=32,
        max_new_tokens=2048,
        context_limit=24576,
        harness_id="bigfinance-derived-vtdo-v7",
        seed=20260928,
    )
    keys = [f"finqa/q{i}" for i in range(1147)]
    tasks = [SimpleNamespace(dataset="finqa", task_id=key[6:]) for key in keys]
    lineages = [
        SimpleNamespace(
            original_split="test", source_group=f"source{i % 7}", source_group_level="company"
        )
        for i in range(1147)
    ]
    runtime = {"providers.py": "actual", "harness.py": "same"}
    dev = dict(
        schema="v9_fifteen_final_dev_evaluation.v1",
        runtime_binding=runtime,
        evaluation_source_sha256=runtime,
        config=config,
        snapshot="public-fixture",
        snapshot_id="fixture-manifest",
        role_plan={"assignments": dict.fromkeys(keys, "test")},
        assets={"base_binding": {"id": "original-base"}},
    )
    certificate = dict(
        schema="v22_exact_provider_compatibility_certificate.v1",
        actual_runtime_binding=runtime,
        actual_evaluation_sources=runtime,
    )
    final = SimpleNamespace(
        base=SimpleNamespace(evaluation_config=lambda: Config(config)),
        RunConfig=Config,
        runtime_binding=lambda: runtime.copy(),
        load_public_snapshot=lambda _: ({"id": "fixture-manifest"}, tasks, lineages),
        verify_role_plan=lambda *_: None,
        task_key=lambda t: t.dataset + "/" + t.task_id,
        runtime_task_view=lambda t, c: {"task_id": t.task_id},
        digest=digest,
        system_message=lambda _: "unchanged-public-system",
        episode_tool_specs=lambda _: [{"name": "unchanged-public-tool"}],
    )
    return SimpleNamespace(
        final=final, dev=dev, certificate=certificate, tasks=tasks, lineages=lineages, keys=keys
    )


def test_public_contract_changes_role_only_without_reading_reference(public_fixture):
    f = public_fixture
    result = confirmation.public_test_contract(f.final, f.dev, f.certificate)
    expected = {**f.dev["config"], "role": "test"}
    assert result["config"] == expected
    assert result["tasks"] == f.keys
    assert result["original_split"] == "test"
    assert result["denominator"] == 1147
    assert result["evaluation_source_sha256"] == f.certificate["actual_evaluation_sources"]
    assert result["Base_or_dev_contract_rewritten"] is False
    assert f.dev["config"]["role"] == "development"


@pytest.mark.parametrize("mutation", ["source", "snapshot", "split", "role", "model", "budget"])
def test_public_contract_rejects_mutated_original_inputs(public_fixture, mutation):
    f = public_fixture
    if mutation == "source":
        f.certificate["actual_runtime_binding"] = {"providers.py": "other"}
    elif mutation == "snapshot":
        f.dev["snapshot_id"] = "other"
    elif mutation == "split":
        f.lineages[-1].original_split = "dev"
    elif mutation == "role":
        f.dev["role_plan"]["assignments"][f.keys[-1]] = "development"
    elif mutation == "model":
        f.dev["config"]["api_model"] = "other-model"
    elif mutation == "budget":
        f.dev["config"]["max_new_tokens"] = 4096
    with pytest.raises(ValueError):
        confirmation.public_test_contract(f.final, f.dev, f.certificate)


def test_fixed_statistics_and_coordinates():
    contract = confirmation.statistics_contract()
    assert contract["bootstrap"]["replicates"] == 20000
    assert contract["bootstrap"]["seed"] == 20261005
    assert contract["bootstrap"]["quantile_method"] == "linear"
    assert contract["bootstrap"]["shared_cluster_multiplicity_applies_to_all_six_models"]
    assert "not training-randomness" in contract["uncertainty_scope"]
    assert confirmation.coordinate(11, "static") == "seed11/static"
    with pytest.raises(ValueError):
        confirmation.coordinate(11, "c_only")
    with pytest.raises(ValueError):
        confirmation.coordinate(99, "Full")


def test_cluster_bootstrap_is_deterministic_task_weighted_ratio():
    values, groups = [1, 0, 0, 0], ["A", "B", "B", "B"]
    result = confirmation.source_cluster_bootstrap(values, groups)
    rng = np.random.Generator(np.random.PCG64(20261005))
    samples = np.empty(20000)
    for i in range(20000):
        sampled = rng.integers(0, 2, size=2)
        samples[i] = np.array([1, 0])[sampled].sum() / np.array([1, 3])[sampled].sum()
    interval = np.quantile(samples, [0.025, 0.975], method="linear")
    assert result["mean_difference"] == 0.25  # not company-equal-weighted .5
    assert [result["lower"], result["upper"]] == interval.tolist()
    assert result["cluster_task_counts"] == {"A": 1, "B": 3}
    assert (
        result["bootstrap_values_sha256"]
        == hashlib.sha256(samples.astype("<f8").tobytes()).hexdigest()
    )
    assert result == confirmation.source_cluster_bootstrap(values, groups)
    assert not result["confirmed_positive_effect"]  # zero included is not confirmation


def test_positive_degenerate_interval_and_invalid_inputs():
    result = confirmation.source_cluster_bootstrap([1, 1], ["same", "same"])
    assert result["lower"] == result["upper"] == 1
    assert result["confirmed_positive_effect"] is True
    for values, groups in (([np.nan], ["A"]), ([1], [""]), ([1], ["A", "B"])):
        with pytest.raises(ValueError):
            confirmation.source_cluster_bootstrap(values, groups)


def make_reports():
    tasks = [f"finqa/q{i}" for i in range(1147)]
    groups = {
        key: {"group": "A" if i == 0 else "B", "level": "company"} for i, key in enumerate(tasks)
    }
    reports = {}
    for seed in confirmation.SEEDS:
        for arm in confirmation.ARMS:
            rows = []
            for i, key in enumerate(tasks):
                value = int(
                    i == 0 and ((seed != 29 and arm == "Full") or (seed == 29 and arm == "Static"))
                )
                rows.append(
                    dict(
                        task_key=key,
                        native={"native": dict(execution_accuracy=value, program_accuracy=value)},
                    )
                )
            reports[confirmation.coordinate(seed, arm)] = dict(
                seed=seed,
                arm=arm,
                denominator=1147,
                results=rows,
                metrics=confirmation.native_metrics(rows),
            )
    return reports, tasks, groups


def test_paired_summary_averages_seeds_before_source_resampling():
    reports, tasks, groups = make_reports()
    result = confirmation.paired_summary(reports, tasks, groups)
    primary = result["execution_accuracy"]
    assert primary["per_question_mean_difference"][tasks[0]] == 1 / 3
    assert primary["mean_difference"] == pytest.approx(1 / (3 * 1147))
    assert primary["paired_by_seed"]["29"]["mean_difference"] == -1 / 1147
    assert "source_cluster_bootstrap" not in result["program_accuracy"]
    assert result["program_accuracy"]["descriptive_only"]
    assert primary["source_cluster_bootstrap"]["question_count"] == 1147


@pytest.mark.parametrize("mutation", ["missing", "unknown", "order", "coordinate", "metric"])
def test_paired_summary_rejects_incomplete_or_changed_results(mutation):
    reports, tasks, groups = make_reports()
    report = reports["seed11/static"]
    if mutation == "missing":
        del reports["seed47/full"]
    elif mutation == "unknown":
        report["results"][0]["native"]["native"]["execution_accuracy"] = None
        report["metrics"] = confirmation.native_metrics(report["results"])
    elif mutation == "order":
        report["results"] = report["results"][::-1]
    elif mutation == "coordinate":
        report["seed"] = 29
    elif mutation == "metric":
        report["metrics"]["execution_accuracy"]["correct"] = 7
    with pytest.raises(ValueError):
        confirmation.paired_summary(reports, tasks, groups)


def test_global_seal_is_required_before_any_private_read(tmp_path, monkeypatch):
    private_reads, attempts, publications = [], [], []
    jobs = {
        confirmation.coordinate(s, a): {"seed": s, "arm": a}
        for s in confirmation.SEEDS
        for a in confirmation.ARMS
    }
    plan = {"id": "registered-before-test", "jobs": jobs}

    def fake_seal(root, plan, job, final):
        key = confirmation.coordinate(job["seed"], job["arm"])
        attempts.append(key)
        if key == "seed47/full":
            raise ValueError("unsealed last model")
        return {"id": key}, ["sealed-episodes"]

    final = SimpleNamespace(
        file_binding=lambda path: {"path": str(path), "sha256": "fixture"},
        bound=bound,
        _publish=lambda *args: publications.append(args),
        _read_snapshot_rows=lambda *args: private_reads.append(args),
    )
    monkeypatch.setattr(confirmation, "load_runtime", lambda: final)
    monkeypatch.setattr(confirmation, "checked_plan", lambda *args: plan)
    monkeypatch.setattr(confirmation, "seal_model", fake_seal)
    with pytest.raises(ValueError, match="unsealed last model"):
        confirmation.score(tmp_path)
    assert len(attempts) == 6
    assert private_reads == publications == []


def test_global_seal_contains_exactly_six_model_seals(tmp_path, monkeypatch):
    jobs = {
        confirmation.coordinate(s, a): {"seed": s, "arm": a}
        for s in confirmation.SEEDS
        for a in confirmation.ARMS
    }
    calls = []
    final = SimpleNamespace(
        file_binding=lambda path: {"path": str(path), "sha256": "fixture"},
        bound=bound,
        _publish=lambda *args: calls.append(args),
    )
    monkeypatch.setattr(
        confirmation,
        "seal_model",
        lambda root, plan, job, runtime: (
            {"id": confirmation.coordinate(job["seed"], job["arm"])},
            ["episodes"],
        ),
    )
    barrier, episodes = confirmation.seal_all(tmp_path, {"id": "fixed", "jobs": jobs}, final)
    assert set(barrier["models"]) == set(episodes) == set(jobs)
    assert barrier["total_episodes"] == 6882
    assert barrier["private_references_read"] is False
    assert calls[0][0] == tmp_path / "all_generation_seal"


def test_registration_is_persisted_before_any_generation_preparation(tmp_path, monkeypatch):
    calls, read_states = [], []
    jobs = {
        confirmation.coordinate(s, a): dict(
            seed=s, arm=a, step=1490, model_identity={"backend": "local_torch"}
        )
        for s in confirmation.SEEDS
        for a in confirmation.ARMS
    }
    dev = dict(
        jobs=jobs,
        training_protocol={"path": "old"},
        training_root="old",
        training_task_ids=["train"],
        material_identity={},
        device_policy={},
    )
    common = dict(snapshot="public", role_plan={}, config={"role": "test"}, tasks=["test"])
    final = SimpleNamespace(
        read_bound=lambda _: dev,
        read_registered_state=lambda _, job: read_states.append(job),
        bound=bound,
        now=lambda: "fixed",
        runtime_binding=lambda: {"frozen": "source"},
        file_binding=lambda path: {"path": str(path), "sha256": "fixture"},
        _publish=lambda path, plan: calls.append(("register", path, plan)),
        prepare_run=lambda *args, **kwargs: calls.append(("prepare", args, kwargs)),
        RunConfig=Config,
        ModelIdentity=Config,
    )
    monkeypatch.setattr(confirmation, "load_runtime", lambda: final)
    monkeypatch.setattr(confirmation, "public_test_contract", lambda *args: common)
    result = confirmation.register(tmp_path / "mock-registration")
    assert len(read_states) == 6
    assert calls[0][0] == "register"
    assert len(calls) == 7 and all(c[0] == "prepare" for c in calls[1:])
    assert result["statistics"] == confirmation.statistics_contract()
    assert result["API_calls"] == 0 and result["no_training"]
    assert result["total_provider_attempt_cap"] == 220224


def test_unsettled_generation_blocks_before_state_load_or_gpu(tmp_path, monkeypatch):
    touched = []
    final = SimpleNamespace(
        read_registered_state=lambda *args: touched.append("checkpoint"),
        gpu_inventory=lambda: touched.append("GPU"),
    )
    plan = {"jobs": {"seed11/static": {"seed": 11, "arm": "Static"}}}
    monkeypatch.setattr(confirmation, "load_runtime", lambda: final)
    monkeypatch.setattr(confirmation, "checked_plan", lambda *args: plan)

    def unsettled(*args):
        raise ValueError("durable episode intent without completed raw episode")

    monkeypatch.setattr(confirmation, "inspect_model", unsettled)
    with pytest.raises(ValueError, match="durable episode intent"):
        confirmation.generate(tmp_path, 11, "static", 0, resume=True)
    assert touched == []


def test_existing_attempt_needs_explicit_resume_before_gpu(tmp_path, monkeypatch):
    touched = []
    job = {"seed": 11, "arm": "Static"}
    (confirmation.model_root(tmp_path, job) / "attempts").mkdir(parents=True)
    final = SimpleNamespace(
        read_registered_state=lambda *args: touched.append("checkpoint"),
        gpu_inventory=lambda: touched.append("GPU"),
    )
    monkeypatch.setattr(confirmation, "load_runtime", lambda: final)
    monkeypatch.setattr(
        confirmation, "checked_plan", lambda *args: {"jobs": {"seed11/static": job}}
    )
    monkeypatch.setattr(confirmation, "inspect_model", lambda *args: {"sealed": False})
    with pytest.raises(ValueError, match="explicit resume"):
        confirmation.generate(tmp_path, 11, "static", 0)
    assert touched == []


def test_sealed_generation_only_returns_seal_never_scores_or_reads_private(tmp_path, monkeypatch):
    job = {"seed": 11, "arm": "Static"}
    monkeypatch.setattr(confirmation, "load_runtime", lambda: SimpleNamespace())
    monkeypatch.setattr(
        confirmation, "checked_plan", lambda *args: {"jobs": {"seed11/static": job}}
    )
    monkeypatch.setattr(confirmation, "inspect_model", lambda *args: {"sealed": True})
    monkeypatch.setattr(confirmation, "seal_model", lambda *args: ({"id": "generation-only"}, []))
    assert confirmation.generate(tmp_path, 11, "static", 0) == {"id": "generation-only"}
