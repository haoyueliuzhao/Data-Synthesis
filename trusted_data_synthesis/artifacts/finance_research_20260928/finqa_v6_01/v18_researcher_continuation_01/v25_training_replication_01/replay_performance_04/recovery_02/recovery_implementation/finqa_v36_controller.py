"""Three fixed missing tasks, then one original global recomputation.

V35 failures remain immutable. V36 changes only lifecycle supervision and
read-only cache routing; its mathematical worker is the original 19-file seal.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import math
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
lifecycle = _module(Path(__file__).with_name("finqa_v36_lifecycle.py"), __name__ + "_lifecycle")
SOURCE = base.ROOT
PREVIOUS = SOURCE / "recovery_01"
ROOT = SOURCE / "recovery_02"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/0fd78b12-350a-4c1c-82b1-45353da17c26/已粘贴的文本.txt"
)
CLOSEOUT_ID = "3676d9c63fd9df3e17300d97d0c5815c52ed473e1c70723a8010e59ffd19800e"
MISSING_INDICES = (739, 741, 743)
NEW_FILES = (
    "finqa_v35_task_controller.py",
    "finqa_v36_controller.py",
    "finqa_v36_lifecycle.py",
    "finqa_v36_cache.py",
    "finqa_v36_worker.py",
)
STAGES = ("shard01", "coordinator")
require, sha, checked, publish = base.require, base.sha, base.checked, base.publish
entry, read_ref, file_ref, now = base.entry, base.read_ref, base.file_ref, base.now


def __getattr__(name):
    return getattr(base, name)


def checked_math_implementation(root):
    original = base.checked_implementation(SOURCE)
    require(base.checked_implementation(root) == original, "original mathematical seal changed")
    return original


def checked_v36_implementation(root):
    directory = Path(root) / "recovery_implementation"
    record = checked(directory / "record.json")
    require(
        record["schema"] == "v36_lifecycle_overlay_implementation.v1"
        and list(record["sha256"]) == list(NEW_FILES)
        and len(record["source_commit"]) == 40
        and record["mathematical_implementation"] == entry(SOURCE / "implementation/record.json"),
        "V36 implementation provenance differs",
    )
    for name, expected in record["sha256"].items():
        require(sha(directory / name) == expected, "V36 frozen bytes changed: " + name)
    return record


def checked_parents():
    original = base.checked_protocol(SOURCE)
    previous = checked(PREVIOUS / "protocol/record.json")
    closeout = checked(PREVIOUS / "closeout_01/record.json")
    require(
        closeout["id"] == CLOSEOUT_ID
        and closeout["durable_complete_tasks"] == 741
        and closeout["durable_complete_rows"] == 4948
        and not closeout["global_coordinator_launched"],
        "wrong previous closeout",
    )
    require(
        read_ref(closeout["original_protocol"]) == original
        and read_ref(closeout["recovery_protocol"]) == previous,
        "previous protocol references changed",
    )
    read_ref(closeout["original_failure"])
    read_ref(closeout["recovery_failure"])
    for source in (SOURCE, PREVIOUS):
        queue = json.loads((source / "queue/status.json").read_bytes())
        require(
            queue["phase"] == "STOPPED_FAILURE_NO_RETRY" and not queue["active_children"],
            "prior failure must remain stopped",
        )
        parent = checked(source / "launch_01/record.json")
        require(base.birth(parent["pid"]) != parent["birth"], "prior controller still alive")
        for stage in base.SHARD_STAGES:
            launch_path = source / stage / "launch/record.json"
            if launch_path.exists():
                launch = checked(launch_path)
                require(base.birth(launch["pid"]) != launch["birth"], "prior worker still alive")
        require(not (source / "coordinator").exists(), "global recomputation previously attempted")
    return original, previous, closeout


def authority(root):
    return dict(
        schema="v36_explicit_three_task_supplement_authorization.v1",
        user_date="2026-10-10",
        user_request="参照审计修订并开展后续实验",
        audit=entry(Path(root) / "audit/record.json"),
        scope="one shard01 missing-three-task pass, then one original global recomputation",
        inherited_task_count=741,
        new_task_indices=list(MISSING_INDICES),
        new_task_count=3,
        new_complete_task_rows=26,
        maximum_simultaneous_workers=1,
        shard_gpu_index=4,
        coordinator_gpu_index=7,
        original_B_resume_authorized=False,
        no_response_replay_or_sampling_or_scoring_or_optimizer_update=True,
        previous_failures_reclassified=False,
        automatic_retry=False,
        original_absolute_deadline_retained=True,
    )


def protocol_body(root, original, *, at):
    root = Path(root)
    body = copy.deepcopy({k: v for k, v in original.items() if k != "id"})
    window = checked(SOURCE / "execution_window/record.json")
    host = copy.deepcopy(base.HOST_RAM)
    host["shard_admission_bytes"] = host["shard_rss_limit_bytes"] + host["reserve_bytes"]
    body.update(
        schema="v36_three_task_global_validation_protocol.v1",
        at=at,
        output_root=str(root),
        authorization=entry(root / "authorization/record.json"),
        audit=entry(root / "audit/record.json"),
        source_protocol=entry(SOURCE / "protocol/record.json"),
        previous_protocol=entry(PREVIOUS / "protocol/record.json"),
        previous_closeout=entry(PREVIOUS / "closeout_01/record.json"),
        execution_implementation=entry(root / "recovery_implementation/record.json"),
        cache_index=entry(root / "cache_index/record.json"),
        task_cache_root=str(root / "task_cache"),
        stages=list(STAGES),
        maximum_workers=1,
        max_gpu_workers=1,
        maximum_gpu_workers_including_CPU_initialization=1,
        inherited_complete_stages=["shard00", "shard02", "shard03"],
        inherited_task_count=741,
        new_task_indices=list(MISSING_INDICES),
        new_class_task_calls=3,
        new_complete_task_rows=26,
        new_complete_task_states=7,
        new_complete_task_packages=13,
        full_class_passes_started_this_attempt=0,
        global_recomputations_this_attempt=1,
        previous_failed_partial_task_rows_replayed=7,
        parent_tensor_files_copied=0,
        parent_cache_read_only=True,
        host_ram=host,
        disk_admission="twice raw three-new-task tensors plus 32GiB reserve",
        absolute_deadline_epoch=window["deadline_epoch"],
        source_execution_window=entry(SOURCE / "execution_window/record.json"),
        no_stage_deadline_reset=True,
        global_clock_starts="original V35 first GPU-worker Popen; inherited absolute deadline",
        draining_episode_seconds=base.TERM_GRACE_SECONDS,
        draining_keeps_gpu_lock_and_worker_slot=True,
        short_wait_timeout_is_not_compute_failure=True,
        scheduled_worker_hours_upper_bound=base.GLOBAL_DEADLINE_SECONDS / 3600,
        shutdown_grace_worker_hours_upper_bound=base.TERM_GRACE_SECONDS / 3600,
        candidate_change=(
            "trusted result draining lifecycle and read-only parent task cache overlay"
        ),
        original_V35_failures_reclassified=False,
    )
    return body


def checked_protocol(root):
    root = Path(root).resolve()
    require(root == ROOT, "only the explicitly registered V36 root is allowed")
    original, _, _ = checked_parents()
    checked_math_implementation(root)
    checked_v36_implementation(root)
    auth = checked(root / "authorization/record.json")
    require(
        {k: v for k, v in auth.items() if k != "id"} == authority(root), "V36 authority changed"
    )
    audit = checked(root / "audit/record.json")
    require(
        sha(audit["source"]["path"])
        == audit["source"]["sha256"]
        == audit["original_attachment"]["sha256"],
        "audit bytes changed",
    )
    protocol = checked(root / "protocol/record.json")
    require(
        {k: v for k, v in protocol.items() if k != "id"}
        == protocol_body(root, original, at=protocol["at"]),
        "fixed V36 contract changed",
    )
    require(
        protocol["task_binding"] == original["task_binding"], "parent mathematical binding changed"
    )
    window = checked(root / "execution_window/record.json")
    old_window = checked(SOURCE / "execution_window/record.json")
    require(
        window["protocol_id"] == protocol["id"]
        and window["deadline_epoch"]
        == old_window["deadline_epoch"]
        == protocol["absolute_deadline_epoch"]
        and window["first_launch_epoch"] == old_window["first_launch_epoch"]
        and window["source_window"] == entry(SOURCE / "execution_window/record.json")
        and window["additional_runtime_window_seconds"] == 0,
        "absolute execution window changed",
    )
    return protocol


def initialize(root, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one new V36 registration; never overwrite/retry")
    original, _, _ = checked_parents()
    window = checked(SOURCE / "execution_window/record.json")
    require(
        time.time() < window["deadline_epoch"], "original window expired; no implicit replacement"
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", source_commit + "^{commit}"], cwd=base.REPO, text=True
    ).strip()
    files = {}
    for name in NEW_FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=base.REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(base.REPO / relative), "uncommitted V36 source"
        )
        files[name] = raw
    root.mkdir()
    math_record = base.checked_implementation(SOURCE)
    (root / "implementation").mkdir()
    for name in (*math_record["sha256"], "record.json"):
        shutil.copyfile(SOURCE / "implementation" / name, root / "implementation" / name)
    checked_math_implementation(root)
    directory = root / "recovery_implementation"
    directory.mkdir()
    for name, raw in files.items():
        with (directory / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    publish(
        directory / "record.json",
        dict(
            schema="v36_lifecycle_overlay_implementation.v1",
            at=now(),
            source_commit=commit,
            mathematical_implementation=entry(SOURCE / "implementation/record.json"),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
        ),
    )
    (root / "audit").mkdir()
    shutil.copyfile(AUDIT, root / "audit/source.txt")
    publish(
        root / "audit/record.json",
        dict(
            schema="v36_supplied_audit_text.v1",
            at=now(),
            source=file_ref(root / "audit/source.txt"),
            original_attachment=file_ref(AUDIT),
            linked_zip_or_standalone_report_supplied=False,
            external_25_checks_are_not_server_test_results=True,
        ),
    )
    publish(root / "authorization/record.json", authority(root))
    cache_module = _module(directory / "finqa_v36_cache.py", __name__ + "_cache")
    cache_module.prepare_index(SOURCE, PREVIOUS, root, base)
    protocol = publish(root / "protocol/record.json", protocol_body(root, original, at=now()))
    publish(
        root / "execution_window/record.json",
        dict(
            schema="v36_inherited_absolute_window.v1",
            at=now(),
            protocol_id=protocol["id"],
            first_launch_epoch=window["first_launch_epoch"],
            deadline_epoch=window["deadline_epoch"],
            source_window=entry(SOURCE / "execution_window/record.json"),
            additional_runtime_window_seconds=0,
        ),
    )
    checked_protocol(root)
    require(time.time() < window["deadline_epoch"], "original window expired during registration")
    base.status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=protocol["id"],
            original_B_resume_authorized=False,
        ),
    )
    return protocol


class Controller(lifecycle.LifecycleMixin, base.Controller):
    lifecycle_api = base

    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.protocol = checked_protocol(self.root)
        self.task_plan = read_ref(self.protocol["task_plan"])
        original, previous, _ = checked_parents()
        self.index = read_ref(self.protocol["cache_index"])
        self.results = {}
        for stage, directory, protocol in (
            ("shard00", SOURCE, original),
            ("shard02", PREVIOUS, previous),
            ("shard03", PREVIOUS, previous),
        ):
            result = checked(directory / stage / "result/record.json")
            require(
                checked(directory / stage / "exit/record.json")["returncode"] == 0,
                "inherited stage did not exit successfully",
            )
            self.results[stage] = base.check_result(protocol, stage, result, self.task_plan)
        self.active = {}
        self.stop = False
        self.host_event_count = 0
        prior_wait = json.loads((SOURCE / "queue/status.json").read_bytes()).get(
            "resource_wait_seconds", 0
        )
        self.wait_used = json.loads((PREVIOUS / "queue/status.json").read_bytes()).get(
            "resource_wait_seconds", 0
        )
        require(self.wait_used >= prior_wait, "cumulative resource wait decreased")
        self.deadline_epoch = self.protocol["absolute_deadline_epoch"]
        self.first_launch_epoch = checked(SOURCE / "execution_window/record.json")[
            "first_launch_epoch"
        ]
        self.deadline = time.monotonic() + self.deadline_epoch - time.time()

    def lifecycle_result_validator(self, stage, result):
        base.check_result(self.protocol, stage, result, self.task_plan)
        verification = read_ref(result["cache_tensor_verification"])
        parent_count, local_count = (183, 0) if stage == "shard01" else (741, 3)
        require(
            verification["protocol_id"] == self.protocol["id"]
            and verification["stage"] == stage
            and verification["index_id"] == self.index["id"]
            and verification["parent_tasks_strictly_verified"] == parent_count
            and verification["local_tasks_strictly_verified"] == local_count
            and verification["strict_payload_file_reads"] == parent_count + local_count
            and verification["cross_process_verification_waiver"] is False
            and verification["parent_gradient_payload_bytes_copied"] == 0,
            "actual cache tensor verification is incomplete or foreign",
        )
        if stage in self.active:
            require(
                verification["process_id"] == self.active[stage]["launch"]["pid"],
                "cache tensor verification belongs to another worker",
            )
        if stage == "shard01":
            expected = [
                t["task_id"]
                for t in self.task_plan["tasks"]
                if t["shard"] == 1 and t["index"] not in MISSING_INDICES
            ]
            require(
                result["reused_task_ids"] == expected
                and result["class_task_calls"] == 3
                and result["new_completed_rows"] == 26,
                "exact three-task supplement differs",
            )
        return result

    def acquire(self, stages):
        require(
            len(stages) == 1 and stages[0] in STAGES and not self.active,
            "single worker admission only",
        )
        stage = stages[0]
        index = base.STAGE_GPU[stage]
        admission = self.protocol["host_ram"][
            "coordinator_admission_bytes" if stage == "coordinator" else "shard_admission_bytes"
        ]
        specs = self.task_plan["parameter_spec"]
        parameter_bytes = sum(math.prod(s["shape"]) * 4 for s in specs)
        disk_admission = 2 * 7 * parameter_bytes + 32 * base.GIB
        while True:
            self.time_gate()
            started = time.monotonic()
            rows = {r["index"]: r for r in base.inventory()}
            memory = base.host_memory()
            require(
                shutil.disk_usage(self.root).free >= disk_admission,
                "insufficient new-task disk reserve",
            )
            lock = None
            if (
                memory["available_bytes"] >= admission
                and index in rows
                and base.eligible(rows[index], self.protocol)
            ):
                path = self.root / "locks" / ("gpu-" + rows[index]["uuid"] + ".lock")
                path.parent.mkdir(parents=True, exist_ok=True)
                lock = path.open("a")
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fresh = {r["index"]: r for r in base.inventory()}
                    if base.host_memory()["available_bytes"] >= admission and base.eligible(
                        fresh[index], self.protocol
                    ):
                        self.wait_used += time.monotonic() - started
                        self.time_gate()
                        return fresh, {index: lock}
                except BlockingIOError:
                    pass
                except BaseException:
                    lock.close()
                    raise
            if lock is not None:
                lock.close()
            self.update(
                "WAITING_FOR_IDLE_GPU_AND_HOST_RAM",
                waiting_stage=stage,
                host_admission_bytes=admission,
                host_observation=memory,
                gpu_observation=list(rows.values()),
            )
            time.sleep(min(base.POLL_SECONDS, max(0, self.deadline - time.monotonic())))
            self.wait_used += time.monotonic() - started

    def launch(self, stage, row, lock):
        self.time_gate()
        require(
            stage in STAGES
            and not self.active
            and stage not in self.results
            and not (self.root / stage / "launch/record.json").exists(),
            "single dispatch per registered stage",
        )
        require(row["index"] == base.STAGE_GPU[stage], "wrong physical GPU")
        if stage == "coordinator":
            require(
                set(self.results) == set(base.SHARD_STAGES)
                and (self.root / "complete_task_cache/record.json").is_file(),
                "coordinator not admitted",
            )
        base.verify_original_B_paused(self.protocol)
        fresh = next(r for r in base.inventory() if r["index"] == row["index"])
        require(base.eligible(fresh, self.protocol), "GPU no longer idle")
        directory = self.root / stage
        directory.mkdir(parents=True, exist_ok=True)
        command = base.worker_command(self.root, stage, row, self.protocol, self.deadline_epoch)
        original_worker = str(self.root / "implementation/finqa_v35_task_worker.py")
        require(command.count(original_worker) == 1, "unexpected original worker argv")
        worker = str(self.root / "recovery_implementation/finqa_v36_worker.py")
        command[command.index(original_worker)] = worker
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
            schema="v36_bounded_stage_launch.v1",
            at=now(),
            protocol_id=self.protocol["id"],
            stage=stage,
            pid=process.pid,
            birth=born,
            worker=worker,
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

    def validate_task_coverage(self, *, complete):
        module = _module(
            self.root / "recovery_implementation/finqa_v36_cache.py", __name__ + "_coverage"
        )
        return module.inspect_overlay(self.root, complete=complete)

    def worker_accounting(self):
        current = super().worker_accounting()
        prior = checked(PREVIOUS / "closeout_01/record.json")["total_elapsed_worker_wall_seconds"]
        current.update(
            prior_two_attempts_worker_wall_seconds=prior,
            all_attempts_exited_worker_hours=(prior + current["total_elapsed_worker_wall_seconds"])
            / 3600,
        )
        return current

    def run(self):
        require(
            Path(__file__).resolve()
            == self.root / "recovery_implementation/finqa_v36_controller.py",
            "run only the frozen V36 controller",
        )
        path = self.root / "queue/controller.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            publish(
                self.root / "queue/run_intent/record.json",
                dict(
                    schema="v36_one_controller_attempt.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    pid=os.getpid(),
                    birth=base.birth(os.getpid()),
                    automatic_retry=False,
                ),
            )
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            for sig in handlers:
                signal.signal(sig, lambda *_: setattr(self, "stop", True))
            try:
                self.run_group(("shard01",))
                self.time_gate()
                coverage = self.validate_task_coverage(complete=True)
                self.time_gate()
                publish(
                    self.root / "complete_task_cache/record.json",
                    dict(
                        schema="v36_all_tasks_complete.v1",
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
                        schema="v36_completed_fixed_point_supplement.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        status="COMPLETE",
                        numeric_pass=True,
                        coordinator_result=entry(self.root / "coordinator/result/record.json"),
                        cache_coverage=entry(self.root / "complete_task_cache/record.json"),
                        task_count=744,
                        state_count=1360,
                        reused_complete_tasks=741,
                        new_complete_tasks=3,
                        new_complete_task_rows=26,
                        global_recomputations=1,
                        API_calls=0,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        replayed_responses=0,
                        optimizer_steps=0,
                        original_B_resume_authorized=False,
                        previous_failures_reclassified=False,
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
                except BaseException as cache_error:
                    coverage = dict(cache_validation_failed=True, error=str(cache_error))
                body = dict(
                    error_type=type(error).__name__,
                    error=str(error),
                    stop_error=stop_error,
                    task_cache_coverage=coverage,
                    no_automatic_retry=True,
                    previous_failures_reclassified=False,
                )
                self.update("STOPPED_FAILURE_NO_RETRY", **body)
                publish(
                    self.root / "failure/record.json",
                    dict(
                        schema="v36_bounded_failure.v1",
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
        require(args.source_commit is not None, "committed implementation required")
        result = initialize(args.root, args.source_commit)
    elif args.action == "run":
        Controller(args.root).run()
        return
    else:
        result = checked_protocol(args.root)
    print(json.dumps(dict(id=result["id"], deadline_epoch=result["absolute_deadline_epoch"])))


if __name__ == "__main__":
    main()
