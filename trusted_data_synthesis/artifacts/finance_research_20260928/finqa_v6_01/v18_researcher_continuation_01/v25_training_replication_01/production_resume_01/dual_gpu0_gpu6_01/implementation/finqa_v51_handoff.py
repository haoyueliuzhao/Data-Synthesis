"""Pinned GPU0 natural boundary for the independent two-device successor.

Only the old GPU0 lease is acquired when its previous owner releases it.
Cancellation or a failed preflight releases it without stopping the old run.
After a fresh empty queue and independently verified successful worker
exits, one pidfd signal goes to the pinned old supervisor. Its real controller
exit receipt is required before a callback may initialize the independent run.
"""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import math
import os
import sys
import time
from pathlib import Path


def _load_primitives():
    name = __name__ + "_sealed_v41_primitives"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v41_handoff.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = _load_primitives()

SCHEMA = "v51_pinned_natural_two_gpu_handoff.v1"
PINNED_PROTOCOL_ID = "bd19014d33e034cc7b64b25bd919f9e332dadff65b934b2e89b70aaae300c912"
PINNED_CONTROLLER = dict(pid=1782931, birth="455286765")
PINNED_SUPERVISOR = dict(pid=1782886, birth="455286621")
PRODUCTION = base.SOURCE_ROOT / "production_resume_01"
PARENT_ROOT = PRODUCTION / "single_gpu0_01"
ROOT = PRODUCTION / "dual_gpu0_gpu6_01"
GPUS = (0,)
SUCCESSOR_GPUS = (0, 6)
SHUTDOWN_GRACE_SECONDS = 600
require, checked, publish = base.require, base.checked, base.publish
process_identity, signal_supervisor = base.process_identity, base.signal_controller


class Barrier:
    """Only GPU0 belonged to the old run; never reserve successor GPU6 here."""

    def __init__(self, training_root, gpu_uuids):
        require(set(gpu_uuids) == {"0"}, "old V50 barrier must cover GPU0 only")
        self.paths = {0: base.lock_path(training_root, gpu_uuids["0"])}
        self.held = {}

    def acquire_available(self):
        if self.complete:
            return []
        path = self.paths[0]
        require(path.parent.is_dir(), "original GPU0 lock directory missing")
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            return []
        except BaseException:
            os.close(descriptor)
            raise
        self.held[0] = descriptor
        return [0]

    @property
    def complete(self):
        return tuple(sorted(self.held)) == GPUS

    def close(self):
        for descriptor in self.held.values():
            os.close(descriptor)
        self.held.clear()


def entry(path):
    return dict(base.ref(path), id=checked(path)["id"])


def _same_launch(record, expected):
    return record.get("pid") == expected["pid"] and str(record.get("birth")) == str(
        expected["birth"]
    )


def _exited(expected, identity):
    actual = identity(expected["pid"])
    return actual is None or str(actual["birth"]) != str(expected["birth"])


def _runtime_sources(root):
    root = Path(root).resolve()
    for path in (Path(__file__).resolve(), Path(base.__file__).resolve()):
        require(
            path == root / "implementation" / path.name,
            "handoff must use its actual frozen source paths",
        )


def _fresh_queue(spec, clock):
    queue = base.queue_snapshot(spec["parent_root"], spec["parent_protocol_id"])
    require(-1 <= clock() - base.epoch(queue["at"]) <= 60, "parent queue is not fresh")
    return queue


