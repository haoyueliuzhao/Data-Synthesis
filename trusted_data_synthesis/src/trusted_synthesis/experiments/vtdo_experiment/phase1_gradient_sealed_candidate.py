from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_contribution_gradient as gradient,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_gradient_numeric_root_cause as root,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_initial_distribution import (
    FinanceInitialDistributionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_reachability import (
    _load_model_config,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_state_realizations import (
    FinanceStateRealizationReport,
)
from trusted_synthesis.hashing import canonical_hash

SEALED_VERSION = "finance_gradient_numeric_sealed_candidate.v1"
SEALED_SOURCE_VERSION = "finance_gradient_numeric_sealed_source.v1"
SEALED_CHECKPOINT_VERSION = "finance_gradient_numeric_sealed_checkpoint.v1"
EXPECTED_CONTRACT_HASH = (
    "finance_gradient_numeric_contract:"
    "e2a1c890af575f477389b0bfb1475810aeecec3e5f4bf3a6213c552a82fa86b7"
)
EXPECTED_ROOT_PLAN_HASH = (
    "finance_gradient_numeric_root_cause_plan:"
    "8bc01deae493ebcc2d55ed7084fe954f87119d4a536b54c8bef3880417634662"
)
EXPECTED_SELECTION_HASH = (
    "finance_gradient_numeric_root_cause_selection:"
    "5518e72d2b46e9ab134ad216422ad3dc9d5eebb130292d782db2840bb11a126a"
)
EXPECTED_POPULATION_HASH = (
    "finance_gradient_calibration_population:"
    "9a019738f37bbcbdd35df8171709def13ef31c712d7c5336f88562233aa5b4c8"
)
EXPECTED_TASK_SET_ID = (
    "finance_gradient_calibration_task_set:"
    "884e85bc9a8f531c8fe36aab2920dc0ff1432428b1c0efca61122b92767cf034"
)
EXPECTED_PROFILE_ID = "fp32_activation_strict"
EXPECTED_TASK_FAMILIES = {
    "comparison",
    "derived_growth_comparison",
    "registered_ratio",
    "temporal_absolute_change",
    "temporal_average",
    "temporal_growth",
}
EXPECTED_TASK_COUNT = 6
EXPECTED_STATE_COUNT = 20
INITIAL_REPLICAS_PER_TASK = 4
REALIZATIONS_PER_STATE = 3
INITIAL_TEMPERATURE = 0.0
REALIZATION_TEMPERATURE = 0.2
INITIAL_SEED = 20260881
REALIZATION_SEED = 20260882
GRADIENT_SEED = 20260883
INITIAL_SAMPLING_SALT = "finance_v17_sealed_initial_distribution_20260805"
GRADIENT_SAMPLING_SALT = "finance_v17_sealed_gradient_source_20260805"
EXPECTED_OLD_NUMERIC_CONTRACT_HASH = (
    "finance_gradient_precision_contract:"
    "526e1c39d202b0168bede2e2df0ca08eeec5d0cc4587949bba554e0cef91396c"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"sealed JSON object is invalid:{path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _replay_hash(value: dict[str, Any], *, field: str, prefix: str) -> str:
    observed = value.get(field)
    if not isinstance(observed, str) or not observed:
        raise ValueError(f"sealed artifact has no {field}")
    payload = dict(value)
    payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"sealed artifact failed identity replay:{field}")
    return observed


def _implementation_sha256() -> str:
    return _sha256(Path(__file__).resolve())


def _require_absent_or_empty(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"sealed output already contains observations:{path}")


def _load_frozen_contract(
    contract_path: Path,
    *,
    root_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root_plan = _read_json(root_dir / "plan.json")
    root._verify_plan(root_plan)
    if root_plan["plan_hash"] != EXPECTED_ROOT_PLAN_HASH:
        raise ValueError("sealed candidate uses another root-cause plan")
    selection = _read_json(root_dir / "selection.json")
    root._verify_selection(selection, root_plan, output_dir=root_dir)
    if selection["selection_hash"] != EXPECTED_SELECTION_HASH:
        raise ValueError("sealed candidate uses another profile selection")
    contract = _read_json(contract_path)
    contract_hash = _replay_hash(
        contract,
        field="contract_hash",
        prefix="finance_gradient_numeric_contract:",
    )
    if contract_hash != EXPECTED_CONTRACT_HASH:
        raise ValueError("sealed candidate uses another numeric contract")
    if contract.get("contract_version") != "finance_gradient_numeric_contract.v17":
        raise ValueError("sealed candidate numeric contract version differs")
    if contract.get("allowed_next_run_role") != "independent_sealed_candidate":
        raise ValueError("numeric contract does not authorize the sealed role")
    if contract.get("selected_profile", {}).get("profile_id") != EXPECTED_PROFILE_ID:
        raise ValueError("sealed candidate profile differs")
    if contract.get("fixed_numeric_thresholds") != root.FIXED_NUMERIC_THRESHOLDS:
        raise ValueError("sealed candidate thresholds differ")
    if contract.get("pairwise_uncertainty_envelope") != selection.get(
        "pairwise_uncertainty_envelope"
    ):
        raise ValueError("sealed candidate uncertainty envelope differs")
    if contract.get("plan_hash") != root_plan["plan_hash"]:
        raise ValueError("numeric contract crosses root-cause plans")
    if contract.get("selection_hash") != selection["selection_hash"]:
        raise ValueError("numeric contract crosses profile selections")
    if contract.get("production_effect") != "none_until_sealed_candidate_passes":
        raise ValueError("sealed candidate production boundary differs")
    return contract, root_plan, selection


def _load_population(
    population_path: Path,
    *,
    artifacts_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
    population = _read_json(population_path)
    if (
        _replay_hash(
            population,
            field="report_hash",
            prefix="finance_gradient_calibration_population:",
        )
        != EXPECTED_POPULATION_HASH
    ):
        raise ValueError("sealed candidate population differs")
    if population.get("status") != "passed":
        raise ValueError("sealed candidate population did not pass")
    if population.get("sealed_candidate_outcomes_observed") is not False:
        raise ValueError("sealed candidate outcomes were already observed")
    partition = population.get("partitions", {}).get("sealed_candidate")
    if not isinstance(partition, dict):
        raise ValueError("sealed candidate partition is missing")
    if partition.get("task_set_id") != EXPECTED_TASK_SET_ID:
        raise ValueError("sealed candidate task set differs")
    if Path(str(partition.get("output_path"))).resolve() != artifacts_path:
        raise ValueError("sealed candidate Artifact path differs")
    if partition.get("output_sha256") != _sha256(artifacts_path):
        raise ValueError("sealed candidate Artifact changed")
    if set(partition.get("task_type_counts", {})) != EXPECTED_TASK_FAMILIES or any(
        int(value) != 1 for value in partition["task_type_counts"].values()
    ):
        raise ValueError("sealed candidate lacks family-balanced task coverage")
    task_ids = tuple(str(value) for value in partition.get("task_ids", ()))
    if len(task_ids) != EXPECTED_TASK_COUNT or len(set(task_ids)) != EXPECTED_TASK_COUNT:
        raise ValueError("sealed candidate task identity is incomplete")
    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    if {item.omega.task.task_id for item in artifacts} != set(task_ids):
        raise ValueError("sealed candidate task Artifact differs from its partition")
    state_count = sum(len(item.state_catalog.states) for item in artifacts)
    if state_count != EXPECTED_STATE_COUNT:
        raise ValueError("sealed candidate state count differs")
    return population, partition, tuple(sorted(task_ids))


def _load_support(
    support_dir: Path,
    *,
    artifacts_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _read_json(support_dir / "plan.json")
    report = _read_json(support_dir / "beneficiary_evaluation_report.json")
    _replay_hash(
        plan,
        field="plan_hash",
        prefix="finance_contribution_evaluation_support_plan:",
    )
    _replay_hash(
        report,
        field="report_hash",
        prefix="finance_contribution_evaluation_support_report:",
    )
    if plan.get("experiment_version") != gradient.REQUIRED_OBJECTIVE_SUPPORT_VERSION:
        raise ValueError("sealed candidate Objective Support version differs")
    if report.get("status") != "passed" or report.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("sealed candidate Objective Support did not pass")
    disjoint_paths = {Path(str(value)).resolve() for value in plan["disjoint_artifact_paths"]}
    if artifacts_path not in disjoint_paths or len(disjoint_paths) != 3:
        raise ValueError("Objective Support does not freeze all three numeric partitions")
    sha_by_path = dict(
        zip(
            (Path(str(value)).resolve() for value in plan["disjoint_artifact_paths"]),
            plan["disjoint_artifact_sha256"],
            strict=True,
        )
    )
    if sha_by_path[artifacts_path] != _sha256(artifacts_path):
        raise ValueError("Objective Support sealed Artifact changed")
    partitions = plan.get("objective_partitions")
    if not isinstance(partitions, dict) or set(partitions) != {
        "estimation",
        "validation",
        "authorization",
    }:
        raise ValueError("Objective Support lacks explicit three-way partitions")
    record_sets = [set(value["record_ids"]) for value in partitions.values()]
    if any(
        left & right for index, left in enumerate(record_sets) for right in record_sets[index + 1 :]
    ):
        raise ValueError("Objective Support record partitions overlap")
    if plan.get("numeric_contract_hash") != EXPECTED_OLD_NUMERIC_CONTRACT_HASH:
        raise ValueError("Objective Support source numeric profile differs")
    return plan, report


def _model_contract(path: Path, *, temperature: float) -> dict[str, Any]:
    config = _load_model_config(path, temperature=temperature)
    if config.provider != "deepseek" or config.fallback_models:
        raise ValueError("sealed Agent requires the frozen DeepSeek route without fallback")
    return {
        "config_path": str(path),
        "config_sha256": _sha256(path),
        "public_manifest_hash": config.public_manifest_hash,
        "provider": config.provider,
        "endpoint": config.endpoint,
        "models_endpoint": config.models_endpoint,
        "requested_model": config.model,
        "temperature": temperature,
        "max_output_tokens": config.max_output_tokens,
        "maximum_model_attempts": config.maximum_model_attempts,
        "contract_repair_attempts": config.contract_repair_attempts,
        "auto_discover_models": config.auto_discover_models,
        "require_requested_model": config.require_requested_model,
        "interaction_protocol": config.interaction_protocol,
    }


def prepare(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and (output_dir / "plan.json").exists():
        raise ValueError("sealed candidate plan is immutable and already exists")
    artifacts_path = Path(args.artifacts_path).resolve()
    root_dir = Path(args.root_run_dir).resolve()
    contract_path = Path(args.numeric_contract_path).resolve()
    population_path = Path(args.population_report_path).resolve()
    support_dir = Path(args.source_support_dir).resolve()
    model_config_path = Path(args.model_config_path).resolve()
    archive_config_path = Path(args.archive_config_path).resolve()
    initial_output_dir = Path(args.initial_output_dir).resolve()
    realization_output_dir = Path(args.realization_output_dir).resolve()
    source_output_dir = Path(args.source_output_dir).resolve()
    for path in (initial_output_dir, realization_output_dir, source_output_dir):
        _require_absent_or_empty(path)
    contract, root_plan, selection = _load_frozen_contract(
        contract_path,
        root_dir=root_dir,
    )
    population, partition, task_ids = _load_population(
        population_path,
        artifacts_path=artifacts_path,
    )
    support_plan, support_report = _load_support(
        support_dir,
        artifacts_path=artifacts_path,
    )
    initial_model = _model_contract(model_config_path, temperature=INITIAL_TEMPERATURE)
    realization_model = _model_contract(
        model_config_path,
        temperature=REALIZATION_TEMPERATURE,
    )
    plan: dict[str, Any] = {
        "sealed_version": SEALED_VERSION,
        "run_role": "independent_sealed_candidate",
        "implementation_sha256": _implementation_sha256(),
        "root_run_dir": str(root_dir),
        "root_plan_path": str(root_dir / "plan.json"),
        "root_plan_sha256": _sha256(root_dir / "plan.json"),
        "root_plan_hash": root_plan["plan_hash"],
        "root_implementation_manifest_hash": root_plan["implementation_manifest_hash"],
        "root_selection_path": str(root_dir / "selection.json"),
        "root_selection_sha256": _sha256(root_dir / "selection.json"),
        "root_selection_hash": selection["selection_hash"],
        "numeric_contract_path": str(contract_path),
        "numeric_contract_sha256": _sha256(contract_path),
        "numeric_contract": contract,
        "numeric_contract_hash": contract["contract_hash"],
        "selected_profile": contract["selected_profile"],
        "selected_profile_id": EXPECTED_PROFILE_ID,
        "resource_contract": root.PROFILE_RESOURCE_CONTRACTS[EXPECTED_PROFILE_ID],
        "fixed_numeric_thresholds": contract["fixed_numeric_thresholds"],
        "pairwise_uncertainty_envelope": contract["pairwise_uncertainty_envelope"],
        "population_report_path": str(population_path),
        "population_report_sha256": _sha256(population_path),
        "population_report_hash": population["report_hash"],
        "sealed_partition": partition,
        "artifacts_path": str(artifacts_path),
        "artifacts_sha256": _sha256(artifacts_path),
        "task_set_id": EXPECTED_TASK_SET_ID,
        "task_ids": task_ids,
        "task_count": EXPECTED_TASK_COUNT,
        "state_count": EXPECTED_STATE_COUNT,
        "source_support_dir": str(support_dir),
        "source_support_plan_path": str(support_dir / "plan.json"),
        "source_support_plan_sha256": _sha256(support_dir / "plan.json"),
        "source_support_plan_hash": support_plan["plan_hash"],
        "source_support_report_path": str(support_dir / "beneficiary_evaluation_report.json"),
        "source_support_report_sha256": _sha256(support_dir / "beneficiary_evaluation_report.json"),
        "source_support_report_hash": support_report["report_hash"],
        "source_numeric_contract_hash": support_plan["numeric_contract_hash"],
        "archive_config_path": str(archive_config_path),
        "archive_config_sha256": _sha256(archive_config_path),
        "api_contract": {
            "initial_distribution": initial_model,
            "state_realizations": realization_model,
            "credential_storage": "environment_only_not_hashed_or_serialized",
        },
        "initial_distribution_contract": {
            "output_dir": str(initial_output_dir),
            "replicas_per_task": INITIAL_REPLICAS_PER_TASK,
            "prior_strength": 1.0,
            "workers": int(args.initial_workers),
            "seed": INITIAL_SEED,
            "sampling_salt": INITIAL_SAMPLING_SALT,
        },
        "state_realization_contract": {
            "output_dir": str(realization_output_dir),
            "minimum_realizations_per_state": REALIZATIONS_PER_STATE,
            "maximum_realizations_per_state": REALIZATIONS_PER_STATE,
            "maximum_attempt_multiplier": 3,
            "workers": int(args.realization_workers),
            "seed": REALIZATION_SEED,
            "beneficiary_model_state_id": support_plan["beneficiary_model_state_id"],
            "final_student_model_id": "qwen2_5_7b_vtdo_student.fresh_training",
        },
        "gradient_source_contract": {
            "output_dir": str(source_output_dir),
            "task_sampling_salt": GRADIENT_SAMPLING_SALT,
            "task_count": EXPECTED_TASK_COUNT,
            "run_role": "smoke",
            "numeric_seed": GRADIENT_SEED,
            "local_learning_rate": 2e-4,
            "optimizer_epsilon": 1e-8,
            "maximum_gradient_norm": 1.0,
            "uncertainty_penalty_coefficient": 1.0,
            "objective_split": "authorization",
        },
        "claim_boundary": (
            "This one-shot inherited sealed run tests only the v17 numerical contract. "
            "It cannot authorize Contribution, GP-C, VTDO updates, or production synthesis."
        ),
        "production_effect": "none_until_sealed_result_passes",
        "sealed_outcomes_observed": False,
    }
    plan["plan_hash"] = canonical_hash(
        plan,
        prefix="finance_gradient_numeric_sealed_plan:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "plan.json", plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


def _verify_plan(plan: dict[str, Any]) -> None:
    if plan.get("sealed_version") != SEALED_VERSION:
        raise ValueError("sealed candidate plan version differs")
    if plan.get("run_role") != "independent_sealed_candidate":
        raise ValueError("sealed candidate run role differs")
    if plan.get("implementation_sha256") != _implementation_sha256():
        raise ValueError("sealed candidate implementation changed after planning")
    _replay_hash(
        plan,
        field="plan_hash",
        prefix="finance_gradient_numeric_sealed_plan:",
    )
    immutable_paths = (
        ("root_plan_path", "root_plan_sha256"),
        ("root_selection_path", "root_selection_sha256"),
        ("numeric_contract_path", "numeric_contract_sha256"),
        ("population_report_path", "population_report_sha256"),
        ("artifacts_path", "artifacts_sha256"),
        ("source_support_plan_path", "source_support_plan_sha256"),
        ("source_support_report_path", "source_support_report_sha256"),
        ("archive_config_path", "archive_config_sha256"),
    )
    for path_field, sha_field in immutable_paths:
        if _sha256(Path(str(plan[path_field]))) != plan[sha_field]:
            raise ValueError(f"sealed candidate immutable input changed:{path_field}")
    config = plan["api_contract"]["initial_distribution"]
    if _sha256(Path(str(config["config_path"]))) != config["config_sha256"]:
        raise ValueError("sealed candidate API config changed")
    contract, root_plan, selection = _load_frozen_contract(
        Path(str(plan["numeric_contract_path"])),
        root_dir=Path(str(plan["root_run_dir"])),
    )
    if (
        contract != plan["numeric_contract"]
        or root_plan["plan_hash"] != plan["root_plan_hash"]
        or selection["selection_hash"] != plan["root_selection_hash"]
    ):
        raise ValueError("sealed candidate frozen contract lineage differs")
    _, partition, task_ids = _load_population(
        Path(str(plan["population_report_path"])),
        artifacts_path=Path(str(plan["artifacts_path"])),
    )
    if partition != plan["sealed_partition"] or task_ids != tuple(plan["task_ids"]):
        raise ValueError("sealed candidate partition lineage differs")
    support_plan, support_report = _load_support(
        Path(str(plan["source_support_dir"])),
        artifacts_path=Path(str(plan["artifacts_path"])),
    )
    if (
        support_plan["plan_hash"] != plan["source_support_plan_hash"]
        or support_report["report_hash"] != plan["source_support_report_hash"]
    ):
        raise ValueError("sealed candidate Objective Support lineage differs")


def _load_initial_report(plan: dict[str, Any]) -> tuple[FinanceInitialDistributionReport, Path]:
    contract = plan["initial_distribution_contract"]
    output_dir = Path(str(contract["output_dir"]))
    report_path = output_dir / "finance_initial_distribution_report.json"
    report = FinanceInitialDistributionReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    distributions_path = output_dir / "initial_distributions.jsonl"
    if report.status != "passed":
        raise ValueError("sealed initial distribution did not pass")
    if tuple(sorted(report.selected_task_ids)) != tuple(plan["task_ids"]):
        raise ValueError("sealed initial distribution task set differs")
    if report.artifact_sha256 != plan["artifacts_sha256"]:
        raise ValueError("sealed initial distribution uses another Artifact")
    if (
        report.model_config_hash
        != plan["api_contract"]["initial_distribution"]["public_manifest_hash"]
    ):
        raise ValueError("sealed initial distribution model contract differs")
    if (
        report.replicas_per_task != INITIAL_REPLICAS_PER_TASK
        or report.seed != INITIAL_SEED
        or report.sampling_salt != INITIAL_SAMPLING_SALT
        or report.requested_trajectory_count != EXPECTED_TASK_COUNT * INITIAL_REPLICAS_PER_TASK
        or report.valid_catalog_observation_counts
        != {task_id: INITIAL_REPLICAS_PER_TASK for task_id in report.selected_task_ids}
        or report.off_catalog_valid_count != 0
        or report.distribution_sha256 != _sha256(distributions_path)
    ):
        raise ValueError("sealed initial distribution completeness contract failed")
    return report, distributions_path


def _load_realization_report(
    plan: dict[str, Any],
    *,
    initial_report: FinanceInitialDistributionReport,
    distributions_path: Path,
) -> tuple[FinanceStateRealizationReport, Path, str]:
    output_dir = Path(str(plan["state_realization_contract"]["output_dir"]))
    report_path = output_dir / "finance_state_realization_report.json"
    realizations_path = output_dir / "gradient_state_realizations.jsonl"
    report = FinanceStateRealizationReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    if report.status != "passed":
        raise ValueError("sealed state realizations did not pass")
    expected_counts = {
        task_id: {state_id: REALIZATIONS_PER_STATE for state_id in states}
        for task_id, states in report.requested_counts_by_task.items()
    }
    lineage_mode = _initial_report_lineage_mode(
        current_report_id=initial_report.report_id,
        current_report_sha256=_sha256(
            Path(str(plan["initial_distribution_contract"]["output_dir"]))
            / "finance_initial_distribution_report.json"
        ),
        referenced_report_id=report.initial_distribution_report_id,
        referenced_report_sha256=report.initial_distribution_report_sha256,
    )
    if (
        report.artifact_sha256 != plan["artifacts_sha256"]
        or report.distribution_sha256 != _sha256(distributions_path)
        or report.model_config_hash
        != plan["api_contract"]["state_realizations"]["public_manifest_hash"]
        or report.task_count != EXPECTED_TASK_COUNT
        or report.state_count != EXPECTED_STATE_COUNT
        or report.requested_realization_count != EXPECTED_STATE_COUNT * REALIZATIONS_PER_STATE
        or report.released_realization_count != EXPECTED_STATE_COUNT * REALIZATIONS_PER_STATE
        or report.requested_counts_by_task != expected_counts
        or report.released_counts_by_task != expected_counts
        or report.unique_trajectory_hash_count != report.released_realization_count
        or report.realizations_sha256 != _sha256(realizations_path)
    ):
        raise ValueError("sealed state realization completeness contract failed")
    return report, realizations_path, lineage_mode


def _initial_report_lineage_mode(
    *,
    current_report_id: str,
    current_report_sha256: str,
    referenced_report_id: str,
    referenced_report_sha256: str,
) -> str:
    id_equal = current_report_id == referenced_report_id
    sha_equal = current_report_sha256 == referenced_report_sha256
    if id_equal != sha_equal:
        raise ValueError("initial report ID and content hash disagree")
    if id_equal:
        return "exact_report_snapshot"
    # Report IDs include resume telemetry, while state realization depends on the
    # separately hashed Artifact and conditional distribution.  Both scientific
    # identities are checked by the caller before this supersession is accepted.
    return "distribution_equivalent_superseded_report_snapshot"


def build_authorization_gradient(args: argparse.Namespace) -> None:
    raise RuntimeError(
        "The archived v18 authorization-gradient runner is retired; use the v19 "
        "sealed causal pilot and its frozen FP32 execution contract."
    )
    import torch
    from safetensors.torch import save_file

    output_dir = Path(args.output_dir).resolve()
    sealed_plan = _read_json(output_dir / "plan.json")
    _verify_plan(sealed_plan)
    initial_report, distributions_path = _load_initial_report(sealed_plan)
    realization_report, realizations_path, _ = _load_realization_report(
        sealed_plan,
        initial_report=initial_report,
        distributions_path=distributions_path,
    )
    source_dir = Path(str(sealed_plan["gradient_source_contract"]["output_dir"]))
    source_plan = _read_json(source_dir / "plan.json")
    manifest_path = source_dir / "evaluation_gradient_manifest.json"
    if manifest_path.exists():
        raise ValueError("sealed authorization gradient manifest is immutable and exists")
    if source_plan.get("experiment_version") != gradient.GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("sealed source gradient implementation differs")
    if source_plan.get("run_role") != "smoke":
        raise ValueError("sealed source uses an unexpected run role")
    if Path(str(source_plan["artifacts_path"])).resolve() != Path(
        str(sealed_plan["artifacts_path"])
    ):
        raise ValueError("sealed gradient source uses another Artifact")
    if source_plan.get("source_support_plan_hash") != sealed_plan["source_support_plan_hash"]:
        raise ValueError("sealed gradient source uses another Objective Support")
    if source_plan.get("numeric_contract_hash") != EXPECTED_OLD_NUMERIC_CONTRACT_HASH:
        raise ValueError("sealed objective gradient numeric source differs")
    if source_plan.get("current_distributions_sha256") != _sha256(distributions_path):
        raise ValueError("sealed gradient source uses another distribution")
    realization_manifest = source_plan.get("state_realization_manifest", {})
    if (
        realization_manifest.get("source_sha256") != _sha256(realizations_path)
        or realization_manifest.get("source_report_id") != realization_report.report_id
        or realization_manifest.get("all_fresh_independently_verified") is not True
    ):
        raise ValueError("sealed gradient source realization lineage differs")
    gpu_ids = tuple(int(value) for value in args.gpu_ids)
    if not gpu_ids or len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError("authorization gradient GPU ids are empty or duplicate")
    if any(value < 0 or value >= torch.cuda.device_count() for value in gpu_ids):
        raise ValueError("authorization gradient GPU id is not visible")
    torch.cuda.set_device(gpu_ids[0])
    gradient._seed_everything(GRADIENT_SEED)
    gradient._configure_numeric_policy(gradient.CALIBRATED_NUMERIC_PROFILE)
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    tokenizer = gradient._load_tokenizer(Path(str(source_plan["model_dir"])))
    model = (
        gradient._sharded_baseline_lora_model(
            Path(str(source_plan["model_dir"])),
            Path(str(source_plan["beneficiary_adapter_dir"])),
            device_ids=gpu_ids,
        )
        if len(gpu_ids) > 1
        else gradient._baseline_lora_model(
            Path(str(source_plan["model_dir"])),
            Path(str(source_plan["beneficiary_adapter_dir"])),
        )
    )
    if gradient._adapter_tensor_sha256(model) != source_plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("sealed authorization gradient loaded another Adapter")
    parameter_manifest, parameter_manifest_hash = gradient._gradient_parameter_manifest(model)
    gradient._assert_trainable_parameter_precision(parameter_manifest)
    support_plan = _read_json(Path(str(sealed_plan["source_support_plan_path"])))
    source_records = gradient._load_records(Path(str(support_plan["records_path"])))
    record_ids = tuple(
        str(value) for value in support_plan["objective_partitions"]["authorization"]["record_ids"]
    )
    gradient_dir = source_dir / "evaluation_gradients"
    gradient_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    gradients: list[dict[str, Any]] = []
    weights: list[float] = []
    started = time.monotonic()
    for index, record_id in enumerate(record_ids):
        value, loss, supervised_tokens = gradient._record_gradient(
            model,
            tokenizer,
            source_records[record_id],
            mode="objective_eval",
        )
        path = gradient_dir / f"authorization_record_{index:02d}.safetensors"
        save_file(value, path)
        gradients.append(value)
        weights.append(float(supervised_tokens))
        rows.append(
            {
                "record_id": record_id,
                "file": str(path),
                "sha256": _sha256(path),
                "loss": loss,
                "supervised_tokens": supervised_tokens,
                "gradient_norm": gradient._gradient_norm(value),
            }
        )
    aggregate = gradient._weighted_gradient(gradients, weights)
    aggregate_path = gradient_dir / "authorization_aggregate.safetensors"
    save_file(aggregate, aggregate_path)
    peak_memory = {str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids}
    manifest: dict[str, Any] = {
        "experiment_version": gradient.GRADIENT_ALIGNMENT_VERSION,
        "plan_hash": source_plan["plan_hash"],
        "beneficiary_checkpoint_hash": source_plan["beneficiary_checkpoint_hash"],
        "beneficiary_adapter_tensor_sha256": source_plan["beneficiary_adapter_tensor_sha256"],
        "gradient_parameter_space": source_plan["gradient_parameter_space"],
        "gradient_mode_contract": source_plan["gradient_mode_contract"],
        "gradient_mode_contract_id": source_plan["gradient_mode_contract_id"],
        "numeric_contract_hash": source_plan["numeric_contract_hash"],
        "numeric_profile": source_plan["numeric_contract"]["selected_profile"],
        "objective_gradient_mode": source_plan["gradient_mode_contract"]["objective_gradient_mode"],
        "objective_gradient_evaluation_point": "beneficiary_before_global_pi_update",
        "objective_gradient_role": "sealed_candidate_untouched_authorization",
        "parameter_manifest": parameter_manifest,
        "parameter_manifest_hash": parameter_manifest_hash,
        "record_gradients": rows,
        "aggregate_gradients": [
            {
                "split": "authorization",
                "record_ids": record_ids,
                "weights": weights,
                "file": str(aggregate_path),
                "sha256": _sha256(aggregate_path),
                "gradient_norm": gradient._gradient_norm(aggregate),
            }
        ],
        "source_support_plan_hash": support_plan["plan_hash"],
        "sealed_numeric_contract_hash": sealed_plan["numeric_contract_hash"],
        "numeric_seed": GRADIENT_SEED,
        "runtime_seconds": time.monotonic() - started,
        "requested_cuda_device_ids": gpu_ids,
        "cuda_visible_devices_env": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "peak_gpu_memory_bytes_by_requested_device": peak_memory,
        "torch_version": torch.__version__,
        "claim_boundary": (
            "Authorization objective is held out from v17 development and validation."
        ),
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix="finance_contribution_evaluation_gradient_manifest:",
    )
    _write_json(manifest_path, manifest)
    del model, gradients, aggregate
    gc.collect()
    torch.cuda.empty_cache()
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


def freeze_source(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    source_manifest_path = output_dir / "source_manifest.json"
    if source_manifest_path.exists():
        raise ValueError("sealed source manifest is immutable and exists")
    initial_report, distributions_path = _load_initial_report(plan)
    realization_report, realizations_path, initial_report_lineage_mode = _load_realization_report(
        plan,
        initial_report=initial_report,
        distributions_path=distributions_path,
    )
    source_dir = Path(str(plan["gradient_source_contract"]["output_dir"]))
    source_plan_path = source_dir / "plan.json"
    gradient_manifest_path = source_dir / "evaluation_gradient_manifest.json"
    source_plan = _read_json(source_plan_path)
    gradient_manifest = _read_json(gradient_manifest_path)
    source_plan_hash = _replay_hash(
        source_plan,
        field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
    )
    gradient_manifest_hash = _replay_hash(
        gradient_manifest,
        field="manifest_hash",
        prefix="finance_contribution_evaluation_gradient_manifest:",
    )
    if gradient_manifest.get("plan_hash") != source_plan_hash:
        raise ValueError("sealed authorization gradient crosses source plans")
    if source_plan.get("selected_task_ids") != list(plan["task_ids"]):
        if set(source_plan.get("selected_task_ids", ())) != set(plan["task_ids"]):
            raise ValueError("sealed gradient source task set differs")
    jobs = tuple(source_plan.get("jobs", ()))
    if (
        len(jobs) != EXPECTED_STATE_COUNT * REALIZATIONS_PER_STATE
        or len({str(row["record_id"]) for row in jobs}) != len(jobs)
        or {str(row["task_id"]) for row in jobs} != set(plan["task_ids"])
        or any(row.get("realization_role") != "fresh_independently_verified" for row in jobs)
    ):
        raise ValueError("sealed gradient source job matrix is incomplete")
    counts = Counter((str(row["task_id"]), str(row["state_id"])) for row in jobs)
    if set(counts.values()) != {REALIZATIONS_PER_STATE} or len(counts) != EXPECTED_STATE_COUNT:
        raise ValueError("sealed gradient source per-state realization count differs")
    if source_plan.get("state_realization_count") != len(jobs):
        raise ValueError("sealed gradient source realization accounting differs")
    if (
        source_plan.get("state_realization_manifest", {}).get("source_report_id")
        != realization_report.report_id
    ):
        raise ValueError("sealed gradient source report lineage differs")
    if source_plan.get("current_distributions_sha256") != _sha256(distributions_path):
        raise ValueError("sealed gradient source distribution lineage differs")
    target_records_path = Path(str(source_plan["target_records_path"]))
    if _sha256(target_records_path) != source_plan["target_records_sha256"]:
        raise ValueError("sealed gradient source target records changed")
    token_regions = source_plan.get("token_region_decomposition", {}).get("records", {})
    if set(token_regions) != {str(row["record_id"]) for row in jobs}:
        raise ValueError("sealed gradient source token regions are incomplete")
    aggregates = [
        row
        for row in gradient_manifest.get("aggregate_gradients", ())
        if row.get("split") == "authorization"
    ]
    if len(aggregates) != 1:
        raise ValueError("sealed authorization objective aggregate is not unique")
    objective = aggregates[0]
    support_plan = _read_json(Path(str(plan["source_support_plan_path"])))
    expected_objective_ids = tuple(
        str(value) for value in support_plan["objective_partitions"]["authorization"]["record_ids"]
    )
    if tuple(objective["record_ids"]) != expected_objective_ids:
        raise ValueError("sealed authorization objective record set differs")
    source_descriptor = {
        "source_run_dir": str(source_dir),
        "plan_path": str(source_plan_path),
        "plan_sha256": _sha256(source_plan_path),
        "plan_hash": source_plan_hash,
        "manifest_path": str(gradient_manifest_path),
        "manifest_sha256": _sha256(gradient_manifest_path),
        "manifest_hash": gradient_manifest_hash,
        "model_dir": source_plan["model_dir"],
        "beneficiary_adapter_dir": source_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": source_plan["beneficiary_adapter_tensor_sha256"],
        "target_records_path": str(target_records_path),
        "target_records_sha256": source_plan["target_records_sha256"],
        "token_region_manifest_hash": source_plan["token_region_decomposition"]["manifest_hash"],
        "token_regions": token_regions,
        "task_distributions": source_plan["task_distributions"],
        "jobs": jobs,
        "objective_split": "authorization",
        "objective_record_ids": expected_objective_ids,
        "objective_record_set_id": canonical_hash(
            tuple(sorted(expected_objective_ids)),
            prefix="finance_gradient_numeric_objective_record_set:",
        ),
    }
    source_descriptor = root._diagnostic_source_descriptor(source_descriptor)
    source: dict[str, Any] = {
        "source_version": SEALED_SOURCE_VERSION,
        "sealed_plan_hash": plan["plan_hash"],
        "initial_report_path": str(
            Path(str(plan["initial_distribution_contract"]["output_dir"]))
            / "finance_initial_distribution_report.json"
        ),
        "initial_report_sha256": _sha256(
            Path(str(plan["initial_distribution_contract"]["output_dir"]))
            / "finance_initial_distribution_report.json"
        ),
        "initial_report_id": initial_report.report_id,
        "state_referenced_initial_report_id": (realization_report.initial_distribution_report_id),
        "state_referenced_initial_report_sha256": (
            realization_report.initial_distribution_report_sha256
        ),
        "initial_report_lineage_mode": initial_report_lineage_mode,
        "distribution_path": str(distributions_path),
        "distribution_sha256": _sha256(distributions_path),
        "realization_report_path": str(
            Path(str(plan["state_realization_contract"]["output_dir"]))
            / "finance_state_realization_report.json"
        ),
        "realization_report_sha256": _sha256(
            Path(str(plan["state_realization_contract"]["output_dir"]))
            / "finance_state_realization_report.json"
        ),
        "realization_report_id": realization_report.report_id,
        "realizations_path": str(realizations_path),
        "realizations_sha256": _sha256(realizations_path),
        "source": source_descriptor,
        "full_job_count": len(jobs),
        "diagnostic_job_count": len(source_descriptor["jobs"]),
        "task_count": EXPECTED_TASK_COUNT,
        "state_count": EXPECTED_STATE_COUNT,
        "realizations_per_state": REALIZATIONS_PER_STATE,
        "api_failure_counts": {
            "initial": initial_report.failure_counts,
            "state": realization_report.generation_failure_counts,
        },
        "claim_boundary": "Inputs are frozen before the sealed numeric result is observed.",
    }
    source["source_hash"] = canonical_hash(
        source,
        prefix="finance_gradient_numeric_sealed_source:",
    )
    _write_json(source_manifest_path, source)
    print(json.dumps(source, ensure_ascii=False, indent=2, sort_keys=True))


def _load_source(plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    value = _read_json(output_dir / "source_manifest.json")
    if value.get("source_version") != SEALED_SOURCE_VERSION:
        raise ValueError("sealed source version differs")
    _replay_hash(
        value,
        field="source_hash",
        prefix="finance_gradient_numeric_sealed_source:",
    )
    if value.get("sealed_plan_hash") != plan["plan_hash"]:
        raise ValueError("sealed source crosses plans")
    for path_field, sha_field in (
        ("initial_report_path", "initial_report_sha256"),
        ("distribution_path", "distribution_sha256"),
        ("realization_report_path", "realization_report_sha256"),
        ("realizations_path", "realizations_sha256"),
    ):
        if _sha256(Path(str(value[path_field]))) != value[sha_field]:
            raise ValueError(f"sealed source input changed:{path_field}")
    source = value["source"]
    for path_field, sha_field in (
        ("plan_path", "plan_sha256"),
        ("manifest_path", "manifest_sha256"),
        ("target_records_path", "target_records_sha256"),
    ):
        if _sha256(Path(str(source[path_field]))) != source[sha_field]:
            raise ValueError(f"sealed gradient source changed:{path_field}")
    root._verify_diagnostic_source(source)
    return value


def _checkpoint_path(output_dir: Path, job_id: str) -> Path:
    digest = hashlib.sha256(job_id.encode("utf-8")).hexdigest()
    return output_dir / "checkpoints" / f"{digest}.json"


def _load_checkpoints(
    output_dir: Path,
    *,
    plan: dict[str, Any],
    source_manifest: dict[str, Any],
    profile: root.RootCauseProfile,
) -> dict[str, dict[str, Any]]:
    source = source_manifest["source"]
    jobs = {str(row["job_id"]): row for row in source["jobs"]}
    values: dict[str, dict[str, Any]] = {}
    checkpoint_dir = output_dir / "checkpoints"
    if not checkpoint_dir.is_dir():
        return values
    for path in sorted(checkpoint_dir.glob("*.json")):
        checkpoint = _read_json(path)
        _replay_hash(
            checkpoint,
            field="checkpoint_hash",
            prefix="finance_gradient_numeric_sealed_checkpoint:",
        )
        job = checkpoint.get("job")
        if not isinstance(job, dict) or str(job.get("job_id")) not in jobs:
            raise ValueError("sealed checkpoint references an unknown job")
        job_id = str(job["job_id"])
        expected = {
            "checkpoint_version": SEALED_CHECKPOINT_VERSION,
            "sealed_plan_hash": plan["plan_hash"],
            "source_hash": source_manifest["source_hash"],
            "profile": root.asdict(profile),
            "job": jobs[job_id],
        }
        if any(checkpoint.get(key) != value for key, value in expected.items()):
            raise ValueError("sealed checkpoint identity differs")
        if path != _checkpoint_path(output_dir, job_id) or job_id in values:
            raise ValueError("sealed checkpoint path or identity is duplicated")
        values[job_id] = checkpoint
    return values


def _build_checkpoint(
    *,
    plan: dict[str, Any],
    source: dict[str, Any],
    profile: root.RootCauseProfile,
    job: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "checkpoint_version": SEALED_CHECKPOINT_VERSION,
        "sealed_plan_hash": plan["plan_hash"],
        "source_hash": source["source_hash"],
        "profile": root.asdict(profile),
        "job": job,
        "row": row,
    }
    value["checkpoint_hash"] = canonical_hash(
        value,
        prefix="finance_gradient_numeric_sealed_checkpoint:",
    )
    return value


def run(args: argparse.Namespace) -> None:
    import torch

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    source_manifest = _load_source(plan, output_dir)
    source = source_manifest["source"]
    result_path = output_dir / "result.json"
    if result_path.exists():
        raise ValueError("sealed candidate result is immutable and already exists")
    profile = root._profile(EXPECTED_PROFILE_ID)
    gpu_ids = tuple(int(value) for value in args.gpu_ids)
    if any(value < 0 or value >= torch.cuda.device_count() for value in gpu_ids):
        raise ValueError("sealed candidate GPU id is not visible")
    torch.cuda.set_device(gpu_ids[0])
    snapshot = root._gpu_memory_snapshot(torch, gpu_ids)
    resource_contract = root._verify_resource_contract(profile, gpu_ids, snapshot)
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    root._seed_everything(GRADIENT_SEED)
    root._configure_numeric_policy(profile.precision)
    result: dict[str, Any] = {
        "sealed_version": SEALED_VERSION,
        "sealed_plan_hash": plan["plan_hash"],
        "source_hash": source_manifest["source_hash"],
        "numeric_contract_hash": plan["numeric_contract_hash"],
        "profile": root.asdict(profile),
        "profile_algorithm_contract": profile.algorithm_contract,
        "applied_uncertainty_envelope": plan["pairwise_uncertainty_envelope"],
        "requested_cuda_device_ids": gpu_ids,
        "resource_contract": resource_contract,
        "preflight_gpu_memory": snapshot,
        "cuda_visible_devices_env": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    model: Any | None = None
    started = time.monotonic()
    try:
        tokenizer = root._load_tokenizer(Path(str(source["model_dir"])))
        model, device_map = root._load_calibration_model(
            model_dir=Path(str(source["model_dir"])),
            adapter_dir=Path(str(source["beneficiary_adapter_dir"])),
            profile=profile.precision,
            gpu_ids=gpu_ids,
        )
        if root._adapter_tensor_sha256(model) != source["beneficiary_adapter_tensor_sha256"]:
            raise ValueError("sealed candidate loaded another beneficiary Adapter")
        source_gradient_manifest = _read_json(Path(str(source["manifest_path"])))
        parameter_manifest, parameter_manifest_hash = root._gradient_parameter_manifest(model)
        if (
            parameter_manifest != source_gradient_manifest["parameter_manifest"]
            or parameter_manifest_hash != source_gradient_manifest["parameter_manifest_hash"]
        ):
            raise ValueError("sealed candidate parameter space differs")
        _, objective_gradients = root._load_gradient_artifacts(source_gradient_manifest)
        objective = objective_gradients["authorization"]
        objective_norm = root._gradient_norm(objective)
        records = root._load_records(Path(str(source["target_records_path"])))
        checkpoints = _load_checkpoints(
            output_dir,
            plan=plan,
            source_manifest=source_manifest,
            profile=profile,
        )
        completed_before_resume = len(checkpoints)
        for job in source["jobs"]:
            job_id = str(job["job_id"])
            if job_id in checkpoints:
                continue
            root._seed_everything(int(job["gradient_seed"]))
            root._configure_numeric_policy(profile.precision)
            regions = source["token_regions"][job["record_id"]]
            decomposition = root._root_cause_decomposition(
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
            _, full_score, _, _ = root._gradient_alignment(full, objective)
            _, recomposed_score, _, _ = root._gradient_alignment(recomposed, objective)
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
            checkpoint = _build_checkpoint(
                plan=plan,
                source=source_manifest,
                profile=profile,
                job=job,
                row=row,
            )
            checkpoint_path = _checkpoint_path(output_dir, job_id)
            if checkpoint_path.exists():
                raise ValueError("sealed checkpoint appeared concurrently")
            _write_json(checkpoint_path, checkpoint)
            checkpoints[job_id] = checkpoint
            del full, recomposed
        if len(checkpoints) != len(source["jobs"]):
            raise ValueError("sealed checkpoint matrix is incomplete")
        rows = [checkpoints[str(job["job_id"])]["row"] for job in source["jobs"]]
        summary = root._combined_summary(
            rows,
            task_distributions=source["task_distributions"],
            raw_thresholds=plan["fixed_numeric_thresholds"],
            uncertainty_envelope=float(plan["pairwise_uncertainty_envelope"]),
        )
        result.update(
            {
                "status": "completed",
                "rows": rows,
                "checkpoint_hashes": tuple(
                    str(checkpoints[str(job["job_id"])]["checkpoint_hash"])
                    for job in source["jobs"]
                ),
                "completed_before_resume": completed_before_resume,
                "completed_now": len(source["jobs"]) - completed_before_resume,
                "summary": summary,
                "resolved_hf_device_map": device_map,
                "resolved_hf_device_map_hash": canonical_hash(
                    device_map,
                    prefix="finance_gradient_numeric_sealed_device_map:",
                ),
                "trainable_parameter_manifest_hash": parameter_manifest_hash,
            }
        )
        model = None
        del objective_gradients, objective
    except torch.cuda.OutOfMemoryError as error:
        result.update(
            {
                "status": "resource_capacity_failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "failure_gpu_memory": root._gpu_memory_snapshot(torch, gpu_ids),
            }
        )
        model = None
    except Exception as error:
        result.update(
            {
                "status": "execution_failed",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        model = None
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
        prefix="finance_gradient_numeric_sealed_result:",
    )
    _write_json(result_path, result)
    assert model is None
    gc.collect()
    torch.cuda.empty_cache()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    source = _load_source(plan, output_dir)
    result = _read_json(output_dir / "result.json")
    _replay_hash(
        result,
        field="result_hash",
        prefix="finance_gradient_numeric_sealed_result:",
    )
    if (
        result.get("sealed_plan_hash") != plan["plan_hash"]
        or result.get("source_hash") != source["source_hash"]
        or result.get("numeric_contract_hash") != plan["numeric_contract_hash"]
        or result.get("profile", {}).get("profile_id") != EXPECTED_PROFILE_ID
    ):
        raise ValueError("sealed result lineage differs")
    passed = (
        result.get("status") == "completed" and result.get("summary", {}).get("status") == "passed"
    )
    report: dict[str, Any] = {
        "sealed_version": SEALED_VERSION,
        "sealed_plan_hash": plan["plan_hash"],
        "source_hash": source["source_hash"],
        "result_hash": result["result_hash"],
        "numeric_contract_hash": plan["numeric_contract_hash"],
        "task_set_id": plan["task_set_id"],
        "profile_id": EXPECTED_PROFILE_ID,
        "task_count": source["task_count"],
        "state_count": source["state_count"],
        "realization_count": source["full_job_count"],
        "evaluated_realization_count": source["diagnostic_job_count"],
        "api_failure_counts": source["api_failure_counts"],
        "numeric_summary": result.get("summary"),
        "status": "passed" if passed else "failed",
        "sealed_numeric_contract_passed": passed,
        "production_authorized": False,
        "contribution_authorized": False,
        "allowed_next_stage": (
            "preregister_contribution_authorization_experiment" if passed else None
        ),
        "failure_effect": (
            None if passed else "close_fp32_gradient_projection_route_without_posthoc_retuning"
        ),
        "claim_boundary": (
            "Passing authorizes only preregistration of a separate Contribution experiment. "
            "It is not evidence that Contribution estimates downstream utility."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_gradient_numeric_sealed_report:",
    )
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the inherited v17 sealed numeric candidate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--root-run-dir", required=True)
    prepare_parser.add_argument("--numeric-contract-path", required=True)
    prepare_parser.add_argument("--population-report-path", required=True)
    prepare_parser.add_argument("--artifacts-path", required=True)
    prepare_parser.add_argument("--source-support-dir", required=True)
    prepare_parser.add_argument("--model-config-path", required=True)
    prepare_parser.add_argument("--archive-config-path", required=True)
    prepare_parser.add_argument("--initial-output-dir", required=True)
    prepare_parser.add_argument("--realization-output-dir", required=True)
    prepare_parser.add_argument("--source-output-dir", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--initial-workers", type=int, default=6)
    prepare_parser.add_argument("--realization-workers", type=int, default=12)
    prepare_parser.set_defaults(handler=prepare)
    objective_parser = subparsers.add_parser("build-authorization-gradient")
    objective_parser.add_argument("--output-dir", required=True)
    objective_parser.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    objective_parser.set_defaults(handler=build_authorization_gradient)
    freeze_parser = subparsers.add_parser("freeze-source")
    freeze_parser.add_argument("--output-dir", required=True)
    freeze_parser.set_defaults(handler=freeze_source)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    run_parser.set_defaults(handler=run)
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--output-dir", required=True)
    aggregate_parser.set_defaults(handler=aggregate)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
