"""Independent queued-lock amendment over the unchanged V45 scientific package.

CPU-only lock helpers remain queued in the kernel instead of sampling a short
release window. The new barrier must own GPU3 before the old handoff can stop;
scientific workers are never signalled. The original V45 receipt contract,
actual successful worker exits, fresh queue and legal supervisor stop remain.
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

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01/"
    "production_resume_01/host_memory_admission_01"
)
HANDOFF_ROOT = ROOT / "queued_handoff_01"


def _load_primitives():
    name = __name__ + "_sealed_v41_primitives"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "implementation/finqa_v41_handoff.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = _load_primitives()

SCHEMA = "v46_pinned_queued_natural_lease_handoff.v1"
PINNED_PROTOCOL_ID = "93d74f870865e1ecd40b93c77155d8a2fb00d33ef47960cd33c99847af731d60"
PINNED_CONTROLLER = dict(pid=2068036, birth="438667781")
PINNED_SUPERVISOR = dict(pid=2068024, birth="438667686")
PINNED_MIGRATION = dict(pid=2911728, birth="441686539")
PRODUCTION = base.SOURCE_ROOT / "production_resume_01"
PARENT_ROOT = PRODUCTION / "recovery_04"
GPUS = tuple(range(8))
ANCHOR_GPU = 3
PREDECESSOR_GPUS = tuple(gpu for gpu in GPUS if gpu != ANCHOR_GPU)
SHUTDOWN_GRACE_SECONDS = 600
require, checked, publish = base.require, base.checked, base.publish
process_identity, signal_supervisor = base.process_identity, base.signal_controller


def handoff_directory(root):
    return Path(root).resolve() / "queued_handoff_01"


def _barrier_class():
    name = __name__ + "_frozen_queued_barrier"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v46_queued_barrier.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.QueuedBarrier


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
    require(
        root == ROOT
        and Path(__file__).resolve()
        == handoff_directory(root) / "implementation/finqa_v46_handoff.py"
        and Path(base.__file__).resolve() == root / "implementation/finqa_v41_handoff.py",
        "queued amendment and unchanged scientific primitives need their separate frozen paths",
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


def _predecessor_registration(root, identity, clock):
    directory = root / "handoff_01"
    migration = checked(root / "migration_launch/record.json")
    launched = checked(directory / "launch/record.json")
    process = identity(migration["pid"])
    require(
        _same_launch(migration, PINNED_MIGRATION)
        and _same_launch(launched, PINNED_MIGRATION)
        and process is not None
        and _same_launch(process, PINNED_MIGRATION)
        and process["uid"] == os.getuid()
        and process["argv"][1:]
        == [
            "-u",
            str(root / "implementation/finqa_v45_supervisor.py"),
            "migrate",
            "--root",
            str(root),
        ],
        "only the pinned unactivated V45 migration may be superseded",
    )
    observed = base.read(directory / "status.json")
    require(
        observed["phase"] == "DRAINING_NATURALLY"
        and observed["barrier_gpus"] == list(PREDECESSOR_GPUS)
        and observed["worker_signals_sent"] == observed["supervisor_signals_sent"] == 0
        and -1 <= clock() - base.epoch(observed["at"]) <= 60
        and not (directory / "supervisor_signal/record.json").exists()
        and not (directory / "closeout/record.json").exists()
        and not (root / "protocol/record.json").exists(),
        "old V45 must still hold exactly the seven non-anchor locks without scientific transition",
    )
    preparation = checked(root / "preparation/record.json")
    implementation = checked(root / "implementation/record.json")
    require(
        len(implementation["sha256"]) == 81
        and preparation["implementation"] == entry(root / "implementation/record.json"),
        "the prepared V45 scientific package must remain unchanged",
    )
    return dict(
        predecessor_identity=process,
        predecessor_migration_launch=entry(root / "migration_launch/record.json"),
        predecessor_handoff_protocol=entry(directory / "protocol/record.json"),
        predecessor_handoff_launch=entry(directory / "launch/record.json"),
        initial_predecessor_status=observed,
        scientific_implementation=entry(root / "implementation/record.json"),
        scientific_preparation=entry(root / "preparation/record.json"),
        amendment_implementation=entry(handoff_directory(root) / "implementation/record.json"),
    )


def _predecessor_still_unactivated(spec, identity):
    if spec["pidfd_capability"].get("cpu_mock_only"):
        return
    root = Path(spec["root"])
    require(
        identity(spec["predecessor_identity"]["pid"]) == spec["predecessor_identity"]
        and not (root / "handoff_01/supervisor_signal/record.json").exists()
        and not (root / "handoff_01/closeout/record.json").exists()
        and not (root / "protocol/record.json").exists(),
        "original V45 already transitioned or exited; queued amendment must not interrupt it",
    )


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
            root == ROOT and parent == PARENT_ROOT,
            "fixed independent V46 queued handoff scope required",
        )
        _runtime_sources(root)
        capability = base.verify_pidfd_capability()
    else:
        capability = dict(cpu_mock_only=True, signals_sent=0)
    authority = base.check_ref(authorization_ref)
    require(
        bool(authority.get("user_consent")),
        "explicit queued-handoff repair authorization required",
    )
    protocol = checked(parent / "protocol/record.json")
    require(
        protocol["id"] == PINNED_PROTOCOL_ID
        and protocol["output_root"] == str(parent)
        and protocol["allowed_gpu_indices"] == list(GPUS),
        "initial pinned V43 protocol changed",
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
            str(parent / "implementation/finqa_v43_controller.py"),
            "run",
            "--root",
            str(parent),
        ]
        and supervisor["argv"]
        == [
            command[0],
            "-u",
            str(parent / "implementation/finqa_v43_supervisor.py"),
            "run",
            "--root",
            str(parent),
        ],
        "pinned process command is not the original V43 script/action/root",
    )
    if supervisor_launch.get("command") is not None:
        require(
            supervisor["argv"] == supervisor_launch["command"], "supervisor launch command changed"
        )
    body = dict(
        schema=SCHEMA,
        at=base.timestamp(clock()),
        root=str(root),
        handoff_root=str(handoff_directory(root)),
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
        mode="queued_open_file_description_natural_lease_drain",
        anchor_gpu=ANCHOR_GPU,
        waiters_required_before_predecessor_stop=list(PREDECESSOR_GPUS),
        anchor_owned_before_predecessor_stop=True,
        kernel_flock_fifo_fairness_claimed=False,
        no_thread_close_cancellation=True,
        new_max_gpu_workers=5,
        worker_signals_allowed=False,
        no_attempt_following=True,
        deadline_epoch=None,
        resource_wait_limit_seconds=None,
        shutdown_grace_seconds=SHUTDOWN_GRACE_SECONDS,
        unfinished_unlaunched_class_shards_may_migrate=True,
        pidfd_capability=capability,
        parent_scientific_files_modified=False,
        scientific_package_changed=False,
        previous_handoff_records_modified=False,
    )
    queue = _pinned_live(body, identity, clock)
    if freeze:
        require(
            len(queue["active_children"]) == 1
            and queue["active_children"][0]["gpu_index"] == ANCHOR_GPU,
            "initial science must have its single active worker on the registered anchor GPU3",
        )
        body.update(_predecessor_registration(root, identity, clock))
    body["initial_active_children"] = queue["active_children"]
    body["initial_parent_resource_wait_seconds"] = queue["global_external_resource_wait_seconds"]
    return publish(handoff_directory(root) / "protocol/record.json", body)


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


def run(
    root,
    *,
    validate_quiescent,
    on_waiters_registered,
    on_quiesced=None,
    stop_requested=lambda: False,
    clock=time.time,
    monotonic=time.monotonic,
    sleep=time.sleep,
    identity=process_identity,
    send_signal=signal_supervisor,
    barrier_factory=None,
):
    root = Path(root).resolve()
    _runtime_sources(root)
    directory = handoff_directory(root)
    spec = checked(directory / "protocol/record.json")
    require(
        spec["schema"] == SCHEMA
        and spec["root"] == str(root)
        and spec["handoff_root"] == str(directory)
        and spec["anchor_gpu"] == ANCHOR_GPU
        and spec["waiters_required_before_predecessor_stop"] == list(PREDECESSOR_GPUS),
        "unregistered queued handoff entry",
    )
    base.check_ref(spec["authorization"])
    if not spec["pidfd_capability"].get("cpu_mock_only"):
        for key in (
            "scientific_implementation",
            "scientific_preparation",
            "amendment_implementation",
            "predecessor_migration_launch",
            "predecessor_handoff_protocol",
            "predecessor_handoff_launch",
        ):
            base.check_ref(spec[key])
    with (directory / "owner.lock").open("a") as ownership:
        fcntl.flock(ownership, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "launch/record.json").exists(), "one handoff attempt only")
        publish(
            directory / "launch/record.json",
            dict(
                schema="v46_natural_handoff_launch.v1",
                at=base.timestamp(clock()),
                pid=os.getpid(),
                birth=process_identity(os.getpid())["birth"],
                protocol=entry(directory / "protocol/record.json"),
                worker_signals_sent=0,
            ),
        )
        barrier = (barrier_factory or _barrier_class())(spec["training_root"], spec["gpu_uuids"])
        started, sent, closeout, shutdown_started = monotonic(), False, None, None
        signal_attempted, barrier_acquired_epoch, barrier_released = False, None, False
        predecessor_transition = None
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
                    schema="v46_single_successor_barrier_release.v1",
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
            require(not stop_requested(), "explicit stop before starting queued lock helpers")
            _pinned_live(spec, identity, clock)
            _predecessor_still_unactivated(spec, identity)
            barrier.start_waiters()
            while True:
                require(not stop_requested(), "explicit stop requested before handoff")
                queue = _pinned_live(spec, identity, clock)
                _worker_receipts(spec, identity, complete_cache=complete_worker_receipts)
                barrier.acquire_available()
                if predecessor_transition is None:
                    _predecessor_still_unactivated(spec, identity)
                    if ANCHOR_GPU in barrier.held and barrier.waiters_ready(PREDECESSOR_GPUS):
                        publish(
                            directory / "waiters_registered/record.json",
                            dict(
                                schema="v46_anchor_owned_and_waiters_kernel_registered.v1",
                                at=base.timestamp(clock()),
                                protocol=entry(directory / "protocol/record.json"),
                                anchor_gpu=ANCHOR_GPU,
                                anchor_actually_owned=True,
                                required_waiter_gpus=list(PREDECESSOR_GPUS),
                                kernel_queued_is_not_lock_ownership=True,
                                lock_helper_snapshot=barrier.snapshot(),
                                scientific_worker_signals_sent=0,
                            ),
                        )
                        require(not stop_requested(), "explicit stop before migration replacement")
                        _pinned_live(spec, identity, clock)
                        _predecessor_still_unactivated(spec, identity)
                        reference = on_waiters_registered(spec, barrier)
                        base.check_ref(reference)
                        predecessor_transition = reference
                        publish(
                            directory / "predecessor_replaced/record.json",
                            dict(
                                schema="v46_old_migration_replaced_after_safe_anchor.v1",
                                at=base.timestamp(clock()),
                                waiters_registered=entry(
                                    directory / "waiters_registered/record.json"
                                ),
                                predecessor_transition=reference,
                                anchor_gpu=ANCHOR_GPU,
                                anchor_remained_owned=ANCHOR_GPU in barrier.held,
                                scientific_worker_signals_sent=0,
                            ),
                        )
                        require(
                            ANCHOR_GPU in barrier.held,
                            "anchor lease lost during migration replacement",
                        )
                if barrier.complete and barrier_acquired_epoch is None:
                    require(
                        predecessor_transition is not None,
                        "cannot complete before verified predecessor replacement",
                    )
                    barrier_acquired_epoch = clock()
                    publish(
                        directory / "barrier_acquired/record.json",
                        dict(
                            schema="v46_all_project_gpu_locks_acquired.v1",
                            at=base.timestamp(barrier_acquired_epoch),
                            acquired_epoch=barrier_acquired_epoch,
                            all_gpu_locks_held=list(GPUS),
                        ),
                    )
                base.status(
                    directory,
                    dict(
                        phase=(
                            "DRAINING_NATURALLY"
                            if predecessor_transition is not None
                            else "WAITING_FOR_ANCHOR_AND_REGISTERED_WAITERS"
                        ),
                        at=base.timestamp(clock()),
                        barrier_gpus=sorted(barrier.held),
                        active_children=queue["active_children"],
                        worker_signals_sent=0,
                        supervisor_signals_sent=0,
                        deadline_epoch=None,
                        anchor_gpu=ANCHOR_GPU,
                        anchor_owned=ANCHOR_GPU in barrier.held,
                        predecessor_replaced=predecessor_transition is not None,
                        lock_helpers=barrier.snapshot(),
                    ),
                )
                if (
                    not barrier.complete
                    or queue["active_children"]
                    or base.epoch(queue["at"]) <= barrier_acquired_epoch
                ):
                    sleep(2)
                    continue
                audit = validate_quiescent(Path(spec["parent_root"]), queue)
                require(
                    audit["status"] == "CLEAN_NATURAL_WORKER_BOUNDARY", "unsafe quiescent boundary"
                )
                publish(
                    directory / "preflight/record.json",
                    dict(
                        schema="v46_held_barrier_quiescent_preflight.v1",
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
                        schema="v46_verified_supervisor_pidfd_stop.v1",
                        at=base.timestamp(clock()),
                        target=spec["supervisor_identity"],
                        signals_sent=1,
                        worker_signals_sent=0,
                        all_gpu_locks_held=list(GPUS),
                        pidfd_only=True,
                    ),
                )
                _wait_for_exit(spec, identity, monotonic, sleep, started=shutdown_started)
                evidence = _stopped_parent_evidence(spec)
                require(barrier.complete, "handoff barrier lost before parent exit verification")
                closeout = publish(
                    directory / "closeout/record.json",
                    dict(
                        schema="v45_clean_natural_handoff.v1",
                        execution_schema="v46_independent_queued_handoff_execution.v1",
                        execution_protocol=entry(directory / "protocol/record.json"),
                        execution_authorization=spec["authorization"],
                        amendment_implementation=spec.get("amendment_implementation"),
                        unchanged_scientific_implementation=spec.get("scientific_implementation"),
                        predecessor_migration_transition=predecessor_transition,
                        previous_v45_handoff_reclassified_as_success=False,
                        old_handoff_directory_modified_by_this_entry=False,
                        lock_helpers=barrier.snapshot(),
                        kernel_flock_fifo_fairness_claimed=False,
                        status="CLEAN_NATURAL_HANDOFF",
                        at=base.timestamp(clock()),
                        parent_root=spec["parent_root"],
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
                        handoff_elapsed_seconds=max(0.0, monotonic() - started),
                        handoff_elapsed_not_added_again_to_parent_wait=True,
                        **evidence,
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
                schema="v46_handoff_stopped_no_retry.v1",
                at=base.timestamp(clock()),
                status="STOPPED_AFTER_CLEAN_HANDOFF" if closeout else "STOPPED_NO_MIGRATION",
                error_type=type(error).__name__,
                error=str(error),
                worker_signals_sent=0,
                supervisor_signals_sent=1 if sent else None if signal_attempted else 0,
                supervisor_signal_attempted=signal_attempted,
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
        description="Read-only inspection; production entry is finqa_v46_supervisor.py run"
    )
    parser.add_argument("action", choices=("inspect",))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            checked(handoff_directory(args.root) / "protocol/record.json"), ensure_ascii=False
        )
    )
