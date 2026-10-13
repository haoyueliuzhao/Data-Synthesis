"""CPU-only V41 non-starving barriers and clean single-controller transition."""

import errno
import fcntl
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v41_handoff")


@pytest.mark.parametrize("with_id", [False, True])
def test_record_reference_checks_file_hash_and_optional_content_id(tmp_path, with_id):
    path = tmp_path / "record.json"
    record = subject.publish(path, dict(source="CPU fixture"))
    reference = subject.ref(path)
    if with_id:
        reference["id"] = record["id"]
    assert subject.check_ref(reference) == record
    assert subject.record_file_ref(reference) == subject.ref(path)


@pytest.mark.parametrize("corruption", ["sha256", "id", "extra", "missing", "record_id"])
def test_record_reference_rejects_changed_digest_id_or_shape(tmp_path, corruption):
    path = tmp_path / "record.json"
    record = subject.publish(path, dict(source="CPU fixture"))
    reference = dict(subject.ref(path), id=record["id"])
    if corruption in ("sha256", "id"):
        reference[corruption] = "0" * 64
    elif corruption == "extra":
        reference["unregistered"] = True
    elif corruption == "missing":
        reference.pop("sha256")
    else:
        path.write_text(json.dumps({**record, "id": "0" * 64}))
        reference = dict(subject.ref(path), id="0" * 64)
    with pytest.raises(subject.HandoffError):
        subject.record_file_ref(reference)


def test_pidfd_open_prefers_native_without_loading_libc(monkeypatch):
    calls = []
    monkeypatch.setattr(
        subject.os,
        "pidfd_open",
        lambda pid, flags: calls.append((pid, flags)) or 73,
        raising=False,
    )
    monkeypatch.setattr(subject.ctypes, "CDLL", lambda *_a, **_k: pytest.fail("no libc retry"))
    assert subject.open_pidfd(1234) == 73
    assert calls == [(1234, 0)]


def test_native_pidfd_error_does_not_trigger_another_open(monkeypatch):
    def denied(_pid, _flags):
        raise PermissionError(errno.EPERM, "fixture denied")

    monkeypatch.setattr(subject.os, "pidfd_open", denied, raising=False)
    monkeypatch.setattr(subject.ctypes, "CDLL", lambda *_a, **_k: pytest.fail("no libc retry"))
    with pytest.raises(PermissionError) as caught:
        subject.open_pidfd(1234)
    assert caught.value.errno == errno.EPERM


@pytest.mark.parametrize("descriptor,error_number", [(74, 0), (-1, errno.ESRCH), (-1, 0)])
def test_libc_pidfd_export_has_exact_abi_and_errno(monkeypatch, descriptor, error_number):
    monkeypatch.delattr(subject.os, "pidfd_open", raising=False)
    calls = []

    def exported(pid, flags):
        assert exported.argtypes == (subject.ctypes.c_int, subject.ctypes.c_uint)
        assert exported.restype is subject.ctypes.c_int
        assert subject.ctypes.get_errno() == 0
        calls.append((pid, flags))
        subject.ctypes.set_errno(error_number)
        return descriptor

    def library(name, *, use_errno):
        assert name is None and use_errno is True
        return SimpleNamespace(pidfd_open=exported)

    monkeypatch.setattr(subject.ctypes, "CDLL", library)
    subject.ctypes.set_errno(errno.EACCES)
    if descriptor < 0:
        with pytest.raises(OSError) as caught:
            subject.open_pidfd(1234)
        assert caught.value.errno == (error_number or errno.EIO)
    else:
        assert subject.open_pidfd(1234) == descriptor
    assert calls == [(1234, 0)]


def test_missing_pidfd_export_fails_closed(monkeypatch):
    monkeypatch.delattr(subject.os, "pidfd_open", raising=False)
    monkeypatch.setattr(subject.ctypes, "CDLL", lambda *_a, **_k: SimpleNamespace())
    with pytest.raises(subject.HandoffError, match="no unsafe PID-only fallback"):
        subject.open_pidfd(1234)


