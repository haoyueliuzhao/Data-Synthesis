"""Read-only durable admission and evidence-based V63 attempt disposition.

Admission reads small metadata and file sizes, never Tensor payloads. The cold
scientific consumer still checks actual bytes and values. CPU finalization is
separate: it verifies an already-complete result, without a new scientific call.
"""
from __future__ import annotations

import errno
import importlib
import json
import os
from pathlib import Path
import re
import sys
import time

import finqa_v63_binding as binding

binding.install_scientific_paths()

import finqa_v63_training as training
import finqa_v63_temperature as temperature
import finqa_v56_feedback as durable

require, checked, digest = binding.require, binding.checked, binding.digest
GIB = 1024 ** 3
IO_ERRNOS = {errno.EIO, errno.EAGAIN, errno.ENOSPC, errno.ESTALE}


def _job_id(job):
    value = job.get("job_id", job.get("id"))
    require(isinstance(value, str) and value and "/" not in value and "\\" not in value,
            "registered scalar scientific job identity required")
    return value


def _job_directory(root, job):
    root = Path(root).resolve()
    require(root == binding.ROOT.resolve(), "V63 audit cannot target another scientific root")
    require(job.get("seed") in binding.SEEDS and job.get("arm") in binding.ARMS,
            "only the six new seed/temperature coordinates are admitted")
    key, stage = _job_id(job), job["stage"]
    if stage == "generate":
        return root / "evaluations/jobs" / key
    require(stage in {f"{part}_{arm}" for part in ("feedback", "replay", "distribution", "train")
                      for arm in binding.ARMS}
            and stage.rsplit("_", 1)[1] == job["arm"]
            and key == f"seed{job['seed']}.{stage}",
            "job stage/arm differs or requests an unauthorized new class pass")
    return root / f"stages/seed{job['seed']}/{stage}"


def checked_attempt_directory(root, job, attempt_dir=None):
    """Both aliases denote one actual attempt; neither can silently override."""
    aliases = [os.environ.get(name) for name in
               ("V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR", "V56_JOB_ATTEMPT_ROOT")]
    supplied = [Path(value).resolve() for value in ([attempt_dir] + aliases) if value is not None]
    require(supplied and all(path == supplied[0] for path in supplied),
            "V63/V56 attempt directory aliases disagree or are missing")
    path = supplied[0]
    require(path.parent == _job_directory(root, job) / "attempts"
            and re.fullmatch(r"attempt[0-9]{4,}", path.name) is not None,
            "attempt must be the independently dispatched job attempt")
    ids = [os.environ.get(name) for name in ("V63_ATTEMPT_ID", "V56_ATTEMPT_ID")]
    require(all(value is None or value == path.name for value in ids),
            "V63/V56 attempt ID aliases disagree")
    return path


def _state_metadata(directory, record, *, field="state_sha256", filename="state.pt"):
    path = Path(directory) / filename
    require(path.is_file() and not path.is_symlink() and path.stat().st_size > 0,
            "durable actual tensor file is missing or aliased")
    require(isinstance(record.get(field), str) and len(record[field]) == 64,
            "actual tensor digest is missing")
    size = path.stat().st_size
    require("state_bytes" not in record or size == record["state_bytes"],
            "actual tensor size differs from the immutable metadata")
    return dict(path=str(path), sha256=record[field], bytes=size,
                full_tensor_validation_required_in_cold_worker=True)


def _parent(root, job, protocol):
    parent = training.checked_parent(root, job["seed"])
    require(parent["protocol_id"] == protocol["id"] and parent["feedback_batch"] == binding.BATCH,
            "parent belongs to another batch or protocol")
    return parent


def _feedback_condition(root, job, parent, *, required=False):
    directory = Path(root) / f"stages/seed{job['seed']}/feedback_{job['arm']}/feedback"
    paths = sorted(directory.glob("*/intent/record.json"))
    require(len(paths) <= 1 and (not required or len(paths) == 1),
            "exactly one independently registered batch1 condition required")
    if not paths:
        require(not any(directory.glob("*/draw*/run.json")),
                "feedback run exists without its pre-generation condition")
        return None, []
    path = paths[0]
    condition = temperature.checked_condition(checked(path))
    require(path.parent.parent.name == condition["id"]
            and condition["feedback_batch"] == binding.BATCH
            and condition["arm"] == job["arm"]
            and condition["temperature"] == binding.TEMPERATURES[job["arm"]]
            and condition["draw_seeds"] == list(binding.DRAW_SEEDS)
            and condition["identity"]["point_id"] == parent["point_id"]
            and condition["denominator"] == 700 and condition["cpu_test_only"] is False,
            "saved feedback condition has another batch, draw, temperature or actual parent point")
    return condition, [binding.entry(path)]


