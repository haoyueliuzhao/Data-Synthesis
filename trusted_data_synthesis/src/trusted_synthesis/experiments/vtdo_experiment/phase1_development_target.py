from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import random
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    CALIBRATED_NUMERIC_PROFILE,
    _assert_trainable_parameter_precision,
    _configure_numeric_policy,
    _gradient_norm,
    _gradient_parameter_manifest,
    _load_conditional_distributions,
    _load_execution_model,
    _load_state_realizations,
    _load_verified_gradient,
    _record_gradient,
    _seed_everything,
    _weighted_gradient,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_development_design_analysis import (
    classify_effect_interval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
    _apply_descent_vector,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _load_records,
    _load_tokenizer,
)
from trusted_synthesis.hashing import canonical_hash

TARGET_CONTRACT_VERSION = "finance_development_exact_target_contract.v22"
TARGET_CONTRACT_PREFIX = "finance_development_exact_target_contract:"
STATE_WORKER_VERSION = "finance_development_state_gradient_worker.v22"
STATE_WORKER_PREFIX = "finance_development_state_gradient_worker:"
STATE_AGGREGATE_VERSION = "finance_development_state_gradient_aggregate.v22"
STATE_AGGREGATE_PREFIX = "finance_development_state_gradient_aggregate:"
OBJECTIVE_WORKER_VERSION = "finance_development_objective_gradient_worker.v22"
OBJECTIVE_WORKER_PREFIX = "finance_development_objective_gradient_worker:"
TARGET_REPORT_VERSION = "finance_development_exact_target_report.v22.1"
TARGET_REPORT_PREFIX = "finance_development_exact_target_report:"
PRIMARY_COORDINATE_SALT = "finance_v22_development_primary_coordinate_20260808"
STATE_PARTITION_COUNT = 2
OBJECTIVE_PARTITION_COUNT = 2
POWER_REPLICATES = 10_000
POWER_TASK_GRID = (30, 45, 50, 60, 80, 100)
TARGET_POWER = 0.80


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _artifact_ref(path: Path, **identity: Any) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"target input is missing:{resolved}")
    return {"path": str(resolved), "sha256": _sha256(resolved), **identity}


def _replay_hash(value: Mapping[str, Any], *, field: str, prefix: str) -> str:
    payload = dict(value)
    observed = payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"target identity changed:{field}")
    return str(observed)


def _verify_ref(value: Mapping[str, Any], *, label: str) -> Path:
    path = Path(str(value.get("path", ""))).resolve()
    if not path.is_file() or _sha256(path) != value.get("sha256"):
        raise ValueError(f"target input changed:{label}")
    return path


def _git_identity(repo_root: Path) -> dict[str, str]:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status.strip():
        raise ValueError("target contract requires a clean source tree")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"git_commit": commit, "git_tree": tree}


def verify_target_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    contract = dict(value)
    _replay_hash(contract, field="contract_hash", prefix=TARGET_CONTRACT_PREFIX)
    if contract.get("contract_version") != TARGET_CONTRACT_VERSION:
        raise ValueError("target contract version differs")
    if contract.get("run_role") != "development_exact_target_only":
        raise ValueError("target contract role differs")
    if (
        contract.get("validation_objective_access") != "forbidden"
        or contract.get("authorization_objective_access") != "forbidden"
        or contract.get("gp_c_evaluated") is not False
        or contract.get("contribution_approximation_authorized") is not False
    ):
        raise ValueError("target contract crossed its scientific boundary")
    for label, ref in contract["inputs"].items():
        _verify_ref(ref, label=label)
    numeric = contract["numeric_execution"]
    if numeric["numeric_profile"] != CALIBRATED_NUMERIC_PROFILE:
        raise ValueError("target contract changed the calibrated numeric profile")
    if contract["optimizer_contract"] != {
        "optimizer_name": "adamw",
        "step_count": 1,
        "cold_start": True,
        "reuse_main_optimizer_state": False,
        "learning_rate": 0.0002,
        "betas": [0.9, 0.999],
        "epsilon": 1e-8,
        "weight_decay": 0.0,
        "maximum_gradient_norm": 1.0,
    }:
        raise ValueError("target optimizer contract differs")
    if contract["measurement_contract"]["task_marginal_policy"] != "uniform_fixed_mu":
        raise ValueError("target task marginal changed")
    if contract["measurement_contract"]["within_state_policy"] != "equal_realization_mean":
        raise ValueError("target realization expectation changed")
    if len(contract["task_rows"]) != 30 or len(contract["state_rows"]) != 100:
        raise ValueError("target task-state support differs")
    if len(contract["state_gradient_jobs"]) != 500:
        raise ValueError("target realization support differs")
    if len(contract["objective_micro_splits"]) != 8:
        raise ValueError("target Objective micro-split support differs")
    if len(contract["primary_coordinate_by_task"]) != 30:
        raise ValueError("target primary coordinates differ")
    return contract


