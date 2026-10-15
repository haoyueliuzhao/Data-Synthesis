"""One explicitly authorized, no-replay V33 tail-memory supplement.

Reuse the sealed V33 stage lifecycle and its V32 standard-library GPU queue.
Only the new protocol, strict result validation and one-stage run are local.
The original B and the failed V33 trial are read-only, never restart targets.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V25_SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
V33_ROOT = V25_SOURCE_ROOT / "replay_performance_02"
ROOT = V25_SOURCE_ROOT / "replay_performance_03"
FILES = (
    "finqa_v34_tail_controller.py",
    "finqa_v34_tail_worker.py",
    "finqa_v34_tail_memory.py",
)
V33_IMPLEMENTATION_ID = "083b606c1a73566065ab250622a6e926c79aa3e13c472c8fa0221c0cb114cebd"
V33_PROTOCOL_ID = "7ad6c31cff714508e137f2d6b50797b34aa56172e6387f568614c760af96c68a"
V33_CLOSEOUT_ID = "1b410399abc5e0d3425dd9344474ef2cbca8434cbe3e413450487b9e45c562c4"
FINAL_CHECKPOINT_ID = "b4552c908f2aef48f466c0e3de0bb8307e02da596fce59ae6bb62506beff9605"
FINAL_STATE_SHA256 = "a17beb9c26309d1075126fe547853e429449544b2597bb37b81bf59e7cd1072c"
SAVED_GJ_DIGEST = "a75897647fccc988d55edb8e03d7b2bce29d40688390aabbb80d9df41f32c5e5"
FINAL_CHECKPOINT = V33_ROOT / "cohort_replay/checkpoints/response000573"
STAGE = "tail_validation"
STAGES = (STAGE,)
STAGE_TIMEOUTS = {STAGE: 4 * 3600}
FIXED_GPU_INDEX = 7
MAXIMUM_ALLOCATED_BYTES = 76 * 1024**3
MINIMUM_DEVICE_FREE_BYTES = 2 * 1024**3
BACKEND_VERSION = "v34_layout_preserving_class_saved_tensors.v1"
TAIL_STORAGE_POLICY = dict(
    version=BACKEND_VERSION,
    immutable_owner="retain registered storage/version original GPU views",
    activation_pack=(
        "nonoverlapping strided tensor copied exactly into contiguous pinned CPU storage"
    ),
    activation_unpack="restore original GPU shape/stride/storage_offset using independent backing",
    retain_before_pack=(
        "overlap/broadcast, nonstrided, conjugate/negative or quantized views stay on GPU"
    ),
    class_gradient_code_and_reduction_order_unchanged=True,
    cleanup="gc and empty_cache at stage boundaries only; observe before and after",
    every_completed_class_row_resource_gate=True,
    include_model_loading_in_worker_lifetime_peak=True,
    maximum_peak_resets_before_model_load=1,
    peak_resets_after_model_loading_begins=0,
    OOM_fallback=False,
)
AUTHORIZATION_QUESTION = (
    "是否授权另行登记一次末段显存修订与补验：复用已保存梯度，不重采样、"
    "不重放573条、不放宽显存门，原 B 仍暂停？"
)
AUTHORIZATION_ANSWER = "授权"
AUTHORIZATION_SCOPE = (
    "one tail-memory revision and supplemental validation using saved response573 gJ; "
    "no sampling, no response replay, unchanged memory gates; original B stays paused"
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _sealed_body(path, expected_id):
    body = json.loads(Path(path).read_bytes())
    identity = hashlib.sha256(
        json.dumps(
            {k: v for k, v in body.items() if k != "id"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    require(body.get("id") == expected_id == identity, "pinned V33 record changed")
    return body


def _load_v33(name, *, local):
    manifest = _sealed_body(V33_ROOT / "implementation/record.json", V33_IMPLEMENTATION_ID)
    directory = Path(__file__).resolve().parent if local else V33_ROOT / "implementation"
    path = directory / "finqa_v33_bounded_controller.py"
    if local and not path.exists():
        path = V33_ROOT / "implementation/finqa_v33_bounded_controller.py"
    require(
        hashlib.sha256(path.read_bytes()).hexdigest() == manifest["sha256"][path.name],
        "sealed V33 controller bytes changed",
    )
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# These are private module instances; no live or frozen source is modified.
_common = _load_v33(__name__ + "_common", local=False)
_runtime = _load_v33(__name__ + "_runtime", local=True)
ALLOWED_GPUS = _common.ALLOWED_GPUS
MINIMUM_FREE_MIB = _common.MINIMUM_FREE_MIB
WAIT_BUDGET_SECONDS = _common.WAIT_BUDGET_SECONDS
TERM_GRACE_SECONDS = _common.TERM_GRACE_SECONDS
POLL_SECONDS = _common.POLL_SECONDS
COHORT_COMPARISON_KEYS = _common.COHORT_COMPARISON_KEYS


def __getattr__(name):
    return getattr(_runtime, name)


checked = _common.checked
sha = _common.sha
digest = _common.digest
entry = _common.entry
read_ref = _common.read_ref
file_ref = _common.file_ref
publish = _common.publish
now = _common.now
status = _common.status
inventory = _common.inventory
verify_original_B_paused = _common.verify_original_B_paused
worker_environment = _common.worker_environment
birth = _common.birth
signal_owned = _common.signal_owned


def inherited_protocol():
    """Read and hash immutable records only; never deserialize model/tensor state."""
    common = _common.checked_protocol(V33_ROOT)
    require(common["id"] == V33_PROTOCOL_ID, "different V33 source protocol")
    closeout = _sealed_body(V33_ROOT / "closeout_01/record.json", V33_CLOSEOUT_ID)
    checkpoint = _sealed_body(FINAL_CHECKPOINT / "record.json", FINAL_CHECKPOINT_ID)
    require(
        closeout["protocol"] == entry(V33_ROOT / "protocol/record.json")
        and closeout["terminal_queue_snapshot"]["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and closeout["full_validation_pass"] is False
        and closeout["original_failure_reclassified"] is False
        and closeout["GPU_workers_running"] == 0
        and closeout["original_B_resume_authorized"] is False
        and closeout["final_checkpoint"] == entry(FINAL_CHECKPOINT / "record.json")
        and closeout["final_checkpoint_state_sha256"] == FINAL_STATE_SHA256
        and closeout["saved_gJ_CPU_bitwise_digest_equal"] is True
        and closeout["saved_gJ_digest"] == closeout["reference_gJ_digest"] == SAVED_GJ_DIGEST
        and closeout["saved_RNG_digest_equal"] is True
        and closeout["final_checkpoint_semantic_digest_verified"] is True
        and closeout["response16_cold_restore_evidenced"] is True
        and closeout["completed_responses"] == 573,
        "tail supplement requires the sealed failed V33 closeout and verified saved gradient",
    )
    require(
        checkpoint["cursor"] == 573
        and checkpoint["full_replay_complete"] is True
        and checkpoint["response_prefix_complete"] is True
        and checkpoint["optimizer_steps_performed"] == 0
        and checkpoint["no_feedback_generation"] is True
        and checkpoint["state_sha256"] == FINAL_STATE_SHA256
        and sha(FINAL_CHECKPOINT / "state.pt") == FINAL_STATE_SHA256,
        "immutable completed response573 checkpoint changed",
    )
    _common.check_replay_binding(common, checkpoint["binding"], variant="R3")
    queue = json.loads((V33_ROOT / "queue/status.json").read_bytes())
    require(
        queue["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and queue["protocol_id"] == V33_PROTOCOL_ID
        and queue["active_child"] is None
        and all(
            birth(row["pid"]) != row["birth"]
            for row in closeout["controller_and_worker_process_checks"]
        ),
        "old V33 controller or worker is still active; never run alongside it",
    )
    launch = checked(V33_ROOT / "cohort_resume/launch/record.json")
    require(
        launch["protocol_id"] == V33_PROTOCOL_ID
        and launch["gpu_index"] == FIXED_GPU_INDEX
        and launch["gpu_uuid"] == common["gpu_uuids"][str(FIXED_GPU_INDEX)],
        "tail supplement must retain the original paired physical GPU7",
    )
    return common


def authorization_body():
    return dict(
        schema="v34_explicit_tail_supplement_authorization.v1",
        user_date="2026-10-09",
        user_question=AUTHORIZATION_QUESTION,
        user_answer=AUTHORIZATION_ANSWER,
        response_annotation_index=1,
        authorization_scope=AUTHORIZATION_SCOPE,
        original_B_resume_authorized=False,
        prior_closed_trial=entry(V33_ROOT / "closeout_01/record.json"),
    )


def _freeze(root, commit):
    """Commit-bound three new files, then exact ordered copies of 13 V33 files."""
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    require(len(commit) == 40, "full source commit required")
    original = _sealed_body(V33_ROOT / "implementation/record.json", V33_IMPLEMENTATION_ID)
    require(len(original["sha256"]) == 13, "expected exactly thirteen inherited V33 files")
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted source: " + name
        )
        sources[name] = raw
    for name, expected in original["sha256"].items():
        raw = (V33_ROOT / "implementation" / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "frozen V33 dependency changed")
        sources[name] = raw
    destination = Path(root) / "implementation"
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return publish(
        destination / "record.json",
        dict(
            schema="v34_committed_tail_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            inherited_V33_implementation=entry(V33_ROOT / "implementation/record.json"),
            inherited_V33_files=list(original["sha256"]),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )


def protocol_body(common, implementation, root, *, at, observed):
    body = copy.deepcopy({key: value for key, value in common.items() if key != "id"})
    # Prior candidate storage knobs are evidence, not knobs for this tail stage.
    for key in (
        "candidate_base_variant",
        "resident_saved_activation_budget_bytes",
        "resident_activation_and_KV_budgets_independent",
        "activation_budget_admission_rule",
        "activation_budget_is_reservation",
        "allocator_fragmentation_or_OOM_guarantee",
    ):
        body.pop(key, None)
    body.update(
        schema="v34_bounded_tail_memory_protocol.v1",
        at=at,
        source_commit=implementation["source_commit"],
        output_root=str(root),
        implementation_id=implementation["id"],
        inherited_V33_protocol=entry(V33_ROOT / "protocol/record.json"),
        authorization=entry(root / "authorization/record.json"),
        previous_trial_closeout=entry(V33_ROOT / "closeout_01/record.json"),
        source_final_checkpoint=entry(FINAL_CHECKPOINT / "record.json"),
        source_final_checkpoint_state=file_ref(FINAL_CHECKPOINT / "state.pt"),
        saved_gJ_digest=SAVED_GJ_DIGEST,
        stages=list(STAGES),
        fixed_gpu_index=FIXED_GPU_INDEX,
        fixed_gpu_uuid=common["gpu_uuids"][str(FIXED_GPU_INDEX)],
        gpu_observation_at_registration=observed,
        micro_variants=[],
        maximum_micro_response_calls=0,
        warmup_per_variant=0,
        warmup_case_id=None,
        profile_responses=0,
        paired_fresh_R0_baseline_required=False,
        no_new_speedup_claim=True,
        previous_speedup_is_inherited_evidence_only=True,
        candidate_count=1,
        candidate_variant="tail_memory",
        candidate_change="saved class-gradient activation storage and local boundary release only",
        tail_storage_policy=copy.deepcopy(TAIL_STORAGE_POLICY),
        tail_storage_source=file_ref(root / "implementation" / FILES[2]),
        reused_completed_responses=573,
        replayed_responses=0,
        original_reference_full700_reruns=0,
        class_gradient_passes=1,
        full_cohort_validation_count=0,
        independent_class_gradient_rebuilds=1,
        pause_after_response=None,
        pause_resume_new_process=False,
        fresh_tail_process=True,
        tail_supplement_validation_count=1,
        maximum_allocated_bytes=MAXIMUM_ALLOCATED_BYTES,
        minimum_device_free_bytes=MINIMUM_DEVICE_FREE_BYTES,
        resource_limits_unchanged=True,
        stage_timeout_seconds=STAGE_TIMEOUTS,
        original_V33_protocol_or_results_may_be_modified=False,
        original_V33_failure_reclassified=False,
        original_B_resume_authorized=False,
    )
    return body


def initialize(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(root == ROOT, "one registered V34 destination only")
    require(not root.exists(), "never overwrite or silently restart this supplement")
    common = inherited_protocol()
    observed = inventory()
    uuids = {str(row["index"]): row["uuid"] for row in observed if row["index"] in ALLOWED_GPUS}
    require(uuids == common["gpu_uuids"], "physical GPU identities changed since V33")
    implementation = _freeze(root, source_commit)
    publish(root / "authorization/record.json", authorization_body())
    protocol = publish(
        root / "protocol/record.json",
        protocol_body(common, implementation, root, at=now(), observed=observed),
    )
    status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=protocol["id"],
            original_B_resume_authorized=False,
        ),
    )
    return protocol


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "fixed V34 destination required")
    common = inherited_protocol()
    protocol = checked(root / "protocol/record.json")
    implementation = checked(root / "implementation/record.json")
    original = _sealed_body(V33_ROOT / "implementation/record.json", V33_IMPLEMENTATION_ID)
    require(
        implementation["schema"] == "v34_committed_tail_implementation.v1"
        and implementation["committed_files"] == list(FILES)
        and implementation["inherited_V33_implementation"]
        == entry(V33_ROOT / "implementation/record.json")
        and implementation["inherited_V33_files"] == list(original["sha256"])
        and list(implementation["sha256"]) == [*FILES, *original["sha256"]]
        and len(implementation["source_commit"]) == 40,
        "V34 implementation binding or freeze order changed",
    )
    for name, expected in implementation["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen source bytes changed")
        if name in original["sha256"]:
            require(expected == original["sha256"][name], "inherited source differs from V33")
    authorization = checked(root / "authorization/record.json")
    require(
        {k: v for k, v in authorization.items() if k != "id"} == authorization_body(),
        "explicit tail supplement scope changed",
    )
    expected = protocol_body(
        common,
        implementation,
        root,
        at=protocol["at"],
        observed=protocol["gpu_observation_at_registration"],
    )
    require(
        {k: v for k, v in protocol.items() if k != "id"} == expected, "fixed V34 contract changed"
    )
    observed_uuids = {
        str(row["index"]): row["uuid"]
        for row in protocol["gpu_observation_at_registration"]
        if row["index"] in ALLOWED_GPUS
    }
    require(observed_uuids == common["gpu_uuids"], "registered GPU observation changed")
    verify_original_B_paused(protocol)
    return protocol


def eligible(row, protocol):
    return row["index"] == FIXED_GPU_INDEX and _common.eligible(row, protocol)


def check_result(protocol, stage, result):
    require(
        stage == STAGE and result["stage"] == STAGE and result["protocol_id"] == protocol["id"],
        "foreign tail result or stage",
    )
    require(
        result["status"] == "COMPLETE" and result["numeric_pass"] is True,
        "failed or incomplete tail supplement cannot retry or fall back",
    )
    require(
        result["backend_version"] == BACKEND_VERSION,
        "tail result did not use the registered storage backend",
    )
    require(
        all(
            type(result[key]) is int and result[key] == 0
            for key in (
                "API_calls",
                "new_sampling_calls",
                "scoring_calls",
                "optimizer_steps",
                "replayed_responses",
            )
        ),
        "tail supplement performed unauthorized scientific work",
    )
    require(
        type(result["class_gradient_passes"]) is int
        and result["class_gradient_passes"] == 1
        and type(result["reused_completed_responses"]) is int
        and result["reused_completed_responses"] == 573
        and result["original_B_resume_authorized"] is False,
        "tail pass count, saved response reuse or B pause changed",
    )
    require(
        all(result["comparison"].get(key) is True for key in COHORT_COMPARISON_KEYS)
        and all(value is True for value in result["comparison"].values()),
        "all independent tail numerical comparisons must pass",
    )
    resources = result["resources"]
    require(
        resources["all_gates_passed"] is True
        and resources["limits_unchanged"] is True
        and resources["maximum_allocated_bytes"] == MAXIMUM_ALLOCATED_BYTES
        and resources["minimum_device_free_bytes"] == MINIMUM_DEVICE_FREE_BYTES,
        "unchanged allocated-peak and physical-free resource gates required",
    )
    require(
        resources["peak_resets_before_model_load"] == 1
        and resources["peak_resets_after_model_loading_begins"] == 0
        and resources["helper_peak_reset_calls"] == 0,
        "model loading and every tail phase must share one unreset allocated-memory peak",
    )
    observations = resources["observations"]
    require(
        bool(observations) and all(row["passed"] is True for row in observations),
        "every recorded resource gate must pass",
    )
    require(
        {
            "after_model_load.after_cleanup",
            "class_gradients_complete.after_cleanup",
            "after_distribution.after_cleanup",
        }
        <= {row["label"] for row in observations if row["boundary"] is True},
        "model loading, completed class gradients and final distribution need boundary gates",
    )
    for row in observations:
        require(
            row["limits"]
            == dict(
                allocated_memory_limit_bytes=MAXIMUM_ALLOCATED_BYTES,
                free_memory_reserve_bytes=MINIMUM_DEVICE_FREE_BYTES,
            )
            and type(row["boundary"]) is bool
            and row["allocated_pass"] is True
            and row["free_pass"] is True
            and row["stop_requested"] is False,
            "resource observation changed limits or contradicted its pass flag",
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
            and row["allocated_bytes"] <= row["peak_allocated_bytes"] <= MAXIMUM_ALLOCATED_BYTES
            and row["allocated_bytes"] <= row["reserved_bytes"] <= row["peak_reserved_bytes"]
            and row["peak_allocated_bytes"] <= row["peak_reserved_bytes"]
            and row["free_bytes"] <= row["total_bytes"]
            and (not row["boundary"] or row["free_bytes"] >= MINIMUM_DEVICE_FREE_BYTES),
            "recorded allocated peak or boundary physical free failed its unchanged hard gate",
        )
    require(
        resources["observed_peak_allocated_bytes"]
        == max(row["peak_allocated_bytes"] for row in observations)
        and resources["observed_minimum_boundary_free_bytes"]
        == min(row["free_bytes"] for row in observations if row["boundary"]),
        "resource summary disagrees with detailed observations",
    )
    return result


def worker_command(root, stage, row, protocol):
    require(stage == STAGE and row["index"] == FIXED_GPU_INDEX, "unregistered tail launch")
    command = _common.worker_command(root, stage, row, protocol)
    command[5] = str(Path(root) / "implementation" / FILES[1])
    return command


# Adapt only private instances; preserve the original V33 validator and all files.
_runtime.FILES = FILES
_runtime.STAGES = STAGES
_runtime.STAGE_TIMEOUTS = STAGE_TIMEOUTS
_runtime.check_result = lambda protocol, stage, result: check_result(protocol, stage, result)
_runtime.worker_command = lambda root, stage, row, protocol: worker_command(
    root, stage, row, protocol
)
_runtime.birth = lambda pid: birth(pid)
_runtime.signal_owned = lambda launch, sig: signal_owned(launch, sig)
_runtime._runtime.checked_protocol = lambda root: checked_protocol(root)
_runtime._runtime.eligible = lambda row, protocol: eligible(row, protocol)
_runtime.inventory = lambda: inventory()
_runtime.verify_original_B_paused = lambda protocol: verify_original_B_paused(protocol)


class Controller(_runtime.Controller):
    def __init__(self, root=ROOT):
        super().__init__(root)
        self.paired_gpu = dict(index=FIXED_GPU_INDEX, uuid=self.protocol["fixed_gpu_uuid"])

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run only the frozen committed V34 controller",
        )
        lock_path = self.root / "queue/controller.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            publish(
                self.root / "queue/run_intent/record.json",
                dict(
                    schema="v34_bounded_tail_controller_intent.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    pid=os.getpid(),
                    birth=birth(os.getpid()),
                    no_automatic_controller_restart=True,
                ),
            )
            previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            for sig in previous:
                signal.signal(sig, lambda *_: setattr(self, "stop", True))
            try:
                final = self.run_stage(STAGE)
                check_result(self.protocol, STAGE, final)
                publish(
                    self.root / "result/record.json",
                    dict(
                        schema="v34_completed_tail_supplement.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        status="COMPLETE",
                        numeric_pass=True,
                        tail_result=entry(self.root / STAGE / "result/record.json"),
                        tail_supplement_validation_complete=True,
                        original_V33_failure_reclassified=False,
                        original_B_resume_authorized=False,
                        API_calls=0,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        optimizer_steps=0,
                        replayed_responses=0,
                        reused_completed_responses=573,
                        class_gradient_passes=1,
                    ),
                )
                self.update("COMPLETE", tail_supplement_validation_complete=True)
                return True
            except BaseException as error:
                self.update(
                    "STOPPED_FAILURE_NO_RETRY", error_type=type(error).__name__, error=str(error)
                )
                publish(
                    self.root / "failure/record.json",
                    dict(
                        schema="v34_bounded_tail_failure.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        error_type=type(error).__name__,
                        error=str(error),
                        no_automatic_retry=True,
                        no_implicit_fallback=True,
                        original_B_resume_authorized=False,
                    ),
                )
                raise
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "initialize":
        require(args.source_commit is not None, "committed source required")
        result = initialize(args.root, source_commit=args.source_commit)
        print(json.dumps(dict(id=result["id"], status="REGISTERED_NOT_STARTED")))
    elif args.action == "run":
        Controller(args.root).run()
    else:
        result = checked_protocol(args.root)
        print(
            json.dumps(
                dict(
                    id=result["id"], gpu_observation=inventory(), original_B_resume_authorized=False
                )
            )
        )


if __name__ == "__main__":
    main()
