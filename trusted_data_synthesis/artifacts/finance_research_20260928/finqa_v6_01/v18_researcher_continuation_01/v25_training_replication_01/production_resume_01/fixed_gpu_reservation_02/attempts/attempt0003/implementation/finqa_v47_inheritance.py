"""Explicit stopped-V45 recovery and V47 durable-boundary inheritance.

No Tensor is opened here. Actual training commits and original same-point R3
checkpoint/backend bindings remain authoritative; historical unsafe stops are
not relabelled. The new resource shell does not change scientific mathematics.
"""

from __future__ import annotations

import copy
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
SCHEMA = "v47_fixed_gpu_reservation_inheritance.v1"
ALIAS_SCHEMA = "v47_per_stage_original_context_alias.v1"
CACHE_SCHEMA = "v41_complete_read_only_task_cache_view.v1"
PARTIAL_CACHE_SCHEMA = "v43_same_point_partial_task_cache_union.v1"


PRODUCTION_ROOT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/"
    "v25_training_replication_01/production_resume_01"
)
PARENT_ROOT = PRODUCTION_ROOT / "host_memory_admission_01"
FAILED_REGISTRATION_ROOT = PRODUCTION_ROOT / "fixed_gpu_reservation_01"
RECOVERY_PARENT_ROOT = FAILED_REGISTRATION_ROOT / "attempts/attempt0002"
ROOT = PRODUCTION_ROOT / "fixed_gpu_reservation_02"
PROTOCOL_SCHEMA = "v47_fixed_gpu_reservation_supervised_protocol.v1"
PARENT_SCHEMA = "v45_verified_five_worker_handoff_inheritance.v1"
PARENT_PROTOCOL_ID = "920ff2da160a3bbf055c6c3a5b0e9b3a080ca421deb90efce950959f17f735bf"
PARENT_IMPLEMENTATION_ID = "c32c3a60ec4b3fa5c943bfa740cf53bdf985d7da7587f664c068ea8058857a6d"
PARENT_FAILURE_ID = "3708de990d31da5098f28436f908a4c840cc43364ecf58c0bdffb9b195820bc1"
PARENT_PROGRESS_ID = "3490634a666e00f95b735e86912edafb42d7699083ce04378d0f6de5a7dd3462"
UNSAFE_DECISION_ID = "3102a365899f069d172d74623aed571608db280dbec23939867d81b87772467d"
UNSAFE_CLOSEOUT_ID = "336fc20855d627b4c4d777ee80424d4db2304c1fca8f0fc8f6ef5cf3bf4118d0"
EXPECTED_FAILURES = {
    "contexts/seed389/c_only/step1192_outer/replay_R3": dict(
        id="cfa32c0a56e275644dd403376f8c2be0b711b5ceb174cd9b0d945bd5d048652e",
        context_id="4ffac84ac48ccf05375767dadb498eab93ef23029fa87490d2a9d669e00234ce",
        error_type="ValueError",
        error="insufficient free memory for R3 KV/non-KV residency plus reserve",
        returncode=-15,
        recovery_kind="explicit_known_R3_budget_failure_saved_prefix",
    ),
    "contexts/seed389/full/step0894_outer/replay_R3": dict(
        id="ffffbd82768078b78c81e14e150ab706a2e5e8dddfef00d9ab7da1cc6aad2447",
        context_id="a9285e089e3952a9873d38ffc098d07a66f3eb1d85eb9146918752709f0b7e04",
        error_type="ReplayPaused",
        error="replay paused at complete response 133",
        returncode=1,
        recovery_kind="same_pool_stop_saved_response_prefix",
    ),
    "contexts/seed251/full/step1192_outer/train": dict(
        id="c983b5bcdd00dfb316f30ee563edcbf6827637c0ac473971a5de5a60c58bcc66",
        context_id="c668b6cd96ac72b559a253e31cbcb18e93d1a9c2299f32ce2f6920d9532aa693",
        error_type="TailStopRequested",
        error="stop requested at after_real_optimizer_step.before_cleanup",
        returncode=1,
        recovery_kind="same_pool_stop_actual_committed_training_state",
    ),
}
EXPECTED_REPLAYS = {
    (389, "C-only", 1192): dict(
        cursor=240,
        total=419,
        observed=251,
        checkpoint_id="dd0003e7100fc18541c1fe82cd47ae4ed02e7bbda128069163dbdd03ba12a48d",
    ),
    (389, "Full", 894): dict(
        cursor=133,
        total=540,
        observed=133,
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
FAILED_REGISTRATION_CLOSEOUT_ID = (
    "1d721b807e8bbaa94cdb5347b00328ee081be80a4563cd29f4d1fc5b9a6828ba"
)
FAILED_REGISTRATION_PROTOCOL_IDS = (
    "6330364ea55d14a37aee89bd3a954397bb166dd52cdd711197eda4013834ab84",
    "3a0875f2bf448e27b8d82e3c20991d82432fed5bca2aeda6681604054abf0dbd",
)
FAILED_REGISTRATION_FAILURE_IDS = (
    "c8f9cdfc55c376c80bbb840d9eb1648b32b4e7e59bc4b6f3f781c5a35d4bbd32",
    "9d7da5ac015e0a15b4b093ce694bd3f838747891e4ed3a11f9b7cafb1568697d",
)


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


def _initial_failure_audit(parent, authority):
    """New user authority accepts only the exact stopped V45 episode, once."""
    require(
        parent == PARENT_ROOT
        and authority.get("known_failure_recovery_authorized") is True
        and authority.get("parent_failure") == entry(parent / "failure/record.json"),
        "explicit known V45 failure recovery authority required",
    )
    protocol = checked(parent / "protocol/record.json")
    failure = checked(parent / "failure/record.json")
    queue = read_ref(file_ref(parent / "queue/status.json"))
    progress = checked(parent / "actual_final_progress/record.json")
    supervisor = checked(parent / "supervisor/launch/record.json")
    controller = checked(parent / "launch_01/record.json")
    actual_exit = checked(parent / "supervisor/attempt0001/actual_exit/record.json")
    decision = checked(parent / "supervisor/attempt0001/recovery_decision/record.json")
    closeout = checked(parent / "supervisor/closeout/record.json")
    require(
        protocol["id"] == PARENT_PROTOCOL_ID
        and protocol["schema"] == "v45_five_worker_supervised_protocol.v1"
        and protocol["output_root"] == protocol["supervision_root"] == str(parent)
        and protocol["max_gpu_workers"] == 5
        and failure["id"] == PARENT_FAILURE_ID
        and failure["error_type"] == "ValueError"
        and failure["error"] == "worker reported failure: replay_R3"
        and queue["protocol_id"] == protocol["id"]
        and queue["active_children"] == []
        and queue["phase"] == failure["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and failure["stop_error"] is None
        and failure["actual_progress_audit_error"] is None,
        "initial V47 recovery is not the pinned stopped V45 failure",
    )
    old._stopped(controller)
    old._stopped(supervisor)
    require(
        actual_exit["pid"] == controller["pid"]
        and str(actual_exit["birth"]) == str(controller["birth"])
        and actual_exit["attempt_root"] == str(parent)
        and actual_exit["returncode"] == 1
        and actual_exit["manual_stop_requested"] is False
        and actual_exit["stop_forwarded"] is False
        and supervisor["protocol"] == entry(parent / "protocol/record.json")
        and decision["id"] == UNSAFE_DECISION_ID
        and decision["allowed"] is False
        and decision["reason"]
        == "unsafe_or_unsupported_recovery: unsupported_nonresource_failure_requires_user"
        and closeout["id"] == UNSAFE_CLOSEOUT_ID
        and closeout["status"] == "STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY"
        and closeout["final_attempt"] == 1,
        "prior actual exits and unsafe automatic-recovery refusal must remain unchanged",
    )
    require(
        progress["id"] == PARENT_PROGRESS_ID
        and progress["endpoint_scores_or_answers_read"] is False
        and progress["original_state_or_feedback_modified"] is False
        and progress["remaining_physical_updates"] == 1171
        and progress["remaining_outers"] == 3,
        "actual stopped scientific frontier changed",
    )
    arms = {(row["seed"], row["arm"]): row for row in progress["arms"]}
    require(
        len(arms) == 9
        and arms[(251, "Full")]["step"] == 1213
        and arms[(251, "Full")]["outer_done"] == [298, 596, 894, 1192]
        and arms[(389, "C-only")]["step"] == 1192
        and arms[(389, "C-only")]["outer_done"] == [298, 596, 894]
        and arms[(389, "Full")]["step"] == 894
        and arms[(389, "Full")]["outer_done"] == [298, 596],
        "actual SFT1213 / committed outer1192 / two uncommitted points changed",
    )
    failed = {}
    worker_refs = []
    launch_paths = sorted(parent.glob("contexts/seed*/*/step*/*/launch/record.json"))
    launch_paths += sorted(parent.glob("evaluations/*/generate/launch/record.json"))
    for path in launch_paths:
        directory = path.parent.parent
        launch, exited = checked(path), checked(directory / "exit/record.json")
        old._stopped(launch)
        require(
            all(row["protocol_id"] == protocol["id"] for row in (launch, exited))
            and launch["context_id"] == exited["context_id"]
            and launch["stage"] == exited["stage"],
            "worker ownership changed before explicit recovery",
        )
        worker_refs.extend((entry(path), entry(directory / "exit/record.json")))
        if exited["returncode"] == 0 and exited["stop_requested"] is False:
            require(
                (directory / "result/record.json").is_file(), "successful worker result missing"
            )
            continue
        relative = str(directory.relative_to(parent))
        require(
            relative in EXPECTED_FAILURES, "unregistered failed stage cannot use this exception"
        )
        expected = EXPECTED_FAILURES[relative]
        stopped = checked(directory / "failure/record.json")
        require(
            all(
                stopped[key] == expected[key] for key in ("id", "context_id", "error_type", "error")
            )
            and stopped["protocol_id"] == protocol["id"]
            and stopped["context_id"] == launch["context_id"]
            and stopped["stage"] == launch["stage"]
            and exited["returncode"] == expected["returncode"]
            and exited["stop_requested"] is True
            and stopped["API_calls"] == 0
            and stopped["original_mathematical_functions_unchanged"] is True
            and stopped["resources"]["limits_unchanged"] is True
            and not _observed_physical_resource_failure(stopped)
            and all(
                row.get("passed") is True
                or (
                    expected["error_type"] == "TailStopRequested"
                    and row.get("stop_requested") is True
                    and row.get("allocated_pass") is True
                    and row.get("free_pass") is True
                    and row.get("host", {}).get("rss_pass") is True
                    and row.get("host", {}).get("available_pass") is True
                )
                for row in stopped["resources"]["observations"]
            ),
            "known R3 budget failure or lawful pool-stop evidence changed",
        )
        stop = stopped["stop_evidence"]
        if expected["error_type"] == "ValueError":
            require(
                stop["received_signals"] == [] and stop["stop_requested"] is False,
                "initial resource guard must precede the pool-stop consequences",
            )
        else:
            require(
                stop["stop_requested"] is True
                and stop["stop_reason"] == "signal:15"
                and [row["signal_number"] for row in stop["received_signals"]] == [15],
                "pool-stop consequence is not the recorded legal stop",
            )
        failed[relative] = dict(
            directory=str(directory),
            stage=launch["stage"],
            pre_cuda=False,
            recovery_kind=expected["recovery_kind"],
            failure=entry(directory / "failure/record.json"),
        )
    require(
        set(failed) == set(EXPECTED_FAILURES), "the exact three failed workers must be preserved"
    )
    return dict(
        allowed=True,
        reason="new_explicit_authority_for_exact_V45_budget_failure_and_pool_stop",
        previous_automatic_recovery_allowed=False,
        previous_unsafe_decision=entry(
            parent / "supervisor/attempt0001/recovery_decision/record.json"
        ),
        previous_unsafe_closeout=entry(parent / "supervisor/closeout/record.json"),
        previous_failure=entry(parent / "failure/record.json"),
        actual_controller_exit=entry(parent / "supervisor/attempt0001/actual_exit/record.json"),
        interrupted_stages=list(failed.values()),
        evidence_refs=worker_refs,
        unknown_feedback_retry=False,
        numerical_failures_retried=False,
        old_unsafe_failure_relabelled=False,
        additional_scientific_sampling_budget=0,
    )


def _require_initial_frontier(value):
    require(
        value["remaining_optimizer_updates"] == 1171
        and value["remaining_outer_updates"] == 3
        and len(value["completed_evaluations"]) == 6,
        "V47 initial optimizer/outer/endpoint dose changed",
    )
    budget = value["remaining_scientific_budget"]
    require(
        budget["remaining_endpoint_answers"] == 3441
        and budget["pending_sealed_feedback_episodes"] == 1400
        and budget["future_first_sampling_feedback_episodes"] == 700
        and budget["remaining_new_feedback_episodes"] == 700
        and budget["reserved_partial_feedback_episodes"] == 0,
        "V47 initial sealed/future feedback or endpoint ownership changed",
    )
    inherited = {
        (row["seed"], row["arm"], row["step"]): row for row in value["context_inheritances"]
    }
    require(
        set(inherited) == set(EXPECTED_REPLAYS), "only the two stopped R3 contexts may be aliased"
    )
    for coordinate, expected in EXPECTED_REPLAYS.items():
        row = inherited[coordinate]
        replay = row["replay_resume"]
        original_path = (
            R3_REFERENCE
            if coordinate[1] == "C-only"
            else PARENT_ROOT
            / "contexts/seed389/full/step0894_outer/replay_R3"
            / "checkpoints/response000133/record.json"
        )
        original = checked(original_path)
        current = read_ref(replay["checkpoint"])
        _, context, _ = _actual_context(row["original_context"])
        _verify_replay_backend(replay["binding"], context)
        require(
            original["id"] == expected["checkpoint_id"]
            and current["binding"] == original["binding"] == replay["binding"]
            and current["state_sha256"] == original["state_sha256"] == replay["state"]["sha256"]
            and current["state_digest"] == original["state_digest"]
            and replay["inherited_response_count"] == expected["cursor"]
            and replay["total_response_count"] == expected["total"]
            and replay["remaining_response_count"] == expected["total"] - expected["cursor"]
            and replay["observed_response_count"] == expected["cursor"]
            and replay["observed_unpersisted_response_count"] == 0
            and all(
                row["stage_bindings"][stage]["protocol_scope"] == "parent"
                for stage in (*SHARDS, "virtual_point")
            )
            and row["stage_bindings"]["replay_R3"]["protocol_scope"] == "current",
            "actual saved R3 prefix or complete same-point upstream stages changed",
        )
    latest = {(row["seed"], row["arm"]): row for row in value["latest_checkpoints"]}
    actual = {
        (row["seed"], row["arm"]): row
        for row in read_ref(value["actual_final_progress"])["arms"]
    }
    require(latest[(251, "Full")]["step"] == 1213, "Full251 must restart from actual SFT1213")
    require(
        all(row["seed"] != 251 for row in inherited.values())
        and actual[(251, "Full")]["outer_done"] == [298, 596, 894, 1192],
        "committed Full251 outer/SFT must not be replayed as the old training context",
    )
    preserved = {binding["directory"] for binding in value["all_parent_stage_bindings"]}
    require(
        all(
            str(PARENT_ROOT / "contexts/seed251/full/step1192_outer" / stage) in preserved
            for stage in ("virtual_point", "replay_R3", "distribution")
        ),
        "Full251 completed same-point stages must remain read-only source bindings",
    )


def _reregistered_failure_audit(parent, authority):
    """A new user restart, not an automatic exception for the failed registration."""
    failed = FAILED_REGISTRATION_ROOT
    closeout_ref = entry(failed / "closeout_01/record.json")
    operator_ref = entry(failed / "operator_guard_stop/record.json")
    require(
        parent == RECOVERY_PARENT_ROOT
        and authority.get("failed_registration_recovery_authorized") is True
        and authority.get("known_failure_recovery_authorized") is True
        and authority.get("failed_registration_root") == str(failed)
        and authority.get("failed_registration_closeout") == closeout_ref
        and authority.get("failed_registration_operator_stop") == operator_ref
        and authority.get("parent_failure") == entry(parent / "failure/record.json")
        and authority.get("original_mathematical_parent_protocol")
        == entry(PARENT_ROOT / "protocol/record.json")
        and authority.get("original_mathematical_parent_failure")
        == entry(PARENT_ROOT / "failure/record.json"),
        "new explicit corrected-registration restart authority required",
    )
    closeout, operator = read_ref(closeout_ref), read_ref(operator_ref)
    initial_ref = entry(failed / "initial_state/record.json")
    baseline = read_ref(initial_ref)
    require(
        closeout["id"] == FAILED_REGISTRATION_CLOSEOUT_ID
        and closeout["status"] == "STOPPED_IMPLEMENTATION_FAILURE_NO_SCIENTIFIC_PROGRESS"
        and closeout["operator_guard_stop"] == operator_ref
        and closeout["initial_state"] == initial_ref
        and closeout["actual_final_progress"] == entry(parent / "actual_final_progress/record.json")
        and closeout["all_registered_processes_exited"] is True
        and closeout["attempts_launched"] == 2
        and closeout["attempt3_created"] is False
        and all(
            closeout[key] == 0
            for key in (
                "new_response_forward_calls",
                "new_feedback_episodes",
                "provider_API_calls",
                "optimizer_updates",
                "outer_updates",
                "new_endpoint_answers",
            )
        ),
        "the exact two-attempt zero-scientific-progress closeout changed",
    )
    require(
        sorted(path.name for path in (failed / "attempts").iterdir()) == ["attempt0002"],
        "unregistered later attempts cannot use the explicit restart exception",
    )
    supervisor = checked(failed / "supervisor/launch/record.json")
    old._stopped(supervisor)
    stopped_supervisor = read_ref(closeout["supervisor_closeout"])
    require(
        operator["id"] == "ec4a79aa455e5a8a8816c6a8ce3bda1dc1f8df7be2a1f872a6ed47aae36bf0ec"
        and operator["pid"] == supervisor["pid"]
        and str(operator["birth"]) == str(supervisor["birth"])
        and operator["signal_number"] == 15
        and operator["pidfd_used"] is True
        and operator["new_scientific_restart_authorized_by_this_record"] is False
        and stopped_supervisor["status"] == "STOPPED_BY_EXPLICIT_REQUEST"
        and stopped_supervisor["final_attempt"] == 2
        and stopped_supervisor["automatic_recovery_after_manual_stop"] is False,
        "operator stop must remain terminal until this new explicit user authority",
    )
    decision_ref = entry(failed / "supervisor/attempt0001/recovery_decision/record.json")
    decision = read_ref(decision_ref)
    require(
        decision["id"] == "06e92354a70e736ebb3d59e61140b7b6be5465ddf43b89ffcc0949d8883817d8"
        and decision["allowed"] is True
        and closeout["invalid_automatic_recovery_decision"] == decision_ref
        and operator["invalid_automatic_recovery_decision"] == decision_ref,
        "the historical invalid automatic-recovery decision must remain unchanged",
    )
    evidence = [
        closeout_ref, operator_ref, initial_ref, decision_ref, closeout["supervisor_closeout"]
    ]
    phase_history = []
    for number, attempt in enumerate((failed, parent), start=1):
        plan = checked(attempt / "protocol/record.json")
        failure = checked(attempt / "failure/record.json")
        queue_ref = file_ref(attempt / "queue/status.json")
        queue = read_ref(queue_ref)
        launch = checked(attempt / "launch_01/record.json")
        old._stopped(launch)
        exit_ref = entry(failed / f"supervisor/attempt{number:04d}/actual_exit/record.json")
        exited = read_ref(exit_ref)
        progress_ref = entry(attempt / "actual_final_progress/record.json")
        progress = read_ref(progress_ref)
        require(
            plan["id"] == FAILED_REGISTRATION_PROTOCOL_IDS[number - 1]
            and plan["supervision_root"] == str(failed)
            and plan["output_root"] == str(attempt)
            and failure["id"] == FAILED_REGISTRATION_FAILURE_IDS[number - 1]
            and failure["error_type"] == "ValueError"
            and failure["error"]
            == "admission heartbeat does not belong to the actual worker/phase policy"
            and queue["protocol_id"] == failure["protocol_id"]
            == launch["protocol_id"] == plan["id"]
            and queue["active_children"] == []
            and queue["phase"] == failure["phase"] == "STOPPED_FAILURE_NO_RETRY"
            and failure["stop_error"] is None
            and failure["actual_progress_audit_error"] is None
            and exited["pid"] == launch["pid"]
            and str(exited["birth"]) == str(launch["birth"])
            and exited["attempt_root"] == str(attempt)
            and exited["returncode"] == 1
            and exited["manual_stop_requested"] is (number == 2)
            and exited["stop_forwarded"] is (number == 2)
            and progress["arms"] == baseline["arms"]
            and progress["remaining_physical_updates"] == 1171
            and progress["remaining_outers"] == 3
            and progress["endpoint_scores_or_answers_read"] is False
            and progress["original_state_or_feedback_modified"] is False,
            "known failed-registration identity, actual exits or unchanged state changed",
        )
        evidence.extend(
            [
                entry(attempt / "protocol/record.json"), entry(attempt / "failure/record.json"),
                entry(attempt / "launch_01/record.json"), exit_ref, progress_ref, queue_ref,
            ]
        )
        launches = sorted(attempt.glob("contexts/seed*/*/step*/*/launch/record.json"))
        require(
            len(launches) == 1
            and not list(attempt.glob("evaluations/*/generate/launch/record.json")),
            "explicit restart permits only the two registered zero-progress workers",
        )
        worker_path = launches[0]
        directory = worker_path.parent.parent
        worker, worker_exit, stopped = (
            checked(directory / name / "record.json") for name in ("launch", "exit", "failure")
        )
        old._stopped(worker)
        expected_type = "TailStopRequested" if number == 1 else "ReplayPaused"
        reservation = closeout["reservations"][number - 1]
        require(
            all(
                record["protocol_id"] == plan["id"]
                and record["context_id"] == worker["context_id"]
                and record["stage"] == worker["stage"]
                for record in (worker_exit, stopped)
            )
            and stopped["error_type"] == expected_type
            and worker["stage"] == ("train" if number == 1 else "replay_R3")
            and reservation["failure"] == entry(directory / "failure/record.json")
            and reservation["actual_exit"] == entry(directory / "exit/record.json")
            and worker_exit["returncode"] == 1
            and worker_exit["stop_requested"] is True
            and stopped["stop_evidence"]["stop_requested"] is True
            and stopped["API_calls"] == 0
            and stopped["original_mathematical_functions_unchanged"] is True
            and not _observed_physical_resource_failure(stopped),
            "registered child stop or zero-scientific-progress evidence changed",
        )
        phase_history.append(
            dict(
                attempt_root=str(attempt),
                context_id=worker["context_id"],
                stage=worker["stage"],
                launch=entry(worker_path),
                actual_exit=entry(directory / "exit/record.json"),
                failure=entry(directory / "failure/record.json"),
                elapsed_worker_wall_seconds=worker_exit["elapsed_worker_wall_seconds"],
                new_scientific_progress=False,
            )
        )
    replay = closeout["response_checkpoint"]
    original, copied = read_ref(replay["original"]), read_ref(replay["latest"])
    require(
        replay["original"] == entry(R3_REFERENCE)
        and replay["same_actual_tensor_bytes_and_state_digest"] is True
        and replay["latest_tensor_sha256"] == copied["state_sha256"] == original["state_sha256"]
        and copied["state_digest"] == original["state_digest"]
        and copied["binding"] == original["binding"]
        and copied["cursor"] == original["cursor"] == 240,
        "latest copied response240 is not the unchanged original saved scientific state",
    )
    return dict(
        allowed=True,
        reason="new_explicit_user_restart_after_two_known_registration_failures_and_operator_stop",
        previous_automatic_recovery_decision_invalid=True,
        previous_invalid_automatic_recovery_decision=decision_ref,
        original_V45_unsafe_decision=entry(
            PARENT_ROOT / "supervisor/attempt0001/recovery_decision/record.json"
        ),
        historical_failures_reclassified=False,
        explicit_restart_does_not_authorize_unknown_future_failures=True,
        old_unsafe_failure_relabelled=False,
        failed_registration_closeout=closeout_ref,
        operator_stop=operator_ref,
        actual_training_state_unchanged=True,
        new_scientific_calls_in_failed_registration=0,
        phase_history=phase_history,
        latest_resource_wait_snapshot=file_ref(parent / "queue/status.json"),
        evidence_refs=evidence,
        unknown_feedback_retry=False,
        numerical_failures_retried=False,
        additional_scientific_sampling_budget=0,
    )


def inspect_initial_recovery(
    newroot, parentroot, *, authorization_record=None, authorization_body=None
):
    root, parent = Path(newroot).resolve(), Path(parentroot).resolve()
    require(
        root == ROOT
        and parent == RECOVERY_PARENT_ROOT
        and not (root / "inheritance/record.json").exists(),
        "one fresh explicitly authorized V47 root required",
    )
    authority_ref = _authorization(root, authorization_record, authorization_body)
    authority = authorization_body if authorization_body is not None else read_ref(authority_ref)
    audit = _reregistered_failure_audit(parent, authority)
    protocol = checked(parent / "protocol/record.json")
    value = _build_frontier(
        root, parent, protocol, authority_ref, audit, allowed_parent_schemas=(SCHEMA,)
    )
    _require_initial_frontier(value)
    value.update(
        initial_known_failure_exception_applied=True,
        previous_unsafe_recovery_decision_preserved=True,
        failed_registration_phase_history=audit["phase_history"],
        failed_registration_accounting_inherited_from_latest_attempt=True,
        historical_max_observed_C_only389_response_count=251,
        historical_C_only389_observed_but_unpersisted_responses=11,
        previously_committed_Full251_outer1192_repeated=False,
        Full251_actual_training_restart_step=1213,
        C_only389_saved_response_prefix=240,
        C_only389_observed_response_count=240,
        C_only389_observed_but_unpersisted_responses=0,
        C_only389_remaining_ordered_response_calls=179,
        Full389_saved_response_prefix=133,
        Full389_remaining_ordered_response_calls=407,
        zero_additional_replay_claimed=False,
        known_failure_exception_authorizes_future_unknown_errors=False,
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
        and value.get("total_worker_limit_removed") is True
        and value.get("max_gpu_workers") is None
        and "independent_total_worker_limit" in value
        and value["independent_total_worker_limit"] is None
        and value.get("max_workers_per_gpu") == 1
        and value.get("effective_device_capacity") == 8
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
    if Path(parentroot).resolve() == RECOVERY_PARENT_ROOT:
        return inspect_initial_recovery(
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
        "wrong V47 inheritance episode",
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
        schema="v47_r3_changed_capacity_required.v1",
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
        proof["schema"] == "v47_r3_internal_capacity_failure.v1"
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
    producer = Path(protocol["output_root"]) / "implementation/finqa_v47_reservation.py"
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
            stage = launch["stage"]
            if stage in ("virtual_point", "generate") and not pre_cuda:
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
                    recovery_kind="pre_cuda_no_scientific_call"
                    if pre_cuda
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
        effective_device_capacity=8,
        fixed_gpu_reservation_authorized=True,
        host_ram_runtime_hard_gates_unchanged=True,
        clean_handoff_from_successful_workers=False,
        initial_known_failure_exception_applied=False,
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
