"""CPU-only composite acceptance of V65's already sealed public generations.

The original failed scientific exit, failure and native generation bytes remain
read-only.  A separately observed CPU exit zero accepts only the JSON envelope
repair; it never changes the original scientific process into a successful one.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import fcntl
import importlib
import os
from pathlib import Path
import signal
import sys
import time

import finqa_v67_binding as binding

GIB = 1024 ** 3
CPU_RSS_LIMIT_BYTES = 64 * GIB
HOST_RESERVE_BYTES = 96 * GIB
KNOWN_ERROR = "Object of type Episode is not JSON serializable"
require = binding.require


def _root(root):
    root = Path(root).resolve()
    require(root == Path(binding.ROOT).resolve(), "CPU repair requires its independent registered root")
    return root


def _source_root():
    return Path(binding.SOURCE_GENERATION_ROOT).resolve()


def _early():
    return binding.source_generation_module("finqa_v65_evaluation")


def _native():
    # Select byte-frozen public readers, never a model provider or checkpoint.
    binding.source_module("finqa_v63_binding").install_scientific_paths()
    return (importlib.import_module("trusted_synthesis.finance_research.storage"),
            importlib.import_module("trusted_synthesis.finance_research.v7_base_evaluation"))


def canonical_episode_payload(episode):
    return importlib.import_module("finqa_v67_evaluation").canonical_episode_payload(episode)


def canonical_episode_hash(episode):
    return importlib.import_module("finqa_v67_evaluation").canonical_episode_hash(episode)


def _checked_plan():
    early, source = _early(), _source_root()
    protocol = binding.checked(source / "protocol/record.json")
    plan = binding.checked(source / "evaluations/registration/record.json")
    science = binding.read_ref(protocol["science_protocol_ref"])
    require(protocol["id"] == binding.EARLY_PROTOCOL_ID
            and science["id"] == binding.BASE_PROTOCOL_ID
            and Path(protocol["science_protocol_ref"]["path"]).resolve() ==
            Path(binding.SCIENTIFIC_ROOT).resolve() / "protocol/record.json",
            "CPU repair requires the exact frozen original V65 and V63 protocols")
    planned = early.planned_jobs()
    require(len(planned) == 20 and sum(row["denominator"] for row in planned.values()) == 6215
            and set(plan["jobs"]) == set(planned), "only the original twenty V65 jobs may be repaired")
    require(plan["schema"] == "v65_generation_only_registration.v1"
            and plan["protocol_id"] == protocol["id"]
            and plan["scientific_protocol_id"] == science["id"]
            and plan["contract"] == protocol["evaluation"] == early.evaluation_contract()
            and plan["feedback_batch"] == 1 and plan["scoring_calls"] == 0
            and plan["private_references_read"] is False
            and plan["source_binding"] == early._implementation_binding()
            and plan["original_evaluation_source"] == science["evaluation_source_registration"]
            and plan["old_evaluation_registration"] == science["old_evaluation_registration"],
            "original V65 public registration or scientific sources changed")
    require(all(all(plan["jobs"][key].get(field) == value for field, value in job.items())
                for key, job in planned.items()), "original V65 cohort, draw or decoding changed")
    barrier = binding.read_ref(plan["training_barrier"])
    require(Path(plan["training_barrier"]["path"]).resolve() == source / "evaluations/training_barrier/record.json"
            and barrier["protocol_id"] == protocol["id"]
            and barrier["scientific_protocol_id"] == science["id"]
            and barrier["eligible_training_branches"] == protocol["eligible_training_branches"]
            and len(barrier["branches"]) == len(barrier["snapshots"]) == 5,
            "original five accepted training branches must remain bound")
    for job in plan["jobs"].values():
        coordinate = early.original.stats.coordinate(job["seed"], job["arm"])
        require(job["checkpoint"] == barrier["snapshots"][coordinate + "/step894"]
                and job["model_identity"]["point_id"] == "v63-b1-evaluation:" + binding.digest(dict(
                    protocol_id=science["id"], seed=job["seed"], arm=job["arm"], feedback_batch=1,
                    step=894, checkpoint=job["checkpoint"])),
                "CPU repair cannot change the original scientific model/checkpoint identity")
    return protocol, plan


def _same_live_identity(pid, birth):
    try:
        row = Path(f"/proc/{pid}/stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return False
    values = row[row.rfind(")") + 2:].split()
    return str(values[19]) == str(birth)


def _wait(job_id, reason):
    return dict(status="WAIT", job_id=job_id, reason=reason,
                scientific_calls=0, original_files_modified=False)


@contextmanager
def _source_lock(directory):
    # Opening read-only does not create/touch any historical artifact.
    with (directory / "worker.lock").open("r") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def eligible_source_job(root, job_id):
    """Cheap read-only eligibility; incomplete/live sources WAIT, other faults fail closed."""
    _root(root)
    protocol, plan = _checked_plan()
    require(job_id in plan["jobs"], "CPU repair cannot add or replace any of the original twenty jobs")
    job = plan["jobs"][job_id]
    directory = _source_root() / "evaluations/jobs" / job_id
    attempts = sorted((directory / "attempts").glob("attempt[0-9]*"))
    if not attempts:
        return _wait(job_id, "original generation not dispatched")
    require(len(attempts) == 1 and attempts[0].name == "attempt0001",
            "CPU sealing exception cannot adopt extra or unknown original attempts")
    attempt = attempts[0]
    launch_path, exit_path = attempt / "launch/record.json", attempt / "actual_exit/record.json"
    if not launch_path.exists():
        return _wait(job_id, "original generation launch not complete")
    launch = binding.checked(launch_path)
    require(launch["protocol_id"] == protocol["id"] and launch["attempt"] == 1
            and launch["job"]["job_id"] == job_id
            and all(launch["job"].get(k) == v for k, v in job.items()),
            "original generation launch binding changed")
    if _same_live_identity(launch["pid"], launch["birth"]):
        return _wait(job_id, "original generation process still alive or draining")
    if not exit_path.exists():
        return _wait(job_id, "original actual waitpid observation not yet published")
    actual = binding.checked(exit_path)
    require(actual["protocol_id"] == protocol["id"] and actual["job_id"] == job_id
            and actual["actual_waitpid_observed"] is True and actual["returncode"] == 1
            and actual["attempt"] == 1
            and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"]),
            "repair requires original identity-matched actual generation exit one")
    failure_path = attempt / "failure/record.json"
    require(failure_path.exists(), "exited original generation lacks the known structured sealing failure")
    failure = binding.checked(failure_path)
    require(failure["schema"] == "v63_actual_attempt_failure.v1"
            and failure["protocol_id"] == protocol["id"] and failure["pid"] == actual["pid"]
            and failure["attempt_root"] == str(attempt)
            and failure["feedback_batch"] == 1
            and all(failure["job"].get(k) == v for k, v in job.items())
            and failure["exception_type"] == "TypeError" and failure["error"] == KNOWN_ERROR
            and failure["exception_chain"] == [dict(type="TypeError", module="builtins",
                actual_errno=None, message=KNOWN_ERROR, automatic_recovery_allowed=None)],
            "only the exact post-generation Episode JSON TypeError is repairable")
    close_ref = failure["resource_closeout"]
    require(Path(close_ref["path"]).resolve() == _source_root() / "resources" / job_id /
            f"pid{actual['pid']}" / "closeout/record.json", "original resource evidence escaped its process")
    closed = binding.read_ref(close_ref)
    resources = closed["resources"]
    require(closed["status"] == "COMPLETE" and closed["protocol_id"] == protocol["id"]
            and closed["job_id"] == job_id and closed["pid"] == actual["pid"]
            and closed["birth"] == actual["birth"] and closed["error"] is None
            and datetime.fromisoformat(closed["at"]).timestamp() <= failure["finished_epoch"]
            <= actual["observed_epoch"]
            and failure["resources"] == resources and resources["all_gates_passed"] is True
            and resources["single_process_lifetime_includes_loading"] is True
            and resources.get("received_signals") == []
            and resources.get("observed_violation") is None
            and resources.get("deferred_observation") is None
            and resources["peak_allocated_bytes"] <= 76 * GIB
            and resources["peak_rss_bytes"] <= 192 * GIB
            and resources["minimum_boundary_free_bytes"] >= 2 * GIB
            and resources["minimum_host_available_bytes"] >= HOST_RESERVE_BYTES,
            "original scientific resource lifetime, stop or hard gates failed")
    generation = directory / "shards" / job["panel"] / "generation"
    native_seal_path = generation / "generation_seal/seal.json"
    require(native_seal_path.exists(), "known post-generation repair requires the complete native seal")
    native_seal = binding.checked(native_seal_path)
    require(native_seal["complete"] is True and native_seal["all_provider_calls_settled"] is True
            and native_seal["registered_denominator"] == job["denominator"]
            and len(native_seal["episodes"]) == job["denominator"],
            "incomplete or UNKNOWN native generation cannot be repaired")
    require(not (directory / "result/record.json").exists()
            and not (directory / "whole_queue_seal/record.json").exists(),
            "original complete result unexpectedly exists; no overwrite or alternate adoption")
    try:
        with _source_lock(directory):
            pass
    except BlockingIOError:
        return _wait(job_id, "original worker lock is still held")
    return dict(status="ELIGIBLE", job_id=job_id, job=job, source_directory=str(directory),
        generation_root=str(generation), original_generation_returncode=1,
        source_refs=dict(protocol=binding.entry(_source_root() / "protocol/record.json"),
            plan=binding.entry(_source_root() / "evaluations/registration/record.json"),
            launch=binding.entry(launch_path), actual_exit=binding.entry(exit_path),
            failure=binding.entry(failure_path), resource_closeout=close_ref,
            run=binding.entry(generation / "run.json"), native_seal=binding.entry(native_seal_path)))


def _assert_cpu_only():
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "", "CPU finalization must hide every CUDA device")
    torch = sys.modules.get("torch")
    require(torch is None or not torch.cuda.is_initialized(), "CPU finalization must not initialize CUDA")


def _resource_sample(label):
    _assert_cpu_only()
    # Same frozen /proc + cgroup-aware measurements used by scientific admission.
    runtime = binding.source_module("finqa_v63_runtime").controller_runtime()
    host, process = runtime.host_memory(), runtime.process_memory(os.getpid())
    require(process is not None, "CPU finalizer resource identity vanished")
    row = dict(label=label, observed_epoch=time.time(), pid=os.getpid(), host=host,
        rss_bytes=process["rss_bytes"], peak_rss_bytes=process["peak_rss_bytes"],
        rss_limit_bytes=CPU_RSS_LIMIT_BYTES, host_reserve_bytes=HOST_RESERVE_BYTES,
        CUDA_initialized=False, CUDA_VISIBLE_DEVICES="")
    row["passed"] = bool(row["peak_rss_bytes"] <= CPU_RSS_LIMIT_BYTES
                          and host["available_bytes"] >= HOST_RESERVE_BYTES)
    return row


class CPUFinalizationStopped(RuntimeError):
    pass


@contextmanager
def _stop_guard():
    def stopped(signum, _frame):
        raise CPUFinalizationStopped(f"explicit signal {signum} stopped CPU finalization")
    previous = {number: signal.signal(number, stopped) for number in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def _attempt(root, job_id, attempt_root):
    root, attempt = _root(root), Path(attempt_root).resolve()
    require(attempt == root / "repairs" / job_id / "attempt0001",
            "CPU repair has exactly one independently dispatched attempt per original job")
    return attempt


def run_cpu_repair(root, job_id, attempt_root):
    """Read and canonicalize one sealed job, never generate, score or load tensors."""
    root, attempt = _root(root), _attempt(root, job_id, attempt_root)
    _assert_cpu_only()
    protocol = binding.checked(root / "protocol/record.json")
    launch = binding.checked(attempt / "launch/record.json")
    require(launch["protocol_id"] == protocol["id"] and launch["job_id"] == job_id
            and launch["attempt"] == 1 and launch["pid"] == os.getpid()
            and launch["cuda_visible_devices"] == "", "CPU repair requires this actual dispatched launch")
    require(not (attempt / "failure/record.json").exists()
            and not (attempt / "completed/record.json").exists(),
            "an executed CPU finalization attempt cannot be reopened")
    observations = []

    def sample(label):
        row = _resource_sample(label)
        observations.append(row)
        binding.publish(attempt / "resources" / label / "record.json", row)
        require(row["passed"], "CPU finalization RSS or effective host RAM gate failed")

    try:
        with _stop_guard():
            sample("before_source_audit")
            eligible = eligible_source_job(root, job_id)
            require(eligible["status"] == "ELIGIBLE", "source is not yet eligible for CPU finalization")
            target = root / "adopted" / job_id
            require(not (target / "result/record.json").exists(), "completed CPU repair cannot run again")
            attempt.mkdir(parents=True, exist_ok=True)
            with (attempt / "worker.lock").open("a") as own, _source_lock(Path(eligible["source_directory"])):
                fcntl.flock(own, fcntl.LOCK_EX | fcntl.LOCK_NB)
                source = eligible["source_refs"]
                plan, job = binding.read_ref(source["plan"]), eligible["job"]
                require(protocol["scientific_protocol_id"] == plan["scientific_protocol_id"],
                        "CPU repair cannot change original scientific identity")
                storage, native = _native()
                require(plan["runtime_binding"] == storage.runtime_binding(), "frozen public runtime changed")
                progress = native.inspect_shard(eligible["source_directory"], dict(
                    runtime_binding=plan["runtime_binding"], config=job["config"],
                    model_identity=job["model_identity"], snapshot_id=plan["snapshot_id"]),
                    dict(key=job["panel"], task_keys=plan["cohorts"][job["role"]]["tasks"]))
                require(progress == dict(completed=job["denominator"], denominator=job["denominator"], sealed=True),
                        "original native public identity or durable completion failed")
                run, native_seal, episodes = storage.sealed_episodes(eligible["generation_root"])
                require(run["id"] == source["run"]["id"] and native_seal["id"] == source["native_seal"]["id"]
                        and run["tasks"] == plan["cohorts"][job["role"]]["tasks"]
                        and len(episodes) == job["denominator"] and run["config"] == job["config"]
                        and run["provider"] == job["model_identity"] and run["role"] == job["role"],
                        "original model, cohort, task order or Episode count changed")
                hashes = []
                for index, episode in enumerate(episodes):
                    hashes.append(canonical_episode_hash(episode))
                    if (index + 1) % 120 == 0:
                        sample(f"canonicalized_{index + 1:04d}")
                sample("after_public_native_validation")
                sealed = binding.publish(target / "whole_queue_seal/record.json", dict(
                    schema="v67_read_only_original_generation_envelope.v1", protocol_id=protocol["id"],
                    scientific_protocol_id=plan["scientific_protocol_id"], registration_id=plan["id"],
                    job_id=job_id, feedback_batch=1, checkpoint=job["checkpoint"],
                    denominator=job["denominator"], run_id=run["id"], generation_seal_id=native_seal["id"],
                    generation_seal=source["native_seal"], source_refs=source,
                    episode_sha256=hashes, episode_hash_encoding="Episode.model_dump(mode=json)",
                    all_provider_calls_settled=True, original_generation_returncode=1,
                    original_failure_preserved=True, original_generation_bytes_rewritten=False,
                    new_response_calls=0, new_API_calls=0, scoring_calls=0, private_references_read=False))
                sample("after_envelope_publication")
                resources = dict(all_gates_passed=all(row["passed"] for row in observations),
                    peak_rss_bytes=max(row["peak_rss_bytes"] for row in observations),
                    minimum_host_available_bytes=min(row["host"]["available_bytes"] for row in observations),
                    cpu_rss_limit_bytes=CPU_RSS_LIMIT_BYTES, host_reserve_bytes=HOST_RESERVE_BYTES,
                    CUDA_initialized=False, received_signals=[], observations=observations)
                binding.publish(attempt / "resource_closeout/record.json", dict(
                    schema="v67_cpu_finalization_resources.v1", protocol_id=protocol["id"], job_id=job_id,
                    pid=os.getpid(), status="COMPLETE", resources=resources))
                result = binding.publish(target / "result/record.json", dict(
                    schema="v67_cpu_finalized_generation_result.v1", protocol_id=protocol["id"],
                    scientific_protocol_id=plan["scientific_protocol_id"], registration_id=plan["id"],
                    job_id=job_id, status="COMPLETE", feedback_batch=1, sessions=job["denominator"],
                    whole_queue_seal=binding.entry(target / "whole_queue_seal/record.json"),
                    whole_queue_seal_id=sealed["id"], source_refs=source,
                    original_generation_returncode=1, original_failure_preserved=True,
                    original_scientific_resources_passed=True, cpu_resources=resources,
                    cpu_resource_closeout=binding.entry(attempt / "resource_closeout/record.json"),
                    actual_new_response_calls=0, new_API_calls=0, scoring_calls=0,
                    private_references_read=False, CPU_actual_exit_acceptance_still_required=True))
                binding.publish(attempt / "completed/record.json", dict(
                    schema="v67_cpu_finalization_completed.v1", protocol_id=protocol["id"], job_id=job_id,
                    pid=os.getpid(), result=binding.entry(target / "result/record.json"),
                    original_generation_returncode=1, new_scientific_calls=0))
                return result
    except BaseException as error:
        binding.publish(attempt / "failure/record.json", dict(
            schema="v67_cpu_finalization_failure.v1", protocol_id=protocol["id"], job_id=job_id,
            pid=os.getpid(), error=str(error), exception_type=type(error).__name__,
            observations=observations, new_scientific_calls=0, original_files_modified=False,
            automatic_retry_authorized=False))
        raise


def accept_cpu_repair(root, job_id, attempt_root):
    """Controller-only composition: original exit one plus actual CPU exit zero."""
    root, attempt = _root(root), _attempt(root, job_id, attempt_root)
    protocol = binding.checked(root / "protocol/record.json")
    launch, actual = (binding.checked(attempt / part / "record.json") for part in ("launch", "actual_exit"))
    require(launch["protocol_id"] == actual["protocol_id"] == protocol["id"]
            and launch["job_id"] == actual["job_id"] == job_id
            and launch["attempt"] == actual["attempt"] == 1
            and launch["cuda_visible_devices"] == ""
            and (launch["pid"], launch["birth"]) == (actual["pid"], actual["birth"])
            and actual["actual_waitpid_observed"] is True and actual["returncode"] == 0
            and not _same_live_identity(actual["pid"], actual["birth"]),
            "CPU envelope repair needs its separately observed identity-matched exit zero")
    require(not (attempt / "failure/record.json").exists(), "failed CPU finalization cannot be accepted")
    target = root / "adopted" / job_id
    result, completed = binding.checked(target / "result/record.json"), binding.checked(attempt / "completed/record.json")
    require(result["protocol_id"] == completed["protocol_id"] == protocol["id"]
            and result["job_id"] == completed["job_id"] == job_id
            and result["status"] == "COMPLETE" and completed["pid"] == actual["pid"]
            and binding.read_ref(completed["result"])["id"] == result["id"]
            and result["original_generation_returncode"] == 1 and result["original_failure_preserved"] is True
            and result["cpu_resources"]["all_gates_passed"] is True
            and result["cpu_resources"]["CUDA_initialized"] is False
            and result["actual_new_response_calls"] == result["new_API_calls"] == result["scoring_calls"] == 0
            and result["private_references_read"] is False,
            "CPU result must retain the known original failure and zero scientific/scoring calls")
    for reference in result["source_refs"].values():
        binding.read_ref(reference)
    closed = binding.read_ref(result["cpu_resource_closeout"])
    require(closed["status"] == "COMPLETE" and closed["pid"] == actual["pid"]
            and closed["resources"] == result["cpu_resources"], "CPU resource evidence changed")
    return binding.publish(target / "accepted/record.json", dict(
        schema="v67_composite_public_generation_acceptance.v1", protocol_id=protocol["id"],
        scientific_protocol_id=result["scientific_protocol_id"], job_id=job_id,
        result=binding.entry(target / "result/record.json"), result_id=result["id"],
        original_generation_actual_exit=result["source_refs"]["actual_exit"],
        original_generation_returncode=1, original_failure_preserved=True,
        cpu_finalization_actual_exit=binding.entry(attempt / "actual_exit/record.json"),
        cpu_finalization_returncode=0, cpu_finalization_actual_exit_zero=True,
        resources_passed=True, new_GPU_exit_required=False, new_scientific_calls=0,
        private_references_read=False, scoring_calls=0))
