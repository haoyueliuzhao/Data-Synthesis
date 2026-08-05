from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_tail_analysis import (
    _load_worker_rows,
    _read_json,
    _replay_hash,
    _validate_integrity,
)
from trusted_synthesis.hashing import canonical_hash

NUMERIC_VALIDATION_VERSION = "finance_gradient_numeric_validation.v1"
MARGIN_ORDERING_VERSION = "finance_gradient_margin_aware_ordering.v1"
RETROSPECTIVE_ENVELOPE_GRID = (
    0.0,
    0.00025,
    0.0005,
    0.001,
    0.0015,
    0.002,
    0.003,
)


@dataclass(frozen=True)
class MarginOrderingPolicy:
    policy_version: str = MARGIN_ORDERING_VERSION
    state_error_aggregation: str = "maximum_absolute_state_mean_score_error"
    pair_error_multiplier: float = 2.0
    envelope_quantization: float = 0.0001
    maximum_pairwise_uncertainty_envelope: float = 0.005
    minimum_resolvable_pair_fraction: float = 0.50
    minimum_resolvable_task_fraction: float = 0.80
    maximum_resolvable_pair_violation_count: int = 0
    maximum_resolvable_winner_violation_count: int = 0


DEFAULT_MARGIN_ORDERING_POLICY = MarginOrderingPolicy()


