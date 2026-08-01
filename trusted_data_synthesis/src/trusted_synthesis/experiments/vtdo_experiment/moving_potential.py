from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypedDict

from .schema import (
    AggregateMetric,
    MovingPotentialBenchmarkConfig,
    MovingPotentialMethod,
    MovingPotentialMethodSummary,
    MovingPotentialTrack,
    MovingPotentialTrackingSummary,
    SyntheticExperimentConfig,
    VariationalObjectiveVerificationSummary,
    moving_potential_tracking_hash,
)
from .statistics import aggregate_metric
from .synthetic import _production_vtdo_update


@dataclass(frozen=True)
class MovingPotentialExecution:
    summary: MovingPotentialTrackingSummary
    rows: tuple[dict[str, object], ...]


class _MovingTransition(TypedDict):
    next_distribution: dict[str, float]
    potential: dict[str, float]
    anchor_target: dict[str, float]
    objective_before: float
    objective_after: float
    objective_gain: float
    proximal_optimizer_kl: float


def run_moving_potential_tracking_experiments(
    config: MovingPotentialBenchmarkConfig,
    synthetic: SyntheticExperimentConfig,
    *,
    experiment_id: str,
) -> tuple[MovingPotentialExecution, ...]:
    return tuple(
        run_moving_potential_tracking_experiment(
            config,
            synthetic,
            experiment_id=experiment_id,
            track=track,
        )
        for track in config.tracks
    )


def run_moving_potential_tracking_experiment(
    config: MovingPotentialBenchmarkConfig,
    synthetic: SyntheticExperimentConfig,
    *,
    experiment_id: str,
    track: MovingPotentialTrack = "exogenous_shared",
) -> MovingPotentialExecution:
    """Measure one declared moving-potential track without changing its environment."""

    rows = tuple(
        row
        for seed in synthetic.seeds
        for row in _run_seed(
            config,
            synthetic,
            seed=seed,
            experiment_id=experiment_id,
            track=track,
        )
    )
    methods = tuple(
        _summarize_method(method, rows, config.rounds)
        for method in ("no_feedback", "static_optimization", "full_vtdo")
    )
    objective_rows = tuple(row for row in rows if row["method"] == "full_vtdo")
    gains = [_number(row["variational_objective_gain"]) for row in objective_rows]
    optimizer_kls = [_number(row["proximal_optimizer_kl"]) for row in objective_rows]
    monotonic_count = sum(value >= -config.objective_tolerance for value in gains)
    objective = VariationalObjectiveVerificationSummary(
        transition_count=len(objective_rows),
        monotonic_transition_count=monotonic_count,
        minimum_objective_gain=min(gains),
        maximum_proximal_optimizer_kl=max(optimizer_kls),
        tolerance=config.objective_tolerance,
        all_transitions_verified=(
            monotonic_count == len(objective_rows)
            and max(optimizer_kls) <= config.objective_tolerance
        ),
    )
    no_feedback_advantages: list[float] = []
    static_advantages: list[float] = []
    for seed in synthetic.seeds:
        final = {
            str(row["method"]): _number(row["cumulative_regret"])
            for row in rows
            if row["seed"] == seed and row["round_index"] == config.rounds
        }
        no_feedback_advantages.append(final["no_feedback"] - final["full_vtdo"])
        static_advantages.append(final["static_optimization"] - final["full_vtdo"])
    no_feedback_advantage = _aggregate(no_feedback_advantages)
    static_advantage = _aggregate(static_advantages)
    direction_supported = all(
        (
            metric.mean - metric.ci95_half_width
            if config.require_regret_ci_lower_bound_nonnegative
            else metric.mean
        )
        >= -config.objective_tolerance
        for metric in (no_feedback_advantage, static_advantage)
    )
    target_movements = [
        _number(row["target_movement_kl"])
        for row in objective_rows
        if row["target_movement_kl"] is not None
    ]
    values = {
        "track": track,
        "is_primary_track": track == config.primary_track,
        "status": (
            "passed"
            if objective.all_transitions_verified
            and (direction_supported or not config.require_regret_advantage)
            else "failed"
        ),
        "state_count": synthetic.state_count,
        "round_count": config.rounds,
        "seed_count": len(synthetic.seeds),
        "potential_sequence_definition": _track_definition(track),
        "instantaneous_optimum_formula": (
            "pi_anchor_t*(z|x) proportional to r(z|x) "
            "Phi_t(z)^(1/kappa); the historical KL term is a proximal tracking penalty"
        ),
        "method_summaries": methods,
        "target_movement_kl": _aggregate(target_movements),
        "variational_objective": objective,
        "vtdo_regret_advantage_over_no_feedback": no_feedback_advantage,
        "vtdo_regret_advantage_over_static": static_advantage,
        "regret_advantage_required": config.require_regret_advantage,
        "regret_advantage_ci_lower_bound_required": (
            config.require_regret_ci_lower_bound_nonnegative
        ),
        "optimization_direction_supported": direction_supported,
    }
    provisional = MovingPotentialTrackingSummary.model_construct(
        **values,
        report_hash="pending",
    )
    summary = MovingPotentialTrackingSummary(
        **values,
        report_hash=moving_potential_tracking_hash(provisional),
    )
    return MovingPotentialExecution(summary=summary, rows=rows)


