from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from trusted_synthesis.core.vtdo import VTDORoundArtifact
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    AggregateMetric,
    FixedPotentialContractionSummary,
    PracticalConvergenceSummary,
    RealRefinementDynamicsSummary,
    RefinementCheckpointSummary,
    RefinementDynamicsConfig,
    RefinementDynamicsReport,
    RefinementRoundAggregate,
    SyntheticExperimentConfig,
    SyntheticExperimentReport,
    SyntheticMetricPoint,
    SyntheticState,
    refinement_dynamics_report_hash,
)


@dataclass(frozen=True)
class RefinementDynamicsExecution:
    report: RefinementDynamicsReport
    controlled_rows: tuple[dict[str, object], ...]
    fixed_potential_rows: tuple[dict[str, object], ...]
    real_rows: tuple[dict[str, object], ...]


def run_refinement_dynamics_experiment(
    config: RefinementDynamicsConfig,
    synthetic_config: SyntheticExperimentConfig,
    synthetic_report: SyntheticExperimentReport,
    state_catalogs: Mapping[int, tuple[SyntheticState, ...]],
    phase_rows: Iterable[Mapping[str, float | int | str]],
    *,
    experiment_id: str,
) -> RefinementDynamicsExecution:
    """Separate fixed-potential contraction from moving-potential stabilization."""

    controlled_rows, practical = _controlled_round_dynamics(config, synthetic_report)
    aggregates = _aggregate_controlled_rounds(config, controlled_rows)
    checkpoints = _checkpoint_summaries(config, aggregates)
    fixed_summary, fixed_rows = _fixed_potential_contraction(
        config,
        synthetic_config,
        state_catalogs,
        tuple(phase_rows),
    )
    real_summary, real_rows = _real_round_dynamics(config)
    interpretation = (
        "The fixed-potential control numerically verifies the predicted projective "
        "contraction. The production update recomputes its potential each round and is "
        "therefore evaluated only with a finite-step practical-stability criterion."
    )
    values = {
        "experiment_id": experiment_id,
        "config_hash": canonical_hash(config, prefix="refinement_dynamics_config:"),
        "controlled_method": config.method,
        "analysis_rounds": config.analysis_rounds,
        "round_aggregates": aggregates,
        "checkpoint_summaries": checkpoints,
        "practical_convergence": practical,
        "fixed_potential_contraction": fixed_summary,
        "real_refinement": real_summary,
        "strict_convergence_claim_supported": False,
        "interpretation": interpretation,
    }
    provisional = RefinementDynamicsReport.model_construct(report_hash="pending", **values)
    report = RefinementDynamicsReport(
        **values,
        report_hash=refinement_dynamics_report_hash(provisional),
    )
    return RefinementDynamicsExecution(
        report=report,
        controlled_rows=controlled_rows,
        fixed_potential_rows=fixed_rows,
        real_rows=real_rows,
    )


def _controlled_round_dynamics(
    config: RefinementDynamicsConfig,
    report: SyntheticExperimentReport,
) -> tuple[tuple[dict[str, object], ...], PracticalConvergenceSummary]:
    points_by_seed: defaultdict[int, dict[int, SyntheticMetricPoint]] = defaultdict(dict)
    for point in report.metric_points:
        if point.method == config.method and point.round_index <= config.analysis_rounds:
            points_by_seed[point.seed][point.round_index] = point
    expected_rounds = set(range(config.analysis_rounds + 1))
    if not points_by_seed:
        raise ValueError("no controlled refinement points match the configured method")

    rows: list[dict[str, object]] = []
    convergence_by_seed: dict[str, int | None] = {}
    for seed, by_round in sorted(points_by_seed.items()):
        if set(by_round) != expected_rounds:
            raise ValueError(f"synthetic refinement seed {seed} has an incomplete round horizon")
        streak = 0
        convergence_round: int | None = None
        previous_utility: float | None = None
        seed_rows: list[dict[str, object]] = []
        for round_index in range(config.analysis_rounds + 1):
            point = by_round[round_index]
            utility = point.expected_contribution_novelty
            utility_delta = None if previous_utility is None else abs(utility - previous_utility)
            kl_shift = None if round_index == 0 else point.kl_to_previous
            stable = bool(
                kl_shift is not None
                and utility_delta is not None
                and kl_shift < config.kl_stabilization_threshold
                and utility_delta < config.utility_delta_threshold
            )
            streak = streak + 1 if stable else 0
            if streak >= config.consecutive_stable_rounds and convergence_round is None:
                convergence_round = round_index
            seed_rows.append(
                {
                    "seed": seed,
                    "round_index": round_index,
                    "kl_shift": kl_shift,
                    "expected_utility": utility,
                    "absolute_utility_delta": utility_delta,
                    "entropy": point.entropy,
                    "coverage_count": point.coverage_count,
                    "stable_transition": stable,
                }
            )
            previous_utility = utility
        convergence_by_seed[str(seed)] = convergence_round
        for row in seed_rows:
            row["first_practical_convergence_round"] = convergence_round
            rows.append(row)

    round_counts: dict[str, int] = {}
    for convergence_value in convergence_by_seed.values():
        key = "not_observed" if convergence_value is None else str(convergence_value)
        round_counts[key] = round_counts.get(key, 0) + 1
    converged = sum(value is not None for value in convergence_by_seed.values())
    summary = PracticalConvergenceSummary(
        kl_threshold=config.kl_stabilization_threshold,
        utility_delta_threshold=config.utility_delta_threshold,
        consecutive_rounds=config.consecutive_stable_rounds,
        evaluated_seed_count=len(convergence_by_seed),
        converged_seed_count=converged,
        convergence_round_by_seed=convergence_by_seed,
        convergence_round_counts=dict(sorted(round_counts.items())),
        practical_convergence_observed=(converged == len(convergence_by_seed)),
    )
    return tuple(rows), summary


