"""Fake-model/CPU controls; no new sources, actual model or financial scoring."""

import copy
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_direction_calibration_evaluation_20260926 as m
import pytest
import test_fixed_kernel_B_generation as legacy_tests

from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record as archive_record,
)

legacy_worker = legacy_tests.worker


def tasks(raw):
    return [
        {
            "task_id": f"synthetic-task-{index}",
            "group": m.GROUPS[index % 3],
            "source_cluster": "cik:" + str(index % 12 + 1).zfill(10),
            "path": str(raw / "never-read-task-text" / f"{index}.json"),
            "surface_version_id": f"synthetic-surface:{index}",
            "public_messages_sha256": f"synthetic-public:{index}",
        }
        for index in range(180)
    ]


def public_assets(raw, write):
    manifest = m.p.record("source_view_manifest_v2", split="calibration", tasks=tasks(raw))
    admitted = m.p.record(
        "calibration_panel_admission", passed=True, source_manifest_id=manifest["id"]
    )
    references = {}
    for name, value in (("manifest", manifest), ("admission", admitted)):
        path = raw / "panel" / (name + ".json")
        write(path, value)
        references[name] = {"path": str(path), "sha256": m.p.sha(path), "id": value["id"]}
    references["private_assets"] = {
        "path": str(raw / "must-not-read-private-index.json"),
        "sha256": "0" * 64,
    }
    return manifest, references


@pytest.fixture
def generation(legacy_worker):
    state = legacy_worker
    c, raw = state.common, state.common.RAW
    manifest, refs = public_assets(raw, c.write)
    state.plan = m.p.record(
        "synthetic_stage2_protocol", materials=state.plan["materials"], panel=refs
    )
    state.point = m.p.record(
        "anchored_model_parameter_point",
        **{
            key: value
            for key, value in state.point.items()
            if key not in {"schema_version", "id", "source_manifest_id"}
        },
        source_manifest_id=manifest["id"],
        step=240,
        run={"seed": 11, "condition": "negative"},
    )
    c.write(raw / "point/point.json", state.point, immutable=False)

    def committed(point_id, index, item):
        mode = "greedy" if item["job"]["repeat"] == 0 else "stochastic"
        key = point_id, mode, index
        assert state.commits.get(key, item) == item
        state.commits[key] = item

    c.generation_committed = committed

    def job(mode="stochastic", indices=(0, 1)):
        cohort = raw / "cohorts" / mode
        units = [
            {"index": index, "task": task, "repeat": repeat, "seed": index + 11000}
            for index, (task, repeat) in enumerate(
                (task, repeat)
                for task in manifest["tasks"]
                for repeat in ((1, 2) if mode == "stochastic" else (0,))
            )
        ]
        registration = m.p.record(
            "direction_calibration_generation_registration",
            protocol_id=state.plan["id"],
            point_id=state.point["id"],
            source_manifest_id=manifest["id"],
            seed=11,
            condition="negative",
            phase=mode,
            stochastic=mode == "stochastic",
            jobs=units,
        )
        c.write(cohort / "registration.json", registration)
        return dict(
            key="negative_11_" + mode,
            phase=mode,
            condition="negative",
            seed=11,
            point_path=str(raw / "point/point.json"),
            point_id=state.point["id"],
            source_manifest_id=manifest["id"],
            registration_path=str(cohort / "registration.json"),
            directory=str(cohort),
            jobs=[units[index] for index in indices],
        )

    state.new_job = job
    return state


def test_negative_generation_retains_label_and_exact_original_decoder_mode(generation):
    s, c = generation, generation.common
    old_context = m.legacy_generation.b
    job = s.new_job()
    result = m.run_generation(c, c.RAW, job, 1)
    assert result["condition"] == "negative" and result["phase"] == "stochastic"
    assert result["stochastic"] is True and result["trajectory_count"] == 2
    assert len(s.calls) == len(s.reserves) == 2
    assert result["private_assessment_performed"] is False
    assert m.legacy_generation.b is old_context
    loads = len(s.loads)
    assert m.run_generation(c, c.RAW, job, 2) == result
    assert len(s.loads) == loads and len(s.calls) == 2


def test_same_model_point_index_is_distinct_for_stochastic_and_greedy(generation):
    s, c = generation, generation.common
    stochastic = m.run_generation(c, c.RAW, s.new_job("stochastic", (0,)), 1)
    greedy = m.run_generation(c, c.RAW, s.new_job("greedy", (0,)), 1)
    assert stochastic["point_id"] == greedy["point_id"]
    assert stochastic["trajectories"][0]["job"]["repeat"] == 1
    assert greedy["trajectories"][0]["job"]["repeat"] == 0
    assert greedy["stochastic"] is False
    assert len(s.commits) == 2