def _run_seed(
    config: MovingPotentialBenchmarkConfig,
    synthetic: SyntheticExperimentConfig,
    *,
    seed: int,
    experiment_id: str,
    track: MovingPotentialTrack,
) -> tuple[dict[str, object], ...]:
    rng = random.Random(seed + 700_001)
    state_ids = tuple(f"moving_state:{seed}:{index:03d}" for index in range(synthetic.state_count))
    tail = list(range(synthetic.state_count))
    rng.shuffle(tail)
    coverage = _normalize(
        {
            state_id: 0.2 + 4.8 * (tail[index] / max(synthetic.state_count - 1, 1)) ** 2
            for index, state_id in enumerate(state_ids)
        }
    )
    base_contribution = {state_id: rng.gauss(0.0, 1.0) for state_id in state_ids}
    drift_phase = {state_id: rng.uniform(0.0, 2.0 * math.pi) for state_id in state_ids}
    initial = _normalize(
        {
            state_id: math.exp(0.75 * base_contribution[state_id])
            / (0.25 + synthetic.state_count * coverage[state_id])
            for state_id in state_ids
        }
    )
    policies: dict[MovingPotentialMethod, dict[str, float]] = {
        "no_feedback": dict(initial),
        "static_optimization": dict(initial),
        "full_vtdo": dict(initial),
    }
    exposures = {
        method: {state_id: 0.0 for state_id in state_ids}
        for method in policies
    }
    previous_targets: dict[MovingPotentialMethod, dict[str, float] | None] = {
        method: None for method in policies
    }
    cumulative_regret = {
        "no_feedback": 0.0,
        "static_optimization": 0.0,
        "full_vtdo": 0.0,
    }
    rows: list[dict[str, object]] = []
    for round_index in range(1, config.rounds + 1):
        shared_exposure = exposures["full_vtdo"]
        shared_contributions = _contributions(
            state_ids,
            base_contribution,
            drift_phase,
            shared_exposure,
            config,
            synthetic,
            round_index,
            include_capability_decay=track == "vtdo_induced_shared",
        )
        transitions: dict[MovingPotentialMethod, _MovingTransition] = {}
        for method, prior in policies.items():
            contributions = (
                _contributions(
                    state_ids,
                    base_contribution,
                    drift_phase,
                    exposures[method],
                    config,
                    synthetic,
                    round_index,
                    include_capability_decay=True,
                )
                if track == "method_specific_closed_loop"
                else shared_contributions
            )
            transitions[method] = _transition(
                prior,
                coverage,
                contributions,
                synthetic,
                round_index=round_index,
                condition_suffix=f"moving_{track}_{seed}_{method}",
            )

        next_policies: dict[MovingPotentialMethod, dict[str, float]] = {
            "no_feedback": dict(initial),
            "static_optimization": (
                dict(transitions["static_optimization"]["anchor_target"])
                if round_index == 1
                else dict(policies["static_optimization"])
            ),
            "full_vtdo": dict(transitions["full_vtdo"]["next_distribution"]),
        }
        for method, policy in next_policies.items():
            transition = transitions[method]
            potential = transition["potential"]
            anchor_target = transition["anchor_target"]
            movement = (
                None
                if previous_targets[method] is None
                else _kl(anchor_target, previous_targets[method] or {})
            )
            anchor_target_objective = _anchor_objective(
                anchor_target,
                potential,
                coverage,
                synthetic.coverage_kl_weight,
            )
            anchor_objective = _anchor_objective(
                policy,
                potential,
                coverage,
                synthetic.coverage_kl_weight,
            )
            regret = max(0.0, anchor_target_objective - anchor_objective)
            cumulative_regret[method] += regret
            rows.append(
                {
                    "experiment_id": experiment_id,
                    "track": track,
                    "seed": seed,
                    "round_index": round_index,
                    "method": method,
                    "tracking_error": _kl(policy, anchor_target),
                    "instantaneous_regret": regret,
                    "cumulative_regret": cumulative_regret[method],
                    "anchor_objective": anchor_objective,
                    "target_anchor_objective": anchor_target_objective,
                    "target_movement_kl": movement,
                    "distribution_kl_shift": _kl(policy, policies[method]),
                    "variational_objective_before": (
                        transition["objective_before"] if method == "full_vtdo" else None
                    ),
                    "variational_objective_after": (
                        transition["objective_after"] if method == "full_vtdo" else None
                    ),
                    "variational_objective_gain": (
                        transition["objective_gain"] if method == "full_vtdo" else None
                    ),
                    "proximal_optimizer_kl": (
                        transition["proximal_optimizer_kl"]
                        if method == "full_vtdo"
                        else None
                    ),
                }
            )
            previous_targets[method] = dict(anchor_target)
        for method, policy in next_policies.items():
            for state_id in state_ids:
                exposures[method][state_id] += policy[state_id]
        policies = next_policies
    return tuple(rows)


