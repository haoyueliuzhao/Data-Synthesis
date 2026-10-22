"""Generate-only admission, UNKNOWN, real-exit disposition and reuse controls."""
from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

import finqa_v65_binding as binding
import finqa_v65_evaluation as evaluation
import finqa_v65_worker as worker
from test_finance_v65_evaluation import prepared_fixture, rewrite


@pytest.fixture
def environment(tmp_path, monkeypatch):
    e, plan, _, _ = prepared_fixture(tmp_path, monkeypatch)
    for name in ("V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR", "V56_JOB_ATTEMPT_ROOT", "V65_ATTEMPT_DIR",
                 "V63_ATTEMPT_ID", "V56_ATTEMPT_ID", "V65_ATTEMPT_ID"):
        monkeypatch.delenv(name, raising=False)
    e.plan = plan
    e.job = dict(next(iter(plan["jobs"].values())), kind="generate")
    e.directory = evaluation.job_root(e.root, e.job)
    e.directory.mkdir(parents=True, exist_ok=True)
    e.attempt = e.directory / "attempts/attempt0001"
    monkeypatch.setattr(worker.original.durable, "audit_resume", lambda *_args, **kwargs: dict(
        evidence=[], progress_units=3, unknown_calls=0, resume_allowed=True, durable_progress_digest="saved-prefix"))
    return e


def failure_attempt(e, *, code=1, unknown=False, error_type="ResourceDeferred", actual_errno=None, hard=False):
    rewrite(e.attempt / "launch/record.json", dict(protocol_id=e.protocol["id"], job=e.job,
        pid=123, birth="same-birth", attempt=1))
    rewrite(e.attempt / "actual_exit/record.json", dict(protocol_id=e.protocol["id"], job_id=e.job["job_id"],
        pid=123, birth="same-birth", attempt=1, actual_waitpid_observed=True, returncode=code))
    failure = rewrite(e.attempt / "failure/record.json", dict(schema="v63_actual_attempt_failure.v1",
        protocol_id=e.protocol["id"], feedback_batch=1, attempt_root=str(e.attempt), pid=123, job=e.job,
        exception_type=error_type, resources={"deferred_observation": {"shortage": True}}, resource_closeout=None,
        exception_chain=[dict(type=error_type, module="builtins", actual_errno=actual_errno,
                             automatic_recovery_allowed=False if hard else None)]))
    return failure


def test_only_exact_twenty_generation_jobs_are_admitted(environment):
    e = environment
    assert worker._job_directory(e.root, e.job) == e.directory
    for job in ({**e.job, "stage": "train_C1"}, {**e.job, "seed": 389, "arm": "C05"},
                {**e.job, "denominator": 1}, {**e.job, "config": {}}):
        with pytest.raises(ValueError):
            worker.audit_job_resume(e.root, job)
    with pytest.raises(ValueError, match="scientific root"):
        worker.audit_job_resume(e.science, e.job)


def test_unknown_call_is_never_given_reexecution_quota(environment, monkeypatch):
    e = environment
    inherited = []

    def audit(_root, *, inheritance):
        inherited.append(inheritance)
        return dict(evidence=[], progress_units=3, unknown_calls=1, resume_allowed=False,
                    durable_progress_digest="actual-returned-prefix-plus-unknown")

    monkeypatch.setattr(worker.original.durable, "audit_resume", audit)
    result = worker.audit_job_resume(e.root, e.job)
    assert result["unknown_calls"] == 1 and not result["resume_allowed"] and inherited == [None]
    failure_attempt(e)
    verdict = worker.classify_attempt(e.root, e.job, e.attempt, 1)
    assert verdict["classification"] == "HARD_BLOCK" and not verdict["resume_allowed"]
    assert "UNKNOWN" in verdict["reason"]


def test_resource_recovery_requires_this_actual_waitpid_and_settled_state(environment):
    e = environment
    failure_attempt(e)
    result = worker.classify_attempt(e.root, e.job, e.attempt, 1)
    assert result["classification"] == "RETRY_SAFE_RESOURCE" and result["resume_allowed"]
    assert result["durable_progress_digest"] == "saved-prefix"
    (e.attempt / "actual_exit/record.json").unlink()
    result = worker.classify_attempt(e.root, e.job, e.attempt, 1)
    assert result["classification"] == "HARD_BLOCK" and not result["resume_allowed"]


