"""CPU-only, one-shot V38 admission barrier for the authorized GPU6 handoff.

The frozen old controller is never edited. Existing GPU leases drain naturally;
this process acquires the SAME locks only after their current owners release
them. It signals only the old controller, only after a fresh empty queue and
actual successful exits. No worker is signalled and no experiment is launched
by this module. A caller may supply a continuation callback that runs while the
barrier is still held; without it, the sealed closeout is returned to the caller.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

OLD_GPUS = (3, 4, 5, 7)
PAUSED = "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME"
LIVE_PHASES = {"RUNNING", "WAITING_FOR_REGISTERED_RESOURCES", "WAITING_FOR_PRE_CUDA_RESOURCES"}
SCHEMA = "v39_natural_drain_handoff.v1"


class HandoffError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise HandoffError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def timestamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def epoch(value):
    result = datetime.fromisoformat(value).timestamp()
    require(math.isfinite(result), "non-finite timestamp")
    return result


def read(path):
    return json.loads(Path(path).read_bytes())


def checked(path):
    body = read(path)
    require(
        body.get("id") == digest({k: v for k, v in body.items() if k != "id"}),
        "immutable record changed: " + str(path),
    )
    return body


def ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def check_ref(value):
    require(ref(value["path"]) == value, "record reference changed: " + value["path"])
    return checked(value["path"])


def publish(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require("id" not in body, "record must not supply its own id")
    body = {**body, "id": digest(body)}
    with path.open("x") as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return body


def status(root, body):
    path = Path(root) / "status.json"
    tmp = path.with_name("status." + str(os.getpid()) + ".tmp")
    with tmp.open("w") as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def process_identity(pid):
    """A zombie is already exited; PID, birth, UID and full argv bind ownership."""
    try:
        directory = Path("/proc") / str(int(pid))
        stat = (directory / "stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == "Z":
            return None
        argv = [x.decode() for x in (directory / "cmdline").read_bytes().split(b"\0") if x]
        return dict(pid=int(pid), birth=stat[19], uid=directory.stat().st_uid, argv=argv)
    except (FileNotFoundError, ProcessLookupError):
        return None


def assert_controller_identity(expected, identity=process_identity):
    require(identity(expected["pid"]) == expected, "controller PID/birth/UID/argv changed")


def signal_controller(expected):
    """Linux pidfd closes the check-to-signal PID-reuse race."""
    require(
        hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"),
        "pidfd signalling is required; no unsafe PID-only fallback",
    )
    descriptor = os.pidfd_open(expected["pid"], 0)
    try:
        assert_controller_identity(expected)
        signal.pidfd_send_signal(descriptor, signal.SIGTERM)
    finally:
        os.close(descriptor)


def lock_path(training_root, uuid):
    # Byte-identical to the V37/V38 LeasePool namespace (JSON string digest).
    return Path(training_root) / "locks" / ("gpu-" + digest(uuid) + ".lock")


class Barrier:
    def __init__(self, training_root, gpu_uuids):
        self.paths = {int(gpu): lock_path(training_root, uuid) for gpu, uuid in gpu_uuids.items()}
        require(tuple(sorted(self.paths)) == OLD_GPUS, "barrier must cover all four OLD GPUs")
        self.held = {}

    def acquire_available(self):
        acquired = []
        for gpu in OLD_GPUS:
            if gpu in self.held:
                continue
            path = self.paths[gpu]
            require(path.parent.is_dir(), "original lock directory is missing")
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                continue
            except BaseException:
                os.close(fd)
                raise
            self.held[gpu] = fd
            acquired.append(gpu)
        return acquired

    @property
    def complete(self):
        return tuple(sorted(self.held)) == OLD_GPUS

    def close(self):
        for fd in self.held.values():
            os.close(fd)
        self.held.clear()


def launches(parent_root):
    root = Path(parent_root)
    return sorted(
        [
            *root.glob("contexts/*/*/*/*/launch/record.json"),
            *root.glob("evaluations/*/*/launch/record.json"),
        ]
    )


def stage_key(launch):
    return (launch["context_id"], launch["stage"], launch["pid"], str(launch["birth"]))


def queue_snapshot(parent_root, protocol_id):
    body = read(Path(parent_root) / "queue/status.json")
    require(body.get("protocol_id") == protocol_id, "parent queue protocol changed")
    require(isinstance(body.get("active_children"), list), "parent queue has no active list")
    require(
        math.isfinite(body["global_external_resource_wait_seconds"]),
        "unknown parent resource budget",
    )
    return body


def deadline_bound(queue, active_launches, now, resource_wait_budget, grace_seconds=600):
    remaining = resource_wait_budget - queue["global_external_resource_wait_seconds"]
    require(remaining > 0, "parent resource wait budget exhausted")
    # No active stage means no reason to invent a fresh stage budget: only the
    # original stop grace is available to reach and seal the empty boundary.
    stage_deadlines = [float(item["deadline_epoch"]) for item in active_launches]
    require(
        all(math.isfinite(x) and x > now for x in stage_deadlines),
        "an active parent stage deadline has already expired",
    )
    return min(max([now, *stage_deadlines]) + grace_seconds, now + remaining)


def register(
    root,
    *,
    parent_root,
    training_root,
    authorization,
    source_commit,
    expected_controller=None,
    deadline_epoch=None,
    now=None,
    identity=process_identity,
    freeze=True,
):
    """Register once. Production freezes the committed byte-identical script.

    ``freeze=False`` is for CPU test fixtures only; such a plan cannot use the
    command-line run path. ``deadline_epoch`` may only tighten the computed bound.
    """
    root, parent_root, training_root = map(
        lambda p: Path(p).resolve(), (root, parent_root, training_root)
    )
    now = time.time() if now is None else now
    require(not root.exists(), "handoff root already exists; no automatic retry")
    plan = checked(parent_root / "protocol/record.json")
    queue = queue_snapshot(parent_root, plan["id"])
    require(queue["phase"] in LIVE_PHASES, "parent is not a live authorized V38 episode")
    require(0 <= now - epoch(queue["at"]) <= 120, "registration requires a fresh parent queue")
    intent = checked(parent_root / "queue/run_intent/record.json")
    require(intent["protocol_id"] == plan["id"], "controller intent protocol changed")
    actual = identity(intent["pid"])
    require(
        actual is not None and actual["birth"] == str(intent["birth"]),
        "parent controller is not live with its recorded birth",
    )
    require(actual["uid"] == os.getuid(), "controller belongs to another account")
    expected_controller = actual if expected_controller is None else expected_controller
    assert_controller_identity(expected_controller, identity)
    require(expected_controller == actual, "supplied controller disagrees with run intent")
    expected_script = str(parent_root / "implementation/finqa_v38_controller.py")
    require(
        expected_script in actual["argv"]
        and "run" in actual["argv"]
        and str(parent_root) in actual["argv"],
        "not the frozen V38 controller command",
    )
    launch_record = checked(parent_root / "launch_01/record.json")
    require(
        launch_record["pid"] == actual["pid"]
        and str(launch_record["birth"]) == actual["birth"]
        and launch_record["command"] == actual["argv"],
        "controller differs from its registered full launch command",
    )
    gpu_uuids = {str(gpu): plan["gpu_uuids"][str(gpu)] for gpu in OLD_GPUS}
    require(len(set(gpu_uuids.values())) == 4, "GPU UUIDs are not unique")
    all_launches = {
        stage_key(value): (path, value)
        for path in launches(parent_root)
        for value in [checked(path)]
    }
    active = []
    for item in queue["active_children"]:
        require(stage_key(item) in all_launches, "active queue entry lacks its sealed launch")
        active.append(all_launches[stage_key(item)][1])
    budget = float(plan["resource_wait_budget_seconds"])
    bound = deadline_bound(queue, active, now, budget)
    deadline_epoch = bound if deadline_epoch is None else float(deadline_epoch)
    require(now < deadline_epoch <= bound, "handoff deadline may not extend parent budgets")
    require(
        isinstance(authorization, dict) and authorization.get("user_consent"),
        "explicit controlled-switch consent is required",
    )
    source = Path(__file__).resolve()
    raw = source.read_bytes()
    if freeze:
        repo = Path(__file__).resolve().parents[2]
        relative = "trusted_data_synthesis/scripts/finqa_v39_handoff.py"
        commit = subprocess.check_output(
            ["git", "rev-parse", source_commit + "^{commit}"], cwd=repo, text=True
        ).strip()
        committed = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=repo)
        require(raw == committed, "handoff must use committed byte-identical source")
        source_commit = commit
    root.mkdir(parents=True, exist_ok=False)
    implementation = root / "implementation/finqa_v39_handoff.py"
    implementation.parent.mkdir()
    with implementation.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    publish(
        root / "implementation/record.json",
        dict(
            schema=SCHEMA + ".implementation",
            source_commit=source_commit,
            source=ref(implementation),
            committed_source_verified=freeze,
        ),
    )
    publish(
        root / "authorization/record.json",
        dict(
            schema=SCHEMA + ".authorization",
            at=timestamp(now),
            **authorization,
        ),
    )
    body = dict(
        schema=SCHEMA,
        at=timestamp(now),
        parent_root=str(parent_root),
        training_root=str(training_root),
        parent_protocol=ref(parent_root / "protocol/record.json"),
        parent_run_intent=ref(parent_root / "queue/run_intent/record.json"),
        parent_controller_launch=ref(parent_root / "launch_01/record.json"),
        implementation=ref(root / "implementation/record.json"),
        authorization=ref(root / "authorization/record.json"),
        controller=expected_controller,
        gpu_uuids=gpu_uuids,
        initial_queue=queue,
        baseline_launches=[ref(path) for path, _ in all_launches.values()],
        initially_active_stages=[stage_key(item) for item in active],
        deadline_epoch=deadline_epoch,
        maximum_allowed_deadline_epoch=bound,
        resource_wait_budget_seconds=budget,
        queue_freshness_seconds=120,
        polling_seconds=1.0,
        workers_signalled=False,
        automatic_retry=False,
        original_budgets_reset=False,
        launches_new_experiment=False,
    )
    result = publish(root / "plan/record.json", body)
    status(root, dict(at=timestamp(now), phase="REGISTERED_NOT_STARTED", plan_id=result["id"]))
    return result


def validate_stage(path, launch, protocol_id, identity=process_identity):
    directory = Path(path).parent.parent
    require(not (directory / "failure/record.json").exists(), "observed stage recorded failure")
    result_path, exit_path = directory / "result/record.json", directory / "exit/record.json"
    if not result_path.exists() or not exit_path.exists():
        return None
    result, exited = checked(result_path), checked(exit_path)
    for value in (launch, result, exited):
        require(
            value.get("protocol_id") == protocol_id
            and value.get("context_id") == launch["context_id"]
            and value.get("stage") == launch["stage"],
            "stage protocol/context binding changed",
        )
    require(result.get("status") == "COMPLETE", "stage did not complete")
    require(
        exited.get("returncode") == 0 and exited.get("stop_requested") is False,
        "stage did not naturally exit with code zero",
    )
    require(
        result.get("gpu_uuid") == launch["gpu_uuid"]
        and result.get("gpu_index") == launch["gpu_index"],
        "stage GPU identity changed",
    )
    require(
        result.get("resources", {}).get("all_gates_passed") is True,
        "stage resource gates did not pass",
    )
    process = identity(launch["pid"])
    require(
        process is None or process["birth"] != str(launch["birth"]),
        "stage exit record exists but original worker is still alive",
    )
    return dict(launch=ref(path), result=ref(result_path), exit=ref(exit_path))


def validate_complete_class_boundaries(parent_root, protocol_id, identity=process_identity):
    """No old task cache receives new gradients after migration.

    A context with no class launch may be registered anew. Once any shard has
    launched, all four must already have immutable successful exits; a partial
    class pass is not supported by this explicitly scoped handoff.
    """
    evidence = []
    for context in sorted((Path(parent_root) / "contexts").glob("*/*/*")):
        shard_paths = [context / f"shard{index:02d}/launch/record.json" for index in range(4)]
        if not any(path.exists() for path in shard_paths):
            continue
        require(
            all(path.exists() for path in shard_paths),
            "partial class context cannot migrate; parent continues without interruption",
        )
        for path in shard_paths:
            value = validate_stage(path, checked(path), protocol_id, identity)
            require(value is not None, "class context has an unsealed shard; cannot migrate")
            evidence.append(value)
    return evidence


def run(
    root,
    *,
    stop_requested=lambda: False,
    on_quiesced=None,
    validate_quiescent=None,
    clock=time.time,
    sleep=time.sleep,
    identity=process_identity,
    send_signal=signal_controller,
    barrier_factory=Barrier,
):
    """Drain once; return the sealed closeout. Never starts/retries an experiment."""
    root = Path(root).resolve()
    plan = checked(root / "plan/record.json")
    require(plan["schema"] == SCHEMA, "wrong handoff schema")
    manifest = check_ref(plan["implementation"])
    require(ref(manifest["source"]["path"]) == manifest["source"], "frozen handoff source changed")
    require(
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == manifest["source"]["sha256"],
        "executing handoff source differs from the registered implementation",
    )
    check_ref(plan["authorization"])
    parent = check_ref(plan["parent_protocol"])
    check_ref(plan["parent_run_intent"])
    check_ref(plan["parent_controller_launch"])
    parent_root = Path(plan["parent_root"])
    intent = publish(
        root / "run_intent/record.json",
        dict(
            schema=SCHEMA + ".run",
            at=timestamp(clock()),
            plan_id=plan["id"],
            pid=os.getpid(),
            identity=process_identity(os.getpid()),
            automatic_retry=False,
        ),
    )
    barrier = barrier_factory(plan["training_root"], plan["gpu_uuids"])
    baseline = {item["path"]: item for item in plan["baseline_launches"]}
    active_keys = {tuple(x) for x in plan["initially_active_stages"]}
    observed, verified, events = {}, {}, 0
    all_locks_epoch = None
    signal_sent = False
    signal_epoch = None
    callback_invoked = False

    def event(phase, **extra):
        nonlocal events
        events += 1
        value = dict(
            schema=SCHEMA + ".event",
            at=timestamp(clock()),
            plan_id=plan["id"],
            phase=phase,
            barrier_gpus=sorted(barrier.held),
            **extra,
        )
        publish(root / f"events/event{events:06d}/record.json", value)
        status(
            root,
            {
                **value,
                "observed_stages": len(observed),
                "verified_stages": len(verified),
                "controller_signalled": signal_sent,
                "workers_signalled": False,
            },
        )

    def gate():
        require(not stop_requested(), "handoff stop requested; no migration")
        require(clock() < plan["deadline_epoch"], "handoff deadline expired; no migration")

    def observe(queue):
        require(
            queue["global_external_resource_wait_seconds"] < plan["resource_wait_budget_seconds"],
            "parent resource wait budget exhausted; no migration",
        )
        for path in launches(parent_root):
            path_string = str(path.resolve())
            if path_string in observed:
                continue
            launch = checked(path)
            require(launch.get("protocol_id") == parent["id"], "unexpected stage protocol")
            if path_string in baseline and stage_key(launch) not in active_keys:
                require(ref(path) == baseline[path_string], "baseline launch changed")
                # A launch can be newer than the last parent heartbeat; include
                # every baseline stage without an exit, even if not listed active.
                if (path.parent.parent / "exit/record.json").exists():
                    continue
            observed[path_string] = launch
            event("STAGE_OBSERVED", launch=ref(path))
        keys = {stage_key(x) for x in observed.values()}
        for item in queue["active_children"]:
            require(
                stage_key(item) in keys, "fresh active worker is not bound to an observed launch"
            )
        for path_string, launch in observed.items():
            if path_string in verified:
                continue
            value = validate_stage(path_string, launch, parent["id"], identity)
            if value is not None:
                verified[path_string] = value
                event("STAGE_NATURALLY_EXITED", evidence=value)

    try:
        event("ACQUIRING_ADMISSION_BARRIER")
        while True:
            gate()
            queue = queue_snapshot(parent_root, parent["id"])
            require(
                queue["phase"] in LIVE_PHASES, "parent stopped or failed before handoff boundary"
            )
            assert_controller_identity(plan["controller"], identity)
            observe(queue)
            acquired = barrier.acquire_available()
            if acquired:
                event("ADMISSION_LOCKS_ACQUIRED", newly_acquired_gpus=acquired)
            if barrier.complete and all_locks_epoch is None:
                all_locks_epoch = clock()
                event("ALL_ADMISSION_LOCKS_HELD", all_locks_epoch=all_locks_epoch)
            queue_time = epoch(queue["at"])
            fresh = 0 <= clock() - queue_time <= plan["queue_freshness_seconds"]
            if (
                barrier.complete
                and fresh
                and queue_time > all_locks_epoch
                and not queue["active_children"]
                and len(verified) == len(observed)
            ):
                # A new fresh read after all checks guards queue transition; with
                # all old GPU locks held, no additional stage may be dispatched.
                final_queue = queue_snapshot(parent_root, parent["id"])
                require(
                    final_queue["phase"] in LIVE_PHASES
                    and not final_queue["active_children"]
                    and epoch(final_queue["at"]) >= queue_time,
                    "parent queue changed before signal",
                )
                observe(final_queue)
                require(len(verified) == len(observed), "new unverified stage appeared")
                class_boundaries = validate_complete_class_boundaries(
                    parent_root, parent["id"], identity
                )
                if validate_quiescent is not None:
                    validate_quiescent(plan, final_queue)
                gate()
                final_queue = queue_snapshot(parent_root, parent["id"])
                require(
                    final_queue["phase"] in LIVE_PHASES
                    and not final_queue["active_children"]
                    and epoch(final_queue["at"]) > all_locks_epoch
                    and 0 <= clock() - epoch(final_queue["at"]) <= plan["queue_freshness_seconds"]
                    and final_queue["global_external_resource_wait_seconds"]
                    < plan["resource_wait_budget_seconds"],
                    "parent ceased to be freshly quiescent during migration preflight",
                )
                assert_controller_identity(plan["controller"], identity)
                event(
                    "ZERO_WORKER_SIGNAL_INTENT",
                    queue=final_queue,
                    controller=plan["controller"],
                    verified_stages=list(verified.values()),
                    complete_class_boundaries=class_boundaries,
                )
                send_signal(plan["controller"])
                signal_sent, signal_epoch = True, clock()
                event("CONTROLLER_SIGTERM_SENT", signal_epoch=signal_epoch)
                break
            status(
                root,
                dict(
                    at=timestamp(clock()),
                    phase="DRAINING_NATURALLY",
                    plan_id=plan["id"],
                    barrier_gpus=sorted(barrier.held),
                    parent_queue_at=queue["at"],
                    parent_active=queue["active_children"],
                    observed_stages=len(observed),
                    verified_stages=len(verified),
                    deadline_epoch=plan["deadline_epoch"],
                    workers_signalled=False,
                ),
            )
            sleep(min(plan["polling_seconds"], max(0, plan["deadline_epoch"] - clock())))

        while True:
            gate()
            require(
                clock() < signal_epoch + 600,
                "controller did not exit within the original 600-second stop grace",
            )
            queue = queue_snapshot(parent_root, parent["id"])
            require(not queue["active_children"], "parent launched a worker behind the barrier")
            require(
                queue["phase"] in LIVE_PHASES | {"SAFE_BOUNDARY_STOP_REQUESTED", PAUSED},
                "parent failed during controlled pause",
            )
            actual = identity(plan["controller"]["pid"])
            if actual is not None:
                require(actual == plan["controller"], "controller identity changed during exit")
            if actual is None and queue["phase"] == PAUSED:
                require(
                    epoch(queue["at"]) >= signal_epoch, "paused queue is older than handoff signal"
                )
                failure = checked(parent_root / "failure/record.json")
                require(
                    failure.get("phase") == PAUSED
                    and failure.get("protocol_id") == parent["id"]
                    and failure.get("error_type") == "DurablePause"
                    and failure.get("error") == "explicit safe stop requested"
                    and failure.get("stop_error") is None
                    and failure.get("actual_progress_audit_error") is None,
                    "parent did not record the requested clean durable pause",
                )
                progress = checked(parent_root / "actual_final_progress/record.json")
                elapsed = clock() - epoch(plan["at"])
                final_wait = max(
                    queue["global_external_resource_wait_seconds"],
                    plan["initial_queue"]["global_external_resource_wait_seconds"] + elapsed,
                )
                require(
                    final_wait < plan["resource_wait_budget_seconds"],
                    "conservative handoff resource wait budget exhausted",
                )
                closeout = publish(
                    root / "closeout/record.json",
                    dict(
                        schema=SCHEMA + ".closeout",
                        at=timestamp(clock()),
                        status="COMPLETE",
                        plan_id=plan["id"],
                        run_intent_id=intent["id"],
                        parent_root=str(parent_root),
                        parent_protocol_id=parent["id"],
                        parent_protocol=plan["parent_protocol"],
                        parent_final_queue=queue,
                        parent_pause=ref(parent_root / "failure/record.json"),
                        actual_progress=ref(parent_root / "actual_final_progress/record.json"),
                        actual_progress_id=progress["id"],
                        all_old_gpu_locks_held=True,
                        controller_exited=True,
                        children_exited=True,
                        controller_real_exit_observed=True,
                        controller_returncode=None,
                        controller_returncode_observable=False,
                        exit_code_observed=False,
                        workers_signalled=False,
                        observed_stages=list(verified.values()),
                        original_budgets_reset=False,
                        complete_class_boundaries=class_boundaries,
                        elapsed_handoff_wall_seconds=elapsed,
                        global_resource_wait_seconds=final_wait,
                        resource_wait_accounting=(
                            "max(parent_final_wait, parent_initial_wait + entire_handoff_wall); "
                            "conservative overcharge includes periods with active workers"
                        ),
                        continuation_started=False,
                        automatic_retry=False,
                    ),
                )
                event("QUIESCED", closeout=ref(root / "closeout/record.json"))
                if on_quiesced is not None:
                    gate()
                    event("EXPLICIT_CONTINUATION_CALLBACK_INTENT")
                    callback_invoked = True
                    released = False

                    def release_barrier(
                        parent_wait=queue["global_external_resource_wait_seconds"],
                    ):
                        nonlocal released
                        require(not released, "barrier release is single-use")
                        gate()
                        charged_wait = max(
                            parent_wait,
                            plan["initial_queue"]["global_external_resource_wait_seconds"]
                            + clock()
                            - epoch(plan["at"]),
                        )
                        require(
                            charged_wait < plan["resource_wait_budget_seconds"],
                            "handoff callback initialization exhausted resource wait budget",
                        )
                        billing = publish(
                            root / "barrier_release/record.json",
                            dict(
                                schema=SCHEMA + ".release",
                                at=timestamp(clock()),
                                plan_id=plan["id"],
                                global_resource_wait_seconds=charged_wait,
                                initialization_wall_charged=True,
                                original_budgets_reset=False,
                            ),
                        )
                        barrier.close()
                        released = True
                        event("BARRIER_RELEASED_AFTER_CLEAN_PAUSE")
                        return billing

                    callback_result = on_quiesced(closeout, release_barrier)
                    publish(
                        root / "continuation_callback/record.json",
                        dict(
                            schema=SCHEMA + ".callback",
                            at=timestamp(clock()),
                            plan_id=plan["id"],
                            result=callback_result,
                            automatic_retry=False,
                        ),
                    )
                    event("EXPLICIT_CONTINUATION_CALLBACK_RETURNED")
                return closeout
            sleep(min(plan["polling_seconds"], max(0, plan["deadline_epoch"] - clock())))
    except BaseException as error:
        phase = (
            "CONTINUATION_CALLBACK_ERROR_NO_RETRY" if callback_invoked else "STOPPED_NO_MIGRATION"
        )
        event(
            phase,
            error_type=type(error).__name__,
            error=str(error),
            controller_signalled=signal_sent,
            automatic_retry=False,
            new_experiment_started_by_handoff=False,
            continuation_callback_invoked=callback_invoked,
        )
        publish(
            root / "failure/record.json",
            dict(
                schema=SCHEMA + ".failure",
                at=timestamp(clock()),
                plan_id=plan["id"],
                status=phase,
                error_type=type(error).__name__,
                error=str(error),
                controller_signalled=signal_sent,
                workers_signalled=False,
                new_experiment_started_by_handoff=False,
                continuation_callback_invoked=callback_invoked,
                automatic_retry=False,
            ),
        )
        raise
    finally:
        barrier.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    registration = sub.add_parser("register")
    registration.add_argument("--root", type=Path, required=True)
    registration.add_argument("--parent-root", type=Path, required=True)
    registration.add_argument("--training-root", type=Path, required=True)
    registration.add_argument("--authorization-json", type=Path, required=True)
    registration.add_argument("--source-commit", required=True)
    registration.add_argument("--deadline-epoch", type=float)
    execution = sub.add_parser("run")
    execution.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        result = register(
            args.root,
            parent_root=args.parent_root,
            training_root=args.training_root,
            authorization=read(args.authorization_json),
            source_commit=args.source_commit,
            deadline_epoch=args.deadline_epoch,
        )
    else:
        plan = checked(args.root / "plan/record.json")
        manifest = check_ref(plan["implementation"])
        require(manifest["committed_source_verified"] is True, "test fixture cannot run production")
        require(
            Path(__file__).resolve() == Path(manifest["source"]["path"]),
            "run only the frozen registered handoff",
        )
        stopped = False

        def stop(*_):
            nonlocal stopped
            stopped = True

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, stop)
        result = run(args.root, stop_requested=lambda: stopped)
    print(json.dumps(dict(id=result["id"], status=result.get("status", "REGISTERED"))))


if __name__ == "__main__":
    main()
