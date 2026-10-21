"""Memory-protected control plane over unchanged V63 scientific identities.

The new control root owns its journal, stop markers and closeout. Scientific
payloads, accepted results and monotonically numbered attempts remain in V63.
Only the explicitly registered maintenance interruption may be continued; no
other hard block is converted into an automatic retry.
"""
from __future__ import annotations

import copy
import fcntl
import importlib
import os
from pathlib import Path
import signal
import subprocess
import time

import finqa_v64_binding as binding

inherited = binding.source_module("finqa_v63_controller")
base, evaluation = inherited.base, inherited.evaluation
ROOT, SCIENTIFIC_ROOT = binding.ROOT, binding.SCIENTIFIC_ROOT
require = binding.require
POLL_SECONDS = inherited.POLL_SECONDS
TEMPORARY_CONTROLLER_EXIT = inherited.TEMPORARY_CONTROLLER_EXIT
TERMINAL_STATES = inherited.TERMINAL_STATES
TRANSIENT_ERRNOS = inherited.TRANSIENT_ERRNOS
ACTIVE_STATES = frozenset(("RUNNING", "DRAINING", "DISPATCHING", "SETTLING_EXIT"))


def stop_requested(root=ROOT):
    return inherited.stop_requested(root)


def execution_pythonpath(control_root=ROOT):
    science = binding.source_module("finqa_v63_binding").install_scientific_paths()
    return os.pathsep.join((str(Path(control_root) / "implementation"),
        str(SCIENTIFIC_ROOT / "implementation"), science["frozen_source_root"]))


def _control_binding(value, protocol, control_protocol):
    require(value["protocol_id"] == protocol["id"]
            and value["control_protocol_id"] == control_protocol["id"],
            "control evidence belongs to another scientific or protection protocol")


def checked_attempt_directory(row):
    directory = Path(row["directory"]).resolve()
    require(directory.is_relative_to(SCIENTIFIC_ROOT.resolve())
            and directory.parent.name == "attempts"
            and directory.name == f"attempt{row['attempt']:04d}",
            "attempt escaped its unchanged scientific directory")
    return directory


def audit_attempt_exit(row, protocol, runtime):
    """Never infer exit zero from a disappeared PID or a durable result."""
    directory = checked_attempt_directory(row)
    launch_path = directory / "launch/record.json"
    if not launch_path.exists():
        failure = evaluation.checked(directory / "launch_failure/record.json")
        require(failure["actual_child_created"] is False,
                "an unsettled dispatch may have created a worker")
        return
    launch = evaluation.checked(launch_path)
    require(launch["protocol_id"] == protocol["id"]
            and launch["job"]["job_id"] == row["job_id"]
            and launch["attempt"] == row["attempt"], "attempt launch identity changed")
    require(not inherited._same_live_identity(runtime, launch["pid"], launch["birth"]),
            "old worker identity is still alive")
    actual = evaluation.checked(directory / "actual_exit/record.json")
    require(actual["protocol_id"] == protocol["id"]
            and actual["job_id"] == row["job_id"] and actual["attempt"] == row["attempt"]
            and actual["actual_waitpid_observed"] is True
            and type(actual["returncode"]) is int
            and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"]),
            "worker needs its actual matching observed exit, not an inferred code")


