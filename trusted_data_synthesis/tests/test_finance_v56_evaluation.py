from types import SimpleNamespace

import pytest

import finqa_v54_evaluation as evaluation


def test_automatic_evaluation_records_structured_failure_in_dispatched_attempt(tmp_path, monkeypatch):
    key, job = next(iter(evaluation.planned_jobs().items()))
    attempt = evaluation.job_root(tmp_path, job) / "attempts/attempt0001"
    monkeypatch.setenv("V56_ATTEMPT_ID", "attempt0001")
    monkeypatch.setenv("V56_ATTEMPT_DIR", str(attempt))
    monkeypatch.setattr(evaluation, "_protocol", lambda root: dict(auto_recovery_policy={}))
    observed = []
    original_import = evaluation.importlib.import_module
    monkeypatch.setattr(evaluation.importlib, "import_module", lambda name: SimpleNamespace(
        record_attempt_failure=lambda *args: observed.append(args)) if name == "finqa_v56_worker" else original_import(name))
    def fail(*args, **kwargs):
        raise ValueError("actual UNKNOWN")
    monkeypatch.setattr(evaluation, "_worker", fail)
    with pytest.raises(ValueError, match="UNKNOWN"):
        evaluation.worker(tmp_path, key, 0)
    assert observed[0][0] == tmp_path and observed[0][1]["job_id"] == key
    assert observed[0][2] == attempt and isinstance(observed[0][3], ValueError)


def test_returned_evaluation_turn_is_durable_before_post_response_resource_gate(tmp_path, monkeypatch):
    key, job = next(iter(evaluation.planned_jobs().items()))
    job = dict(job, checkpoint={})
    root = evaluation.job_root(tmp_path, job)
    root.mkdir(parents=True)
    persisted = []
    observations = []
    class Deferred(RuntimeError):
        pass
    class Guard:
        stop = SimpleNamespace(requested=False)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def check(self, label, **kwargs):
            observations.append(label)
            if label == "after_durable_evaluation_response":
                assert persisted == ["actual returned turn"]
                raise Deferred("capacity changed after durable return")
    class Provider:
        actual_model_calls = 0
        async def chat(self):
            self.actual_model_calls += 1
            return "actual returned turn"
    async def runner(run_root, provider, *, attempt_root, stop_check, after_return):
        stopped = stop_check()
        assert stopped is None
        value = await provider.chat()
        persisted.append(value)
        after_return({"phase": "after_durable_response"})
    final = SimpleNamespace(load_final_provider=lambda *args: Provider(),
        torch=SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda: None)))
    monkeypatch.setattr(evaluation, "checked_plan", lambda root: dict(jobs={key: job}, assets={}))
    monkeypatch.setattr(evaluation, "_runtime", lambda: final)
    monkeypatch.setattr(evaluation, "_snapshot_state", lambda *args: {})
    original_import = evaluation.importlib.import_module
    modules = dict(finqa_v56_worker=SimpleNamespace(audit_job_resume=lambda *args: dict(resume_allowed=True, unknown_calls=0)),
        finqa_v56_runtime=SimpleNamespace(ExplicitStop=RuntimeError),
        finqa_v56_feedback=SimpleNamespace(execute_run_resumable=runner))
    monkeypatch.setattr(evaluation.importlib, "import_module", lambda name: modules[name] if name in modules else original_import(name))
    with pytest.raises(Deferred, match="durable return"):
        evaluation._worker(tmp_path, key, 0, attempt_root=root / "attempts/attempt0001",
                           execution_context=lambda *args: Guard())
    assert "after_evaluation_response" not in observations
    assert observations[-1] == "after_durable_evaluation_response"