def _pinned_live(spec, identity, clock):
    parent = Path(spec["parent_root"])
    require(
        base.check_ref(spec["parent_protocol"])["id"] == spec["parent_protocol_id"],
        "parent protocol changed",
    )
    base.check_ref(spec["controller_launch"])
    base.check_ref(spec["supervisor_launch"])
    base.check_ref(spec["supervisor_dispatch"])
    for key in ("controller_identity", "supervisor_identity"):
        require(
            identity(spec[key]["pid"]) == spec[key], "pinned supervisor/controller identity changed"
        )
    status = base.read(parent / "supervisor/queue/status.json")
    child = status.get("child", {})
    require(
        status.get("phase") == "RUNNING"
        and status.get("attempt_number") == 1
        and status.get("attempt_root") == str(parent)
        and status.get("manual_stop_requested") is False
        and _same_launch(child, spec["controller_identity"]),
        "supervisor changed attempt or received a stop; handoff cannot follow it",
    )
    require(
        not (parent / "failure/record.json").exists()
        and not (parent / "supervisor/failure/record.json").exists(),
        "parent failure stops handoff without migration",
    )
    queue = _fresh_queue(spec, clock)
    require(queue["phase"] in base.LIVE_PHASES, "parent is not a live original attempt")
    return queue


def register(
    root,
    parentroot,
    authorization_ref,
    *,
    expected_supervisor=None,
    expected_controller=None,
    identity=process_identity,
    freeze=True,
    clock=time.time,
):
    root, parent = Path(root).resolve(), Path(parentroot).resolve()
    if freeze:
        require(
            root == ROOT and parent == PARENT_ROOT, "fixed independent V51 handoff scope required"
        )
        _runtime_sources(root)
        capability = base.verify_pidfd_capability()
    else:
        capability = dict(cpu_mock_only=True, signals_sent=0)
    authority = base.check_ref(authorization_ref)
    require(
        bool(authority.get("user_consent"))
        and authority.get("max_gpu_workers") == 2
        and authority.get("max_workers_per_gpu") == 1
        and authority.get("allowed_gpu_indices") == list(SUCCESSOR_GPUS),
        "explicit new two-device/two-worker handoff authorization required",
    )
    protocol = checked(parent / "protocol/record.json")
    require(
        protocol["id"] == PINNED_PROTOCOL_ID
        and protocol["output_root"] == str(parent)
        and protocol["allowed_gpu_indices"] == list(GPUS)
        and protocol["schema"] == "v50_single_gpu0_supervised_protocol.v1"
        and protocol["supervision_root"] == str(parent)
        and protocol["max_gpu_workers"] == 1
        and protocol["max_workers_per_gpu"] == 1
        and set(protocol["gpu_uuids"]) == {"0"},
        "initial pinned V50 protocol changed",
    )
    controller_launch = checked(parent / "launch_01/record.json")
    supervisor_launch = checked(parent / "supervisor/launch/record.json")
    dispatch = checked(parent / "supervisor/attempt0001/dispatch/record.json")
    expected_controller = expected_controller or PINNED_CONTROLLER
    expected_supervisor = expected_supervisor or PINNED_SUPERVISOR
    require(
        _same_launch(controller_launch, expected_controller)
        and _same_launch(supervisor_launch, expected_supervisor),
        "registered parent process changed",
    )
    controller = identity(controller_launch["pid"])
    supervisor = identity(supervisor_launch["pid"])
    require(
        controller is not None
        and supervisor is not None
        and _same_launch(controller, controller_launch)
        and _same_launch(supervisor, supervisor_launch)
        and controller["uid"] == supervisor["uid"] == os.getuid(),
        "live parent ownership differs",
    )
    require(
        controller_launch["protocol_id"] == protocol["id"]
        and supervisor_launch["protocol"] == entry(parent / "protocol/record.json")
        and _same_launch(dispatch, controller_launch)
        and dispatch["attempt_number"] == 1
        and dispatch["attempt_root"] == str(parent)
        and controller["argv"] == controller_launch["command"] == dispatch["command"],
        "controller live command differs from its actual launch and supervisor dispatch",
    )
    command = controller["argv"]
    require(
        len(command) == 6
        and command[1:]
        == [
            "-u",
            str(parent / "implementation/finqa_v50_controller.py"),
            "run",
            "--root",
            str(parent),
        ]
        and supervisor["argv"]
        == [
            command[0],
            "-u",
            str(parent / "implementation/finqa_v50_supervisor.py"),
            "run",
            "--root",
            str(parent),
        ],
        "pinned process command is not the original V50 script/action/root",
    )
    if supervisor_launch.get("command") is not None:
        require(
            supervisor["argv"] == supervisor_launch["command"], "supervisor launch command changed"
        )
    body = dict(
        schema=SCHEMA,
        at=base.timestamp(clock()),
        root=str(root),
        parent_root=str(parent),
        parent_protocol=entry(parent / "protocol/record.json"),
        parent_protocol_id=protocol["id"],
        controller_launch=entry(parent / "launch_01/record.json"),
        supervisor_launch=entry(parent / "supervisor/launch/record.json"),
        supervisor_dispatch=entry(parent / "supervisor/attempt0001/dispatch/record.json"),
        controller_identity=controller,
        supervisor_identity=supervisor,
        authorization=authorization_ref,
        gpu_uuids=protocol["gpu_uuids"],
        training_root=protocol["training_root"],
        mode="pinned_natural_lease_drain",
        new_max_gpu_workers=2,
        new_allowed_gpu_indices=list(SUCCESSOR_GPUS),
        old_scope_gpu_indices=list(GPUS),
        extra_device_lease_acquired_by_handoff=False,
        cancellation_does_not_stop_old_execution=True,
        worker_signals_allowed=False,
        no_attempt_following=True,
        deadline_epoch=None,
        resource_wait_limit_seconds=None,
        shutdown_grace_seconds=SHUTDOWN_GRACE_SECONDS,
        unfinished_unlaunched_class_shards_may_migrate=True,
        pidfd_capability=capability,
        parent_scientific_files_modified=False,
    )
    queue = _pinned_live(body, identity, clock)
    body["initial_active_children"] = queue["active_children"]
    body["initial_parent_resource_wait_seconds"] = queue["global_external_resource_wait_seconds"]
    return publish(root / "handoff_01/protocol/record.json", body)