def maintenance_states(journal, before, prepared, control_protocol, jobs, *, audit_reader=None):
    """Apply only the registered maintenance exception, preserving all history.

The old explicit-stop path also blocks downstream jobs. Restore those only if
they were healthy before this exact pause and their blocking dependency chain
is entirely explained by the maintenance jobs admitted here.
"""
    audit_reader = audit_reader or binding.read_ref
    require(journal["protocol_id"] == before["protocol_id"]
            == control_protocol["scientific_protocol_id"], "maintenance scientific protocol changed")
    require(journal["active_jobs"] == [], "maintenance inheritance requires no live workers")
    require(set(journal["job_states"]) == set(before["job_states"]) == set(jobs),
            "maintenance cannot change the scientific job roster")
    require(journal["attempt_history"] == before["attempt_history"],
            "a new dispatch occurred during the registered maintenance pause")
    require(journal["evaluation_registered"] == before["evaluation_registered"],
            "the evaluation phase changed during maintenance")
    require(float(journal["resource_wait_seconds"]) >= float(before["resource_wait_seconds"]),
            "maintenance cannot reset resource-wait statistics")
    for key, reference in before["accepted"].items():
        require(journal["accepted"].get(key) == reference,
                "an accepted scientific result changed during maintenance")
    states = copy.deepcopy(journal["job_states"])
    allowed = prepared["maintenance_resume_jobs"]
    authorization = control_protocol["maintenance_authorization"]["id"]
    paused = set()
    for key, proof in allowed.items():
        require(key in jobs and jobs[key]["kind"] == "replay" and key not in journal["accepted"],
                "maintenance cannot rerun an accepted or unregistered job")
        previous, state = before["job_states"][key], states[key]
        active = [row for row in before["active_jobs"] if row["job_id"] == key]
        require(len(active) == 1 and (active[0]["pid"], active[0]["birth"], active[0]["attempt"])
                == (proof["pid"], proof["birth"], proof["attempt"]),
                "maintenance must match the exact pre-stop active replay identity")
        require(previous["status"] in ("RUNNING", "DRAINING")
                and state["status"] == "HARD_BLOCKED"
                and state.get("reason") == "explicit controller/supervisor stop",
                "only this maintenance stop, never an unrelated hard block, may resume")
        require(proof["authorization_id"] == authorization
                and proof["attempt"] == previous["attempts"] == state["attempts"],
                "maintenance authorization or actual attempt does not match")
        launch, actual = audit_reader(proof["launch"]), audit_reader(proof["actual_exit"])
        acceptance, audit = audit_reader(proof["maintenance_acceptance"]), audit_reader(proof["resume_audit"])
        require(launch["job"]["job_id"] == actual["job_id"] == key
                and launch["attempt"] == actual["attempt"] == proof["attempt"]
                and launch["protocol_id"] == actual["protocol_id"] == journal["protocol_id"]
                and (launch["pid"], launch["birth"]) == (actual["pid"], actual["birth"])
                    == (proof["pid"], proof["birth"])
                and actual["actual_waitpid_observed"] is True
                and type(actual["returncode"]) is int and actual["returncode"] != 0,
                "maintenance resume needs the exact actual nonzero worker exit")
        require(acceptance["status"] == "PASS"
                and acceptance["authorization_id"] == authorization
                and acceptance["job_id"] == key and acceptance["attempt"] == proof["attempt"]
                and (acceptance["pid"], acceptance["birth"]) == (proof["pid"], proof["birth"])
                and acceptance["checkpoint_boundary"] == "complete_response"
                and acceptance["error_type"] in ("ReplayPaused", "ExplicitStop")
                and acceptance["worker_signaled"] is True,
                "complete-response maintenance acceptance is missing or differs")
        checked = inherited.checked_audit(audit)
        require(checked["resume_allowed"] and checked["unknown_calls"] == 0
                and checked["progress_units"] >= previous["progress_units"],
                "maintenance checkpoint is unsafe or regressed")
        state.update(status="PENDING", reason="explicitly authorized complete-response maintenance continuation",
            progress_units=checked["progress_units"], durable_progress_digest=checked["durable_progress_digest"],
            maintenance_source_status="HARD_BLOCKED", maintenance_authorization_id=authorization,
            maintenance_resume_audit=proof["resume_audit"])
        # Keep attempt ordinal, no-progress history and the original eligibility
        # clock. PENDING does not grant a new scientific dose.
        paused.add(key)
    restored = set(paused)
    changed = True
    while changed:
        changed = False
        for key, state in states.items():
            previous = before["job_states"][key]
            if state["status"] != "DEPENDENCY_BLOCKED" or previous["status"] in TERMINAL_STATES | ACTIVE_STATES:
                continue
            blockers = state.get("blocked_by", [])
            require(isinstance(blockers, list), "malformed inherited dependency block")
            if blockers and set(blockers) <= restored:
                require(set(blockers) <= set(jobs[key]["dependencies"]),
                        "maintenance block is not an actual registered dependency")
                require(state["attempts"] == previous["attempts"],
                        "dependent job attempt changed during maintenance")
                states[key] = copy.deepcopy(previous)
                states[key]["maintenance_dependency_restore"] = dict(
                    authorization_id=authorization, old_blockers=blockers,
                    original_status=previous["status"])
                restored.add(key)
                changed = True
    require(not any(value["status"] in ACTIVE_STATES for value in states.values()),
            "unregistered unsettled worker cannot be silently inherited")
    for key, previous in before["job_states"].items():
        if previous["status"] in ("HARD_BLOCKED", "DEPENDENCY_BLOCKED"):
            require(states[key] == journal["job_states"][key]
                    and states[key]["status"] == previous["status"],
                    "an unrelated existing scientific block cannot be unlocked")
    return states