def _payload_metadata(directory, parent, job):
    path = Path(directory) / "payload/record.json"
    row = checked(path)
    require(row["schema"] == "v63_actual_scientific_payload.v1"
            and row["parent_id"] == parent["id"]
            and row["parent_state_digest"] == parent["parent_state_digest"]
            and row["stage"] == job["stage"]
            and row["feedback_batch"] == binding.BATCH
            and row["arm"] == job["arm"]
            and row["temperature"] == binding.TEMPERATURES[job["arm"]]
            and row["actual_tensors_saved"] is True,
            "saved actual payload belongs to another parent, batch or temperature")
    _state_metadata(path.parent, row)
    return row, binding.entry(path)


def _evaluation_context(root, job):
    evaluation = importlib.import_module("finqa_v63_evaluation")
    plan_path = Path(root) / "evaluations/registration/record.json"
    plan = checked(plan_path)
    require(plan["protocol_id"] == checked(Path(root) / "protocol/record.json")["id"],
            "evaluation registration belongs to another scientific protocol")
    key = _job_id(job)
    require(key in plan["jobs"], "unregistered evaluation job")
    registered = plan["jobs"][key]
    for field in ("seed", "arm", "feedback_batch", "stage", "panel", "draw_seed", "denominator",
                  "config", "checkpoint", "model_identity", "role", "step"):
        require(job.get(field) == registered.get(field), "evaluation scientific binding changed: " + field)
    require(registered["feedback_batch"] == binding.BATCH and registered["step"] == 894,
            "only new b1 step894 evaluation may resume")
    return plan, evaluation.generation_root(root, job), [binding.entry(plan_path)]


def _validate_complete_result(root, job, protocol, *, parent=None, condition=None):
    directory = _job_directory(root, job)
    result = checked(directory / "result/record.json")
    require(result["status"] == "COMPLETE" and result["feedback_batch"] == binding.BATCH
            and result["resources"]["all_gates_passed"] is True,
            "result must already be complete under the original resource hard gates")
    if job["stage"] == "generate":
        plan, _generation, _refs = _evaluation_context(root, job)
        require(result["registration_id"] == plan["id"] and result["job_id"] == _job_id(job)
                and result["sessions"] == job["denominator"]
                and result["scoring_calls"] == 0 and result["private_references_read"] is False,
                "complete generation result belongs to another registered panel")
        seal = binding.read_ref(result["whole_queue_seal"])
        require(Path(result["whole_queue_seal"]["path"]).resolve() ==
                directory / "whole_queue_seal/record.json"
                and seal["id"] == result["whole_queue_seal_id"]
                and seal["registration_id"] == plan["id"] and seal["job_id"] == _job_id(job)
                and seal["feedback_batch"] == binding.BATCH
                and seal["all_provider_calls_settled"] is True,
                "new generation completion seal changed")
    else:
        require(parent is not None
                and result["protocol_id"] == protocol["id"]
                and result["stage"] == job["stage"] and result["seed"] == job["seed"]
                and result["arm"] == job["arm"]
                and result["temperature"] == binding.TEMPERATURES[job["arm"]],
                "saved result belongs to another new scientific coordinate")
        if job["stage"].startswith(("feedback_", "replay_", "distribution_")):
            require(condition is not None and result["condition_id"] == condition["id"],
                    "complete result differs from the registered new feedback condition")
            row, reference = _payload_metadata(directory, parent, job)
            require(result["payload"]["path"] == reference["path"]
                    and result["payload"]["sha256"] == reference["sha256"],
                    "complete result payload reference changed")
        elif job["stage"].startswith("train_"):
            branch = training.checked_branch_result(root, job["seed"], job["arm"])
            require(branch["protocol_id"] == protocol["id"]
                    and branch["parent_state_digest"] == parent["parent_state_digest"]
                    and result["branch_result"]["id"] == branch["id"],
                    "complete result references another new training branch")
            require(Path(result["branch_result"]["path"]).resolve() ==
                    training.branch_root(root, job["seed"], job["arm"]) / "completed/record.json",
                    "new training result cannot alias a historical branch")
    return result