def _worker_receipts(spec, identity, *, complete_cache=None):
    complete_cache = {} if complete_cache is None else complete_cache
    complete = []
    for path in base.launches(spec["parent_root"]):
        key = str(path)
        if key in complete_cache:
            complete.append(complete_cache[key])
            continue
        launch = checked(path)
        require(launch["protocol_id"] == spec["parent_protocol_id"], "foreign launched worker")
        directory = path.parent.parent
        exit_path = directory / "exit/record.json"
        if exit_path.exists():
            exit_record = checked(exit_path)
            require(
                exit_record["returncode"] == 0 and exit_record["stop_requested"] is False,
                "a worker failed or was stopped; release handoff locks",
            )
        receipt = base.validate_stage(path, launch, spec["parent_protocol_id"], identity)
        if receipt is not None:
            complete_cache[key] = receipt
            complete.append(receipt)
    return complete


def _wait_for_exit(spec, identity, monotonic, sleep, *, started):
    while not all(
        _exited(spec[key], identity) for key in ("controller_identity", "supervisor_identity")
    ):
        require(
            monotonic() - started <= SHUTDOWN_GRACE_SECONDS,
            "pinned supervisor/controller did not exit within shutdown grace",
        )
        sleep(1)


def _stopped_parent_evidence(spec):
    parent = Path(spec["parent_root"])
    actual_exit = checked(parent / "supervisor/attempt0001/actual_exit/record.json")
    supervisor_closeout = checked(parent / "supervisor/closeout/record.json")
    queue = base.queue_snapshot(parent, spec["parent_protocol_id"])
    require(
        actual_exit["attempt_number"] == 1
        and actual_exit["attempt_root"] == str(parent)
        and _same_launch(actual_exit, spec["controller_identity"])
        and actual_exit["returncode"] == 1
        and actual_exit["manual_stop_requested"] is True
        and actual_exit["stop_forwarded"] is True,
        "missing actual legal-stop controller exit receipt; do not invent exit0",
    )
    require(
        supervisor_closeout["status"] == "STOPPED_BY_EXPLICIT_REQUEST"
        and supervisor_closeout["final_attempt"] == 1
        and supervisor_closeout["received_signals"] == [15]
        and supervisor_closeout["automatic_recovery_after_manual_stop"] is False,
        "old supervisor did not terminate its automatic restart authority",
    )
    require(
        queue["phase"] == "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME"
        and queue["active_children"] == [],
        "old controller did not preserve a clean empty boundary",
    )
    failure = checked(parent / "failure/record.json")
    require(
        failure["phase"] == queue["phase"]
        and failure["error_type"] == "DurablePause"
        and failure["error"] == "explicit safe stop requested"
        and failure["stop_error"] is None
        and failure["actual_progress_audit_error"] is None,
        "scientific failure cannot be relabelled as a clean handoff",
    )
    progress = checked(parent / "actual_final_progress/record.json")
    require(
        progress["endpoint_scores_or_answers_read"] is False
        and progress["original_state_or_feedback_modified"] is False,
        "old final actual-state audit is not read-only",
    )
    return dict(
        actual_progress=entry(parent / "actual_final_progress/record.json"),
        parent_final_queue=base.ref(parent / "queue/status.json"),
        supervisor_actual_controller_exit=entry(
            parent / "supervisor/attempt0001/actual_exit/record.json"
        ),
        supervisor_closeout=entry(parent / "supervisor/closeout/record.json"),
        global_resource_wait_seconds=math.ceil(queue["global_external_resource_wait_seconds"]),
    )