class Controller(inherited.Controller):
    def __init__(self, root=ROOT, *, controller_attempt=1, runtime=None,
                 registration=None, scientific_registration=None):
        self.control_root = Path(root).resolve()
        require(self.control_root == ROOT.resolve(), "unregistered protection control root")
        self.control_registration = registration or importlib.import_module("finqa_v64_registration")
        self.control_protocol = self.control_registration.checked_protocol(self.control_root)
        self.control_registration.checked_implementation(self.control_root)
        self.control_prepared = self.control_registration.checked_prepared(self.control_root)
        require(Path(self.control_protocol["scientific_root"]).resolve() == SCIENTIFIC_ROOT.resolve(),
                "scientific root cannot move during memory protection")
        scientific_registration = scientific_registration or binding.source_module("finqa_v63_registration")
        runtime = runtime or importlib.import_module("finqa_v64_runtime").controller_runtime()
        # The parent constructor rejects the historical terminal closeout. Do
        # not bypass that old rule globally: initialize only the unchanged base
        # science and put this explicitly authorized control state in V64.
        base.Controller.__init__(self, SCIENTIFIC_ROOT, runtime=runtime, registration=scientific_registration)
        require(self.protocol["id"] == self.control_protocol["scientific_protocol_id"]
                == binding.BASE_PROTOCOL_ID, "memory protection changed scientific identity")
        require(self.protocol["auto_recovery_policy"] == inherited.auto_recovery_policy(),
                "old automatic recovery contract changed")
        require(type(controller_attempt) is int and controller_attempt >= 1,
                "positive independently numbered controller attempt required")
        require(not (self.control_root / "closeout/record.json").exists(),
                "a terminal protection run cannot be automatically reopened")
        self.controller_attempt = controller_attempt
        self.controller_directory = self.control_root / "controllers" / f"attempt{controller_attempt:04d}"
        self.job_states = {key: inherited._initial_state() for key in self.jobs}
        self.attempt_history, self.explicit_stop = [], False
        self._restore_journal()

    def _audit(self, job):
        worker = importlib.import_module("finqa_v64_worker")
        return inherited.checked_audit(worker.audit_job_resume(self.root, job))

    def _validate_result(self, child):
        result = super()._validate_result(child)
        if (child.attempt_dir / "reused_result/record.json").exists():
            # Original validation proves zero scientific calls and the exact
            # already-complete source resource closeout. Do not relabel old
            # successful resources as having used the new protection policy.
            return result
        resources = result["resources"]
        protection = resources.get("resource_protection", {})
        require(resources.get("control_protocol_id") == self.control_protocol["id"]
                and protection.get("policy") == self.control_protocol["memory_protection_policy"]
                and protection.get("future_capacity_or_exclusivity_guaranteed") is False,
                "new scientific work lacks its actual registered protection resource report")
        receipt = protection.get("receipt")
        if receipt is not None:
            warmed = binding.read_ref(receipt)
            require(warmed["control_protocol_id"] == self.control_protocol["id"]
                    and warmed["scientific_protocol_id"] == self.protocol["id"]
                    and warmed["job_id"] == child.job["job_id"]
                    and warmed["gpu_index"] == child.gpu
                    and warmed["actual_warm_allocation_bytes"] == protection["actual_warm_allocation_bytes"]
                    and warmed["status"] == protection["status"]
                    and warmed["live_warm_tensor_remaining"] is False
                    and warmed["original_peak_stats_not_reset"] is True,
                    "actual cache-warm receipt differs from this worker's resource lifetime")
        else:
            require(protection.get("warm_attempted") is False,
                    "an attempted successful cache warm needs its immutable actual receipt")
        return result

    def _restore_journal(self):
        require(not stop_requested(self.control_root), "explicit new stop forbids automatic restart")
        path = self.control_root / "journal/state.json"
        fresh = not path.exists()
        if fresh:
            require(self.controller_attempt == 1, "missing initial protection journal")
            journal = binding.read_ref(self.control_prepared["inherited_journal"])
            require(journal["protocol_id"] == self.protocol["id"], "inherited scientific protocol changed")
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
        if fresh:
            before = binding.read_ref(self.control_prepared["pre_stop_journal"])
            self.job_states = maintenance_states(journal, before, self.control_prepared,
                                                self.control_protocol, self.jobs)
        else:
            self.job_states = copy.deepcopy(journal["job_states"])
        self.attempt_history = copy.deepcopy(journal["attempt_history"])
        self.resource_wait_seconds = journal["resource_wait_seconds"]
        for row in self.attempt_history:
            audit_attempt_exit(row, self.protocol, self.runtime)
        for key, reference in journal["accepted"].items():
            self.accepted[key] = evaluation.checked(evaluation.checked_file(reference))
            require(self.job_states[key]["status"] == "COMPLETE", "accepted jobs cannot be redispatched")
        for key, state in self.job_states.items():
            maximum = max((row["attempt"] for row in self.attempt_history if row["job_id"] == key), default=0)
            require(state["attempts"] == maximum, "attempt ordinal differs from immutable history")
            require((state["status"] == "COMPLETE") == (key in self.accepted),
                    "complete job lacks its accepted actual exit")
            if state["status"] not in TERMINAL_STATES:
                try:
                    audit = self._audit(self.jobs[key])
                    require(audit["resume_allowed"] and audit["unknown_calls"] == 0
                            and audit["progress_units"] >= state["progress_units"],
                            "protection continuation found unsafe durable state")
                except Exception as error:
                    if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                        if state["status"] != "AUDIT_IO_WAIT":
                            state.update(status="PRE_DISPATCH_AUDIT_WAIT")
                        state.update(actual_errno=error.errno, next_eligible_epoch=time.time() + 300)
                    else:
                        state.update(status="HARD_BLOCKED", reason="controller-restart durable audit failed",
                                     error_type=type(error).__name__, error=str(error))
        self._block_dependencies()

    def journal(self):
        value = dict(schema="v64_actual_job_attempt_journal.v1", protocol_id=self.protocol["id"],
            control_protocol_id=self.control_protocol["id"], controller_attempt=self.controller_attempt,
            updated_epoch=time.time(), active_jobs=[dict(job_id=key, pid=child.process.pid,
                birth=child.birth, gpu_index=child.gpu, attempt=child.attempt) for key, child in self.active.items()],
            job_states=self.job_states, attempt_history=self.attempt_history,
            accepted={key: evaluation.file_binding(self.job_directory(self.jobs[key]) / "accepted/record.json")
                      for key in self.accepted}, evaluation_registered=self.evaluation_registered,
            resource_wait_seconds=self.resource_wait_seconds, old_stop_and_failure_records_unchanged=True)
        base._status(self.control_root / "journal/state.json", evaluation.bound(value))

    def status(self, status):
        base._status(self.control_root / "queue/status.json", dict(schema="v64_protected_per_job_queue.v1",
            protocol_id=self.protocol["id"], control_protocol_id=self.control_protocol["id"],
            status=status, controller_attempt=self.controller_attempt, updated_epoch=time.time(),
            active_workers=[dict(job_id=key, pid=child.process.pid, birth=child.birth,
                gpu_index=child.gpu, attempt=child.attempt, lifecycle=child.lifecycle)
                for key, child in self.active.items()], job_states=self.job_states,
            accepted_jobs=list(self.accepted), max_gpu_workers=base.MAX_WORKERS,
            total_registered_jobs=len(self.jobs), resource_wait_seconds=self.resource_wait_seconds,
            evaluation_registered=self.evaluation_registered))

    def launch(self, job, acquired):
        row, lease, admission = acquired
        key, state = job["job_id"], self.job_states[job["job_id"]]
        stable = self.job_directory(job)
        try:
            before = self._audit(job)
            require(before["resume_allowed"] and before["unknown_calls"] == 0,
                    "job is unsafe for a protected cold attempt")
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
        require(not directory.exists(), "immutable worker attempts cannot be reused")
        try:
            evaluation.publish(directory / "dispatch_intent/record.json", dict(
                schema="v64_protected_cold_attempt_dispatch.v1", protocol_id=self.protocol["id"],
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
        wrapper = str(self.control_root / "implementation/finqa_v64_entry.py")
        if job["kind"] == "generate":
            arguments = [wrapper, "--mode", "generate", "--root", str(self.control_root),
                         "--job", key, "--gpu", str(row["index"]), "--attempt-root", str(directory)]
        else:
            arguments = [wrapper, "--mode", "worker", "--root", str(self.control_root),
                         "--seed", str(job["seed"]), "--stage", job["stage"],
                         "--gpu-index", str(row["index"]), "--attempt-root", str(directory)]
        command = ["/usr/bin/taskset", "--cpu-list", self.protocol["cpu_affinity"][str(row["index"])],
                   str(base.PYTHON), "-u", *arguments]
        environment = self.runtime.worker_environment(row)
        environment.update(CUDA_VISIBLE_DEVICES=row["uuid"], V54_GPU_LEASE_FD=str(lease.fileno()),
            V54_JOB_ID=key, V63_ATTEMPT_ID=directory.name, V63_ATTEMPT_DIR=str(directory),
            V56_ATTEMPT_ID=directory.name, V56_ATTEMPT_DIR=str(directory),
            V64_CONTROL_ROOT=str(self.control_root), V64_CONTROL_PROTOCOL_ID=self.control_protocol["id"],
            PYTHONPATH=execution_pythonpath(self.control_root))
        try:
            with (directory / "worker.log").open("xb") as log:
                process = subprocess.Popen(command, cwd=base.REPO, env=environment, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(lease.fileno(),))
        except BaseException as error:
            lease.close()
            failure = inherited.launch_failure_record(error)
            evaluation.publish(directory / "launch_failure/record.json", dict(
                schema="v64_actual_pre_child_launch_failure.v1", protocol_id=self.protocol["id"],
                control_protocol_id=self.control_protocol["id"], job_id=key, attempt=attempt, **failure))
            failure["evidence"] = [evaluation.file_binding(directory / "launch_failure/record.json")]
            self._record_decision(job, directory, failure, before)
            self.journal()
            return
        child = base.Child(job=job, gpu=row["index"], uuid=row["uuid"], process=process, lease=lease,
            birth=self.runtime.birth(process.pid), pidfd=None, directory=stable, started_epoch=time.time())
        child.attempt, child.attempt_dir, child.durable_before = attempt, directory, before
        self.active[key] = child
        require((isinstance(child.birth, str) and child.birth.isdigit()) or process.poll() is not None,
                "a live worker needs its recorded birth identity")
        if hasattr(os, "pidfd_open"):
            try:
                child.pidfd = os.pidfd_open(process.pid)
            except ProcessLookupError:
                pass
        evaluation.publish(directory / "launch/record.json", dict(schema="v64_actual_protected_attempt_launch.v1",
            protocol_id=self.protocol["id"], control_protocol_id=self.control_protocol["id"],
            job=job, attempt=attempt, pid=process.pid, birth=child.birth, gpu_index=child.gpu,
            gpu_uuid=child.uuid, command=command, admission=admission, inherited_gpu_lease=True,
            started_epoch=child.started_epoch))
        state.update(status="RUNNING", pid=process.pid, birth=child.birth, gpu_index=child.gpu)
        base.can_dispatch(self.active)
        self.journal()

    def finish(self):
        require(self.evaluation_registered and set(self.jobs) == set(self.accepted) and not self.active,
                "all 24 evaluation jobs need successful actual exits before scoring")
        generation = {key: job for key, job in self.jobs.items() if job["kind"] == "generate"}
        require(len(self.core) == len(generation) == 24 and len(self.accepted) == 48,
                "the registered core/evaluation dose changed")
        evaluation.publish(self.root / "evaluation_barrier/record.json", dict(
            schema="v63_actual_all_generation_exit_barrier.v1", protocol_id=self.protocol["id"],
            all_24_generation_jobs_complete=True, all_dispatched_evaluation_workers_exited=True,
            active_children=[], job_results={key: evaluation.file_binding(
                self.job_directory(job) / "result/record.json") for key, job in generation.items()},
            accepted_jobs={key: evaluation.file_binding(self.job_directory(job) / "accepted/record.json")
                           for key, job in generation.items()},
            actual_exits={key: self.accepted[key]["actual_exit"] for key in generation}))
        panels = {}
        for panel, *_ in evaluation.PANEL_SPECS:
            require(not self.explicit_stop and not stop_requested(self.control_root),
                    "explicit stop before next fixed-panel scoring")
            panels[panel] = evaluation.score(self.root, panel)
        require(not self.explicit_stop and not stop_requested(self.control_root),
                "explicit stop before original postrun diagnostics")
        panel_complete = all(all(row["status"] == "COMPLETE" for row in summary["comparisons"].values())
                             for summary in panels.values())
        diagnostics = binding.source_module("finqa_v63_diagnostics").postrun(self.root)
        require(isinstance(diagnostics, dict) and diagnostics.get("status") == "COMPLETE",
                "registered postrun diagnostics are incomplete")
        require(not self.explicit_stop and not stop_requested(self.control_root),
                "explicit stop before final protected-run decision")
        complete = panel_complete and diagnostics["status"] == "COMPLETE"
        decision = base.stats.advancement(panels[evaluation.PRIMARY_PANEL], contracts_complete=complete)
        evaluation.publish(self.root / "promotion/record.json", dict(
            schema="v63_new_batch_minimum_research_value_decision.v1", protocol_id=self.protocol["id"],
            primary_summary=evaluation.file_binding(self.root / "evaluations/panels" /
                evaluation.PRIMARY_PANEL / "summary/record.json"), all_panels_complete=panel_complete,
            diagnostics_complete=True, **decision))
        require(self.prepared["actual_new_optimizer_budget"] == 1788,
                "six unchanged training branches must total 1788 optimizer commits")
        result = evaluation.publish(self.control_root / "closeout/record.json", dict(
            schema="v64_memory_protected_scientific_closeout.v1", protocol_id=self.protocol["id"],
            control_protocol_id=self.control_protocol["id"], status="COMPLETE" if complete else "EVALUATION_INCOMPLETE",
            active_workers=0, accepted_jobs=len(self.accepted), core_jobs=24, evaluation_jobs=24,
            logical_endpoint_conditions=15, old_endpoint_conditions_reused=9, new_training_branches=6,
            independent_parent_count=3, new_feedback_sessions=4200, new_evaluation_sessions=7458,
            new_logical_sessions=11658, new_API_calls=0, step745_new_generation=0,
            old_test1147_new_generation=0, old_unknown_reexecution_allowances_consumed_again=False,
            actual_new_optimizer_budget=1788, resource_wait_seconds=self.resource_wait_seconds,
            panel_summaries={panel: evaluation.file_binding(self.root / "evaluations/panels" /
                panel / "summary/record.json") for panel in panels},
            promotion=evaluation.file_binding(self.root / "promotion/record.json"), postrun_diagnostics=diagnostics,
            actual_attempts=self.attempt_history, job_states=self.job_states,
            rejected_attempts_not_reclassified_as_success=True, old_stop_and_failure_records_unchanged=True,
            automatic_followup_started=False, finished_epoch=time.time()))
        self.status(result["status"])
        return result

    def _terminal(self, status):
        self.journal()
        self.status(status)
        return evaluation.publish(self.control_root / "closeout/record.json", dict(
            schema="v64_protected_control_closeout.v1", protocol_id=self.protocol["id"],
            control_protocol_id=self.control_protocol["id"], status=status, active_workers=0,
            job_states=self.job_states, accepted_jobs=list(self.accepted), attempt_count=len(self.attempt_history),
            resource_wait_seconds=self.resource_wait_seconds, automatic_restart_allowed=False,
            old_stop_and_failure_records_unchanged=True, finished_epoch=time.time()))

    def _stop(self, reason):
        self.explicit_stop = True
        marker = self.control_root / "control/stop_requested/record.json"
        if not marker.exists():
            evaluation.publish(marker, dict(schema="v64_terminal_explicit_stop.v1",
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
        with (self.root / "owner.lock").open("a") as science_owner, (self.control_root / "owner.lock").open("a") as owner:
            fcntl.flock(science_owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(not stop_requested(self.control_root), "explicit new stop forbids controller restart")
            evaluation.publish(self.controller_directory / "launch/record.json", dict(
                schema="v64_controller_attempt_launch.v1", protocol_id=self.protocol["id"],
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
                    schema="v64_actual_controller_failure.v1", protocol_id=self.protocol["id"],
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


def controller_restart_audit(root, protocol, control_protocol, runtime):
    root = Path(root)
    require(not stop_requested(root), "explicit protection stop is terminal")
    journal = evaluation.checked(root / "journal/state.json")
    _control_binding(journal, protocol, control_protocol)
    inherited._require_empty_settled_journal(journal)
    for row in journal["attempt_history"]:
        audit_attempt_exit(row, protocol, runtime)
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


def stop_orphaned_workers(root, protocol, control_protocol, runtime):
    root = Path(root)
    marker = root / "control/stop_requested/record.json"
    if not marker.exists():
        evaluation.publish(marker, dict(schema="v64_terminal_explicit_stop.v1",
            protocol_id=protocol["id"], control_protocol_id=control_protocol["id"],
            reason="explicit supervisor/controller stop", at_epoch=time.time(), automatic_restart_allowed=False))
    rows = []
    path = root / "journal/state.json"
    if path.exists():
        journal = evaluation.checked(path)
        _control_binding(journal, protocol, control_protocol)
        for active in journal["active_jobs"]:
            history = [row for row in journal["attempt_history"]
                       if (row["job_id"], row["attempt"]) == (active["job_id"], active["attempt"])]
            require(len(history) == 1, "orphan requires exactly one actual dispatch")
            directory = checked_attempt_directory(history[0])
            launch = evaluation.checked(directory / "launch/record.json")
            _control_binding(launch, protocol, control_protocol)
            require(launch["job"]["job_id"] == active["job_id"] and launch["attempt"] == active["attempt"]
                    and (launch["pid"], launch["birth"]) == (active["pid"], active["birth"]),
                    "orphan stop requires matching new control journal and actual launch")
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
    until = time.monotonic() + 30
    while time.monotonic() < until and any(inherited._same_live_identity(runtime, r["pid"], r["birth"]) for r in rows):
        time.sleep(0.2)
    for row in rows:
        row.update(identity_observed_exited=not inherited._same_live_identity(runtime, row["pid"], row["birth"]),
                   OS_exitcode_independently_observed=False, OS_exitcode=None)
    return evaluation.publish(root / "supervisor/orphan_stop/record.json", dict(
        schema="v64_explicit_stop_orphan_identity_audit.v1", protocol_id=protocol["id"],
        control_protocol_id=control_protocol["id"], workers=rows,
        all_identities_observed_exited=all(row["identity_observed_exited"] for row in rows),
        shared_cooperative_grace_seconds=base.STOP_GRACE_SECONDS, automatic_restart_allowed=False,
        nonchild_waitpid_or_exit_zero_not_fabricated=True))


def supervise(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT.resolve(), "unregistered protection supervisor root")
    registration = importlib.import_module("finqa_v64_registration")
    runtime = importlib.import_module("finqa_v64_runtime").controller_runtime()
    control_protocol = registration.checked_protocol(root)
    registration.checked_implementation(root)
    registration.checked_prepared(root)
    protocol = binding.source_module("finqa_v63_registration").checked_protocol(SCIENTIFIC_ROOT)
    require(protocol["id"] == control_protocol["scientific_protocol_id"], "scientific protocol changed")
    directory = root / "supervisor"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "owner.lock").open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / "launch/record.json").exists() and not stop_requested(root),
                "supervisor is single-use and explicit stop is terminal")
        evaluation.publish(directory / "launch/record.json", dict(schema="v64_supervisor_launch.v1",
            protocol_id=protocol["id"], control_protocol_id=control_protocol["id"],
            pid=os.getpid(), birth=runtime.birth(os.getpid()), started_epoch=time.time()))
        requested = []
        previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        for sig in previous:
            signal.signal(sig, lambda signum, _frame: requested.append(signum))
        attempt, no_progress, last_accepted = 0, 0, 0
        final_status = "BLOCKED_OPERATOR_REQUIRED"
        try:
            while not requested and not stop_requested(root):
                attempt += 1
                command = [str(base.PYTHON), "-u", str(root / "implementation/finqa_v64_entry.py"),
                           "--mode", "run", "--root", str(root), "--controller-attempt", str(attempt)]
                env = dict(os.environ, PYTHONPATH=execution_pythonpath(root),
                    V64_CONTROL_ROOT=str(root), V64_CONTROL_PROTOCOL_ID=control_protocol["id"])
                attempt_dir = directory / "attempts" / f"attempt{attempt:04d}"
                attempt_dir.mkdir(parents=True, exist_ok=False)
                with (attempt_dir / "controller.log").open("xb") as log:
                    process = subprocess.Popen(command, cwd=base.REPO, env=env, stdout=log,
                                               stderr=subprocess.STDOUT, start_new_session=True)
                identity = runtime.birth(process.pid)
                require((isinstance(identity, str) and identity.isdigit()) or process.poll() is not None,
                        "live controller birth identity must be recorded")
                evaluation.publish(attempt_dir / "launch/record.json", dict(protocol_id=protocol["id"],
                    control_protocol_id=control_protocol["id"], controller_attempt=attempt,
                    pid=process.pid, birth=identity, command=command))
                signaled = False
                while process.poll() is None:
                    if (requested or stop_requested(root)) and not signaled:
                        if not (root / "control/stop_requested/record.json").exists():
                            evaluation.publish(root / "control/stop_requested/record.json", dict(
                                schema="v64_terminal_explicit_stop.v1", protocol_id=protocol["id"],
                                control_protocol_id=control_protocol["id"], signals=requested,
                                at_epoch=time.time(), automatic_restart_allowed=False))
                        observed = runtime.birth(process.pid)
                        if observed is not None:
                            require(observed == identity, "controller identity changed before stop")
                            os.kill(process.pid, signal.SIGTERM)
                            signaled = True
                    base._status(directory / "queue/status.json", dict(status="STOPPING" if signaled else "RUNNING",
                        protocol_id=protocol["id"], control_protocol_id=control_protocol["id"],
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
                    final_status = inherited.controller_closeout_status(evaluation.checked(root / "closeout/record.json"), code)
                    break
                if code not in (TEMPORARY_CONTROLLER_EXIT, -signal.SIGKILL):
                    final_status = "BLOCKED_OPERATOR_REQUIRED"
                    break
                try:
                    journal = controller_restart_audit(root, protocol, control_protocol, runtime)
                except (ValueError, KeyError, OSError) as error:
                    evaluation.publish(attempt_dir / "restart_blocked/record.json", dict(
                        error_type=type(error).__name__, error=str(error), actual_exit=code,
                        missing_exitcode_was_not_fabricated=True, automatic_restart=False))
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
            if requested or stop_requested(root):
                orphan_path = root / "supervisor/orphan_stop/record.json"
                orphan = evaluation.checked(orphan_path) if orphan_path.exists() else stop_orphaned_workers(
                    root, protocol, control_protocol, runtime)
                final_status = ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME" if orphan["all_identities_observed_exited"]
                                else "STOP_REQUESTED_WORKER_EXIT_UNCONFIRMED")
            return evaluation.publish(directory / "closeout/record.json", dict(
                schema="v64_supervisor_closeout.v1", protocol_id=protocol["id"],
                control_protocol_id=control_protocol["id"], status=final_status,
                controller_attempts=attempt, automatic_restart_stopped=True, finished_epoch=time.time()))
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit("use the frozen finqa_v64_entry.py: signal observation must precede scientific imports")
