"""One conditional GPU0-to-GPU6 migration at an actual durable boundary.

The original target is signaled at most once, only after GPU6 is physically
idle, its secondary lease is held, and the frozen source queue is safe. This
coordinator never signals another source worker/controller or uses SIGKILL.
"""
from __future__ import annotations

import fcntl
import importlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import finqa_v69_binding as b

MODES = ("check-imports", "run")
POLL_SECONDS = 5
GIB = 1024 ** 3
COMPLETE_STATUS = "MIGRATION_COMPLETE_TARGET_ACCEPTED"
NO_MIGRATION_STATUS = "NO_MIGRATION_NEEDED"
_OBSERVER = None


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return None if fields[0] in ("Z", "X", "x") else fields[19]


def alive(pid, birth):
    b.require(type(pid) is int and pid > 0 and isinstance(birth, str) and birth.isdigit(),
              "positive PID and exact numeric birth identity required")
    return identity(pid) == birth


def stop_requested(root):
    return (Path(root) / "control/stop_requested/record.json").exists()


def signal_api():
    return b.source_module("finqa_v63_signals")


def checked_signal_registration(root, protocol=None):
    b.require(Path(root).resolve() == b.ROOT.resolve(), "foreign migration signal root")
    protocol = b.checked(Path(root) / "protocol/record.json") if protocol is None else protocol
    source, signals = b.base_protocol(), signal_api()
    b.require(protocol["scientific_protocol_id"] == source["id"] == b.BASE_PROTOCOL_ID
        and protocol["signal_policy"] == source["signal_policy"] == signals.signals_policy()
        and protocol["signal_source_bindings"] == source["signal_source_bindings"] == signals.external_source_bindings(),
        "migration cannot change the original legal-stop filter")
    return protocol


def require_early_install(modules=None):
    allowed = {"finqa_v69_binding.py", "finqa_v69_entry.py", "finqa_v67_binding.py", "finqa_v65_binding.py",
        "finqa_v64_binding.py", "finqa_v63_binding.py", "finqa_v63_signals.py", "finqa_v59_signals.py",
        "finqa_v58_signals.py", "finqa_v58_observer.py"}
    for name, module in (sys.modules if modules is None else modules).items():
        origin = getattr(module, "__file__", None)
        if (name == "torch" or name.startswith("torch.") or name == "trusted_synthesis"
                or name.startswith("trusted_synthesis.")
                or origin and Path(origin).name.startswith("finqa_") and Path(origin).name not in allowed):
            raise RuntimeError("migration signal observation must precede scientific imports: " + name)


def install_signal_observer(root, mode, protocol):
    global _OBSERVER
    b.require(_OBSERVER is None and os.getuid() == os.geteuid() == b.OWNER_UID,
              "one registered nonroot migration signal observer is required")
    require_early_install()
    directory = root / ("coordinator/signals" if mode == "run" else "frozen_import_verification/signals")
    _OBSERVER = signal_api()._reference().install(directory, role=mode, context=dict(
        control_root=str(root), protocol_id=protocol["id"], target_job_id=b.TARGET_JOB_ID,
        source_gpu=0, destination_gpu=6, original_signal_policy_unchanged=True))
    return _OBSERVER


def runtime_api():
    b.install_scientific_paths()
    b.source_module("finqa_v63_entry").install_registered_auxiliary()
    return b.completion_module("finqa_v67_runtime").controller_runtime()


