"""One explicitly authorized V35 recovery, within the ORIGINAL absolute window.

The original 19-file mathematical implementation and task binding stay intact.
Only the separately sealed process-control shell changes. Old failures remain
failures; completed task values are copied without rebinding or recalculation.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = _module(Path(__file__).with_name("finqa_v35_task_controller.py"), __name__ + "_base")
SOURCE_ROOT = base.ROOT
ROOT = SOURCE_ROOT / "recovery_01"
SOURCE_PROTOCOL_ID = "28baa409dc59e872df69da4950262fd9606140e3eeb8a8911c36429e350976a3"
FILES = (
    "finqa_v35_task_controller.py",
    "finqa_v35_recovery_controller.py",
    "finqa_v35_recovery_worker.py",
    "finqa_v35_recovery_cache.py",
)
RECOVERY_STAGES = ("shard01", "shard02", "shard03")
require, sha, checked, publish = base.require, base.sha, base.checked, base.publish
entry, read_ref, file_ref, now = base.entry, base.read_ref, base.file_ref, base.now


def __getattr__(name):
    # The byte-identical V35 worker uses these existing non-mathematical helpers.
    return getattr(base, name)


def checked_math_implementation(root):
    original = base.checked_implementation(SOURCE_ROOT)
    copied = base.checked_implementation(root)
    require(copied == original, "recovery mathematical implementation differs")
    return copied


def checked_recovery_implementation(root):
    directory = Path(root) / "recovery_implementation"
    record = checked(directory / "record.json")
    require(
        record["schema"] == "v35_separate_recovery_control_implementation.v1"
        and list(record["sha256"]) == list(FILES)
        and len(record["source_commit"]) == 40
        and record["original_math_implementation"]
        == entry(SOURCE_ROOT / "implementation/record.json"),
        "unregistered recovery control implementation",
    )
    for name, expected in record["sha256"].items():
        require(sha(directory / name) == expected, "recovery shell bytes changed: " + name)
    return record


def authorization_body():
    return dict(
        schema="v35_explicit_same_window_recovery_authorization.v1",
        user_request="尝试恢复任务",
        user_date="2026-10-10",
        original_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
        original_failure=entry(SOURCE_ROOT / "failure/record.json"),
        original_execution_window=entry(SOURCE_ROOT / "execution_window/record.json"),
        scope="one recovery of the 70 missing whole tasks, followed by one global recomputation",
        complete_tasks_reused=674,
        missing_tasks=70,
        new_complete_task_rows=480,
        current_uncommitted_tasks_may_repeat_their_unsealed_rows=True,
        inherited_absolute_deadline=True,
        additional_runtime_window_seconds=0,
        original_B_resume_authorized=False,
        original_failure_reclassified=False,
        automatic_retry=False,
    )


def protocol_body(root, original, *, at):
    root = Path(root)
    result = copy.deepcopy({k: v for k, v in original.items() if k != "id"})
    result.update(
        schema="v35_same_window_explicit_recovery_protocol.v1",
        at=at,
        output_root=str(root),
        source_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
        source_failure=entry(SOURCE_ROOT / "failure/record.json"),
        authorization=entry(root / "authorization/record.json"),
        recovery_implementation=entry(root / "recovery_implementation/record.json"),
        cache_inheritance=entry(root / "cache_inheritance/record.json"),
        task_cache_root=str(root / "task_cache"),
        recovery_stages=list(RECOVERY_STAGES),
        inherited_complete_stages=["shard00"],
        source_execution_window=entry(SOURCE_ROOT / "execution_window/record.json"),
        absolute_deadline_epoch=checked(SOURCE_ROOT / "execution_window/record.json")[
            "deadline_epoch"
        ],
        no_deadline_reset=True,
        original_V35_failure_reclassified=False,
        task_binding_is_original_and_not_rebound=True,
        original_math_files_unchanged=True,
        coordinator_runs_across_original_and_recovery=1,
        candidate_change="process-exit observation fix and explicit same-window recovery only",
    )
    return result


def source_still_stopped(original):
    failure = checked(SOURCE_ROOT / "failure/record.json")
    queue = json.loads((SOURCE_ROOT / "queue/status.json").read_bytes())
    require(
        queue["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and queue["protocol_id"] == original["id"] == SOURCE_PROTOCOL_ID
        and not queue["active_children"]
        and failure["error"] == queue["error"] == "live worker RSS unavailable",
        "source is not the specific stopped V35 attempt",
    )
    for relative in ("queue/run_intent", *(stage + "/launch" for stage in base.SHARD_STAGES)):
        launch = checked(SOURCE_ROOT / relative / "record.json")
        require(base.birth(launch["pid"]) != launch["birth"], "source process still alive")
    require(not (SOURCE_ROOT / "coordinator").exists(), "global recomputation already attempted")
    return queue


def checked_protocol(root):
    root = Path(root).resolve()
    require(root == ROOT, "only the explicitly registered recovery destination is allowed")
    original = base.checked_protocol(SOURCE_ROOT)
    source_still_stopped(original)
    checked_math_implementation(root)
    checked_recovery_implementation(root)
    authorization = checked(root / "authorization/record.json")
    require(
        {k: v for k, v in authorization.items() if k != "id"} == authorization_body(),
        "recovery authorization changed",
    )
    result = checked(root / "protocol/record.json")
    require(
        {k: v for k, v in result.items() if k != "id"}
        == protocol_body(root, original, at=result["at"]),
        "fixed recovery contract changed",
    )
    # Deliberately retain the ORIGINAL cache binding, including original paths
    # and implementation ID. A separate shell manifest records this adapter.
    require(result["task_binding"] == original["task_binding"], "cache math was rebound")
    window = checked(root / "execution_window/record.json")
    original_window = checked(SOURCE_ROOT / "execution_window/record.json")
    require(
        window["protocol_id"] == result["id"]
        and window["deadline_epoch"]
        == original_window["deadline_epoch"]
        == result["absolute_deadline_epoch"]
        and window["first_launch_epoch"] == original_window["first_launch_epoch"]
        and window["source_window"] == entry(SOURCE_ROOT / "execution_window/record.json")
        and window["additional_runtime_window_seconds"] == 0
        and window["no_stage_deadline_reset"] is True,
        "recovery execution window must preserve the original absolute deadline",
    )
    return result


def initialize(root, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one recovery registration; never overwrite")
    original = base.checked_protocol(SOURCE_ROOT)
    source_still_stopped(original)
    window = checked(SOURCE_ROOT / "execution_window/record.json")
    require(time.time() < window["deadline_epoch"], "original absolute deadline already expired")
    disk = base.disk_memory(SOURCE_ROOT, read_ref(original["task_plan"]))
    require(
        disk["free_bytes"] >= disk["admission_bytes"],
        "insufficient disk for independent cache copy",
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", source_commit + "^{commit}"], cwd=base.REPO, text=True
    ).strip()
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=base.REPO)
        require(
            base.hashlib.sha256(raw).hexdigest() == sha(base.REPO / relative), "uncommitted shell"
        )
        sources[name] = raw
    root.mkdir()
    math = base.checked_implementation(SOURCE_ROOT)
    math_directory = root / "implementation"
    math_directory.mkdir()
    for name in (*math["sha256"], "record.json"):
        shutil.copyfile(SOURCE_ROOT / "implementation" / name, math_directory / name)
    checked_math_implementation(root)
    directory = root / "recovery_implementation"
    directory.mkdir()
    for name, raw in sources.items():
        with (directory / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    publish(
        directory / "record.json",
        dict(
            schema="v35_separate_recovery_control_implementation.v1",
            at=now(),
            source_commit=commit,
            original_math_implementation=entry(SOURCE_ROOT / "implementation/record.json"),
            sha256={name: base.hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )
    publish(root / "authorization/record.json", authorization_body())
    module = _module(directory / "finqa_v35_recovery_cache.py", __name__ + "_copy")
    module.prepare_cache(SOURCE_ROOT, root, base)
    protocol = publish(root / "protocol/record.json", protocol_body(root, original, at=now()))
    publish(
        root / "execution_window/record.json",
        dict(
            schema="v35_inherited_absolute_execution_window.v1",
            at=now(),
            protocol_id=protocol["id"],
            first_launch_epoch=window["first_launch_epoch"],
            deadline_epoch=window["deadline_epoch"],
            source_window=entry(SOURCE_ROOT / "execution_window/record.json"),
            additional_runtime_window_seconds=0,
            no_stage_deadline_reset=True,
        ),
    )
    checked_protocol(root)
    require(time.time() < window["deadline_epoch"], "original deadline expired during registration")
    base.status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=protocol["id"],
            original_B_resume_authorized=False,
        ),
    )
    return protocol


def worker_command(root, stage, row, protocol, deadline_epoch):
    command = base.worker_command(root, stage, row, protocol, deadline_epoch)
    expected = str(Path(root) / "implementation/finqa_v35_task_worker.py")
    require(command.count(expected) == 1, "original worker argv layout changed")
    command[command.index(expected)] = str(
        Path(root) / "recovery_implementation/finqa_v35_recovery_worker.py"
    )
    return command


class RecoveryController(base.Controller):
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.protocol = checked_protocol(self.root)
        self.task_plan = read_ref(self.protocol["task_plan"])
        original = base.checked_protocol(SOURCE_ROOT)
        queue = source_still_stopped(original)
        receipt = read_ref(self.protocol["cache_inheritance"])
        self.inheritance = receipt
        inherited = receipt["inherited_completed_stages"]["shard00"]
        old_result = read_ref(inherited["result"])
        require(
            read_ref(inherited["exit"])["returncode"] == 0, "source shard00 did not exit cleanly"
        )
        self.results = {
            "shard00": base.check_result(original, "shard00", old_result, self.task_plan)
        }
        self.active = {}
        self.wait_used = queue["resource_wait_seconds"]
        self.stop = False
        self.deadline_epoch = self.protocol["absolute_deadline_epoch"]
        self.first_launch_epoch = checked(SOURCE_ROOT / "execution_window/record.json")[
            "first_launch_epoch"
        ]
        self.deadline = time.monotonic() + self.deadline_epoch - time.time()
        self.host_event_count = 0

    def collect_finished(self):
        super().collect_finished()
        for row in self.inheritance["by_shard"]:
            stage = row["stage"]
            if stage in RECOVERY_STAGES and stage in self.results:
                result = self.results[stage]
                require(
                    result["reused_task_ids"] == row["complete_task_ids"]
                    and result["class_task_calls"] == len(row["missing_task_ids"]),
                    "recovery recomputed inherited tasks or omitted missing tasks",
                )

    def launch(self, stage, row, lock):
        self.time_gate()
        require(stage in (*RECOVERY_STAGES, "coordinator"), "completed shard00 must not relaunch")
        require(
            stage not in self.active
            and stage not in self.results
            and not (self.root / stage / "launch/record.json").exists(),
            "one attempt per recovery stage",
        )
        require(
            len(self.active) < 3
            and row["index"] == base.STAGE_GPU[stage]
            and all(item["launch"]["gpu_index"] != row["index"] for item in self.active.values()),
            "recovery worker or device cap exceeded",
        )
        if stage == "coordinator":
            require(
                not self.active
                and set(self.results) == set(base.SHARD_STAGES)
                and (self.root / "complete_task_cache/record.json").is_file(),
                "coordinator requires all task caches and all shard exits",
            )
        base.verify_original_B_paused(self.protocol)
        fresh = next((item for item in base.inventory() if item["index"] == row["index"]), None)
        require(fresh is not None and base.eligible(fresh, self.protocol), "GPU not fully idle")
        directory = self.root / stage
        directory.mkdir(parents=True, exist_ok=True)
        command = worker_command(self.root, stage, row, self.protocol, self.deadline_epoch)
        started_monotonic, started_epoch = time.monotonic(), time.time()
        with (directory / "worker.log").open("xb") as stream:
            process = subprocess.Popen(
                command,
                cwd=base.REPO,
                env=base.worker_environment(row),
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        born = base.birth(process.pid)
        launch = dict(
            schema="v35_explicit_recovery_stage_launch.v1",
            at=now(),
            protocol_id=self.protocol["id"],
            stage=stage,
            pid=process.pid,
            birth=born,
            worker=str(self.root / "recovery_implementation/finqa_v35_recovery_worker.py"),
            command=command,
            gpu_index=row["index"],
            gpu_uuid=row["uuid"],
            gpu_observed=fresh,
            global_deadline_epoch=self.deadline_epoch,
            global_first_launch_epoch=self.first_launch_epoch,
            popen_started_epoch=started_epoch,
            term_grace_seconds=base.TERM_GRACE_SECONDS,
        )
        self.active[stage] = dict(
            process=process, launch=launch, lock=lock, started_monotonic=started_monotonic
        )
        require(born is not None, "worker exited before ownership established")
        self.active[stage]["launch"] = publish(directory / "launch/record.json", launch)
        self.update("RUNNING", stage=stage)

    def worker_accounting(self):
        current = super().worker_accounting()
        prior = json.loads((SOURCE_ROOT / "queue/status.json").read_bytes())["worker_accounting"]
        current.update(
            original_attempt_worker_hours=prior["total_elapsed_worker_hours"],
            original_plus_recovery_exited_worker_hours=(
                prior["total_elapsed_worker_hours"] + current["total_elapsed_worker_hours"]
            ),
            original_attempt_failure_reclassified=False,
        )
        return current

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "recovery_implementation" / FILES[1],
            "run only the frozen recovery controller",
        )
        path = self.root / "queue/controller.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            publish(
                self.root / "queue/run_intent/record.json",
                dict(
                    schema="v35_explicit_recovery_intent.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    pid=os.getpid(),
                    birth=base.birth(os.getpid()),
                    no_automatic_controller_restart=True,
                ),
            )
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            for sig in handlers:
                signal.signal(sig, lambda *_: setattr(self, "stop", True))
            try:
                self.time_gate()
                self.run_group(RECOVERY_STAGES)
                require(
                    not self.active and set(self.results) == set(base.SHARD_STAGES),
                    "missing shard completion",
                )
                self.time_gate()
                coverage = self.validate_task_coverage(complete=True)
                self.time_gate()
                publish(
                    self.root / "complete_task_cache/record.json",
                    dict(
                        schema="v35_all_tasks_complete_before_coordinator.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        all_shard_processes_exited=True,
                        **coverage,
                    ),
                )
                self.run_group(("coordinator",))
                publish(
                    self.root / "result/record.json",
                    dict(
                        schema="v35_completed_same_window_recovery.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        status="COMPLETE",
                        numeric_pass=True,
                        coordinator_result=entry(self.root / "coordinator/result/record.json"),
                        task_cache_complete=entry(self.root / "complete_task_cache/record.json"),
                        inherited_cache=entry(self.root / "cache_inheritance/record.json"),
                        task_count=744,
                        state_count=1360,
                        reused_complete_tasks=674,
                        new_complete_tasks=70,
                        global_recomputations=1,
                        API_calls=0,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        optimizer_steps=0,
                        replayed_responses=0,
                        original_B_resume_authorized=False,
                        original_V35_failure_reclassified=False,
                        worker_accounting=self.worker_accounting(),
                    ),
                )
                self.update("COMPLETE", supplement_validation_complete=True)
                return True
            except BaseException as error:
                stop_error = None
                try:
                    self.drain_stopped()
                except BaseException as stop_exception:
                    stop_error = dict(
                        error_type=type(stop_exception).__name__, error=str(stop_exception)
                    )
                try:
                    coverage = self.validate_task_coverage(complete=False)
                except BaseException as cache_exception:
                    coverage = dict(cache_validation_failed=True, error=str(cache_exception))
                body = dict(
                    error_type=type(error).__name__,
                    error=str(error),
                    stop_error=stop_error,
                    task_cache_coverage=coverage,
                    no_automatic_retry=True,
                    original_V35_failure_reclassified=False,
                )
                self.update("STOPPED_FAILURE_NO_RETRY", **body)
                publish(
                    self.root / "failure/record.json",
                    dict(
                        schema="v35_explicit_recovery_failure.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        original_B_resume_authorized=False,
                        worker_accounting=self.worker_accounting(),
                        **body,
                    ),
                )
                raise
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "initialize":
        require(args.source_commit is not None, "committed recovery shell required")
        result = initialize(args.root, args.source_commit)
    elif args.action == "run":
        RecoveryController(args.root).run()
        return
    else:
        result = checked_protocol(args.root)
    print(json.dumps(dict(id=result["id"], deadline_epoch=result["absolute_deadline_epoch"])))


if __name__ == "__main__":
    main()
