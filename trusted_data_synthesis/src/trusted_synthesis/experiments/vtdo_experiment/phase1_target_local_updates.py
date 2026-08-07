from __future__ import annotations

import argparse
import gc
import hashlib
import json
import multiprocessing
import statistics
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_ALIGNMENT_VERSION,
    TARGET_OBSERVABILITY_ROLE,
    _adapter_tensor_sha256,
    _append_jsonl,
    _assert_trainable_parameter_precision,
    _configure_numeric_policy,
    _gradient_norm,
    _gradient_parameter_manifest,
    _load_execution_model,
    _load_jsonl,
    _load_records,
    _load_tokenizer,
    _load_verified_gradient,
    _parse_gpu_groups,
    _read_json,
    _record_gradient,
    _replay_numeric_contract,
    _seed_everything,
    _sha256,
    _state_realization_diagnostics,
    _weighted_gradient,
    _write_json,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
    _cold_start_adamw_update,
    _linear_combination,
)
from trusted_synthesis.hashing import canonical_hash

TARGET_LOCAL_UPDATE_VERSION = "finance_target_local_updates.v21"
RESULT_HASH_PREFIX = "finance_target_local_gradient_result:"
WORKER_REPORT_HASH_PREFIX = "finance_target_local_gradient_worker:"
STATE_ARTIFACT_HASH_PREFIX = "finance_target_local_state_gradient:"
JACKKNIFE_HASH_PREFIX = "finance_target_local_state_jackknife:"
MANIFEST_HASH_PREFIX = "finance_target_local_update_manifest:"
EXPECTED_TASK_COUNT = 6
EXPECTED_STATE_COUNT = 20
EXPECTED_REALIZATION_COUNT = 60
EXPECTED_REALIZATIONS_PER_STATE = 3


def _replay_hash(
    value: Mapping[str, Any],
    *,
    field: str,
    prefix: str,
    label: str,
) -> str:
    payload = dict(value)
    observed = payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"{label} identity changed")
    return str(observed)


