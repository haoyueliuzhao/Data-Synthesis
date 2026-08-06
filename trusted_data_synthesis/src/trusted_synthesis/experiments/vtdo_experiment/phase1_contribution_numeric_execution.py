from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.hashing import canonical_hash

EXECUTION_CONTRACT_VERSION = "finance_contribution_numeric_execution_contract.v19"
EXECUTION_CONTRACT_HASH_PREFIX = "finance_contribution_numeric_execution_contract:"
EXECUTION_PLAN_VERSION = "finance_contribution_gradient_projection.v15"
SEALED_CAUSAL_PILOT_ROLE = "sealed_causal_pilot"
EXPECTED_V18_PLAN_HASH = (
    "finance_gradient_numeric_sealed_plan:"
    "1084b81bc24f341aabced0fe0649913dc1163495736ed6461605fd5714850313"
)
EXPECTED_V18_RESULT_HASH = (
    "finance_gradient_numeric_sealed_result:"
    "ed13f8f07830ad47471293a8c73c22f464844959699b1b91d7c6cc99c94721d2"
)
EXPECTED_V18_REPORT_HASH = (
    "finance_gradient_numeric_sealed_report:"
    "2cdddbc561c67cbcca6728d2a1a54c6fa89a80c3b499f4e22d4097947a36c745"
)
EXPECTED_V18_NUMERIC_CONTRACT_HASH = (
    "finance_gradient_numeric_contract:"
    "e2a1c890af575f477389b0bfb1475810aeecec3e5f4bf3a6213c552a82fa86b7"
)
EXPECTED_TASK_SET_ID = (
    "finance_gradient_calibration_task_set:"
    "884e85bc9a8f531c8fe36aab2920dc0ff1432428b1c0efca61122b92767cf034"
)
EXPECTED_PROFILE = {
    "baseline_profile_id": "tf32_off_only",
    "factor_id": "activation_dtype",
    "intervention_count": 2,
    "precision": {
        "cuda_matmul_allow_tf32": False,
        "float32_matmul_precision": "highest",
        "gradient_checkpointing": True,
        "loss_accumulator_dtype": "float32",
        "model_dtype": "float32",
        "profile_id": "fp32_activation_strict",
        "sparse_projection_dtype": "model",
    },
    "profile_id": "fp32_activation_strict",
    "projection_execution_dtype": "bfloat16",
    "required_gpu_count": 3,
    "vjp_mode": "shared_retained_backward",
}

EXPECTED_PROFILE_ALGORITHM_CONTRACT = {
    "root_cause_version": "finance_gradient_numeric_root_cause.v3",
    "vjp_mode": "shared_retained_backward",
    "forward_graph_count_per_realization": 1,
    "cross_entropy_evaluation_count_per_realization": 1,
    "region_loss_policy": "slice_one_shared_per_token_cross_entropy_vector",
    "gradient_extraction": "tensor_backward",
    "functional_decoder_call": False,
    "saved_tensor_policy": "stride_preserving_pinned_cpu_roundtrip_synchronous_restore",
    "saved_tensor_restore_non_blocking": False,
    "model_input_device_policy": "input_embedding_weight_device",
    "sdpa_backend_policy": "torch_efficient_attention_for_all_cuda_profiles",
    "gqa_execution_policy": "explicit_repeat_kv_before_fused_sdpa",
    "projection_execution_dtype": "bfloat16",
    "effective_projection_dtype": "bfloat16",
    "precision": EXPECTED_PROFILE["precision"],
}

NUMERIC_THRESHOLDS = {
    "maximum_loss_identity_absolute_error": 1e-6,
    "minimum_gradient_recomposition_cosine": 0.99967,
    "maximum_gradient_recomposition_relative_error": 0.027,
    "maximum_gp_score_absolute_delta": 0.0023,
    "minimum_task_rank_agreement": 1.0,
    "maximum_update_total_variation": 0.00023,
    "maximum_update_jensen_shannon": 1e-6,
}
FINITE_TARGET_PROTOCOL = {
    "base_radius": 0.1,
    "radii": [0.1, 0.05, 0.025],
    "block_size": 7,
    "design_count": 2,
    "finite_difference": "symmetric_central",
    "extrapolation": "two_level_richardson_O_h4",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"v19 artifact is not a JSON object:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _replay_hash(
    value: Mapping[str, Any],
    *,
    field: str,
    prefix: str,
) -> str:
    payload = dict(value)
    observed = payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"v19 prerequisite failed identity replay:{field}")
    return str(observed)


