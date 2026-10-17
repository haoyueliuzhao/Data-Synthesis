"""V52 one explicitly authorized response121 recovery and safe-only later recovery.

The initial transition consumes the user's new recovery authorization for one
pinned unknown-sender SIGTERM stop. It does not change the old unsafe decision
or authorize automatic retries of future unknown signals.
"""

from __future__ import annotations

import copy
import hashlib
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import finqa_v42_inheritance as previous

base, old = previous.base, previous.old
require, checked, entry, read_ref = old.require, old.checked, old.entry, old.read_ref
publish, file_ref, digest = old.publish, old.file_ref, old.digest
SHARDS, STAGES = previous.SHARDS, previous.STAGES
checkpoint_metadata = previous.checkpoint_metadata
_actual_context = previous._actual_context
GIB = 1024**3
SCHEMA = "v52_response121_authorized_recovery_inheritance.v1"
ALIAS_SCHEMA = "v52_per_stage_original_context_alias.v1"
CACHE_SCHEMA = "v41_complete_read_only_task_cache_view.v1"
PARTIAL_CACHE_SCHEMA = "v43_same_point_partial_task_cache_union.v1"
PROTOCOL_SCHEMA = "v52_response121_supervised_protocol.v1"
PRODUCTION_ROOT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/"
    "v25_training_replication_01/production_resume_01"
)
PARENT_ROOT = PRODUCTION_ROOT / "host_memory_admission_01"
SOURCE_ROOT = PRODUCTION_ROOT / "dual_gpu0_gpu6_01"
ROOT = PRODUCTION_ROOT / "signal_checkpoint_recovery_03"
ALLOWED_GPU_INDICES = (0, 1, 3, 4, 5, 6, 7)
PARENT_IMPLEMENTATION_ID = "c32c3a60ec4b3fa5c943bfa740cf53bdf985d7da7587f664c068ea8058857a6d"
SOURCE_PROTOCOL_SCHEMA = "v51_dual_gpu_two_worker_supervised_protocol.v1"
SOURCE_INHERITANCE_SCHEMA = "v51_dual_gpu_two_worker_inheritance.v1"
SOURCE_PROTOCOL_ID = "6a0c83d2af5bd2d65a4635ab6fe494be83f45b488eaed6f7cd156c3daf724055"
SOURCE_IMPLEMENTATION_ID = "d3c37529146a5109abbfb5a1d0505d433bece4fa6d0911d6b04fe6e4c4e1f952"
SOURCE_CONTEXT_ID = "fc5e65c75ae05e1a0edede9b9e78aa73a5a8fe66e2d7c57d88a0edb03ff195fa"
SOURCE_FAILURE_ID = "57016497eff3ce1519810c2fb84b8a09b35a055672fafc9b6dd38733909a2f42"
SOURCE_WORKER_FAILURE_ID = "0ca006a3e2a13fb6133f7d818e45dd67a7e64045b7931f2995c31f0d860b2f14"
SOURCE_CONTEXT_RELATIVE = Path("contexts/seed389/full/step1192_outer")
SOURCE_CHECKPOINT_RELATIVE = SOURCE_CONTEXT_RELATIVE / "replay_R3/checkpoints/response000121"
SOURCE_CHECKPOINT_ID = "e93a031a2b53597c8916065505841b423686a218978075f3194bfcbf6f8a9000"
SOURCE_CHECKPOINT_SHA256 = "d928c206c36c2ae7e7fc206f80785ead590ba1f3f7f319407045c3dd12c876d9"
SOURCE_DENIAL_REASON = (
    "unsafe_or_unsupported_recovery: "
    "controller_failure_requires_one_matching_resource_worker_not_stop_consequences"
)
SOURCE_PROCESS_IDENTITIES = {
    "supervisor": dict(pid=3592725, birth="458506298"),
    "controller": dict(pid=54311, birth="460924335"),
    "worker": dict(pid=1345126, birth="465452011"),
}
EXPECTED_REPLAYS = {
    (389, "C-only", 1192): dict(
        cursor=240,
        total=419,
        checkpoint_id="dd0003e7100fc18541c1fe82cd47ae4ed02e7bbda128069163dbdd03ba12a48d",
    ),
    (389, "Full", 894): dict(
        cursor=133,
        total=540,
        checkpoint_id="23d8daf44fc1de8697828f664dc8ce14c7253fea1a744c9b70bb5240b0981b93",
    ),
}
R3_REFERENCE = PARENT_ROOT / (
    "contexts/seed389/c_only/step1192_outer/replay_R3/checkpoints/response000240/record.json"
)
R3_MATH_FILES = {
    "finqa_v19_optimized_replay.py",
    "finqa_v32_replay_variants.py",
    "finqa_v33_activation_residency.py",
    "fixed_kernel_anchored_canonical_saves_20260916.py",
    "fixed_kernel_anchored_saved_tensors_20260916.py",
    "fixed_kernel_anchored_segmented_replay_20260916.py",
    "fixed_kernel_anchored_sources_gpu_gate_20260916.py",
}


def _verify_replay_backend(binding, context):
    """An allocator shell must not change the original saved-prefix mathematics."""
    saved = checked(R3_REFERENCE)
    require(
        saved["id"] == EXPECTED_REPLAYS[(389, "C-only", 1192)]["checkpoint_id"],
        "original R3 mathematical reference changed",
    )
    expected = copy.deepcopy(saved["binding"]["backend_identity"])
    expected["context_id"] = context["id"]
    require(
        binding["backend_identity"] == expected
        and expected["variant"] == "R3"
        and binding["replay_state_adapter"] == saved["binding"]["replay_state_adapter"],
        "saved response prefix R3 mathematical backend changed",
    )
    implementation = checked(PARENT_ROOT / "implementation/record.json")
    sources = expected["source_binding"]["sources"]
    require(
        implementation["id"] == PARENT_IMPLEMENTATION_ID
        and len(implementation["sha256"]) == 81
        and set(sources) == R3_MATH_FILES,
        "original R3 scientific source ownership changed",
    )
    for name, expected_sha in sources.items():
        require(
            implementation["sha256"][name] == expected_sha
            and old.sha(PARENT_ROOT / "implementation" / name) == expected_sha,
            "original R3 mathematics/source digest changed: " + name,
        )


def _check_paused_replay_resources(resources):
    """Original resource gates on observed boundaries, without inventing a release."""
    cap, reserve, rss = 76 * GIB, 2 * GIB, 192 * GIB
    require(
        resources["all_gates_passed"] is True
        and resources["limits_unchanged"] is True
        and resources["maximum_allocated_bytes"] == cap
        and resources["minimum_device_free_bytes"] == reserve
        and resources["peak_resets_before_model_load"] == 1
        and resources["peak_resets_after_model_loading_begins"] == 0
        and resources["helper_peak_reset_calls"] == 0,
        "parent lifetime resource contract failed",
    )
    observations = resources["observations"]
    require(
        observations
        and observations[-1]["label"] == "replay.after_response"
        and observations[-1]["context"]["cooperative_stop_pending"] is True
        and any(row["label"] == "after_model_load.after_cleanup" for row in observations),
        "paused replay lacks its actual model-load and complete-response boundaries",
    )
    for row in observations:
        require(
            all(
                row[key] is True
                for key in ("passed", "allocated_pass", "free_pass", "deadline_pass")
            )
            and row["stop_requested"] is False
            and row["deadline_epoch"] is None
            and row["deadline_limit_enforced"] is False
            and row["wallclock_limits_removed"] is True
            and row["limits"]
            == dict(allocated_memory_limit_bytes=cap, free_memory_reserve_bytes=reserve),
            "parent resource observation failed",
        )
        require(
            all(
                type(row[key]) is int and row[key] >= 0
                for key in (
                    "allocated_bytes",
                    "reserved_bytes",
                    "peak_allocated_bytes",
                    "peak_reserved_bytes",
                    "free_bytes",
                    "total_bytes",
                )
            )
            and row["allocated_bytes"] <= row["peak_allocated_bytes"] <= cap
            and row["allocated_bytes"] <= row["reserved_bytes"] <= row["peak_reserved_bytes"]
            and row["peak_allocated_bytes"] <= row["peak_reserved_bytes"]
            and row["free_bytes"] <= row["total_bytes"]
            and (not row["boundary"] or row["free_bytes"] >= reserve),
            "parent GPU resource values violate original limits",
        )
        host = row["host"]
        require(
            all(host[key] is True for key in ("passed", "rss_pass", "available_pass"))
            and host["rss_limit_bytes"] == rss
            and host["available_reserve_bytes"] == 96 * GIB
            and 0 <= host["rss_bytes"] <= host["peak_rss_bytes"] <= rss
            and host["available_bytes"] >= 96 * GIB,
            "parent host resource values violate original limits",
        )
    boundaries = [row for row in observations if row["boundary"]]
    host = resources["host"]
    require(
        boundaries
        and resources["observed_peak_allocated_bytes"]
        == max(row["peak_allocated_bytes"] for row in observations)
        and resources["observed_minimum_boundary_free_bytes"]
        == min(row["free_bytes"] for row in boundaries)
        and host["all_passed"] is True
        and host["rss_limit_bytes"] == rss
        and host["available_reserve_bytes"] == 96 * GIB
        and host["max_observed_peak_rss_bytes"]
        == max(row["host"]["peak_rss_bytes"] for row in observations)
        and host["min_observed_available_bytes"]
        == min(row["host"]["available_bytes"] for row in observations),
        "parent resource summary contradicts its observations",
    )


