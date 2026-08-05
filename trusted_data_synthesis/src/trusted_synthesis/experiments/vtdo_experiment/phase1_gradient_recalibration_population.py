from __future__ import annotations

import argparse
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_support import (
    _artifact_evidence_version_ids,
    _task_semantic_signature,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_calibration_population import (
    _read_json,
    _sha256,
    _write_json,
    _write_jsonl,
    balanced_partition_ids,
)
from trusted_synthesis.hashing import canonical_hash

RECALIBRATION_POPULATION_VERSION = "finance_gradient_calibration_population.v2"
PARTITION_NAMES = ("development", "validation", "sealed_candidate")
FRESH_PARTITION_NAMES = ("development", "validation")


def successor_partition_ids(
    rows: tuple[dict[str, str], ...],
    *,
    predecessor_report: dict[str, Any],
    sampling_salt: str,
) -> dict[str, tuple[str, ...]]:
    if predecessor_report.get("status") != "passed":
        raise ValueError("predecessor calibration population did not pass")
    if predecessor_report.get("sealed_candidate_outcomes_observed") is not False:
        raise ValueError("predecessor sealed candidate was already observed")
    partitions = predecessor_report.get("partitions")
    if not isinstance(partitions, dict) or set(partitions) != set(PARTITION_NAMES):
        raise ValueError("predecessor calibration partitions are incomplete")
    all_artifact_ids = {str(row["artifact_id"]) for row in rows}
    unused_ids = {str(value) for value in predecessor_report.get("unused_artifact_ids", ())}
    prior_selected_ids = {
        str(value)
        for partition in partitions.values()
        for value in partition["artifact_ids"]
    }
    if unused_ids & prior_selected_ids:
        raise ValueError("predecessor unused artifacts overlap selected artifacts")
    predecessor_ids = unused_ids | prior_selected_ids
    if not predecessor_ids <= all_artifact_ids:
        raise ValueError("predecessor artifacts are absent from the successor sources")
    supplemental_ids = all_artifact_ids - predecessor_ids
    fresh_candidate_ids = unused_ids | supplemental_ids
    reserve_rows = tuple(
        row for row in rows if row["artifact_id"] in fresh_candidate_ids
    )
    fresh = balanced_partition_ids(
        reserve_rows,
        partition_names=FRESH_PARTITION_NAMES,
        tasks_per_family_per_partition=1,
        sampling_salt=sampling_salt,
    )
    sealed_ids = tuple(
        sorted(
            str(value)
            for value in partitions["sealed_candidate"]["artifact_ids"]
        )
    )
    if set(fresh["development"]) & set(fresh["validation"]):
        raise ValueError("successor fresh partitions overlap")
    if (set(fresh["development"]) | set(fresh["validation"])) & set(sealed_ids):
        raise ValueError("successor fresh partitions overlap sealed candidate")
    return {
        "development": fresh["development"],
        "validation": fresh["validation"],
        "sealed_candidate": sealed_ids,
    }


def _partition_manifest(
    *,
    name: str,
    values: tuple[FinanceTaskStateArtifact, ...],
    artifact_ids: tuple[str, ...],
    output_path: Path,
) -> dict[str, Any]:
    task_ids = tuple(sorted(artifact.omega.task.task_id for artifact in values))
    evidence_ids = tuple(
        sorted(
            {
                evidence_id
                for artifact in values
                for evidence_id in _artifact_evidence_version_ids(artifact)
            }
        )
    )
    semantic_signatures = tuple(
        sorted(_task_semantic_signature(artifact) for artifact in values)
    )
    return {
        "artifact_ids": artifact_ids,
        "artifact_set_id": canonical_hash(
            artifact_ids,
            prefix="finance_gradient_calibration_artifact_set:",
        ),
        "task_ids": task_ids,
        "task_set_id": canonical_hash(
            task_ids,
            prefix="finance_gradient_calibration_task_set:",
        ),
        "task_type_counts": dict(
            sorted(
                Counter(
                    artifact.omega.task.public.task_type for artifact in values
                ).items()
            )
        ),
        "evidence_version_count": len(evidence_ids),
        "evidence_version_set_id": canonical_hash(
            evidence_ids,
            prefix="finance_gradient_calibration_evidence_set:",
        ),
        "semantic_signature_count": len(semantic_signatures),
        "semantic_signature_set_id": canonical_hash(
            semantic_signatures,
            prefix="finance_gradient_calibration_semantic_set:",
        ),
        "output_path": str(output_path),
        "output_sha256": _sha256(output_path),
        "partition_role": (
            "fresh_unobserved_calibration"
            if name in FRESH_PARTITION_NAMES
            else "inherited_unobserved_sealed_candidate"
        ),
    }


def build_successor_calibration_population(
    *,
    source_artifacts_path: Path,
    source_report_path: Path,
    predecessor_report_path: Path,
    output_dir: Path,
    sampling_salt: str,
    supplemental_artifacts_path: Path | None = None,
    supplemental_report_path: Path | None = None,
) -> dict[str, Any]:
    source_artifacts_path = source_artifacts_path.resolve()
    source_report_path = source_report_path.resolve()
    predecessor_report_path = predecessor_report_path.resolve()
    output_dir = output_dir.resolve()
    source_report = _read_json(source_report_path)
    predecessor_report = _read_json(predecessor_report_path)
    source_artifact_sha256 = _sha256(source_artifacts_path)
    if (supplemental_artifacts_path is None) != (supplemental_report_path is None):
        raise ValueError("supplemental calibration source contract is incomplete")
    supplemental_report: dict[str, Any] | None = None
    supplemental_artifact_sha256: str | None = None
    if supplemental_artifacts_path is not None and supplemental_report_path is not None:
        supplemental_artifacts_path = supplemental_artifacts_path.resolve()
        supplemental_report_path = supplemental_report_path.resolve()
        supplemental_report = _read_json(supplemental_report_path)
        supplemental_artifact_sha256 = _sha256(supplemental_artifacts_path)
        if supplemental_report.get("artifact_sha256") != supplemental_artifact_sha256:
            raise ValueError("supplemental calibration source artifact changed")
        if supplemental_report.get("status") != "passed":
            raise ValueError("supplemental calibration source report did not pass")
    if source_report.get("artifact_sha256") != source_artifact_sha256:
        raise ValueError("successor calibration source artifact changed")
    if source_report.get("status") != "passed":
        raise ValueError("successor calibration source report did not pass")
    if predecessor_report.get("source_artifact_sha256") != source_artifact_sha256:
        raise ValueError("predecessor calibration used another source artifact")
    artifacts = list(load_finance_multi_state_artifacts(source_artifacts_path))
    if supplemental_artifacts_path is not None:
        artifacts.extend(load_finance_multi_state_artifacts(supplemental_artifacts_path))
    artifact_tuple = tuple(artifacts)
    by_artifact_id = {artifact.artifact_id: artifact for artifact in artifact_tuple}
    if len(by_artifact_id) != len(artifact_tuple):
        raise ValueError("successor calibration source artifact ids are duplicated")
    rows = tuple(
        {
            "artifact_id": artifact.artifact_id,
            "task_id": artifact.omega.task.task_id,
            "task_type": artifact.omega.task.public.task_type,
        }
        for artifact in artifact_tuple
    )
    partition_ids = successor_partition_ids(
        rows,
        predecessor_report=predecessor_report,
        sampling_salt=sampling_salt,
    )
    partitions = {
        name: tuple(by_artifact_id[artifact_id] for artifact_id in partition_ids[name])
        for name in PARTITION_NAMES
    }
    task_sets = {
        name: {artifact.omega.task.task_id for artifact in values}
        for name, values in partitions.items()
    }
    evidence_sets = {
        name: {
            evidence_id
            for artifact in values
            for evidence_id in _artifact_evidence_version_ids(artifact)
        }
        for name, values in partitions.items()
    }
    semantic_sets = {
        name: {_task_semantic_signature(artifact) for artifact in values}
        for name, values in partitions.items()
    }
    for left, right in combinations(PARTITION_NAMES, 2):
        if task_sets[left] & task_sets[right]:
            raise ValueError("successor calibration task partitions overlap")
        if evidence_sets[left] & evidence_sets[right]:
            raise ValueError("successor calibration evidence partitions overlap")
        if semantic_sets[left] & semantic_sets[right]:
            raise ValueError("successor calibration semantic partitions overlap")

    manifests: dict[str, Any] = {}
    for name in PARTITION_NAMES:
        output_path = output_dir / f"{name}_task_states.jsonl"
        _write_jsonl(output_path, partitions[name])
        manifests[name] = _partition_manifest(
            name=name,
            values=partitions[name],
            artifact_ids=partition_ids[name],
            output_path=output_path,
        )
    selected_ids = {value for values in partition_ids.values() for value in values}
    predecessor_observed_ids = {
        str(value)
        for name in FRESH_PARTITION_NAMES
        for value in predecessor_report["partitions"][name]["artifact_ids"]
    }
    predecessor_sealed_ids = {
        str(value)
        for value in predecessor_report["partitions"]["sealed_candidate"][
            "artifact_ids"
        ]
    }
    fresh_source_ids = (
        set(by_artifact_id) - predecessor_observed_ids - predecessor_sealed_ids
    )
    selected_fresh_ids = (
        set(partition_ids["development"]) | set(partition_ids["validation"])
    )
    remaining_fresh_ids = fresh_source_ids - selected_fresh_ids
    report: dict[str, Any] = {
        "population_version": RECALIBRATION_POPULATION_VERSION,
        "source_population_report_id": source_report["report_id"],
        "source_population_schema_version": source_report["schema_version"],
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifact_sha256": source_artifact_sha256,
        "supplemental_source_artifacts_path": (
            str(supplemental_artifacts_path)
            if supplemental_artifacts_path is not None
            else None
        ),
        "supplemental_source_artifact_sha256": supplemental_artifact_sha256,
        "supplemental_source_report_id": (
            supplemental_report["report_id"]
            if supplemental_report is not None
            else None
        ),
        "supplemental_source_report_path": (
            str(supplemental_report_path)
            if supplemental_report_path is not None
            else None
        ),
        "supplemental_source_report_sha256": (
            _sha256(supplemental_report_path)
            if supplemental_report_path is not None
            else None
        ),
        "source_exclusion_artifact_set_id": source_report.get(
            "excluded_population_artifact_set_id"
        ),
        "predecessor_report_path": str(predecessor_report_path),
        "predecessor_report_sha256": _sha256(predecessor_report_path),
        "predecessor_report_hash": predecessor_report["report_hash"],
        "sampling_salt": sampling_salt,
        "partition_names": PARTITION_NAMES,
        "partitions": manifests,
        "selected_artifact_count": len(selected_ids),
        "unused_artifact_ids": tuple(sorted(remaining_fresh_ids)),
        "excluded_predecessor_observed_artifact_ids": tuple(
            sorted(predecessor_observed_ids)
        ),
        "inherited_sealed_candidate_artifact_ids": tuple(
            sorted(predecessor_sealed_ids)
        ),
        "cross_partition_task_overlap_count": 0,
        "cross_partition_evidence_overlap_count": 0,
        "cross_partition_semantic_overlap_count": 0,
        "development_validation_source": (
            "predecessor_unused_reserve_plus_disjoint_supplemental"
        ),
        "sealed_candidate_source": "predecessor_unobserved_sealed_candidate",
        "sealed_candidate_outcomes_observed": False,
        "status": "passed",
        "claim_boundary": (
            "Development and validation use only predecessor-unused or independently "
            "supplemental tasks. The inherited sealed candidate remains identity-frozen "
            "and outcome-unobserved."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_gradient_calibration_population:",
    )
    _write_json(output_dir / "report.json", report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze fresh successor numeric-calibration partitions"
    )
    parser.add_argument("--source-artifacts-path", required=True)
    parser.add_argument("--source-report-path", required=True)
    parser.add_argument("--predecessor-report-path", required=True)
    parser.add_argument("--supplemental-artifacts-path")
    parser.add_argument("--supplemental-report-path")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sampling-salt", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = build_successor_calibration_population(
        source_artifacts_path=Path(args.source_artifacts_path),
        source_report_path=Path(args.source_report_path),
        predecessor_report_path=Path(args.predecessor_report_path),
        output_dir=Path(args.output_dir),
        sampling_salt=str(args.sampling_salt),
        supplemental_artifacts_path=(
            Path(args.supplemental_artifacts_path)
            if args.supplemental_artifacts_path
            else None
        ),
        supplemental_report_path=(
            Path(args.supplemental_report_path)
            if args.supplemental_report_path
            else None
        ),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
