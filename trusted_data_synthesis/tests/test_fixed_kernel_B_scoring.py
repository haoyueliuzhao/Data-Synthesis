"""Synthetic CPU scoring recovery/barrier checks, with no real private data."""

import ast
import copy
import hashlib
import importlib.util
import json
import os
import sys
from concurrent.futures import Future
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/fixed_kernel_B_scoring_20260922.py"


def pure_protocol():
    path = (
        Path(__file__).parents[1]
        / "src/trusted_synthesis/experiments/finance_qa_vnext_fixed_kernel_value/protocol.py"
    )
    names = {"require", "encode", "sha", "record", "checked", "read_json", "now"}
    tree = ast.parse(path.read_text())
    tree.body = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = dict(
        copy=copy,
        hashlib=hashlib,
        json=json,
        os=os,
        Path=Path,
        datetime=datetime,
        timezone=timezone,
    )
    exec(compile(tree, str(path), "exec"), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in names})


p = pure_protocol()


@pytest.fixture
def scorer(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    state = SimpleNamespace(
        raw=raw,
        calls=[],
        reserves=[],
        private_calls=[],
        gate_calls=[],
        executor_sizes=[],
        fail_case=None,
        fail_assessment_once=None,
    )

    def write(path, value, *, immutable=True):
        path = Path(path)
        if path.parent.name == "assessments" and path.stem == state.fail_assessment_once:
            state.fail_assessment_once = None
            raise RuntimeError("synthetic interruption after score_rows commit")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = p.encode(value)
        if immutable and path.exists():
            p.require(path.read_bytes() == data, "fake.immutable_conflict")
        else:
            path.write_bytes(data)
        return value

    def reserve(kind, key, attempt, index):
        assert kind == "score_case"
        value = kind, key, attempt, index
        assert value not in state.reserves
        state.reserves.append(value)

    def score_value(item):
        unit, task = item["job"], item["job"]["task"]
        result = p.record(
            "synthetic_assessment",
            session_id=item["session_id"],
            financial_valid=bool(unit["index"] % 2),
        )
        return dict(
            index=unit["index"],
            task_id=task["task_id"],
            repeat=unit["repeat"],
            group=task["group"],
            session_id=item["session_id"],
            Q=int(result["financial_valid"]),
            assessment=result,
        )

    def score_one(item):
        index = item["job"]["index"]
        assert state.reserves[-1][-1] == index
        state.calls.append(index)
        if index == state.fail_case:
            raise RuntimeError("synthetic scoring failure")
        stored = feedback._SCORING
        assert stored[0] == raw
        assert stored[2:5] == (
            state.frozen["source_manifest_id"],
            state.frozen["point_id"],
            state.frozen["stochastic"],
        )
        assert stored[5:] == ("synthetic-runtime", {})
        return score_value(item)

    def development_private(root, source_root, tasks):
        assert Path(source_root) == tmp_path / "private-dev-never-opened"
        assert tasks == state.frozen["tasks"]
        state.private_calls.append("dev")
        return dict(confirm_bundles_opened=0, bundles={})

    def generation_seal(root, plan, manifest, seal_path):
        state.gate_calls.append("global_generation_barrier")
        seal = p.checked(p.read_json(seal_path), "B_confirm_generation_seal")
        p.require(
            seal["complete"] is True
            and seal["all_generation_workers_exited"] is True
            and seal["total_trajectories"] == 4320
            and len(seal["models"]) == 6
            and {(model["seed"], model["condition"]) for model in seal["models"]}
            == {(seed, condition) for seed in (11, 29, 47) for condition in ("static", "delayed_c")}
            and seal["protocol_id"] == plan["id"]
            and seal["source_manifest_id"] == manifest["id"],
            "fake.global_six_model_generation_seal",
        )
        return seal

    def confirmation_private(root, plan, manifest, seal_path):
        seal = generation_seal(root, plan, manifest, seal_path)
        state.private_calls.append("confirm")
        return dict(
            confirm_bundles_opened=720,
            source_manifest_id=manifest["id"],
            generation_seal_id=seal["id"],
            sealed_point_ids=[model["point_id"] for model in seal["models"]],
            bundles={},
        )

    feedback = SimpleNamespace(
        score_one=score_one,
        given=SimpleNamespace(offline_assets=development_private),
        views=SimpleNamespace(build_runtime=lambda: "synthetic-runtime"),
    )
    common = SimpleNamespace(
        RAW=raw,
        p=p,
        old=SimpleNamespace(feedback=feedback),
        write=write,
        reserve=reserve,
        read_protocol=lambda root: state.plan,
    )
    confirmation = SimpleNamespace(
        offline_assets=confirmation_private,
        require_generation_seal=generation_seal,
    )
    monkeypatch.setitem(sys.modules, "fixed_kernel_B_common_20260922", common)
    monkeypatch.setitem(sys.modules, "fixed_kernel_B_confirm_views_20260922", confirmation)
    spec = importlib.util.spec_from_file_location("synthetic_B_scoring", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class SyncExecutor:
        def __init__(self, *, max_workers, mp_context, initializer, initargs):
            assert mp_context.get_start_method() == "spawn"
            state.executor_sizes.append(max_workers)
            initializer(*initargs)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def submit(self, function, item):
            future = Future()
            try:
                future.set_result(function(item))
            except Exception as failure:
                future.set_exception(failure)
            return future

    module.ProcessPoolExecutor = SyncExecutor
    state.module, state.common, state.score_value = module, common, score_value
    state.plan = p.record(
        "B_confirm_protocol",
        materials=dict(private_scoring_source_root=str(tmp_path / "private-dev-never-opened")),
    )

    def setup(*, phase="feedback", incomplete=False, seal_complete=True):
        count = 180 if phase == "feedback" else 720
        tasks = [
            dict(
                task_id=f"synthetic-task-{index}",
                group="composition_required",
                path=str(raw / "public-never-opened" / f"{index:04d}.json"),
            )
            for index in range(count)
        ]
        source_id = "synthetic-dev-source"
        if phase == "confirm":
            views = p.record("source_view_manifest_v2", tasks=tasks, split="confirm")
            write(raw / "confirm_views/manifest.json", views)
            source_id = views["id"]
        jobs = [
            dict(index=index, task=task, repeat=repeat, seed=100 + index)
            for index, (task, repeat) in enumerate(
                (task, repeat)
                for task in tasks
                for repeat in ((1, 2) if phase == "feedback" else (0,))
            )
        ]
        rows = [
            p.record(
                "anchored_generated_trajectory",
                job=unit,
                point_id="point:synthetic",
                session_id=f"session:synthetic-{unit['index']}",
                path="never-read.json.gz",
                sha256="synthetic-bytes",
                bytes=1,
                actual_generate_calls=1,
                generated_tokens=1,
                private_assessment_performed=False,
            )
            for unit in jobs
        ]
        directory = raw / phase
        registration = p.record(
            "B_generation_registration",
            protocol_id=state.plan["id"],
            point_id="point:synthetic",
            source_manifest_id=source_id,
            stochastic=phase == "feedback",
            seed=11,
            condition="delayed_c",
            jobs=jobs,
        )
        frozen = p.record(
            "anchored_generation_manifest",
            complete=True,
            stochastic=phase == "feedback",
            point_id="point:synthetic",
            source_manifest_id=source_id,
            tasks=tasks,
            trajectories=rows[:-1] if incomplete else rows,
        )
        write(directory / "registration.json", registration)
        write(directory / "generation_manifest.json", frozen)
        job = dict(
            key="synthetic_score",
            phase=phase,
            directory=str(directory),
            point_id="point:synthetic",
            source_manifest_id=source_id,
            seed=11,
            condition="delayed_c",
        )
        state.seal_id = None
        if phase == "confirm":
            seal = p.record(
                "B_confirm_generation_seal",
                complete=seal_complete,
                all_generation_workers_exited=seal_complete,
                total_trajectories=4320,
                protocol_id=state.plan["id"],
                source_manifest_id=source_id,
                models=[
                    dict(seed=seed, condition=condition, point_id="point:synthetic")
                    for seed in (11, 29, 47)
                    for condition in ("static", "delayed_c")
                ],
            )
            write(raw / "confirm_global_seal.json", seal)
            job["seal_path"] = str(raw / "confirm_global_seal.json")
            state.seal_id = seal["id"]
        state.job, state.frozen = job, frozen
        return job

    def precommit(indices):
        for index in indices:
            value = score_value(state.frozen["trajectories"][index])
            row = p.record(
                "B_scored_case",
                **value,
                generation_manifest_id=state.frozen["id"],
                point_id="point:synthetic",
                source_manifest_id=state.frozen["source_manifest_id"],
                generation_seal_id=state.seal_id,
            )
            write(Path(state.job["directory"]) / "score_rows" / f"{index:04d}.json", row)

    state.setup, state.precommit = setup, precommit
    return state


@pytest.mark.parametrize("phase", ["feedback", "confirm"])
def test_incomplete_cohort_is_rejected_before_any_private_access(scorer, phase):
    job = scorer.setup(phase=phase, incomplete=True)
    with pytest.raises(ValueError, match="complete_fixed_cohort_before_private_assets"):
        scorer.module.run(scorer.raw, job, 1)
    assert scorer.private_calls == scorer.gate_calls == scorer.calls == scorer.reserves == []


def test_global_confirmation_seal_blocks_private_access_and_scoring(scorer):
    job = scorer.setup(phase="confirm", seal_complete=False)
    with pytest.raises(ValueError, match="global_six_model_generation_seal"):
        scorer.module.run(scorer.raw, job, 1)
    assert scorer.gate_calls == ["global_generation_barrier"]
    assert scorer.private_calls == scorer.calls == scorer.reserves == []


@pytest.mark.parametrize("phase,denominator", [("feedback", 360), ("confirm", 720)])
def test_complete_scoring_preserves_report_and_never_rescores_on_resume(scorer, phase, denominator):
    job = scorer.setup(phase=phase)
    report = scorer.module.run(scorer.raw, job, 1)
    assert report["denominator"] == denominator
    assert report["qualified"] == denominator // 2
    assert report["confirm_tasks_opened"] == (720 if phase == "confirm" else 0)
    assert scorer.calls == list(range(denominator))
    assert len(scorer.reserves) == denominator
    assert scorer.executor_sizes == [12]
    assert all(set(row) == set(scorer.module.SCORE_FIELDS) for row in report["scores"])
    private_before = list(scorer.private_calls)
    assert scorer.module.run(scorer.raw, job, 2) == report
    assert scorer.private_calls == private_before
    assert len(scorer.calls) == denominator


def test_missing_assessment_copy_is_repaired_and_only_missing_score_is_submitted(scorer):
    job = scorer.setup()
    scorer.precommit(range(1, 360))
    report = scorer.module.run(scorer.raw, job, 1)
    assert scorer.calls == [0]
    assert len(scorer.reserves) == 1
    assert scorer.executor_sizes == [1]
    assert report["denominator"] == 360
    assert len(list((Path(job["directory"]) / "assessments").glob("*.json"))) == 360


@pytest.mark.parametrize("phase,count", [("feedback", 360), ("confirm", 720)])
def test_all_score_rows_committed_need_no_private_reopen_or_rescoring(scorer, phase, count):
    job = scorer.setup(phase=phase)
    scorer.precommit(range(count))
    report = scorer.module.run(scorer.raw, job, 1)
    assert report["denominator"] == count
    assert scorer.private_calls == scorer.calls == scorer.reserves == scorer.executor_sizes == []
    assert scorer.gate_calls == (["global_generation_barrier"] if phase == "confirm" else [])


def test_interruption_after_score_commit_repairs_assessment_without_repeating_case(scorer):
    job = scorer.setup()
    scorer.precommit(range(1, 360))
    scorer.fail_assessment_once = "0000"
    with pytest.raises(RuntimeError, match="after score_rows commit"):
        scorer.module.run(scorer.raw, job, 1)
    assert (Path(job["directory"]) / "score_rows/0000.json").exists()
    assert not (Path(job["directory"]) / "assessments/0000.json").exists()
    report = scorer.module.run(scorer.raw, job, 2)
    assert scorer.calls == [0]
    assert scorer.private_calls == ["dev"]
    assert len(scorer.reserves) == 1
    assert report["denominator"] == 360


@pytest.mark.parametrize("tamper", ["Q", "session_id", "task_id", "assessment_session"])
def test_tampered_committed_score_is_rejected_before_private_access(scorer, tamper):
    job = scorer.setup()
    scorer.precommit([0])
    path = Path(job["directory"]) / "score_rows/0000.json"
    row = p.read_json(path)
    body = {key: value for key, value in row.items() if key not in ("id", "schema_version")}
    if tamper == "Q":
        body["Q"] = 1
    elif tamper == "assessment_session":
        body["assessment"]["session_id"] = "wrong-assessment-session"
    else:
        body[tamper] = "wrong-identity"
    scorer.common.write(path, p.record("B_scored_case", **body), immutable=False)
    with pytest.raises(ValueError):
        scorer.module.run(scorer.raw, job, 1)
    assert scorer.private_calls == scorer.calls == scorer.reserves == []


def test_scoring_failure_is_not_committed_as_zero_reward(scorer):
    job = scorer.setup()
    scorer.precommit(range(1, 360))
    scorer.fail_case = 0
    with pytest.raises(RuntimeError, match="scoring failure"):
        scorer.module.run(scorer.raw, job, 1)
    directory = Path(job["directory"])
    assert not (directory / "score_rows/0000.json").exists()
    assert not (directory / "assessments/0000.json").exists()
    assert not (directory / "scoring_report.json").exists()
    assert len(scorer.reserves) == 1