def verify_execution_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(contract)
    observed = _replay_hash(
        frozen,
        field="contract_hash",
        prefix=EXECUTION_CONTRACT_HASH_PREFIX,
    )
    if frozen.get("contract_version") != EXECUTION_CONTRACT_VERSION:
        raise ValueError("Contribution execution contract version differs")
    if frozen.get("run_role") != SEALED_CAUSAL_PILOT_ROLE:
        raise ValueError("Contribution execution contract role differs")
    if frozen.get("selected_profile") != EXPECTED_PROFILE:
        raise ValueError("Contribution execution profile differs from v18")
    if frozen.get("numeric_thresholds") != NUMERIC_THRESHOLDS:
        raise ValueError("Contribution numeric thresholds differ from v18")
    if frozen.get("profile_algorithm_contract") != EXPECTED_PROFILE_ALGORITHM_CONTRACT:
        raise ValueError("Contribution execution algorithm differs from v18")
    if frozen.get("finite_target_protocol") != FINITE_TARGET_PROTOCOL:
        raise ValueError("Contribution finite-target protocol differs")
    if frozen.get("task_set_id") != EXPECTED_TASK_SET_ID:
        raise ValueError("Contribution pilot task set differs")
    task_ids = frozen.get("task_ids")
    if not isinstance(task_ids, list) or len(task_ids) != 6 or len(set(task_ids)) != 6:
        raise ValueError("Contribution pilot task identities differ")
    if frozen.get("task_count") != 6 or frozen.get("state_count") != 20:
        raise ValueError("Contribution pilot support differs")
    if frozen.get("state_realization_count") != 60:
        raise ValueError("Contribution pilot realization support differs")
    source_support = frozen.get("source_support")
    partitions = (
        source_support.get("objective_partition_ids") if isinstance(source_support, dict) else None
    )
    if not isinstance(partitions, dict) or set(partitions) != {
        "estimation",
        "validation",
        "authorization",
    }:
        raise ValueError("Contribution pilot objective partitions differ")
    partition_sets = []
    for role in ("estimation", "validation", "authorization"):
        values = partitions[role]
        if not isinstance(values, list) or len(values) != 4 or len(set(values)) != 4:
            raise ValueError("Contribution pilot objective partition support differs")
        partition_sets.append(set(values))
    if any(
        left & right
        for index, left in enumerate(partition_sets)
        for right in partition_sets[index + 1 :]
    ):
        raise ValueError("Contribution pilot objective partitions overlap")
    if frozen.get("allowed_objective_roles") != ["estimation", "validation"]:
        raise ValueError("Contribution pilot objective access differs")
    if frozen.get("authorization_objective_access") != "forbidden":
        raise ValueError("Contribution pilot must keep authorization sealed")
    if frozen.get("production_authorization_eligible") is not False:
        raise ValueError("Contribution pilot cannot be production eligible")
    if not observed:
        raise ValueError("Contribution execution contract has no identity")
    return frozen


