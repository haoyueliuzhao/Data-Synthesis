from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from trusted_synthesis.hashing import canonical_hash

TAIL_ANALYSIS_VERSION = "finance_gradient_projection_tail_analysis.v1"
WORKER_RESULT_HASH_PREFIX = "finance_contribution_gradient_result:"


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


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot summarize an empty metric")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("quantile probability must lie in [0, 1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + weight * (ordered[upper] - ordered[lower])


def _metric_summary(
    rows: list[dict[str, Any]],
    *,
    field: str,
    threshold: float,
    direction: str,
) -> dict[str, Any]:
    values = [float(row[field]) for row in rows]
    if direction == "maximum":
        violated = [row for row in rows if float(row[field]) > threshold]
    elif direction == "minimum":
        violated = [row for row in rows if float(row[field]) < threshold]
    else:
        raise ValueError(f"unknown threshold direction:{direction}")
    return {
        "field": field,
        "direction": direction,
        "threshold": threshold,
        "count": len(values),
        "violation_count": len(violated),
        "violation_rate": len(violated) / len(values),
        "minimum": min(values),
        "p50": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
        "p99": _quantile(values, 0.99),
        "maximum": max(values),
    }


def _threshold_predicate(
    *,
    field: str,
    threshold: float,
    direction: str,
) -> Callable[[dict[str, Any]], bool]:
    if direction == "maximum":

        def exceeds_maximum(row: dict[str, Any]) -> bool:
            return float(row[field]) > threshold

        return exceeds_maximum
    if direction == "minimum":

        def falls_below_minimum(row: dict[str, Any]) -> bool:
            return float(row[field]) < threshold

        return falls_below_minimum
    raise ValueError(f"unknown threshold direction:{direction}")


def _differential_token_bucket(value: float) -> str:
    if value < 0.025:
        return "lt_0.025"
    if value < 0.05:
        return "0.025_to_0.05"
    if value < 0.10:
        return "0.05_to_0.10"
    if value < 0.20:
        return "0.10_to_0.20"
    return "ge_0.20"


def _supervised_token_bucket(value: int) -> str:
    if value < 2500:
        return "lt_2500"
    if value < 3500:
        return "2500_to_3499"
    if value < 4500:
        return "3500_to_4499"
    return "ge_4500"


def _load_worker_rows(output_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    worker_summary = _read_json(output_dir / "worker_summary.json")
    partitions = sorted((output_dir / "workers").glob("partition_*.jsonl"))
    if not partitions:
        raise ValueError("Gradient Projection tail analysis found no active worker partitions")
    rows: list[dict[str, Any]] = []
    for path in partitions:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"worker row is not an object:{path}")
                rows.append(value)
    return rows, worker_summary


def _artifact_references(
    output_dir: Path,
    report: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[dict[str, str], str]:
    references: dict[str, str] = {}

    def add(path_value: Any, sha_value: Any) -> None:
        path = Path(str(path_value))
        sha256 = str(sha_value)
        previous = references.setdefault(str(path), sha256)
        if previous != sha256:
            raise ValueError(f"one gradient artifact has conflicting hashes:{path}")

    for row in rows:
        add(row["state_gradient_file"], row["state_gradient_sha256"])
        add(row["common_token_gradient_file"], row["common_token_gradient_sha256"])
        add(row["differential_token_gradient_file"], row["differential_token_gradient_sha256"])
    for row in report["state_rows"]:
        add(row["state_gradient_file"], row["state_gradient_sha256"])
    for row in report["task_gradient_artifacts"]:
        add(row["file"], row["sha256"])
    add(
        report["global_gradient_artifact"]["file"],
        report["global_gradient_artifact"]["sha256"],
    )
    evaluation_manifest = _read_json(output_dir / "evaluation_gradient_manifest.json")
    evaluation_manifest_hash = _replay_hash(
        evaluation_manifest,
        field="manifest_hash",
        prefix="finance_contribution_evaluation_gradient_manifest:",
    )
    if evaluation_manifest_hash != report["evaluation_gradient_manifest_hash"]:
        raise ValueError("evaluation gradient manifest differs from the aggregate report")
    for row in (
        list(evaluation_manifest["record_gradients"])
        + list(evaluation_manifest["aggregate_gradients"])
    ):
        add(row["file"], row["sha256"])
    return references, evaluation_manifest_hash


def _validate_integrity(
    output_dir: Path,
    *,
    plan: dict[str, Any],
    report: dict[str, Any],
    rows: list[dict[str, Any]],
    worker_summary: dict[str, Any],
    rehash_artifacts: bool,
) -> dict[str, Any]:
    plan_hash = _replay_hash(
        plan,
        field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
    )
    report_hash = _replay_hash(
        report,
        field="report_hash",
        prefix="finance_contribution_gradient_report:",
    )
    if report["plan_hash"] != plan_hash or worker_summary.get("plan_hash") != plan_hash:
        raise ValueError("Gradient Projection plan identity differs across artifacts")
    expected_jobs = {str(row["job_id"]) for row in plan["jobs"]}
    observed_jobs: set[str] = set()
    observed_results: set[str] = set()
    partition_count = len(worker_summary.get("workers", ()))
    if partition_count < 1:
        raise ValueError("worker summary has no partitions")
    for row in rows:
        _replay_hash(row, field="result_hash", prefix=WORKER_RESULT_HASH_PREFIX)
        job_id = str(row["job_id"])
        if job_id in observed_jobs:
            raise ValueError(f"duplicate active worker job:{job_id}")
        observed_jobs.add(job_id)
        result_hash = str(row["result_hash"])
        if result_hash in observed_results:
            raise ValueError(f"duplicate active worker result:{result_hash}")
        observed_results.add(result_hash)
        if row.get("status") != "passed":
            raise ValueError(f"active worker result did not pass:{job_id}")
        if row.get("plan_hash") != plan_hash:
            raise ValueError(f"worker result belongs to another plan:{job_id}")
        if int(row.get("partition_count", -1)) != partition_count:
            raise ValueError(f"worker result has another partition contract:{job_id}")
    if observed_jobs != expected_jobs:
        raise ValueError("active worker results do not exactly cover the frozen job set")
    if len(rows) != int(report["state_realization_count"]):
        raise ValueError("worker result count differs from the aggregate report")
    if len({(str(row["task_id"]), str(row["state_id"])) for row in rows}) != int(
        report["state_count"]
    ):
        raise ValueError("worker state support differs from the aggregate report")
    if len({str(row["task_id"]) for row in rows}) != int(report["task_count"]):
        raise ValueError("worker task support differs from the aggregate report")
    references, evaluation_manifest_hash = _artifact_references(output_dir, report, rows)
    missing = [path for path in references if not Path(path).is_file()]
    if missing:
        raise ValueError(f"referenced gradient artifacts are missing:{missing[:3]}")
    content_failures: list[str] = []
    if rehash_artifacts:
        content_failures = [
            path for path, expected in references.items() if _sha256(Path(path)) != expected
        ]
        if content_failures:
            raise ValueError(f"gradient content hash replay failed:{content_failures[:3]}")
    return {
        "status": "passed",
        "plan_hash": plan_hash,
        "report_hash": report_hash,
        "evaluation_gradient_manifest_hash": evaluation_manifest_hash,
        "worker_result_count": len(rows),
        "worker_result_identity_pass_count": len(rows),
        "expected_job_count": len(expected_jobs),
        "unique_job_count": len(observed_jobs),
        "unique_result_hash_count": len(observed_results),
        "referenced_gradient_artifact_count": len(references),
        "referenced_gradient_artifact_exists_count": len(references),
        "artifact_content_hash_replay_requested": rehash_artifacts,
        "artifact_content_hash_pass_count": len(references) if rehash_artifacts else None,
        "artifact_content_hash_failure_count": len(content_failures),
    }


def _violation_slices(
    rows: list[dict[str, Any]],
    predicates: dict[str, Callable[[dict[str, Any]], bool]],
) -> dict[str, Any]:
    labels_by_job = {
        str(row["job_id"]): tuple(name for name, predicate in predicates.items() if predicate(row))
        for row in rows
    }
    violating_jobs = {job_id for job_id, labels in labels_by_job.items() if labels}

    def grouped(key: Callable[[dict[str, Any]], str]) -> dict[str, Any]:
        groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[key(row)].append(row)
        result: dict[str, Any] = {}
        for name, values in sorted(groups.items()):
            ids = {str(row["job_id"]) for row in values}
            result[name] = {
                "count": len(values),
                "any_violation_count": len(ids & violating_jobs),
                "any_violation_rate": len(ids & violating_jobs) / len(values),
                "violation_counts": {
                    label: sum(predicate(row) for row in values)
                    for label, predicate in predicates.items()
                },
            }
        return result

    violation_sets = {
        name: {str(row["job_id"]) for row in rows if predicate(row)}
        for name, predicate in predicates.items()
    }
    overlap = {
        left: {
            right: len(violation_sets[left] & violation_sets[right])
            for right in violation_sets
        }
        for left in violation_sets
    }
    state_violations: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if str(row["job_id"]) in violating_jobs:
            state_violations[(str(row["task_id"]), str(row["state_id"]))] += 1
    worst_rows = sorted(
        (row for row in rows if str(row["job_id"]) in violating_jobs),
        key=lambda row: (
            -float(row["token_gradient_recomposition_relative_error"]),
            -float(row["numeric_gp_score_absolute_delta"]),
            str(row["job_id"]),
        ),
    )
    return {
        "any_violation_count": len(violating_jobs),
        "any_violation_rate": len(violating_jobs) / len(rows),
        "violation_overlap": overlap,
        "violating_state_count": len(state_violations),
        "by_task_type": grouped(lambda row: str(row["task_type"])),
        "by_differential_supervised_token_fraction": grouped(
            lambda row: _differential_token_bucket(
                float(row["differential_supervised_token_fraction"])
            )
        ),
        "by_supervised_token_count": grouped(
            lambda row: _supervised_token_bucket(int(row["state_supervised_tokens"]))
        ),
        "violating_rows": [
            {
                "job_id": str(row["job_id"]),
                "task_id": str(row["task_id"]),
                "task_type": str(row["task_type"]),
                "state_id": str(row["state_id"]),
                "realization_index": int(row["realization_index"]),
                "violations": labels_by_job[str(row["job_id"])],
                "differential_supervised_token_fraction": float(
                    row["differential_supervised_token_fraction"]
                ),
                "state_supervised_tokens": int(row["state_supervised_tokens"]),
                "token_gradient_recomposition_relative_error": float(
                    row["token_gradient_recomposition_relative_error"]
                ),
                "token_gradient_recomposition_cosine": float(
                    row["token_gradient_recomposition_cosine"]
                ),
                "numeric_gp_score_absolute_delta": float(
                    row["numeric_gp_score_absolute_delta"]
                ),
            }
            for row in worst_rows
        ],
    }


def _rank_flip_details(
    rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_task_state: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task_state[(str(row["task_id"]), str(row["state_id"]))].append(row)
    details: list[dict[str, Any]] = []
    for task_row in task_rows:
        if float(task_row["rank_agreement"]) >= 1.0:
            continue
        task_id = str(task_row["task_id"])
        states: list[dict[str, Any]] = []
        for (row_task_id, state_id), values in by_task_state.items():
            if row_task_id != task_id:
                continue
            states.append(
                {
                    "state_id": state_id,
                    "full_gp_score": statistics.fmean(
                        float(row["numeric_full_gp_score"]) for row in values
                    ),
                    "recomposed_gp_score": statistics.fmean(
                        float(row["numeric_recomposed_gp_score"]) for row in values
                    ),
                }
            )
        full_order = sorted(states, key=lambda row: (-row["full_gp_score"], row["state_id"]))
        recomposed_order = sorted(
            states,
            key=lambda row: (-row["recomposed_gp_score"], row["state_id"]),
        )
        adjacent_margins = [
            abs(full_order[index]["full_gp_score"] - full_order[index + 1]["full_gp_score"])
            for index in range(len(full_order) - 1)
        ]
        details.append(
            {
                "task_id": task_id,
                "task_type": next(
                    str(row["task_type"]) for row in rows if str(row["task_id"]) == task_id
                ),
                "state_count": len(states),
                "full_order": tuple(row["state_id"] for row in full_order),
                "recomposed_order": tuple(row["state_id"] for row in recomposed_order),
                "minimum_adjacent_full_score_margin": min(adjacent_margins),
                "maximum_state_mean_score_delta": max(
                    abs(row["full_gp_score"] - row["recomposed_gp_score"])
                    for row in states
                ),
                "states": sorted(states, key=lambda row: row["state_id"]),
            }
        )
    return details


def analyze_gradient_projection_tail(
    output_dir: Path,
    *,
    rehash_artifacts: bool = False,
) -> dict[str, Any]:
    plan = _read_json(output_dir / "plan.json")
    report = _read_json(output_dir / "report.json")
    rows, worker_summary = _load_worker_rows(output_dir)
    integrity = _validate_integrity(
        output_dir,
        plan=plan,
        report=report,
        rows=rows,
        worker_summary=worker_summary,
        rehash_artifacts=rehash_artifacts,
    )
    thresholds = {
        str(key): float(value)
        for key, value in report["gradient_numeric_precision"]["thresholds"].items()
    }
    record_specs = {
        "loss_identity": (
            "loss_identity_absolute_error",
            thresholds["maximum_loss_identity_absolute_error"],
            "maximum",
        ),
        "token_recomposition_relative_error": (
            "token_gradient_recomposition_relative_error",
            thresholds["maximum_token_gradient_recomposition_relative_error"],
            "maximum",
        ),
        "token_recomposition_cosine": (
            "token_gradient_recomposition_cosine",
            thresholds["minimum_token_gradient_recomposition_cosine"],
            "minimum",
        ),
        "gp_score_absolute_delta": (
            "numeric_gp_score_absolute_delta",
            thresholds["maximum_gp_score_absolute_delta"],
            "maximum",
        ),
    }
    predicates: dict[str, Callable[[dict[str, Any]], bool]] = {}
    metric_summaries: dict[str, Any] = {}
    for name, (field, threshold, direction) in record_specs.items():
        predicates[name] = _threshold_predicate(
            field=field,
            threshold=threshold,
            direction=direction,
        )
        metric_summaries[name] = _metric_summary(
            rows,
            field=field,
            threshold=threshold,
            direction=direction,
        )
    numeric_task_rows = list(report["gradient_numeric_precision"]["task_rows"])
    task_metric_specs = {
        "rank_agreement": (
            "rank_agreement",
            thresholds["minimum_task_rank_agreement"],
            "minimum",
        ),
        "update_total_variation": (
            "update_total_variation",
            thresholds["maximum_update_total_variation"],
            "maximum",
        ),
        "update_jensen_shannon": (
            "update_jensen_shannon",
            thresholds["maximum_update_jensen_shannon"],
            "maximum",
        ),
    }
    task_metric_summaries = {
        name: _metric_summary(
            numeric_task_rows,
            field=field,
            threshold=threshold,
            direction=direction,
        )
        for name, (field, threshold, direction) in task_metric_specs.items()
    }
    contribution_by_type: dict[str, Any] = {}
    grouped_task_rows: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in report["task_rows"]:
        grouped_task_rows[str(row["task_type"])].append(row)
    for task_type, values in sorted(grouped_task_rows.items()):
        contribution_by_type[task_type] = {
            "task_count": len(values),
            "mean_spearman": statistics.fmean(float(row["spearman"]) for row in values),
            "mean_pairwise_concordance": statistics.fmean(
                float(row["pairwise_concordance"]) for row in values
            ),
            "winner_agreement_rate": statistics.fmean(
                float(row["winner_agreement"]) for row in values
            ),
        }
    tail = {
        "analysis_version": TAIL_ANALYSIS_VERSION,
        "source": {
            "experiment_version": report["experiment_version"],
            "run_role": report["run_role"],
            "plan_hash": plan["plan_hash"],
            "report_hash": report["report_hash"],
            "numeric_contract_hash": report["numeric_contract_hash"],
            "task_count": report["task_count"],
            "state_count": report["state_count"],
            "state_realization_count": report["state_realization_count"],
        },
        "integrity": integrity,
        "record_level_numeric_tail": {
            "metrics": metric_summaries,
            "slices": _violation_slices(rows, predicates),
        },
        "task_level_numeric_tail": {
            "metrics": task_metric_summaries,
            "rank_flip_details": _rank_flip_details(rows, numeric_task_rows),
        },
        "sampling_stability": report["gradient_realization_sampling_stability"],
        "contribution_validation": {
            "macro_task_spearman": report["macro_task_spearman"],
            "macro_task_spearman_ci95": report["macro_task_spearman_ci95"],
            "macro_spearman_p_value": report["macro_spearman_p_value"],
            "macro_pairwise_concordance": report["macro_pairwise_concordance"],
            "macro_pairwise_concordance_ci95": report[
                "macro_pairwise_concordance_ci95"
            ],
            "macro_pairwise_concordance_p_value": report[
                "macro_pairwise_concordance_p_value"
            ],
            "winner_agreement_rate": report["winner_agreement_rate"],
            "by_task_type": contribution_by_type,
        },
        "production_decision": {
            "aggregate_status": report["status"],
            "production_authorized": report["production_authorized"],
            "blockers": report["blockers"],
            "downstream_experiments_permitted": False,
            "reason": (
                "The immutable production numeric contract failed. GP-C and the independent "
                "distribution intervention must remain closed for this plan."
            ),
            "thresholds_changed_after_observation": False,
        },
    }
    tail["analysis_hash"] = canonical_hash(
        tail,
        prefix="finance_gradient_projection_tail_analysis:",
    )
    return tail


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay and slice a frozen Gradient Projection production candidate"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--analysis-path")
    parser.add_argument("--rehash-artifacts", action="store_true")
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    report = analyze_gradient_projection_tail(
        output_dir,
        rehash_artifacts=bool(args.rehash_artifacts),
    )
    analysis_path = (
        Path(args.analysis_path).resolve()
        if args.analysis_path
        else output_dir / "tail_analysis.json"
    )
    _write_json(analysis_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