def _response_state_sha256(path):
    """Hash the one small saved response accumulator without deserializing tensors."""
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _inspect_explicit_source_stop(parent, protocol):
    """Accept only the separately authorized V51 event, not a generic signal retry."""
    require(
        parent == SOURCE_ROOT
        and protocol["schema"] == SOURCE_PROTOCOL_SCHEMA
        and protocol["id"] == SOURCE_PROTOCOL_ID
        and protocol["output_root"] == protocol["supervision_root"] == str(parent)
        and protocol["allowed_gpu_indices"] == [0, 6]
        and protocol["max_gpu_workers"] == protocol["independent_total_worker_limit"] == 2
        and protocol["max_workers_per_gpu"] == 1,
        "initial recovery must consume the exact stopped V51 attempt and resource scope",
    )
    source_implementation = checked(parent / "implementation/record.json")
    scientific_implementation = checked(PARENT_ROOT / "implementation/record.json")
    require(
        source_implementation["id"] == protocol["implementation_id"] == SOURCE_IMPLEMENTATION_ID
        and len(source_implementation["sha256"]) == 90
        and scientific_implementation["id"] == PARENT_IMPLEMENTATION_ID
        and len(scientific_implementation["sha256"]) == 81
        and all(
            source_implementation["sha256"].get(name) == value
            for name, value in scientific_implementation["sha256"].items()
        ),
        "frozen V51 package or original 81-file scientific ownership changed",
    )
    directory = parent / SOURCE_CONTEXT_RELATIVE
    replay = directory / "replay_R3"
    context = checked(directory / "context/record.json")
    require(
        context["schema"] == "v37_actual_production_context.v1"
        and context["id"] == SOURCE_CONTEXT_ID
        and (context["seed"], context["arm"], context["step"]) == (389, "Full", 1192)
        and context["due_outer"] is True
        and context["run_root"] == context["outer_root"] == str(directory),
        "authorized Full389 step1192 scientific context changed",
    )
    paths = {
        "supervisor": parent / "supervisor/launch/record.json",
        "controller": parent / "launch_01/record.json",
        "worker": replay / "launch/record.json",
    }
    owners = {name: checked(path) for name, path in paths.items()}
    for name, owner in owners.items():
        expected = SOURCE_PROCESS_IDENTITIES[name]
        require(
            owner["pid"] == expected["pid"] and str(owner["birth"]) == expected["birth"],
            "authorized source process identity changed: " + name,
        )
        old._stopped(owner)
    require(
        owners["supervisor"]["protocol"] == entry(parent / "protocol/record.json")
        and owners["controller"]["protocol_id"] == SOURCE_PROTOCOL_ID,
        "source supervisor/controller protocol ownership changed",
    )
    queue = read_ref(file_ref(parent / "queue/status.json"))
    failure = checked(parent / "failure/record.json")
    require(
        failure["id"] == SOURCE_FAILURE_ID
        and failure["protocol_id"] == queue["protocol_id"] == SOURCE_PROTOCOL_ID
        and failure["phase"] == queue["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and failure["error_type"] == "ValueError"
        and failure["error"] == "worker reported failure: replay_R3"
        and failure["stop_error"] is None
        and failure["actual_progress_audit_error"] is None
        and queue["active_children"] == []
        and queue["pilot_accepted"] is True
        and len(queue["completed_training_coordinates"]) == 8
        and len(queue["completed_evaluation_coordinates"]) == 8
        and not (parent / "attempts/attempt0002").exists()
        and not (parent / "scoring").exists(),
        "source is not the exact unscored, fully stopped eight-endpoint frontier",
    )
    actual_exit = checked(parent / "supervisor/attempt0001/actual_exit/record.json")
    denial_path = parent / "supervisor/attempt0001/recovery_decision/record.json"
    denial = checked(denial_path)
    closeout = checked(parent / "supervisor/closeout/record.json")
    require(
        actual_exit["attempt_number"] == 1
        and actual_exit["attempt_root"] == str(parent)
        and actual_exit["pid"] == owners["controller"]["pid"]
        and str(actual_exit["birth"]) == str(owners["controller"]["birth"])
        and actual_exit["returncode"] == 1
        and actual_exit["manual_stop_requested"] is False
        and actual_exit["stop_forwarded"] is False
        and denial["allowed"] is False
        and denial["reason"] == SOURCE_DENIAL_REASON
        and closeout["status"] == "STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY"
        and closeout["final_attempt"] == 1
        and all(
            closeout["decision"][key] == denial[key]
            for key in ("allowed", "reason", "evidence_refs")
        ),
        "old unsafe automatic-recovery decision must be retained with its actual controller exit",
    )
    stopped, exited = checked(replay / "failure/record.json"), checked(replay / "exit/record.json")
    require(
        stopped["id"] == SOURCE_WORKER_FAILURE_ID
        and all(
            value["protocol_id"] == SOURCE_PROTOCOL_ID
            and value["context_id"] == SOURCE_CONTEXT_ID
            and value["stage"] == "replay_R3"
            for value in (owners["worker"], stopped, exited)
        )
        and owners["worker"]["gpu_index"] == 0
        and owners["worker"]["gpu_uuid"] == protocol["gpu_uuids"]["0"]
        and stopped["error_type"] == "ReplayPaused"
        and stopped["error"] == "replay paused at complete response 121"
        and stopped["failure_classification"] == "COOPERATIVE_RESPONSE_BOUNDARY_PAUSE"
        and stopped["API_calls"] == 0
        and stopped["original_mathematical_functions_unchanged"] is True
        and exited["returncode"] == -15
        and exited["stop_requested"] is True
        and not (replay / "result/record.json").exists(),
        "only the explicitly identified response121 SIGTERM interruption may be resumed",
    )
    stop = stopped["stop_evidence"]
    receipts = stop["received_signals"]
    require(
        stop["stop_requested"] is True
        and stop["stop_reason"] == "signal:15"
        and stop["sender_attribution"] == "unknown"
        and stop["signals_ignored"] is False
        and stop["automatic_restart"] is False
        and len(receipts) == 1
        and receipts[0]["signal_number"] == 15
        and receipts[0]["sender_identity_available"] is False
        and receipts[0]["sender_pid"] is None
        and receipts[0]["received_epoch"] == 1792235778.5961702,
        "the one authorized unknown-sender signal receipt changed",
    )
    _check_paused_replay_resources(stopped["resources"])
    checkpoint_path = parent / SOURCE_CHECKPOINT_RELATIVE / "record.json"
    checkpoint = checked(checkpoint_path)
    require(
        checkpoint["id"] == SOURCE_CHECKPOINT_ID
        and checkpoint["schema"] == "v19_response_boundary_checkpoint.v1"
        and checkpoint["cursor"] == 121
        and checkpoint["binding"]["response_count"] == 431
        and checkpoint["binding"]["execution_profile_id"] == SOURCE_CONTEXT_ID
        and checkpoint["state_sha256"] == SOURCE_CHECKPOINT_SHA256
        and checkpoint["response_prefix_complete"] is True
        and checkpoint["full_replay_complete"] is False
        and checkpoint["no_feedback_generation"] is True
        and checkpoint["optimizer_steps_performed"] == 0
        and stopped["durable_replay_checkpoint"] == checkpoint
        and stopped["response_pause_report"]["completed_responses"] == 121
        and stopped["response_pause_report"]["restored_completed_responses"] == 0
        and stopped["response_pause_report"]["response_checkpoint_binding"] == checkpoint["binding"]
        and _response_state_sha256(checkpoint_path.with_name("state.pt"))
        == SOURCE_CHECKPOINT_SHA256,
        "the exact actual response121 checkpoint metadata or state bytes changed",
    )
    failed_workers = []
    for path in sorted(parent.glob("contexts/seed*/*/step*/*/launch/record.json")) + sorted(
        parent.glob("evaluations/*/generate/launch/record.json")
    ):
        stage_root = path.parent.parent
        launch = checked(path)
        stage_exit = checked(stage_root / "exit/record.json")
        old._stopped(launch)
        require(
            launch["protocol_id"] == stage_exit["protocol_id"] == SOURCE_PROTOCOL_ID
            and launch["context_id"] == stage_exit["context_id"]
            and launch["stage"] == stage_exit["stage"],
            "source worker exit ownership changed",
        )
        if (stage_root / "failure/record.json").exists():
            failed_workers.append(stage_root)
        else:
            require(
                stage_exit["returncode"] == 0
                and stage_exit["stop_requested"] is False
                and (stage_root / "result/record.json").exists(),
                "another source worker is incomplete or unexplained",
            )
    require(failed_workers == [replay], "this authorization cannot recover another failed worker")
    progress = checked(parent / "actual_final_progress/record.json")
    full = [row for row in progress["arms"] if (row["seed"], row["arm"]) == (389, "Full")]
    require(
        progress["endpoint_scores_or_answers_read"] is False
        and progress["original_state_or_feedback_modified"] is False
        and progress["remaining_physical_updates"] == 298
        and progress["remaining_outers"] == 1
        and len(full) == 1
        and full[0]["step"] == 1192
        and full[0]["due_outer"] is True
        and full[0]["outer_done"] == [298, 596, 894]
        and full[0]["checkpoint"] == context["checkpoint"]
        and not (directory / "distribution").exists()
        and not (directory / "train").exists()
        and not (Path(context["arm_root"]) / "training/step1192_outer").exists()
        and not (Path(context["arm_root"]) / "result/record.json").exists(),
        "outer1192 or real training advanced beyond the explicitly authorized pending point",
    )
    return dict(
        allowed=True,
        reason="explicit_user_authorized_once_from_exact_response121_after_unknown_SIGTERM",
        explicit_initial_recovery_exception=True,
        automatic_recovery_of_this_old_failure_allowed=False,
        old_unsafe_decision_reclassified=False,
        old_unsafe_decision=entry(denial_path),
        controller_failure=entry(parent / "failure/record.json"),
        worker_failure=entry(replay / "failure/record.json"),
        supervisor_closeout=entry(parent / "supervisor/closeout/record.json"),
        actual_controller_exit=entry(parent / "supervisor/attempt0001/actual_exit/record.json"),
        actual_worker_exit=entry(replay / "exit/record.json"),
        original_processes_exited={name: entry(path) for name, path in paths.items()},
        response_checkpoint=entry(checkpoint_path),
        checkpoint_state_bytes_sha256_verified=True,
        checkpoint_state_sha256=SOURCE_CHECKPOINT_SHA256,
        complete_response_prefix=121,
        remaining_response_count=310,
        total_response_count=431,
        observed_resource_gates_passed=True,
        successful_model_release_claimed=False,
        sender_attribution="unknown",
        signal_sender_inferred=False,
        endpoint_answers_or_scores_read=False,
    )


def inspect_authorized_recovery(
    newroot, parentroot, *, authorization_record=None, authorization_body=None
):
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    require(
        root == ROOT and parent == SOURCE_ROOT and not (root / "inheritance/record.json").exists(),
        "one explicit recovery requires its fresh independent V52 root and pinned V51 parent",
    )
    authority = _authorization(root, authorization_record, authorization_body)
    body = authorization_body if authorization_body is not None else read_ref(authority)
    require(
        body.get("explicit_signal_checkpoint_recovery_authorized") is True
        and body.get("known_failure_recovery_authorized") is True
        and body.get("automatic_attempt") is False
        and body.get("clean_handoff_authorized") is False
        and body.get("initial_parent_protocol") == entry(parent / "protocol/record.json")
        and body.get("parent_protocol") == entry(parent / "protocol/record.json")
        and body.get("initial_response_checkpoint")
        == entry(parent / SOURCE_CHECKPOINT_RELATIVE / "record.json")
        and body.get("initial_response_checkpoint_id") == SOURCE_CHECKPOINT_ID
        and body.get("initial_inherited_response_count") == 121
        and body.get("initial_remaining_response_count") == 310
        and body.get("initial_total_response_count") == 431
        and body.get("prior_conditional_four_worker_ceiling_superseded") is True
        and body.get("new_sampling_or_optimizer_dose_authorized") is False,
        "explicit one-time authority must bind the exact signal stop and response121 checkpoint",
    )
    protocol = checked(parent / "protocol/record.json")
    audit = _inspect_explicit_source_stop(parent, protocol)
    value = _build_frontier(
        root,
        parent,
        protocol,
        authority,
        audit,
        allowed_parent_schemas=(SOURCE_INHERITANCE_SCHEMA,),
    )
    require(
        len(value["context_inheritances"]) == 1
        and len(value["completed_evaluations"]) == 8
        and value["remaining_optimizer_updates"] == 298
        and value["remaining_outer_updates"] == 1,
        "the original remaining nine-model matrix changed",
    )
    item = value["context_inheritances"][0]
    require(
        (item["seed"], item["arm"], item["step"]) == (389, "Full", 1192)
        and set(item["interrupted_stage_bindings"]) == {"replay_R3"}
        and all(
            item["stage_bindings"][stage]["protocol_scope"] == "parent"
            for stage in (*SHARDS, "virtual_point")
        )
        and all(
            item["stage_bindings"][stage]["protocol_scope"] == "current"
            for stage in ("replay_R3", "distribution", "train")
        )
        and item["task_cache_view"]["tasks"] == 744
        and item["task_cache_view"]["read_only"] is True
        and item["replay_resume"]["checkpoint"] == audit["response_checkpoint"]
        and item["replay_resume"]["inherited_response_count"] == 121
        and item["replay_resume"]["remaining_response_count"] == 310
        and item["replay_resume"]["total_response_count"] == 431
        and item["replay_resume"]["parent_saved_prefix_replayed_again"] is False,
        "initial recovery must reuse all class/point/feedback and only replay responses122..431",
    )
    budget = value["remaining_scientific_budget"]
    require(
        budget["pending_sealed_feedback_episodes"] == 700
        and budget["future_first_sampling_feedback_episodes"] == 0
        and budget["future_first_sampling_outers"] == 0
        and budget["remaining_new_feedback_episodes"] == 0
        and budget["reserved_partial_feedback_episodes"] == 0
        and budget["remaining_endpoint_answers"] == 1147,
        "one pending sealed cohort and one final endpoint cannot expand scientific dose",
    )
    item["replay_resume"]["state_bytes_verified"] = True
    value.update(
        initial_explicit_signal_recovery_exception_applied=True,
        initial_known_failure_exception_applied=False,
        old_unsafe_decision_reclassified=False,
        initial_authorized_signal_stop=audit,
        clean_handoff_from_successful_workers=False,
        unknown_signal_automatic_retry_allowed=False,
        prior_conditional_four_worker_ceiling_superseded=True,
    )
    return value


def _authorization(root, reference=None, body=None):
    require(reference is None or body is None, "cannot mix preview and sealed authority")
    if body is not None:
        value, ref = body, dict(preview_only=True, authorization_body_digest=digest(body))
    else:
        ref = (
            reference
            if isinstance(reference, dict)
            else entry(reference or root / "authorization/record.json")
        )
        value = read_ref(ref)
    require(
        bool(value.get("user_consent"))
        and value.get("time_limits_removed") is True
        and value.get("automatic_recovery_authorized") is True
        and value.get("unknown_feedback_retry_allowed") is False
        and value.get("unknown_signal_automatic_retry_allowed") is False
        and value.get("total_worker_limit_removed") is True
        and "max_gpu_workers" in value
        and value["max_gpu_workers"] is None
        and "independent_total_worker_limit" in value
        and value["independent_total_worker_limit"] is None
        and value.get("max_workers_per_gpu") == 1
        and value.get("effective_device_capacity") == 7
        and value.get("allowed_gpu_indices") == list(ALLOWED_GPU_INDICES)
        and value.get("steady_gpu_indices") == list(ALLOWED_GPU_INDICES)
        and "steady_max_gpu_workers" in value
        and value["steady_max_gpu_workers"] is None
        and value.get("resource_pool_without_independent_cap_authorized") is True
        and value.get("host_ram_runtime_hard_gates_unchanged") is True
        and value.get("fixed_gpu_reservation_authorized") is True,
        "explicit time-waiver and safe-only automatic-recovery authority required",
    )
    return ref


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _interrupted_binding(directory, protocol, context_id, stage):
    directory = Path(directory)
    launch, exited = (checked(directory / name / "record.json") for name in ("launch", "exit"))
    require(
        all(
            value["protocol_id"] == protocol["id"]
            and value["context_id"] == context_id
            and value["stage"] == stage
            for value in (launch, exited)
        ),
        "interrupted process point/protocol binding changed",
    )
    old._stopped(launch)
    return dict(
        protocol_scope="parent",
        protocol_ref=entry(Path(protocol["output_root"]) / "protocol/record.json"),
        protocol_id=protocol["id"],
        directory=str(directory),
        stage=stage,
        launch=entry(directory / "launch/record.json"),
        exit=entry(directory / "exit/record.json"),
        failure=entry(directory / "failure/record.json")
        if (directory / "failure/record.json").exists()
        else None,
        immediate_parent_local=True,
        accepted_complete_stage=False,
    )


def _charged_time(prior, directory, interrupted):
    snapshot_path = Path(directory) / "queue/status.json"
    snapshot = read_ref(file_ref(snapshot_path))
    intervals = []
    for binding in interrupted.values():
        launch, exited = read_ref(binding["launch"]), read_ref(binding["exit"])
        start = old._time(launch["at"])
        end = max(old._time(exited["at"]), start + exited["elapsed_worker_wall_seconds"])
        intervals.append((start, end))
    whole = base.union_seconds(intervals)
    tail = base.union_seconds(
        [
            (max(start, old._time(snapshot["at"])), end)
            for start, end in intervals
            if end > max(start, old._time(snapshot["at"]))
        ]
    )
    return dict(
        inherited_compute_seconds=math.ceil(max(prior + whole, snapshot["compute_seconds"] + tail)),
        earlier_inherited_compute_seconds=prior,
        parent_compute_snapshot_seconds=snapshot["compute_seconds"],
        immediate_parent_worker_interval_union_seconds=whole,
        unaccounted_interrupted_seconds_added=tail,
        parent_context_snapshot=file_ref(snapshot_path),
    )


def inspect_parent_recovery(
    newroot, parentroot, *, authorization_record=None, authorization_body=None
):
    if Path(newroot).resolve() == ROOT:
        return inspect_authorized_recovery(
            newroot,
            parentroot,
            authorization_record=authorization_record,
            authorization_body=authorization_body,
        )
    return inspect_automatic_recovery(
        newroot,
        parentroot,
        authorization_record=authorization_record,
        authorization_body=authorization_body,
    )


def _publish_aliases(root, value):
    sealed = publish(root / "inheritance/record.json", value)
    for item in sealed["context_inheritances"]:
        publish(
            Path(item["new_context_directory"]) / "context/record.json",
            dict(
                schema=ALIAS_SCHEMA,
                **{
                    key: item[key]
                    for key in (
                        "new_context_directory",
                        "original_context",
                        "original_context_id",
                        "origin_context_directory",
                    )
                },
                inheritance=entry(root / "inheritance/record.json"),
                original_context_rewritten=False,
                actual_scientific_context_copied=False,
            ),
        )
    return sealed


def initialize_parent_recovery(newroot, parentroot, *, authorization_record=None):
    root = Path(newroot).resolve()
    return _publish_aliases(
        root, inspect_parent_recovery(root, parentroot, authorization_record=authorization_record)
    )


def _inheritance(plan):
    value = read_ref(plan["inheritance"])
    require(
        value["schema"] == SCHEMA and value["new_root"] == str(Path(plan["output_root"]).resolve()),
        "wrong V52 inheritance episode",
    )
    return value


def inherited_context(newctx, plan):
    rows = [
        row
        for row in _inheritance(plan)["context_inheritances"]
        if row["new_context_directory"] == str(Path(newctx).resolve())
    ]
    require(len(rows) <= 1, "duplicate inherited scientific context")
    return rows[0] if rows else None


def resolve_origin_context(newctx, plan):
    directory = Path(newctx).resolve()
    require(
        directory.is_relative_to(Path(plan["output_root"]).resolve() / "contexts"),
        "foreign context path",
    )
    alias = checked(directory / "context/record.json")
    item = inherited_context(directory, plan)
    if item is None:
        require(
            alias["schema"] == "v37_actual_production_context.v1"
            and alias["run_root"] == alias["outer_root"] == str(directory),
            "fresh context must own actual point",
        )
        return directory
    require(
        alias["schema"] == ALIAS_SCHEMA
        and alias["inheritance"] == plan["inheritance"]
        and all(
            alias[key] == item[key]
            for key in (
                "new_context_directory",
                "original_context",
                "original_context_id",
                "origin_context_directory",
            )
        ),
        "original scientific alias binding changed",
    )
    reference, context, origin = _actual_context(item["original_context"])
    require(
        reference == item["original_context"]
        and context["id"] == item["original_context_id"]
        and str(origin) == item["origin_context_directory"],
        "original scientific point changed",
    )
    return origin


def stage_directory(newctx, plan, stage):
    require(stage in STAGES, "unknown stage")
    directory = Path(newctx).resolve()
    resolve_origin_context(directory, plan)
    item = inherited_context(directory, plan)
    if item is None:
        return directory / stage
    binding = item["stage_bindings"][stage]
    source = Path(binding["directory"])
    require(source == source.resolve() and source.name == stage, "redirected stage")
    if binding["protocol_scope"] == "current":
        require(source == directory / stage, "current stage escaped attempt")
    else:
        require(
            read_ref(binding["protocol_ref"])["id"] == binding["protocol_id"]
            and entry(source / "result/record.json") == binding["result"]
            and entry(source / "exit/record.json") == binding["exit"],
            "inherited stage owner changed",
        )
    return source


def task_cache_overlay_binding(newctx, plan):
    resolve_origin_context(newctx, plan)
    item = inherited_context(newctx, plan)
    if item is None:
        return None
    return item.get("task_cache_overlay") or item.get("task_cache_view")


def task_cache_view_binding(newctx, plan):
    value = task_cache_overlay_binding(newctx, plan)
    return value if value is not None and value["schema"] == CACHE_SCHEMA else None


def feedback_resume_binding(newctx, plan):
    resolve_origin_context(newctx, plan)
    item = inherited_context(newctx, plan)
    return item.get("feedback_resume") if item else None


def replay_resume_binding(newctx, plan):
    resolve_origin_context(newctx, plan)
    item = inherited_context(newctx, plan)
    return item.get("replay_resume") if item else None


def require_upstream(newctx, context, plan, stage, control):
    directory = Path(newctx).resolve()
    origin, item = resolve_origin_context(directory, plan), inherited_context(directory, plan)
    require(context == checked(origin / "context/record.json"), "scientific point relabelled")
    require(
        stage_directory(directory, plan, stage) == directory / stage, "complete stage cannot rerun"
    )
    required = {
        "virtual_point": SHARDS,
        "replay_R3": ("virtual_point",),
        "distribution": (*SHARDS, "virtual_point", "replay_R3"),
        "train": ("distribution",) if context["due_outer"] else (),
    }.get(stage, ())
    task_plan = read_ref(context["task_plan"]) if context["due_outer"] else None
    for prior in required:
        source = stage_directory(directory, plan, prior)
        binding = item["stage_bindings"][prior] if item else None
        inherited = binding is not None and binding["protocol_scope"] == "parent"
        owner = read_ref(binding["protocol_ref"]) if inherited else plan
        result, exited = (
            checked(source / "result/record.json"),
            checked(source / "exit/record.json"),
        )
        require(
            result["context_id"] == exited["context_id"] == context["id"]
            and result["protocol_id"] == exited["protocol_id"] == owner["id"]
            and exited["returncode"] == 0
            and exited["stop_requested"] is False,
            "upstream actual point/owner/exit changed",
        )
        control.check_result(owner, prior, result, task_plan)
        if prior in ("virtual_point", "replay_R3", "distribution"):
            reference, _ = old._payload(source, context, prior)
            require(
                result["payload"] == reference
                and (not inherited or binding["payload"] == reference),
                "saved upstream mathematical value changed",
            )


def inspect_stage(directory, protocol, context, stage, task_plan=None, *, protocol_ref):
    """Validate each accepted worker under its real protocol, including all 8 GPUs."""
    directory = Path(directory)
    markers = ("launch", "attempt", "result", "exit", "failure", "payload")
    if not any((directory / name).exists() for name in markers):
        return None
    require(directory == directory.resolve(), "redirected stage directory")
    require(not (directory / "failure").exists(), "failed stage cannot migrate or retry")
    require(
        all((directory / name / "record.json").is_file() for name in ("launch", "result", "exit")),
        "partial or unexited stage cannot migrate",
    )
    launch, result, exited = (
        checked(directory / name / "record.json") for name in ("launch", "result", "exit")
    )
    require(read_ref(protocol_ref) == protocol, "stage protocol reference changed")
    require(
        all(row["protocol_id"] == protocol["id"] for row in (launch, result, exited))
        and all(row["context_id"] == context["id"] for row in (launch, result, exited))
        and all(row["stage"] == stage for row in (launch, result, exited))
        and result["status"] == "COMPLETE"
        and result["model_released"] is True
        and exited["returncode"] == 0
        and exited["stop_requested"] is False,
        "stage is not accepted, physically successful and bound to its actual point",
    )
    old._stopped(launch)
    gpu = result["gpu_index"]
    require(
        type(gpu) is int
        and gpu in protocol["allowed_gpu_indices"]
        and gpu == launch["gpu_index"]
        and result["gpu_uuid"] == launch["gpu_uuid"] == protocol["gpu_uuids"][str(gpu)],
        "stage GPU differs from its own registered protocol",
    )
    old._check_resources(result["resources"], stage)
    for key in (
        "API_calls",
        "new_sampling_calls",
        "scoring_calls",
        "optimizer_steps",
        "replayed_responses",
    ):
        require(type(result[key]) is int and result[key] >= 0, "invalid scientific counter")
    require(
        result["API_calls"] == 0
        and (stage == "virtual_point" or result["scoring_calls"] == 0)
        and (stage == "train" or result["optimizer_steps"] == 0)
        and (stage == "replay_R3" or result["replayed_responses"] == 0)
        and (stage in ("virtual_point", "generate") or result["new_sampling_calls"] == 0),
        "scientific activity outside its registered stage",
    )
    if stage not in ("train", "generate"):
        require(result["model_optimizer_rng_buffers_unchanged"] is True, "real state changed")
    if stage in SHARDS:
        tasks = task_plan["assignments"][SHARDS.index(stage)]["task_ids"]
        reused = result["reused_task_ids"]
        require(
            result["task_ids"] == tasks
            and result["task_count"] == len(tasks)
            and result["class_task_calls"] + len(reused) == len(tasks)
            and len(set(reused)) == len(reused)
            and set(reused) <= set(tasks),
            "whole-task coverage changed",
        )
    if stage in ("virtual_point", "replay_R3", "distribution"):
        require(result["denominator"] == 700, "feedback denominator changed")
    if stage == "virtual_point":
        expected = 0 if context["feedback"]["mode"] == "sealed_existing" else 700
        require(
            result["feedback_mode"] == context["feedback"]["mode"]
            and result["new_feedback_episodes"] + result.get("inherited_feedback_episodes", 0)
            == expected,
            "same-point feedback ownership or dose changed",
        )
    if stage == "replay_R3":
        require(
            result["complete_replay"] is True and result["current_point_only"] is True,
            "actual cumulative response replay is incomplete",
        )
        if result.get("restored_completed_responses", 0):
            require(
                result["restored_completed_responses"] == result["inherited_response_count"]
                and result["actual_new_response_calls"] == result["replayed_responses"]
                and result["inherited_response_count"] + result["replayed_responses"]
                == result["response_count"],
                "resumed replay cumulative and new response counts differ",
            )
        else:
            require(
                result["replayed_responses"] == result["response_count"],
                "non-resumed replay must cover its complete response cohort",
            )
    if stage == "generate":
        require(
            result["session_count"] == result["new_generation_episodes"] == 1147
            and result["new_sampling_calls"] == result["actual_response_calls"]
            and result["private_test_scoring"] is False,
            "endpoint dose or all-model scoring barrier changed",
        )
    binding = dict(
        protocol_scope="parent",
        protocol_id=protocol["id"],
        protocol_ref=protocol_ref,
        directory=str(directory),
        launch=entry(directory / "launch/record.json"),
        result=entry(directory / "result/record.json"),
        exit=entry(directory / "exit/record.json"),
    )
    if (directory / "attempt/record.json").exists():
        binding["attempt"] = entry(directory / "attempt/record.json")
    if stage in ("virtual_point", "replay_R3", "distribution"):
        binding["payload"], binding["tensor_identity"] = old._payload(directory, context, stage)
        require(result["payload"] == binding["payload"], "actual saved phase value changed")
    if stage == "train":
        commits = {}
        for key in ("next_checkpoint", "outer_checkpoint", "first_sft_after_outer"):
            if result.get(key):
                path = Path(result[key]).resolve()
                # Legacy scientific checkpoints use their state digest and a
                # file reference, not the scheduler's self-ID JSON wrapper.
                meta = read_ref(file_ref(path / "record.json"))
                reference = dict(
                    path=str(path),
                    record=file_ref(path / "record.json"),
                    state=dict(path=str(path / "state.pt"), sha256=meta["state_sha256"]),
                    **{
                        name: meta[name]
                        for name in ("seed", "arm", "step", "phase", "actual_state_digest")
                    },
                )
                commits[key] = checkpoint_metadata(reference)
        require(
            commits["next_checkpoint"]["step"] == result["committed_step"]
            and all(
                (row["seed"], row["arm"]) == (context["seed"], context["arm"])
                for row in commits.values()
            ),
            "actual training commit coordinate changed",
        )
        binding["actual_training_commits"] = commits
    return binding


def _observed_physical_resource_failure(value):
    resources = value.get("resources") or {}
    if resources.get("limits_unchanged") is not True:
        return False
    return any(
        row.get("allocated_pass") is False
        or row.get("free_pass") is False
        or (row.get("host") or {}).get("rss_pass") is False
        or (row.get("host") or {}).get("available_pass") is False
        for row in resources.get("observations", [])
    )


def _physical_resource_assessment(proof):
    """Recompute the actual byte predicate; do not trust an error-type label alone."""
    row = proof.get("observation")
    keys = (
        "allocated_bytes",
        "reserved_bytes",
        "peak_allocated_bytes",
        "peak_reserved_bytes",
        "physical_free_bytes",
        "device_total_bytes",
    )
    require(
        isinstance(row, dict)
        and isinstance(row.get("label"), str)
        and bool(row["label"])
        and all(type(row.get(key)) is int and row[key] >= 0 for key in keys),
        "typed physical resource evidence requires actual integer byte observations",
    )
    allocated, reserved, peak, reserved_peak, free, total = (row[key] for key in keys)
    gib = 1024**3
    require(
        allocated <= reserved <= reserved_peak <= total
        and allocated <= peak <= 76 * gib
        and reserved + free <= total
        and free < 2 * gib
        and proof.get("required_physical_free_bytes") == 2 * gib
        and proof.get("lifetime_allocated_limit_bytes") == 76 * gib
        and proof.get("reason") == "physical_boundary_free_exhausted"
        and proof.get("model_load_started") is True
        and proof.get("proof_no_scientific_work") is False
        and proof.get("allocator_anchor_and_lifetime_peak_invariants_passed") is True,
        "typed physical evidence failed its exact resource-only predicate or lifetime invariants",
    )
    return row


def _verified_physical_resource_failure(directory, protocol, launch, stopped):
    """Accept only a frozen V52 producer's same-worker post-model physical gate."""
    directory = Path(directory)
    require(
        stopped["error_type"] == "ReservationPhysicalResourceError"
        and stopped["error"] == "physical boundary reserve exhausted"
        and stopped["API_calls"] == 0
        and stopped["original_mathematical_functions_unchanged"] is True,
        "typed physical resource failure cannot authorize a generic reservation failure",
    )
    reference = entry(directory / "reservation/physical_resource_failure/record.json")
    proof = read_ref(reference)
    identity = ("protocol_id", "context_id", "stage", "gpu_index", "gpu_uuid", "pid", "birth")
    require(
        proof["schema"] == "v52_observed_physical_resource_failure.v1"
        and proof["error_type"] == stopped["error_type"]
        and all(proof[key] == launch[key] for key in identity)
        and proof["gpu_index"] in protocol["allowed_gpu_indices"]
        and proof["gpu_uuid"] == protocol["gpu_uuids"][str(proof["gpu_index"])],
        "typed physical resource failure belongs to another worker or device",
    )
    _physical_resource_assessment(proof)
    producer = Path(protocol["output_root"]) / "implementation/finqa_v52_reservation.py"
    implementation = checked(producer.parent / "record.json")
    require(
        implementation["id"] == protocol["implementation_id"]
        and old.sha(producer) == implementation["sha256"][producer.name],
        "typed physical resource producer differs from the parent's frozen source",
    )
    require(
        proof["reservation_admission"] == entry(directory / "reservation/admission/record.json"),
        "typed physical resource failure lost its original process admission",
    )
    admission = read_ref(proof["reservation_admission"])
    require(
        all(admission[key] == launch[key] for key in identity)
        and admission["before_CPU_state_and_model_load"] is True
        and admission["scientific_model_calls"] == 0
        and admission["cuda_initialized"] is True
        and admission["policy"] == protocol["gpu_reservation_policy"],
        "typed physical resource admission ownership or policy changed",
    )
    return dict(evidence_refs=[reference, file_ref(producer), proof["reservation_admission"]])


def _verified_pre_scientific_wait_stop(directory, protocol, launch, stopped):
    """A stopped waiting sibling is a zero-science consequence, never a root cause."""
    directory = Path(directory)
    require(
        stopped["error_type"] == "ReservationWaitStopped"
        and stopped["error"] == "safe stop requested during CUDA resource wait"
        and stopped["API_calls"] == 0
        and stopped["original_mathematical_functions_unchanged"] is True
        and not (directory / "reservation/model_load_started/record.json").exists(),
        "pre-scientific wait stop cannot hide started science",
    )
    candidates = sorted((directory / "reservation_wait").glob("episode[0-9]*/status.json"))
    require(bool(candidates), "stopped resource waiter has no durable wait episode")
    path = candidates[-1]
    require(re.fullmatch(r"episode\d{4,}", path.parent.name), "invalid resource wait episode")
    proof = checked(path)
    identity = ("protocol_id", "context_id", "stage", "gpu_index", "gpu_uuid", "pid", "birth")
    require(
        proof["schema"] == "v52_pre_scientific_resource_wait.v1"
        and proof["phase"] == "STOPPED"
        and proof["error"] == dict(type=stopped["error_type"], message=stopped["error"])
        and all(proof[key] == launch[key] for key in identity)
        and proof["gpu_index"] in protocol["allowed_gpu_indices"]
        and proof["gpu_uuid"] == protocol["gpu_uuids"][str(proof["gpu_index"])]
        and proof["cuda_initialized"] is True
        and proof["model_load_started"] is False
        and proof["proof_no_scientific_work"] is True
        and all(
            type(proof[key]) is int and proof[key] == 0
            for key in (
                "scientific_model_calls",
                "API_calls",
                "optimizer_commits",
                "new_feedback_calls",
                "actual_response_calls",
            )
        )
        and proof["original_scientific_source_unchanged"] is True
        and proof["worker_slot_retained"] is True
        and proof["gpu_lease_retained"] is True
        and proof["lifetime_peak_reset_calls"] == 1
        and proof["gpu_admission_policy_schema"] == "v52_empirical_shared_gpu_reserved_admission.v1"
        and proof["gpu_reservation_policy_schema"]
        == "v52_adaptive_same_process_native_segment_reservation.v1"
        and type(proof["sequence"]) is int
        and proof["sequence"] >= 0,
        "stopped resource wait proof lost exact identity or zero-scientific-work guarantees",
    )
    immutable = path.parent / f"event{proof['sequence']:06d}/record.json"
    require(checked(immutable) == proof, "terminal resource wait event differs from its snapshot")
    producer = Path(protocol["output_root"]) / "implementation/finqa_v52_reservation.py"
    implementation = checked(producer.parent / "record.json")
    require(
        implementation["id"] == protocol["implementation_id"]
        and old.sha(producer) == implementation["sha256"][producer.name],
        "stopped resource wait producer differs from frozen source",
    )
    return dict(evidence_refs=[entry(immutable), file_ref(path), file_ref(producer)])


def _capacity_assessment(value):
    """Independently recompute the frozen resource shell's byte predicates."""
    keys = (
        "allocated_bytes",
        "reserved_bytes",
        "physical_free_bytes",
        "device_total_bytes",
        "estimated_complete_kv_bytes",
        "peak_allocated_bytes",
    )
    require(
        isinstance(value, dict)
        and all(type(value.get(key)) is int and value[key] >= 0 for key in keys),
        "typed R3 capacity evidence must contain actual integer byte observations",
    )
    allocated, reserved, free, total, kv, peak = (value[key] for key in keys)
    gib = 1024**3
    require(
        allocated <= reserved and allocated <= peak and reserved + free <= total,
        "typed R3 physical observations are inconsistent",
    )
    raw_required = 4 * gib + kv
    available_required = 20 * gib + kv
    required_capacity = allocated + available_required
    allocated_budget = allocated + 18 * gib + kv
    dispatch = max(56 * gib, ((required_capacity + 4 * gib + gib - 1) // gib) * gib)
    recoverable = (
        kv <= 8 * gib
        and raw_required <= 8 * gib
        and allocated_budget <= 76 * gib
        and dispatch <= total
        and free + reserved + 4 * gib <= total
        and peak <= 76 * gib
    )
    condition = dict(
        schema="v52_r3_changed_capacity_required.v1",
        stage="replay_R3",
        required_dispatch_free_bytes=dispatch,
        failed_available_capacity_bytes=free + reserved,
        self_context_reclaim_allowance_bytes=3 * gib,
        minimum_capacity_increase_bytes=4 * gib,
        required_allocated_budget_bytes=allocated_budget,
        device_total_bytes=total,
        recoverable_when_capacity_changes=recoverable,
    )
    expected = dict(
        allocated_bytes=allocated,
        reserved_bytes=reserved,
        physical_free_bytes=free,
        device_total_bytes=total,
        estimated_complete_kv_bytes=kv,
        resident_kv_budget_bytes=2 * gib,
        activation_resident_budget_bytes=16 * gib,
        free_reserve_bytes=2 * gib,
        allocated_limit_bytes=76 * gib,
        reusable_bytes=reserved - allocated,
        available_bytes=free + reserved - allocated,
        raw_required_free_bytes=raw_required,
        required_available_bytes=available_required,
        required_device_capacity_bytes=required_capacity,
        required_allocated_budget_bytes=allocated_budget,
        physical_free_pass=free >= 2 * gib,
        raw_free_pass=free >= raw_required,
        available_pass=free + reserved - allocated >= available_required,
        allocated_pass=allocated < 76 * gib,
        original_full_KV_cap_pass=kv <= 8 * gib,
        expected_KV_bound_pass=kv <= 2 * gib,
        peak_allocated_bytes=peak,
        lifetime_allocated_pass=peak <= 76 * gib,
        recoverable_when_capacity_changes=recoverable,
        retry_capacity_condition=condition,
    )
    require(value == expected, "typed R3 capacity arithmetic or registered retry margin changed")
    require(
        not all(
            expected[key]
            for key in (
                "physical_free_pass",
                "raw_free_pass",
                "available_pass",
                "allocated_pass",
                "original_full_KV_cap_pass",
                "lifetime_allocated_pass",
            )
        ),
        "typed R3 capacity proof does not demonstrate an actual failed predicate",
    )
    return condition


def _verified_r3_capacity_failure(directory, protocol, launch, stopped):
    """No ValueError text heuristic: require one frozen, same-worker typed proof."""
    directory = Path(directory)
    require(
        launch["stage"] == stopped["stage"] == "replay_R3"
        and stopped["error_type"] == "R3CapacityError"
        and stopped["API_calls"] == 0
        and stopped["original_mathematical_functions_unchanged"] is True,
        "typed R3 resource recovery cannot authorize another stage or scientific error",
    )
    reference = entry(directory / "reservation/r3_capacity_failure/record.json")
    proof = read_ref(reference)
    identity_keys = ("protocol_id", "context_id", "stage", "gpu_index", "gpu_uuid", "pid", "birth")
    require(
        proof["schema"] == "v52_r3_internal_capacity_failure.v1"
        and proof["error_type"] == "R3CapacityError"
        and all(proof[key] == launch[key] for key in identity_keys)
        and proof["gpu_index"] in protocol["allowed_gpu_indices"]
        and proof["gpu_uuid"] == protocol["gpu_uuids"][str(proof["gpu_index"])]
        and proof["before_scientific_response"] is True
        and proof["failed_response_forward_calls"] == 0
        and proof["original_R3_predicates_not_bypassed"] is True
        and type(proof["successful_response_calls_this_worker"]) is int
        and proof["successful_response_calls_this_worker"] >= 0,
        "typed R3 resource proof belongs to another worker or began the failed response",
    )
    producer = Path(protocol["output_root"]) / "implementation/finqa_v52_reservation.py"
    implementation = checked(producer.parent / "record.json")
    require(
        implementation["id"] == protocol["implementation_id"]
        and old.sha(producer) == implementation["sha256"][producer.name],
        "typed R3 resource producer is not the parent's frozen source",
    )
    original = checked(R3_REFERENCE)
    expected_source = original["binding"]["backend_identity"]["source_binding"]
    require(
        original["id"] == EXPECTED_REPLAYS[(389, "C-only", 1192)]["checkpoint_id"]
        and proof["backend_source_binding"] == expected_source
        and proof["backend_source_binding_digest"] == digest(expected_source),
        "typed R3 resource failure changed the original mathematical backend",
    )
    require(
        proof["reservation_admission"] == entry(directory / "reservation/admission/record.json"),
        "typed R3 resource proof lost its actual same-process admission",
    )
    admitted = read_ref(proof["reservation_admission"])
    require(
        all(admitted[key] == proof[key] for key in identity_keys)
        and admitted["before_CPU_state_and_model_load"] is True
        and admitted["scientific_model_calls"] == 0
        and admitted["cuda_initialized"] is True
        and admitted["policy"] == protocol["gpu_reservation_policy"],
        "typed R3 resource admission provenance changed",
    )
    origin = resolve_origin_context(directory.parent, protocol)
    context = checked(origin / "context/record.json")
    require(context["id"] == launch["context_id"], "typed R3 original scientific context changed")
    virtual_directory = stage_directory(directory.parent, protocol, "virtual_point")
    virtual = checked(virtual_directory / "result/record.json")
    virtual_exit = checked(virtual_directory / "exit/record.json")
    require(
        virtual["status"] == "COMPLETE"
        and virtual["model_released"] is True
        and virtual["context_id"] == context["id"]
        and virtual["denominator"] == 700
        and virtual_exit["returncode"] == 0
        and virtual_exit["stop_requested"] is False,
        "typed R3 failure lacks complete original same-point feedback",
    )
    inherited_path = directory / "inherited_prefix/record.json"
    inherited = checked(inherited_path) if inherited_path.exists() else None
    restored = inherited["inherited_response_count"] if inherited else 0
    candidates = sorted((directory / "checkpoints").glob("response*/record.json"))
    latest = (
        entry(candidates[-1])
        if candidates
        else inherited["parent_checkpoint"]
        if inherited
        else None
    )
    cursor = read_ref(latest)["cursor"] if latest else None
    require(
        proof["latest_actual_checkpoint_ref"] == latest
        and proof["latest_actual_checkpoint_cursor"] == cursor,
        "typed R3 recovery must bind the actual latest durable checkpoint",
    )
    if latest is not None:
        checkpoint = read_ref(latest)
        binding = checkpoint["binding"]
        _verify_replay_backend(binding, context)
        require(
            checkpoint["schema"] == "v19_response_boundary_checkpoint.v1"
            and checkpoint["response_prefix_complete"] is True
            and checkpoint["no_feedback_generation"] is True
            and checkpoint["optimizer_steps_performed"] == 0
            and 0 <= restored <= cursor <= binding["response_count"]
            and binding["execution_profile_id"] == context["id"]
            and binding["point_id"] == virtual["point_id"]
            and binding["response_count"] == virtual["response_count"]
            and binding["denominator"] == 700,
            "typed R3 checkpoint belongs to another point, prefix or feedback cohort",
        )
        old._file_identity(Path(latest["path"]).parent / "state.pt")
    else:
        previous_item = inherited_context(directory.parent, protocol)
        require(
            previous_item is None or previous_item.get("replay_resume") is None,
            "restored prefix evidence is missing; never restart that replay from zero",
        )
    completed = restored + proof["successful_response_calls_this_worker"]
    require(
        (cursor or 0) <= completed < virtual["response_count"],
        "typed R3 failure has no unfinished response after its actual prefix",
    )
    live_path = directory / "checkpoints/progress/status.json"
    if live_path.exists():
        live = read_ref(file_ref(live_path))
        require(
            live["completed_responses"] == completed
            and live["restored_completed_responses"] == restored
            and live["total_responses"] == virtual["response_count"],
            "typed R3 successful-call counter differs from the original progress cursor",
        )
    condition = _capacity_assessment(proof["assessment"])
    require(
        proof["retry_capacity_condition"] == condition
        and proof["recoverable_when_capacity_changes"]
        == condition["recoverable_when_capacity_changes"],
        "typed R3 top-level recovery decision differs from actual capacity arithmetic",
    )
    return dict(
        condition=condition,
        recoverable=condition["recoverable_when_capacity_changes"],
        evidence_refs=[reference, file_ref(producer), proof["reservation_admission"]]
        + ([latest] if latest else []),
    )


def validate_safe_recovery(parentroot):
    """Only an identified resource-failed worker may trigger automatic recovery.

    Native feedback or endpoint generation interrupted after CUDA is deliberately
    unsupported: no generic consumer may silently retry an unknown response.
    A lawful child stop is only a consequence, never evidence that an unknown
    controller failure was a recoverable resource failure.
    """
    parent = Path(parentroot).resolve()
    evidence = []
    try:
        protocol = checked(parent / "protocol/record.json")
        require(
            protocol["schema"] == PROTOCOL_SCHEMA
            and protocol["output_root"] == str(parent)
            and protocol["allowed_gpu_indices"] == list(ALLOWED_GPU_INDICES)
            and protocol["max_gpu_workers"] is None
            and protocol["independent_total_worker_limit"] is None
            and protocol["total_worker_limit_removed"] is True
            and protocol["max_workers_per_gpu"] == 1
            and Path(protocol["supervision_root"]).resolve() == ROOT
            and (
                parent == ROOT
                or (
                    parent.parent == ROOT / "attempts"
                    and re.fullmatch(r"attempt\d{4,}", parent.name)
                )
            ),
            "foreign automatic-recovery parent",
        )
        queue = read_ref(file_ref(parent / "queue/status.json"))
        failure = checked(parent / "failure/record.json")
        require(
            queue["active_children"] == []
            and queue["protocol_id"] == failure["protocol_id"] == protocol["id"]
            and queue["phase"] == failure["phase"]
            and failure["phase"]
            in ("STOPPED_FAILURE_NO_RETRY", "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME")
            and failure["stop_error"] is None
            and failure["actual_progress_audit_error"] is None,
            "parent pool is not fully stopped with valid actual-state audit",
        )
        old._stopped(checked(parent / "launch_01/record.json"))
        progress = checked(parent / "actual_final_progress/record.json")
        require(
            progress["endpoint_scores_or_answers_read"] is False
            and progress["original_state_or_feedback_modified"] is False,
            "actual checkpoint audit is not read-only",
        )
        evidence.extend(
            entry(parent / name / "record.json")
            for name in ("protocol", "failure", "launch_01", "actual_final_progress")
        )
        trigger = failure.get("error", "").lower()
        if (
            "explicit safe stop requested" in trigger
            or "user stop" in trigger
            or "manual stop" in trigger
        ):
            return dict(allowed=False, reason="manual_stop_is_terminal", evidence_refs=evidence)
        # These are the two exact worker-failure propagation sites in the frozen
        # lifecycle. All direct controller failures (including identity/policy,
        # binding, unknown memory observations, and numerical guards) fail closed.
        # Do this BEFORE considering any child: pool shutdown can itself create
        # a perfectly durable TailStopRequested/ReplayPaused record.
        worker_trigger = re.fullmatch(
            r"worker (?:reported failure|exited unsuccessfully): ([A-Za-z0-9_]+)",
            failure.get("error", ""),
        )
        require(
            failure.get("error_type") == "ValueError"
            and worker_trigger is not None
            and worker_trigger[1] in (*SHARDS, *STAGES, "generate"),
            "unsupported_controller_root_failure_requires_user",
        )
        trigger_stage = worker_trigger[1]
        classes, retry_capacity_conditions, retry_capacity_evidence_refs = [], [], []
        trigger_workers = []
        for path in sorted(parent.glob("contexts/seed*/*/step*/*/launch/record.json")) + sorted(
            parent.glob("evaluations/*/generate/launch/record.json")
        ):
            directory = path.parent.parent
            launch, exited = checked(path), checked(directory / "exit/record.json")
            require(
                launch["protocol_id"] == exited["protocol_id"] == protocol["id"]
                and launch["context_id"] == exited["context_id"]
                and launch["stage"] == exited["stage"],
                "worker ownership mismatch",
            )
            old._stopped(launch)
            evidence.extend((entry(path), entry(directory / "exit/record.json")))
            if (
                (directory / "result/record.json").exists()
                and exited["returncode"] == 0
                and exited["stop_requested"] is False
            ):
                continue
            failure_path = directory / "failure/record.json"
            require(failure_path.exists(), "unsupported_unexplained_worker_exit")
            stopped = checked(failure_path)
            evidence.append(entry(failure_path))
            require(
                stopped["protocol_id"] == protocol["id"]
                and stopped["context_id"] == launch["context_id"]
                and stopped["stage"] == launch["stage"],
                "failed-worker identity mismatch",
            )
            cause = stopped.get("error", "").lower()
            if any(
                word in cause
                for word in (
                    "checksum",
                    "binding",
                    "mismatch",
                    "numerical",
                    "nonfinite",
                    "nan",
                    "explicit reexecution",
                    "wrong point",
                    "changed",
                )
            ):
                return dict(
                    allowed=False,
                    reason="numerical_or_binding_failure_requires_user",
                    evidence_refs=evidence,
                )
            stop_consequence = stopped.get("error_type") in (
                "AdmissionStopped",
                "TailStopRequested",
                "ReplayPaused",
                "ReservationWaitStopped",
            )
            stop_evidence = stopped.get("stop_evidence") or {}
            if stop_consequence:
                require(
                    stop_evidence.get("stop_requested") is True,
                    "unverified_child_stop_cannot_explain_controller_failure",
                )
            resource = stopped.get("error_type") == "OutOfMemoryError"
            if (
                stopped.get("error_type") == "TailMemoryError"
                or cause == "production host ram envelope failed"
            ):
                resource = _observed_physical_resource_failure(stopped)
            if stopped.get("error_type") == "AdmissionError" and cause in (
                "host available ram below 96 gib reserve",
                "worker rss limit exceeded",
                "worker lifetime rss above stage limit",
            ):
                resource = True
            if stopped.get("error_type") == "R3CapacityError":
                capacity = _verified_r3_capacity_failure(directory, protocol, launch, stopped)
                evidence.extend(capacity["evidence_refs"])
                if not capacity["recoverable"]:
                    return dict(
                        allowed=False,
                        reason="verified_R3_capacity_cannot_fit_registered_device_or_fixed_headroom",
                        evidence_refs=evidence,
                        retry_capacity_conditions=[],
                        impossible_capacity_not_automatically_retried=True,
                    )
                resource = True
                retry_capacity_conditions.append(capacity["condition"])
                retry_capacity_evidence_refs.extend(capacity["evidence_refs"])
            if stopped.get("error_type") == "ReservationPhysicalResourceError":
                physical = _verified_physical_resource_failure(directory, protocol, launch, stopped)
                evidence.extend(physical["evidence_refs"])
                resource = True
            require(resource or stop_consequence, "unsupported_nonresource_failure_requires_user")
            if resource and launch["stage"] == trigger_stage and not stop_consequence:
                require(
                    stop_evidence.get("stop_requested") is False
                    and stop_evidence.get("received_signals") == [],
                    "resource_trigger_worker_has_prior_stop_or_unknown_stop_evidence",
                )
                trigger_workers.append(entry(failure_path))
            heartbeat = directory / "pre_cuda_wait/status.json"
            pre_cuda = False
            if heartbeat.exists():
                value = checked(heartbeat)
                pre_cuda = (
                    value.get("cuda_initialized") is False
                    and value.get("phase") in ("STOPPED", "FAILED", "TIMED_OUT")
                    and stopped.get("resources") is None
                )
            pre_scientific = False
            if stopped.get("error_type") == "ReservationWaitStopped":
                waiting = _verified_pre_scientific_wait_stop(directory, protocol, launch, stopped)
                evidence.extend(waiting["evidence_refs"])
                pre_scientific = True
            stage = launch["stage"]
            if stage in ("virtual_point", "generate") and not (pre_cuda or pre_scientific):
                return dict(
                    allowed=False,
                    reason="unsupported_partial_generation_or_unknown_feedback_requires_user",
                    evidence_refs=evidence,
                )
            classes.append(
                dict(
                    directory=str(directory),
                    stage=stage,
                    pre_cuda=pre_cuda,
                    pre_scientific_resource_wait=pre_scientific,
                    recovery_kind="pre_cuda_no_scientific_call"
                    if pre_cuda
                    else "post_cuda_pre_scientific_resource_wait_no_model_or_provider_call"
                    if pre_scientific
                    else "whole_task_cache"
                    if stage in SHARDS
                    else "ordered_response_checkpoint"
                    if stage == "replay_R3"
                    else "actual_committed_training_state"
                    if stage == "train"
                    else "saved_distribution_inputs",
                )
            )
        require(
            len(trigger_workers) == 1,
            "controller_failure_requires_one_matching_resource_worker_not_stop_consequences",
        )
        return dict(
            allowed=True,
            reason="resource_failure_with_verified_exits_and_durable_boundary_consumers",
            controller_root_failure=entry(parent / "failure/record.json"),
            controller_trigger_stage=trigger_stage,
            controller_trigger_worker_failure=trigger_workers[0],
            child_stop_consequences_not_used_as_root_cause=True,
            evidence_refs=evidence,
            interrupted_stages=classes,
            unknown_feedback_retry=False,
            numerical_failures_retried=False,
            retry_capacity_conditions=retry_capacity_conditions,
            retry_capacity_evidence_refs=retry_capacity_evidence_refs,
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        return dict(
            allowed=False,
            reason="unsafe_or_unsupported_recovery: " + str(error),
            evidence_refs=evidence,
        )


def _automatic_cache(context, source_directory, target, prior_item, bindings):
    """Partition exact whole-task tensor ownership across any number of attempts."""
    plan = read_ref(context["task_plan"])
    tasks = {row["task_id"]: row for row in plan["tasks"]}
    index = {f"task{row['index']:04d}": task for task, row in tasks.items()}
    older = (prior_item or {}).get("task_cache_overlay") or (prior_item or {}).get(
        "task_cache_view"
    )
    roots = (
        [Path(row["cache_root"]) for row in older["cache_sources"]]
        if older
        else [Path(context["task_cache_root"])]
    )
    if older and older.get("local_cache_root"):
        roots.append(Path(older["local_cache_root"]))
    roots.append(Path(source_directory) / "task_cache")
    inventory, owners, sources = {}, {}, []
    for cache in dict.fromkeys(roots):
        if not cache.exists():
            continue
        require(
            cache == cache.resolve() and cache.is_dir() and not cache.is_symlink(),
            "redirected task source",
        )
        selected = []
        for directory in sorted(cache.iterdir()):
            require(
                directory.name in index and directory.is_dir() and directory == directory.resolve(),
                "unrecognized/incomplete task-cache entry",
            )
            task = index[directory.name]
            require(
                task not in owners
                and {path.name for path in directory.iterdir()} == {"record.json", "gradient.pt"},
                "task cache shadow or incomplete whole task",
            )
            record = checked(directory / "record.json")
            require(
                record["complete_task"] is True
                and record["binding"] == context["task_binding"]
                and record["binding_sha256"]
                == context["math_context_id"]
                == digest(context["task_binding"])
                and record["task_plan_id"] == plan["id"]
                and record["task"] == tasks[task]
                and record["parameter_spec"] == context["parameter_spec"],
                "task point/order/parameter mismatch",
            )
            owners[task] = str(cache)
            inventory[task] = dict(
                task_id=task,
                cache_root=str(cache),
                record=entry(directory / "record.json"),
                gradient=dict(
                    path=str(directory / "gradient.pt"),
                    sha256=record["gradient_sha256"],
                    bytes=record["gradient_bytes"],
                ),
                record_file_identity=old._file_identity(directory / "record.json"),
                gradient_file_identity=old._file_identity(
                    directory / "gradient.pt", size=record["gradient_bytes"]
                ),
            )
            selected.append(task)
        if selected:
            sources.append(
                dict(
                    cache_root=str(cache),
                    task_ids=[task for task in plan["task_ids"] if task in set(selected)],
                )
            )
    parent_ids = [task for task in plan["task_ids"] if task in owners]
    local_ids = [task for task in plan["task_ids"] if task not in owners]
    complete_shards = [stage for stage in SHARDS if stage in bindings]
    for stage in complete_shards:
        require(
            set(plan["assignments"][SHARDS.index(stage)]["task_ids"]) <= set(parent_ids),
            "successful shard lost its actual task tensors",
        )
    record = dict(
        original_context_id=context["id"],
        seed=context["seed"],
        arm=context["arm"],
        step=context["step"],
        task_plan=context["task_plan"],
        task_plan_id=plan["id"],
        binding_sha256=context["math_context_id"],
        task_ids=plan["task_ids"],
        task_records=[inventory[task] for task in parent_ids],
        cache_sources=sources,
    )
    if set(complete_shards) == set(SHARDS):
        require(
            len(parent_ids) == 744 and not local_ids, "complete class requires all actual tensors"
        )
        return dict(
            record, schema=CACHE_SCHEMA, tasks=744, read_only=True, writes_allowed=False
        ), None
    pending = [stage for stage in SHARDS if stage not in complete_shards]
    receipts = [
        stage
        for stage in pending
        if set(plan["assignments"][SHARDS.index(stage)]["task_ids"]) <= set(parent_ids)
    ]
    return None, dict(
        record,
        schema=PARTIAL_CACHE_SCHEMA,
        parent_task_ids=parent_ids,
        local_task_ids=local_ids,
        local_cache_root=str(Path(target) / "task_cache"),
        allowed_new_stages=pending,
        cache_only_receipt_stages=receipts,
        parent_tasks=len(parent_ids),
        new_tasks=len(local_ids),
        total_tasks=744,
        time_limits_removed=True,
        class_deadline_epoch=None,
    )


def _replay_prefix(directory, context, virtual_binding, old_resume=None):
    directory = Path(directory)
    candidates = sorted(
        path for path in (directory / "checkpoints").glob("response[0-9]*") if path.is_dir()
    )
    if not candidates:
        return old_resume
    require(
        all(
            re.fullmatch(r"response\d{6}", path.name) and (path / "record.json").exists()
            for path in candidates
        ),
        "incomplete response checkpoint directory",
    )
    source = candidates[-1]
    record = checked(source / "record.json")
    binding, cursor = record["binding"], record["cursor"]
    _verify_replay_backend(binding, context)
    virtual = read_ref(virtual_binding["result"])
    require(
        record["schema"] == "v19_response_boundary_checkpoint.v1"
        and record["response_prefix_complete"] is True
        and record["no_feedback_generation"] is True
        and record["optimizer_steps_performed"] == 0
        and source.name == f"response{cursor:06d}"
        and 0 <= cursor <= binding["response_count"]
        and (not record["full_replay_complete"] or cursor == binding["response_count"])
        and binding["execution_profile_id"] == context["id"]
        and binding["point_id"] == virtual["point_id"]
        and binding["response_count"] == virtual["response_count"]
        and binding["denominator"] == 700
        and binding["gradient_length_normalized"] is False,
        "response checkpoint point/cohort/cursor mismatch",
    )
    if old_resume is not None:
        require(
            cursor >= old_resume["inherited_response_count"] and binding == old_resume["binding"],
            "response checkpoint rewound or changed binding",
        )
    observed_count = cursor
    observation = directory / "checkpoints/progress/status.json"
    observation_ref = file_ref(observation) if observation.exists() else None
    if observation_ref is not None:
        live = read_ref(observation_ref)
        require(
            live["binding"] == binding
            and live["total_responses"] == binding["response_count"]
            and type(live["completed_responses"]) is int
            and cursor <= live["completed_responses"] <= binding["response_count"],
            "observed replay progress changed its saved checkpoint binding",
        )
        observed_count = live["completed_responses"]
    return dict(
        checkpoint=entry(source / "record.json"),
        observed_response_count=observed_count,
        observed_unpersisted_response_count=observed_count - cursor,
        observed_progress=observation_ref,
        unpersisted_observed_responses_are_not_a_checkpoint=True,
        unpersisted_observed_responses_must_be_recomputed_in_original_order=True,
        state=dict(path=str(source / "state.pt"), sha256=record["state_sha256"]),
        checkpoint_directory=str(source),
        tensor_identity=old._file_identity(source / "state.pt"),
        binding=binding,
        inherited_response_count=cursor,
        total_response_count=binding["response_count"],
        remaining_response_count=binding["response_count"] - cursor,
        parent_stage_launch=entry(directory / "launch/record.json"),
        parent_stage_exit=entry(directory / "exit/record.json"),
        parent_stage_failure=entry(directory / "failure/record.json")
        if (directory / "failure/record.json").exists()
        else None,
        full_replay_complete=record["full_replay_complete"],
        parent_saved_prefix_replayed_again=False,
        state_bytes_verified=False,
        tensor_structure_gradient_and_RNG_verification="unchanged_v19_storage_read_before_resume",
    )


def inspect_automatic_recovery(
    newroot,
    parentroot,
    *,
    authorization_record=None,
    authorization_body=None,
    authorization_root=None,
):
    audit = validate_safe_recovery(parentroot)
    require(audit["allowed"], audit["reason"])
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    protocol = checked(parent / "protocol/record.json")
    supervision = Path(protocol["supervision_root"]).resolve()
    require(
        supervision == ROOT
        and (parent == supervision or parent.parent == supervision / "attempts")
        and root.parent == supervision / "attempts"
        and re.fullmatch(r"attempt\d{4,}", root.name),
        "automatic attempt escaped the explicitly authorized recovery tree",
    )
    number = 1 if parent == supervision else int(parent.name.removeprefix("attempt"))
    require(
        root.name == f"attempt{number + 1:04d}" and not (root / "inheritance/record.json").exists(),
        "automatic attempt must be fresh and strictly sequential",
    )
    authority = _authorization(root, authorization_record, authorization_body)
    return _build_frontier(
        root, parent, protocol, authority, audit, allowed_parent_schemas=(SCHEMA,)
    )


def _build_frontier(root, parent, protocol, authority, audit, *, allowed_parent_schemas):
    prior = read_ref(protocol["inheritance"])
    require(
        prior["schema"] in allowed_parent_schemas and prior["new_root"] == str(parent),
        "parent inheritance changed",
    )
    progress = checked(parent / "actual_final_progress/record.json")
    latest = {(row["seed"], row["arm"]): row for row in progress["arms"]}
    require(
        len(latest) == 9
        and progress["completed_physical_updates"] + progress["remaining_physical_updates"] == 11622
        and progress["completed_outers"] + progress["remaining_outers"] == 24,
        "original nine-model scientific dose changed",
    )
    checkpoints = [
        checkpoint_metadata(row["checkpoint"], coordinate=(row["seed"], row["arm"], row["step"]))
        for row in progress["arms"]
    ]
    prior_items = {row["new_context_directory"]: row for row in prior["context_inheritances"]}
    require(
        all((Path(path) / "context/record.json").is_file() for path in prior_items),
        "registered parent context alias is missing; never recreate it as fresh work",
    )
    stages = list(prior["all_parent_stage_bindings"])
    inherited, completed, superseded, unused = [], [], [], []
    parent_ref = entry(parent / "protocol/record.json")
    for record_path in sorted(parent.glob("contexts/seed*/*/step*/context/record.json")):
        directory = record_path.parent.parent
        source_item = prior_items.get(str(directory))
        original_ref = source_item["original_context"] if source_item else entry(record_path)
        _, context, origin = _actual_context(original_ref)
        plan = read_ref(context["task_plan"]) if context["due_outer"] else None
        bindings, interrupted = {}, {}
        for stage in STAGES:
            older = source_item["stage_bindings"][stage] if source_item else None
            if older and older["protocol_scope"] == "parent":
                source, owner_ref = Path(older["directory"]), older["protocol_ref"]
                binding = inspect_stage(
                    source, read_ref(owner_ref), context, stage, plan, protocol_ref=owner_ref
                )
            else:
                source = directory / stage
                if (source / "launch/record.json").exists() and not (
                    (source / "result/record.json").exists()
                    and checked(source / "exit/record.json")["returncode"] == 0
                    and checked(source / "exit/record.json")["stop_requested"] is False
                ):
                    interrupted[stage] = _interrupted_binding(
                        source, protocol, context["id"], stage
                    )
                    continue
                binding = inspect_stage(
                    source, protocol, context, stage, plan, protocol_ref=parent_ref
                )
            if binding is not None:
                bindings[stage] = binding
                stages.append(binding)
        coordinate = context["seed"], context["arm"]
        actual = latest[coordinate]
        if "train" in bindings:
            completed.append(
                dict(
                    context=entry(record_path),
                    original_context=original_ref,
                    context_id=context["id"],
                    stage_bindings=bindings,
                )
            )
            continue
        if actual["checkpoint"] != context["checkpoint"]:
            limits = [context["execution_plan"]["final_step"]]
            if context["arm"] != "Static":
                limits.extend(
                    step
                    for step in context["execution_plan"]["outer_steps"]
                    if step > context["step"]
                )
            training_limit = context.get(
                "training_stop_step", min(min(limits), context["step"] + 298)
            )
            require(
                "train" in interrupted
                and actual["step"] >= context["step"]
                and actual["step"] <= training_limit,
                "actual state changed outside the interrupted training segment",
            )
            if actual["step"] == 1490:
                endpoint = Path(context["arm_root"]) / "result/record.json"
                require(
                    endpoint.exists(),
                    "unsupported_final_step_without_model_endpoint_seal_requires_user",
                )
                value = checked(endpoint)
                require(
                    value["final_checkpoint"]["path"] == actual["checkpoint"]["path"]
                    and value["result"]["committed_step"] == 1490,
                    "final-model endpoint differs from actual committed state",
                )
            superseded.append(
                dict(
                    context=entry(record_path),
                    actual_checkpoint=actual["checkpoint"],
                    reason="recreate_from_actual_committed_optimizer_and_outer_state_without_repeating_commits",
                )
            )
            continue
        if not bindings and not interrupted:
            unused.append(
                dict(
                    context=entry(record_path),
                    seed=context["seed"],
                    arm=context["arm"],
                    reason="not_dispatched_recreate_from_identical_actual_checkpoint",
                )
            )
            continue
        if not context["due_outer"]:
            require(
                set(interrupted) <= {"train"}, "non-outer attempt has unexpected scientific stage"
            )
            unused.append(
                dict(
                    context=entry(record_path),
                    seed=context["seed"],
                    arm=context["arm"],
                    reason="train_recreate_from_actual_unchanged_checkpoint",
                )
            )
            continue
        target = root / directory.relative_to(parent)
        item = copy.deepcopy(source_item or {})
        current_attempt_bindings = {
            stage: value
            for stage, value in bindings.items()
            if Path(value["directory"]).is_relative_to(parent)
        }
        local_timing = {**current_attempt_bindings, **interrupted}
        timing = _charged_time(
            (source_item or {}).get("inherited_compute_seconds", 0), directory, local_timing
        )
        cache_view, overlay = _automatic_cache(context, directory, target, source_item, bindings)
        resume = (source_item or {}).get("replay_resume")
        if "replay_R3" in interrupted:
            require(
                "virtual_point" in bindings, "interrupted replay lacks sealed same-point feedback"
            )
            resume = _replay_prefix(
                directory / "replay_R3", context, bindings["virtual_point"], resume
            )
        if "replay_R3" in bindings:
            resume = None
        for stage in STAGES:
            bindings.setdefault(
                stage, dict(protocol_scope="current", directory=str(target / stage))
            )
        item.update(
            seed=context["seed"],
            arm=context["arm"],
            step=context["step"],
            original_context=original_ref,
            original_context_id=context["id"],
            origin_context_directory=str(origin),
            immediate_parent_context=entry(record_path),
            immediate_parent_context_directory=str(directory),
            new_context_directory=str(target),
            parent_protocol=parent_ref,
            stage_bindings=bindings,
            task_plan=context["task_plan"],
            task_cache_root=context["task_cache_root"],
            task_cache_view=cache_view,
            task_cache_overlay=overlay,
            replay_resume=resume,
            interrupted_stage_bindings=interrupted,
            phase_deadlines_epoch={},
            phase_first_launch_epoch={},
            phase_deadline_overrides={},
            distribution_recovery_window=False,
            time_limits_removed=True,
            **timing,
        )
        if item.get("feedback_resume") is not None:
            if bindings["virtual_point"]["protocol_scope"] == "parent":
                # Later replay/distribution must read the already completed cohort,
                # not instantiate another partial-feedback view.
                item["feedback_resume"]["new_feedback_base_root"] = source_item["feedback_resume"][
                    "new_feedback_base_root"
                ]
            else:
                item["feedback_resume"]["new_feedback_base_root"] = str(
                    target / "feedback_resume_view"
                )
        inherited.append(item)
    evaluations = copy.deepcopy(prior["completed_evaluations"])
    known = {(row["seed"], row["arm"]) for row in evaluations}
    for seed, arm in latest:
        key = previous.ARM_KEYS[arm]
        directory = parent / f"evaluations/seed{seed}_{key}/generate"
        if not (directory / "result/record.json").exists():
            continue
        binding = inspect_stage(
            directory,
            protocol,
            dict(id=f"evaluation:{seed}:{key}", seed=seed, arm=arm),
            "generate",
            protocol_ref=parent_ref,
        )
        require((seed, arm) not in known, "completed endpoint was generated twice")
        result = read_ref(binding["result"])
        seal = read_ref(result["whole_test_seal"])
        require(
            latest[(seed, arm)]["step"] == 1490
            and seal["denominator"] == 1147
            and seal["all_generation_complete"] is True
            and seal["all_provider_calls_settled"] is True,
            "endpoint is not a complete actual final-model generation seal",
        )
        evaluations.append(
            dict(
                seed=seed,
                arm=arm,
                whole_test_seal=result["whole_test_seal"],
                stage_binding=binding,
                answers_or_scores_read=False,
            )
        )
        stages.append(binding)
    stages = previous._deduplicate(stages)
    sampled = sum(
        700
        for binding in stages
        if Path(binding["directory"]).name == "virtual_point"
        and read_ref(binding["result"]).get("feedback_mode") == "first_sampling"
    )
    pending = sum(
        700
        for item in inherited
        if item["stage_bindings"]["virtual_point"]["protocol_scope"] == "parent"
    )
    partial = [
        item
        for item in inherited
        if item.get("feedback_resume") is not None
        and item["stage_bindings"]["virtual_point"]["protocol_scope"] == "current"
    ]
    require(len(partial) <= 1 and sampled <= 8400, "scientific feedback ownership changed")
    reserved, partial_done = 700 * len(partial), 450 * len(partial)
    virgin = 8400 - sampled - reserved
    require(virgin >= 0 and virgin % 700 == 0, "remaining first-sampling cohort budget invalid")
    budget = dict(
        original_reused_feedback_episodes=2100,
        original_first_sampling_feedback_episodes=8400,
        already_generated_first_sampling_feedback_episodes=sampled,
        already_generated_uncommitted_feedback_episodes=pending,
        pending_sealed_feedback_episodes=pending,
        future_first_sampling_outers=virgin // 700,
        future_first_sampling_feedback_episodes=virgin,
        reserved_partial_feedback_episodes=reserved,
        completed_partial_feedback_episodes=partial_done,
        remaining_partial_feedback_episodes=reserved - partial_done,
        remaining_new_feedback_episodes=8400 - sampled - partial_done,
        remaining_endpoint_answers=(9 - len(evaluations)) * 1147,
        total_endpoint_answers=10323,
    )
    queue = read_ref(file_ref(parent / "queue/status.json"))
    value = copy.deepcopy(prior)
    value.pop("id", None)
    # These describe the historical V50 GPU retirement/bootstrap, not this
    # natural two-worker transition. Keep them as provenance only; all active
    # scheduling uses the actual nine-arm frontier just inspected above.
    superseded_policy = {}
    for key in (
        "Full251_actual_training_restart_step",
        "Full251_initial_training_complete",
        "Full251_actual_training_checkpoint",
        "Full251_training_first_if_incomplete",
        "single_gpu0_authorized",
        "dual_gpu_two_worker_authorized",
        "resource_retirement_handoff",
        "explicit_manual_retirement_not_automatic_failure_retry",
        "final_device_authorization",
        "GPU5_returned",
        "GPU1_returned",
    ):
        if key in value:
            superseded_policy[key] = value.pop(key)
    if superseded_policy:
        value["historical_source_transition_policy"] = superseded_policy
    historical_handoff = value.pop("clean_handoff", None)
    if historical_handoff is not None:
        value["historical_clean_handoff"] = historical_handoff
    value.update(
        schema=SCHEMA,
        at=_stamp(),
        max_gpu_workers=None,
        independent_total_worker_limit=None,
        total_worker_limit_removed=True,
        max_workers_per_gpu=1,
        effective_device_capacity=7,
        allowed_gpu_indices=list(ALLOWED_GPU_INDICES),
        steady_gpu_indices=list(ALLOWED_GPU_INDICES),
        steady_max_gpu_workers=None,
        temporary_gpu0_full251_train_only=False,
        resource_pool_without_independent_cap_authorized=True,
        fixed_gpu_reservation_authorized=True,
        host_ram_runtime_hard_gates_unchanged=True,
        clean_handoff_from_successful_workers=False,
        initial_known_failure_exception_applied=False,
        initial_explicit_signal_recovery_exception_applied=False,
        unknown_signal_automatic_retry_allowed=False,
        new_root=str(root),
        parent_root=str(parent),
        parent_protocol=parent_ref,
        parent_implementation=entry(parent / "implementation/record.json"),
        historical_inheritance=protocol["inheritance"],
        parent_pause=entry(parent / "failure/record.json"),
        parent_failure=entry(parent / "failure/record.json"),
        parent_queue=file_ref(parent / "queue/status.json"),
        actual_final_progress=entry(parent / "actual_final_progress/record.json"),
        recovery_authorization=authority,
        safe_recovery_audit=audit,
        context_inheritances=inherited,
        completed_contexts=completed,
        superseded_interrupted_training_contexts=superseded,
        unused_contexts=unused,
        latest_checkpoints=checkpoints,
        completed_evaluations=evaluations,
        all_parent_stage_bindings=stages,
        accepted_new_optimizer_updates=5810 - progress["remaining_physical_updates"],
        accepted_new_outer_updates=15 - progress["remaining_outers"],
        remaining_optimizer_updates=progress["remaining_physical_updates"],
        remaining_outer_updates=progress["remaining_outers"],
        remaining_scientific_budget=budget,
        inherited_resource_wait_seconds=math.ceil(queue["global_external_resource_wait_seconds"]),
        resource_wait_budget_seconds=None,
        outer_compute_budget_seconds=None,
        time_limits_removed=True,
        original_accounting_reset=False,
    )
    return value


def initialize_automatic_recovery(
    newroot, parentroot, *, authorization_record=None, authorization_root=None
):
    root = Path(newroot).resolve()
    return _publish_aliases(
        root,
        inspect_automatic_recovery(
            root,
            parentroot,
            authorization_record=authorization_record,
            authorization_root=authorization_root,
        ),
    )


initialize_authorized_recovery = initialize_parent_recovery
