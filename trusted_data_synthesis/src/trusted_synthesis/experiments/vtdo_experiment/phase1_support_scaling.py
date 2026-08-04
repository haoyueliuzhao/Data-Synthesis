from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _read_json,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

SUPPORT_SCALING_VERSION = "finance_objective_support_scaling.v1"
REQUIRED_SUPPORT_SIZES = (4, 8, 16, 32)
MINIMUM_GRADIENT_COSINE = 0.95
MINIMUM_TASK_RANK_SPEARMAN = 0.80
MINIMUM_WINNER_AGREEMENT = 0.80
MINIMUM_DIRECTION_AGREEMENT = 0.85


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("support-scaling vectors have incompatible support")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm > 0 or not right_norm > 0:
        raise ValueError("support-scaling vectors must be nonzero")
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def _ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        rank = (cursor + end - 1) / 2.0
        for index in range(cursor, end):
            result[indexed[index][0]] = rank
        cursor = end
    return result


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    left_rank = _ranks(left)
    right_rank = _ranks(right)
    left_mean = statistics.fmean(left_rank)
    right_mean = statistics.fmean(right_rank)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left_rank, right_rank, strict=True)
    )
    left_scale = math.sqrt(sum((value - left_mean) ** 2 for value in left_rank))
    right_scale = math.sqrt(sum((value - right_mean) ** 2 for value in right_rank))
    if not left_scale > 0 or not right_scale > 0:
        return 0.0
    return numerator / (left_scale * right_scale)


