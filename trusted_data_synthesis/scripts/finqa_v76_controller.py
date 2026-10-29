"""One Full path: two applications/training windows, then one unapplied probe.

Per-job recovery and actual-process-exit settlement reuse the frozen V63
lifecycle in a private operational namespace. No historical scientific finish,
six-branch registration or single-point diagnostic exception is reachable.
"""
from __future__ import annotations

import importlib
import fcntl
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import ModuleType

import finqa_v76_binding as binding
import finqa_v76_queue_base as base

ROOT = binding.ROOT
require = binding.require


def _private_lifecycle():
    source = binding.source_module("finqa_v63_controller")
    raw = Path(source.__file__).read_text()
    substitutions = (
        ("import finqa_v63_binding as binding", "import finqa_v76_binding as binding"),
        ("import finqa_v63_queue_base as base", "import finqa_v76_queue_base as base"),
        ("import finqa_v63_evaluation as evaluation", "evaluation = base.records"),
        ('return importlib.import_module("finqa_v63_worker")',
         'return importlib.import_module("finqa_v76_worker")'),
        ('"--seed", str(job["seed"]), "--stage", job["stage"],',
         '"--seed", str(job["seed"]), "--stage", job["job_id"],'),
        ('V56_ATTEMPT_ID=f"attempt{attempt:04d}", V56_ATTEMPT_DIR=str(directory),',
         'V56_ATTEMPT_ID=f"attempt{attempt:04d}", V56_ATTEMPT_DIR=str(directory), '
         'V76_ATTEMPT_ID=f"attempt{attempt:04d}", V76_ATTEMPT_DIR=str(directory),'),
    )
    for before, after in substitutions:
        require(raw.count(before) == 1, "frozen operational lifecycle structure changed: " + before)
        raw = raw.replace(before, after)
    raw = raw.replace("finqa_v63_registration", "finqa_v76_registration")
    raw = raw.replace("finqa_v63_runtime", "finqa_v76_resources")
    raw = raw.replace("finqa_v63_entry.py", "finqa_v76_entry.py")
    raw = raw.replace('schema="v63_', 'schema="v76_')
    module = ModuleType("_v76_frozen_durable_lifecycle")
    module.__file__, module.__package__ = str(Path(source.__file__).resolve()), ""
    sys.modules[module.__name__] = module
    exec(compile(raw, module.__file__ + "::V76_private_lifecycle", "exec"), module.__dict__)
    return module, source


inherited, original = _private_lifecycle()
TERMINAL_STATES, TRANSIENT_ERRNOS = inherited.TERMINAL_STATES, inherited.TRANSIENT_ERRNOS
_inherited_failure_decision = inherited.failure_decision

def failure_decision(failure, audit, *, previous_units, no_progress_failures, attempt):
    result = _inherited_failure_decision(failure,audit,previous_units=previous_units,
        no_progress_failures=no_progress_failures,attempt=attempt)
    if result["status"] in ("BACKOFF", "RESOURCE_COOLDOWN") and result.get("no_progress_failures",0) >= 3:
        return dict(result,status="HARD_BLOCKED",automatic_readmission=False,
            reason="three confirmed resource attempts without durable progress; no automatic expansion")
    if result["status"] == "BACKOFF":
        result["backoff_seconds"] = 300
    return result

inherited.failure_decision = failure_decision
stop_requested = inherited.stop_requested
_original_controller_restart_audit = inherited.controller_restart_audit
_original_stop_orphaned_workers = inherited.stop_orphaned_workers


def planned_jobs():
    return base.all_jobs()


def controller_restart_audit(root, protocol):
    journal = _original_controller_restart_audit(root, protocol)
    cpu = journal.get("cpu_analysis")
    if cpu is not None:
        directory = Path(root) / "final_analysis/attempt0001"
        launch = binding.checked(directory / "launch/record.json")
        actual = binding.checked(directory / "actual_exit/record.json")
        require(actual["actual_waitpid_observed"] is True and actual["returncode"] == 0
                and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"])
                and not inherited._same_live_identity(base.resource_api, launch["pid"], launch["birth"]),
                "unsettled or failed final CPU child forbids controller restart")
    return journal


