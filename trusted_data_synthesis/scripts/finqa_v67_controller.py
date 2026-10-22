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
import os
import signal
import subprocess
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace

import finqa_v67_binding as binding

ROOT, SCIENTIFIC_ROOT = binding.ROOT, binding.SCIENTIFIC_ROOT
require = binding.require
SEALED_STATUS = "GENERATIONS_24_SEALED_AWAITING_GLOBAL_SCORING"
MAX_WORKERS = 3
PEER_WORKERS = 3
CPU_SEAL_RSS_GIB = 64
OTHER_CONTROL_STARTUP_GIB = 3 * 48 + CPU_SEAL_RSS_GIB


def _private_lifecycle():
    """Explicit, source-bound operational adapters; never edit frozen files."""
    source = binding.source_module("finqa_v63_controller")
    raw = Path(source.__file__).read_text()
    before = 'return importlib.import_module("finqa_v63_worker")'
    require(raw.count(before) == 1, "frozen generation attempt-disposition adapter changed")
    raw = raw.replace(before, 'return importlib.import_module("finqa_v67_worker")')
    queue = ModuleType("_v67_private_generation_queue")
    queue.__file__, queue.__package__ = str(Path(source.__file__).resolve()), ""
    sys.modules[queue.__name__] = queue
    exec(compile(raw, queue.__file__ + "::V67_generation_attempt_api", "exec"), queue.__dict__)
    original = binding.predecessor_module("finqa_v64_controller")
    raw = Path(original.__file__).read_text()
    substitutions = (
        ('import finqa_v64_binding as binding', 'import finqa_v67_binding as binding'),
        ('inherited = binding.source_module("finqa_v63_controller")', 'inherited = __v67_queue'),
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
    raw = raw.replace("finqa_v64_", "finqa_v67_").replace("V64_CONTROL_", "V67_CONTROL_")
    raw = raw.replace('V56_ATTEMPT_ID=directory.name, V56_ATTEMPT_DIR=str(directory),',
                      'V56_ATTEMPT_ID=directory.name, V56_ATTEMPT_DIR=str(directory), '
                      'V67_ATTEMPT_ID=directory.name, V67_ATTEMPT_DIR=str(directory),')
    raw = raw.replace('schema="v64_', 'schema="v67_')
    raw = raw.replace('protocol_id=self.protocol["id"],',
                      'protocol_id=self.protocol["id"], scientific_protocol_id=binding.BASE_PROTOCOL_ID,')
    raw = raw.replace('protocol_id=protocol["id"],',
                      'protocol_id=protocol["id"], scientific_protocol_id=binding.BASE_PROTOCOL_ID,')
    # CPU sealing children participate in every stop/restart/terminal decision.
    raw = raw.replace('self.evaluation_registered and set(self.jobs) == set(self.accepted) and not self.active:',
                      'self._all_work_complete():')
    raw = raw.replace('not self.active and all(s["status"] in TERMINAL_STATES for s in self.job_states.values()):',
                      'not self.active and self._all_repairs_terminal() and all(s["status"] in TERMINAL_STATES for s in self.job_states.values()):')
    raw = raw.replace('and not self.active', 'and not self.active and not self.cpu_active')
    raw = raw.replace('if self.active:', 'if self.active or self.cpu_active:')
    protected = ModuleType("_v67_private_protected_generation_lifecycle")
    protected.__file__, protected.__package__ = str(Path(original.__file__).resolve()), ""
    protected.__dict__["__v67_queue"] = queue
    sys.modules[protected.__name__] = protected
    exec(compile(raw, protected.__file__ + "::V67_generation_control", "exec"), protected.__dict__)
    return queue, protected


inherited, lifecycle = _private_lifecycle()
original_base, evaluation = inherited.base, inherited.evaluation


def can_dispatch(active):
    require(len(active) <= MAX_WORKERS, "registered three-worker generation cap exceeded")
    devices = [child.gpu for child in active.values()]
    require(len(devices) == len(set(devices)), "one V67 secondary-slot worker per physical GPU required")
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
    return importlib.import_module("finqa_v67_evaluation")


def sealing_api():
    return importlib.import_module("finqa_v67_sealing")


def checked_peer_snapshot(journal, prepared, *, terminal=None, now=None):
    now = time.time() if now is None else now
    roster, residual = set(prepared["peer_job_roster"]), set(prepared["peer_residual_roster"])
    require(len(roster) == 20 and len(residual) == PEER_WORKERS and residual <= roster,
            "peer registration must bind exactly twenty jobs and three residual jobs")
    require(journal["protocol_id"] == journal["control_protocol_id"] == prepared["peer_protocol_id"]
            and set(journal["job_states"]) == roster, "peer protocol or full job roster changed")
    require(all(journal["job_states"][key]["status"] in ("COMPLETE", "HARD_BLOCKED")
                for key in roster - residual), "old non-residual job became dispatchable")
    active = journal["active_jobs"]
    require(len(active) <= PEER_WORKERS and len({row["job_id"] for row in active}) == len(active)
            and {row["job_id"] for row in active} <= residual,
            "old peer exceeded its immutable three-job residual")
    require(len({row["gpu_index"] for row in active}) == len(active), "peer duplicated a physical GPU")
    if terminal is not None:
        require(terminal["protocol_id"] == prepared["peer_protocol_id"]
                and not active and terminal["active_workers"] == 0
                and all(s["status"] in TERMINAL_STATES for s in journal["job_states"].values()),
                "peer terminal record cannot conceal running or dispatchable jobs")
    elif not -5 <= now - journal["updated_epoch"] <= 60:
        return None
    return dict(peer_protocol_id=prepared["peer_protocol_id"],
                peer_job_roster_digest=binding.digest(sorted(roster)),
                peer_residual_roster=sorted(residual), peer_active_workers=len(active),
                peer_capacity_bound=PEER_WORKERS, terminal_observed=terminal is not None,
                snapshot_epoch=journal["updated_epoch"], observed_epoch=now,
                frozen_peer_HARD_BLOCKED_is_absorbing=True, old_worker_signals_sent=0)


def checked_cpu_attempt_directory(row):
    directory = Path(row["directory"]).resolve()
    require(row["attempt"] == 1 and directory == ROOT.resolve() / "repairs" / row["job_id"] / "attempt0001",
            "CPU sealing attempt escaped its distinct registered directory")
    return directory


def audit_cpu_attempt_exit(row, protocol, runtime):
    directory = checked_cpu_attempt_directory(row)
    launch_path = directory / "launch/record.json"
    if not launch_path.exists():
        failure = evaluation.checked(directory / "launch_failure/record.json")
        require(failure["actual_child_created"] is False and failure["protocol_id"] == protocol["id"]
                and failure["job_id"] == row["job_id"], "unsettled CPU dispatch may have a child")
        return
    launch = evaluation.checked(launch_path)
    actual = evaluation.checked(directory / "actual_exit/record.json")
    require(launch["protocol_id"] == actual["protocol_id"] == protocol["id"]
            and launch["job_id"] == actual["job_id"] == row["job_id"]
            and launch["attempt"] == actual["attempt"] == 1
            and (launch["pid"], launch["birth"]) == (actual["pid"], actual["birth"])
            and actual["actual_waitpid_observed"] is True and type(actual["returncode"]) is int
            and not inherited._same_live_identity(runtime, launch["pid"], launch["birth"]),
            "CPU sealing restart requires its actual observed settled exit")


def checked_generation_jobs(plan):
    jobs = {key: dict(value, kind="generate", dependencies=[], priority=0 if value["denominator"] == 883 else 1)
            for key, value in plan["jobs"].items()}
    allowed = {(389, "C05")}
    require(len(jobs) == 4 and sum(job["denominator"] for job in jobs.values()) == 1243
            and {(job["seed"], job["arm"]) for job in jobs.values()} == allowed
            and all(key == job["job_id"] and job["stage"] == "generate"
                    and job["feedback_batch"] == 1 and job["step"] == 894
                    for key, job in jobs.items()),
            "only the four original generation jobs from the final completed endpoint are allowed")
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
        self.control_registration = registration or importlib.import_module("finqa_v67_registration")
        self.control_protocol = self.control_registration.checked_protocol(self.root)
        self.control_registration.checked_implementation(self.root)
        self.control_prepared = self.control_registration.checked_prepared(self.root)
        self.scientific_protocol = binding.source_module("finqa_v63_registration").checked_protocol(SCIENTIFIC_ROOT)
        self.protocol = self.control_protocol
        require(self.scientific_protocol["id"] == self.control_protocol["scientific_protocol_id"] == binding.BASE_PROTOCOL_ID,
                "early generation cannot change its scientific identity")
        require(self.control_protocol["max_gpu_workers"] == MAX_WORKERS == 3
                and self.control_protocol["max_workers_per_gpu"] == 2
                and self.control_protocol["own_max_workers_per_gpu"] == 1
                and self.control_protocol["gpu_slot_policy"] == binding.gpu_slot_policy()
                and self.control_protocol["global_total_limit"] == 6
                and self.control_protocol["reserved_cross_control_startup_gib"] == OTHER_CONTROL_STARTUP_GIB
                and self.control_protocol["reserved_peer_gpu_workers"] == PEER_WORKERS
                and self.control_protocol["reserved_peer_worker_startup_gib"] == 48
                and self.control_protocol["cpu_seal_rss_limit_gib"] == CPU_SEAL_RSS_GIB,
                "new generation uses three slots plus the bounded old three-job residual")
        self.runtime = runtime or importlib.import_module("finqa_v67_runtime").controller_runtime()
        self.priority = self.protocol["gpu_priority"]
        require(self.priority == self.control_protocol["gpu_priority"], "GPU scheduling priority changed")
        self.plan = generation_api().checked_plan(self.root)
        self.jobs = checked_generation_jobs(self.plan)
        self.core, self.active, self.accepted, self.launched = {}, {}, {}, set()
        self.cpu_active = None
        self.repair_states = {key: dict(status="PENDING") for key in self.control_prepared["peer_job_roster"]}
        self.repairs_accepted, self.repair_history = {}, []
        self.evaluation_registered, self.explicit_stop, self.wait_started = True, False, None
        self.job_states = {key: inherited._initial_state() for key in self.jobs}
        self.attempt_history = []
        parent = binding.read_ref(self.control_prepared["inherited_journal"])
        require(parent["protocol_id"] == self.control_prepared["peer_protocol_id"],
                "peer generation protocol changed")
        require(len(self.repair_states) == 20 and len(self.control_prepared["peer_residual_roster"]) == PEER_WORKERS,
                "only twenty old jobs and their immutable three-job residual are registered")
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
        if self.peer_admission() is None:
            return None
        host = self._host_gate(job)
        if host is None:
            return None
        try:
            inventory = {row["index"]: row for row in self.runtime.inventory()}
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        # Legacy controls exclusively share the unchanged primary lock. This
        # scope exclusively shares one independent secondary lock, giving the
        # authorized bound of one legacy plus one new worker on each GPU. The
        # bound survives primary release/reacquisition without lock handoff.
        policy = binding.gpu_slot_policy()
        lease_root = Path(self.protocol["gpu_lease_root"]).resolve()
        require(self.protocol["gpu_slot_policy"] == policy
                and lease_root == Path(policy["second_slot_lease_root"]).resolve()
                and lease_root != Path(self.protocol["legacy_gpu_lease_root"]).resolve(),
                "new secondary lease namespace must not replace the legacy primary lock")
        used = {child.gpu for child in self.active.values()}
        for gpu in self.priority:
            row = inventory.get(gpu)
            if gpu in used or row is None or not original_base.gpu_eligible(row, self.protocol, job):
                continue
            path = lease_root / ("gpu-" + evaluation.digest(row["uuid"]) + ".lock")
            path.parent.mkdir(parents=True, exist_ok=True)
            lease = path.open("a")
            try:
                lifecycle.fcntl.flock(lease, lifecycle.fcntl.LOCK_EX | lifecycle.fcntl.LOCK_NB)
            except BlockingIOError:
                lease.close()
                continue
            try:
                fresh = next((r for r in self.runtime.inventory() if r["index"] == gpu), None)
                host = self._host_gate(job)
                if fresh is None or host is None or not original_base.gpu_eligible(fresh, self.protocol, job):
                    lease.close()
                    continue
                return fresh, lease, dict(host=host, gpu=fresh, lease_path=str(path),
                    lease_inode=path.stat().st_ino, minimum_free_mib=original_base.GPU_FREE_GIB["generate"] * 1024,
                    gpu_slot_policy=policy, own_slot="secondary", legacy_slot_touched=False,
                    per_GPU_new_bound=1, per_GPU_legacy_bound=1, per_GPU_total_bound=2)
            except BaseException:
                lease.close()
                raise
        return None

    def launch(self, job, acquired):
        try:
            peer = self.peer_admission()
            if peer is None:
                acquired[1].close()
                return
            acquired[2]["peer"] = peer
        except BaseException:
            acquired[1].close()
            raise
        return super().launch(job, acquired)

    def _audit(self, job):
        return inherited.checked_audit(importlib.import_module("finqa_v67_worker").audit_job_resume(self.root, job))

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
        require(journal.get("cpu_active") is None
                and not any(s["status"] in lifecycle.ACTIVE_STATES for s in journal["repair_states"].values()),
                "CPU sealing child or dispatch is not settled")
        self.repair_states = copy.deepcopy(journal["repair_states"])
        require(set(self.repair_states) == set(self.control_prepared["peer_job_roster"]),
                "CPU repair roster changed")
        self.repair_history = copy.deepcopy(journal["repair_history"])
        for row in self.repair_history:
            audit_cpu_attempt_exit(row, self.protocol, self.runtime)
        for key, ref in journal["repairs_accepted"].items():
            require(key in self.repair_states
                    and Path(ref["path"]).resolve() == self.root / "adopted" / key / "accepted/record.json",
                    "CPU accepted reference escaped its adopted job")
            self.repairs_accepted[key] = binding.read_ref(ref)
        for key, state in self.repair_states.items():
            history = [row for row in self.repair_history if row["job_id"] == key]
            require(len(history) <= 1 and ((state["status"] == "COMPLETE") == (key in self.repairs_accepted))
                    and (state["status"] != "PENDING" or not history),
                    "CPU attempt cannot be reset or accepted without a matching completed state")
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
        raise ValueError("V67 cannot unlock, train, or reseal any scientific core branch")

    def peer_admission(self):
        """Bound the unchanged five-slot peer by its immutable residual roster.

        HARD_BLOCKED is absorbing in the frozen peer. Its 17 other jobs cannot
        be retried; only the three registered residual jobs may remain active.
        Controller restarts are allowed only with their new immutable launch
        matching the latest journal. An absent heartbeat is a wait, not proof
        of process exit or extra capacity.
        """
        peer = binding.OLD_GENERATION_ROOT
        journal = binding.checked(peer / "journal/state.json")
        terminal_path = peer / "closeout/record.json"
        terminal = binding.checked(terminal_path) if terminal_path.exists() else None
        receipt = checked_peer_snapshot(journal, self.control_prepared, terminal=terminal)
        if receipt is None or terminal is not None:
            return receipt
        launch = binding.checked(peer / "controllers" / f"attempt{journal['controller_attempt']:04d}" / "launch/record.json")
        require(launch["protocol_id"] == self.control_prepared["peer_protocol_id"]
                and launch["controller_attempt"] == journal["controller_attempt"],
                "peer controller launch identity changed")
        if not inherited._same_live_identity(self.runtime, launch["pid"], launch["birth"]):
            return None
        return dict(receipt, controller_pid=launch["pid"], controller_birth=launch["birth"],
                    controller_attempt=journal["controller_attempt"])

    def _all_work_complete(self):
        return (set(self.accepted) == set(self.jobs) and not self.active and self.cpu_active is None
                and set(self.repairs_accepted) == set(self.repair_states))

    def _all_repairs_terminal(self):
        return self.cpu_active is None and all(s["status"] in TERMINAL_STATES for s in self.repair_states.values())

    def journal(self):
        child = self.cpu_active
        value = dict(schema="v67_actual_generation_and_CPU_sealing_journal.v1",
            protocol_id=self.protocol["id"], control_protocol_id=self.control_protocol["id"],
            scientific_protocol_id=binding.BASE_PROTOCOL_ID, controller_attempt=self.controller_attempt,
            updated_epoch=time.time(), active_jobs=[dict(job_id=key, pid=c.process.pid,
                birth=c.birth, gpu_index=c.gpu, attempt=c.attempt) for key, c in self.active.items()],
            job_states=self.job_states, attempt_history=self.attempt_history,
            accepted={key: evaluation.file_binding(self.job_directory(self.jobs[key]) / "accepted/record.json")
                      for key in self.accepted}, evaluation_registered=True,
            cpu_active=None if child is None else dict(job_id=child.job_id, pid=child.process.pid,
                birth=child.birth, directory=str(child.directory), attempt=1),
            repair_states=self.repair_states, repair_history=self.repair_history,
            repairs_accepted={key: evaluation.file_binding(self.root / "adopted" / key / "accepted/record.json")
                              for key in self.repairs_accepted},
            resource_wait_seconds=self.resource_wait_seconds, old_stop_and_failure_records_unchanged=True)
        base._status(self.root / "journal/state.json", evaluation.bound(value))

    def status(self, status):
        child = self.cpu_active
        base._status(self.root / "queue/status.json", dict(schema="v67_parallel_completion_queue.v1",
            status=status, protocol_id=self.protocol["id"], control_protocol_id=self.control_protocol["id"],
            scientific_protocol_id=binding.BASE_PROTOCOL_ID, controller_attempt=self.controller_attempt,
            updated_epoch=time.time(), active_workers=[dict(job_id=key, pid=c.process.pid,
                birth=c.birth, gpu_index=c.gpu, attempt=c.attempt, lifecycle=c.lifecycle)
                for key, c in self.active.items()], max_gpu_workers=MAX_WORKERS,
            peer_max_residual_gpu_workers=PEER_WORKERS, global_gpu_worker_limit=6,
            cpu_active=None if child is None else dict(job_id=child.job_id, pid=child.process.pid,
                birth=child.birth, gpu_worker=False), max_cpu_sealing_workers=1,
            accepted_jobs=list(self.accepted), job_states=self.job_states,
            adopted_jobs=list(self.repairs_accepted), repair_states=self.repair_states,
            resource_wait_seconds=self.resource_wait_seconds, scoring_calls=0))

    def _cpu_host_gate(self):
        needed = original_base.host_requirement("generate", self._memory())
        if needed is None:
            return None
        # Replace the candidate generation startup budget with 64 GiB for the
        # only CPU child; reserve every possible peer worker without RSS credit.
        needed += (CPU_SEAL_RSS_GIB - original_base.HOST_STARTUP_GIB["generate"] + 3 * 48) * base.GIB
        try:
            observed = self.runtime.host_memory()
        except (OSError, ValueError):
            return None
        available = observed.get("available_bytes")
        if type(available) is not int or available < needed:
            return None
        return dict(available_bytes=available, required_bytes=needed,
                    CPU_RSS_limit_gib=CPU_SEAL_RSS_GIB, peer_reserved_gib=144,
                    original_host_reserve_gib=96, GPU_initialized=False)

    def _launch_cpu(self, key, eligibility, admission):
        require(self.cpu_active is None and self.repair_states[key]["status"] == "PENDING",
                "only one previously unstarted CPU sealing attempt is allowed")
        directory = self.root / "repairs" / key / "attempt0001"
        require(not directory.exists(), "CPU sealing attempt is immutable and cannot be retried")
        evaluation.publish(directory / "dispatch_intent/record.json", dict(
            schema="v67_CPU_only_sealing_dispatch.v1", protocol_id=self.protocol["id"],
            control_protocol_id=self.protocol["id"], job_id=key, attempt=1,
            eligibility=eligibility, admission=admission, CUDA_initialized=False,
            provider_calls=0, scoring_calls=0, created_epoch=time.time()))
        self.repair_states[key] = dict(status="DISPATCHING", attempts=1)
        self.repair_history.append(dict(job_id=key, attempt=1, directory=str(directory)))
        self.journal()
        command = [str(base.PYTHON), "-u", str(self.root / "implementation/finqa_v67_entry.py"),
            "--mode", "seal", "--root", str(self.root), "--job", key, "--attempt-root", str(directory)]
        environment = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONPATH=execution_pythonpath(self.root),
            V67_CONTROL_ROOT=str(self.root), V67_CONTROL_PROTOCOL_ID=self.protocol["id"], V54_JOB_ID=key,
            V63_ATTEMPT_ID=directory.name, V56_ATTEMPT_ID=directory.name,
            V63_ATTEMPT_DIR=str(directory), V56_ATTEMPT_DIR=str(directory),
            V67_ATTEMPT_ID=directory.name, V67_ATTEMPT_DIR=str(directory))
        environment.pop("V54_GPU_LEASE_FD", None)
        try:
            with (directory / "worker.log").open("xb") as log:
                process = subprocess.Popen(command, cwd=base.REPO, env=environment, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True)
        except BaseException as error:
            evaluation.publish(directory / "launch_failure/record.json", dict(
                protocol_id=self.protocol["id"], job_id=key, actual_child_created=False,
                error_type=type(error).__name__, error=str(error)))
            self.repair_states[key] = dict(status="HARD_BLOCKED", reason="CPU launch failed", error=str(error))
            self.journal()
            return
        child = SimpleNamespace(job_id=key, process=process, birth=self.runtime.birth(process.pid),
            directory=directory, resource_failure=None)
        self.cpu_active = child
        require((isinstance(child.birth, str) and child.birth.isdigit()) or process.poll() is not None,
                "live CPU sealing worker requires its actual birth")
        evaluation.publish(directory / "launch/record.json", dict(schema="v67_actual_CPU_sealing_launch.v1",
            protocol_id=self.protocol["id"], control_protocol_id=self.protocol["id"],
            job_id=key, attempt=1, pid=process.pid, birth=child.birth, command=command,
            cuda_visible_devices="", GPU_worker=False, admission=admission, started_epoch=time.time()))
        self.repair_states[key] = dict(status="RUNNING", attempts=1, pid=process.pid, birth=child.birth)
        self.journal()

    def _signal_cpu(self, signum):
        child = self.cpu_active
        if child is not None and inherited._same_live_identity(self.runtime, child.process.pid, child.birth):
            try:
                os.kill(child.process.pid, signum)
            except ProcessLookupError:
                pass

    def _reap_cpu(self):
        child = self.cpu_active
        if child is None:
            return
        code = child.process.poll()  # Popen performs the actual child waitpid.
        if code is None:
            try:
                memory = self.runtime.process_memory(child.process.pid)
                host = self.runtime.host_memory()
            except (OSError, ValueError):
                return
            if memory is not None and (memory["peak_rss_bytes"] > CPU_SEAL_RSS_GIB * base.GIB
                                       or host["available_bytes"] < base.HOST_RESERVE_BYTES):
                child.resource_failure = dict(memory=memory, host=host)
                self._signal_cpu(signal.SIGTERM)
            return
        key = child.job_id
        evaluation.publish(child.directory / "actual_exit/record.json", dict(
            schema="v67_actual_CPU_sealing_exit.v1", protocol_id=self.protocol["id"],
            control_protocol_id=self.protocol["id"], job_id=key, attempt=1,
            pid=child.process.pid, birth=child.birth, returncode=code, actual_waitpid_observed=True,
            GPU_worker=False, resource_failure=child.resource_failure, observed_epoch=time.time()))
        try:
            require(code == 0 and child.resource_failure is None and not self.explicit_stop,
                    "CPU sealing needs its own actual successful exit and resource gates")
            accepted = sealing_api().accept_cpu_repair(self.root, key, child.directory)
            self.repairs_accepted[key] = accepted
            self.repair_states[key] = dict(status="COMPLETE", attempts=1)
        except Exception as error:
            self.repair_states[key] = dict(status="HARD_BLOCKED", attempts=1,
                error_type=type(error).__name__, error=str(error), reason="CPU sealing did not pass acceptance")
            evaluation.publish(child.directory / "acceptance_failure/record.json", dict(
                protocol_id=self.protocol["id"], job_id=key, error_type=type(error).__name__,
                error=str(error), automatic_retry=False, old_generation_exit_not_rewritten=True))
        finally:
            self.cpu_active = None
        self.journal()

    def _pump_cpu(self):
        if self.cpu_active is not None or self.explicit_stop or stop_requested(self.root):
            return
        for key, state in self.repair_states.items():
            if state["status"] != "PENDING":
                continue
            try:
                eligibility = sealing_api().eligible_source_job(self.root, key)
                if eligibility["status"] == "WAIT":
                    continue
                require(eligibility["status"] == "ELIGIBLE", "unknown CPU sealing eligibility")
                admission = self._cpu_host_gate()
                if admission is None:
                    return
                self._launch_cpu(key, eligibility, admission)
                return
            except Exception as error:
                state.update(status="HARD_BLOCKED", error_type=type(error).__name__, error=str(error),
                             reason="old durable generation is not eligible for CPU sealing")

    def reap(self):
        super().reap()
        self._reap_cpu()
        self._pump_cpu()

    def _stop(self, reason):
        self.explicit_stop = True
        marker = self.root / "control/stop_requested/record.json"
        if not marker.exists():
            evaluation.publish(marker, dict(schema="v67_terminal_explicit_stop.v1",
                protocol_id=self.protocol["id"], control_protocol_id=self.protocol["id"],
                reason=reason, at_epoch=time.time(), automatic_restart_allowed=False))
        deadline = time.monotonic() + base.STOP_GRACE_SECONDS
        self._signal_cpu(signal.SIGTERM)
        for child in self.active.values():
            self._signal(child, signal.SIGTERM)
        while (self.active or self.cpu_active is not None) and time.monotonic() < deadline:
            self.reap()
            self.status("STOPPING_NO_AUTO_RESTART")
            if self.active or self.cpu_active is not None:
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
        self._signal_cpu(signal.SIGKILL)
        for child in self.active.values():
            self._signal(child, signal.SIGKILL)
        while self.active or self.cpu_active is not None:
            self.reap()
            if self.active or self.cpu_active is not None:
                time.sleep(0.2)
        return self._terminal("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME")

    def finish(self):
        require(not self.explicit_stop and not stop_requested(self.root) and self._all_work_complete(),
                "all four new and twenty adopted generations require separate actual exits")
        require(len(self.accepted) == 4 and len(self.repairs_accepted) == 20,
                "all original 24 jobs must be sealed before completion")
        for key, accepted in self.accepted.items():
            actual = binding.read_ref(accepted["actual_exit"])
            require(actual["job_id"] == key and actual["returncode"] == 0
                    and actual["actual_waitpid_observed"] is True and accepted["actual_exit_zero"] is True,
                    "new generation acceptance requires actual exit zero")
        for row in self.repair_history:
            actual = evaluation.checked(Path(row["directory"]) / "actual_exit/record.json")
            require(actual["returncode"] == 0 and actual["actual_waitpid_observed"] is True,
                    "adopted generation requires CPU repair's separate actual exit zero")
        result = evaluation.publish(self.root / "closeout/record.json", dict(
            schema="v67_all_24_generation_sealed_without_scoring.v1", status=SEALED_STATUS,
            protocol_id=self.protocol["id"], control_protocol_id=self.protocol["id"],
            scientific_protocol_id=binding.BASE_PROTOCOL_ID, generation_registration_id=self.plan["id"],
            generation_jobs=24, generation_sessions=7458, new_generation_jobs=4, new_generation_sessions=1243,
            adopted_generation_jobs=20, adopted_generation_sessions=6215,
            accepted_jobs={key: evaluation.file_binding(self.job_directory(self.jobs[key]) / "accepted/record.json")
                           for key in self.accepted},
            adopted_jobs={key: evaluation.file_binding(self.root / "adopted" / key / "accepted/record.json")
                          for key in self.repairs_accepted},
            active_workers=0, active_CPU_workers=0, scoring_calls=0, private_references_read=False,
            global_scientific_experiment_complete=False, global_scoring_authorized=False,
            original_all_24_generation_scoring_barrier_preserved=True, old_failures_and_exit_codes_unchanged=True,
            resource_wait_seconds=self.resource_wait_seconds, finished_epoch=time.time()))
        self.journal()
        self.status(SEALED_STATUS)
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
    require(journal.get("cpu_active") is None
            and not any(s["status"] in lifecycle.ACTIVE_STATES for s in journal["repair_states"].values()),
            "CPU sealing child or dispatch is unsettled")
    for row in journal["repair_history"]:
        audit_cpu_attempt_exit(row, protocol, runtime)
    for row in journal["attempt_history"]:
        audit_attempt_exit(row, protocol, runtime)
    # Every future worker still acquires its actual physical GPU's original
    # exclusive lease. Taking all eight here would incorrectly block recovery
    # while the independently authorized one-slot control is healthy.
    return journal


