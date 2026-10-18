"""Explicitly authorized signal recovery with a separate control namespace.

All scientific state, IDs, frozen mathematics and durable worker data stay in
V56. Only this new control journal may consume the registered old unobserved
exit exception. No old exit code or stop history is rewritten.
"""

from __future__ import annotations

import argparse
import fcntl
import importlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SCIENTIFIC_ROOT = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01"
ROOT = SCIENTIFIC_ROOT / "signal_recovery_02"

# Capture signal sender metadata before any scientific import or library thread
# exists. The installed relay still invokes the ordinary main-thread handlers.
if __name__ == "__main__":
    early = argparse.ArgumentParser(add_help=False)
    early.add_argument("action", choices=("run", "supervise", "check-imports"))
    early.add_argument("--root", type=Path, default=ROOT)
    early.add_argument("--controller-attempt", type=int, default=1)
    early_args, _ = early.parse_known_args()
    from finqa_v57_signals import install
    install(early_args.root / "signals" / f"{early_args.action}-{os.getpid()}",
            role="supervisor" if early_args.action == "supervise" else "controller",
            context=dict(control_root=str(early_args.root),
                         controller_attempt=early_args.controller_attempt))

# V57 deliberately executes the original frozen V56 implementation, not the
# mutable workspace copies. The V57 registration itself is loaded separately.
sys.path.insert(0, str(SCIENTIFIC_ROOT / "implementation"))
import finqa_v56_controller as inherited

base = inherited.base
evaluation = inherited.evaluation
require = evaluation.require
POLL_SECONDS = inherited.POLL_SECONDS
TEMPORARY_CONTROLLER_EXIT = inherited.TEMPORARY_CONTROLLER_EXIT
TERMINAL_STATES = inherited.TERMINAL_STATES
TRANSIENT_ERRNOS = inherited.TRANSIENT_ERRNOS

if __name__ == "__main__":
    require(Path(inherited.__file__).resolve() == SCIENTIFIC_ROOT / "implementation/finqa_v56_controller.py",
            "V57 must inherit the original frozen V56 controller, not mutable workspace code")


def stop_requested(control_root):
    return inherited.stop_requested(control_root)


def execution_pythonpath(control_root, scientific_root=SCIENTIFIC_ROOT):
    # Preserve V56's registered auxiliary lookup directory. The frozen package
    # remains first; some original worker-only historical imports are helpers
    # in REPO/scripts rather than members of the 96-file copied package.
    return os.pathsep.join((str(Path(control_root) / "implementation"),
        str(Path(scientific_root) / "implementation"),
        str(base.REPO / "trusted_data_synthesis/scripts"), str(evaluation.FROZEN_SOURCE)))


def initialize_science():
    # Historical /proc helpers load controller aliases. Complete the original
    # science closure before any runtime.birth/inventory call can do that.
    original = importlib.import_module("finqa_v56_registration")
    original.modules()
    return original


def check_imports():
    original = initialize_science()
    protocol = original.checked_protocol(SCIENTIFIC_ROOT)
    implementation = original.checked(SCIENTIFIC_ROOT / "implementation/record.json")
    runtime = importlib.import_module("finqa_v54_runtime")
    loaded, frozen_packages = {}, {}
    for name, module in sorted(sys.modules.items()):
        source = getattr(module, "__file__", None)
        if not source:
            continue
        path = Path(source).resolve()
        if name == "trusted_synthesis" or name.startswith("trusted_synthesis."):
            require(path.is_relative_to(evaluation.FROZEN_SOURCE), "mutable scientific package was imported")
            frozen_packages[name] = str(path)
        if path.name in implementation["sha256"]:
            reference = evaluation.file_binding(path)
            require(reference["sha256"] == implementation["sha256"][path.name],
                    "loaded scientific implementation differs from original frozen bytes: " + name + " " + str(path))
            loaded[name] = reference
    # Lifecycle import subsequently loads its own separately verified historical
    # controller helpers, which can have the same basename as a science helper.
    # They must not be mistaken for the already-bound scientific closure.
    actual_birth = runtime.birth(os.getpid())
    require(not sys.modules["torch"].cuda.is_initialized(), "import preflight must never initialize CUDA")
    return evaluation.bound(dict(status="CPU_IMPORTS_VERIFIED", protocol_id=protocol["id"],
        actual_process_birth=actual_birth, original_frozen_modules=loaded,
        frozen_scientific_packages=frozen_packages, CUDA_initialized=False,
        science_closure_verified_before_lifecycle=True, scientific_workers_started=0))


def _control_binding(value, protocol, control_protocol):
    require(value["protocol_id"] == protocol["id"]
            and value["control_protocol_id"] == control_protocol["id"],
            "control journal belongs to another scientific point or authorization")


