"""Mock-only natural lease handoff: no real process signal or GPU lease taken."""

import fcntl
import importlib
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
h = importlib.import_module("finqa_v51_handoff")


@pytest.fixture
def handoff(tmp_path, monkeypatch):
    parent, root = tmp_path / "single_gpu0_01", tmp_path / "dual_gpu0_gpu6_01"
    clock = SimpleNamespace(now=1000.0)

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    protocol = h.publish(
        parent / "protocol/record.json",
        dict(
            output_root=str(parent),
            supervision_root=str(parent),
            schema="v50_single_gpu0_supervised_protocol.v1",
            max_gpu_workers=1,
            max_workers_per_gpu=1,
            allowed_gpu_indices=[0],
            gpu_uuids={"0": "GPU-0"},
            training_root=str(tmp_path / "training"),
        ),
    )
    monkeypatch.setattr(h, "PINNED_PROTOCOL_ID", protocol["id"])
    command = [
        "/CPU/python",
        "-u",
        str(parent / "implementation/finqa_v50_controller.py"),
        "run",
        "--root",
        str(parent),
    ]
    controller = dict(pid=101, birth="c-birth", uid=os.getuid(), argv=command)
    supervisor = dict(
        pid=102,
        birth="s-birth",
        uid=os.getuid(),
        argv=[
            command[0],
            "-u",
            str(parent / "implementation/finqa_v50_supervisor.py"),
            "run",
            "--root",
            str(parent),
        ],
    )
    processes = {101: controller, 102: supervisor}
    h.publish(
        parent / "launch_01/record.json",
        dict(pid=101, birth="c-birth", protocol_id=protocol["id"], command=command),
    )
    h.publish(
        parent / "supervisor/launch/record.json",
        dict(pid=102, birth="s-birth", protocol=h.entry(parent / "protocol/record.json")),
    )
    h.publish(
        parent / "supervisor/attempt0001/dispatch/record.json",
        dict(pid=101, birth="c-birth", attempt_number=1, attempt_root=str(parent), command=command),
    )
    authority = h.publish(
        root / "authorization/record.json",
        dict(
            user_consent="CPU_ONLY_TWO_SLOTS",
            allowed_gpu_indices=[0, 6],
            max_gpu_workers=2,
            max_workers_per_gpu=1,
        ),
    )
    queue = dict(
        protocol_id=protocol["id"],
        phase="RUNNING",
        at=h.base.timestamp(clock.now),
        active_children=[],
        global_external_resource_wait_seconds=123.25,
    )
    sup_queue = dict(
        phase="RUNNING",
        attempt_number=1,
        attempt_root=str(parent),
        manual_stop_requested=False,
        child=dict(pid=101, birth="c-birth"),
    )

    def refresh():
        queue["at"] = h.base.timestamp(clock.now)
        write(parent / "queue/status.json", queue)
        write(parent / "supervisor/queue/status.json", sup_queue)

    refresh()
    state = SimpleNamespace(
        stopped=False,
        signals=[],
        snapshots=[],
        callback_count=0,
        ready=True,
        sleep_calls=0,
        after_sleep=None,
        exit_on_signal=True,
    )

    def sleep(seconds):
        clock.now += seconds
        state.sleep_calls += 1
        if state.after_sleep:
            state.after_sleep()
        refresh()

    class Barrier:
        def __init__(self, *_args):
            self.held = {}
            state.barrier = self

        @property
        def complete(self):
            return set(self.held) == {0}

        def acquire_available(self):
            self.held.update({0: 0} if state.ready else {})

        def close(self):
            self.held.clear()

    def signal(expected):
        assert expected == supervisor and state.barrier.complete
        assert (
            clock.now
            > h.checked(root / "handoff_01/barrier_acquired/record.json")["acquired_epoch"]
        )
        state.signals.append(expected)
        if not state.exit_on_signal:
            return
        processes[101] = processes[102] = None
        h.publish(
            parent / "supervisor/attempt0001/actual_exit/record.json",
            dict(
                pid=101,
                birth="c-birth",
                attempt_number=1,
                attempt_root=str(parent),
                returncode=1,
                manual_stop_requested=True,
                stop_forwarded=True,
            ),
        )
        h.publish(
            parent / "supervisor/closeout/record.json",
            dict(
                status="STOPPED_BY_EXPLICIT_REQUEST",
                final_attempt=1,
                received_signals=[15],
                automatic_recovery_after_manual_stop=False,
            ),
        )
        h.publish(
            parent / "actual_final_progress/record.json",
            dict(endpoint_scores_or_answers_read=False, original_state_or_feedback_modified=False),
        )
        h.publish(
            parent / "failure/record.json",
            dict(
                phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME",
                error_type="DurablePause",
                error="explicit safe stop requested",
                stop_error=None,
                actual_progress_audit_error=None,
            ),
        )
        queue.update(phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME", active_children=[])
        refresh()

    def audit(parent_arg, value):
        assert parent_arg == parent and value["active_children"] == []
        return dict(
            status="CLEAN_NATURAL_WORKER_BOUNDARY",
            parent_protocol=h.entry(parent / "protocol/record.json"),
            launched_workers_all_complete_and_exit_zero=True,
            worker_signals_sent=0,
            observed_stage_bindings=[],
        )

    monkeypatch.setattr(h, "_runtime_sources", lambda *_args: None)

    def register():
        return h.register(
            root,
            parent,
            h.entry(root / "authorization/record.json"),
            expected_supervisor=supervisor,
            expected_controller=controller,
            identity=processes.get,
            freeze=False,
            clock=lambda: clock.now,
        )

    def run(callback=None, preflight=audit):
        return h.run(
            root,
            validate_quiescent=preflight,
            on_quiesced=callback,
            stop_requested=lambda: state.stopped,
            clock=lambda: clock.now,
            monotonic=lambda: clock.now,
            sleep=sleep,
            identity=processes.get,
            send_signal=signal,
            barrier_factory=Barrier,
        )

    return SimpleNamespace(
        root=root,
        parent=parent,
        clock=clock,
        state=state,
        queue=queue,
        sup_queue=sup_queue,
        controller=controller,
        supervisor=supervisor,
        processes=processes,
        write=write,
        refresh=refresh,
        register=register,
        run=run,
        audit=audit,
        authority=authority,
    )


def test_natural_handoff_waits_for_post_barrier_queue_and_releases_once(handoff):
    f = handoff
    f.register()

    def continuation(closeout, release):
        assert closeout["status"] == "CLEAN_NATURAL_HANDOFF" and f.state.barrier.complete
        assert closeout["global_resource_wait_seconds"] == 124
        assert closeout["supervisor_os_exit_code_observed"] is False
        release()
        assert not f.state.barrier.held
        with pytest.raises(h.base.HandoffError, match="exactly once"):
            release()
        return closeout

    result = f.run(continuation)
    assert result["status"] == "CLEAN_NATURAL_HANDOFF" and len(f.state.signals) == 1
    assert f.state.sleep_calls >= 1
    assert h.checked(f.root / "handoff_01/barrier_release/record.json")["release_count"] == 1


def test_held_locks_do_not_force_active_worker_stop(handoff):
    f = handoff
    f.state.ready = False
    f.queue["active_children"] = [dict(pid=303)]
    f.refresh()
    f.register()

    def natural_finish():
        assert not f.state.signals
        assert 0 not in f.state.barrier.held
        f.queue["active_children"] = []
        f.state.ready = True
        f.state.after_sleep = None

    f.state.after_sleep = natural_finish
    assert f.run()["status"] == "CLEAN_NATURAL_HANDOFF"
    assert f.state.sleep_calls >= 2 and len(f.state.signals) == 1


def test_attempt_change_releases_locks_without_signal(handoff):
    f = handoff
    f.state.ready = False
    f.register()
    f.state.after_sleep = lambda: f.sup_queue.update(attempt_number=2)
    assert f.run()["status"] == "STOPPED_NO_MIGRATION"
    assert not f.state.signals and not f.state.barrier.held


def test_stop_after_preflight_never_signals_parent(handoff):
    f = handoff
    f.register()

    def audit(*args):
        value = f.audit(*args)
        f.state.stopped = True
        return value

    assert f.run(preflight=audit)["status"] == "STOPPED_NO_MIGRATION"
    assert not f.state.signals and not f.state.barrier.held


def test_wrong_live_command_rejected_at_registration(handoff):
    f = handoff
    f.controller["argv"] = ["/CPU/python", "different-script"]
    with pytest.raises(h.base.HandoffError, match="live command"):
        f.register()


def test_shutdown_cleanup_cannot_restart_the_shared_grace(handoff, monkeypatch):
    f = handoff
    f.state.exit_on_signal = False
    f.register()
    monkeypatch.setattr(h, "SHUTDOWN_GRACE_SECONDS", 3)
    result = f.run()
    assert result["status"] == "STOPPED_AFTER_PARENT_SIGNAL_NO_SUCCESSOR"
    assert len(f.state.signals) == 1
    assert (
        f.clock.now == 1006.0
    )  # 2 seconds post-barrier snapshot + 4 seconds shutdown, not another grace.
    assert not f.state.barrier.held


def test_late_stop_during_continuation_blocks_release_and_new_start(handoff):
    f = handoff
    f.register()

    def continuation(_closeout, release):
        f.state.stopped = True
        release()

    result = f.run(continuation)
    assert (
        result["status"] == "STOPPED_AFTER_CLEAN_HANDOFF" and result["successor_started"] is False
    )
    assert not (f.root / "handoff_01/barrier_release/record.json").exists()
    assert not f.state.barrier.held


def test_callback_failure_reports_observed_successor_launch(handoff):
    f = handoff
    f.register()

    def continuation(_closeout, release):
        release()
        h.publish(f.root / "supervisor/launch/record.json", dict(pid=999, birth="mock"))
        raise RuntimeError("mock successor failure after its launch")

    result = f.run(continuation)
    assert (
        result["successor_started"] is True
        and "supervisor_launch" in result["successor_launch_evidence"]
    )
    assert result["handoff_itself_never_launches_scientific_workers"] is True


def test_failed_worker_exit_prevents_all_parent_signals(handoff):
    f = handoff
    f.register()
    stage = f.parent / "contexts/seed389/full/step0596_outer/shard01"
    protocol = h.checked(f.parent / "protocol/record.json")
    h.publish(
        stage / "launch/record.json",
        dict(
            protocol_id=protocol["id"],
            context_id="CPU",
            stage="shard01",
            pid=303,
            birth="worker",
            gpu_index=0,
            gpu_uuid="GPU-0",
        ),
    )
    h.publish(stage / "exit/record.json", dict(returncode=1, stop_requested=True))
    assert f.run()["status"] == "STOPPED_NO_MIGRATION"
    assert not f.state.signals and not f.state.barrier.held


def test_prepared_module_loads_neighbor_primitive_despite_canonical_import(tmp_path):
    canonical = importlib.import_module("finqa_v41_handoff")
    implementation = tmp_path / "implementation"
    implementation.mkdir()
    for source in (Path(h.__file__), Path(h.base.__file__)):
        shutil.copy2(source, implementation / source.name)
    spec = importlib.util.spec_from_file_location(
        "v51_cpu_prepared_handoff", implementation / "finqa_v51_handoff.py"
    )
    candidate = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = candidate
    spec.loader.exec_module(candidate)
    assert candidate.base is not canonical
    assert Path(candidate.base.__file__) == implementation / "finqa_v41_handoff.py"
    candidate._runtime_sources(tmp_path)


def test_completed_worker_receipts_cached_until_final_independent_preflight(handoff, monkeypatch):
    f = handoff
    spec = f.register()
    stage = f.parent / "contexts/seed389/full/step0596_outer/shard01"
    h.publish(
        stage / "launch/record.json", dict(protocol_id=spec["parent_protocol_id"], stage="shard01")
    )
    checks = []
    monkeypatch.setattr(
        h.base, "validate_stage", lambda *a: checks.append(a) or dict(mock_complete=True)
    )
    cache = {}
    h._worker_receipts(spec, f.processes.get, complete_cache=cache)
    h._worker_receipts(spec, f.processes.get, complete_cache=cache)
    assert len(checks) == 1


def test_old_barrier_covers_only_gpu0_never_successor_gpu6(tmp_path):
    training = tmp_path / "training"
    (training / "locks").mkdir(parents=True)
    barrier = h.Barrier(training, {"0": "CPU-GPU0"})
    path = h.base.lock_path(training, "CPU-GPU0")
    with path.open("a") as old_worker_lease:
        fcntl.flock(old_worker_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert barrier.acquire_available() == []
        assert not barrier.complete and barrier.held == {}
    try:
        assert barrier.acquire_available() == [0]
        assert barrier.complete and set(barrier.held) == {0}
        assert len(list((training / "locks").iterdir())) == 1
    finally:
        barrier.close()
    assert barrier.held == {}
    with pytest.raises(h.base.HandoffError, match="GPU0 only"):
        h.Barrier(training, {"0": "CPU-GPU0", "6": "CPU-GPU6"})


def _local_worker(f, *, result=True, exit_record=True, gates=True, live=False):
    stage = f.parent / "contexts/seed389/full/step0894_outer/replay_R3"
    protocol = h.checked(f.parent / "protocol/record.json")
    common = dict(protocol_id=protocol["id"], context_id="CPU", stage="replay_R3")
    launch = dict(**common, pid=303, birth="worker", gpu_index=0, gpu_uuid="GPU-0")
    h.publish(stage / "launch/record.json", launch)
    if result:
        h.publish(
            stage / "result/record.json",
            dict(
                **common,
                status="COMPLETE",
                gpu_index=0,
                gpu_uuid="GPU-0",
                resources=dict(all_gates_passed=gates),
            ),
        )
    if exit_record:
        h.publish(stage / "exit/record.json", dict(**common, returncode=0, stop_requested=False))
    if live:
        f.processes[303] = launch
    return stage


@pytest.mark.parametrize(
    "case", ["missing_result", "missing_exit", "resource_failure", "still_alive"]
)
def test_empty_queue_cannot_hide_incomplete_or_draining_worker(handoff, case):
    f = handoff
    f.register()
    _local_worker(
        f,
        result=case != "missing_result",
        exit_record=case != "missing_exit",
        gates=case != "resource_failure",
        live=case == "still_alive",
    )
    result = f.run()
    assert result["status"] == "STOPPED_NO_MIGRATION"
    assert result["old_execution_left_running_if_not_signalled"] is True
    assert not f.state.signals and not f.state.barrier.held
    assert f.processes[101] is not None and f.processes[102] is not None


def test_complete_worker_and_partial_unlaunched_class_allowed_by_same_point_audit(handoff):
    f = handoff
    f.register()
    _local_worker(f)

    def audit(*args):
        value = f.audit(*args)
        value["context_boundaries"] = [
            dict(completed_stages=["shard00"], unlaunched_stages=["shard01", "shard02", "shard03"])
        ]
        return value

    result = f.run(preflight=audit)
    assert result["schema"] == "v51_clean_handoff_receipt.v1"
    assert result["all_gpu_locks_held"] == [0]
    assert result["parent_attempt_root"] == result["parent_supervision_root"] == str(f.parent)
    assert result["status"] == "CLEAN_NATURAL_HANDOFF"
    assert len(f.state.signals) == 1


def test_preflight_error_releases_barrier_and_keeps_old_supervision(handoff):
    f = handoff
    f.register()

    def reject(*_args):
        raise ValueError("same-point evidence mismatch")

    result = f.run(preflight=reject)
    assert result["status"] == "STOPPED_NO_MIGRATION"
    assert not f.state.signals and not f.state.barrier.held
    assert f.processes[101] is not None and f.processes[102] is not None


def test_cancel_while_waiting_does_not_forward_signal_to_science(handoff):
    f = handoff
    f.state.ready = False
    f.queue["active_children"] = [dict(pid=303)]
    f.refresh()
    f.register()
    f.state.after_sleep = lambda: setattr(f.state, "stopped", True)
    result = f.run()
    assert result["status"] == "STOPPED_NO_MIGRATION"
    assert result["no_cleanup_signal_sent"] is True
    assert not f.state.signals and not f.state.barrier.held
    assert f.processes[101] is not None and f.processes[102] is not None


def test_preflight_cannot_claim_clean_if_worker_success_flag_false(handoff):
    f = handoff
    f.register()

    def reject(*args):
        return dict(f.audit(*args), launched_workers_all_complete_and_exit_zero=False)

    result = f.run(preflight=reject)
    assert result["status"] == "STOPPED_NO_MIGRATION" and not f.state.signals
