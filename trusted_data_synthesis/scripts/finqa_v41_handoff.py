"""One bounded V40 resource-policy handoff, without scientific worker signals.

The default barrier takes all eight original GPU locks or immediately releases
every lock. The explicitly registered alternative drains naturally, but releases
every barrier lock whenever an already-started class has undispatched shards.
Neither mode edits V40, launches a second scientific pool, retries science, or
extends any registered compute, phase or resource-wait budget.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import math
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

GPUS = tuple(range(8))
SHARDS = tuple(f"shard{index:02d}" for index in range(4))
MODES = ("passive_all_or_none", "class_aware_natural_drain")
PAUSED = "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME"
LIVE_PHASES = {"RUNNING", "WAITING_FOR_REGISTERED_RESOURCES", "WAITING_FOR_PRE_CUDA_RESOURCES"}
SCHEMA = "v41_nonstarving_resource_policy_handoff.v1"
SOURCE_ROOT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/"
    "v25_training_replication_01"
)
PARENT_ROOT = SOURCE_ROOT / "production_resume_01/recovery_02"
HANDOFF_ROOT = PARENT_ROOT / "controlled_admission_handoff_01"
TRAINING_ROOT = SOURCE_ROOT / "training_replication"


class HandoffError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise HandoffError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def epoch(value):
    result = datetime.fromisoformat(value).timestamp()
    require(math.isfinite(result), "non-finite timestamp")
    return result


def read(path):
    return json.loads(Path(path).read_bytes())


def checked(path):
    value = read(path)
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "immutable record changed: " + str(path),
    )
    return value


def ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def check_ref(value):
    require(
        isinstance(value, dict) and set(value) in ({"path", "sha256"}, {"path", "sha256", "id"}),
        "record reference requires exactly path/sha256 and optional content id",
    )
    expected = {key: value[key] for key in ("path", "sha256")}
    require(ref(value["path"]) == expected, "record reference changed: " + value["path"])
    record = checked(value["path"])
    require("id" not in value or value["id"] == record["id"], "record reference content id changed")
    return record


def record_file_ref(value):
    """Normalize only after checking both the file digest and optional record ID."""
    check_ref(value)
    return {key: value[key] for key in ("path", "sha256")}


def publish(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require("id" not in body, "record must not provide its own id")
    value = {**body, "id": digest(body)}
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return value


def status(root, body):
    path = Path(root) / "status.json"
    temporary = path.with_name(f"status.{os.getpid()}.tmp")
    with temporary.open("w") as stream:
        json.dump(body, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def process_identity(pid):
    try:
        directory = Path("/proc") / str(int(pid))
        fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        argv = [part.decode() for part in (directory / "cmdline").read_bytes().split(b"\0") if part]
        return dict(pid=int(pid), birth=fields[19], uid=directory.stat().st_uid, argv=argv)
    except (FileNotFoundError, ProcessLookupError):
        return None


def assert_controller_identity(expected, identity=process_identity):
    require(identity(expected["pid"]) == expected, "controller PID/birth/UID/argv changed")


def open_pidfd(pid):
    """Open a process handle; never degrade to signalling an unbound PID.

    Some Python builds omit os.pidfd_open despite local libc/kernel support.
    The local sys/pidfd.h ABI is int pidfd_open(pid_t, unsigned int), with
    signed 32-bit pid_t and flags zero. No architecture-specific syscall number
    is guessed, and native-open errors are not retried through another path.
    """
    require(type(pid) is int and 0 < pid <= 2**31 - 1, "positive signed pid_t required")
    native = getattr(os, "pidfd_open", None)
    if callable(native):
        return native(pid, 0)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        exported = libc.pidfd_open
    except (AttributeError, OSError) as error:
        raise HandoffError("pidfd_open unavailable; no unsafe PID-only fallback") from error
    exported.argtypes = (ctypes.c_int, ctypes.c_uint)
    exported.restype = ctypes.c_int
    ctypes.set_errno(0)
    descriptor = exported(pid, 0)
    if descriptor < 0:
        code = ctypes.get_errno() or errno.EIO
        raise OSError(code, os.strerror(code))
    return descriptor


def verify_pidfd_capability():
    """No-signal preflight: open and close only this process's own handle."""
    require(
        callable(getattr(signal, "pidfd_send_signal", None)),
        "pidfd signalling required; no unsafe PID-only fallback",
    )
    descriptor = open_pidfd(os.getpid())
    try:
        require(type(descriptor) is int and descriptor >= 0, "invalid pidfd descriptor")
    finally:
        os.close(descriptor)
    return dict(
        open_backend="os.pidfd_open"
        if callable(getattr(os, "pidfd_open", None))
        else "libc.pidfd_open",
        pidfd_sender_available=True,
        own_process_handle_opened_and_closed=True,
        signals_sent=0,
        pid_only_fallback=False,
    )