def _contributions(
    state_ids: tuple[str, ...],
    base: Mapping[str, float],
    phase: Mapping[str, float],
    exposure: Mapping[str, float],
    config: MovingPotentialBenchmarkConfig,
    synthetic: SyntheticExperimentConfig,
    round_index: int,
    *,
    include_capability_decay: bool,
) -> dict[str, float]:
    return {
        state_id: (
            base[state_id]
            + config.contribution_drift_scale
            * math.sin(
                phase[state_id] + 2.0 * math.pi * (round_index - 1) / config.drift_period
            )
            - (
                config.capability_decay * synthetic.state_count * exposure[state_id]
                if include_capability_decay
                else 0.0
            )
        )
        for state_id in state_ids
    }


def _transition(
    prior: Mapping[str, float],
    coverage: Mapping[str, float],
    contributions: Mapping[str, float],
    synthetic: SyntheticExperimentConfig,
    *,
    round_index: int,
    condition_suffix: str,
) -> _MovingTransition:
    next_distribution, phase = _production_vtdo_update(
        prior,
        coverage,
        contributions,
        {state_id: 1.0 for state_id in prior},
        synthetic,
        round_index=round_index - 1,
        condition_suffix=condition_suffix,
    )
    by_state = {str(item["state_id"]): item for item in phase}
    if set(by_state) != set(prior):
        raise ValueError("moving-potential phase does not cover its state space")
    potential = {state_id: _number(by_state[state_id]["potential"]) for state_id in prior}
    anchor_target = _normalize(
        {
            state_id: coverage[state_id]
            * potential[state_id] ** (1.0 / synthetic.coverage_kl_weight)
            for state_id in prior
        }
    )
    denominator = synthetic.history_kl_weight + synthetic.coverage_kl_weight
    proximal_target = _normalize(
        {
            state_id: prior[state_id] ** (synthetic.history_kl_weight / denominator)
            * coverage[state_id] ** (synthetic.coverage_kl_weight / denominator)
            * potential[state_id] ** (1.0 / denominator)
            for state_id in prior
        }
    )
    objective_before = _proximal_objective(
        prior,
        potential,
        prior,
        coverage,
        synthetic.history_kl_weight,
        synthetic.coverage_kl_weight,
    )
    objective_after = _proximal_objective(
        next_distribution,
        potential,
        prior,
        coverage,
        synthetic.history_kl_weight,
        synthetic.coverage_kl_weight,
    )
    return {
        "next_distribution": next_distribution,
        "potential": potential,
        "anchor_target": anchor_target,
        "objective_before": objective_before,
        "objective_after": objective_after,
        "objective_gain": objective_after - objective_before,
        "proximal_optimizer_kl": _kl(next_distribution, proximal_target),
    }