def _verify_v18(v18_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _read_json(v18_dir / "plan.json")
    result = _read_json(v18_dir / "result.json")
    report = _read_json(v18_dir / "report.json")
    source = _read_json(v18_dir / "source_manifest.json")
    if plan.get("plan_hash") != EXPECTED_V18_PLAN_HASH:
        raise ValueError("v19 requires the frozen v18 plan")
    if result.get("result_hash") != EXPECTED_V18_RESULT_HASH:
        raise ValueError("v19 requires the frozen v18 result")
    if report.get("report_hash") != EXPECTED_V18_REPORT_HASH:
        raise ValueError("v19 requires the frozen v18 report")
    _replay_hash(
        report,
        field="report_hash",
        prefix="finance_gradient_numeric_sealed_report:",
    )
    _replay_hash(
        result,
        field="result_hash",
        prefix="finance_gradient_numeric_sealed_result:",
    )
    if (
        report.get("status") != "passed"
        or report.get("sealed_numeric_contract_passed") is not True
        or report.get("contribution_authorized") is not False
        or report.get("production_authorized") is not False
        or report.get("allowed_next_stage") != "preregister_contribution_authorization_experiment"
    ):
        raise ValueError("v18 did not authorize a preregistered successor experiment")
    if report.get("numeric_contract_hash") != EXPECTED_V18_NUMERIC_CONTRACT_HASH:
        raise ValueError("v18 numeric contract identity differs")
    if plan.get("selected_profile") != EXPECTED_PROFILE:
        raise ValueError("v18 selected profile differs")
    if result.get("profile_algorithm_contract") != EXPECTED_PROFILE_ALGORITHM_CONTRACT:
        raise ValueError("v18 execution algorithm differs")
    if source.get("source_hash") != report.get("source_hash"):
        raise ValueError("v18 source identity differs")
    if source.get("full_job_count") != 60 or source.get("diagnostic_job_count") != 20:
        raise ValueError("v18 source job support differs")
    source_payload = source.get("source")
    if not isinstance(source_payload, dict):
        raise ValueError("v18 source payload is missing")
    source_plan_path = Path(str(source_payload["plan_path"])).resolve()
    if _sha256(source_plan_path) != source_payload.get("plan_sha256"):
        raise ValueError("v18 source Gradient Projection plan changed")
    source_plan = _read_json(source_plan_path)
    _replay_hash(
        source_plan,
        field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
    )
    if source_plan.get("plan_hash") != source_payload.get("plan_hash"):
        raise ValueError("v18 source Gradient Projection identity differs")
    jobs = source_plan.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 60:
        raise ValueError("v18 source Gradient Projection matrix is incomplete")
    if len({str(row.get("job_id")) for row in jobs}) != 60:
        raise ValueError("v18 source Gradient Projection jobs are not unique")
    return {"plan": plan, "result": result, "report": report, "source": source}, source_plan


def issue_execution_contract(*, v18_dir: Path, output_path: Path) -> dict[str, Any]:
    v18, source_plan = _verify_v18(v18_dir)
    source = v18["source"]["source"]
    support_plan_path = Path(str(v18["plan"]["source_support_plan_path"])).resolve()
    support_report_path = Path(str(v18["plan"]["source_support_report_path"])).resolve()
    artifacts_path = Path(str(v18["plan"]["artifacts_path"])).resolve()
    distributions_path = Path(str(v18["source"]["distribution_path"])).resolve()
    realizations_path = Path(str(v18["source"]["realizations_path"])).resolve()
    realization_report_path = Path(str(v18["source"]["realization_report_path"])).resolve()
    target_records_path = Path(str(source["target_records_path"])).resolve()
    required_files = (
        support_plan_path,
        support_report_path,
        artifacts_path,
        distributions_path,
        realizations_path,
        realization_report_path,
        target_records_path,
    )
    if any(not path.is_file() for path in required_files):
        raise ValueError("v19 prerequisite file is missing")
    support_plan = _read_json(support_plan_path)
    support_report = _read_json(support_report_path)
    if support_report.get("status") != "passed" or support_report.get(
        "plan_hash"
    ) != support_plan.get("plan_hash"):
        raise ValueError("v19 Objective Support did not pass")
    partitions = support_plan.get("objective_partitions")
    if not isinstance(partitions, dict) or set(partitions) != {
        "estimation",
        "validation",
        "authorization",
    }:
        raise ValueError("v19 Objective Support lacks three frozen partitions")
    partition_ids = {
        role: tuple(str(value) for value in payload["record_ids"])
        for role, payload in partitions.items()
    }
    if any(len(values) != 4 for values in partition_ids.values()) or any(
        set(left) & set(right)
        for index, left in enumerate(partition_ids.values())
        for right in list(partition_ids.values())[index + 1 :]
    ):
        raise ValueError("v19 Objective Support partitions are not 4/4/4 disjoint")
    contract: dict[str, Any] = {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "run_role": SEALED_CAUSAL_PILOT_ROLE,
        "source_v18": {
            "directory": str(v18_dir),
            "plan_hash": v18["plan"]["plan_hash"],
            "result_hash": v18["result"]["result_hash"],
            "report_hash": v18["report"]["report_hash"],
            "source_hash": v18["source"]["source_hash"],
            "numeric_contract_hash": EXPECTED_V18_NUMERIC_CONTRACT_HASH,
        },
        "source_gradient_plan": {
            "path": str(source["plan_path"]),
            "sha256": source["plan_sha256"],
            "plan_hash": source_plan["plan_hash"],
            "source_numeric_contract_hash": source_plan["numeric_contract_hash"],
        },
        "source_support": {
            "plan_path": str(support_plan_path),
            "plan_sha256": _sha256(support_plan_path),
            "plan_hash": support_plan["plan_hash"],
            "report_path": str(support_report_path),
            "report_sha256": _sha256(support_report_path),
            "report_hash": support_report["report_hash"],
            "source_numeric_contract_hash": support_plan["numeric_contract_hash"],
            "objective_partition_ids": partition_ids,
        },
        "frozen_inputs": {
            "artifacts": {"path": str(artifacts_path), "sha256": _sha256(artifacts_path)},
            "distributions": {
                "path": str(distributions_path),
                "sha256": _sha256(distributions_path),
            },
            "state_realizations": {
                "path": str(realizations_path),
                "sha256": _sha256(realizations_path),
            },
            "state_realization_report": {
                "path": str(realization_report_path),
                "sha256": _sha256(realization_report_path),
            },
            "target_records": {
                "path": str(target_records_path),
                "sha256": _sha256(target_records_path),
            },
        },
        "selected_profile": EXPECTED_PROFILE,
        "profile_algorithm_contract": EXPECTED_PROFILE_ALGORITHM_CONTRACT,
        "numeric_thresholds": NUMERIC_THRESHOLDS,
        "finite_target_protocol": FINITE_TARGET_PROTOCOL,
        "task_set_id": EXPECTED_TASK_SET_ID,
        "task_ids": list(v18["plan"]["task_ids"]),
        "task_count": 6,
        "state_count": 20,
        "state_realization_count": 60,
        "allowed_objective_roles": ["estimation", "validation"],
        "authorization_objective_access": "forbidden",
        "production_authorization_eligible": False,
        "success_transition": "launch_fresh_30_task_independent_authorization_study",
        "failure_transition": "retain_contribution_zero_and_investigate_estimator_bias",
        "claim_boundary": (
            "This six-task sealed causal pilot tests whether the v18-certified numeric path "
            "restores GP-C rank and distribution fidelity. It cannot authorize production "
            "Contribution and cannot open the authorization objective partition."
        ),
    }
    contract["contract_hash"] = canonical_hash(
        contract,
        prefix=EXECUTION_CONTRACT_HASH_PREFIX,
    )
    verify_execution_contract(contract)
    if output_path.exists():
        raise ValueError("v19 execution contract is immutable and already exists")
    _write_json(output_path, contract)
    return contract


def rebase_gradient_plan(
    *,
    contract_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    contract = verify_execution_contract(_read_json(contract_path))
    source = contract["source_gradient_plan"]
    source_path = Path(str(source["path"])).resolve()
    if _sha256(source_path) != source["sha256"]:
        raise ValueError("v19 source Gradient Projection plan changed")
    source_plan = _read_json(source_path)
    _replay_hash(
        source_plan,
        field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
    )
    if source_plan["plan_hash"] != source["plan_hash"]:
        raise ValueError("v19 source Gradient Projection plan identity differs")
    if output_dir.exists() and (output_dir / "plan.json").exists():
        raise ValueError("v19 Gradient Projection plan is immutable and already exists")
    from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
        GRADIENT_MODE_CONTRACT,
    )

    plan = dict(source_plan)
    plan.pop("plan_hash", None)
    gradient_mode_contract = {
        **GRADIENT_MODE_CONTRACT,
        "numeric_profile": contract["selected_profile"],
        "numeric_contract_hash": contract["contract_hash"],
        "profile_algorithm_contract": contract["profile_algorithm_contract"],
    }
    plan.update(
        {
            "experiment_version": EXECUTION_PLAN_VERSION,
            "run_role": SEALED_CAUSAL_PILOT_ROLE,
            "numeric_contract_path": str(contract_path),
            "numeric_contract_sha256": _sha256(contract_path),
            "numeric_contract": contract,
            "numeric_contract_hash": contract["contract_hash"],
            "profile_algorithm_contract": contract["profile_algorithm_contract"],
            "gradient_mode_contract": gradient_mode_contract,
            "gradient_mode_contract_id": canonical_hash(
                gradient_mode_contract,
                prefix="finance_gradient_mode_contract:",
            ),
            "source_gradient_plan_path": str(source_path),
            "source_gradient_plan_sha256": source["sha256"],
            "source_gradient_plan_hash": source["plan_hash"],
            "source_numeric_contract_hash": source["source_numeric_contract_hash"],
            "production_authorization_eligible": False,
            "allowed_objective_roles": contract["allowed_objective_roles"],
            "claim_boundary": contract["claim_boundary"],
        }
    )
    plan["plan_hash"] = canonical_hash(
        plan,
        prefix="finance_contribution_gradient_plan:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "plan.json", plan)
    return plan


def _issue(args: argparse.Namespace) -> None:
    contract = issue_execution_contract(
        v18_dir=Path(args.v18_run_dir).resolve(),
        output_path=Path(args.output_path).resolve(),
    )
    print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))


def _rebase(args: argparse.Namespace) -> None:
    plan = rebase_gradient_plan(
        contract_path=Path(args.contract_path).resolve(),
        output_dir=Path(args.output_dir).resolve(),
    )
    summary = {
        "plan_hash": plan["plan_hash"],
        "run_role": plan["run_role"],
        "task_count": plan["task_count"],
        "state_count": plan["state_count"],
        "state_realization_count": plan["state_realization_count"],
        "numeric_contract_hash": plan["numeric_contract_hash"],
        "gradient_mode_contract_id": plan["gradient_mode_contract_id"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze the v19 FP32 Contribution execution contract"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    issue = subparsers.add_parser("issue-contract")
    issue.add_argument("--v18-run-dir", required=True)
    issue.add_argument("--output-path", required=True)
    issue.set_defaults(handler=_issue)
    rebase = subparsers.add_parser("rebase-gradient-plan")
    rebase.add_argument("--contract-path", required=True)
    rebase.add_argument("--output-dir", required=True)
    rebase.set_defaults(handler=_rebase)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