def signal_controller(expected):
    require(
        callable(getattr(signal, "pidfd_send_signal", None)),
        "pidfd signalling required; no unsafe PID-only fallback",
    )
    descriptor = open_pidfd(expected["pid"])
    try:
        assert_controller_identity(expected)
        signal.pidfd_send_signal(descriptor, signal.SIGTERM)
    finally:
        os.close(descriptor)


def lock_path(training_root, uuid):
    return Path(training_root) / "locks" / ("gpu-" + digest(uuid) + ".lock")


class Barrier:
    def __init__(self, training_root, gpu_uuids):
        self.paths = {int(gpu): lock_path(training_root, uuid) for gpu, uuid in gpu_uuids.items()}
        require(tuple(sorted(self.paths)) == GPUS, "barrier must cover all eight V40 GPUs")
        self.held = {}

    def acquire_available(self):
        acquired = []
        for gpu in GPUS:
            if gpu in self.held:
                continue
            path = self.paths[gpu]
            require(path.parent.is_dir(), "original GPU lock directory missing")
            descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(descriptor)
                continue
            except BaseException:
                os.close(descriptor)
                raise
            self.held[gpu] = descriptor
            acquired.append(gpu)
        return acquired

    def acquire_all_or_none(self):
        self.acquire_available()
        if not self.complete:
            self.close()
            return False
        return True

    @property
    def complete(self):
        return tuple(sorted(self.held)) == GPUS

    def close(self):
        for descriptor in self.held.values():
            os.close(descriptor)
        self.held.clear()


def launches(parent_root):
    root = Path(parent_root)
    return sorted(
        [
            *root.glob("contexts/*/*/*/*/launch/record.json"),
            *root.glob("evaluations/*/*/launch/record.json"),
        ]
    )


def stage_key(value):
    return (value["context_id"], value["stage"], value["pid"], str(value["birth"]))


def queue_snapshot(parent_root, protocol_id):
    value = read(Path(parent_root) / "queue/status.json")
    require(value.get("protocol_id") == protocol_id, "parent queue protocol changed")
    require(isinstance(value.get("active_children"), list), "parent active list missing")
    wait = value.get("global_external_resource_wait_seconds")
    require(
        isinstance(wait, (int, float))
        and not isinstance(wait, bool)
        and math.isfinite(wait)
        and wait >= 0,
        "parent resource budget unknown",
    )
    return value


def deadline_bound(queue, active_launches, now, resource_wait_budget, grace_seconds=600):
    remaining = resource_wait_budget - queue["global_external_resource_wait_seconds"]
    require(remaining > 0, "parent resource wait budget exhausted")
    deadlines = [float(value["deadline_epoch"]) for value in active_launches]
    require(
        all(math.isfinite(value) and value > now for value in deadlines),
        "an active parent stage deadline already expired",
    )
    return min(max([now, *deadlines]) + grace_seconds, now + remaining)


def validate_stage(path, launch, protocol_id, identity=process_identity):
    directory = Path(path).parent.parent
    require(not (directory / "failure/record.json").exists(), "observed stage recorded failure")
    result_path, exit_path = directory / "result/record.json", directory / "exit/record.json"
    if not result_path.exists() or not exit_path.exists():
        return None
    result, exited = checked(result_path), checked(exit_path)
    for value in (launch, result, exited):
        require(
            value.get("protocol_id") == protocol_id
            and value.get("context_id") == launch["context_id"]
            and value.get("stage") == launch["stage"],
            "stage protocol/context binding changed",
        )
    require(result.get("status") == "COMPLETE", "stage did not complete")
    require(
        exited.get("returncode") == 0 and exited.get("stop_requested") is False,
        "stage did not naturally exit with code zero",
    )
    require(
        result.get("gpu_uuid") == launch["gpu_uuid"]
        and result.get("gpu_index") == launch["gpu_index"],
        "stage GPU identity changed",
    )
    require(
        result.get("resources", {}).get("all_gates_passed") is True,
        "stage resource gates did not pass",
    )
    actual = identity(launch["pid"])
    require(
        actual is None or actual["birth"] != str(launch["birth"]),
        "stage exit record exists but original worker is still alive",
    )
    return dict(launch=ref(path), result=ref(result_path), exit=ref(exit_path))