def stop_orphaned_workers(root, protocol, runtime):
    result = _original_stop_orphaned_workers(root, protocol, runtime)
    directory = Path(root) / "final_analysis/attempt0001"
    path = directory / "launch/record.json"
    if not path.exists():
        return result
    launch = binding.checked(path)
    require(launch["protocol_id"] == protocol["id"]
            and launch["kind"] == "final_CPU_analysis", "CPU orphan launch identity changed")
    live = lambda: inherited._same_live_identity(runtime, launch["pid"], launch["birth"])
    signals_sent = []
    if live():
        os.kill(launch["pid"], signal.SIGTERM)
        signals_sent.append(signal.SIGTERM)
    deadline = time.monotonic() + base.STOP_GRACE_SECONDS
    while live() and time.monotonic() < deadline:
        time.sleep(1)
    if live():
        os.kill(launch["pid"], signal.SIGKILL)
        signals_sent.append(signal.SIGKILL)
    until = time.monotonic() + 30
    while live() and time.monotonic() < until:
        time.sleep(0.2)
    exited = not live()
    binding.publish(Path(root) / "supervisor/cpu_orphan_stop/record.json", dict(
        schema="v76_final_CPU_orphan_stop.v1", protocol_id=protocol["id"],
        launch=binding.entry(path), signals_sent=signals_sent,
        identity_observed_exited=exited, OS_exitcode_independently_observed=False,
        OS_exitcode=None, automatic_restart_allowed=False))
    return dict(result, all_identities_observed_exited=result["all_identities_observed_exited"] and exited)


inherited.controller_restart_audit = controller_restart_audit
inherited.stop_orphaned_workers = stop_orphaned_workers


def auto_recovery_policy():
    policy = original.auto_recovery_policy()
    for key in ("complete_six_new_branches_and_actual_exits_before_evaluation",
                "all_24_generation_actual_exits_before_any_private_scoring",
                "new_feedback_conditions", "new_feedback_batch"):
        policy.pop(key, None)
    policy.update(schema="v76_single_Full_path_durable_recovery.v1",
        max_gpu_workers=6, per_GPU_workers=1, primary_EX_lease_only=True,
        new_feedback_conditions=3, feedback_sessions_per_point=700,
        applied_updates=2, optimizer_updates=894,
        terminal_probe_applied=False, terminal_probe_extra_training=False,
        evaluation_jobs=6, evaluation_sessions=2649,
        new_point_class_passes=3, whole_point_class_tasks=744,
        later_point_requires_previous_training_actual_exit_zero=True,
        evaluation_requires_corresponding_training_actual_exit_zero=True,
        endpoint_evaluation_and_terminal_probe_may_overlap=True,
        intermediate_accuracy_never_selects_or_changes_path=True,
        all_registered_actual_exits_before_final_scoring=True,
        legacy_single_point_numeric_exceptions_inherited=False,
        automatic_controller_restart=False, controller_failure_automatic_restart=False,
        automatic_followup_authorized=False)
    policy.update(controller_restart="forbidden; single controller attempt",
        controller_unknown_crash_no_progress_restart_limit=0,
        controller_confirmed_resource_failure_max_attempts=1,
        no_progress_limit_action="stop after three consecutive attempts with no durable progress",
        resource_job_backoff_seconds=[300], no_progress_resource_cooldown_seconds=None,
        no_durable_progress_failure_limit=3)
    return policy


inherited.auto_recovery_policy = auto_recovery_policy