def _ceil_to(value: float, quantum: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError("numeric uncertainty must be finite and non-negative")
    if not math.isfinite(quantum) or quantum <= 0:
        raise ValueError("numeric uncertainty quantization must be positive")
    return math.ceil(value / quantum - 1e-12) * quantum


def _task_state_mean_scores(
    rows: list[dict[str, Any]],
    *,
    full_score_field: str,
    recomposed_score_field: str,
) -> dict[str, dict[str, dict[str, Any]]]:
    if not rows:
        raise ValueError("margin-aware ordering requires result rows")
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    task_types: dict[str, str] = {}
    for row in rows:
        task_id = str(row.get("task_id") or "")
        state_id = str(row.get("state_id") or "")
        task_type = str(row.get("task_type") or "")
        if not task_id or not state_id or not task_type:
            raise ValueError("margin-aware ordering row identity is incomplete")
        for field in (full_score_field, recomposed_score_field):
            value = float(row[field])
            if not math.isfinite(value):
                raise ValueError(f"margin-aware ordering score is non-finite:{field}")
        previous = task_types.setdefault(task_id, task_type)
        if previous != task_type:
            raise ValueError("one task has multiple task types")
        grouped[(task_id, state_id)].append(row)

    by_task: defaultdict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for (task_id, state_id), values in sorted(grouped.items()):
        by_task[task_id][state_id] = {
            "state_id": state_id,
            "realization_count": len(values),
            "full_score": statistics.fmean(
                float(row[full_score_field]) for row in values
            ),
            "recomposed_score": statistics.fmean(
                float(row[recomposed_score_field]) for row in values
            ),
            "task_type": task_types[task_id],
        }
    if any(len(states) < 2 for states in by_task.values()):
        raise ValueError("margin-aware ordering requires at least two states per task")
    return dict(by_task)


def derive_pairwise_uncertainty_envelope(
    rows: list[dict[str, Any]],
    *,
    full_score_field: str = "full_gp_score",
    recomposed_score_field: str = "recomposed_gp_score",
    policy: MarginOrderingPolicy = DEFAULT_MARGIN_ORDERING_POLICY,
) -> dict[str, Any]:
    by_task = _task_state_mean_scores(
        rows,
        full_score_field=full_score_field,
        recomposed_score_field=recomposed_score_field,
    )
    state_errors = [
        abs(float(state["full_score"]) - float(state["recomposed_score"]))
        for states in by_task.values()
        for state in states.values()
    ]
    maximum_state_error = max(state_errors)
    raw_envelope = policy.pair_error_multiplier * maximum_state_error
    envelope = _ceil_to(raw_envelope, policy.envelope_quantization)
    passed = envelope <= policy.maximum_pairwise_uncertainty_envelope
    return {
        "policy": asdict(policy),
        "task_count": len(by_task),
        "state_count": len(state_errors),
        "maximum_absolute_state_mean_score_error": maximum_state_error,
        "raw_pairwise_uncertainty_envelope": raw_envelope,
        "pairwise_uncertainty_envelope": envelope,
        "status": "passed" if passed else "failed",
        "failure_reasons": (
            ()
            if passed
            else ("pairwise_uncertainty_envelope_exceeds_preregistered_cap",)
        ),
    }


def _ordered_state_ids(
    states: dict[str, dict[str, Any]],
    *,
    score_key: str,
) -> tuple[str, ...]:
    return tuple(
        state_id
        for state_id, _ in sorted(
            states.items(),
            key=lambda item: (-float(item[1][score_key]), item[0]),
        )
    )


def _evaluate_task_ordering(
    task_id: str,
    states: dict[str, dict[str, Any]],
    *,
    uncertainty_envelope: float,
) -> dict[str, Any]:
    full_order = _ordered_state_ids(states, score_key="full_score")
    recomposed_order = _ordered_state_ids(states, score_key="recomposed_score")
    pair_rows: list[dict[str, Any]] = []
    for left_id, right_id in itertools.combinations(sorted(states), 2):
        left = states[left_id]
        right = states[right_id]
        full_margin = float(left["full_score"]) - float(right["full_score"])
        recomposed_margin = float(left["recomposed_score"]) - float(
            right["recomposed_score"]
        )
        resolvable = abs(full_margin) > uncertainty_envelope
        direction_agrees = (
            full_margin * recomposed_margin > 0 if resolvable else None
        )
        pair_rows.append(
            {
                "left_state_id": left_id,
                "right_state_id": right_id,
                "full_score_margin": full_margin,
                "recomposed_score_margin": recomposed_margin,
                "absolute_full_score_margin": abs(full_margin),
                "resolvable": resolvable,
                "direction_agrees": direction_agrees,
            }
        )

    resolvable_rows = [row for row in pair_rows if bool(row["resolvable"])]
    violations = [
        row for row in resolvable_rows if row["direction_agrees"] is not True
    ]
    winner_id = full_order[0]
    recomposed_winner_id = recomposed_order[0]
    runner_up_id = full_order[1]
    winner_margin = (
        float(states[winner_id]["full_score"])
        - float(states[runner_up_id]["full_score"])
    )
    winner_resolvable = winner_margin > uncertainty_envelope
    winner_agrees = winner_id == recomposed_winner_id
    return {
        "task_id": task_id,
        "task_type": str(next(iter(states.values()))["task_type"]),
        "state_count": len(states),
        "pair_count": len(pair_rows),
        "resolvable_pair_count": len(resolvable_rows),
        "resolvable_pair_fraction": len(resolvable_rows) / len(pair_rows),
        "resolvable_pair_violation_count": len(violations),
        "resolvable_pair_direction_agreement": (
            1.0 - len(violations) / len(resolvable_rows)
            if resolvable_rows
            else None
        ),
        "strict_permutation_agreement": full_order == recomposed_order,
        "full_order": full_order,
        "recomposed_order": recomposed_order,
        "full_winner_state_id": winner_id,
        "recomposed_winner_state_id": recomposed_winner_id,
        "winner_margin": winner_margin,
        "winner_resolvable": winner_resolvable,
        "winner_agrees": winner_agrees,
        "resolvable_winner_violation": winner_resolvable and not winner_agrees,
        "pair_violations": tuple(violations),
    }


def evaluate_margin_aware_ordering(
    rows: list[dict[str, Any]],
    *,
    uncertainty_envelope: float,
    full_score_field: str = "numeric_full_gp_score",
    recomposed_score_field: str = "numeric_recomposed_gp_score",
    policy: MarginOrderingPolicy = DEFAULT_MARGIN_ORDERING_POLICY,
) -> dict[str, Any]:
    if not math.isfinite(uncertainty_envelope) or uncertainty_envelope < 0:
        raise ValueError("pairwise uncertainty envelope must be finite and non-negative")
    if uncertainty_envelope > policy.maximum_pairwise_uncertainty_envelope:
        raise ValueError("pairwise uncertainty envelope exceeds the preregistered cap")
    by_task = _task_state_mean_scores(
        rows,
        full_score_field=full_score_field,
        recomposed_score_field=recomposed_score_field,
    )
    task_rows = [
        _evaluate_task_ordering(
            task_id,
            states,
            uncertainty_envelope=uncertainty_envelope,
        )
        for task_id, states in sorted(by_task.items())
    ]
    total_pairs = sum(int(row["pair_count"]) for row in task_rows)
    resolvable_pairs = sum(int(row["resolvable_pair_count"]) for row in task_rows)
    pair_violations = sum(
        int(row["resolvable_pair_violation_count"]) for row in task_rows
    )
    resolvable_tasks = sum(int(row["resolvable_pair_count"]) > 0 for row in task_rows)
    resolvable_winner_tasks = sum(bool(row["winner_resolvable"]) for row in task_rows)
    winner_violations = sum(
        bool(row["resolvable_winner_violation"]) for row in task_rows
    )
    strict_task_agreements = sum(
        bool(row["strict_permutation_agreement"]) for row in task_rows
    )
    resolvable_pair_fraction = resolvable_pairs / total_pairs
    resolvable_task_fraction = resolvable_tasks / len(task_rows)
    metrics = {
        "task_count": len(task_rows),
        "pair_count": total_pairs,
        "resolvable_pair_count": resolvable_pairs,
        "resolvable_pair_fraction": resolvable_pair_fraction,
        "resolvable_pair_violation_count": pair_violations,
        "resolvable_pair_direction_agreement": (
            1.0 - pair_violations / resolvable_pairs
            if resolvable_pairs
            else None
        ),
        "resolvable_task_count": resolvable_tasks,
        "resolvable_task_fraction": resolvable_task_fraction,
        "resolvable_winner_task_count": resolvable_winner_tasks,
        "resolvable_winner_task_fraction": resolvable_winner_tasks / len(task_rows),
        "resolvable_winner_violation_count": winner_violations,
        "strict_permutation_agreement_count": strict_task_agreements,
        "strict_permutation_agreement_rate": strict_task_agreements / len(task_rows),
        "all_winner_agreement_count": sum(bool(row["winner_agrees"]) for row in task_rows),
        "all_winner_agreement_rate": (
            sum(bool(row["winner_agrees"]) for row in task_rows) / len(task_rows)
        ),
    }
    failure_reasons = []
    if resolvable_pair_fraction < policy.minimum_resolvable_pair_fraction:
        failure_reasons.append("resolvable_pair_coverage_below_minimum")
    if resolvable_task_fraction < policy.minimum_resolvable_task_fraction:
        failure_reasons.append("resolvable_task_coverage_below_minimum")
    if (
        pair_violations
        > policy.maximum_resolvable_pair_violation_count
    ):
        failure_reasons.append("resolvable_pair_direction_violation")
    if (
        winner_violations
        > policy.maximum_resolvable_winner_violation_count
    ):
        failure_reasons.append("resolvable_winner_violation")
    return {
        "ordering_policy": asdict(policy),
        "pairwise_uncertainty_envelope": uncertainty_envelope,
        "metrics": metrics,
        "task_rows": task_rows,
        "status": "passed" if not failure_reasons else "failed",
        "failure_reasons": tuple(failure_reasons),
    }


def ordering_sensitivity(
    rows: list[dict[str, Any]],
    *,
    envelopes: tuple[float, ...] = RETROSPECTIVE_ENVELOPE_GRID,
) -> tuple[dict[str, Any], ...]:
    if (
        not envelopes
        or tuple(sorted(set(envelopes))) != envelopes
        or envelopes[0] < 0
    ):
        raise ValueError("ordering sensitivity grid must be sorted and unique")
    return tuple(
        evaluate_margin_aware_ordering(
            rows,
            uncertainty_envelope=envelope,
        )
        for envelope in envelopes
    )


def build_retrospective_report(
    source_run_dir: Path,
    *,
    rehash_artifacts: bool = False,
) -> dict[str, Any]:
    source_run_dir = source_run_dir.resolve()
    plan = _read_json(source_run_dir / "plan.json")
    source_report = _read_json(source_run_dir / "report.json")
    rows, worker_summary = _load_worker_rows(source_run_dir)
    integrity = _validate_integrity(
        source_run_dir,
        plan=plan,
        report=source_report,
        rows=rows,
        worker_summary=worker_summary,
        rehash_artifacts=rehash_artifacts,
    )
    source_tail_path = source_run_dir / "tail_analysis.json"
    source_tail_hash = None
    if source_tail_path.is_file():
        source_tail = _read_json(source_tail_path)
        source_tail_hash = _replay_hash(
            source_tail,
            field="analysis_hash",
            prefix="finance_gradient_projection_tail_analysis:",
        )

    sensitivity = ordering_sensitivity(rows)
    zero_violation_envelopes = [
        float(row["pairwise_uncertainty_envelope"])
        for row in sensitivity
        if int(row["metrics"]["resolvable_pair_violation_count"]) == 0
    ]
    report: dict[str, Any] = {
        "validation_version": NUMERIC_VALIDATION_VERSION,
        "ordering_policy_version": MARGIN_ORDERING_VERSION,
        "source_run_dir": str(source_run_dir),
        "source_plan_hash": integrity["plan_hash"],
        "source_report_hash": integrity["report_hash"],
        "source_tail_analysis_hash": source_tail_hash,
        "source_numeric_contract_hash": source_report.get("numeric_contract_hash"),
        "source_integrity": integrity,
        "population_role": "observed_production_validation_holdout",
        "analysis_role": "retrospective_sensitivity_only",
        "contract_selection_allowed": False,
        "envelope_grid": RETROSPECTIVE_ENVELOPE_GRID,
        "sensitivity": sensitivity,
        "first_grid_envelope_with_zero_resolvable_pair_violations": (
            min(zero_violation_envelopes) if zero_violation_envelopes else None
        ),
        "authorization_effect": "none",
        "production_authorized": False,
        "status": "completed",
        "claim_boundary": (
            "This read-only analysis may diagnose v14 but cannot select or relax a "
            "production numeric contract. A disjoint calibration population must freeze "
            "the uncertainty envelope before a new production candidate is evaluated."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_gradient_numeric_validation:",
    )
    return report


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run read-only margin-aware numeric sensitivity analysis"
    )
    parser.add_argument("--source-run-dir", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--rehash-artifacts", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = build_retrospective_report(
        Path(args.source_run_dir),
        rehash_artifacts=bool(args.rehash_artifacts),
    )
    _write_json(Path(args.output_path).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
