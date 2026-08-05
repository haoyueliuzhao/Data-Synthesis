from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_ALIGNMENT_VERSION,
    _gradient_alignment,
    _gradient_norm,
    _gradient_parameter_manifest,
    _load_gradient_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_numeric_validation import (
    DEFAULT_MARGIN_ORDERING_POLICY,
    derive_pairwise_uncertainty_envelope,
    evaluate_margin_aware_ordering,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_precision_calibration import (
    PRECISION_PROFILES as ALL_PRECISION_PROFILES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_precision_calibration import (
    PrecisionProfile,
    _adapter_tensor_sha256,
    _configure_numeric_policy,
    _derive_validation_thresholds,
    _gradient_decomposition_shared_token_loss,
    _load_calibration_model,
    _load_records,
    _load_tokenizer,
    _seed_everything,
    _summary,
)
from trusted_synthesis.hashing import canonical_hash

CALIBRATION_VERSION = "finance_gradient_finite_precision_calibration.v5"
PROFILE_CHECKPOINT_VERSION = "finance_gradient_precision_v5_checkpoint.v1"
POPULATION_VERSION = "finance_gradient_calibration_population.v2"
SPLITS = ("development", "validation")
OBJECTIVE_SPLIT_BY_CALIBRATION_SPLIT = {
    "development": "estimation",
    "validation": "validation",
}
RAW_THRESHOLD_KEYS = {
    "maximum_loss_identity_absolute_error",
    "minimum_gradient_recomposition_cosine",
    "maximum_gradient_recomposition_relative_error",
    "maximum_gp_score_absolute_delta",
    "maximum_update_total_variation",
    "maximum_update_jensen_shannon",
}
RAW_SAFETY_BOUNDS = {
    "maximum_loss_identity_absolute_error": 1e-6,
    "minimum_gradient_recomposition_cosine": 0.999,
    "maximum_gradient_recomposition_relative_error": 0.03,
    "maximum_gp_score_absolute_delta": 0.005,
    "maximum_update_total_variation": 0.001,
    "maximum_update_jensen_shannon": 1e-6,
}
EXPECTED_TASK_FAMILIES = {
    "comparison",
    "derived_growth_comparison",
    "registered_ratio",
    "temporal_absolute_change",
    "temporal_average",
    "temporal_growth",
}
ACTIVE_PRECISION_PROFILE_IDS = (
    "bf16_checkpoint_tf32_v10_control",
    "bf16_checkpoint_strict_accumulation",
)
PRECISION_PROFILES = tuple(
    profile
    for profile in ALL_PRECISION_PROFILES
    if profile.profile_id in ACTIVE_PRECISION_PROFILE_IDS
)
if tuple(profile.profile_id for profile in PRECISION_PROFILES) != ACTIVE_PRECISION_PROFILE_IDS:
    raise RuntimeError("numeric calibration v5 profile registry order differs")
GIB = 1024**3
PROFILE_RESOURCE_CONTRACTS = {
    profile_id: {
        "required_gpu_count": 1,
        "minimum_free_memory_bytes_per_gpu": 64 * GIB,
    }
    for profile_id in ACTIVE_PRECISION_PROFILE_IDS
}
NUMERIC_ALGORITHM_CONTRACT = {
    "algorithm_version": "shared_token_loss_gradient_decomposition.v1",
    "forward_graph_count_per_realization": 1,
    "cross_entropy_evaluation_count_per_realization": 1,
    "region_loss_policy": "slice_one_shared_per_token_cross_entropy_vector",
    "vjp_policy": "full_common_differential_on_one_retained_forward_graph",
    "checkpoint_policy": "deterministic_eval_without_stochastic_children",
}
NUMERIC_ALGORITHM_CONTRACT_HASH = canonical_hash(
    NUMERIC_ALGORITHM_CONTRACT,
    prefix="finance_gradient_numeric_algorithm_contract:",
)


def _profile(profile_id: str) -> PrecisionProfile:
    for profile in PRECISION_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise ValueError(f"unknown numeric calibration v5 profile:{profile_id}")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object:{path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _checkpoint_source_identity(source: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "plan_hash",
        "plan_sha256",
        "manifest_hash",
        "manifest_sha256",
        "objective_split",
        "objective_record_set_id",
        "target_records_sha256",
        "token_region_manifest_hash",
        "beneficiary_adapter_tensor_sha256",
    )
    return {key: source[key] for key in keys}


def _profile_checkpoint_path(
    output_dir: Path,
    *,
    split: str,
    profile_id: str,
    job_id: str,
) -> Path:
    job_digest = hashlib.sha256(job_id.encode("utf-8")).hexdigest()
    return output_dir / "checkpoints" / split / profile_id / f"{job_digest}.json"


def _build_profile_checkpoint(
    *,
    plan: dict[str, Any],
    source: dict[str, Any],
    split: str,
    profile: PrecisionProfile,
    job: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "checkpoint_version": PROFILE_CHECKPOINT_VERSION,
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "split": split,
        "profile": asdict(profile),
        "numeric_algorithm_contract_hash": NUMERIC_ALGORITHM_CONTRACT_HASH,
        "source_identity": _checkpoint_source_identity(source),
        "job": job,
        "row": row,
    }
    value["checkpoint_hash"] = canonical_hash(
        value,
        prefix="finance_gradient_precision_v5_checkpoint:",
    )
    return value


def _verify_profile_checkpoint(
    checkpoint: dict[str, Any],
    *,
    plan: dict[str, Any],
    source: dict[str, Any],
    split: str,
    profile: PrecisionProfile,
    job: dict[str, Any],
) -> None:
    _replay_hash(
        checkpoint,
        field="checkpoint_hash",
        prefix="finance_gradient_precision_v5_checkpoint:",
    )
    expected = {
        "checkpoint_version": PROFILE_CHECKPOINT_VERSION,
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "split": split,
        "profile": asdict(profile),
        "numeric_algorithm_contract_hash": NUMERIC_ALGORITHM_CONTRACT_HASH,
        "source_identity": _checkpoint_source_identity(source),
        "job": job,
    }
    if any(checkpoint.get(key) != value for key, value in expected.items()):
        raise ValueError("numeric calibration checkpoint identity differs")
    row = checkpoint.get("row")
    if not isinstance(row, dict):
        raise ValueError("numeric calibration checkpoint row is invalid")
    identity_keys = (
        "job_id",
        "task_id",
        "task_type",
        "state_id",
        "record_id",
        "gradient_seed",
    )
    if any(row.get(key) != job.get(key) for key in identity_keys):
        raise ValueError("numeric calibration checkpoint row identity differs")


def _load_profile_checkpoints(
    output_dir: Path,
    *,
    plan: dict[str, Any],
    source: dict[str, Any],
    split: str,
    profile: PrecisionProfile,
) -> dict[str, dict[str, Any]]:
    expected_jobs = {str(job["job_id"]): job for job in source["jobs"]}
    checkpoint_dir = output_dir / "checkpoints" / split / profile.profile_id
    if not checkpoint_dir.is_dir():
        return {}
    checkpoints: dict[str, dict[str, Any]] = {}
    for path in sorted(checkpoint_dir.glob("*.json")):
        checkpoint = _read_json(path)
        job_value = checkpoint.get("job")
        if not isinstance(job_value, dict):
            raise ValueError("numeric calibration checkpoint job is invalid")
        job_id = str(job_value.get("job_id", ""))
        job = expected_jobs.get(job_id)
        if job is None:
            raise ValueError("numeric calibration checkpoint references an unknown job")
        expected_path = _profile_checkpoint_path(
            output_dir,
            split=split,
            profile_id=profile.profile_id,
            job_id=job_id,
        )
        if path != expected_path:
            raise ValueError("numeric calibration checkpoint path identity differs")
        if job_id in checkpoints:
            raise ValueError("numeric calibration checkpoint job is duplicated")
        _verify_profile_checkpoint(
            checkpoint,
            plan=plan,
            source=source,
            split=split,
            profile=profile,
            job=job,
        )
        checkpoints[job_id] = checkpoint
    return checkpoints


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _replay_hash(value: dict[str, Any], *, field: str, prefix: str) -> str:
    expected = value.get(field)
    if not isinstance(expected, str) or not expected:
        raise ValueError(f"missing immutable identity:{field}")
    payload = dict(value)
    payload.pop(field, None)
    if canonical_hash(payload, prefix=prefix) != expected:
        raise ValueError(f"immutable identity replay failed:{field}")
    return expected


def _objective_aggregate(
    manifest: dict[str, Any],
    *,
    objective_split: str,
) -> dict[str, Any]:
    rows = [
        row
        for row in manifest.get("aggregate_gradients", ())
        if str(row.get("split")) == objective_split
    ]
    if len(rows) != 1:
        raise ValueError(f"objective aggregate is not unique:{objective_split}")
    row = rows[0]
    record_ids = tuple(str(value) for value in row.get("record_ids", ()))
    if not record_ids or len(set(record_ids)) != len(record_ids):
        raise ValueError("objective aggregate record identity is incomplete")
    return row


def _source_descriptor(
    source_run_dir: Path,
    *,
    split: str,
    expected_task_ids: set[str],
) -> dict[str, Any]:
    source_run_dir = source_run_dir.resolve()
    plan_path = source_run_dir / "plan.json"
    manifest_path = source_run_dir / "evaluation_gradient_manifest.json"
    plan = _read_json(plan_path)
    manifest = _read_json(manifest_path)
    plan_hash = _replay_hash(
        plan,
        field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
    )
    manifest_hash = _replay_hash(
        manifest,
        field="manifest_hash",
        prefix="finance_contribution_evaluation_gradient_manifest:",
    )
    if plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("numeric calibration source uses another gradient implementation")
    if manifest.get("plan_hash") != plan_hash:
        raise ValueError("numeric calibration source manifest crosses plans")
    target_records_path = Path(str(plan["target_records_path"])).resolve()
    if _sha256(target_records_path) != plan["target_records_sha256"]:
        raise ValueError("numeric calibration source records changed")
    task_ids = {str(value) for value in plan["task_distributions"]}
    if task_ids != expected_task_ids:
        raise ValueError(f"numeric calibration {split} tasks differ from frozen population")
    jobs = tuple(plan.get("jobs", ()))
    if not jobs or {str(row["task_id"]) for row in jobs} != task_ids:
        raise ValueError("numeric calibration source jobs do not cover frozen tasks")
    task_types = {str(row["task_type"]) for row in jobs}
    if task_types != EXPECTED_TASK_FAMILIES:
        raise ValueError("numeric calibration source lacks family-balanced task coverage")
    objective_split = OBJECTIVE_SPLIT_BY_CALIBRATION_SPLIT[split]
    objective = _objective_aggregate(manifest, objective_split=objective_split)
    return {
        "source_run_dir": str(source_run_dir),
        "plan_path": str(plan_path),
        "plan_sha256": _sha256(plan_path),
        "plan_hash": plan_hash,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "manifest_hash": manifest_hash,
        "model_dir": plan["model_dir"],
        "beneficiary_adapter_dir": plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": plan["beneficiary_adapter_tensor_sha256"],
        "target_records_path": str(target_records_path),
        "target_records_sha256": plan["target_records_sha256"],
        "token_region_manifest_hash": plan["token_region_decomposition"]["manifest_hash"],
        "token_regions": plan["token_region_decomposition"]["records"],
        "task_distributions": plan["task_distributions"],
        "jobs": jobs,
        "objective_split": objective_split,
        "objective_record_ids": tuple(str(value) for value in objective["record_ids"]),
        "objective_record_set_id": canonical_hash(
            tuple(sorted(str(value) for value in objective["record_ids"])),
            prefix="finance_gradient_numeric_objective_record_set:",
        ),
    }


def prepare(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    population_report_path = Path(args.population_report_path).resolve()
    population_report = _read_json(population_report_path)
    population_report_hash = _replay_hash(
        population_report,
        field="report_hash",
        prefix="finance_gradient_calibration_population:",
    )
    if population_report.get("population_version") != POPULATION_VERSION:
        raise ValueError("numeric calibration population version differs")
    if population_report.get("status") != "passed":
        raise ValueError("numeric calibration population did not pass")
    if population_report.get("sealed_candidate_outcomes_observed") is not False:
        raise ValueError("sealed candidate outcomes were observed before calibration")
    partitions = population_report.get("partitions")
    if not isinstance(partitions, dict) or set(partitions) != {
        "development",
        "validation",
        "sealed_candidate",
    }:
        raise ValueError("numeric calibration requires three frozen population partitions")
    expected_task_ids = {
        split: {str(value) for value in partitions[split]["task_ids"]} for split in SPLITS
    }
    sources = {
        "development": _source_descriptor(
            Path(args.development_source_run_dir),
            split="development",
            expected_task_ids=expected_task_ids["development"],
        ),
        "validation": _source_descriptor(
            Path(args.validation_source_run_dir),
            split="validation",
            expected_task_ids=expected_task_ids["validation"],
        ),
    }
    if sources["development"]["model_dir"] != sources["validation"]["model_dir"]:
        raise ValueError("numeric calibration source models differ")
    if (
        sources["development"]["beneficiary_adapter_tensor_sha256"]
        != sources["validation"]["beneficiary_adapter_tensor_sha256"]
    ):
        raise ValueError("numeric calibration beneficiary checkpoints differ")
    for key in ("task_id", "record_id", "gradient_seed"):
        development_values = {str(row[key]) for row in sources["development"]["jobs"]}
        validation_values = {str(row[key]) for row in sources["validation"]["jobs"]}
        if development_values & validation_values:
            raise ValueError(f"numeric calibration {key} partitions overlap")
    if set(sources["development"]["objective_record_ids"]) & set(
        sources["validation"]["objective_record_ids"]
    ):
        raise ValueError("numeric calibration objective records overlap")

    plan: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "source_gradient_version": GRADIENT_ALIGNMENT_VERSION,
        "population_report_path": str(population_report_path),
        "population_report_sha256": _sha256(population_report_path),
        "population_report_hash": population_report_hash,
        "population_partition_ids": {
            split: partitions[split]["task_set_id"]
            for split in ("development", "validation", "sealed_candidate")
        },
        "sources": sources,
        "profiles": tuple(asdict(profile) for profile in PRECISION_PROFILES),
        "profile_resource_contracts": PROFILE_RESOURCE_CONTRACTS,
        "numeric_algorithm_contract": NUMERIC_ALGORITHM_CONTRACT,
        "numeric_algorithm_contract_hash": NUMERIC_ALGORITHM_CONTRACT_HASH,
        "raw_safety_bounds": RAW_SAFETY_BOUNDS,
        "margin_ordering_policy": asdict(DEFAULT_MARGIN_ORDERING_POLICY),
        "selection_policy": ("raw_safety_and_margin_ordering_pass_then_min_update_tv_js_gp_delta"),
        "validation_blinding_policy": (
            "validation_profile_runs_only_after_development_selection_is_frozen"
        ),
        "sealed_candidate_policy": ("sealed_candidate_task_artifact_is_not_a_calibration_input"),
        "production_effect": "none_until_disjoint_validation_passes",
    }
    plan["plan_hash"] = canonical_hash(
        plan,
        prefix="finance_gradient_precision_v5_plan:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "plan.json", plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


def _verify_plan(plan: dict[str, Any]) -> None:
    if plan.get("calibration_version") != CALIBRATION_VERSION:
        raise ValueError("numeric calibration v5 plan version differs")
    if tuple(plan.get("profiles", ())) != tuple(asdict(profile) for profile in PRECISION_PROFILES):
        raise ValueError("numeric calibration v5 profile registry differs")
    if plan.get("profile_resource_contracts") != PROFILE_RESOURCE_CONTRACTS:
        raise ValueError("numeric calibration v5 resource contract differs")
    if plan.get("numeric_algorithm_contract") != NUMERIC_ALGORITHM_CONTRACT:
        raise ValueError("numeric calibration v5 algorithm contract differs")
    if plan.get("numeric_algorithm_contract_hash") != NUMERIC_ALGORITHM_CONTRACT_HASH:
        raise ValueError("numeric calibration v5 algorithm identity differs")
    _replay_hash(
        plan,
        field="plan_hash",
        prefix="finance_gradient_precision_v5_plan:",
    )
    if _sha256(Path(plan["population_report_path"])) != plan["population_report_sha256"]:
        raise ValueError("numeric calibration population report changed")
    for source in plan["sources"].values():
        for path_key, hash_key in (
            ("plan_path", "plan_sha256"),
            ("manifest_path", "manifest_sha256"),
            ("target_records_path", "target_records_sha256"),
        ):
            if _sha256(Path(source[path_key])) != source[hash_key]:
                raise ValueError(f"numeric calibration source changed:{path_key}")


def _verify_selection(selection: dict[str, Any], plan: dict[str, Any]) -> None:
    if selection.get("calibration_version") != CALIBRATION_VERSION:
        raise ValueError("numeric calibration selection version differs")
    if selection.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("numeric calibration selection crosses plans")
    _replay_hash(
        selection,
        field="selection_hash",
        prefix="finance_gradient_precision_v5_selection:",
    )
    if selection.get("validation_observed") is not False:
        raise ValueError("numeric calibration selection observed validation outcomes")
    if selection.get("sealed_candidate_outcomes_observed") is not False:
        raise ValueError("numeric calibration selection observed sealed-candidate outcomes")
    if selection.get("numeric_algorithm_contract_hash") != NUMERIC_ALGORITHM_CONTRACT_HASH:
        raise ValueError("numeric calibration selection algorithm identity differs")
    if selection.get("profile_resource_contracts") != PROFILE_RESOURCE_CONTRACTS:
        raise ValueError("numeric calibration selection resource contracts differ")


def _verify_result(
    result: dict[str, Any],
    plan: dict[str, Any],
    *,
    split: str,
    profile_id: str,
) -> None:
    if result.get("calibration_version") != CALIBRATION_VERSION:
        raise ValueError("numeric calibration result version differs")
    if result.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("numeric calibration result crosses plans")
    if result.get("split") != split:
        raise ValueError("numeric calibration result crosses splits")
    profile = result.get("profile")
    expected_profile = asdict(_profile(profile_id))
    if profile != expected_profile:
        raise ValueError("numeric calibration result profile identity differs")
    if result.get("numeric_algorithm_contract_hash") != NUMERIC_ALGORITHM_CONTRACT_HASH:
        raise ValueError("numeric calibration result algorithm identity differs")
    gpu_ids = tuple(int(value) for value in result.get("requested_cuda_device_ids", ()))
    resource_contract = PROFILE_RESOURCE_CONTRACTS[profile_id]
    if len(gpu_ids) != int(resource_contract["required_gpu_count"]):
        raise ValueError("numeric calibration result GPU count differs")
    if result.get("resource_contract") != resource_contract:
        raise ValueError("numeric calibration result resource contract differs")
    preflight = result.get("preflight_gpu_memory")
    if not isinstance(preflight, dict) or set(preflight) != {str(value) for value in gpu_ids}:
        raise ValueError("numeric calibration result preflight identity differs")
    minimum_free = int(resource_contract["minimum_free_memory_bytes_per_gpu"])
    if any(
        not isinstance(row, dict) or int(row.get("free_bytes", -1)) < minimum_free
        for row in preflight.values()
    ):
        raise ValueError("numeric calibration result violated GPU preflight")
    source = plan["sources"][split]
    for field in (
        "source_plan_hash",
        "source_manifest_hash",
        "objective_split",
        "objective_record_set_id",
    ):
        expected_field = {
            "source_plan_hash": "plan_hash",
            "source_manifest_hash": "manifest_hash",
            "objective_split": "objective_split",
            "objective_record_set_id": "objective_record_set_id",
        }[field]
        if result.get(field) != source[expected_field]:
            raise ValueError(f"numeric calibration result source differs:{field}")
    _replay_hash(
        result,
        field="result_hash",
        prefix="finance_gradient_precision_v5_result:",
    )


def _raw_summary(
    rows: list[dict[str, Any]],
    *,
    task_distributions: dict[str, Any],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    base_thresholds = {
        **thresholds,
        "minimum_task_rank_agreement": 0.0,
    }
    base = _summary(
        rows,
        task_distributions=task_distributions,
        thresholds=base_thresholds,
    )
    metrics = {
        key: float(value) for key, value in base["metrics"].items() if key in RAW_THRESHOLD_KEYS
    }
    passed = all(
        metrics[key] >= value if key.startswith("minimum_") else metrics[key] <= value
        for key, value in thresholds.items()
    )
    return {
        "metrics": metrics,
        "thresholds": thresholds,
        "task_rows": base["task_rows"],
        "strict_rank_agreement_diagnostic": float(base["metrics"]["minimum_task_rank_agreement"]),
        "status": "passed" if passed else "failed",
    }


def _combined_summary(
    rows: list[dict[str, Any]],
    *,
    task_distributions: dict[str, Any],
    raw_thresholds: dict[str, float],
    uncertainty_envelope: float | None,
) -> dict[str, Any]:
    raw = _raw_summary(
        rows,
        task_distributions=task_distributions,
        thresholds=raw_thresholds,
    )
    envelope_calibration = None
    if uncertainty_envelope is None:
        envelope_calibration = derive_pairwise_uncertainty_envelope(
            rows,
            full_score_field="full_gp_score",
            recomposed_score_field="recomposed_gp_score",
        )
        if envelope_calibration["status"] != "passed":
            return {
                "raw_numeric": raw,
                "envelope_calibration": envelope_calibration,
                "margin_ordering": None,
                "status": "failed",
                "failure_reasons": ("pairwise_uncertainty_envelope_exceeds_preregistered_cap",),
            }
        uncertainty_envelope = float(envelope_calibration["pairwise_uncertainty_envelope"])
    ordering = evaluate_margin_aware_ordering(
        rows,
        uncertainty_envelope=uncertainty_envelope,
        full_score_field="full_gp_score",
        recomposed_score_field="recomposed_gp_score",
    )
    failure_reasons = []
    if raw["status"] != "passed":
        failure_reasons.append("raw_numeric_precision_failed")
    if ordering["status"] != "passed":
        failure_reasons.append("margin_aware_ordering_failed")
    return {
        "raw_numeric": raw,
        "envelope_calibration": envelope_calibration,
        "margin_ordering": ordering,
        "status": "passed" if not failure_reasons else "failed",
        "failure_reasons": tuple(failure_reasons),
    }


def _gpu_memory_snapshot(torch: Any, gpu_ids: tuple[int, ...]) -> dict[str, dict[str, int]]:
    snapshot: dict[str, dict[str, int]] = {}
    for gpu_id in gpu_ids:
        free_bytes, total_bytes = torch.cuda.mem_get_info(gpu_id)
        snapshot[str(gpu_id)] = {
            "free_bytes": int(free_bytes),
            "total_bytes": int(total_bytes),
            "allocated_bytes": int(torch.cuda.memory_allocated(gpu_id)),
            "reserved_bytes": int(torch.cuda.memory_reserved(gpu_id)),
        }
    return snapshot


def _verify_gpu_resource_preflight(
    *,
    profile_id: str,
    gpu_ids: tuple[int, ...],
    snapshot: dict[str, dict[str, int]],
) -> dict[str, int]:
    contract = PROFILE_RESOURCE_CONTRACTS[profile_id]
    required_gpu_count = int(contract["required_gpu_count"])
    minimum_free = int(contract["minimum_free_memory_bytes_per_gpu"])
    if len(gpu_ids) != required_gpu_count:
        raise ValueError(f"numeric calibration v5 profile requires {required_gpu_count} GPU(s)")
    if any(row["free_bytes"] < minimum_free for row in snapshot.values()):
        raise ValueError("numeric calibration v5 GPU free-memory preflight failed")
    return contract


def run_profile(args: argparse.Namespace) -> None:
    import torch

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    split = str(args.split)
    if split not in SPLITS:
        raise ValueError("unknown numeric calibration split")
    profile: PrecisionProfile = _profile(str(args.profile_id))
    result_path = output_dir / split / f"{profile.profile_id}.json"
    if result_path.exists():
        raise ValueError("numeric calibration result already exists and is immutable")
    selection_path = output_dir / "selection.json"
    if split == "validation":
        if not selection_path.is_file():
            raise ValueError("validation cannot run before profile selection is frozen")
        selection = _read_json(selection_path)
        _verify_selection(selection, plan)
        if selection.get("selected_profile_id") != profile.profile_id:
            raise ValueError("validation may run only for the frozen selected profile")
        raw_thresholds = {
            str(key): float(value) for key, value in selection["frozen_raw_thresholds"].items()
        }
        uncertainty_envelope = float(selection["pairwise_uncertainty_envelope"])
    else:
        raw_thresholds = RAW_SAFETY_BOUNDS
        uncertainty_envelope = None

    gpu_ids = tuple(int(value) for value in args.gpu_ids)
    if not gpu_ids or len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError("numeric calibration requires unique GPU ids")
    if any(gpu_id < 0 or gpu_id >= torch.cuda.device_count() for gpu_id in gpu_ids):
        raise ValueError("numeric calibration GPU id is not visible")
    torch.cuda.set_device(gpu_ids[0])
    preflight_memory = _gpu_memory_snapshot(torch, gpu_ids)
    resource_contract = _verify_gpu_resource_preflight(
        profile_id=profile.profile_id,
        gpu_ids=gpu_ids,
        snapshot=preflight_memory,
    )
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    _seed_everything(20260841)
    _configure_numeric_policy(profile)
    source = plan["sources"][split]
    tokenizer = _load_tokenizer(Path(source["model_dir"]))
    started = time.monotonic()
    result: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "split": split,
        "profile": asdict(profile),
        "source_plan_hash": source["plan_hash"],
        "source_manifest_hash": source["manifest_hash"],
        "objective_split": source["objective_split"],
        "objective_record_set_id": source["objective_record_set_id"],
        "requested_cuda_device_ids": gpu_ids,
        "resource_contract": resource_contract,
        "preflight_gpu_memory": preflight_memory,
        "numeric_algorithm_contract_hash": NUMERIC_ALGORITHM_CONTRACT_HASH,
        "cuda_visible_devices_env": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    model: Any | None = None
    try:
        model, device_map = _load_calibration_model(
            model_dir=Path(source["model_dir"]),
            adapter_dir=Path(source["beneficiary_adapter_dir"]),
            profile=profile,
            gpu_ids=gpu_ids,
        )
        if _adapter_tensor_sha256(model) != source["beneficiary_adapter_tensor_sha256"]:
            raise ValueError("numeric calibration loaded another beneficiary Adapter")
        source_manifest = _read_json(Path(source["manifest_path"]))
        parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
        if parameter_manifest != source_manifest["parameter_manifest"]:
            raise ValueError("numeric calibration parameter manifest differs")
        if parameter_manifest_hash != source_manifest["parameter_manifest_hash"]:
            raise ValueError("numeric calibration parameter identity differs")
        _, objective_gradients = _load_gradient_artifacts(source_manifest)
        objective = objective_gradients[source["objective_split"]]
        objective_norm = _gradient_norm(objective)
        records = _load_records(Path(source["target_records_path"]))
        checkpoints = _load_profile_checkpoints(
            output_dir,
            plan=plan,
            source=source,
            split=split,
            profile=profile,
        )
        completed_before_resume = len(checkpoints)
        completed_now = 0
        for job in source["jobs"]:
            job_id = str(job["job_id"])
            if job_id in checkpoints:
                continue
            _seed_everything(int(job["gradient_seed"]))
            _configure_numeric_policy(profile)
            regions = source["token_regions"][job["record_id"]]
            decomposition = _gradient_decomposition_shared_token_loss(
                model,
                tokenizer,
                records[job["record_id"]],
                profile=profile,
                common_label_positions=tuple(
                    int(value) for value in regions["common_label_positions"]
                ),
                differential_label_positions=tuple(
                    int(value) for value in regions["differential_label_positions"]
                ),
            )
            full = decomposition.pop("full_gradient")
            recomposed = decomposition.pop("recomposed_gradient")
            _, full_score, _, _ = _gradient_alignment(full, objective)
            _, recomposed_score, _, _ = _gradient_alignment(recomposed, objective)
            row = {
                "job_id": job["job_id"],
                "task_id": job["task_id"],
                "task_type": job["task_type"],
                "state_id": job["state_id"],
                "record_id": job["record_id"],
                "gradient_seed": int(job["gradient_seed"]),
                "full_gp_score": full_score,
                "recomposed_gp_score": recomposed_score,
                "objective_gradient_norm": objective_norm,
                **decomposition,
            }
            checkpoint = _build_profile_checkpoint(
                plan=plan,
                source=source,
                split=split,
                profile=profile,
                job=job,
                row=row,
            )
            checkpoint_path = _profile_checkpoint_path(
                output_dir,
                split=split,
                profile_id=profile.profile_id,
                job_id=job_id,
            )
            if checkpoint_path.exists():
                raise ValueError("numeric calibration checkpoint appeared concurrently")
            _write_json(checkpoint_path, checkpoint)
            checkpoints[job_id] = checkpoint
            completed_now += 1
            del full, recomposed
        if len(checkpoints) != len(source["jobs"]):
            raise ValueError("numeric calibration checkpoint matrix is incomplete")
        rows = [checkpoints[str(job["job_id"])]["row"] for job in source["jobs"]]
        checkpoint_hashes = tuple(
            str(checkpoints[str(job["job_id"])]["checkpoint_hash"]) for job in source["jobs"]
        )
        result.update(
            {
                "status": "completed",
                "rows": rows,
                "checkpoint_version": PROFILE_CHECKPOINT_VERSION,
                "checkpoint_hashes": checkpoint_hashes,
                "completed_before_resume": completed_before_resume,
                "completed_now": completed_now,
                "summary": _combined_summary(
                    rows,
                    task_distributions=source["task_distributions"],
                    raw_thresholds=raw_thresholds,
                    uncertainty_envelope=uncertainty_envelope,
                ),
                "resolved_hf_device_map": device_map,
                "resolved_hf_device_map_hash": canonical_hash(
                    device_map,
                    prefix="finance_gradient_precision_v5_device_map:",
                ),
                "trainable_parameter_manifest": parameter_manifest,
                "trainable_parameter_manifest_hash": parameter_manifest_hash,
                "trainable_parameter_dtypes": tuple(
                    sorted({str(value["dtype"]) for value in parameter_manifest.values()})
                ),
            }
        )
        del objective_gradients, objective
        model = None
    except torch.cuda.OutOfMemoryError as error:
        failure_memory = _gpu_memory_snapshot(torch, gpu_ids)
        external_bytes = {
            gpu_id: max(
                0,
                row["total_bytes"] - row["free_bytes"] - row["reserved_bytes"],
            )
            for gpu_id, row in failure_memory.items()
        }
        failure_kind = (
            "resource_contention_failed"
            if max(external_bytes.values(), default=0) >= 8 * GIB
            else "resource_capacity_failed"
        )
        attempt = {
            **result,
            "status": failure_kind,
            "error_type": type(error).__name__,
            "error": str(error),
            "failure_gpu_memory": failure_memory,
            "estimated_external_gpu_bytes": external_bytes,
            "runtime_seconds": time.monotonic() - started,
            "peak_gpu_memory_bytes_by_requested_device": {
                str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
            },
            "torch_version": torch.__version__,
        }
        attempt["resource_attempt_hash"] = canonical_hash(
            attempt,
            prefix="finance_gradient_precision_v5_resource_attempt:",
        )
        attempt_suffix = str(attempt["resource_attempt_hash"]).split(":", 1)[-1]
        attempt_path = (
            output_dir / "resource_failures" / split / profile.profile_id / f"{attempt_suffix}.json"
        )
        _write_json(attempt_path, attempt)
        model = None
        assert model is None
        gc.collect()
        torch.cuda.empty_cache()
        print(json.dumps(attempt, ensure_ascii=False, indent=2, sort_keys=True))
        return
    result.update(
        {
            "runtime_seconds": time.monotonic() - started,
            "peak_gpu_memory_bytes_by_requested_device": {
                str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
            },
            "torch_version": torch.__version__,
        }
    )
    result["result_hash"] = canonical_hash(
        result,
        prefix="finance_gradient_precision_v5_result:",
    )
    _write_json(result_path, result)
    assert model is None
    gc.collect()
    torch.cuda.empty_cache()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def _derived_raw_thresholds(metrics: dict[str, Any]) -> dict[str, float]:
    old = _derive_validation_thresholds(
        {
            **{str(key): float(value) for key, value in metrics.items()},
            "minimum_task_rank_agreement": 1.0,
        }
    )
    return {key: float(value) for key, value in old.items() if key in RAW_THRESHOLD_KEYS}


def freeze_selection(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    validation_dir = output_dir / "validation"
    if validation_dir.exists() and any(validation_dir.glob("*.json")):
        raise ValueError("selection must be frozen before validation is observed")
    results = []
    for profile in PRECISION_PROFILES:
        path = output_dir / "development" / f"{profile.profile_id}.json"
        if not path.is_file():
            raise ValueError(f"missing development profile:{profile.profile_id}")
        result = _read_json(path)
        _verify_result(
            result,
            plan,
            split="development",
            profile_id=profile.profile_id,
        )
        results.append(result)
    eligible = [
        result
        for result in results
        if result.get("status") == "completed"
        and result.get("summary", {}).get("status") == "passed"
    ]
    selected = (
        min(
            eligible,
            key=lambda result: (
                float(
                    result["summary"]["raw_numeric"]["metrics"]["maximum_update_total_variation"]
                ),
                float(result["summary"]["raw_numeric"]["metrics"]["maximum_update_jensen_shannon"]),
                float(
                    result["summary"]["raw_numeric"]["metrics"]["maximum_gp_score_absolute_delta"]
                ),
                str(result["profile"]["profile_id"]),
            ),
        )
        if eligible
        else None
    )
    selection: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "status": "frozen" if selected is not None else "calibration_failed",
        "selected_profile_id": (
            str(selected["profile"]["profile_id"]) if selected is not None else None
        ),
        "development_result_hashes": tuple(str(result["result_hash"]) for result in results),
        "eligible_profile_ids": tuple(str(result["profile"]["profile_id"]) for result in eligible),
        "selection_policy": plan["selection_policy"],
        "numeric_algorithm_contract_hash": NUMERIC_ALGORITHM_CONTRACT_HASH,
        "profile_resource_contracts": PROFILE_RESOURCE_CONTRACTS,
        "selected_resource_contract": (
            PROFILE_RESOURCE_CONTRACTS[str(selected["profile"]["profile_id"])]
            if selected is not None
            else None
        ),
        "frozen_raw_thresholds": (
            _derived_raw_thresholds(selected["summary"]["raw_numeric"]["metrics"])
            if selected is not None
            else None
        ),
        "pairwise_uncertainty_envelope": (
            float(selected["summary"]["envelope_calibration"]["pairwise_uncertainty_envelope"])
            if selected is not None
            else None
        ),
        "margin_ordering_policy": plan["margin_ordering_policy"],
        "validation_observed": False,
        "sealed_candidate_outcomes_observed": False,
    }
    selection["selection_hash"] = canonical_hash(
        selection,
        prefix="finance_gradient_precision_v5_selection:",
    )
    _write_json(output_dir / "selection.json", selection)
    print(json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True))


def _reject_stale_frozen_contract(
    output_dir: Path,
    *,
    validation_passed: bool,
) -> None:
    contract_path = output_dir / "frozen_numeric_contract.json"
    if not validation_passed and contract_path.exists():
        raise ValueError(
            "failed numeric validation output contains a stale frozen contract"
        )


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    selection = _read_json(output_dir / "selection.json")
    _verify_selection(selection, plan)
    profile_id = selection.get("selected_profile_id")
    if selection.get("status") != "frozen" or not isinstance(profile_id, str):
        raise ValueError("numeric calibration v5 has no frozen profile")
    development = _read_json(output_dir / "development" / f"{profile_id}.json")
    validation = _read_json(output_dir / "validation" / f"{profile_id}.json")
    _verify_result(
        development,
        plan,
        split="development",
        profile_id=profile_id,
    )
    _verify_result(
        validation,
        plan,
        split="validation",
        profile_id=profile_id,
    )
    if development["result_hash"] not in selection["development_result_hashes"]:
        raise ValueError("selected development result is absent from selection lineage")
    if validation.get("summary", {}).get("raw_numeric", {}).get("thresholds") != selection.get(
        "frozen_raw_thresholds"
    ):
        raise ValueError("validation result does not use the frozen raw thresholds")
    if validation.get("summary", {}).get("margin_ordering", {}).get(
        "pairwise_uncertainty_envelope"
    ) != selection.get("pairwise_uncertainty_envelope"):
        raise ValueError("validation result does not use the frozen uncertainty envelope")
    validation_passed = bool(
        validation.get("status") == "completed"
        and validation.get("summary", {}).get("status") == "passed"
    )
    _reject_stale_frozen_contract(
        output_dir,
        validation_passed=validation_passed,
    )
    report: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "population_report_hash": plan["population_report_hash"],
        "selection_hash": selection["selection_hash"],
        "selected_profile": development["profile"],
        "selected_resource_contract": selection["selected_resource_contract"],
        "numeric_algorithm_contract_hash": NUMERIC_ALGORITHM_CONTRACT_HASH,
        "development_result_hash": development["result_hash"],
        "validation_result_hash": validation["result_hash"],
        "development_summary": development["summary"],
        "validation_summary": validation["summary"],
        "status": "passed" if validation_passed else "failed",
        "production_authorized": False,
        "authorization_effect": (
            "numeric_contract_frozen_for_one_independent_sealed_candidate"
            if validation_passed
            else "none"
        ),
        "claim_boundary": (
            "This calibration authorizes only the numeric profile and ordering contract. "
            "It does not authorize Contribution, GP-C, or a VTDO energy update."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_gradient_precision_v5_report:",
    )
    _write_json(output_dir / "report.json", report)
    if validation_passed:
        contract: dict[str, Any] = {
            "calibration_version": CALIBRATION_VERSION,
            "plan_hash": plan["plan_hash"],
            "population_report_hash": plan["population_report_hash"],
            "sealed_candidate_task_set_id": plan["population_partition_ids"]["sealed_candidate"],
            "selection_hash": selection["selection_hash"],
            "selected_profile": development["profile"],
            "selected_resource_contract": selection["selected_resource_contract"],
            "numeric_algorithm_contract": NUMERIC_ALGORITHM_CONTRACT,
            "numeric_algorithm_contract_hash": NUMERIC_ALGORITHM_CONTRACT_HASH,
            "raw_thresholds": selection["frozen_raw_thresholds"],
            "pairwise_uncertainty_envelope": selection["pairwise_uncertainty_envelope"],
            "margin_ordering_policy": selection["margin_ordering_policy"],
            "development_result_hash": development["result_hash"],
            "validation_result_hash": validation["result_hash"],
            "allowed_next_run_role": "independent_sealed_candidate",
        }
        contract["contract_hash"] = canonical_hash(
            contract,
            prefix="finance_gradient_precision_contract:",
        )
        _write_json(output_dir / "frozen_numeric_contract.json", contract)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate Gradient Projection precision on disjoint task families"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--population-report-path", required=True)
    prepare_parser.add_argument("--development-source-run-dir", required=True)
    prepare_parser.add_argument("--validation-source-run-dir", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.set_defaults(handler=prepare)
    run_parser = subparsers.add_parser("run-profile")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--profile-id", required=True)
    run_parser.add_argument("--split", choices=SPLITS, required=True)
    run_parser.add_argument("--gpu-ids", nargs="+", type=int, required=True)
    run_parser.set_defaults(handler=run_profile)
    freeze_parser = subparsers.add_parser("freeze-selection")
    freeze_parser.add_argument("--output-dir", required=True)
    freeze_parser.set_defaults(handler=freeze_selection)
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--output-dir", required=True)
    aggregate_parser.set_defaults(handler=aggregate)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
