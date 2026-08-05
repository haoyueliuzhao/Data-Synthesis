from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
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
from trusted_synthesis.hashing import canonical_hash

CALIBRATION_POPULATION_VERSION = "finance_gradient_calibration_population.v1"
PARTITION_NAMES = ("development", "validation", "sealed_candidate")


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


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, values: tuple[FinanceTaskStateArtifact, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as sink:
        for value in values:
            sink.write(value.model_dump_json() + "\n")
    temporary.replace(path)


def balanced_partition_ids(
    rows: tuple[dict[str, str], ...],
    *,
    partition_names: tuple[str, ...] = PARTITION_NAMES,
    tasks_per_family_per_partition: int = 1,
    sampling_salt: str,
) -> dict[str, tuple[str, ...]]:
    if not rows or not partition_names or not sampling_salt.strip():
        raise ValueError("calibration population partition contract is incomplete")
    if tasks_per_family_per_partition < 1:
        raise ValueError("tasks per family and partition must be positive")
    task_ids = tuple(str(row["task_id"]) for row in rows)
    artifact_ids = tuple(str(row["artifact_id"]) for row in rows)
    if len(set(task_ids)) != len(task_ids) or len(set(artifact_ids)) != len(artifact_ids):
        raise ValueError("calibration population contains duplicate identities")
    groups: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        task_type = str(row["task_type"])
        if not task_type:
            raise ValueError("calibration population task family is empty")
        groups[task_type].append(row)
    required_per_family = len(partition_names) * tasks_per_family_per_partition
    for task_type, values in groups.items():
        if len(values) < required_per_family:
            raise ValueError(
                f"task family {task_type} has {len(values)} rows; "
                f"{required_per_family} are required"
            )
        values.sort(
            key=lambda row: (
                canonical_hash(
                    {
                        "sampling_salt": sampling_salt,
                        "task_type": task_type,
                        "artifact_id": row["artifact_id"],
                    },
                    prefix="finance_gradient_calibration_population_order:",
                ),
                row["artifact_id"],
            )
        )
    partitions: dict[str, list[str]] = {name: [] for name in partition_names}
    for task_type in sorted(groups):
        values = groups[task_type]
        cursor = 0
        for partition_name in partition_names:
            selected = values[cursor : cursor + tasks_per_family_per_partition]
            partitions[partition_name].extend(str(row["artifact_id"]) for row in selected)
            cursor += tasks_per_family_per_partition
    return {
        name: tuple(sorted(artifact_ids))
        for name, artifact_ids in partitions.items()
    }


def build_calibration_population(
    *,
    source_artifacts_path: Path,
    source_report_path: Path,
    output_dir: Path,
    sampling_salt: str,
    tasks_per_family_per_partition: int = 1,
) -> dict[str, Any]:
    source_artifacts_path = source_artifacts_path.resolve()
    source_report_path = source_report_path.resolve()
    output_dir = output_dir.resolve()
    source_report = _read_json(source_report_path)
    source_artifact_sha256 = _sha256(source_artifacts_path)
    if source_report.get("artifact_sha256") != source_artifact_sha256:
        raise ValueError("calibration population source artifact changed")
    if source_report.get("status") != "passed":
        raise ValueError("calibration population source report did not pass")
    artifacts = load_finance_multi_state_artifacts(source_artifacts_path)
    by_artifact_id = {artifact.artifact_id: artifact for artifact in artifacts}
    if len(by_artifact_id) != len(artifacts):
        raise ValueError("calibration population source artifact ids are duplicated")
    rows = tuple(
        {
            "artifact_id": artifact.artifact_id,
            "task_id": artifact.omega.task.task_id,
            "task_type": artifact.omega.task.public.task_type,
        }
        for artifact in artifacts
    )
    partition_ids = balanced_partition_ids(
        rows,
        tasks_per_family_per_partition=tasks_per_family_per_partition,
        sampling_salt=sampling_salt,
    )
    partitions = {
        name: tuple(by_artifact_id[artifact_id] for artifact_id in artifact_ids)
        for name, artifact_ids in partition_ids.items()
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
            raise ValueError("calibration task partitions overlap")
        if evidence_sets[left] & evidence_sets[right]:
            raise ValueError("calibration evidence partitions overlap")
        if semantic_sets[left] & semantic_sets[right]:
            raise ValueError("calibration semantic partitions overlap")

    output_paths: dict[str, str] = {}
    output_sha256s: dict[str, str] = {}
    partition_manifests: dict[str, Any] = {}
    selected_artifact_ids = {
        artifact_id for values in partition_ids.values() for artifact_id in values
    }
    for name, values in partitions.items():
        path = output_dir / f"{name}_task_states.jsonl"
        _write_jsonl(path, values)
        output_paths[name] = str(path)
        output_sha256s[name] = _sha256(path)
        partition_manifests[name] = {
            "artifact_ids": partition_ids[name],
            "artifact_set_id": canonical_hash(
                partition_ids[name],
                prefix="finance_gradient_calibration_artifact_set:",
            ),
            "task_ids": tuple(sorted(task_sets[name])),
            "task_set_id": canonical_hash(
                tuple(sorted(task_sets[name])),
                prefix="finance_gradient_calibration_task_set:",
            ),
            "task_type_counts": dict(
                sorted(
                    Counter(
                        artifact.omega.task.public.task_type
                        for artifact in values
                    ).items()
                )
            ),
            "evidence_version_count": len(evidence_sets[name]),
            "evidence_version_set_id": canonical_hash(
                tuple(sorted(evidence_sets[name])),
                prefix="finance_gradient_calibration_evidence_set:",
            ),
            "semantic_signature_count": len(semantic_sets[name]),
            "semantic_signature_set_id": canonical_hash(
                tuple(sorted(semantic_sets[name])),
                prefix="finance_gradient_calibration_semantic_set:",
            ),
            "output_path": str(path),
            "output_sha256": output_sha256s[name],
        }

    unused = tuple(
        sorted(
            artifact.artifact_id
            for artifact in artifacts
            if artifact.artifact_id not in selected_artifact_ids
        )
    )
    report: dict[str, Any] = {
        "population_version": CALIBRATION_POPULATION_VERSION,
        "source_population_report_id": source_report["report_id"],
        "source_population_schema_version": source_report["schema_version"],
        "source_artifacts_path": str(source_artifacts_path),
        "source_artifact_sha256": source_artifact_sha256,
        "source_exclusion_artifact_set_id": source_report.get(
            "excluded_population_artifact_set_id"
        ),
        "sampling_salt": sampling_salt,
        "tasks_per_family_per_partition": tasks_per_family_per_partition,
        "partition_names": PARTITION_NAMES,
        "partitions": partition_manifests,
        "selected_artifact_count": len(selected_artifact_ids),
        "unused_artifact_ids": unused,
        "cross_partition_task_overlap_count": 0,
        "cross_partition_evidence_overlap_count": 0,
        "cross_partition_semantic_overlap_count": 0,
        "sealed_candidate_outcomes_observed": False,
        "status": "passed",
        "claim_boundary": (
            "The sealed candidate partition is identity-frozen but must not be read by "
            "numeric profile selection or threshold calibration."
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
        description="Freeze family-balanced numeric calibration populations"
    )
    parser.add_argument("--source-artifacts-path", required=True)
    parser.add_argument("--source-report-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sampling-salt", required=True)
    parser.add_argument("--tasks-per-family-per-partition", type=int, default=1)
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = build_calibration_population(
        source_artifacts_path=Path(args.source_artifacts_path),
        source_report_path=Path(args.source_report_path),
        output_dir=Path(args.output_dir),
        sampling_salt=str(args.sampling_salt),
        tasks_per_family_per_partition=int(
            args.tasks_per_family_per_partition
        ),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
