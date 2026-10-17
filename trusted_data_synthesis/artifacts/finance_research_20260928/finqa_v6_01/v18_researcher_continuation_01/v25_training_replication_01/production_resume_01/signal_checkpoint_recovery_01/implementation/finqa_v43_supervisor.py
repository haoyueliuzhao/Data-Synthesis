"""One persistent owner; retry only freshly audited durable scientific boundaries."""

from __future__ import annotations

import argparse
import fcntl
import importlib
import os
import signal
import subprocess
import time
from pathlib import Path

BACKOFF_SECONDS = (30, 60, 120, 300)


class Supervisor:
    def __init__(self, root, *, control=None, spawn=None, sleep=time.sleep, clock=time.monotonic):
        self.control = control or importlib.import_module("finqa_v43_controller")
        self.root = Path(root).resolve()
        self.control.require(self.root == self.control.ROOT, "fixed V43 supervision root required")
        self.spawn = spawn or subprocess.Popen
        self.sleep, self.clock = sleep, clock
        self.stopped = False
        self.received_signals = []
        self.child = self.child_identity = None
        self.signal_forwarded = False

    def request_stop(self, signum, _frame=None):
        # No I/O and no restart from signal handlers. The owner loop forwards once.
        self.stopped = True
        self.received_signals.append(signum)

    def update(self, phase, **extra):
        self.control.status(
            self.root / "supervisor",
            dict(
                phase=phase,
                supervisor_pid=os.getpid(),
                manual_stop_requested=self.stopped,
                received_signals=list(self.received_signals),
                **extra,
            ),
        )

    def publish(self, relative, body):
        return self.control.publish(
            self.root / "supervisor" / relative / "record.json", dict(at=self.control.now(), **body)
        )

    def stop_owned_child_once(self):
        if self.child is None or self.signal_forwarded or self.child.poll() is not None:
            return
        self.control.require(
            self.control.birth(self.child.pid) == str(self.child_identity["birth"]),
            "child PID/birth changed before forwarding explicit stop",
        )
        os.kill(self.child.pid, signal.SIGTERM)
        self.signal_forwarded = True

    def backoff(self, attempt_number):
        delay = BACKOFF_SECONDS[min(attempt_number - 1, len(BACKOFF_SECONDS) - 1)]
        start = self.clock()
        while not self.stopped and self.clock() - start < delay:
            self.sleep(max(0, min(1, delay - (self.clock() - start))))
        self.publish(
            f"attempt{attempt_number:04d}/backoff",
            dict(
                schema="v43_inter_attempt_backoff_accounting.v1",
                requested_seconds=delay,
                actual_elapsed_seconds=max(0, self.clock() - start),
                separate_from_parent_worker_compute_and_resource_wait_accounting=True,
                manual_stop_requested=self.stopped,
            ),
        )
        return not self.stopped

    def launch(self, attempt_root, number):
        control = self.control
        control.checked_protocol(attempt_root)
        control.require(
            not (attempt_root / "launch_01/record.json").exists(),
            "a previous controller attempt cannot be relaunched",
        )
        command = [
            str(control.parent.PYTHON),
            "-u",
            str(attempt_root / "implementation/finqa_v43_controller.py"),
            "run",
            "--root",
            str(attempt_root),
        ]
        output = attempt_root / "supervised_controller.log"
        with output.open("xb") as stream:
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
                schema="v43_supervised_fresh_attempt_dispatch.v1",
                attempt_number=number,
                attempt_root=str(attempt_root),
                command=command,
                **self.child_identity,
                previous_attempt_relaunched=False,
            ),
        )

    def wait_child(self, attempt_root, number):
        observed = 0
        while self.child.poll() is None:
            if self.stopped:
                self.stop_owned_child_once()
            if self.clock() >= observed:
                self.update(
                    "STOPPING_MANUALLY" if self.stopped else "RUNNING",
                    attempt_number=number,
                    attempt_root=str(attempt_root),
                    child=dict(self.child_identity),
                )
                observed = self.clock() + 10
            self.sleep(1)
        code = self.child.poll()
        self.publish(
            f"attempt{number:04d}/actual_exit",
            dict(
                schema="v43_supervised_controller_actual_exit.v1",
                attempt_number=number,
                attempt_root=str(attempt_root),
                returncode=code,
                **self.child_identity,
                manual_stop_requested=self.stopped,
                stop_forwarded=self.signal_forwarded,
            ),
        )
        return code

    def loop(self):
        control, attempt_root, number = self.control, self.root, 1
        while not self.stopped:
            self.launch(attempt_root, number)
            code = self.wait_child(attempt_root, number)
            if self.stopped:
                break
            result_path = attempt_root / "result/record.json"
            if code == 0 and result_path.exists():
                result = control.checked(result_path)
                control.require(
                    result.get("status") == "COMPLETE"
                    and result.get("nine_endpoint_models_complete") is True,
                    "successful controller must seal the complete original matrix",
                )
                self.publish(
                    "closeout",
                    dict(
                        status="COMPLETE",
                        actual_result=control.entry(result_path),
                        final_attempt=number,
                        automatic_attempts=number - 1,
                    ),
                )
                self.update("COMPLETE", attempt_number=number)
                return "COMPLETE"
            # A direct lawful stop of the scientific controller also terminates
            # the supervision request, even if the observer itself saw no signal.
            audit = attempt_root / "signal_audit/record.json"
            if audit.exists() and control.checked(audit).get("received_signals"):
                self.stopped = True
                break
            try:
                decision = control.inheritance.validate_safe_recovery(attempt_root)
            except Exception as error:
                decision = dict(
                    allowed=False,
                    reason="safe-boundary audit rejected",
                    error_type=type(error).__name__,
                    error=str(error),
                )
            self.publish(
                f"attempt{number:04d}/recovery_decision",
                dict(schema="v43_explicit_safe_boundary_recovery_decision.v1", **decision),
            )
            if decision.get("allowed") is not True:
                self.publish(
                    "closeout",
                    dict(
                        status="STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY",
                        final_attempt=number,
                        decision=decision,
                    ),
                )
                self.update("STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY", attempt_number=number)
                return "STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY"
            self.update("BACKOFF_BEFORE_VERIFIED_RECOVERY", attempt_number=number)
            if not self.backoff(number):
                break
            next_root = self.root / "attempts" / f"attempt{number + 1:04d}"
            # Initialization verifies the same evidence again immediately before
            # publishing; failure is terminal and cannot widen the whitelist.
            control.prepare_automatic(next_root, parentroot=attempt_root)
            if self.stopped:
                break
            attempt_root, number = next_root, number + 1
        self.publish(
            "closeout",
            dict(
                status="STOPPED_BY_EXPLICIT_REQUEST",
                final_attempt=number,
                received_signals=list(self.received_signals),
                automatic_recovery_after_manual_stop=False,
            ),
        )
        self.update("STOPPED_BY_EXPLICIT_REQUEST", attempt_number=number)
        return "STOPPED_BY_EXPLICIT_REQUEST"

    def run(self):
        control = self.control
        control.require(
            Path(__file__).resolve() == self.root / "implementation/finqa_v43_supervisor.py",
            "only the frozen V43 supervisor may run",
        )
        control.checked_protocol(self.root)
        directory = self.root / "supervisor"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "owner.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.publish(
                "launch",
                dict(
                    schema="v43_single_persistent_supervisor.v1",
                    pid=os.getpid(),
                    birth=control.birth(os.getpid()),
                    protocol=control.entry(self.root / "protocol/record.json"),
                    backoff_seconds=list(BACKOFF_SECONDS),
                    explicit_stop_is_terminal=True,
                ),
            )
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            for sig in handlers:
                signal.signal(sig, self.request_stop)
            try:
                return self.loop()
            except BaseException as error:
                self.stopped = True
                self.stop_owned_child_once()
                self.publish(
                    "failure",
                    dict(
                        status="SUPERVISOR_STOPPED_NO_BLIND_RESTART",
                        error_type=type(error).__name__,
                        error=str(error),
                        automatic_recovery_not_attempted_after_audit_or_initialization_failure=True,
                    ),
                )
                raise
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run",))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    Supervisor(args.root).run()


if __name__ == "__main__":
    main()