def prepare_target_contract(
    *,
    repo_root: Path,
    development_contract_path: Path,
    development_report_path: Path,
    task_states_path: Path,
    distributions_path: Path,
    realizations_path: Path,
    realization_report_path: Path,
    objective_support_path: Path,
    objective_records_path: Path,
    source_gradient_plan_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise ValueError("Development target contract is immutable and already exists")
    development_contract = _read_json(development_contract_path)
    development_report = _read_json(development_report_path)
    realization_report = _read_json(realization_report_path)
    objective_support = _read_json(objective_support_path)
    source_plan = _read_json(source_gradient_plan_path)
    if development_report.get("status") != "data_ready_for_development_target_measurement":
        raise ValueError("Development data is not ready for target measurement")
    if development_report.get("nested_variance_measurement_status") != (
        "pending_direct_target_measurements"
    ):
        raise ValueError("Development target stage has already changed")
    if (
        development_contract.get("validation_objective_access") != "forbidden"
        or development_contract.get("authorization_objective_access") != "forbidden"
        or objective_support.get("validation_objective_access") != "forbidden"
        or objective_support.get("authorization_objective_access") != "forbidden"
    ):
        raise ValueError("Development inputs opened a forbidden Objective role")
    if (
        realization_report.get("status") != "passed"
        or realization_report.get("requested_realization_count") != 500
        or realization_report.get("released_realization_count") != 500
        or realization_report.get("artifact_sha256") != _sha256(task_states_path)
        or realization_report.get("distribution_sha256") != _sha256(distributions_path)
        or realization_report.get("realizations_sha256") != _sha256(realizations_path)
        or realization_report.get("realization_uniqueness_policy") != "independent_trajectory_draws"
    ):
        raise ValueError("Development realization report differs")
    if (
        Path(str(objective_support.get("records_path", ""))).resolve()
        != objective_records_path.resolve()
        or objective_support.get("records_sha256") != _sha256(objective_records_path)
        or objective_support.get("record_count") != 64
    ):
        raise ValueError("Development Objective record manifest differs")
    if source_plan.get("local_optimizer_contract") != {
        "optimizer_name": "adamw",
        "estimator_scope": "local_distribution_update_only",
        "step_count": 1,
        "cold_start": True,
        "reuse_main_optimizer_state": False,
        "learning_rate": 0.0002,
        "betas": [0.9, 0.999],
        "epsilon": 1e-8,
        "weight_decay": 0.0,
        "maximum_gradient_norm": 1.0,
        "gradient_accumulation_steps": 1,
        "mixed_state_batches_allowed": False,
        "state_gradient_mode": "train",
        "objective_gradient_mode": "deterministic_eval_with_checkpoint_wrappers",
        "objective_gradient_point": "post_global_update",
    }:
        raise ValueError("source one-step optimizer differs")
    artifacts = load_finance_multi_state_artifacts(task_states_path)
    distributions = _load_conditional_distributions(distributions_path)
    realizations = _load_state_realizations(realizations_path)
    if len(artifacts) != 30 or len(distributions) != 30 or len(realizations) != 500:
        raise ValueError("Development target support count differs")
    artifacts_by_task = {item.omega.task.task_id: item for item in artifacts}
    if set(artifacts_by_task) != set(distributions):
        raise ValueError("Development task distributions differ")
    grouped_realizations: defaultdict[tuple[str, str], list[Any]] = defaultdict(list)
    for realization in realizations:
        grouped_realizations[(realization.task_condition_id, realization.state_id)].append(
            realization
        )
    task_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    primary_coordinate_by_task: dict[str, str] = {}
    for task_id, artifact in sorted(artifacts_by_task.items()):
        state_strategy = {
            item.assignment.state.state_id: item.strategy for item in artifact.accepted_states
        }
        probabilities = distributions[task_id].probabilities
        if set(state_strategy) != set(probabilities):
            raise ValueError("Development state catalog differs from its distribution")
        primary = min(
            state_strategy,
            key=lambda state_id: canonical_hash(
                {
                    "salt": PRIMARY_COORDINATE_SALT,
                    "task_id": task_id,
                    "state_id": state_id,
                },
                prefix="finance_development_primary_coordinate_order:",
            ),
        )
        primary_coordinate_by_task[task_id] = primary
        task_rows.append(
            {
                "task_id": task_id,
                "task_type": artifact.omega.task.public.task_type,
                "artifact_id": artifact.artifact_id,
                "distribution_id": distributions[task_id].distribution_id,
                "task_marginal": 1.0 / len(artifacts),
                "state_count": len(state_strategy),
                "primary_coordinate_state_id": primary,
            }
        )
        for state_id, strategy in sorted(state_strategy.items()):
            state_realizations = grouped_realizations[(task_id, state_id)]
            if len(state_realizations) != 5:
                raise ValueError("Development state lacks five independent realizations")
            state_rows.append(
                {
                    "task_id": task_id,
                    "task_type": artifact.omega.task.public.task_type,
                    "state_id": state_id,
                    "strategy": strategy,
                    "current_probability": float(probabilities[state_id]),
                    "realization_ids": sorted(item.realization_id for item in state_realizations),
                    "is_primary_coordinate": state_id == primary,
                }
            )
    jobs = []
    for realization in sorted(realizations, key=lambda item: item.realization_id):
        gradient_seed = int(
            canonical_hash(
                {
                    "realization_id": realization.realization_id,
                    "target_contract_version": TARGET_CONTRACT_VERSION,
                },
                prefix="finance_development_target_gradient_seed:",
            ).rsplit(":", 1)[-1][:8],
            16,
        )
        jobs.append(
            {
                "job_id": canonical_hash(
                    {
                        "task_id": realization.task_condition_id,
                        "state_id": realization.state_id,
                        "realization_id": realization.realization_id,
                        "record_id": realization.record.record_id,
                    },
                    prefix="finance_development_state_gradient_job:",
                ),
                "task_id": realization.task_condition_id,
                "state_id": realization.state_id,
                "realization_id": realization.realization_id,
                "record_id": realization.record.record_id,
                "gradient_seed": gradient_seed,
            }
        )
    micro_splits = objective_support.get("micro_splits")
    if not isinstance(micro_splits, list) or len(micro_splits) != 8:
        raise ValueError("Development Objective micro-splits differ")
    if any(len(item.get("record_ids", ())) != 8 for item in micro_splits):
        raise ValueError("Development Objective split size differs")
    optimizer = source_plan["local_optimizer_contract"]
    contract: dict[str, Any] = {
        "contract_version": TARGET_CONTRACT_VERSION,
        "run_role": "development_exact_target_only",
        "repository_identity": _git_identity(repo_root),
        "inputs": {
            "development_contract": _artifact_ref(
                development_contract_path,
                contract_hash=development_contract.get("contract_hash"),
            ),
            "development_report": _artifact_ref(
                development_report_path,
                report_hash=development_report.get("report_hash"),
            ),
            "task_states": _artifact_ref(task_states_path),
            "distributions": _artifact_ref(distributions_path),
            "realizations": _artifact_ref(realizations_path),
            "realization_report": _artifact_ref(realization_report_path),
            "objective_support": _artifact_ref(
                objective_support_path,
                manifest_hash=objective_support.get("manifest_hash"),
            ),
            "objective_records": _artifact_ref(objective_records_path),
            "source_gradient_plan": _artifact_ref(
                source_gradient_plan_path,
                plan_hash=source_plan.get("plan_hash"),
            ),
        },
        "numeric_execution": {
            "numeric_profile": source_plan["numeric_contract"]["selected_profile"],
            "profile_algorithm_contract": source_plan["profile_algorithm_contract"],
            "model_dir": source_plan["model_dir"],
            "base_model_manifest_hash": source_plan["base_model_manifest_hash"],
            "beneficiary_adapter_dir": source_plan["beneficiary_adapter_dir"],
            "beneficiary_adapter_tensor_sha256": source_plan["beneficiary_adapter_tensor_sha256"],
            "beneficiary_checkpoint_hash": source_plan["beneficiary_checkpoint_hash"],
            "beneficiary_model_state_id": source_plan["beneficiary_model_state_id"],
        },
        "optimizer_contract": {
            "optimizer_name": optimizer["optimizer_name"],
            "step_count": optimizer["step_count"],
            "cold_start": optimizer["cold_start"],
            "reuse_main_optimizer_state": optimizer["reuse_main_optimizer_state"],
            "learning_rate": optimizer["learning_rate"],
            "betas": optimizer["betas"],
            "epsilon": optimizer["epsilon"],
            "weight_decay": optimizer["weight_decay"],
            "maximum_gradient_norm": optimizer["maximum_gradient_norm"],
        },
        "measurement_contract": {
            "estimand": (
                "exact_chain_derivative_of_post_update_negative_nll_under_frozen_one_step_adamw"
            ),
            "state_gradient_point": "beneficiary_checkpoint_before_global_update",
            "objective_gradient_point": "single_shared_post_global_update_checkpoint",
            "task_marginal_policy": "uniform_fixed_mu",
            "within_state_policy": "equal_realization_mean",
            "objective_record_policy": "equal_record_mean_within_frozen_micro_split",
            "simplex_direction": "delta_z_minus_current_pi_within_task",
            "global_update_policy": "sum_x_mu_x_sum_z_pi_z_mean_r_gradient_xzr",
            "target_sign": "positive_predicts_improvement_in_negative_objective_loss",
            "finite_radius_used": False,
            "hadamard_used": False,
            "gp_c_used_as_target": False,
        },
        "task_rows": task_rows,
        "state_rows": state_rows,
        "primary_coordinate_by_task": primary_coordinate_by_task,
        "primary_coordinate_selection": {
            "salt_hash": canonical_hash(
                PRIMARY_COORDINATE_SALT,
                prefix="finance_development_primary_coordinate_salt:",
            ),
            "policy": "one_outcome_blind_salted_hash_coordinate_per_task",
        },
        "state_gradient_jobs": jobs,
        "state_worker_partition_count": STATE_PARTITION_COUNT,
        "objective_micro_splits": micro_splits,
        "objective_worker_partition_count": OBJECTIVE_PARTITION_COUNT,
        "mpe_rows": development_report["mpe_rows"],
        "mpe_contract": {
            "target_probability_shift": development_report["target_probability_shift"],
            "minimum": development_report["minimum_practical_effect"],
            "median": development_report["median_practical_effect"],
            "maximum": development_report["maximum_practical_effect"],
        },
        "power_contract": {
            "target_power": TARGET_POWER,
            "replicates": POWER_REPLICATES,
            "task_count_grid": list(POWER_TASK_GRID),
            "effect": "one_state_specific_update_derived_mpe",
            "freeze_after": "nested_target_variance_observed",
        },
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "claim_boundary": (
            "This Development-only contract measures an exact one-step surrogate target and "
            "nested target variance. It cannot inspect Validation or Authorization, evaluate "
            "GP-C, authorize Contribution, update VTDO, or support Student claims."
        ),
    }
    contract["contract_hash"] = canonical_hash(contract, prefix=TARGET_CONTRACT_PREFIX)
    verify_target_contract(contract)
    _write_json(output_path, contract)
    return contract


def _worker_checkpoint_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("checkpoint_hash", None)
    return canonical_hash(payload, prefix="finance_development_state_gradient_checkpoint:")


def run_state_gradient_worker(
    *,
    contract_path: Path,
    output_dir: Path,
    partition_index: int,
    partition_count: int,
    gpu_ids: tuple[int, ...],
) -> dict[str, Any]:
    import torch
    from safetensors.torch import save_file

    contract = verify_target_contract(_read_json(contract_path))
    if partition_count != contract["state_worker_partition_count"]:
        raise ValueError("state worker partition count differs")
    if not 0 <= partition_index < partition_count:
        raise ValueError("state worker partition index differs")
    if len(gpu_ids) != 3 or len(set(gpu_ids)) != 3:
        raise ValueError("state worker requires one three-GPU group")
    torch.cuda.set_device(gpu_ids[0])
    numeric = contract["numeric_execution"]
    _configure_numeric_policy(numeric["numeric_profile"])
    realizations = {
        item.record.record_id: item
        for item in _load_state_realizations(
            _verify_ref(contract["inputs"]["realizations"], label="realizations")
        )
    }
    jobs = [
        job
        for index, job in enumerate(contract["state_gradient_jobs"])
        if index % partition_count == partition_index
    ]
    if any(job["record_id"] not in realizations for job in jobs):
        raise ValueError("state worker job record is missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    gradient_dir = output_dir / "state_gradients"
    checkpoint_dir = output_dir / "state_gradient_checkpoints"
    report_dir = output_dir / "state_workers"
    gradient_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    tokenizer = _load_tokenizer(Path(str(numeric["model_dir"])))
    model, device_map = _load_execution_model(
        Path(str(numeric["model_dir"])),
        Path(str(numeric["beneficiary_adapter_dir"])),
        gpu_ids=gpu_ids,
        profile=numeric["numeric_profile"],
    )
    if _adapter_tensor_sha256(model) != numeric["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("state worker loaded another beneficiary Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    _assert_trainable_parameter_precision(parameter_manifest)
    rows: list[dict[str, Any]] = []
    resumed = 0
    started = time.monotonic()
    for ordinal, job in enumerate(jobs):
        stem = str(job["realization_id"]).rsplit(":", 1)[-1]
        gradient_path = gradient_dir / f"{stem}.safetensors"
        checkpoint_path = checkpoint_dir / f"{stem}.json"
        if checkpoint_path.is_file():
            checkpoint = _read_json(checkpoint_path)
            if checkpoint.get("checkpoint_hash") != _worker_checkpoint_hash(checkpoint):
                raise ValueError("state gradient checkpoint identity changed")
            if (
                checkpoint.get("contract_hash") != contract["contract_hash"]
                or checkpoint.get("job_id") != job["job_id"]
                or not gradient_path.is_file()
                or checkpoint.get("sha256") != _sha256(gradient_path)
            ):
                raise ValueError("state gradient checkpoint changed")
            rows.append(checkpoint)
            resumed += 1
            continue
        realization = realizations[str(job["record_id"])]
        _seed_everything(int(job["gradient_seed"]))
        gradient, loss, supervised_tokens = _record_gradient(
            model,
            tokenizer,
            realization.record,
            mode="train",
        )
        save_file(gradient, gradient_path)
        row: dict[str, Any] = {
            "schema_version": "finance_development_state_gradient_shard.v22",
            "contract_hash": contract["contract_hash"],
            "partition_index": partition_index,
            "partition_count": partition_count,
            "job_ordinal": ordinal,
            **job,
            "file": str(gradient_path.resolve()),
            "sha256": _sha256(gradient_path),
            "loss": loss,
            "supervised_tokens": supervised_tokens,
            "gradient_norm": _gradient_norm(gradient),
        }
        row["checkpoint_hash"] = _worker_checkpoint_hash(row)
        _write_json(checkpoint_path, row)
        rows.append(row)
        del gradient
    report: dict[str, Any] = {
        "schema_version": STATE_WORKER_VERSION,
        "contract": _artifact_ref(contract_path, contract_hash=contract["contract_hash"]),
        "partition_index": partition_index,
        "partition_count": partition_count,
        "gpu_ids": list(gpu_ids),
        "assigned_count": len(jobs),
        "completed_before_resume": resumed,
        "completed_now": len(jobs) - resumed,
        "runtime_seconds": time.monotonic() - started,
        "peak_memory_by_device": {
            str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
        },
        "resolved_device_map": device_map,
        "parameter_manifest": parameter_manifest,
        "parameter_manifest_hash": parameter_manifest_hash,
        "gradient_rows": sorted(rows, key=lambda row: str(row["job_id"])),
        "status": "passed",
    }
    report["report_hash"] = canonical_hash(report, prefix=STATE_WORKER_PREFIX)
    report_path = report_dir / f"partition_{partition_index}.json"
    _write_json(report_path, report)
    del model, tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    return report


def _verify_state_worker_report(value: Mapping[str, Any], *, contract_hash: str) -> dict[str, Any]:
    report = dict(value)
    _replay_hash(report, field="report_hash", prefix=STATE_WORKER_PREFIX)
    if (
        report.get("schema_version") != STATE_WORKER_VERSION
        or report.get("status") != "passed"
        or report.get("contract", {}).get("contract_hash") != contract_hash
        or report.get("assigned_count") != len(report.get("gradient_rows", ()))
    ):
        raise ValueError("state worker report differs")
    for row in report["gradient_rows"]:
        path = Path(str(row["file"]))
        if not path.is_file() or _sha256(path) != row.get("sha256"):
            raise ValueError("state gradient shard changed")
        if row.get("checkpoint_hash") != _worker_checkpoint_hash(row):
            raise ValueError("state gradient checkpoint hash differs")
    return report


def combine_state_gradients(
    *, contract_path: Path, worker_dir: Path, output_dir: Path
) -> dict[str, Any]:
    from safetensors.torch import save_file

    contract = verify_target_contract(_read_json(contract_path))
    reports = [
        _verify_state_worker_report(
            _read_json(worker_dir / f"partition_{index}.json"),
            contract_hash=contract["contract_hash"],
        )
        for index in range(contract["state_worker_partition_count"])
    ]
    if {report["partition_index"] for report in reports} != set(
        range(contract["state_worker_partition_count"])
    ):
        raise ValueError("state worker partitions differ")
    parameter_hashes = {report["parameter_manifest_hash"] for report in reports}
    if len(parameter_hashes) != 1:
        raise ValueError("state workers used different parameter manifests")
    gradient_rows = [row for report in reports for row in report["gradient_rows"]]
    expected_jobs = {str(job["job_id"]): job for job in contract["state_gradient_jobs"]}
    if {str(row["job_id"]) for row in gradient_rows} != set(expected_jobs):
        raise ValueError("state gradient job coverage differs")
    by_state: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in gradient_rows:
        by_state[(str(row["task_id"]), str(row["state_id"]))].append(row)
    distributions = _load_conditional_distributions(
        _verify_ref(contract["inputs"]["distributions"], label="distributions")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir = output_dir / "state_mean_gradients"
    task_dir = output_dir / "task_mean_gradients"
    state_dir.mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    state_artifacts = []
    state_means: dict[tuple[str, str], dict[str, Any]] = {}
    for index, key in enumerate(sorted(by_state)):
        rows = sorted(by_state[key], key=lambda row: str(row["realization_id"]))
        if len(rows) != 5:
            raise ValueError("state aggregate requires five realizations")
        gradients = [
            _load_verified_gradient(Path(str(row["file"])), str(row["sha256"])) for row in rows
        ]
        mean_gradient = _weighted_gradient(gradients, [1.0] * len(gradients))
        path = state_dir / f"state_{index:03d}.safetensors"
        save_file(mean_gradient, path)
        state_means[key] = mean_gradient
        state_artifacts.append(
            {
                "task_id": key[0],
                "state_id": key[1],
                "file": str(path.resolve()),
                "sha256": _sha256(path),
                "gradient_norm": _gradient_norm(mean_gradient),
                "realization_ids": [str(row["realization_id"]) for row in rows],
            }
        )
        del gradients
    task_artifacts = []
    task_means: dict[str, dict[str, Any]] = {}
    for index, task_id in enumerate(sorted(distributions)):
        probabilities = distributions[task_id].probabilities
        gradients = [state_means[(task_id, state_id)] for state_id in sorted(probabilities)]
        weights = [float(probabilities[state_id]) for state_id in sorted(probabilities)]
        task_mean = _weighted_gradient(gradients, weights)
        path = task_dir / f"task_{index:02d}.safetensors"
        save_file(task_mean, path)
        task_means[task_id] = task_mean
        task_artifacts.append(
            {
                "task_id": task_id,
                "file": str(path.resolve()),
                "sha256": _sha256(path),
                "gradient_norm": _gradient_norm(task_mean),
            }
        )
    global_gradient = _weighted_gradient(
        [task_means[task_id] for task_id in sorted(task_means)],
        [1.0] * len(task_means),
    )
    optimizer = contract["optimizer_contract"]
    norm = _gradient_norm(global_gradient)
    clip_scale = min(1.0, float(optimizer["maximum_gradient_norm"]) / norm)
    update = {
        name: (
            float(optimizer["learning_rate"])
            * (value * clip_scale)
            / (value.abs() * clip_scale + float(optimizer["epsilon"]))
        ).contiguous()
        for name, value in global_gradient.items()
    }
    global_path = output_dir / "global_gradient.safetensors"
    update_path = output_dir / "global_update.safetensors"
    save_file(global_gradient, global_path)
    save_file(update, update_path)
    manifest: dict[str, Any] = {
        "schema_version": STATE_AGGREGATE_VERSION,
        "contract": _artifact_ref(contract_path, contract_hash=contract["contract_hash"]),
        "state_worker_report_hashes": [report["report_hash"] for report in reports],
        "parameter_manifest": reports[0]["parameter_manifest"],
        "parameter_manifest_hash": reports[0]["parameter_manifest_hash"],
        "realization_gradient_artifacts": sorted(
            gradient_rows, key=lambda row: str(row["realization_id"])
        ),
        "state_mean_artifacts": state_artifacts,
        "task_mean_artifacts": task_artifacts,
        "global_gradient_artifact": {
            "file": str(global_path.resolve()),
            "sha256": _sha256(global_path),
            "gradient_norm": norm,
        },
        "global_update_artifact": {
            "file": str(update_path.resolve()),
            "sha256": _sha256(update_path),
            "update_norm": _gradient_norm(update),
        },
        "global_gradient_clip_scale": clip_scale,
        "task_marginal": 1.0 / len(task_means),
        "task_count": len(task_means),
        "state_count": len(state_artifacts),
        "realization_count": len(gradient_rows),
        "status": "passed",
    }
    manifest["manifest_hash"] = canonical_hash(manifest, prefix=STATE_AGGREGATE_PREFIX)
    _write_json(output_dir / "state_gradient_manifest.json", manifest)
    return manifest


def _verify_state_manifest(value: Mapping[str, Any], *, contract_hash: str) -> dict[str, Any]:
    manifest = dict(value)
    _replay_hash(manifest, field="manifest_hash", prefix=STATE_AGGREGATE_PREFIX)
    if (
        manifest.get("schema_version") != STATE_AGGREGATE_VERSION
        or manifest.get("status") != "passed"
        or manifest.get("contract", {}).get("contract_hash") != contract_hash
        or manifest.get("task_count") != 30
        or manifest.get("state_count") != 100
        or manifest.get("realization_count") != 500
    ):
        raise ValueError("state gradient aggregate differs")
    for key in ("global_gradient_artifact", "global_update_artifact"):
        item = manifest[key]
        path = Path(str(item["file"]))
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ValueError(f"state aggregate changed:{key}")
    return manifest


def run_objective_gradient_worker(
    *,
    contract_path: Path,
    state_manifest_path: Path,
    output_dir: Path,
    partition_index: int,
    partition_count: int,
    gpu_ids: tuple[int, ...],
) -> dict[str, Any]:
    import torch
    from safetensors.torch import save_file

    contract = verify_target_contract(_read_json(contract_path))
    manifest = _verify_state_manifest(
        _read_json(state_manifest_path), contract_hash=contract["contract_hash"]
    )
    if partition_count != contract["objective_worker_partition_count"]:
        raise ValueError("Objective worker partition count differs")
    if not 0 <= partition_index < partition_count:
        raise ValueError("Objective worker partition index differs")
    if len(gpu_ids) != 3 or len(set(gpu_ids)) != 3:
        raise ValueError("Objective worker requires one three-GPU group")
    torch.cuda.set_device(gpu_ids[0])
    numeric = contract["numeric_execution"]
    _configure_numeric_policy(numeric["numeric_profile"])
    records = _load_records(
        _verify_ref(contract["inputs"]["objective_records"], label="objective_records")
    )
    splits = [
        item
        for index, item in enumerate(contract["objective_micro_splits"])
        if index % partition_count == partition_index
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    gradient_dir = output_dir / "objective_gradients"
    checkpoint_dir = output_dir / "objective_gradient_checkpoints"
    report_dir = output_dir / "objective_workers"
    gradient_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    tokenizer = _load_tokenizer(Path(str(numeric["model_dir"])))
    model, device_map = _load_execution_model(
        Path(str(numeric["model_dir"])),
        Path(str(numeric["beneficiary_adapter_dir"])),
        gpu_ids=gpu_ids,
        profile=numeric["numeric_profile"],
    )
    if _adapter_tensor_sha256(model) != numeric["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("Objective worker loaded another beneficiary Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    _assert_trainable_parameter_precision(parameter_manifest)
    global_update = _load_verified_gradient(
        Path(str(manifest["global_update_artifact"]["file"])),
        str(manifest["global_update_artifact"]["sha256"]),
    )
    _apply_descent_vector(model, global_update)
    post_update_adapter_hash = _adapter_tensor_sha256(model)
    rows: list[dict[str, Any]] = []
    resumed = 0
    started = time.monotonic()
    for split in splits:
        split_id = str(split["micro_split_id"])
        stem = split_id.rsplit("_", 1)[-1]
        path = gradient_dir / f"micro_split_{stem}.safetensors"
        checkpoint_path = checkpoint_dir / f"micro_split_{stem}.json"
        if checkpoint_path.is_file():
            checkpoint = _read_json(checkpoint_path)
            observed = dict(checkpoint)
            observed_hash = observed.pop("checkpoint_hash", None)
            if observed_hash != canonical_hash(
                observed, prefix="finance_development_objective_gradient_checkpoint:"
            ):
                raise ValueError("Objective gradient checkpoint identity changed")
            if (
                checkpoint.get("contract_hash") != contract["contract_hash"]
                or checkpoint.get("micro_split_id") != split_id
                or not path.is_file()
                or checkpoint.get("sha256") != _sha256(path)
            ):
                raise ValueError("Objective gradient checkpoint changed")
            rows.append(checkpoint)
            resumed += 1
            continue
        gradients = []
        losses = []
        supervised_tokens = []
        for record_index, record_id in enumerate(split["record_ids"]):
            if record_id not in records:
                raise ValueError("Objective record is missing")
            _seed_everything(
                int(
                    canonical_hash(
                        {
                            "micro_split_id": split_id,
                            "record_id": record_id,
                            "record_index": record_index,
                        },
                        prefix="finance_development_objective_gradient_seed:",
                    ).rsplit(":", 1)[-1][:8],
                    16,
                )
            )
            gradient, loss, token_count = _record_gradient(
                model,
                tokenizer,
                records[record_id],
                mode="objective_eval",
            )
            gradients.append(gradient)
            losses.append(loss)
            supervised_tokens.append(token_count)
        aggregate = _weighted_gradient(gradients, [1.0] * len(gradients))
        save_file(aggregate, path)
        row: dict[str, Any] = {
            "schema_version": "finance_development_objective_gradient_shard.v22",
            "contract_hash": contract["contract_hash"],
            "state_manifest_hash": manifest["manifest_hash"],
            "partition_index": partition_index,
            "partition_count": partition_count,
            "micro_split_id": split_id,
            "record_ids": list(split["record_ids"]),
            "file": str(path.resolve()),
            "sha256": _sha256(path),
            "mean_loss": statistics.fmean(losses),
            "record_losses": losses,
            "supervised_tokens": supervised_tokens,
            "gradient_norm": _gradient_norm(aggregate),
        }
        row["checkpoint_hash"] = canonical_hash(
            row, prefix="finance_development_objective_gradient_checkpoint:"
        )
        _write_json(checkpoint_path, row)
        rows.append(row)
        del gradients, aggregate
    report: dict[str, Any] = {
        "schema_version": OBJECTIVE_WORKER_VERSION,
        "contract": _artifact_ref(contract_path, contract_hash=contract["contract_hash"]),
        "state_manifest": _artifact_ref(
            state_manifest_path, manifest_hash=manifest["manifest_hash"]
        ),
        "partition_index": partition_index,
        "partition_count": partition_count,
        "gpu_ids": list(gpu_ids),
        "assigned_count": len(splits),
        "completed_before_resume": resumed,
        "completed_now": len(splits) - resumed,
        "runtime_seconds": time.monotonic() - started,
        "peak_memory_by_device": {
            str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
        },
        "resolved_device_map": device_map,
        "parameter_manifest": parameter_manifest,
        "parameter_manifest_hash": parameter_manifest_hash,
        "post_update_adapter_hash": post_update_adapter_hash,
        "objective_rows": sorted(rows, key=lambda row: str(row["micro_split_id"])),
        "status": "passed",
    }
    report["report_hash"] = canonical_hash(report, prefix=OBJECTIVE_WORKER_PREFIX)
    _write_json(report_dir / f"partition_{partition_index}.json", report)
    del model, tokenizer, global_update
    gc.collect()
    torch.cuda.empty_cache()
    return report


def _verify_objective_worker_report(
    value: Mapping[str, Any], *, contract_hash: str, state_manifest_hash: str
) -> dict[str, Any]:
    report = dict(value)
    _replay_hash(report, field="report_hash", prefix=OBJECTIVE_WORKER_PREFIX)
    if (
        report.get("schema_version") != OBJECTIVE_WORKER_VERSION
        or report.get("status") != "passed"
        or report.get("contract", {}).get("contract_hash") != contract_hash
        or report.get("state_manifest", {}).get("manifest_hash") != state_manifest_hash
        or report.get("assigned_count") != len(report.get("objective_rows", ()))
    ):
        raise ValueError("Objective worker report differs")
    for row in report["objective_rows"]:
        path = Path(str(row["file"]))
        if not path.is_file() or _sha256(path) != row.get("sha256"):
            raise ValueError("Objective gradient shard changed")
    return report


def cold_start_adamw_vjp(
    global_gradient: Mapping[str, Any],
    objective_loss_gradient: Mapping[str, Any],
    *,
    learning_rate: float,
    epsilon: float,
    maximum_gradient_norm: float,
    dtype: Any,
) -> dict[str, Any]:
    import torch

    if tuple(global_gradient) != tuple(objective_loss_gradient):
        raise ValueError("target VJP parameter manifests differ")
    if learning_rate <= 0 or epsilon <= 0 or maximum_gradient_norm <= 0:
        raise ValueError("target VJP optimizer constants are invalid")
    norm_squared = torch.zeros((), dtype=torch.float64)
    for value in global_gradient.values():
        norm_squared += torch.sum(value.double() * value.double())
    norm = math.sqrt(float(norm_squared))
    if not norm > 0:
        raise ValueError("target VJP requires a nonzero global gradient")
    scale = min(1.0, maximum_gradient_norm / norm)
    first: dict[str, Any] = {}
    dot_ag = torch.zeros((), dtype=torch.float64)
    for name, value in global_gradient.items():
        gradient = value.to(dtype=dtype)
        objective = objective_loss_gradient[name].to(dtype=dtype)
        clipped = gradient * scale
        derivative = learning_rate * epsilon / (clipped.abs() + epsilon).square()
        a_value = objective * derivative
        first[name] = a_value
        dot_ag += torch.sum(a_value.double() * gradient.double())
    if scale == 1.0:
        return {name: value.contiguous() for name, value in first.items()}
    correction = scale * float(dot_ag) / (norm * norm)
    return {
        name: (
            scale * first[name] - correction * global_gradient[name].to(dtype=dtype)
        ).contiguous()
        for name in first
    }


def _directional_dot(
    vjp: Mapping[str, Any],
    realization_gradient: Mapping[str, Any],
    task_mean_gradient: Mapping[str, Any],
) -> float:
    import torch

    if tuple(vjp) != tuple(realization_gradient) or tuple(vjp) != tuple(task_mean_gradient):
        raise ValueError("target directional parameter manifests differ")
    result = torch.zeros((), dtype=torch.float64)
    for name, value in vjp.items():
        difference = realization_gradient[name].to(dtype=value.dtype) - task_mean_gradient[name].to(
            dtype=value.dtype
        )
        result += torch.sum(value.double() * difference.double())
    return float(result)


def crossed_effect_summary(values: Mapping[tuple[str, str], float]) -> dict[str, float]:
    micro_splits = sorted({key[0] for key in values})
    realizations = sorted({key[1] for key in values})
    if len(values) != len(micro_splits) * len(realizations):
        raise ValueError("crossed target matrix is incomplete")
    overall = statistics.fmean(values.values())
    objective_means = {
        micro_split: statistics.fmean(
            values[(micro_split, realization)] for realization in realizations
        )
        for micro_split in micro_splits
    }
    realization_means = {
        realization: statistics.fmean(
            values[(micro_split, realization)] for micro_split in micro_splits
        )
        for realization in realizations
    }
    objective_variance = (
        statistics.variance(objective_means.values()) if len(objective_means) > 1 else 0.0
    )
    realization_variance = (
        statistics.variance(realization_means.values()) if len(realization_means) > 1 else 0.0
    )
    residuals = [
        values[(micro_split, realization)]
        - objective_means[micro_split]
        - realization_means[realization]
        + overall
        for micro_split in micro_splits
        for realization in realizations
    ]
    interaction_variance = statistics.variance(residuals) if len(residuals) > 1 else 0.0
    standard_error = math.sqrt(
        objective_variance / len(micro_splits)
        + realization_variance / len(realizations)
        + interaction_variance / len(values)
    )
    return {
        "mean": overall,
        "objective_variance": objective_variance,
        "realization_variance": realization_variance,
        "interaction_variance": interaction_variance,
        "standard_error": standard_error,
        "ci_lower": overall - 1.96 * standard_error,
        "ci_upper": overall + 1.96 * standard_error,
    }


def homogeneous_mean_power_diagnostic(
    *, task_between_variance: float, measurement_variance: float, seed: int = 20262208
) -> list[dict[str, Any]]:
    if task_between_variance < 0 or measurement_variance < 0:
        raise ValueError("empirical power variances must be nonnegative")
    standard_deviation = math.sqrt(task_between_variance + measurement_variance)
    rows = []
    for task_count in POWER_TASK_GRID:
        randomizer = random.Random(seed + task_count)
        detected = 0
        for _ in range(POWER_REPLICATES):
            values = [randomizer.gauss(1.0, standard_deviation) for _ in range(task_count)]
            if standard_deviation == 0:
                detected += 1
                continue
            standard_error = statistics.stdev(values) / math.sqrt(task_count)
            detected += int(statistics.fmean(values) - 1.96 * standard_error > 0)
        power = detected / POWER_REPLICATES
        rows.append(
            {
                "task_count": task_count,
                "power": power,
                "target_power_reached": power >= TARGET_POWER,
            }
        )
    return rows


def aggregate_target_measurements(
    *,
    contract_path: Path,
    state_manifest_path: Path,
    objective_worker_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    import torch

    contract = verify_target_contract(_read_json(contract_path))
    state_manifest = _verify_state_manifest(
        _read_json(state_manifest_path), contract_hash=contract["contract_hash"]
    )
    objective_reports = [
        _verify_objective_worker_report(
            _read_json(objective_worker_dir / f"partition_{index}.json"),
            contract_hash=contract["contract_hash"],
            state_manifest_hash=state_manifest["manifest_hash"],
        )
        for index in range(contract["objective_worker_partition_count"])
    ]
    objective_rows = [row for report in objective_reports for row in report["objective_rows"]]
    if {str(row["micro_split_id"]) for row in objective_rows} != {
        str(item["micro_split_id"]) for item in contract["objective_micro_splits"]
    }:
        raise ValueError("Objective gradient coverage differs")
    if len({report["post_update_adapter_hash"] for report in objective_reports}) != 1:
        raise ValueError("Objective workers used different post-update checkpoints")
    global_gradient = _load_verified_gradient(
        Path(str(state_manifest["global_gradient_artifact"]["file"])),
        str(state_manifest["global_gradient_artifact"]["sha256"]),
    )
    optimizer = contract["optimizer_contract"]
    vjp32 = {}
    vjp64 = {}
    for row in sorted(objective_rows, key=lambda item: str(item["micro_split_id"])):
        objective = _load_verified_gradient(Path(str(row["file"])), str(row["sha256"]))
        split_id = str(row["micro_split_id"])
        vjp32[split_id] = cold_start_adamw_vjp(
            global_gradient,
            objective,
            learning_rate=float(optimizer["learning_rate"]),
            epsilon=float(optimizer["epsilon"]),
            maximum_gradient_norm=float(optimizer["maximum_gradient_norm"]),
            dtype=torch.float32,
        )
        vjp64[split_id] = cold_start_adamw_vjp(
            global_gradient,
            objective,
            learning_rate=float(optimizer["learning_rate"]),
            epsilon=float(optimizer["epsilon"]),
            maximum_gradient_norm=float(optimizer["maximum_gradient_norm"]),
            dtype=torch.float64,
        )
        del objective
    realization_refs = {
        str(row["realization_id"]): row for row in state_manifest["realization_gradient_artifacts"]
    }
    task_mean_refs = {str(row["task_id"]): row for row in state_manifest["task_mean_artifacts"]}
    realization_objects = _load_state_realizations(
        _verify_ref(contract["inputs"]["realizations"], label="realizations")
    )
    by_task: defaultdict[str, list[Any]] = defaultdict(list)
    for realization in realization_objects:
        by_task[realization.task_condition_id].append(realization)
    task_types = {str(row["task_id"]): str(row["task_type"]) for row in contract["task_rows"]}
    mpe = {
        (str(row["task_id"]), str(row["state_id"])): float(row["minimum_practical_effect"])
        for row in contract["mpe_rows"]
    }
    task_marginal = 1.0 / len(contract["task_rows"])
    observations: list[dict[str, Any]] = []
    state_mean_targets: defaultdict[tuple[str, str, str], list[float]] = defaultdict(list)
    maximum_numeric_delta = 0.0
    for task_id in sorted(by_task):
        task_mean_ref = task_mean_refs[task_id]
        task_mean = _load_verified_gradient(
            Path(str(task_mean_ref["file"])), str(task_mean_ref["sha256"])
        )
        for realization in sorted(by_task[task_id], key=lambda item: item.realization_id):
            ref = realization_refs[realization.realization_id]
            gradient = _load_verified_gradient(Path(str(ref["file"])), str(ref["sha256"]))
            for split_id in sorted(vjp32):
                target32 = task_marginal * _directional_dot(vjp32[split_id], gradient, task_mean)
                target64 = task_marginal * _directional_dot(vjp64[split_id], gradient, task_mean)
                numeric_delta = abs(target64 - target32)
                maximum_numeric_delta = max(maximum_numeric_delta, numeric_delta)
                key = (task_id, realization.state_id, split_id)
                state_mean_targets[key].append(target64)
                observations.append(
                    {
                        "task_id": task_id,
                        "task_type": task_types[task_id],
                        "state_id": realization.state_id,
                        "realization_id": realization.realization_id,
                        "micro_split_id": split_id,
                        "target_value": target64,
                        "float32_target_value": target32,
                        "numeric_absolute_delta": numeric_delta,
                        "minimum_practical_effect": mpe[(task_id, realization.state_id)],
                        "normalized_target_value": (
                            target64 / mpe[(task_id, realization.state_id)]
                        ),
                    }
                )
            del gradient
        del task_mean
    grouped: defaultdict[tuple[str, str], dict[tuple[str, str], float]] = defaultdict(dict)
    for row in observations:
        grouped[(str(row["task_id"]), str(row["state_id"]))][
            (str(row["micro_split_id"]), str(row["realization_id"]))
        ] = float(row["target_value"])
    primary_by_task = {
        str(key): str(value) for key, value in contract["primary_coordinate_by_task"].items()
    }
    state_summaries: list[dict[str, Any]] = []
    resolution_counts: Counter[str] = Counter()
    for (task_id, state_id), values in sorted(grouped.items()):
        summary = crossed_effect_summary(values)
        threshold = mpe[(task_id, state_id)]
        inference = classify_effect_interval(
            mean=float(summary["mean"]),
            ci_lower=float(summary["ci_lower"]),
            ci_upper=float(summary["ci_upper"]),
            minimum_practical_effect=threshold,
        )
        resolution = str(inference["joint_resolution"])
        if state_id == primary_by_task[task_id]:
            resolution_counts[resolution] += 1
        state_summaries.append(
            {
                "task_id": task_id,
                "task_type": task_types[task_id],
                "state_id": state_id,
                "is_primary_coordinate": state_id == primary_by_task[task_id],
                "minimum_practical_effect": threshold,
                "resolution": resolution,
                "dual_axis_inference": inference,
                **summary,
            }
        )
    distributions = _load_conditional_distributions(
        _verify_ref(contract["inputs"]["distributions"], label="distributions")
    )
    maximum_center_error = 0.0
    for split_id in sorted(vjp64):
        for task_id, distribution in sorted(distributions.items()):
            centered = 0.0
            for state_id, probability in distribution.probabilities.items():
                state_values = state_mean_targets[(task_id, state_id, split_id)]
                centered += float(probability) * statistics.fmean(state_values)
            maximum_center_error = max(maximum_center_error, abs(centered))
    primary = [row for row in state_summaries if row["is_primary_coordinate"]]
    normalized_means = [
        float(row["mean"]) / float(row["minimum_practical_effect"]) for row in primary
    ]
    normalized_measurement_variances = [
        float(row["standard_error"]) ** 2 / float(row["minimum_practical_effect"]) ** 2
        for row in primary
    ]
    observed_variance = statistics.variance(normalized_means)
    mean_measurement_variance = statistics.fmean(normalized_measurement_variances)
    task_between_variance = max(0.0, observed_variance - mean_measurement_variance)
    homogeneous_power_rows = homogeneous_mean_power_diagnostic(
        task_between_variance=task_between_variance,
        measurement_variance=mean_measurement_variance,
    )
    diagnostic_task_count = next(
        (row["task_count"] for row in homogeneous_power_rows if row["target_power_reached"]),
        None,
    )
    per_state_components = [
        {
            "objective": float(row["objective_variance"]),
            "realization": float(row["realization_variance"]),
            "interaction": float(row["interaction_variance"]),
        }
        for row in state_summaries
    ]
    task_means = defaultdict(list)
    for row in state_summaries:
        task_means[str(row["task_id"])].append(float(row["mean"]))
    task_effects = {task_id: statistics.fmean(values) for task_id, values in task_means.items()}
    family_means: defaultdict[str, list[float]] = defaultdict(list)
    for task_id, value in task_effects.items():
        family_means[task_types[task_id]].append(value)
    family_effects = {key: statistics.fmean(values) for key, values in family_means.items()}
    family_variance = statistics.variance(family_effects.values())
    task_within_family = statistics.fmean(
        statistics.variance(values) if len(values) > 1 else 0.0 for values in family_means.values()
    )
    state_within_task = statistics.fmean(
        statistics.variance(values) if len(values) > 1 else 0.0 for values in task_means.values()
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    observations_path = output_dir / "target_observations.jsonl"
    _write_jsonl(observations_path, observations)
    report: dict[str, Any] = {
        "report_version": TARGET_REPORT_VERSION,
        "run_role": "development_exact_target_only",
        "contract": _artifact_ref(contract_path, contract_hash=contract["contract_hash"]),
        "state_manifest": _artifact_ref(
            state_manifest_path, manifest_hash=state_manifest["manifest_hash"]
        ),
        "objective_worker_report_hashes": [report["report_hash"] for report in objective_reports],
        "post_update_adapter_hash": objective_reports[0]["post_update_adapter_hash"],
        "observation_artifact": _artifact_ref(observations_path),
        "task_count": len(contract["task_rows"]),
        "state_count": len(contract["state_rows"]),
        "realization_count": len(realization_objects),
        "objective_micro_split_count": len(objective_rows),
        "target_observation_count": len(observations),
        "primary_coordinate_count": len(primary),
        "primary_resolution_counts": dict(sorted(resolution_counts.items())),
        "state_summaries": state_summaries,
        "variance_components": {
            "family_between": family_variance,
            "task_within_family": task_within_family,
            "state_within_task": state_within_task,
            "objective_mean": statistics.fmean(row["objective"] for row in per_state_components),
            "realization_mean": statistics.fmean(
                row["realization"] for row in per_state_components
            ),
            "objective_realization_interaction_mean": statistics.fmean(
                row["interaction"] for row in per_state_components
            ),
            "numeric_maximum_absolute_delta": maximum_numeric_delta,
        },
        "simplex_center_maximum_absolute_error": maximum_center_error,
        "homogeneous_mean_power_diagnostic": {
            "effect_size": "one_update_derived_mpe",
            "normalized_task_between_variance": task_between_variance,
            "normalized_measurement_variance": mean_measurement_variance,
            "observed_primary_normalized_mean_variance": observed_variance,
            "rows": homogeneous_power_rows,
            "diagnostic_task_count": diagnostic_task_count,
            "accepted_as_final_validation_task_count": False,
            "interpretation": (
                "A homogeneous one-MPE population-mean diagnostic cannot freeze the number "
                "of task-specific coordinates required for proxy-target validation."
            ),
        },
        "nested_variance_measurement_status": "measured_on_development_only",
        "final_validation_task_count_frozen": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "status": "development_target_variance_measured",
        "claim_boundary": (
            "This report estimates nested variance and power for an exact one-step Development "
            "surrogate. Development outcomes may size a future fresh Validation study, but they "
            "cannot establish target identifiability on Validation, evaluate GP-C, authorize "
            "Contribution, update VTDO, or support Student claims."
        ),
    }
    report["report_hash"] = canonical_hash(report, prefix=TARGET_REPORT_PREFIX)
    _write_json(output_dir / "report.json", report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure the Finance v22 exact one-step Development target"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--repo-root", type=Path, required=True)
    prepare.add_argument("--development-contract", type=Path, required=True)
    prepare.add_argument("--development-report", type=Path, required=True)
    prepare.add_argument("--task-states", type=Path, required=True)
    prepare.add_argument("--distributions", type=Path, required=True)
    prepare.add_argument("--realizations", type=Path, required=True)
    prepare.add_argument("--realization-report", type=Path, required=True)
    prepare.add_argument("--objective-support", type=Path, required=True)
    prepare.add_argument("--objective-records", type=Path, required=True)
    prepare.add_argument("--source-gradient-plan", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    state_worker = commands.add_parser("state-worker")
    state_worker.add_argument("--contract", type=Path, required=True)
    state_worker.add_argument("--output-dir", type=Path, required=True)
    state_worker.add_argument("--partition-index", type=int, required=True)
    state_worker.add_argument("--partition-count", type=int, required=True)
    state_worker.add_argument("--gpu-ids", type=int, nargs=3, required=True)
    combine = commands.add_parser("combine-state-gradients")
    combine.add_argument("--contract", type=Path, required=True)
    combine.add_argument("--worker-dir", type=Path, required=True)
    combine.add_argument("--output-dir", type=Path, required=True)
    objective = commands.add_parser("objective-worker")
    objective.add_argument("--contract", type=Path, required=True)
    objective.add_argument("--state-manifest", type=Path, required=True)
    objective.add_argument("--output-dir", type=Path, required=True)
    objective.add_argument("--partition-index", type=int, required=True)
    objective.add_argument("--partition-count", type=int, required=True)
    objective.add_argument("--gpu-ids", type=int, nargs=3, required=True)
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--contract", type=Path, required=True)
    aggregate.add_argument("--state-manifest", type=Path, required=True)
    aggregate.add_argument("--objective-worker-dir", type=Path, required=True)
    aggregate.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        result = prepare_target_contract(
            repo_root=args.repo_root,
            development_contract_path=args.development_contract,
            development_report_path=args.development_report,
            task_states_path=args.task_states,
            distributions_path=args.distributions,
            realizations_path=args.realizations,
            realization_report_path=args.realization_report,
            objective_support_path=args.objective_support,
            objective_records_path=args.objective_records,
            source_gradient_plan_path=args.source_gradient_plan,
            output_path=args.output,
        )
    elif args.command == "state-worker":
        result = run_state_gradient_worker(
            contract_path=args.contract,
            output_dir=args.output_dir,
            partition_index=args.partition_index,
            partition_count=args.partition_count,
            gpu_ids=tuple(args.gpu_ids),
        )
    elif args.command == "combine-state-gradients":
        result = combine_state_gradients(
            contract_path=args.contract,
            worker_dir=args.worker_dir,
            output_dir=args.output_dir,
        )
    elif args.command == "objective-worker":
        result = run_objective_gradient_worker(
            contract_path=args.contract,
            state_manifest_path=args.state_manifest,
            output_dir=args.output_dir,
            partition_index=args.partition_index,
            partition_count=args.partition_count,
            gpu_ids=tuple(args.gpu_ids),
        )
    else:
        result = aggregate_target_measurements(
            contract_path=args.contract,
            state_manifest_path=args.state_manifest,
            objective_worker_dir=args.objective_worker_dir,
            output_dir=args.output_dir,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
