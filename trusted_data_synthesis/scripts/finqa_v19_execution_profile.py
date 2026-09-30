"""Queued-only execution profile; original scientific artifacts remain immutable."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from trusted_synthesis.finance_research.calibration import identity, now
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.storage import runtime_binding
from trusted_synthesis.finance_research.v6_collection import bound, persist, require, sha
from trusted_synthesis.finance_research.v10_workflow import WORKTREE
from trusted_synthesis.finance_research.v13_material_registration import checked, entry, read_ref
from trusted_synthesis.finance_research.v18_registration import OUTPUT

ROOT = OUTPUT / "queued_optimization_01"
GPUS = [1, 2, 3, 6]
OPTIMIZED_KEYS = ["arm-29-full", "arm-47-full"]
FILES = (
    "finqa_v19_optimized_replay.py",
    "finqa_v19_replay_state.py",
    "finqa_v19_execution_profile.py",
    "finqa_v19_profiled_worker.py",
    "finqa_v19_validate_replay.py",
    "finqa_v19_queued_scheduler.py",
    "finqa_v18_four_gpu_queue_recovery.py",
)
BASE_SCRIPTS = (
    "fixed_kernel_anchored_segmented_replay_20260916.py",
    "fixed_kernel_anchored_sources_gpu_gate_20260916.py",
    "fixed_kernel_anchored_canonical_saves_20260916.py",
    "fixed_kernel_anchored_saved_tensors_20260916.py",
)


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def read_file(ref):
    require(sha(ref["path"]) == ref["sha256"], "immutable execution source bytes changed")
    return json.loads(Path(ref["path"]).read_bytes())


def script_sources():
    return {name: sha(Path(__file__).parent / name) for name in FILES}


def process_state(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return None


def guard_dispatcher(profile):
    paused = read_ref(profile["paused_dispatcher"])
    require(
        identity(paused["target_pid"]) != paused["target_birth"]
        or process_state(paused["target_pid"]) in ("T", "t"),
        "the superseded dispatcher must stay paused or exited",
    )


def validation_cases(feedback_root):
    root = Path(feedback_root)
    rewards = read_file(file_ref(root / "native_rewards/record.json"))["rewards"]
    require(
        len(rewards) == 700 and all(type(v) in (int, float) and v in (0, 1) for v in rewards),
        "the validation source must already have complete fixed700 native scores",
    )
    rows = []
    offset = 0
    for draw in (0, 1):
        seal = json.loads((root / f"draw{draw}/generation_seal/seal.json").read_bytes())
        require(
            seal["complete"] and len(seal["episodes"]) == 350,
            "two actual complete350 seals required",
        )
        for reference in seal["episodes"]:
            reward = rewards[offset]
            offset += 1
            if reward == 0:
                continue
            path = root / f"draw{draw}" / reference["path"]
            require(sha(path) == reference["sha256"], "registered performance case episode changed")
            episode = json.loads(path.read_bytes())
            episode_reference = dict(path=str(path.resolve()), sha256=reference["sha256"])
            for index, turn in enumerate(episode["turns"]):
                receipt = turn["receipt"]
                rows.append(
                    dict(
                        episode=episode_reference,
                        turn_index=index,
                        receipt_sha256=digest(receipt),
                        call_id=receipt["call_id"],
                        prompt_tokens=len(receipt["prompt_input_ids"]),
                        output_tokens=len(receipt["raw_generated_token_ids"]),
                    )
                )
    require(offset == 700 and len(rows) >= 4, "complete fixed700 and existing responses required")
    by_length = sorted(rows, key=lambda x: (x["prompt_tokens"] + x["output_tokens"], x["call_id"]))
    chosen = [
        max(rows, key=lambda x: (x["prompt_tokens"], x["call_id"])),
        max(rows, key=lambda x: (x["output_tokens"], x["call_id"])),
        by_length[len(by_length) // 2],
        by_length[0],
    ]
    unique = {row["call_id"]: row for row in chosen}
    for row in by_length:
        if len(unique) >= 4:
            break
        unique.setdefault(row["call_id"], row)
    return list(unique.values())


def register(root=ROOT):
    root = Path(root).resolve()
    require(not (root / "registration/record.json").exists(), "preserve execution registration")
    old = OUTPUT / "queue_recovery_01"
    previous = checked(old / "registration/record.json")
    pause = entry(root / "dispatcher_pause_receipt/record.json")
    launcher = Path(read_ref(previous["training_handoff"])["launcher"])
    plan = checked(launcher / "registration/record.json")
    require(
        WORKTREE.resolve() == Path(previous["original_worktree"]).resolve()
        and plan["runtime_binding"] == runtime_binding(),
        "import the original frozen scientific runtime",
    )
    require(
        all(
            sha(Path(__file__).parent / name)
            == sha(WORKTREE / "trusted_data_synthesis/scripts" / name)
            for name in BASE_SCRIPTS
        ),
        "baseline helper files must equal the running frozen version",
    )
    for job in previous["queued_jobs"]:
        require(
            not Path(job["result"]).parents[1].exists(),
            "only the eleven still-unstarted arms may change",
        )
    feedback = (
        launcher
        / "seed11/arms/c_only/feedback"
        / "34f937b1cebb0a478009a90dc689fd287be2b8e685545ebd8dda6adf86e26f08"
    )
    intent = json.loads((feedback / "intent/record.json").read_bytes())
    taskset = shutil.which("taskset")
    require(
        taskset is not None, "existing taskset executable required for queued-only CPU locality"
    )
    cpu_affinity = {
        str(g): Path(f"/sys/devices/system/node/node{0 if g in (1, 2, 3) else 1}/cpulist")
        .read_text()
        .strip()
        for g in GPUS
    }
    body = dict(
        schema="v19_queued_only_execution_profile.v1",
        at=now(),
        user_request=(
            "针对正在排队的任务做优化，正在运行的实验不受干预，"
            "同时注意保存断点及恢复相关的设置，优化完毕之后继续在这四张卡上排队"
        ),
        original_queue=entry(old / "registration/record.json"),
        paused_dispatcher=pause,
        original_worktree=previous["original_worktree"],
        original_runtime_binding=plan["runtime_binding"],
        original_launcher=entry(launcher / "registration/record.json"),
        original_handoff=previous["training_handoff"],
        material_binding=previous["material_binding"],
        source_bindings=script_sources(),
        retained_script_bindings={name: sha(Path(__file__).parent / name) for name in BASE_SCRIPTS},
        protected_workers=previous["adopted_workers"],
        queued_jobs=previous["queued_jobs"],
        optimized_job_keys=OPTIMIZED_KEYS,
        allowed_gpu_indices=GPUS,
        max_gpu_workers=4,
        minimum_free_mib=24576,
        cpu_affinity=cpu_affinity,
        taskset=file_ref(taskset),
        cpu_locality_source="observed nvidia-smi topology and sysfs node CPU lists",
        block_size=8,
        resident_saved_KV_budget_bytes=2 * 1024**3,
        checkpoint_every_responses=16,
        unchanged_numeric_bytecode=True,
        unchanged_response_accumulation_order=True,
        frozen_owner_validation="per_saved_operand_and_complete_response_boundaries",
        model_Adam_RNG_pi_payload_unchanged=True,
        execution_provenance_in_atomic_record_not_state=True,
        retain_completed_replay_checkpoints=True,
        partial_feedback_resampling=False,
        automatic_numerical_failure_retry=False,
        API_calls=0,
        api_model_policy="deepseek-flash",
        validation=dict(
            source_feedback_intent=file_ref(feedback / "intent/record.json"),
            source_rewards=file_ref(feedback / "native_rewards/record.json"),
            cases=validation_cases(feedback),
            expected_parameter_digest=intent["identity"]["parameter_digest"],
            expected_point_id=intent["point_id"],
            required_completed_outer=str(launcher / "seed11/arms/c_only/training/step0298_outer"),
            completed_outer_must_exist_before_CUDA_validation=True,
            case_selection=(
                "four deterministic length cases from existing positive-reward responses"
            ),
            new_generation_calls=0,
            new_optimizer_steps=0,
            require_bitwise_equal_logp_and_gradient=True,
            maximum_optimized_time_ratio=1.05,
            no_fallback_if_validation_fails=True,
        ),
    )
    value = bound(body)
    guard_dispatcher(value)
    persist(root / "registration", value)
    return value


def checked_profile(root=ROOT):
    root = Path(root).resolve()
    value = checked(root / "registration/record.json")
    require(
        value["schema"] == "v19_queued_only_execution_profile.v1"
        and value["source_bindings"] == script_sources()
        and value["allowed_gpu_indices"] == GPUS
        and value["max_gpu_workers"] == 4
        and value["minimum_free_mib"] == 24576
        and value["block_size"] == 8
        and value["resident_saved_KV_budget_bytes"] == 2 * 1024**3
        and value["checkpoint_every_responses"] == 16
        and value["optimized_job_keys"] == OPTIMIZED_KEYS
        and value["API_calls"] == 0
        and value["api_model_policy"] == "deepseek-flash"
        and value["partial_feedback_resampling"] is False
        and value["automatic_numerical_failure_retry"] is False,
        "execution profile/source or fixed scientific constraints changed",
    )
    require(
        WORKTREE.resolve() == Path(value["original_worktree"]).resolve()
        and runtime_binding() == value["original_runtime_binding"],
        "new execution wrapper must import the original scientific implementation",
    )
    require(
        all(
            sha(Path(__file__).parent / name) == expected
            for name, expected in value["retained_script_bindings"].items()
        ),
        "retained replay implementation changed",
    )
    require(
        sha(value["taskset"]["path"]) == value["taskset"]["sha256"], "CPU locality launcher changed"
    )
    return value


def admitted_validation(root=ROOT, profile=None):
    root = Path(root).resolve()
    profile = profile or checked_profile(root)
    result = checked(root / "validation/result/record.json")
    require(
        result["execution_profile_id"] == profile["id"]
        and result["admitted"] is True
        and result["all_cases_bitwise_equal"] is True
        and result["production_CUDA_measured"] is True
        and result["saved_KV_residency_exercised"] is True
        and result["actual_point_model_RNG_buffers_unchanged"] is True
        and result["case_count"] == len(profile["validation"]["cases"])
        and result["new_generation_calls"] == result["optimizer_steps"] == result["API_calls"] == 0
        and 0
        < result["optimized_over_baseline"]
        <= profile["validation"]["maximum_optimized_time_ratio"],
        "actual same-token CUDA equivalence/performance acceptance required",
    )
    for index, expected in enumerate(profile["validation"]["cases"]):
        case = checked(root / "validation/cases" / f"case{index:02d}/record.json")
        require(
            case["execution_profile_id"] == profile["id"]
            and case["case"] == expected
            and case["logp_bitwise_equal"] is True
            and case["gradient_bitwise_equal"] is True
            and case["same_shape_dtype_keys"] is True
            and case["baseline_gradient_digest"] == case["optimized_gradient_digest"],
            "aggregate admission cannot override a contradictory CUDA case",
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register",))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(dict(id=register(args.root)["id"])))