def _known_exits(prepared):
    rows = prepared["known_unobserved_attempts"]
    result = {str(Path(row["directory"]).resolve()): row for row in rows}
    require(len(result) == len(rows), "duplicate registered unobserved worker attempt")
    return result


def checked_attempt_directory(row, scientific_root=SCIENTIFIC_ROOT):
    directory = Path(row["directory"]).resolve()
    require(directory.is_relative_to(Path(scientific_root).resolve())
            and directory.parent.name == "attempts"
            and directory.name == f"attempt{row['attempt']:04d}",
            "worker attempt escaped its stable scientific directory")
    return directory


def audit_attempt_exit(row, prepared, protocol, runtime, scientific_root=SCIENTIFIC_ROOT):
    """The one-time old exception is evidence, never an invented waitpid exit."""
    directory = checked_attempt_directory(row, scientific_root)
    launch_path = directory / "launch/record.json"
    if not launch_path.exists():
        failed = evaluation.checked(directory / "launch_failure/record.json")
        require(failed["actual_child_created"] is False, "unsettled dispatch may have created a worker")
        return
    launch = evaluation.checked(launch_path)
    require(launch["protocol_id"] == protocol["id"]
            and launch["job"]["job_id"] == row["job_id"] and launch["attempt"] == row["attempt"],
            "worker launch changed its registered attempt")
    require(not inherited._same_live_identity(runtime, launch["pid"], launch["birth"]),
            "old worker identity is still alive")
    exit_path = directory / "actual_exit/record.json"
    if exit_path.exists():
        observed = evaluation.checked(exit_path)
        require(observed["protocol_id"] == protocol["id"]
                and observed["job_id"] == row["job_id"] and observed["attempt"] == row["attempt"]
                and observed["actual_waitpid_observed"] is True
                and (observed["pid"], observed["birth"]) == (launch["pid"], launch["birth"]),
                "worker exit does not match its actual launch")
        return
    allowed = _known_exits(prepared).get(str(directory))
    require(allowed is not None, "new unobserved worker exit is not authorized for automatic recovery")
    require(allowed["old_returncode"] is None
            and (allowed["pid"], allowed["birth"]) == (launch["pid"], launch["birth"])
            and evaluation.checked_file(allowed["launch"]).resolve() == launch_path,
            "old unobserved-exit authorization does not match the exact launch")
    evaluation.checked_file(allowed["identity_exit"])


