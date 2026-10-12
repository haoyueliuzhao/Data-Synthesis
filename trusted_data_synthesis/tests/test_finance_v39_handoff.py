"""CPU-only handoff ownership, lock, natural-drain and no-retry boundaries."""

import fcntl
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v39_handoff")


@pytest.fixture
def scenario(tmp_path):
    parent, training, handoff = tmp_path / "parent", tmp_path / "training", tmp_path / "handoff"
    (training / "locks").mkdir(parents=True)
    state = SimpleNamespace(
        now=1000.0,
        parent=parent,
        training=training,
        handoff=handoff,
        signals=[],
        callbacks=[],
        on_sleep=None,
        worker_live=True,
    )
    protocol = subject.publish(
        parent / "protocol/record.json",
        dict(
            gpu_uuids={str(gpu): "GPU-" + str(gpu) for gpu in subject.OLD_GPUS},
            resource_wait_budget_seconds=1000,
        ),
    )
    state.protocol = protocol
    controller = dict(
        pid=700,
        birth="500",
        uid=os.getuid(),
        argv=[
            "python",
            str(parent / "implementation/finqa_v38_controller.py"),
            "run",
            "--root",
            str(parent),
        ],
    )
    state.controller = controller
    state.processes = {700: controller, 800: dict(pid=800, birth="600")}
    subject.publish(
        parent / "queue/run_intent/record.json",
        dict(protocol_id=protocol["id"], pid=700, birth="500"),
    )
    subject.publish(
        parent / "launch_01/record.json",
        dict(protocol_id=protocol["id"], pid=700, birth="500", command=controller["argv"]),
    )
    stage = parent / "contexts/seed137/c_only/step1193_training/train"
    state.stage = stage
    launch = subject.publish(
        stage / "launch/record.json",
        dict(
            protocol_id=protocol["id"],
            context_id="context",
            stage="train",
            pid=800,
            birth="600",
            gpu_index=4,
            gpu_uuid="GPU-4",
            deadline_epoch=1030.0,
        ),
    )
    state.launch = launch
    state.queue = dict(
        at=subject.timestamp(state.now),
        phase="RUNNING",
        protocol_id=protocol["id"],
        global_external_resource_wait_seconds=10.0,
        active_children=[
            {k: launch[k] for k in ("context_id", "stage", "pid", "birth", "gpu_index", "gpu_uuid")}
        ],
    )

    def queue_update():
        state.queue["at"] = subject.timestamp(state.now)
        (parent / "queue/status.json").write_text(json.dumps(state.queue))

    state.queue_update = queue_update
    queue_update()

    def complete(returncode=0, live=False):
        subject.publish(
            stage / "result/record.json",
            dict(
                protocol_id=protocol["id"],
                context_id="context",
                stage="train",
                status="COMPLETE",
                gpu_index=4,
                gpu_uuid="GPU-4",
                resources=dict(all_gates_passed=True),
            ),
        )
        subject.publish(
            stage / "exit/record.json",
            dict(
                protocol_id=protocol["id"],
                context_id="context",
                stage="train",
                returncode=returncode,
                stop_requested=False,
            ),
        )
        if not live:
            state.processes.pop(800, None)
        state.queue["active_children"] = []
        queue_update()

    state.complete = complete

    def sleep(seconds):
        state.now += seconds
        if state.on_sleep:
            state.on_sleep()
        queue_update()

    state.sleep = sleep

    def signal_controller(expected):
        assert expected == controller
        assert not state.queue["active_children"]
        # Every old lock must already be held by the barrier at the exact signal.
        for gpu in subject.OLD_GPUS:
            with subject.lock_path(training, "GPU-" + str(gpu)).open("a") as stream:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state.signals.append(expected)
        state.now += 0.1
        state.processes.pop(700)
        state.queue["phase"] = subject.PAUSED
        queue_update()
        subject.publish(
            parent / "failure/record.json",
            dict(
                phase=subject.PAUSED,
                protocol_id=protocol["id"],
                error_type="DurablePause",
                error="explicit safe stop requested",
                stop_error=None,
                actual_progress_audit_error=None,
            ),
        )
        subject.publish(parent / "actual_final_progress/record.json", dict(remaining_outers=9))

    state.signal = signal_controller
    state.register = lambda **kwargs: subject.register(
        handoff,
        parent_root=parent,
        training_root=training,
        authorization=dict(user_consent="同意；当前阶段完整封存后受控切换GPU6"),
        source_commit="cpu-fixture",
        identity=lambda pid: state.processes.get(pid),
        now=state.now,
        freeze=False,
        **kwargs,
    )
    state.run = lambda **kwargs: subject.run(
        handoff,
        clock=lambda: state.now,
        sleep=sleep,
        identity=lambda pid: state.processes.get(pid),
        send_signal=signal_controller,
        **kwargs,
    )
    return state