def _track_definition(track: MovingPotentialTrack) -> str:
    return {
        "exogenous_shared": (
            "Primary method-neutral control: all methods share one potential sequence generated "
            "only by a frozen exogenous drift process; no method exposure enters Phi_t."
        ),
        "vtdo_induced_shared": (
            "Supplementary counterfactual track: all methods share one potential sequence whose "
            "capability decay is induced by the full-VTDO exposure path."
        ),
        "method_specific_closed_loop": (
            "Supplementary endogenous track: each method updates its own capability exposure and "
            "is evaluated against its own instantaneous anchored optimum."
        ),
    }[track]


def _summarize_method(
    method: MovingPotentialMethod,
    rows: tuple[dict[str, object], ...],
    final_round: int,
) -> MovingPotentialMethodSummary:
    selected = tuple(row for row in rows if row["method"] == method)
    by_seed: defaultdict[int, list[dict[str, object]]] = defaultdict(list)
    for row in selected:
        by_seed[_integer(row["seed"])].append(row)
    final = tuple(row for row in selected if row["round_index"] == final_round)
    return MovingPotentialMethodSummary(
        method=method,
        run_count=len(by_seed),
        mean_tracking_error=_aggregate(
            [
                statistics.fmean(_number(row["tracking_error"]) for row in values)
                for values in by_seed.values()
            ]
        ),
        final_tracking_error=_aggregate([_number(row["tracking_error"]) for row in final]),
        cumulative_regret=_aggregate([_number(row["cumulative_regret"]) for row in final]),
        final_anchor_objective=_aggregate([_number(row["anchor_objective"]) for row in final]),
    )


def _anchor_objective(
    distribution: Mapping[str, float],
    potential: Mapping[str, float],
    coverage: Mapping[str, float],
    coverage_kl_weight: float,
) -> float:
    return sum(distribution[key] * math.log(potential[key]) for key in distribution) - (
        coverage_kl_weight * _kl(distribution, coverage)
    )


def _proximal_objective(
    distribution: Mapping[str, float],
    potential: Mapping[str, float],
    prior: Mapping[str, float],
    coverage: Mapping[str, float],
    history_kl_weight: float,
    coverage_kl_weight: float,
) -> float:
    return (
        sum(distribution[key] * math.log(potential[key]) for key in distribution)
        - history_kl_weight * _kl(distribution, prior)
        - coverage_kl_weight * _kl(distribution, coverage)
    )


def _normalize(values: Mapping[str, float]) -> dict[str, float]:
    if any(value <= 0 for value in values.values()):
        raise ValueError("moving-potential distributions require positive support")
    total = sum(values.values())
    if total <= 0:
        raise ValueError("moving-potential distribution has no mass")
    return {key: values[key] / total for key in sorted(values)}


def _kl(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if set(left) != set(right):
        raise ValueError("KL distributions have different support")
    return sum(left[key] * math.log(left[key] / right[key]) for key in left)


def _aggregate(values: list[float]) -> AggregateMetric:
    return aggregate_metric(values)


def _number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError("moving-potential metric is not numeric")


def _integer(value: object) -> int:
    if isinstance(value, int):
        return value
    raise TypeError("moving-potential index is not an integer")