class Controller(inherited.Controller):
    def __init__(self, root=ROOT, *, controller_attempt=1, runtime=None,
                 registration=None, scientific_registration=None):
        self.control_root = Path(root).resolve()
        require(self.control_root == ROOT, "V57 requires its independently registered control root")
        self.control_registration = registration or importlib.import_module("finqa_v57_registration")
        self.control_protocol = self.control_registration.checked_protocol(self.control_root)
        self.control_registration.checked_implementation(self.control_root)
        self.control_prepared = self.control_registration.checked_prepared(self.control_root)
        require(Path(self.control_protocol["scientific_root"]).resolve() == SCIENTIFIC_ROOT,
                "scientific data root cannot migrate during signal recovery")
        if scientific_registration is None:
            scientific_registration = initialize_science()
        super().__init__(SCIENTIFIC_ROOT, controller_attempt=controller_attempt,
                         runtime=runtime, registration=scientific_registration)
        require(self.protocol["id"] == self.control_protocol["scientific_protocol_id"],
                "signal recovery cannot replace the original scientific protocol")
        self.controller_directory = self.control_root / "controllers" / f"attempt{controller_attempt:04d}"

    def _restore_journal(self):
        require(not stop_requested(self.control_root), "explicit new stop forbids automatic restart")
        path = self.control_root / "journal/state.json"
        fresh = not path.exists()
        if fresh:
            require(self.controller_attempt == 1, "missing initial V57 control journal")
            journal = dict(self.control_prepared,
                           job_states=self.control_prepared["initial_job_states"])
            for row in journal["attempt_history"]:
                audit_attempt_exit(row, self.control_prepared, self.protocol, self.runtime, self.root)
        else:
            journal = evaluation.checked(path)
            _control_binding(journal, self.protocol, self.control_protocol)
            inherited._require_empty_settled_journal(journal)
        if journal["evaluation_registered"]:
            plan = evaluation.checked_plan(self.root)
            for key, job in plan["jobs"].items():
                self.jobs[key] = dict(job, kind="generate", dependencies=list(self.core), priority=6)
            self.evaluation_registered = True
        require(set(journal["job_states"]) == set(self.jobs), "scientific job roster changed")
        self.job_states = {key: dict(state) for key, state in journal["job_states"].items()}
        self.attempt_history = list(journal["attempt_history"])
        self.resource_wait_seconds = journal["resource_wait_seconds"]
        for key, reference in journal["accepted"].items():
            self.accepted[key] = evaluation.checked(evaluation.checked_file(reference))
            require(self.job_states[key]["status"] == "COMPLETE", "accepted job cannot be redispatched")
        for key, state in self.job_states.items():
            maximum = max((row["attempt"] for row in self.attempt_history if row["job_id"] == key), default=0)
            require(state["attempts"] == maximum, "attempt ordinal does not match immutable dispatch history")
            require((state["status"] == "COMPLETE") == (key in self.accepted),
                    "complete job lacks an accepted actual exit")
            if not fresh and state["status"] not in TERMINAL_STATES:
                try:
                    audit = self._audit(self.jobs[key])
                    require(audit["resume_allowed"] and audit["unknown_calls"] == 0
                            and audit["progress_units"] >= state["progress_units"],
                            "controller restart found unsafe durable scientific state")
                except Exception as error:
                    if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                        if state["status"] != "AUDIT_IO_WAIT":
                            state.update(status="PRE_DISPATCH_AUDIT_WAIT")
                        state.update(actual_errno=error.errno, next_eligible_epoch=time.time() + 300)
                    else:
                        state.update(status="HARD_BLOCKED", reason="controller-restart durable audit failed", error=str(error))
        self._block_dependencies()

    def journal(self):
        value = dict(schema="v57_actual_job_attempt_journal.v1", protocol_id=self.protocol["id"],
            control_protocol_id=self.control_protocol["id"], controller_attempt=self.controller_attempt,
            updated_epoch=time.time(), active_jobs=[dict(job_id=key, pid=child.process.pid,
                birth=child.birth, gpu_index=child.gpu, attempt=child.attempt) for key, child in self.active.items()],
            job_states=self.job_states, attempt_history=self.attempt_history,
            accepted={key: evaluation.file_binding(self.job_directory(self.jobs[key]) / "accepted/record.json")
                      for key in self.accepted}, evaluation_registered=self.evaluation_registered,
            resource_wait_seconds=self.resource_wait_seconds,
            inherited_unobserved_exits_not_reclassified=True)
        base._status(self.control_root / "journal/state.json", evaluation.bound(value))

    def status(self, status):
        base._status(self.control_root / "queue/status.json", dict(schema="v57_per_job_queue.v1",
            protocol_id=self.protocol["id"], control_protocol_id=self.control_protocol["id"],
            status=status, controller_attempt=self.controller_attempt, updated_epoch=time.time(),
            active_workers=[dict(job_id=key, pid=child.process.pid, birth=child.birth,
                gpu_index=child.gpu, attempt=child.attempt, lifecycle=child.lifecycle)
                for key, child in self.active.items()], job_states=self.job_states,
            accepted_jobs=list(self.accepted), max_gpu_workers=4,
            resource_wait_seconds=self.resource_wait_seconds, evaluation_registered=self.evaluation_registered))

    def launch(self, job, acquired):
        """Same cold V56 worker contract, with a stdlib-only signal-aware wrapper."""
        row, lease, admission = acquired
        key, state = job["job_id"], self.job_states[job["job_id"]]
        stable = self.job_directory(job)
        try:
            before = self._audit(job)
            require(before["resume_allowed"] and before["unknown_calls"] == 0,
                    "job is not safe to enter an automatic attempt")
        except Exception as error:
            lease.close()
            if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                state.update(status="PRE_DISPATCH_AUDIT_WAIT", reason="temporary durable-evidence read failure",
                             actual_errno=error.errno, next_eligible_epoch=time.time() + 300)
            else:
                state.update(status="HARD_BLOCKED", reason="pre-dispatch durable-state audit failed", error=str(error))
            self._block_dependencies()
            return
        attempt = state["attempts"] + 1
        directory = stable / "attempts" / f"attempt{attempt:04d}"
        require(not directory.exists(), "attempt directories are immutable and cannot be reused")
        try:
            evaluation.publish(directory / "dispatch_intent/record.json", dict(
                schema="v57_cold_attempt_dispatch_intent.v1", protocol_id=self.protocol["id"],
                control_protocol_id=self.control_protocol["id"], job=job, attempt=attempt,
                gpu_index=row["index"], gpu_uuid=row["uuid"], durable_before=before,
                admission=admission, created_epoch=time.time()))
            state.update(status="DISPATCHING", attempts=attempt, progress_units=before["progress_units"],
                         durable_progress_digest=before["durable_progress_digest"])
            self.attempt_history.append(dict(job_id=key, attempt=attempt, directory=str(directory)))
            self.journal()
        except BaseException:
            lease.close()
            raise
        wrapper = str(self.control_root / "implementation/finqa_v57_worker.py")
        if job["kind"] == "generate":
            arguments = [wrapper, "--mode", "evaluation", "worker", "--root", str(self.root),
                         "--job", key, "--gpu", str(row["index"])]
        else:
            arguments = [wrapper, "--mode", "science", "--root", str(self.root),
                         "--seed", str(job["seed"]), "--stage", job["stage"], "--gpu-index", str(row["index"])]
        command = ["/usr/bin/taskset", "--cpu-list", self.protocol["cpu_affinity"][str(row["index"])],
                   str(base.PYTHON), "-u", *arguments]
        environment = self.runtime.worker_environment(row)
        environment.update(CUDA_VISIBLE_DEVICES=row["uuid"], V54_GPU_LEASE_FD=str(lease.fileno()),
            V54_JOB_ID=key, V56_ATTEMPT_ID=f"attempt{attempt:04d}", V56_ATTEMPT_DIR=str(directory),
            V57_CONTROL_ROOT=str(self.control_root), V57_SIGNAL_LOG_DIR=str(directory / "signals"),
            PYTHONPATH=execution_pythonpath(self.control_root, self.root))
        try:
            with (directory / "worker.log").open("xb") as stream:
                process = subprocess.Popen(command, cwd=base.REPO, env=environment, stdout=stream,
                    stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(lease.fileno(),))
        except BaseException as error:
            lease.close()
            failure = inherited.launch_failure_record(error)
            evaluation.publish(directory / "launch_failure/record.json", dict(
                schema="v56_actual_pre_child_launch_failure.v1", protocol_id=self.protocol["id"],
                job_id=key, attempt=attempt, **failure))
            failure["evidence"] = [evaluation.file_binding(directory / "launch_failure/record.json")]
            self._record_decision(job, directory, failure, before)
            self.journal()
            return
        child = base.Child(job=job, gpu=row["index"], uuid=row["uuid"], process=process, lease=lease,
            birth=self.runtime.birth(process.pid), pidfd=None, directory=stable, started_epoch=time.time())
        child.attempt, child.attempt_dir, child.durable_before = attempt, directory, before
        self.active[key] = child
        if hasattr(os, "pidfd_open"):
            try:
                child.pidfd = os.pidfd_open(process.pid)
            except ProcessLookupError:
                pass
        evaluation.publish(directory / "launch/record.json", dict(schema="v57_actual_attempt_launch.v1",
            protocol_id=self.protocol["id"], control_protocol_id=self.control_protocol["id"],
            job=job, attempt=attempt, pid=process.pid, birth=child.birth, gpu_index=child.gpu,
            gpu_uuid=child.uuid, command=command, admission=admission, inherited_gpu_lease=True,
            original_frozen_scientific_entrypoint=True, started_epoch=child.started_epoch))
        state.update(status="RUNNING", pid=process.pid, birth=child.birth, gpu_index=child.gpu)
        base.can_dispatch(self.active)
        self.journal()

    def finish(self):
        require(self.evaluation_registered and set(self.jobs) == set(self.accepted) and not self.active,
                "all fixed generation jobs require real successful exits before scoring")
        panels = {}
        for panel, *_ in evaluation.PANEL_SPECS:
            require(not self.explicit_stop and not stop_requested(self.control_root),
                    "explicit stop before next complete-panel scoring")
            panels[panel] = evaluation.score(self.root, panel)
        require(not self.explicit_stop and not stop_requested(self.control_root), "explicit stop before final decision")
        complete = all(all(row["status"] == "COMPLETE" for row in summary["comparisons"].values())
                       for summary in panels.values())
        decision = base.stats.advancement(panels[evaluation.PRIMARY_PANEL], contracts_complete=complete)
        accounting = self.feedback_recovery_accounting(require_complete=True)
        inherited_feedback = self.protocol["feedback_inheritance"]
        require(inherited_feedback["inherited_complete_episodes"] == 70
                and inherited_feedback["inherited_partial_returned_turns"] == 3
                and self.prepared["remaining_feedback_episodes"] == 2030,
                "original inherited and newly completed feedback accounting changed")
        evaluation.publish(self.root / "promotion/record.json", dict(
            schema="v56_directional_development_decision.v1", protocol_id=self.protocol["id"],
            primary_summary=evaluation.file_binding(self.root / "evaluations/panels" /
                evaluation.PRIMARY_PANEL / "summary/record.json"), all_panels_complete=complete, **decision))
        result = evaluation.publish(self.control_root / "closeout/record.json", dict(
            schema="v57_fixed_experiment_control_recovery_closeout.v1", protocol_id=self.protocol["id"],
            control_protocol_id=self.control_protocol["id"], status="COMPLETE" if complete else "EVALUATION_INCOMPLETE",
            active_workers=0, accepted_jobs=len(self.accepted), logical_branches=9, snapshots=18,
            logical_C05_feedback_sessions=2100, complete_feedback_sessions_inherited_before_V56=70,
            incomplete_feedback_sessions_completed_across_V56_V57=2030,
            inherited_returns_regenerated=0, new_evaluation_sessions=12267, new_API_calls=0,
            old_test1147_new_generation=0, actual_new_optimizer_budget=self.prepared["actual_new_optimizer_budget"],
            resource_wait_seconds=self.resource_wait_seconds, feedback_request_recovery=accounting,
            panel_summaries={panel: evaluation.file_binding(self.root / "evaluations/panels" /
                panel / "summary/record.json") for panel in panels},
            promotion=evaluation.file_binding(self.root / "promotion/record.json"),
            actual_attempts=self.attempt_history, job_states=self.job_states,
            old_unobserved_exits_not_reclassified=True, old_stop_history_unchanged=True,
            automatic_followup_started=False, finished_epoch=time.time()))
        self.status(result["status"])
        return result

    def _terminal(self, status):
        self.journal()
        self.status(status)
        return evaluation.publish(self.control_root / "closeout/record.json", dict(
            schema="v57_per_job_recovery_closeout.v1", protocol_id=self.protocol["id"],
            control_protocol_id=self.control_protocol["id"], status=status, active_workers=0,
            job_states=self.job_states, accepted_jobs=list(self.accepted), attempt_count=len(self.attempt_history),
            resource_wait_seconds=self.resource_wait_seconds, automatic_restart_allowed=False,
            old_unobserved_exits_not_reclassified=True, finished_epoch=time.time()))

    def _stop(self, reason):
        self.explicit_stop = True
        marker = self.control_root / "control/stop_requested/record.json"
        if not marker.exists():
            evaluation.publish(marker, dict(schema="v57_terminal_explicit_stop.v1",
                protocol_id=self.protocol["id"], control_protocol_id=self.control_protocol["id"],
                reason=reason, at_epoch=time.time(), automatic_restart_allowed=False))
        deadline = time.monotonic() + base.STOP_GRACE_SECONDS
        for child in self.active.values():
            self._signal(child, signal.SIGTERM)
        while self.active and time.monotonic() < deadline:
            self.reap()
            self.status("STOPPING_NO_AUTO_RESTART")
            if self.active:
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
        for child in self.active.values():
            self._signal(child, signal.SIGKILL)
        while self.active:
            self.reap()
            if self.active:
                time.sleep(0.2)
        return self._terminal("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME")

    def run(self):
        # The original science lock prevents any concurrent old or new controller.
        with (self.root / "owner.lock").open("a") as science_owner, (self.control_root / "owner.lock").open("a") as owner:
            fcntl.flock(science_owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(not stop_requested(self.control_root), "explicit stop forbids controller restart")
            evaluation.publish(self.controller_directory / "launch/record.json", dict(
                schema="v57_controller_attempt_launch.v1", protocol_id=self.protocol["id"],
                control_protocol_id=self.control_protocol["id"], controller_attempt=self.controller_attempt,
                pid=os.getpid(), birth=self.runtime.birth(os.getpid()), started_epoch=time.time()))
            self.journal()
            requested = []
            previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
            def request(signum, _frame):
                requested.append(signum)
                self.explicit_stop = True
            for sig in previous:
                signal.signal(sig, request)
            try:
                while True:
                    if requested or stop_requested(self.control_root):
                        return self._stop(dict(signals=requested, marker=stop_requested(self.control_root)))
                    self.reap()
                    self.refresh_deferred_audits()
                    if not self.evaluation_registered and set(self.core) <= set(self.accepted) and not self.active:
                        self.seal_training()
                    if self.evaluation_registered and set(self.jobs) == set(self.accepted) and not self.active:
                        return self.finish()
                    self._block_dependencies()
                    if not self.active and all(s["status"] in TERMINAL_STATES for s in self.job_states.values()):
                        return self._terminal("BLOCKED_OPERATOR_REQUIRED")
                    dispatched = False
                    for job in self.ready():
                        if requested or stop_requested(self.control_root) or not base.can_dispatch(self.active):
                            break
                        acquired = self.acquire(job)
                        if acquired is not None:
                            self.launch(job, acquired)
                            dispatched = True
                    now = time.monotonic()
                    if not dispatched and self.ready() and base.can_dispatch(self.active):
                        if self.wait_started is not None:
                            self.resource_wait_seconds += now - self.wait_started
                        self.wait_started = now
                    else:
                        self.wait_started = None
                    self.journal()
                    blocked = any(s["status"] in ("HARD_BLOCKED", "DEPENDENCY_BLOCKED")
                                  for s in self.job_states.values())
                    self.status("RUNNING_WITH_BLOCKED_JOBS" if blocked else "RUNNING" if self.active
                                else "WAITING_OR_BOUNDED_BACKOFF")
                    time.sleep(POLL_SECONDS)
            except BaseException as error:
                if requested or stop_requested(self.control_root):
                    return self._stop(dict(signals=requested, marker=stop_requested(self.control_root)))
                transient = isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS and not self.active
                evaluation.publish(self.controller_directory / "failure/record.json", dict(
                    schema="v57_actual_controller_failure.v1", protocol_id=self.protocol["id"],
                    control_protocol_id=self.control_protocol["id"], error_type=type(error).__name__,
                    actual_errno=getattr(error, "errno", None), error=str(error),
                    transient_without_active_children=transient, active_children=list(self.active),
                    automatic_restart_requested=transient))
                if transient:
                    self.journal()
                    return dict(status="CONTROLLER_TRANSIENT_FAILURE", id=self.control_protocol["id"])
                if self.active:
                    return self._stop(dict(kind="CONTROLLER_IMPLEMENTATION_OR_UNKNOWN", error=str(error)))
                return self._terminal("BLOCKED_OPERATOR_REQUIRED")
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)


