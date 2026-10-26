"""One fixed hybrid continuation worker, observed exits, and a single final CPU analysis.

Only confirmed resource failures at actual return boundaries may retry. A hard
failure stops the whole pool. The supervisor never restarts a failed controller.
"""
from __future__ import annotations

import fcntl
import importlib
import os
from pathlib import Path
import signal
import subprocess
import time
from types import SimpleNamespace

import finqa_v74_binding as b

base = b.source_v72("queue_base")
ROOT, GIB = b.ROOT, 1024 ** 3
POLL_SECONDS, STOP_GRACE_SECONDS = 5, 600
BACKOFF_SECONDS, NO_PROGRESS_LIMIT = 300, 3
require = b.require


def cpu_resource_policy():
    return dict(schema="v74_final_CPU_analysis_resource_policy.v1",
        GPU_initialization_allowed=False, GPU_workers_required_exited=True,
        max_cpu_children=1, startup_required_available_bytes=160 * GIB,
        rss_historical_peak_limit_bytes=64 * GIB,
        effective_host_available_reserve_bytes=96 * GIB,
        sample_interval_seconds=1, actual_exit_zero_required=True,
        explicit_stop_no_auto_restart=True, automatic_retry=False,
        native_scores_after_192_terminal_conditions=192, new_model_calls=0)


def stop_requested(root=ROOT):
    root = Path(root)
    return (root / "STOP").exists() or (root / "control/stop_requested/record.json").exists()


def _stop_marker(root, protocol, reason):
    path = Path(root) / "control/stop_requested/record.json"
    if path.exists():
        record = b.checked(path)
        require(record["protocol_id"] == protocol["id"], "foreign stop marker")
        return record
    now = time.time()
    try:
        return b.publish(path, dict(schema="v74_shared_stop_request.v1",
            protocol_id=protocol["id"], reason=reason, requested_epoch=now,
            grace_deadline_epoch=now + STOP_GRACE_SECONDS,
            automatic_restart_allowed=False))
    except (FileExistsError, ValueError):
        # Controller and supervisor may observe the same STOP concurrently.
        # The first immutable marker owns the shared grace; never reset it.
        if not path.exists():
            raise
        record = b.checked(path)
        require(record["protocol_id"] == protocol["id"], "foreign concurrent stop marker")
        return record


def _status(path, body):
    b.write_status(path, dict(body, id=b.digest(body)))


def _environment(root):
    return dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONUNBUFFERED="1",
        PYTHONPATH=os.pathsep.join((str(Path(root) / "implementation"),
            b.install_scientific_paths()["frozen_source_root"])))


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


def retry_decision(failure, audit, *, previous_units, no_progress_failures, returncode):
    require(type(audit["progress_units"]) is int and audit["progress_units"] >= 0
        and type(audit["unknown_calls"]) is int and audit["unknown_calls"] >= 0
        and type(audit["resume_allowed"]) is bool and isinstance(audit["completed_digest"], str),
        "structured actual-return audit is required")
    if audit["progress_units"] < previous_units:
        return dict(status="HARD_BLOCKED", reason="durable progress regressed")
    if audit["unknown_calls"] or not audit["resume_allowed"]:
        return dict(status="HARD_BLOCKED", reason="unresolved actual model call")
    if not (returncode > 0 and failure.get("confirmed_resource_failure") is True
            and failure.get("recoverable_at_actual_return_boundary") is True):
        return dict(status="HARD_BLOCKED", reason="no confirmed safe resource failure")
    progress = audit["progress_units"] > previous_units
    failures = 0 if progress else no_progress_failures + 1
    if failures >= NO_PROGRESS_LIMIT:
        return dict(status="HARD_BLOCKED", reason="three resource failures without durable progress",
            no_progress_failures=failures, progress_units=audit["progress_units"])
    return dict(status="BACKOFF", no_progress_failures=failures,
        progress_units=audit["progress_units"], completed_digest=audit["completed_digest"],
        backoff_seconds=BACKOFF_SECONDS, reason="confirmed resource failure at actual return boundary")


