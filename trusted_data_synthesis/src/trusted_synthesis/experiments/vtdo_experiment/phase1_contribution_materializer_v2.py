from __future__ import annotations

import argparse
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.core.vtdo import (
    ConditionalTrajectoryDistribution,
    ContributionApproximationAuthorization,
    ContributionEstimationManifest,
    contribution_current_distribution_hash,
    contribution_materialization_protocol_hash,
    make_gradient_projection_contribution_manifest,
    validate_contribution_approximation_authorization,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _read_json,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

MATERIALIZER_VERSION = "finance_gradient_contribution_materializer.v4"


def _assert_canonical(
    artifact: Mapping[str, Any],
    *,
    hash_field: str,
    prefix: str,
    name: str,
) -> str:
    unhashed = dict(artifact)
    observed = unhashed.pop(hash_field, None)
    if observed != canonical_hash(unhashed, prefix=prefix):
        raise ValueError(f"{name} identity changed")
    return str(observed)


def materialize_contribution_manifests(
    *,
    gradient_plan: Mapping[str, Any],
    authorization: ContributionApproximationAuthorization,
    validation_proxy_report: Mapping[str, Any],
) -> tuple[tuple[ContributionEstimationManifest, ...], dict[str, Any]]:
    _assert_canonical(
        gradient_plan,
        hash_field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
        name="Gradient Projection plan",
    )
    _assert_canonical(
        validation_proxy_report,
        hash_field="report_hash",
        prefix="finance_post_global_gp_c_proxy_report:",
        name="validation GP-C proxy report",
    )
    if gradient_plan.get("run_role") != "production_candidate":
        raise ValueError("Contribution materialization forbids smoke Gradient plans")
    if authorization.source_plan_hash != gradient_plan["plan_hash"]:
        raise ValueError("Contribution authorization belongs to another Gradient plan")
    if (
        gradient_plan.get("token_region_decomposition", {}).get("manifest_hash")
        != authorization.token_region_manifest_hash
    ):
        raise ValueError("Contribution materialization changed token-region lineage")
    expected_proxy_hash = dict(authorization.proxy_report_hashes)["validation"]
    if validation_proxy_report.get("report_hash") != expected_proxy_hash:
        raise ValueError("Contribution materialization requires the authorized validation proxy")
    expected_proxy_identity = {
        "objective_role": "validation",
        "source_gradient_plan_hash": gradient_plan["plan_hash"],
        "beneficiary_model_state_id": authorization.beneficiary_model_state_id,
        "beneficiary_checkpoint_hash": authorization.beneficiary_checkpoint_hash,
        "objective_gradient_point": "post_global_update",
        "local_update_manifest_hash": authorization.local_update_manifest_hash,
        "status": "passed",
    }
    mismatches = tuple(
        field
        for field, expected in expected_proxy_identity.items()
        if validation_proxy_report.get(field) != expected
    )
    if mismatches:
        raise ValueError(f"validation GP-C proxy identity mismatch:{mismatches}")
    if (
        validation_proxy_report.get("state_uncertainty_method")
        != authorization.state_uncertainty_method
    ):
        raise ValueError("validation GP-C proxy changed the authorized uncertainty method")
    proxy_rows = {
        (str(row["task_id"]), str(row["state_id"])): row
        for row in validation_proxy_report["state_rows"]
    }
    if len(proxy_rows) != len(validation_proxy_report["state_rows"]):
        raise ValueError("validation GP-C proxy contains duplicate task states")
    authorized_tasks = tuple(authorization.task_condition_ids)
    if set(gradient_plan["task_distributions"]) != set(authorized_tasks):
        raise ValueError("Gradient Plan task population differs from authorization")
    authorized_realization_counts = {
        (task_id, state_id): count
        for task_id, state_id, count in authorization.state_realization_counts
    }
    expected_realization_ids: dict[tuple[str, str], set[str]] = {}
    for job in gradient_plan["jobs"]:
        key = (str(job["task_id"]), str(job["state_id"]))
        expected_realization_ids.setdefault(key, set()).add(str(job["realization_id"]))
    if (
        set(expected_realization_ids) != set(authorized_realization_counts)
        or any(
            len(values) != authorized_realization_counts[key]
            for key, values in expected_realization_ids.items()
        )
        or sum(len(values) for values in expected_realization_ids.values())
        != len({value for values in expected_realization_ids.values() for value in values})
    ):
        raise ValueError("Gradient plan realization lineage is not an exact partition")
    protocol_hash = contribution_materialization_protocol_hash(authorization)
    manifests = []
    for task_id in authorized_tasks:
        distribution_payload = gradient_plan["task_distributions"][task_id].get(
            "distribution"
        )
        if distribution_payload is None:
            raise ValueError("production Gradient plan lacks a typed current distribution")
        distribution = ConditionalTrajectoryDistribution.model_validate(
            distribution_payload
        )
        if distribution.task_condition_id != task_id:
            raise ValueError("Gradient plan distribution crosses task conditions")
        expected_hash = dict(authorization.task_distribution_hashes)[task_id]
        plan_probabilities = {
            str(state_id): float(probability)
            for state_id, probability in gradient_plan["task_distributions"][task_id][
                "probabilities"
            ].items()
        }
        if distribution.probabilities != plan_probabilities:
            raise ValueError("Gradient plan probabilities differ from typed distribution")
        if expected_hash != contribution_current_distribution_hash(
            task_id,
            plan_probabilities,
        ):
            raise ValueError("Gradient plan current-distribution hash is invalid")
        state_realizations = {}
        for state_id, probability in distribution.probabilities.items():
            row = proxy_rows.get((task_id, state_id))
            if row is None:
                raise ValueError("validation GP-C proxy does not cover current support")
            if not math.isclose(
                float(row["current_probability"]),
                probability,
                abs_tol=1e-12,
            ):
                raise ValueError("validation GP-C proxy changed current probability")
            values = tuple(
                float(value) for value in row["jackknife_raw_gp_c_proxy_values"]
            )
            expected_count = authorized_realization_counts[(task_id, state_id)]
            if len(values) != expected_count or not 3 <= len(values) <= 5:
                raise ValueError("validation GP-C Jackknife support is incomplete")
            if any(not math.isfinite(value) for value in values):
                raise ValueError("validation GP-C Jackknife value is non-finite")
            realization_ids = tuple(
                str(value) for value in row["jackknife_realization_ids"]
            )
            if (
                int(row["jackknife_realization_count"]) != expected_count
                or len(realization_ids) != expected_count
                or len(set(realization_ids)) != expected_count
                or set(realization_ids) != expected_realization_ids[(task_id, state_id)]
            ):
                raise ValueError("validation GP-C Jackknife changed realization lineage")
            observed_deviation = float(row["jackknife_proxy_sample_standard_deviation"])
            if not math.isfinite(observed_deviation) or not math.isclose(
                observed_deviation,
                statistics.stdev(values),
                rel_tol=1e-10,
                abs_tol=1e-12,
            ):
                raise ValueError("validation GP-C Jackknife deviation failed replay")
            state_realizations[state_id] = values
        manifest = make_gradient_projection_contribution_manifest(
            distribution,
            state_realizations,
            beneficiary_model_state_id=authorization.beneficiary_model_state_id,
            beneficiary_checkpoint_hash=authorization.beneficiary_checkpoint_hash,
            target_validation_set_id=dict(authorization.objective_partition_ids)[
                "validation"
            ],
            authorization_set_id=dict(authorization.objective_partition_ids)[
                "authorization"
            ],
            target_metric_id=authorization.target_metric_id,
            estimation_protocol_hash=protocol_hash,
            data_isolation_contract_id=authorization.strict_freshness_contract_hash,
            estimator_id=authorization.estimator_id,
            optimizer_contract=authorization.optimizer_contract,
            calibration_contract=authorization.calibration_contract,
            uncertainty_penalty_coefficient=(
                authorization.uncertainty_penalty_coefficient
            ),
        )
        validate_contribution_approximation_authorization(manifest, authorization)
        manifests.append(manifest)
    consumed_pairs = {
        (task_id, state_id)
        for task_id in authorized_tasks
        for state_id in gradient_plan["task_distributions"][task_id]["probabilities"]
    }
    if set(proxy_rows) != consumed_pairs:
        raise ValueError("validation GP-C proxy contains unconsumed task states")
    frozen = tuple(sorted(manifests, key=lambda value: value.task_condition_id))
    report: dict[str, Any] = {
        "experiment_version": MATERIALIZER_VERSION,
        "artifact_type": "GradientProjectionContributionMaterializationReport",
        "source_gradient_plan_hash": gradient_plan["plan_hash"],
        "authorization_id": authorization.authorization_id,
        "validation_proxy_report_hash": validation_proxy_report["report_hash"],
        "materialization_protocol_hash": protocol_hash,
        "state_uncertainty_method": authorization.state_uncertainty_method,
        "realization_lineage_hash": canonical_hash(
            tuple(
                (task_id, state_id, tuple(sorted(values)))
                for (task_id, state_id), values in sorted(expected_realization_ids.items())
            ),
            prefix="finance_gradient_materialization_realization_lineage:",
        ),
        "task_count": len(frozen),
        "state_count": sum(len(item.estimates) for item in frozen),
        "manifest_ids": tuple(item.manifest_id for item in frozen),
        "manifest_set_hash": canonical_hash(
            tuple(item.manifest_id for item in frozen),
            prefix="finance_gradient_contribution_manifest_set:",
        ),
        "status": "passed",
        "claim_boundary": authorization.claim_boundary,
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_gradient_contribution_materialization_report:",
    )
    return frozen, report


def _write_jsonl(path: Path, values: Sequence[ContributionEstimationManifest]) -> None:
    path.write_text(
        "".join(value.model_dump_json() + "\n" for value in values),
        encoding="utf-8",
    )


def _run(args: argparse.Namespace) -> None:
    gradient_dir = Path(args.gradient_dir).resolve()
    gradient_plan = _read_json(gradient_dir / "plan.json")
    authorization = ContributionApproximationAuthorization.model_validate(
        _read_json(Path(args.authorization_path).resolve())
    )
    validation_proxy = _read_json(Path(args.validation_proxy_report).resolve())
    manifests, report = materialize_contribution_manifests(
        gradient_plan=gradient_plan,
        authorization=authorization,
        validation_proxy_report=validation_proxy,
    )
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "contribution_manifests.jsonl", manifests)
    _write_json(output_dir / "materialization_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize authorized GP-C proxies into Core Contribution manifests"
    )
    parser.add_argument("--gradient-dir", required=True)
    parser.add_argument("--authorization-path", required=True)
    parser.add_argument("--validation-proxy-report", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.set_defaults(handler=_run)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
