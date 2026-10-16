"""One explicitly authorized recovery after V38 stopped and V39 never migrated.

The first gate cold-restores the real Full389/298 response261 state, finishes
responses262..447, commits its original outer exactly once and one SFT to299.
Only its successful physical worker exit opens the remaining original matrix.
Neither historical failure is rewritten or represented as a clean handoff.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import finqa_v40_admission as admission
import finqa_v40_inheritance as inheritance
import finqa_v40_signals as stop_signals

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
PARENT_ROOT = SOURCE_ROOT / "production_resume_01/recovery_01"
V39_ROOT = SOURCE_ROOT / "production_resume_01/gpu6_resume_01"
ROOT = SOURCE_ROOT / "production_resume_01/recovery_02"
FAILED_HANDOFF = PARENT_ROOT / "controlled_handoff_gpu6_01"
RESOURCE_AUTHORIZATION = PARENT_ROOT / "resource_authorization_gpu6_20261012_01/record.json"
PARENT_PROTOCOL_ID = "28a3d931f15acc5240a07da7c126c42418c4ed50ab665811d072d1d290706462"
V39_IMPLEMENTATION_ID = "342c590101b97b3cc0e84c5fa9341fe0562e9778e5d5a5d046b80e75a28a76a9"
FILES = (
    "finqa_v40_controller.py",
    "finqa_v40_worker.py",
    "finqa_v40_admission.py",
    "finqa_v40_inheritance.py",
    "finqa_v40_evaluation.py",
    "finqa_v40_signals.py",
    "finqa_v40_replay.py",
    "finqa_v40_task_overlay.py",
)
ALLOWED_GPUS = admission.ALLOWED_GPUS
DISPATCH_ORDER = admission.DISPATCH_ORDER
RECOVERY_COORDINATE = (389, "Full")
RECOVERY_PILOT = dict(
    seed=389,
    arm="Full",
    step=298,
    training_stop_step=299,
    inherited_response_count=261,
    total_response_count=447,
    actual_new_response_calls=186,
    denominator=700,
    new_sampling_calls=0,
    API_calls=0,
    outer_commits=1,
    actual_optimizer_steps=1,
    worker_actual_zero_exit_required=True,
    remaining_matrix_before_acceptance=False,
)
CLASS_COMPLETION = dict(
    seed=251,
    arm="C-only",
    step=1192,
    inherited_shards=["shard02"],
    remaining_shards=["shard00", "shard01", "shard03"],
    inherited_task_count=186,
    remaining_task_count=558,
    window_seconds=4 * 3600,
    starts_at_first_remaining_shard_dispatch=True,
    shared_deadline_not_per_shard=True,
    only_class_phase_deadline_exception=True,
    original_outer_and_global_wait_budgets_reset=False,
    inherited_tasks_recomputed=False,
)


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Only the execution shell is adapted. Its historical V38 validator remains in
# a distinct module scope, with its original four-card scientific registration.
_bundle = inheritance.checked(V39_ROOT / "implementation/record.json")
inheritance.require(_bundle["id"] == V39_IMPLEMENTATION_ID, "V39 frozen source bundle changed")
_directory = (
    Path(__file__).resolve().parent
    if Path(__file__).resolve().parent.name == "implementation"
    else V39_ROOT / "implementation"
)
_shell = _directory / "finqa_v39_controller.py"
inheritance.require(
    hashlib.sha256(_shell.read_bytes()).hexdigest() == _bundle["sha256"][_shell.name],
    "unchanged V39 shell bytes required",
)
base = _module(_shell, __name__ + "_unchanged_shell")
parent = base.parent
verifier = base.verifier
require, checked, publish = parent.require, parent.checked, parent.publish
entry, read_ref, file_ref = parent.entry, parent.read_ref, parent.file_ref
now, sha, birth, status = parent.now, parent.sha, parent.birth, parent.status
DurablePause = parent.DurablePause
_original_parent_module = base._base_module


def __getattr__(name):
    return getattr(parent, name)


def checked_parent():
    protocol = verifier.checked_protocol(PARENT_ROOT)
    require(protocol["id"] == PARENT_PROTOCOL_ID, "original V38 protocol changed")
    return protocol


def verify_parent_stopped():
    protocol = checked_parent()
    failure = checked(PARENT_ROOT / "failure/record.json")
    queue = json.loads((PARENT_ROOT / "queue/status.json").read_bytes())
    require(
        failure["phase"] == queue["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and failure["protocol_id"] == queue["protocol_id"] == protocol["id"]
        and not queue["active_children"]
        and failure["stop_error"] is None
        and failure["actual_progress_audit_error"] is None,
        "parent is not a stopped, audited failure; no automatic handoff or retry",
    )
    launch = checked(PARENT_ROOT / "launch_01/record.json")
    require(birth(launch["pid"]) != str(launch["birth"]), "old controller is still live")
    abandoned = checked(FAILED_HANDOFF / "failure/record.json")
    require(
        abandoned["status"] == "STOPPED_NO_MIGRATION"
        and abandoned["controller_signalled"] is False
        and abandoned["workers_signalled"] is False
        and abandoned["continuation_callback_invoked"] is False,
        "V39 did not stop before migration as registered",
    )
    handoff_launch = checked(FAILED_HANDOFF / "run_intent/record.json")
    identity = handoff_launch["identity"]
    require(birth(identity["pid"]) != str(identity["birth"]), "failed handoff is still live")
    require(
        not (V39_ROOT / "protocol/record.json").exists()
        and not (V39_ROOT / "launch_01/record.json").exists(),
        "unexpected prior V39 scientific launch",
    )
    return protocol


def checked_source_bundle():
    source = checked(V39_ROOT / "implementation/record.json")
    require(source["id"] == V39_IMPLEMENTATION_ID, "unchanged V39 source seal required")
    old = verifier.checked_implementation(PARENT_ROOT)
    require(
        source["unchanged_parent_implementation"]
        == entry(PARENT_ROOT / "implementation/record.json"),
        "V39-to-V38 source binding changed",
    )
    for name, expected in source["sha256"].items():
        require(
            sha(V39_ROOT / "implementation" / name) == expected, "frozen source changed: " + name
        )
        if name in old["sha256"]:
            require(expected == old["sha256"][name], "original V38 scientific code changed")
    return source


def freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    source = checked_source_bundle()
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted source: " + name
        )
        sources[name] = raw
    for name, expected in source["sha256"].items():
        raw = (V39_ROOT / "implementation" / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "parent source changed while freezing")
        sources[name] = raw
    directory = Path(root) / "implementation"
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return publish(
        directory / "record.json",
        dict(
            schema="v40_committed_explicit_recovery_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            unchanged_v39_implementation=entry(V39_ROOT / "implementation/record.json"),
            unchanged_v38_implementation=entry(PARENT_ROOT / "implementation/record.json"),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )


def checked_implementation(root):
    root = Path(root).resolve()
    if root == PARENT_ROOT:
        return verifier.checked_implementation(root)
    require(root == ROOT, "fixed independent recovery_02 root required")
    manifest = checked(root / "implementation/record.json")
    source = checked_source_bundle()
    require(
        manifest["schema"] == "v40_committed_explicit_recovery_implementation.v1"
        and manifest["committed_files"] == list(FILES)
        and list(manifest["sha256"]) == [*FILES, *source["sha256"]]
        and manifest["unchanged_v39_implementation"]
        == entry(V39_ROOT / "implementation/record.json")
        and manifest["unchanged_v38_implementation"]
        == entry(PARENT_ROOT / "implementation/record.json"),
        "recovery implementation ownership changed",
    )
    for name, expected in manifest["sha256"].items():
        require(
            sha(root / "implementation" / name) == expected,
            "frozen recovery source changed: " + name,
        )
        if name in source["sha256"]:
            require(expected == source["sha256"][name], "frozen historical source changed")
    return manifest


def protocol_body(root, implementation, initial, *, at):
    root = Path(root)
    old = checked_parent()
    devices = checked(root / "device_scope_authorization/record.json")
    require(
        devices["user_instruction"] == "扩大范围，在满足显存要求的GPU上运行即可"
        and devices["allowed_gpu_indices"] == list(ALLOWED_GPUS)
        and devices["gpu_uuids"] == admission.GPU_UUIDS
        and devices["dispatch_priority"] == list(DISPATCH_ORDER)
        and devices["max_total_gpu_workers"] == 4
        and devices["old_gpu6_handoff_is_current_execution_authority"] is False,
        "new explicitly broadened device authority changed",
    )
    inherited = checked(root / "inheritance/record.json")
    body = copy.deepcopy({k: v for k, v in old.items() if k != "id"})
    for key in (
        "first_gate",
        "recovery_scope",
        "inherited_compute_seconds",
        "inherited_distribution_seconds",
    ):
        body.pop(key, None)
    body.update(
        schema="v40_explicit_durable_replay_recovery_protocol.v1",
        at=at,
        output_root=str(root),
        implementation_id=implementation["id"],
        source_commit=implementation["source_commit"],
        authority="用户明确要求：修复问题继续实验；失败后独立登记一次冷恢复，不重启旧控制器",
        audit=entry(root / "authorization/record.json"),
        parent_protocol=entry(PARENT_ROOT / "protocol/record.json"),
        parent_failure=entry(PARENT_ROOT / "failure/record.json"),
        failed_handoff=entry(FAILED_HANDOFF / "failure/record.json"),
        clean_handoff_claimed=False,
        failed_handoff_restarted=False,
        resource_authorization=entry(root / "device_scope_authorization/record.json"),
        historical_gpu6_resource_authorization=entry(RESOURCE_AUTHORIZATION),
        inheritance=entry(root / "inheritance/record.json"),
        initial_state_snapshot=entry(root / "initial_state/record.json"),
        original_initial_progress=old["initial_progress"],
        initial_progress=dict(
            completed_optimizer_updates=initial["completed_physical_updates"],
            remaining_optimizer_updates=initial["remaining_physical_updates"],
            completed_outer_updates=initial["completed_outers"],
            remaining_outer_updates=initial["remaining_outers"],
            **inherited["remaining_scientific_budget"],
        ),
        original_first_gate=old["first_gate"],
        original_accepted_pilot=entry(PARENT_ROOT / "pilot_acceptance/record.json"),
        recovery_pilot=copy.deepcopy(RECOVERY_PILOT),
        partial_class_completion=copy.deepcopy(CLASS_COMPLETION),
        partial_class_completion_authorization=entry(
            root / "class_completion_authorization/record.json"
        ),
        original_pilot_repeated=False,
        original_first_gate_relabelled=False,
        already_complete_evaluations_regenerated=False,
        allowed_gpu_indices=list(ALLOWED_GPUS),
        gpu_uuids=admission.GPU_UUIDS,
        dispatch_priority=list(DISPATCH_ORDER),
        cpu_affinity=admission.CPU_AFFINITY,
        max_gpu_workers=4,
        temporary_GPU6_only=False,
        broadened_scope_only_for_original_remaining_matrix=True,
        old_gpu6_handoff_is_current_execution_authority=False,
        temporary_GPU6_withdrawal=(
            "A sealed queue/gpu6_withdrawal/record.json disables only future GPU6 dispatch"
        ),
        device_admission_override=dict(
            original_scientific_evaluation_plan_unchanged=True,
            scoped_old_evaluator_device_check_adapter=True,
            overridden_fields=["allowed_gpu_indices", "minimum_free_mib"],
            minimum_free_mib="max(original minimum,73728)",
            physical_GPU_UUIDs_bound=True,
        ),
        inherited_resource_wait_seconds=inherited["inherited_resource_wait_seconds"],
        per_context_compute_and_phase_deadlines_in_inheritance=True,
        failed_handoff_wall_and_new_initialization_wall_charged_conservatively=True,
        original_budgets_reset=False,
        outer_and_global_budgets_reset=False,
        only_explicitly_authorized_class_deadline_extended=True,
        automatic_retry=False,
        stop_signal_audit=dict(
            received_signal_numbers_and_times=True,
            unknown_sender_attribution=True,
            original_stop_handlers_preserved=True,
            stop_signals_ignored=False,
        ),
        recovery_scope=dict(
            only_authorized_failed_stage="Full389_step298_replay_R3",
            durable_prefix=261,
            fixed_total=447,
            remaining_actual_responses=186,
            inherited_prefix_replayed=False,
            partial_response_reused=False,
            all_completed_stage_values_read_only=True,
            parent_task_caches_read_only=True,
            parent_tensors_copied=False,
            new_phase_outputs_only_in_new_episode=True,
            first_outer_commit_once=True,
            first_real_SFT_stop=299,
            remaining_original_matrix_after_actual_pilot_exit=True,
            prior_failure_records_unchanged=True,
            unknown_external_signal_source_fixed=False,
            partial_class_completion=copy.deepcopy(CLASS_COMPLETION),
        ),
    )
    return body


def prepare(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(
        root == ROOT and not root.exists(), "one independent recovery; do not overwrite or retry"
    )
    registered_at = now()
    verify_parent_stopped()
    implementation = freeze(root, source_commit)
    publish(
        root / "device_scope_authorization/record.json",
        dict(
            schema="v40_explicit_whole_host_device_scope.v1",
            at=registered_at,
            user_instruction="扩大范围，在满足显存要求的GPU上运行即可",
            allowed_gpu_indices=list(ALLOWED_GPUS),
            gpu_uuids=admission.GPU_UUIDS,
            cpu_affinity=admission.CPU_AFFINITY,
            dispatch_priority=list(DISPATCH_ORDER),
            max_total_gpu_workers=4,
            max_workers_per_gpu=1,
            minimum_idle_free_mib=parent.MINIMUM_FREE_MIB,
            fresh_idle_inventory_and_exclusive_current_uuid_lease_required=True,
            old_gpu6_handoff_is_current_execution_authority=False,
            existing_other_project_processes_may_be_interfered_with=False,
            mathematical_or_feedback_or_optimizer_dose_expanded=False,
            original_outer_and_global_wait_budgets_reset=False,
            gpu6_needed_only_after_other_eligible_priorities=True,
        ),
    )
    publish(
        root / "authorization/record.json",
        dict(
            schema="v40_explicit_failed_episode_recovery_authority.v1",
            at=registered_at,
            user_instruction="修复问题继续实验",
            source_commit=implementation["source_commit"],
            parent_failure=entry(PARENT_ROOT / "failure/record.json"),
            failed_handoff=entry(FAILED_HANDOFF / "failure/record.json"),
            resource_authorization=entry(root / "device_scope_authorization/record.json"),
            historical_gpu6_resource_authorization=entry(RESOURCE_AUTHORIZATION),
            recovery_pilot=copy.deepcopy(RECOVERY_PILOT),
            partial_class_recovery=copy.deepcopy(inheritance.PARTIAL_CLASS_AUTHORIZATION),
            allowed_gpu_indices=list(ALLOWED_GPUS),
            max_total_gpu_workers=4,
            original_budgets_reset=False,
            outer_and_global_budgets_reset=False,
            only_explicitly_authorized_class_deadline_extended=True,
            no_claim_of_fixing_unknown_signal_sender=True,
            old_controllers_restarted=False,
            automatic_retry=False,
            clean_handoff_claimed=False,
        ),
    )
    publish(
        root / "class_completion_authorization/record.json",
        dict(
            schema="v40_explicit_bounded_partial_class_completion.v1",
            at=registered_at,
            user_instruction="授权该有界补齐并继续原矩阵",
            scope=copy.deepcopy(CLASS_COMPLETION),
            original_parent_records_unchanged=True,
            original_class_deadline_not_rewritten=True,
            class_window_is_explicit_new_authorization=True,
            additional_optimizer_or_feedback_budget=0,
            automatic_retry=False,
        ),
    )
    inherited = inheritance.initialize_parent_recovery(root, PARENT_ROOT)
    actual = read_ref(inherited["actual_final_progress"])
    initial = publish(
        root / "initial_state/record.json",
        dict(
            **{k: v for k, v in actual.items() if k not in ("id", "schema", "at")},
            schema="v40_initial_actual_training_snapshot.v1",
            at=now(),
            source_snapshot=inherited["actual_final_progress"],
            actual_state_recomputed=False,
        ),
    )
    require(
        inherited["accepted_new_optimizer_updates"] == 1667
        and inherited["accepted_new_outer_updates"] == 4
        and initial["remaining_physical_updates"] == 4143
        and initial["remaining_outers"] == 11,
        "recovery is not the authorized actual 1667/4 progress boundary",
    )
    protocol = publish(
        root / "protocol/record.json", protocol_body(root, implementation, initial, at=now())
    )
    status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=protocol["id"],
            active_children=[],
            pilot_accepted=False,
            original_pilot_still_valid=True,
        ),
    )
    return protocol


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    if root == PARENT_ROOT:
        return checked_parent()
    require(root == ROOT, "fixed recovery_02 root required")
    implementation = checked_implementation(root)
    plan, initial = (
        checked(root / "protocol/record.json"),
        checked(root / "initial_state/record.json"),
    )
    require(
        {k: v for k, v in plan.items() if k != "id"}
        == protocol_body(root, implementation, initial, at=plan["at"]),
        "V40 recovery protocol changed",
    )
    verify_parent_stopped()
    admission.validate_plan(plan)
    require(plan["recovery_pilot"] == RECOVERY_PILOT, "the single recovery pilot scope changed")
    return plan


eligible = base.eligible
check_result = base.check_result
merged_intervals = base.merged_intervals


def own_command():
    raw = Path(f"/proc/{os.getpid()}/cmdline").read_bytes()
    return [part.decode() for part in raw.split(b"\0") if part]


class ContextRunner(base.ContextRunner):
    def is_partial_class_completion(self, stage):
        item = getattr(self, "inherited", None)
        if item is None or not item.get("partial_class_recovery") or stage not in parent.SHARDS:
            return False
        require(
            (self.context["seed"], self.context["arm"], self.context["step"])
            == (251, "C-only", 1192)
            and self.protocol["partial_class_completion"] == CLASS_COMPLETION
            and stage in CLASS_COMPLETION["remaining_shards"]
            and item["stage_bindings"]["shard02"]["protocol_scope"] == "parent",
            "partial class exception is only for the three explicitly authorized C251 shards",
        )
        return True

    def class_completion_window(self, stage, *, create=False):
        require(self.is_partial_class_completion(stage), "not the authorized partial class context")
        path = self.root / "class_recovery_window/record.json"
        if not path.exists():
            if not create:
                return None
            start = time.time()
            publish(
                path,
                dict(
                    schema="v40_single_bounded_class_completion_window.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    context_id=self.context["id"],
                    seed=251,
                    arm="C-only",
                    step=1192,
                    first_dispatched_shard=stage,
                    started_epoch=start,
                    deadline_epoch=start + CLASS_COMPLETION["window_seconds"],
                    window_seconds=CLASS_COMPLETION["window_seconds"],
                    allowed_stages=list(CLASS_COMPLETION["remaining_shards"]),
                    authorization=self.protocol["partial_class_completion_authorization"],
                    inherited_task_count=186,
                    remaining_task_count=558,
                    original_class_deadline_epoch=self.inherited["phase_deadlines_epoch"][
                        "class_gradients"
                    ],
                    original_outer_and_wait_budgets_reset=False,
                    automatic_retry=False,
                ),
            )
        value = checked(path)
        require(
            value["protocol_id"] == self.protocol["id"]
            and value["context_id"] == self.context["id"]
            and value["authorization"] == self.protocol["partial_class_completion_authorization"]
            and value["window_seconds"] == CLASS_COMPLETION["window_seconds"]
            and value["deadline_epoch"]
            == value["started_epoch"] + CLASS_COMPLETION["window_seconds"]
            and value["first_dispatched_shard"] in CLASS_COMPLETION["remaining_shards"]
            and value["allowed_stages"] == CLASS_COMPLETION["remaining_shards"],
            "registered one-shot class completion window changed",
        )
        return value

    def stage_limit(self, stage):
        if self.is_partial_class_completion(stage):
            window = self.class_completion_window(stage)
            remaining = (
                CLASS_COMPLETION["window_seconds"]
                if window is None
                else window["deadline_epoch"] - time.time()
            )
            if remaining <= 0:
                raise DurablePause("authorized shared four-hour class completion window exhausted")
            return "class_gradients", remaining
        return super().stage_limit(stage)

    def launch(self, stage, row, lease):
        self._lifecycle_launch_gate()
        require(
            stage in self.pending() and stage not in self.dispatched,
            "unregistered next recovery stage",
        )
        require(not (self.root / stage / "launch/record.json").exists(), "no automatic retry")
        self.controller.disk_gate(0)
        class_window = (
            self.class_completion_window(stage, create=True)
            if self.is_partial_class_completion(stage)
            else None
        )
        phase, budget = self.stage_limit(stage)
        current = time.monotonic()
        start = self.phase_started.setdefault(phase, current)
        original_deadline = (
            self.inherited["phase_deadlines_epoch"].get(phase)
            if getattr(self, "inherited", None) is not None
            else None
        )
        absolute_deadline = class_window["deadline_epoch"] if class_window else original_deadline
        # Absolute deadlines already include elapsed phase time. Do not charge
        # phase_started a second time for later siblings of the same class pass.
        remaining = budget if absolute_deadline is not None else budget - (current - start)
        if self.context.get("due_outer"):
            remaining = min(remaining, parent.OUTER_COMPUTE_SECONDS - self.compute_used)
        if remaining <= 0:
            raise DurablePause("original phase or outer budget exhausted before recovery dispatch")
        deadline_epoch = time.time() + remaining
        if absolute_deadline is not None:
            # Keep either the old absolute deadline or the one explicitly
            # authorized shared class window; no timestamp-roundtrip extension.
            deadline_epoch = min(deadline_epoch, absolute_deadline)
        if self.evaluation:
            arguments = [
                str(self.controller.root / "implementation/finqa_v40_evaluation.py"),
                "generate",
                "--stage",
                "generate",
                "--root",
                str(self.controller.root),
                "--seed",
                str(self.context["seed"]),
                "--arm",
                parent.ARM_KEYS[self.context["arm"]],
                "--gpu-index",
                str(row["index"]),
                "--deadline-epoch",
                str(deadline_epoch),
            ]
        else:
            arguments = [
                str(self.controller.root / "implementation/finqa_v40_worker.py"),
                "--root",
                str(self.controller.root),
                "--context",
                str(self.root),
                "--stage",
                stage,
                "--gpu-index",
                str(row["index"]),
                "--deadline-epoch",
                str(deadline_epoch),
            ]
        command = [
            "/usr/bin/taskset",
            "--cpu-list",
            self.protocol["cpu_affinity"][str(row["index"])],
            str(parent.PYTHON),
            "-u",
            *arguments,
        ]
        directory = self.root / stage
        directory.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        with (directory / "worker.log").open("xb") as stream:
            process = subprocess.Popen(
                command,
                cwd=REPO,
                env=parent.worker_environment(row),
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        launch = dict(
            schema="v40_owned_recovery_stage_launch.v1",
            at=now(),
            protocol_id=self.protocol["id"],
            context_id=self.context["id"],
            stage=stage,
            pid=process.pid,
            birth=birth(process.pid),
            worker=arguments[0],
            command=command,
            gpu_index=row["index"],
            gpu_uuid=row["uuid"],
            deadline_epoch=deadline_epoch,
            source_checkpoint=self.context.get("checkpoint"),
            no_automatic_retry=True,
            inherited_completed_stages_not_dispatched=True,
            recovery_pilot=getattr(self, "recovery_pilot", False),
            partial_class_completion_window=(
                entry(self.root / "class_recovery_window/record.json") if class_window else None
            ),
        )
        self.active[stage] = dict(
            process=process,
            launch=launch,
            lock=lease,
            started_monotonic=started,
            stage_deadline_monotonic=current + remaining,
        )
        self.dispatched.add(stage)
        require(launch["birth"] is not None, "worker exited before ownership was established")
        self.active[stage]["launch"] = publish(directory / "launch/record.json", launch)
        self.update("RUNNING")

    def lifecycle_result_validator(self, stage, result):
        super().lifecycle_result_validator(stage, result)
        if not getattr(self, "recovery_pilot", False):
            return
        if stage == "replay_R3":
            require(
                result["restored_completed_responses"] == result["inherited_response_count"] == 261
                and result["replayed_responses"] == result["actual_new_response_calls"] == 186
                and result["response_count"] == result["cumulative_complete_response_count"] == 447,
                "pilot must restore261 and actually replay only the remaining186 responses",
            )
        elif stage == "train":
            require(
                result["initial_step"] == 298
                and result["committed_step"] == 299
                and result["actual_optimizer_steps"] == 1
                and result["outer_committed"] is True
                and result["registered_training_stop_step"] == 299
                and result["execution_boundary_policy_protocol_id"] == self.protocol["id"],
                "registered outer298 + one real SFT299 recovery gate was skipped",
            )


class Controller(base.Controller):
    def __init__(self, root=ROOT):
        super().__init__(root)
        self.pilot_accepted = False
        self._pilot_installed = False
        self._remaining_frontier_installed = False
        self._pilot_context_id = None
        self._registered_at = datetime.fromisoformat(
            checked(self.root / "authorization/record.json")["at"]
        ).timestamp()
        self._original_inherited_wait = self.inherited["inherited_resource_wait_seconds"]

    def _install_context(self, item, *, recovery_pilot=False):
        directory = Path(item["new_context_directory"])
        context = read_ref(item["original_context"])
        require(
            inheritance.resolve_origin_context(directory, self.protocol)
            == Path(item["origin_context_directory"]),
            "parent context alias changed",
        )
        runner = ContextRunner(self, directory, context)
        runner.inherited, runner.recovery_pilot = item, recovery_pilot
        for stage, binding in item["stage_bindings"].items():
            if binding["protocol_scope"] != "parent":
                continue
            result, exited = read_ref(binding["result"]), read_ref(binding["exit"])
            require(exited["returncode"] == 0, "completed inherited stage lacks actual zero exit")
            check_result(read_ref(item["parent_protocol"]), stage, result, runner.task_plan)
            runner.results[stage] = result
            runner.dispatched.add(stage)
        runner.compute_used = item["inherited_compute_seconds"]
        require(
            runner.compute_used < parent.OUTER_COMPUTE_SECONDS,
            "inherited outer compute budget exhausted",
        )
        if recovery_pilot:
            require(
                (context["seed"], context["arm"], context["step"]) == (389, "Full", 298)
                and set(runner.results) == {*parent.SHARDS, "virtual_point"}
                and runner.pending() == ["replay_R3"],
                "wrong registered recovery pilot frontier",
            )
        self.runs.append(runner)
        self.active_coordinate[(context["seed"], context["arm"])] = runner
        runner.update("INHERITED_COMPLETED_PHASES_READY")
        return runner

    def create_context(self, coordinate, *, pilot=False):
        if not pilot:
            require(
                self.pilot_accepted, "remaining matrix is locked until actual recovery pilot exit"
            )
            return parent.Controller.create_context(self, coordinate, pilot=False)
        require(
            coordinate == RECOVERY_COORDINATE and not self._pilot_installed and not self.runs,
            "one installation of the explicitly authorized recovery pilot",
        )
        candidates = [
            item
            for item in self.inherited["context_inheritances"]
            if (
                read_ref(item["original_context"])["seed"],
                read_ref(item["original_context"])["arm"],
                read_ref(item["original_context"])["step"],
            )
            == (389, "Full", 298)
        ]
        require(len(candidates) == 1, "exactly one Full389/298 restored context required")
        runner = self._install_context(candidates[0], recovery_pilot=True)
        self._pilot_context_id = runner.context["id"]
        self._pilot_installed = True
        return runner

    def enqueue_remaining(self):
        if not self.pilot_accepted:
            return
        if not self._remaining_frontier_installed:
            for item in self.inherited["context_inheritances"]:
                if read_ref(item["original_context"])["id"] != self._pilot_context_id:
                    self._install_context(item)
            self._remaining_frontier_installed = True
        return parent.Controller.enqueue_remaining(self)

    def accept_finished(self, runner):
        if runner.reported_finished or not runner.finished:
            return
        if self.pilot_accepted:
            return parent.Controller.accept_finished(self, runner)
        require(
            getattr(runner, "recovery_pilot", False)
            and not runner.active
            and runner.context["id"] == self._pilot_context_id,
            "only a naturally exited recovery pilot may unlock the matrix",
        )
        result = runner.results["train"]
        require(
            result["initial_step"] == 298
            and result["committed_step"] == 299
            and result["actual_optimizer_steps"] == 1
            and result["outer_committed"] is True,
            "pilot did not commit exactly one outer and one actual SFT",
        )
        exited = checked(runner.root / "train/exit/record.json")
        require(
            exited["returncode"] == 0
            and exited["stop_requested"] is False
            and exited["protocol_id"] == self.protocol["id"]
            and exited["context_id"] == runner.context["id"],
            "pilot train has not really exited zero",
        )
        # Skip the historical hard-coded C137/1192 first gate, not its real
        # checkpoint/outer validation. The new gate above has a different owner.
        self.pilot_accepted = True
        try:
            parent.Controller.accept_finished(self, runner)
            publish(
                self.root / "pilot_acceptance/record.json",
                dict(
                    schema="v40_actual_recovered_outer_and_SFT_accepted.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    context_id=runner.context["id"],
                    context=entry(runner.root / "context/record.json"),
                    train_result=entry(runner.root / "train/result/record.json"),
                    train_actual_exit=entry(runner.root / "train/exit/record.json"),
                    replay_result=entry(runner.root / "replay_R3/result/record.json"),
                    distribution_result=entry(runner.root / "distribution/result/record.json"),
                    next_checkpoint=parent.checkpoint_reference(result["next_checkpoint"]),
                    outer_checkpoint=parent.checkpoint_reference(result["outer_checkpoint"]),
                    restored_completed_responses=261,
                    actual_new_response_calls=186,
                    cumulative_complete_response_count=447,
                    outer_commits=1,
                    actual_optimizer_steps=1,
                    committed_step=299,
                    API_calls=0,
                    new_sampling_calls=0,
                    remaining_matrix_dispatch_authorized=True,
                    parent_failures_reclassified=False,
                ),
            )
        except BaseException:
            self.pilot_accepted = False
            raise

    def _record_signal_audit(self, evidence):
        publish(
            self.root / "signal_audit/record.json",
            dict(
                schema="v40_controller_stop_signal_audit.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                **evidence,
                original_stop_handlers_preserved=True,
                automatic_retry=False,
            ),
        )

    def _stop_audit(self):
        path = self.root / "failure/record.json"
        if not path.exists() or (self.root / "stop_audit/record.json").exists():
            return
        failure = checked(path)
        signals = self.root / "signal_audit/record.json"
        workers = sorted(self.root.glob("contexts/*/*/*/*/signal_audit/record.json"))
        workers += sorted(self.root.glob("evaluations/*/*/signal_audit/record.json"))
        failures = sorted(self.root.glob("contexts/*/*/*/*/failure/record.json"))
        failures += sorted(self.root.glob("evaluations/*/*/failure/record.json"))
        worker_stops = [(item, checked(item)) for item in failures]
        observed_worker_signal = any(
            value.get("stop_evidence", {}).get("received_signals") for _, value in worker_stops
        )
        observed_controller_signal = (
            bool(checked(signals).get("received_signals")) if signals.exists() else False
        )
        observed_separate_worker_signal = any(
            checked(item).get("received_signals") for item in workers
        )
        observed_signal = bool(
            observed_worker_signal or observed_controller_signal or observed_separate_worker_signal
        )
        cooperative_response_pause = any(
            value.get("failure_classification") == "COOPERATIVE_RESPONSE_BOUNDARY_PAUSE"
            and value.get("durable_replay_checkpoint") is not None
            for _, value in worker_stops
        )
        publish(
            self.root / "stop_audit/record.json",
            dict(
                schema="v40_observed_stop_cause_audit.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                failure=entry(path),
                controller_signal_audit=entry(signals) if signals.exists() else None,
                worker_signal_audits=[entry(item) for item in workers],
                worker_stop_records=[entry(item) for item, _ in worker_stops],
                received_stop_signal_observed=observed_signal,
                cooperative_response_pause_observed=cooperative_response_pause,
                stop_classification=(
                    "COOPERATIVE_RESPONSE_BOUNDARY_PAUSE"
                    if cooperative_response_pause
                    else "OBSERVED_STOP_SIGNAL"
                    if observed_signal
                    else "REGISTERED_BOUNDARY_STOP"
                    if failure["error_type"] == "DurablePause"
                    else "UNCLASSIFIED_STAGE_OR_CONTROLLER_FAILURE"
                ),
                signal_sender_attribution="unknown" if observed_signal else "not_observed",
                numerical_failure_inferred_from_signal=False,
                failed_stage_automatically_retried=False,
                existing_parent_failures_unchanged=True,
            ),
        )

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run only the newly committed frozen V40 controller",
        )
        elapsed = time.time() - self._registered_at
        require(math.isfinite(elapsed) and elapsed >= 0, "initialization wall clock reversed")
        charged = math.ceil(self._original_inherited_wait + elapsed)
        self.inherited["inherited_resource_wait_seconds"] = charged
        self.resource_wait_used = charged
        self._resource_waiting = True
        self._resource_accounting_at = time.monotonic()
        self.resource_wait_gate()
        publish(
            self.root / "launch_01/record.json",
            dict(
                schema="v40_explicit_single_recovery_controller_launch.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                pid=os.getpid(),
                birth=birth(os.getpid()),
                command=own_command(),
                inherited_resource_wait_before_initialization=self._original_inherited_wait,
                initialization_wall_seconds=elapsed,
                inherited_global_wait_at_dispatch=charged,
                independent_recovery_not_clean_handoff=True,
                automatic_restart=False,
            ),
        )
        try:
            with stop_signals.audit_signal_installations(sink=self._record_signal_audit):
                return parent.Controller.run(self)
        finally:
            self._stop_audit()


def _routed_module(path, name):
    if (
        Path(path).name == "finqa_v37_evaluation.py"
        and Path(path).parent == ROOT / "implementation"
    ):
        return _original_parent_module(Path(path).with_name("finqa_v40_evaluation.py"), name)
    return _original_parent_module(path, name)


# Adapt only the distinct execution modules. Do not alter the historical
# verifier, any old file on disk, any old protocol or any original mathematics.
base.ROOT = ROOT
base.checked_protocol = checked_protocol
base.checked_implementation = checked_implementation
base.inheritance = inheritance
base.ALLOWED_GPUS = ALLOWED_GPUS
parent.ALLOWED_GPUS = DISPATCH_ORDER
parent.FIRST = RECOVERY_COORDINATE
parent.checked_protocol = checked_protocol
parent.checked_implementation = checked_implementation
parent.ContextRunner = ContextRunner
parent.eligible = eligible
parent.check_result = check_result
parent._module = _routed_module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "prepare":
        require(args.source_commit is not None, "committed new source required")
        result = prepare(args.root, source_commit=args.source_commit)
    elif args.action == "run":
        success = Controller(args.root).run()
        raise SystemExit(0 if success else 1)
    else:
        result = checked_protocol(args.root)
    print(json.dumps(dict(id=result["id"], root=str(args.root)), sort_keys=True))


if __name__ == "__main__":
    main()
