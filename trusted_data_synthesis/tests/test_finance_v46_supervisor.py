"""CPU-only tests of the independent queued handoff's scientific-entry boundary.

No production controller, handoff helper, GPU, API or scientific payload is
imported. All episode records and process identities below are test fixtures.
"""

import copy
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_SOURCE = Path(__file__).parents[1] / "scripts/finqa_v46_supervisor.py"
_SPEC = importlib.util.spec_from_file_location("v46_supervisor_cpu_subject", _SOURCE)
subject = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(subject)


def require(value, message):
    if not value:
        raise ValueError(message)


def write_record(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    value = {**body, "id": digest}
    with path.open("x") as stream:
        json.dump(value, stream)
    return value


def read_record(path):
    return json.loads(Path(path).read_text())


def entry(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), id=json.loads(raw)["id"])


@pytest.fixture
def episode(tmp_path, monkeypatch):
    science = tmp_path / "science"
    root = science / "queued_handoff_01"
    science.mkdir()
    monkeypatch.setattr(subject, "SCIENCE_ROOT", science)
    monkeypatch.setattr(subject, "ROOT", root)
    expected = dict(
        **subject.OLD_MIGRATION,
        uid=os.getuid(),
        argv=[
            sys.executable,
            "-u",
            str(science / "implementation/finqa_v45_supervisor.py"),
            "migrate",
            "--root",
            str(science),
        ],
    )
    write_record(science / "migration_launch/record.json", dict(subject.OLD_MIGRATION))
    status_path = science / "handoff_01/status.json"
    write_record(
        status_path,
        dict(
            phase="DRAINING_NATURALLY",
            worker_signals_sent=0,
            supervisor_signals_sent=0,
            barrier_gpus=[0, 1, 2, 4, 5, 6, 7],
        ),
    )
    write_record(
        root / "authorization/record.json",
        dict(user_consent="处理此问题", pending_migration_identity=expected),
    )
    write_record(root / "protocol/record.json", dict(schema="CPU_QUEUED_PROTOCOL"))
    events = []
    state = SimpleNamespace(alive=True, stopped=False, time=0.0, closeout_overrides={})

    def process_identity(pid):
        assert pid == expected["pid"]
        return copy.deepcopy(expected) if state.alive else None

    def signal_pending(identity):
        assert identity == expected
        events.append(("signal_pending", copy.deepcopy(identity)))
        state.alive = False
        write_record(
            science / "handoff_01/closeout/record.json",
            dict(
                status="STOPPED_NO_MIGRATION",
                worker_signals_sent=0,
                supervisor_signals_sent=0,
                supervisor_signal_attempted=False,
                successor_started=False,
                **state.closeout_overrides,
            ),
        )

    def sleep(seconds):
        state.time += seconds

    def exited(target, identity):
        observed = identity(target["pid"])
        return observed is None or str(observed["birth"]) != str(target["birth"])

    control = SimpleNamespace(
        parent=SimpleNamespace(PYTHON=Path(sys.executable)),
        require=require,
        checked=read_record,
        publish=write_record,
        entry=entry,
        sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        now=lambda: "CPU_TIME",
        birth=lambda pid: "CPU_ENTRY_BIRTH",
        PARENT_ROOT=tmp_path / "old-science",
    )
    handoff = SimpleNamespace(
        process_identity=process_identity, signal_supervisor=signal_pending, _exited=exited
    )
    barrier = SimpleNamespace(held={3})
    return SimpleNamespace(**locals())


def test_pending_owner_requires_the_original_command_and_identity(episode):
    e = episode
    owner, snapshot = subject.pending_migration(e.control, e.handoff)
    assert owner == e.expected
    assert snapshot["barrier_gpus"] == [0, 1, 2, 4, 5, 6, 7]
    assert not e.events


@pytest.mark.parametrize(
    "relative",
    [
        "protocol/record.json",
        "launch_01/record.json",
        "supervisor/launch/record.json",
        "handoff_01/supervisor_signal/record.json",
        "handoff_01/closeout/record.json",
    ],
)
def test_already_switched_or_stopping_old_entry_is_never_signalled(episode, relative):
    e = episode
    write_record(e.science / relative, dict(status="ALREADY_PROGRESSED"))
    with pytest.raises(ValueError, match="already progressed"):
        subject.supersede_pending(e.control, e.handoff, {}, e.barrier, lambda: False)
    assert not e.events
    assert not (e.root / "supersession_intent/record.json").exists()


@pytest.mark.parametrize("change", ["gone", "birth", "uid", "command"])
def test_recycled_or_foreign_pending_owner_is_not_followed(episode, change):
    e = episode
    foreign = copy.deepcopy(e.expected)
    if change == "gone":
        foreign = None
    elif change == "birth":
        foreign["birth"] = "RECYCLED"
    elif change == "uid":
        foreign["uid"] += 1
    else:
        foreign["argv"][3] = "run"
    e.handoff.process_identity = lambda pid: foreign
    with pytest.raises(ValueError, match="identity changed"):
        subject.pending_migration(e.control, e.handoff)
    assert not e.events