def controller_restart_audit(control_root, protocol, control_protocol, prepared, runtime):
    root = Path(control_root)
    require(not stop_requested(root), "explicit stop is terminal")
    journal = evaluation.checked(root / "journal/state.json")
    _control_binding(journal, protocol, control_protocol)
    inherited._require_empty_settled_journal(journal)
    for row in journal["attempt_history"]:
        audit_attempt_exit(row, prepared, protocol, runtime)
    leases = []
    try:
        for gpu in range(8):
            path = base.GPU_LEASE_ROOT / ("gpu-" + evaluation.digest(protocol["gpu_uuids"][str(gpu)]) + ".lock")
            lease = path.open("a")
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                lease.close()
                raise
            leases.append(lease)
    finally:
        for lease in leases:
            lease.close()
    return journal


def stop_orphaned_workers(control_root, protocol, control_protocol, runtime, *, reason=None):
    root = Path(control_root)
    marker = root / "control/stop_requested/record.json"
    if not marker.exists():
        evaluation.publish(marker, dict(schema="v57_terminal_fault_stop.v1" if reason else "v57_terminal_explicit_stop.v1",
            protocol_id=protocol["id"], control_protocol_id=control_protocol["id"],
            reason=reason or "explicit supervisor/controller stop",
            at_epoch=time.time(), automatic_restart_allowed=False))
    path, rows = root / "journal/state.json", []
    if path.exists():
        journal = evaluation.checked(path)
        _control_binding(journal, protocol, control_protocol)
        for active in journal["active_jobs"]:
            history = [row for row in journal["attempt_history"]
                       if (row["job_id"], row["attempt"]) == (active["job_id"], active["attempt"])]
            require(len(history) == 1, "orphan worker needs one actual dispatch history")
            directory = checked_attempt_directory(history[0])
            launch = evaluation.checked(directory / "launch/record.json")
            require(launch["protocol_id"] == protocol["id"] and launch["control_protocol_id"] == control_protocol["id"]
                    and launch["job"]["job_id"] == active["job_id"] and launch["attempt"] == active["attempt"]
                    and (launch["pid"], launch["birth"]) == (active["pid"], active["birth"]),
                    "orphan stop requires matching new journal and actual launch identity")
            rows.append(dict(job_id=active["job_id"], pid=active["pid"], birth=active["birth"],
                launch=evaluation.file_binding(directory / "launch/record.json"), signals_sent=[]))
    deadline = time.monotonic() + base.STOP_GRACE_SECONDS
    for row in rows:
        if inherited._same_live_identity(runtime, row["pid"], row["birth"]):
            try:
                os.kill(row["pid"], signal.SIGTERM)
                row["signals_sent"].append(signal.SIGTERM)
            except ProcessLookupError:
                pass
    while time.monotonic() < deadline and any(inherited._same_live_identity(runtime, r["pid"], r["birth"]) for r in rows):
        time.sleep(max(0, min(POLL_SECONDS, deadline - time.monotonic())))
    for row in rows:
        if inherited._same_live_identity(runtime, row["pid"], row["birth"]):
            try:
                os.kill(row["pid"], signal.SIGKILL)
                row["signals_sent"].append(signal.SIGKILL)
            except ProcessLookupError:
                pass
    final_deadline = time.monotonic() + 30
    while time.monotonic() < final_deadline and any(inherited._same_live_identity(runtime, r["pid"], r["birth"]) for r in rows):
        time.sleep(0.2)
    for row in rows:
        row.update(identity_observed_exited=not inherited._same_live_identity(runtime, row["pid"], row["birth"]),
                   OS_exitcode_independently_observed=False, OS_exitcode=None)
    return evaluation.publish(root / "supervisor/orphan_stop/record.json", dict(
        schema="v57_explicit_stop_orphan_identity_audit.v1", protocol_id=protocol["id"],
        control_protocol_id=control_protocol["id"], workers=rows,
        all_identities_observed_exited=all(r["identity_observed_exited"] for r in rows),
        shared_cooperative_grace_seconds=base.STOP_GRACE_SECONDS,
        stop_reason=reason or "explicit supervisor/controller stop",
        automatic_restart_allowed=False, nonchild_waitpid_or_exit_zero_not_fabricated=True))


