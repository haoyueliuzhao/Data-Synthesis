"""Supervise fresh V47 durable attempts; explicit stop remains terminal.

The initial stopped-parent recovery is separately authorized and initialized.
There is no migration action and no independent total GPU-worker count limit.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
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
    return importlib.import_module("finqa_v47_controller")


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
                schema="v47_supervisor_capacity_change_wait.v1",
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
            str(attempt_root / "implementation/finqa_v47_controller.py"),
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
                schema="v47_supervised_fresh_attempt_dispatch.v1",
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
            Path(__file__).resolve() == self.root / "implementation/finqa_v47_supervisor.py"
            and Path(original.__file__).resolve()
            == self.root / "implementation/finqa_v43_supervisor.py",
            "both the new V47 entry and unchanged supervisor must be frozen",
        )
        return super().run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run",))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    Supervisor(args.root).run()


if __name__ == "__main__":
    main()