@pytest.mark.parametrize("pid", [0, -1, True, 1.0, "1234", 2**31])
def test_pidfd_rejects_pid_t_coercion_or_overflow(monkeypatch, pid):
    monkeypatch.setattr(
        subject.os, "pidfd_open", lambda *_: pytest.fail("invalid PID opened"), raising=False
    )
    with pytest.raises(subject.HandoffError, match="signed pid_t"):
        subject.open_pidfd(pid)


@pytest.mark.parametrize("failure", [None, "identity", "send"])
def test_controller_signal_rechecks_identity_and_always_closes_pidfd(monkeypatch, failure):
    expected, calls = dict(pid=1234, birth="fixture"), []
    monkeypatch.setattr(subject, "open_pidfd", lambda pid: calls.append(("open", pid)) or 75)

    def identity(value):
        assert value == expected
        calls.append(("identity", value["pid"]))
        if failure == "identity":
            raise subject.HandoffError("fixture identity changed")

    def send(descriptor, sig):
        calls.append(("send", descriptor, sig))
        if failure == "send":
            raise ProcessLookupError(errno.ESRCH, "fixture disappeared")

    monkeypatch.setattr(subject, "assert_controller_identity", identity)
    monkeypatch.setattr(subject.signal, "pidfd_send_signal", send, raising=False)
    monkeypatch.setattr(subject.os, "close", lambda descriptor: calls.append(("close", descriptor)))
    if failure:
        with pytest.raises((subject.HandoffError, ProcessLookupError)):
            subject.signal_controller(expected)
    else:
        subject.signal_controller(expected)
    assert calls[:2] == [("open", 1234), ("identity", 1234)]
    assert calls[-1] == ("close", 75)
    assert [row for row in calls if row[0] == "send"] == (
        [] if failure == "identity" else [("send", 75, subject.signal.SIGTERM)]
    )


def test_missing_pidfd_sender_never_opens_or_signals(monkeypatch):
    monkeypatch.delattr(subject.signal, "pidfd_send_signal", raising=False)
    monkeypatch.setattr(subject, "open_pidfd", lambda _: pytest.fail("must fail before opening"))
    with pytest.raises(subject.HandoffError, match="no unsafe PID-only fallback"):
        subject.signal_controller(dict(pid=1234))


