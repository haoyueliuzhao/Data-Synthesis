"""Independent queued-lease handoff into the unchanged prepared V45 science.

Only the pending migration coordinator is replaced. Scientific workers finish
naturally, and the original V45 initializer and supervisor consume real proof.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
PRODUCTION = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01/production_resume_01"
)
SCIENCE_ROOT = PRODUCTION / "host_memory_admission_01"
ROOT = SCIENCE_ROOT / "queued_handoff_01"
SCIENCE_IMPLEMENTATION_ID = "c32c3a60ec4b3fa5c943bfa740cf53bdf985d7da7587f664c068ea8058857a6d"
SCIENCE_PREPARATION_ID = "a027dd7eddd35524a3ed548d5c649e97ec1016b7bc69c94b23f4374a6af9ebd2"
OLD_MIGRATION = dict(pid=2911728, birth="441686539")
FILES = ("finqa_v46_supervisor.py", "finqa_v46_handoff.py", "finqa_v46_queued_barrier.py")


def _control():
    directory = str(SCIENCE_ROOT / "implementation")
    if directory not in sys.path:
        sys.path.insert(0, directory)
    control = importlib.import_module("finqa_v45_controller")
    control.require(
        Path(control.__file__).resolve() == SCIENCE_ROOT / "implementation/finqa_v45_controller.py",
        "only the unchanged frozen V45 scientific controller may be consumed",
    )
    return control


def _handoff():
    module = importlib.import_module("finqa_v46_handoff")
    _control().require(
        Path(module.__file__).resolve()
        == Path(__file__).with_name("finqa_v46_handoff.py").resolve(),
        "queued handoff must come from the same independent package",
    )
    return module


def checked_science(control):
    implementation = control.checked_implementation(SCIENCE_ROOT)
    preparation = control.checked_preparation()
    control.require(
        implementation["id"] == SCIENCE_IMPLEMENTATION_ID
        and len(implementation["sha256"]) == 81
        and preparation["id"] == SCIENCE_PREPARATION_ID,
        "prepared V45 science or memory policy changed",
    )
    return implementation, preparation


def pending_migration(control, handoff):
    """No signal is authorized if the old coordinator has already switched."""
    launch = control.checked(SCIENCE_ROOT / "migration_launch/record.json")
    expected = handoff.process_identity(OLD_MIGRATION["pid"])
    control.require(
        expected is not None
        and launch["pid"] == expected["pid"] == OLD_MIGRATION["pid"]
        and str(launch["birth"]) == str(expected["birth"]) == OLD_MIGRATION["birth"]
        and expected["uid"] == os.getuid()
        and expected["argv"]
        == [
            str(control.parent.PYTHON),
            "-u",
            str(SCIENCE_ROOT / "implementation/finqa_v45_supervisor.py"),
            "migrate",
            "--root",
            str(SCIENCE_ROOT),
        ],
        "old pending V45 migration identity changed; do not follow or stop a successor",
    )
    for relative in (
        "protocol/record.json",
        "launch_01/record.json",
        "supervisor/launch/record.json",
        "handoff_01/supervisor_signal/record.json",
        "handoff_01/closeout/record.json",
    ):
        control.require(
            not (SCIENCE_ROOT / relative).exists(), "V45 already progressed: " + relative
        )
    snapshot = json.loads((SCIENCE_ROOT / "handoff_01/status.json").read_text())
    control.require(
        snapshot["phase"] == "DRAINING_NATURALLY"
        and snapshot["worker_signals_sent"] == snapshot["supervisor_signals_sent"] == 0
        and 3 not in snapshot["barrier_gpus"],
        "old handoff is not a pending seven-lock migration",
    )
    return expected, snapshot


def prepare(source_commit):
    control, handoff = _control(), _handoff()
    control.require(not ROOT.exists(), "one fresh independent queued-handoff preparation")
    checked_science(control)
    expected, snapshot = pending_migration(control, handoff)
    commit = subprocess.check_output(
        ["git", "rev-parse", source_commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        control.require(
            hashlib.sha256(raw).hexdigest() == control.sha(REPO / relative),
            "uncommitted patch source: " + name,
        )
        sources[name] = raw
    directory = ROOT / "implementation"
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    control.publish(
        directory / "record.json",
        dict(
            schema="v46_independent_queued_handoff_implementation.v1",
            at=control.now(),
            source_commit=commit,
            files=list(FILES),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
            unchanged_scientific_implementation=control.entry(
                SCIENCE_ROOT / "implementation/record.json"
            ),
            unchanged_scientific_preparation=control.entry(
                SCIENCE_ROOT / "preparation/record.json"
            ),
        ),
    )
    control.publish(
        ROOT / "authorization/record.json",
        dict(
            schema="v46_explicit_pending_handoff_correction_authority.v1",
            at=control.now(),
            user_instruction="处理此问题",
            user_consent="处理此问题",
            original_problem=(
                "two-second nonblocking polling misses sub-second lease release and reuse"
            ),
            scientific_root=str(SCIENCE_ROOT),
            pending_migration_identity=expected,
            pending_migration_launch=control.entry(SCIENCE_ROOT / "migration_launch/record.json"),
            original_handoff_snapshot=snapshot,
            anchor_gpu=3,
            anchor_must_be_actually_held_before_replacing_old_migration=True,
            worker_signals_allowed=False,
            temporary_controller_freeze_allowed=False,
            scientific_source_or_protocol_hot_edit_allowed=False,
            max_gpu_workers=5,
            dispatch_priority=list(control.DISPATCH_ORDER),
            scientific_budget_and_resource_gates_unchanged=True,
            new_scientific_replay_sampling_or_optimizer_budget=0,
            only_original_V45_initialize_and_supervisor_may_continue=True,
            manual_stop_is_terminal=True,
            strict_fifo_or_next_release_guaranteed=False,
        ),
    )
    # Fresh interpreter avoids mixing workspace modules into the sealed patch.
    subprocess.run(
        [str(control.parent.PYTHON), "-u", str(directory / FILES[0]), "register"],
        cwd=REPO,
        check=True,
    )
    return control.checked(ROOT / "protocol/record.json")


def checked_patch(control):
    control.require(
        Path(__file__).resolve() == ROOT / "implementation" / FILES[0],
        "only the frozen queued-handoff entry may run",
    )
    value = control.checked(ROOT / "implementation/record.json")
    control.require(
        value["schema"] == "v46_independent_queued_handoff_implementation.v1"
        and value["files"] == list(FILES)
        and set(value["sha256"]) == set(FILES),
        "queued patch source ownership changed",
    )
    for name, expected in value["sha256"].items():
        control.require(
            control.sha(ROOT / "implementation" / name) == expected, "queued patch bytes changed"
        )
    checked_science(control)
    control.require(
        value["unchanged_scientific_implementation"]
        == control.entry(SCIENCE_ROOT / "implementation/record.json")
        and value["unchanged_scientific_preparation"]
        == control.entry(SCIENCE_ROOT / "preparation/record.json"),
        "queued patch cannot change prepared science",
    )
    return value


def supersede_pending(
    control, handoff, spec, barrier, stop_requested, *, sleep=time.sleep, monotonic=time.monotonic
):
    # Holding the actual final lease prevents the old migration from completing
    # its eight-lock barrier between our final identity check and pidfd signal.
    control.require(3 in barrier.held, "actual anchor lease required before old migration stop")
    control.require(not stop_requested(), "explicit stop before pending migration replacement")
    expected, snapshot = pending_migration(control, handoff)
    authority = control.checked(ROOT / "authorization/record.json")
    control.require(
        expected == authority["pending_migration_identity"],
        "pending owner differs from authorization",
    )
    control.publish(
        ROOT / "supersession_intent/record.json",
        dict(
            schema="v46_anchor_bound_pending_migration_stop_intent.v1",
            at=control.now(),
            target=expected,
            authorization=control.entry(ROOT / "authorization/record.json"),
            actual_anchor_gpu=3,
            actual_held_gpus=sorted(barrier.held),
            old_handoff_snapshot=snapshot,
            worker_signals_sent=0,
            scientific_supervisor_signals_sent=0,
            scientific_controller_signals_sent=0,
            queued_protocol=control.entry(ROOT / "protocol/record.json"),
        ),
    )
    control.require(not stop_requested(), "explicit stop before pending migration pidfd signal")
    handoff.signal_supervisor(expected)
    started = monotonic()
    while not handoff._exited(expected, handoff.process_identity):
        control.require(
            monotonic() - started <= 600, "old pending migration did not exit within shutdown grace"
        )
        sleep(0.2)
    closed = control.checked(SCIENCE_ROOT / "handoff_01/closeout/record.json")
    control.require(
        closed["status"] == "STOPPED_NO_MIGRATION"
        and closed["worker_signals_sent"] == closed["supervisor_signals_sent"] == 0
        and closed["supervisor_signal_attempted"] is False
        and closed["successor_started"] is False,
        "old migration was not stopped solely before scientific activation",
    )
    control.require(3 in barrier.held, "anchor lease lost before old migration exit verification")
    control.publish(
        ROOT / "supersession/record.json",
        dict(
            schema="v46_unactivated_V45_handoff_replaced.v1",
            at=control.now(),
            intent=control.entry(ROOT / "supersession_intent/record.json"),
            old_handoff_closeout=control.entry(SCIENCE_ROOT / "handoff_01/closeout/record.json"),
            target=expected,
            target_process_exited=True,
            target_os_exit_code_observed=False,
            pending_migration_signals_sent=1,
            worker_signals_sent=0,
            scientific_controller_signals_sent=0,
            scientific_supervisor_signals_sent=0,
            anchor_retained_until_old_migration_exit=3 in barrier.held,
            scientific_source_or_feedback_changed=False,
        ),
    )
    return control.entry(ROOT / "supersession/record.json")


def continue_science(control, supervisor_module, state, release_barrier):
    control.require(not state["stopped"], "explicit stop before scientific initialization")
    supervisor = supervisor_module.Supervisor(SCIENCE_ROOT, control=control)
    state["supervisor"] = supervisor
    supervisor.stopped = supervisor.stopped or state["stopped"]
    control.require(not supervisor.stopped, "explicit stop before scientific registration")
    control.initialize(SCIENCE_ROOT, handoff_record=ROOT / "closeout/record.json")
    control.checked_protocol(SCIENCE_ROOT)
    control.require(
        not state["stopped"] and not supervisor.stopped,
        "explicit stop during scientific initialization",
    )
    release_barrier()
    control.require(
        not state["stopped"] and not supervisor.stopped,
        "explicit stop before scientific supervisor start",
    )
    return supervisor.run()


def run():
    control, handoff = _control(), _handoff()
    checked_patch(control)
    authority = control.checked(ROOT / "authorization/record.json")
    control.require(
        authority["user_consent"] == "处理此问题", "new explicit handoff authorization required"
    )
    control.require(
        not (ROOT / "entry_launch/record.json").exists(), "single queued migration entry only"
    )
    pending_migration(control, handoff)
    control.publish(
        ROOT / "entry_launch/record.json",
        dict(
            schema="v46_single_queued_handoff_then_original_V45_supervisor.v1",
            at=control.now(),
            pid=os.getpid(),
            birth=control.birth(os.getpid()),
            command=[
                part.decode()
                for part in Path("/proc/self/cmdline").read_bytes().split(b"\0")
                if part
            ],
            implementation=control.entry(ROOT / "implementation/record.json"),
            authorization=control.entry(ROOT / "authorization/record.json"),
            original_scientific_root=str(SCIENCE_ROOT),
            new_science_started=False,
        ),
    )
    state = dict(stopped=False, supervisor=None)

    def request_stop(signum, _frame=None):
        state["stopped"] = True
        if state["supervisor"] is not None:
            state["supervisor"].request_stop(signum)

    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    for sig in handlers:
        signal.signal(sig, request_stop)

    def after_waiters(spec, barrier):
        return supersede_pending(control, handoff, spec, barrier, lambda: state["stopped"])

    try:
        supervisor_module = importlib.import_module("finqa_v45_supervisor")
        control.require(
            Path(supervisor_module.__file__).resolve()
            == SCIENCE_ROOT / "implementation/finqa_v45_supervisor.py",
            "unchanged sealed supervisor required",
        )
        return handoff.run(
            SCIENCE_ROOT,
            validate_quiescent=lambda _spec, queue: control.inheritance.preflight_clean_handoff(
                control.PARENT_ROOT, queue
            ),
            on_waiters_registered=after_waiters,
            on_quiesced=lambda _receipt, release: continue_science(
                control, supervisor_module, state, release
            ),
            stop_requested=lambda: state["stopped"],
        )
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "register", "run", "inspect"))
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "prepare":
        _control().require(args.source_commit is not None, "committed patch source required")
        value = prepare(args.source_commit)
    elif args.action == "register":
        control, handoff = _control(), _handoff()
        checked_patch(control)
        pending_migration(control, handoff)
        value = handoff.register(
            SCIENCE_ROOT, control.PARENT_ROOT, control.entry(ROOT / "authorization/record.json")
        )
    elif args.action == "run":
        value = run()
    else:
        value = checked_patch(_control())
    if isinstance(value, dict):
        print(json.dumps({key: value[key] for key in ("id", "status") if key in value}))


if __name__ == "__main__":
    main()
