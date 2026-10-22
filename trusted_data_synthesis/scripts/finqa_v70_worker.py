"""Cold V70 execution and read-only, same-state durable recovery admission.

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

import finqa_v70_binding as binding
import finqa_v70_queue_base as queue

original = binding.source_module("finqa_v63_worker_audit")
temperature = importlib.import_module("finqa_v70_temperature")
durable = original.durable
require, checked = binding.require, binding.checked


def _job_id(job):
    value = job.get("job_id", job.get("id"))
    require(isinstance(value, str) and value and "/" not in value and "\\" not in value,
            "registered scalar V70 job ID required")
    return value


def _job_directory(root, job):
    key = _job_id(job)
    roster = queue.all_jobs()
    require(key in roster and all(job.get(field) == value for field, value in roster[key].items()
            if field not in ("dependencies", "priority")), "scientific job differs from fixed V70 roster")
    return queue.job_directory(root, job)


def checked_attempt_directory(root, job, attempt_dir=None):
    aliases = [os.environ.get(name) for name in
               ("V70_ATTEMPT_DIR", "V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR", "V56_JOB_ATTEMPT_ROOT")]
    supplied = [Path(value).resolve() for value in [attempt_dir, *aliases] if value is not None]
    require(supplied and all(path == supplied[0] for path in supplied), "durable attempt aliases disagree")
    path = supplied[0]
    require(path.parent == _job_directory(root, job) / "attempts"
            and re.fullmatch(r"attempt[0-9]{4,}", path.name) is not None,
            "V70 attempt escaped its immutable per-job dispatch directory")
    require(all(os.environ.get(name) in (None, path.name)
                for name in ("V70_ATTEMPT_ID", "V63_ATTEMPT_ID", "V56_ATTEMPT_ID")),
            "actual attempt identifiers differ")
    return path


def _payload_metadata(directory, point, stage):
    path = Path(directory) / "payload/record.json"
    row = checked(path)
    require(row["point_context_id"] == point["id"] and row["stage"] == stage
            and row["parent_state_digest"] == point["parent_state_digest"],
            "durable payload belongs to another real parameter point")
    original._state_metadata(path.parent, row)
    return row, binding.entry(path)


def _condition(root, job, point):
    directory = Path(root) / "points" / f"step{job['step']:04d}" / "virtual_point/feedback"
    paths = sorted(directory.glob("*/intent/record.json"))
    require(len(paths) <= 1, "each real point has one registered 700-session condition")
    if not paths:
        require(not any(directory.glob("*/draw*/run.json")), "feedback exists without pre-call intent")
        return None, []
    condition = temperature.checked_condition(checked(paths[0]))
    require(condition["arm"] == "C1" and condition["feedback_batch"] == 1
            and condition["temperature"] == 1.0 and condition["denominator"] == 700
            and condition["draw_seeds"] == [101, 103] and condition["cpu_test_only"] is False
            and paths[0].parent.parent.name == condition["id"], "feedback dose or probability changed")
    computed = Path(root) / "points" / f"step{job['step']:04d}" / "virtual_point/computed_point/payload/record.json"
    require(computed.exists(), "feedback cannot precede the same-point virtual computation")
    row = checked(computed)
    require(row["point_context_id"] == point["id"]
            and row["point_id"] == condition["identity"]["point_id"],
            "feedback and actual computed point disagree")
    return condition, [binding.entry(paths[0]), binding.entry(computed)]


def _response_metadata(directory, condition):
    candidates = sorted(Path(directory).glob("checkpoints/response*/record.json"))
    if not candidates:
        return 0, []
    require(condition is not None, "response checkpoint has no complete same-point condition")
    path, row = candidates[-1], checked(candidates[-1])
    point, counts = row["binding"], row.get("draw_response_counts")
    backend = point["backend_identity"]
    require(row["schema"] == "v19_response_boundary_checkpoint.v1"
            and row["response_prefix_complete"] is True
            and row.get("formal_and_draws_atomically_committed") is True
            and row.get("draw_components_schema") == temperature.components.VERSION
            and path.parent.name == f"response{row['cursor']:06d}"
            and type(row["cursor"]) is int and 0 <= row["cursor"] <= point["response_count"]
            and row["full_replay_complete"] is (row["cursor"] == point["response_count"])
            and point["point_id"] == condition["identity"]["point_id"]
            and point["parameter_digest"] == condition["identity"]["parameter_digest"]
            and point["denominator"] == 700 and point["gradient_length_normalized"] is False
            and point["block_size"] == 8 and point["checkpoint_every_responses"] == 16
            and point["replay_state_adapter"] == temperature.BACKEND_VERSION
            and backend["backend_version"] == temperature.BACKEND_VERSION
            and backend["feedback_condition_id"] == condition["id"]
            and backend["temperature"] == 1.0 and backend["arm"] == "C1"
            and backend["feedback_batch"] == 1 and backend["draw_seeds"] == [101, 103]
            and backend["draw_component_version"] == temperature.components.VERSION
            and backend["mean_tolerances"] == temperature.MEAN_TOLERANCES
            and isinstance(counts, dict) and set(counts) == {"101", "103"}
            and all(type(n) is int and n >= 0 for n in counts.values())
            and sum(counts.values()) == row["cursor"], "actual joint formal/draw response binding changed")
    order = point["response_order"]
    require(len(order) == point["response_count"]
            and point["response_order_sha256"] == binding.digest(order), "response order changed")
    actual = {"101": 0, "103": 0}
    for episode_index, _turn, _call in order[:row["cursor"]]:
        require(type(episode_index) is int and 0 <= episode_index < 700, "foreign feedback episode")
        actual[str(condition["ordered_episode_roster"][episode_index]["seed"])] += 1
    require(actual == counts, "durable draw counts disagree with actual ordered prefix")
    original._state_metadata(path.parent, row)
    return row["cursor"], [binding.entry(path)]


def _accepted_previous_training(root, step, protocol):
    training = importlib.import_module("finqa_v70_training")
    require(step in (1192, 1490), "only a later actual point has a new predecessor")
    preceding = f"step{step - 298}.train"
    path = training.point_root(root, step - 298) / "train/accepted/record.json"
    accepted = checked(path)
    actual = binding.read_ref(accepted["actual_exit"])
    require(accepted["protocol_id"] == actual["protocol_id"] == protocol["id"]
            and accepted["job_id"] == actual["job_id"] == preceding
            and accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
            and actual["actual_waitpid_observed"] is True and actual["returncode"] == 0,
            "new actual point requires its preceding accepted training worker exit zero")
    return [binding.entry(path), accepted["actual_exit"]]


def audit_job_resume(root, job):
    directory = _job_directory(root, job)
    if job["kind"] == "generate":
        return importlib.import_module("finqa_v70_evaluation").audit_job_resume(root, job)
    training = importlib.import_module("finqa_v70_training")
    protocol = checked(Path(root) / "protocol/record.json")
    context = training.point_root(root, job["step"]) / "context/record.json"
    evidence, progress, unknown, allowed, details = [binding.entry(Path(root) / "protocol/record.json")], 0, 0, True, {}
    if not context.exists():
        allowed_entries = {"attempts", "worker.lock"}
        require(job["step"] in (1192, 1490)
                and (not directory.exists() or job["kind"] == "class"
                     and all(path.name in allowed_entries for path in directory.iterdir()))
                and not (context.parent.parent / "task_cache").exists(),
                "missing context cannot conceal an already-dispatched scientific stage")
        if directory.exists():
            evidence.extend(_accepted_previous_training(root, job["step"], protocol))
        return dict(resume_allowed=True, unknown_calls=0, progress_units=0, evidence=evidence,
                    durable_progress_digest=binding.digest(dict(job_id=job["job_id"], pending_point=True)),
                    complete_stage=False, full_tensor_validation_before_cold_scientific_use=True,
                    details=dict(awaiting_registered_previous_training=True))
    point = training.checked_point(root, job["step"])
    require(point["protocol_id"] == protocol["id"], "point belongs to another protocol")
    evidence.append(binding.entry(context))
    stage = job["stage"]
    condition, condition_refs = (None, []) if job["kind"] == "class" else _condition(root, job, point)
    evidence.extend(condition_refs)
    if job["kind"] == "class":
        plan = binding.read_ref(point["task_plan"])
        assigned = set(plan["assignments"][int(stage[-2:])]["task_ids"])
        for task in plan["tasks"]:
            if task["task_id"] not in assigned:
                continue
            path = Path(point["task_cache_root"]) / f"task{task['index']:04d}/record.json"
            if not path.exists():
                continue
            row = checked(path)
            require(row["complete_task"] is True and row["task"] == task
                    and row["task_plan_id"] == plan["id"] and row["binding"] == point["task_binding"],
                    "class cache belongs to another point, shard or partial task")
            original._state_metadata(path.parent, row, field="gradient_sha256", filename="gradient.pt")
            evidence.append(binding.entry(path))
            progress += 1
        details["complete_task_count"] = progress
    elif stage == "virtual_point":
        audit = durable.audit_resume(directory, inheritance=None)
        evidence.extend(audit["evidence"])
        progress, unknown, allowed = audit["progress_units"], audit["unknown_calls"], audit["resume_allowed"]
        details["feedback_audit"] = audit
    elif stage == "replay":
        progress, references = _response_metadata(directory, condition)
        evidence.extend(references)
        details["persisted_response_prefix"] = progress
    elif stage == "distribution":
        if (directory / "payload/record.json").exists():
            _row, reference = _payload_metadata(directory, point, stage)
            evidence.append(reference)
            progress = 1
    elif stage == "train":
        contract_path = directory / "binding/record.json"
        checkpoint = training.latest_window_checkpoint(Path(root) / "training", job["step"])
        if contract_path.exists():
            contract = checked(contract_path)
            require(contract["point_context_id"] == point["id"]
                    and contract["protocol_id"] == protocol["id"]
                    and contract["parent_state_digest"] == point["parent_state_digest"]
                    and contract["start_step"] == job["step"] and contract["end_step"] == job["step"] + 298
                    and contract["outer_schedule_during_window"] == [] and contract["optimizer_updates"] == 298,
                    "continuous fixed-q training binding changed")
            evidence.append(binding.entry(contract_path))
        if checkpoint is not None:
            require(contract_path.exists(), "actual train checkpoint lacks window binding")
            row = json.loads((checkpoint / "record.json").read_bytes())
            require(row["seed"] == 137 and row["arm"] == "Full"
                    and job["step"] <= row["step"] <= job["step"] + 298
                    and row["phase"] == ("outer" if row["step"] == job["step"] else "step")
                    and row["pool_id"] == point["pool_id"]
                    and row["checkpoint_contains_actual_model_Adam_RNG_pi"] is True,
                    "training cursor, actual Full state or phase changed")
            original._state_metadata(checkpoint, row)
            evidence.append(binding.file_ref(checkpoint / "record.json"))
            progress = row["step"] - job["step"] + 1  # Includes exactly one durable outer commit.
        details["durable_outer_plus_optimizer_commits"] = progress
    else:
        raise ValueError("unregistered V70 durable stage")
    complete = (directory / "result/record.json").exists()
    if complete:
        validate_result(root, job, checked(directory / "result/record.json"))
        evidence.append(binding.entry(directory / "result/record.json"))
    return dict(resume_allowed=bool(allowed and unknown == 0), unknown_calls=unknown,
        progress_units=progress, evidence=evidence, complete_stage=complete,
        full_tensor_validation_before_cold_scientific_use=True, details=details,
        durable_progress_digest=binding.digest(dict(progress_units=progress,
            evidence=[dict(path=ref["path"], sha256=ref["sha256"]) for ref in evidence])))


def validate_result(root, job, result):
    protocol = checked(Path(root) / "protocol/record.json")
    require(result["status"] == "COMPLETE" and result["protocol_id"] == protocol["id"]
            and result["job_id"] == job["job_id"] and result["seed"] == 137
            and result["step"] == job["step"] and result["stage"] == job["stage"]
            and result["model_released"] is True and result["resources"]["all_gates_passed"] is True,
            "complete result coordinate or resource contract changed")
    if job["kind"] == "generate":
        require(result["schema"] == "v70_generation_job_result.v1"
                and result["sessions"] == job["denominator"] and result["scoring_calls"] == 0
                and result["private_references_read"] is False, "evaluation dose/separation changed")
        binding.read_ref(result["whole_queue_seal"])
        return
    point = importlib.import_module("finqa_v70_training").checked_point(root, job["step"])
    require(result["schema"] == "v70_scientific_stage_result.v1"
            and result["point_context_id"] == point["id"], "result actual parameter point changed")
    if job["kind"] == "class":
        plan = binding.read_ref(point["task_plan"])
        assignment = plan["assignments"][int(job["stage"][-2:])]
        require(result["complete_class_tasks"] == len(assignment["task_ids"])
                and result["complete_class_rows"] == assignment["row_count"],
                "complete fixed task shard required")
    elif job["stage"] == "virtual_point":
        require(result["denominator"] == result["total_feedback_sessions"] == result["new_feedback_sessions"] == 700
                and result["new_feedback_sessions_is_logical_condition_total_not_new_attempt"] is True
                and type(result["new_actual_response_calls"]) is int and result["new_actual_response_calls"] >= 0
                and result["real_parent_unchanged"] is True, "one complete new 700-session condition required")
    elif job["stage"] == "replay":
        require(result["denominator"] == 700 and result["complete_replay"] is True
                and result["draw_diagnostics_passed"] is True and result["real_parent_unchanged"] is True,
                "complete original formal/draw replay diagnostics required")
    elif job["stage"] == "distribution":
        require(result["complete_class_tasks"] == 744 and result["complete_class_rows"] == 4974
                and result["draw_C_diagnostics_passed"] is True and result["real_parent_unchanged"] is True
                and result["applied"] is False, "distribution remains a same-point unapplied candidate")
    elif job["stage"] == "train":
        require((result["initial_step"], result["final_step"], result["optimizer_updates"],
                 result["new_optimizer_updates"], result["outer_updates"])
                == (job["step"], job["step"] + 298, 298, 298, 1), "exact original training window required")
        binding.read_ref(result["branch_result"])
    if result.get("payload"):
        binding.read_ref(result["payload"])


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
    """One new context in a counted class worker, after prior actual exit zero."""
    if job["kind"] != "class":
        return
    training = importlib.import_module("finqa_v70_training")
    point_root = training.point_root(root, job["step"])
    context = point_root / "context/record.json"
    if context.exists():
        return
    require(job["step"] in (1192, 1490), "initial point must be sealed during preparation")
    protocol = checked(Path(root) / "protocol/record.json")
    _accepted_previous_training(root, job["step"], protocol)
    point_root.mkdir(parents=True, exist_ok=True)
    with (point_root / "context_prepare.lock").open("a") as lock:
        while True:
            if guard.stop.requested:
                raise importlib.import_module("finqa_v70_resources").ExplicitStop(
                    "explicit stop while waiting for same-point CPU registration")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(0.2)
        if not context.exists():
            guard.check("before_actual_next_point_CPU_registration", boundary=True)
            training.prepare_point(root, job["step"], protocol["id"])
            guard.check("after_actual_next_point_CPU_registration", boundary=True)


def run(root, job, gpu_index, *, attempt_root):
    import finqa_v70_resources as resources
    directory = _job_directory(root, job)
    directory.mkdir(parents=True, exist_ok=True)
    protocol = checked(Path(root) / "protocol/record.json")
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt = checked_attempt_directory(root, job, attempt_root)
        started = time.time()
        binding.publish(attempt / "started/record.json", dict(schema="v70_actual_worker_started.v1",
            protocol_id=protocol["id"], job=job, gpu_index=gpu_index, pid=os.getpid(),
            started_epoch=started, automatic_retry_in_worker=False))
        guard = None
        try:
            if (directory / "result/record.json").exists():
                return reuse_complete_result(root, job, attempt)
            with resources.execution_context(root, job, gpu_index) as guard:
                prepare_point_for_job(root, job, guard)
                if job["kind"] == "generate":
                    body = importlib.import_module("finqa_v70_evaluation").run(
                        root, job, gpu_index, attempt, guard)
                else:
                    body = importlib.import_module("finqa_v70_runtime").execute(root, job, attempt, guard)
            result = binding.publish(directory / "result/record.json", dict(body,
                schema="v70_generation_job_result.v1" if job["kind"] == "generate"
                       else "v70_scientific_stage_result.v1",
                status="COMPLETE", protocol_id=protocol["id"], job_id=job["job_id"],
                job=job, seed=137, step=job["step"], stage=job["stage"],
                arm="Full", algorithm="Full", feedback_temperature=1.0,
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