def audit_job_resume(root, job):
    """Small-metadata disposition; never loads Tensor or changes any artifact."""
    root = Path(root).resolve()
    directory = _job_directory(root, job)
    protocol = checked(root / "protocol/record.json")
    evidence = [binding.entry(root / "protocol/record.json")]
    progress, unknown, allowed, details = 0, 0, True, {}
    stage, condition, parent = job["stage"], None, None
    if stage == "generate":
        _plan, generation, refs = _evaluation_context(root, job)
        evidence.extend(refs)
        result = durable.audit_resume(generation, inheritance=None)
        details["feedback_audit"] = result
        evidence.extend(result["evidence"])
        progress, unknown, allowed = result["progress_units"], result["unknown_calls"], result["resume_allowed"]
    else:
        parent = _parent(root, job, protocol)
        evidence.append(binding.entry(root / f"parents/seed{job['seed']}/record.json"))
        condition, refs = _feedback_condition(root, job, parent)
        evidence.extend(refs)
        if stage.startswith("feedback_"):
            result = durable.audit_resume(directory, inheritance=None)
            details["feedback_audit"] = result
            evidence.extend(result["evidence"])
            progress, unknown, allowed = result["progress_units"], result["unknown_calls"], result["resume_allowed"]
        elif stage.startswith("replay_"):
            candidates = sorted(directory.glob("checkpoints/response*/record.json"))
            if candidates:
                require(condition is not None, "replay checkpoint has no complete new condition")
                path, row = candidates[-1], checked(candidates[-1])
                point = row["binding"]
                backend = point["backend_identity"]
                counts = row.get("draw_response_counts")
                require(row["schema"] == "v19_response_boundary_checkpoint.v1"
                        and row["response_prefix_complete"] is True
                        and row.get("formal_and_draws_atomically_committed") is True
                        and row.get("draw_components_schema") == temperature.components.VERSION
                        and path.parent.name == f"response{row['cursor']:06d}"
                        and type(row["cursor"]) is int and 0 <= row["cursor"] <= point["response_count"]
                        and row["full_replay_complete"] is (row["cursor"] == point["response_count"])
                        and point["point_id"] == parent["point_id"] and point["denominator"] == 700
                        and point["parameter_digest"] == condition["identity"]["parameter_digest"]
                        and point["gradient_length_normalized"] is False
                        and point["block_size"] == 8 and point["checkpoint_every_responses"] == 16
                        and point["replay_state_adapter"] == temperature.BACKEND_VERSION
                        and backend["backend_version"] == temperature.BACKEND_VERSION
                        and backend["feedback_condition_id"] == condition["id"]
                        and backend["temperature"] == binding.TEMPERATURES[job["arm"]]
                        and backend["arm"] == job["arm"] and backend["feedback_batch"] == binding.BATCH
                        and backend["draw_seeds"] == list(binding.DRAW_SEEDS)
                        and backend["draw_component_version"] == temperature.components.VERSION
                        and backend["mean_tolerances"] == temperature.MEAN_TOLERANCES
                        and isinstance(counts, dict) and set(counts) == {"101", "103"}
                        and all(type(n) is int and n >= 0 for n in counts.values())
                        and sum(counts.values()) == row["cursor"],
                        "response checkpoint lacks its exact atomic formal/draw condition")
                order = point["response_order"]
                require(len(order) == point["response_count"]
                        and point["response_order_sha256"] == digest(order),
                        "response checkpoint order identity changed")
                actual_counts = {"101": 0, "103": 0}
                for episode_index, _turn, _call in order[:row["cursor"]]:
                    require(type(episode_index) is int and 0 <= episode_index < 700,
                            "response episode outside the fixed cohort")
                    actual_counts[str(condition["ordered_episode_roster"][episode_index]["seed"])] += 1
                require(counts == actual_counts, "saved draw counts differ from ordered response prefix")
                _state_metadata(path.parent, row)
                evidence.append(binding.entry(path))
                progress = row["cursor"]
                details["joint_formal_and_draw_checkpoint"] = binding.entry(path)
            details["persisted_response_prefix"] = progress
        elif stage.startswith("train_"):
            base = training.branch_root(root, job["seed"], job["arm"])
            checkpoint = training.latest_branch_checkpoint(base / "training")
            contract_path = base / "binding/record.json"
            if contract_path.exists():
                contract = checked(contract_path)
                require(contract["schema"] == "v63_fixed_q_training_binding.v1"
                        and contract["protocol_id"] == protocol["id"]
                        and contract["parent_id"] == parent["id"]
                        and contract["parent_state_digest"] == parent["parent_state_digest"]
                        and (contract["seed"], contract["arm"], contract["feedback_batch"]) ==
                        (job["seed"], job["arm"], binding.BATCH)
                        and contract["temperature"] == binding.TEMPERATURES[job["arm"]]
                        and contract["start_step"] == 596 and contract["end_step"] == 894
                        and contract["outer_schedule_during_window"] == []
                        and contract["real_parent_not_theta_bar"] is True,
                        "new fixed-q training binding changed")
                evidence.append(binding.entry(contract_path))
            if checkpoint is not None:
                require(contract_path.exists(), "actual training checkpoint lacks its new branch binding")
                row = json.loads((checkpoint / "record.json").read_bytes())
                require(row["seed"] == job["seed"] and row["arm"] == "C-only"
                        and type(row["step"]) is int and 596 <= row["step"] <= 894
                        and row["phase"] == ("branch" if row["step"] == 596 else "step")
                        and row["pool_id"] == parent["pool_id"]
                        and row["checkpoint_contains_actual_model_Adam_RNG_pi"] is True,
                        "training durable cursor or actual-state contract changed")
                _state_metadata(checkpoint, row)
                evidence.append(binding.file_ref(checkpoint / "record.json"))
                progress = row["step"] - 596
            details.update(committed_optimizer_updates=progress,
                           cold_consumer_must_check_actual_outer_done_equals_298=True)
        elif stage.startswith("distribution_"):
            if (directory / "payload/record.json").exists():
                require(condition is not None, "distribution payload lacks its new feedback condition")
                _row, reference = _payload_metadata(directory, parent, job)
                evidence.append(reference)
                progress = 1
        else:
            raise ValueError("unregistered V63 durable stage")
    complete = (directory / "result/record.json").exists()
    if complete:
        _validate_complete_result(root, job, protocol, parent=parent, condition=condition)
        evidence.append(binding.entry(directory / "result/record.json"))
    body = dict(
        resume_allowed=bool(allowed and unknown == 0), unknown_calls=unknown,
        progress_units=progress, evidence=evidence, complete_stage=complete,
        full_tensor_validation_before_cold_scientific_use=True, details=details)
    body["durable_progress_digest"] = (
        details["feedback_audit"]["durable_progress_digest"] if "feedback_audit" in details
        else digest(dict(progress_units=progress,
                         evidence=[dict(path=v["path"], sha256=v["sha256"]) for v in evidence])))
    return body


