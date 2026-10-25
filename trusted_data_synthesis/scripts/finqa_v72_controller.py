"""One fixed-pi low-LR window, untouched parent dev and two endpoint evaluations.

Per-job recovery and actual-process-exit settlement reuse the frozen V63
lifecycle in a private operational namespace. No historical scientific finish,
six-branch registration or single-point diagnostic exception is reachable.
"""
from __future__ import annotations

import importlib
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import ModuleType

import finqa_v72_binding as binding
import finqa_v72_queue_base as base

ROOT = binding.ROOT
require = binding.require


def _private_lifecycle():
    source = binding.source_module("finqa_v63_controller")
    raw = Path(source.__file__).read_text()
    substitutions = (
        ("import finqa_v63_binding as binding", "import finqa_v72_binding as binding"),
        ("import finqa_v63_queue_base as base", "import finqa_v72_queue_base as base"),
        ("import finqa_v63_evaluation as evaluation", "evaluation = base.records"),
        ('return importlib.import_module("finqa_v63_worker")',
         'return importlib.import_module("finqa_v72_worker")'),
        ('"--seed", str(job["seed"]), "--stage", job["stage"],',
         '"--seed", str(job["seed"]), "--stage", str(job["step"]) + "." + job["stage"],'),
        ('V56_ATTEMPT_ID=f"attempt{attempt:04d}", V56_ATTEMPT_DIR=str(directory),',
         'V56_ATTEMPT_ID=f"attempt{attempt:04d}", V56_ATTEMPT_DIR=str(directory), '
         'V72_ATTEMPT_ID=f"attempt{attempt:04d}", V72_ATTEMPT_DIR=str(directory),'),
    )
    for before, after in substitutions:
        require(raw.count(before) == 1, "frozen operational lifecycle structure changed: " + before)
        raw = raw.replace(before, after)
    raw = raw.replace("finqa_v63_registration", "finqa_v72_registration")
    raw = raw.replace("finqa_v63_runtime", "finqa_v72_resources")
    raw = raw.replace("finqa_v63_entry.py", "finqa_v72_entry.py")
    raw = raw.replace('schema="v63_', 'schema="v72_')
    module = ModuleType("_v72_frozen_durable_lifecycle")
    module.__file__, module.__package__ = str(Path(source.__file__).resolve()), ""
    sys.modules[module.__name__] = module
    exec(compile(raw, module.__file__ + "::V72_private_lifecycle", "exec"), module.__dict__)
    return module, source


inherited, original = _private_lifecycle()
TERMINAL_STATES, TRANSIENT_ERRNOS = inherited.TERMINAL_STATES, inherited.TRANSIENT_ERRNOS
failure_decision = inherited.failure_decision
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
        schema="v72_final_CPU_orphan_stop.v1", protocol_id=protocol["id"],
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
    policy.update(schema="v72_fixed_distribution_durable_recovery.v1",
        max_gpu_workers=6, per_GPU_workers=1, primary_EX_lease_only=True,
        new_feedback_conditions=0, new_feedback_sessions=0,
        applied_updates=0, optimizer_updates=298,
        terminal_probe_applied=False, terminal_probe_extra_training=False,
        evaluation_jobs=3, evaluation_sessions=1886, new_point_class_passes=0,
        exact_parent_Adam_RNG_and_fixed_distribution_required=True,
        learning_rate_intervention_after_exact_restore=[1e-4, 1e-5],
        static_supervision_audit_PASS_required_before_dispatch=True,
        original_outer_history_unchanged=[298],
        parent_dev_requires_original_V71_parent_actual_exit_zero=True,
        evaluation_requires_corresponding_training_actual_exit_zero=True,
        parent_dev_generation_may_overlap_registered_low_LR_training=True,
        intermediate_accuracy_never_selects_or_changes_path=True,
        all_registered_actual_exits_before_final_scoring=True,
        legacy_single_point_numeric_exceptions_inherited=False,
        automatic_followup_authorized=False)
    return policy


inherited.auto_recovery_policy = auto_recovery_policy