def test_barrier_uses_original_json_digest_and_never_takes_existing_lease(scenario):
    s = scenario
    path = subject.lock_path(s.training, "GPU-4")
    assert path.name == "gpu-" + subject.digest("GPU-4") + ".lock"
    barrier = subject.Barrier(s.training, s.protocol["gpu_uuids"])
    with path.open("a") as existing:
        fcntl.flock(existing, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert barrier.acquire_available() == [3, 5, 7]
        assert not barrier.complete
    assert barrier.acquire_available() == [4]
    assert barrier.complete
    barrier.close()


def test_active_stage_naturally_finishes_before_controller_signal(scenario):
    s = scenario
    old_lease = subject.lock_path(s.training, "GPU-4").open("a")
    fcntl.flock(old_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    s.register(deadline_epoch=1010)

    def drain():
        assert not s.signals
        if s.now >= 1002 and s.worker_live:
            s.complete()
            s.worker_live = False
            old_lease.close()

    s.on_sleep = drain
    result = s.run()
    assert result["status"] == "COMPLETE" and len(s.signals) == 1
    assert result["children_exited"] and result["controller_exited"]
    assert result["controller_returncode"] is None and result["exit_code_observed"] is False
    assert result["global_resource_wait_seconds"] == pytest.approx(10 + s.now - 1000)
    assert len(result["observed_stages"]) == 1 and result["workers_signalled"] is False
    assert not (s.handoff / "failure/record.json").exists()
    # Barrier is released on return; the old controller is already exited.
    barrier = subject.Barrier(s.training, s.protocol["gpu_uuids"])
    assert barrier.acquire_available() == [3, 4, 5, 7]
    barrier.close()


def test_active_queue_never_signalled_even_with_all_locks_free(scenario):
    s = scenario
    s.register(deadline_epoch=1003)
    with pytest.raises(subject.HandoffError, match="deadline expired"):
        s.run(on_quiesced=lambda *_: s.callbacks.append(True))
    assert not s.signals and not s.callbacks
    assert subject.checked(s.handoff / "failure/record.json")["automatic_retry"] is False


def test_stale_empty_queue_is_not_evidence_of_empty_live_pool(scenario):
    s = scenario
    s.complete()
    s.register(deadline_epoch=1003)
    # Never publish a queue timestamp after all locks were acquired.
    s.queue_update = lambda: None
    with pytest.raises(subject.HandoffError, match="deadline expired"):
        subject.run(
            s.handoff,
            clock=lambda: s.now,
            sleep=lambda seconds: setattr(s, "now", s.now + seconds),
            identity=lambda pid: s.processes.get(pid),
            send_signal=s.signal,
        )
    assert not s.signals


@pytest.mark.parametrize("kind", ["birth", "argv", "uid"])
def test_changed_parent_identity_blocks_signal(scenario, kind):
    s = scenario
    s.register(deadline_epoch=1010)
    s.processes[700] = dict(s.controller, **{kind: ["other"] if kind == "argv" else "other"})
    with pytest.raises(subject.HandoffError, match="identity|PID/birth"):
        s.run()
    assert not s.signals


@pytest.mark.parametrize(
    "returncode,live,match", [(1, False, "code zero"), (0, True, "still alive")]
)
def test_bad_exit_or_not_really_exited_blocks_signal(scenario, returncode, live, match):
    s = scenario
    s.register(deadline_epoch=1010)
    s.complete(returncode=returncode, live=live)
    with pytest.raises(subject.HandoffError, match=match):
        s.run()
    assert not s.signals


def test_parent_failure_stops_handoff_without_any_callback(scenario):
    s = scenario
    s.register(deadline_epoch=1010)
    s.queue["phase"] = "STOPPED_FAILURE_NO_RETRY"
    s.queue_update()
    with pytest.raises(subject.HandoffError, match="parent stopped or failed"):
        s.run(on_quiesced=lambda *_: s.callbacks.append(True))
    assert not s.signals and not s.callbacks


def test_callback_owns_barrier_until_explicit_release(scenario):
    s = scenario
    s.complete()
    s.register(deadline_epoch=1010)

    def callback(closeout, release):
        assert closeout["controller_exited"] and closeout["children_exited"]
        competitor = subject.Barrier(s.training, s.protocol["gpu_uuids"])
        assert competitor.acquire_available() == []
        s.now += 2
        billing = release()
        assert billing["global_resource_wait_seconds"] == pytest.approx(10 + s.now - 1000)
        assert competitor.acquire_available() == [3, 4, 5, 7]
        competitor.close()
        with pytest.raises(subject.HandoffError, match="single-use"):
            release()
        s.callbacks.append(True)
        return dict(initialized=True)

    result = s.run(on_quiesced=callback)
    assert result["status"] == "COMPLETE" and s.callbacks == [True]


def test_preflight_rejects_before_signal_and_releases_barrier(scenario):
    s = scenario
    s.complete()
    s.register(deadline_epoch=1010)

    def reject(_plan, _queue):
        raise subject.HandoffError("migration not supported")

    with pytest.raises(subject.HandoffError, match="migration not supported"):
        s.run(validate_quiescent=reject)
    assert not s.signals
    competitor = subject.Barrier(s.training, s.protocol["gpu_uuids"])
    assert competitor.acquire_available() == [3, 4, 5, 7]
    competitor.close()


def test_partial_class_boundary_refuses_to_pause_parent(scenario):
    s = scenario
    s.complete()
    context = s.parent / "contexts/seed251/full/step0596_outer"
    subject.publish(
        context / "shard00/launch/record.json",
        dict(
            protocol_id=s.protocol["id"],
            context_id="partial",
            stage="shard00",
            pid=801,
            birth="601",
            gpu_index=5,
            gpu_uuid="GPU-5",
            deadline_epoch=1030,
        ),
    )
    subject.publish(
        context / "shard00/result/record.json",
        dict(
            protocol_id=s.protocol["id"],
            context_id="partial",
            stage="shard00",
            status="COMPLETE",
            gpu_index=5,
            gpu_uuid="GPU-5",
            resources=dict(all_gates_passed=True),
        ),
    )
    subject.publish(
        context / "shard00/exit/record.json",
        dict(
            protocol_id=s.protocol["id"],
            context_id="partial",
            stage="shard00",
            returncode=0,
            stop_requested=False,
        ),
    )
    s.register(deadline_epoch=1010)
    with pytest.raises(subject.HandoffError, match="partial class context"):
        s.run()
    assert not s.signals


def test_no_restart_of_used_handoff_run(scenario):
    s = scenario
    s.complete()
    s.register(deadline_epoch=1010)
    s.run()
    with pytest.raises(FileExistsError):
        s.run()
    assert len(s.signals) == 1


def test_registered_deadline_cannot_extend_either_parent_budget(scenario):
    s = scenario
    with pytest.raises(subject.HandoffError, match="may not extend"):
        s.register(deadline_epoch=1631)
    assert not s.handoff.exists()
    queue = dict(global_external_resource_wait_seconds=998)
    assert subject.deadline_bound(queue, [dict(deadline_epoch=5000)], 1000, 1000) == 1002
    with pytest.raises(subject.HandoffError, match="already expired"):
        subject.deadline_bound(queue, [dict(deadline_epoch=999)], 1000, 1000)


def test_launch_appearing_after_registration_is_drained(scenario):
    s = scenario
    s.complete()
    s.register(deadline_epoch=1010)
    other = s.parent / "evaluations/seed137_full/generate"
    values = dict(protocol_id=s.protocol["id"], context_id="evaluation:137:full", stage="generate")
    subject.publish(
        other / "launch/record.json",
        dict(**values, pid=900, birth="700", gpu_index=5, gpu_uuid="GPU-5", deadline_epoch=1030),
    )
    subject.publish(
        other / "result/record.json",
        dict(
            **values,
            status="COMPLETE",
            gpu_index=5,
            gpu_uuid="GPU-5",
            resources=dict(all_gates_passed=True),
        ),
    )
    subject.publish(other / "exit/record.json", dict(**values, returncode=0, stop_requested=False))
    result = s.run()
    assert len(result["observed_stages"]) == 1
    assert result["observed_stages"][0]["launch"]["path"] == str(other / "launch/record.json")


def test_worker_failure_evidence_blocks_handoff_before_signal(scenario):
    s = scenario
    s.register(deadline_epoch=1010)
    subject.publish(s.stage / "failure/record.json", dict(error="worker resource gate"))
    with pytest.raises(subject.HandoffError, match="stage recorded failure"):
        s.run()
    assert not s.signals


def test_explicit_handoff_stop_never_signals_workers_or_controller(scenario):
    s = scenario
    s.register(deadline_epoch=1010)
    with pytest.raises(subject.HandoffError, match="stop requested"):
        s.run(stop_requested=lambda: True)
    assert not s.signals
    assert subject.checked(s.handoff / "failure/record.json")["workers_signalled"] is False


def test_parent_budget_exhaustion_never_invokes_continuation(scenario):
    s = scenario
    s.register(deadline_epoch=1010)
    s.queue["global_external_resource_wait_seconds"] = 1000
    s.queue_update()
    with pytest.raises(subject.HandoffError, match="budget exhausted"):
        s.run(on_quiesced=lambda *_: s.callbacks.append(True))
    assert not s.signals and not s.callbacks


def test_callback_initialization_cannot_release_after_deadline(scenario):
    s = scenario
    s.complete()
    s.register(deadline_epoch=1004)

    def callback(_closeout, release):
        s.now = 1004
        release()
        s.callbacks.append(True)

    with pytest.raises(subject.HandoffError, match="deadline expired"):
        s.run(on_quiesced=callback)
    assert not s.callbacks
    assert (
        subject.checked(s.handoff / "failure/record.json")["status"]
        == "CONTINUATION_CALLBACK_ERROR_NO_RETRY"
    )


def test_wrong_registered_controller_command_prevents_registration(scenario):
    s = scenario
    s.processes[700] = dict(s.controller, argv=[*s.controller["argv"], "--unexpected"])
    with pytest.raises(subject.HandoffError, match="registered full launch"):
        s.register()
    assert not s.handoff.exists()


def test_parent_failure_during_preflight_is_rechecked_before_signal(scenario):
    s = scenario
    s.complete()
    s.register(deadline_epoch=1010)

    def preflight(_plan, _queue):
        s.queue["phase"] = "STOPPED_FAILURE_NO_RETRY"
        s.queue_update()

    with pytest.raises(subject.HandoffError, match="freshly quiescent"):
        s.run(validate_quiescent=preflight)
    assert not s.signals
