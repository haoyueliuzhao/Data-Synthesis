"""Bounded R2 controller controls; no actual model or device is loaded."""

from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import calibration_v2 as c
from trusted_synthesis.finance_research.contracts import ModelIdentity


def test_fixed_matrix_has_original_120_tasks_and_7920_H_calls():
    tasks = [f"finqa/task-{n}" for n in range(120)]
    jobs = c.build_jobs(tasks)
    assert len(jobs) == 16
    assert sum(len(j["task_keys"]) for j in jobs) == 480
    assert sum(len(j["task_keys"]) * j["config"]["max_steps"] for j in jobs) == 7920
    for model in ("base", "static11_step240"):
        for harness in ("H1-R", "Direct-DSL"):
            cohort = [j for j in jobs if j["model"] == model and j["harness"] == harness]
            assert [k for j in cohort for k in j["task_keys"]] == tasks
            assert all(j["config"]["temperature"] == 0 for j in cohort)
            assert all(j["config"]["submission_profile"] == "finqa_program_v2" for j in cohort)
            assert all(j["config"]["max_new_tokens"] == 2048 for j in cohort)
    with pytest.raises(ValueError):
        c.build_jobs(tasks[:-1] + [tasks[0]])


@pytest.mark.parametrize("tag", ["failure", "error", "skipped"])
def test_r2_admission_never_accepts_failed_or_skipped_actual_template_controls(tmp_path, tag):
    report = tmp_path / "cpu.xml"
    report.write_text(
        f'<testsuite><testcase classname="test_finance_research_r2"><{tag}/></testcase></testsuite>'
    )
    with pytest.raises(ValueError, match="no failure/error/skip"):
        c.cpu_admission(report)


def test_worker_direct_shard_and_durable_records(tmp_path, monkeypatch):
    job = c.build_jobs([f"finqa/{n}" for n in range(120)])[0]
    assert job["harness"] == "Direct-DSL"
    plan = dict(jobs=[job], snapshot="fixture", role_plan={})
    c.publish(tmp_path / "gate_complete", {"eval_native_passed": True})
    monkeypatch.setattr(c, "checked_plan", lambda _: plan)
    monkeypatch.setattr(c, "identity", lambda _: "fixture-birth")
    provider = SimpleNamespace(identity=ModelIdentity(backend="scripted", model_id="fixture"))
    monkeypatch.setattr(c, "load_provider", lambda *_: provider)
    prepared = []
    monkeypatch.setattr(c, "prepare_run", lambda *args, **kwargs: prepared.append(kwargs))

    async def execute(directory, actual_provider):
        assert actual_provider is provider
        return {"id": "fixture-seal"}

    monkeypatch.setattr(c, "execute_run", execute)
    assert c.worker(tmp_path, job["key"], 1, "GPU-fixture") == 0
    assert prepared[0]["config"].max_steps == 1
    assert len(prepared[0]["task_keys"]) == 30
    row = c.read_json(tmp_path / "jobs" / job["key"] / "attempts/01/outcome/record.json")
    assert row["status"] == "COMPLETE"


@pytest.mark.parametrize("active_last_worker", [True, False])
def test_all_480_and_last_worker_exit_precede_any_private_score(
    tmp_path, monkeypatch, active_last_worker
):
    jobs = c.build_jobs([f"finqa/{n}" for n in range(120)])
    plan = dict(id="fixture", jobs=jobs, maximum_GPU_workers=4)
    c.publish(tmp_path / "gate_complete", {"eval_native_passed": True})
    monkeypatch.setattr(c, "checked_plan", lambda _: plan)

    def latest(_, key):
        return dict(
            alive=active_last_worker and key == jobs[-1]["key"],
            process={"gpu": "GPU-fixture"},
            outcome={"status": "COMPLETE"},
        )

    monkeypatch.setattr(c, "latest", latest)
    monkeypatch.setattr(c, "gpu_inventory", lambda: [])
    monkeypatch.setattr(c, "status", lambda *_: None)
    finished = []
    monkeypatch.setattr(c, "finish", lambda *_: finished.append(True))

    class StopLoop(Exception):
        pass

    monkeypatch.setattr(c.time, "sleep", lambda _: (_ for _ in ()).throw(StopLoop()))
    if active_last_worker:
        with pytest.raises(StopLoop):
            c.coordinate(tmp_path)
        assert finished == []
    else:
        c.coordinate(tmp_path)
        assert finished == [True]
