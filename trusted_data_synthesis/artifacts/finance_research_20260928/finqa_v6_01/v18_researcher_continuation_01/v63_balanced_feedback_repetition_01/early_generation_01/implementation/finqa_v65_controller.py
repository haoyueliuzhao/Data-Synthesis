"""Generation-only continuation: five sealed endpoints, no scoring or core retry.

The exact frozen V63/V64 lifecycle implementations are adapted in private
modules. Only operational imports/names and the shared science-owner lock are
changed; the new Controller supplies an independent twenty-job generation DAG.
No inherited scientific finish or training barrier is reachable.
"""
from __future__ import annotations

import copy
import importlib
import math
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace

import finqa_v65_binding as binding

ROOT, SCIENTIFIC_ROOT = binding.ROOT, binding.SCIENTIFIC_ROOT
require = binding.require
SEALED_STATUS = "GENERATIONS_SEALED_AWAITING_GLOBAL_SCORING"
MAX_WORKERS = 5
OTHER_CONTROL_STARTUP_GIB = 64


def _private_lifecycle():
    """Explicit, source-bound operational adapters; never edit frozen files."""
    source = binding.source_module("finqa_v63_controller")
    raw = Path(source.__file__).read_text()
    before = 'return importlib.import_module("finqa_v63_worker")'
    require(raw.count(before) == 1, "frozen generation attempt-disposition adapter changed")
    raw = raw.replace(before, 'return importlib.import_module("finqa_v65_worker")')
    queue = ModuleType("_v65_private_generation_queue")
    queue.__file__, queue.__package__ = str(Path(source.__file__).resolve()), ""
    sys.modules[queue.__name__] = queue
    exec(compile(raw, queue.__file__ + "::V65_generation_attempt_api", "exec"), queue.__dict__)
    original = binding.predecessor_module("finqa_v64_controller")
    raw = Path(original.__file__).read_text()
    substitutions = (
        ('import finqa_v64_binding as binding', 'import finqa_v65_binding as binding'),
        ('inherited = binding.source_module("finqa_v63_controller")', 'inherited = __v65_queue'),
        ('(self.root / "owner.lock").open("a") as science_owner',
         '(SCIENTIFIC_ROOT / "owner.lock").open("a") as science_owner'),
        ('fcntl.flock(science_owner, fcntl.LOCK_EX | fcntl.LOCK_NB)',
         'fcntl.flock(science_owner, fcntl.LOCK_SH | fcntl.LOCK_NB)'),
        ('protocol = binding.source_module("finqa_v63_registration").checked_protocol(SCIENTIFIC_ROOT)',
         'protocol = control_protocol'),
        ('require(protocol["id"] == control_protocol["scientific_protocol_id"], "scientific protocol changed")',
         'require(binding.BASE_PROTOCOL_ID == control_protocol["scientific_protocol_id"], "scientific protocol changed")'),
        ('all_project_leases_observed_released=True',
         'own_workers_actual_exits_observed=True, peer_gpu_leases_not_required_to_be_released=True'),
    )
    for before, after in substitutions:
        require(raw.count(before) == 1, "frozen protection lifecycle adapter changed: " + before)
        raw = raw.replace(before, after)
    # These names denote only the explicitly frozen operational control layer.
    raw = raw.replace("finqa_v64_", "finqa_v65_").replace("V64_CONTROL_", "V65_CONTROL_")
    raw = raw.replace('schema="v64_', 'schema="v65_')
    raw = raw.replace('protocol_id=self.protocol["id"],',
                      'protocol_id=self.protocol["id"], scientific_protocol_id=binding.BASE_PROTOCOL_ID,')
    raw = raw.replace('protocol_id=protocol["id"],',
                      'protocol_id=protocol["id"], scientific_protocol_id=binding.BASE_PROTOCOL_ID,')
    protected = ModuleType("_v65_private_protected_generation_lifecycle")
    protected.__file__, protected.__package__ = str(Path(original.__file__).resolve()), ""
    protected.__dict__["__v65_queue"] = queue
    sys.modules[protected.__name__] = protected
    exec(compile(raw, protected.__file__ + "::V65_generation_control", "exec"), protected.__dict__)
    return queue, protected