class Controller(base.Controller):
    """Reuse only frozen GPU admission, RAM reservation and PID-safe signalling."""
    def __init__(self, root=ROOT, *, runtime=None, registration=None):
        self.root = Path(root).resolve()
        require(self.root == b.ROOT.resolve(), "foreign V74 root")
        self.registration = registration or importlib.import_module("finqa_v74_registration")
        self.protocol = self.registration.checked_protocol(root)
        self.registration.checked_implementation(root)
        self.runtime = runtime or importlib.import_module("finqa_v74_resources").controller_runtime()
        require(self.protocol["max_gpu_workers"] == 1 and self.protocol["max_workers_per_gpu"] == 1
            and set(self.protocol["gpu_uuids"]) == {str(gpu) for gpu in range(8)}
            and Path(self.protocol["gpu_lease_root"]).resolve() == base.GPU_LEASE_ROOT.resolve(),
            "fixed eight GPU identities, original leases and one/one worker limits required")
        self.priority = self.protocol["gpu_priority"]
        require(len(self.priority) == 8 and set(self.priority) == set(range(8)), "GPU priority changed")
        self.jobs = self.protocol["jobs"]
        require(set(self.jobs) == {"P.continuation"},
            "exactly the single registered continuation worker are allowed")
        require(all(job["job_id"] == key and job["kind"] == job["stage"] == job["memory_phase"] == "generate"
            for key, job in self.jobs.items()), "foreign probe resource stage")
        require(not any((self.root / path).exists() for path in (
            "closeout/record.json", "controllers/attempt0001/launch/record.json", "journal/state.json")),
            "controller is single-use; existing journals must not be restarted")
        self.active, self.accepted, self.attempt_history = {}, {}, []
        self.job_states = {key: dict(status="PENDING", attempts=0, progress_units=0,
            completed_digest=b.digest([]), no_progress_failures=0, next_eligible_epoch=0.0)
            for key in self.jobs}
        self.explicit_stop, self.stopping = False, False
        self.cpu_analysis, self.resource_wait_seconds, self.wait_started = None, 0.0, None

    def job_directory(self, job):
        require(job["job_id"] in self.jobs, "foreign probe job directory")
        return self.root / "jobs" / job["job_id"]

    def _audit(self, job):
        source_id = b.digest(self.protocol["model_bindings"][job["model"]])
        return importlib.import_module("finqa_v74_worker").audit(job, self.protocol["id"], source_id)

    def journal(self):
        _status(self.root / "journal/state.json", dict(schema="v74_actual_process_journal.v1",
            protocol_id=self.protocol["id"], updated_epoch=time.time(),
            active_jobs=[dict(job_id=key, pid=child.process.pid, birth=child.birth,
                gpu_index=child.gpu, attempt=child.attempt, attempt_root=str(child.attempt_dir),
                lifecycle=child.lifecycle) for key, child in self.active.items()],
            job_states=self.job_states, attempt_history=self.attempt_history,
            accepted={key: b.entry(self.job_directory(self.jobs[key]) / "accepted/record.json")
                for key in self.accepted}, cpu_analysis=self.cpu_analysis,
            resource_wait_seconds=self.resource_wait_seconds,
            automatic_controller_restart_allowed=False))

    def status(self, status):
        b.write_status(self.root / "queue/status.json", dict(schema="v74_hybrid_continuation_queue.v1",
            protocol_id=self.protocol["id"], status=status, updated_epoch=time.time(),
            active_workers=[dict(job_id=key, pid=child.process.pid, birth=child.birth,
                gpu_index=child.gpu, attempt=child.attempt, lifecycle=child.lifecycle)
                for key, child in self.active.items()], job_states=self.job_states,
            accepted_jobs=list(self.accepted), total_registered_jobs=1, max_gpu_workers=1,
            resource_wait_seconds=self.resource_wait_seconds, cpu_analysis=self.cpu_analysis))

    def ready(self):
        return [self.jobs[key] for key, state in self.job_states.items()
            if state["status"] in ("PENDING", "BACKOFF")
            and state["next_eligible_epoch"] <= time.time()]

    def launch(self, job, acquired):
        row, lease, admission = acquired
        key, state = job["job_id"], self.job_states[job["job_id"]]
        try:
            before = self._audit(job)
            require(before["resume_allowed"] and before["unknown_calls"] == 0,
                "UNKNOWN blocks a new model attempt")
            require(before["progress_units"] >= state["progress_units"], "durable progress regressed")
            attempt = state["attempts"] + 1
            directory = self.job_directory(job) / "attempts" / f"attempt{attempt:04d}"
            require(not directory.exists(), "attempt directories are never reused")
            b.publish(directory / "dispatch_intent/record.json", dict(
                schema="v74_gpu_dispatch_intent.v1", protocol_id=self.protocol["id"], job=job,
                attempt=attempt, gpu_index=row["index"], gpu_uuid=row["uuid"],
                admission=admission, durable_before=before, created_epoch=time.time()))
            state.update(status="DISPATCHING", attempts=attempt, progress_units=before["progress_units"],
                completed_digest=before["completed_digest"])
            self.attempt_history.append(dict(job_id=key, attempt=attempt, directory=str(directory)))
            self.journal()
            command = ["/usr/bin/taskset", "--cpu-list", self.protocol["cpu_affinity"][str(row["index"])],
                str(b.PYTHON), "-u", str(self.root / "implementation/finqa_v74_entry.py"),
                "--mode", "worker", "--job", key, "--gpu", str(row["index"]),
                "--attempt-root", str(directory)]
            environment = self.runtime.worker_environment(row)
            environment.update(CUDA_VISIBLE_DEVICES=row["uuid"], V54_GPU_LEASE_FD=str(lease.fileno()),
                V54_JOB_ID=key, V74_ATTEMPT_ID=f"attempt{attempt:04d}", V74_ATTEMPT_DIR=str(directory),
                V56_ATTEMPT_ID=f"attempt{attempt:04d}", V56_ATTEMPT_DIR=str(directory),
                PYTHONPATH=_environment(self.root)["PYTHONPATH"])
            with (directory / "worker.log").open("xb") as log:
                process = subprocess.Popen(command, cwd=b.REPO, env=environment, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(lease.fileno(),))
        except BaseException:
            lease.close()
            state.update(status="HARD_BLOCKED", reason="dispatch or original-return audit failed")
            raise
        child = SimpleNamespace(job=job, process=process, lease=lease, gpu=row["index"], uuid=row["uuid"],
            birth=self.runtime.birth(process.pid), pidfd=None, directory=self.job_directory(job),
            attempt=attempt, attempt_dir=directory, durable_before=before, lifecycle="RUNNING",
            started_epoch=time.time())
        self.active[key] = child
        if hasattr(os, "pidfd_open"):
            try:
                child.pidfd = os.pidfd_open(process.pid)
            except ProcessLookupError:
                pass
        require(isinstance(child.birth, str) and child.birth.isdigit() or process.poll() is not None,
            "live worker birth identity unavailable")
        b.publish(directory / "launch/record.json", dict(schema="v74_gpu_worker_launch.v1",
            protocol_id=self.protocol["id"], job=job, attempt=attempt, pid=process.pid, birth=child.birth,
            gpu_index=child.gpu, gpu_uuid=child.uuid, command=command, admission=admission,
            inherited_gpu_lease=True, started_epoch=child.started_epoch))
        state.update(status="RUNNING", pid=process.pid, birth=child.birth, gpu_index=child.gpu)
        self.journal()

    def _validate_coordinate(self, child, result):
        require(result["status"] == "COMPLETE" and result["protocol_id"] == self.protocol["id"]
            and result["job"] == child.job and result["job_id"] == child.job["job_id"]
            and result["pid"] == child.process.pid and result["gpu_index"] == child.gpu
            and result["model_released"] is True
            and result["terminal_conditions"] == len(child.job["condition_ids"]) == 192
            and 0 <= result["new_model_calls"] <= self.protocol["scientific_contract"]["maximum_new_model_calls"]
            and all(result[k] == 0 for k in ("optimizer_updates", "new_first_responses", "native_scores", "external_API_calls")),
            "actual worker result differs from fixed inference-only shard")
        completed = b.checked(child.attempt_dir / "completed/record.json")
        require(completed["protocol_id"] == self.protocol["id"]
            and completed["result"] == b.entry(child.directory / "result/record.json"),
            "result is not sealed by this actual worker attempt")
        audit = self._audit(child.job)
        require(audit["resume_allowed"] and audit["unknown_calls"] == 0
            and audit["terminal_conditions"] == len(child.job["condition_ids"]),
            "complete shard lacks registered actual-return boundaries")

    def _accept(self, child, result):
        key = child.job["job_id"]
        accepted = b.publish(child.directory / "accepted/record.json", dict(
            schema="v74_actual_shard_exit_accepted.v1", protocol_id=self.protocol["id"],
            job_id=key, attempt=child.attempt, result=b.entry(child.directory / "result/record.json"),
            result_id=result["id"], actual_exit=b.entry(child.attempt_dir / "actual_exit/record.json"),
            actual_exit_zero=True, resources_passed=True))
        self.accepted[key] = accepted
        self.job_states[key].update(status="COMPLETE", accepted_attempt=child.attempt)

    def reap(self):
        for key, child in list(self.active.items()):
            code = child.process.poll()
            if code is None:
                child.lifecycle = "DRAINING" if (child.directory / "result/record.json").exists() else "RUNNING"
                self.job_states[key]["status"] = child.lifecycle
                continue  # The lease and worker slot remain occupied until real exit.
            code = child.process.wait()
            self.job_states[key]["status"] = "SETTLING_EXIT"
            b.publish(child.attempt_dir / "actual_exit/record.json", dict(
                schema="v74_actual_worker_exit.v1", protocol_id=self.protocol["id"], job_id=key,
                attempt=child.attempt, pid=child.process.pid, birth=child.birth, gpu_index=child.gpu,
                returncode=code, actual_waitpid_observed=True, observed_epoch=time.time()))
            try:
                if code == 0:
                    self._accept(child, self._validate_result(child))
                elif self.stopping:
                    self.job_states[key].update(status="STOPPED_NO_AUTO_RETRY", returncode=code)
                else:
                    failure = b.checked(child.attempt_dir / "failure/record.json")
                    require(failure["protocol_id"] == self.protocol["id"] and failure["job_id"] == key,
                        "foreign worker failure evidence")
                    after = self._audit(child.job)
                    require(failure["durable"] == after, "failure return-boundary evidence changed")
                    decision = retry_decision(failure, after, previous_units=child.durable_before["progress_units"],
                        no_progress_failures=self.job_states[key]["no_progress_failures"], returncode=code)
                    b.publish(child.attempt_dir / "recovery_decision/record.json", dict(
                        schema="v74_actual_resource_retry_decision.v1", protocol_id=self.protocol["id"],
                        failure=b.entry(child.attempt_dir / "failure/record.json"),
                        actual_exit=b.entry(child.attempt_dir / "actual_exit/record.json"),
                        durable_after=after, decision=decision, new_sampling_budget=0))
                    self.job_states[key].update(decision)
                    if decision["status"] == "BACKOFF":
                        self.job_states[key]["next_eligible_epoch"] = time.time() + BACKOFF_SECONDS
            except Exception as error:
                self.job_states[key].update(status="HARD_BLOCKED", reason="actual exit/result/audit validation failed",
                    exception=type(error).__name__, error=str(error))
                b.publish(child.attempt_dir / "acceptance_failure/record.json", dict(
                    protocol_id=self.protocol["id"], job_id=key, actual_returncode=code,
                    exception=type(error).__name__, error=str(error), automatic_retry=False))
            finally:
                child.lease.close()
                if child.pidfd is not None:
                    os.close(child.pidfd)
                del self.active[key]
        self.journal()

    def _terminal(self, status, **fields):
        require(not self.active, "cannot report a stopped/completed pool while workers remain active")
        self.journal()
        result = b.publish(self.root / "closeout/record.json", dict(
            schema="v74_same_context_probe_closeout.v1", protocol_id=self.protocol["id"], status=status,
            active_workers=0, accepted_jobs=list(self.accepted), job_states=self.job_states,
            actual_attempts=self.attempt_history, resource_wait_seconds=self.resource_wait_seconds,
            automatic_followup_started=False, automatic_controller_restart_allowed=False,
            finished_epoch=time.time(), **fields))
        self.status(status)
        return result

    def stop_pool(self, reason):
        self.stopping = True
        marker = _stop_marker(self.root, self.protocol, reason)
        for child in self.active.values():
            self._signal(child, signal.SIGTERM)
        while self.active and time.time() < marker["grace_deadline_epoch"]:
            self.reap()
            self.status("STOPPING_NO_AUTO_RESTART")
            if self.active:
                time.sleep(min(POLL_SECONDS, max(0, marker["grace_deadline_epoch"] - time.time())))
        for child in self.active.values():
            self._signal(child, signal.SIGKILL)
        while self.active:
            self.reap()
            if self.active:
                time.sleep(0.2)
        status = ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME" if marker["reason"].get("kind") == "EXPLICIT"
            else "STOPPED_FAILURE_NO_RETRY")
        return self._terminal(status, stop_reason=marker["reason"], subsequent_stop_context=reason)

    def _finish_cpu(self):
        policy = cpu_resource_policy()
        require(self.protocol["final_analysis_resource_policy"] == policy, "CPU resource policy changed")
        directory = self.root / "final_analysis/attempt0001"
        require(not directory.exists(), "CPU analysis is one actual attempt; never relaunch")
        while self.runtime.host_memory()["available_bytes"] < policy["startup_required_available_bytes"]:
            require(not self.explicit_stop and not stop_requested(self.root), "stop before CPU analysis")
            self.status("WAITING_FOR_FINAL_CPU_RESOURCES")
            time.sleep(POLL_SECONDS)
        b.publish(directory / "dispatch_intent/record.json", dict(protocol_id=self.protocol["id"],
            resource_policy=policy, no_GPU_workers_active=True, only_one_CPU_attempt=True))
        self.cpu_analysis = dict(status="DISPATCHING", directory=str(directory))
        self.journal()
        command = [str(b.PYTHON), "-u", str(self.root / "implementation/finqa_v74_entry.py"),
            "--mode", "analyze", "--attempt-root", str(directory)]
        process, birth, signals_sent, violation = None, None, [], None
        try:
            with (directory / "analysis.log").open("xb") as log:
                process = subprocess.Popen(command, cwd=b.REPO, env=_environment(self.root),
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            birth = self.runtime.birth(process.pid)
            require(isinstance(birth, str) and birth.isdigit() or process.poll() is not None,
                "live CPU analysis birth identity missing")
            b.publish(directory / "launch/record.json", dict(protocol_id=self.protocol["id"],
                kind="final_CPU_analysis", pid=process.pid, birth=birth, command=command))
            self.cpu_analysis.update(status="RUNNING", pid=process.pid, birth=birth)
            self.journal()
            while process.poll() is None:
                memory, host = self.runtime.process_memory(process.pid), self.runtime.host_memory()
                if memory is None and process.poll() is not None:
                    break
                require(isinstance(memory, dict), "live CPU resource observation unavailable")
                if memory["peak_rss_bytes"] > policy["rss_historical_peak_limit_bytes"] or host["available_bytes"] < policy["effective_host_available_reserve_bytes"]:
                    violation = dict(memory=memory, host=host, observed_epoch=time.time())
                if self.explicit_stop or stop_requested(self.root) or violation:
                    marker = _stop_marker(self.root, self.protocol, dict(kind="EXPLICIT" if self.explicit_stop else "FAILURE", cpu_resource_violation=violation))
                    if not signals_sent and same_live_identity(self.runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGTERM); signals_sent.append(signal.SIGTERM)
                    if time.time() >= marker["grace_deadline_epoch"] and signal.SIGKILL not in signals_sent and same_live_identity(self.runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGKILL); signals_sent.append(signal.SIGKILL)
                self.status("FINAL_CPU_ANALYSIS" if not signals_sent else "STOPPING_FINAL_CPU_ANALYSIS")
                time.sleep(1)
        finally:
            if process is not None:
                if process.poll() is None:
                    marker = _stop_marker(self.root, self.protocol, dict(kind="FAILURE", reason="CPU controller interrupted"))
                    if same_live_identity(self.runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGTERM); signals_sent.append(signal.SIGTERM)
                    while process.poll() is None and time.time() < marker["grace_deadline_epoch"]:
                        time.sleep(1)
                    if process.poll() is None and same_live_identity(self.runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGKILL); signals_sent.append(signal.SIGKILL)
                code = process.wait()
                b.publish(directory / "actual_exit/record.json", dict(protocol_id=self.protocol["id"],
                    pid=process.pid, birth=birth, returncode=code, actual_waitpid_observed=True,
                    signals_sent=signals_sent, parent_resource_violation=violation))
                self.cpu_analysis.update(status="EXITED", returncode=code)
                self.journal()
        require(code == 0 and not signals_sent and violation is None and not self.explicit_stop and not stop_requested(self.root),
            "CPU analysis requires actual exit zero and passing resource/stop gates")
        result = b.checked(directory / "result/record.json")
        resources = b.read_ref(result["resources"])
        require(result["status"] == resources["status"] == "COMPLETE"
            and result["protocol_id"] == resources["protocol_id"] == self.protocol["id"]
            and result["pid"] == resources["pid"] == process.pid and resources["birth"] == birth
            and resources["CUDA_initialized"] is False and resources["all_gates_passed"] is True
            and resources["policy"] == policy, "CPU completion/resource binding changed")
        summary = b.read_ref(result["analysis"])
        require(summary["status"] in ("COMPLETE", "COMPLETE_WITH_UNKNOWN"), "CPU summary incomplete")
        b.publish(self.root / "final_analysis/accepted/record.json", dict(protocol_id=self.protocol["id"],
            result=b.entry(directory / "result/record.json"), actual_exit=b.entry(directory / "actual_exit/record.json"),
            resources=result["resources"], analysis=result["analysis"]))
        return result["analysis"], summary

    def finish(self):
        require(set(self.accepted) == set(self.jobs) and not self.active and not stop_requested(self.root),
            "the actual accepted worker exit must precede CPU analysis")
        b.publish(self.root / "all_jobs_exit_barrier/record.json", dict(protocol_id=self.protocol["id"],
            active_workers=[], accepted_jobs={key: b.entry(self.job_directory(job) / "accepted/record.json")
                for key, job in self.jobs.items()}, actual_exits={key: self.accepted[key]["actual_exit"] for key in self.jobs}))
        reference, summary = self._finish_cpu()
        return self._terminal("COMPLETE", analysis=reference, analysis_status=summary["status"],
            terminal_conditions=192, native_scores=192, optimizer_updates=0,
            new_first_responses=0, new_probability_sequences=0, external_API_calls=0)


    def run(self):
        with (self.root / "owner.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(not stop_requested(self.root), "explicit stop forbids controller launch")
            launch = self.root / "controllers/attempt0001/launch/record.json"
            b.publish(launch, dict(protocol_id=self.protocol["id"], pid=os.getpid(),
                birth=self.runtime.birth(os.getpid()), started_epoch=time.time()))
            requested, previous = [], {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            def request(signum, frame):
                requested.append(signum)
                self.explicit_stop = True
            for sig in previous: signal.signal(sig, request)
            try:
                self.journal()
                while True:
                    if requested or stop_requested(self.root):
                        return self.stop_pool(dict(kind="EXPLICIT", signals=requested))
                    self.reap()
                    if any(state["status"] == "HARD_BLOCKED" for state in self.job_states.values()):
                        return self.stop_pool(dict(kind="FAILURE", reason="one shard has a non-retryable failure"))
                    if len(self.accepted) == 1 and not self.active:
                        return self.finish()
                    dispatched = False
                    for job in self.ready():
                        if self.explicit_stop or stop_requested(self.root) or not len(self.active) < 1: break
                        acquired = self.acquire(job)
                        if acquired is not None:
                            self.launch(job, acquired)
                            dispatched = True
                    now = time.monotonic()
                    if not dispatched and self.ready() and len(self.active) < 1:
                        if self.wait_started is not None: self.resource_wait_seconds += now - self.wait_started
                        self.wait_started = now
                    else:
                        self.wait_started = None
                    self.journal()
                    self.status("RUNNING" if self.active else "WAITING_FOR_RESOURCES_OR_BACKOFF")
                    time.sleep(POLL_SECONDS)
            except BaseException as error:
                b.publish(self.root / "controllers/attempt0001/failure/record.json", dict(
                    protocol_id=self.protocol["id"], exception=type(error).__name__, error=str(error),
                    active_jobs=list(self.active), automatic_restart=False))
                return self.stop_pool(dict(kind="EXPLICIT" if self.explicit_stop else "FAILURE",
                    exception=type(error).__name__, error=str(error)))
            finally:
                for sig, handler in previous.items(): signal.signal(sig, handler)


def stop_orphans(root, protocol, runtime):
    """Stop only journal+launch+current-birth matches; never fabricate waitpid."""
    marker = _stop_marker(root, protocol, dict(kind="FAILURE", reason="controller ended before settled closeout"))
    path = Path(root) / "journal/state.json"
    rows, unbound = [], []
    if path.exists():
        journal = b.checked(path)
        require(journal["protocol_id"] == protocol["id"], "foreign orphan journal")
        for active in journal["active_jobs"]:
            directory = Path(active["attempt_root"]).resolve()
            require(directory.is_relative_to(Path(root).resolve()), "orphan attempt escaped root")
            launch_path = directory / "launch/record.json"
            if not launch_path.exists():
                unbound.append(dict(job_id=active["job_id"], reason="missing actual launch identity")); continue
            launch = b.checked(launch_path)
            require(launch["protocol_id"] == protocol["id"] and launch["job"]["job_id"] == active["job_id"]
                and (launch["pid"], launch["birth"]) == (active["pid"], active["birth"]), "orphan launch differs from journal")
            rows.append(dict(pid=launch["pid"], birth=launch["birth"], launch=b.entry(launch_path), signals_sent=[]))
        for key, state in journal["job_states"].items():
            if state["status"] == "DISPATCHING" and not any(r["job_id"] == key for r in journal["active_jobs"]):
                unbound.append(dict(job_id=key, reason="unsettled dispatch without recorded child identity"))
        cpu = journal.get("cpu_analysis")
        if cpu and cpu["status"] in ("DISPATCHING", "RUNNING"):
            directory = Path(cpu["directory"]).resolve()
            require(directory == Path(root).resolve() / "final_analysis/attempt0001", "CPU orphan escaped root")
            launch_path = directory / "launch/record.json"
            if launch_path.exists():
                launch = b.checked(launch_path)
                require(launch["protocol_id"] == protocol["id"] and launch["kind"] == "final_CPU_analysis", "foreign CPU orphan")
                rows.append(dict(pid=launch["pid"], birth=launch["birth"], launch=b.entry(launch_path), signals_sent=[]))
            else:
                unbound.append(dict(kind="CPU", reason="unsettled CPU dispatch"))
    for row in rows:
        if row["birth"] is None:
            unbound.append(dict(pid=row["pid"], reason="birth unavailable")); continue
        if same_live_identity(runtime, row["pid"], row["birth"]):
            try:
                os.kill(row["pid"], signal.SIGTERM); row["signals_sent"].append(signal.SIGTERM)
            except ProcessLookupError: pass
    live = lambda row: row["birth"] is not None and same_live_identity(runtime, row["pid"], row["birth"])
    while any(live(row) for row in rows) and time.time() < marker["grace_deadline_epoch"]:
        time.sleep(min(POLL_SECONDS, max(0, marker["grace_deadline_epoch"] - time.time())))
    for row in rows:
        if live(row):
            try:
                os.kill(row["pid"], signal.SIGKILL); row["signals_sent"].append(signal.SIGKILL)
            except ProcessLookupError: pass
    until = time.monotonic() + 30
    while any(live(row) for row in rows) and time.monotonic() < until:
        time.sleep(0.2)
    for row in rows:
        row.update(identity_observed_exited=not live(row), OS_exitcode=None,
            OS_exitcode_independently_observed=False)
    return b.publish(Path(root) / "supervisor/orphan_stop/record.json", dict(
        protocol_id=protocol["id"], workers=rows, unbound_dispatches=unbound,
        all_identities_observed_exited=not unbound and all(row["identity_observed_exited"] for row in rows),
        nonchild_exit_zero_not_fabricated=True, automatic_restart_allowed=False))


def supervise(root=ROOT):
    root = Path(root).resolve()
    require(root == b.ROOT.resolve(), "foreign supervisor root")
    registration = importlib.import_module("finqa_v74_registration")
    runtime = importlib.import_module("finqa_v74_resources").controller_runtime()
    protocol = registration.checked_protocol(root)
    directory = root / "supervisor"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "owner.lock").open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "launch/record.json").exists() and not stop_requested(root)
            and not (root / "closeout/record.json").exists(), "supervisor is single-use")
        b.publish(directory / "launch/record.json", dict(protocol_id=protocol["id"],
            pid=os.getpid(), birth=runtime.birth(os.getpid()), started_epoch=time.time()))
        requested, previous = [], {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        for sig in previous: signal.signal(sig, lambda number, frame: requested.append(number))
        attempt = directory / "attempts/attempt0001"
        attempt.mkdir(parents=True, exist_ok=False)
        command = [str(b.PYTHON), "-u", str(root / "implementation/finqa_v74_entry.py"), "--mode", "run"]
        process, birth, sent = None, None, []
        final_status = "STOPPED_CONTROLLER_FAILURE_NO_RETRY"
        try:
            with (attempt / "controller.log").open("xb") as log:
                process = subprocess.Popen(command, cwd=b.REPO, env=_environment(root),
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            birth = runtime.birth(process.pid)
            require(isinstance(birth, str) and birth.isdigit() or process.poll() is not None,
                "live controller birth identity unavailable")
            b.publish(attempt / "launch/record.json", dict(protocol_id=protocol["id"],
                pid=process.pid, birth=birth, command=command, controller_attempt=1))
            while process.poll() is None:
                if requested or stop_requested(root):
                    marker = _stop_marker(root, protocol, dict(kind="EXPLICIT", signals=requested))
                    if not sent and same_live_identity(runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGTERM); sent.append(signal.SIGTERM)
                    if time.time() >= marker["grace_deadline_epoch"] and signal.SIGKILL not in sent and same_live_identity(runtime, process.pid, birth):
                        os.kill(process.pid, signal.SIGKILL); sent.append(signal.SIGKILL)
                b.write_status(directory / "queue/status.json", dict(protocol_id=protocol["id"],
                    status="STOPPING" if sent else "RUNNING", pid=process.pid, birth=birth,
                    controller_attempt=1, updated_epoch=time.time(), automatic_controller_restart=False))
                time.sleep(POLL_SECONDS)
            code = process.wait()
            b.publish(attempt / "actual_exit/record.json", dict(protocol_id=protocol["id"],
                pid=process.pid, birth=birth, returncode=code, actual_waitpid_observed=True,
                signals_sent=sent, observed_epoch=time.time()))
            closeout = root / "closeout/record.json"
            if closeout.exists():
                value = b.checked(closeout)
                require(value["protocol_id"] == protocol["id"], "foreign scientific closeout")
                # The entry intentionally returns2 for a completed failure/STOP
                # closeout. Preserve that scientific meaning; a nonzero exit can
                # only invalidate a claimed COMPLETE, never rewrite old failure.
                final_status = ("STOPPED_CONTROLLER_NONZERO_NO_RETRY"
                    if value["status"] == "COMPLETE" and code != 0 else value["status"])
            if not closeout.exists() or code != 0:
                orphan = stop_orphans(root, protocol, runtime)
                if not orphan["all_identities_observed_exited"]:
                    final_status = "STOPPED_CONTROLLER_FAILURE_UNCONFIRMED_CHILD_EXIT"
            return b.publish(directory / "closeout/record.json", dict(protocol_id=protocol["id"],
                status=final_status, controller_attempts=1, automatic_restart_stopped=True,
                actual_controller_exit=b.entry(attempt / "actual_exit/record.json"), finished_epoch=time.time()))
        finally:
            if process is not None and process.poll() is None:
                marker = _stop_marker(root, protocol, dict(kind="FAILURE", reason="supervisor interrupted"))
                if birth is not None and same_live_identity(runtime, process.pid, birth): os.kill(process.pid, signal.SIGTERM)
                while process.poll() is None and time.time() < marker["grace_deadline_epoch"]: time.sleep(1)
                if process.poll() is None and birth is not None and same_live_identity(runtime, process.pid, birth): os.kill(process.pid, signal.SIGKILL)
                process.wait()
                if not (directory / "orphan_stop/record.json").exists(): stop_orphans(root, protocol, runtime)
            for sig, handler in previous.items(): signal.signal(sig, handler)


def activate(root=ROOT):
    root = Path(root).resolve()
    require(root == b.ROOT.resolve(), "foreign activation root")
    registration = importlib.import_module("finqa_v74_registration")
    protocol = registration.checked_protocol(root)
    runtime = importlib.import_module("finqa_v74_resources").controller_runtime()
    directory = root / "activation"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "owner.lock").open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "intent/record.json").exists() and not (root / "supervisor/launch/record.json").exists()
            and not stop_requested(root) and not (root / "closeout/record.json").exists(), "V74 activation already consumed or stopped")
        b.publish(directory / "intent/record.json", dict(protocol_id=protocol["id"],
            created_epoch=time.time(), only_one_supervisor=True, automatic_controller_restart=False))
        command = [str(b.PYTHON), "-u", str(root / "implementation/finqa_v74_entry.py"), "--mode", "supervise"]
        with (directory / "supervisor.log").open("xb") as log:
            process = subprocess.Popen(command, cwd=b.REPO, env=_environment(root),
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        birth = runtime.birth(process.pid)
        require(isinstance(birth, str) and birth.isdigit() or process.poll() is not None, "supervisor birth unavailable")
        return b.publish(directory / "record.json", dict(protocol_id=protocol["id"],
            pid=process.pid, birth=birth, command=command, started_epoch=time.time(),
            status="ACTIVATED", automatic_controller_restart=False))