def test_pidfd_capability_probe_opens_only_self_and_never_signals(monkeypatch):
    calls = []
    own_pid = os.getpid()
    monkeypatch.setattr(subject, "open_pidfd", lambda pid: calls.append(("open", pid)) or 76)
    monkeypatch.setattr(subject.os, "close", lambda fd: calls.append(("close", fd)))
    monkeypatch.setattr(
        subject.signal,
        "pidfd_send_signal",
        lambda *_: pytest.fail("no signal probe"),
        raising=False,
    )
    result = subject.verify_pidfd_capability()
    assert calls == [("open", own_pid), ("close", 76)]
    assert result["own_process_handle_opened_and_closed"] and result["signals_sent"] == 0
    assert result["pid_only_fallback"] is False


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subject,
        "verify_pidfd_capability",
        lambda: dict(
            open_backend="CPU_fixture",
            own_process_handle_opened_and_closed=True,
            signals_sent=0,
        ),
    )
    s = SimpleNamespace(
        now=1000.0,
        parent=tmp_path / "parent",
        training=tmp_path / "training",
        handoff=tmp_path / "handoff",
        signals=[],
        on_sleep=None,
        processes={},
    )
    (s.training / "locks").mkdir(parents=True)
    subject.publish(s.parent / "inheritance/record.json", dict(context_inheritances=[]))
    s.protocol = subject.publish(
        s.parent / "protocol/record.json",
        dict(
            allowed_gpu_indices=list(subject.GPUS),
            gpu_uuids={str(gpu): "GPU-" + str(gpu) for gpu in subject.GPUS},
            inheritance=subject.ref(s.parent / "inheritance/record.json"),
            resource_wait_budget_seconds=1000,
        ),
    )
    s.controller = dict(
        pid=700,
        birth="500",
        uid=os.getuid(),
        argv=[
            "python",
            str(s.parent / "implementation/finqa_v40_controller.py"),
            "run",
            "--root",
            str(s.parent),
        ],
    )
    s.processes[700] = s.controller
    subject.publish(
        s.parent / "queue/run_intent/record.json",
        dict(protocol_id=s.protocol["id"], pid=700, birth="500"),
    )
    subject.publish(
        s.parent / "launch_01/record.json",
        dict(protocol_id=s.protocol["id"], pid=700, birth="500", command=s.controller["argv"]),
    )
    s.queue = dict(
        at=subject.timestamp(s.now),
        phase="RUNNING",
        protocol_id=s.protocol["id"],
        global_external_resource_wait_seconds=10.0,
        active_children=[],
    )

    def update():
        s.queue["at"] = subject.timestamp(s.now)
        (s.parent / "queue/status.json").write_text(json.dumps(s.queue))

    s.update = update
    update()

    def launch(directory=None, *, stage="train", pid=800, context_id="context", gpu=4):
        directory = directory or s.parent / "contexts/seed389/full/step0299_training" / stage
        value = subject.publish(
            directory / "launch/record.json",
            dict(
                protocol_id=s.protocol["id"],
                context_id=context_id,
                stage=stage,
                pid=pid,
                birth=str(pid),
                gpu_index=gpu,
                gpu_uuid="GPU-" + str(gpu),
                deadline_epoch=1030,
            ),
        )
        s.processes[pid] = dict(pid=pid, birth=str(pid))
        s.queue["active_children"].append(value)
        update()
        return directory, value

    s.launch = launch

    def complete(directory, value, *, returncode=0, live=False):
        common = {key: value[key] for key in ("protocol_id", "context_id", "stage")}
        subject.publish(
            directory / "result/record.json",
            dict(
                **common,
                status="COMPLETE",
                gpu_index=value["gpu_index"],
                gpu_uuid=value["gpu_uuid"],
                resources=dict(all_gates_passed=True),
            ),
        )
        subject.publish(
            directory / "exit/record.json",
            dict(**common, returncode=returncode, stop_requested=False),
        )
        if not live:
            s.processes.pop(value["pid"], None)
        s.queue["active_children"] = [
            row for row in s.queue["active_children"] if row["pid"] != value["pid"]
        ]
        update()

    s.complete = complete

    def sleep(seconds):
        s.now += seconds
        if s.on_sleep:
            s.on_sleep()
        update()

    s.sleep = sleep

    def signal_controller(expected):
        assert expected == s.controller and not s.queue["active_children"]
        for gpu in subject.GPUS:
            with subject.lock_path(s.training, "GPU-" + str(gpu)).open("a") as stream:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        s.signals.append(expected)
        s.now += 0.1
        s.processes.pop(700)
        s.queue["phase"] = subject.PAUSED
        update()
        subject.publish(
            s.parent / "failure/record.json",
            dict(
                phase=subject.PAUSED,
                protocol_id=s.protocol["id"],
                error_type="DurablePause",
                error="explicit safe stop requested",
                stop_error=None,
                actual_progress_audit_error=None,
            ),
        )
        subject.publish(s.parent / "actual_final_progress/record.json", dict(remaining_outers=9))

    s.signal = signal_controller

    def register(mode=subject.MODES[0], **kwargs):
        return subject.register(
            s.handoff,
            parent_root=s.parent,
            training_root=s.training,
            authorization=dict(user_consent="按实际需求放宽；该模式受控切换", mode=mode),
            mode=mode,
            source_commit="cpu-fixture",
            now=s.now,
            freeze=False,
            identity=lambda pid: s.processes.get(pid),
            **kwargs,
        )

    s.register = register

    def run(**kwargs):
        defaults = dict(
            clock=lambda: s.now,
            sleep=sleep,
            identity=lambda pid: s.processes.get(pid),
            send_signal=signal_controller,
            validate_quiescent=lambda *_: None,
        )
        return subject.run(s.handoff, **{**defaults, **kwargs})

    s.run = run
    return s