def reuse_complete_result(root, job, attempt_dir):
    """CPU-only verification; never regenerates feedback or replays/trains."""
    root = Path(root).resolve()
    attempt_dir = checked_attempt_directory(root, job, attempt_dir)
    audit = audit_job_resume(root, job)
    require(audit["resume_allowed"] and audit["unknown_calls"] == 0 and audit["complete_stage"],
            "only an already complete and settled result may be finalized")
    directory = _job_directory(root, job)
    result = checked(directory / "result/record.json")
    protocol = checked(root / "protocol/record.json")
    if result.get("payload"):
        payload = binding.read_ref(result["payload"])
        require(binding.sha(Path(result["payload"]["path"]).parent / "state.pt") == payload["state_sha256"],
                "complete actual scientific payload bytes changed")
    if result.get("branch_result"):
        branch = binding.read_ref(result["branch_result"])
        for reference in branch["snapshots"].values():
            require(binding.sha(Path(reference["path"]) / "state.pt") == reference["state_sha256"],
                    "complete actual branch snapshot bytes changed")
    observations = Path(result["resources"]["observations_path"]).resolve()
    require(observations.is_relative_to(root / "resources" / _job_id(job))
            and observations.name == "observations.jsonl",
            "complete resources belong to another job")
    path = observations.parent / "closeout/record.json"
    closed = checked(path)
    require(closed["status"] == "COMPLETE" and closed["resources"] == result["resources"]
            and closed["protocol_id"] == protocol["id"] and closed["job_id"] == _job_id(job)
            and closed["resources"]["single_process_lifetime_includes_loading"] is True,
            "complete original lifetime resource proof required for CPU finalization")
    binding.publish(attempt_dir / "reused_result/record.json", dict(
        schema="v63_complete_result_CPU_finalization.v1",
        protocol_id=protocol["id"], job_id=_job_id(job), feedback_batch=binding.BATCH,
        source_result=binding.entry(directory / "result/record.json"),
        source_resource_closeout=binding.entry(path), scientific_calls=0,
        verified_durable_result=True, original_scientific_result_rewritten=False))
    return result