@pytest.mark.parametrize(
    "override",
    [
        dict(phase="CLEAN_NATURAL_HANDOFF"),
        dict(worker_signals_sent=1),
        dict(supervisor_signals_sent=1),
        dict(barrier_gpus=list(range(8))),
    ],
)
def test_pending_snapshot_cannot_claim_a_completed_old_barrier(episode, override):
    e = episode
    value = read_record(e.status_path)
    value.update(override)
    e.status_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="pending seven-lock"):
        subject.pending_migration(e.control, e.handoff)
    assert not e.events


def test_actual_anchor_is_required_before_even_publishing_stop_intent(episode):
    e = episode
    e.barrier.held = set()
    with pytest.raises(ValueError, match="actual anchor"):
        subject.supersede_pending(e.control, e.handoff, {}, e.barrier, lambda: False)
    assert not e.events
    assert not (e.root / "supersession_intent/record.json").exists()


def test_supersession_signals_only_old_migration_and_preserves_its_real_closeout(episode):
    e = episode
    result = subject.supersede_pending(e.control, e.handoff, {}, e.barrier, lambda: False)
    assert e.events == [("signal_pending", e.expected)]
    receipt = read_record(result["path"])
    assert receipt["target"] == e.expected
    assert receipt["pending_migration_signals_sent"] == 1
    assert receipt["scientific_supervisor_signals_sent"] == 0
    assert receipt["scientific_controller_signals_sent"] == 0
    assert receipt["worker_signals_sent"] == 0
    assert receipt["anchor_retained_until_old_migration_exit"] is True
    assert receipt["old_handoff_closeout"] == entry(e.science / "handoff_01/closeout/record.json")
    assert e.barrier.held == {3}
    assert not (e.science / "protocol/record.json").exists()


@pytest.mark.parametrize("stop_at", ["before_intent", "after_intent"])
def test_explicit_stop_before_pidfd_never_signals_old_migration(episode, stop_at):
    e = episode
    e.state.stopped = stop_at == "before_intent"

    def publish(path, body):
        result = write_record(path, body)
        if Path(path).parent.name == "supersession_intent":
            e.state.stopped = True
        return result

    e.control.publish = publish
    with pytest.raises(ValueError, match="explicit stop"):
        subject.supersede_pending(e.control, e.handoff, {}, e.barrier, lambda: e.state.stopped)
    assert not e.events
    assert not (e.root / "supersession/record.json").exists()


@pytest.mark.parametrize(
    "override",
    [
        dict(status="CLEAN_NATURAL_HANDOFF"),
        dict(worker_signals_sent=1),
        dict(supervisor_signals_sent=1),
        dict(supervisor_signal_attempted=True),
        dict(successor_started=True),
    ],
)
def test_supersession_rejects_non_pending_real_closeout(episode, override):
    e = episode
    original_signal = e.handoff.signal_supervisor

    def bad_closeout(identity):
        original_signal(identity)
        path = e.science / "handoff_01/closeout/record.json"
        value = read_record(path)
        value.update(override)
        path.write_text(json.dumps(value))

    e.handoff.signal_supervisor = bad_closeout
    with pytest.raises(ValueError, match="solely before scientific activation"):
        subject.supersede_pending(e.control, e.handoff, {}, e.barrier, lambda: False)
    assert not (e.root / "supersession/record.json").exists()
    assert read_record(e.science / "handoff_01/closeout/record.json").items() >= override.items()


def test_lost_anchor_cannot_be_reported_as_successful_supersession(episode):
    e = episode
    original_signal = e.handoff.signal_supervisor

    def lost_anchor(identity):
        original_signal(identity)
        e.barrier.held.clear()

    e.handoff.signal_supervisor = lost_anchor
    with pytest.raises(ValueError, match="anchor"):
        subject.supersede_pending(e.control, e.handoff, {}, e.barrier, lambda: False)
    assert not (e.root / "supersession/record.json").exists()


@pytest.mark.parametrize(
    "stop_at", [None, "before", "constructor", "initialize", "protocol", "release", "supervisor"]
)
def test_scientific_continuation_has_no_launch_across_any_stop_boundary(episode, stop_at):
    e = episode
    calls = []
    state = dict(stopped=stop_at == "before", supervisor=None)

    class Supervisor:
        def __init__(self, root, *, control):
            assert root == e.science and control is e.control
            calls.append("constructor")
            self.stopped = False
            if stop_at == "constructor":
                state["stopped"] = True

        def run(self):
            assert not self.stopped and not state["stopped"]
            calls.append("supervisor_run")
            return "CPU_ONLY_CONTINUATION"

    def initialize(root, *, handoff_record):
        assert root == e.science
        assert handoff_record == e.root / "closeout/record.json"
        assert handoff_record != e.science / "handoff_01/closeout/record.json"
        calls.append("initialize")
        if stop_at == "initialize":
            state["stopped"] = True
        if stop_at == "supervisor":
            state["supervisor"].stopped = True

    def checked_protocol(root):
        assert root == e.science
        calls.append("protocol")
        if stop_at == "protocol":
            state["stopped"] = True

    def release():
        calls.append("release")
        if stop_at == "release":
            state["stopped"] = True

    e.control.initialize = initialize
    e.control.checked_protocol = checked_protocol
    module = SimpleNamespace(Supervisor=Supervisor)
    if stop_at is None:
        assert (
            subject.continue_science(e.control, module, state, release) == "CPU_ONLY_CONTINUATION"
        )
        assert calls == ["constructor", "initialize", "protocol", "release", "supervisor_run"]
    else:
        with pytest.raises(ValueError, match="explicit stop"):
            subject.continue_science(e.control, module, state, release)
        assert "supervisor_run" not in calls
        if stop_at != "release":
            assert "release" not in calls
        if stop_at in ("before", "constructor"):
            assert "initialize" not in calls


