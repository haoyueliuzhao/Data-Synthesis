"""Supervise fresh V51 durable attempts; explicit stop remains terminal.

The initial live V50 handoff must naturally seal all active work before activation.
Every initial and automatic attempt keeps GPU0/GPU6 and the two-worker total cap.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import signal
import subprocess
import sys
from pathlib import Path

SOURCE_ROOT = Path("/data1/zhuxinrui/projects/Data-Synthesis") / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
SOURCE_BUNDLE = SOURCE_ROOT / "production_resume_01/host_memory_admission_01/implementation"
_directory = (
    Path(__file__).resolve().parent
    if Path(__file__).resolve().parent.name == "implementation"
    else SOURCE_BUNDLE
)
_spec = importlib.util.spec_from_file_location(
    __name__ + "_unchanged_v43_supervisor", _directory / "finqa_v43_supervisor.py"
)
original = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = original
_spec.loader.exec_module(original)
BACKOFF_SECONDS = original.BACKOFF_SECONDS


def _control():
    return importlib.import_module("finqa_v51_controller")


class _ExplicitStopBeforeLaunch(RuntimeError):
    pass


class Supervisor(original.Supervisor):
    def __init__(self, root, *, control=None, **kwargs):
        super().__init__(root, control=control or _control(), **kwargs)
        self._recovery_decision = None

    def publish(self, relative, body):
        if relative.endswith("/recovery_decision"):
            self._recovery_decision = body
        return super().publish(relative, body)

    def backoff(self, attempt_number):
        if not super().backoff(attempt_number):
            return False
        decision = self._recovery_decision or {}
        conditions = decision.get("retry_capacity_conditions")
        if conditions is None and decision.get("retry_capacity_condition") is not None:
            conditions = [decision["retry_capacity_condition"]]
        if not conditions:
            return True
        self.control.require(
            isinstance(conditions, list), "typed retry capacity conditions required"
        )
        started, ready, snapshot = self.clock(), False, None
        parentroot = (
            self.root
            if attempt_number == 1
            else self.root / "attempts" / f"attempt{attempt_number:04d}"
        )
        while not self.stopped:
            snapshot = self.control.recovery_capacity_snapshot(conditions)
            self.control.require(
                type(snapshot.get("ready")) is bool,
                "unknown capacity wait response cannot authorize a retry",
            )
            ready = snapshot["ready"]
            if ready:
                break
            self.update(
                "WAITING_FOR_CHANGED_RECOVERY_CAPACITY",
                attempt_number=attempt_number,
                attempt_root=str(parentroot),
                retry_capacity_conditions=conditions,
                retry_capacity_evidence_refs=decision.get("retry_capacity_evidence_refs", []),
                capacity_observation=snapshot,
            )
            self.sleep(10)
        self.publish(
            f"attempt{attempt_number:04d}/capacity_wait",
            dict(
                schema="v51_supervisor_capacity_change_wait.v1",
                parent_attempt_root=str(parentroot),
                retry_capacity_conditions=conditions,
                retry_capacity_evidence_refs=decision.get("retry_capacity_evidence_refs", []),
                actual_elapsed_seconds=max(0, self.clock() - started),
                capacity_ready=ready and not self.stopped,
                manual_stop_requested=self.stopped,
                final_capacity_observation=snapshot,
                charge_as_additional_next_attempt_resource_wait=True,
                mathematical_work_or_CUDA_started_by_supervisor=False,
            ),
        )
        return ready and not self.stopped

    def launch(self, attempt_root, number):
        control = self.control
        self._next_attempt_number = number
        if self.stopped:
            raise _ExplicitStopBeforeLaunch("stopped before controller dispatch")
        control.checked_protocol(attempt_root)
        control.require(
            not (attempt_root / "launch_01/record.json").exists(),
            "a previous controller attempt cannot be relaunched",
        )
        command = [
            str(control.parent.PYTHON),
            "-u",
            str(attempt_root / "implementation/finqa_v51_controller.py"),
            "run",
            "--root",
            str(attempt_root),
        ]
        output = attempt_root / "supervised_controller.log"
        with output.open("xb") as stream:
            if self.stopped:
                raise _ExplicitStopBeforeLaunch("stopped before controller spawn")
            self.child = self.spawn(
                command,
                cwd=control.REPO,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self.child_identity = dict(pid=self.child.pid, birth=control.birth(self.child.pid))
        control.require(
            self.child_identity["birth"] is not None,
            "controller exited before supervisor ownership established",
        )
        self.signal_forwarded = False
        self.publish(
            f"attempt{number:04d}/dispatch",
            dict(
                schema="v51_supervised_fresh_attempt_dispatch.v1",
                attempt_number=number,
                attempt_root=str(attempt_root),
                command=command,
                **self.child_identity,
                previous_attempt_relaunched=False,
            ),
        )
        if self.stopped:
            self.stop_owned_child_once()

    def loop(self):
        try:
            return super().loop()
        except _ExplicitStopBeforeLaunch:
            self.publish(
                "closeout",
                dict(
                    status="STOPPED_BY_EXPLICIT_REQUEST",
                    final_attempt=self._next_attempt_number,
                    received_signals=list(self.received_signals),
                    automatic_recovery_after_manual_stop=False,
                    controller_not_launched_after_stop=True,
                ),
            )
            self.update("STOPPED_BY_EXPLICIT_REQUEST")
            return "STOPPED_BY_EXPLICIT_REQUEST"

    def run(self):
        self.control.require(
            Path(__file__).resolve() == self.root / "implementation/finqa_v51_supervisor.py"
            and Path(original.__file__).resolve()
            == self.root / "implementation/finqa_v43_supervisor.py",
            "both the new V51 entry and unchanged supervisor must be frozen",
        )
        return super().run()


def migrate(root):
    """Observe one pinned live parent, then initialize and supervise exactly once."""
    control = _control()
    root = Path(root).resolve()
    control.require(
        root == control.ROOT
        and Path(__file__).resolve() == root / "implementation/finqa_v51_supervisor.py",
        "only the prepared frozen two-worker migration entry may run",
    )
    control.checked_implementation(root)
    preparation = control.checked_preparation()
    handoff = importlib.import_module("finqa_v51_handoff")
    control.require(
        Path(handoff.__file__).resolve() == root / "implementation/finqa_v51_handoff.py",
        "handoff must use the same frozen implementation",
    )
    control.publish(
        root / "migration_launch/record.json",
        dict(
            schema="v51_single_natural_drain_then_supervise_entry.v1",
            at=control.now(),
            pid=os.getpid(),
            birth=control.birth(os.getpid()),
            preparation=control.entry(root / "preparation/record.json"),
            handoff_mode=preparation["handoff_mode"],
            worker_signals_allowed=False,
            scientific_controller_started=False,
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

    def continue_once(_closeout, release_barrier):
        control.require(not state["stopped"], "migration stopped before initialization")
        supervisor = Supervisor(root, control=control)
        state["supervisor"] = supervisor
        supervisor.stopped = supervisor.stopped or state["stopped"]
        control.require(not supervisor.stopped, "migration stopped before new registration")
        control.initialize_with_handoff(root / "handoff_01/closeout/record.json", root=root)
        control.checked_protocol(root)
        control.require(
            not state["stopped"] and not supervisor.stopped,
            "migration stopped during initialization",
        )
        release_barrier()
        control.require(
            not state["stopped"] and not supervisor.stopped,
            "migration stopped before successor supervisor start",
        )
        return supervisor.run()

    def validate_quiescent(parentroot, queue):
        control.require(
            Path(parentroot).resolve() == Path(preparation["parent_root"]).resolve(),
            "handoff must retain the prepared parent attempt",
        )
        return control.inheritance.preflight_clean_handoff(Path(parentroot), queue)

    try:
        return handoff.run(
            root,
            validate_quiescent=validate_quiescent,
            on_quiesced=continue_once,
            stop_requested=lambda: state["stopped"],
        )
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("migrate", "run"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "migrate":
        migrate(args.root)
    else:
        Supervisor(args.root).run()


if __name__ == "__main__":
    main()