def verify_imported_modules(root, implementation, *, modules=None):
    root = Path(root).resolve()
    b.require(root == b.ROOT.resolve(), "foreign migration dependency root")
    previous, additions = {}, []
    for name, module in sorted((sys.modules if modules is None else modules).items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        if path.name.startswith("finqa_v69_") or name.startswith("finqa_v69_"):
            b.require(path.parent == root / "implementation" and path.name in implementation["sha256"]
                and b.sha(path) == implementation["sha256"][path.name], "workspace or changed migration source")
            additions.append(dict(module=name, path=str(path), sha256=b.sha(path), origin="frozen_one_target_migration"))
        else:
            previous[name] = module
    parent = b.completion_module("finqa_v67_entry")
    parent_root = Path(parent.__file__).resolve().parent.parent
    inherited = parent.verify_imported_modules(parent_root, b.checked(parent_root / "implementation/record.json"),
                                               modules=previous)
    verified = inherited["verified_dependencies"] + additions
    return dict(verified_dependencies=verified, verified_dependency_count=len(verified),
        verified_dependencies_digest=b.digest(verified), new_migration_sources=additions,
        original_worker_frozen_closure_verified=True)


def check_imports(root):
    registration = importlib.import_module("finqa_v69_registration")
    protocol = registration.checked_protocol(root)
    checked_signal_registration(root, protocol)
    implementation = registration.checked_implementation(root)
    registration.modules()
    original = b.completion_module("finqa_v67_entry").initialize_science()
    training = b.source_module("finqa_v63_training")
    _, model_runtime = training.runtime()
    for name in (*original.WORKER_IMPORTS, *original.RECOVERY_IMPORTS, *original.NEW_IMPORTS):
        importlib.import_module(name)
    for name in ("finqa_v67_runtime", "finqa_v67_evaluation", "finqa_v67_worker", "finqa_v67_controller"):
        b.completion_module(name)
    b.require(not model_runtime.torch.cuda.is_initialized(), "CPU migration preflight cannot initialize CUDA")
    dependencies = verify_imported_modules(root, implementation)
    body = dict(schema="v69_actual_frozen_original_worker_CPU_import_check.v1", status="PASS",
        protocol_id=protocol["id"], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        implementation_id=implementation["id"], CUDA_initialized=False, model_loaded=False,
        source_signals_sent=0, generation_calls=0, scoring_calls=0, private_references_read=False,
        **dependencies)
    return dict(body, id=b.digest(body))


def _status(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = dict(value, id=b.digest(value))
    fd, temporary = tempfile.mkstemp(prefix=".v69-status-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def physical_destination_gate(row, source_protocol):
    expected = source_protocol["gpu_uuids"]["6"]
    b.require(row["index"] == 6 and row["uuid"] == expected, "destination physical GPU identity changed")
    isolation = row.get("gpu_isolation", {})
    b.require(isolation.get("gpu_uuid") == expected, "destination isolation snapshot UUID changed")
    if (isolation.get("allowed") is not True or isolation.get("known_processes") != []
            or isolation.get("unresolved_processes") != [] or isolation.get("process_count") != 0
            or row.get("processes") != []):
        return False
    free = row.get("free_mib", row.get("memory_free_mib"))
    minimum = source_protocol["resource_policy"]["minimum_free_gib_by_kind"]["generate"]
    b.require(minimum == 24, "the original generation admission threshold changed")
    return type(free) in (int, float) and math.isfinite(free) and free >= minimum * 1024


def checked_accepted_job(source_root, job_id, source_protocol, *, expected_identity=None):
    directory = Path(source_root) / "evaluations/jobs" / job_id
    path = directory / "accepted/record.json"
    if not path.exists():
        return None
    accepted = b.checked(path)
    actual = b.read_ref(accepted["actual_exit"])
    launch_path = Path(accepted["actual_exit"]["path"]).parent.parent / "launch/record.json"
    launch = b.checked(launch_path)
    b.require(accepted["protocol_id"] == actual["protocol_id"] == launch["protocol_id"] == source_protocol["id"]
        and accepted["job_id"] == actual["job_id"] == launch["job"]["job_id"] == job_id
        and accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
        and actual["actual_waitpid_observed"] is True and type(actual["returncode"]) is int and actual["returncode"] == 0
        and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"])
        and not alive(actual["pid"], actual["birth"]),
        "a completed source job needs its bound accepted result and real successful exit")
    if expected_identity is not None:
        b.require((actual["pid"], actual["birth"]) == expected_identity,
                  "the registered source/destination waiting job changed identity")
    return b.entry(path)


class Migration:
    def __init__(self, root, *, runtime=None, registration=None, bridge=None):
        self.root = Path(root).resolve()
        b.require(self.root == b.ROOT.resolve(), "foreign migration root")
        self.registration = registration or importlib.import_module("finqa_v69_registration")
        self.protocol = self.registration.checked_protocol(self.root)
        self.registration.checked_implementation(self.root)
        self.registration.checked_prepared(self.root)
        self.source = b.read_ref(self.protocol["source_protocol"])
        self.plan = b.read_ref(self.protocol["source_plan"])
        self.target, self.destination = self.protocol["target"], self.protocol["destination"]
        self.controller = self.protocol["source_controller"]
        b.require(self.target == dict(job_id=b.TARGET_JOB_ID, pid=b.TARGET_PID, birth=b.TARGET_BIRTH,
            gpu_index=0, attempt=1) and self.destination["gpu_index"] == 6
            and self.destination["await_job_id"] == b.DESTINATION_JOB_ID
            and self.protocol["startup_available_gib"] == b.STARTUP_AVAILABLE_GIB == 512,
            "migration must retain the single registered job and source/destination identities")
        self.runtime = runtime or runtime_api()
        self.bridge = bridge or importlib.import_module("finqa_v69_worker_bridge")
        self.lease, self.child, self.baseline = None, None, None
        self.signals, self.source_signal_sent, self.child_signal_sent = [], False, False

    def cancelled(self):
        return bool(self.signals or stop_requested(self.root))

    def status(self, status, **extra):
        _status(self.root / "queue/status.json", dict(schema="v69_conditional_single_target_migration_queue.v1",
            protocol_id=self.protocol["id"], status=status, updated_epoch=time.time(),
            target=self.target, destination_gpu=6, destination_lease_held=self.lease is not None,
            source_signal_sent=self.source_signal_sent, source_SIGKILL_allowed=False,
            child=None if self.child is None else dict(pid=self.child.process.pid, birth=self.child.birth,
                gpu_index=6, actual_exit_observed=self.child.process.returncode is not None),
            other_workers_or_controllers_signaled=False, automatic_retry=False, **extra))

    def target_completed(self):
        return checked_accepted_job(b.SOURCE_ROOT, b.TARGET_JOB_ID, self.source,
            expected_identity=(b.TARGET_PID, b.TARGET_BIRTH))

    def readiness(self):
        accepted = self.target_completed()
        if accepted is not None:
            return dict(status=NO_MIGRATION_STATUS, accepted=accepted)
        journal = b.checked(b.SOURCE_ROOT / "journal/state.json")
        b.require(journal["protocol_id"] == self.source["id"]
            and set(journal["job_states"]) == set(self.plan["jobs"]), "source job roster or protocol changed")
        b.require(journal["controller_attempt"] == self.controller["controller_attempt"]
            and alive(self.controller["pid"], self.controller["birth"]), "source controller identity changed")
        if not -5 <= time.time() - journal["updated_epoch"] <= 60:
            return dict(status="WAIT", reason="source journal is not fresh")
        state = journal["job_states"][b.TARGET_JOB_ID]
        generation = b.target_directory() / "shards" / self.plan["jobs"][b.TARGET_JOB_ID]["panel"] / "generation"
        native_seal = generation / "generation_seal/seal.json"
        if (b.target_directory() / "result/record.json").exists() or native_seal.exists():
            b.require(state["status"] not in ("HARD_BLOCKED", "DEPENDENCY_BLOCKED"),
                      "a failed source completion is not a natural successful exit")
            return dict(status="WAIT", reason="target native output complete; waiting for actual successful exit and acceptance")
        b.require(state["status"] in ("RUNNING", "DRAINING")
            and state["attempts"] == 1 and alive(b.TARGET_PID, b.TARGET_BIRTH),
            "target source identity or healthy attempt changed before migration")
        target_rows = [row for row in journal["active_jobs"] if row["job_id"] == b.TARGET_JOB_ID]
        b.require(len(target_rows) == 1 and (target_rows[0]["pid"], target_rows[0]["birth"],
            target_rows[0]["gpu_index"], target_rows[0]["attempt"]) == (b.TARGET_PID, b.TARGET_BIRTH, 0, 1),
            "target active launch does not match the registered exact identity")
        other = set(self.plan["jobs"]) - {b.TARGET_JOB_ID}
        b.require(not any(journal["job_states"][key]["status"] in ("HARD_BLOCKED", "DEPENDENCY_BLOCKED")
            for key in other), "another source job failed; this migration cannot retry or ignore that failure")
        if not all(journal["job_states"][key]["status"] == "COMPLETE" for key in other):
            return dict(status="WAIT", reason="registered GPU6 job has not completed and actually exited")
        b.require(len(journal["active_jobs"]) == 1, "source has another unsettled generation worker")
        for key in other:
            proof = checked_accepted_job(b.SOURCE_ROOT, key, self.source,
                expected_identity=(b.DESTINATION_PID, b.DESTINATION_BIRTH) if key == b.DESTINATION_JOB_ID else None)
            b.require(proof is not None, "source COMPLETE without accepted successful exit")
        old = b.checked(b.SOURCE_GENERATION_ROOT / "journal/state.json")
        b.require(old["protocol_id"] == b.EARLY_PROTOCOL_ID, "legacy generation protocol changed")
        if any(row["gpu_index"] == 6 for row in old["active_jobs"]):
            return dict(status="WAIT", reason="legacy GPU6 slot still has an initializing, running or draining worker")
        if not (b.SOURCE_GENERATION_ROOT / "closeout/record.json").exists() and not -5 <= time.time() - old["updated_epoch"] <= 60:
            return dict(status="WAIT", reason="legacy generation journal is not fresh")
        return dict(status="READY", source_journal_epoch=journal["updated_epoch"],
                    target_still_same_live_attempt=True, only_target_generation_remains=True)

    def destination_admission(self):
        inventory = {row["index"]: row for row in self.runtime.inventory()}
        row = inventory.get(6)
        if row is None or not physical_destination_gate(row, self.source):
            return None
        host = self.runtime.host_memory()
        if host["available_bytes"] < 512 * GIB:
            return None
        return dict(gpu=row, host=host, minimum_GPU_free_gib=24, required_host_available_gib=512,
            physical_destination_processes_empty=True, original_per_worker_resource_gates_unchanged=True)

    def acquire_destination(self):
        b.require(self.lease is None, "destination lease is acquired only once per prospective handoff")
        admission = self.destination_admission()
        if admission is None:
            return None
        path = Path(self.source["gpu_lease_root"]) / ("gpu-" + b.digest(self.source["gpu_uuids"]["6"]) + ".lock")
        b.require(not path.is_symlink(), "destination secondary lease is aliased")
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = path.open("a")
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            return None
        try:
            fresh = self.destination_admission()
            if fresh is None:
                lease.close()
                return None
            b.require(os.fstat(lease.fileno()).st_ino == path.stat().st_ino,
                      "destination secondary lease inode changed")
            self.lease = lease
            return dict(fresh, lease_path=str(path), lease_inode=path.stat().st_ino,
                        secondary_EX_lease_acquired_before_source_signal=True)
        except BaseException:
            lease.close()
            raise

    def signal_source_once(self, admission):
        b.require(self.lease is not None and not self.source_signal_sent
            and not (self.root / "signal_intent/record.json").exists()
            and not (self.root / "signal/record.json").exists() and not self.cancelled(),
            "source SIGTERM is conditional and single-use")
        ready = self.readiness()
        if ready["status"] != "READY":
            return ready
        fresh = self.destination_admission()
        if fresh is None:
            return dict(status="WAIT", reason="destination resources changed before source stop")
        descriptor = None
        try:
            if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
                descriptor = os.pidfd_open(b.TARGET_PID)
            b.require(alive(b.TARGET_PID, b.TARGET_BIRTH)
                and alive(self.controller["pid"], self.controller["birth"]),
                "source identity changed immediately before the authorized signal")
            sender_birth = identity(os.getpid())
            b.require(sender_birth is not None and os.getuid() == os.geteuid() == b.OWNER_UID,
                      "authorized migration sender identity unavailable")
            intent = b.publish(self.root / "signal_intent/record.json", dict(
                schema="v69_exact_single_target_stop_intent.v1", protocol_id=self.protocol["id"],
                target_pid=b.TARGET_PID, target_birth=b.TARGET_BIRTH, signal=signal.SIGTERM,
                sender_pid=os.getpid(), sender_birth=sender_birth, sender_uid=b.OWNER_UID,
                admission=admission, fresh_destination=fresh, source_readiness=ready,
                created_epoch=time.time(), no_worker_or_controller_other_than_target_authorized=True))
            b.require(not self.cancelled() and alive(b.TARGET_PID, b.TARGET_BIRTH),
                      "cancelled or changed identity before authorized source signal")
            sent_epoch = time.time()
            if descriptor is not None:
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
            else:
                os.kill(b.TARGET_PID, signal.SIGTERM)
            self.source_signal_sent = True
            b.publish(self.root / "signal/record.json", dict(schema="v69_exact_single_target_SIGTERM_sent.v1",
                protocol_id=self.protocol["id"], target_pid=b.TARGET_PID, target_birth=b.TARGET_BIRTH,
                signal=signal.SIGTERM, sender_pid=os.getpid(), sender_birth=sender_birth, sender_uid=b.OWNER_UID,
                sent_epoch=sent_epoch, intent_id=intent["id"], pidfd_used=descriptor is not None,
                actual_kernel_receipt_must_be_verified_before_resume=True, source_SIGKILL_sent=False))
            return dict(status="SOURCE_STOP_REQUESTED")
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def wait_source_settled(self):
        deadline = time.monotonic() + b.STOP_SETTLE_SECONDS
        while time.monotonic() < deadline:
            if self.cancelled():
                return dict(status="STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME")
            accepted = self.target_completed()
            if accepted is not None:
                return dict(status=NO_MIGRATION_STATUS, accepted=accepted)
            actual_path = b.source_attempt_directory() / "actual_exit/record.json"
            journal = b.checked(b.SOURCE_ROOT / "journal/state.json")
            b.require(journal["protocol_id"] == self.source["id"]
                and set(journal["job_states"]) == set(self.plan["jobs"]),
                "source identity changed while waiting for its actual stopped exit")
            if (actual_path.exists() and journal["job_states"][b.TARGET_JOB_ID]["status"] == "HARD_BLOCKED"
                    and not any(row["job_id"] == b.TARGET_JOB_ID for row in journal["active_jobs"])
                    and not alive(b.TARGET_PID, b.TARGET_BIRTH)):
                self.baseline = self.bridge.audit_paused_source(self.root)
                return dict(status="SOURCE_DURABLE_BOUNDARY_VERIFIED")
            self.status("WAITING_SOURCE_ACTUAL_DURABLE_EXIT", source_identity_alive=alive(b.TARGET_PID, b.TARGET_BIRTH))
            time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
        return dict(status="STOPPED_SOURCE_NOT_SETTLED_NO_RETRY", source_identity_alive=alive(b.TARGET_PID, b.TARGET_BIRTH),
                    actual_exit_not_inferred=True, SIGKILL_sent=False)

    def launch_child(self, admission):
        b.require(self.lease is not None and self.baseline is not None and self.child is None and not self.cancelled(),
                  "one new GPU6 child requires the exact durable source audit and held destination lease")
        invocation = self.bridge.worker_invocation(self.root, self.baseline, self.lease.fileno())
        b.require(invocation["gpu_index"] == 6 and invocation["gpu_uuid"] == self.source["gpu_uuids"]["6"],
                  "migration worker cannot use any other destination")
        directory = self.root / "worker"
        directory.mkdir(parents=True, exist_ok=False)
        with (directory / "worker.log").open("xb") as log:
            process = subprocess.Popen(invocation["command"], cwd=b.REPO, env=invocation["environment"],
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(self.lease.fileno(),))
        self.child = SimpleNamespace(process=process, birth=identity(process.pid), directory=directory)
        b.require(self.child.birth is not None or process.poll() is not None,
                  "new live generation child lacks its exact birth identity")
        b.publish(directory / "launch/record.json", dict(schema="v69_actual_single_destination_child_launch.v1",
            protocol_id=self.protocol["id"], job_id=b.TARGET_JOB_ID, pid=process.pid, birth=self.child.birth,
            gpu_index=6, gpu_uuid=self.source["gpu_uuids"]["6"], command=invocation["command"],
            admission=admission, original_attempt_root=str(invocation["attempt_root"]),
            original_frozen_worker_unchanged=True, started_epoch=time.time()))
        self.bridge.publish_launch(self.root, self.baseline, process.pid, self.child.birth,
                                   invocation["command"], admission)

    def signal_own_child_once(self):
        if self.child is None or self.child_signal_sent:
            return
        if alive(self.child.process.pid, self.child.birth):
            try:
                os.kill(self.child.process.pid, signal.SIGTERM)
                self.child_signal_sent = True
                b.publish(self.root / "worker/stop_signal/record.json", dict(protocol_id=self.protocol["id"],
                    pid=self.child.process.pid, birth=self.child.birth, signal=signal.SIGTERM,
                    sent_epoch=time.time(), SIGKILL_sent=False, explicit_stop_no_auto_resume=True))
            except ProcessLookupError:
                pass

    def wait_child(self, *, force_stop=False):
        child = self.child
        b.require(child is not None, "no migration child exists")
        while child.process.poll() is None:
            if force_stop or self.cancelled():
                self.signal_own_child_once()
            self.status("STOPPING_OWN_DESTINATION_WORKER_AT_DURABLE_BOUNDARY"
                if force_stop or self.cancelled() else "RUNNING_MIGRATED_TARGET")
            time.sleep(POLL_SECONDS)
        path = self.root / "worker/actual_exit/record.json"
        if path.exists():
            actual = b.checked(path)
            b.require(actual["protocol_id"] == self.protocol["id"] and actual["job_id"] == b.TARGET_JOB_ID
                and (actual["pid"], actual["birth"], actual["returncode"])
                    == (child.process.pid, child.birth, child.process.returncode)
                and actual["actual_waitpid_observed"] is True,
                "an already observed destination exit cannot be rewritten or replaced")
        else:
            b.publish(path, dict(schema="v69_actual_destination_child_waitpid_exit.v1",
                protocol_id=self.protocol["id"], source_protocol_id=self.source["id"], job_id=b.TARGET_JOB_ID,
                pid=child.process.pid, birth=child.birth, gpu_index=6, attempt=2,
                returncode=child.process.returncode, actual_waitpid_observed=True,
                observed_epoch=time.time(), source_exit_not_rewritten=True))
        try:
            accepted = self.bridge.accept_resumed_target(self.root, self.baseline, b.entry(path))
            return dict(status=COMPLETE_STATUS, accepted=accepted)
        except Exception as error:
            b.publish(self.root / "worker/acceptance_failure/record.json", dict(protocol_id=self.protocol["id"],
                returncode=child.process.returncode, error_type=type(error).__name__, error=str(error), automatic_retry=False))
            return dict(status="STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME" if self.cancelled() else
                "STOPPED_FAILURE_NO_RETRY", actual_returncode=child.process.returncode,
                error_type=type(error).__name__, error=str(error))

    def closeout(self, result):
        b.require(self.child is None or self.child.process.returncode is not None,
                  "migration closeout cannot hide its own live generation child")
        status = result["status"]
        if self.lease is not None:
            self.lease.close()
            self.lease = None
        record = b.publish(self.root / "closeout/record.json", dict(schema="v69_single_target_migration_closeout.v1",
            protocol_id=self.protocol["id"], scientific_protocol_id=b.BASE_PROTOCOL_ID, status=status,
            result=result, source_signal_sent=self.source_signal_sent,
            original_target_alive=alive(b.TARGET_PID, b.TARGET_BIRTH), actual_owned_children_running=0,
            other_workers_or_controllers_signaled=False, SIGKILL_sent=False, automatic_retry=False,
            destination_secondary_lease_released=True,
            old_source_journal_and_failures_unchanged=True, old_control_not_relabelled_COMPLETE=True,
            finished_epoch=time.time()))
        self.status(status, result=result)
        return record

    def run(self):
        with (b.SCIENTIFIC_ROOT / "owner.lock").open("a") as science, (self.root / "owner.lock").open("a") as owner:
            fcntl.flock(science, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            b.require(not (self.root / "coordinator/launch/record.json").exists()
                and not (self.root / "closeout/record.json").exists() and not stop_requested(self.root),
                "the conditional migration entry is single-use; no automatic reopen")
            b.publish(self.root / "coordinator/launch/record.json", dict(schema="v69_conditional_coordinator_launch.v1",
                protocol_id=self.protocol["id"], pid=os.getpid(), birth=identity(os.getpid()), started_epoch=time.time()))
            previous = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)}
            for number in previous:
                signal.signal(number, lambda signum, _frame: self.signals.append(signum))
            try:
                while not self.cancelled():
                    ready = self.readiness()
                    if ready["status"] == NO_MIGRATION_STATUS:
                        return self.closeout(ready)
                    if ready["status"] == "READY":
                        admission = self.acquire_destination()
                        if admission is not None:
                            decision = self.signal_source_once(admission)
                            if decision["status"] == "SOURCE_STOP_REQUESTED":
                                settled = self.wait_source_settled()
                                if settled["status"] != "SOURCE_DURABLE_BOUNDARY_VERIFIED":
                                    return self.closeout(settled)
                                while not self.cancelled():
                                    fresh = self.destination_admission()
                                    if fresh is not None:
                                        self.launch_child(dict(fresh, reserved_lease=admission))
                                        return self.closeout(self.wait_child())
                                    self.status("WAITING_DESTINATION_AFTER_SOURCE_DURABLE_STOP")
                                    time.sleep(POLL_SECONDS)
                                break
                            if decision["status"] == NO_MIGRATION_STATUS:
                                return self.closeout(decision)
                            self.lease.close()
                            self.lease = None
                    self.status("WAITING_GPU6_IDLE_AND_SAFE_SOURCE", source_readiness=ready)
                    time.sleep(POLL_SECONDS)
                return self.closeout(dict(status="STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME",
                    source_may_be_durably_paused=self.source_signal_sent))
            except BaseException as error:
                if self.child is not None and not (self.root / "worker/actual_exit/record.json").exists():
                    # Popen may already have reaped an early-exiting child while
                    # birth/launch publication failed. Still record the actual
                    # code; retain unknown birth as None and never invent zero.
                    self.wait_child(force_stop=self.child.process.poll() is None)
                return self.closeout(dict(status="STOPPED_FAILURE_NO_RETRY", error_type=type(error).__name__, error=str(error)))
            finally:
                if self.lease is not None:
                    self.lease.close()
                    self.lease = None
                for number, handler in previous.items():
                    signal.signal(number, handler)


def _arguments(argv):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--root", type=Path, default=b.ROOT)
    return parser.parse_args(argv)


def _validate_arguments(args):
    root = args.root.resolve()
    b.require(root == b.ROOT.resolve() and Path(__file__).resolve().parent == root / "implementation",
              "migration requires its exact independently frozen entry")
    return root


def exit_status(result, mode):
    return 0 if result.get("status") in (("PASS",) if mode == "check-imports" else
                                        (COMPLETE_STATUS, NO_MIGRATION_STATUS)) else 2


def main(argv=None):
    args = _arguments(sys.argv[1:] if argv is None else argv)
    root = _validate_arguments(args)
    protocol = checked_signal_registration(root)
    observer = install_signal_observer(root, args.mode, protocol)
    try:
        result = check_imports(root) if args.mode == "check-imports" else Migration(root).run()
        print(json.dumps(result if args.mode == "check-imports" else dict(
            schema=result.get("schema"), status=result.get("status"), id=result.get("id")), sort_keys=True))
        return exit_status(result, args.mode)
    finally:
        observer.close()


if __name__ == "__main__":
    raise SystemExit(main())