def inherited_class_shards(parent_root, protocol, identity=process_identity):
    """Read V40's sealed completed-shard aliases, including C251's parent shard02."""
    parent_root = Path(parent_root).resolve()
    inheritance_ref = protocol.get("inheritance")
    require(
        isinstance(inheritance_ref, dict)
        and Path(inheritance_ref["path"]) == parent_root / "inheritance/record.json",
        "parent sealed inheritance reference missing",
    )
    inherited = check_ref(inheritance_ref)
    result = {}
    for item in inherited["context_inheritances"]:
        directory = Path(item["new_context_directory"])
        require(
            directory.is_relative_to(parent_root / "contexts") and directory == directory.resolve(),
            "inherited context outside parent",
        )
        context = check_ref(item["original_context"])
        stages = {}
        for stage, binding in item["stage_bindings"].items():
            if stage not in SHARDS or binding.get("protocol_scope") != "parent":
                continue
            launch = check_ref(binding["launch"])
            require(
                launch["context_id"] == context["id"]
                and launch["stage"] == stage
                and launch["protocol_id"] == binding["protocol_id"],
                "inherited class launch binding changed",
            )
            evidence = validate_stage(
                binding["launch"]["path"], launch, binding["protocol_id"], identity
            )
            require(
                evidence is not None
                and evidence["result"] == record_file_ref(binding["result"])
                and evidence["exit"] == record_file_ref(binding["exit"]),
                "inherited class shard lacks actual complete zero exit",
            )
            stages[stage] = evidence
        require(str(directory) not in result, "duplicate inherited context")
        result[str(directory)] = stages
    return result


def class_frontiers(parent_root, inherited):
    """Metadata only; an inherited complete shard counts as already dispatched."""
    directories = {
        str(path.resolve())
        for path in (Path(parent_root) / "contexts").glob("*/*/*")
        if path.is_dir()
    } | set(inherited)
    rows = []
    for name in sorted(directories):
        existing = inherited.get(name, {})
        local = {
            stage: Path(name) / stage / "launch/record.json"
            for stage in SHARDS
            if (Path(name) / stage / "launch/record.json").exists()
        }
        require(not set(existing) & set(local), "inherited completed class shard dispatched again")
        dispatched = set(existing) | set(local)
        if dispatched:
            rows.append(
                dict(
                    directory=name,
                    inherited_shards=sorted(existing),
                    local_launches={key: ref(path) for key, path in local.items()},
                    dispatched_shards=sorted(dispatched),
                    undispatched_shards=sorted(set(SHARDS) - dispatched),
                )
            )
    return rows


def validate_complete_class_boundaries(
    parent_root, protocol_id, inherited, identity=process_identity
):
    evidence = []
    for row in class_frontiers(parent_root, inherited):
        require(not row["undispatched_shards"], "partial class context cannot migrate")
        shards = dict(inherited.get(row["directory"], {}))
        for stage, reference in row["local_launches"].items():
            value = validate_stage(reference["path"], check_ref(reference), protocol_id, identity)
            require(value is not None, "class context has an unsealed shard")
            shards[stage] = value
        require(set(shards) == set(SHARDS), "complete four-shard boundary required")
        evidence.append(dict(directory=row["directory"], shards=shards))
    return evidence