def _exception_chain(error):
    result, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        native_errno = error.errno if isinstance(error, OSError) else None
        if isinstance(error, durable.GenerationPreCallPause) and error.actual_model_calls == 0:
            native_errno = error.errno
        result.append(dict(
            type=type(error).__name__, module=type(error).__module__, actual_errno=native_errno,
            message=str(error), automatic_recovery_allowed=getattr(error, "automatic_recovery_allowed", None)))
        error = error.__cause__ or error.__context__
    return result


def record_attempt_failure(root, job, attempt_dir, error, *, guard=None):
    root = Path(root).resolve()
    attempt_dir = checked_attempt_directory(root, job, attempt_dir)
    protocol = checked(root / "protocol/record.json")
    resources, resource_closeout = guard.report() if guard is not None else None, None
    path = (Path(guard.directory) / "closeout/record.json" if guard is not None else
            root / "resources" / _job_id(job) / f"pid{os.getpid()}/closeout/record.json")
    if path.exists():
        closed = checked(path)
        resources, resource_closeout = closed["resources"], binding.entry(path)
    torch = sys.modules.get("torch")
    return binding.publish(attempt_dir / "failure/record.json", dict(
        schema="v63_actual_attempt_failure.v1", protocol_id=protocol["id"],
        job=job, feedback_batch=binding.BATCH, pid=os.getpid(), attempt_root=str(attempt_dir),
        exception_chain=_exception_chain(error), exception_type=type(error).__name__,
        error=str(error), finished_epoch=time.time(), resource_closeout=resource_closeout,
        resources=resources, automatic_retry_in_worker=False,
        CUDA_initialized=bool(torch and torch.cuda.is_initialized())))