def stop_orphaned_workers(root, protocol, control_protocol, runtime):
    """Stop only identity-verified children of this scope, including CPU seal.

    A supervisor is not the orphan's parent and cannot observe waitpid. The
    record states that explicitly; no missing CPU or GPU exit becomes zero.
    """
    root = Path(root).resolve()
    require(root == ROOT.resolve(), "orphan stop escaped the new completion scope")
    marker = root / "control/stop_requested/record.json"
    if not marker.exists():
        evaluation.publish(marker, dict(schema="v67_terminal_explicit_stop.v1",
            protocol_id=protocol["id"], control_protocol_id=control_protocol["id"],
            reason="explicit supervisor/controller stop", at_epoch=time.time(), automatic_restart_allowed=False))
    rows, unresolved_cpu_dispatches = [], []
    path = root / "journal/state.json"
    if path.exists():
        journal = evaluation.checked(path)
        lifecycle._control_binding(journal, protocol, control_protocol)
        for active in journal["active_jobs"]:
            history = [r for r in journal["attempt_history"]
                       if (r["job_id"], r["attempt"]) == (active["job_id"], active["attempt"])]
            require(len(history) == 1, "GPU orphan lacks exact attempt history")
            directory = checked_attempt_directory(history[0])
            launch = evaluation.checked(directory / "launch/record.json")
            require(launch["job"]["job_id"] == active["job_id"] and launch["attempt"] == active["attempt"],
                    "GPU orphan launch differs")
            rows.append(dict(active, directory=directory, CPU_only=False, launch=launch))
        active = journal.get("cpu_active")
        if active is not None:
            directory = checked_cpu_attempt_directory(active)
            launch = evaluation.checked(directory / "launch/record.json")
            require(launch["job_id"] == active["job_id"] and launch["attempt"] == 1,
                    "CPU orphan launch differs")
            rows.append(dict(active, directory=directory, CPU_only=True, launch=launch))
        # A controller can die after publishing a child's launch but before
        # its next active-child journal write. The immutable dispatch history
        # must still be inspected; absence of both launch and no-child proof
        # is UNKNOWN, never evidence that no CPU process exists.
        identified_cpu = {r["job_id"] for r in rows if r["CPU_only"]}
        for history in journal.get("repair_history", []):
            key = history["job_id"]
            if key in identified_cpu or journal["repair_states"][key]["status"] not in lifecycle.ACTIVE_STATES:
                continue
            directory = checked_cpu_attempt_directory(history)
            launch_path = directory / "launch/record.json"
            if not launch_path.exists():
                failed_path = directory / "launch_failure/record.json"
                if failed_path.exists():
                    failed = evaluation.checked(failed_path)
                    require(failed["protocol_id"] == protocol["id"] and failed["job_id"] == key
                            and failed["actual_child_created"] is False,
                            "CPU dispatch no-child proof differs")
                else:
                    unresolved_cpu_dispatches.append(dict(job_id=key, directory=str(directory),
                        reason="dispatch may have created a child but actual launch identity is unavailable"))
                continue
            launch = evaluation.checked(launch_path)
            require(launch["job_id"] == key and launch["attempt"] == 1,
                    "CPU dispatch launch identity differs from immutable history")
            rows.append(dict(job_id=key, attempt=1, pid=launch["pid"], birth=launch["birth"],
                directory=directory, CPU_only=True, launch=launch,
                recovered_from_immutable_dispatch_history=True))
    for row in rows:
        launch = row.pop("launch")
        require(launch["protocol_id"] == protocol["id"]
                and (launch["pid"], launch["birth"]) == (row["pid"], row["birth"]),
                "orphan stop requires exact own launch identity")
        row["launch"] = evaluation.file_binding(row.pop("directory") / "launch/record.json")
        row["signals_sent"] = []
    deadline = time.monotonic() + base.STOP_GRACE_SECONDS
    for signum in (signal.SIGTERM, signal.SIGKILL):
        for row in rows:
            if inherited._same_live_identity(runtime, row["pid"], row["birth"]):
                try:
                    os.kill(row["pid"], signum)
                    row["signals_sent"].append(signum)
                except ProcessLookupError:
                    pass
        until = deadline if signum == signal.SIGTERM else time.monotonic() + 30
        while time.monotonic() < until and any(
                inherited._same_live_identity(runtime, r["pid"], r["birth"]) for r in rows):
            time.sleep(max(0, min(POLL_SECONDS, until - time.monotonic())))
    for row in rows:
        row.update(identity_observed_exited=not inherited._same_live_identity(runtime, row["pid"], row["birth"]),
                   OS_exitcode_independently_observed=False, OS_exitcode=None)
    return evaluation.publish(root / "supervisor/orphan_stop/record.json", dict(
        schema="v67_explicit_stop_GPU_and_CPU_orphan_audit.v1", protocol_id=protocol["id"],
        control_protocol_id=control_protocol["id"], workers=rows,
        all_identities_observed_exited=not unresolved_cpu_dispatches
            and all(r["identity_observed_exited"] for r in rows),
        unresolved_cpu_dispatches=unresolved_cpu_dispatches,
        shared_cooperative_grace_seconds=base.STOP_GRACE_SECONDS, automatic_restart_allowed=False,
        old_generation_control_signaled=False, nonchild_waitpid_or_exit_zero_not_fabricated=True))


# Rebind only the new private module: no global original module is patched.
lifecycle.Controller = Controller
lifecycle.checked_attempt_directory = checked_attempt_directory
lifecycle.audit_attempt_exit = audit_attempt_exit
lifecycle.controller_restart_audit = controller_restart_audit
lifecycle.stop_orphaned_workers = stop_orphaned_workers
inherited.controller_closeout_status = controller_closeout_status
supervise = lifecycle.supervise


if __name__ == "__main__":
    raise SystemExit("use the frozen finqa_v67_entry.py; early signal observation is mandatory")