inherited, lifecycle = _private_lifecycle()
original_base, evaluation = inherited.base, inherited.evaluation


def can_dispatch(active):
    require(len(active) <= MAX_WORKERS, "registered five-worker generation cap exceeded")
    devices = [child.gpu for child in active.values()]
    require(len(devices) == len(set(devices)), "one experiment worker per physical GPU required")
    return len(active) < MAX_WORKERS


# A private operational namespace avoids changing the original six-worker cap.
base = SimpleNamespace(**{key: value for key, value in vars(original_base).items() if not key.startswith("__")})
base.MAX_WORKERS, base.can_dispatch = MAX_WORKERS, can_dispatch
inherited.base = lifecycle.base = base
POLL_SECONDS = inherited.POLL_SECONDS
TERMINAL_STATES = inherited.TERMINAL_STATES
TRANSIENT_ERRNOS = inherited.TRANSIENT_ERRNOS
TEMPORARY_CONTROLLER_EXIT = inherited.TEMPORARY_CONTROLLER_EXIT
stop_requested = lifecycle.stop_requested
execution_pythonpath = lifecycle.execution_pythonpath


def generation_api():
    return importlib.import_module("finqa_v65_evaluation")


def checked_generation_jobs(plan):
    jobs = {key: dict(value, kind="generate", dependencies=[], priority=6)
            for key, value in plan["jobs"].items()}
    allowed = {(137, "C1"), (137, "C05"), (251, "C1"), (251, "C05"), (389, "C1")}
    require(len(jobs) == 20 and sum(job["denominator"] for job in jobs.values()) == 6215
            and {(job["seed"], job["arm"]) for job in jobs.values()} == allowed
            and all(key == job["job_id"] and job["stage"] == "generate"
                    and job["feedback_batch"] == 1 and job["step"] == 894
                    for key, job in jobs.items()),
            "only the twenty authorized generation jobs from five completed endpoints are allowed")
    return jobs


def checked_attempt_directory(row):
    directory = Path(row["directory"]).resolve()
    require(directory.parent.parent.parent == ROOT.resolve() / "evaluations/jobs"
            and directory.parent.name == "attempts"
            and directory.parent.parent.name == row["job_id"]
            and directory.name == f"attempt{row['attempt']:04d}",
            "generation attempt escaped its independent registered job directory")
    return directory


def audit_attempt_exit(row, protocol, runtime):
    directory = checked_attempt_directory(row)
    launch_path = directory / "launch/record.json"
    if not launch_path.exists():
        failed = evaluation.checked(directory / "launch_failure/record.json")
        require(failed["actual_child_created"] is False, "unsettled generation dispatch may have created a child")
        return
    launch = evaluation.checked(launch_path)
    require(launch["protocol_id"] == protocol["id"]
            and launch["job"]["job_id"] == row["job_id"] and launch["attempt"] == row["attempt"],
            "generation launch identity changed")
    require(not inherited._same_live_identity(runtime, launch["pid"], launch["birth"]),
            "previous generation worker remains alive")
    actual = evaluation.checked(directory / "actual_exit/record.json")
    require(actual["protocol_id"] == protocol["id"] and actual["job_id"] == row["job_id"]
            and actual["attempt"] == row["attempt"] and actual["actual_waitpid_observed"] is True
            and type(actual["returncode"]) is int
            and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"]),
            "generation continuation requires a matching actual observed exit")


