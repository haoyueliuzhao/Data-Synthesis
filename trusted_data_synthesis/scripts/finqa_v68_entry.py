"""Frozen CPU-only watcher: score each of six complete groups once as ready.

This entry owns no GPU lease and never signals generation controls. Automatic
continuation means first dispatch after a complete four-job adoption; it does
not mean retrying a failed scoring attempt or reopening an explicit stop.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import finqa_v68_binding as b

MODES = ("check-imports", "run", "score")
POLL_SECONDS = 5
STOP_GRACE_SECONDS = 600
GIB = 1024 ** 3
SEALED_STATUS = "ALL_SIX_GROUPS_SCORED_AWAITING_GLOBAL_ANALYSIS"
_OBSERVER = None


def coordinates():
    return tuple(f"seed{seed}/{arm}" for seed, arm in b.ELIGIBLE_COORDINATES)


def checked_coordinate(value):
    b.require(value in coordinates(), "only the six registered complete model groups may be scored")
    return value


def attempt_directory(root, coordinate):
    return Path(root).resolve() / "attempts" / checked_coordinate(coordinate).replace("/", "_") / "attempt0001"


def signal_api():
    return b.source_module("finqa_v63_signals")


def checked_signal_registration(root, protocol=None):
    b.require(Path(root).resolve() == b.ROOT.resolve(), "foreign partial-scoring signal root")
    protocol = b.checked(Path(root) / "protocol/record.json") if protocol is None else protocol
    science = b.base_protocol()
    signals = signal_api()
    b.require(protocol["scientific_protocol_id"] == science["id"] == b.BASE_PROTOCOL_ID
        and protocol["signal_policy"] == science["signal_policy"] == signals.signals_policy()
        and protocol["signal_source_bindings"] == science["signal_source_bindings"] == signals.external_source_bindings(),
        "partial scoring must retain the original legal-stop filter")
    return protocol


def require_early_install(modules=None):
    allowed = {"finqa_v68_binding.py", "finqa_v68_entry.py", "finqa_v67_binding.py", "finqa_v65_binding.py",
        "finqa_v64_binding.py", "finqa_v63_binding.py", "finqa_v63_signals.py", "finqa_v59_signals.py",
        "finqa_v58_signals.py", "finqa_v58_observer.py"}
    for name, module in (sys.modules if modules is None else modules).items():
        origin = getattr(module, "__file__", None)
        if (name == "torch" or name.startswith("torch.") or name == "trusted_synthesis"
                or name.startswith("trusted_synthesis.")
                or origin and Path(origin).name.startswith("finqa_") and Path(origin).name not in allowed):
            raise RuntimeError("V68 legal-stop observation must precede scientific imports: " + name)


def install_signal_observer(root, args, protocol):
    global _OBSERVER
    b.require(_OBSERVER is None and os.getuid() == os.geteuid() == b.OWNER_UID,
              "one registered nonroot legal-stop observer is required")
    require_early_install()
    directory = (args.attempt_root / "signals" if args.mode == "score" else
                 root / ("coordinator/signals" if args.mode == "run" else "frozen_import_verification/signals"))
    b.require(directory.resolve().is_relative_to(root), "signal evidence escaped V68")
    _OBSERVER = signal_api()._reference().install(directory, role=args.mode, context=dict(
        mode=args.mode, control_root=str(root), protocol_id=protocol["id"],
        scientific_protocol_id=b.BASE_PROTOCOL_ID, group=args.group, CPU_only=True,
        original_signal_policy_unchanged=True))
    return _OBSERVER


def assert_cpu_only():
    b.require(os.environ.get("CUDA_VISIBLE_DEVICES") == "" and "V54_GPU_LEASE_FD" not in os.environ,
              "CPU scoring must hide CUDA and cannot inherit a GPU lease")
    torch = sys.modules.get("torch")
    b.require(torch is None or not torch.cuda.is_initialized(), "CPU scoring cannot initialize CUDA")


def runtime_api():
    b.install_scientific_paths()
    b.source_module("finqa_v63_entry").install_registered_auxiliary()
    return b.source_module("finqa_v63_runtime").controller_runtime()


def verify_imported_modules(root, implementation, *, modules=None):
    root = Path(root).resolve()
    b.require(root == b.ROOT.resolve(), "foreign scoring dependency root")
    previous, additions = {}, []
    for name, module in sorted((sys.modules if modules is None else modules).items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        if path.name.startswith("finqa_v68_") or name.startswith("finqa_v68_"):
            b.require(path.parent == root / "implementation" and path.name in implementation["sha256"],
                      "workspace or unregistered V68 dependency")
            actual = b.sha(path)
            b.require(actual == implementation["sha256"][path.name], "frozen V68 source bytes changed")
            additions.append(dict(module=name, path=str(path), sha256=actual, origin="frozen_CPU_scoring_only"))
        else:
            previous[name] = module
    parent = b.completion_module("finqa_v67_entry")
    parent_root = Path(parent.__file__).resolve().parent.parent
    inherited = parent.verify_imported_modules(parent_root, b.checked(parent_root / "implementation/record.json"),
                                               modules=previous)
    verified = inherited["verified_dependencies"] + additions
    return dict(verified_dependencies=verified, verified_dependency_count=len(verified),
        verified_dependencies_digest=b.digest(verified), new_scoring_sources=additions,
        parent_frozen_closure_verified=True)


def check_imports(root):
    registration = importlib.import_module("finqa_v68_registration")
    protocol = registration.checked_protocol(root)
    checked_signal_registration(root, protocol)
    implementation = registration.checked_implementation(root)
    registration.modules()
    runtime_api()
    native = importlib.import_module("finqa_v68_scoring")._runtime()
    old_plan = b.checked(b.SOURCE_GENERATION_ROOT / "evaluations/registration/record.json")
    b.require(native.runtime_binding() == old_plan["runtime_binding"],
              "actual frozen native scorer/storage dependencies changed")
    assert_cpu_only()
    dependencies = verify_imported_modules(root, implementation)
    body = dict(schema="v68_actual_frozen_CPU_only_import_check.v1", status="PASS",
        protocol_id=protocol["id"], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        implementation_id=implementation["id"], CUDA_initialized=False, model_loaded=False,
        provider_calls=0, native_scoring_calls=0, private_references_read=False,
        **dependencies)
    return dict(body, id=b.digest(body))


def _status(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = dict(value, id=b.digest(value))
    fd, temporary = tempfile.mkstemp(prefix=".v68-status-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def stop_requested(root):
    return (Path(root) / "control/stop_requested/record.json").exists()


def same_live_identity(runtime, pid, birth):
    value = runtime.birth(pid)
    return value is not None and value == birth


class ScoringStopped(RuntimeError):
    pass


@contextmanager
def worker_stop_guard():
    def stop(signum, _frame):
        raise ScoringStopped(f"legal signal {signum} stopped this scoring worker")
    previous = {number: signal.signal(number, stop) for number in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def score_worker(root, coordinate, attempt, protocol):
    root, attempt = Path(root).resolve(), Path(attempt).resolve()
    b.require(attempt == attempt_directory(root, coordinate), "foreign CPU scoring attempt")
    assert_cpu_only()
    runtime = runtime_api()
    observations = []

    def check(label="native_score_boundary"):
        assert_cpu_only()
        if stop_requested(root):
            raise ScoringStopped("explicit CPU scoring stop marker")
        host, memory = runtime.host_memory(), runtime.process_memory(os.getpid())
        b.require(memory is not None and memory["peak_rss_bytes"] <= b.CPU_RSS_LIMIT_GIB * GIB
            and host["available_bytes"] >= b.HOST_RESERVE_GIB * GIB,
            "CPU scoring RSS or effective host-memory gate failed")
        observations.append(dict(label=str(label), epoch=time.time(), rss_bytes=memory["rss_bytes"],
            peak_rss_bytes=memory["peak_rss_bytes"], host_available_bytes=host["available_bytes"]))

    with worker_stop_guard(), (attempt / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        b.require(not (attempt / "completed/record.json").exists() and not (attempt / "failure/record.json").exists(),
                  "a scoring attempt cannot be executed twice")
        try:
            # A real child waits until its parent has durably published launch
            # identity. Parent death produces EOF, never permission to score.
            launch_fd = int(os.environ["V68_LAUNCH_READY_FD"])
            try:
                ready = os.read(launch_fd, 1)
            finally:
                os.close(launch_fd)
            b.require(ready == b"1", "parent did not commit the scoring launch")
            launch = b.checked(attempt / "launch/record.json")
            b.require(launch["protocol_id"] == protocol["id"] and launch["coordinate"] == coordinate
                and launch["pid"] == os.getpid() and launch["birth"] == runtime.birth(os.getpid())
                and launch["CUDA_VISIBLE_DEVICES"] == "" and launch["GPU_worker"] is False,
                "CPU scoring launch identity changed")
            b.require(not (root / "groups" / coordinate / "result/record.json").exists(),
                      "an already scored group cannot receive another attempt")
            check("before_private_scoring")
            scored = importlib.import_module("finqa_v68_scoring").score_group(root, coordinate,
                protocol=protocol, check=check)
            check("after_private_scoring")
            result, reference = scored["result"], scored["result_ref"]
            b.require(result["coordinate"] == coordinate and result["protocol_id"] == protocol["id"]
                and result["sessions"] == 1243 and result["scoring_execution_complete"] is True
                and result["native_scores_present"] == scored["new_native_scoring_calls"] == 1243,
                "one first scoring execution must cover exactly the original complete group")
            resources = b.publish(attempt / "resource_closeout/record.json", dict(
                schema="v68_CPU_scoring_resource_closeout.v1", status="COMPLETE",
                protocol_id=protocol["id"], coordinate=coordinate, pid=os.getpid(),
                all_gates_passed=True, cpu_rss_limit_gib=b.CPU_RSS_LIMIT_GIB,
                host_reserve_gib=b.HOST_RESERVE_GIB, CUDA_initialized=False, provider_calls=0,
                peak_rss_bytes=max(row["peak_rss_bytes"] for row in observations),
                minimum_host_available_bytes=min(row["host_available_bytes"] for row in observations),
                observations=observations))
            return b.publish(attempt / "completed/record.json", dict(
                schema="v68_first_group_scoring_worker_completed.v1", status="COMPLETE",
                protocol_id=protocol["id"], coordinate=coordinate, group_result=reference,
                group_result_id=result["id"], new_native_scoring_calls=scored["new_native_scoring_calls"],
                resource_closeout=b.entry(attempt / "resource_closeout/record.json"),
                resource_closeout_id=resources["id"], provider_calls=0, GPU_worker=False,
                unknown_preserved_not_converted_to_zero=True, global_analysis_computed=False))
        except BaseException as error:
            b.publish(attempt / "failure/record.json", dict(schema="v68_CPU_scoring_attempt_failure.v1",
                protocol_id=protocol["id"], coordinate=coordinate, pid=os.getpid(),
                error_type=type(error).__name__, error=str(error), automatic_retry=False,
                complete_group_not_resampled=True, previous_observations=observations))
            raise


class ScoringQueue:
    def __init__(self, root, *, runtime=None, registration=None):
        self.root = Path(root).resolve()
        b.require(self.root == b.ROOT.resolve(), "foreign scoring queue root")
        self.registration = registration or importlib.import_module("finqa_v68_registration")
        self.protocol = self.registration.checked_protocol(self.root)
        self.registration.checked_implementation(self.root)
        self.prepared = self.registration.checked_prepared(self.root)
        b.require(self.protocol["max_cpu_workers"] == b.MAX_CPU_WORKERS == 2
            and self.protocol["cpu_rss_limit_gib"] == b.CPU_RSS_LIMIT_GIB == 32
            and self.protocol["host_reserve_gib"] == b.HOST_RESERVE_GIB == 96
            and self.protocol["other_scopes_startup_gib"] == b.OTHER_SCOPES_STARTUP_GIB == 352
            and set(self.protocol["allowed_groups"]) == set(coordinates()) and len(coordinates()) == 6,
            "fixed six-group automatic CPU scoring and resources cannot expand")
        self.runtime = runtime or runtime_api()
        self.states = {key: dict(status="WAITING_COMPLETE_GROUP") for key in coordinates()}
        self.active, self.accepted, self.eligibility = {}, {}, {}
        self.explicit_stop, self.signals = False, []

    def journal(self, status):
        _status(self.root / "queue/status.json", dict(schema="v68_complete_group_auto_scoring_queue.v1",
            protocol_id=self.protocol["id"], scientific_protocol_id=b.BASE_PROTOCOL_ID,
            status=status, updated_epoch=time.time(), max_cpu_workers=2, GPU_workers=0,
            active_workers=[dict(coordinate=key, pid=child.process.pid, birth=child.birth,
                attempt_root=str(child.directory), lifecycle=child.lifecycle) for key, child in self.active.items()],
            group_states=self.states, accepted_groups=self.accepted, eligible_groups=self.eligibility,
            auto_continue_only_after_complete_group=True, automatic_failed_attempt_retry=False,
            global_analysis_computed=False))

    def discover(self):
        value = importlib.import_module("finqa_v68_adoption").read_ready_groups(
            self.root, skip_coordinates=tuple(self.eligibility))
        b.require(set(value["ready_groups"]) <= set(self.states), "discovery expanded the six-group scope")
        for coordinate, group in value["ready_groups"].items():
            b.require(coordinate not in self.eligibility and group["sessions"] == 1243,
                      "group eligibility cannot be reset or use a partial denominator")
            path = b.eligibility_path(coordinate)
            b.publish(path, group)
            self.eligibility[coordinate] = b.entry(path)
            self.states[coordinate] = dict(status="READY", eligibility=self.eligibility[coordinate])

    def admission(self):
        b.require(len(self.active) <= b.MAX_CPU_WORKERS, "CPU scoring concurrency exceeded")
        if len(self.active) == b.MAX_CPU_WORKERS:
            return None
        # Full reservation for both CPU scorers, all six generation startup
        # budgets and V67's one possible repair child. Never credit low RSS.
        required = (b.HOST_RESERVE_GIB + b.OTHER_SCOPES_STARTUP_GIB
                    + b.MAX_CPU_WORKERS * b.CPU_RSS_LIMIT_GIB) * GIB
        host = self.runtime.host_memory()
        if host["available_bytes"] < required:
            return None
        return dict(required_bytes=required, observed_host=host, CPU_worker_budget_gib=32,
            reserved_scoring_worker_count=2, other_scopes_reserved_gib=352,
            host_reserve_gib=96, other_worker_actual_RSS_not_deducted=True, GPU_requested=False)

    def launch(self, coordinate, admission):
        b.require(len(self.active) < 2 and self.states[coordinate]["status"] == "READY",
                  "only an unstarted ready group may receive one CPU attempt")
        directory = attempt_directory(self.root, coordinate)
        b.require(not directory.exists(), "scoring attempt is immutable; automatic retry is forbidden")
        b.publish(directory / "dispatch_intent/record.json", dict(
            schema="v68_first_complete_group_CPU_dispatch.v1", protocol_id=self.protocol["id"],
            coordinate=coordinate, eligibility=self.eligibility[coordinate], attempt=1,
            admission=admission, created_epoch=time.time(), GPU_worker=False))
        self.states[coordinate] = dict(status="DISPATCHING", attempt=1, directory=str(directory))
        self.journal("DISPATCHING")
        command = [str(b.PYTHON), "-u", str(self.root / "implementation/finqa_v68_entry.py"),
            "--mode", "score", "--root", str(self.root), "--group", coordinate,
            "--attempt-root", str(directory)]
        reader, writer = os.pipe()
        environment = dict(os.environ, CUDA_VISIBLE_DEVICES="", V68_ROOT=str(self.root),
            V68_PROTOCOL_ID=self.protocol["id"], V68_GROUP=coordinate, V68_ATTEMPT_ROOT=str(directory),
            V68_LAUNCH_READY_FD=str(reader), PYTHONPATH=str(self.root / "implementation"))
        environment.pop("V54_GPU_LEASE_FD", None)
        process = None
        try:
            with (directory / "worker.log").open("xb") as log:
                process = subprocess.Popen(command, cwd=b.REPO, env=environment, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(reader,))
            os.close(reader)
            reader = None
            child = SimpleNamespace(process=process, birth=self.runtime.birth(process.pid),
                directory=directory, lifecycle="INITIALIZING", resource_failure=None)
            self.active[coordinate] = child
            b.require(isinstance(child.birth, str) and child.birth.isdigit(),
                      "actual CPU child needs a birth identity before launch permission")
            b.publish(directory / "launch/record.json", dict(schema="v68_actual_CPU_scoring_launch.v1",
                protocol_id=self.protocol["id"], coordinate=coordinate, attempt=1, pid=process.pid,
                birth=child.birth, command=command, admission=admission, CUDA_VISIBLE_DEVICES="",
                GPU_worker=False, eligibility=self.eligibility[coordinate], started_epoch=time.time()))
            self.states[coordinate] = dict(status="RUNNING", attempt=1, pid=process.pid, birth=child.birth)
            self.journal("RUNNING")
            os.write(writer, b"1")
        except BaseException as error:
            if process is None:
                b.publish(directory / "launch_failure/record.json", dict(protocol_id=self.protocol["id"],
                    coordinate=coordinate, actual_child_created=False, error_type=type(error).__name__,
                    error=str(error), automatic_retry=False))
                self.states[coordinate] = dict(status="HARD_BLOCKED", reason="CPU child was not launched", error=str(error))
            else:
                raise
        finally:
            if reader is not None:
                os.close(reader)
            os.close(writer)

    def signal_child(self, child, signum):
        if same_live_identity(self.runtime, child.process.pid, child.birth):
            try:
                os.kill(child.process.pid, signum)
            except ProcessLookupError:
                pass

    def accept(self, coordinate, child):
        completed = b.checked(child.directory / "completed/record.json")
        resource_ref = completed["resource_closeout"]
        resources = b.read_ref(resource_ref)
        result = b.read_ref(completed["group_result"])
        actual = b.checked(child.directory / "actual_exit/record.json")
        launch = b.checked(child.directory / "launch/record.json")
        b.require(completed["status"] == resources["status"] == "COMPLETE"
            and completed["protocol_id"] == resources["protocol_id"] == result["protocol_id"] == self.protocol["id"]
            and completed["coordinate"] == resources["coordinate"] == result["coordinate"] == coordinate
            and completed["group_result_id"] == result["id"]
            and result["eligibility"] == self.eligibility[coordinate] == launch["eligibility"]
            and result["scoring_execution_complete"] is True and result["sessions"] == 1243
            and result["native_scores_present"] == completed["new_native_scoring_calls"] == 1243
            and actual["protocol_id"] == launch["protocol_id"] == self.protocol["id"]
            and actual["coordinate"] == launch["coordinate"] == coordinate
            and type(actual["returncode"]) is int and actual["returncode"] == 0
            and actual["actual_waitpid_observed"] is True
            and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"]) == (child.process.pid, child.birth)
            and resources["all_gates_passed"] is True and resources["CUDA_initialized"] is False
            and resources["peak_rss_bytes"] <= 32 * GIB and resources["minimum_host_available_bytes"] >= 96 * GIB
            and resources["pid"] == child.process.pid
            and Path(resource_ref["path"]).resolve() == child.directory / "resource_closeout/record.json"
            and Path(completed["group_result"]["path"]).resolve() == self.root / "groups" / coordinate / "result/record.json"
            and child.resource_failure is None,
            "group scoring acceptance needs exact result, full denominator, resources and actual exit zero")
        path = self.root / "groups" / coordinate / "accepted/record.json"
        b.publish(path, dict(schema="v68_actual_complete_group_score_accepted.v1",
            protocol_id=self.protocol["id"], coordinate=coordinate, group_result=completed["group_result"],
            group_result_id=result["id"], actual_exit=b.entry(child.directory / "actual_exit/record.json"),
            worker_completed=b.entry(child.directory / "completed/record.json"), resource_closeout=resource_ref,
            actual_exit_zero=True, complete_original_sessions=1243, resources_passed=True,
            UNKNOWN_not_asserted_known=True, original_generation_control_unmodified=True))
        self.accepted[coordinate] = b.entry(path)
        self.states[coordinate] = dict(status="COMPLETE", attempt=1, accepted=self.accepted[coordinate])

    def reap(self):
        for coordinate, child in list(self.active.items()):
            code = child.process.poll()  # Actual parent waitpid, not a disappeared-PID inference.
            if code is None:
                child.lifecycle = "DRAINING" if (child.directory / "completed/record.json").exists() else "RUNNING"
                try:
                    memory, host = self.runtime.process_memory(child.process.pid), self.runtime.host_memory()
                except (FileNotFoundError, ProcessLookupError):
                    continue
                if memory is not None and (memory["peak_rss_bytes"] > 32 * GIB or host["available_bytes"] < 96 * GIB):
                    child.resource_failure = dict(memory=memory, host=host)
                    self.signal_child(child, signal.SIGTERM)
                continue
            b.publish(child.directory / "actual_exit/record.json", dict(schema="v68_actual_CPU_scoring_exit.v1",
                protocol_id=self.protocol["id"], coordinate=coordinate, attempt=1, pid=child.process.pid,
                birth=child.birth, returncode=code, actual_waitpid_observed=True,
                resource_failure=child.resource_failure, observed_epoch=time.time(), GPU_worker=False))
            try:
                b.require(code == 0, "CPU scoring attempt did not exit successfully; no automatic retry")
                self.accept(coordinate, child)
            except Exception as error:
                self.states[coordinate] = dict(status="HARD_BLOCKED", attempt=1,
                    error_type=type(error).__name__, error=str(error), automatic_retry=False)
                b.publish(child.directory / "acceptance_failure/record.json", dict(protocol_id=self.protocol["id"],
                    coordinate=coordinate, actual_returncode=code, error_type=type(error).__name__,
                    error=str(error), automatic_retry=False))
            finally:
                del self.active[coordinate]

    def closeout(self, status, *, error=None):
        b.require(not self.active, "scoring closeout cannot conceal a live child")
        self.journal(status)
        return b.publish(self.root / "closeout/record.json", dict(schema="v68_CPU_auto_scoring_closeout.v1",
            status=status, protocol_id=self.protocol["id"], scientific_protocol_id=b.BASE_PROTOCOL_ID,
            accepted_groups=self.accepted, group_states=self.states, active_workers=0,
            total_registered_groups=6, accepted_native_scores=1243 * len(self.accepted),
            global_analysis_computed=False, global_scientific_experiment_complete=False,
            automatic_retry=False, automatic_future_scope_expansion=False,
            generation_controls_signaled=False, error=error, finished_epoch=time.time()))

    def stop(self, reason, *, status="STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME"):
        self.explicit_stop = True
        marker = self.root / "control/stop_requested/record.json"
        if not marker.exists():
            b.publish(marker, dict(schema="v68_scoring_stop_no_auto_resume.v1", protocol_id=self.protocol["id"],
                reason=reason, at_epoch=time.time(), automatic_restart_allowed=False))
        deadline = time.monotonic() + STOP_GRACE_SECONDS
        for child in self.active.values():
            self.signal_child(child, signal.SIGTERM)
        while self.active and time.monotonic() < deadline:
            self.reap()
            self.journal("STOPPING_OWN_CPU_WORKERS")
            if self.active:
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
        for child in self.active.values():
            self.signal_child(child, signal.SIGKILL)
        while self.active:
            self.reap()
            if self.active:
                time.sleep(0.2)
        return self.closeout(status, error=reason)

    def run(self):
        assert_cpu_only()
        with (b.SCIENTIFIC_ROOT / "owner.lock").open("a") as science, (self.root / "owner.lock").open("a") as owner:
            fcntl.flock(science, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            launch_path = self.root / "coordinator/launch/record.json"
            b.require(not launch_path.exists() and not (self.root / "closeout/record.json").exists()
                and not stop_requested(self.root), "the one-shot scoring watcher cannot be automatically reopened")
            b.publish(launch_path, dict(schema="v68_CPU_scoring_watcher_launch.v1",
                protocol_id=self.protocol["id"], pid=os.getpid(), birth=self.runtime.birth(os.getpid()),
                allowed_groups=list(coordinates()), started_epoch=time.time(), GPU_worker=False))
            previous = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)}
            for number in previous:
                signal.signal(number, lambda signum, _frame: self.signals.append(signum))
            try:
                while True:
                    if self.signals or stop_requested(self.root):
                        return self.stop(dict(signals=self.signals, marker=stop_requested(self.root)))
                    self.reap()
                    if len(self.accepted) == 6 and not self.active:
                        return self.closeout(SEALED_STATUS)
                    self.discover()
                    for coordinate, state in self.states.items():
                        if self.signals or stop_requested(self.root) or len(self.active) == 2:
                            break
                        if state["status"] != "READY":
                            continue
                        admission = self.admission()
                        if admission is None:
                            break
                        self.launch(coordinate, admission)
                    if not self.active and all(s["status"] in ("COMPLETE", "HARD_BLOCKED") for s in self.states.values()):
                        return self.closeout("BLOCKED_OPERATOR_REQUIRED")
                    blocked = any(s["status"] == "HARD_BLOCKED" for s in self.states.values())
                    self.journal("RUNNING_WITH_BLOCKED_GROUPS" if blocked else "RUNNING" if self.active
                        else "WAITING_RESOURCES" if any(s["status"] == "READY" for s in self.states.values())
                        else "WAITING_COMPLETE_GROUPS")
                    time.sleep(POLL_SECONDS)
            except BaseException as error:
                return self.stop(dict(error_type=type(error).__name__, error=str(error)),
                                 status="BLOCKED_OPERATOR_REQUIRED")
            finally:
                for number, handler in previous.items():
                    signal.signal(number, handler)


def _arguments(argv):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--root", type=Path, default=b.ROOT)
    parser.add_argument("--group")
    parser.add_argument("--attempt-root", type=Path)
    return parser.parse_args(argv)


def _validate_arguments(args):
    root = args.root.resolve()
    b.require(root == b.ROOT.resolve() and Path(__file__).resolve().parent == root / "implementation",
              "V68 must run from its own registered frozen implementation")
    assert_cpu_only()
    if args.mode == "score":
        checked_coordinate(args.group)
        b.require(args.attempt_root is not None and not args.attempt_root.is_symlink()
            and args.attempt_root.resolve() == attempt_directory(root, args.group)
            and os.environ.get("V68_ROOT") == str(root) and os.environ.get("V68_GROUP") == args.group
            and os.environ.get("V68_ATTEMPT_ROOT") == str(args.attempt_root.resolve())
            and os.environ.get("V68_LAUNCH_READY_FD", "").isdigit(),
            "CPU scoring group, first attempt or launch pipe escaped its registration")
    else:
        b.require(args.group is None and args.attempt_root is None, "only score children may name a group attempt")
    return root


def _dispatch(root, args):
    if args.mode == "check-imports":
        return check_imports(root)
    registration = importlib.import_module("finqa_v68_registration")
    protocol = registration.checked_protocol(root)
    registration.checked_implementation(root)
    registration.modules()
    if args.mode == "run":
        return ScoringQueue(root, registration=registration).run()
    b.require(os.environ.get("V68_PROTOCOL_ID") == protocol["id"], "CPU scoring launch protocol changed")
    return score_worker(root, args.group, args.attempt_root, protocol)


def exit_status(result, mode):
    return 0 if result.get("status") == ("PASS" if mode == "check-imports" else
        "COMPLETE" if mode == "score" else SEALED_STATUS) else 2


def main(argv=None):
    args = _arguments(sys.argv[1:] if argv is None else argv)
    root = _validate_arguments(args)
    protocol = checked_signal_registration(root)
    observer = install_signal_observer(root, args, protocol)
    try:
        result = _dispatch(root, args)
        print(json.dumps(result if args.mode == "check-imports" else dict(
            id=result.get("id"), schema=result.get("schema"), status=result.get("status")), sort_keys=True))
        return exit_status(result, args.mode)
    finally:
        observer.close()


if __name__ == "__main__":
    raise SystemExit(main())
