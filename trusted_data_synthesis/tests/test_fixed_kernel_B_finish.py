"""CPU-only finish/publication recovery: synthetic metadata and fake git only."""

import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
runner = importlib.import_module("run_fixed_kernel_B_confirmation_20260922")
b, p = runner.b, runner.p


@pytest.fixture
def completion(tmp_path, monkeypatch):
    root, raw = tmp_path / "repo", tmp_path / "raw"
    root.mkdir()
    monkeypatch.setattr(b, "RAW", raw)
    models = [
        dict(key=f"B_{condition}_{seed}", seed=seed, pool="B", condition=condition)
        for seed in (11, 29, 47)
        for condition in ("static", "delayed_c")
    ]
    tasks = [
        dict(
            task_id=f"synthetic-{index}",
            group=runner.statistics.GROUPS[index // 240],
            path=str(raw / "public-never-opened" / f"{index:04d}.json"),
        )
        for index in range(720)
    ]
    plan = p.record(
        "B_confirm_protocol",
        training_jobs=models,
        confirm_registry=[
            dict(task_id=row["task_id"], group=row["group"], source_cluster="cik:0000000001")
            for row in tasks
        ],
    )
    state = SimpleNamespace(
        root=root,
        raw=raw,
        plan=plan,
        models=models,
        now=1000,
        analyses=0,
        pushes=0,
        commits=0,
        gate_calls=0,
    )

    def analyze(registry, outcomes):
        assert len(registry) == 720
        assert len(outcomes) == 4320
        state.analyses += 1
        return dict(
            status="COMPLETE",
            point_estimate=0.0,
            ci95=dict(lower=0.0, upper=0.0, lower_rational="0/1", upper_rational="0/1"),
            positive_effect_confirmed=False,
        )

    def fake_git(command, **kwargs):
        assert command[0] == "git"
        assert kwargs["cwd"] == root
        if command[1:4] == ["diff", "--cached", "--quiet"]:
            return SimpleNamespace(returncode=0 if state.commits else 1)
        if command[1] == "commit":
            state.commits += 1
        if "push" in command:
            state.pushes += 1
            if state.pushes == 1:
                raise subprocess.CalledProcessError(1, command, stderr="synthetic push failure")
        return SimpleNamespace(returncode=0)

    def fake_head(command, **kwargs):
        assert command == ["git", "rev-parse", "HEAD"]
        assert kwargs["cwd"] == root
        return "synthetic-committed-result\n"

    def metadata_seal(*_):
        state.gate_calls += 1
        return {"id": "synthetic-global-generation-seal"}

    monkeypatch.setattr(runner.statistics, "analyze_confirmation", analyze)
    monkeypatch.setattr(runner, "time", SimpleNamespace(time=lambda: state.now))
    monkeypatch.setattr(runner, "subprocess", SimpleNamespace(run=fake_git, check_output=fake_head))
    monkeypatch.setattr(runner.views, "require_generation_seal", metadata_seal)

    def existing_final_report():
        # The report fast path must not open or analyze these score files again.
        for model in models:
            b.write(raw / "generation/confirm" / model["key"] / "scoring_report.json", {})
        report = p.record(
            "B_confirm_completed_study",
            protocol_id=plan["id"],
            status="COMPLETE_B_MAIN_CONFIRMATION",
            positive_effect_confirmed=False,
        )
        b.write(raw / "report.json", report)
        return report

    def complete_score_metadata():
        view = p.record("source_view_manifest_v2", protocol_id=plan["id"], tasks=tasks)
        b.write(raw / "confirm_views/manifest.json", view)
        for model in models:
            directory = raw / "generation/confirm" / model["key"]
            point = p.record(
                "anchored_model_parameter_point",
                run=model,
                step=400,
                source_manifest_id=view["id"],
            )
            b.write(raw / "points" / model["key"] / "point.json", point)
            jobs = [
                dict(index=index, task=task, repeat=0, seed=100 + index)
                for index, task in enumerate(tasks)
            ]
            trajectories = [
                p.record(
                    "anchored_generated_trajectory",
                    job=unit,
                    point_id=point["id"],
                    session_id=f"synthetic-session:{model['key']}:{unit['index']}",
                    actual_generate_calls=0,
                    private_assessment_performed=False,
                )
                for unit in jobs
            ]
            generated = p.record(
                "anchored_generation_manifest",
                complete=True,
                stochastic=False,
                point_id=point["id"],
                source_manifest_id=view["id"],
                tasks=tasks,
                trajectories=trajectories,
            )
            b.write(directory / "generation_manifest.json", generated)
            b.write(
                directory / "registration.json",
                p.record(
                    "B_generation_registration",
                    protocol_id=plan["id"],
                    point_id=point["id"],
                    source_manifest_id=view["id"],
                    seed=model["seed"],
                    condition=model["condition"],
                    stochastic=False,
                    jobs=jobs,
                ),
            )
            scores = [
                dict(
                    index=index,
                    task_id=task["task_id"],
                    group=task["group"],
                    repeat=0,
                    session_id=trajectories[index]["session_id"],
                    Q=index % 2,
                )
                for index, task in enumerate(tasks)
            ]
            b.write(
                directory / "scoring_report.json",
                p.record(
                    "anchored_independent_scoring",
                    complete=True,
                    generation_manifest_id=generated["id"],
                    point_id=point["id"],
                    source_manifest_id=view["id"],
                    denominator=720,
                    scores=scores,
                    qualified=360,
                    financial_rule_unchanged=True,
                    scoring_after_all_generation_complete=True,
                    confirm_tasks_opened=720,
                ),
            )
        b.write(raw / "budget/state.json", dict(counts=dict(optimizer=1800, generate_call=0)))

    state.existing_final_report = existing_final_report
    state.complete_score_metadata = complete_score_metadata
    return state


def test_existing_report_push_failure_is_pending_until_publication_retry_succeeds(completion):
    state = completion
    report = state.existing_final_report()
    assert runner.finish(state.root, state.plan) is False
    assert not (state.raw / "complete.json").exists()
    pending = p.read_json(state.raw / "publication.json")
    assert pending["status"] == "PUBLICATION_PENDING_NO_SCIENTIFIC_RETRY"
    assert pending["report_id"] == report["id"]
    assert state.analyses == state.gate_calls == 0
    assert state.commits == state.pushes == 1

    # Backoff cannot be bypassed by a coordinator restart.
    assert runner.finish(state.root, state.plan) is False
    assert state.pushes == 1
    state.now += 301
    assert runner.finish(state.root, state.plan) is True
    assert p.read_json(state.raw / "complete.json") == report
    assert p.read_json(state.raw / "publication.json")["status"] == "PUBLISHED"
    assert state.commits == 1  # Existing identical public JSON/doc are reused.
    assert state.pushes == 2
    assert state.analyses == 0
    assert runner.finish(state.root, state.plan) is True
    assert state.pushes == 2


def test_publication_retry_never_repeats_completed_statistical_analysis(completion):
    state = completion
    state.complete_score_metadata()
    assert runner.finish(state.root, state.plan) is False
    assert state.analyses == 1
    report = p.read_json(state.raw / "report.json")
    analysis = (state.raw / "confirmation_analysis.json").read_bytes()
    assert not (state.raw / "complete.json").exists()
    state.now += 301
    assert runner.finish(state.root, state.plan) is True
    assert state.analyses == 1
    assert (state.raw / "confirmation_analysis.json").read_bytes() == analysis
    assert p.read_json(state.raw / "report.json") == report


def test_other_models_valid_score_report_in_wrong_directory_is_rejected(completion):
    state = completion
    state.complete_score_metadata()
    first, other = state.models[:2]
    base = state.raw / "generation/confirm"
    wrong = p.read_json(base / other["key"] / "scoring_report.json")
    p.checked(wrong, "anchored_independent_scoring")  # Legitimate hash, wrong origin.
    b.write(base / first["key"] / "scoring_report.json", wrong, immutable=False)
    with pytest.raises(ValueError, match="complete_report_exact_generation_binding"):
        runner.finish(state.root, state.plan)
    assert state.analyses == state.pushes == state.commits == 0
    assert not (state.raw / "confirmation_analysis.json").exists()
    assert not (state.raw / "report.json").exists()
    assert not (state.raw / "complete.json").exists()