def assert_all_locks_free(s):
    barrier = subject.Barrier(s.training, s.protocol["gpu_uuids"])
    assert barrier.acquire_all_or_none()
    barrier.close()


def test_registration_requires_pidfd_capability_before_creating_output(scenario, monkeypatch):
    def unavailable():
        raise subject.HandoffError("fixture pidfd unavailable")

    monkeypatch.setattr(subject, "verify_pidfd_capability", unavailable)
    with pytest.raises(subject.HandoffError, match="pidfd unavailable"):
        scenario.register()
    assert not scenario.handoff.exists()
    assert not scenario.signals


def test_passive_barrier_releases_every_lock_when_any_gpu_busy(scenario):
    s = scenario
    barrier = subject.Barrier(s.training, s.protocol["gpu_uuids"])
    path = subject.lock_path(s.training, "GPU-4")
    assert path.name == "gpu-" + subject.digest("GPU-4") + ".lock"
    with path.open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not barrier.acquire_all_or_none()
        assert not barrier.held
        # The free cards are not retained between probes.
        with subject.lock_path(s.training, "GPU-0").open("a") as competitor:
            fcntl.flock(competitor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert barrier.acquire_all_or_none()
    barrier.close()


@pytest.mark.parametrize("mode", subject.MODES)
def test_single_clean_transition_after_actual_worker_exit(scenario, mode):
    s = scenario
    directory, launch = s.launch()
    owner = subject.lock_path(s.training, "GPU-4").open("a")
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    s.register(mode=mode, deadline_epoch=1010)

    def drain():
        assert not s.signals
        if s.now >= 1002 and 800 in s.processes:
            s.complete(directory, launch)
            owner.close()

    s.on_sleep = drain
    result = s.run()
    assert len(s.signals) == 1 and result["status"] == "COMPLETE"
    assert result["mode"] == mode and result["children_exited"] and result["controller_exited"]
    assert not result["workers_signalled"] and not result["exit_code_observed"]
    assert result["global_resource_wait_seconds"] == pytest.approx(10 + s.now - 1000)
    assert_all_locks_free(s)


@pytest.mark.parametrize("mode", subject.MODES)
def test_partial_class_never_holds_idle_locks_or_signals_parent(scenario, mode):
    s = scenario
    directory, launch = s.launch(
        s.parent / "contexts/seed251/full/step0596_outer/shard00", stage="shard00"
    )
    s.complete(directory, launch)
    s.register(mode=mode, deadline_epoch=1003)
    s.on_sleep = lambda: assert_all_locks_free(s)
    with pytest.raises(subject.HandoffError, match="deadline expired"):
        s.run()
    assert not s.signals
    assert subject.checked(s.handoff / "failure/record.json")["status"] == "STOPPED_NO_MIGRATION"


def test_class_aware_releases_existing_barrier_when_partial_class_appears(scenario):
    s = scenario
    directory, launch = s.launch()
    owner = subject.lock_path(s.training, "GPU-4").open("a")
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    s.register(mode=subject.MODES[1], deadline_epoch=1004)

    def appear():
        if s.now == 1001:
            s.launch(
                s.parent / "contexts/seed251/full/step0596_outer/shard00",
                stage="shard00",
                pid=801,
                context_id="partial",
            )
        elif s.now >= 1002:
            # Only the old science lease remains; the handoff must release GPU0.
            with subject.lock_path(s.training, "GPU-0").open("a") as competitor:
                fcntl.flock(competitor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    s.on_sleep = appear
    with pytest.raises(subject.HandoffError, match="deadline expired"):
        s.run()
    owner.close()
    assert not s.signals
    assert any(
        subject.checked(path)["phase"] == "BARRIER_RELEASED_FOR_PARENT_PROGRESS"
        for path in (s.handoff / "events").glob("*/record.json")
    )


@pytest.mark.parametrize("with_id", [False, True])
def test_inherited_completed_shard_counts_without_parent_recomputation(tmp_path, with_id):
    def reference(path):
        value = subject.ref(path)
        if with_id:
            value["id"] = subject.checked(path)["id"]
        return value

    parent = tmp_path / "parent"
    origin = tmp_path / "original"
    context = subject.publish(
        origin / "context/record.json", dict(seed=251, arm="C-only", step=1192)
    )
    stage = origin / "shard02"
    fields = dict(protocol_id="old-protocol", context_id=context["id"], stage="shard02")
    subject.publish(
        stage / "launch/record.json",
        dict(**fields, pid=11, birth="1", gpu_index=4, gpu_uuid="GPU-4"),
    )
    subject.publish(
        stage / "result/record.json",
        dict(
            **fields,
            status="COMPLETE",
            gpu_index=4,
            gpu_uuid="GPU-4",
            resources=dict(all_gates_passed=True),
        ),
    )
    subject.publish(stage / "exit/record.json", dict(**fields, returncode=0, stop_requested=False))
    target = parent / "contexts/seed251/c_only/step1192_outer"
    subject.publish(
        parent / "inheritance/record.json",
        dict(
            context_inheritances=[
                dict(
                    new_context_directory=str(target),
                    original_context=reference(origin / "context/record.json"),
                    stage_bindings=dict(
                        shard02=dict(
                            protocol_scope="parent",
                            protocol_id="old-protocol",
                            launch=reference(stage / "launch/record.json"),
                            result=reference(stage / "result/record.json"),
                            exit=reference(stage / "exit/record.json"),
                        )
                    ),
                )
            ]
        ),
    )
    protocol = dict(inheritance=reference(parent / "inheritance/record.json"))
    inherited = subject.inherited_class_shards(parent, protocol, identity=lambda _: None)
    first = subject.class_frontiers(parent, inherited)[0]
    assert first["inherited_shards"] == ["shard02"]
    assert first["undispatched_shards"] == ["shard00", "shard01", "shard03"]
    for stage_name in first["undispatched_shards"]:
        subject.publish(target / stage_name / "launch/record.json", dict(stage=stage_name))
    assert subject.class_frontiers(parent, inherited)[0]["undispatched_shards"] == []


def test_inheritance_preflight_required_and_failure_never_pauses(scenario):
    s = scenario
    s.register(deadline_epoch=1010)
    with pytest.raises(subject.HandoffError, match="preflight callback required"):
        s.run(validate_quiescent=None)
    assert not (s.handoff / "run_intent/record.json").exists()

    def reject(*_):
        raise subject.HandoffError("inheritance unsupported")

    with pytest.raises(subject.HandoffError, match="inheritance unsupported"):
        s.run(validate_quiescent=reject)
    assert not s.signals
    assert_all_locks_free(s)


@pytest.mark.parametrize("kind", ["birth", "uid", "argv"])
def test_changed_controller_identity_blocks_all_signals(scenario, kind):
    s = scenario
    s.register(deadline_epoch=1010)
    s.processes[700] = {**s.controller, kind: "changed"}
    with pytest.raises(subject.HandoffError, match="PID/birth"):
        s.run()
    assert not s.signals


@pytest.mark.parametrize(
    "returncode,live,match", [(1, False, "code zero"), (0, True, "still alive")]
)
def test_worker_exit_must_be_zero_and_real(scenario, returncode, live, match):
    s = scenario
    directory, launch = s.launch()
    s.register(deadline_epoch=1010)
    s.complete(directory, launch, returncode=returncode, live=live)
    with pytest.raises(subject.HandoffError, match=match):
        s.run()
    assert not s.signals


def test_stale_empty_queue_cannot_pause_parent(scenario):
    s = scenario
    s.register(deadline_epoch=1003)
    with pytest.raises(subject.HandoffError, match="deadline expired"):
        s.run(sleep=lambda seconds: setattr(s, "now", s.now + seconds))
    assert not s.signals


def test_active_queue_never_paused_even_if_lock_evidence_inconsistent(scenario):
    s = scenario
    s.launch()
    s.register(deadline_epoch=1003)
    with pytest.raises(subject.HandoffError, match="deadline expired"):
        s.run()
    assert not s.signals


def test_preflight_parent_failure_is_rechecked_before_signal(scenario):
    s = scenario
    s.register(deadline_epoch=1010)

    def preflight(*_):
        s.queue["phase"] = "STOPPED_FAILURE_NO_RETRY"
        s.update()

    with pytest.raises(subject.HandoffError, match="freshly quiescent"):
        s.run(validate_quiescent=preflight)
    assert not s.signals


def test_callback_owns_barrier_and_bills_initialization_before_single_release(scenario):
    s = scenario
    s.register(deadline_epoch=1010)

    def callback(closeout, release):
        assert closeout["controller_exited"] and closeout["children_exited"]
        competitor = subject.Barrier(s.training, s.protocol["gpu_uuids"])
        assert not competitor.acquire_all_or_none()
        s.now += 2
        assert release()["global_resource_wait_seconds"] == pytest.approx(10 + s.now - 1000)
        assert competitor.acquire_all_or_none()
        competitor.close()
        with pytest.raises(subject.HandoffError, match="single-use"):
            release()
        return dict(initialized=True)

    assert s.run(on_quiesced=callback)["status"] == "COMPLETE"
    with pytest.raises(FileExistsError):
        s.run()
    assert len(s.signals) == 1


def test_callback_cannot_extend_deadline_and_no_parent_resume(scenario):
    s = scenario
    s.register(deadline_epoch=1004)

    def callback(_closeout, release):
        s.now = 1004
        release()

    with pytest.raises(subject.HandoffError, match="deadline expired"):
        s.run(on_quiesced=callback)
    failure = subject.checked(s.handoff / "failure/record.json")
    assert failure["status"] == "CONTINUATION_CALLBACK_ERROR_NO_RETRY"
    assert failure["controller_signalled"] and not failure["parent_resume_attempted"]
    assert s.queue["phase"] == subject.PAUSED


def test_mode_requires_matching_explicit_registration_and_budget_not_extended(scenario):
    s = scenario
    with pytest.raises(subject.HandoffError, match="matching fixed handoff mode"):
        subject.register(
            s.handoff,
            parent_root=s.parent,
            training_root=s.training,
            authorization=dict(user_consent="同意", mode=subject.MODES[1]),
            mode=subject.MODES[0],
            source_commit="cpu-fixture",
            freeze=False,
        )
    with pytest.raises(subject.HandoffError, match="may not extend"):
        s.register(deadline_epoch=2000)
    assert not s.handoff.exists()
    assert (
        subject.deadline_bound(
            dict(global_external_resource_wait_seconds=998), [dict(deadline_epoch=5000)], 1000, 1000
        )
        == 1002
    )


def test_global_wait_budget_charges_observer_wall_even_while_parent_computes(scenario):
    s = scenario
    s.register(deadline_epoch=1010)
    s.queue["global_external_resource_wait_seconds"] = 1000
    s.update()
    with pytest.raises(subject.HandoffError, match="budget exhausted"):
        s.run()
    assert not s.signals


def test_explicit_observer_stop_releases_without_scientific_signals(scenario):
    s = scenario
    s.register(deadline_epoch=1010)
    with pytest.raises(subject.HandoffError, match="stop requested"):
        s.run(stop_requested=lambda: True)
    assert not s.signals
    assert_all_locks_free(s)
