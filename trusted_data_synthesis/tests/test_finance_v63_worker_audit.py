"""CPU metadata/failure controls; no Tensor load, GPU, model, API or old writes."""
from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import finqa_v63_worker_audit as audit

import pytest
import torch
from test_finance_research_providers import Model, Tokenizer, feedback_config
from trusted_synthesis.finance_research.providers import local_model_identity


def rewrite(path, value):
    value = {k: v for k, v in value.items() if k != "id"}
    value["id"] = audit.digest(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(audit.binding, "ROOT", tmp_path)
    monkeypatch.setattr(audit.training, "ROOT", tmp_path)
    for name in ("V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR", "V56_JOB_ATTEMPT_ROOT",
                 "V63_ATTEMPT_ID", "V56_ATTEMPT_ID"):
        monkeypatch.delenv(name, raising=False)
    protocol = rewrite(tmp_path / "protocol/record.json", {"schema": "test-registered"})
    parent = rewrite(tmp_path / "parents/seed137/record.json", dict(
        schema="v63_inherited_complete_parent.v1", protocol_id=protocol["id"],
        seed=137, feedback_batch=1, point_id="fixed-point", parent_state_digest="parent",
        pool_id="fixed-pool", new_class_task_count=0))
    monkeypatch.setattr(audit.training, "checked_parent", lambda root, seed: parent)
    model, tokenizer = Model(), Tokenizer()
    identity = local_model_identity(model, tokenizer, model_id="cpu-fixture", point_id="fixed-point")
    condition = audit.temperature.build_condition(
        identity=identity, temperature=1.0, arm="C1", batch=1,
        configs=[feedback_config(temperature=1.0, seed=seed) for seed in (101, 103)],
        task_roster=[dict(dataset="finqa", task_id=f"q{i}") for i in range(350)],
        source_manifest_sha256="a" * 64, role_plan_id="role")
    condition_path = tmp_path / f"stages/seed137/feedback_C1/feedback/{condition['id']}/intent/record.json"
    rewrite(condition_path, condition)
    return SimpleNamespace(root=tmp_path, protocol=protocol, parent=parent,
                           condition=condition, condition_path=condition_path)


def job(phase="replay"):
    return dict(job_id=f"seed137.{phase}_C1", stage=f"{phase}_C1",
                seed=137, arm="C1", kind=phase)


def checkpoint(e):
    order = [[0, 0, "call0"], [350, 0, "call1"], [351, 0, "call2"]]
    point = dict(
        point_id="fixed-point", parameter_digest=e.condition["identity"]["parameter_digest"],
        denominator=700, response_count=3, response_order=order,
        response_order_sha256=audit.digest(order), gradient_length_normalized=False,
        block_size=8, checkpoint_every_responses=16,
        replay_state_adapter=audit.temperature.BACKEND_VERSION,
        backend_identity=dict(
            backend_version=audit.temperature.BACKEND_VERSION,
            feedback_condition_id=e.condition["id"], temperature=1.0, arm="C1",
            feedback_batch=1, draw_seeds=[101, 103],
            draw_component_version=audit.temperature.components.VERSION,
            mean_tolerances=audit.temperature.MEAN_TOLERANCES))
    directory = e.root / "stages/seed137/replay_C1/checkpoints/response000002"
    directory.mkdir(parents=True)
    (directory / "state.pt").write_bytes(b"metadata-only-placeholder-not-deserialized")
    value = rewrite(directory / "record.json", dict(
        schema="v19_response_boundary_checkpoint.v1", cursor=2, binding=point,
        response_prefix_complete=True, full_replay_complete=False, state_sha256="c" * 64,
        formal_and_draws_atomically_committed=True,
        draw_components_schema=audit.temperature.components.VERSION,
        draw_response_counts={"101": 1, "103": 1}))
    return directory / "record.json", value


def test_joint_replay_admission_reads_only_metadata_not_tensor(environment, monkeypatch):
    e = environment
    checkpoint(e)
    original_sha = audit.binding.sha

    def sha(path):
        assert Path(path).suffix != ".pt"
        return original_sha(path)

    monkeypatch.setattr(audit.binding, "sha", sha)
    monkeypatch.setattr(torch, "load", lambda *a, **k: pytest.fail("Tensor load in admission"))
    result = audit.audit_job_resume(e.root, job())
    assert result["resume_allowed"] and result["progress_units"] == 2
    assert result["details"]["persisted_response_prefix"] == 2
    assert result["full_tensor_validation_before_cold_scientific_use"]


@pytest.mark.parametrize("field,value", [
    ("formal_and_draws_atomically_committed", False),
    ("draw_components_schema", "old-formal-only"),
    ("draw_response_counts", {"101": 2, "103": 0}),
    ("full_replay_complete", True),
])
def test_joint_checkpoint_missing_or_mismatched_draw_proof_blocks(environment, field, value):
    path, row = checkpoint(environment)
    rewrite(path, {**row, field: value})
    with pytest.raises(ValueError, match="checkpoint|draw counts"):
        audit.audit_job_resume(environment.root, job())


def test_feedback_condition_gate_precedes_durable_unknown_audit(environment, monkeypatch):
    e = environment
    changed = copy.deepcopy(e.condition)
    changed["feedback_batch"] = 0
    rewrite(e.condition_path, changed)
    monkeypatch.setattr(audit.durable, "audit_resume", lambda *a, **k: pytest.fail("must reject condition first"))
    with pytest.raises(ValueError):
        audit.audit_job_resume(e.root, job("feedback"))


def test_feedback_audit_has_no_inherited_quota_and_unknown_stays_blocked(environment, monkeypatch):
    calls = []

    def unknown(directory, *, inheritance):
        calls.append(inheritance)
        return dict(evidence=[], progress_units=4, unknown_calls=1, resume_allowed=False,
                    durable_progress_digest="actual-prefix")

    monkeypatch.setattr(audit.durable, "audit_resume", unknown)
    result = audit.audit_job_resume(environment.root, job("feedback"))
    assert calls == [None]
    assert result["unknown_calls"] == 1 and not result["resume_allowed"]


def test_new_C1_training_metadata_does_not_allow_old_C1_or_outer(environment, monkeypatch):
    e = environment
    base = e.root / "branches/seed137/C1"
    rewrite(base / "binding/record.json", dict(
        schema="v63_fixed_q_training_binding.v1", protocol_id=e.protocol["id"],
        parent_id=e.parent["id"], parent_state_digest="parent", seed=137, arm="C1",
        feedback_batch=1, temperature=1.0, start_step=596, end_step=894,
        outer_schedule_during_window=[], real_parent_not_theta_bar=True))
    directory = base / "training/step0600_step"
    directory.mkdir(parents=True)
    (directory / "state.pt").write_bytes(b"actual-state-placeholder")
    (directory / "record.json").write_text(json.dumps(dict(
        seed=137, arm="C-only", step=600, phase="step", pool_id="fixed-pool",
        checkpoint_contains_actual_model_Adam_RNG_pi=True, state_sha256="c" * 64)))
    monkeypatch.setattr(torch, "load", lambda *a, **k: pytest.fail("no Tensor admission"))
    result = audit.audit_job_resume(e.root, job("train"))
    assert result["progress_units"] == 4
    (base / "training/step0596_outer").mkdir()
    with pytest.raises(ValueError, match="unexpected outer"):
        audit.audit_job_resume(e.root, job("train"))


def failure_attempt(e, *, error_type="ResourceDeferred", resources=None, code=1,
                    actual_errno=None, module="finqa_v63_runtime", hard=False):
    task = job()
    path = e.root / "stages/seed137/replay_C1/attempts/attempt0001"
    rewrite(path / "launch/record.json", dict(
        protocol_id=e.protocol["id"], job=task, pid=12345, birth="birth", attempt=1))
    rewrite(path / "actual_exit/record.json", dict(
        protocol_id=e.protocol["id"], job_id=task["job_id"], pid=12345, birth="birth",
        attempt=1, actual_waitpid_observed=True, returncode=code))
    failure = rewrite(path / "failure/record.json", dict(
        schema="v63_actual_attempt_failure.v1", protocol_id=e.protocol["id"],
        feedback_batch=1, attempt_root=str(path), pid=12345, job=task,
        exception_type=error_type, resources=resources or {}, resource_closeout=None,
        exception_chain=[dict(type=error_type, module=module, message="fixture actual error",
                              actual_errno=actual_errno,
                              automatic_recovery_allowed=False if hard else None)]))
    return path, failure


def test_safe_resource_requires_exact_actual_waitpid_and_no_unknown(environment):
    e = environment
    path, _ = failure_attempt(e, resources={"deferred_observation": {"actual_shortage": True}})
    value = audit.classify_attempt(e.root, job(), path, 1)
    assert value["classification"] == "RETRY_SAFE_RESOURCE" and value["resume_allowed"]
    (path / "actual_exit/record.json").unlink()
    blocked = audit.classify_attempt(e.root, job(), path, 1)
    assert blocked["classification"] == "HARD_BLOCK" and not blocked["resume_allowed"]


@pytest.mark.parametrize("error_type,module,hard", [
    ("DrawDiagnosticError", "finqa_v63_draw_components", True),
    ("GenerationUnknown", "finqa_v56_feedback", True),
    ("ModuleNotFoundError", "builtins", False),
    ("ValueError", "builtins", False),
])
def test_diagnostic_binding_and_implementation_errors_never_become_resource_retry(
        environment, error_type, module, hard):
    e = environment
    path, _ = failure_attempt(e, error_type=error_type, module=module, hard=hard,
                              resources={"deferred_observation": {"old_shortage": True}})
    result = audit.classify_attempt(e.root, job(), path, 1)
    assert result["classification"] == "HARD_BLOCK" and not result["resume_allowed"]


def test_actual_io_errno_can_retry_but_signal_and_historical_peak_cannot(environment):
    e = environment
    path, failure = failure_attempt(e, error_type="OSError", module="builtins", actual_errno=errno.EIO)
    result = audit.classify_attempt(e.root, job(), path, 1)
    assert result["classification"] == "RETRY_SAFE_IO" and result["actual_errno"] == errno.EIO
    actual = audit.checked(path / "actual_exit/record.json")
    rewrite(path / "actual_exit/record.json", {**actual, "returncode": -9})
    assert audit.classify_attempt(e.root, job(), path, -9)["classification"] == "EXPLICIT_STOP"
    rewrite(path / "actual_exit/record.json", {**actual, "returncode": 1})
    rewrite(path / "failure/record.json", {**failure, "resources": {
        "peak_allocated_bytes": 77 * audit.GIB, "deferred_observation": {"shortage": True}}})
    result = audit.classify_attempt(e.root, job(), path, 1)
    assert result["classification"] == "HARD_BLOCK"


def test_temporary_audit_io_defers_without_scientific_retry(environment, monkeypatch):
    e = environment
    path, _ = failure_attempt(e)

    def unavailable(*args):
        raise OSError(errno.ESTALE, "saved evidence temporarily unreadable")

    monkeypatch.setattr(audit, "audit_job_resume", unavailable)
    result = audit.classify_attempt(e.root, job(), path, 1)
    assert result["classification"] == "AUDIT_IO_WAIT"
    assert result["resume_allowed"] is False


def test_attempt_aliases_must_identify_same_independent_attempt(environment, monkeypatch):
    e = environment
    path = e.root / "stages/seed137/replay_C1/attempts/attempt0001"
    for name in ("V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR"):
        monkeypatch.setenv(name, str(path))
    for name in ("V63_ATTEMPT_ID", "V56_ATTEMPT_ID"):
        monkeypatch.setenv(name, path.name)
    assert audit.checked_attempt_directory(e.root, job(), path) == path
    monkeypatch.setenv("V56_ATTEMPT_ID", "attempt0002")
    with pytest.raises(ValueError, match="ID aliases"):
        audit.checked_attempt_directory(e.root, job(), path)


def test_record_failure_retains_diagnostic_hard_block_marker(environment):
    e = environment
    path = e.root / "stages/seed137/replay_C1/attempts/attempt0001"
    error = audit.temperature.components.DrawDiagnosticError("draw mean differs")
    result = audit.record_attempt_failure(e.root, job(), path, error)
    assert result["schema"] == "v63_actual_attempt_failure.v1"
    assert result["exception_chain"][0]["automatic_recovery_allowed"] is False
    assert result["automatic_retry_in_worker"] is False
    assert result["CUDA_initialized"] is False


def test_CPU_finalization_binds_actual_payload_and_original_resources(environment, monkeypatch):
    e = environment
    task = job("distribution")
    directory = e.root / "stages/seed137/distribution_C1"
    state = b"actual-complete-payload-fixture"
    payload_directory = directory / "payload"
    payload_directory.mkdir(parents=True)
    (payload_directory / "state.pt").write_bytes(state)
    payload = rewrite(payload_directory / "record.json", dict(
        schema="v63_actual_scientific_payload.v1", parent_id=e.parent["id"],
        parent_state_digest="parent", stage="distribution_C1", feedback_batch=1,
        arm="C1", temperature=1.0, actual_tensors_saved=True, state_bytes=len(state),
        state_sha256=hashlib.sha256(state).hexdigest(), state_digest="semantic"))
    resource_dir = e.root / "resources/seed137.distribution_C1/pid12345"
    resources = dict(all_gates_passed=True, single_process_lifetime_includes_loading=True,
                     observations_path=str(resource_dir / "observations.jsonl"))
    rewrite(resource_dir / "closeout/record.json", dict(
        status="COMPLETE", protocol_id=e.protocol["id"], job_id=task["job_id"],
        pid=12345, resources=resources))
    result = rewrite(directory / "result/record.json", dict(
        status="COMPLETE", protocol_id=e.protocol["id"], seed=137, stage="distribution_C1",
        arm="C1", temperature=1.0, feedback_batch=1, condition_id=e.condition["id"],
        payload=audit.binding.entry(payload_directory / "record.json"), resources=resources))
    attempt = directory / "attempts/attempt0002"
    monkeypatch.setattr(torch, "load", lambda *a, **k: pytest.fail("CPU finalization does not deserialize"))
    actual = audit.reuse_complete_result(e.root, task, attempt)
    assert actual == result
    proof = audit.checked(attempt / "reused_result/record.json")
    assert proof["scientific_calls"] == 0 and proof["verified_durable_result"]
    assert proof["source_resource_closeout"]["path"] == str(resource_dir / "closeout/record.json")
    (payload_directory / "state.pt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="size differs|bytes changed"):
        audit.reuse_complete_result(e.root, task, directory / "attempts/attempt0003")
