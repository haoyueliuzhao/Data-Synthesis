"""Per-job bounded durable recovery and a conservative controller supervisor.

Unreturned feedback, changed state/hash, numerical failures and unknown errors
never acquire a retry allowance. Healthy independent jobs continue after a job
is blocked. A controller restart requires no active or unsettled dispatches.
"""

from __future__ import annotations

import errno
import fcntl
import importlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import finqa_v63_binding as binding

binding.install_scientific_paths()

import finqa_v63_queue_base as base
import finqa_v63_evaluation as evaluation

ROOT = binding.ROOT
RETRY_BACKOFF_SECONDS = (30, 60, 120, 300)
NO_PROGRESS_LIMIT = 4
RESOURCE_COOLDOWN_SECONDS = 900
TEMPORARY_CONTROLLER_EXIT = 75
POLL_SECONDS = 5
TRANSIENT_ERRNOS = frozenset((errno.EAGAIN, errno.ENOMEM, errno.ENOSPC, errno.EDQUOT,
                            errno.EIO, errno.ESTALE, errno.ETIMEDOUT))
TERMINAL_STATES = frozenset(("COMPLETE", "HARD_BLOCKED", "DEPENDENCY_BLOCKED"))
RETRY_CLASSIFICATIONS = frozenset(("RETRY_SAFE_RESOURCE", "RETRY_SAFE_IO", "PRE_SCIENCE_RESOURCE_YIELD"))
require = evaluation.require


def auto_recovery_policy():
    return dict(schema="v63_bounded_per_job_automatic_recovery.v1",
        resource_job_backoff_seconds=list(RETRY_BACKOFF_SECONDS),
        no_durable_progress_failure_limit=NO_PROGRESS_LIMIT,
        progress_measure="strictly increasing registered durable scientific units, never changing audit IDs",
        no_progress_limit_action="long resource cooldown then automatic original-gate readmission; independent jobs continue",
        no_progress_resource_cooldown_seconds=RESOURCE_COOLDOWN_SECONDS,
        confirmed_resource_failure_max_attempts=None,
        resource_wait_or_resource_cooldown_requires_manual_unlock=False,
        pre_scientific_resource_yield_seconds=60, total_scientific_deadline_seconds=None,
        runtime_resumability_audit_required=True, actual_failure_evidence_required=True,
        temporary_readonly_audit_IO_wait_does_not_authorize_scientific_retry=True,
        retry_classifications=sorted(RETRY_CLASSIFICATIONS),
        transient_OS_errnos=sorted(TRANSIENT_ERRNOS),
        UNKNOWN_feedback_retry=False, numerical_or_hash_or_state_failure_retry=False,
        unknown_or_ambiguous_worker_signal_retry=False,
        resource_hard_gates_relaxed=False, same_stable_scientific_data_across_attempts=True,
        independent_attempt_launch_log_exit_failure_and_backoff=True,
        max_gpu_workers=base.MAX_WORKERS, per_GPU_workers=1, initialization_wait_and_draining_count=True,
        inherited_GPU_lease_retained_until_actual_exit=True,
        controller_supervisor=True,
        controller_restart="only empty settled journal, original identities exited, all leases available, durable audit passed",
        controller_restart_backoff_seconds=list(RETRY_BACKOFF_SECONDS),
        controller_unknown_crash_no_progress_restart_limit=NO_PROGRESS_LIMIT,
        controller_confirmed_resource_failure_max_attempts=None,
        live_or_unobserved_worker_exit_blocks_controller_restart=True,
        explicit_SIGTERM_SIGINT_or_stop_marker_is_terminal=True,
        explicit_orphan_stop_requires_matching_journal_launch_and_current_birth=True,
        explicit_stop_shared_grace_seconds=600, nonchild_exit_zero_never_fabricated=True,
        complete_six_new_branches_and_actual_exits_before_evaluation=True,
        all_24_generation_actual_exits_before_any_private_scoring=True,
        old_UNKNOWN_reexecution_allowances_inherited=False,
        new_feedback_conditions=6, new_feedback_batch=1,
        automatic_followup_authorized=False)


def worker_api():
    return importlib.import_module("finqa_v63_worker")


def stop_requested(root):
    return (Path(root) / "STOP").exists() or (Path(root) / "control/stop_requested/record.json").exists()


def controller_closeout_status(closeout, returncode):
    """A saved COMPLETE cannot conceal the controller's actual nonzero exit."""
    status = closeout["status"]
    return ("CONTROLLER_NONZERO_AFTER_CLOSEOUT"
            if status == "COMPLETE" and returncode != 0 else status)


def checked_audit(value):
    require(type(value.get("resume_allowed")) is bool and type(value.get("unknown_calls")) is int
            and value["unknown_calls"] >= 0 and type(value.get("progress_units")) is int
            and value["progress_units"] >= 0 and isinstance(value.get("durable_progress_digest"), str)
            and value["durable_progress_digest"] and isinstance(value.get("evidence"), list),
            "structured actual durable-resume audit required")
    for reference in value["evidence"]:
        evaluation.checked_file(reference)
    return value


