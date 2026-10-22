"""Generate-only durable auditing with the frozen V63 failure disposition.

The private function namespace redirects only paths and registration checks.
It cannot dispatch feedback, replay, distribution, training, or scoring, and
never changes the imported historical modules or their frozen source files.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import FunctionType, SimpleNamespace

import finqa_v65_binding as binding

original = binding.source_module("finqa_v63_worker_audit")
require = binding.require


def _evaluation():
    return importlib.import_module("finqa_v65_evaluation")


def _job_id(job):
    return original._job_id(job)


def _job_directory(root, job):
    root = Path(root).resolve()
    require(root == Path(binding.ROOT).resolve(), "V65 generation cannot target the scientific root")
    planned = _evaluation().planned_jobs()
    key = _job_id(job)
    require(job.get("stage") == "generate" and key in planned,
            "V65 admits only its twenty authorized generation jobs")
    require(all(job.get(field) == value for field, value in planned[key].items()),
            "V65 generation job differs from the registered scientific configuration")
    return root / "evaluations/jobs" / key


def checked_attempt_directory(root, job, attempt_dir=None):
    _job_directory(root, job)
    path = _adapted["checked_attempt_directory"](root, job, attempt_dir)
    require(os.environ.get("V65_ATTEMPT_DIR") in (None, str(path))
            and os.environ.get("V65_ATTEMPT_ID") in (None, path.name),
            "V65 and historical durable attempt aliases disagree")
    return path


def _evaluation_context(root, job):
    evaluation = _evaluation()
    plan = evaluation.checked_plan(root)
    key = _job_id(job)
    require(key in plan["jobs"], "unregistered V65 generation job")
    registered = plan["jobs"][key]
    for field in ("seed", "arm", "feedback_batch", "stage", "panel", "draw_seed", "denominator",
                  "config", "checkpoint", "model_identity", "role", "step"):
        require(job.get(field) == registered.get(field), "evaluation scientific binding changed: " + field)
    require(registered["feedback_batch"] == 1 and registered["step"] == 894,
            "only original b1 step894 generation may resume")
    return plan, evaluation.generation_root(root, job), [binding.entry(
        Path(root) / "evaluations/registration/record.json")]


def audit_job_resume(root, job):
    """Read only durable public generation metadata; UNKNOWN remains blocked."""
    directory = _job_directory(root, job)
    plan, generation, refs = _evaluation_context(root, job)
    protocol = _evaluation()._protocol(root)
    result = original.durable.audit_resume(generation, inheritance=None)
    evidence = [binding.entry(Path(root) / "protocol/record.json"), *refs, *result["evidence"]]
    complete = (directory / "result/record.json").exists()
    if complete:
        saved = binding.checked(directory / "result/record.json")
        require(saved.get("schema") == "v65_generation_only_job_result.v1"
                and saved.get("scientific_protocol_id") == plan["scientific_protocol_id"]
                and saved.get("payload") is None and saved.get("branch_result") is None,
                "V65 complete result must contain generation only, with unchanged scientific identity")
        _adapted["_validate_complete_result"](root, job, protocol)
        evidence.append(binding.entry(directory / "result/record.json"))
    return dict(resume_allowed=bool(result["resume_allowed"] and result["unknown_calls"] == 0),
        unknown_calls=result["unknown_calls"], progress_units=result["progress_units"],
        evidence=evidence, complete_stage=complete,
        full_tensor_validation_before_cold_scientific_use=True,
        details=dict(feedback_audit=result), durable_progress_digest=result["durable_progress_digest"])


def _private_disposition():
    # The original transient-resource/errno classifier is reused byte-for-byte.
    # A private namespace replaces root ownership and generate admission only.
    proxy = SimpleNamespace(**{name: getattr(original.binding, name) for name in
        ("SEEDS", "ARMS", "TEMPERATURES", "BATCH")}, ROOT=Path(binding.ROOT),
        checked=binding.checked, require=binding.require, digest=binding.digest,
        entry=binding.entry, read_ref=binding.read_ref, sha=binding.sha,
        publish=binding.publish, file_ref=binding.file_ref)
    namespace = dict(vars(original), binding=proxy,
        _job_directory=_job_directory, _evaluation_context=_evaluation_context,
        audit_job_resume=audit_job_resume, checked_attempt_directory=checked_attempt_directory)
    names = ("_validate_complete_result", "checked_attempt_directory", "reuse_complete_result",
             "_exception_chain", "record_attempt_failure", "classify_attempt")
    adapted = {}
    for name in names:
        value = getattr(original, name)
        cloned = FunctionType(value.__code__, namespace, value.__name__, value.__defaults__, value.__closure__)
        cloned.__kwdefaults__ = value.__kwdefaults__
        adapted[name] = cloned
        if name != "checked_attempt_directory":
            namespace[name] = cloned
    return adapted


_adapted = _private_disposition()


def classify_attempt(root, job, attempt_dir, returncode):
    _job_directory(root, job)
    return _adapted["classify_attempt"](root, job, attempt_dir, returncode)


def reuse_complete_result(root, job, attempt_dir):
    _job_directory(root, job)
    return _adapted["reuse_complete_result"](root, job, attempt_dir)


def record_attempt_failure(root, job, attempt_dir, error, *, guard=None):
    _job_directory(root, job)
    return _adapted["record_attempt_failure"](root, job, attempt_dir, error, guard=guard)