def _direction_agreement(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("support-scaling directions have incompatible support")

    def sign(value: float) -> int:
        return 0 if abs(value) <= 1e-12 else (1 if value > 0 else -1)

    return statistics.fmean(
        float(sign(a) == sign(b)) for a, b in zip(left, right, strict=True)
    )


def _bootstrap_ci(
    values: Sequence[float],
    *,
    seed: int,
    samples: int = 2000,
) -> tuple[float, float]:
    if not values:
        raise ValueError("support-scaling bootstrap requires values")
    randomizer = random.Random(seed)
    estimates = sorted(
        statistics.fmean(randomizer.choice(values) for _ in values)
        for _ in range(samples)
    )
    return estimates[int(0.025 * (samples - 1))], estimates[int(0.975 * (samples - 1))]


def analyze_support_scaling(
    *,
    gradient_vectors: Mapping[int, Sequence[float]],
    state_rows: Mapping[int, Sequence[Mapping[str, Any]]],
    source_manifest_hashes: Mapping[int, str],
) -> dict[str, Any]:
    if tuple(sorted(gradient_vectors)) != REQUIRED_SUPPORT_SIZES:
        raise ValueError("support scaling requires the preregistered 4/8/16/32 grid")
    if set(state_rows) != set(REQUIRED_SUPPORT_SIZES) or set(source_manifest_hashes) != set(
        REQUIRED_SUPPORT_SIZES
    ):
        raise ValueError("support-scaling manifests do not cover the size grid")
    maximum_size = REQUIRED_SUPPORT_SIZES[-1]
    reference_vector = tuple(float(value) for value in gradient_vectors[maximum_size])
    reference_rows = {
        (str(row["task_id"]), str(row["state_id"])): row
        for row in state_rows[maximum_size]
    }
    if not reference_rows:
        raise ValueError("support scaling has no state population")
    if len(reference_rows) != len(state_rows[maximum_size]):
        raise ValueError("support scaling contains duplicate task states")
    rows_by_task_reference: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in reference_rows.values():
        rows_by_task_reference[str(row["task_id"])].append(row)
    size_rows: list[dict[str, Any]] = []
    task_type_rows: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    for size in REQUIRED_SUPPORT_SIZES:
        current = {
            (str(row["task_id"]), str(row["state_id"])): row
            for row in state_rows[size]
        }
        if set(current) != set(reference_rows) or len(current) != len(state_rows[size]):
            raise ValueError("support scaling changes the task-state population")
        task_spearman = []
        task_winner = []
        task_direction = []
        for task_id, reference_task_rows in sorted(rows_by_task_reference.items()):
            ordered_reference = sorted(
                reference_task_rows,
                key=lambda row: str(row["state_id"]),
            )
            ordered_current = [
                current[(task_id, str(row["state_id"]))]
                for row in ordered_reference
            ]
            reference_values = [float(row["gp_c_proxy"]) for row in ordered_reference]
            current_values = [float(row["gp_c_proxy"]) for row in ordered_current]
            spearman = _spearman(current_values, reference_values)
            winner = float(
                max(range(len(current_values)), key=current_values.__getitem__)
                == max(range(len(reference_values)), key=reference_values.__getitem__)
            )
            direction = _direction_agreement(current_values, reference_values)
            task_spearman.append(spearman)
            task_winner.append(winner)
            task_direction.append(direction)
            task_type = str(ordered_reference[0].get("task_type", "unknown"))
            task_type_rows[task_type].append(
                {
                    "support_size": float(size),
                    "spearman": spearman,
                    "winner_agreement": winner,
                    "direction_agreement": direction,
                }
            )
        gradient_cosine = _cosine(
            tuple(float(value) for value in gradient_vectors[size]),
            reference_vector,
        )
        macro_spearman = statistics.fmean(task_spearman)
        winner_agreement = statistics.fmean(task_winner)
        direction_agreement = statistics.fmean(task_direction)
        size_rows.append(
            {
                "support_size": size,
                "source_manifest_hash": source_manifest_hashes[size],
                "aggregate_objective_gradient_cosine_to_32": gradient_cosine,
                "macro_task_rank_spearman_to_32": macro_spearman,
                "macro_task_rank_spearman_ci95": _bootstrap_ci(
                    task_spearman,
                    seed=20261100 + size,
                ),
                "winner_agreement_to_32": winner_agreement,
                "gp_c_direction_agreement_to_32": direction_agreement,
                "passes_stability_gate": bool(
                    size >= 16
                    and gradient_cosine >= MINIMUM_GRADIENT_COSINE
                    and macro_spearman >= MINIMUM_TASK_RANK_SPEARMAN
                    and winner_agreement >= MINIMUM_WINNER_AGREEMENT
                    and direction_agreement >= MINIMUM_DIRECTION_AGREEMENT
                ),
            }
        )
    task_type_summary = {
        task_type: {
            str(size): {
                "task_count": len(
                    [row for row in rows if int(row["support_size"]) == size]
                ),
                "mean_spearman": statistics.fmean(
                    row["spearman"]
                    for row in rows
                    if int(row["support_size"]) == size
                ),
                "winner_agreement": statistics.fmean(
                    row["winner_agreement"]
                    for row in rows
                    if int(row["support_size"]) == size
                ),
                "direction_agreement": statistics.fmean(
                    row["direction_agreement"]
                    for row in rows
                    if int(row["support_size"]) == size
                ),
            }
            for size in REQUIRED_SUPPORT_SIZES
        }
        for task_type, rows in sorted(task_type_rows.items())
    }
    production_candidates = [
        int(row["support_size"])
        for row in size_rows
        if row["passes_stability_gate"]
    ]
    selected_support_size = min(production_candidates) if production_candidates else None
    report: dict[str, Any] = {
        "experiment_version": SUPPORT_SCALING_VERSION,
        "artifact_type": "ObjectiveSupportScalingReport",
        "support_sizes": REQUIRED_SUPPORT_SIZES,
        "source_manifest_hashes": dict(sorted(source_manifest_hashes.items())),
        "thresholds": {
            "minimum_gradient_cosine": MINIMUM_GRADIENT_COSINE,
            "minimum_task_rank_spearman": MINIMUM_TASK_RANK_SPEARMAN,
            "minimum_winner_agreement": MINIMUM_WINNER_AGREEMENT,
            "minimum_direction_agreement": MINIMUM_DIRECTION_AGREEMENT,
            "minimum_production_support_size": 16,
        },
        "size_rows": size_rows,
        "task_type_stratified_metrics": task_type_summary,
        "selected_minimum_support_size": selected_support_size,
        "status": "passed" if selected_support_size is not None else "failed",
        "claim_boundary": (
            "This report selects objective-support size for the frozen local GP-C estimand. "
            "It is not evidence for full Student-training utility."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_objective_support_scaling_report:",
    )
    return report


def _run(args: argparse.Namespace) -> None:
    payload = _read_json(Path(args.input_path).resolve())
    report = analyze_support_scaling(
        gradient_vectors={
            int(size): values for size, values in payload["gradient_vectors"].items()
        },
        state_rows={int(size): values for size, values in payload["state_rows"].items()},
        source_manifest_hashes={
            int(size): str(value)
            for size, value in payload["source_manifest_hashes"].items()
        },
    )
    output_path = Path(args.output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze GP-C stability on the 4/8/16/32 objective-support grid"
    )
    parser.add_argument("--input-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.set_defaults(handler=_run)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