class Controller(inherited.Controller):
    def __init__(self, root=ROOT, *, controller_attempt=1, runtime=None, registration=None):
        self.root = Path(root).resolve()
        require(self.root == ROOT.resolve(), "V72 requires its independent fixed-distribution root")
        self.registration = registration or importlib.import_module("finqa_v72_registration")
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
                and not (self.root / "closeout/record.json").exists(), "terminal V72 cannot reopen")
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
                and set(journal["job_states"]) == set(self.jobs), "fixed four-job roster changed")
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
        value = dict(schema="v72_actual_job_attempt_journal.v1", protocol_id=self.protocol["id"],
            controller_attempt=self.controller_attempt, updated_epoch=time.time(),
            active_jobs=[dict(job_id=key, pid=child.process.pid, birth=child.birth,
                gpu_index=child.gpu, attempt=child.attempt) for key, child in self.active.items()],
            job_states=self.job_states, attempt_history=self.attempt_history,
            accepted={key: binding.entry(self.job_directory(self.jobs[key]) / "accepted/record.json")
                      for key in self.accepted}, evaluation_registered=True,
            resource_wait_seconds=self.resource_wait_seconds, cpu_analysis=self.cpu_analysis)
        base._status(self.root / "journal/state.json", base.bound(value))

    def _validate_coordinate(self, child, result):
        from finqa_v72_worker import validate_result
        validate_result(self.root, child.job, result)

    def seal_training(self):
        raise ValueError("V72 evaluation is preregistered by endpoint, not the V63 six-branch barrier")

    def _finish_cpu(self):
        from finqa_v72_analysis import resource_policy
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
                schema="v72_final_CPU_dispatch_intent.v1", protocol_id=self.protocol["id"],
                resource_policy=policy, only_one_CPU_attempt=True, no_GPU_workers_active=True))
            self.cpu_analysis = dict(status="DISPATCHING", directory=str(directory))
            self.journal()
            command = [str(base.PYTHON), "-u", str(self.root / "implementation/finqa_v72_entry.py"),
                       "--mode", "score", "--root", str(self.root), "--attempt-root", str(directory)]
            environment = dict(os.environ, CUDA_VISIBLE_DEVICES="",
                V72_CPU_ANALYSIS_ATTEMPT=str(directory),
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
                    schema="v72_final_CPU_actual_launch.v1", protocol_id=self.protocol["id"],
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
                    binding.publish(actual_path, dict(schema="v72_final_CPU_actual_exit.v1",
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
            schema="v72_final_CPU_result_actual_exit_accepted.v1", protocol_id=self.protocol["id"],
            result=binding.entry(directory / "result/record.json"), actual_exit=binding.entry(actual_path),
            resources=binding.entry(directory / "resources/closeout/record.json")))
        return result["analysis"]

    def finish(self):
        require(set(self.jobs) == set(self.accepted) and not self.active,
                "all four jobs need actual accepted exit zero before final analysis")
        require(len(self.core) == 1 and len(self.jobs) == 4, "registered fixed-distribution dose changed")
        require(not self.explicit_stop and not stop_requested(self.root), "explicit stop precedes analysis")
        binding.publish(self.root / "all_jobs_exit_barrier/record.json", dict(
            schema="v72_fixed_path_all_jobs_actual_exit_barrier.v1", protocol_id=self.protocol["id"],
            active_workers=[], scientific_jobs=1, evaluation_jobs=3,
            accepted_jobs={key: binding.entry(self.job_directory(job) / "accepted/record.json")
                           for key, job in self.jobs.items()},
            actual_exits={key: self.accepted[key]["actual_exit"] for key in self.jobs}))
        summary = self._finish_cpu()
        require(not self.explicit_stop and not stop_requested(self.root), "explicit stop before final closeout")
        require(summary.get("status") == "COMPLETE", "prespecified analysis is not complete")
        result = binding.publish(self.root / "closeout/record.json", dict(
            schema="v72_low_learning_rate_control_closeout.v1", status="COMPLETE", protocol_id=self.protocol["id"],
            active_workers=0, accepted_jobs=4, scientific_jobs=1, evaluation_jobs=3,
            new_training_paths=1, new_independent_training_seeds=0,
            new_feedback_sessions=0, optimizer_updates=298, task_exposures=1488,
            applied_Full_updates=0, terminal_candidate_probes=0,
            terminal_candidate_applied=False, final_training_step=1490,
            new_evaluation_sessions=1886, new_logical_sessions=1886,
            summary=summary, actual_attempts=self.attempt_history, job_states=self.job_states,
            resource_wait_seconds=self.resource_wait_seconds,
            historical_failures_or_exceptions_reclassified=False,
            automatic_followup_started=False, finished_epoch=time.time()))
        self.status("COMPLETE")
        return result


def supervise(root=ROOT):
    return inherited.supervise(root)