def clean_receipt_body(root, spec, *, elapsed_seconds, at=None):
    """Produce the real pinned-attempt receipt after independently observed exit.

    This only reads and checks final evidence. The caller must already own the
    GPU0 barrier and have observed both original processes exit; it cannot stop
    or launch anything, and does not generalize to another parent attempt.
    """
    require(
        type(elapsed_seconds) in (int, float)
        and math.isfinite(elapsed_seconds)
        and elapsed_seconds >= 0,
        "finite nonnegative handoff elapsed time required",
    )
    directory = Path(root).resolve() / "handoff_01"
    evidence = _stopped_parent_evidence(spec)
    return dict(
        schema="v51_clean_handoff_receipt.v1",
        status="CLEAN_NATURAL_HANDOFF",
        at=base.timestamp(time.time()) if at is None else at,
        parent_root=spec["parent_root"],
        parent_attempt_root=spec["parent_root"],
        parent_supervision_root=spec["parent_root"],
        parent_protocol=spec["parent_protocol"],
        controller_launch=spec["controller_launch"],
        supervisor_launch=spec["supervisor_launch"],
        preflight=entry(directory / "preflight/record.json"),
        worker_signals_sent=0,
        barrier_acquired=entry(directory / "barrier_acquired/record.json"),
        empty_queue_observed_after_barrier=True,
        supervisor_signal_sent=True,
        supervisor_signals_sent=1,
        all_gpu_locks_held=list(GPUS),
        fresh_empty_queue_verified=True,
        controller_original_process_exited=True,
        supervisor_original_process_exited=True,
        supervisor_os_exit_code_observed=False,
        handoff_elapsed_seconds=elapsed_seconds,
        handoff_elapsed_not_added_again_to_parent_wait=True,
        **evidence,
    )