class Controller(lifecycle.Controller):
    def __init__(self, root=ROOT, *, controller_attempt=1, runtime=None, registration=None):
        self.root = self.control_root = Path(root).resolve()
        require(self.root == ROOT.resolve(), "unregistered early-generation control root")
        self.control_registration = registration or importlib.import_module("finqa_v65_registration")
        self.control_protocol = self.control_registration.checked_protocol(self.root)
        self.control_registration.checked_implementation(self.root)
        self.control_prepared = self.control_registration.checked_prepared(self.root)
        self.scientific_protocol = binding.source_module("finqa_v63_registration").checked_protocol(SCIENTIFIC_ROOT)
        self.protocol = self.control_protocol
        require(self.scientific_protocol["id"] == self.control_protocol["scientific_protocol_id"] == binding.BASE_PROTOCOL_ID,
                "early generation cannot change its scientific identity")
        require(self.control_protocol["max_gpu_workers"] == MAX_WORKERS == 5
                and self.control_protocol["max_workers_per_gpu"] == 1
                and self.control_protocol["global_total_limit"] == 6
                and self.control_protocol["reserved_other_control_startup_gib"] == OTHER_CONTROL_STARTUP_GIB,
                "generation uses five slots plus one separately reserved recovery slot")
        self.runtime = runtime or importlib.import_module("finqa_v65_runtime").controller_runtime()
        self.priority = self.protocol["gpu_priority"]
        require(self.priority == self.control_protocol["gpu_priority"], "GPU scheduling priority changed")
        self.plan = generation_api().checked_plan(self.root)
        self.jobs = checked_generation_jobs(self.plan)
        self.core, self.active, self.accepted, self.launched = {}, {}, {}, set()
        self.evaluation_registered, self.explicit_stop, self.wait_started = True, False, None
        self.job_states = {key: inherited._initial_state() for key in self.jobs}
        self.attempt_history = []
        parent = binding.read_ref(self.control_prepared["inherited_journal"])
        require(parent["active_jobs"] == [] and parent["protocol_id"] == self.scientific_protocol["id"],
                "old scientific control must be completely settled before early generation")
        self.resource_wait_seconds = float(parent["resource_wait_seconds"])
        require(math.isfinite(self.resource_wait_seconds) and self.resource_wait_seconds >= 0,
                "historical resource waiting cannot be reset")
        require(type(controller_attempt) is int and controller_attempt >= 1
                and not (self.root / "closeout/record.json").exists(),
                "terminal early-generation runs cannot be reopened")
        self.controller_attempt = controller_attempt
        self.controller_directory = self.root / "controllers" / f"attempt{controller_attempt:04d}"
        self._restore_journal()

    def job_directory(self, job):
        require(job["job_id"] in self.jobs and job["kind"] == "generate",
                "early control cannot dispatch scientific core work")
        return self.root / "evaluations/jobs" / job["job_id"]

    def _host_gate(self, job):
        needed = original_base.host_requirement(job["kind"], self._memory())
        if needed is None:
            return None
        needed += OTHER_CONTROL_STARTUP_GIB * base.GIB
        try:
            observed = self.runtime.host_memory()
        except (OSError, ValueError):
            return None
        available = observed.get("available_bytes")
        if type(available) is not int or available < needed:
            return None
        return dict(available_bytes=available, required_bytes=needed,
            reserve_bytes=base.HOST_RESERVE_BYTES, live_worker_count=len(self.active),
            reserved_other_control_startup_gib=OTHER_CONTROL_STARTUP_GIB,
            global_total_worker_limit=6, own_worker_limit=MAX_WORKERS,
            other_control_actual_RSS_not_deducted=True)

    def acquire(self, job):
        if not can_dispatch(self.active):
            return None
        return super().acquire(job)

    def _audit(self, job):
        return inherited.checked_audit(importlib.import_module("finqa_v65_worker").audit_job_resume(self.root, job))

    def _restore_journal(self):
        require(not stop_requested(self.root), "explicit generation stop forbids automatic restart")
        path = self.root / "journal/state.json"
        if not path.exists():
            require(self.controller_attempt == 1, "missing first generation journal")
            return
        journal = evaluation.checked(path)
        lifecycle._control_binding(journal, self.protocol, self.control_protocol)
        inherited._require_empty_settled_journal(journal)
        require(journal["evaluation_registered"] is True and set(journal["job_states"]) == set(self.jobs)
                and journal["resource_wait_seconds"] >= self.resource_wait_seconds,
                "early-generation roster or inherited waiting changed")
        self.job_states, self.attempt_history = copy.deepcopy(journal["job_states"]), copy.deepcopy(journal["attempt_history"])
        self.resource_wait_seconds = journal["resource_wait_seconds"]
        for row in self.attempt_history:
            audit_attempt_exit(row, self.protocol, self.runtime)
        for key, ref in journal["accepted"].items():
            require(key in self.jobs and Path(ref["path"]).resolve() == self.job_directory(self.jobs[key]) / "accepted/record.json",
                    "accepted generation reference escaped its own job")
            self.accepted[key] = binding.read_ref(ref)
        for key, state in self.job_states.items():
            maximum = max((row["attempt"] for row in self.attempt_history if row["job_id"] == key), default=0)
            require(state["attempts"] == maximum and ((state["status"] == "COMPLETE") == (key in self.accepted)),
                    "generation attempt ordinal or accepted completion changed")
            if state["status"] in TERMINAL_STATES:
                continue
            try:
                audit = self._audit(self.jobs[key])
                require(audit["resume_allowed"] and audit["unknown_calls"] == 0
                        and audit["progress_units"] >= state["progress_units"],
                        "UNKNOWN or changed generation state is not resumable")
            except Exception as error:
                if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
                    if state["status"] != "AUDIT_IO_WAIT":
                        state["status"] = "PRE_DISPATCH_AUDIT_WAIT"
                    state.update(actual_errno=error.errno, next_eligible_epoch=time.time() + 300)
                else:
                    state.update(status="HARD_BLOCKED", reason="generation restart durable audit failed", error=str(error))

    def _validate_result(self, child):
        result = evaluation.checked(child.directory / "result/record.json")
        require(result["status"] == "COMPLETE" and result["registration_id"] == self.plan["id"]
                and result["job_id"] == child.job["job_id"] and result["sessions"] == child.job["denominator"]
                and result["feedback_batch"] == 1 and result["scoring_calls"] == 0
                and result["private_references_read"] is False,
                "generation result must have its registered dose and no scoring")
        seal = binding.read_ref(result["whole_queue_seal"])
        require(Path(result["whole_queue_seal"]["path"]).resolve() == child.directory / "whole_queue_seal/record.json"
                and seal["id"] == result["whole_queue_seal_id"] and seal["registration_id"] == self.plan["id"]
                and seal["job_id"] == child.job["job_id"] and seal["all_provider_calls_settled"] is True
                and seal["private_references_read"] is False,
                "generation needs its exact complete settled output seal")
        resources = result["resources"]
        require(resources["all_gates_passed"] is True and resources["single_process_lifetime_includes_loading"] is True,
                "generation must pass original full-lifetime resource gates")
        reused_path = child.attempt_dir / "reused_result/record.json"
        if reused_path.exists():
            proof = evaluation.checked(reused_path)
            closed = binding.read_ref(proof["source_resource_closeout"])
            require(proof["protocol_id"] == self.protocol["id"] and proof["job_id"] == child.job["job_id"]
                    and proof["scientific_calls"] == 0 and proof["verified_durable_result"] is True
                    and Path(proof["source_result"]["path"]).resolve() == child.directory / "result/record.json"
                    and binding.read_ref(proof["source_result"]) == result,
                    "CPU finalization cannot fabricate generation or rewrite a prior result")
        else:
            closed = evaluation.checked(self.root / "resources" / child.job["job_id"] /
                f"pid{child.process.pid}" / "closeout/record.json")
            protection = resources.get("resource_protection", {})
            require(resources.get("control_protocol_id") == self.control_protocol["id"]
                    and protection.get("policy") == self.control_protocol["memory_protection_policy"]
                    and protection.get("future_capacity_or_exclusivity_guaranteed") is False
                    and protection.get("warm_attempted") is False,
                    "new generation must use registered protection without replay-only warm allocation")
            require(closed["pid"] == child.process.pid and closed["gpu_index"] == child.gpu,
                    "resource closeout belongs to another actual generation worker")
        require(closed["status"] == "COMPLETE" and closed["protocol_id"] == self.protocol["id"]
                and closed["job_id"] == child.job["job_id"] and closed["resources"] == resources,
                "matching successful generation resource closeout required")
        return result

    def seal_training(self):
        raise ValueError("V65 cannot unlock, train, or reseal any scientific core branch")

    def finish(self):
        require(not self.explicit_stop and not stop_requested(self.root), "explicit stop before generation seal")
        require(set(self.accepted) == set(self.jobs) and len(self.jobs) == 20 and not self.active
                and sum(job["denominator"] for job in self.jobs.values()) == 6215,
                "all twenty authorized generation jobs need actual successful exits")
        for key, accepted in self.accepted.items():
            actual = binding.read_ref(accepted["actual_exit"])
            require(accepted["job_id"] == actual["job_id"] == key
                    and accepted["actual_exit_zero"] is True and actual["returncode"] == 0
                    and actual["actual_waitpid_observed"] is True,
                    "generation closeout requires actual accepted exit zero")
        result = evaluation.publish(self.root / "closeout/record.json", dict(
            schema="v65_early_generation_sealed_without_scoring.v1", status=SEALED_STATUS,
            protocol_id=self.protocol["id"], control_protocol_id=self.control_protocol["id"],
            scientific_protocol_id=self.scientific_protocol["id"],
            generation_registration_id=self.plan["id"], generation_jobs=20, generation_sessions=6215,
            active_workers=0, accepted_jobs={key: evaluation.file_binding(self.job_directory(self.jobs[key]) /
                "accepted/record.json") for key in self.accepted}, actual_attempts=self.attempt_history,
            original_core_jobs_unmodified_by_this_control=True, blocked_seed389_C05_not_retried_by_this_control=True,
            scoring_calls=0, private_references_read=False, promotion_computed=False,
            global_scientific_experiment_complete=False, global_scoring_authorized=False,
            original_all_24_generation_scoring_barrier_preserved=True,
            automatic_followup_started=False, resource_wait_seconds=self.resource_wait_seconds,
            finished_epoch=time.time()))
        self.journal()
        self.status(result["status"])
        return result