def failure_decision(failure, audit, *, previous_units, no_progress_failures, attempt):
    audit = checked_audit(audit)
    classification = failure.get("classification")
    evidence = failure.get("evidence", [])
    if audit["progress_units"] < previous_units:
        return dict(status="HARD_BLOCKED", reason="durable scientific progress regressed")
    if audit["unknown_calls"] or not audit["resume_allowed"]:
        return dict(status="HARD_BLOCKED", reason="UNKNOWN feedback or failed durable-state binding")
    if classification not in RETRY_CLASSIFICATIONS or not evidence:
        return dict(status="HARD_BLOCKED", reason="no verified retry-safe resource/I/O failure",
                    failure_classification=classification)
    for reference in evidence:
        evaluation.checked_file(reference)
    if classification == "RETRY_SAFE_IO" and failure.get("actual_errno") not in TRANSIENT_ERRNOS:
        return dict(status="HARD_BLOCKED", reason="I/O retry lacks an admitted actual errno")
    progress = audit["progress_units"] > previous_units
    failures = 0 if progress else no_progress_failures + 1
    if failures >= NO_PROGRESS_LIMIT:
        return dict(status="RESOURCE_COOLDOWN", reason="confirmed resource failure without recent durable progress",
                    no_progress_failures=failures, progress_units=audit["progress_units"],
                    durable_progress_digest=audit["durable_progress_digest"],
                    backoff_seconds=RESOURCE_COOLDOWN_SECONDS, automatic_readmission=True)
    return dict(status="BACKOFF", reason=failure.get("reason", classification),
        backoff_seconds=RETRY_BACKOFF_SECONDS[min(max(0, attempt - 1), len(RETRY_BACKOFF_SECONDS) - 1)],
        no_progress_failures=failures, progress_units=audit["progress_units"],
        durable_progress_digest=audit["durable_progress_digest"], actual_progress=progress)


def launch_failure_record(error):
    allowed = isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS
    return dict(classification="RETRY_SAFE_IO" if allowed else "HARD_BLOCK",
                reason=str(error), error_type=type(error).__name__, actual_errno=getattr(error, "errno", None),
                actual_child_created=False, scientific_call_started=False)


def _initial_state():
    return dict(status="PENDING", attempts=0, no_progress_failures=0, next_eligible_epoch=0.0,
                progress_units=0, durable_progress_digest=None)


def _require_empty_settled_journal(journal):
    require(journal["active_jobs"] == [], "controller recovery cannot inherit active/unobserved children")
    require(not any(row["status"] in ("RUNNING", "DRAINING", "DISPATCHING", "SETTLING_EXIT")
                    for row in journal["job_states"].values()), "unsettled dispatch blocks controller recovery")