def source_manifest(e, monkeypatch):
    implementation = e.root / "implementation"
    implementation.mkdir()
    raw_by_name = {name: ("# CPU source " + name + "\n").encode() for name in subject.FILES}
    for name, raw in raw_by_name.items():
        (implementation / name).write_bytes(raw)
    science_manifest = write_record(e.science / "implementation/record.json", dict(frozen_files=81))
    preparation = write_record(
        e.science / "preparation/record.json", dict(frozen_memory_policy=True)
    )
    body = dict(
        schema="v46_independent_queued_handoff_implementation.v1",
        files=list(subject.FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in raw_by_name.items()},
        unchanged_scientific_implementation=entry(e.science / "implementation/record.json"),
        unchanged_scientific_preparation=entry(e.science / "preparation/record.json"),
    )
    write_record(implementation / "record.json", body)
    monkeypatch.setattr(subject, "__file__", str(implementation / subject.FILES[0]))
    e.control.checked_implementation = lambda root: dict(
        id=subject.SCIENCE_IMPLEMENTATION_ID, sha256={str(i): "CPU" for i in range(81)}
    )
    e.control.checked_preparation = lambda: dict(id=subject.SCIENCE_PREPARATION_ID)
    return SimpleNamespace(**locals())


def test_three_file_patch_binds_all_81_frozen_science_files_and_preparation(episode, monkeypatch):
    e = episode
    f = source_manifest(e, monkeypatch)
    assert subject.checked_patch(e.control)["files"] == list(subject.FILES)
    (f.implementation / subject.FILES[1]).write_text("# changed\n")
    with pytest.raises(ValueError, match="patch bytes changed"):
        subject.checked_patch(e.control)


@pytest.mark.parametrize(
    "change", ["count", "science_id", "preparation_id", "fourth_file", "reference"]
)
def test_patch_cannot_relax_science_or_expand_its_source_scope(episode, monkeypatch, change):
    e = episode
    f = source_manifest(e, monkeypatch)
    if change == "count":
        e.control.checked_implementation = lambda root: dict(
            id=subject.SCIENCE_IMPLEMENTATION_ID, sha256={}
        )
    elif change == "science_id":
        e.control.checked_implementation = lambda root: dict(
            id="CHANGED", sha256={str(i): "CPU" for i in range(81)}
        )
    elif change == "preparation_id":
        e.control.checked_preparation = lambda: dict(id="CHANGED")
    else:
        path = f.implementation / "record.json"
        value = read_record(path)
        if change == "fourth_file":
            value["sha256"]["extra.py"] = "CPU"
        else:
            value["unchanged_scientific_preparation"]["sha256"] = "CHANGED"
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        subject.checked_patch(e.control)


@pytest.mark.parametrize("failure", ["import", "wrong_path"])
def test_signal_handlers_are_restored_even_if_frozen_supervisor_loading_fails(
    episode, monkeypatch, failure
):
    e = episode
    write_record(e.root / "implementation/record.json", dict(schema="CPU_PATCH"))
    handlers = {15: object(), 2: object()}
    original = dict(handlers)
    fake_signal = SimpleNamespace(
        SIGTERM=15,
        SIGINT=2,
        getsignal=lambda sig: handlers[sig],
        signal=lambda sig, handler: handlers.__setitem__(sig, handler),
    )
    monkeypatch.setattr(subject, "signal", fake_signal)
    monkeypatch.setattr(subject, "_control", lambda: e.control)
    monkeypatch.setattr(subject, "_handoff", lambda: e.handoff)
    monkeypatch.setattr(subject, "checked_patch", lambda control: {})

    def import_module(name):
        assert name == "finqa_v45_supervisor"
        if failure == "import":
            raise ImportError("CPU missing sealed module")
        return SimpleNamespace(__file__=str(e.root / "wrong_supervisor.py"))

    monkeypatch.setattr(subject, "importlib", SimpleNamespace(import_module=import_module))
    with pytest.raises((ImportError, ValueError)):
        subject.run()
    assert handlers == original
    assert not e.events