def run(
    root,
    *,
    validate_quiescent,
    on_quiesced=None,
    stop_requested=lambda: False,
    clock=time.time,
    monotonic=time.monotonic,
    sleep=time.sleep,
    identity=process_identity,
    send_signal=signal_supervisor,
    barrier_factory=Barrier,
):
    root = Path(root).resolve()
    _runtime_sources(root)
    directory = root / "handoff_01"
    spec = checked(directory / "protocol/record.json")
    require(spec["schema"] == SCHEMA and spec["root"] == str(root), "unregistered handoff entry")
    base.check_ref(spec["authorization"])
    with (directory / "owner.lock").open("a") as ownership:
        fcntl.flock(ownership, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "launch/record.json").exists(), "one handoff attempt only")
        publish(
            directory / "launch/record.json",
            dict(
                schema="v51_natural_handoff_launch.v1",
                at=base.timestamp(clock()),
                pid=os.getpid(),
                birth=process_identity(os.getpid())["birth"],
                protocol=entry(directory / "protocol/record.json"),
                worker_signals_sent=0,
            ),
        )
        barrier = barrier_factory(spec["training_root"], spec["gpu_uuids"])
        started, sent, closeout, shutdown_started = monotonic(), False, None, None
        signal_attempted, barrier_acquired_epoch, barrier_released = False, None, False
        complete_worker_receipts = {}

        def release_barrier_once():
            nonlocal barrier_released
            require(
                not barrier_released and barrier.complete,
                "handoff barrier release must occur exactly once",
            )
            require(not stop_requested(), "explicit stop before barrier release")
            before = clock()
            barrier.close()
            barrier_released = True
            publish(
                directory / "barrier_release/record.json",
                dict(
                    schema="v51_single_successor_barrier_release.v1",
                    at=base.timestamp(clock()),
                    release_started_at=base.timestamp(before),
                    released_gpu_locks=list(GPUS),
                    closeout=entry(directory / "closeout/record.json"),
                    release_count=1,
                    stop_requested_after_release=bool(stop_requested()),
                    scientific_worker_dispatched_by_handoff=False,
                ),
            )
            require(not stop_requested(), "explicit stop arrived during barrier release")

        try:
            while True:
                require(not stop_requested(), "explicit stop requested before handoff")
                queue = _pinned_live(spec, identity, clock)
                _worker_receipts(spec, identity, complete_cache=complete_worker_receipts)
                barrier.acquire_available()
                if barrier.complete and barrier_acquired_epoch is None:
                    barrier_acquired_epoch = clock()
                    publish(
                        directory / "barrier_acquired/record.json",
                        dict(
                            schema="v51_old_scope_gpu0_lease_acquired.v1",
                            at=base.timestamp(barrier_acquired_epoch),
                            acquired_epoch=barrier_acquired_epoch,
                            all_gpu_locks_held=list(GPUS),
                        ),
                    )
                base.status(
                    directory,
                    dict(
                        phase="DRAINING_NATURALLY",
                        at=base.timestamp(clock()),
                        barrier_gpus=sorted(barrier.held),
                        active_children=queue["active_children"],
                        worker_signals_sent=0,
                        supervisor_signals_sent=0,
                        deadline_epoch=None,
                    ),
                )
                if (
                    not barrier.complete
                    or queue["active_children"]
                    or base.epoch(queue["at"]) <= barrier_acquired_epoch
                ):
                    sleep(2)
                    continue
                # Independent fresh receipts prevent an empty/stale queue from
                # disguising a live, failed, or incompletely sealed worker.
                receipts = _worker_receipts(spec, identity)
                require(
                    len(receipts) == len(base.launches(spec["parent_root"])),
                    "every launched worker must have a complete successful exit receipt",
                )
                audit = validate_quiescent(Path(spec["parent_root"]), queue)
                require(
                    audit["status"] == "CLEAN_NATURAL_WORKER_BOUNDARY"
                    and audit["parent_protocol"] == spec["parent_protocol"]
                    and audit["launched_workers_all_complete_and_exit_zero"] is True
                    and audit["worker_signals_sent"] == 0,
                    "unsafe quiescent boundary",
                )
                publish(
                    directory / "preflight/record.json",
                    dict(
                        schema="v51_held_barrier_quiescent_preflight.v1",
                        at=base.timestamp(clock()),
                        all_gpu_locks_held=list(GPUS),
                        **audit,
                    ),
                )
                require(not stop_requested(), "explicit stop requested before supervisor signal")
                latest = _pinned_live(spec, identity, clock)
                require(
                    barrier.complete
                    and latest["active_children"] == []
                    and base.epoch(latest["at"]) > barrier_acquired_epoch,
                    "empty queue must be newer than the complete barrier acquisition",
                )
                signal_attempted = True
                shutdown_started = monotonic()
                send_signal(spec["supervisor_identity"])
                sent = True
                publish(
                    directory / "supervisor_signal/record.json",
                    dict(
                        schema="v51_verified_supervisor_pidfd_stop.v1",
                        at=base.timestamp(clock()),
                        target=spec["supervisor_identity"],
                        signals_sent=1,
                        worker_signals_sent=0,
                        all_gpu_locks_held=list(GPUS),
                        pidfd_only=True,
                    ),
                )
                _wait_for_exit(spec, identity, monotonic, sleep, started=shutdown_started)
                require(barrier.complete, "handoff barrier lost before parent exit verification")
                closeout = publish(
                    directory / "closeout/record.json",
                    clean_receipt_body(
                        root,
                        spec,
                        elapsed_seconds=max(0.0, monotonic() - started),
                        at=base.timestamp(clock()),
                    ),
                )
                require(
                    not stop_requested(),
                    "explicit stop after clean handoff; no new science may start",
                )
                base.status(
                    directory,
                    dict(
                        phase="CLEAN_NATURAL_HANDOFF",
                        at=base.timestamp(clock()),
                        barrier_gpus=sorted(barrier.held),
                        worker_signals_sent=0,
                        supervisor_signals_sent=1,
                    ),
                )
                if on_quiesced is not None:
                    return on_quiesced(closeout, release_barrier_once)
                return closeout
        except BaseException as error:
            if signal_attempted and not all(
                _exited(spec[key], identity)
                for key in ("controller_identity", "supervisor_identity")
            ):
                # Keep the barrier while the already-signalled parent shuts down;
                # releasing it early could permit a final unwanted dispatch.
                try:
                    _wait_for_exit(spec, identity, monotonic, sleep, started=shutdown_started)
                except BaseException as cleanup:
                    error.add_note("parent shutdown: " + str(cleanup))
            body = dict(
                schema="v51_handoff_stopped_no_retry.v1",
                at=base.timestamp(clock()),
                status=(
                    "STOPPED_AFTER_CLEAN_HANDOFF"
                    if closeout
                    else "STOPPED_AFTER_PARENT_SIGNAL_NO_SUCCESSOR"
                    if signal_attempted
                    else "STOPPED_NO_MIGRATION"
                ),
                error_type=type(error).__name__,
                error=str(error),
                worker_signals_sent=0,
                supervisor_signals_sent=1 if sent else None if signal_attempted else 0,
                supervisor_signal_attempted=signal_attempted,
                old_execution_left_running_if_not_signalled=not signal_attempted,
                no_cleanup_signal_sent=True,
                automatic_retry=False,
                handoff_itself_never_launches_scientific_workers=True,
            )
            successor_refs = {}
            for name, relative in (
                ("supervisor_launch", "supervisor/launch/record.json"),
                ("controller_dispatch", "supervisor/attempt0001/dispatch/record.json"),
                ("controller_launch", "launch_01/record.json"),
            ):
                path = root / relative
                if path.is_file():
                    successor_refs[name] = entry(path)
            body.update(
                successor_started=bool(successor_refs),
                successor_launch_evidence=successor_refs,
                successor_start_observation="immutable_launch_or_dispatch_receipts_only",
            )
            publish(
                directory / ("continuation_failure" if closeout else "closeout") / "record.json",
                body,
            )
            base.status(
                directory,
                dict(
                    phase=body["status"],
                    at=base.timestamp(clock()),
                    barrier_gpus=[],
                    worker_signals_sent=0,
                    supervisor_signals_sent=body["supervisor_signals_sent"],
                ),
            )
            return body
        finally:
            barrier.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Read-only inspection; production entry is finqa_v51_supervisor.py migrate"
    )
    parser.add_argument("action", choices=("inspect",))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(checked(args.root / "handoff_01/protocol/record.json"), ensure_ascii=False))