class Controller(base.Controller):
    def __init__(self, root=ROOT, *, controller_attempt=1, runtime=None, registration=None):
        require(Path(root).resolve() == ROOT, "V63 requires its independent balanced-feedback experiment root")
        registration = registration or importlib.import_module("finqa_v63_registration")
        super().__init__(root, runtime=runtime, registration=registration)
        require(self.protocol["auto_recovery_policy"] == auto_recovery_policy(), "automatic recovery contract changed")
        require(type(controller_attempt) is int and controller_attempt >= 1,
                "positive independent controller attempt required")
        require(not (self.root / "closeout/record.json").exists(),
                "a terminal V63 experiment must not be automatically reopened")
        self.controller_attempt = controller_attempt
        self.controller_directory = self.root / "controllers" / f"attempt{controller_attempt:04d}"
        self.job_states = {key: _initial_state() for key in self.jobs}
        self.attempt_history = []
        self.explicit_stop = False
        self._restore_journal()

    def _audit(self, job):
        return checked_audit(worker_api().audit_job_resume(self.root, job))

    def _restore_journal(self):
        path = self.root / "journal/state.json"
        if not path.exists():
            require(self.controller_attempt == 1, "missing original controller journal")
            return
        require(not stop_requested(self.root), "explicit stop forbids automatic controller restart")
        journal = evaluation.checked(path)
        require(journal["protocol_id"] == self.protocol["id"], "journal belongs to another protocol")
        _require_empty_settled_journal(journal)
        if journal["evaluation_registered"]:
            plan = evaluation.checked_plan(self.root)
            for key, job in plan["jobs"].items():
                self.jobs[key] = dict(job, kind="generate", dependencies=list(self.core), priority=6)
            self.evaluation_registered = True
        require(set(journal["job_states"]) == set(self.jobs), "journal scientific job roster changed")
        self.job_states = journal["job_states"]
        self.attempt_history = journal["attempt_history"]
        self.resource_wait_seconds = journal["resource_wait_seconds"]
        for key, reference in journal["accepted"].items():
            self.accepted[key] = evaluation.checked(evaluation.checked_file(reference))
        for key, job in self.jobs.items():
            if self.job_states[key]["status"] not in TERMINAL_STATES:
                state = self.job_states[key]
                try:
                    audit = self._audit(job)
                    require(audit["resume_allowed"] and audit["unknown_calls"] == 0,
                            "controller recovery found unsafe durable scientific state")
                    require(audit["progress_units"] >= state["progress_units"],
                            "controller recovery lost durable progress")
                except Exception as error:
                    if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                        if state["status"] != "AUDIT_IO_WAIT":
                            state.update(status="PRE_DISPATCH_AUDIT_WAIT")
                        state.update(actual_errno=error.errno, next_eligible_epoch=time.time() + 300)
                    else:
                        state.update(status="HARD_BLOCKED", reason="controller-restart durable audit failed", error=str(error))
        self._block_dependencies()

    def journal(self):
        state = dict(schema="v63_actual_job_attempt_journal.v1", protocol_id=self.protocol["id"],
            controller_attempt=self.controller_attempt, updated_epoch=time.time(),
            active_jobs=[dict(job_id=key, pid=child.process.pid, birth=child.birth,
                             gpu_index=child.gpu, attempt=child.attempt) for key, child in self.active.items()],
            job_states=self.job_states, attempt_history=self.attempt_history,
            accepted={key: evaluation.file_binding(self.job_directory(self.jobs[key]) / "accepted/record.json")
                      for key in self.accepted}, evaluation_registered=self.evaluation_registered,
            resource_wait_seconds=self.resource_wait_seconds)
        base._status(self.root / "journal/state.json", evaluation.bound(state))

    def status(self, status):
        base._status(self.root / "queue/status.json", dict(schema="v63_per_job_queue.v1",
            protocol_id=self.protocol["id"], status=status, controller_attempt=self.controller_attempt,
            updated_epoch=time.time(), active_workers=[dict(job_id=key, pid=child.process.pid,
                birth=child.birth, gpu_index=child.gpu, attempt=child.attempt, lifecycle=child.lifecycle)
                for key, child in self.active.items()], job_states=self.job_states,
            accepted_jobs=list(self.accepted), max_gpu_workers=base.MAX_WORKERS, total_registered_jobs=len(self.jobs),
            resource_wait_seconds=self.resource_wait_seconds, evaluation_registered=self.evaluation_registered))

    def ready(self):
        now = time.time()
        return sorted((self.jobs[key] for key, state in self.job_states.items()
            if state["status"] in ("PENDING", "BACKOFF", "RESOURCE_COOLDOWN", "PRE_DISPATCH_AUDIT_WAIT")
            and state["next_eligible_epoch"] <= now
            and set(self.jobs[key]["dependencies"]) <= set(self.accepted)),
            key=lambda job: (job["priority"], job["seed"], job["job_id"]))

    def _block_dependencies(self):
        changed = True
        while changed:
            changed = False
            for key, state in self.job_states.items():
                if state["status"] not in ("PENDING", "BACKOFF", "RESOURCE_COOLDOWN", "AUDIT_IO_WAIT", "PRE_DISPATCH_AUDIT_WAIT"):
                    continue
                blocked = [d for d in self.jobs[key]["dependencies"]
                           if self.job_states[d]["status"] in TERMINAL_STATES - {"COMPLETE"}]
                if blocked:
                    state.update(status="DEPENDENCY_BLOCKED", blocked_by=blocked)
                    changed = True

    def _record_decision(self, job, attempt_dir, failure, before):
        key, state = job["job_id"], self.job_states[job["job_id"]]
        audit = None
        if failure.get("classification") == "AUDIT_IO_WAIT" and failure.get("actual_errno") in TRANSIENT_ERRNOS:
            decision = dict(status="AUDIT_IO_WAIT", reason="temporary failure reading actual durable evidence",
                actual_errno=failure["actual_errno"], backoff_seconds=300,
                pending_audit_attempt=str(attempt_dir), pending_durable_before=before)
        else:
            try:
                audit = self._audit(job)
                decision = failure_decision(failure, audit, previous_units=before["progress_units"],
                    no_progress_failures=state["no_progress_failures"], attempt=state["attempts"])
            except Exception as error:
                decision = dict(status="HARD_BLOCKED", reason="durable resume audit failed",
                                error_type=type(error).__name__, error=str(error))
                if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                    decision.update(status="AUDIT_IO_WAIT", actual_errno=error.errno, backoff_seconds=300,
                        pending_audit_attempt=str(attempt_dir), pending_durable_before=before)
        index = len(list((attempt_dir / "recovery_decisions").glob("decision*/record.json"))) + 1
        evaluation.publish(attempt_dir / "recovery_decisions" / f"decision{index:04d}/record.json", dict(
            schema="v63_actual_attempt_recovery_decision.v1", protocol_id=self.protocol["id"],
            job_id=key, attempt=state["attempts"], failure=failure, durable_before=before,
            durable_after=audit, decision=decision, automatic_sampling_override=False))
        state.update(decision)
        if decision["status"] in ("BACKOFF", "RESOURCE_COOLDOWN", "AUDIT_IO_WAIT"):
            state["next_eligible_epoch"] = time.time() + decision["backoff_seconds"]
        self._block_dependencies()

    def refresh_deferred_audits(self):
        for key, state in self.job_states.items():
            if state["status"] != "AUDIT_IO_WAIT" or state["next_eligible_epoch"] > time.time():
                continue
            attempt_dir = Path(state["pending_audit_attempt"])
            try:
                if state.get("pending_acceptance"):
                    exit_record = evaluation.checked(attempt_dir / "actual_exit/record.json")
                    launch = evaluation.checked(attempt_dir / "launch/record.json")
                    require(exit_record["returncode"] == 0 and exit_record["actual_waitpid_observed"] is True
                            and (exit_record["pid"], exit_record["birth"]) == (launch["pid"], launch["birth"]),
                            "CPU acceptance retry requires the already observed actual exit zero")
                    child = SimpleNamespace(job=self.jobs[key], attempt_dir=attempt_dir,
                        directory=self.job_directory(self.jobs[key]), attempt=state["attempts"],
                        gpu=exit_record["gpu_index"], process=SimpleNamespace(pid=exit_record["pid"]))
                    self._accept_result(child, self._validate_result(child))
                    state.pop("pending_acceptance", None)
                    continue
                if (attempt_dir / "actual_exit/record.json").exists():
                    code = evaluation.checked(attempt_dir / "actual_exit/record.json")["returncode"]
                    failure = worker_api().classify_attempt(self.root, self.jobs[key], attempt_dir, code)
                else:
                    failure = evaluation.checked(attempt_dir / "launch_failure/record.json")
                    require(failure["actual_child_created"] is False,
                            "pre-child launch failure required when no actual exit exists")
                    failure["evidence"] = [evaluation.file_binding(attempt_dir / "launch_failure/record.json")]
            except Exception as error:
                if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                    state["next_eligible_epoch"] = time.time() + 300
                else:
                    state.update(status="HARD_BLOCKED", reason="retry evidence cannot be established", error=str(error))
                continue
            self._record_decision(self.jobs[key], attempt_dir, failure, state["pending_durable_before"])

    def _validate_result(self, child):
        reused = child.attempt_dir / "reused_result/record.json"
        if not reused.exists():
            return super()._validate_result(child)
        proof = evaluation.checked(reused)
        result = evaluation.checked(evaluation.checked_file(proof["source_result"]))
        resources = evaluation.checked(evaluation.checked_file(proof["source_resource_closeout"]))
        require(proof["protocol_id"] == self.protocol["id"] and proof["job_id"] == child.job["job_id"]
                and proof["scientific_calls"] == 0 and proof["verified_durable_result"] is True
                and Path(proof["source_result"]["path"]).resolve() == child.directory / "result/record.json"
                and result["status"] == "COMPLETE" and result["resources"] == resources["resources"]
                and resources["status"] == "COMPLETE" and resources["job_id"] == child.job["job_id"]
                and resources["protocol_id"] == self.protocol["id"]
                and resources["resources"]["all_gates_passed"] is True
                and resources["resources"]["single_process_lifetime_includes_loading"] is True,
                "completed-stage reuse requires exact original successful lifetime resource evidence")
        self._validate_coordinate(child, result)
        return result

    def launch(self, job, acquired):
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
                schema="v63_cold_attempt_dispatch_intent.v1", protocol_id=self.protocol["id"],
                job=job, attempt=attempt, gpu_index=row["index"], gpu_uuid=row["uuid"],
                durable_before=before, admission=admission, created_epoch=time.time()))
            state.update(status="DISPATCHING", attempts=attempt, progress_units=before["progress_units"],
                         durable_progress_digest=before["durable_progress_digest"])
            self.attempt_history.append(dict(job_id=key, attempt=attempt, directory=str(directory)))
            self.journal()
        except BaseException:
            lease.close()
            raise
        entry = str(self.root / "implementation/finqa_v63_entry.py")
        if job["kind"] == "generate":
            arguments = [entry, "--mode", "generate", "--root", str(self.root),
                         "--job", key, "--gpu", str(row["index"]), "--attempt-root", str(directory)]
        else:
            arguments = [entry, "--mode", "worker", "--root", str(self.root),
                         "--seed", str(job["seed"]), "--stage", job["stage"],
                         "--gpu-index", str(row["index"]), "--attempt-root", str(directory)]
        command = ["/usr/bin/taskset", "--cpu-list", self.protocol["cpu_affinity"][str(row["index"])],
                   str(base.PYTHON), "-u", *arguments]
        environment = self.runtime.worker_environment(row)
        environment.update(CUDA_VISIBLE_DEVICES=row["uuid"], V54_GPU_LEASE_FD=str(lease.fileno()),
            V54_JOB_ID=key, V63_ATTEMPT_ID=f"attempt{attempt:04d}", V63_ATTEMPT_DIR=str(directory),
            V56_ATTEMPT_ID=f"attempt{attempt:04d}", V56_ATTEMPT_DIR=str(directory),
            PYTHONPATH=os.pathsep.join((str(self.root / "implementation"),
                binding.install_scientific_paths()["frozen_source_root"])))
        process = None
        try:
            with (directory / "worker.log").open("xb") as stream:
                process = subprocess.Popen(command, cwd=base.REPO, env=environment, stdout=stream,
                    stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(lease.fileno(),))
        except BaseException as error:
            lease.close()
            failure = launch_failure_record(error)
            evaluation.publish(directory / "launch_failure/record.json", dict(
                schema="v63_actual_pre_child_launch_failure.v1", protocol_id=self.protocol["id"],
                job_id=key, attempt=attempt, **failure))
            failure["evidence"] = [evaluation.file_binding(directory / "launch_failure/record.json")]
            self._record_decision(job, directory, failure, before)
            self.journal()
            return
        child = base.Child(job=job, gpu=row["index"], uuid=row["uuid"], process=process, lease=lease,
            birth=self.runtime.birth(process.pid), pidfd=None, directory=stable, started_epoch=time.time())
        child.attempt, child.attempt_dir, child.durable_before = attempt, directory, before
        self.active[key] = child
        require((isinstance(child.birth, str) and child.birth.isdigit()) or process.poll() is not None,
                "live worker birth identity must be established before acceptance")
        if hasattr(os, "pidfd_open"):
            try:
                child.pidfd = os.pidfd_open(process.pid)
            except ProcessLookupError:
                pass
        evaluation.publish(directory / "launch/record.json", dict(schema="v63_actual_attempt_launch.v1",
            protocol_id=self.protocol["id"], job=job, attempt=attempt, pid=process.pid, birth=child.birth,
            gpu_index=child.gpu, gpu_uuid=child.uuid, command=command, admission=admission,
            inherited_gpu_lease=True, started_epoch=child.started_epoch))
        state.update(status="RUNNING", pid=process.pid, birth=child.birth, gpu_index=child.gpu)
        base.can_dispatch(self.active)
        self.journal()

    def reap(self):
        for key, child in list(self.active.items()):
            child.lifecycle, code = base.process_state(child.process,
                (child.directory / "result/record.json").exists())
            self.job_states[key]["status"] = child.lifecycle if code is None else "SETTLING_EXIT"
            if code is None:
                continue
            evaluation.publish(child.attempt_dir / "actual_exit/record.json", dict(
                schema="v63_actual_attempt_worker_exit.v1", protocol_id=self.protocol["id"], job_id=key,
                attempt=child.attempt, pid=child.process.pid, birth=child.birth, gpu_index=child.gpu,
                returncode=code, actual_waitpid_observed=True, observed_epoch=time.time()))
            try:
                if code == 0:
                    result = self._validate_result(child)
                    self._accept_result(child, result)
                elif self.explicit_stop:
                    self.job_states[key].update(status="HARD_BLOCKED", reason="explicit controller/supervisor stop")
                else:
                    failure = worker_api().classify_attempt(self.root, child.job, child.attempt_dir, code)
                    self._record_decision(child.job, child.attempt_dir, failure, child.durable_before)
            except Exception as error:
                if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                    self.job_states[key].update(status="AUDIT_IO_WAIT", reason="temporary acceptance evidence IO failure",
                        actual_errno=error.errno, next_eligible_epoch=time.time() + 300,
                        pending_audit_attempt=str(child.attempt_dir), pending_durable_before=child.durable_before,
                        pending_acceptance=code == 0)
                    evaluation.publish(child.attempt_dir / "acceptance_io_wait/record.json", dict(
                        schema="v63_actual_acceptance_IO_wait.v1", protocol_id=self.protocol["id"],
                        job_id=key, actual_errno=error.errno, error=str(error), actual_exit_code=code,
                        no_scientific_retry_authorized=True, CPU_evidence_retry_only=True))
                else:
                    self.job_states[key].update(status="HARD_BLOCKED", reason="result/resource/resume validation failed",
                                                error_type=type(error).__name__, error=str(error))
                    evaluation.publish(child.attempt_dir / "acceptance_failure/record.json", dict(
                        schema="v63_attempt_acceptance_failure.v1", protocol_id=self.protocol["id"],
                        job_id=key, error_type=type(error).__name__, error=str(error), automatic_retry=False))
            finally:
                child.lease.close()
                if child.pidfd is not None:
                    os.close(child.pidfd)
                del self.active[key]
        self._block_dependencies()
        self.journal()

    def _accept_result(self, child, result):
        key = child.job["job_id"]
        accepted = evaluation.publish(child.directory / "accepted/record.json", dict(
            schema="v63_actual_attempt_exit_and_result_accepted.v1", protocol_id=self.protocol["id"],
            job_id=key, attempt=child.attempt, result=evaluation.file_binding(child.directory / "result/record.json"),
            result_id=result["id"], actual_exit=evaluation.file_binding(child.attempt_dir / "actual_exit/record.json"),
            actual_exit_zero=True, resources_passed=True))
        self.accepted[key] = accepted
        self.job_states[key].update(status="COMPLETE", accepted_attempt=child.attempt)

    def seal_training(self):
        require(set(self.core) <= set(self.accepted) and not self.active,
                "all 24 core jobs need accepted real exits before any generation")
        training = importlib.import_module("finqa_v63_training")
        branches = {}
        for seed in base.stats.SEEDS:
            for arm in base.stats.ARMS:
                training.checked_branch_result(self.root, seed, arm)
                branches[base.stats.coordinate(seed, arm)] = evaluation.file_binding(
                    self.root / f"branches/seed{seed}/{arm}/completed/record.json")
        evaluation.publish(self.root / "training_barrier/record.json", dict(
            schema="v63_actual_six_new_training_exit_barrier.v1", protocol_id=self.protocol["id"],
            all_six_new_branches_complete=True, all_six_894_snapshots_sealed=True,
            all_dispatched_training_workers_exited=True, active_children=[], branch_records=branches,
            worker_exits=[self.accepted[key]["actual_exit"] for key in self.core],
            accepted_core_jobs={key: evaluation.file_binding(self.job_directory(job) / "accepted/record.json")
                                for key, job in self.core.items()}))
        plan = evaluation.prepare_jobs(self.root)
        for key, job in plan["jobs"].items():
            self.jobs[key] = dict(job, kind="generate", dependencies=list(self.core), priority=6)
            self.job_states[key] = _initial_state()
        self.evaluation_registered = True
        self.journal()

    def finish(self):
        require(self.evaluation_registered and set(self.jobs) == set(self.accepted) and not self.active,
                "all 24 new generation jobs require actual successful exits before scoring")
        generation = {key: job for key, job in self.jobs.items() if job["kind"] == "generate"}
        require(len(self.core) == len(generation) == 24 and len(self.accepted) == 48,
                "registered core/evaluation dose changed")
        evaluation.publish(self.root / "evaluation_barrier/record.json", dict(
            schema="v63_actual_all_generation_exit_barrier.v1", protocol_id=self.protocol["id"],
            all_24_generation_jobs_complete=True, all_dispatched_evaluation_workers_exited=True,
            active_children=[], job_results={
                key: evaluation.file_binding(self.job_directory(job) / "result/record.json")
                for key, job in generation.items()},
            accepted_jobs={key: evaluation.file_binding(self.job_directory(job) / "accepted/record.json")
                           for key, job in generation.items()},
            actual_exits={key: self.accepted[key]["actual_exit"] for key in generation}))
        panels = {}
        for panel, *_ in evaluation.PANEL_SPECS:
            require(not self.explicit_stop and not stop_requested(self.root),
                    "explicit stop before next fixed-panel scoring")
            panels[panel] = evaluation.score(self.root, panel)
        require(not self.explicit_stop and not stop_requested(self.root), "explicit stop before postrun diagnostics")
        panel_complete = all(all(row["status"] == "COMPLETE" for row in summary["comparisons"].values())
                             for summary in panels.values())
        diagnostics = importlib.import_module("finqa_v63_diagnostics").postrun(self.root)
        require(isinstance(diagnostics, dict) and diagnostics.get("status") == "COMPLETE",
                "registered postrun diagnostics are incomplete; do not claim whole-experiment COMPLETE")
        require(not self.explicit_stop and not stop_requested(self.root), "explicit stop before final decision")
        complete = panel_complete and diagnostics["status"] == "COMPLETE"
        decision = base.stats.advancement(panels[evaluation.PRIMARY_PANEL], contracts_complete=complete)
        evaluation.publish(self.root / "promotion/record.json", dict(
            schema="v63_new_batch_minimum_research_value_decision.v1", protocol_id=self.protocol["id"],
            primary_summary=evaluation.file_binding(self.root / "evaluations/panels" /
                evaluation.PRIMARY_PANEL / "summary/record.json"), all_panels_complete=panel_complete,
            diagnostics_complete=True, **decision))
        require(self.prepared["actual_new_optimizer_budget"] == 1788,
                "six new fixed learning windows must total 1788 optimizer commits")
        result = evaluation.publish(self.root / "closeout/record.json", dict(
            schema="v63_balanced_feedback_repetition_closeout.v1", protocol_id=self.protocol["id"],
            status="COMPLETE" if complete else "EVALUATION_INCOMPLETE", active_workers=0,
            accepted_jobs=len(self.accepted), core_jobs=24, evaluation_jobs=24,
            logical_endpoint_conditions=15, old_endpoint_conditions_reused=9, new_training_branches=6,
            independent_parent_count=3, new_feedback_sessions=4200, new_evaluation_sessions=7458,
            new_logical_sessions=11658, new_API_calls=0, step745_new_generation=0,
            old_test1147_new_generation=0, old_unknown_reexecution_allowances_consumed_again=False,
            actual_new_optimizer_budget=1788, resource_wait_seconds=self.resource_wait_seconds,
            panel_summaries={panel: evaluation.file_binding(self.root / "evaluations/panels" /
                panel / "summary/record.json") for panel in panels},
            promotion=evaluation.file_binding(self.root / "promotion/record.json"),
            postrun_diagnostics=diagnostics,
            actual_attempts=self.attempt_history, job_states=self.job_states,
            rejected_attempts_not_reclassified_as_success=True,
            automatic_followup_started=False, finished_epoch=time.time()))
        self.status(result["status"])
        return result

    def _terminal(self, status):
        self.journal()
        self.status(status)
        return evaluation.publish(self.root / "closeout/record.json", dict(
            schema="v63_per_job_recovery_closeout.v1", protocol_id=self.protocol["id"], status=status,
            active_workers=0, job_states=self.job_states, accepted_jobs=list(self.accepted),
            attempt_count=len(self.attempt_history), resource_wait_seconds=self.resource_wait_seconds,
            automatic_restart_allowed=False, finished_epoch=time.time()))

    def _stop(self, reason):
        self.explicit_stop = True
        if not (self.root / "control/stop_requested/record.json").exists():
            evaluation.publish(self.root / "control/stop_requested/record.json", dict(
                schema="v63_terminal_explicit_stop.v1", protocol_id=self.protocol["id"],
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
        with (self.root / "owner.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(not stop_requested(self.root), "explicit stop forbids controller restart")
            evaluation.publish(self.controller_directory / "launch/record.json", dict(
                schema="v63_controller_attempt_launch.v1", protocol_id=self.protocol["id"],
                controller_attempt=self.controller_attempt, pid=os.getpid(), birth=self.runtime.birth(os.getpid()),
                started_epoch=time.time()))
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
                    if requested or stop_requested(self.root):
                        return self._stop(dict(signals=requested, marker=stop_requested(self.root)))
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
                        if requested or stop_requested(self.root) or not base.can_dispatch(self.active):
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
                if requested or stop_requested(self.root):
                    return self._stop(dict(signals=requested, marker=stop_requested(self.root)))
                transient = isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS and not self.active
                evaluation.publish(self.controller_directory / "failure/record.json", dict(
                    schema="v63_actual_controller_failure.v1", protocol_id=self.protocol["id"],
                    error_type=type(error).__name__, actual_errno=getattr(error, "errno", None), error=str(error),
                    transient_without_active_children=transient, active_children=list(self.active),
                    automatic_restart_requested=transient))
                if transient:
                    self.journal()
                    return dict(status="CONTROLLER_TRANSIENT_FAILURE", id=self.protocol["id"])
                if self.active:
                    # Unknown control-plane errors do not authorize unnoticed
                    # job replay; stop existing owned children and preserve data.
                    return self._stop(dict(kind="CONTROLLER_IMPLEMENTATION_OR_UNKNOWN", error=str(error)))
                return self._terminal("BLOCKED_OPERATOR_REQUIRED")
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)


def controller_restart_audit(root, protocol):
    root = Path(root)
    require(not stop_requested(root), "explicit stop is terminal")
    journal = evaluation.checked(root / "journal/state.json")
    require(journal["protocol_id"] == protocol["id"], "journal protocol changed")
    _require_empty_settled_journal(journal)
    for attempt in journal["attempt_history"]:
        directory = Path(attempt["directory"])
        require(directory.is_relative_to(root), "attempt path left the registered root")
        if (directory / "launch/record.json").exists():
            launch = evaluation.checked(directory / "launch/record.json")
            exit_record = evaluation.checked(directory / "actual_exit/record.json")
            require(exit_record["actual_waitpid_observed"] is True
                    and (exit_record["pid"], exit_record["birth"]) == (launch["pid"], launch["birth"]),
                    "unobserved worker exit forbids controller restart")
        else:
            failed = evaluation.checked(directory / "launch_failure/record.json")
            require(failed["actual_child_created"] is False, "unsettled dispatch may have created a worker")
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
    # Constructor rechecks all actual durable states immediately before work.
    require(journal["active_jobs"] == [], "all leases released while journal children remain")
    return journal


def _same_live_identity(runtime, pid, birth):
    require(type(pid) is int and pid > 0 and isinstance(birth, str) and birth.isdigit(),
            "a positive PID and complete numeric /proc birth identity are required")
    if runtime.birth(pid) != birth:
        return False
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return False
    return state not in ("Z", "X", "x")


def stop_orphaned_workers(root, protocol, runtime):
    """Explicit stop only; journal plus actual launch and birth jointly bind PIDs."""
    root = Path(root)
    marker = root / "control/stop_requested/record.json"
    if not marker.exists():
        evaluation.publish(marker, dict(schema="v63_terminal_explicit_stop.v1",
            protocol_id=protocol["id"], reason="explicit supervisor/controller stop",
            at_epoch=time.time(), automatic_restart_allowed=False))
    path = root / "journal/state.json"
    rows = []
    if path.exists():
        journal = evaluation.checked(path)
        require(journal["protocol_id"] == protocol["id"], "stop journal protocol changed")
        for active in journal["active_jobs"]:
            history = [row for row in journal["attempt_history"]
                       if (row["job_id"], row["attempt"]) == (active["job_id"], active["attempt"])]
            require(len(history) == 1, "orphan worker needs one actual dispatch history")
            directory = Path(history[0]["directory"]).resolve()
            require(directory.is_relative_to(root.resolve()), "orphan launch path escaped its experiment")
            launch = evaluation.checked(directory / "launch/record.json")
            require(launch["protocol_id"] == protocol["id"] and launch["job"]["job_id"] == active["job_id"]
                    and launch["attempt"] == active["attempt"]
                    and (launch["pid"], launch["birth"]) == (active["pid"], active["birth"]),
                    "orphan stop requires matching journal and actual launch identity")
            rows.append(dict(job_id=active["job_id"], pid=active["pid"], birth=active["birth"],
                launch=evaluation.file_binding(directory / "launch/record.json"), signals_sent=[]))
    deadline = time.monotonic() + base.STOP_GRACE_SECONDS
    for row in rows:
        if _same_live_identity(runtime, row["pid"], row["birth"]):
            try:
                os.kill(row["pid"], signal.SIGTERM)
                row["signals_sent"].append(signal.SIGTERM)
            except ProcessLookupError:
                pass
    while time.monotonic() < deadline and any(_same_live_identity(runtime, r["pid"], r["birth"]) for r in rows):
        time.sleep(max(0, min(POLL_SECONDS, deadline - time.monotonic())))
    for row in rows:
        if _same_live_identity(runtime, row["pid"], row["birth"]):
            try:
                os.kill(row["pid"], signal.SIGKILL)
                row["signals_sent"].append(signal.SIGKILL)
            except ProcessLookupError:
                pass
    final_deadline = time.monotonic() + 30
    while time.monotonic() < final_deadline and any(_same_live_identity(runtime, r["pid"], r["birth"]) for r in rows):
        time.sleep(0.2)
    for row in rows:
        row["identity_observed_exited"] = not _same_live_identity(runtime, row["pid"], row["birth"])
        row["OS_exitcode_independently_observed"] = False
        row["OS_exitcode"] = None
    return evaluation.publish(root / "supervisor/orphan_stop/record.json", dict(
        schema="v63_explicit_stop_orphan_identity_audit.v1", protocol_id=protocol["id"],
        workers=rows, all_identities_observed_exited=all(r["identity_observed_exited"] for r in rows),
        shared_cooperative_grace_seconds=base.STOP_GRACE_SECONDS,
        automatic_restart_allowed=False, nonchild_waitpid_or_exit_zero_not_fabricated=True))


def supervise(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered supervisor root")
    registration = importlib.import_module("finqa_v63_registration")
    runtime = importlib.import_module("finqa_v63_runtime").controller_runtime()
    protocol = registration.checked_protocol(root)
    registration.checked_implementation(root)
    registration.checked_prepared(root)
    require(protocol["auto_recovery_policy"] == auto_recovery_policy(), "supervisor policy changed")
    directory = root / "supervisor"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "owner.lock").open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "launch/record.json").exists() and not stop_requested(root),
                "supervisor is fresh once and explicit stop is terminal")
        evaluation.publish(directory / "launch/record.json", dict(schema="v63_supervisor_launch.v1",
            protocol_id=protocol["id"], pid=os.getpid(), birth=runtime.birth(os.getpid()), started_epoch=time.time()))
        requested = []
        previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        for sig in previous:
            signal.signal(sig, lambda signum, _frame: requested.append(signum))
        attempt, no_progress, last_accepted = 0, 0, 0
        final_status = "BLOCKED_OPERATOR_REQUIRED"
        try:
            while not requested and not stop_requested(root):
                attempt += 1
                command = [str(base.PYTHON), "-u", str(root / "implementation/finqa_v63_entry.py"),
                           "--mode", "run", "--root", str(root), "--controller-attempt", str(attempt)]
                env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root / "implementation"),
                    binding.install_scientific_paths()["frozen_source_root"])))
                attempt_dir = directory / "attempts" / f"attempt{attempt:04d}"
                attempt_dir.mkdir(parents=True, exist_ok=False)
                with (attempt_dir / "controller.log").open("xb") as log:
                    process = subprocess.Popen(command, cwd=base.REPO, env=env, stdout=log,
                                               stderr=subprocess.STDOUT, start_new_session=True)
                identity = runtime.birth(process.pid)
                require((isinstance(identity, str) and identity.isdigit()) or process.poll() is not None,
                        "live controller birth identity must be recorded")
                evaluation.publish(attempt_dir / "launch/record.json", dict(protocol_id=protocol["id"],
                    controller_attempt=attempt, pid=process.pid, birth=identity, command=command))
                signaled = False
                while process.poll() is None:
                    if (requested or stop_requested(root)) and not signaled:
                        if not (root / "control/stop_requested/record.json").exists():
                            evaluation.publish(root / "control/stop_requested/record.json", dict(
                                schema="v63_terminal_explicit_stop.v1", protocol_id=protocol["id"],
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
                    pid=process.pid, birth=identity, returncode=code, actual_waitpid_observed=True))
                if requested or stop_requested(root) or code in (-signal.SIGTERM, -signal.SIGINT):
                    orphan = stop_orphaned_workers(root, protocol, runtime)
                    final_status = ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME" if orphan["all_identities_observed_exited"]
                                    else "STOP_REQUESTED_WORKER_EXIT_UNCONFIRMED")
                    break
                if (root / "closeout/record.json").exists():
                    final_status = controller_closeout_status(
                        evaluation.checked(root / "closeout/record.json"), code)
                    break
                if code not in (TEMPORARY_CONTROLLER_EXIT, -signal.SIGKILL):
                    final_status = "BLOCKED_OPERATOR_REQUIRED"
                    break
                try:
                    journal = controller_restart_audit(root, protocol)
                except (ValueError, KeyError, OSError) as error:
                    evaluation.publish(attempt_dir / "restart_blocked/record.json", dict(
                        error_type=type(error).__name__, error=str(error), actual_exit=code,
                        missing_exitcode_was_not_fabricated=True, automatic_restart=False))
                    break
                progress = len(journal["accepted"])
                no_progress = 0 if progress > last_accepted else no_progress + 1
                last_accepted = progress
                if no_progress >= NO_PROGRESS_LIMIT and code != TEMPORARY_CONTROLLER_EXIT:
                    final_status = "CONTROLLER_RESTART_LIMIT_REACHED"
                    break
                delay = (RESOURCE_COOLDOWN_SECONDS if no_progress >= NO_PROGRESS_LIMIT else
                         RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)])
                evaluation.publish(attempt_dir / "restart_admission/record.json", dict(
                    backoff_seconds=delay, no_active_workers=True, no_unsettled_dispatches=True,
                    all_project_leases_observed_released=True, accepted_jobs=progress,
                    automatic_restart=True, old_exit_code=code))
                until = time.monotonic() + delay
                while time.monotonic() < until and not requested and not stop_requested(root):
                    time.sleep(max(0, min(POLL_SECONDS, until - time.monotonic())))
            if requested or stop_requested(root):
                orphan_path = root / "supervisor/orphan_stop/record.json"
                orphan = evaluation.checked(orphan_path) if orphan_path.exists() else stop_orphaned_workers(root, protocol, runtime)
                final_status = ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME" if orphan["all_identities_observed_exited"]
                                else "STOP_REQUESTED_WORKER_EXIT_UNCONFIRMED")
            return evaluation.publish(directory / "closeout/record.json", dict(
                schema="v63_supervisor_closeout.v1", protocol_id=protocol["id"], status=final_status,
                controller_attempts=attempt, automatic_restart_stopped=True, finished_epoch=time.time()))
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit("use the registered finqa_v63_entry.py so signal filtering precedes scientific imports")
