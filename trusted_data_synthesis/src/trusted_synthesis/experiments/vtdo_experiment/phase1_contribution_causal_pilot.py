from __future__ import annotations

import argparse
import json
import math
import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.core.vtdo import make_contribution_rank_validation_evidence
from trusted_synthesis.experiments.vtdo_experiment.phase1_authorization_v2 import (
    CALIBRATION_FLOOR,
    DISTRIBUTION_THRESHOLDS,
    _distribution_metrics,
    _rank_metrics,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_numeric_execution import (
    SEALED_CAUSAL_PILOT_ROLE,
    verify_execution_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_finite_target import (
    FINITE_TARGET_VERSION,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
    GP_C_PROXY_VERSION,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _read_json,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

PILOT_GATE_VERSION = "finance_contribution_causal_pilot.v19"
PILOT_REPORT_PREFIX = "finance_contribution_causal_pilot_report:"
PREREQUISITE_REPORT_PREFIX = "finance_contribution_causal_pilot_prerequisite_report:"
EXPECTED_ROLES = ("estimation", "validation")


def _replay_proxy_report(report: Mapping[str, Any]) -> str:
    payload = dict(report)
    observed = payload.pop("report_hash", None)
    expected = canonical_hash(payload, prefix="finance_post_global_gp_c_proxy_report:")
    if observed != expected:
        raise ValueError("causal pilot GP-C report identity changed")
    if report.get("status") != "passed":
        raise ValueError("causal pilot requires a passed GP-C report")
    return str(observed)


def _replay_finite_report(report: Mapping[str, Any]) -> str:
    payload = dict(report)
    observed = payload.pop("report_hash", None)
    expected = canonical_hash(payload, prefix="finance_finite_target_report:")
    if observed != expected:
        raise ValueError("causal pilot finite-target report identity changed")
    return str(observed)


def _finite_failure_reasons(report: Mapping[str, Any]) -> tuple[str, ...]:
    reasons = []
    if float(report["reconstruction_relative_error"]) > float(
        report["maximum_reconstruction_relative_error"]
    ):
        reasons.append("reconstruction_relative_error_exceeded")
    if float(report["p95_radius_instability"]) > float(
        report["maximum_p95_radius_instability"]
    ):
        reasons.append("p95_radius_instability_exceeded")
    if float(report["signal_to_null_ratio"]) < float(report["minimum_signal_to_null_ratio"]):
        reasons.append("signal_to_null_ratio_below_minimum")
    return tuple(reasons)


def analyze_prerequisite_failure(
    *,
    execution_contract: Mapping[str, Any],
    estimation_finite_report: Mapping[str, Any],
    validation_finite_report: Mapping[str, Any],
) -> dict[str, Any]:
    contract = verify_execution_contract(execution_contract)
    reports = {
        "estimation": dict(estimation_finite_report),
        "validation": dict(validation_finite_report),
    }
    report_hashes = {role: _replay_finite_report(report) for role, report in reports.items()}
    frozen_ids = contract["source_support"]["objective_partition_ids"]
    coordinate_count = int(contract["state_count"]) - int(contract["task_count"])
    block_size = int(contract["finite_target_protocol"]["block_size"])
    block_count = math.ceil(coordinate_count / block_size)
    hadamard_order = 1 << (block_size - 1).bit_length()
    design_rows = int(contract["finite_target_protocol"]["design_count"]) * (
        block_count * hadamard_order + 1
    )
    expected_observations = (
        design_rows * len(contract["finite_target_protocol"]["radii"]) * 2
    )
    diagnostics = {}
    for role, report in reports.items():
        if report.get("experiment_version") != FINITE_TARGET_VERSION:
            raise ValueError("causal pilot finite-target version differs")
        if report.get("run_role") != SEALED_CAUSAL_PILOT_ROLE:
            raise ValueError("causal pilot finite target uses another run role")
        if report.get("numeric_contract_hash") != contract["contract_hash"]:
            raise ValueError("causal pilot finite target crosses numeric contracts")
        if report.get("numeric_profile") != contract["selected_profile"]:
            raise ValueError("causal pilot finite target crosses numeric profiles")
        if report.get("objective_role") != role:
            raise ValueError("causal pilot finite-target objective role differs")
        if {str(value) for value in report.get("objective_record_ids", ())} != {
            str(value) for value in frozen_ids[role]
        }:
            raise ValueError("causal pilot finite-target partition differs from contract")
        if int(report.get("objective_record_count", 0)) != 4:
            raise ValueError("causal pilot finite target has another objective support size")
        if int(report.get("coordinate_count", 0)) != coordinate_count:
            raise ValueError("causal pilot finite target has another coordinate support")
        if int(report.get("design_count", 0)) != int(
            contract["finite_target_protocol"]["design_count"]
        ):
            raise ValueError("causal pilot finite target has another design count")
        if int(report.get("observation_count", 0)) != expected_observations:
            raise ValueError("causal pilot finite target is incomplete")
        if report.get("status") != "failed":
            raise ValueError("prerequisite-failure report requires a failed finite target")
        if report.get("development_gate_eligible") is not False:
            raise ValueError("failed finite target incorrectly claims gate eligibility")
        if report.get("authorization_access_granted") is not False:
            raise ValueError("failed finite target incorrectly opens authorization")
        reasons = _finite_failure_reasons(report)
        if not reasons:
            raise ValueError("failed finite target lacks a reproducible failed gate")
        diagnostics[role] = {
            "source_report_hash": report_hashes[role],
            "failure_reasons": reasons,
            "observation_count": int(report["observation_count"]),
            "reconstruction_relative_error": float(report["reconstruction_relative_error"]),
            "maximum_reconstruction_relative_error": float(
                report["maximum_reconstruction_relative_error"]
            ),
            "mean_radius_instability": float(report["mean_radius_instability"]),
            "p95_radius_instability": float(report["p95_radius_instability"]),
            "maximum_p95_radius_instability": float(
                report["maximum_p95_radius_instability"]
            ),
            "signal_to_null_ratio": float(report["signal_to_null_ratio"]),
            "minimum_signal_to_null_ratio": float(report["minimum_signal_to_null_ratio"]),
        }
    values: dict[str, Any] = {
        "experiment_version": PILOT_GATE_VERSION,
        "artifact_type": "FinanceContributionCausalPilotPrerequisiteReport",
        "run_role": SEALED_CAUSAL_PILOT_ROLE,
        "execution_contract_hash": contract["contract_hash"],
        "numeric_profile": contract["selected_profile"],
        "source_finite_target_report_hashes": report_hashes,
        "diagnostics": diagnostics,
        "status": "blocked_prerequisite",
        "pilot_gate_passed": False,
        "gp_c_executed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "authorization_objective_access": "forbidden",
        "allowed_next_stage": contract["failure_transition"],
        "claim_boundary": contract["claim_boundary"],
    }
    values["report_hash"] = canonical_hash(values, prefix=PREREQUISITE_REPORT_PREFIX)
    return values


def _distribution_passed(metrics: Mapping[str, Any]) -> bool:
    thresholds = DISTRIBUTION_THRESHOLDS
    return bool(
        float(metrics["mean_total_variation"]) <= thresholds.maximum_mean_total_variation
        and float(metrics["p95_total_variation"]) <= thresholds.maximum_p95_total_variation
        and float(metrics["mean_jensen_shannon"]) <= thresholds.maximum_mean_jensen_shannon
        and float(metrics["p95_jensen_shannon"]) <= thresholds.maximum_p95_jensen_shannon
        and float(metrics["mean_update_direction_agreement"])
        >= thresholds.minimum_update_direction_agreement
        and float(metrics["mean_absolute_target_regret"])
        <= thresholds.maximum_mean_absolute_target_regret
        and float(metrics["p95_absolute_target_regret"])
        <= thresholds.maximum_p95_absolute_target_regret
        and float(metrics["mean_normalized_target_regret"])
        <= thresholds.maximum_mean_normalized_target_regret
        and float(metrics["p95_normalized_target_regret"])
        <= thresholds.maximum_p95_normalized_target_regret
        and float(metrics["mean_attainable_gain"]) >= thresholds.minimum_mean_attainable_gain
        and float(metrics["normalizable_task_rate"]) >= thresholds.minimum_normalizable_task_rate
    )


def _role_diagnostics(
    report: Mapping[str, Any],
    *,
    role: str,
    temperature: float,
    seed: int,
) -> dict[str, Any]:
    rank = _rank_metrics(report["state_rows"], seed=seed)
    rank_evidence = make_contribution_rank_validation_evidence(
        evaluation_role=("internal_estimation" if role == "estimation" else "internal_validation"),
        macro_task_spearman=rank["macro_task_spearman"],
        macro_task_spearman_ci95=rank["macro_task_spearman_ci95"],
        macro_pairwise_concordance=rank["macro_pairwise_concordance"],
        macro_pairwise_concordance_ci95=rank["macro_pairwise_concordance_ci95"],
        winner_agreement_rate=rank["winner_agreement_rate"],
        macro_spearman_p_value=rank["macro_spearman_p_value"],
        macro_pairwise_concordance_p_value=rank["macro_pairwise_concordance_p_value"],
    )
    distribution = _distribution_metrics(
        report["state_rows"],
        temperature=temperature,
        normalizable_gain_floor=(DISTRIBUTION_THRESHOLDS.minimum_normalizable_attainable_gain),
    )
    rank_passed = rank_evidence.passes_production_gate
    distribution_passed = _distribution_passed(distribution)
    return {
        "role": role,
        "source_proxy_report_hash": report["report_hash"],
        "rank": rank,
        "rank_evidence": rank_evidence.model_dump(mode="json"),
        "rank_gate_passed": rank_passed,
        "distribution": distribution,
        "distribution_thresholds": DISTRIBUTION_THRESHOLDS.model_dump(mode="json"),
        "distribution_gate_passed": distribution_passed,
        "role_gate_passed": rank_passed and distribution_passed,
    }


def analyze_causal_pilot(
    *,
    execution_contract: Mapping[str, Any],
    estimation_proxy_report: Mapping[str, Any],
    validation_proxy_report: Mapping[str, Any],
) -> dict[str, Any]:
    contract = verify_execution_contract(execution_contract)
    reports = {
        "estimation": dict(estimation_proxy_report),
        "validation": dict(validation_proxy_report),
    }
    report_hashes = {role: _replay_proxy_report(report) for role, report in reports.items()}
    for role, report in reports.items():
        if report.get("experiment_version") != GP_C_PROXY_VERSION:
            raise ValueError("causal pilot GP-C report version differs")
        if report.get("run_role") != SEALED_CAUSAL_PILOT_ROLE:
            raise ValueError("causal pilot consumed another run role")
        if report.get("objective_role") != role:
            raise ValueError("causal pilot objective role differs")
        if report.get("numeric_contract_hash") != contract["contract_hash"]:
            raise ValueError("causal pilot crosses numeric execution contracts")
        if report.get("numeric_profile") != contract["selected_profile"]:
            raise ValueError("causal pilot crosses numeric execution profiles")
        if report.get("production_authorization_eligible") is not False:
            raise ValueError("causal pilot input incorrectly claims production eligibility")
        if report.get("objective_record_count") != 4:
            raise ValueError("causal pilot objective support differs from frozen 4/4 split")
        state_rows = report.get("state_rows")
        if not isinstance(state_rows, list) or len(state_rows) != contract["state_count"]:
            raise ValueError("causal pilot state support differs")
        if len({str(row["task_id"]) for row in state_rows}) != contract["task_count"]:
            raise ValueError("causal pilot task support differs")
    frozen_partition_ids = contract["source_support"]["objective_partition_ids"]
    observed_partition_ids = {
        role: {str(value) for value in reports[role]["objective_record_ids"]}
        for role in EXPECTED_ROLES
    }
    for role in EXPECTED_ROLES:
        if observed_partition_ids[role] != {str(value) for value in frozen_partition_ids[role]}:
            raise ValueError("causal pilot objective partition differs from contract")
    estimation_ids = observed_partition_ids["estimation"]
    validation_ids = observed_partition_ids["validation"]
    if estimation_ids & validation_ids:
        raise ValueError("causal pilot objective partitions overlap")
    if reports["estimation"].get("calibration_source") != "fitted_on_estimation_only":
        raise ValueError("causal pilot estimation calibration was not fitted independently")
    frozen_scale = reports["estimation"].get("fitted_estimation_scale")
    if not isinstance(frozen_scale, (int, float)) or not math.isfinite(float(frozen_scale)):
        raise ValueError("causal pilot estimation calibration is invalid")
    if reports["validation"].get("calibration_source") != "frozen_estimation_scale":
        raise ValueError("causal pilot validation did not consume frozen calibration")
    if reports["validation"].get("calibration_report_hash") != report_hashes["estimation"]:
        raise ValueError("causal pilot validation consumed another calibration report")
    if not math.isclose(
        float(reports["validation"]["applied_calibration_scale"]),
        float(frozen_scale),
        rel_tol=0,
        abs_tol=1e-12,
    ):
        raise ValueError("causal pilot validation calibration changed")
    estimation_support = {
        (str(row["task_id"]), str(row["state_id"])) for row in reports["estimation"]["state_rows"]
    }
    validation_support = {
        (str(row["task_id"]), str(row["state_id"])) for row in reports["validation"]["state_rows"]
    }
    if estimation_support != validation_support:
        raise ValueError("causal pilot Estimation and Validation support differs")
    temperature = max(
        statistics.median(
            abs(float(row["finite_target"])) for row in reports["estimation"]["state_rows"]
        ),
        CALIBRATION_FLOOR,
    )
    diagnostics = {
        role: _role_diagnostics(
            reports[role],
            role=role,
            temperature=temperature,
            seed=20261910 + index * 10,
        )
        for index, role in enumerate(EXPECTED_ROLES)
    }
    passed = all(row["role_gate_passed"] for row in diagnostics.values())
    values: dict[str, Any] = {
        "experiment_version": PILOT_GATE_VERSION,
        "artifact_type": "FinanceContributionCausalPilotReport",
        "run_role": SEALED_CAUSAL_PILOT_ROLE,
        "execution_contract_hash": contract["contract_hash"],
        "numeric_profile": contract["selected_profile"],
        "source_proxy_report_hashes": report_hashes,
        "calibration_scale": float(frozen_scale),
        "distribution_temperature": temperature,
        "diagnostics": diagnostics,
        "pilot_gate_passed": passed,
        "status": "passed" if passed else "failed",
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "authorization_objective_access": "forbidden",
        "allowed_next_stage": (
            contract["success_transition"] if passed else contract["failure_transition"]
        ),
        "claim_boundary": contract["claim_boundary"],
    }
    values["report_hash"] = canonical_hash(values, prefix=PILOT_REPORT_PREFIX)
    return values


def _analyze(args: argparse.Namespace) -> None:
    report = analyze_causal_pilot(
        execution_contract=_read_json(Path(args.execution_contract).resolve()),
        estimation_proxy_report=_read_json(Path(args.estimation_proxy_report).resolve()),
        validation_proxy_report=_read_json(Path(args.validation_proxy_report).resolve()),
    )
    output_path = Path(args.output_path).resolve()
    if output_path.exists():
        raise ValueError("causal pilot report is immutable and already exists")
    _write_json(output_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _record_prerequisite_failure(args: argparse.Namespace) -> None:
    report = analyze_prerequisite_failure(
        execution_contract=_read_json(Path(args.execution_contract).resolve()),
        estimation_finite_report=_read_json(Path(args.estimation_finite_report).resolve()),
        validation_finite_report=_read_json(Path(args.validation_finite_report).resolve()),
    )
    output_path = Path(args.output_path).resolve()
    if output_path.exists():
        raise ValueError("causal pilot prerequisite report is immutable and already exists")
    _write_json(output_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate the sealed v19 causal pilot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--execution-contract", required=True)
    analyze.add_argument("--estimation-proxy-report", required=True)
    analyze.add_argument("--validation-proxy-report", required=True)
    analyze.add_argument("--output-path", required=True)
    analyze.set_defaults(handler=_analyze)
    prerequisite = subparsers.add_parser("record-prerequisite-failure")
    prerequisite.add_argument("--execution-contract", required=True)
    prerequisite.add_argument("--estimation-finite-report", required=True)
    prerequisite.add_argument("--validation-finite-report", required=True)
    prerequisite.add_argument("--output-path", required=True)
    prerequisite.set_defaults(handler=_record_prerequisite_failure)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