def test_generation_rejects_wrong_arm_or_nonregistered_unit_before_model(generation):
    s, c = generation, generation.common
    job = s.new_job()
    with pytest.raises(ValueError, match="correct_arm"):
        m.run_generation(c, c.RAW, {**job, "condition": "positive"}, 1)
    changed = copy.deepcopy(job)
    changed["jobs"][0]["repeat"] = 0
    with pytest.raises(ValueError, match="exact_registered_shard"):
        m.run_generation(c, c.RAW, changed, 1)
    assert not s.loads and not s.calls


def test_generation_oom_preserves_commits_and_resumes_only_missing(generation):
    s, c = generation, generation.common
    job = s.new_job()
    s.fail_indices.add(1)
    with pytest.raises(c.old.feedback.torch.OutOfMemoryError):
        m.run_generation(c, c.RAW, job, 1)
    assert s.calls == [0, 1]
    result = m.run_generation(c, c.RAW, job, 2)
    assert result["complete"] and s.calls == [0, 1, 1]
    assert len(s.commits) == 2


@pytest.fixture
def scoring(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    state = SimpleNamespace(raw=raw, private_reads=[], calls=[], reserves=[], sizes=[], fail=None)

    def write(path, value, immutable=True):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = m.p.encode(value)
        if path.exists() and immutable:
            assert path.read_bytes() == encoded
        else:
            path.write_bytes(encoded)
        return value

    def reserve(kind, key, attempt, index):
        assert kind == "score_case"
        debit = kind, key, attempt, index
        assert debit not in state.reserves
        state.reserves.append(debit)

    manifest, refs = public_assets(raw, write)
    bundles = []
    for task in manifest["tasks"]:
        bundle = archive_record(
            "EvaluationTaskBundle",
            task_id=task["task_id"],
            source_cluster=task["source_cluster"],
            family=task["group"],
            validation={"status": "passed"},
            private={"synthetic": True},
        )
        path = raw / "private" / (task["task_id"] + ".json")
        write(path, bundle)
        bundles.append(
            dict(task_id=task["task_id"], path=str(path), sha256=m.p.sha(path), id=bundle["id"])
        )
    native = raw / "private/native_bindings.json"
    write(native, {})
    assets = m.p.record(
        "calibration_private_assets",
        source_manifest_id=manifest["id"],
        bundles=bundles,
        native_bindings=dict(path=str(native), sha256=m.p.sha(native)),
    )
    assets_path = raw / "private/assets.json"
    write(assets_path, assets)
    refs["private_assets"] = dict(
        path=str(assets_path), sha256=m.p.sha(assets_path), id=assets["id"]
    )
    plan = m.p.record("synthetic_stage2_protocol", panel=refs)
    cohorts, jobs = [], {}
    for seed in m.SEEDS:
        for arm in m.ARMS:
            point_id = f"synthetic_point:{arm}_{seed}"
            for mode in m.MODES:
                key = f"{arm}_{seed}_{mode}"
                directory = raw / "cohorts" / key
                units = [
                    {"index": index, "task": task, "repeat": repeat, "seed": seed * 1000 + index}
                    for index, (task, repeat) in enumerate(
                        (task, repeat)
                        for task in manifest["tasks"]
                        for repeat in ((1, 2) if mode == "stochastic" else (0,))
                    )
                ]
                registration = m.p.record(
                    "direction_calibration_generation_registration",
                    protocol_id=plan["id"],
                    point_id=point_id,
                    source_manifest_id=manifest["id"],
                    seed=seed,
                    condition=arm,
                    phase=mode,
                    stochastic=mode == "stochastic",
                    jobs=units,
                )
                write(directory / "registration.json", registration)
                trajectories = [
                    m.p.record(
                        "anchored_generated_trajectory",
                        job=unit,
                        point_id=point_id,
                        session_id=f"synthetic:{key}:{unit['index']}",
                        private_assessment_performed=False,
                        actual_generate_calls=1,
                        generated_tokens=1,
                    )
                    for unit in units
                ]
                frozen = m.p.record(
                    "anchored_generation_manifest",
                    complete=True,
                    point_id=point_id,
                    source_manifest_id=manifest["id"],
                    stochastic=mode == "stochastic",
                    tasks=manifest["tasks"],
                    trajectories=trajectories,
                )
                path = directory / "generation_manifest.json"
                write(path, frozen)
                row = dict(
                    key=key,
                    seed=seed,
                    condition=arm,
                    phase=mode,
                    point_id=point_id,
                    generation_manifest_path=str(path),
                    generation_manifest_sha256=m.p.sha(path),
                )
                cohorts.append(row)
                jobs[key] = dict(
                    key="score_" + key,
                    phase=mode,
                    condition=arm,
                    seed=seed,
                    directory=str(directory),
                    point_id=point_id,
                    source_manifest_id=manifest["id"],
                    seal_path=str(raw / "seal.json"),
                )
    seal = m.p.record(
        "calibration_generation_seal",
        protocol_id=plan["id"],
        source_manifest_id=manifest["id"],
        complete=True,
        all_generation_workers_exited=True,
        total_trajectories=4860,
        cohorts=cohorts,
    )
    write(raw / "seal.json", seal)
    state.plan, state.manifest, state.seal, state.jobs = plan, manifest, seal, jobs

    def initialize(raw_path, private, manifest_id, point_id, stochastic):
        assert Path(raw_path) == raw
        assert len(private["bundles"]) == 180
        assert private["generation_seal_id"] == seal["id"]
        state.initialized = manifest_id, point_id, stochastic

    def score_one(item):
        index, task = item["job"]["index"], item["job"]["task"]
        assert state.reserves[-1][-1] == index
        state.calls.append(index)
        if index == state.fail:
            raise RuntimeError("synthetic score failure, not a Q=0")
        assessment = m.p.record(
            "synthetic_assessment", session_id=item["session_id"], financial_valid=bool(index % 2)
        )
        return dict(
            index=index,
            task_id=task["task_id"],
            repeat=item["job"]["repeat"],
            group=task["group"],
            session_id=item["session_id"],
            Q=index % 2,
            assessment=assessment,
        )

    c = SimpleNamespace(
        RAW=raw,
        p=m.p,
        old=SimpleNamespace(feedback=SimpleNamespace(score_one=score_one)),
        read_protocol=lambda _root: plan,
        write=write,
        reserve=reserve,
    )
    state.c, state.write = c, write
    real_reference = m._reference

    def traced(reference):
        if "/private/" in reference["path"]:
            state.private_reads.append(reference["path"])
        return real_reference(reference)

    monkeypatch.setattr(m, "_reference", traced)
    monkeypatch.setattr(m.legacy_scoring, "initialize_scoring", initialize)

    class SyncExecutor:
        def __init__(self, *, max_workers, mp_context, initializer, initargs):
            assert mp_context.get_start_method() == "spawn"
            state.sizes.append(max_workers)
            initializer(*initargs)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def submit(self, fn, item):
            result = Future()
            try:
                result.set_result(fn(item))
            except BaseException as error:
                result.set_exception(error)
            return result

    monkeypatch.setattr(m, "ProcessPoolExecutor", SyncExecutor)
    return state


@pytest.mark.parametrize("change", ["workers", "count", "cohort", "point", "seed"])
def test_global_all4860_barrier_precedes_even_private_index_read(scoring, change):
    s = scoring
    body = {
        key: copy.deepcopy(value)
        for key, value in s.seal.items()
        if key not in {"id", "schema_version"}
    }
    if change == "workers":
        body["all_generation_workers_exited"] = False
    elif change == "count":
        body["total_trajectories"] -= 1
    elif change == "cohort":
        body["cohorts"].pop()
    elif change == "point":
        body["cohorts"][0]["point_id"] = "synthetic:wrong_point"
    else:
        body["cohorts"][0]["seed"] = 999
    s.write(s.raw / "seal.json", m.p.record("calibration_generation_seal", **body), immutable=False)
    with pytest.raises(ValueError):
        m.run_scoring(s.c, s.raw, s.jobs["negative_11_greedy"], 1)
    assert not s.private_reads and not s.calls and not s.reserves


@pytest.mark.parametrize("mode,expected", [("greedy", 180), ("stochastic", 360)])
def test_scoring_uses_original_financial_Q_and_same_global_seal(scoring, mode, expected):
    s = scoring
    job = s.jobs["negative_11_" + mode]
    result = m.run_scoring(s.c, s.raw, job, 1)
    assert result["denominator"] == expected
    assert result["qualified"] == expected // 2
    assert result["phase"] == mode and result["condition"] == "negative"
    assert result["generation_seal_id"] == s.seal["id"]
    assert result["financial_rule_unchanged"] is True
    assert s.sizes == [12] and len(s.calls) == expected
    reads = list(s.private_reads)
    assert m.run_scoring(s.c, s.raw, job, 2) == result
    assert s.private_reads == reads and len(s.calls) == expected


def test_score_failure_is_not_zero_and_resume_skips_committed_cases(scoring):
    s = scoring
    job = s.jobs["negative_11_greedy"]
    s.fail = 2
    with pytest.raises(RuntimeError, match="not a Q=0"):
        m.run_scoring(s.c, s.raw, job, 1)
    path = Path(job["directory"])
    assert (path / "score_rows/0000.json").exists()
    assert (path / "score_rows/0001.json").exists()
    assert not (path / "score_rows/0002.json").exists()
    s.fail = None
    result = m.run_scoring(s.c, s.raw, job, 2)
    assert result["denominator"] == 180
    assert s.calls.count(0) == s.calls.count(1) == 1
