from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_finite_target import (
    DIRECTION_MANIFEST_HASH_PREFIX,
    _load_jsonl,
    _observation_hash,
    _percentile,
    _verify_direction_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _read_json,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

DIAGNOSTIC_VERSION = "finance_finite_radius_diagnostic.v1"
PLAN_PREFIX = "finance_finite_radius_diagnostic_plan:"
REPORT_PREFIX = "finance_finite_radius_diagnostic_report:"
RUN_ROLE = "sealed_causal_failure_diagnostic"
SELECTED_DIRECTION_COUNT = 8
SOURCE_RADII = (0.1, 0.05, 0.025)
ANCHOR_RADIUS = 0.025
DIAGNOSTIC_RADII = (0.0125, 0.00625)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _read_complete_source_observations(source_dir: Path) -> tuple[Path, list[dict[str, Any]]]:
    worker_paths = sorted((source_dir / "workers").glob("partition_*.jsonl"))
    if not worker_paths:
        raise ValueError("radius diagnostic source has no observations")
    rows = [row for worker_path in worker_paths for row in _load_jsonl(worker_path)]
    keys = {
        (str(row["design_row_id"]), float(row["radius"]), int(row["sign"]))
        for row in rows
    }
    if len(keys) != len(rows):
        raise ValueError("radius diagnostic source observations overlap")
    if len(worker_paths) != 1:
        raise ValueError("sealed radius diagnostic requires one frozen source partition")
    return worker_paths[0], rows


def prepare_radius_diagnostic(
    *,
    source_dir: Path,
    source_direction_manifest_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    source_plan_path = source_dir / "plan.json"
    source_report_path = source_dir / "report.json"
    source_plan = _read_json(source_plan_path)
    source_report = _read_json(source_report_path)
    source_manifest = _read_json(source_direction_manifest_path)
    source_plan_hash = _replay_hash(
        source_plan,
        field="plan_hash",
        prefix="finance_finite_target_plan:",
        label="radius diagnostic source plan",
    )
    source_report_hash = _replay_hash(
        source_report,
        field="report_hash",
        prefix="finance_finite_target_report:",
        label="radius diagnostic source report",
    )
    source_manifest_hash = _verify_direction_manifest(source_plan, source_manifest)
    if source_report.get("plan_hash") != source_plan_hash:
        raise ValueError("radius diagnostic source report belongs to another plan")
    if source_report.get("status") != "failed":
        raise ValueError("radius diagnostic requires a failed finite target")
    if source_plan.get("run_role") != "sealed_causal_pilot":
        raise ValueError("radius diagnostic requires the sealed causal pilot")
    if source_plan.get("production_authorization_eligible") is not False:
        raise ValueError("radius diagnostic source incorrectly claims production eligibility")
    if tuple(float(value) for value in source_plan.get("radii", ())) != SOURCE_RADII:
        raise ValueError("radius diagnostic source ladder changed")
    source_observation_path, source_observations = _read_complete_source_observations(source_dir)
    if len(source_observations) != int(source_report.get("observation_count", 0)):
        raise ValueError("radius diagnostic source observation count differs")
    source_seeds = {int(row["numeric_seed"]) for row in source_observations}
    if len(source_seeds) != 1:
        raise ValueError("radius diagnostic source seed is not frozen")
    source_rows = {
        str(row["design_row_id"]): row
        for row in source_plan["design_rows"]
        if row.get("role") == "orthogonal_design"
    }
    selected_ids = tuple(sorted(source_rows)[:SELECTED_DIRECTION_COUNT])
    if len(selected_ids) != SELECTED_DIRECTION_COUNT:
        raise ValueError("radius diagnostic has insufficient orthogonal directions")
    artifact_by_id = {
        str(row["design_row_id"]): row for row in source_manifest["direction_artifacts"]
    }
    selected_artifacts = tuple(artifact_by_id[direction_id] for direction_id in selected_ids)
    for artifact in selected_artifacts:
        artifact_path = Path(str(artifact["file"]))
        if _sha256(artifact_path) != artifact["sha256"]:
            raise ValueError("radius diagnostic direction artifact changed")
    values: dict[str, Any] = {
        "experiment_version": DIAGNOSTIC_VERSION,
        "artifact_type": "FinanceFiniteRadiusDiagnosticPlan",
        "run_role": RUN_ROLE,
        "diagnostic_only": True,
        "production_authorization_eligible": False,
        "authorization_objective_access": "forbidden",
        "source_finite_target_plan_path": str(source_plan_path.resolve()),
        "source_finite_target_plan_sha256": _sha256(source_plan_path),
        "source_finite_target_plan_hash": source_plan_hash,
        "source_finite_target_report_path": str(source_report_path.resolve()),
        "source_finite_target_report_sha256": _sha256(source_report_path),
        "source_finite_target_report_hash": source_report_hash,
        "source_direction_manifest_path": str(source_direction_manifest_path.resolve()),
        "source_direction_manifest_sha256": _sha256(source_direction_manifest_path),
        "source_direction_manifest_hash": source_manifest_hash,
        "source_observations_path": str(source_observation_path.resolve()),
        "source_observations_sha256": _sha256(source_observation_path),
        "source_numeric_seed": next(iter(source_seeds)),
        "source_radii": SOURCE_RADII,
        "anchor_radius": ANCHOR_RADIUS,
        "radii": DIAGNOSTIC_RADII,
        "selection_policy": "lexicographic_first_8_non_null_direction_ids_v1",
        "selected_direction_ids": selected_ids,
        "model_dir": source_plan["model_dir"],
        "base_model_manifest_hash": source_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": source_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": source_plan[
            "beneficiary_adapter_tensor_sha256"
        ],
        "beneficiary_model_state_id": source_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": source_plan["beneficiary_checkpoint_hash"],
        "source_records_path": source_plan["source_records_path"],
        "source_records_sha256": source_plan["source_records_sha256"],
        "numeric_contract_hash": source_plan["numeric_contract_hash"],
        "numeric_profile": source_plan["numeric_profile"],
        "optimizer_contract": source_plan["optimizer_contract"],
        "objective_role": source_plan["objective_role"],
        "objective_record_ids": source_plan["objective_record_ids"],
        "objective_records_hash": source_plan["objective_records_hash"],
        "objective_record_count": source_plan["objective_record_count"],
        "objective_gradient_mode": source_plan["objective_gradient_mode"],
        "objective_gradient_point": "post_global_update",
        "state_gradient_mode": source_plan["state_gradient_mode"],
        "design_rows": tuple(source_rows[direction_id] for direction_id in selected_ids),
        "claim_boundary": (
            "Post-failure diagnostic only. Smaller radii are selected after the v19 finite-target "
            "gate failed and cannot authorize GP-C, Contribution, VTDO updates, or production."
        ),
    }
    values["plan_hash"] = canonical_hash(values, prefix=PLAN_PREFIX)
    diagnostic_manifest: dict[str, Any] = {
        "experiment_version": DIAGNOSTIC_VERSION,
        "artifact_type": "FiniteRadiusDiagnosticDirectionManifest",
        "finite_target_plan_hash": values["plan_hash"],
        "source_finite_target_plan_hash": source_plan_hash,
        "source_direction_manifest_hash": source_manifest_hash,
        "global_update_artifact": source_manifest["global_update_artifact"],
        "direction_artifacts": selected_artifacts,
        "diagnostic_only": True,
    }
    diagnostic_manifest["manifest_hash"] = canonical_hash(
        diagnostic_manifest,
        prefix=DIRECTION_MANIFEST_HASH_PREFIX,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "plan.json", values)
    _write_json(output_dir / "direction_manifest.json", diagnostic_manifest)
    return values


def _signed_derivatives(
    rows: Sequence[Mapping[str, Any]],
    *,
    direction_ids: Sequence[str],
    radii: Sequence[float],
    expected_plan_hash: str,
    expected_role: str,
    expected_numeric_contract_hash: str,
) -> dict[str, dict[float, float]]:
    selected = set(direction_ids)
    grouped: defaultdict[tuple[str, float], dict[int, float]] = defaultdict(dict)
    baseline_hashes = set()
    baseline_objectives = set()
    for row in rows:
        if row.get("observation_hash") != _observation_hash(row):
            raise ValueError("radius diagnostic observation identity changed")
        if row.get("plan_hash") != expected_plan_hash:
            raise ValueError("radius diagnostic observation belongs to another plan")
        if row.get("objective_role") != expected_role:
            raise ValueError("radius diagnostic observation uses another objective role")
        if row.get("numeric_contract_hash") != expected_numeric_contract_hash:
            raise ValueError("radius diagnostic observation crosses numeric contracts")
        direction_id = str(row["design_row_id"])
        radius = float(row["radius"])
        sign = int(row["sign"])
        if direction_id not in selected or radius not in radii or sign not in {-1, 1}:
            continue
        key = (direction_id, radius)
        if sign in grouped[key]:
            raise ValueError("radius diagnostic observation duplicates a sign")
        grouped[key][sign] = float(row["objective_value"])
        baseline_hashes.add(str(row["baseline_post_global_adapter_hash"]))
        baseline_objectives.add(float(row["baseline_objective_value"]))
    required = {(direction_id, float(radius)) for direction_id in selected for radius in radii}
    if set(grouped) != required or any(set(pair) != {-1, 1} for pair in grouped.values()):
        raise ValueError("radius diagnostic observation matrix is incomplete")
    if len(baseline_hashes) != 1 or len(baseline_objectives) != 1:
        raise ValueError("radius diagnostic baseline changed")
    return {
        direction_id: {
            float(radius): (
                grouped[(direction_id, float(radius))][1]
                - grouped[(direction_id, float(radius))][-1]
            )
            / (2.0 * float(radius))
            for radius in radii
        }
        for direction_id in direction_ids
    }


def _triplet_instability(values: Mapping[float, float], radii: Sequence[float]) -> float:
    derivative_h, derivative_h2, derivative_h4 = (float(values[radius]) for radius in radii)
    first = (4.0 * derivative_h2 - derivative_h) / 3.0
    second = (4.0 * derivative_h4 - derivative_h2) / 3.0
    return abs(second - first) / max(abs(first), abs(second), 1e-12)


def _sign_consistent(values: Mapping[float, float]) -> bool:
    signs = {0 if abs(value) < 1e-15 else (1 if value > 0 else -1) for value in values.values()}
    return len(signs) == 1


def analyze_radius_diagnostic(
    *,
    plan: Mapping[str, Any],
    direction_manifest: Mapping[str, Any],
    diagnostic_observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    plan_hash = _replay_hash(
        plan,
        field="plan_hash",
        prefix=PLAN_PREFIX,
        label="radius diagnostic plan",
    )
    _verify_direction_manifest(plan, direction_manifest)
    if plan.get("run_role") != RUN_ROLE or plan.get("diagnostic_only") is not True:
        raise ValueError("radius diagnostic plan has another role")
    if plan.get("production_authorization_eligible") is not False:
        raise ValueError("radius diagnostic incorrectly claims production eligibility")
    source_plan_path = Path(str(plan["source_finite_target_plan_path"]))
    source_report_path = Path(str(plan["source_finite_target_report_path"]))
    source_manifest_path = Path(str(plan["source_direction_manifest_path"]))
    source_observations_path = Path(str(plan["source_observations_path"]))
    for path, expected in (
        (source_plan_path, plan["source_finite_target_plan_sha256"]),
        (source_report_path, plan["source_finite_target_report_sha256"]),
        (source_manifest_path, plan["source_direction_manifest_sha256"]),
        (source_observations_path, plan["source_observations_sha256"]),
    ):
        if _sha256(path) != expected:
            raise ValueError("radius diagnostic source artifact changed")
    source_plan = _read_json(source_plan_path)
    source_report = _read_json(source_report_path)
    source_manifest = _read_json(source_manifest_path)
    _replay_hash(
        source_plan,
        field="plan_hash",
        prefix="finance_finite_target_plan:",
        label="radius diagnostic source plan",
    )
    _replay_hash(
        source_report,
        field="report_hash",
        prefix="finance_finite_target_report:",
        label="radius diagnostic source report",
    )
    _verify_direction_manifest(source_plan, source_manifest)
    if source_report.get("status") != "failed":
        raise ValueError("radius diagnostic source no longer fails")
    direction_ids = tuple(str(value) for value in plan["selected_direction_ids"])
    source_rows = _load_jsonl(source_observations_path)
    source_derivatives = _signed_derivatives(
        source_rows,
        direction_ids=direction_ids,
        radii=SOURCE_RADII,
        expected_plan_hash=str(plan["source_finite_target_plan_hash"]),
        expected_role=str(plan["objective_role"]),
        expected_numeric_contract_hash=str(plan["numeric_contract_hash"]),
    )
    diagnostic_radii = tuple(float(value) for value in plan["radii"])
    new_derivatives = _signed_derivatives(
        diagnostic_observations,
        direction_ids=direction_ids,
        radii=diagnostic_radii,
        expected_plan_hash=plan_hash,
        expected_role=str(plan["objective_role"]),
        expected_numeric_contract_hash=str(plan["numeric_contract_hash"]),
    )
    smaller_radii = (ANCHOR_RADIUS, *diagnostic_radii)
    rows = []
    source_instabilities = []
    smaller_instabilities = []
    for direction_id in direction_ids:
        smaller_values = {
            ANCHOR_RADIUS: source_derivatives[direction_id][ANCHOR_RADIUS],
            **new_derivatives[direction_id],
        }
        source_instability = _triplet_instability(
            source_derivatives[direction_id],
            SOURCE_RADII,
        )
        smaller_instability = _triplet_instability(smaller_values, smaller_radii)
        source_instabilities.append(source_instability)
        smaller_instabilities.append(smaller_instability)
        rows.append(
            {
                "design_row_id": direction_id,
                "source_derivatives": source_derivatives[direction_id],
                "smaller_radius_derivatives": smaller_values,
                "source_radius_instability": source_instability,
                "smaller_radius_instability": smaller_instability,
                "source_sign_consistent": _sign_consistent(source_derivatives[direction_id]),
                "smaller_radius_sign_consistent": _sign_consistent(smaller_values),
                "smaller_radius_improved": smaller_instability < source_instability,
            }
        )
    threshold = float(source_report["maximum_p95_radius_instability"])
    improvement_rate = statistics.fmean(
        float(smaller < source)
        for source, smaller in zip(source_instabilities, smaller_instabilities, strict=True)
    )
    smaller_p95 = _percentile(smaller_instabilities, 0.95)
    conclusion = (
        "smaller_radius_restores_local_linearity"
        if smaller_p95 <= threshold and improvement_rate >= 0.75
        else "smaller_radius_does_not_restore_local_linearity"
    )
    report: dict[str, Any] = {
        "experiment_version": DIAGNOSTIC_VERSION,
        "artifact_type": "FinanceFiniteRadiusDiagnosticReport",
        "run_role": RUN_ROLE,
        "diagnostic_only": True,
        "plan_hash": plan_hash,
        "source_finite_target_report_hash": plan["source_finite_target_report_hash"],
        "objective_role": plan["objective_role"],
        "selected_direction_count": len(direction_ids),
        "source_radii": SOURCE_RADII,
        "smaller_radii": smaller_radii,
        "source_median_radius_instability": statistics.median(source_instabilities),
        "source_p95_radius_instability": _percentile(source_instabilities, 0.95),
        "smaller_median_radius_instability": statistics.median(smaller_instabilities),
        "smaller_p95_radius_instability": smaller_p95,
        "maximum_p95_radius_instability": threshold,
        "smaller_radius_improvement_rate": improvement_rate,
        "source_sign_consistency_rate": statistics.fmean(
            1.0 if bool(row["source_sign_consistent"]) else 0.0 for row in rows
        ),
        "smaller_sign_consistency_rate": statistics.fmean(
            1.0 if bool(row["smaller_radius_sign_consistent"]) else 0.0 for row in rows
        ),
        "direction_rows": rows,
        "conclusion": conclusion,
        "status": "completed_diagnostic",
        "gp_c_executed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "authorization_objective_access": "forbidden",
        "claim_boundary": plan["claim_boundary"],
    }
    report["report_hash"] = canonical_hash(report, prefix=REPORT_PREFIX)
    return report


def _prepare(args: argparse.Namespace) -> None:
    plan = prepare_radius_diagnostic(
        source_dir=Path(args.source_dir).resolve(),
        source_direction_manifest_path=Path(args.source_direction_manifest).resolve(),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


def _analyze(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    observations = [
        row
        for worker_path in sorted((output_dir / "workers").glob("partition_*.jsonl"))
        for row in _load_jsonl(worker_path)
    ]
    report = analyze_radius_diagnostic(
        plan=_read_json(output_dir / "plan.json"),
        direction_manifest=_read_json(output_dir / "direction_manifest.json"),
        diagnostic_observations=observations,
    )
    output_path = output_dir / "report.json"
    if output_path.exists():
        raise ValueError("radius diagnostic report is immutable and already exists")
    _write_json(output_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a post-failure finite-radius diagnostic")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-dir", required=True)
    prepare.add_argument("--source-direction-manifest", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.set_defaults(handler=_prepare)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--output-dir", required=True)
    analyze.set_defaults(handler=_analyze)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