def register(
    root,
    *,
    parent_root,
    training_root,
    authorization,
    source_commit,
    mode=MODES[0],
    expected_controller=None,
    deadline_epoch=None,
    now=None,
    identity=process_identity,
    freeze=True,
):
    root, parent_root, training_root = map(
        lambda value: Path(value).resolve(), (root, parent_root, training_root)
    )
    now = time.time() if now is None else now
    require(not root.exists(), "handoff root already exists; no automatic retry")
    if freeze:
        require(
            root == HANDOFF_ROOT and parent_root == PARENT_ROOT and training_root == TRAINING_ROOT,
            "production handoff requires the independently registered V40 parent and lease roots",
        )
    require(
        mode in MODES
        and isinstance(authorization, dict)
        and authorization.get("mode") == mode
        and authorization.get("user_consent"),
        "explicit consent and matching fixed handoff mode required",
    )
    protocol = checked(parent_root / "protocol/record.json")
    require(
        protocol["allowed_gpu_indices"] == list(GPUS)
        and set(protocol["gpu_uuids"]) == {str(gpu) for gpu in GPUS}
        and len(set(protocol["gpu_uuids"].values())) == 8,
        "V40 eight-device scope required",
    )
    queue = queue_snapshot(parent_root, protocol["id"])
    require(queue["phase"] in LIVE_PHASES, "parent is not a live V40 episode")
    require(0 <= now - epoch(queue["at"]) <= 120, "registration requires fresh parent queue")
    intent = checked(parent_root / "queue/run_intent/record.json")
    actual = identity(intent["pid"])
    require(
        intent["protocol_id"] == protocol["id"]
        and actual is not None
        and actual["birth"] == str(intent["birth"])
        and actual["uid"] == os.getuid(),
        "parent controller identity or account changed",
    )
    expected_controller = actual if expected_controller is None else expected_controller
    require(expected_controller == actual, "supplied controller disagrees with parent run intent")
    assert_controller_identity(expected_controller, identity)
    require(
        str(parent_root / "implementation/finqa_v40_controller.py") in actual["argv"]
        and "run" in actual["argv"]
        and str(parent_root) in actual["argv"],
        "not the frozen V40 controller command",
    )
    launch = checked(parent_root / "launch_01/record.json")
    require(
        launch["pid"] == actual["pid"]
        and str(launch["birth"]) == actual["birth"]
        and launch["command"] == actual["argv"],
        "registered full launch command changed",
    )
    inherited_class_shards(parent_root, protocol, identity)
    observed = {
        stage_key(value): (path, value)
        for path in launches(parent_root)
        for value in [checked(path)]
    }
    active = []
    for value in queue["active_children"]:
        require(stage_key(value) in observed, "active queue entry lacks sealed launch")
        active.append(observed[stage_key(value)][1])
    # Include dispatches made after the last heartbeat, not just its active list.
    known = {stage_key(value) for value in active}
    active.extend(
        value
        for path, value in observed.values()
        if stage_key(value) not in known and not (path.parents[1] / "exit/record.json").exists()
    )
    budget = float(protocol["resource_wait_budget_seconds"])
    bound = deadline_bound(queue, active, now, budget)
    deadline_epoch = bound if deadline_epoch is None else float(deadline_epoch)
    require(now < deadline_epoch <= bound, "handoff deadline may not extend parent budgets")
    raw = Path(__file__).read_bytes()
    if freeze:
        repository = Path(__file__).resolve().parents[2]
        source_commit = subprocess.check_output(
            ["git", "rev-parse", source_commit + "^{commit}"], cwd=repository, text=True
        ).strip()
        committed = subprocess.check_output(
            ["git", "show", source_commit + ":trusted_data_synthesis/scripts/finqa_v41_handoff.py"],
            cwd=repository,
        )
        require(raw == committed, "handoff must use committed byte-identical source")
    capability = verify_pidfd_capability()
    root.mkdir(parents=True, exist_ok=False)
    implementation = root / "implementation/finqa_v41_handoff.py"
    implementation.parent.mkdir()
    with implementation.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    publish(
        root / "implementation/record.json",
        dict(
            schema=SCHEMA + ".implementation",
            source_commit=source_commit,
            source=ref(implementation),
            committed_source_verified=freeze,
        ),
    )
    publish(
        root / "authorization/record.json",
        dict(schema=SCHEMA + ".authorization", at=timestamp(now), **authorization),
    )
    plan = publish(
        root / "plan/record.json",
        dict(
            schema=SCHEMA,
            at=timestamp(now),
            mode=mode,
            mode_automatically_upgraded=False,
            pidfd_capability=capability,
            parent_root=str(parent_root),
            training_root=str(training_root),
            parent_protocol=ref(parent_root / "protocol/record.json"),
            parent_run_intent=ref(parent_root / "queue/run_intent/record.json"),
            parent_controller_launch=ref(parent_root / "launch_01/record.json"),
            implementation=ref(root / "implementation/record.json"),
            authorization=ref(root / "authorization/record.json"),
            controller=expected_controller,
            gpu_uuids=protocol["gpu_uuids"],
            initial_queue=queue,
            baseline_launches=[ref(path) for path, _ in observed.values()],
            deadline_epoch=deadline_epoch,
            maximum_allowed_deadline_epoch=bound,
            resource_wait_budget_seconds=budget,
            queue_freshness_seconds=120,
            polling_seconds=1.0,
            workers_signalled=False,
            automatic_retry=False,
            original_budgets_reset=False,
            launches_new_experiment=False,
            class_undispatched_shards_never_blocked=True,
        ),
    )
    status(
        root, dict(at=timestamp(now), phase="REGISTERED_NOT_STARTED", plan_id=plan["id"], mode=mode)
    )
    return plan