class Controller(inherited.Controller):
    def __init__(self, root=ROOT, *, controller_attempt=1, runtime=None, registration=None):
        self.root = Path(root).resolve()
        require(self.root == ROOT.resolve(), "V76 requires its independent closed-loop root")
        self.registration = registration or importlib.import_module("finqa_v76_registration")
        self.protocol = self.registration.checked_protocol(root)
        self.registration.checked_implementation(root)
        self.prepared = self.registration.checked_prepared(root)
        require(self.protocol["auto_recovery_policy"] == auto_recovery_policy(), "recovery policy changed")
        require(set(self.protocol["gpu_uuids"]) == {str(gpu) for gpu in range(8)}
                and Path(self.protocol["gpu_lease_root"]).resolve() == base.GPU_LEASE_ROOT.resolve()
                and self.protocol["max_gpu_workers"] == 6
                and self.protocol["max_workers_per_gpu"] == 1,
                "original primary leases and six-total/one-per-GPU contract required")
        self.runtime = runtime or base.resource_api.controller_runtime()
        self.priority = self.protocol["gpu_priority"]
        require(len(self.priority) == 8 and set(self.priority) == set(range(8)), "GPU priority changed")
        require(type(controller_attempt) is int and controller_attempt >= 1
                and not (self.root / "closeout/record.json").exists(), "terminal V76 cannot reopen")
        self.controller_attempt = controller_attempt
        self.controller_directory = self.root / "controllers" / f"attempt{controller_attempt:04d}"
        self.core, self.jobs = base.core_jobs(), base.all_jobs()
        self.active, self.accepted, self.launched = {}, {}, set()
        self.evaluation_registered = True  # Fixed roster; no score-dependent registration.
        self.job_states = {key: inherited._initial_state() for key in self.jobs}
        self.attempt_history, self.explicit_stop, self.wait_started = [], False, None
        self.cpu_analysis = None
        self.resource_wait_seconds = float(self.protocol.get("inherited_resource_wait_seconds", 0.0))
        require(math.isfinite(self.resource_wait_seconds) and self.resource_wait_seconds >= 0,
                "invalid resource waiting statistics")
        self._restore_journal()

    def _restore_journal(self):
        path = self.root / "journal/state.json"
        if not path.exists():
            require(self.controller_attempt == 1, "missing original controller journal")
            return
        require(not stop_requested(self.root), "explicit stop forbids restart")
        journal = binding.checked(path)
        require(journal["protocol_id"] == self.protocol["id"], "journal protocol changed")
        inherited._require_empty_settled_journal(journal)
        require(journal["evaluation_registered"] is True
                and set(journal["job_states"]) == set(self.jobs), "fixed 30-job roster changed")
        self.job_states, self.attempt_history = journal["job_states"], journal["attempt_history"]
        self.resource_wait_seconds = journal["resource_wait_seconds"]
        self.cpu_analysis = journal.get("cpu_analysis")
        for key, reference in journal["accepted"].items():
            self.accepted[key] = binding.read_ref(reference)
            require(self.job_states[key]["status"] == "COMPLETE", "accepted job not terminal")
        for key, job in self.jobs.items():
            state = self.job_states[key]
            if state["status"] in TERMINAL_STATES:
                continue
            # Future points legitimately have no context yet; their audit binds
            # the still-fixed predecessor, and cannot dispatch before acceptance.
            try:
                audit = self._audit(job)
                require(audit["resume_allowed"] and audit["unknown_calls"] == 0
                        and audit["progress_units"] >= state["progress_units"],
                        "unsafe or regressed scientific durable state")
            except Exception as error:
                if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                    state.update(status="PRE_DISPATCH_AUDIT_WAIT", actual_errno=error.errno,
                                 next_eligible_epoch=time.time() + 300)
                else:
                    state.update(status="HARD_BLOCKED", reason="controller restart audit failed", error=str(error))
        self._block_dependencies()

    def journal(self):
        value = dict(schema="v76_actual_job_attempt_journal.v1", protocol_id=self.protocol["id"],
            controller_attempt=self.controller_attempt, updated_epoch=time.time(),
            active_jobs=[dict(job_id=key, pid=child.process.pid, birth=child.birth,
                gpu_index=child.gpu, attempt=child.attempt) for key, child in self.active.items()],
            job_states=self.job_states, attempt_history=self.attempt_history,
            accepted={key: binding.entry(self.job_directory(self.jobs[key]) / "accepted/record.json")
                      for key in self.accepted}, evaluation_registered=True,
            resource_wait_seconds=self.resource_wait_seconds, cpu_analysis=self.cpu_analysis)
        base._status(self.root / "journal/state.json", base.bound(value))

    def _validate_coordinate(self, child, result):
        from finqa_v76_worker import validate_result
        validate_result(self.root, child.job, result)

    def seal_training(self):
        raise ValueError("V76 evaluation is preregistered by endpoint, not the V63 six-branch barrier")

    def _finish_cpu(self):
        from finqa_v76_analysis import resource_policy
        policy = resource_policy()
        require(self.protocol["final_analysis_resource_policy"] == policy, "CPU analysis policy changed")
        directory = self.root / "final_analysis/attempt0001"
        actual_path = directory / "actual_exit/record.json"
        if not actual_path.exists():
            require(not directory.exists(), "unsettled/failed CPU attempt cannot be relaunched")
            while self.runtime.host_memory()["available_bytes"] < policy["startup_required_available_bytes"]:
                require(not self.explicit_stop and not stop_requested(self.root), "explicit stop before CPU analysis")
                self.status("WAITING_FOR_FINAL_CPU_RESOURCES")
                time.sleep(base.POLL_SECONDS)
            binding.publish(directory / "dispatch_intent/record.json", dict(
                schema="v76_final_CPU_dispatch_intent.v1", protocol_id=self.protocol["id"],
                resource_policy=policy, only_one_CPU_attempt=True, no_GPU_workers_active=True))
            self.cpu_analysis = dict(status="DISPATCHING", directory=str(directory))
            self.journal()
            command = [str(base.PYTHON), "-u", str(self.root / "implementation/finqa_v76_entry.py"),
                       "--mode", "score", "--root", str(self.root), "--attempt-root", str(directory)]
            environment = dict(os.environ, CUDA_VISIBLE_DEVICES="",
                V76_CPU_ANALYSIS_ATTEMPT=str(directory),
                PYTHONPATH=os.pathsep.join((str(self.root / "implementation"),
                    binding.install_scientific_paths()["frozen_source_root"])))
            process, birth, sent, parent_violation = None, None, [], None
            try:
                with (directory / "analysis.log").open("xb") as log:
                    process = subprocess.Popen(command, cwd=base.REPO, env=environment,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                birth = self.runtime.birth(process.pid)
                require(isinstance(birth, str) and birth.isdigit() or process.poll() is not None,
                        "live final CPU PID birth must be established")
                binding.publish(directory / "launch/record.json", dict(
                    schema="v76_final_CPU_actual_launch.v1", protocol_id=self.protocol["id"],
                    kind="final_CPU_analysis", pid=process.pid, birth=birth, command=command))
                self.cpu_analysis.update(status="RUNNING", pid=process.pid, birth=birth)
                self.journal()
                stop_deadline = None
                while process.poll() is None:
                    memory, host = self.runtime.process_memory(process.pid), self.runtime.host_memory()
                    if isinstance(memory, dict) and (memory["peak_rss_bytes"] > policy["rss_historical_peak_limit_bytes"]
                            or host["available_bytes"] < policy["effective_host_available_reserve_bytes"]):
                        parent_violation = dict(memory=memory, host=host, epoch=time.time())
                    stopping = self.explicit_stop or stop_requested(self.root) or parent_violation is not None
                    if stopping and not sent and inherited._same_live_identity(self.runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGTERM)
                        sent.append(signal.SIGTERM)
                        stop_deadline = time.monotonic() + base.STOP_GRACE_SECONDS
                    if stop_deadline is not None and time.monotonic() >= stop_deadline and signal.SIGKILL not in sent:
                        if inherited._same_live_identity(self.runtime, process.pid, birth):
                            os.kill(process.pid, signal.SIGKILL)
                            sent.append(signal.SIGKILL)
                    self.status("STOPPING_FINAL_CPU_ANALYSIS" if stopping else "FINAL_CPU_ANALYSIS")
                    time.sleep(1)
            finally:
                if process is not None:
                    if process.poll() is None:
                        if inherited._same_live_identity(self.runtime, process.pid, birth):
                            os.kill(process.pid, signal.SIGTERM)
                            sent.append(signal.SIGTERM)
                        until = time.monotonic() + base.STOP_GRACE_SECONDS
                        while process.poll() is None and time.monotonic() < until:
                            time.sleep(1)
                        if process.poll() is None and inherited._same_live_identity(self.runtime, process.pid, birth):
                            os.kill(process.pid, signal.SIGKILL)
                            sent.append(signal.SIGKILL)
                    code = process.wait()
                    binding.publish(actual_path, dict(schema="v76_final_CPU_actual_exit.v1",
                        protocol_id=self.protocol["id"], pid=process.pid, birth=birth, returncode=code,
                        actual_waitpid_observed=True, signals_sent=sent, parent_resource_violation=parent_violation))
                    self.cpu_analysis.update(status="EXITED", returncode=code)
                    self.journal()
        launch, actual = binding.checked(directory / "launch/record.json"), binding.checked(actual_path)
        require(actual["protocol_id"] == self.protocol["id"] and actual["actual_waitpid_observed"] is True
                and actual["returncode"] == 0 and not actual["signals_sent"]
                and actual["parent_resource_violation"] is None
                and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"]),
                "final analysis requires an observed exit zero and unchanged resource hard gates")
        result = binding.checked(directory / "result/record.json")
        resources = binding.read_ref(result["resources"])
        require(result["status"] == resources["status"] == "COMPLETE"
                and result["protocol_id"] == resources["protocol_id"] == self.protocol["id"]
                and result["pid"] == resources["pid"] == launch["pid"]
                and resources["birth"] == launch["birth"] and resources["CUDA_initialized"] is False
                and resources["all_gates_passed"] is True and resources["policy"] == policy,
                "CPU result/resource proof belongs to another process or policy")
        binding.publish(self.root / "final_analysis/accepted/record.json", dict(
            schema="v76_final_CPU_result_actual_exit_accepted.v1", protocol_id=self.protocol["id"],
            result=binding.entry(directory / "result/record.json"), actual_exit=binding.entry(actual_path),
            resources=binding.entry(directory / "resources/closeout/record.json")))
        return result["analysis"]

    def finish(self):
        require(set(self.jobs) == set(self.accepted) and not self.active,
                "all 30 jobs need actual accepted exit zero before final analysis")
        require(len(self.core) == 24 and len(self.jobs) == 30, "registered closed-loop dose changed")
        require(not self.explicit_stop and not stop_requested(self.root), "explicit stop precedes analysis")
        binding.publish(self.root / "all_jobs_exit_barrier/record.json", dict(
            schema="v76_fixed_path_all_jobs_actual_exit_barrier.v1", protocol_id=self.protocol["id"],
            active_workers=[], scientific_jobs=24, evaluation_jobs=6,
            accepted_jobs={key: binding.entry(self.job_directory(job) / "accepted/record.json")
                           for key, job in self.jobs.items()},
            actual_exits={key: self.accepted[key]["actual_exit"] for key in self.jobs}))
        summary = self._finish_cpu()
        require(not self.explicit_stop and not stop_requested(self.root), "explicit stop before final closeout")
        require(summary.get("status") == "COMPLETE", "prespecified analysis is not complete")
        result = binding.publish(self.root / "closeout/record.json", dict(
            schema="v76_single_Full_path_closeout.v1", status="COMPLETE", protocol_id=self.protocol["id"],
            active_workers=0, accepted_jobs=30, scientific_jobs=24, evaluation_jobs=6,
            new_training_paths=2, new_independent_training_seeds=0,
            new_feedback_sessions=2100, optimizer_updates=894, task_exposures=4464,
            applied_Full_updates=2, terminal_candidate_probes=1,
            terminal_candidate_applied=False, final_training_step=1788,
            new_evaluation_sessions=2649, new_logical_sessions=4749,
            summary=summary, actual_attempts=self.attempt_history, job_states=self.job_states,
            resource_wait_seconds=self.resource_wait_seconds,
            historical_failures_or_exceptions_reclassified=False,
            automatic_followup_started=False, finished_epoch=time.time()))
        self.status("COMPLETE")
        return result


STOP_GRACE_SECONDS, POLL_SECONDS = base.STOP_GRACE_SECONDS, base.POLL_SECONDS

def _stop_marker(root, protocol, reason):
    path = Path(root) / "control/stop_requested/record.json"
    if path.exists():
        record = binding.checked(path)
        require(record["protocol_id"] == protocol["id"], "foreign stop marker")
        return dict(record,grace_deadline_epoch=record.get("grace_deadline_epoch",
            record.get("requested_epoch",record.get("at_epoch",path.stat().st_mtime))+STOP_GRACE_SECONDS))
    now = time.time()
    try:
        return binding.publish(path, dict(schema="v76_shared_stop_request.v1",
            protocol_id=protocol["id"], reason=reason, requested_epoch=now,
            grace_deadline_epoch=now + STOP_GRACE_SECONDS,
            automatic_restart_allowed=False))
    except (FileExistsError, ValueError):
        # Controller and supervisor may observe the same STOP concurrently.
        # The first immutable marker owns the shared grace; never reset it.
        if not path.exists():
            raise
        record = binding.checked(path)
        require(record["protocol_id"] == protocol["id"], "foreign concurrent stop marker")
        return record


def _status(path, body):
    binding.write_status(path, dict(body, id=binding.digest(body)))


def _environment(root):
    return dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONUNBUFFERED="1",
        PYTHONPATH=os.pathsep.join((str(Path(root) / "implementation"),
            binding.install_scientific_paths()["frozen_source_root"])))