def _aggregate_controlled_rounds(
    config: RefinementDynamicsConfig,
    rows: tuple[dict[str, object], ...],
) -> tuple[RefinementRoundAggregate, ...]:
    output: list[RefinementRoundAggregate] = []
    for round_index in range(config.analysis_rounds + 1):
        current = tuple(row for row in rows if row["round_index"] == round_index)
        if not current:
            raise ValueError(f"refinement round {round_index} has no controlled observations")
        output.append(
            RefinementRoundAggregate(
                round_index=round_index,
                transition_from_round=(round_index - 1 if round_index else None),
                kl_shift=(
                    _aggregate([_as_float(row["kl_shift"]) for row in current])
                    if round_index
                    else None
                ),
                expected_utility=_aggregate(
                    [_as_float(row["expected_utility"]) for row in current]
                ),
                absolute_utility_delta=(
                    _aggregate([_as_float(row["absolute_utility_delta"]) for row in current])
                    if round_index
                    else None
                ),
                entropy=_aggregate([_as_float(row["entropy"]) for row in current]),
                coverage_count=_aggregate([_as_float(row["coverage_count"]) for row in current]),
                stable_seed_count=sum(bool(row["stable_transition"]) for row in current),
            )
        )
    return tuple(output)


def _checkpoint_summaries(
    config: RefinementDynamicsConfig,
    aggregates: tuple[RefinementRoundAggregate, ...],
) -> tuple[RefinementCheckpointSummary, ...]:
    by_round = {item.round_index: item for item in aggregates}
    one_shot = by_round[1].expected_utility.mean
    output = []
    for round_index in config.checkpoint_rounds:
        aggregate = by_round[round_index]
        if aggregate.kl_shift is None:
            raise ValueError("checkpoint round is missing its KL transition")
        role = (
            "one_shot"
            if round_index == 1
            else "primary_iterative"
            if round_index == config.primary_training_round
            else "analysis_only"
        )
        output.append(
            RefinementCheckpointSummary(
                round_index=round_index,
                role=role,
                expected_utility=aggregate.expected_utility,
                utility_gain_from_one_shot=aggregate.expected_utility.mean - one_shot,
                kl_shift=aggregate.kl_shift,
                entropy=aggregate.entropy,
                coverage_count=aggregate.coverage_count,
                downstream_training_evaluated=False,
            )
        )
    return tuple(output)


