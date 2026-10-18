"""One bounded zero-sampling replay validation; never resumes the original B queue.

The controller uses only the standard library before GPU admission. Its worker
is a separate process per stage, including the registered response-16 restart.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import importlib.util
import io
import json
import math
import os
import signal
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V25_SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
ROOT = V25_SOURCE_ROOT / "replay_performance_01"
FROZEN = REPO / ".codex-worktrees/finqa-v18-researcher-continuation-20260930"
PYTHON = REPO / "trusted_data_synthesis/.venv/bin/python"
ALLOWED_GPUS = (3, 4, 5, 7)
MINIMUM_FREE_MIB = 72 * 1024
FILES = (
    "finqa_v32_performance_controller.py",
    "finqa_v32_performance_worker.py",
    "finqa_v32_same_point_guard.py",
    "finqa_v32_replay_variants.py",
    "finqa_v19_optimized_replay.py",
    "finqa_v19_replay_state.py",
)
BASE_SCRIPTS = (
    "fixed_kernel_anchored_segmented_replay_20260916.py",
    "fixed_kernel_anchored_sources_gpu_gate_20260916.py",
    "fixed_kernel_anchored_canonical_saves_20260916.py",
    "fixed_kernel_anchored_saved_tensors_20260916.py",
)
MICRO_STAGES = ("micro_R0", "micro_R1", "micro_R2")
STAGES = (*MICRO_STAGES, "cohort_first", "cohort_resume")
STAGE_TIMEOUTS = {**{stage: 2 * 3600 for stage in STAGES}, "cohort_resume": 14 * 3600}
WAIT_BUDGET_SECONDS = 24 * 3600
TERM_GRACE_SECONDS = 10 * 60
POLL_SECONDS = 10
BENCHMARK_POINT = "946a8dacfdd859ee75515ce946589c7832156995956e6e974b44087e54148238"
TASKSET = Path("/usr/bin/taskset")  # Already used by the original V25 dispatcher.
AUDIT_ATTACHMENT = Path(
    "/home/zhuxinrui/.codex/attachments/0f5929cc-2e4a-40fd-9941-e09535740bc6/已粘贴的文本.txt"
)
BACKEND_VERSION = "v32_v19_storage_adapters_response_boundary.v1"
COHORT_COMPARISON_KEYS = (
    "gJ_bitwise_equal",
    "aggregate_G_bitwise_equal",
    "theta_bar_bitwise_equal",
    "point_id_equal",
    "pullback_bitwise_equal",
    "C_equal",
    "pi_equal",
    "model_optimizer_rng_buffers_unchanged",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(chunk)
    return h.hexdigest()


def file_ref(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(path))


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "record identity changed: " + str(path),
    )
    return value


def entry(path):
    return {**file_ref(path), "id": checked(path)["id"]}


def read_ref(ref):
    require(file_ref(ref["path"])["sha256"] == ref["sha256"], "bound file bytes changed")
    value = checked(ref["path"])
    require(value["id"] == ref["id"], "bound record identity changed")
    return value


def publish(path, body):
    """Immutable durable JSON. Used for protocol/results, never original artifacts."""
    path = Path(path)
    require("id" not in body, "publish expects a new body")
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {**body, "id": digest(body)}
    with path.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return result


def status(root, body):
    path = Path(root) / "queue/status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"status.{os.getpid()}.tmp")
    with temporary.open("w") as stream:
        json.dump({"at": now(), **body}, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "missing frozen module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def frozen_training_module():
    """Import the V25 source snapshot; no model or CUDA construction."""
    path = V25_SOURCE_ROOT / "implementation/finqa_v25_training_replication.py"
    manifest = checked(V25_SOURCE_ROOT / "implementation/record.json")
    require(sha(path) == manifest["sha256"][path.name], "original V25 worker source changed")
    name = "finqa_v25_training_replication"
    old = sys.modules.get(name)
    if old is not None:
        require(Path(old.__file__).resolve() == path.resolve(), "non-frozen V25 module imported")
        return old
    return _module(path, name)


def inventory():
    """No torch import, no context, no memory allocation or reservation."""
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.total,memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    processes = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,used_memory",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    by_uuid = {}
    for fields in csv.reader(io.StringIO(processes), skipinitialspace=True):
        if not fields:
            continue
        uuid, pid, memory = (field.strip() for field in fields)
        by_uuid.setdefault(uuid, []).append(dict(pid=int(pid), used_memory_mib=memory))
    result = []
    for fields in csv.reader(io.StringIO(raw), skipinitialspace=True):
        index, uuid, total, used, free = (field.strip() for field in fields)
        result.append(
            dict(
                index=int(index),
                uuid=uuid,
                total_mib=int(total),
                used_mib=int(used),
                free_mib=int(free),
                processes=by_uuid.get(uuid, []),
            )
        )
    return result


def eligible(row, protocol):
    return (
        row["index"] in ALLOWED_GPUS
        and row["uuid"] == protocol["gpu_uuids"].get(str(row["index"]))
        and not row["processes"]
        and row["free_mib"] >= MINIMUM_FREE_MIB
    )


def verify_original_B_paused(protocol):
    reference = protocol["original_B_queue_status"]
    path = V25_SOURCE_ROOT / "four_gpu_release_01/queue/status.json"
    require(Path(reference["path"]).resolve() == path, "foreign original-B queue status path")
    value = json.loads(path.read_bytes())
    require(
        value["protocol_id"] == reference["protocol_id"]
        and value["phase"] == "PAUSED_BY_USER_CHECKPOINT_SAVED"
        and value["active_children"] == []
        and value["automatic_resume_authorized"] is False,
        "original B is no longer cold-paused; performance dispatch forbidden",
    )
    return value


def worker_environment(row):
    return {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": row["uuid"],
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(FROZEN / "trusted_data_synthesis/src"),
        "OMP_NUM_THREADS": "4",
        "MKL_NUM_THREADS": "4",
        "TOKENIZERS_PARALLELISM": "false",
    }


def worker_command(root, stage, row, protocol):
    return [
        str(TASKSET),
        "--cpu-list",
        protocol["cpu_affinity"][str(row["index"])],
        str(PYTHON),
        "-u",
        str(Path(root) / "implementation/finqa_v32_performance_worker.py"),
        "--root",
        str(root),
        "--stage",
        stage,
        "--gpu-index",
        str(row["index"]),
    ]


def select_cases(cohort, rewards):
    """Select by workload lengths before examining any candidate timings/errors."""
    rows = []
    for episode_index, (episode, reward) in enumerate(zip(cohort.episodes, rewards, strict=True)):
        if reward == 0:
            continue
        for turn_index, turn in enumerate(episode.turns):
            receipt = turn.receipt
            rows.append(
                dict(
                    response_index=len(rows),
                    episode_index=episode_index,
                    turn_index=turn_index,
                    call_id=receipt.call_id,
                    prompt_tokens=len(receipt.prompt_input_ids),
                    output_tokens=len(receipt.raw_generated_token_ids),
                    receipt_sha256=digest(receipt.model_dump(mode="json")),
                )
            )
    require(rows, "empty replay workload cannot support a performance trial")
    medians = {
        key: statistics.median(row[key] for row in rows)
        for key in ("prompt_tokens", "output_tokens")
    }
    selected, counts = {}, {}
    for row in rows:
        cell = "_".join(
            "short" if row[key] <= medians[key] else "long"
            for key in ("prompt_tokens", "output_tokens")
        )
        counts[cell] = counts.get(cell, 0) + 1
        selected.setdefault(cell, {"case_id": cell, **row})
    cases = sorted(selected.values(), key=lambda row: row["response_index"])
    return cases, medians, counts, len(rows)


def _freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    require(len(commit) == 40, "full source commit required")
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative),
            "source has uncommitted changes: " + name,
        )
        sources[name] = raw
    for name in BASE_SCRIPTS:
        original = FROZEN / "trusted_data_synthesis/scripts" / name
        raw = original.read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / "trusted_data_synthesis/scripts" / name),
            "retained baseline helper differs from frozen V18: " + name,
        )
        sources[name] = raw
    destination = Path(root) / "implementation"
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    manifest = publish(
        destination / "record.json",
        dict(
            schema="v32_committed_performance_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            retained_V18_files=list(BASE_SCRIPTS),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
            original_training_implementation=entry(V25_SOURCE_ROOT / "implementation/record.json"),
        ),
    )
    return commit, manifest


def initialize(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(root == ROOT, "one registered performance destination only")
    require(not root.exists(), "never overwrite or silently restart the performance trial")
    pause = entry(V25_SOURCE_ROOT / "four_gpu_release_01/experiment_pause_01/cold_stop/record.json")
    old = read_ref(pause)
    require(
        old["controller_and_workers_absent"] and not old["automatic_resume_authorized"],
        "original B must remain cold-paused",
    )
    original_science = entry(V25_SOURCE_ROOT / "protocol/record.json")
    original_plan = read_ref(original_science)
    old_status_path = V25_SOURCE_ROOT / "four_gpu_release_01/queue/status.json"
    old_status_ref = dict(
        path=str(old_status_path),
        protocol_id=json.loads(old_status_path.read_bytes())["protocol_id"],
    )
    verify_original_B_paused(dict(original_B_queue_status=old_status_ref))
    commit, implementation = _freeze(root, source_commit)
    audit_raw = AUDIT_ATTACHMENT.read_bytes()
    publish(
        root / "audit_request/record.json",
        dict(
            schema="v32_user_supplied_audit_request.v1",
            at=now(),
            text=audit_raw.decode("utf-8"),
            source_file_sha256=hashlib.sha256(audit_raw).hexdigest(),
            source_file_path=str(AUDIT_ATTACHMENT),
            source_file_bytes=len(audit_raw),
            user_request="参照审计修订并开展后续实验",
            linked_sandbox_md_zip_not_supplied=True,
            authorization_scope=(
                "bounded zero-new-sampling performance validation only; B stays paused"
            ),
        ),
    )
    frozen_training_module()
    guard = _module(root / "implementation/finqa_v32_same_point_guard.py", "v32_registration_guard")
    manifests, benchmark = [], None
    for target in guard.registered_targets():
        manifest = guard.build_manifest(
            target["checkpoint"],
            target["feedback_root"],
            expected_point_id=target["expected_point_id"],
        )
        path = root / "manifests" / target["name"] / "record.json"
        publish(path, {key: value for key, value in manifest.items() if key != "id"})
        manifests.append(entry(path))
        if target["purpose"] == "completed_point_benchmark":
            benchmark = entry(path)
    require(benchmark is not None, "completed benchmark manifest is required")
    manifest = read_ref(benchmark)
    require(manifest["point_id"] == BENCHMARK_POINT, "fixed C-only137 outer298 required")
    cohort, rewards = guard.read_sealed_feedback(manifest)
    cases, medians, cell_counts, responses = select_cases(cohort, rewards)
    response_order = [
        [episode_index, turn_index, turn.receipt.call_id]
        for episode_index, episode in enumerate(cohort.episodes)
        if rewards[episode_index] != 0
        for turn_index, turn in enumerate(episode.turns)
    ]
    require(
        medians == dict(prompt_tokens=4123, output_tokens=140)
        and responses == 573
        and [
            (
                row["response_index"],
                row["episode_index"],
                row["turn_index"],
                row["prompt_tokens"],
                row["output_tokens"],
            )
            for row in cases
        ]
        == [
            (0, 2, 0, 3648, 177),
            (2, 4, 0, 2761, 120),
            (8, 11, 0, 6755, 147),
            (9, 11, 1, 7021, 125),
        ],
        "fixed workload selection changed; no substitution or additional cases",
    )
    observed = inventory()
    uuids = {str(row["index"]): row["uuid"] for row in observed if row["index"] in ALLOWED_GPUS}
    require(
        set(uuids) == {str(index) for index in ALLOWED_GPUS}, "four allowed GPUs must be visible"
    )
    protocol = publish(
        root / "protocol/record.json",
        dict(
            schema="v32_bounded_replay_performance_protocol.v1",
            at=now(),
            source_commit=commit,
            output_root=str(root),
            implementation_id=implementation["id"],
            original_B_pause=pause,
            audit_request=entry(root / "audit_request/record.json"),
            original_scientific_protocol=original_science,
            original_B_queue_status=old_status_ref,
            cpu_affinity={
                str(index): original_plan["cpu_affinity"][str(index)] for index in ALLOWED_GPUS
            },
            taskset=file_ref(TASKSET),
            CPU_environment=dict(
                OMP_NUM_THREADS="4", MKL_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false"
            ),
            original_B_resume_authorized=False,
            original_B_training_or_evaluation_allowed=False,
            original_sources_may_be_modified=False,
            same_point_manifests=manifests,
            benchmark_manifest=benchmark,
            source_outer=dict(
                path=manifest["checkpoint"],
                record=manifest["checkpoint_record"],
                state=manifest["checkpoint_state"],
                outer_inputs=manifest["outer_inputs"],
            ),
            allowed_gpu_indices=list(ALLOWED_GPUS),
            gpu_uuids=uuids,
            max_gpu_workers=1,
            minimum_free_mib=MINIMUM_FREE_MIB,
            require_no_compute_processes=True,
            gpu_observation_at_registration=observed,
            paired_stages_same_physical_gpu=True,
            memory_reservation_or_blank_cache=False,
            cases=cases,
            median_thresholds=medians,
            case_cell_counts=cell_counts,
            case_selection=(
                "per-axis median; short<=median; first original ordered response per cell; "
                "empty cells stay empty"
            ),
            warmup_case_id="short_short",
            warmup_per_variant=1,
            profile_case_id="short_short",
            profile_variant="R0",
            profile_responses=1,
            micro_variants=["R0", "R1", "R2"],
            maximum_micro_response_calls=16,
            profiler_or_warmup_in_speed_ratio=False,
            block_size=8,
            checkpoint_every_responses=16,
            pause_after_response=16,
            resident_saved_KV_budget_bytes=2 * 1024**3,
            denominator=700,
            full_kv_budget_bytes=8 * 1024**3,
            allocated_memory_limit_bytes=76 * 1024**3,
            free_memory_reserve_bytes=2 * 1024**3,
            actual_response_count=responses,
            saved_reward_count=700,
            replay_binding_expected=dict(
                point_id=manifest["point_id"],
                parameter_digest=manifest["intent"]["identity"]["parameter_digest"],
                cohort_seal_sha256=manifest["cohort_seal_sha256"],
                reward_sha256=manifest["rewards_sha256"],
                response_order_sha256=digest(response_order),
                rng_restore_source=dict(
                    outer_inputs=manifest["outer_inputs"],
                    field="pre_state.rng",
                    digest=manifest["component_digest"]["rng"],
                ),
                backend_version=BACKEND_VERSION,
                adapter_source=file_ref(root / "implementation/finqa_v32_replay_variants.py"),
                inherited_V19_source=file_ref(
                    root / "implementation/finqa_v19_optimized_replay.py"
                ),
            ),
            sampling_logp_atol=1e-6,
            sampling_logp_rtol=1e-5,
            require_bitwise_logp_gradient=True,
            minimum_speedup=1.20,
            R2_minimum_extra_speedup=1.05,
            full_cohort_validation_count=1,
            original_full_cohort_baseline_reruns=0,
            independent_class_gradient_rebuilds=1,
            class_gradients_same_frozen_numerics=True,
            pause_resume_new_process=True,
            resource_wait_budget_seconds=WAIT_BUDGET_SECONDS,
            stage_timeout_seconds=STAGE_TIMEOUTS,
            term_grace_seconds=TERM_GRACE_SECONDS,
            no_automatic_retry=True,
            no_implicit_fallback=True,
            original_B_auto_dispatch=False,
            API_calls=0,
            api_model="deepseek-flash",
            new_sampling_calls=0,
            scoring_calls=0,
            optimizer_steps=0,
            maximum_gpu_workers_including_CPU_initialization=1,
        ),
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
    require(root == ROOT, "fixed performance destination required")
    protocol = checked(root / "protocol/record.json")
    manifest = checked(root / "implementation/record.json")
    require(
        protocol["schema"] == "v32_bounded_replay_performance_protocol.v1"
        and protocol["output_root"] == str(root)
        and protocol["implementation_id"] == manifest["id"]
        and protocol["source_commit"] == manifest["source_commit"]
        and set(manifest["sha256"]) == set(FILES + BASE_SCRIPTS),
        "implementation binding changed",
    )
    require(
        all(
            sha(root / "implementation" / name) == expected
            for name, expected in manifest["sha256"].items()
        ),
        "frozen performance source changed",
    )
    require(
        protocol["allowed_gpu_indices"] == list(ALLOWED_GPUS)
        and protocol["max_gpu_workers"] == 1
        and protocol["minimum_free_mib"] == MINIMUM_FREE_MIB
        and protocol["require_no_compute_processes"] is True
        and protocol["original_B_resume_authorized"] is False
        and protocol["original_B_training_or_evaluation_allowed"] is False
        and protocol["maximum_micro_response_calls"] == 16
        and protocol["pause_after_response"] == protocol["checkpoint_every_responses"] == 16
        and protocol["denominator"] == 700
        and protocol["block_size"] == 8
        and protocol["actual_response_count"] == 573
        and protocol["median_thresholds"] == dict(prompt_tokens=4123, output_tokens=140)
        and protocol["warmup_case_id"] == protocol["profile_case_id"] == "short_short"
        and protocol["warmup_per_variant"] == protocol["profile_responses"] == 1
        and protocol["profile_variant"] == "R0"
        and protocol["micro_variants"] == ["R0", "R1", "R2"]
        and protocol["profiler_or_warmup_in_speed_ratio"] is False
        and protocol["full_cohort_validation_count"] == 1
        and protocol["original_full_cohort_baseline_reruns"] == 0
        and protocol["independent_class_gradient_rebuilds"] == 1
        and protocol["class_gradients_same_frozen_numerics"] is True
        and protocol["paired_stages_same_physical_gpu"] is True
        and protocol["memory_reservation_or_blank_cache"] is False
        and protocol["pause_resume_new_process"] is True
        and protocol["sampling_logp_atol"] == 1e-6
        and protocol["sampling_logp_rtol"] == 1e-5
        and protocol["resident_saved_KV_budget_bytes"] == 2 * 1024**3
        and protocol["full_kv_budget_bytes"] == 8 * 1024**3
        and protocol["allocated_memory_limit_bytes"] == 76 * 1024**3
        and protocol["free_memory_reserve_bytes"] == 2 * 1024**3
        and protocol["require_bitwise_logp_gradient"] is True
        and protocol["minimum_speedup"] == 1.20
        and protocol["R2_minimum_extra_speedup"] == 1.05
        and protocol["resource_wait_budget_seconds"] == WAIT_BUDGET_SECONDS
        and protocol["stage_timeout_seconds"] == STAGE_TIMEOUTS
        and protocol["term_grace_seconds"] == TERM_GRACE_SECONDS
        and protocol["no_automatic_retry"] is True
        and protocol["no_implicit_fallback"] is True
        and protocol["API_calls"]
        == protocol["new_sampling_calls"]
        == protocol["scoring_calls"]
        == protocol["optimizer_steps"]
        == 0,
        "fixed bounded trial contract changed",
    )
    read_ref(protocol["original_B_pause"])
    audit = read_ref(protocol["audit_request"])
    require(
        audit["linked_sandbox_md_zip_not_supplied"] is True
        and audit["authorization_scope"]
        == "bounded zero-new-sampling performance validation only; B stays paused"
        and hashlib.sha256(audit["text"].encode("utf-8")).hexdigest() == audit["source_file_sha256"]
        and len(audit["text"].encode("utf-8")) == audit["source_file_bytes"],
        "bound user audit text or bounded authorization changed",
    )
    verify_original_B_paused(protocol)
    original_plan = read_ref(protocol["original_scientific_protocol"])
    require(
        protocol["cpu_affinity"]
        == {str(index): original_plan["cpu_affinity"][str(index)] for index in ALLOWED_GPUS}
        and protocol["taskset"] == file_ref(TASKSET)
        and protocol["CPU_environment"]
        == dict(OMP_NUM_THREADS="4", MKL_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false"),
        "original CPU locality or four-thread environment changed",
    )
    read_ref(manifest["original_training_implementation"])
    for ref in protocol["same_point_manifests"]:
        read_ref(ref)
    benchmark = read_ref(protocol["benchmark_manifest"])
    replay = protocol["replay_binding_expected"]
    require(
        protocol["benchmark_manifest"] in protocol["same_point_manifests"]
        and benchmark["point_id"] == BENCHMARK_POINT
        and replay["point_id"] == BENCHMARK_POINT
        and replay["parameter_digest"] == benchmark["intent"]["identity"]["parameter_digest"]
        and replay["cohort_seal_sha256"] == benchmark["cohort_seal_sha256"]
        and replay["reward_sha256"] == benchmark["rewards_sha256"]
        and replay["rng_restore_source"]
        == dict(
            outer_inputs=benchmark["outer_inputs"],
            field="pre_state.rng",
            digest=benchmark["component_digest"]["rng"],
        )
        and replay["backend_version"] == BACKEND_VERSION
        and replay["adapter_source"]
        == file_ref(root / "implementation/finqa_v32_replay_variants.py")
        and replay["inherited_V19_source"]
        == file_ref(root / "implementation/finqa_v19_optimized_replay.py")
        and protocol["source_outer"]
        == dict(
            path=benchmark["checkpoint"],
            record=benchmark["checkpoint_record"],
            state=benchmark["checkpoint_state"],
            outer_inputs=benchmark["outer_inputs"],
        ),
        "benchmark and original outer bindings changed",
    )
    return protocol


def check_replay_binding(protocol, binding, *, variant):
    """JSON-only identity check before admitting a durable replay boundary."""
    expected = protocol["replay_binding_expected"]
    require(
        binding["schema"] == "v32_fixed_replay_point_binding.v1"
        and binding["execution_profile_id"] == protocol["id"]
        and all(
            binding[key] == expected[key]
            for key in (
                "point_id",
                "parameter_digest",
                "cohort_seal_sha256",
                "reward_sha256",
                "response_order_sha256",
                "rng_restore_source",
            )
        )
        and binding["response_count"] == protocol["actual_response_count"]
        and binding["denominator"] == 700
        and binding["block_size"] == 8
        and binding["gradient_length_normalized"] is False
        and binding["checkpoint_every_responses"] == 16
        and binding["replay_state_adapter"] == expected["backend_version"] == BACKEND_VERSION
        and len(binding["reward_vector"]) == 700
        and all(
            type(value) in (int, float) and value in (0, 1) for value in binding["reward_vector"]
        )
        and digest(binding["reward_vector"]) == expected["reward_sha256"]
        and len(binding["response_order"]) == protocol["actual_response_count"]
        and digest(binding["response_order"]) == expected["response_order_sha256"]
        and variant in ("R1", "R2")
        and binding["backend_identity"]
        == dict(
            protocol_id=protocol["id"],
            variant=variant,
            version=expected["backend_version"],
            adapter_source=expected["adapter_source"],
            inherited_V19_source=expected["inherited_V19_source"],
        ),
        "replay checkpoint point/reward/order/RNG/backend differs from protocol",
    )


def check_prefix_checkpoint(protocol, result):
    checkpoint = result["checkpoint"]
    require(
        checkpoint["schema"] == "v19_response_boundary_checkpoint.v1"
        and checkpoint["id"]
        == digest({key: value for key, value in checkpoint.items() if key != "id"})
        and checkpoint["cursor"] == 16
        and checkpoint["response_prefix_complete"] is True
        and checkpoint["full_replay_complete"] is False
        and checkpoint["optimizer_steps_performed"] == 0
        and checkpoint["no_feedback_generation"] is True,
        "response16 checkpoint is not a complete immutable prefix boundary",
    )
    check_replay_binding(protocol, checkpoint["binding"], variant=result["selected_variant"])
    report = result["replay_report"]
    require(
        report["response_checkpoint_binding"] == checkpoint["binding"]
        and report["restored_completed_responses"] == 0
        and report["completed_responses"] == report["accounting"]["responses_replayed"] == 16
        and report["complete_replay"] is False
        and report["pause_reason"] == "registered_boundary"
        and report["new_sampling_calls"] == report["optimizer_steps_performed"] == 0,
        "prefix report contradicts the durable response16 checkpoint",
    )


def verify_durable_prefix(protocol, result):
    """Check the actual record and tensor bytes without deserializing a model."""
    root = Path(protocol["output_root"])
    directory = root / "cohort_replay/checkpoints/response000016"
    record = checked(directory / "record.json")
    require(
        record == result["checkpoint"] and sha(directory / "state.pt") == record["state_sha256"],
        "durable response16 checkpoint missing or changed",
    )
    selection = checked(root / "selection/record.json")
    require(
        selection["protocol_id"] == protocol["id"]
        and selection["selected_variant"] == result["selected_variant"],
        "replay backend differs from preregistered selection",
    )


def check_result(protocol, stage, result):
    require(
        result["protocol_id"] == protocol["id"] and result["stage"] == stage,
        "result belongs to another stage or protocol",
    )
    require(
        all(
            result[key] == 0
            for key in ("API_calls", "new_sampling_calls", "scoring_calls", "optimizer_steps")
        ),
        "performance validation changed scientific work",
    )
    require(result["numeric_pass"] is True, "numerical failure stops all remaining bounded work")
    expected_status = "PAUSED_AT_REGISTERED_BOUNDARY" if stage == "cohort_first" else "COMPLETE"
    require(result["status"] == expected_status, "failed, OOM or incomplete stage cannot fall back")
    if stage in MICRO_STAGES:
        elapsed = result["unprofiled_seconds"]
        require(
            type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed > 0,
            "positive finite unprofiled replay time required",
        )
        rows = result["case_results"]
        require(len(rows) == len(protocol["cases"]), "every registered case must be measured")
        for wanted, row in zip(protocol["cases"], rows, strict=True):
            require(
                row["case_id"] == wanted["case_id"]
                and row["response_index"] == wanted["response_index"]
                and all(
                    row[key] is True
                    for key in (
                        "bitwise_logp_equal",
                        "bitwise_gradient_equal",
                        "shape_dtype_keys_equal",
                        "state_unchanged",
                    )
                )
                and row["logp_digest"] == row["baseline_logp_digest"]
                and row["gradient_digest"] == row["baseline_gradient_digest"],
                "aggregate numerical pass cannot override a contradictory case",
            )
            require(
                type(row["seconds"]) in (int, float)
                and math.isfinite(row["seconds"])
                and row["seconds"] > 0
                and type(row["peak_allocated_bytes"]) is int
                and 0 < row["peak_allocated_bytes"] <= 76 * 1024**3
                and type(row["peak_reserved_bytes"]) is int
                and row["peak_reserved_bytes"] >= row["peak_allocated_bytes"],
                "case timing or complete allocated-memory envelope failed",
            )
        require(
            math.isclose(sum(row["seconds"] for row in rows), elapsed, rel_tol=1e-12, abs_tol=1e-9),
            "unprofiled total must include exactly the registered measured cases",
        )
    elif stage == "cohort_first":
        require(
            result["pause_cursor"] == 16 and result["full_cohort_validation_complete"] is False,
            "only the registered response16 cold boundary may advance to resume",
        )
        require(
            result["model_optimizer_rng_buffers_unchanged"] is True,
            "prefix pause changed actual model/Adam/RNG/buffers",
        )
        check_prefix_checkpoint(protocol, result)
    else:
        require(
            result["full_cohort_validation_complete"] is True,
            "complete saved-cohort comparison required",
        )
        require(
            all(result["comparison"].get(key) is True for key in COHORT_COMPARISON_KEYS)
            and result["class_gradient_passes"] == 1
            and result["original_reference_full700_reruns"] == 0
            and result["pause_resume_verified"] is True
            and result["replay_report"]["restored_completed_responses"] == 16
            and result["replay_report"]["complete_replay"] is True
            and result["replay_report"]["accounting"]["responses_replayed"]
            == protocol["actual_response_count"],
            "full-cohort comparison or actual cold-resume proof contradicts summary",
        )
        check_replay_binding(
            protocol,
            result["replay_report"]["response_checkpoint_binding"],
            variant=result["selected_variant"],
        )
    return result


def choose_variant(protocol, results):
    """Inspect every result before selection; no recovery from a failed R2 trial."""
    for stage in MICRO_STAGES:
        check_result(protocol, stage, results[stage])
    times = {
        stage.removeprefix("micro_"): results[stage]["unprofiled_seconds"] for stage in MICRO_STAGES
    }
    admitted = [name for name in ("R1", "R2") if times[name] <= times["R0"] / 1.20]
    if not admitted:
        selected = None
    elif admitted == ["R1", "R2"]:
        selected = "R2" if times["R2"] <= times["R1"] / 1.05 else "R1"
    else:
        selected = admitted[0]
    return dict(
        selected_variant=selected,
        unprofiled_seconds=times,
        eligible_variants=admitted,
        minimum_speedup=1.20,
        R2_minimum_extra_speedup=1.05,
        selection_is_not_formal_B_resume_authority=True,
    )


def birth(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def signal_owned(launch, sig):
    """Never signal a process merely because its old PID still exists."""
    if birth(launch["pid"]) != launch["birth"]:
        return False
    try:
        command = Path(f"/proc/{launch['pid']}/cmdline").read_bytes().split(b"\0")
    except (FileNotFoundError, ProcessLookupError):
        return False
    command = [part.decode() for part in command if part]
    require(
        launch["worker"] in command
        and "--stage" in command
        and command[command.index("--stage") + 1] == launch["stage"],
        "PID/birth matches but worker command does not; no signal sent",
    )
    if birth(launch["pid"]) != launch["birth"]:
        return False
    try:
        os.kill(launch["pid"], sig)
    except ProcessLookupError:
        return False
    return True


class Controller:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.protocol = checked_protocol(self.root)
        self.wait_used = 0.0
        self.paired_gpu = None
        self.stop = False
        self.active = None

    def update(self, phase, **extra):
        status(
            self.root,
            dict(
                phase=phase,
                protocol_id=self.protocol["id"],
                resource_wait_seconds=self.wait_used,
                active_child=self.active,
                original_B_resume_authorized=False,
                **extra,
            ),
        )

    def verify_original_B_paused(self):
        return verify_original_B_paused(self.protocol)

    def acquire_gpu(self, stage):
        while not self.stop:
            require(
                self.wait_used < WAIT_BUDGET_SECONDS, "24-hour resource waiting budget exhausted"
            )
            started = time.monotonic()
            rows = inventory()
            for row in rows:
                if not eligible(row, self.protocol) or (
                    self.paired_gpu is not None and row["uuid"] != self.paired_gpu["uuid"]
                ):
                    continue
                lock_path = self.root / "locks" / ("gpu-" + row["uuid"] + ".lock")
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                lock = lock_path.open("a")
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    lock.close()
                    continue
                fresh = next(
                    (current for current in inventory() if current["index"] == row["index"]), None
                )
                if (
                    fresh is None
                    or fresh["uuid"] != row["uuid"]
                    or not eligible(fresh, self.protocol)
                ):
                    lock.close()
                    continue
                self.wait_used += time.monotonic() - started
                self.paired_gpu = fresh
                return fresh, lock
            self.update("WAITING_FOR_IDLE_GPU", waiting_stage=stage, gpu_observation=rows)
            time.sleep(min(POLL_SECONDS, max(0, WAIT_BUDGET_SECONDS - self.wait_used)))
            self.wait_used += time.monotonic() - started
        raise RuntimeError("controller stop requested before launch")

    def run_stage(self, stage):
        require(self.active is None, "one worker including CPU initialization at a time")
        require(
            stage in STAGES and not (self.root / stage / "launch/record.json").exists(),
            "stage was already dispatched; automatic retry forbidden",
        )
        self.verify_original_B_paused()
        if stage == "cohort_resume":
            first = checked(self.root / "cohort_first/result/record.json")
            check_result(self.protocol, "cohort_first", first)
            verify_durable_prefix(self.protocol, first)
        row, lock = self.acquire_gpu(stage)
        process = None
        launch = None
        try:
            self.verify_original_B_paused()
            worker = str(self.root / "implementation/finqa_v32_performance_worker.py")
            command = worker_command(self.root, stage, row, self.protocol)
            directory = self.root / stage
            directory.mkdir(parents=True, exist_ok=True)
            env = worker_environment(row)
            with (directory / "worker.log").open("xb") as output:
                process = subprocess.Popen(
                    command,
                    cwd=REPO,
                    env=env,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            born = birth(process.pid)
            require(born is not None, "worker exited before its ownership could be established")
            launch = dict(
                schema="v32_bounded_stage_launch.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                stage=stage,
                pid=process.pid,
                birth=born,
                worker=worker,
                command=command,
                gpu_index=row["index"],
                gpu_uuid=row["uuid"],
                gpu_observed=row,
                timeout_seconds=STAGE_TIMEOUTS[stage],
                term_grace_seconds=TERM_GRACE_SECONDS,
            )
            # Keep ownership in memory even if durable publication itself fails.
            # Cleanup can then stop this child without dropping its GPU lock early.
            launch = publish(directory / "launch/record.json", launch)
            self.active = {
                key: launch[key] for key in ("stage", "pid", "birth", "gpu_index", "gpu_uuid")
            }
            self.update("RUNNING", stage=stage)
            deadline = time.monotonic() + STAGE_TIMEOUTS[stage]
            termination_at, timed_out = None, False
            while process.poll() is None:
                current = time.monotonic()
                if termination_at is None and (self.stop or current >= deadline):
                    timed_out = current >= deadline
                    signal_owned(launch, signal.SIGTERM)
                    termination_at = current
                    self.update("SAFE_BOUNDARY_STOP_REQUESTED", stage=stage, timed_out=timed_out)
                if termination_at is not None and current - termination_at >= TERM_GRACE_SECONDS:
                    signal_owned(launch, signal.SIGKILL)
                    process.wait(timeout=30)
                    break
                time.sleep(POLL_SECONDS)
            code = process.wait()
            publish(
                directory / "exit/record.json",
                dict(
                    schema="v32_bounded_stage_exit.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    stage=stage,
                    returncode=code,
                    timed_out=timed_out,
                    stop_requested=termination_at is not None,
                    no_retry=True,
                ),
            )
            require(
                termination_at is None and code == 0,
                "stage failed/stopped/timed out; no retry, fallback or further dispatch",
            )
            result = checked(directory / "result/record.json")
            check_result(self.protocol, stage, result)
            if stage == "cohort_first":
                verify_durable_prefix(self.protocol, result)
            elif stage == "cohort_resume":
                first = checked(self.root / "cohort_first/result/record.json")
                check_result(self.protocol, "cohort_first", first)
                verify_durable_prefix(self.protocol, first)
                require(
                    first["selected_variant"] == result["selected_variant"],
                    "cold resume changed selected backend",
                )
            return result
        except BaseException:
            # A controller error also stops its own child; never a foreign PID.
            if process is not None and launch is not None and process.poll() is None:
                signal_owned(launch, signal.SIGTERM)
                try:
                    process.wait(timeout=TERM_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    signal_owned(launch, signal.SIGKILL)
                    process.wait(timeout=30)
            raise
        finally:
            self.active = None
            lock.close()

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run only the frozen committed controller",
        )
        lock_path = self.root / "queue/controller.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            publish(
                self.root / "queue/run_intent/record.json",
                dict(
                    schema="v32_bounded_controller_intent.v1",
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
                results = {stage: self.run_stage(stage) for stage in MICRO_STAGES}
                selection = choose_variant(self.protocol, results)
                publish(
                    self.root / "selection/record.json",
                    dict(
                        schema="v32_preregistered_backend_selection.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        **selection,
                    ),
                )
                if selection["selected_variant"] is None:
                    self.update(
                        "STOPPED_NO_MATERIAL_SPEEDUP",
                        numeric_pass=True,
                        full_cohort_validation_complete=False,
                    )
                    return False
                self.run_stage("cohort_first")
                final = self.run_stage("cohort_resume")
                publish(
                    self.root / "result/record.json",
                    dict(
                        schema="v32_completed_bounded_performance_validation.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        status="COMPLETE",
                        numeric_pass=True,
                        selected_variant=selection["selected_variant"],
                        full_cohort_result=entry(self.root / "cohort_resume/result/record.json"),
                        full_cohort_validation_complete=final["full_cohort_validation_complete"],
                        original_B_resume_authorized=False,
                        API_calls=0,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        optimizer_steps=0,
                    ),
                )
                self.update("COMPLETE", selected_variant=selection["selected_variant"])
                return True
            except BaseException as error:
                self.update(
                    "STOPPED_FAILURE_NO_RETRY", error_type=type(error).__name__, error=str(error)
                )
                publish(
                    self.root / "failure/record.json",
                    dict(
                        schema="v32_bounded_performance_failure.v1",
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
        require(args.source_commit is not None, "committed source is required")
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