def classify_attempt(root, job, attempt_dir, returncode):
    """Actual exit + settled state + positive resource/errno evidence, or block."""
    root = Path(root).resolve()
    attempt_dir = checked_attempt_directory(root, job, attempt_dir)
    protocol = checked(root / "protocol/record.json")
    verdict = dict(classification="HARD_BLOCK", reason="missing actual waitpid or structured failure evidence",
                   resume_allowed=False, unknown_calls=0, evidence=[], actual_errno=None)
    exit_path, launch_path = attempt_dir / "actual_exit/record.json", attempt_dir / "launch/record.json"
    if not exit_path.exists() or not launch_path.exists() or type(returncode) is not int:
        return verdict
    actual, launch = checked(exit_path), checked(launch_path)
    require(actual["protocol_id"] == launch["protocol_id"] == protocol["id"]
            and actual["job_id"] == _job_id(job) == _job_id(launch["job"])
            and actual["actual_waitpid_observed"] is True and actual["returncode"] == returncode
            and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"])
            and actual["attempt"] == launch["attempt"] == int(attempt_dir.name[7:]),
            "retry requires this exact actual launched process and waitpid result")
    verdict["evidence"] = [binding.entry(launch_path), binding.entry(exit_path)]
    path = attempt_dir / "failure/record.json"
    if not path.exists():
        return verdict
    failure = checked(path)
    require(failure["schema"] == "v63_actual_attempt_failure.v1"
            and failure["protocol_id"] == protocol["id"]
            and failure["feedback_batch"] == binding.BATCH
            and failure["attempt_root"] == str(attempt_dir)
            and failure["pid"] == actual["pid"]
            and failure["job"]["stage"] == job["stage"]
            and _job_id(failure["job"]) == _job_id(job),
            "attempt failure ownership changed")
    verdict["evidence"].append(binding.entry(path))
    try:
        audit = audit_job_resume(root, job)
    except OSError as error:
        if error.errno in IO_ERRNOS:
            verdict.update(classification="AUDIT_IO_WAIT", actual_errno=error.errno,
                           reason="actual IO prevents durable audit; no scientific dispatch allowed")
        else:
            verdict["reason"] = "durable state audit IO failed: " + str(error)
        return verdict
    except (ValueError, KeyError) as error:
        verdict["reason"] = "durable state audit failed: " + type(error).__name__ + ": " + str(error)
        return verdict
    verdict.update({key: audit[key] for key in ("unknown_calls", "durable_progress_digest", "progress_units")})
    verdict["evidence"].extend(audit["evidence"])
    if audit["unknown_calls"] or not audit["resume_allowed"]:
        verdict["reason"] = "UNKNOWN or invalid actual saved state cannot be retried"
        return verdict
    resources, chain = failure.get("resources") or {}, failure.get("exception_chain", [])
    types = {row["type"] for row in chain}
    if returncode < 0 or resources.get("received_signals") or types & {
            "ExplicitStop", "KeyboardInterrupt", "ReplayPaused"}:
        verdict.update(classification="EXPLICIT_STOP", reason="explicit/signal stop does not authorize automatic retry")
        return verdict
    if any(row.get("automatic_recovery_allowed") is False for row in chain) or types & {
            "DrawDiagnosticError", "GenerationUnknown", "GenerationBindingError",
            "AssertionError", "ImportError", "ModuleNotFoundError", "KeyError", "TypeError"}:
        verdict["reason"] = "diagnostic, scientific binding, UNKNOWN or implementation failure"
        return verdict
    if "ValueError" in types and failure["exception_type"] != "R3CapacityError":
        verdict["reason"] = "numeric/state ValueError is not a resource retry"
        return verdict
    violation = resources.get("observed_violation") or {}
    host = violation.get("host") or {}
    peak = max(resources.get("peak_allocated_bytes", 0),
               violation.get("peak_allocated_bytes", 0), violation.get("torch_peak_allocated_bytes", 0))
    rss = max(resources.get("peak_rss_bytes", 0), host.get("peak_rss_bytes", 0))
    if peak > 76 * GIB or rss > min(host.get("rss_limit_bytes", 192 * GIB), 192 * GIB):
        verdict["reason"] = "historical allocated/RSS hard peak requires diagnosis, not retry"
        return verdict
    if failure.get("resource_closeout"):
        closed = binding.read_ref(failure["resource_closeout"])
        require(closed["resources"] == resources and closed["pid"] == actual["pid"]
                and closed["protocol_id"] == protocol["id"] and closed["job_id"] == _job_id(job),
                "closed resource evidence belongs to another actual process")
        verdict["evidence"].append(failure["resource_closeout"])
    external_ram = bool(host) and host.get("available_bytes", float("inf")) < host.get(
        "available_reserve_bytes", 96 * GIB)
    external_free = violation.get("boundary") is True and violation.get("free_bytes", float("inf")) < 2 * GIB
    actual_oom = any(row["type"] == "OutOfMemoryError" and row["module"].startswith("torch") for row in chain)
    if resources.get("deferred_observation") or external_ram or external_free or actual_oom:
        verdict.update(classification="RETRY_SAFE_RESOURCE", resume_allowed=True,
                       reason="proved resource shortage after actual exit and settled durable audit")
        return verdict
    for row in chain:
        if row.get("actual_errno") in IO_ERRNOS:
            verdict.update(classification="RETRY_SAFE_IO", resume_allowed=True,
                           actual_errno=row["actual_errno"],
                           reason="proved transient IO errno after actual exit and settled durable audit")
            return verdict
    verdict["reason"] = "failure is not a proved transient resource or allowed IO error"
    return verdict