def _fixed_potential_contraction(
    config: RefinementDynamicsConfig,
    synthetic_config: SyntheticExperimentConfig,
    state_catalogs: Mapping[int, tuple[SyntheticState, ...]],
    phase_rows: tuple[Mapping[str, float | int | str], ...],
) -> tuple[FixedPotentialContractionSummary, tuple[dict[str, object], ...]]:
    rho = synthetic_config.history_kl_weight / (
        synthetic_config.history_kl_weight + synthetic_config.coverage_kl_weight
    )
    eta = 1.0 / (synthetic_config.history_kl_weight + synthetic_config.coverage_kl_weight)
    rows: list[dict[str, object]] = []
    initial_distances: list[float] = []
    final_distances: list[float] = []
    final_kls: list[float] = []
    contraction_factors: list[float] = []
    for seed, states in sorted(state_catalogs.items()):
        accepted = tuple(item for item in states if item.validity_region == "accepted")
        initial = _normalize({item.state_id: item.initial_probability for item in accepted})
        coverage = _normalize({item.state_id: item.coverage_prior for item in accepted})
        first_phase = {
            str(row["state_id"]): row
            for row in phase_rows
            if int(row["seed"]) == seed and int(row["round_index"]) == 1
        }
        if set(first_phase) != set(initial):
            raise ValueError(f"fixed-potential control has incomplete phase data for seed {seed}")
        potential = {
            state_id: (
                float(first_phase[state_id]["normalized_contribution"])
                ** synthetic_config.contribution_weight
                * float(first_phase[state_id]["normalized_novelty"])
                ** synthetic_config.novelty_weight
            )
            for state_id in initial
        }
        fixed_point = _normalize(
            {
                state_id: coverage[state_id] * potential[state_id] ** (eta / (1.0 - rho))
                for state_id in initial
            }
        )
        current = initial
        distance = _projective_distance(current, fixed_point)
        initial_distances.append(distance)
        rows.append(
            {
                "seed": seed,
                "round_index": 0,
                "projective_distance_to_fixed_point": distance,
                "kl_to_fixed_point": _kl(current, fixed_point),
                "observed_contraction_factor": None,
            }
        )
        for round_index in range(1, config.fixed_potential_rounds + 1):
            next_distribution = _normalize(
                {
                    state_id: current[state_id] ** rho
                    * coverage[state_id] ** (1.0 - rho)
                    * potential[state_id] ** eta
                    for state_id in current
                }
            )
            next_distance = _projective_distance(next_distribution, fixed_point)
            factor = next_distance / distance if distance > 1e-14 else rho
            contraction_factors.append(factor)
            rows.append(
                {
                    "seed": seed,
                    "round_index": round_index,
                    "projective_distance_to_fixed_point": next_distance,
                    "kl_to_fixed_point": _kl(next_distribution, fixed_point),
                    "observed_contraction_factor": factor,
                }
            )
            current = next_distribution
            distance = next_distance
        final_distances.append(distance)
        final_kls.append(_kl(current, fixed_point))
    maximum_error = max(abs(value - rho) for value in contraction_factors)
    summary = FixedPotentialContractionSummary(
        run_count=len(state_catalogs),
        round_count=config.fixed_potential_rounds,
        history_exponent=rho,
        energy_exponent=eta,
        analytic_fixed_point_formula="pi*(z|x) proportional to r(z|x) Phi(z)^(eta/(1-rho))",
        initial_projective_distance=_aggregate(initial_distances),
        final_projective_distance=_aggregate(final_distances),
        observed_projective_contraction_factor=_aggregate(contraction_factors),
        maximum_absolute_factor_error=maximum_error,
        final_kl_to_fixed_point=_aggregate(final_kls),
        projective_contraction_verified=(maximum_error <= config.contraction_tolerance),
    )
    return summary, tuple(rows)