@pytest.mark.parametrize("kind,code,expected", [
    ("GenerationUnknown", 1, "HARD_BLOCK"), ("GenerationBindingError", 1, "HARD_BLOCK"),
    ("DrawDiagnosticError", 1, "HARD_BLOCK"), ("ValueError", 1, "HARD_BLOCK"),
    ("ExplicitStop", 1, "EXPLICIT_STOP"), ("ResourceDeferred", -9, "EXPLICIT_STOP")])
def test_unknown_numeric_binding_and_stop_never_become_resource_retry(environment, kind, code, expected):
    e = environment
    failure_attempt(e, error_type=kind, code=code)
    result = worker.classify_attempt(e.root, e.job, e.attempt, code)
    assert result["classification"] == expected and not result["resume_allowed"]


def test_attempt_aliases_and_failure_record_preserve_new_control_identity(environment, monkeypatch):
    e = environment
    monkeypatch.setenv("V63_ATTEMPT_DIR", str(e.attempt))
    monkeypatch.setenv("V63_ATTEMPT_ID", "attempt0001")
    monkeypatch.setenv("V65_ATTEMPT_DIR", str(e.attempt.parent / "attempt0002"))
    with pytest.raises(ValueError, match="aliases disagree"):
        worker.checked_attempt_directory(e.root, e.job, e.attempt)
    monkeypatch.setenv("V65_ATTEMPT_DIR", str(e.attempt))
    row = worker.record_attempt_failure(e.root, e.job, e.attempt, OSError(errno.EIO, "actual IO fixture"))
    assert row["protocol_id"] == e.protocol["id"] != e.scientific["id"]
    assert row["pid"] == os.getpid() and row["exception_chain"][0]["actual_errno"] == errno.EIO
    assert not row["automatic_retry_in_worker"]


def complete_result(e):
    resource_dir = e.root / "resources" / e.job["job_id"] / "pid123"
    resources = dict(all_gates_passed=True, single_process_lifetime_includes_loading=True,
                     observations_path=str(resource_dir / "observations.jsonl"))
    rewrite(resource_dir / "closeout/record.json", dict(status="COMPLETE", resources=resources,
        protocol_id=e.protocol["id"], job_id=e.job["job_id"]))
    seal = rewrite(e.directory / "whole_queue_seal/record.json", dict(
        registration_id=e.plan["id"], job_id=e.job["job_id"], feedback_batch=1,
        all_provider_calls_settled=True))
    return rewrite(e.directory / "result/record.json", dict(schema="v65_generation_only_job_result.v1",
        scientific_protocol_id=e.scientific["id"], registration_id=e.plan["id"], job_id=e.job["job_id"],
        status="COMPLETE", feedback_batch=1, resources=resources, sessions=e.job["denominator"],
        scoring_calls=0, private_references_read=False, whole_queue_seal_id=seal["id"],
        whole_queue_seal=binding.file_ref(e.directory / "whole_queue_seal/record.json")))


def test_complete_generation_is_cpu_finalized_without_new_calls(environment):
    e = environment
    saved = complete_result(e)
    result = worker.reuse_complete_result(e.root, e.job, e.attempt)
    assert result == saved
    reuse = binding.checked(e.attempt / "reused_result/record.json")
    assert reuse["protocol_id"] == e.protocol["id"] and reuse["scientific_calls"] == 0
    assert reuse["original_scientific_result_rewritten"] is False
    assert binding.checked(e.directory / "result/record.json") == saved


def test_complete_result_cannot_smuggle_scoring_or_scientific_payload(environment):
    e = environment
    saved = complete_result(e)
    rewrite(e.directory / "result/record.json", {**saved, "payload": {"path": "/forbidden"}})
    with pytest.raises(ValueError, match="generation only"):
        worker.audit_job_resume(e.root, e.job)
    rewrite(e.directory / "result/record.json", {**saved, "scoring_calls": 1})
    with pytest.raises(ValueError, match="complete generation"):
        worker.audit_job_resume(e.root, e.job)


def test_native_failure_disposition_bytecode_is_unchanged():
    for name in ("classify_attempt", "_exception_chain", "record_attempt_failure", "reuse_complete_result"):
        assert worker._adapted[name].__code__ is getattr(worker.original, name).__code__
