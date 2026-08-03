from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from trusted_synthesis.core.vtdo import (
    AnchoredDistributionUpdate,
    ContributionEstimationManifest,
    ContributionProbeObservation,
    ContributionProbeProtocol,
    ContributionProductionAuthorization,
    CoveragePrior,
    EmpiricalDistributionEstimate,
    StateConditionedTrainingArtifact,
    TrajectoryStateCatalog,
    TrajectoryStateMaterializationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOTrainingRecord
from trusted_synthesis.hashing import canonical_hash

ModelT = TypeVar("ModelT", bound=BaseModel)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _typed_json(path: Path, model: type[ModelT]) -> ModelT:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def _typed_jsonl(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    values = tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not values:
        raise ValueError(f"expected at least one JSONL record: {path}")
    return values


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _check_embedded_hash(value: dict[str, Any], field: str, prefix: str) -> None:
    observed = value.get(field)
    payload = {key: item for key, item in value.items() if key != field}
    expected = canonical_hash(payload, prefix=prefix)
    _check(observed == expected, f"{field} does not replay under {prefix}")


def _file_manifest(root: Path) -> dict[str, Any]:
    ignored = {
        "artifact_integrity_audit.json",
        "artifact_manifest.json",
    }
    files = {
        str(path.relative_to(root)): {
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in ignored
    }
    value: dict[str, Any] = {"files": files}
    value["manifest_hash"] = canonical_hash(
        value,
        prefix="finance_phase1_artifact_manifest:",
    )
    return value


def _verify_input_manifest(path: Path) -> dict[str, Any]:
    value = _json(path)
    _check_embedded_hash(
        value,
        "manifest_hash",
        "finance_phase1_input_manifest:",
    )
    files = value.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("input manifest has no files")
    for name, metadata in files.items():
        _check(isinstance(metadata, dict), f"invalid input metadata: {name}")
        source = Path(str(metadata["path"]))
        _check(source.is_file(), f"frozen input is missing: {name}")
        _check(source.stat().st_size == metadata["size"], f"input size changed: {name}")
        _check(_sha256(source) == metadata["sha256"], f"input content changed: {name}")
    return value


def _verify_model_manifest(
    output_dir: Path,
    plan: dict[str, Any],
    *,
    verify_live_model_files: bool,
) -> int:
    value = _json(output_dir / "base_model_content_manifest.json")
    files = value.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("base model manifest has no files")
    expected_hash = canonical_hash(files, prefix="base_model_content_manifest:")
    _check(value.get("manifest_hash") == expected_hash, "base model manifest hash is invalid")
    _check(
        value.get("manifest_hash") == plan.get("base_model_manifest_hash"),
        "Probe plan names another base model manifest",
    )
    if verify_live_model_files:
        model_dir = Path(str(value["model_dir"]))
        for relative, metadata in files.items():
            path = model_dir / relative
            _check(path.is_file(), f"base model file is missing: {relative}")
            _check(
                path.stat().st_size == metadata["size"],
                f"base model file size changed: {relative}",
            )
            _check(_sha256(path) == metadata["sha256"], f"base model changed: {relative}")
    return len(files)


def _verify_training_identities(
    output_dir: Path,
    plan: dict[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    baseline = _json(output_dir / "beneficiary_training_report.json")
    _check_embedded_hash(
        baseline,
        "report_hash",
        "finance_phase1_beneficiary:",
    )
    _check(baseline["plan_hash"] == plan["plan_hash"], "beneficiary crossed Probe plans")
    adapter_dir = Path(str(baseline["adapter_dir"]))
    adapter_files = baseline["adapter_files"]
    for relative, metadata in adapter_files.items():
        path = adapter_dir / relative
        _check(path.is_file(), f"beneficiary Adapter file is missing: {relative}")
        _check(path.stat().st_size == metadata["size"], f"Adapter size changed: {relative}")
        _check(_sha256(path) == metadata["sha256"], f"Adapter content changed: {relative}")
    expected_checkpoint = canonical_hash(
        {
            "base_model_manifest_hash": plan["base_model_manifest_hash"],
            "adapter_tensor_sha256": baseline["adapter_tensor_sha256"],
            "adapter_files": adapter_files,
        },
        prefix="qwen_beneficiary_checkpoint:",
    )
    _check(
        baseline["checkpoint_hash"] == expected_checkpoint,
        "beneficiary checkpoint identity is invalid",
    )
    expected_state = canonical_hash(
        {
            "checkpoint_hash": expected_checkpoint,
            "role": "vtdo_beneficiary",
            "task_family": "finance_phase1",
        },
        prefix="beneficiary_model_state:",
    )
    _check(baseline["model_state_id"] == expected_state, "beneficiary state identity is invalid")

    workers = tuple(
        _json(path)
        for path in sorted((output_dir / "probe_workers").glob("*.json"))
    )
    expected_pairs = {
        (state_id, int(seed))
        for state_id in plan["probe_update_records_by_state"]
        for seed in plan["probe_seeds"]
    }
    observed_pairs = {(item["state_id"], int(item["seed"])) for item in workers}
    _check(observed_pairs == expected_pairs, "Probe worker state/seed matrix is incomplete")
    for worker in workers:
        _check_embedded_hash(
            worker,
            "report_hash",
            "finance_phase1_probe_worker:",
        )
        _check(worker["plan_hash"] == plan["plan_hash"], "worker crossed Probe plans")
        _check(
            worker["beneficiary_report_hash"] == baseline["report_hash"],
            "worker crossed beneficiary reports",
        )
        expected_adapted_checkpoint = canonical_hash(
            {
                "base_checkpoint_hash": baseline["checkpoint_hash"],
                "adapter_tensor_sha256": worker["adapted_adapter_tensor_sha256"],
                "state_id": worker["state_id"],
                "seed": worker["seed"],
                "step_count": worker["step_count"],
            },
            prefix="qwen_probe_adapted_checkpoint:",
        )
        _check(
            worker["adapted_checkpoint_hash"] == expected_adapted_checkpoint,
            "adapted Probe checkpoint identity is invalid",
        )
        expected_adapted_state = canonical_hash(
            {
                "checkpoint_hash": expected_adapted_checkpoint,
                "role": "contribution_probe_adaptation",
            },
            prefix="probe_model_state:",
        )
        _check(
            worker["adapted_model_state_id"] == expected_adapted_state,
            "adapted Probe model-state identity is invalid",
        )
    return baseline, workers


def audit_phase1(
    output_dir: Path,
    *,
    verify_live_model_files: bool,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    aggregate_dir = output_dir / "distribution_update"
    plan = _json(output_dir / "probe_plan.json")
    _check_embedded_hash(plan, "plan_hash", "finance_phase1_probe_plan:")
    model_file_count = _verify_model_manifest(
        output_dir,
        plan,
        verify_live_model_files=verify_live_model_files,
    )
    baseline, workers = _verify_training_identities(output_dir, plan)
    input_manifest = _verify_input_manifest(aggregate_dir / "phase1_input_manifest.json")

    catalog = _typed_json(aggregate_dir / "three_state_catalog.json", TrajectoryStateCatalog)
    pi0 = _typed_json(
        aggregate_dir / "pi0_empirical_estimate.json",
        EmpiricalDistributionEstimate,
    )
    coverage = _typed_json(aggregate_dir / "coverage_prior.json", CoveragePrior)
    protocol = _typed_json(
        aggregate_dir / "contribution_protocol.json",
        ContributionProbeProtocol,
    )
    contribution = _typed_json(
        aggregate_dir / "contribution_manifest.json",
        ContributionEstimationManifest,
    )
    authorization = _typed_json(
        aggregate_dir / "contribution_production_authorization.json",
        ContributionProductionAuthorization,
    )
    update = _typed_json(
        aggregate_dir / "anchored_distribution_update.json",
        AnchoredDistributionUpdate,
    )
    materialization = _typed_json(
        aggregate_dir / "materialization_report.json",
        TrajectoryStateMaterializationReport,
    )
    observations = _typed_jsonl(
        aggregate_dir / "probe_observations.jsonl",
        ContributionProbeObservation,
    )
    artifacts = _typed_jsonl(
        aggregate_dir / "materialized_artifacts.jsonl",
        StateConditionedTrainingArtifact,
    )
    records = _typed_jsonl(
        aggregate_dir / "D1_materialized_training_records.jsonl",
        VTDOTrainingRecord,
    )

    support = set(catalog.states)
    supports = {
        "pi0": set(pi0.distribution.probabilities),
        "coverage": set(coverage.probabilities),
        "contribution": {item.state_id for item in contribution.estimates},
        "update_prior": set(update.prior_distribution.probabilities),
        "update_next": set(update.next_distribution.probabilities),
        "materialization": set(materialization.requested_state_counts),
    }
    _check(all(value == support for value in supports.values()), "VTDO supports diverge")
    _check(pi0.distribution == update.prior_distribution, "update is detached from empirical pi0")
    _check(coverage == update.coverage_prior, "update is detached from coverage prior")
    _check(contribution == update.contribution_manifest, "update crossed Contribution manifests")
    _check(
        authorization == update.contribution_production_authorization,
        "update crossed Contribution production authorizations",
    )
    _check(protocol.protocol_id == contribution.estimation_protocol_hash, "wrong Probe protocol")
    _check(
        materialization.source_distribution_id == update.next_distribution.distribution_id,
        "materialization is detached from pi1",
    )
    _check(
        tuple(materialization.artifacts) == artifacts,
        "standalone and embedded materialized artifacts differ",
    )

    observation_pairs = {(item.state_id, item.seed) for item in observations}
    expected_pairs = {
        (state_id, seed)
        for state_id in support
        for seed in protocol.probe_seeds
    }
    _check(observation_pairs == expected_pairs, "typed Probe observation matrix is incomplete")
    _check(
        all(item.probe_contract == protocol for item in observations),
        "Probe observations crossed protocols",
    )
    _check(
        len({item.observation_id for item in observations}) == len(observations),
        "duplicate observations",
    )

    artifact_ids = {item.artifact_id for item in artifacts}
    _check(len(artifact_ids) == len(artifacts), "duplicate materialized artifact identities")
    _check(
        len({item.decision_trace_hash for item in artifacts}) == len(artifacts),
        "materialization reused a decision trace",
    )
    _check(
        {item.source_artifact_id for item in records} == artifact_ids,
        "D1 records do not exactly cover materialized artifacts",
    )
    _check(len({item.record_id for item in records}) == len(records), "duplicate D1 records")
    _check(
        all(
            item.source_distribution_id == update.next_distribution.distribution_id
            for item in records
        ),
        "D1 records crossed source distributions",
    )

    probe_records = _typed_jsonl(Path(str(plan["records_path"])), VTDOTrainingRecord)
    probe_record_by_id = {item.record_id: item for item in probe_records}
    _check(len(probe_record_by_id) == len(probe_records), "duplicate Probe preparation records")
    baseline_ids = set(plan["baseline_record_ids"])
    validation_ids = set(plan["internal_validation_record_ids"])
    final_ids = set(plan["final_test_record_ids"])
    update_ids = {
        str(value["record_id"])
        for value in plan["probe_update_records_by_state"].values()
    }
    all_groups = (baseline_ids, validation_ids, final_ids, update_ids)
    _check(
        sum(len(group) for group in all_groups) == len(set().union(*all_groups)),
        "Probe train/validation/final/update record groups overlap",
    )
    _check(set(probe_record_by_id) == set().union(*all_groups), "unclassified Probe record")
    final_task_ids = {probe_record_by_id[record_id].task_id for record_id in final_ids}
    consumed_task_ids = {
        probe_record_by_id[record_id].task_id
        for record_id in baseline_ids | validation_ids | update_ids
    }
    _check(final_task_ids.isdisjoint(consumed_task_ids), "final-test task leaked into Probe use")
    _check(
        final_ids.isdisjoint({item.record_id for item in records}),
        "final-test record leaked into materialized D1",
    )
    isolation = protocol.data_isolation
    _check(
        set(isolation.baseline_training_instance_ids) == baseline_ids,
        "protocol baseline set differs from Probe plan",
    )
    _check(
        set(isolation.internal_validation_instance_ids) == validation_ids,
        "protocol validation set differs from Probe plan",
    )
    _check(
        set(isolation.final_test_instance_ids) == final_ids,
        "protocol final-test set differs from Probe plan",
    )

    summary = _json(output_dir / "finance_phase1_mvp_summary.json")
    _check_embedded_hash(summary, "report_hash", "finance_phase1_mvp:")
    _check(
        summary.get("input_manifest_hash") == input_manifest["manifest_hash"],
        "summary crossed input manifests",
    )
    _check(summary["pi0"] == pi0.distribution.probabilities, "summary pi0 is stale")
    _check(summary["pi1"] == update.next_distribution.probabilities, "summary pi1 is stale")
    _check(
        summary["contribution_production_authorization_id"]
        == authorization.authorization_id,
        "summary names another Contribution authorization",
    )
    _check(
        summary["contribution_analysis_report_hash"]
        == authorization.analysis_report_hash,
        "summary names another Contribution analysis",
    )
    _check(
        summary["untouched_final_test_record_ids"] == plan["final_test_record_ids"],
        "summary names another final-test set",
    )
    _check(
        summary["untouched_final_test_used_for_selection"] is False,
        "final-test set was declared used for selection",
    )

    artifact_manifest = _file_manifest(output_dir)
    (output_dir / "artifact_manifest.json").write_text(
        json.dumps(artifact_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    warnings = [
        "experiment remains partial: fewer than three real-model accepted states"
        if not summary["q1_three_real_states_passed"]
        else "",
        "real unconditioned Explorer covers less than the planned task-attempt grid"
        if summary["real_unconditioned_explorer_plan_coverage_rate"] < 1.0
        else "",
        "default energy profile is explicitly not production-ready"
        if not summary["default_energy_profile_production_ready"]
        else "",
        "Contribution authorization is population-level; this materialization covers one task",
        "D1 uses the controlled deterministic materializer, not a real LLM materializer",
    ]
    report: dict[str, Any] = {
        "artifact_integrity_status": "passed",
        "experiment_status": summary["status"],
        "experiment_version": summary["experiment_version"],
        "input_manifest_hash": input_manifest["manifest_hash"],
        "artifact_manifest_hash": artifact_manifest["manifest_hash"],
        "base_model_manifest_hash": plan["base_model_manifest_hash"],
        "base_model_live_files_verified": verify_live_model_files,
        "base_model_file_count": model_file_count,
        "beneficiary_checkpoint_hash": baseline["checkpoint_hash"],
        "probe_worker_count": len(workers),
        "catalog_state_count": len(support),
        "probe_observation_count": len(observations),
        "contribution_production_authorization_id": authorization.authorization_id,
        "contribution_analysis_report_hash": authorization.analysis_report_hash,
        "materialized_artifact_count": len(artifacts),
        "training_record_count": len(records),
        "unique_materialized_decision_trace_count": len(
            {item.decision_trace_hash for item in artifacts}
        ),
        "final_test_record_count": len(final_ids),
        "final_test_task_count": len(final_task_ids),
        "final_test_leakage_count": 0,
        "warnings": [item for item in warnings if item],
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_phase1_artifact_integrity_audit:",
    )
    (output_dir / "artifact_integrity_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit finance VTDO phase-one artifacts")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--verify-live-model-files", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = audit_phase1(
        Path(args.output_dir),
        verify_live_model_files=bool(args.verify_live_model_files),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