def _real_round_dynamics(
    config: RefinementDynamicsConfig,
) -> tuple[RealRefinementDynamicsSummary, tuple[dict[str, object], ...]]:
    if not config.real_round_artifact_paths:
        return (
            RealRefinementDynamicsSummary(
                status="not_configured",
                configured_artifact_count=0,
                validated_artifact_count=0,
                task_condition_count=0,
                complete_sequence_count=0,
                sequential_link_failure_count=0,
                convergence_eligible_sequence_count=0,
                converged_sequence_count=0,
                blockers=("no_real_vtdo_round_artifacts",),
            ),
            (),
        )
    artifacts: list[VTDORoundArtifact] = []
    blockers: list[str] = []
    for source in config.real_round_artifact_paths:
        paths = tuple(sorted(source.glob("*.json*"))) if source.is_dir() else (source,)
        if not paths or any(not path.is_file() for path in paths):
            blockers.append(f"missing_round_artifact_source:{source}")
            continue
        for path in paths:
            try:
                payloads = _read_json_records(path)
            except (OSError, json.JSONDecodeError) as error:
                blockers.append(f"unreadable_round_artifact:{path.name}:{type(error).__name__}")
                continue
            for index, payload in enumerate(payloads):
                try:
                    artifacts.append(VTDORoundArtifact.model_validate(payload))
                except ValidationError:
                    blockers.append(f"invalid_round_artifact:{path.name}:{index}")
    if not artifacts:
        return (
            RealRefinementDynamicsSummary(
                status="blocked",
                configured_artifact_count=len(config.real_round_artifact_paths),
                validated_artifact_count=0,
                task_condition_count=0,
                complete_sequence_count=0,
                sequential_link_failure_count=0,
                convergence_eligible_sequence_count=0,
                converged_sequence_count=0,
                blockers=tuple(sorted(set(blockers or ["no_valid_real_round_artifacts"]))),
            ),
            (),
        )

    grouped: defaultdict[str, list[VTDORoundArtifact]] = defaultdict(list)
    rows: list[dict[str, object]] = []
    for artifact in artifacts:
        grouped[artifact.task_condition_id].append(artifact)
        potentials = {item.state_id: item for item in artifact.update.state_potentials}
        utility_by_state = {
            state_id: item.centered_contribution * item.coverage_relative_novelty
            for state_id, item in potentials.items()
        }
        prior = artifact.update.prior_distribution.probabilities
        next_distribution = artifact.update.next_distribution.probabilities
        utility_before = sum(prior[key] * utility_by_state[key] for key in prior)
        utility_after = sum(
            next_distribution[key] * utility_by_state[key] for key in next_distribution
        )
        rows.append(
            {
                "task_condition_id": artifact.task_condition_id,
                "round_index": artifact.round_index,
                "round_id": artifact.round_id,
                "kl_shift": artifact.update.kl_to_history,
                "utility_before": utility_before,
                "utility_after": utility_after,
                "absolute_utility_delta": abs(utility_after - utility_before),
                "entropy": artifact.update.next_entropy,
                "coverage_count": sum(
                    value > config.coverage_epsilon for value in next_distribution.values()
                ),
            }
        )

    complete = 0
    link_failures = 0
    eligible = 0
    converged = 0
    final_kls: list[float] = []
    expected_indices = tuple(range(config.analysis_rounds))
    for condition_id, values in sorted(grouped.items()):
        ordered = sorted(values, key=lambda item: item.round_index)
        by_index = {item.round_index: item for item in ordered}
        if len(by_index) != len(ordered):
            blockers.append(f"duplicate_round_index:{condition_id}")
            continue
        if not all(index in by_index for index in expected_indices):
            continue
        sequence = tuple(by_index[index] for index in expected_indices)
        complete += 1
        linked = all(
            current.exploration.training_distribution.distribution_id
            == previous.update.next_distribution.distribution_id
            for previous, current in zip(sequence, sequence[1:], strict=False)
        )
        if not linked:
            link_failures += 1
            blockers.append(f"round_distribution_link_failure:{condition_id}")
            continue
        eligible += 1
        streak = 0
        reached = False
        for artifact in sequence:
            row = next(item for item in rows if item["round_id"] == artifact.round_id)
            stable = bool(
                _as_float(row["kl_shift"]) < config.kl_stabilization_threshold
                and _as_float(row["absolute_utility_delta"]) < config.utility_delta_threshold
            )
            streak = streak + 1 if stable else 0
            if streak >= config.consecutive_stable_rounds:
                reached = True
        converged += int(reached)
        final_kls.append(sequence[-1].update.kl_to_history)
    if not complete:
        blockers.append("no_complete_real_refinement_sequence")
    status = (
        "passed"
        if complete and not blockers and link_failures == 0
        else "partial"
        if artifacts
        else "blocked"
    )
    summary = RealRefinementDynamicsSummary(
        status=status,
        configured_artifact_count=len(config.real_round_artifact_paths),
        validated_artifact_count=len(artifacts),
        task_condition_count=len(grouped),
        complete_sequence_count=complete,
        sequential_link_failure_count=link_failures,
        convergence_eligible_sequence_count=eligible,
        converged_sequence_count=converged,
        mean_final_kl_shift=(statistics.fmean(final_kls) if final_kls else None),
        blockers=tuple(sorted(set(blockers))),
    )
    return summary, tuple(
        sorted(
            rows,
            key=lambda row: (
                str(row["task_condition_id"]),
                _as_int(row["round_index"]),
            ),
        )
    )


def _read_json_records(path: Path) -> tuple[object, ...]:
    if path.suffix == ".jsonl":
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    return tuple(value) if isinstance(value, list) else (value,)


def _aggregate(values: list[float]) -> AggregateMetric:
    if not values:
        raise ValueError("cannot aggregate an empty refinement metric")
    mean = statistics.fmean(values)
    standard_deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    return AggregateMetric(
        mean=mean,
        standard_deviation=standard_deviation,
        ci95_half_width=1.96 * standard_deviation / math.sqrt(len(values)),
    )


def _normalize(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0 or any(value <= 0 for value in values.values()):
        raise ValueError("fixed-potential weights must be strictly positive")
    return {key: values[key] / total for key in sorted(values)}


def _kl(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return sum(left[key] * math.log(left[key] / right[key]) for key in left)


def _projective_distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    log_ratios = [math.log(left[key] / right[key]) for key in left]
    return max(log_ratios) - min(log_ratios)


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError("refinement metric is not numeric")


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise TypeError("refinement index is not an integer")