def supervise(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered supervisor control root")
    registration = importlib.import_module("finqa_v57_registration")
    original = initialize_science()
    runtime = importlib.import_module("finqa_v54_runtime")
    control_protocol = registration.checked_protocol(root)
    registration.checked_implementation(root)
    prepared = registration.checked_prepared(root)
    protocol = original.checked_protocol(SCIENTIFIC_ROOT)
    require(protocol["id"] == control_protocol["scientific_protocol_id"], "original scientific protocol changed")
    directory = root / "supervisor"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "owner.lock").open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "launch/record.json").exists() and not stop_requested(root),
                "supervisor is fresh once and explicit stop is terminal")
        evaluation.publish(directory / "launch/record.json", dict(schema="v57_supervisor_launch.v1",
            protocol_id=protocol["id"], control_protocol_id=control_protocol["id"],
            pid=os.getpid(), birth=runtime.birth(os.getpid()), started_epoch=time.time()))
        requested = []
        previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        for sig in previous:
            signal.signal(sig, lambda signum, _frame: requested.append(signum))
        attempt, no_progress, last_accepted = 0, 0, len(prepared["accepted"])
        final_status, fault_stopped = "BLOCKED_OPERATOR_REQUIRED", False
        try:
            while not requested and not stop_requested(root):
                attempt += 1
                command = [str(base.PYTHON), "-u", str(root / "implementation/finqa_v57_controller.py"),
                           "run", "--root", str(root), "--controller-attempt", str(attempt)]
                env = dict(os.environ, V57_CONTROL_ROOT=str(root),
                           PYTHONPATH=execution_pythonpath(root))
                attempt_dir = directory / "attempts" / f"attempt{attempt:04d}"
                attempt_dir.mkdir(parents=True, exist_ok=False)
                with (attempt_dir / "controller.log").open("xb") as log:
                    process = subprocess.Popen(command, cwd=base.REPO, env=env, stdout=log,
                                               stderr=subprocess.STDOUT, start_new_session=True)
                identity = runtime.birth(process.pid)
                evaluation.publish(attempt_dir / "launch/record.json", dict(protocol_id=protocol["id"],
                    control_protocol_id=control_protocol["id"], controller_attempt=attempt,
                    pid=process.pid, birth=identity, command=command))
                signaled = False
                while process.poll() is None:
                    if (requested or stop_requested(root)) and not signaled:
                        marker = root / "control/stop_requested/record.json"
                        if not marker.exists():
                            evaluation.publish(marker, dict(schema="v57_terminal_explicit_stop.v1",
                                protocol_id=protocol["id"], control_protocol_id=control_protocol["id"],
                                signals=requested, at_epoch=time.time(), automatic_restart_allowed=False))
                        observed_birth = runtime.birth(process.pid)
                        if observed_birth is not None:
                            require(observed_birth == identity, "controller PID identity changed before stop")
                            os.kill(process.pid, signal.SIGTERM)
                            signaled = True
                    base._status(directory / "queue/status.json", dict(status="STOPPING" if signaled else "RUNNING",
                        controller_attempt=attempt, pid=process.pid, birth=identity, updated_epoch=time.time()))
                    time.sleep(POLL_SECONDS)
                code = process.returncode
                evaluation.publish(attempt_dir / "actual_exit/record.json", dict(protocol_id=protocol["id"],
                    control_protocol_id=control_protocol["id"], pid=process.pid, birth=identity,
                    returncode=code, actual_waitpid_observed=True))
                if requested or stop_requested(root) or code in (-signal.SIGTERM, -signal.SIGINT):
                    orphan = stop_orphaned_workers(root, protocol, control_protocol, runtime)
                    final_status = ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME" if orphan["all_identities_observed_exited"]
                                    else "STOP_REQUESTED_WORKER_EXIT_UNCONFIRMED")
                    break
                if (root / "closeout/record.json").exists():
                    final_status = evaluation.checked(root / "closeout/record.json")["status"]
                    break
                if code not in (TEMPORARY_CONTROLLER_EXIT, -signal.SIGKILL):
                    orphan = stop_orphaned_workers(root, protocol, control_protocol, runtime,
                        reason=dict(kind="CONTROLLER_EXIT_UNSAFE_TO_RESTART", returncode=code,
                                    actual_signal_sender_unknown=True, explicit_user_stop_inferred=False))
                    fault_stopped = True
                    final_status = ("BLOCKED_CONTROLLER_EXIT_WORKER_IDENTITIES_DRAINED" if orphan["all_identities_observed_exited"]
                                    else "BLOCKED_CONTROLLER_EXIT_WORKER_IDENTITIES_UNCONFIRMED")
                    break
                try:
                    journal = controller_restart_audit(root, protocol, control_protocol, prepared, runtime)
                except (ValueError, KeyError, OSError) as error:
                    evaluation.publish(attempt_dir / "restart_blocked/record.json", dict(
                        error_type=type(error).__name__, error=str(error), actual_exit=code,
                        missing_exitcode_was_not_fabricated=True, automatic_restart=False))
                    orphan = stop_orphaned_workers(root, protocol, control_protocol, runtime,
                        reason=dict(kind="CONTROLLER_RESTART_AUDIT_FAILED", returncode=code,
                                    actual_signal_sender_unknown=True, explicit_user_stop_inferred=False))
                    fault_stopped = True
                    final_status = ("BLOCKED_CONTROLLER_EXIT_WORKER_IDENTITIES_DRAINED" if orphan["all_identities_observed_exited"]
                                    else "BLOCKED_CONTROLLER_EXIT_WORKER_IDENTITIES_UNCONFIRMED")
                    break
                progress = len(journal["accepted"])
                no_progress = 0 if progress > last_accepted else no_progress + 1
                last_accepted = progress
                if no_progress >= inherited.NO_PROGRESS_LIMIT and code != TEMPORARY_CONTROLLER_EXIT:
                    final_status = "CONTROLLER_RESTART_LIMIT_REACHED"
                    break
                delay = (inherited.RESOURCE_COOLDOWN_SECONDS if no_progress >= inherited.NO_PROGRESS_LIMIT else
                         inherited.RETRY_BACKOFF_SECONDS[min(attempt - 1, len(inherited.RETRY_BACKOFF_SECONDS) - 1)])
                evaluation.publish(attempt_dir / "restart_admission/record.json", dict(
                    backoff_seconds=delay, no_active_workers=True, no_unsettled_dispatches=True,
                    all_project_leases_observed_released=True, accepted_jobs=progress,
                    automatic_restart=True, old_exit_code=code))
                until = time.monotonic() + delay
                while time.monotonic() < until and not requested and not stop_requested(root):
                    time.sleep(max(0, min(POLL_SECONDS, until - time.monotonic())))
            if requested or (stop_requested(root) and not fault_stopped):
                orphan_path = root / "supervisor/orphan_stop/record.json"
                orphan = evaluation.checked(orphan_path) if orphan_path.exists() else stop_orphaned_workers(
                    root, protocol, control_protocol, runtime)
                final_status = ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME" if orphan["all_identities_observed_exited"]
                                else "STOP_REQUESTED_WORKER_EXIT_UNCONFIRMED")
            result = evaluation.publish(directory / "closeout/record.json", dict(
                schema="v57_supervisor_closeout.v1", protocol_id=protocol["id"],
                control_protocol_id=control_protocol["id"], status=final_status,
                controller_attempts=attempt, automatic_restart_stopped=True, finished_epoch=time.time()))
            base._status(directory / "queue/status.json", dict(status=final_status,
                controller_attempt=attempt, updated_epoch=time.time(), active_controller=False))
            return result
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "supervise", "check-imports"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--controller-attempt", type=int, default=1)
    args = parser.parse_args()
    result = (check_imports() if args.action == "check-imports" else
              supervise(args.root) if args.action == "supervise" else
              Controller(args.root, controller_attempt=args.controller_attempt).run())
    print(json.dumps(dict(status=result["status"], id=result["id"]), sort_keys=True))
    return TEMPORARY_CONTROLLER_EXIT if result["status"] == "CONTROLLER_TRANSIENT_FAILURE" else 0 if result["status"] in ("COMPLETE", "CPU_IMPORTS_VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
