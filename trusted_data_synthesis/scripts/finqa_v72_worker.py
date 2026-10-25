"""Cold V72 execution and read-only, same-state durable recovery admission.

No previous UNKNOWN replay allowance or numerical diagnostic exception is
inherited. Metadata admission never loads Tensor payloads; cold science checks
their complete bytes and semantic identities before using them.
"""
from __future__ import annotations

import fcntl
import importlib
import json
import os
from pathlib import Path
import re
import time
from types import FunctionType, SimpleNamespace

import finqa_v72_binding as binding
import finqa_v72_queue_base as queue

original = binding.source_module("finqa_v63_worker_audit")
durable = original.durable
require, checked = binding.require, binding.checked


def _job_id(job):
    value = job.get("job_id", job.get("id"))
    require(isinstance(value, str) and value and "/" not in value and "\\" not in value,
            "registered scalar V72 job ID required")
    return value


def _job_directory(root, job):
    key = _job_id(job)
    roster = queue.all_jobs()
    require(key in roster and all(job.get(field) == value for field, value in roster[key].items()
            if field not in ("dependencies", "priority")), "scientific job differs from fixed V72 roster")
    return queue.job_directory(root, job)


def checked_attempt_directory(root, job, attempt_dir=None):
    aliases = [os.environ.get(name) for name in
               ("V72_ATTEMPT_DIR", "V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR", "V56_JOB_ATTEMPT_ROOT")]
    supplied = [Path(value).resolve() for value in [attempt_dir, *aliases] if value is not None]
    require(supplied and all(path == supplied[0] for path in supplied), "durable attempt aliases disagree")
    path = supplied[0]
    require(path.parent == _job_directory(root, job) / "attempts"
            and re.fullmatch(r"attempt[0-9]{4,}", path.name) is not None,
            "V72 attempt escaped its immutable per-job dispatch directory")
    require(all(os.environ.get(name) in (None, path.name)
                for name in ("V72_ATTEMPT_ID", "V63_ATTEMPT_ID", "V56_ATTEMPT_ID")),
            "actual attempt identifiers differ")
    return path


def audit_job_resume(root, job):
    _job_directory(root, job)
    if job["kind"] == "generate":
        return importlib.import_module("finqa_v72_evaluation").audit_job_resume(root, job)
    return importlib.import_module("finqa_v72_training").audit_training_resume(root, job)


def validate_result(root, job, result):
    protocol = checked(Path(root) / "protocol/record.json")
    require(result["status"] == "COMPLETE" and result["protocol_id"] == protocol["id"]
            and result["job_id"] == job["job_id"] and result["seed"] == 137
            and result["step"] == job["step"] and result["stage"] == job["stage"]
            and result["model_released"] is True and result["resources"]["all_gates_passed"] is True,
            "complete result coordinate or resource contract changed")
    if job["kind"] == "generate":
        require(result["schema"] == "v72_generation_job_result.v1"
                and result["sessions"] == job["denominator"] and result["scoring_calls"] == 0
                and result["private_references_read"] is False, "evaluation dose/separation changed")
        binding.read_ref(result["whole_queue_seal"])
    else:
        require(result["schema"] == "v72_scientific_stage_result.v1" and job["stage"] == "train",
                "only fixed-distribution training is registered")
        importlib.import_module("finqa_v72_training").validate_training_result(root, job, result)


def _validate_complete_result(root, job, protocol, **_kwargs):
    require(protocol["id"] == checked(Path(root) / "protocol/record.json")["id"], "protocol changed")
    return validate_result(root, job, checked(_job_directory(root, job) / "result/record.json"))


def _private_disposition():
    proxy = SimpleNamespace(**vars(binding), BATCH=1)
    namespace = dict(vars(original), binding=proxy, _job_id=_job_id,
        _job_directory=_job_directory, checked_attempt_directory=checked_attempt_directory,
        audit_job_resume=audit_job_resume, _validate_complete_result=_validate_complete_result)
    for name in ("_exception_chain", "record_attempt_failure", "classify_attempt", "reuse_complete_result"):
        function = getattr(original, name)
        namespace[name] = FunctionType(function.__code__, namespace, function.__name__,
                                      function.__defaults__, function.__closure__)
        namespace[name].__kwdefaults__ = function.__kwdefaults__
    return namespace


_disposition = _private_disposition()
record_attempt_failure = _disposition["record_attempt_failure"]
classify_attempt = _disposition["classify_attempt"]
reuse_complete_result = _disposition["reuse_complete_result"]


def prepare_point_for_job(root, job, guard):
    if job["kind"] != "train":
        return
    protocol = checked(Path(root) / "protocol/record.json")
    guard.check("before_fixed_window_CPU_registration", boundary=True)
    importlib.import_module("finqa_v72_training").prepare_window(root, job["step"], protocol["id"])
    guard.check("after_fixed_window_CPU_registration", boundary=True)


def run(root, job, gpu_index, *, attempt_root):
    import finqa_v72_resources as resources
    directory = _job_directory(root, job)
    directory.mkdir(parents=True, exist_ok=True)
    protocol = checked(Path(root) / "protocol/record.json")
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt = checked_attempt_directory(root, job, attempt_root)
        started = time.time()
        binding.publish(attempt / "started/record.json", dict(schema="v72_actual_worker_started.v1",
            protocol_id=protocol["id"], job=job, gpu_index=gpu_index, pid=os.getpid(),
            started_epoch=started, automatic_retry_in_worker=False))
        guard = None
        try:
            if (directory / "result/record.json").exists():
                return reuse_complete_result(root, job, attempt)
            with resources.execution_context(root, job, gpu_index) as guard:
                prepare_point_for_job(root, job, guard)
                if job["kind"] == "generate":
                    body = importlib.import_module("finqa_v72_evaluation").run(
                        root, job, gpu_index, attempt, guard)
                else:
                    body = importlib.import_module("finqa_v72_runtime").execute(root, job, attempt, guard)
            result = binding.publish(directory / "result/record.json", dict(body,
                schema="v72_generation_job_result.v1" if job["kind"] == "generate"
                       else "v72_scientific_stage_result.v1",
                status="COMPLETE", protocol_id=protocol["id"], job_id=job["job_id"],
                job=job, seed=137, step=job["step"], stage=job["stage"],
                arm=job["arm"], algorithm=job.get("algorithm", job.get("condition", "low_lr_1e-5_from_fixed1192")), feedback_temperature=None,
                temperature=job["config"]["temperature"] if job["kind"] == "generate" else 1.0,
                feedback_batch=1,
                gpu_index=gpu_index, started_epoch=started, finished_epoch=time.time(),
                actual_worker_pid=os.getpid(), actual_attempt_root=str(attempt),
                resources=guard.report(), model_released=True))
            validate_result(root, job, result)
            binding.publish(attempt / "completed/record.json", dict(protocol_id=protocol["id"],
                result=binding.entry(directory / "result/record.json")))
            binding.publish(attempt / "result/record.json", dict(protocol_id=protocol["id"],
                job_id=job["job_id"], stable_result=binding.entry(directory / "result/record.json"),
                actual_worker_pid=os.getpid(), scientific_result_reused=False))
            return result
        except BaseException as error:
            record_attempt_failure(root, job, attempt, error, guard=guard)
            raise