def run(
    root,
    *,
    stop_requested=lambda: False,
    on_quiesced=None,
    validate_quiescent=None,
    clock=time.time,
    sleep=time.sleep,
    identity=process_identity,
    send_signal=signal_controller,
    barrier_factory=Barrier,
):
    root = Path(root).resolve()
    plan = checked(root / "plan/record.json")
    require(plan["schema"] == SCHEMA and plan["mode"] in MODES, "wrong handoff schema or mode")
    manifest = check_ref(plan["implementation"])
    require(
        ref(manifest["source"]["path"]) == manifest["source"]
        and hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == manifest["source"]["sha256"],
        "executing handoff source changed",
    )
    authorization = check_ref(plan["authorization"])
    require(
        authorization.get("mode") == plan["mode"] and authorization.get("user_consent"),
        "registered handoff mode or consent changed",
    )
    require(callable(validate_quiescent), "explicit inheritance preflight callback required")
    parent = check_ref(plan["parent_protocol"])
    check_ref(plan["parent_run_intent"])
    check_ref(plan["parent_controller_launch"])
    for reference in plan["baseline_launches"]:
        check_ref(reference)
    parent_root = Path(plan["parent_root"])
    inherited = inherited_class_shards(parent_root, parent, identity)
    publish(
        root / "run_intent/record.json",
        dict(
            schema=SCHEMA + ".run",
            at=timestamp(clock()),
            plan_id=plan["id"],
            mode=plan["mode"],
            identity=process_identity(os.getpid()),
            automatic_retry=False,
        ),
    )
    barrier = barrier_factory(plan["training_root"], plan["gpu_uuids"])
    observed, verified, events = {}, {}, 0
    all_locks_epoch = signal_epoch = None
    signal_sent = callback_invoked = False

    def event(phase, **extra):
        nonlocal events
        events += 1
        value = dict(
            schema=SCHEMA + ".event",
            at=timestamp(clock()),
            plan_id=plan["id"],
            mode=plan["mode"],
            phase=phase,
            barrier_gpus=sorted(barrier.held),
            **extra,
        )
        publish(root / f"events/event{events:06d}/record.json", value)
        status(root, {**value, "controller_signalled": signal_sent, "workers_signalled": False})

    def charged_wait(queue):
        return max(
            queue["global_external_resource_wait_seconds"],
            plan["initial_queue"]["global_external_resource_wait_seconds"]
            + clock()
            - epoch(plan["at"]),
        )

    def gate(queue=None):
        require(not stop_requested(), "handoff stop requested; no migration")
        require(
            math.isfinite(clock()) and clock() >= epoch(plan["at"]), "handoff wall clock reversed"
        )
        require(clock() < plan["deadline_epoch"], "handoff deadline expired; no migration")
        require(
            charged_wait(plan["initial_queue"] if queue is None else queue)
            < plan["resource_wait_budget_seconds"],
            "parent resource wait budget exhausted",
        )

    def observe(queue):
        for path in launches(parent_root):
            name = str(path.resolve())
            if name not in observed:
                launch = checked(path)
                require(launch["protocol_id"] == parent["id"], "unexpected stage protocol")
                observed[name] = launch
            if name not in verified:
                value = validate_stage(path, observed[name], parent["id"], identity)
                if value is not None:
                    verified[name] = value
        keys = {stage_key(value) for value in observed.values()}
        require(
            all(stage_key(value) in keys for value in queue["active_children"]),
            "active worker lacks observed launch",
        )

    def release_for_progress(reason):
        nonlocal all_locks_epoch
        had_locks = bool(barrier.held)
        barrier.close()
        all_locks_epoch = None
        if had_locks:
            event("BARRIER_RELEASED_FOR_PARENT_PROGRESS", reason=reason)

    def freshly_empty(queue):
        return (
            barrier.complete
            and all_locks_epoch is not None
            and queue["phase"] in LIVE_PHASES
            and not queue["active_children"]
            and epoch(queue["at"]) > all_locks_epoch
            and 0 <= clock() - epoch(queue["at"]) <= plan["queue_freshness_seconds"]
        )

    try:
        event("OBSERVING_PARENT_WITHOUT_WORKER_SIGNALS")
        while True:
            queue = queue_snapshot(parent_root, parent["id"])
            gate(queue)
            require(
                queue["phase"] in LIVE_PHASES, "parent stopped or failed before handoff boundary"
            )
            assert_controller_identity(plan["controller"], identity)
            observe(queue)
            frontiers = class_frontiers(parent_root, inherited)
            partial = [row for row in frontiers if row["undispatched_shards"]]
            if partial:
                release_for_progress("started_class_has_undispatched_shards")
            elif plan["mode"] == MODES[0]:
                # A busy all-or-none probe never holds otherwise usable cards.
                if not barrier.acquire_all_or_none():
                    all_locks_epoch = None
            else:
                barrier.acquire_available()
            # A parent can win a released-card race and start a new partial
            # class during lock acquisition. Never leave that class starved.
            if any(row["undispatched_shards"] for row in class_frontiers(parent_root, inherited)):
                release_for_progress("class_frontier_changed_while_acquiring")
            if barrier.complete and all_locks_epoch is None:
                all_locks_epoch = clock()
                event("ALL_ADMISSION_LOCKS_HELD")
            if freshly_empty(queue) and len(verified) == len(observed):
                final_queue = queue_snapshot(parent_root, parent["id"])
                require(freshly_empty(final_queue), "parent ceased to be freshly quiescent")
                observe(final_queue)
                require(len(verified) == len(observed), "new unverified stage appeared")
                class_boundaries = validate_complete_class_boundaries(
                    parent_root, parent["id"], inherited, identity
                )
                validate_quiescent(plan, final_queue)
                final_queue = queue_snapshot(parent_root, parent["id"])
                gate(final_queue)
                require(
                    freshly_empty(final_queue),
                    "parent ceased to be freshly quiescent during preflight",
                )
                assert_controller_identity(plan["controller"], identity)
                event(
                    "ZERO_WORKER_CONTROLLER_SIGNAL_INTENT",
                    queue=final_queue,
                    verified_stages=list(verified.values()),
                    complete_class_boundaries=class_boundaries,
                )
                send_signal(plan["controller"])
                signal_sent, signal_epoch = True, clock()
                event("CONTROLLER_SIGTERM_SENT")
                break
            status(
                root,
                dict(
                    at=timestamp(clock()),
                    phase="WAITING_FOR_SAFE_NATURAL_BOUNDARY",
                    plan_id=plan["id"],
                    mode=plan["mode"],
                    barrier_gpus=sorted(barrier.held),
                    parent_queue_at=queue["at"],
                    parent_active=queue["active_children"],
                    blocked_class_frontiers=partial,
                    deadline_epoch=plan["deadline_epoch"],
                    workers_signalled=False,
                    controller_signalled=False,
                ),
            )
            sleep(min(plan["polling_seconds"], max(0, plan["deadline_epoch"] - clock())))

        while True:
            queue = queue_snapshot(parent_root, parent["id"])
            gate(queue)
            require(clock() < signal_epoch + 600, "controller exceeded original stop grace")
            require(not queue["active_children"], "parent launched behind the barrier")
            require(
                queue["phase"] in LIVE_PHASES | {"SAFE_BOUNDARY_STOP_REQUESTED", PAUSED},
                "parent failed during clean pause",
            )
            actual = identity(plan["controller"]["pid"])
            require(
                actual is None or actual == plan["controller"],
                "controller identity changed during exit",
            )
            if actual is None and queue["phase"] == PAUSED:
                require(
                    epoch(queue["at"]) >= signal_epoch, "paused queue predates controller signal"
                )
                failure = checked(parent_root / "failure/record.json")
                require(
                    failure.get("phase") == PAUSED
                    and failure.get("protocol_id") == parent["id"]
                    and failure.get("error_type") == "DurablePause"
                    and failure.get("error") == "explicit safe stop requested"
                    and failure.get("stop_error") is None
                    and failure.get("actual_progress_audit_error") is None,
                    "parent did not record the requested clean durable pause",
                )
                progress = checked(parent_root / "actual_final_progress/record.json")
                closeout = publish(
                    root / "closeout/record.json",
                    dict(
                        schema=SCHEMA + ".closeout",
                        at=timestamp(clock()),
                        status="COMPLETE",
                        plan_id=plan["id"],
                        mode=plan["mode"],
                        parent_root=str(parent_root),
                        parent_protocol_id=parent["id"],
                        parent_protocol=plan["parent_protocol"],
                        parent_final_queue=queue,
                        parent_pause=ref(parent_root / "failure/record.json"),
                        actual_progress=ref(parent_root / "actual_final_progress/record.json"),
                        actual_progress_id=progress["id"],
                        all_old_gpu_locks_held=True,
                        controller_exited=True,
                        children_exited=True,
                        controller_real_exit_observed=True,
                        controller_returncode=None,
                        controller_returncode_observable=False,
                        exit_code_observed=False,
                        workers_signalled=False,
                        observed_stages=list(verified.values()),
                        complete_class_boundaries=class_boundaries,
                        original_budgets_reset=False,
                        elapsed_handoff_wall_seconds=clock() - epoch(plan["at"]),
                        global_resource_wait_seconds=charged_wait(queue),
                        resource_wait_accounting=(
                            "max(parent_final_wait, initial_wait + entire_handoff_wall)"
                        ),
                        continuation_started=False,
                        automatic_retry=False,
                    ),
                )
                event("QUIESCED", closeout=ref(root / "closeout/record.json"))
                if on_quiesced is not None:
                    gate(queue)
                    callback_invoked = True
                    released = False

                    def release_barrier(*, paused_queue=queue):
                        nonlocal released
                        require(not released, "barrier release is single-use")
                        gate(paused_queue)
                        billing = publish(
                            root / "barrier_release/record.json",
                            dict(
                                schema=SCHEMA + ".release",
                                at=timestamp(clock()),
                                plan_id=plan["id"],
                                global_resource_wait_seconds=charged_wait(paused_queue),
                                initialization_wall_charged=True,
                                original_budgets_reset=False,
                            ),
                        )
                        barrier.close()
                        released = True
                        event("BARRIER_RELEASED_AFTER_CLEAN_PAUSE")
                        return billing

                    callback_result = on_quiesced(closeout, release_barrier)
                    require(
                        released, "continuation callback must explicitly bill and release barrier"
                    )
                    publish(
                        root / "continuation_callback/record.json",
                        dict(
                            schema=SCHEMA + ".callback",
                            at=timestamp(clock()),
                            plan_id=plan["id"],
                            result=callback_result,
                            automatic_retry=False,
                        ),
                    )
                return closeout
            sleep(min(plan["polling_seconds"], max(0, plan["deadline_epoch"] - clock())))
    except BaseException as error:
        phase = (
            "CONTINUATION_CALLBACK_ERROR_NO_RETRY"
            if callback_invoked
            else "PAUSED_HANDOFF_ERROR_NO_RETRY"
            if signal_sent
            else "STOPPED_NO_MIGRATION"
        )
        event(phase, error_type=type(error).__name__, error=str(error))
        publish(
            root / "failure/record.json",
            dict(
                schema=SCHEMA + ".failure",
                at=timestamp(clock()),
                plan_id=plan["id"],
                status=phase,
                error_type=type(error).__name__,
                error=str(error),
                controller_signalled=signal_sent,
                workers_signalled=False,
                parent_resume_attempted=False,
                new_experiment_started_by_handoff=False,
                continuation_callback_invoked=callback_invoked,
                automatic_retry=False,
            ),
        )
        raise
    finally:
        barrier.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.parse_args()
    # A command-line handoff without the new controller's inheritance preflight
    # must never be an alternate way to pause the live scientific controller.
    parser.error(
        "invoke register/run from the registered V41 controller with inheritance preflight"
    )


if __name__ == "__main__":
    main()