def same_live_identity(runtime, pid, birth):
    require(type(pid) is int and pid > 0 and isinstance(birth, str) and birth.isdigit(),
            "complete positive PID/birth identity required before signalling")
    if runtime.birth(pid) != birth:
        return False
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return False
    return state not in ("Z", "X", "x")



def supervise(root=ROOT):
    root = Path(root).resolve()
    require(root == binding.ROOT.resolve(), "foreign supervisor root")
    registration = importlib.import_module("finqa_v76_registration")
    runtime = importlib.import_module("finqa_v76_resources").controller_runtime()
    protocol = registration.checked_protocol(root)
    directory = root / "supervisor"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "owner.lock").open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "launch/record.json").exists() and not stop_requested(root)
            and not (root / "closeout/record.json").exists(), "supervisor is single-use")
        binding.publish(directory / "launch/record.json", dict(protocol_id=protocol["id"],
            pid=os.getpid(), birth=runtime.birth(os.getpid()), started_epoch=time.time()))
        requested, previous = [], {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        for sig in previous: signal.signal(sig, lambda number, frame: requested.append(number))
        attempt = directory / "attempts/attempt0001"
        attempt.mkdir(parents=True, exist_ok=False)
        command = [str(binding.PYTHON), "-u", str(root / "implementation/finqa_v76_entry.py"), "--mode", "run"]
        process, birth, sent = None, None, []
        final_status = "STOPPED_CONTROLLER_FAILURE_NO_RETRY"
        try:
            with (attempt / "controller.log").open("xb") as log:
                process = subprocess.Popen(command, cwd=binding.REPO, env=_environment(root),
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            birth = runtime.birth(process.pid)
            require(isinstance(birth, str) and birth.isdigit() or process.poll() is not None,
                "live controller birth identity unavailable")
            binding.publish(attempt / "launch/record.json", dict(protocol_id=protocol["id"],
                pid=process.pid, birth=birth, command=command, controller_attempt=1))
            while process.poll() is None:
                if requested or stop_requested(root):
                    marker = _stop_marker(root, protocol, dict(kind="EXPLICIT", signals=requested))
                    if not sent and same_live_identity(runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGTERM); sent.append(signal.SIGTERM)
                    if time.time() >= marker["grace_deadline_epoch"] and signal.SIGKILL not in sent and same_live_identity(runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGKILL); sent.append(signal.SIGKILL)
                binding.write_status(directory / "queue/status.json", dict(protocol_id=protocol["id"],
                    status="STOPPING" if sent else "RUNNING", pid=process.pid, birth=birth,
                    controller_attempt=1, updated_epoch=time.time(), automatic_controller_restart=False))
                time.sleep(POLL_SECONDS)
            code = process.wait()
            binding.publish(attempt / "actual_exit/record.json", dict(protocol_id=protocol["id"],
                pid=process.pid, birth=birth, returncode=code, actual_waitpid_observed=True,
                signals_sent=sent, observed_epoch=time.time()))
            closeout = root / "closeout/record.json"
            if closeout.exists():
                value = binding.checked(closeout)
                require(value["protocol_id"] == protocol["id"], "foreign scientific closeout")
                # The entry intentionally returns2 for a completed failure/STOP
                # closeout. Preserve that scientific meaning; a nonzero exit can
                # only invalidate a claimed COMPLETE, never rewrite old failure.
                final_status = ("STOPPED_CONTROLLER_NONZERO_NO_RETRY"
                    if value["status"] == "COMPLETE" and code != 0 else value["status"])
            if not closeout.exists() or code != 0:
                orphan = stop_orphaned_workers(root, protocol, runtime)
                if not orphan["all_identities_observed_exited"]:
                    final_status = "STOPPED_CONTROLLER_FAILURE_UNCONFIRMED_CHILD_EXIT"
            return binding.publish(directory / "closeout/record.json", dict(protocol_id=protocol["id"],
                status=final_status, controller_attempts=1, automatic_restart_stopped=True,
                actual_controller_exit=binding.entry(attempt / "actual_exit/record.json"), finished_epoch=time.time()))
        finally:
            if process is not None and process.poll() is None:
                marker = _stop_marker(root, protocol, dict(kind="FAILURE", reason="supervisor interrupted"))
                if birth is not None and same_live_identity(runtime, process.pid, birth): os.kill(process.pid, signal.SIGTERM)
                while process.poll() is None and time.time() < marker["grace_deadline_epoch"]: time.sleep(1)
                if process.poll() is None and birth is not None and same_live_identity(runtime, process.pid, birth): os.kill(process.pid, signal.SIGKILL)
                process.wait()
                if not (directory / "orphan_stop/record.json").exists(): stop_orphaned_workers(root, protocol, runtime)
            for sig, handler in previous.items(): signal.signal(sig, handler)


def activate(root=ROOT):
    root = Path(root).resolve()
    require(root == binding.ROOT.resolve(), "foreign activation root")
    registration = importlib.import_module("finqa_v76_registration")
    protocol = registration.checked_protocol(root)
    runtime = importlib.import_module("finqa_v76_resources").controller_runtime()
    registration.checked_prepared(root)
    checked_imports=binding.checked(root/"frozen_worker_import_verification/record.json")
    cold=binding.checked(root/"cold_controller_verification/record.json")
    require(checked_imports["status"]==cold["status"]=="PASS"
        and checked_imports["protocol_id"]==cold["protocol_id"]==protocol["id"]
        and checked_imports["CUDA_initialized"] is False and cold["workers_dispatched"]==0,
        "actual frozen CPU imports and zero-dispatch controller gates precede activation")
    directory = root / "activation"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "owner.lock").open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "intent/record.json").exists() and not (root / "supervisor/launch/record.json").exists()
            and not stop_requested(root) and not (root / "closeout/record.json").exists(), "V76 activation already consumed or stopped")
        binding.publish(directory / "intent/record.json", dict(protocol_id=protocol["id"],
            created_epoch=time.time(), only_one_supervisor=True, automatic_controller_restart=False))
        command = [str(binding.PYTHON), "-u", str(root / "implementation/finqa_v76_entry.py"), "--mode", "supervise"]
        with (directory / "supervisor.log").open("xb") as log:
            process = subprocess.Popen(command, cwd=binding.REPO, env=_environment(root),
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        birth = runtime.birth(process.pid)
        require(isinstance(birth, str) and birth.isdigit() or process.poll() is not None, "supervisor birth unavailable")
        return binding.publish(directory / "record.json", dict(protocol_id=protocol["id"],
            pid=process.pid, birth=birth, command=command, started_epoch=time.time(),
            status="ACTIVATED", automatic_controller_restart=False))