def controller_closeout_status(closeout, returncode):
    status = closeout["status"]
    return "CONTROLLER_NONZERO_AFTER_CLOSEOUT" if status in ("COMPLETE", SEALED_STATUS) and returncode != 0 else status


def controller_restart_audit(root, protocol, control_protocol, runtime):
    """Settle this control only; the authorized peer may retain its own leases."""
    root = Path(root).resolve()
    require(root == ROOT.resolve() and not stop_requested(root),
            "foreign root or explicit generation stop forbids controller restart")
    journal = evaluation.checked(root / "journal/state.json")
    lifecycle._control_binding(journal, protocol, control_protocol)
    inherited._require_empty_settled_journal(journal)
    for row in journal["attempt_history"]:
        audit_attempt_exit(row, protocol, runtime)
    # Every future worker still acquires its actual physical GPU's original
    # exclusive lease. Taking all eight here would incorrectly block recovery
    # while the independently authorized one-slot control is healthy.
    return journal


# Rebind only the new private module: no global original module is patched.
lifecycle.Controller = Controller
lifecycle.checked_attempt_directory = checked_attempt_directory
lifecycle.audit_attempt_exit = audit_attempt_exit
lifecycle.controller_restart_audit = controller_restart_audit
inherited.controller_closeout_status = controller_closeout_status
stop_orphaned_workers = lifecycle.stop_orphaned_workers
supervise = lifecycle.supervise


if __name__ == "__main__":
    raise SystemExit("use the frozen finqa_v65_entry.py; early signal observation is mandatory")