def _verify_plan(plan: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    frozen = dict(plan)
    if frozen.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("target local updates require a current gradient plan")
    if frozen.get("run_role") != TARGET_OBSERVABILITY_ROLE:
        raise ValueError("target local updates require the target-observability role")
    numeric_contract = _replay_numeric_contract(frozen)
    if (
        numeric_contract.get("run_role") != TARGET_OBSERVABILITY_ROLE
        or numeric_contract.get("authorization_objective_access") != "forbidden"
        or numeric_contract.get("gp_c_execution_allowed") is not False
        or numeric_contract.get("contribution_approximation_authorized") is not False
    ):
        raise ValueError("target local update contract opened a forbidden path")
    if frozen.get("authorization_objective_access") != "forbidden":
        raise ValueError("target local update plan opened Authorization")
    if (
        int(frozen.get("task_count", 0)) != EXPECTED_TASK_COUNT
        or int(frozen.get("state_count", 0)) != EXPECTED_STATE_COUNT
        or int(frozen.get("state_realization_count", 0)) != EXPECTED_REALIZATION_COUNT
        or len(frozen.get("jobs", ())) != EXPECTED_REALIZATION_COUNT
    ):
        raise ValueError("target local update support differs from the sealed contract")
    target_path = Path(str(frozen["target_records_path"]))
    if not target_path.is_file() or _sha256(target_path) != frozen.get("target_records_sha256"):
        raise ValueError("target local update records changed after planning")
    job_ids = tuple(str(row["job_id"]) for row in frozen["jobs"])
    record_ids = tuple(str(row["record_id"]) for row in frozen["jobs"])
    if len(set(job_ids)) != len(job_ids) or len(set(record_ids)) != len(record_ids):
        raise ValueError("target local update job identities are not unique")
    return frozen, numeric_contract


def _result_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("result_hash", None)
    return canonical_hash(payload, prefix=RESULT_HASH_PREFIX)


def _worker(
    plan_path: str,
    output_path: str,
    *,
    gpu_ids: tuple[int, ...],
    partition_index: int,
    partition_count: int,
) -> dict[str, Any]:
    import torch
    from safetensors.torch import save_file

    plan, numeric_contract = _verify_plan(_read_json(Path(plan_path)))
    output_dir = Path(output_path)
    worker_dir = output_dir / "workers"
    gradient_dir = output_dir / "realization_gradients"
    worker_dir.mkdir(parents=True, exist_ok=True)
    gradient_dir.mkdir(parents=True, exist_ok=True)
    worker_path = worker_dir / f"partition_{partition_index}.jsonl"
    completed: set[str] = set()
    for resume_row in _load_jsonl(worker_path):
        gradient_path = Path(str(resume_row.get("gradient_file", "")))
        if (
            resume_row.get("result_hash") != _result_hash(resume_row)
            or resume_row.get("status") != "passed"
            or resume_row.get("plan_hash") != plan["plan_hash"]
            or not gradient_path.is_file()
            or _sha256(gradient_path) != resume_row.get("gradient_sha256")
        ):
            raise ValueError("target local update resume artifact failed replay")
        completed.add(str(resume_row["job_id"]))
    jobs = [
        row for index, row in enumerate(plan["jobs"]) if index % partition_count == partition_index
    ]
    required_gpu_count = int(numeric_contract["selected_profile"]["required_gpu_count"])
    if len(gpu_ids) != required_gpu_count:
        raise ValueError("target local update worker requires one frozen GPU group")
    if any(gpu_id < 0 or gpu_id >= torch.cuda.device_count() for gpu_id in gpu_ids):
        raise ValueError("target local update GPU group is unavailable")
    torch.cuda.set_device(gpu_ids[0])
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    _seed_everything(20260850 + partition_index)
    _configure_numeric_policy(numeric_contract["selected_profile"])
    tokenizer = _load_tokenizer(Path(str(plan["model_dir"])))
    model, resolved_device_map = _load_execution_model(
        Path(str(plan["model_dir"])),
        Path(str(plan["beneficiary_adapter_dir"])),
        gpu_ids=gpu_ids,
        profile=numeric_contract["selected_profile"],
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("target local update worker loaded another beneficiary Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    _assert_trainable_parameter_precision(parameter_manifest)
    records = _load_records(Path(str(plan["target_records_path"])))
    started = time.monotonic()
    completed_now = 0
    for job in jobs:
        if str(job["job_id"]) in completed:
            continue
        _seed_everything(int(job["gradient_seed"]))
        _configure_numeric_policy(numeric_contract["selected_profile"])
        gradient, loss, supervised_tokens = _record_gradient(
            model,
            tokenizer,
            records[str(job["record_id"])],
            mode="train",
        )
        key = hashlib.sha256(str(job["job_id"]).encode("utf-8")).hexdigest()[:24]
        gradient_path = gradient_dir / f"realization_{key}.safetensors"
        save_file(gradient, gradient_path)
        result_row: dict[str, Any] = {
            **job,
            "schema_version": TARGET_LOCAL_UPDATE_VERSION,
            "plan_hash": plan["plan_hash"],
            "numeric_contract_hash": plan["numeric_contract_hash"],
            "authorization_objective_access": "forbidden",
            "objective_record_access": "none",
            "gp_c_evaluated": False,
            "partition_index": partition_index,
            "partition_count": partition_count,
            "gpu_ids": gpu_ids,
            "parameter_manifest_hash": parameter_manifest_hash,
            "loss": loss,
            "supervised_tokens": supervised_tokens,
            "gradient_file": str(gradient_path),
            "gradient_sha256": _sha256(gradient_path),
            "gradient_norm": _gradient_norm(gradient),
            "status": "passed",
        }
        result_row["result_hash"] = _result_hash(result_row)
        _append_jsonl(worker_path, result_row)
        completed_now += 1
        del gradient
    peak_memory = {str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids}
    report: dict[str, Any] = {
        "schema_version": TARGET_LOCAL_UPDATE_VERSION,
        "plan_hash": plan["plan_hash"],
        "numeric_contract_hash": plan["numeric_contract_hash"],
        "partition_index": partition_index,
        "partition_count": partition_count,
        "assigned_count": len(jobs),
        "completed_before_resume": len(completed),
        "completed_now": completed_now,
        "parameter_manifest": parameter_manifest,
        "parameter_manifest_hash": parameter_manifest_hash,
        "requested_cuda_device_ids": gpu_ids,
        "resolved_hf_device_map": resolved_device_map,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": max(peak_memory.values()),
        "peak_gpu_memory_bytes_by_requested_device": peak_memory,
        "authorization_objective_access": "forbidden",
        "objective_record_access": "none",
        "gp_c_evaluated": False,
    }
    report["report_hash"] = canonical_hash(report, prefix=WORKER_REPORT_HASH_PREFIX)
    _write_json(worker_dir / f"partition_{partition_index}_report.json", report)
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return report


def run(args: argparse.Namespace) -> None:
    plan_path = str(Path(args.gradient_plan).resolve())
    output_dir = Path(args.output_dir).resolve()
    plan, _ = _verify_plan(_read_json(Path(plan_path)))
    gpu_groups = _parse_gpu_groups(args.gpu_groups)
    partition_count = min(len(gpu_groups), len(plan["jobs"]))
    context = multiprocessing.get_context("spawn")
    reports = []
    with ProcessPoolExecutor(max_workers=partition_count, mp_context=context) as executor:
        futures = {
            executor.submit(
                _worker,
                plan_path,
                str(output_dir),
                gpu_ids=gpu_ids,
                partition_index=index,
                partition_count=partition_count,
            ): index
            for index, gpu_ids in enumerate(gpu_groups[:partition_count])
        }
        for future in as_completed(futures):
            reports.append(future.result())
    summary: dict[str, Any] = {
        "schema_version": TARGET_LOCAL_UPDATE_VERSION,
        "plan_hash": plan["plan_hash"],
        "partition_count": partition_count,
        "gpu_groups": gpu_groups,
        "worker_report_hashes": tuple(
            row["report_hash"]
            for row in sorted(reports, key=lambda value: value["partition_index"])
        ),
        "authorization_objective_access": "forbidden",
        "objective_record_access": "none",
        "gp_c_evaluated": False,
    }
    summary["summary_hash"] = canonical_hash(
        summary,
        prefix="finance_target_local_update_worker_summary:",
    )
    _write_json(output_dir / "worker_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def _freeze_updates(
    *,
    plan: Mapping[str, Any],
    state_rows: Sequence[Mapping[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    from safetensors.torch import save_file

    optimizer = plan["local_optimizer_contract"]
    state_dir = output_dir / "state_updates"
    jackknife_dir = output_dir / "state_jackknife_updates"
    state_dir.mkdir(parents=True, exist_ok=True)
    jackknife_dir.mkdir(parents=True, exist_ok=True)
    state_updates: dict[tuple[str, str], dict[str, Any]] = {}
    state_artifacts = []
    jackknife_artifacts = []
    for index, row in enumerate(state_rows):
        gradient = _load_verified_gradient(
            Path(str(row["state_gradient_file"])),
            str(row["state_gradient_sha256"]),
        )
        update = _cold_start_adamw_update(
            gradient,
            learning_rate=float(optimizer["learning_rate"]),
            epsilon=float(optimizer["epsilon"]),
            maximum_gradient_norm=float(optimizer["maximum_gradient_norm"]),
        )
        path = state_dir / f"state_{index:04d}.safetensors"
        save_file(update, path)
        task_id = str(row["task_id"])
        state_id = str(row["state_id"])
        state_updates[(task_id, state_id)] = update
        state_artifacts.append(
            {
                "task_id": task_id,
                "task_type": row["task_type"],
                "state_id": state_id,
                "source_state_artifact_id": row["state_artifact_id"],
                "file": str(path),
                "sha256": _sha256(path),
                "update_norm": _gradient_norm(update),
            }
        )
        sources = tuple(row["realization_gradient_artifacts"])
        gradients = [
            _load_verified_gradient(Path(str(value["file"])), str(value["sha256"]))
            for value in sources
        ]
        for excluded_index, excluded in enumerate(sources):
            retained = [
                gradient
                for position, gradient in enumerate(gradients)
                if position != excluded_index
            ]
            jackknife_gradient = _weighted_gradient(retained, [1.0] * len(retained))
            jackknife_update = _cold_start_adamw_update(
                jackknife_gradient,
                learning_rate=float(optimizer["learning_rate"]),
                epsilon=float(optimizer["epsilon"]),
                maximum_gradient_norm=float(optimizer["maximum_gradient_norm"]),
            )
            jackknife_path = (
                jackknife_dir / f"state_{index:04d}_leave_{excluded_index:02d}.safetensors"
            )
            save_file(jackknife_update, jackknife_path)
            jackknife_artifacts.append(
                {
                    "task_id": task_id,
                    "state_id": state_id,
                    "jackknife_id": canonical_hash(
                        {
                            "task_id": task_id,
                            "state_id": state_id,
                            "excluded_realization_id": excluded["realization_id"],
                            "retained_realization_ids": tuple(
                                str(value["realization_id"])
                                for position, value in enumerate(sources)
                                if position != excluded_index
                            ),
                        },
                        prefix=JACKKNIFE_HASH_PREFIX,
                    ),
                    "excluded_realization_id": str(excluded["realization_id"]),
                    "file": str(jackknife_path),
                    "sha256": _sha256(jackknife_path),
                    "update_norm": _gradient_norm(jackknife_update),
                }
            )
    task_marginal = 1.0 / EXPECTED_TASK_COUNT
    task_marginals = {str(task_id): task_marginal for task_id in sorted(plan["task_distributions"])}
    task_updates = []
    task_vectors = []
    for task_id, distribution in sorted(plan["task_distributions"].items()):
        probabilities = {
            str(key): float(value) for key, value in distribution["probabilities"].items()
        }
        states = tuple(sorted(probabilities))
        if {(task_id, state_id) for state_id in states} - set(state_updates):
            raise ValueError("target local update manifest lacks a frozen state")
        task_update = _linear_combination(
            [state_updates[(task_id, state_id)] for state_id in states],
            [probabilities[state_id] for state_id in states],
        )
        task_vectors.append(task_update)
        task_updates.append(
            {
                "task_id": task_id,
                "current_probabilities": probabilities,
                "update_norm": _gradient_norm(task_update),
            }
        )
    global_update = _linear_combination(
        task_vectors,
        [task_marginal] * len(task_vectors),
    )
    global_path = output_dir / "global_local_adamw_update.safetensors"
    save_file(global_update, global_path)
    manifest: dict[str, Any] = {
        "schema_version": TARGET_LOCAL_UPDATE_VERSION,
        "artifact_type": "ObjectiveBlindLocalAdamWUpdateManifest",
        "source_gradient_plan_hash": plan["plan_hash"],
        "run_role": TARGET_OBSERVABILITY_ROLE,
        "numeric_contract_hash": plan["numeric_contract_hash"],
        "numeric_profile": plan["numeric_contract"]["selected_profile"],
        "beneficiary_model_state_id": plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": plan["beneficiary_checkpoint_hash"],
        "state_realization_manifest_hash": plan["state_realization_manifest_hash"],
        "optimizer_contract": optimizer,
        "local_update_estimand": ("expectation_of_state_homogeneous_cold_start_adamw_updates"),
        "state_artifacts": tuple(state_artifacts),
        "state_jackknife_artifacts": tuple(jackknife_artifacts),
        "state_uncertainty_method": "leave_one_realization_out_jackknife_pseudovalues",
        "task_updates": tuple(task_updates),
        "task_marginals": task_marginals,
        "global_update_artifact": {
            "file": str(global_path),
            "sha256": _sha256(global_path),
            "update_norm": _gradient_norm(global_update),
        },
        "authorization_objective_access": "forbidden",
        "objective_record_access": "none",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "claim_boundary": (
            "These vectors materialize the frozen one-step training intervention only. "
            "No Objective gradient, GP-C score, Authorization record, or VTDO update was read."
        ),
    }
    manifest["manifest_hash"] = canonical_hash(manifest, prefix=MANIFEST_HASH_PREFIX)
    return manifest


def aggregate(args: argparse.Namespace) -> None:
    from safetensors.torch import save_file

    plan, _ = _verify_plan(_read_json(Path(args.gradient_plan).resolve()))
    output_dir = Path(args.output_dir).resolve()
    worker_summary = _read_json(output_dir / "worker_summary.json")
    if (
        worker_summary.get("plan_hash") != plan["plan_hash"]
        or worker_summary.get("objective_record_access") != "none"
        or worker_summary.get("gp_c_evaluated") is not False
    ):
        raise ValueError("target local update worker summary opened a forbidden path")
    partition_count = int(worker_summary["partition_count"])
    reports = [
        _read_json(output_dir / "workers" / f"partition_{index}_report.json")
        for index in range(partition_count)
    ]
    for index, report in enumerate(reports):
        _replay_hash(
            report,
            field="report_hash",
            prefix=WORKER_REPORT_HASH_PREFIX,
            label="target local update worker report",
        )
        if (
            report.get("partition_index") != index
            or report.get("partition_count") != partition_count
            or report.get("plan_hash") != plan["plan_hash"]
            or report.get("objective_record_access") != "none"
        ):
            raise ValueError("target local update worker report differs")
    if len({str(report["parameter_manifest_hash"]) for report in reports}) != 1:
        raise ValueError("target local update workers used different parameter spaces")
    rows = [
        row
        for index in range(partition_count)
        for row in _load_jsonl(output_dir / "workers" / f"partition_{index}.jsonl")
    ]
    expected_jobs = {str(row["job_id"]): row for row in plan["jobs"]}
    observed_jobs: dict[str, dict[str, Any]] = {}
    for row in rows:
        job_id = str(row["job_id"])
        gradient_path = Path(str(row["gradient_file"]))
        if (
            row.get("result_hash") != _result_hash(row)
            or row.get("status") != "passed"
            or row.get("plan_hash") != plan["plan_hash"]
            or row.get("objective_record_access") != "none"
            or row.get("gp_c_evaluated") is not False
            or not gradient_path.is_file()
            or _sha256(gradient_path) != row.get("gradient_sha256")
            or job_id in observed_jobs
        ):
            raise ValueError("target local gradient result failed replay")
        observed_jobs[job_id] = row
    if set(observed_jobs) != set(expected_jobs):
        raise ValueError("target local gradient matrix is incomplete")
    by_state: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observed_jobs.values():
        by_state[(str(row["task_id"]), str(row["state_id"]))].append(row)
    expected_counts = {
        (str(task_id), str(state_id)): int(count)
        for task_id, state_id, count in plan["state_realization_manifest"]["realization_counts"]
    }
    if (
        set(by_state) != set(expected_counts)
        or len(by_state) != EXPECTED_STATE_COUNT
        or any(
            len(values) != EXPECTED_REALIZATIONS_PER_STATE or len(values) != expected_counts[key]
            for key, values in by_state.items()
        )
    ):
        raise ValueError("target local gradients do not exactly cover state realizations")
    optimizer = plan["local_optimizer_contract"]
    mean_dir = output_dir / "state_mean_gradients"
    mean_dir.mkdir(parents=True, exist_ok=True)
    state_rows = []
    for (task_id, state_id), values in sorted(by_state.items()):
        values.sort(key=lambda row: str(row["realization_id"]))
        gradients = [
            _load_verified_gradient(
                Path(str(row["gradient_file"])),
                str(row["gradient_sha256"]),
            )
            for row in values
        ]
        mean_gradient = _weighted_gradient(gradients, [1.0] * len(gradients))
        key = hashlib.sha256(f"{task_id}|{state_id}".encode()).hexdigest()[:24]
        mean_path = mean_dir / f"state_{key}.safetensors"
        save_file(mean_gradient, mean_path)
        mean_sha256 = _sha256(mean_path)
        state_artifact_id = canonical_hash(
            {
                "task_id": task_id,
                "state_id": state_id,
                "realization_ids": tuple(str(row["realization_id"]) for row in values),
                "mean_gradient_sha256": mean_sha256,
            },
            prefix=STATE_ARTIFACT_HASH_PREFIX,
        )
        diagnostics = _state_realization_diagnostics(
            gradients,
            mean_gradient,
            learning_rate=float(optimizer["learning_rate"]),
            optimizer_epsilon=float(optimizer["epsilon"]),
            maximum_gradient_norm=float(optimizer["maximum_gradient_norm"]),
        )
        state_rows.append(
            {
                "task_id": task_id,
                "task_type": values[0]["task_type"],
                "state_id": state_id,
                "strategy": values[0]["strategy"],
                "state_artifact_id": state_artifact_id,
                "realization_ids": tuple(str(row["realization_id"]) for row in values),
                "realization_gradient_artifacts": tuple(
                    {
                        "realization_id": str(row["realization_id"]),
                        "file": str(row["gradient_file"]),
                        "sha256": str(row["gradient_sha256"]),
                        "loss": float(row["loss"]),
                        "supervised_tokens": int(row["supervised_tokens"]),
                    }
                    for row in values
                ),
                "state_loss_mean": statistics.fmean(float(row["loss"]) for row in values),
                "state_supervised_tokens_mean": statistics.fmean(
                    float(row["supervised_tokens"]) for row in values
                ),
                "state_gradient_file": str(mean_path),
                "state_gradient_sha256": mean_sha256,
                "state_gradient_norm": _gradient_norm(mean_gradient),
                **diagnostics,
            }
        )
    update_manifest = _freeze_updates(
        plan=plan,
        state_rows=state_rows,
        output_dir=output_dir,
    )
    _write_json(output_dir / "local_update_manifest.json", update_manifest)
    aggregate_report: dict[str, Any] = {
        "schema_version": TARGET_LOCAL_UPDATE_VERSION,
        "artifact_type": "ObjectiveBlindLocalUpdateReport",
        "plan_hash": plan["plan_hash"],
        "numeric_contract_hash": plan["numeric_contract_hash"],
        "task_count": EXPECTED_TASK_COUNT,
        "state_count": len(state_rows),
        "realization_count": len(rows),
        "parameter_manifest_hash": reports[0]["parameter_manifest_hash"],
        "state_rows": tuple(state_rows),
        "local_update_manifest_hash": update_manifest["manifest_hash"],
        "authorization_objective_access": "forbidden",
        "objective_record_access": "none",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "status": "passed",
    }
    aggregate_report["report_hash"] = canonical_hash(
        aggregate_report,
        prefix="finance_target_local_update_report:",
    )
    _write_json(output_dir / "report.json", aggregate_report)
    print(
        json.dumps(
            {
                "status": aggregate_report["status"],
                "report_hash": aggregate_report["report_hash"],
                "local_update_manifest_hash": update_manifest["manifest_hash"],
                "task_count": aggregate_report["task_count"],
                "state_count": aggregate_report["state_count"],
                "realization_count": aggregate_report["realization_count"],
                "objective_record_access": aggregate_report["objective_record_access"],
                "gp_c_evaluated": aggregate_report["gp_c_evaluated"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize v21 local training directions without Objective gradients"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--gradient-plan", required=True)
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--gpu-groups", nargs="+", required=True)
    run_parser.set_defaults(handler=run)
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--gradient-plan", required=True)
    aggregate_parser.add_argument("--output-dir", required=True)
    aggregate_parser.set_defaults(handler=aggregate)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
